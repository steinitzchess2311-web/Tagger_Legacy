"""
Control over Dynamics v2 - Detector functions for all CoD subtypes.

Extracted from core.py to improve modularity.
Contains all detect_cod_* functions:
- detect_cod_simplify
- detect_cod_plan_kill
- detect_cod_freeze_bind
- detect_cod_blockade_passed
- detect_cod_file_seal
- detect_cod_king_safety_shell
- detect_cod_space_clamp
- detect_cod_regroup_consolidate
- detect_cod_slowdown

And the COD_DETECTORS registry dictionary.

These detectors now use shared semantic detection from detectors.shared.control_patterns
and add CoD-specific gating, cooldown, and priority logic.
"""
from typing import Any, Dict, Optional, Tuple
import chess

from .control_helpers import (
    _cod_gate,
    _count_passed_push_targets,
    _control_tension_threshold,
    _forward_square,
    phase_bonus,
    reason,
)
from .config import (
    CENTER_FILES,
    CENTER_TOLERANCE,
    CONTROL_BLUNDER_THREAT_THRESH,
    CONTROL_DEFAULTS,
    CONTROL_EVAL_DROP,
    CONTROL_KING_SAFETY_THRESH,
    CONTROL_OPP_MOBILITY_DROP,
    CONTROL_SIMPLIFY_MIN_EXCHANGE,
    CONTROL_TACTICAL_WEIGHT_CEILING,
    CONTROL_TENSION_DELTA,
    CONTROL_VOLATILITY_DROP_CP,
)
from .thresholds import THRESHOLDS

# Import shared semantic detection functions
from ..detectors.shared.control_patterns import (
    is_simplify,
    is_plan_kill,
    is_freeze_bind,
    is_blockade_passed,
    is_file_seal,
    is_king_safety_shell,
    is_space_clamp,
    is_regroup_consolidate,
    is_slowdown,
)


PROPHYLAXIS_PREVENTIVE_TRIGGER_DEFAULT = THRESHOLDS["prophylaxis_preventive_trigger"]
PROPHYLAXIS_THREAT_DROP_DEFAULT = THRESHOLDS.get("prophylaxis_threat_drop", 0.3)

