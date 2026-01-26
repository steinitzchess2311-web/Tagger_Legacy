"""
Prophylaxis-specific helpers extracted from the main rule tagger.

This module encapsulates the tagging heuristics that reason about
preventive play so that the core tagger can focus on orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import chess
import chess.engine

FULL_MATERIAL_COUNT = 32


@dataclass(frozen=True)
class ProphylaxisConfig:
    """Convenience container for thresholds used across prophylaxis logic."""

    structure_min: float = 0.2
    opp_mobility_drop: float = 0.15
    self_mobility_tol: float = 0.3
    preventive_trigger: float = 0.16
    safety_cap: float = 0.6
    score_threshold: float = 0.20
    threat_depth: int = 6
    threat_drop: float = 0.35


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
            depth = max(config.threat_depth, 8)
            info = eng.analyse(temp, chess.engine.Limit(depth=depth))
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
        pov_score = score_obj.pov(actor)
    except Exception:
        return 0.0

    if pov_score.is_mate():
        mate_in = pov_score.mate()
        if mate_in is None or mate_in > 0:
            return 0.0
        threat = 10.0 / (abs(mate_in) + 1)
    else:
        cp_value = pov_score.score(mate_score=10000) or 0
        threat = max(0.0, -cp_value / 100.0)

    return round(min(threat, config.safety_cap), 3)


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
    trend_ok = opp_trend <= 0.12 or opp_tactics_delta <= 0.12
    if piece.piece_type == chess.BISHOP and trend_ok:
        return "anticipatory bishop retreat"
    if piece.piece_type == chess.KNIGHT and trend_ok:
        return "anticipatory knight reposition"
    if piece.piece_type == chess.KING and (opp_trend <= 0.15 or opp_tactics_delta <= 0.1):
        return "king safety shuffle"
    if piece.piece_type == chess.PAWN and trend_ok:
        return "pawn advance to restrict opponent play"
    return None


def is_prophylaxis_candidate(board: chess.Board, move: chess.Move) -> bool:
    """Heuristic gate to decide whether a move is eligible for prophylaxis tagging.

    Prophylactic moves must be anticipatory, not reactive. This function excludes:
    - Full material positions (opening noise, handled separately)
    - Moves that give check (too aggressive)
    - Captures (tactical, not prophylactic)
    - Moves that directly respond to being in check (reactive)
    - Recaptures (clearly reactive)
    - Early opening moves (prophylaxis is a middlegame/endgame concept)
    """
    if is_full_material(board):
        return False
    if board.gives_check(move):
        return False
    piece = board.piece_at(move.from_square)
    if not piece:
        return False

    # Exclude captures - these are tactical/reactive, not prophylactic
    if board.is_capture(move):
        return False

    # Exclude moves made while in check - these are forced/reactive
    if board.is_check():
        return False

    # Exclude recaptures: if opponent just captured on the destination square,
    # moving there is likely a recapture (reactive)
    if len(board.move_stack) > 0:
        last_move = board.peek()
        if last_move.to_square == move.to_square:
            # Moving to the square opponent just moved to could be a recapture pattern
            return False

    # Exclude very early opening phase - prophylaxis is primarily a middlegame concept
    # Allow prophylaxis detection once some development has occurred (move 6+)
    # Use fullmove_number which is available even when board is loaded from FEN
    piece_count = sum(1 for sq in chess.SQUARES if board.piece_at(sq) is not None)
    fullmove_number = board.fullmove_number
    # Only block if all 32 pieces AND we're in the very early opening (before move 6)
    if piece_count >= 32 and fullmove_number < 6:
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
    eval_before_cp: int = 0,
    drop_cp: int = 0,
    threat_delta: float = 0.0,
    volatility_drop: float = 0.0,
    pattern_override: bool = False,
    config: ProphylaxisConfig,
) -> Tuple[Optional[str], float]:
    """Map prophylaxis heuristics to a quality label.

    V2 naming convention:
    - prophylactic_direct (was prophylactic_strong): direct tactical prevention with high weight
    - prophylactic_latent (was prophylactic_soft): latent positional prevention
    - prophylactic_meaningless: ineffective prophylaxis
    """
    if not has_prophylaxis:
        return None, 0.0
    trigger = config.preventive_trigger
    safety_cap = config.safety_cap
    score_threshold = config.score_threshold
    fail_eval_band_cp = 200
    fail_drop_cp = 50

    # Check for failure case first
    if abs(eval_before_cp) <= fail_eval_band_cp and drop_cp < -fail_drop_cp:
        return "prophylactic_meaningless", 0.0

    # If preventive score is below trigger but pattern support exists, classify as latent
    # BUT only if there's also some meaningful signal (not just pattern alone)
    if preventive_score < trigger:
        if pattern_override:
            # Require additional signal beyond just pattern detection
            # Check for threat reduction, volatility drop, or soft positioning value
            has_meaningful_signal = (
                threat_delta >= 0.05  # Some threat reduction
                or volatility_drop >= 15.0  # Some volatility reduction
                or soft_weight >= 0.3  # Decent soft positioning
                or preventive_score >= trigger * 0.5  # At least half the trigger threshold
            )

            if has_meaningful_signal:
                # Pattern-supported prophylaxis with meaningful signal gets latent tag
                latent_base = 0.45
                latent_score = max(latent_base, soft_weight * 0.8, preventive_score * 2.0)
                return "prophylactic_latent", round(min(latent_score, safety_cap), 3)
        return None, 0.0

    # Convert volatility drop to a normalized signal (0-1 scale).
    volatility_signal = max(0.0, min(1.0, volatility_drop / 40.0))
    threat_signal = max(0.0, threat_delta)
    soft_signal = max(0.0, soft_weight)

    direct_gate = (
        preventive_score >= (trigger + 0.02)
        or threat_signal >= max(config.threat_drop * 0.85, 0.2)
        or (soft_signal >= 0.65 and tactical_weight <= 0.6)
        or volatility_signal >= 0.65
    )

    if direct_gate:
        direct_score = max(score_threshold, preventive_score, soft_signal, threat_signal, 0.75)
        label = "prophylactic_direct"
        final_score = round(min(direct_score, safety_cap), 3)
    else:
        latent_base = 0.55 if effective_delta < 0 else 0.45
        latent_score = max(latent_base, preventive_score * 0.9, soft_signal)
        label = "prophylactic_latent"
        final_score = round(min(latent_score, safety_cap), 3)

    if abs(eval_before_cp) <= fail_eval_band_cp and drop_cp < -fail_drop_cp:
        return "prophylactic_meaningless", 0.0

    return label, final_score


def clamp_preventive_score(score: float, *, config: ProphylaxisConfig) -> float:
    """Limit the preventive score to a sensible range for downstream thresholds."""
    if score <= 0.0:
        return 0.0
    return min(score, config.safety_cap)
