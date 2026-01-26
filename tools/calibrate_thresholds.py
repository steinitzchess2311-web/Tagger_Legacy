"""Calibration script for rule_tagger v8 thresholds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Iterable, List

import numpy as np

try:
    import chess
    import chess.pgn
except ImportError:  # pragma: no cover - guidance only
    chess = None


DEFAULT_METRICS = {
    "preventive_score": [],
    "delta_opp_mobility": [],
    "future_synergy_score": [],
    "delta_eval": [],
    "mobility_delta": [],
    "king_safety_delta": [],
    "tension_jump": [],
    "contact_release": [],
    "volatility": [],
}


def winsorize(values: np.ndarray, lower: float = 0.01, upper: float = 0.99) -> np.ndarray:
    if values.size == 0:
        return values
    lower_q = np.quantile(values, lower)
    upper_q = np.quantile(values, upper)
    return np.clip(values, lower_q, upper_q)


def percentiles(values: Iterable[float], points: List[float]):
    arr = np.array(list(values), dtype=float)
    if arr.size == 0:
        return {int(p * 100): 0.0 for p in points}
    arr = winsorize(arr)
    return {int(p * 100): float(np.quantile(arr, p)) for p in points}


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate metrics thresholds for rule_tagger v8.")
    parser.add_argument("--out", type=Path, default=Path("config/metrics_thresholds.auto.json"))
    parser.add_argument("--source", type=Path, nargs="*", help="Optional PGN/JSON files to sample from.")
    args = parser.parse_args()

    metrics = {key: [] for key in DEFAULT_METRICS}

    # TODO: integrate actual sampling; placeholder uses defaults.
    # In absence of corpus, persist default median values to file.
    defaults = {
        "preventive_score": {"p50": 0.10, "p70": 0.15, "p85": 0.25, "p95": 0.35},
        "delta_opp_mobility": {"p15": -0.05, "p30": -0.1, "p60": -0.2, "p85": -0.3},
        "delta_eval": {"p10": -0.35, "p25": -0.2, "p50": 0.0, "p75": 0.2},
        "future_synergy_score": {"p50": 0.1, "p70": 0.2, "p85": 0.3},
        "mobility_delta": {"p20": -0.05, "p50": 0.0, "p70": 0.05, "p85": 0.1},
        "king_safety_delta": {"p15": -0.1, "p50": 0.0, "p85": 0.1},
        "tension_jump": {"p70": 0.03, "p85": 0.05},
        "contact_release": {"p70": 0.03, "p85": 0.05},
        "volatility": {"p60": 0.15, "p85": 0.3},
    }

    args.out.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
    print(f"Wrote default thresholds to {args.out}")


if __name__ == "__main__":
    main()
