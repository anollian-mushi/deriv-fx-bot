"""cTrader broker adapter: the broker-neutral interface on top of fxbot.ctrader.client.

Plain-language summary for the owner:
- cTrader trades ordinary forex positions measured in units of the base currency
  (1 lot = 100,000 units). There is no Multiplier and no automatic stop out at a fixed
  stake, so the stop loss is what limits the loss. A trade without a stop loss is refused.
- quote() picks the largest size whose loss at the stop, plus the spread and the
  commission for opening and closing, stays within the amount the risk module approved.
  It always rounds the size down; if even the smallest allowed size would lose more, it
  refuses (below_minimum_size) instead of rounding up.
- The order goes out as a market order with the stop loss and take profit attached as
  distances from the fill price. Every order carries our client order id (as cTrader's
  clientOrderId and label), so after a lost reply the adapter can look the position up
  instead of sending a second order.
- Demo only: connect() refuses an account that cTrader does not report as non-live, and
  the client only knows the demo host.

Assumptions not confirmed on the wire yet (docs/ctrader_api_notes.md, section "Not verified"):
commission charged on both the open and the close at the symbol's rate; the closing deal's
closePositionDetail.commission covering the whole round trip; sl/tp distance "points" being
the symbol's price step. scripts/ctrader_lifecycle.py prints the numbers that check them.
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

import numpy as np

from fxbot.backtest.candles import Bars
from fxbot.ctrader.client import (PERIOD_SECONDS, PRICE_SCALE, TRENDBAR_PERIODS, VOLUME_SCALE,
                                  CTraderClient)
from fxbot.ctrader.codec import model
from fxbot.ctrader.errors import CTraderDisconnected, CTraderError, CTraderTimeout
from fxbot.ctrader.settings import CTraderSettings, load_ctrader_settings

from fxbot.broker.base import (AccountInfo, BrokerDisconnected, BrokerError, BrokerPosition,
                               Instrument, OrderIntent, Quote)

BELOW_MINIMUM_SIZE = "below_minimum_size"
STOP_REQUIRED = "stop_required"
STOP_TOO_CLOSE = "stop_too_close"
QUOTE_EXPIRED = "quote_expired"
WRONG_ACCOUNT_TYPE = "wrong_account_type"
NOT_FOUND = "not_found"
REJECTED = "rejected"

COMMISSION_TYPES = {1: "USD_PER_MILLION_USD", 2: "USD_PER_LOT", 3: "PERCENTAGE_OF_VALUE",
                    4: "QUOTE_CCY_PER_LOT"}
MAX_CLIENT_ORDER_ID = 50               # ProtoOANewOrderReq.clientOrderId MaxLength (label allows 100)


def project_to_broker_name(symbol: str) -> str:
    """frxEURUSD -> EURUSD."""
    return symbol[3:] if symbol.startswith("frx") else symbol


def _norm(name: str) -> str:
    return "".join(ch for ch in name.upper() if ch.isalnum())


def _broker_error(err: CTraderError) -> BrokerError:
    return BrokerError(err.category, f"{err.code}: {err.description}" if err.description else err.code,
                       retryable=err.retryable)


class CTraderBroker:
    name = "ctrader"

    def __init__(self, settings: CTraderSettings | None = None, *, client: CTraderClient | None = None,
                 quote_ttl: float = 10.0, order_timeout: float = 20.0, lookup_attempts: int = 5,
                 lookup_delay: float = 1.0, clock=time.time):
        self.settings = settings or load_ctrader_settings()
        self.settings.host                                  # raises unless CTRADER_MODE=demo
        self.client = client or CTraderClient(self.settings)
        self.quote_ttl = quote_ttl
        self.order_timeout = order_timeout
        self.lookup_attempts = lookup_attempts
        self.lookup_delay = lookup_delay
        self.clock = clock
        self._demo_verified = False
        self._account_id: int | None = None
        self._money_digits = 2
        self._currency = "?"
        self._assets: dict[int, str] = {}
        self._symbol_ids: dict[str, int] = {}       # project symbol -> symbol id
        self._light: dict[int, Any] = {}            # symbol id -> ProtoOALightSymbol
        self._details: dict[int, Any] = {}          # symbol id -> ProtoOASymbol
        self._sid_to_project: dict[int, str] = {}

    # ---------------------------------------------------------------- session

    @property
    def alive(self) -> bool:
        return self._demo_verified and self.client.ready

    async def _call(self, coro):
        """Run a client call, turning client errors into broker errors."""
        try:
            return await coro
        except CTraderError as err:
            raise _broker_error(err) from None
        except (CTraderDisconnected, CTraderTimeout) as err:
            raise BrokerDisconnected(str(err)) from None

    async def connect(self) -> AccountInfo:
        """Log in and check the account is a demo account (refuses otherwise)."""
        missing = self.settings.missing()
        if missing:
            raise BrokerError("missing_settings", "not set: " + ", ".join(missing))
        accounts = await self._call(self.client.get_accounts())
        wanted = self.settings.account_id
        if wanted is not None:
            chosen = next((a for a in accounts if a.ctidTraderAccountId == wanted), None)
            if chosen is None:
                await self.client.close()
                raise BrokerError("auth_failed", "CTRADER_ACCOUNT_ID is not one of the token's accounts")
        else:
            demos = [a for a in accounts if a.HasField("isLive") and not a.isLive]
            if not demos:
                await self.client.close()
                raise BrokerError(WRONG_ACCOUNT_TYPE, "the token has no demo account")
            chosen = demos[0]
        # The account itself must say it is not live; a missing flag is not good enough.
        if not chosen.HasField("isLive") or chosen.isLive:
            await self.client.close()
            raise BrokerError(WRONG_ACCOUNT_TYPE, "the account is live (or does not say it is demo); "
                                                  "only demo accounts are allowed")
        self._account_id = int(chosen.ctidTraderAccountId)
        await self._call(self.client.connect(self._account_id))
        trader = await self._call(self.client.trader())
        if trader.ctidTraderAccountId != self._account_id:
            raise BrokerError(WRONG_ACCOUNT_TYPE, "trader reply is for another account")
        self._assets = {a.assetId: a.name for a in await self._call(self.client.assets())}
        self._currency = self._assets.get(trader.depositAssetId, "?")
        self._money_digits = trader.moneyDigits if trader.HasField("moneyDigits") else 2
        light = await self._call(self.client.symbols())
        self._light = {s.symbolId: s for s in light}
        self._symbol_ids.clear()
        self._sid_to_project.clear()
        self._details.clear()
        self._demo_verified = True
        return await self.account()

    async def close(self) -> None:
        self._demo_verified = False
        await self.client.close()

    def _require_demo(self) -> None:
        if not self._demo_verified:
            raise BrokerError(WRONG_ACCOUNT_TYPE, "connect() has not verified a demo account")

    async def account(self) -> AccountInfo:
        self._require_demo()
        trader = await self._call(self.client.trader())
        md = trader.moneyDigits if trader.HasField("moneyDigits") else self._money_digits
        self._money_digits = md
        balance = trader.balance / 10 ** md
        pnl, _ = await self._call(self.client.unrealized_pnl())
        equity = balance + sum(net for _, net in pnl.values())
        return AccountInfo(broker=self.name, account_id=str(self._account_id), is_demo=True,
                           currency=self._currency, balance=balance, equity=equity)

    # ---------------------------------------------------------------- symbols

    def _match_symbol(self, symbol: str) -> int:
        target = _norm(project_to_broker_name(symbol))
        enabled = [s for s in self._light.values() if not s.HasField("enabled") or s.enabled]
        exact = [s for s in enabled if _norm(s.symbolName) == target]
        if len(exact) == 1:
            return exact[0].symbolId
        if len(target) == 6:          # fall back to base / quote assets (handles names like "EURUSD.m")
            base, quote = target[:3], target[3:]
            by_asset = [s for s in enabled
                        if self._assets.get(s.baseAssetId) == base and self._assets.get(s.quoteAssetId) == quote]
            if len(by_asset) == 1:
                return by_asset[0].symbolId
            if len(by_asset) > 1:
                raise BrokerError(NOT_FOUND, f"{symbol}: several cTrader symbols match: "
                                  + ", ".join(sorted(s.symbolName for s in by_asset)))
        raise BrokerError(NOT_FOUND, f"{symbol}: no cTrader symbol found")

    def symbol_id(self, symbol: str) -> int:
        self._require_demo()
        if symbol not in self._symbol_ids:
            sid = self._match_symbol(symbol)
            self._symbol_ids[symbol] = sid
            self._sid_to_project[sid] = symbol
        return self._symbol_ids[symbol]

    def _project_symbol(self, sid: int) -> str:
        if sid in self._sid_to_project:
            return self._sid_to_project[sid]
        light = self._light.get(sid)
        return "frx" + _norm(light.symbolName) if light is not None else str(sid)

    async def _symbol(self, symbol: str):
        sid = self.symbol_id(symbol)
        if sid not in self._details:
            details = await self._call(self.client.symbol_details([sid]))
            if not details:
                raise BrokerError(NOT_FOUND, f"{symbol}: no symbol details")
            self._details[sid] = details[0]
        return sid, self._details[sid]

    async def instrument(self, symbol: str) -> Instrument:
        _, d = await self._symbol(symbol)
        return Instrument(symbol=symbol, pip=10.0 ** -d.pipPosition, price_step=10.0 ** -d.digits,
                          min_size=d.minVolume / VOLUME_SCALE, size_step=d.stepVolume / VOLUME_SCALE,
                          size_unit="units")

    async def symbol_spec(self, symbol: str) -> dict:
        """Everything the backtester and the check script want to know about a symbol."""
        sid, d = await self._symbol(symbol)
        light = self._light[sid]
        rate = d.preciseTradingCommissionRate if d.HasField("preciseTradingCommissionRate") else None
        ctype = COMMISSION_TYPES.get(d.commissionType, str(d.commissionType))
        return {
            "symbol": symbol, "broker_symbol": light.symbolName, "symbol_id": sid,
            "base": self._assets.get(light.baseAssetId), "quote": self._assets.get(light.quoteAssetId),
            "digits": d.digits, "pip_position": d.pipPosition, "pip": 10.0 ** -d.pipPosition,
            "min_units": d.minVolume / VOLUME_SCALE, "step_units": d.stepVolume / VOLUME_SCALE,
            "max_units": d.maxVolume / VOLUME_SCALE if d.HasField("maxVolume") else None,
            "lot_units": d.lotSize / VOLUME_SCALE if d.HasField("lotSize") else None,
            "commission_type": ctype,
            "commission_rate": (rate / 1e5 if ctype == "PERCENTAGE_OF_VALUE" else rate / 1e8)
            if rate is not None else None,
            "min_commission": d.preciseMinCommission / 1e8 if d.HasField("preciseMinCommission") else None,
            "min_commission_type": d.minCommissionType,
            "swap_long": d.swapLong, "swap_short": d.swapShort,
            "swap_calculation_type": d.swapCalculationType,
            "swap_triple_day": d.swapRollover3Days,
            "sl_distance": d.slDistance if d.HasField("slDistance") else None,
            "distance_set_in": d.distanceSetIn,
            "trading_mode": d.tradingMode,
            "pnl_conversion_fee_rate": d.pnlConversionFeeRate if d.HasField("pnlConversionFeeRate") else None,
        }

    # ---------------------------------------------------------------- prices

    async def price(self, symbol: str) -> tuple[float, float, float]:
        sid = self.symbol_id(symbol)
        s = await self._call(self.client.spot(sid))
        return s.bid, s.ask, s.epoch

    async def candles(self, symbol: str, timeframe: str, count: int) -> Bars:
        """Last `count` closed candles, oldest first. cTrader trendbars (the docs do not say which
        side of the quote they are built from; cTrader charts default to bid)."""
        period = TRENDBAR_PERIODS.get(timeframe)
        if period is None:
            raise BrokerError("invalid_request", f"timeframe {timeframe!r} not offered")
        tf = PERIOD_SECONDS[period]
        sid = self.symbol_id(symbol)
        now = self.clock()
        span = (count + 2) * tf * 1.5 + 4 * 86400           # room for weekends and holidays
        bars = await self._call(self.client.trendbars(sid, period, int((now - span) * 1000), int(now * 1000),
                                                      count + 1))
        closed = [b for b in bars if b["epoch"] + tf <= now][-count:]
        arr = lambda key: np.array([b[key] for b in closed], dtype=float)  # noqa: E731
        epoch = np.array([b["epoch"] for b in closed], dtype=np.int64)
        return Bars(epoch=epoch, end=epoch + tf, open=arr("open"), high=arr("high"), low=arr("low"),
                    close=arr("close"))

    async def _usd_per_quote_unit(self, quote_ccy: str, worst_pair_price: float, base_ccy: str) -> float:
        """USD value of one unit of the quote currency, taken on the side that makes a loss larger."""
        if quote_ccy == "USD":
            return 1.0
        if base_ccy == "USD":                       # USD/JPY: JPY -> USD at the pair's own (lowest) price
            return 1.0 / worst_pair_price
        for name, invert in ((quote_ccy + "USD", False), ("USD" + quote_ccy, True)):
            try:
                sid = self._match_symbol("frx" + name)
            except BrokerError:
                continue
            s = await self._call(self.client.spot(sid))
            return 1.0 / s.bid if invert else s.ask
        raise BrokerError("no_conversion", f"no symbol to convert {quote_ccy} to USD")

    # ---------------------------------------------------------------- quote / open

    def _commission_per_side(self, d, units: float, notional_usd: float, q2usd: float) -> tuple[float, float]:
        """(USD per unit, minimum USD per side) for one side of a trade (open or close)."""
        rate = d.preciseTradingCommissionRate if d.HasField("preciseTradingCommissionRate") else 0
        lot_units = (d.lotSize / VOLUME_SCALE) if d.HasField("lotSize") and d.lotSize else 100_000.0
        usd_per_unit_value = notional_usd / units if units else 0.0
        ctype = d.commissionType
        if ctype == 1:                                  # USD per million USD of volume
            per_unit = rate / 1e8 / 1e6 * usd_per_unit_value
        elif ctype == 2:                                # USD per lot
            per_unit = rate / 1e8 / lot_units
        elif ctype == 3:                                # percent of value, rate x 10^5
            per_unit = rate / 1e5 / 100 * usd_per_unit_value
        elif ctype == 4:                                # quote currency per lot
            per_unit = rate / 1e8 / lot_units * q2usd
        else:
            raise BrokerError("unsupported_commission", f"commission type {ctype}")
        minimum = d.preciseMinCommission / 1e8 if d.HasField("preciseMinCommission") else 0.0
        if minimum and d.minCommissionType == 2:        # QUOTE_CURRENCY
            minimum *= q2usd
        return per_unit, minimum

    async def quote(self, intent: OrderIntent) -> Quote:
        self._require_demo()
        if intent.direction not in ("up", "down"):
            raise BrokerError("invalid_request", f"direction {intent.direction!r}")
        if intent.stop_loss_pips is None or not intent.stop_loss_pips > 0:
            raise BrokerError(STOP_REQUIRED, "a cTrader trade needs a stop loss: it is what caps the loss")
        if not intent.max_loss_usd > 0:
            raise BrokerError(BELOW_MINIMUM_SIZE, "max_loss_usd must be positive")
        if len(intent.client_order_id) > MAX_CLIENT_ORDER_ID or not intent.client_order_id:
            raise BrokerError("invalid_request", f"client_order_id must be 1-{MAX_CLIENT_ORDER_ID} characters")
        if self._currency != "USD":
            raise BrokerError("unsupported_account_currency", f"account currency {self._currency}; USD expected")
        sid, d = await self._symbol(intent.symbol)
        if d.tradingMode != model.ENABLED:
            raise BrokerError(REJECTED, f"{intent.symbol}: trading mode {d.tradingMode} (not enabled)")
        light = self._light[sid]
        base, quote_ccy = self._assets.get(light.baseAssetId, "?"), self._assets.get(light.quoteAssetId, "?")
        pip = 10.0 ** -d.pipPosition
        step = 10.0 ** -d.digits
        spot = await self._call(self.client.spot(sid))
        bid, ask = spot.bid, spot.ask
        if not (bid > 0 and ask >= bid):
            raise BrokerError(REJECTED, f"{intent.symbol}: no usable price (bid {bid}, ask {ask})")
        spread = ask - bid
        up = intent.direction == "up"
        entry = ask if up else bid
        sl_steps = max(1, round(intent.stop_loss_pips * pip / step))
        sl_dist = sl_steps * step
        min_dist = None
        if d.HasField("slDistance") and d.slDistance:
            if d.distanceSetIn == model.SYMBOL_DISTANCE_IN_PERCENTAGE:
                min_dist = None   # scaling not documented; the server still checks it
            else:
                min_dist = d.slDistance * step
        if min_dist is not None and sl_dist < min_dist:
            raise BrokerError(STOP_TOO_CLOSE, f"stop {sl_dist:g} is closer than the minimum {min_dist:g}")
        tp_dist = None
        if intent.take_profit_pips is not None and intent.take_profit_pips > 0:
            tp_dist = max(1, round(intent.take_profit_pips * pip / step)) * step
        sl_price = round(entry - sl_dist if up else entry + sl_dist, d.digits)
        tp_price = round(entry + tp_dist if up else entry - tp_dist, d.digits) if tp_dist else None

        worst_pair_price = min(bid, ask, sl_price)
        q2usd = await self._usd_per_quote_unit(quote_ccy, worst_pair_price, base)
        mid = (bid + ask) / 2
        b2usd = 1.0 if base == "USD" else mid * q2usd
        comm_unit, comm_min = self._commission_per_side(d, 1.0, b2usd, q2usd)

        # loss(u) = u * (sl_dist + spread) * q2usd + 2 * max(comm_min, u * comm_unit)
        # The spread term is a buffer for a fill worse than the quoted price.
        price_loss_unit = (sl_dist + spread) * q2usd
        cap = intent.max_loss_usd
        u_lin = cap / (price_loss_unit + 2 * comm_unit)
        u_min = (cap - 2 * comm_min) / price_loss_unit if comm_min else math.inf
        units = min(u_lin, u_min)
        step_vol, min_vol = d.stepVolume, d.minVolume
        max_vol = d.maxVolume if d.HasField("maxVolume") and d.maxVolume else None

        def loss(vol_cents: int) -> float:
            u = vol_cents / VOLUME_SCALE
            return u * price_loss_unit + 2 * max(comm_min, u * comm_unit)

        vol = int(math.floor(units * VOLUME_SCALE / step_vol + 1e-9)) * step_vol if units > 0 else 0
        if max_vol is not None:
            vol = min(vol, (max_vol // step_vol) * step_vol)
        while vol > 0 and loss(vol) > cap + 1e-9:
            vol -= step_vol
        if vol < min_vol or vol <= 0:
            need = loss(min_vol)
            raise BrokerError(BELOW_MINIMUM_SIZE, f"{intent.symbol}: the minimum size "
                              f"({min_vol / VOLUME_SCALE:g} units) would lose {need:.2f} USD at the stop, "
                              f"more than the allowed {cap:.2f} USD")
        size = vol / VOLUME_SCALE
        comm_side = max(comm_min, size * comm_unit)
        spread_usd = size * spread * q2usd
        cost_usd = spread_usd + 2 * comm_side
        notional_usd = size * b2usd
        pip_value_usd = size * pip * q2usd
        now = self.clock()
        raw = {
            "symbol_id": sid, "broker_symbol": light.symbolName, "side": "BUY" if up else "SELL",
            "volume": vol, "relative_stop_loss": int(round(sl_dist * PRICE_SCALE)),
            "relative_take_profit": int(round(tp_dist * PRICE_SCALE)) if tp_dist else None,
            "bid": bid, "ask": ask, "spread": spread, "usd_per_quote_unit": q2usd,
            "commission_per_side_usd": comm_side, "spread_usd": spread_usd,
            "commission_type": COMMISSION_TYPES.get(d.commissionType, str(d.commissionType)),
            "quoted_at": now, "label": intent.client_order_id,
        }
        return Quote(intent=intent, price=entry, size=size, cost_usd=cost_usd,
                     cost_pips=cost_usd / pip_value_usd, cost_rate=cost_usd / notional_usd,
                     stop_loss_price=sl_price, take_profit_price=tp_price,
                     worst_case_loss_usd=loss(vol), expires_epoch=now + self.quote_ttl, raw=raw)

    async def _find_by_label(self, label: str, since_epoch: float | None) -> BrokerPosition | None:
        rec = await self._call(self.client.reconcile())
        for p in rec.position:
            if p.tradeData.label == label:
                pnl, _ = await self._call(self.client.unrealized_pnl())
                return self._from_open(p, pnl)
        if since_epoch is not None:            # opened and already closed (e.g. stop hit at once)
            deals = await self._call(self.client.deals(int((since_epoch - 120) * 1000),
                                                       int((self.clock() + 60) * 1000)))
            for d in deals:
                if d.label == label and d.dealStatus in (model.FILLED, model.PARTIALLY_FILLED):
                    return await self.position(str(d.positionId))
        return None

    async def _order_in_flight(self, label: str) -> bool:
        rec = await self._call(self.client.reconcile())
        return any(o.clientOrderId == label or o.tradeData.label == label for o in rec.order)

    async def open(self, quote: Quote) -> BrokerPosition:
        """Idempotent on the client order id: if a position with it exists, that one is returned."""
        self._require_demo()
        if self.clock() > quote.expires_epoch:
            raise BrokerError(QUOTE_EXPIRED, "quote is older than its time limit; ask for a new one")
        raw = quote.raw
        label = quote.intent.client_order_id
        if raw.get("relative_stop_loss") in (None, 0):
            raise BrokerError(STOP_REQUIRED, "quote has no stop loss")
        existing = await self._find_by_label(label, raw.get("quoted_at"))
        if existing is not None:
            return existing
        try:
            env = await self.client.new_market_order(
                raw["symbol_id"], raw["side"], raw["volume"],
                relative_stop_loss=raw["relative_stop_loss"], relative_take_profit=raw.get("relative_take_profit"),
                label=label, client_order_id=label, comment="fxbot", timeout=self.order_timeout)
        except CTraderError as err:
            raise _broker_error(err) from None
        except (CTraderDisconnected, CTraderTimeout):
            return await self._recover_open(label, raw.get("quoted_at"))
        pos = await self._position_after_fill(env)
        return await self._ensure_stop(pos, quote)

    async def _recover_open(self, label: str, since: float | None) -> BrokerPosition:
        """The reply was lost: find out whether the order went through, without sending it again."""
        last: Exception | None = None
        for attempt in range(self.lookup_attempts):
            if attempt:
                await asyncio.sleep(self.lookup_delay)
            try:
                await self.client.ensure_ready()
                found = await self._find_by_label(label, since)
                if found is not None:
                    return found
                if not await self._order_in_flight(label) and attempt >= 1:
                    break
            except (CTraderDisconnected, CTraderTimeout, BrokerDisconnected) as err:
                last = err
                continue
        if last is not None:
            raise BrokerDisconnected(f"order outcome unknown, connection still down: {last}")
        raise BrokerError("not_filled", "the order reply was lost and no position with this client order "
                                        "id exists; it was not filled", retryable=True)

    async def _position_after_fill(self, env) -> BrokerPosition:
        m = env.message
        pid = m.position.positionId if m.HasField("position") else m.deal.positionId
        pos = None
        for _ in range(3):
            try:
                pos = await self.position(str(pid))
                break
            except BrokerError as err:
                if err.code != NOT_FOUND:
                    raise
                await asyncio.sleep(0.2)
        if pos is None:
            raise BrokerError(NOT_FOUND, f"position {pid} filled but not visible yet")
        return pos

    async def _ensure_stop(self, pos: BrokerPosition, quote: Quote) -> BrokerPosition:
        """A filled position must have its stop loss. If the server did not attach it, set it now;
        if that fails, close the position rather than leave it unprotected."""
        if not pos.is_open or pos.stop_loss_price is not None:
            return pos
        dist = quote.raw["relative_stop_loss"] / PRICE_SCALE
        sl = pos.entry_price - dist if pos.direction == "up" else pos.entry_price + dist
        try:
            return await self.modify(pos.ref, stop_loss_price=sl, take_profit_price=pos.take_profit_price)
        except Exception:
            await self.close_position(pos.ref)
            raise BrokerError("stop_not_set", "the stop loss could not be attached; the position was closed")

    # ---------------------------------------------------------------- positions

    def _scale(self, md: int | None) -> float:
        return 10.0 ** (md if md else self._money_digits)

    def _from_open(self, p, pnl: dict) -> BrokerPosition:
        td = p.tradeData
        scale = self._scale(p.moneyDigits if p.HasField("moneyDigits") else None)
        commission = abs(p.commission) / scale if p.HasField("commission") else 0.0
        return BrokerPosition(
            ref=str(p.positionId), symbol=self._project_symbol(td.symbolId),
            direction="up" if td.tradeSide == model.BUY else "down", size=td.volume / VOLUME_SCALE,
            entry_price=p.price, entry_epoch=td.openTimestamp / 1000 if td.HasField("openTimestamp") else 0.0,
            stop_loss_price=p.stopLoss if p.HasField("stopLoss") else None,
            take_profit_price=p.takeProfit if p.HasField("takeProfit") else None,
            open_profit_usd=pnl.get(p.positionId, (0.0, 0.0))[1], is_open=True,
            client_order_id=td.label or None, cost_usd=commission - p.swap / scale)

    async def positions(self) -> list[BrokerPosition]:
        self._require_demo()
        rec = await self._call(self.client.reconcile())
        pnl, _ = await self._call(self.client.unrealized_pnl()) if rec.position else ({}, 0)
        return [self._from_open(p, pnl) for p in rec.position]

    async def _close_reason(self, closing_deal, direction: str, entry: float) -> str:
        try:
            order, _ = await self._call(self.client.order_details(closing_deal.orderId))
        except BrokerError:
            return "broker"
        if order.isStopOut:
            return "stop_out"
        if order.orderType == model.STOP_LOSS_TAKE_PROFIT:
            exit_price = closing_deal.executionPrice
            sl = order.stopLoss if order.HasField("stopLoss") else None
            tp = order.takeProfit if order.HasField("takeProfit") else None
            if sl is not None and tp is not None:
                return "stop_loss" if abs(exit_price - sl) <= abs(exit_price - tp) else "take_profit"
            if sl is not None and tp is None:
                return "stop_loss"
            if tp is not None and sl is None:
                return "take_profit"
            gain = exit_price - entry if direction == "up" else entry - exit_price
            return "take_profit" if gain > 0 else "stop_loss"
        if order.orderType == model.MARKET and order.closingOrder:
            return "closed"
        return "broker"

    async def position(self, ref: str) -> BrokerPosition:
        self._require_demo()
        pid = int(ref)
        rec = await self._call(self.client.reconcile())
        for p in rec.position:
            if p.positionId == pid:
                pnl, _ = await self._call(self.client.unrealized_pnl())
                return self._from_open(p, pnl)
        deals = await self._call(self.client.deals_for_position(pid))
        deals = [d for d in deals if d.dealStatus in (model.FILLED, model.PARTIALLY_FILLED)]
        if not deals:
            raise BrokerError(NOT_FOUND, f"position {ref} not found")
        opening = [d for d in deals if not d.HasField("closePositionDetail")]
        closing = [d for d in deals if d.HasField("closePositionDetail")]
        first = opening[0] if opening else deals[0]
        direction = "up" if first.tradeSide == model.BUY else "down"
        opened = sum(d.filledVolume for d in opening)
        closed = sum(d.closePositionDetail.closedVolume if d.closePositionDetail.HasField("closedVolume")
                     else d.filledVolume for d in closing)
        entry = (closing[0].closePositionDetail.entryPrice if closing
                 else sum(d.executionPrice * d.filledVolume for d in opening) / max(opened, 1))
        symbol = self._project_symbol(first.symbolId)
        if not closing or (opened and closed < opened):
            return BrokerPosition(ref=ref, symbol=symbol, direction=direction, size=(opened - closed) / VOLUME_SCALE,
                                  entry_price=entry, entry_epoch=first.executionTimestamp / 1000,
                                  stop_loss_price=None, take_profit_price=None, open_profit_usd=0.0,
                                  is_open=True, client_order_id=first.label or None)
        profit = 0.0
        costs = 0.0
        for d in closing:
            c = d.closePositionDetail
            scale = self._scale(c.moneyDigits if c.HasField("moneyDigits") else None)
            fee = abs(c.pnlConversionFee) / scale if c.HasField("pnlConversionFee") else 0.0
            profit += (c.grossProfit + c.swap + c.commission) / scale - fee
            costs += abs(c.commission) / scale - c.swap / scale + fee
        last = closing[-1]
        return BrokerPosition(
            ref=ref, symbol=symbol, direction=direction, size=(opened or closed) / VOLUME_SCALE,
            entry_price=entry, entry_epoch=first.executionTimestamp / 1000, stop_loss_price=None,
            take_profit_price=None, open_profit_usd=0.0, is_open=False, exit_price=last.executionPrice,
            exit_epoch=last.executionTimestamp / 1000, profit_usd=round(profit, 8),
            close_reason=await self._close_reason(last, direction, entry),
            client_order_id=first.label or None, cost_usd=round(costs, 8))

    async def modify(self, ref: str, *, stop_loss_price: float | None = None,
                     take_profit_price: float | None = None) -> BrokerPosition:
        """Move the stop loss and/or take profit. The stop can be moved closer to the price (less
        risk) but never further away than it is: that would raise the risk the risk module approved.
        A value left as None keeps the current one (the stop loss is never removed)."""
        self._require_demo()
        pos = await self.position(ref)
        if not pos.is_open:
            raise BrokerError(NOT_FOUND, f"position {ref} is closed")
        _, d = await self._symbol(pos.symbol)
        sl = pos.stop_loss_price if stop_loss_price is None else round(stop_loss_price, d.digits)
        tp = pos.take_profit_price if take_profit_price is None else round(take_profit_price, d.digits)
        if sl is None:
            raise BrokerError(STOP_REQUIRED, "the position has no stop loss and none was given")
        cur = pos.stop_loss_price
        tick = 10.0 ** -d.digits / 2
        if cur is not None and ((pos.direction == "up" and sl < cur - tick)
                                or (pos.direction == "down" and sl > cur + tick)):
            raise BrokerError("stop_widening_refused", f"moving the stop from {cur} to {sl} adds risk")
        await self._call(self.client.amend_position_sltp(int(ref), sl, tp))
        return await self.position(ref)

    async def close_position(self, ref: str) -> BrokerPosition:
        self._require_demo()
        pos = await self.position(ref)
        if not pos.is_open:
            return pos
        try:
            await self.client.close_position(int(ref), int(round(pos.size * VOLUME_SCALE)))
        except CTraderError as err:
            if err.category != "not_found":
                raise _broker_error(err) from None
        except (CTraderDisconnected, CTraderTimeout):
            await self._call(self.client.ensure_ready())     # then read what actually happened
        for _ in range(5):
            pos = await self.position(ref)
            if not pos.is_open:
                return pos
            await asyncio.sleep(0.2)
        return pos

    async def history(self, since_epoch: float) -> list[BrokerPosition]:
        self._require_demo()
        deals = await self._call(self.client.deals(int(since_epoch * 1000), int((self.clock() + 60) * 1000)))
        ids = []
        for d in deals:
            if d.HasField("closePositionDetail") and d.positionId not in ids:
                ids.append(d.positionId)
        out = []
        for pid in ids:
            p = await self.position(str(pid))
            if not p.is_open:
                out.append(p)
        return sorted(out, key=lambda p: p.exit_epoch or 0)
