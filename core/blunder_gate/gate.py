"""Hard gate for dominating engine top pick."""
from __future__ import annotations

from typing import Dict, List, Optional


GateResult = Dict[str, Optional[float] | bool | int]


def evaluate_engine_gap(
    candidates: List[dict],
    *,
    threshold_cp: int = 200,
) -> GateResult:
    """
    Evaluate whether engine pick #1 dominates pick #2 by threshold_cp.

    Returns a dict with gate metadata.
    """
    if len(candidates) < 2:
        return {
            "triggered": False,
            "gap_cp": None,
            "threshold_cp": threshold_cp,
            "engine1_index": 0,
        }

    score1 = candidates[0].get("score_cp")
    score2 = candidates[1].get("score_cp")
    if score1 is None or score2 is None:
        return {
            "triggered": False,
            "gap_cp": None,
            "threshold_cp": threshold_cp,
            "engine1_index": 0,
        }

    gap_cp = int(score1) - int(score2)
    return {
        "triggered": gap_cp >= threshold_cp,
        "gap_cp": gap_cp,
        "threshold_cp": threshold_cp,
        "engine1_index": 0,
    }


def forced_probabilities(
    candidates: List[dict],
    *,
    engine1_index: int = 0,
) -> List[float]:
    """Return probability list with engine1 forced to 1.0 and others 0.0."""
    probs = [0.0 for _ in candidates]
    if 0 <= engine1_index < len(probs):
        probs[engine1_index] = 1.0
    return probs
