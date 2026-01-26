"""
Pure semantic pattern detection for control-based behaviors.

This module contains functions that detect specific positional patterns without
any decision-layer gating, cooldown, or mutual exclusion logic. These functions
can be reused by:
- CoD detectors (legacy/cod_detectors.py) - with dynamic gating
- control_* detectors (detectors/control.py) - without gating

Each function:
- Takes a context dict (ctx) and configuration dict (cfg)
- Returns a SemanticResult with:
  * passed: bool - whether the pattern is detected
  * metrics: dict - raw measurements used for detection
  * why: str - human-readable explanation
  * score: float - strength/severity score for prioritization
  * severity: Optional[str] - "weak", "moderate", "strong" (optional)

Context field dependencies are documented in each function's docstring.
"""

from typing import Any, Dict, Optional, NamedTuple
import chess


class SemanticResult(NamedTuple):
    """Result of semantic pattern detection."""
    passed: bool
    metrics: Dict[str, Any]
    why: str
    score: float
    severity: Optional[str] = None


def is_simplify(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect simplification pattern via exchanges.

    Pattern: Exchanging pieces to reduce complexity, lower volatility, and
    restrict opponent mobility in a materially balanced way.

    Required ctx fields:
    - allow_positional: bool - must be True
    - phase: str - game phase for bonus calculation
    - captures_this_ply: int - number of captures made
    - square_defended_by_opp: int - defenders on target square
    - has_immediate_tactical_followup: bool - tactical continuation exists
    - is_capture: bool - whether move is a capture
    - total_active_drop: int OR (own_active_drop, opp_active_drop)
    - exchange_count: int - total exchanges
    - volatility_drop_cp: float - volatility reduction
    - tension_delta: float - tension change
    - opp_mobility_drop: float - opponent mobility reduction
    - material_delta_self_cp: int - material balance change
    - captured_value_cp: int - value of captured piece
    - captured_piece_type: Optional[int] - chess piece type constant
    - strict_mode: bool - whether to use stricter thresholds

    Config parameters:
    - VOLATILITY_DROP_CP: float - base volatility threshold
    - TENSION_DEC_MIN: float - tension decrease threshold
    - OP_MOBILITY_DROP: float - mobility drop threshold
    - SIMPLIFY_MIN_EXCHANGE: int - minimum exchanges in strict mode
    """
    from ...legacy.control_helpers import phase_bonus, reason
    from ...legacy.config import (
        CONTROL_VOLATILITY_DROP_CP,
        CONTROL_TENSION_DELTA,
        CONTROL_OPP_MOBILITY_DROP,
        CONTROL_SIMPLIFY_MIN_EXCHANGE,
    )

    if not ctx.get("allow_positional", False):
        return SemanticResult(
            passed=False,
            metrics={},
            why="not allowed for non-positional context",
            score=0.0,
        )

    # Calculate thresholds with phase adjustment
    phase_adjust = phase_bonus(ctx, cfg)
    vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + phase_adjust["VOL_BONUS"]
    tension_threshold = cfg.get("TENSION_DEC_MIN", CONTROL_TENSION_DELTA)
    mobility_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)

    # Transaction check: exchanges or active piece reduction
    strict_mode = bool(ctx.get("strict_mode"))
    captures_this_ply = ctx.get("captures_this_ply", 0)
    square_defended_by_opp = ctx.get("square_defended_by_opp", 0)
    has_followup = ctx.get("has_immediate_tactical_followup", False)
    expected_recapture_pairs = 1 if ctx.get("is_capture", False) and square_defended_by_opp >= 1 and not has_followup else 0

    total_active_drop = ctx.get("total_active_drop")
    if total_active_drop is None:
        own_drop = ctx.get("own_active_drop", 0)
        opp_drop = ctx.get("opp_active_drop", 0)
        total_active_drop = max(0, (own_drop or 0)) + max(0, (opp_drop or 0))

    exchange_pairs = min(2, captures_this_ply + expected_recapture_pairs)
    exchange_count = ctx.get("exchange_count", 0)
    transaction_ok = (
        exchange_pairs >= 1
        or exchange_count >= 1
        or (total_active_drop or 0) >= 1
    )
    if strict_mode and exchange_pairs < max(2, cfg.get("SIMPLIFY_MIN_EXCHANGE", CONTROL_SIMPLIFY_MIN_EXCHANGE)) and exchange_count < 1:
        transaction_ok = False

    # Environment check: volatility/tension/mobility
    volatility_drop = ctx.get("volatility_drop_cp", 0.0)
    tension_delta = ctx.get("tension_delta", 0.0)
    opp_mobility_drop = ctx.get("opp_mobility_drop", 0.0)
    env_ok = (
        volatility_drop >= vol_threshold
        and tension_delta <= tension_threshold
        and opp_mobility_drop >= mobility_threshold * 0.8
    )

    # Material balance check
    material_delta_self_cp = ctx.get("material_delta_self_cp")
    if material_delta_self_cp is None:
        material_delta_self_cp = int(round(ctx.get("material_delta_self", 0.0) * 100))
    captured_value_cp = ctx.get("captured_value_cp", 0)
    if expected_recapture_pairs:
        window_cp = max(30, int(round(captured_value_cp * 1.1)))
    else:
        window_cp = 30
    material_ok = abs(material_delta_self_cp or 0) <= window_cp

    passed = env_ok and transaction_ok and material_ok

    # Build result
    capture_type = ctx.get("captured_piece_type")
    captured_label = chess.piece_name(capture_type) if capture_type else "trade"

    metrics = {
        "volatility_drop_cp": volatility_drop,
        "opp_mobility_drop": opp_mobility_drop,
        "tension_delta": tension_delta,
        "exchange_pairs": exchange_pairs,
        "expected_recapture_pairs": expected_recapture_pairs,
        "total_active_drop": total_active_drop,
        "material_delta_self_cp": material_delta_self_cp or 0,
    }

    score = (
        volatility_drop
        + max(0, opp_mobility_drop) * 10
        + exchange_pairs * 40
        - abs(tension_delta) * 2
    )

    why = reason(
        ctx,
        f"{captured_label} exchange_pairs={exchange_pairs}, "
        f"totalActiveDrop={total_active_drop}; vol {volatility_drop:.1f}cp, "
        f"tensionΔ {tension_delta:+.1f}, opMobΔ {opp_mobility_drop:+.1f}"
    ) if passed else "simplify conditions not met"

    # Determine severity based on score
    if passed:
        if score >= 200:
            severity = "strong"
        elif score >= 100:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_plan_kill(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect plan-killing pattern.

    Pattern: Preventing opponent's plans via plan drop detection or preventive squeeze.

    Required ctx fields:
    - preventive_score: float - prophylaxis strength
    - threat_delta: float - threat level change
    - plan_drop_passed: bool - plan drop detected
    - break_candidates_delta: float - break candidate change
    - opp_mobility_drop: float - opponent mobility reduction
    - volatility_drop_cp: float - volatility reduction
    - vol_drop_cp: float - alias for volatility_drop_cp
    - tension_delta: float - tension change
    - phase: str - game phase
    - allow_positional: bool - positional context allowed
    - is_capture: bool - whether move is a capture
    - square_defended_by_opp: int - defenders on target square
    - captures_this_ply: int - captures made
    - captured_piece_type: Optional[int] - piece type

    Config parameters:
    - OP_MOBILITY_DROP: float - mobility threshold
    - VOLATILITY_DROP_CP: float - volatility threshold
    - PREVENTIVE_TRIGGER: float - preventive score trigger
    - THREAT_DROP: float - threat drop threshold
    - PLAN_KILL_STRICT: bool - use AND instead of OR for plan gate
    - VOL_GATE_FOR_PLAN: bool - require volatility for plan drop
    """
    from ...legacy.control_helpers import phase_bonus, reason
    from ...legacy.config import (
        CONTROL_OPP_MOBILITY_DROP,
        CONTROL_VOLATILITY_DROP_CP,
    )
    from ...legacy.thresholds import THRESHOLDS

    PROPHYLAXIS_PREVENTIVE_TRIGGER_DEFAULT = THRESHOLDS["prophylaxis_preventive_trigger"]
    PROPHYLAXIS_THREAT_DROP_DEFAULT = THRESHOLDS.get("prophylaxis_threat_drop", 0.3)

    preventive_score = ctx.get("preventive_score", 0.0)
    threat_delta = ctx.get("threat_delta", 0.0)
    plan_drop = bool(ctx.get("plan_drop_passed"))
    break_delta = ctx.get("break_candidates_delta", 0.0)
    mobility_drop = ctx.get("opp_mobility_drop", 0.0)
    volatility_drop = ctx.get("volatility_drop_cp", 0.0)
    vol_drop_value = ctx.get("vol_drop_cp", volatility_drop)

    # Calculate thresholds
    bonus = phase_bonus(ctx, cfg)
    mob_base = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
    vol_base = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP)
    mob_threshold = mob_base + bonus["OP_MOB_DROP"]
    vol_threshold = vol_base + bonus["VOL_BONUS"]

    # Plan drop gate
    plan_gate = False
    if plan_drop:
        if cfg.get("PLAN_KILL_STRICT", True):
            plan_gate = (break_delta <= -1.0) and (mobility_drop >= mob_threshold)
        else:
            plan_gate = (break_delta <= -1.0) or (mobility_drop >= mob_threshold)
        if cfg.get("VOL_GATE_FOR_PLAN", True):
            plan_gate = plan_gate and (vol_drop_value >= vol_threshold)

    # Preventive fallback
    trigger = float(cfg.get("PREVENTIVE_TRIGGER", PROPHYLAXIS_PREVENTIVE_TRIGGER_DEFAULT))
    threat_drop_threshold = float(cfg.get("THREAT_DROP", PROPHYLAXIS_THREAT_DROP_DEFAULT))
    contested_trade = bool(
        ctx.get("is_capture", False)
        and ctx.get("square_defended_by_opp", 0) >= 1
        and ctx.get("captures_this_ply", 0) <= 1
        and ctx.get("captured_piece_type") in (chess.BISHOP, chess.KNIGHT)
    )
    fallback = (
        ctx.get("allow_positional", False)
        and preventive_score >= trigger
        and not contested_trade
        and (
            threat_delta >= threat_drop_threshold
            or mobility_drop >= mob_base
            or vol_drop_value >= vol_threshold
        )
    )

    passed = plan_gate or fallback
    source = "plan drop" if plan_drop else "preventive squeeze"

    metrics = {
        "preventive_score": preventive_score,
        "threat_delta": threat_delta,
        "opp_mobility_drop": mobility_drop,
        "volatility_drop_cp": volatility_drop,
        "break_candidates_delta": break_delta,
        "plan_gate": plan_gate,
        "fallback": fallback,
    }

    score = preventive_score * 120 + max(mobility_drop, 0.0) * 20 + (10 if plan_drop else 0)

    why = reason(
        ctx,
        f"{source} killed opponent plan (preventive {preventive_score:+.2f}, threatΔ {threat_delta:+.2f})",
    ) if passed else "plan_kill conditions not met"

    if passed:
        if score >= 40:
            severity = "strong"
        elif score >= 20:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_freeze_bind(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect freeze/bind pattern.

    Pattern: Freezing or binding opponent pieces via reduced contact/tension
    and increased pins or mobility restrictions.

    Required ctx fields:
    - allow_positional: bool - must be True
    - tension_delta: float - tension change
    - contact_ratio_drop: float - contact ratio reduction
    - op_pins_increase: int - opponent pins increase
    - opp_mobility_drop: float - opponent mobility reduction
    - volatility_drop_cp: float - volatility reduction
    - vol_drop_cp: float - alias for volatility_drop_cp
    - phase: str - game phase

    Config parameters:
    - VOLATILITY_DROP_CP: float - volatility threshold
    - OP_MOBILITY_DROP: float - mobility threshold
    """
    from ...legacy.control_helpers import phase_bonus, reason
    from ...legacy.config import (
        CONTROL_VOLATILITY_DROP_CP,
        CONTROL_OPP_MOBILITY_DROP,
    )

    if not ctx.get("allow_positional", False):
        return SemanticResult(
            passed=False,
            metrics={},
            why="not allowed for non-positional context",
            score=0.0,
        )

    tension_delta = ctx.get("tension_delta", 0.0)
    contact_ratio_drop = ctx.get("contact_ratio_drop", 0.0)
    op_pins_inc = ctx.get("op_pins_increase", 0)
    opp_mob_drop = ctx.get("opp_mobility_drop", 0.0)
    vol_drop = ctx.get("volatility_drop_cp", 0.0)
    vol_drop_alias = ctx.get("vol_drop_cp", vol_drop)

    # Calculate thresholds
    phase_adjust = phase_bonus(ctx, cfg)
    vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + phase_adjust["VOL_BONUS"]
    mob_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)

    # Check conditions
    t_ok = (tension_delta <= 0.0) or (contact_ratio_drop <= -0.05)
    p_ok = (op_pins_inc >= 1) or (opp_mob_drop >= mob_threshold)
    env_ok = vol_drop_alias >= vol_threshold
    passed = t_ok and p_ok and env_ok

    metrics = {
        "tension_delta": tension_delta,
        "contact_ratio_drop": contact_ratio_drop,
        "opp_mobility_drop": opp_mob_drop,
        "op_pins_increase": op_pins_inc,
        "volatility_drop_cp": vol_drop_alias,
        "t_ok": t_ok,
        "p_ok": p_ok,
        "env_ok": env_ok,
    }

    score = max(-tension_delta, 0.0) * 40 + max(opp_mob_drop, 0.0) * 30 + op_pins_inc * 20

    why = reason(
        ctx,
        f"froze bind: tensionΔ {tension_delta:+.1f}, contact ratio {contact_ratio_drop:+.2f}, "
        f"opp mobilityΔ {opp_mob_drop:+.1f}",
    ) if passed else "freeze_bind conditions not met"

    if passed:
        if score >= 100:
            severity = "strong"
        elif score >= 50:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_blockade_passed(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect blockade of passed pawn pattern.

    Pattern: Establishing a blockade on opponent's passed pawn, reducing
    their ability to push it forward.

    Required ctx fields:
    - opp_passed_exists: bool - opponent has passed pawn
    - blockade_established: bool - blockade is set up
    - opp_passed_push_drop: float - reduction in push ability
    - blockade_front_square_see_non_positive: bool - SEE evaluation
    - blockade_file: Optional[str] - file where blockade is established

    Config parameters:
    - PASSED_PUSH_MIN: float - minimum push drop threshold
    - ALLOW_SEE_BLOCKADE: bool - allow SEE-based blockades
    """
    from ...legacy.control_helpers import reason
    from ...legacy.config import CONTROL_DEFAULTS

    opp_passed_exists = ctx.get("opp_passed_exists", False)
    blockade_established = ctx.get("blockade_established", False)
    push_drop = ctx.get("opp_passed_push_drop", 0.0)
    see_support = bool(ctx.get("blockade_front_square_see_non_positive"))

    min_drop = float(cfg.get("PASSED_PUSH_MIN", CONTROL_DEFAULTS["PASSED_PUSH_MIN"]))
    push_ok = push_drop >= min_drop
    if cfg.get("ALLOW_SEE_BLOCKADE", True):
        push_ok = push_ok or see_support

    passed = opp_passed_exists and blockade_established and push_ok

    metrics = {
        "opp_passed_push_drop": push_drop,
        "blockade_file": ctx.get("blockade_file"),
        "see_non_positive": see_support,
        "push_ok": push_ok,
    }

    score = push_drop * 50

    file_label = ctx.get("blockade_file") or ""
    support_note = " (SEE≤0)" if see_support else ""
    why = reason(
        ctx,
        f"blockaded passed pawn{(' on ' + file_label) if file_label else ''}{support_note}"
    ) if passed else "blockade_passed conditions not met"

    if passed:
        if score >= 100:
            severity = "strong"
        elif score >= 50:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_file_seal(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect file sealing pattern.

    Pattern: Sealing files against opponent activity by reducing their
    line pressure and breaking lanes.

    Required ctx fields:
    - opp_line_pressure_drop: float - opponent line pressure reduction
    - break_candidates_delta: float - breaking lanes change
    - opp_mobility_drop: float - opponent mobility reduction
    - volatility_drop_cp: float - volatility reduction

    Config parameters:
    - LINE_MIN: float - minimum line pressure drop
    - VOLATILITY_DROP_CP: float - volatility threshold
    """
    from ...legacy.control_helpers import reason
    from ...legacy.config import CONTROL_DEFAULTS, CONTROL_VOLATILITY_DROP_CP

    pressure_drop = ctx.get("opp_line_pressure_drop", 0.0)
    break_delta = ctx.get("break_candidates_delta", 0.0)
    mobility_drop = ctx.get("opp_mobility_drop", 0.0)
    vol_drop = ctx.get("volatility_drop_cp", 0.0)

    line_min = float(cfg.get("LINE_MIN", CONTROL_DEFAULTS["LINE_MIN"]))

    passed = (
        pressure_drop >= line_min
        or break_delta <= -1.0
    )
    passed = passed and vol_drop >= cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) * 0.5

    metrics = {
        "opp_line_pressure_drop": pressure_drop,
        "break_candidates_delta": break_delta,
        "opp_mobility_drop": mobility_drop,
        "volatility_drop_cp": vol_drop,
    }

    score = pressure_drop * 40 + max(-break_delta, 0.0) * 25

    why = reason(
        ctx,
        f"sealed file, pressure drop {pressure_drop:.1f}, break lanes Δ {break_delta:+.1f}"
    ) if passed else "file_seal conditions not met"

    if passed:
        if score >= 80:
            severity = "strong"
        elif score >= 40:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_king_safety_shell(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect king safety reinforcement pattern.

    Pattern: Reinforcing king safety shell while reducing opponent's
    tactical opportunities or mobility.

    Required ctx fields:
    - king_safety_gain: float - king safety improvement
    - opp_tactics_change_eval: float - opponent tactical changes
    - opp_mobility_drop: float - opponent mobility reduction

    Config parameters:
    - KS_MIN: float - minimum king safety gain (in centipawns)
    - OP_MOBILITY_DROP: float - mobility threshold
    """
    from ...legacy.control_helpers import reason
    from ...legacy.config import CONTROL_DEFAULTS, CONTROL_OPP_MOBILITY_DROP

    ks_gain = ctx.get("king_safety_gain", 0.0)
    opp_tactics = ctx.get("opp_tactics_change_eval", 0.0)
    mobility_drop = ctx.get("opp_mobility_drop", 0.0)

    threshold = float(cfg.get("KS_MIN", CONTROL_DEFAULTS["KS_MIN"])) / 100.0

    passed = (
        ks_gain >= threshold
        and (
            opp_tactics <= -0.1
            or mobility_drop >= cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
        )
    )

    metrics = {
        "king_safety_gain": ks_gain,
        "opp_tactics_change_eval": opp_tactics,
        "opp_mobility_drop": mobility_drop,
    }

    score = ks_gain * 100 + abs(min(opp_tactics, 0.0)) * 40

    why = reason(
        ctx,
        f"king shelter improved {ks_gain:+.2f}, opp tactics {opp_tactics:+.2f}"
    ) if passed else "king_safety_shell conditions not met"

    if passed:
        if score >= 30:
            severity = "strong"
        elif score >= 15:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_space_clamp(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect space clamping pattern.

    Pattern: Gaining space and controlling more squares while restricting
    opponent mobility and maintaining low tension.

    Required ctx fields:
    - allow_positional: bool - must be True
    - own_space_gain: float OR space_gain: float - space increase
    - space_control_gain: float - controlled squares increase
    - opp_mobility_drop: float - opponent mobility reduction
    - tension_delta: float - tension change
    - volatility_drop_cp: float - volatility reduction
    - vol_drop_cp: float - alias for volatility_drop_cp
    - phase: str - game phase

    Config parameters:
    - SPACE_MIN: float - minimum space gain (in tenths)
    - OP_MOBILITY_DROP: float - mobility threshold
    - VOLATILITY_DROP_CP: float - volatility threshold
    """
    from ...legacy.control_helpers import phase_bonus, reason
    from ...legacy.config import (
        CONTROL_DEFAULTS,
        CONTROL_OPP_MOBILITY_DROP,
        CONTROL_VOLATILITY_DROP_CP,
    )

    if not ctx.get("allow_positional", False):
        return SemanticResult(
            passed=False,
            metrics={},
            why="not allowed for non-positional context",
            score=0.0,
        )

    own_space_gain = ctx.get("own_space_gain", ctx.get("space_gain", 0.0))
    space_control_gain = ctx.get("space_control_gain", 0.0)
    mobility_drop = ctx.get("opp_mobility_drop", 0.0)
    tension_delta = ctx.get("tension_delta", 0.0)
    vol_drop_alias = ctx.get("vol_drop_cp", ctx.get("volatility_drop_cp", 0.0))

    # Calculate thresholds
    phase_adjust = phase_bonus(ctx, cfg)
    space_threshold = float(cfg.get("SPACE_MIN", CONTROL_DEFAULTS["SPACE_MIN"])) / 10.0
    mob_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
    vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + phase_adjust["VOL_BONUS"]

    # Check conditions
    space_ok = (own_space_gain >= space_threshold) or (space_control_gain >= 1)
    tension_ok = tension_delta in (0, -1, -2)
    mob_ok = mobility_drop >= mob_threshold
    env_ok = vol_drop_alias >= vol_threshold
    passed = space_ok and mob_ok and tension_ok and env_ok

    metrics = {
        "space_gain": own_space_gain,
        "space_control_gain": space_control_gain,
        "opp_mobility_drop": mobility_drop,
        "tension_delta": tension_delta,
        "volatility_drop_cp": vol_drop_alias,
        "space_ok": space_ok,
        "tension_ok": tension_ok,
        "mobility_ok": mob_ok,
        "env_ok": env_ok,
    }

    score = own_space_gain * 80 + max(space_control_gain, 0.0) * 10 + mobility_drop * 10

    why = reason(
        ctx,
        f"space clamp {own_space_gain:+.2f} (controlΔ {space_control_gain:+.0f}) "
        f"opp mobilityΔ {mobility_drop:+.1f}",
    ) if passed else "space_clamp conditions not met"

    if passed:
        if score >= 150:
            severity = "strong"
        elif score >= 75:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_regroup_consolidate(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect regrouping/consolidation pattern.

    Pattern: Regrouping pieces to improve king safety and structural integrity
    without losing mobility.

    Required ctx fields:
    - allow_positional: bool - must be True
    - king_safety_gain: float - king safety improvement
    - structure_gain: float - pawn structure improvement
    - self_mobility_change: float - own mobility change
    - volatility_drop_cp: float - volatility reduction

    Config parameters:
    - VOLATILITY_DROP_CP: float - volatility threshold
    """
    from ...legacy.control_helpers import reason
    from ...legacy.config import CONTROL_VOLATILITY_DROP_CP

    ks_gain = ctx.get("king_safety_gain", 0.0)
    structure_gain = ctx.get("structure_gain", 0.0)
    self_mobility_change = ctx.get("self_mobility_change", 0.0)
    vol_drop = ctx.get("volatility_drop_cp", 0.0)

    passed = (
        ctx.get("allow_positional", False)
        and vol_drop >= cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) * 0.6
        and self_mobility_change <= 0.05
        and (ks_gain >= 0.05 or structure_gain >= 0.1)
    )

    metrics = {
        "king_safety_gain": ks_gain,
        "structure_gain": structure_gain,
        "self_mobility_change": self_mobility_change,
        "volatility_drop_cp": vol_drop,
    }

    score = vol_drop + ks_gain * 80 + structure_gain * 60

    why = reason(
        ctx,
        f"regrouped to consolidate safety ({ks_gain:+.2f}) and structure ({structure_gain:+.2f})"
    ) if passed else "regroup_consolidate conditions not met"

    if passed:
        if score >= 150:
            severity = "strong"
        elif score >= 75:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )


def is_slowdown(ctx: Dict[str, Any], cfg: Dict[str, Any]) -> SemanticResult:
    """
    Detect slowdown pattern.

    Pattern: Choosing a positional move over a dynamic alternative to
    dampen dynamics and reduce opponent's mobility/tension.

    Required ctx fields:
    - allow_positional: bool - must be True
    - has_dynamic_in_band: bool - dynamic alternative exists
    - played_kind: str - "dynamic" or "positional"
    - eval_drop_cp: int - evaluation drop
    - volatility_drop_cp: float - volatility reduction
    - tension_delta: float - tension change
    - opp_mobility_drop: float - opponent mobility reduction
    - phase_bucket: str - phase for tension threshold
    - phase: str - game phase for bonus

    Config parameters:
    - VOLATILITY_DROP_CP: float - volatility threshold
    - OP_MOBILITY_DROP: float - mobility threshold
    - EVAL_DROP_CP: int - maximum eval drop allowed
    """
    from ...legacy.control_helpers import phase_bonus, _control_tension_threshold, reason
    from ...legacy.config import (
        CONTROL_VOLATILITY_DROP_CP,
        CONTROL_OPP_MOBILITY_DROP,
        CONTROL_EVAL_DROP,
    )

    if not ctx.get("allow_positional", False):
        return SemanticResult(
            passed=False,
            metrics={},
            why="not allowed for non-positional context",
            score=0.0,
        )

    has_dynamic = ctx.get("has_dynamic_in_band", False)
    played_kind = ctx.get("played_kind")
    eval_drop_cp = ctx.get("eval_drop_cp", 0)

    # Calculate thresholds
    vol_bonus = phase_bonus(ctx, cfg)["VOL_BONUS"]
    mob_bonus = phase_bonus(ctx, cfg)["OP_MOB_DROP"]
    vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + vol_bonus
    mob_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP) + mob_bonus
    phase_bucket = ctx.get("phase_bucket", "middlegame")
    tension_threshold = _control_tension_threshold(phase_bucket)

    tension_delta = ctx.get("tension_delta", 0.0)
    opp_mobility_drop = ctx.get("opp_mobility_drop", 0.0)
    volatility_drop = ctx.get("volatility_drop_cp", 0.0)

    passed = (
        has_dynamic
        and played_kind == "positional"
        and eval_drop_cp <= cfg.get("EVAL_DROP_CP", CONTROL_EVAL_DROP)
        and volatility_drop >= vol_threshold
        and tension_delta <= tension_threshold
        and opp_mobility_drop >= mob_threshold
    )

    metrics = {
        "eval_drop_cp": eval_drop_cp,
        "volatility_drop_cp": volatility_drop,
        "tension_delta": tension_delta,
        "opp_mobility_drop": opp_mobility_drop,
    }

    score = volatility_drop + opp_mobility_drop * 5

    why = reason(
        ctx,
        f"slowdown dampened dynamics (vol {volatility_drop:.1f}cp, opp mobility {opp_mobility_drop:+.0f})"
    ) if passed else "slowdown conditions not met"

    if passed:
        if score >= 150:
            severity = "strong"
        elif score >= 100:
            severity = "moderate"
        else:
            severity = "weak"
    else:
        severity = None

    return SemanticResult(
        passed=passed,
        metrics=metrics,
        why=why,
        score=score,
        severity=severity,
    )
