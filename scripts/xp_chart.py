"""Perfect-fit experiment: side-by-side balance chart for reports/experiment_perfect_fit.md.

Left: whole pre-holdout period (log scale, so the first months are visible).
Right: the first unseen-data test (Deriv holdout), USD.

Run: python scripts/xp_chart.py
"""

from __future__ import annotations

import csv
import datetime as dt
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import xp_lib as L  # noqa: E402

BT = L.ROOT / "reports" / "backtests"
OUT = L.ROOT / "reports" / "experiment_perfect_fit_equity.png"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def curve(run: str, start: float = 100.0):
    with (BT / run / "trades.csv").open() as f:
        rows = list(csv.DictReader(f))
    t = [dt.datetime.fromisoformat(rows[0]["entry_time"])] + \
        [dt.datetime.fromisoformat(r["exit_time"]) for r in rows]
    return t, [start] + [float(r["balance_after"]) for r in rows]


def main() -> int:
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6), facecolor=SURFACE,
                               gridspec_kw={"width_ratios": [1.6, 1]})
    for ax in (a, b):
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    t, y = curve("experiment_perfect_fit_preholdout")
    a.plot(t, y, color=BLUE, linewidth=2)
    a.set_yscale("log")
    a.set_yticks([100, 1e3, 1e4, 1e5, 1e6])
    a.set_yticklabels(["100", "1,000", "10,000", "100,000", "1,000,000"])
    a.set_title("Pre-holdout, fitted period (2021-10 to 2026-04)\nbalance in USD, log scale",
                loc="left", fontsize=11)
    a.annotate(f"{y[-1]:,.0f} USD", (t[-1], y[-1]), xytext=(-8, -16), textcoords="offset points",
               ha="right", color=INK)
    a.annotate("stake reaches the 2,000 USD cap:\ngrowth turns linear", (t[len(t) // 10], y[len(y) // 10]),
               xytext=(30, -50), textcoords="offset points", color=INK2, fontsize=9,
               arrowprops={"arrowstyle": "-", "color": INK2, "linewidth": 0.8})
    t, y = curve("experiment_perfect_fit_first_unseen_test_HOLDOUT")
    b.plot(t, y, color=BLUE, linewidth=2)
    b.axhline(50, color=INK2, linewidth=1, linestyle=(0, (4, 3)))
    b.text(t[0], 51, "kill switch (50 USD)", color=INK2, fontsize=9, va="bottom")
    b.annotate(f"{y[-1]:.2f} USD, stopped {t[-1]:%d %b}", (t[-1], y[-1]), xytext=(-6, -14),
               textcoords="offset points", ha="right", va="top", color=INK)
    b.set_ylim(40, 110)
    b.set_title("First unseen-data test (Deriv, from 2026-04-28)\nbalance in USD",
                loc="left", fontsize=11)
    b.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    for lab in b.get_xticklabels():
        lab.set_rotation(30)
    fig.suptitle("Perfect-fit strategy: same code, same 100 USD start, measured commission",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT, dpi=130, facecolor=SURFACE)
    print("wrote", OUT.relative_to(L.ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
