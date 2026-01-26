"""
Prophylaxis-specific helpers extracted from the main rule tagger.

This module encapsulates the tagging heuristics that reason about
preventive play so that the core tagger can focus on orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import chess
import chess.engine

FULL_MATERIAL_COUNT = 32


@dataclass(frozen=True)
class ProphylaxisConfig:
    """Convenience container for thresholds used across prophylaxis logic."""

    structure_min: float = 0.2
    opp_mobility_drop: float = 0.15
    self_mobility_tol: float = 0.3
    preventive_trigger: float = 0.15
    safety_cap: float = 0.4
    score_threshold: float = 0.15
    threat_depth: int = 6
    threat_drop: float = 0.3


def estimate_opponent_threat(
    engine_path: str,
    board: chess.Board,
    actor: chess.Color,
    *,
    config: ProphylaxisConfig,
) -> float:
    """
    Probe the position with a fixed-depth search to estimate the opponent's
    immediate tactical resources. Used to grade prophylaxis attempts.
    """
    temp = board.copy(stack=False)
    if temp.is_game_over():
        return 0.0
    needs_null = temp.turn == actor
    null_pushed = False
    try:
        with chess.engine.SimpleEngine.popen_uci(engine_path) as eng:
            if needs_null and not temp.is_check():
                try:
                    temp.push(chess.Move.null())
                    null_pushed = True
                except ValueError:
                    null_pushed = False
            info = eng.analyse(temp, chess.engine.Limit(depth=config.threat_depth))
    except Exception:
        if null_pushed:
            temp.pop()
        return 0.0
    finally:
        if null_pushed and len(temp.move_stack) and temp.move_stack[-1] == chess.Move.null():
            temp.pop()

    score_obj = info.get("score")
    if score_obj is None:
        return 0.0
    try:
        raw_cp = score_obj.pov(actor).score(mate_score=10000)
    except Exception:
        return 0.0
    if raw_cp is None:
        return 0.0
    threat = max(0.0, -raw_cp / 100.0)
    return round(threat, 3)


def _mirrored_squares(squares: Iterable[chess.Square]) -> set[chess.Square]:
    return {chess.square_mirror(sq) for sq in squares}


_BISHOP_PROPHYLAXIS_WHITE = {
    chess.A2, chess.B1, chess.C2,
    chess.H2, chess.G1, chess.F2,
}
_KNIGHT_PROPHYLAXIS_WHITE = {
    chess.E4, chess.D2, chess.F3, chess.C3, chess.H4, chess.A4,
}
_KING_PROPHYLAXIS_WHITE = {
    chess.H1, chess.H2, chess.G1, chess.G2,
}
_PAWN_PROPHYLAXIS_WHITE = {
    chess.A4, chess.H4, chess.A3, chess.H3, chess.B4, chess.G4,
}

_BISHOP_PROPHYLAXIS_BLACK = _mirrored_squares(_BISHOP_PROPHYLAXIS_WHITE)
_KNIGHT_PROPHYLAXIS_BLACK = _mirrored_squares(_KNIGHT_PROPHYLAXIS_WHITE)
_KING_PROPHYLAXIS_BLACK = _mirrored_squares(_KING_PROPHYLAXIS_WHITE)
_PAWN_PROPHYLAXIS_BLACK = _mirrored_squares(_PAWN_PROPHYLAXIS_WHITE)


def prophylaxis_pattern_reason(
    board: chess.Board,
    move: chess.Move,
    opp_trend: float,
    opp_tactics_delta: float,
) -> Optional[str]:
    """Detect canonical prophylaxis motifs for telemetry/debugging."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        return None
    color = piece.color
    if piece.piece_type == chess.BISHOP:
        target = _BISHOP_PROPHYLAXIS_WHITE if color == chess.WHITE else _BISHOP_PROPHYLAXIS_BLACK
        if move.to_square in target and (opp_trend <= 0.05 or opp_tactics_delta <= 0.05):
            return "anticipatory bishop retreat"
    elif piece.piece_type == chess.KNIGHT:
        target = _KNIGHT_PROPHYLAXIS_WHITE if color == chess.WHITE else _KNIGHT_PROPHYLAXIS_BLACK
        if move.to_square in target and opp_trend <= 0.05:
            return "anticipatory knight reposition"
    elif piece.piece_type == chess.KING:
        target = _KING_PROPHYLAXIS_WHITE if color == chess.WHITE else _KING_PROPHYLAXIS_BLACK
        if move.to_square in target and opp_trend <= 0.1:
            return "king safety shuffle"
    elif piece.piece_type == chess.PAWN:
        target = _PAWN_PROPHYLAXIS_WHITE if color == chess.WHITE else _PAWN_PROPHYLAXIS_BLACK
        if move.to_square in target and opp_trend <= 0.05:
            return "pawn advance to restrict opponent play"
    return None


def is_prophylaxis_candidate(board: chess.Board, move: chess.Move) -> bool:
    """Heuristic gate to decide whether a move is eligible for prophylaxis tagging."""
    if is_full_material(board):
        return False
    if board.is_capture(move) or board.gives_check(move):
        return False
    piece = board.piece_at(move.from_square)
    if not piece:
        return False
    if piece.piece_type == chess.PAWN:
        file_idx = chess.square_file(move.to_square)
        if file_idx in {3, 4}:  # d/e-files
            return False
    return True


def is_full_material(board: chess.Board) -> bool:
    """Return True when all 32 pieces remain on the board."""
    return len(board.piece_map()) >= FULL_MATERIAL_COUNT


def classify_prophylaxis_quality(
    has_prophylaxis: bool,
    preventive_score: float,
    effective_delta: float,
    tactical_weight: float,
    soft_weight: float,
    *,
    config: ProphylaxisConfig,
) -> Tuple[Optional[str], float]:
    """Map prophylaxis heuristics to a quality label."""
    if not has_prophylaxis:
        return None, 0.0
    trigger = config.preventive_trigger
    safety_cap = config.safety_cap
    score_threshold = config.score_threshold
    if preventive_score < trigger:
        if effective_delta <= -0.2:
            return "prophylactic_meaningless", 0.0
        if -0.2 < effective_delta < -0.1 and soft_weight >= 0.4:
            return "prophylactic_soft", round(soft_weight, 3)
        return "prophylactic_meaningless", 0.0
    if effective_delta <= -0.25:
        return "prophylactic_meaningless", 0.0
    if tactical_weight < 0.3 and effective_delta >= -0.1:
        return "prophylactic_strong", 1.0
    if tactical_weight < 0.5:
        base = 0.5 if effective_delta >= -0.1 else 0.4
        return "prophylactic_soft", round(max(soft_weight, base), 3)
    base = 0.35 if effective_delta >= -0.05 else 0.2
    soft = max(soft_weight, base)
    return "prophylactic_soft", round(min(soft, safety_cap), 3)


def clamp_preventive_score(score: float, *, config: ProphylaxisConfig) -> float:
    """Limit the preventive score to a sensible range for downstream thresholds."""
    if score <= 0.0:
        return 0.0
    return min(score, config.safety_cap)
