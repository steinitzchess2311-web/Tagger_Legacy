"""
Analysis context shared across all tag detectors.

This module defines AnalysisContext, which contains all the data needed
for tag detection: board state, engine analysis, metrics, and computed features.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chess


@dataclass
class Candidate:
    """Represents a candidate move from engine analysis."""

    move: chess.Move
    score_cp: int
    kind: str  # "quiet", "dynamic", "forcing", etc.
    depth: int = 0
    multipv: int = 0


@dataclass
class AnalysisContext:
    """
    Shared context for all tag detectors.

    Contains all information about the position, move, and analysis results
    that detectors need to make decisions.
    """

    # ===== Core Position Data =====
    board: chess.Board
    played_move: chess.Move
    actor: chess.Color
    fen: str = ""

    # ===== Engine Analysis =====
    candidates: List[Candidate] = field(default_factory=list)
    eval_before_cp: int = 0
    eval_played_cp: int = 0
    eval_best_cp: int = 0

    # Floating-point evaluations (in pawns)
    eval_before: float = 0.0
    eval_played: float = 0.0
    eval_best: float = 0.0
    delta_eval: float = 0.0  # eval_best - eval_played

    # ===== Position Metrics (Before Move) =====
    metrics_before: Dict[str, float] = field(default_factory=dict)
    opp_metrics_before: Dict[str, float] = field(default_factory=dict)
    evaluation_before: Dict[str, float] = field(default_factory=dict)
    coverage_before: int = 0

    # ===== Position Metrics (After Played Move) =====
    metrics_played: Dict[str, float] = field(default_factory=dict)
    opp_metrics_played: Dict[str, float] = field(default_factory=dict)
    evaluation_played: Dict[str, float] = field(default_factory=dict)
    coverage_after: int = 0

    # ===== Position Metrics (After Best Move) =====
    metrics_best: Dict[str, float] = field(default_factory=dict)
    opp_metrics_best: Dict[str, float] = field(default_factory=dict)
    evaluation_best: Dict[str, float] = field(default_factory=dict)
    coverage_best: int = 0

    # ===== Computed Deltas =====
    component_deltas: Dict[str, float] = field(default_factory=dict)
    change_played_vs_before: Dict[str, float] = field(default_factory=dict)
    opp_component_deltas: Dict[str, float] = field(default_factory=dict)
    opp_change_played_vs_before: Dict[str, float] = field(default_factory=dict)
    coverage_delta: int = 0

    # ===== Game Phase & Position Features =====
    phase_ratio: float = 1.0
    phase_bucket: str = "middlegame"

    # Contact ratios
    contact_ratio_before: float = 0.0
    contact_ratio_played: float = 0.0
    contact_ratio_best: float = 0.0
    contact_delta_played: float = 0.0
    contact_delta_best: float = 0.0

    # ===== Move Classification =====
    played_kind: str = "quiet"
    best_kind: str = "quiet"
    has_dynamic_in_band: bool = False

    # ===== Tactical Weight =====
    tactical_weight: float = 0.0

    # ===== Follow-up Simulations =====
    followup_metrics: Dict[str, Any] = field(default_factory=dict)

    # ===== Additional Metadata =====
    metadata: Dict[str, Any] = field(default_factory=dict)
    engine_path: str = ""
    depth: int = 14
    multipv: int = 6

    @classmethod
    def from_legacy_data(
        cls,
        board: chess.Board,
        played_move: chess.Move,
        actor: chess.Color,
        **kwargs,
    ) -> "AnalysisContext":
        """
        Creates an AnalysisContext from legacy tag_position data.

        This factory method is used during migration to populate context
        from the existing core.tag_position() function results.

        Args:
            board: Chess board
            played_move: Move that was played
            actor: Side to move
            **kwargs: Additional data to populate context

        Returns:
            Fully populated AnalysisContext
        """
        ctx = cls(board=board, played_move=played_move, actor=actor)

        # Populate from kwargs
        for key, value in kwargs.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)

        return ctx

    @classmethod
    def from_fen_move(
        cls, fen: str, move_uci: str, engine_path: str = "", depth: int = 14
    ) -> "AnalysisContext":
        """
        Creates a minimal AnalysisContext from FEN and UCI move.

        This is used for testing. For production use, call the full
        tag_position pipeline which populates all fields.

        Args:
            fen: FEN string
            move_uci: Move in UCI format (e.g., "e2e4")
            engine_path: Path to chess engine
            depth: Analysis depth

        Returns:
            Minimal AnalysisContext (most fields empty)
        """
        board = chess.Board(fen)
        move = chess.Move.from_uci(move_uci)
        return cls(
            board=board,
            played_move=move,
            actor=board.turn,
            fen=fen,
            engine_path=engine_path,
            depth=depth,
        )

    def get_metric_delta(self, metric_name: str) -> float:
        """
        Gets the delta for a specific metric (played - best).

        Args:
            metric_name: Name of metric (e.g., "mobility", "king_safety")

        Returns:
            Delta value (played - best), or 0.0 if not found
        """
        return self.component_deltas.get(metric_name, 0.0)

    def get_played_metric(self, metric_name: str) -> float:
        """Gets metric value after played move."""
        return self.metrics_played.get(metric_name, 0.0)

    def get_before_metric(self, metric_name: str) -> float:
        """Gets metric value before move."""
        return self.metrics_before.get(metric_name, 0.0)

    def is_endgame(self) -> bool:
        """Returns True if position is in endgame phase."""
        return self.phase_ratio < 0.75

    def is_opening(self) -> bool:
        """Returns True if position is in opening phase."""
        return self.phase_ratio >= 1.5

    def is_tactical_position(self) -> bool:
        """Returns True if tactical weight is high."""
        return self.tactical_weight >= 0.6
