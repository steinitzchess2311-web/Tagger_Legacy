"""
Control over Dynamics v2 - Helper functions for configuration and metrics.

Extracted from core.py to improve modularity.
Contains functions for:
- Control configuration management (_control_flags, _resolve_control_config, etc.)
- Phase and context helpers (_phase_bucket, _normalize_phase_label, etc.)
- Control metrics collection (_collect_control_metrics, _format_control_summary)
"""
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple

import chess

from rule_tagger2.core.engine_io import contact_profile
from .config import (
    CONTROL,
    CONTROL_OPP_MOBILITY_DROP,
    CONTROL_PHASE_WEIGHTS,
    CONTROL_TENSION_DELTA,
    CONTROL_TENSION_DELTA_ENDGAME,
    CONTROL_VOLATILITY_DROP_CP,
)

# Constants
STRICT_MODE_VOL_DELTA = 5
STRICT_MODE_MOB_DELTA = 1

_PHASE_NAME_NORMALIZED = {
    "opening": "OPEN",
    "open": "OPEN",
    "middlegame": "MID",
    "middle": "MID",
    "midgame": "MID",
    "mid": "MID",
    "endgame": "END",
    "end": "END",
}

_DEBUG_CTX_KEYS: Tuple[str, ...] = (
    "phase",
    "phase_ratio",
    "volatility_drop_cp",
    "opp_mobility_drop",
    "tension_delta",
    "king_safety_gain",
    "preventive_score",
    "threat_delta",
    "break_candidates_delta",
    "opp_line_pressure_drop",
    "selected_kind",
    "cooldown_hit",
    "suppressed_by",
)


def _control_flags() -> Tuple[bool, bool]:
    enabled = CONTROL.get("enabled")
    if enabled is None:
        enabled = CONTROL.get("ENABLED", True)
    strict_mode = CONTROL.get("strict_mode")
    if strict_mode is None:
        strict_mode = CONTROL.get("STRICT_MODE", False)
    return bool(enabled), bool(strict_mode)


def _strict_mode_config(base: Dict[str, Any]) -> Dict[str, Any]:
    cfg = deepcopy(base)
    vol_base = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP)
    if isinstance(vol_base, (int, float)):
        cfg["VOLATILITY_DROP_CP"] = vol_base + STRICT_MODE_VOL_DELTA
    else:
        cfg["VOLATILITY_DROP_CP"] = CONTROL_VOLATILITY_DROP_CP + STRICT_MODE_VOL_DELTA
    mob_base = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
    if isinstance(mob_base, (int, float)):
        cfg["OP_MOBILITY_DROP"] = mob_base + STRICT_MODE_MOB_DELTA
    else:
        cfg["OP_MOBILITY_DROP"] = CONTROL_OPP_MOBILITY_DROP + STRICT_MODE_MOB_DELTA
    phase_adjust = cfg.get("PHASE_ADJUST")
    if isinstance(phase_adjust, dict):
        for entry in phase_adjust.values():
            if not isinstance(entry, dict):
                continue
            vol_bonus = entry.get("VOL_BONUS", 0)
            if isinstance(vol_bonus, (int, float)):
                entry["VOL_BONUS"] = vol_bonus + STRICT_MODE_VOL_DELTA
            else:
                entry["VOL_BONUS"] = STRICT_MODE_VOL_DELTA
            mob_bonus = entry.get("OP_MOB_DROP", 0)
            if isinstance(mob_bonus, (int, float)):
                entry["OP_MOB_DROP"] = mob_bonus + STRICT_MODE_MOB_DELTA
            else:
                entry["OP_MOB_DROP"] = STRICT_MODE_MOB_DELTA
    cfg["_strict_deltas"] = {
        "VOLATILITY_DROP_CP": STRICT_MODE_VOL_DELTA,
        "OP_MOBILITY_DROP": STRICT_MODE_MOB_DELTA,
    }
    return cfg


