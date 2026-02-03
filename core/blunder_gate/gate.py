"""Hard gate for dominating engine top pick."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple


GateResult = Dict[str, Optional[float] | bool | int | List[int]]


def filter_candidates(
    candidates: List[dict],
    *,
    cutoff_cp: int = -150,
) -> Tuple[List[dict], List[int], List[int]]:
    """Filter out candidates with score_cp <= cutoff_cp."""
    kept: List[dict] = []
    kept_indices: List[int] = []
    dropped_indices: List[int] = []
    for idx, entry in enumerate(candidates):
        score = entry.get("score_cp")
        if score is not None and int(score) <= cutoff_cp:
            dropped_indices.append(idx)
            continue
        kept.append(entry)
        kept_indices.append(idx)
    return kept, kept_indices, dropped_indices


def evaluate_engine_gap(
    candidates: List[dict],
    *,
    threshold_cp: int = 200,
    cutoff_cp: int = -150,
) -> GateResult:
    """
    Evaluate whether engine pick #1 dominates pick #2 by threshold_cp.

    Returns a dict with gate metadata.
    """
    kept, kept_indices, dropped_indices = filter_candidates(candidates, cutoff_cp=cutoff_cp)
    if len(kept) < 2:
        return {
            "triggered": False,
            "gap_cp": None,
            "threshold_cp": threshold_cp,
            "engine1_index": 0,
            "cutoff_cp": cutoff_cp,
            "kept_indices": kept_indices,
            "dropped_indices": dropped_indices,
        }

    score1 = kept[0].get("score_cp")
    score2 = kept[1].get("score_cp")
    if score1 is None or score2 is None:
        return {
            "triggered": False,
            "gap_cp": None,
            "threshold_cp": threshold_cp,
            "engine1_index": 0,
            "cutoff_cp": cutoff_cp,
            "kept_indices": kept_indices,
            "dropped_indices": dropped_indices,
        }

    gap_cp = int(score1) - int(score2)
    return {
        "triggered": gap_cp >= threshold_cp,
        "gap_cp": gap_cp,
        "threshold_cp": threshold_cp,
        "engine1_index": kept_indices[0] if kept_indices else 0,
        "cutoff_cp": cutoff_cp,
        "kept_indices": kept_indices,
        "dropped_indices": dropped_indices,
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


def apply_inaccuracy_patch(
    candidates: List[dict],
    probabilities: List[float],
    *,
    gap_cp: int = 40,
) -> Tuple[List[float], List[bool]]:
    """Apply inaccuracy penalty when adjacent engine scores diverge sharply."""
    if not candidates or not probabilities:
        return list(probabilities), [False for _ in probabilities]
    if len(candidates) != len(probabilities):
        return list(probabilities), [False for _ in probabilities]

    scores: List[int] = []
    for entry in candidates:
        score = entry.get("score_cp")
        if score is None:
            return list(probabilities), [False for _ in probabilities]
        try:
            scores.append(int(score))
        except (TypeError, ValueError):
            return list(probabilities), [False for _ in probabilities]

    trigger_index: Optional[int] = None
    for idx in range(1, len(scores)):
        prev = scores[idx - 1]
        curr = scores[idx]
        if (prev - curr) > gap_cp or (prev >= 0 and curr < 0) or (prev <= 0 and curr > 0):
            trigger_index = idx
            break

    adjusted = [float(prob) for prob in probabilities]
    flags = [False for _ in adjusted]
    if trigger_index is None:
        return adjusted, flags

    for idx in range(trigger_index, len(adjusted)):
        adjusted[idx] = max(0.0, adjusted[idx] - 0.05)
        flags[idx] = True
    return adjusted, flags
