"""
Tactical-theme evaluation utilities.
"""
from __future__ import annotations

from typing import Any, Dict, List

import chess


def evaluate(board: chess.Board) -> Dict[str, Any]:
    """Summarize tactical patterns such as pins and hanging pieces."""
    pins = _find_pins(board)
    hanging = _find_hanging_pieces(board)

    score = 0.0
    for pin in pins:
        if pin["pinned_color"] == "black":
            score += 0.3
        else:
            score -= 0.3
    for piece in hanging:
        if piece["color"] == "black":
            score += 0.2
        else:
            score -= 0.2

    return {
        "pins": pins,
        "hanging_pieces": hanging,
        "score": round(score, 2),
    }


def _find_pins(board: chess.Board) -> List[Dict[str, Any]]:
    pins: List[Dict[str, Any]] = []

    directions = [1, -1, 8, -8, 9, 7, -9, -7]

    def on_board(square: int) -> bool:
        return 0 <= square < 64

    def step_ok(prev: int, nxt: int, delta: int) -> bool:
        prev_file, prev_rank = chess.square_file(prev), chess.square_rank(prev)
        next_file, next_rank = chess.square_file(nxt), chess.square_rank(nxt)
        if delta in (1, -1):
            return next_rank == prev_rank and abs(next_file - prev_file) == 1
        if delta in (8, -8):
            return next_file == prev_file and abs(next_rank - prev_rank) == 1
        if delta in (9, -9):
            return (
                abs(next_file - prev_file) == 1
                and abs(next_rank - prev_rank) == 1
                and (next_file - prev_file) == (next_rank - prev_rank)
            )
        if delta in (7, -7):
            return (
                abs(next_file - prev_file) == 1
                and abs(next_rank - prev_rank) == 1
                and (next_file - prev_file) == -(next_rank - prev_rank)
            )
        return False

    for color in (chess.WHITE, chess.BLACK):
        king_square = board.king(color)
        if king_square is None:
            continue

        for delta in directions:
            current = king_square
            first_piece_square = None

            while True:
                next_square = current + delta
                if not on_board(next_square) or not step_ok(current, next_square, delta):
                    break
                current = next_square
                piece = board.piece_at(current)
                if piece:
                    first_piece_square = current
                    break

            if first_piece_square is None:
                continue

            first_piece = board.piece_at(first_piece_square)
            if not first_piece or first_piece.color != color or first_piece.piece_type == chess.KING:
                continue

            current_second = first_piece_square
            second_piece_square = None
            while True:
                next_square = current_second + delta
                if not on_board(next_square) or not step_ok(current_second, next_square, delta):
                    break
                current_second = next_square
                piece = board.piece_at(current_second)
                if piece:
                    second_piece_square = current_second
                    break

            if second_piece_square is None:
                continue

            second_piece = board.piece_at(second_piece_square)
            if not second_piece or second_piece.color == color:
                continue

            is_straight = delta in (1, -1, 8, -8)
            is_diagonal = delta in (7, -7, 9, -9)
            if not (
                (is_straight and second_piece.piece_type in (chess.ROOK, chess.QUEEN))
                or (is_diagonal and second_piece.piece_type in (chess.BISHOP, chess.QUEEN))
            ):
                continue

            pins.append(
                {
                    "pinned_piece": chess.piece_name(first_piece.piece_type),
                    "pinned_square": chess.square_name(first_piece_square),
                    "pinned_color": "white" if color == chess.WHITE else "black",
                    "pinning_piece": chess.piece_name(second_piece.piece_type),
                    "pinning_square": chess.square_name(second_piece_square),
                }
            )

    return pins


def _find_hanging_pieces(board: chess.Board) -> List[Dict[str, Any]]:
    hanging: List[Dict[str, Any]] = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.piece_type == chess.KING:
            continue
        if not board.is_attacked_by(not piece.color, square):
            continue
        if board.is_attacked_by(piece.color, square):
            continue
        hanging.append(
            {
                "piece": chess.piece_name(piece.piece_type),
                "square": chess.square_name(square),
                "color": "white" if piece.color == chess.WHITE else "black",
            }
        )
    return hanging


__all__ = ["evaluate"]
