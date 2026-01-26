"""
Core ChessEvaluator orchestration that stitches the specialized evaluators.
"""
from __future__ import annotations

from typing import Any, Dict

import chess

from . import center_control, king_safety, mobility, pawn_structure, tactics


class ChessEvaluator:
    """Lightweight evaluator derived from the provided reference implementation."""

    def __init__(self, board: chess.Board):
        self.board = board

    @classmethod
    def from_fen(cls, fen: str) -> "ChessEvaluator":
        return cls(chess.Board(fen))

    def evaluate(self) -> Dict[str, Any]:
        """Compute the subset of evaluation components needed by the tagger."""
        king = king_safety.evaluate(self.board)
        structure = pawn_structure.evaluate(self.board)
        mobility_payload = mobility.evaluate(self.board)
        center = center_control.evaluate(self.board)
        tactical = tactics.evaluate(self.board)

        components = {
            "king_safety": king["white"]["score"] - king["black"]["score"],
            "mobility": mobility_payload["white"]["score"] - mobility_payload["black"]["score"],
            "center_control": center["white"]["score"] - center["black"]["score"],
            "structure": structure["white"]["score"] - structure["black"]["score"],
            "tactics": tactical["score"],
        }

        return {
            "king_safety": king,
            "pawn_structure": structure,
            "mobility": mobility_payload,
            "center_control": center,
            "tactical_themes": tactical,
            "components": components,
        }


__all__ = ["ChessEvaluator"]
