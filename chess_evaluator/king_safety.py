"""
King safety evaluation helpers.
"""
from __future__ import annotations

from typing import Any, Dict

import chess


def evaluate(board: chess.Board) -> Dict[str, Any]:
    """Compute king-safety telemetry for both colors."""
    return {
        "white": _evaluate_side(board, chess.WHITE),
        "black": _evaluate_side(board, chess.BLACK),
    }


def _evaluate_side(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    king_square = board.king(color)
    if king_square is None:
        return {"error": "king missing", "score": -10.0}

    king_file = chess.square_file(king_square)
    castled = _has_castled(board, color)
    pawn_shield = _count_pawn_shield(board, king_square, color)

    open_files = 0
    semi_open_files = 0
    for file_offset in (-1, 0, 1):
        file_idx = king_file + file_offset
        if 0 <= file_idx <= 7:
            status = _check_file_status(board, file_idx, color)
            if status == "open":
                open_files += 1
            elif status == "semi_open":
                semi_open_files += 1

    attacks_on_zone = _count_king_zone_attacks(board, king_square, color)

    score = 0.0
    score += pawn_shield * 0.3
    score -= open_files * 0.4
    score -= semi_open_files * 0.2
    score -= attacks_on_zone * 0.1
    if castled:
        score += 0.5

    return {
        "pawn_shield": pawn_shield,
        "open_files_near_king": open_files,
        "semi_open_files_near_king": semi_open_files,
        "attacks_on_king_zone": attacks_on_zone,
        "castled": castled,
        "king_square": chess.square_name(king_square),
        "score": round(score, 2),
    }


def _has_castled(board: chess.Board, color: chess.Color) -> bool:
    king_square = board.king(color)
    if king_square is None:
        return False
    if color == chess.WHITE:
        return king_square in (chess.G1, chess.C1)
    return king_square in (chess.G8, chess.C8)


def _count_pawn_shield(board: chess.Board, king_square: int, color: chess.Color) -> int:
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    direction = 1 if color == chess.WHITE else -1
    shield = 0

    for file_offset in (-1, 0, 1):
        for rank_offset in (direction, direction * 2):
            file_idx = king_file + file_offset
            rank_idx = king_rank + rank_offset
            if not (0 <= file_idx <= 7 and 0 <= rank_idx <= 7):
                continue
            square = chess.square(file_idx, rank_idx)
            piece = board.piece_at(square)
            if piece and piece.color == color and piece.piece_type == chess.PAWN:
                shield += 1
    return shield


def _check_file_status(board: chess.Board, file_idx: int, color: chess.Color) -> str:
    own_pawn = False
    enemy_pawn = False
    for rank in range(8):
        square = chess.square(file_idx, rank)
        piece = board.piece_at(square)
        if not piece or piece.piece_type != chess.PAWN:
            continue
        if piece.color == color:
            own_pawn = True
        else:
            enemy_pawn = True
    if not own_pawn and not enemy_pawn:
        return "open"
    if not own_pawn:
        return "semi_open"
    return "closed"


def _count_king_zone_attacks(board: chess.Board, king_square: int, color: chess.Color) -> int:
    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    attacks = 0
    for file_offset in (-1, 0, 1):
        for rank_offset in (-1, 0, 1):
            file_idx = king_file + file_offset
            rank_idx = king_rank + rank_offset
            if not (0 <= file_idx <= 7 and 0 <= rank_idx <= 7):
                continue
            square = chess.square(file_idx, rank_idx)
            if board.is_attacked_by(not color, square):
                attacks += 1
    return attacks


__all__ = ["evaluate"]
