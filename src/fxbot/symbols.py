"""Deriv forex symbols the project knows, with their pip and price step.

The three majors are the original research pairs (Phase 1-4, incubator candidates 1-5). The
six others were added on 31 Oct 2026 for the multi-pair test of the i13 rule; they trade as
Multipliers on Deriv (x100 and x200 offered, checked on the public WebSocket that day).
A candidate's symbol list and commission table are stored in its manifest, so adding a pair
here never changes an existing candidate.
"""

from __future__ import annotations

# symbol -> (pip, price step quoted by Deriv, display name)
SPEC: dict[str, tuple[float, float, str]] = {
    "frxEURUSD": (0.0001, 0.00001, "EUR/USD"),
    "frxGBPUSD": (0.0001, 0.00001, "GBP/USD"),
    "frxUSDJPY": (0.01, 0.001, "USD/JPY"),
    "frxAUDUSD": (0.0001, 0.00001, "AUD/USD"),
    "frxUSDCAD": (0.0001, 0.00001, "USD/CAD"),
    "frxUSDCHF": (0.0001, 0.00001, "USD/CHF"),
    "frxEURGBP": (0.0001, 0.00001, "EUR/GBP"),
    "frxEURJPY": (0.01, 0.001, "EUR/JPY"),
    "frxGBPJPY": (0.01, 0.001, "GBP/JPY"),
}
MAJORS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PAIRS2 = ("frxAUDUSD", "frxUSDCAD", "frxUSDCHF", "frxEURGBP", "frxEURJPY", "frxGBPJPY")
PIP = {s: v[0] for s, v in SPEC.items()}
PIP_SIZE = {s: v[1] for s, v in SPEC.items()}
NAME = {s: v[2] for s, v in SPEC.items()}


def display(symbol: str) -> str:
    return NAME.get(symbol, f"{symbol[3:6]}/{symbol[6:]}" if symbol.startswith("frx") else symbol)


def check(symbols) -> tuple[str, ...]:
    out = tuple(symbols)
    unknown = [s for s in out if s not in SPEC]
    if unknown or not out or len(set(out)) != len(out):
        raise ValueError(f"unknown or repeated symbols: {unknown or out}")
    return out
