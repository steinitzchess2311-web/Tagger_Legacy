"""
Dataclasses representing contextual state for tagging decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

import chess


@dataclass(frozen=True)
class EvalBundles:
    """Container for evaluation metrics scoped to different candidates."""

    metrics_before: Dict[str, float]
    metrics_played: Dict[str, float]
    metrics_best: Dict[str, float]
    opp_before: Dict[str, float]
    opp_played: Dict[str, float]
    opp_best: Dict[str, float]
    component_deltas: Dict[str, float]
    opp_component_deltas: Dict[str, float]


@dataclass(frozen=True)
class Followups:
    """Container for follow-up drill-down metrics."""

    base_self_before: Dict[str, float]
    base_opp_before: Dict[str, float]
    base_self_played: Dict[str, float]
    base_opp_played: Dict[str, float]
    base_self_best: Dict[str, float]
    base_opp_best: Dict[str, float]
    self_played: List[Dict[str, float]]
    opp_played: List[Dict[str, float]]
    self_best: List[Dict[str, float]]
    opp_best: List[Dict[str, float]]


@dataclass(frozen=True)
class PositionContext:
    """Normalized view of a tagged position used by detector logic."""

    board: chess.Board
    actor: chess.Color
    played: chess.Move
    best: chess.Move
    phase_ratio: float
    eval_before_cp: int
    eval_played_cp: int
    eval_best_cp: int
    metrics_before: Mapping[str, float]
    metrics_played: Mapping[str, float]
    metrics_best: Mapping[str, float]
    opp_before: Mapping[str, float]
    opp_played: Mapping[str, float]
    opp_best: Mapping[str, float]
    change_played_vs_before: Mapping[str, float]
    opp_change_played_vs_before: Mapping[str, float]
    tactical_weight: float
    delta_eval_cp: int
    delta_eval_float: float
    drop_cp: int
    effective_delta: float
    coverage_before: int
    coverage_after: int
    coverage_best: int
    contact_ratio_before: float
    contact_ratio_played: float
    contact_ratio_best: float
    followups: Followups
    trends: Mapping[str, float]
    windows: Mapping[str, float]
    eval_bundles: EvalBundles
    analysis_meta: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ThresholdsView:
    """Snapshot of tuned thresholds used by detectors."""

    values: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)
