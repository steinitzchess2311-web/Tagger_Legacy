"""
Engine protocol definition for dependency-injected analyses.
"""
from __future__ import annotations

from typing import Protocol, Tuple, Dict, List

import chess

from ..models import EngineCandidates


class EngineClient(Protocol):
    """Protocol that concrete engine adapters must implement."""

    def analyze(self, fen: str, *, depth: int, multipv: int, depth_low: int = 0) -> EngineCandidates:
        """Return engine candidates and metadata for the given position."""

    def eval_move(self, fen: str, move_uci: str, *, depth: int) -> int:
        """Return centipawn evaluation for the move in the given position."""

    def simulate_followup(
        self,
        fen: str,
        actor: chess.Color,
        *,
        steps: int,
        depth: int,
    ) -> Tuple[
        Dict[str, float],
        Dict[str, float],
        List[Dict[str, float]],
        List[Dict[str, float]],
    ]:
        """Return follow-up metric sequences from the given state."""

    def identifier(self) -> str:
        """Return a string identifier for the underlying engine (e.g. binary path)."""