def _resolve_control_config() -> Tuple[Dict[str, Any], bool, bool]:
    enabled, strict_mode = _control_flags()
    if strict_mode:
        cfg = _strict_mode_config(CONTROL)
    else:
        cfg = CONTROL
    return cfg, enabled, strict_mode


def phase_bonus(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, float]:
    """Return phase-dependent threshold adjustments."""
    adjust_map = cfg.get("PHASE_ADJUST", {})
    phase = ctx.get("phase") or "MID"
    defaults = {"VOL_BONUS": 0.0, "OP_MOB_DROP": 0.0}
    phase_adjust = adjust_map.get(phase, {})
    bonus = defaults.copy()
    bonus["VOL_BONUS"] = float(phase_adjust.get("VOL_BONUS", defaults["VOL_BONUS"]))
    bonus["OP_MOB_DROP"] = float(phase_adjust.get("OP_MOB_DROP", defaults["OP_MOB_DROP"]))
    return bonus


def reason(_: Dict[str, Any], message: str) -> str:
    """Lightweight helper to keep note assembly consistent."""
    return message.strip()


def _forward_square(square: int, color: chess.Color) -> Optional[int]:
    """Square immediately in front of the pawn for the given perspective."""
    step = 8 if color == chess.WHITE else -8
    target = square + step
    if 0 <= target <= 63:
        return target
    return None


def _count_passed_push_targets(
    board: chess.Board,
    color: chess.Color,
) -> Tuple[int, Dict[int, int]]:
    """
    Count immediate push targets for passed pawns and map blocking squares to pawn squares.
    """
    count = 0
    blockers: Dict[int, int] = {}
    for square in board.pieces(chess.PAWN, color):
        if not _is_passed_pawn(board, square, color):
            continue
        front = _forward_square(square, color)
        if front is None:
            continue
        if board.piece_at(front) is None:
            count += 1
        else:
            blockers[front] = square
    return count, blockers


def _is_passed_pawn(board: chess.Board, square: int, color: chess.Color) -> bool:
    """
    Compatibility wrapper for python-chess versions without Board.is_passed_pawn.
    """
    probe = getattr(board, "is_passed_pawn", None)
    if callable(probe):
        try:
            return bool(probe(square))  # python-chess >= 1.0
        except TypeError:
            return bool(probe(square, color))  # older signature with color

    enemy_color = not color
    enemy_pawns = board.pieces(chess.PAWN, enemy_color)
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    rank_range = range(rank_idx + 1, 8) if color == chess.WHITE else range(rank_idx - 1, -1, -1)
    for df in (-1, 0, 1):
        f = file_idx + df
        if f < 0 or f > 7:
            continue
        for r in rank_range:
            target = chess.square(f, r)
            if target in enemy_pawns:
                return False
    return True


def _phase_bucket(phase_ratio: float) -> str:
    if phase_ratio <= 0.33:
        return "endgame"
    if phase_ratio <= 0.66:
        return "middlegame"
    return "opening"


def _normalize_phase_label(phase_name: Optional[str]) -> str:
    if not phase_name:
        return "MID"
    lowered = phase_name.lower()
    return _PHASE_NAME_NORMALIZED.get(lowered, phase_name.upper())


def _maybe_attach_control_context_snapshot(ctx: Dict[str, Any], notes: Dict[str, str]) -> None:
    if not CONTROL.get("DEBUG_CONTEXT"):
        return
    summary_parts = []
    for key in _DEBUG_CTX_KEYS:
        value = ctx.get(key)
        if isinstance(value, float):
            formatted = f"{value:+.2f}"
        else:
            formatted = str(value)
        summary_parts.append(f"{key}={formatted}")
    notes["control_ctx_debug"] = ", ".join(summary_parts)


def _count_legal_moves_for(board: chess.Board, color: chess.Color) -> int:
    probe = board.copy(stack=False)
    probe.turn = color
    return sum(1 for _ in probe.legal_moves)


