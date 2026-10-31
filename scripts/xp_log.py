"""Write research/experiment_log.md from research/experiment/variants.csv.gz.

Every variant tried is one row of variants.csv.gz (too many for a Markdown table);
the log summarises them by family and lists the best ones, plus the engine checks.

Run: python scripts/xp_log.py
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import defaultdict

import xp_lib as L

OUT = L.ROOT / "research" / "experiment_log.md"


def fmt(x, nd=1):
    x = float(x)
    return f"{x:,.{nd}f}"


def main() -> int:
    L.merge_variants()
    with gzip.open(L.VARIANTS, "rt") as f:
        rows = list(csv.DictReader(f))
    fams = defaultdict(list)
    for r in rows:
        fams[r["family"]].append(r)
    key = lambda r: float(r["screen_score"])
    lines = [
        "# Perfect-fit experiment log",
        "",
        "Owner-approved experiment on branch `experiment/perfect-fit` (31 Oct 2026), an explicit",
        "exception to the CLAUDE.md research rules: no walk-forward, no luck check, no",
        "parameter limit, no 2-of-3-pairs rule. Kept: real costs (commission by UTC hour from",
        "`research/phase2/cost_by_hour.json`, slippage rules), every hard risk limit, the entry",
        "window, daily pause, Friday close, and closed candles only.",
        "",
        "Goal: the highest **net profit / max drawdown** on the whole pre-holdout period",
        "(Dukascopy 1m, 2021-10-27 to 2026-04-27). Scores here are net return % / max drawdown %",
        "(drawdown floored at 0.5% so a handful of lucky trades with no loss cannot divide by zero).",
        "",
        f"**Variants tried: {len(rows):,}.** Every one is a row of",
        "[`research/experiment/variants.csv.gz`](experiment/variants.csv.gz) (id, family, rule,",
        "exit setup, screen trades / net / drawdown / score). They were scored with the fast",
        "screen (`src/fxbot/backtest/fastsim.py`); the finalists were then re-run in the real",
        "engine (table at the end), and the engine result decided the winner.",
        "",
        "Exit setups (528, each combined with every rule): x100 with stop loss",
        "{none,10,15,20,30,50} pips, take profit {none,10,15,20,30,50,80}, time exit after",
        "{1,2,3,4,6,8,12,24 h, none}; x200 with stop loss {none,10,15,20,30}, take profit",
        "{none,10,15,20,30,50}, time exit {1,2,4,8 h, none}.",
        "",
        "## By family",
        "",
        "| Family | Variants | Killed (equity hit 50%) | Best screen score | Best variant | Exit setup | Trades | Net % | Max DD % |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for fam in sorted(fams):
        rs = fams[fam]
        b = max(rs, key=key)
        killed = sum(1 for r in rs if r["screen_killed"] == "True")
        lines.append(f"| {fam} | {len(rs):,} | {killed:,} | {fmt(b['screen_score'])} | {b['desc']} | {b['config']} | "
                     f"{b['screen_trades']} | {fmt(b['screen_net_pct'])} | {fmt(b['screen_dd_pct'], 2)} |")
    lines += ["", "## Best 25 variants overall (screen)", "",
              "| Id | Family | Variant | Exit setup | Trades | Net % | Max DD % | Score |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=key, reverse=True)[:25]:
        lines.append(f"| {r['id']} | {r['family']} | {r['desc']} | {r['config']} | {r['screen_trades']} | "
                     f"{fmt(r['screen_net_pct'])} | {fmt(r['screen_dd_pct'], 2)} | {fmt(r['screen_score'])} |")
    oracle = json.loads((L.RES / "ml_setups.json").read_text())["oracle_top"][:3]
    lines += ["", "## Ceiling: perfect hindsight (not a strategy)", "",
              "Taking, at every candidate hour, whichever direction actually made money (knowing the",
              "future) gives these screen scores. No real strategy can beat them; they show how far",
              "in-sample fitting can be pushed.", ""]
    for o in oracle:
        lines.append(f"- {o['cfg']}: score {fmt(o['score'])}")
    vp = L.RES / "verify.json"
    if vp.exists():
        ver = sorted(json.loads(vp.read_text()), key=lambda r: -r["engine"]["score"])
        lines += ["", "## Finalists re-run in the real engine (kill switch enforced)", "",
                  "| Rank | Source | Variant | Exit setup | Engine trades | Net % | Max DD % | Win % | Score | Killed |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(ver, 1):
            e = r["engine"]
            lines.append(f"| {i} | {r['source']} | {r['desc']} | {r['config']} | {e['trades']} | {fmt(e['net_pct'])} | "
                         f"{fmt(e['dd_pct'], 2)} | {e['win_rate']} | {fmt(e['score'])} | {e['killed']} |")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT.relative_to(L.ROOT)} ({len(rows):,} variants)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
