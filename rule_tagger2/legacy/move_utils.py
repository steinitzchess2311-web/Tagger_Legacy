"""
Move-related helper utilities.
"""
from __future__ import annotations

import chess

from .config import CENTER_FILES


def is_quiet(board: chess.Board, move: chess.Move) -> bool:
    """Matches the legacy 'quiet move' heuristic."""
    if board.is_capture(move):
        return False
    if board.gives_check(move):
        return False
    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type == chess.PAWN:
        return False
    if chess.square_file(move.to_square) in CENTER_FILES:
        return False
    return True


def is_dynamic(board: chess.Board, move: chess.Move) -> bool:
    """Legacy dynamic heuristic."""
    if board.is_capture(move):
        return True
    if board.gives_check(move):
        return True
    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type == chess.PAWN:
        return True
    if chess.square_file(move.to_square) in CENTER_FILES:
        return True
    return False


def classify_move(board: chess.Board, move: chess.Move) -> str:
    return "dynamic" if is_dynamic(board, move) else "positional"


def parse_move(board: chess.Board, move_str: str) -> chess.Move:
    """Parse either UCI or SAN notation."""
    try:
        move = chess.Move.from_uci(move_str)
        if move in board.legal_moves:
            return move
    except (ValueError, chess.InvalidMoveError):
        pass

    try:
        return board.parse_san(move_str)
    except ValueError as exc:  # pragma: no cover - user input guard
        raise ValueError(f"Move '{move_str}' is neither legal UCI nor SAN for the given position.") from exc


__all__ = ["classify_move", "is_dynamic", "is_quiet", "parse_move"]