def _contact_stats(board: chess.Board, color: chess.Color) -> Dict[str, float]:
    probe = board.copy(stack=False)
    probe.turn = color
    ratio, total, capture_moves, checking_moves = contact_profile(probe)
    contact_total = capture_moves + checking_moves
    return {
        "ratio": ratio,
        "total": total,
        "contact": contact_total,
        "captures": capture_moves,
        "checks": checking_moves,
    }


def _control_tension_threshold(phase_bucket: str) -> float:
    weight = CONTROL_PHASE_WEIGHTS.get(phase_bucket, 1.0)
    base = CONTROL_TENSION_DELTA * weight
    if phase_bucket == "endgame":
        base = min(base, CONTROL_TENSION_DELTA_ENDGAME)
    return base


def _current_ply_index(board: chess.Board, actor: chess.Color) -> int:
    base = max(0, (board.fullmove_number - 1) * 2)
    return base if actor == chess.WHITE else base + 1


def _active_piece_count(board: chess.Board) -> int:
    return sum(
        1
        for piece in board.piece_map().values()
        if piece.piece_type not in (chess.KING, chess.PAWN)
    )


def _active_piece_count_for(board: chess.Board, color: chess.Color) -> int:
    """Count active non-pawn pieces for a specific side."""
    total = 0
    for square in chess.SquareSet(board.occupied_co[color]):
        piece = board.piece_at(square)
        if piece and piece.piece_type not in (chess.KING, chess.PAWN):
            total += 1
    return total


def _collect_control_metrics(
    board: chess.Board,
    played_board: chess.Board,
    actor: chess.Color,
    played_move: chess.Move,
    phase_ratio: float,
    delta_eval_cp: int,
    drop_cp: int,
    change_played_vs_before: Dict[str, float],
    opp_change_played_vs_before: Dict[str, float],
    analysis_meta: Dict[str, Any],
    material_delta_self: float,
) -> Dict[str, Any]:
    phase_name = _phase_bucket(phase_ratio)
    volatility_before_cp = abs(analysis_meta.get("depth_jump_cp", 0)) + abs(analysis_meta.get("deepening_gain_cp", 0))
    volatility_after_cp = analysis_meta.get("control_volatility_after_cp")
    if volatility_after_cp is None:
        volatility_after_cp = max(abs(drop_cp), abs(delta_eval_cp))
    volatility_drop_cp = max(0.0, volatility_before_cp - volatility_after_cp)

    self_contact_before = _contact_stats(board, actor)
    opp_contact_before = _contact_stats(board, not actor)
    self_contact_after = _contact_stats(played_board, actor)
    opp_contact_after = _contact_stats(played_board, played_board.turn)

    tension_before = self_contact_before["contact"] + opp_contact_before["contact"]
    tension_after = self_contact_after["contact"] + opp_contact_after["contact"]
    tension_delta = tension_after - tension_before

    opp_mobility_before = _count_legal_moves_for(board, not actor)
    opp_mobility_after = _count_legal_moves_for(played_board, played_board.turn)
    opp_mobility_drop = opp_mobility_before - opp_mobility_after

    captured_piece = board.piece_at(played_move.to_square)
    active_before = _active_piece_count(board)
    active_after = _active_piece_count(played_board)
    own_active_before = _active_piece_count_for(board, actor)
    own_active_after = _active_piece_count_for(played_board, actor)
    opp_active_before = _active_piece_count_for(board, not actor)
    opp_active_after = _active_piece_count_for(played_board, not actor)

    own_active_drop = max(0, own_active_before - own_active_after)
    opp_active_drop = max(0, opp_active_before - opp_active_after)
    total_active_drop = max(0, active_before - active_after)

    captures_this_ply = 1 if (captured_piece or board.is_en_passant(played_move)) else 0
    square_defended_by_opp = len(played_board.attackers(not actor, played_move.to_square))
    square_defended_by_self = len(played_board.attackers(actor, played_move.to_square))

    piece_values_cp = {
        chess.PAWN: 100,
        chess.KNIGHT: 300,
        chess.BISHOP: 300,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0,
    }
    captured_value_cp = piece_values_cp.get(captured_piece.piece_type, 0) if captured_piece else 0
    material_delta_self_cp = int(round(material_delta_self * 100))

    metrics = {
        "phase_bucket": phase_name,
        "volatility_before_cp": volatility_before_cp,
        "volatility_after_cp": volatility_after_cp,
        "volatility_drop_cp": volatility_drop_cp,
        "tension_before": tension_before,
        "tension_after": tension_after,
        "tension_delta": tension_delta,
        "self_contact_before": self_contact_before,
        "self_contact_after": self_contact_after,
        "opp_contact_before": opp_contact_before,
        "opp_contact_after": opp_contact_after,
        "opp_mobility_before": opp_mobility_before,
        "opp_mobility_after": opp_mobility_after,
        "opp_mobility_drop": opp_mobility_drop,
        "structure_gain": change_played_vs_before.get("structure", 0.0),
        "center_gain": change_played_vs_before.get("center_control", 0.0),
        "king_safety_gain": change_played_vs_before.get("king_safety", 0.0),
        "self_mobility_change": change_played_vs_before.get("mobility", 0.0),
        "opp_mobility_change_eval": opp_change_played_vs_before.get("mobility", 0.0),
        "opp_tactics_change_eval": opp_change_played_vs_before.get("tactics", 0.0),
        "material_delta_self": material_delta_self,
        "captured_piece_type": captured_piece.piece_type if captured_piece else None,
        "is_capture": bool(captured_piece or board.is_en_passant(played_move)),
        "active_piece_drop": total_active_drop,
        "own_active_drop": own_active_drop,
        "opp_active_drop": opp_active_drop,
        "total_active_drop": total_active_drop,
        "captures_this_ply": captures_this_ply,
        "square_defended_by_opp": square_defended_by_opp,
        "square_defended_by_self": square_defended_by_self,
        "captured_value_cp": captured_value_cp,
        "material_delta_self_cp": material_delta_self_cp,
    }
    return metrics


