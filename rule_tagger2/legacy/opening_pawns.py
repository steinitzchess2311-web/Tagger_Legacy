"""
Opening pawn tag helpers.

Provides a lightweight detector for opening pawn pushes that should be
tagged but kept separate from prophylaxis logic.
"""

from __future__ import annotations

from typing import List, Tuple

import chess

OPENING_PAWN_FULLMOVE_CUTOFF = 15
CENTRAL_PAWN_OPENING_TARGETS = {chess.D4, chess.E4, chess.D5, chess.E5}
ROOK_PAWN_OPENING_TARGETS = {chess.A3, chess.H3, chess.A6, chess.H6}
MIN_PIECES_FOR_OPENING = 28  # allow a couple of early trades


def detect_opening_pawn_tags(board: chess.Board, move: chess.Move) -> Tuple[bool, bool, List[str]]:
    """
    Detect opening pawn pushes for opening_* tags.

    Returns:
        (is_central, is_rook, tags_list)
    """
    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type != chess.PAWN:
        return False, False, []
    if len(board.piece_map()) < MIN_PIECES_FOR_OPENING:
        return False, False, []
    if board.fullmove_number > OPENING_PAWN_FULLMOVE_CUTOFF:
        return False, False, []

    dest = move.to_square
    is_central = dest in CENTRAL_PAWN_OPENING_TARGETS
    is_rook = dest in ROOK_PAWN_OPENING_TARGETS
    tags: List[str] = []
    if is_central:
        tags.append("opening_central_pawn_move")
    if is_rook:
        tags.append("opening_rook_pawn_move")
    return is_central, is_rook, tags
