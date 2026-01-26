"""
Utility helpers shared across ChessEvaluator submodules.
"""
from __future__ import annotations

import chess


def pov(value: float, color: chess.Color) -> float:
    """Convert a white-centric score into the point-of-view of the supplied color."""
    return value if color == chess.WHITE else -value


__all__ = ["pov"]
