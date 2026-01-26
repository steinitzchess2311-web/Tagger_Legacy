"""
Mobility computations for ChessEvaluator.
"""
from __future__ import annotations

from typing import Any, Dict, List

import chess

from .constants import MOBILITY_BONUS


def evaluate(board: chess.Board) -> Dict[str, Any]:
    """Return mobility summaries for both colors."""
    return {
        "white": _evaluate_side(board, chess.WHITE),
        "black": _evaluate_side(board, chess.BLACK),
    }


def _evaluate_side(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    mobility_area = _mobility_area(board, color)
    piece_details = {"queen": [], "rooks": [], "bishops": [], "knights": []}
    score_cp = 0
    total_moves = 0

    for square in board.pieces(chess.QUEEN, color):
        targets = _mobility_targets(board, square, color, chess.QUEEN, mobility_area)
        count = len(targets)
        piece_details["queen"].append({"square": chess.square_name(square), "mobility": count})
        total_moves += count
        score_cp += _mobility_bonus(chess.QUEEN, count)

    for square in board.pieces(chess.ROOK, color):
        targets = _mobility_targets(board, square, color, chess.ROOK, mobility_area)
        count = len(targets)
        piece_details["rooks"].append({"square": chess.square_name(square), "mobility": count})
        total_moves += count
        score_cp += _mobility_bonus(chess.ROOK, count)

    for square in board.pieces(chess.BISHOP, color):
        targets = _mobility_targets(board, square, color, chess.BISHOP, mobility_area)
        count = len(targets)
        piece_details["bishops"].append({"square": chess.square_name(square), "mobility": count})
        total_moves += count
        score_cp += _mobility_bonus(chess.BISHOP, count)

    for square in board.pieces(chess.KNIGHT, color):
        targets = _mobility_targets(board, square, color, chess.KNIGHT, mobility_area)
        count = len(targets)
        piece_details["knights"].append({"square": chess.square_name(square), "mobility": count})
        total_moves += count
        score_cp += _mobility_bonus(chess.KNIGHT, count)

    king_safe_moves = 0
    king_square = board.king(color)
    if king_square is not None:
        for dest in board.attacks(king_square):
            occupant = board.piece_at(dest)
            if occupant and occupant.color == color:
                continue
            if board.is_attacked_by(not color, dest):
                continue
            king_safe_moves += 1

    score = score_cp / 100.0

    return {
        "pieces": piece_details,
        "total_mobility_squares": total_moves,
        "king_safe_moves": king_safe_moves,
        "score_cp": score_cp,
        "score": round(score, 2),
    }


def _mobility_area(board: chess.Board, color: chess.Color) -> chess.SquareSet:
    area = chess.SquareSet(chess.BB_ALL)
    area -= chess.SquareSet(board.occupied_co[color])

    enemy = not color
    pawn_attacks = chess.SquareSet()
    for pawn_sq in board.pieces(chess.PAWN, enemy):
        pawn_attacks |= chess.SquareSet(chess.BB_PAWN_ATTACKS[enemy][pawn_sq])
    area -= pawn_attacks

    enemy_king = board.king(enemy)
    if enemy_king is not None:
        king_zone = chess.SquareSet(chess.BB_KING_ATTACKS[enemy_king])
        king_zone.add(enemy_king)
        area -= king_zone

    return area


def _mobility_targets(
    board: chess.Board,
    square: int,
    color: chess.Color,
    piece_type: chess.PieceType,
    mobility_area: chess.SquareSet,
) -> List[int]:
    attacks = board.attacks(square)
    targets: List[int] = []
    pin_line = _pin_line(board, color, square) if board.is_pinned(color, square) else None

    for dest in attacks:
        occupant = board.piece_at(dest)
        if occupant and occupant.color == color:
            continue
        if pin_line is not None and dest not in pin_line:
            continue
        if dest not in mobility_area:
            continue
        targets.append(dest)
    return targets


def _mobility_bonus(piece_type: chess.PieceType, count: int) -> int:
    table = MOBILITY_BONUS.get(piece_type)
    if not table:
        return 0
    index = min(count, len(table) - 1)
    return table[index]


def _pin_line(board: chess.Board, color: chess.Color, square: int) -> chess.SquareSet:
    king = board.king(color)
    if king is None:
        return chess.SquareSet()
    for attacker_sq in board.attackers(not color, king):
        attacker_piece = board.piece_at(attacker_sq)
        if not attacker_piece or attacker_piece.piece_type not in (chess.ROOK, chess.BISHOP, chess.QUEEN):
            continue
        between = chess.SquareSet.between(attacker_sq, king)
        if square in between:
            allowed = chess.SquareSet.between(king, attacker_sq)
            allowed.add(attacker_sq)
            return allowed
    return chess.SquareSet()


__all__ = ["evaluate"]
