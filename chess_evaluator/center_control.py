"""
Center-control scoring helpers.
"""
from __future__ import annotations

from typing import Any, Dict

import chess

from .constants import CENTER_SQUARES, EXTENDED_CENTER


def evaluate(board: chess.Board) -> Dict[str, Any]:
    """Return center-control summary per color."""
    return {
        "white": _evaluate_side(board, chess.WHITE),
        "black": _evaluate_side(board, chess.BLACK),
    }


def _evaluate_side(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    center_4 = 0
    extended = 0
    for square in CENTER_SQUARES:
        if board.is_attacked_by(color, square):
            center_4 += 1
        piece = board.piece_at(square)
        if piece and piece.color == color:
            center_4 += 1
    for square in EXTENDED_CENTER:
        if board.is_attacked_by(color, square):
            extended += 1
    score = center_4 * 0.3 + extended * 0.05
    return {
        "center_4": center_4,
        "extended_center": extended,
        "score": round(score, 2),
    }


__all__ = ["evaluate"]
