"""
Directional pressure helpers.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import chess

from rule_tagger2.legacy.analysis import file_pressure as _legacy_file_pressure


def file_pressure(
    board_before: chess.Board,
    board_after: chess.Board,
    actor: chess.Color,
    file_idx: int,
    target_square: chess.Square,
) -> Tuple[float, Dict[str, Any]]:
    return _legacy_file_pressure(board_before, board_after, actor, file_idx, target_square)
