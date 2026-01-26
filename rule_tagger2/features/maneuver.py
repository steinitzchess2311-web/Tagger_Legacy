"""
Maneuver feature helpers.
"""
from __future__ import annotations

from typing import Dict, Tuple

from rule_tagger2.legacy.analysis import evaluate_maneuver_metrics as _legacy_evaluate


def evaluate_maneuver_metrics(
    change_self: Dict[str, float],
    change_opp: Dict[str, float],
    effective_delta: float,
    file_pressure_delta: float,
) -> Tuple[float, float, Dict[str, float]]:
    return _legacy_evaluate(change_self, change_opp, effective_delta, file_pressure_delta)
