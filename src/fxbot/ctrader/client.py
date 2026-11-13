"""asyncio client for the cTrader Open API (Protobuf over TLS, port 5035).

Why Protobuf and not the JSON port (5036): the official .proto files define every field,
enum and integer type exactly, so the bytes we send and parse follow a published schema.
The JSON variant is documented only as an envelope ({clientMsgId, payloadType, payload});
how it writes enums and 64-bit integers is not documented, and we could not see it on the
wire without credentials. Protobuf also lets the fake test server speak exactly the same
bytes as the real one. Cost: one pinned dependency (protobuf) and generated code in proto/.

Session flow (from the docs): open TLS -> ProtoOAApplicationAuthReq (client id + secret)
-> ProtoOAGetAccountListByAccessTokenReq (optional, lists the token's accounts and whether
each is live) -> ProtoOAAccountAuthReq (account id + token) -> requests for that account.
Keep-alive: send ProtoHeartbeatEvent every 10 s. Requests carry a clientMsgId that the server
returns on its reply; that is how replies are matched to requests here.

After a drop the client reconnects, authorises the application and the account again and
re-subscribes to the spot prices it had. Requests that were waiting fail with
CTraderDisconnected: the caller decides whether to repeat them (the broker adapter checks
first whether an order went through; see fxbot.broker.ctrader).

Secrets: the client secret and access token are only ever put into the auth messages. They
are never logged and never part of an exception text.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import ssl as ssl_module
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from google.protobuf.message import Message

from fxbot.ctrader import codec
from fxbot.ctrader.codec import PT, Envelope, model, oa
from fxbot.ctrader.errors import CTraderDisconnected, CTraderError, CTraderTimeout
from fxbot.ctrader.settings import CTraderSettings

log = logging.getLogger("fxbot.ctrader")

PRICE_SCALE = 100_000                 # spot prices, trendbars and relative SL/TP are in 1/100000 of a price unit
VOLUME_SCALE = 100                    # volumes are in 0.01 of a unit ("cents")

TRENDBAR_PERIODS = {"1m": "M1", "2m": "M2", "3m": "M3", "4m": "M4", "5m": "M5", "10m": "M10",
                    "15m": "M15", "30m": "M30", "1h": "H1", "4h": "H4", "12h": "H12", "1d": "D1",
                    "1w": "W1"}
PERIOD_SECONDS = {"M1": 60, "M2": 120, "M3": 180, "M4": 240, "M5": 300, "M10": 600, "M15": 900,
                  "M30": 1800, "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400, "W1": 604800}

EXEC = model.ProtoOAExecutionType
_ERROR_TYPES = (PT["ERROR_RES"], PT["PROTO_OA_ERROR_RES"], PT["PROTO_OA_ORDER_ERROR_EVENT"])


def enum_name(enum, value: int) -> str:
    try:
        return enum.Name(value)
    except ValueError:
        return str(value)


def error_of(env: Envelope) -> CTraderError | None:
    """The CTraderError an envelope carries, if it is an error reply or a rejected execution."""
    m = env.message
    if m is None:
        return None
    if env.payload_type == PT["ERROR_RES"]:
        end = m.maintenanceEndTimestamp / 1000 if m.HasField("maintenanceEndTimestamp") else None
        return CTraderError(m.errorCode, m.description, maintenance_end=end)
    if env.payload_type == PT["PROTO_OA_ERROR_RES"]:
        return CTraderError(m.errorCode, m.description,
                            retry_after=float(m.retryAfter) if m.HasField("retryAfter") else None,
                            maintenance_end=float(m.maintenanceEndTimestamp)
                            if m.HasField("maintenanceEndTimestamp") else None)
    if env.payload_type == PT["PROTO_OA_ORDER_ERROR_EVENT"]:
        return CTraderError(m.errorCode, m.description)
    if env.payload_type == PT["PROTO_OA_EXECUTION_EVENT"] and m.executionType in (
            EXEC.ORDER_REJECTED, EXEC.ORDER_CANCEL_REJECTED):
        reason = m.deal.rejectReason if m.HasField("deal") and m.deal.HasField("rejectReason") else ""
        return CTraderError(m.errorCode or "ORDER_REJECTED", reason or enum_name(EXEC, m.executionType))
    return None


def is_execution(env: Envelope, *types: int) -> bool:
    return (env.payload_type == PT["PROTO_OA_EXECUTION_EVENT"] and env.message is not None
            and (not types or env.message.executionType in types))


@dataclass
class _Waiter:
    """Collects the replies to one request until `done` says the request is finished."""
    done: Callable[[Envelope], bool]
    match: Callable[[Envelope], bool] | None
    future: asyncio.Future
    seen: list[Envelope] = field(default_factory=list)

    def offer(self, env: Envelope) -> None:
        if self.future.done():
            return
        self.seen.append(env)
        err = error_of(env)
        if err is not None:
            self.future.set_exception(err)
        elif self.done(env):
            self.future.set_result(env)


@dataclass
class Spot:
    bid: float
    ask: float
    epoch: float                      # server time when sent with the event, else our receive time


class CTraderClient:
    def __init__(self, settings: CTraderSettings | None = None, *, host: str | None = None,
                 port: int | None = None, ssl: bool | ssl_module.SSLContext = True,
                 proxy: str | None = "env", heartbeat_interval: float = 10.0,
                 dead_after: float = 60.0, request_timeout: float = 20.0,
                 connect_timeout: float = 20.0, auto_reconnect: bool = True,
                 reconnect_delays: Iterable[float] = (1, 2, 5, 10, 20, 30),
                 clock: Callable[[], float] = time.time):
        self.settings = settings
        self.host = host or (settings.host if settings else None)
        self.port = port or (settings.port if settings else None)
        if not self.host or not self.port:
            raise ValueError("host and port are needed (or settings)")
        self._ssl = ssl
        self._proxy = self._proxy_for(self.host) if proxy == "env" else proxy
        self.heartbeat_interval = heartbeat_interval
        self.dead_after = dead_after
        self.request_timeout = request_timeout
        self.connect_timeout = connect_timeout
        self.auto_reconnect = auto_reconnect
        self.reconnect_delays = tuple(reconnect_delays)
        self.clock = clock

        self.account_id: int | None = settings.account_id if settings else None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._tasks: list[asyncio.Task] = []
        self._pending: dict[str, _Waiter] = {}
        self._ids = itertools.count(1)
        self._send_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task | None = None
        self._closing = False
        self._connected = False
        self._app_authed = False
        self._account_authed = False
        self._last_rx = 0.0
        self.spots: dict[int, Spot] = {}
        self._spot_subs: set[int] = set()
        self._spot_events: dict[int, asyncio.Event] = {}
        self.listeners: list[Callable[[Envelope], Any]] = []   # every unsolicited event (execution, spot, ...)
        self.connects = 0             # how many times a session was established (1 + reconnects)
        self.last_disconnect_reason: str | None = None

    # ---------------------------------------------------------------- connection

    @staticmethod
    def _proxy_for(host: str) -> str | None:
        """HTTPS proxy from the environment (cloud sessions); None on a plain VPS."""
        proxies = urllib.request.getproxies_environment()
        url = proxies.get("https")
        if not url or urllib.request.proxy_bypass_environment(host):
            return None
        return url

    @property
    def alive(self) -> bool:
        return self._connected and self._writer is not None and not self._writer.is_closing()

    @property
    def ready(self) -> bool:
        """Connected and the account (if one is set) is authorised."""
        return self.alive and self._app_authed and (self.account_id is None or self._account_authed)

    def _ssl_context(self) -> ssl_module.SSLContext | None:
        if self._ssl is False:
            return None
        if isinstance(self._ssl, ssl_module.SSLContext):
            return self._ssl
        return ssl_module.create_default_context()

    async def _open_transport(self) -> None:
        ctx = self._ssl_context()
        if self._proxy:
            p = urlparse(self._proxy)
            reader, writer = await asyncio.open_connection(p.hostname, p.port or 80)
            writer.write(f"CONNECT {self.host}:{self.port} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\n\r\n"
                         .encode())
            await writer.drain()
            head = await reader.readuntil(b"\r\n\r\n")
            status = head.split(b"\r\n", 1)[0].decode(errors="replace")
            if " 200" not in status:
                writer.close()
                raise CTraderDisconnected(f"proxy refused the tunnel: {status}")
            if ctx is not None:
                await writer.start_tls(ctx, server_hostname=self.host)
        else:
            reader, writer = await asyncio.open_connection(
                self.host, self.port, ssl=ctx, server_hostname=self.host if ctx else None)
        self._reader, self._writer = reader, writer

    async def open(self) -> None:
        """Open the connection and start the reader and heartbeat tasks (no authorisation)."""
        self._closing = False
        try:
            await asyncio.wait_for(self._open_transport(), self.connect_timeout)
        except (OSError, asyncio.TimeoutError, ssl_module.SSLError) as err:
            raise CTraderDisconnected(f"could not connect to {self.host}:{self.port}: "
                                      f"{type(err).__name__}: {err}") from None
        self._connected = True
        self._app_authed = self._account_authed = False
        self._last_rx = time.monotonic()
        self._tasks = [asyncio.create_task(self._read_loop(), name="ctrader-read"),
                       asyncio.create_task(self._heartbeat_loop(), name="ctrader-heartbeat")]

    async def connect(self, account_id: int | None = None) -> None:
        """Open, authorise the application and (when an account id is known) the account."""
        async with self._connect_lock:
            if account_id is not None:
                self.account_id = account_id
            if self.ready:
                return
            if self.alive and self._app_authed and self.account_id is not None:
                # only the account session is missing (first login, or the server ended it)
                await self.account_auth(self.account_id)
                await self._resubscribe()
                self.connects += 1
                return
            await self._teardown("reconnect")
            await self.open()
            await self.application_auth()
            if self.account_id is not None:
                await self.account_auth(self.account_id)
                await self._resubscribe()
            self.connects += 1

    async def _resubscribe(self) -> None:
        if self._spot_subs:
            ids = sorted(self._spot_subs)
            self._spot_subs.clear()
            await self.subscribe_spots(ids)

    async def reconnect(self) -> None:
        """Connect again with back-off. Raises CTraderDisconnected when every attempt failed,
        CTraderError when the server refuses the credentials (no point retrying those)."""
        last: Exception | None = None
        for delay in (0.0, *self.reconnect_delays):
            if self._closing:
                raise CTraderDisconnected("client closed")
            if delay:
                await asyncio.sleep(delay)
            try:
                await self.connect()
                return
            except CTraderError as err:
                if not err.retryable:
                    raise
                last = err
            except (CTraderDisconnected, CTraderTimeout, OSError) as err:
                last = err
        raise CTraderDisconnected(f"reconnect failed: {last}")

    async def ensure_ready(self) -> None:
        if self.ready:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            try:
                await asyncio.shield(self._reconnect_task)
            except Exception:
                pass
            if self.ready:
                return
        if self._closing:
            raise CTraderDisconnected("client closed")
        await self.reconnect()

    async def close(self) -> None:
        self._closing = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
        await self._teardown("closed by us")

    async def _teardown(self, reason: str) -> None:
        self._connected = False
        self._app_authed = self._account_authed = False
        current = asyncio.current_task()
        for t in self._tasks:
            if t is not current:
                t.cancel()
        self._tasks = []
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
        self._writer = self._reader = None
        self._fail_pending(CTraderDisconnected(f"connection closed ({reason})"))

    def _fail_pending(self, err: Exception) -> None:
        for waiter in list(self._pending.values()):
            if not waiter.future.done():
                waiter.future.set_exception(err)
        self._pending.clear()

    def _on_lost(self, reason: str) -> None:
        """Called from the reader when the server or the network ends the connection."""
        if not self._connected:
            return
        self.last_disconnect_reason = reason
        log.warning("cTrader connection lost: %s", reason)
        self._connected = False
        self._app_authed = self._account_authed = False
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
        self._fail_pending(CTraderDisconnected(f"connection lost ({reason})"))
        for t in self._tasks:
            if t is not asyncio.current_task():
                t.cancel()
        if self.auto_reconnect and not self._closing:
            self._reconnect_task = asyncio.create_task(self._background_reconnect())

    async def _background_reconnect(self) -> None:
        try:
            await self.reconnect()
            log.info("cTrader reconnected")
        except Exception as err:      # the next request will try again and raise to its caller
            log.error("cTrader reconnect failed: %s", type(err).__name__)

    # ---------------------------------------------------------------- I/O loops

    async def send(self, msg: Message, client_msg_id: str | None = None) -> None:
        if not self.alive:
            raise CTraderDisconnected("not connected")
        frame = codec.encode(msg, client_msg_id)
        async with self._send_lock:
            try:
                self._writer.write(frame)
                await self._writer.drain()
            except (OSError, RuntimeError) as err:
                self._on_lost(f"send failed: {type(err).__name__}")
                raise CTraderDisconnected("send failed") from None

    async def _read_loop(self) -> None:
        reader = self._reader
        try:
            while True:
                body = await codec.read_frame(reader)
                self._last_rx = time.monotonic()
                try:
                    env = codec.decode(body)
                except codec.DecodeError:
                    log.error("cTrader: undecodable message of %d bytes", len(body))
                    continue
                self._dispatch(env)
        except asyncio.CancelledError:
            raise
        except asyncio.IncompleteReadError:
            self._on_lost("server closed the connection")
        except (OSError, codec.FrameError, ssl_module.SSLError) as err:
            self._on_lost(f"{type(err).__name__}")

    async def _heartbeat_loop(self) -> None:
        hb = codec.common.ProtoHeartbeatEvent()
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            if time.monotonic() - self._last_rx > self.dead_after:
                self._on_lost(f"nothing received for {self.dead_after:.0f} s")
                return
            try:
                await self.send(hb)
            except CTraderDisconnected:
                return

    def _dispatch(self, env: Envelope) -> None:
        pt = env.payload_type
        if pt == PT["HEARTBEAT_EVENT"]:
            return
        if env.client_msg_id is not None and env.client_msg_id in self._pending:
            waiter = self._pending[env.client_msg_id]
            waiter.offer(env)
            if waiter.future.done():
                self._pending.pop(env.client_msg_id, None)
            if pt != PT["PROTO_OA_EXECUTION_EVENT"]:
                return
        else:
            # Execution events for our orders may come without our clientMsgId; match them by content.
            for cid, waiter in list(self._pending.items()):
                if waiter.match is not None and waiter.match(env):
                    waiter.offer(env)
                    if waiter.future.done():
                        self._pending.pop(cid, None)
        m = env.message
        if pt == PT["PROTO_OA_SPOT_EVENT"] and m is not None:
            self._on_spot(m)
        elif pt == PT["PROTO_OA_CLIENT_DISCONNECT_EVENT"]:
            self._on_lost(f"server ended the session: {m.reason if m is not None else ''}")
            return
        elif pt in (PT["PROTO_OA_ACCOUNT_DISCONNECT_EVENT"], PT["PROTO_OA_ACCOUNTS_TOKEN_INVALIDATED_EVENT"]):
            log.warning("cTrader: account session ended by the server (%s)", env.name)
            self._account_authed = False
        elif pt in _ERROR_TYPES and env.client_msg_id is None:
            err = error_of(env)
            log.warning("cTrader error without a request id: %s", err)
        for listener in list(self.listeners):
            try:
                listener(env)
            except Exception:
                log.exception("cTrader listener failed")

    def _on_spot(self, m) -> None:
        old = self.spots.get(m.symbolId)
        bid = m.bid / PRICE_SCALE if m.HasField("bid") else (old.bid if old else float("nan"))
        ask = m.ask / PRICE_SCALE if m.HasField("ask") else (old.ask if old else float("nan"))
        epoch = m.timestamp / 1000 if m.HasField("timestamp") else self.clock()
        self.spots[m.symbolId] = Spot(bid, ask, epoch)
        ev = self._spot_events.get(m.symbolId)
        if ev is not None:
            ev.set()

    # ---------------------------------------------------------------- requests

    async def request(self, msg: Message, *, timeout: float | None = None,
                      done: Callable[[Envelope], bool] | None = None,
                      match: Callable[[Envelope], bool] | None = None,
                      needs_auth: bool = True) -> Envelope:
        """Send msg and wait for its reply (or, with `done`, for the reply that finishes it).

        Raises CTraderError on an error reply, CTraderTimeout when nothing final arrives in
        time, CTraderDisconnected when the connection drops while waiting."""
        if needs_auth:
            await self.ensure_ready()
        elif not self.alive:
            raise CTraderDisconnected("not connected")
        cid = f"fx{next(self._ids)}"
        fut = asyncio.get_running_loop().create_future()
        waiter = _Waiter(done or (lambda env: True), match, fut)
        self._pending[cid] = waiter
        try:
            await self.send(msg, cid)
            return await asyncio.wait_for(asyncio.shield(fut), timeout or self.request_timeout)
        except asyncio.TimeoutError:
            raise CTraderTimeout(f"no reply to {type(msg).__name__} within "
                                 f"{timeout or self.request_timeout:.0f} s") from None
        finally:
            self._pending.pop(cid, None)
            if not fut.done():
                fut.cancel()

    async def application_auth(self) -> None:
        s = self.settings
        if s is None or not s.client_id or not s.client_secret:
            raise CTraderError("MISSING_SETTINGS", "CTRADER_CLIENT_ID and CTRADER_CLIENT_SECRET are needed")
        await self.request(oa.ProtoOAApplicationAuthReq(clientId=s.client_id, clientSecret=s.client_secret),
                           needs_auth=False)
        self._app_authed = True

    async def account_auth(self, account_id: int) -> None:
        s = self.settings
        if s is None or not s.access_token:
            raise CTraderError("MISSING_SETTINGS", "CTRADER_ACCESS_TOKEN is needed")
        res = await self.request(oa.ProtoOAAccountAuthReq(ctidTraderAccountId=account_id,
                                                          accessToken=s.access_token), needs_auth=False)
        if res.message.ctidTraderAccountId != account_id:
            raise CTraderError("ACCOUNT_MISMATCH", "the server authorised a different account")
        self.account_id = account_id
        self._account_authed = True

    async def get_accounts(self) -> list:
        """Accounts the access token may use: ProtoOACtidTraderAccount (ctidTraderAccountId, isLive,
        traderLogin, brokerTitleShort). Needs only the application to be authorised."""
        s = self.settings
        if s is None or not s.access_token:
            raise CTraderError("MISSING_SETTINGS", "CTRADER_ACCESS_TOKEN is needed")
        if not self.alive or not self._app_authed:
            async with self._connect_lock:
                if not self.alive:
                    await self.open()
                if not self._app_authed:
                    await self.application_auth()
        res = await self.request(oa.ProtoOAGetAccountListByAccessTokenReq(accessToken=s.access_token),
                                 needs_auth=False)
        return list(res.message.ctidTraderAccount)

    def _acct(self) -> int:
        if self.account_id is None:
            raise CTraderError("ACCOUNT_NOT_AUTHORIZED", "no account selected")
        return self.account_id

    async def version(self) -> str:
        res = await self.request(oa.ProtoOAVersionReq(), needs_auth=False)
        return res.message.version

    async def trader(self):
        return (await self.request(oa.ProtoOATraderReq(ctidTraderAccountId=self._acct()))).message.trader

    async def assets(self) -> list:
        return list((await self.request(oa.ProtoOAAssetListReq(ctidTraderAccountId=self._acct()))).message.asset)

    async def symbols(self) -> list:
        """Light symbols (id, name, enabled, base/quote asset ids)."""
        res = await self.request(oa.ProtoOASymbolsListReq(ctidTraderAccountId=self._acct()))
        return list(res.message.symbol)

    async def symbol_details(self, symbol_ids: Iterable[int]) -> list:
        """Full ProtoOASymbol entries: digits, pipPosition, volumes, lotSize, commission, swaps."""
        res = await self.request(oa.ProtoOASymbolByIdReq(ctidTraderAccountId=self._acct(),
                                                         symbolId=list(symbol_ids)))
        return list(res.message.symbol)

    async def trendbars(self, symbol_id: int, period: str, from_ms: int, to_ms: int,
                        count: int | None = None) -> list[dict]:
        """Historical bars as dicts {epoch, open, high, low, close, volume}, oldest first.
        period: a ProtoOATrendbarPeriod name (M1 ... D1) or a project timeframe ("1h")."""
        period = TRENDBAR_PERIODS.get(period, period)
        req = oa.ProtoOAGetTrendbarsReq(ctidTraderAccountId=self._acct(), symbolId=symbol_id,
                                        period=model.ProtoOATrendbarPeriod.Value(period),
                                        fromTimestamp=int(from_ms), toTimestamp=int(to_ms))
        if count:
            req.count = int(count)
        res = await self.request(req, timeout=max(self.request_timeout, 30))
        return sorted((bar_to_dict(b) for b in res.message.trendbar), key=lambda b: b["epoch"])

    async def subscribe_spots(self, symbol_ids: Iterable[int]) -> None:
        ids = [i for i in symbol_ids if i not in self._spot_subs]
        if not ids:
            return
        for i in ids:
            self._spot_events.setdefault(i, asyncio.Event())
        try:
            await self.request(oa.ProtoOASubscribeSpotsReq(ctidTraderAccountId=self._acct(), symbolId=ids,
                                                           subscribeToSpotTimestamp=True))
        except CTraderError as err:
            if err.code != "ALREADY_SUBSCRIBED":
                raise
        self._spot_subs.update(ids)

    async def unsubscribe_spots(self, symbol_ids: Iterable[int]) -> None:
        ids = [i for i in symbol_ids if i in self._spot_subs]
        if ids:
            await self.request(oa.ProtoOAUnsubscribeSpotsReq(ctidTraderAccountId=self._acct(), symbolId=ids))
            self._spot_subs.difference_update(ids)

    async def spot(self, symbol_id: int, timeout: float = 10.0) -> Spot:
        """Latest bid/ask; subscribes on first use and waits for the first price."""
        await self.subscribe_spots([symbol_id])
        s = self.spots.get(symbol_id)
        if s is not None and s.bid == s.bid and s.ask == s.ask:
            return s
        ev = self._spot_events.setdefault(symbol_id, asyncio.Event())
        deadline = time.monotonic() + timeout
        while True:
            ev.clear()
            s = self.spots.get(symbol_id)
            if s is not None and s.bid == s.bid and s.ask == s.ask:      # both sides known (not NaN)
                return s
            left = deadline - time.monotonic()
            if left <= 0:
                raise CTraderTimeout(f"no price for symbol {symbol_id} within {timeout:.0f} s")
            try:
                await asyncio.wait_for(ev.wait(), left)
            except asyncio.TimeoutError:
                pass

    # ---------------------------------------------------------------- trading

    async def new_market_order(self, symbol_id: int, side: str, volume: int, *,
                               relative_stop_loss: int | None, relative_take_profit: int | None,
                               label: str, client_order_id: str, comment: str | None = None,
                               timeout: float | None = None) -> Envelope:
        """Market order; returns the ORDER_FILLED execution event. volume in 0.01 units.
        Stops are relative (1/100000 of a price unit from the fill price): the docs say absolute
        stopLoss / takeProfit are not supported on MARKET orders."""
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        req = oa.ProtoOANewOrderReq(ctidTraderAccountId=self._acct(), symbolId=symbol_id,
                                    orderType=model.MARKET,
                                    tradeSide=model.BUY if side == "BUY" else model.SELL,
                                    volume=int(volume), label=label, clientOrderId=client_order_id)
        if relative_stop_loss is not None:
            req.relativeStopLoss = int(relative_stop_loss)
        if relative_take_profit is not None:
            req.relativeTakeProfit = int(relative_take_profit)
        if comment:
            req.comment = comment

        def mine(env: Envelope) -> bool:
            m = env.message
            if not is_execution(env) or m.ctidTraderAccountId != self.account_id:
                return False
            return ((m.HasField("order") and m.order.clientOrderId == client_order_id)
                    or (m.HasField("position") and m.position.tradeData.label == label))

        def filled(env: Envelope) -> bool:
            if is_execution(env, EXEC.ORDER_CANCELLED, EXEC.ORDER_EXPIRED):
                raise_later.append(CTraderError("ORDER_CANCELLED", enum_name(EXEC, env.message.executionType)))
                return True
            return is_execution(env, EXEC.ORDER_FILLED)

        raise_later: list[CTraderError] = []
        env = await self.request(req, done=filled, match=mine, timeout=timeout)
        if raise_later:
            raise raise_later[0]
        return env

    async def amend_position_sltp(self, position_id: int, stop_loss: float | None,
                                  take_profit: float | None) -> Envelope:
        """Set the position's stop loss and take profit (absolute prices). Both are sent every time:
        a missing value is read by the server as 'no stop' / 'no take profit'
        (the adapter always fills both in)."""
        req = oa.ProtoOAAmendPositionSLTPReq(ctidTraderAccountId=self._acct(), positionId=position_id)
        if stop_loss is not None:
            req.stopLoss = stop_loss
        if take_profit is not None:
            req.takeProfit = take_profit

        def mine(env: Envelope) -> bool:
            return (is_execution(env) and env.message.HasField("position")
                    and env.message.position.positionId == position_id
                    and env.message.executionType in (EXEC.ORDER_REPLACED, EXEC.ORDER_ACCEPTED))
        return await self.request(req, done=lambda env: is_execution(env), match=mine)

    async def close_position(self, position_id: int, volume: int) -> Envelope:
        """Close `volume` (0.01 units) of the position at market; returns the ORDER_FILLED event."""
        req = oa.ProtoOAClosePositionReq(ctidTraderAccountId=self._acct(), positionId=position_id,
                                         volume=int(volume))

        def mine(env: Envelope) -> bool:
            return (is_execution(env, EXEC.ORDER_FILLED) and env.message.HasField("position")
                    and env.message.position.positionId == position_id)
        return await self.request(req, done=lambda env: is_execution(env, EXEC.ORDER_FILLED), match=mine)

    async def reconcile(self):
        """Open positions and pending orders: ProtoOAReconcileRes(position=[...], order=[...])."""
        return (await self.request(oa.ProtoOAReconcileReq(ctidTraderAccountId=self._acct()))).message

    async def deals(self, from_ms: int, to_ms: int, max_rows: int = 1000) -> list:
        """Deals (executions) between two times. Asked for in windows of at most a week, following
        hasMore inside each window."""
        out = []
        week = 7 * 86400 * 1000
        start = int(from_ms)
        while start < to_ms:
            end = min(int(to_ms), start + week)
            cursor_to = end
            while True:
                res = (await self.request(oa.ProtoOADealListReq(
                    ctidTraderAccountId=self._acct(), fromTimestamp=start, toTimestamp=cursor_to,
                    maxRows=max_rows))).message
                batch = list(res.deal)
                out.extend(batch)
                if not res.hasMore or not batch:
                    break
                oldest = min(d.executionTimestamp for d in batch)
                if oldest <= start or oldest >= cursor_to:
                    break
                cursor_to = oldest - 1
            start = end
        seen, unique = set(), []
        for d in sorted(out, key=lambda d: d.executionTimestamp):
            if d.dealId not in seen:
                seen.add(d.dealId)
                unique.append(d)
        return unique

    async def deals_for_position(self, position_id: int, from_ms: int = 0, to_ms: int | None = None,
                                 max_weeks: int = 8) -> list:
        """Deals of one position. The real server refuses a period longer than about a week
        (INCORRECT_BOUNDARIES, seen on the demo server 13 Nov 2026), so ask week by week, newest first,
        back to from_ms or max_weeks (stopping once the position's opening deal is found)."""
        week = 7 * 86400 * 1000 - 1000
        end = int(to_ms or (time.time() + 60) * 1000)
        floor = max(int(from_ms), end - max_weeks * week)
        out = []
        while end > floor:
            start = max(floor, end - week)
            req = oa.ProtoOADealListByPositionIdReq(ctidTraderAccountId=self._acct(), positionId=position_id,
                                                    fromTimestamp=start, toTimestamp=end)
            batch = list((await self.request(req)).message.deal)
            out.extend(batch)
            if any(not d.HasField("closePositionDetail") for d in batch):   # the opening deal: done
                break
            end = start
        seen, uniq = set(), []
        for d in sorted(out, key=lambda d: d.executionTimestamp):
            if d.dealId not in seen:
                seen.add(d.dealId)
                uniq.append(d)
        return uniq

    async def order_details(self, order_id: int):
        res = (await self.request(oa.ProtoOAOrderDetailsReq(ctidTraderAccountId=self._acct(),
                                                            orderId=order_id))).message
        return res.order, list(res.deal)

    async def unrealized_pnl(self) -> tuple[dict[int, tuple[float, float]], int]:
        """{positionId: (gross, net)} in account currency (already divided by 10^moneyDigits)."""
        res = (await self.request(oa.ProtoOAGetPositionUnrealizedPnLReq(
            ctidTraderAccountId=self._acct()))).message
        scale = 10 ** res.moneyDigits
        return ({p.positionId: (p.grossUnrealizedPnL / scale, p.netUnrealizedPnL / scale)
                 for p in res.positionUnrealizedPnL}, res.moneyDigits)


def bar_to_dict(b) -> dict:
    """ProtoOATrendbar -> prices. low is absolute; open/high/close are low + delta (1/100000 units)."""
    low = b.low
    return {
        "epoch": b.utcTimestampInMinutes * 60,
        "open": (low + b.deltaOpen) / PRICE_SCALE,
        "high": (low + b.deltaHigh) / PRICE_SCALE,
        "low": low / PRICE_SCALE,
        "close": (low + b.deltaClose) / PRICE_SCALE,
        "volume": b.volume,
    }