def detect_cod_simplify(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    CoD wrapper for simplify pattern detection.
    Uses shared semantic detection and adds gating logic.
    """
    # Use shared semantic detection
    semantic_result = is_simplify(ctx, cfg)

    # If semantic pattern not detected, return early
    if not semantic_result.passed:
        return None, {}

    # Apply CoD-specific gating
    # Build gate diagnostic info (for logging/debugging)
    metrics = semantic_result.metrics
    gate = _cod_gate(
        ctx,
        subtype="simplify",
        is_capture=ctx.get("is_capture", False),
        expected_recapture_pairs=metrics.get("expected_recapture_pairs", 0),
        exchange_pairs=metrics.get("exchange_pairs", 0),
        exchange_count=ctx.get("exchange_count", 0),
        captures_this_ply=ctx.get("captures_this_ply", 0),
        square_defended_by_opp=ctx.get("square_defended_by_opp", 0),
        total_active_drop=metrics.get("total_active_drop", 0),
        own_active_drop=ctx.get("own_active_drop", 0),
        opp_active_drop=ctx.get("opp_active_drop", 0),
        has_tactical_followup=ctx.get("has_immediate_tactical_followup", False),
        volatility_drop=metrics.get("volatility_drop_cp", 0.0),
        volatility_threshold=cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP),
        tension_delta=metrics.get("tension_delta", 0.0),
        tension_threshold=cfg.get("TENSION_DEC_MIN", CONTROL_TENSION_DELTA),
        opp_mobility_drop=metrics.get("opp_mobility_drop", 0.0),
        mobility_threshold=cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP),
        strict_mode=ctx.get("strict_mode", False),
        material_delta_cp=metrics.get("material_delta_self_cp", 0),
        captured_value_cp=ctx.get("captured_value_cp", 0),
        material_window_cp=30,
    )
    gate["passed"] = True  # Semantic check already passed

    # Build CoD candidate from semantic result
    candidate = {
        "name": "simplify",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_plan_kill(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    CoD wrapper for plan_kill pattern detection.
    Uses shared semantic detection and adds gating logic.
    """
    # Use shared semantic detection
    semantic_result = is_plan_kill(ctx, cfg)

    # If semantic pattern not detected, return early
    if not semantic_result.passed:
        return None, {}

    # Apply CoD-specific gating
    metrics = semantic_result.metrics
    bonus = phase_bonus(ctx, cfg)
    mob_base = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
    vol_base = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP)
    mob_threshold = mob_base + bonus["OP_MOB_DROP"]
    vol_threshold = vol_base + bonus["VOL_BONUS"]

    gate = _cod_gate(
        ctx,
        subtype="plan_kill",
        plan_drop=bool(ctx.get("plan_drop_passed")),
        preventive_score=metrics.get("preventive_score", 0.0),
        threat_delta=metrics.get("threat_delta", 0.0),
        mobility_drop=metrics.get("opp_mobility_drop", 0.0),
        volatility_drop=metrics.get("volatility_drop_cp", 0.0),
        tension_delta=ctx.get("tension_delta", 0.0),
        break_candidates_delta=metrics.get("break_candidates_delta", 0.0),
        mobility_threshold=mob_threshold,
        volatility_threshold=vol_threshold,
    )
    gate["plan_gate"] = metrics.get("plan_gate", False)
    gate["passed"] = True  # Semantic check already passed

    # Build CoD candidate from semantic result
    candidate = {
        "name": "plan_kill",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_freeze_bind(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    CoD wrapper for freeze_bind pattern detection.
    Uses shared semantic detection and adds gating logic.
    """
    semantic_result = is_freeze_bind(ctx, cfg)
    if not semantic_result.passed:
        return None, {}

    metrics = semantic_result.metrics
    phase_adjust = phase_bonus(ctx, cfg)
    vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + phase_adjust["VOL_BONUS"]
    mob_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)

    gate = _cod_gate(
        ctx,
        subtype="freeze_bind",
        tension_delta=metrics.get("tension_delta", 0.0),
        contact_ratio_drop=metrics.get("contact_ratio_drop", 0.0),
        op_pins_increase=metrics.get("op_pins_increase", 0),
        opp_mobility_drop=metrics.get("opp_mobility_drop", 0.0),
        volatility_drop_cp=metrics.get("volatility_drop_cp", 0.0),
        mobility_threshold=mob_threshold,
        volatility_threshold=vol_threshold,
    )
    gate.update({
        "t_ok": metrics.get("t_ok", False),
        "p_ok": metrics.get("p_ok", False),
        "env_ok": metrics.get("env_ok", False),
        "passed": True,
    })

    candidate = {
        "name": "freeze_bind",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_blockade_passed(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """CoD wrapper for blockade_passed pattern detection."""
    semantic_result = is_blockade_passed(ctx, cfg)
    if not semantic_result.passed:
        return None, {}
    metrics = semantic_result.metrics
    min_drop = float(cfg.get("PASSED_PUSH_MIN", CONTROL_DEFAULTS["PASSED_PUSH_MIN"]))
    gate = _cod_gate(
        ctx, subtype="blockade_passed",
        opp_passed_exists=ctx.get("opp_passed_exists", False),
        blockade_established=ctx.get("blockade_established", False),
        push_drop=metrics.get("opp_passed_push_drop", 0.0),
        push_threshold=min_drop,
        see_non_positive=metrics.get("see_non_positive", False),
        push_ok=metrics.get("push_ok", False),
    )
    gate["passed"] = True
    candidate = {
        "name": "blockade_passed",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_file_seal(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """CoD wrapper for file_seal pattern detection."""
    semantic_result = is_file_seal(ctx, cfg)
    if not semantic_result.passed:
        return None, {}
    metrics = semantic_result.metrics
    line_min = float(cfg.get("LINE_MIN", CONTROL_DEFAULTS["LINE_MIN"]))
    gate = _cod_gate(
        ctx, subtype="file_seal",
        opp_line_pressure_drop=metrics.get("opp_line_pressure_drop", 0.0),
        break_candidates_delta=metrics.get("break_candidates_delta", 0.0),
        mobility_drop=metrics.get("opp_mobility_drop", 0.0),
        line_min=line_min,
        volatility_drop=metrics.get("volatility_drop_cp", 0.0),
    )
    gate["passed"] = True
    candidate = {
        "name": "file_seal",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_king_safety_shell(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """CoD wrapper for king_safety_shell pattern detection."""
    semantic_result = is_king_safety_shell(ctx, cfg)
    if not semantic_result.passed:
        return None, {}
    metrics = semantic_result.metrics
    threshold = float(cfg.get("KS_MIN", CONTROL_DEFAULTS["KS_MIN"])) / 100.0
    gate = _cod_gate(
        ctx, subtype="king_safety_shell",
        king_safety_gain=metrics.get("king_safety_gain", 0.0),
        opp_tactics=metrics.get("opp_tactics_change_eval", 0.0),
        opp_mobility_drop=metrics.get("opp_mobility_drop", 0.0),
        king_safety_threshold=threshold,
    )
    gate["passed"] = True
    candidate = {
        "name": "king_safety_shell",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_space_clamp(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """CoD wrapper for space_clamp pattern detection."""
    semantic_result = is_space_clamp(ctx, cfg)
    if not semantic_result.passed:
        return None, {}
    metrics = semantic_result.metrics
    phase_adjust = phase_bonus(ctx, cfg)
    space_threshold = float(cfg.get("SPACE_MIN", CONTROL_DEFAULTS["SPACE_MIN"])) / 10.0
    mob_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
    vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + phase_adjust["VOL_BONUS"]
    gate = _cod_gate(
        ctx, subtype="space_clamp",
        space_gain=metrics.get("space_gain", 0.0),
        space_control_gain=metrics.get("space_control_gain", 0.0),
        opp_mobility_drop=metrics.get("opp_mobility_drop", 0.0),
        tension_delta=metrics.get("tension_delta", 0.0),
        volatility_drop_cp=metrics.get("volatility_drop_cp", 0.0),
        space_threshold=space_threshold,
        mobility_threshold=mob_threshold,
        volatility_threshold=vol_threshold,
    )
    gate.update({
        "space_ok": metrics.get("space_ok", False),
        "tension_ok": metrics.get("tension_ok", False),
        "mobility_ok": metrics.get("mobility_ok", False),
        "env_ok": metrics.get("env_ok", False),
        "passed": True,
    })
    candidate = {
        "name": "space_clamp",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_regroup_consolidate(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """CoD wrapper for regroup_consolidate pattern detection."""
    semantic_result = is_regroup_consolidate(ctx, cfg)
    if not semantic_result.passed:
        return None, {}
    metrics = semantic_result.metrics
    gate = _cod_gate(
        ctx, subtype="regroup_consolidate",
        king_safety_gain=metrics.get("king_safety_gain", 0.0),
        structure_gain=metrics.get("structure_gain", 0.0),
        self_mobility_change=metrics.get("self_mobility_change", 0.0),
        volatility_drop=metrics.get("volatility_drop_cp", 0.0),
    )
    gate["passed"] = True
    candidate = {
        "name": "regroup_consolidate",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


def detect_cod_slowdown(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """CoD wrapper for slowdown pattern detection."""
    semantic_result = is_slowdown(ctx, cfg)
    if not semantic_result.passed:
        return None, {}
    metrics = semantic_result.metrics
    vol_bonus = phase_bonus(ctx, cfg)["VOL_BONUS"]
    mob_bonus = phase_bonus(ctx, cfg)["OP_MOB_DROP"]
    vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + vol_bonus
    mob_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP) + mob_bonus
    phase_bucket = ctx.get("phase_bucket", "middlegame")
    tension_threshold = _control_tension_threshold(phase_bucket)
    gate = _cod_gate(
        ctx, subtype="slowdown",
        has_dynamic=ctx.get("has_dynamic_in_band", False),
        played_kind=ctx.get("played_kind"),
        eval_drop_cp=metrics.get("eval_drop_cp", 0),
        eval_threshold=cfg.get("EVAL_DROP_CP", CONTROL_EVAL_DROP),
        volatility_drop=metrics.get("volatility_drop_cp", 0.0),
        volatility_threshold=vol_threshold,
        tension_delta=metrics.get("tension_delta", 0.0),
        tension_threshold=tension_threshold,
        opp_mobility_drop=metrics.get("opp_mobility_drop", 0.0),
        mobility_threshold=mob_threshold,
    )
    gate["passed"] = True
    candidate = {
        "name": "slowdown",
        "metrics": metrics,
        "why": semantic_result.why,
        "score": semantic_result.score,
        "gate": gate,
    }
    return candidate, gate


COD_DETECTORS = {
    "simplify": detect_cod_simplify,
    "plan_kill": detect_cod_plan_kill,
    "freeze_bind": detect_cod_freeze_bind,
    "blockade_passed": detect_cod_blockade_passed,
    "file_seal": detect_cod_file_seal,
    "king_safety_shell": detect_cod_king_safety_shell,
    "space_clamp": detect_cod_space_clamp,
    "regroup_consolidate": detect_cod_regroup_consolidate,
    "slowdown": detect_cod_slowdown,
}
