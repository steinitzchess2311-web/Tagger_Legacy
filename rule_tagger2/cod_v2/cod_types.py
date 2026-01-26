"""
Type definitions for Control over Dynamics v2.

This module defines the data structures used by the CoD v2 detector.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import chess


class CoDSubtype(Enum):
    """Control over Dynamics subtypes."""

    PROPHYLAXIS = "prophylaxis"
    PIECE_CONTROL = "piece_control"
    PAWN_CONTROL = "pawn_control"
    SIMPLIFICATION = "simplification"
    NONE = "none"


@dataclass
class CoDMetrics:
    """
    Metrics used for CoD detection.

    All metrics are computed deltas (played vs best alternative).
    """

    # Volatility and evaluation
    volatility_drop_cp: float = 0.0
    eval_drop_cp: float = 0.0

    # Mobility changes
    opp_mobility_drop: float = 0.0
    self_mobility_change: float = 0.0

    # Tactical and structural
    opp_tactics_change: float = 0.0
    tension_delta: float = 0.0

    # King safety
    king_safety_gain: float = 0.0
    king_safety_tolerance: float = 0.0

    # Contact and phase
    contact_ratio_before: float = 0.0
    contact_ratio_played: float = 0.0
    phase_ratio: float = 1.0

    # Preventive score (for prophylaxis)
    preventive_score: float = 0.0
    threat_delta: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for logging."""
        return {
            "volatility_drop_cp": round(self.volatility_drop_cp, 2),
            "eval_drop_cp": round(self.eval_drop_cp, 2),
            "opp_mobility_drop": round(self.opp_mobility_drop, 3),
            "self_mobility_change": round(self.self_mobility_change, 3),
            "opp_tactics_change": round(self.opp_tactics_change, 3),
            "tension_delta": round(self.tension_delta, 3),
            "king_safety_gain": round(self.king_safety_gain, 3),
            "preventive_score": round(self.preventive_score, 3),
            "threat_delta": round(self.threat_delta, 3),
        }


@dataclass
class CoDContext:
    """
    Context for CoD detection.

    This is a simplified view focused on CoD-specific metrics.
    It does NOT replace AnalysisContext from orchestration.
    """

    board: chess.Board
    played_move: chess.Move
    actor: chess.Color

    # Metrics
    metrics: CoDMetrics

    # Tactical context
    tactical_weight: float = 0.0
    mate_threat: bool = False
    blunder_threat_drop: float = 0.0

    # Cooldown tracking
    current_ply: int = 0
    last_cod_ply: Optional[int] = None
    last_cod_subtype: Optional[CoDSubtype] = None

    # Phase information
    phase_bucket: str = "middlegame"

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoDResult:
    """
    Result of CoD detection.

    Contains the detected subtype, confidence, and detailed diagnostics.
    """

    detected: bool
    subtype: CoDSubtype
    confidence: float = 0.0

    # Tags to emit
    tags: List[str] = field(default_factory=list)

    # Diagnostic information
    diagnostic: Dict[str, Any] = field(default_factory=dict)

    # Gate checks
    gates_passed: Dict[str, bool] = field(default_factory=dict)
    gates_failed: List[str] = field(default_factory=list)

    # Evidence trail
    evidence: Dict[str, Any] = field(default_factory=dict)

    # Thresholds used
    thresholds_used: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "detected": self.detected,
            "subtype": self.subtype.value if self.subtype else None,
            "confidence": round(self.confidence, 3),
            "tags": self.tags,
            "diagnostic": self.diagnostic,
            "gates_passed": self.gates_passed,
            "gates_failed": self.gates_failed,
            "evidence": self.evidence,
            "thresholds_used": self.thresholds_used,
        }

    @classmethod
    def no_detection(cls) -> "CoDResult":
        """Create a result indicating no CoD detected."""
        return cls(
            detected=False,
            subtype=CoDSubtype.NONE,
            confidence=0.0,
            tags=[],
        )
