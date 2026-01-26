"""
Sacrifice classification helpers ported from the legacy rule tagger.
"""
from __future__ import annotations

from typing import Dict

import chess

PIECE_VALUES = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.0,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
    chess.KING: 0.0,
}

SACRIFICE_MIN_LOSS = 0.5  # material loss (pawns) needed to treat as sacrifice
SACRIFICE_EVAL_TOLERANCE = 0.6  # evaluation drop tolerance to still consider successful
SACRIFICE_KING_DROP_THRESHOLD = -0.1  # opponent king safety delta required for tactical label
EXCHANGE_EVAL_TOLERANCE = 0.15  # treat near-equal exchanges as non-sacrificial


def _en_passant_capture_square(board: chess.Board, move: chess.Move) -> int | None:
    if not board.is_en_passant(move):
        return None
    direction = 1 if board.turn == chess.BLACK else -1
    return move.to_square + 8 * direction


def _captured_piece_value(board: chess.Board, move: chess.Move) -> float:
    if not board.is_capture(move):
        return 0.0
    if board.is_en_passant(move):
        square = _en_passant_capture_square(board, move)
        if square is None:
            return 0.0
        captured_piece = chess.Piece(chess.PAWN, not board.turn)
    else:
        captured_piece = board.piece_at(move.to_square)
    if captured_piece is None:
        return 0.0
    return PIECE_VALUES.get(captured_piece.piece_type, 0.0)


def _piece_value_on(board: chess.Board, square: int) -> float:
    piece = board.piece_at(square)
    if piece is None:
        return 0.0
    return PIECE_VALUES.get(piece.piece_type, 0.0)


def _opponent_wins_material(board_after: chess.Board, target_square: int, risk_threshold: float) -> bool:
    opponent = board_after.turn
    attackers = board_after.attackers(opponent, target_square)
    if not attackers:
        return False
    return any(_piece_value_on(board_after, sq) <= risk_threshold for sq in attackers)


def _looks_like_even_exchange(
    board_before: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    eval_before: float,
    eval_played: float,
) -> bool:
    """
    Detect offer trades where the mover invites an equal exchange (e.g., bishop-for-bishop),
    so the sacrifice detector does not misclassify them.
    """
    if board_before.is_capture(move):
        return False

    mover = board_before.piece_at(move.from_square)
    if mover is None:
        return False
    mover_value = PIECE_VALUES.get(mover.piece_type, 0.0)
    if mover_value == 0.0:
        return False

    # Only treat near-equal eval outcomes as offers; real sacs drop eval more.
    if abs(eval_played - eval_before) > EXCHANGE_EVAL_TOLERANCE:
        return False

    target = move.to_square
    opponent = board_after.turn
    attackers = board_after.attackers(opponent, target)
    if not attackers:
        return False

    for attacker_sq in attackers:
        attacker_piece = board_after.piece_at(attacker_sq)
        if attacker_piece is None:
            continue
        attacker_value = PIECE_VALUES.get(attacker_piece.piece_type, 0.0)
        if attacker_value == 0.0:
            continue
        if abs(attacker_value - mover_value) > 0.01:
            continue

        capture = chess.Move(attacker_sq, target)
        if capture not in board_after.legal_moves:
            continue

        sim = board_after.copy(stack=False)
        sim.push(capture)

        # After the capture it is the original mover's turn again.
        defenders = sim.attackers(sim.turn, target)
        for defender_sq in defenders:
            defender_piece = sim.piece_at(defender_sq)
            if defender_piece is None:
                continue
            defender_value = PIECE_VALUES.get(defender_piece.piece_type, 0.0)
            if defender_value == 0.0:
                continue

            recapture = chess.Move(defender_sq, target)
            if recapture not in sim.legal_moves:
                continue

            if defender_value <= attacker_value + 0.01:
                return True

    return False


def classify_sacrifice(
    board_before: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    eval_before: float,
    eval_played: float,
    component_deltas: Dict[str, float],
    opp_metrics_before: Dict[str, float],
    opp_metrics_played: Dict[str, float],
    tactical_weight: float,
    aggression_score: float,
) -> tuple[Dict[str, bool], Dict[str, float]]:
    """
    Classify sacrifice intentions based on material/evaluation deltas.

    Returns a mapping of sacrifice tags to booleans.
    """
    tags = {
        "tactical_sacrifice": False,
        "positional_sacrifice": False,
        "inaccurate_tactical_sacrifice": False,
        "speculative_sacrifice": False,
        "desperate_sacrifice": False,
        "tactical_combination_sacrifice": False,
        "tactical_initiative_sacrifice": False,
        "positional_structure_sacrifice": False,
        "positional_space_sacrifice": False,
    }

    piece = board_before.piece_at(move.from_square)
    context = {
        "material_loss": 0.0,
        "eval_loss": 0.0,
        "king_drop": 0.0,
    }

    if piece is None:
        return tags, context

    piece_value = PIECE_VALUES.get(piece.piece_type, 0.0)
    captured_value = _captured_piece_value(board_before, move)
    material_loss = piece_value - captured_value
    context["material_loss"] = material_loss

    if _looks_like_even_exchange(board_before, board_after, move, eval_before, eval_played):
        return tags, context

    if material_loss < SACRIFICE_MIN_LOSS:
        return tags, context

    if not _opponent_wins_material(board_after, move.to_square, material_loss):
        return tags, context

    eval_change = eval_played - eval_before
    eval_loss = abs(eval_change)

    opp_before_ks = opp_metrics_before.get("king_safety", 0.0)
    opp_after_ks = opp_metrics_played.get("king_safety", 0.0)
    opp_king_delta = opp_after_ks - opp_before_ks
    king_drop = opp_king_delta <= SACRIFICE_KING_DROP_THRESHOLD

    context["eval_loss"] = eval_loss
    context["king_drop"] = opp_king_delta

    if king_drop and eval_loss <= SACRIFICE_EVAL_TOLERANCE:
        tags["tactical_sacrifice"] = True
    elif not king_drop and eval_loss <= SACRIFICE_EVAL_TOLERANCE:
        tags["positional_sacrifice"] = True
    elif king_drop:
        tags["inaccurate_tactical_sacrifice"] = True
    else:
        tags["speculative_sacrifice"] = True

    if eval_before <= -3.0:
        tags["desperate_sacrifice"] = True

    mobility_gain = component_deltas.get("mobility", 0.0)
    center_gain = component_deltas.get("center_control", 0.0)
    structure_gain = component_deltas.get("structure", 0.0)
    king_gain = component_deltas.get("king_safety", 0.0)
    tactics_gain = component_deltas.get("tactics", 0.0)

    if tags["tactical_sacrifice"]:
        combination_signal = tactics_gain >= 0.2 or tactical_weight >= 0.6
        initiative_signal = (
            mobility_gain >= 0.1 or center_gain >= 0.1 or aggression_score >= 0.4
        )
        if combination_signal:
            tags["tactical_combination_sacrifice"] = True
        if initiative_signal:
            tags["tactical_initiative_sacrifice"] = True

    if tags["positional_sacrifice"]:
        structure_signal = structure_gain >= 0.15 or king_gain >= 0.1
        space_signal = mobility_gain >= 0.1 or center_gain >= 0.1
        if structure_signal:
            tags["positional_structure_sacrifice"] = True
        if space_signal or not structure_signal:
            tags["positional_space_sacrifice"] = True

    return tags, context