def _format_control_summary(kind: str, metrics: Dict[str, Any]) -> str:
    if kind == "slowdown":
        return (
            f"CoD.slowdown: eval drop {metrics['eval_drop_cp']/100:.2f}, "
            f"volatility drop {metrics['volatility_drop_cp']:.1f}cp, "
            f"tensionΔ {metrics['tension_delta']:+.0f}, "
            f"opp mobilityΔ {metrics['opp_mobility_drop']:+.0f}"
        )
    if kind == "simplify":
        captured = metrics.get("captured_piece")
        captured_label = captured if captured else "trade"
        return (
            f"CoD.simplify: {captured_label} reduced active pieces by {metrics['active_piece_drop']}, "
            f"volatility drop {metrics['volatility_drop_cp']:.1f}cp"
        )
    if kind == "freeze":
        return (
            f"CoD.freeze: structure {metrics['structure_gain']:+.2f}, "
            f"opp mobilityΔ {metrics['opp_mobility_drop']:+.0f}, tensionΔ {metrics['tension_delta']:+.0f}"
        )
    if kind == "king_safety":
        return (
            f"CoD.king_safety: king safety {metrics['king_safety_gain']:+.2f}, "
            f"opp tacticsΔ {metrics['opp_tactics_change_eval']:+.2f}"
        )
    if kind == "prophylaxis":
        return (
            "CoD.prophylaxis: preventive move dampened dynamics "
            f"(volatility drop {metrics['volatility_drop_cp']:.1f}cp, "
            f"opp mobilityΔ {metrics['opp_mobility_drop']:+.0f})"
        )
    return "control_over_dynamics"


def _cod_gate(ctx: Dict[str, Any], **entries: Any) -> Dict[str, Any]:
    gate = dict(entries)
    return gate
