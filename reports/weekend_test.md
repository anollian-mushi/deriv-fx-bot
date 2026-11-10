# Weekend test (Phase 6): one demo contract held over a weekend

**Result in one line:** nothing was charged over the weekend, and the contract
closed with a small profit. The Monday gap was small (9 pips) and went in the
trade's favour, so this weekend did not show what a gap does to a stop loss.

Demo account only. No real money was involved.

## What was opened

| Item | Value |
|---|---|
| Contract | 19642142299, EUR/USD **Up**, x100 |
| Stake | 1.00 USD (the most it could lose) |
| Stop loss | 0.20 USD, which put the stop at price 1.11273 |
| Stop out (Deriv's own safety close) | 1.10381, where the whole 1 USD stake would be gone |
| Opened | Friday 6 Nov 2026, 18:01 UTC, at 1.11470 |
| Commission paid at the start | 0.02 USD |
| Closed | Monday 9 Nov 2026, 06:30 UTC, at 1.11625 (closed by us, on schedule) |

## What happened

**Charges over the weekend: none.** The account statement for this contract
has exactly two lines: the buy (-1.00 USD on Friday) and the sell (+1.12 USD
on Monday). There was no overnight or weekend fee of any kind. The profit is
fully explained by the price move minus the 0.02 USD commission:
1.00 x 100 x (1.11625 - 1.11470) / 1.11470 = 0.139, minus 0.02 = 0.12 USD.

**The Monday gap.** Deriv's EUR/USD price stopped on Friday at 20:55 UTC at
1.11380 and started again on Monday at 00:00 UTC at 1.11473. That is a jump
of **9.3 pips upward**, in the trade's favour.

**The stop loss: not tested.** The stop sat at 1.11273, about 11 pips below
Friday's last price, and the market reopened higher. So the stop was never
touched, and we still do not know whether a large gap against the trade would
fill the stop at the gapped price or slip further. The stop out (109 pips
away) and the "never lose more than the stake" promise were not tested either.

**Final result: +0.12 USD** on a 1.00 USD stake.

**Other contracts on the account.** The statement also shows two other demo
contracts (EUR/USD and USD/JPY, 2.95 USD each, opened Friday 07:00 and closed
Friday 20:00 UTC). They are not part of this test, probably trades of the
live bot on the VPS, and were left out of every number above.

## What this means for the rule "No weekend holding until the Phase 6 weekend test"

**Recommendation (the owner decides): keep the rule for now.**

- One question is answered: **holding over a weekend costs nothing extra**.
  Together with the earlier overnight test, Multipliers charge only the
  commission at the start, however long a trade is held.
- The more important question is still open: **what a big gap against the
  trade does to the stop loss**. One quiet weekend with a small, favourable
  gap cannot answer it. A strategy that holds over weekends could lose more
  than its planned stop on a bad Monday, though never more than its stake.
- To answer it, repeat the test on a few more weekends with **two contracts at
  once, one Up and one Down**, each with the smallest stop loss Deriv allows
  (0.10 USD, about 11 pips at x100 on 1 USD). Whichever way Monday gaps, one
  of the two faces it, and a gap of more than about 11 pips would cross its
  stop.

The CLAUDE.md rule is unchanged until the owner decides.

**Owner's decision (10 Nov 2026): keep "no weekend holding".** The repeat
test with one Up and one Down contract on 13-16 Nov is skipped. Every open
trade is still closed by Friday 20:30 UTC, in the bot and in the backtester.

## Files

- `research/phase6/weekend_test/open.json`: the buy, proposal, stop loss and
  stop out.
- `research/phase6/weekend_test/snapshot_20261106_1801.json`: first look after
  opening.
- `research/phase6/weekend_test/result.json`: Friday's last and Monday's first
  candles, the full statement, the sale and the result.
- Script: `scripts/weekend_test.py` (demo only).
