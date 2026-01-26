"""
Pipeline data models shared across stages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import chess


@dataclass(frozen=True)
class EngineMove:
    """Single engine move suggestion with metadata."""

    move: chess.Move
    score_cp: int
    kind: str
    info: Dict[str, Any] = field(default_factory=dict)

    def uci(self) -> str:
        return self.move.uci()


@dataclass(frozen=True)
class EngineCandidates:
    """Output of the engine analysis stage."""

    fen: str
    side_to_move: chess.Color
    candidates: List[EngineMove]
    eval_before_cp: int
    analysis_meta: Dict[str, Any]

    def best(self) -> EngineMove:
        if not self.candidates:
            raise ValueError("EngineCandidates contains no moves.")
        return self.candidates[0]


@dataclass(frozen=True)
class FeatureBundle:
    """Aggregated feature set produced by feature stages."""

    fen: str
    played_move: chess.Move
    best_move: chess.Move
    tactical_weight: float
    metrics_before: Dict[str, float]
    metrics_played: Dict[str, float]
    metrics_best: Dict[str, float]
    opp_metrics_before: Dict[str, float]
    opp_metrics_played: Dict[str, float]
    opp_metrics_best: Dict[str, float]
    change_played_vs_before: Dict[str, float]
    opp_change_played_vs_before: Dict[str, float]
    evaluation_before: Dict[str, Any]
    evaluation_played: Dict[str, Any]
    evaluation_best: Dict[str, Any]
    component_deltas: Dict[str, float]
    opp_component_deltas: Dict[str, float]
    analysis_meta: Dict[str, Any]
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModeDecision:
    """Result of the mode selection stage."""

    mode: Literal["tactical", "positional", "blended"]
    debug: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TagBundle:
    """Primary/secondary tags and accompanying metadata."""

    primary: List[str]
    secondary: List[str]
    notes: List[str]
    telemetry: Dict[str, Any]
    debug: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalResult:
    """Unified pipeline output."""

    features: FeatureBundle
    mode: ModeDecision
    tags: TagBundle
    raw_result: Optional[Any] = None
