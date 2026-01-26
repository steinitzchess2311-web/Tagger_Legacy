"""
Pawn-structure analysis utilities.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

import chess

from .constants import CENTER_SQUARES


def evaluate(board: chess.Board) -> Dict[str, Any]:
    """Return per-side pawn-structure diagnostics."""
    return {
        "white": _evaluate_side(board, chess.WHITE),
        "black": _evaluate_side(board, chess.BLACK),
    }


def _evaluate_side(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    pawns = list(board.pieces(chess.PAWN, color))

    isolated = _find_isolated_pawns(pawns)
    doubled = _find_doubled_pawns(pawns)
    backward = _find_backward_pawns(board, pawns, color)
    passed = _find_passed_pawns(board, pawns, color)
    chains = _find_pawn_chains(pawns, color)
    islands = _count_pawn_islands(pawns)
    hanging = _find_hanging_pawns(board, pawns, color)
    center_pawns = _find_center_pawns(pawns)

    score = 0.0
    score -= len(isolated) * 0.5
    score -= len(doubled) * 0.3
    score -= len(backward) * 0.4
    score += len(passed) * 0.8
    score += sum(len(chain) * 0.2 for chain in chains)
    score -= islands * 0.3
    score -= len(hanging) * 0.4
    score += len(center_pawns) * 0.3

    return {
        "isolated_pawns": [chess.square_name(sq) for sq in isolated],
        "doubled_pawns": [chess.square_name(sq) for sq in doubled],
        "backward_pawns": [chess.square_name(sq) for sq in backward],
        "passed_pawns": [
            {
                "square": chess.square_name(sq),
                "distance_to_promotion": _distance_to_promotion(sq, color),
                "protected": _is_pawn_protected(board, sq, color),
            }
            for sq in passed
        ],
        "pawn_chains": [[chess.square_name(sq) for sq in chain] for chain in chains],
        "pawn_islands": islands,
        "hanging_pawns": [chess.square_name(sq) for sq in hanging],
        "center_pawns": [chess.square_name(sq) for sq in center_pawns],
        "score": round(score, 2),
    }


def _find_isolated_pawns(pawns: List[int]) -> List[int]:
    isolated = []
    for pawn in pawns:
        file_idx = chess.square_file(pawn)
        has_adjacent = False
        for adj in (file_idx - 1, file_idx + 1):
            if not (0 <= adj <= 7):
                continue
            if any(chess.square_file(other) == adj for other in pawns):
                has_adjacent = True
                break
        if not has_adjacent:
            isolated.append(pawn)
    return isolated


def _find_doubled_pawns(pawns: List[int]) -> List[int]:
    file_map: Dict[int, List[int]] = defaultdict(list)
    for pawn in pawns:
        file_map[chess.square_file(pawn)].append(pawn)
    doubled: List[int] = []
    for entries in file_map.values():
        if len(entries) > 1:
            doubled.extend(entries)
    return doubled


def _find_backward_pawns(board: chess.Board, pawns: List[int], color: chess.Color) -> List[int]:
    backward: List[int] = []
    direction = 1 if color == chess.WHITE else -1
    for pawn in pawns:
        file_idx = chess.square_file(pawn)
        rank = chess.square_rank(pawn)
        next_rank = rank + direction
        if not (0 <= next_rank <= 7):
            continue
        forward = chess.square(file_idx, next_rank)
        if board.piece_at(forward):
            continue
        more_advanced = False
        for adj in (file_idx - 1, file_idx + 1):
            if not (0 <= adj <= 7):
                continue
            for other in pawns:
                if chess.square_file(other) != adj:
                    continue
                other_rank = chess.square_rank(other)
                if (color == chess.WHITE and other_rank > rank) or (color == chess.BLACK and other_rank < rank):
                    more_advanced = True
                    break
            if more_advanced:
                break
        if more_advanced and board.is_attacked_by(not color, forward):
            backward.append(pawn)
    return backward


def _find_passed_pawns(board: chess.Board, pawns: List[int], color: chess.Color) -> List[int]:
    passed: List[int] = []
    enemy_pawns = list(board.pieces(chess.PAWN, not color))
    for pawn in pawns:
        file_idx = chess.square_file(pawn)
        rank = chess.square_rank(pawn)
        is_passed = True
        for enemy in enemy_pawns:
            enemy_file = chess.square_file(enemy)
            enemy_rank = chess.square_rank(enemy)
            if abs(enemy_file - file_idx) <= 1:
                if (color == chess.WHITE and enemy_rank > rank) or (color == chess.BLACK and enemy_rank < rank):
                    is_passed = False
                    break
        if is_passed:
            passed.append(pawn)
    return passed


def _find_pawn_chains(pawns: List[int], color: chess.Color) -> List[List[int]]:
    chains: List[List[int]] = []
    visited: set[int] = set()
    direction = 1 if color == chess.WHITE else -1
    for pawn in pawns:
        if pawn in visited:
            continue
        chain = [pawn]
        visited.add(pawn)
        file_idx = chess.square_file(pawn)
        rank = chess.square_rank(pawn)
        for other in pawns:
            if other == pawn or other in visited:
                continue
            other_file = chess.square_file(other)
            other_rank = chess.square_rank(other)
            if abs(other_file - file_idx) == 1 and other_rank - rank == direction:
                chain.append(other)
                visited.add(other)
        if len(chain) > 1:
            chains.append(chain)
    return chains


def _count_pawn_islands(pawns: List[int]) -> int:
    if not pawns:
        return 0
    files = sorted({chess.square_file(p) for p in pawns})
    islands = 1
    for idx in range(len(files) - 1):
        if files[idx + 1] - files[idx] > 1:
            islands += 1
    return islands


def _find_hanging_pawns(board: chess.Board, pawns: List[int], color: chess.Color) -> List[int]:
    hanging: List[int] = []
    for file_pair in ((2, 3), (3, 4)):
        pair = []
        for pawn in pawns:
            file_idx = chess.square_file(pawn)
            rank = chess.square_rank(pawn)
            if file_idx in file_pair and rank in (3, 4):
                pair.append(pawn)
        if len(pair) == 2:
            supported = any(_is_pawn_protected(board, p, color) for p in pair)
            if not supported:
                hanging.extend(pair)
    return hanging


def _find_center_pawns(pawns: List[int]) -> List[int]:
    return [pawn for pawn in pawns if pawn in CENTER_SQUARES]


def _distance_to_promotion(square: int, color: chess.Color) -> int:
    rank = chess.square_rank(square)
    return 7 - rank if color == chess.WHITE else rank


def _is_pawn_protected(board: chess.Board, square: int, color: chess.Color) -> bool:
    file_idx = chess.square_file(square)
    rank = chess.square_rank(square)
    direction = -1 if color == chess.WHITE else 1
    for file_offset in (-1, 1):
        file_candidate = file_idx + file_offset
        rank_candidate = rank + direction
        if not (0 <= file_candidate <= 7 and 0 <= rank_candidate <= 7):
            continue
        candidate = chess.square(file_candidate, rank_candidate)
        piece = board.piece_at(candidate)
        if piece and piece.color == color and piece.piece_type == chess.PAWN:
            return True
    return False


__all__ = ["evaluate"]
