import math
from copy import deepcopy
import chess
import chess.engine
from typing import Any, Dict, List, Optional, Set, Tuple

from engine_utils.prophylaxis import detect_prophylaxis_plan_drop, PlanDropResult
from rule_tagger2.legacy.prophylaxis import (
    ProphylaxisConfig,
    classify_prophylaxis_quality,
    clamp_preventive_score,
    estimate_opponent_threat,
    is_full_material,
    is_prophylaxis_candidate,
    prophylaxis_pattern_reason,
)

from .config import (
    CONTROL,
    CONTROL_DEFAULTS,
    CENTER_FILES,
    CENTER_TOLERANCE,
    CONTROL_BLUNDER_THREAT_THRESH,
    CONTROL_COOLDOWN_PLIES,
    CONTROL_EVAL_DROP,
    CONTROL_KING_SAFETY_THRESH,
    CONTROL_OPP_MOBILITY_DROP,
    CONTROL_PHASE_WEIGHTS,
    CONTROL_SIMPLIFY_MIN_EXCHANGE,
    CONTROL_TACTICAL_WEIGHT_CEILING,
    CONTROL_TENSION_DELTA,
    CONTROL_TENSION_DELTA_ENDGAME,
    CONTROL_VOLATILITY_DROP_CP,
    DELTA_EVAL_POSITIONAL,
    INITIATIVE_BOOST,
    KING_SAFETY_GAIN,
    KING_SAFETY_TOLERANCE,
    MOBILITY_RISK_TRADEOFF,
    MOBILITY_TOLERANCE,
    RISK_SMALL_LOSS,
    STRUCTURE_DOMINANCE_LIMIT,
    STRUCTURE_THRESHOLD,
    STYLE_COMPONENT_KEYS,
    TACTICAL_DELTA_TACTICS,
    TACTICAL_DOMINANCE_THRESHOLD,
    TACTICAL_GAP_FIRST_CHOICE,
    TACTICAL_MISS_LOSS,
    TACTICAL_SLOPE_THRESHOLD,
    TACTICAL_THRESHOLD,
    TENSION_EVAL_MAX,
    TENSION_EVAL_MIN,
    TENSION_SYMMETRY_TOL,
    NEUTRAL_TENSION_BAND,
)
from rule_tagger2.core.engine_io import (
    analyse_candidates,
    contact_profile,
    defended_square_count,
    eval_specific_move,
    evaluation_and_metrics,
    estimate_phase_ratio,
    material_balance,
    metrics_delta,
    simulate_followup_metrics,
)
from .analysis import (
    _soft_gate_weight,
    backward_delta,
    blockage_penalty,
    compute_behavior_scores,
    compute_premature_compensation,
    compute_tactical_weight,
    compute_tau,
    detect_risk_avoidance,
    file_pressure,
    infer_intent_hint,
    is_attacking_pawn_push,
    open_file_score,
)
from .models import Candidate, StyleTracker, TagResult
from .move_utils import classify_move, parse_move, is_dynamic, is_quiet
from ..detectors.control import detect_control_patterns

NEUTRAL_TENSION_MOBILITY_MIN = 0.05
NEUTRAL_TENSION_MOBILITY_CAP = 0.35
INITIATIVE_EVAL_MIN = 0.12
INITIATIVE_MOBILITY_HIGH = 0.3
from .sacrifice import classify_sacrifice
from .core_v8 import tag_position as legacy_tag_position_v8
from .thresholds import (
    AGGRESSION_THRESHOLD,
    FILE_PRESSURE_THRESHOLD,
    LOSING_TAU_MIN,
    LOSING_TAU_SCALE,
    MOBILITY_SELF_LIMIT,
    PASSIVE_PLAN_EVAL_DROP,
    PASSIVE_PLAN_MOBILITY_OPP,
    PASSIVE_PLAN_MOBILITY_SELF,
    PLAN_DROP_DEPTH,
    PLAN_DROP_ENABLED,
    PLAN_DROP_EVAL_CAP,
    PLAN_DROP_MULTIPV,
    PLAN_DROP_OPP_MOBILITY_GATE,
    PLAN_DROP_PLAN_LOSS_MIN,
    PLAN_DROP_PSI_MIN,
    PLAN_DROP_RUNTIME_CAP_MS,
    PLAN_DROP_SAMPLE_RATE,
    PLAN_DROP_VARIANCE_CAP,
    PREMATURE_ATTACK_HARD,
    PREMATURE_ATTACK_THRESHOLD,
    RISK_AVOIDANCE_MOBILITY_DROP,
    SOFT_BLOCK_SCALE,
    SOFT_GATE_MIDPOINT,
    SOFT_GATE_WIDTH,
    STATIC_BLOCKAGE_MARGIN,
    STATIC_BLOCKAGE_THRESHOLD_BASE,
    STRUCTURE_WEAKEN_LIMIT,
    TENSION_CONTACT_DELAY,
    TENSION_CONTACT_DIRECT,
    TENSION_CONTACT_JUMP,
    TENSION_MOBILITY_DELAY,
    TENSION_MOBILITY_NEAR,
    TENSION_MOBILITY_THRESHOLD,
    TENSION_SUSTAIN_MIN,
    TENSION_SUSTAIN_VAR_CAP,
    TENSION_TREND_OPP,
    TENSION_TREND_SELF,
    THRESHOLDS,
    VOLATILITY_DROP_TOL,
    WINNING_TAU_MAX,
    WINNING_TAU_SCALE,
)
from rule_tagger2.core.context import EvalBundles, Followups, PositionContext, ThresholdsView
from rule_tagger2.core.detectors.maneuver import detect_maneuver, detect_maneuver_prepare
from rule_tagger2.core.gating import TAG_PRIORITY, TENSION_TRIGGER_PRIORITY, apply_tactical_gating
from rule_tagger2.core.tagging import assemble_tags
from rule_tagger2.core.thresholds import load_thresholds
from rule_tagger2.legacy.opening_pawns import (
    OPENING_PAWN_FULLMOVE_CUTOFF,
    detect_opening_pawn_tags,
)

THRESHOLDS_VIEW = ThresholdsView(load_thresholds().values)
TAG_ALIAS_MAP = {
    "misplaced_maneuver": "failed_maneuver",
}


def _attach_persistent_opening_tags(
    raw_tags: List[str], gated_tags: List[str], persistent_opening_tags: List[str]
) -> Tuple[List[str], List[str]]:
    """Ensure opening pawn tags survive gating."""
    if not persistent_opening_tags:
        return raw_tags, gated_tags

    for tag in persistent_opening_tags:
        if tag not in raw_tags:
            raw_tags.append(tag)

    for tag in persistent_opening_tags:
        if tag not in gated_tags:
            gated_tags.append(tag)

    return raw_tags, gated_tags


PROPHYLAXIS_CONFIG = ProphylaxisConfig(
    preventive_trigger=THRESHOLDS["prophylaxis_preventive_trigger"],
    safety_cap=THRESHOLDS["prophylaxis_safety_bonus_cap"],
    score_threshold=THRESHOLDS["prophylaxis_preventive_trigger"],
    structure_min=THRESHOLDS.get("prophylaxis_structure_min", ProphylaxisConfig.structure_min),
    self_mobility_tol=THRESHOLDS.get("prophylaxis_self_mobility_tol", ProphylaxisConfig.self_mobility_tol),
    threat_depth=int(THRESHOLDS.get("prophylaxis_threat_depth", ProphylaxisConfig.threat_depth)),
    threat_drop=THRESHOLDS.get("prophylaxis_threat_drop", ProphylaxisConfig.threat_drop),
)
PROPHYLAXIS_STRUCTURE_MIN = PROPHYLAXIS_CONFIG.structure_min
PROPHYLAXIS_SELF_MOBILITY_TOL = PROPHYLAXIS_CONFIG.self_mobility_tol
PROPHYLAXIS_SCORE_THRESHOLD = PROPHYLAXIS_CONFIG.score_threshold
PROPHYLAXIS_THREAT_DROP = PROPHYLAXIS_CONFIG.threat_drop
PROPHYLAXIS_PREVENTIVE_TRIGGER = PROPHYLAXIS_CONFIG.preventive_trigger
PROPHYLAXIS_SAFETY_CAP = PROPHYLAXIS_CONFIG.safety_cap
PROPHYLAXIS_THREAT_DEPTH = PROPHYLAXIS_CONFIG.threat_depth

COD_SUBTYPES: Tuple[str, ...] = (
    "simplify",
    "plan_kill",
    "freeze_bind",
    "blockade_passed",
    "file_seal",
    "king_safety_shell",
    "space_clamp",
    "regroup_consolidate",
    "slowdown",
)

LEGACY_COD_BRIDGE = {
    "simplify": "simplify",
    "slowdown": "slowdown",
    "freeze": "freeze_bind",
    "king_safety": "king_safety_shell",
    "prophylaxis": "plan_kill",
}

CONTROL_TAGS: Tuple[str, ...] = (
    "control_simplify",
    "control_plan_kill",
    "control_freeze_bind",
    "control_blockade_passed",
    "control_file_seal",
    "control_king_safety_shell",
    "control_space_clamp",
    "control_regroup_consolidate",
    "control_slowdown",
)


# Imported from extracted modules
from .control_helpers import (
    STRICT_MODE_MOB_DELTA,
    STRICT_MODE_VOL_DELTA,
    _active_piece_count,
    _active_piece_count_for,
    _collect_control_metrics,
    _contact_stats,
    _control_flags,
    _control_tension_threshold,
    _count_legal_moves_for,
    _count_passed_push_targets,
    _current_ply_index,
    _format_control_summary,
    _forward_square,
    _is_passed_pawn,
    _maybe_attach_control_context_snapshot,
    _normalize_phase_label,
    _phase_bucket,
    _resolve_control_config,
    _strict_mode_config,
    phase_bonus,
    reason,
)
from .cod_detectors import COD_DETECTORS
from .cod_selection import COD_SUBTYPES, select_cod_subtype


def tag_position(
    engine_path: str,
    fen: str,
    played_move_uci: str,
    depth: int = 14,
    multipv: int = 6,
    cp_threshold: int = 100,
    small_drop_cp: int = 30
) -> TagResult:
    control_cfg, control_enabled, control_strict = _resolve_control_config()
    if not control_enabled:
        return legacy_tag_position_v8(
            engine_path,
            fen,
            played_move_uci,
            depth=depth,
            multipv=multipv,
            cp_threshold=cp_threshold,
            small_drop_cp=small_drop_cp,
        )
    board = chess.Board(fen)
    actor = board.turn
    metrics_before, opp_metrics_before, evaluation_before = evaluation_and_metrics(board, actor)
    coverage_before = defended_square_count(board, actor)
    played_move = parse_move(board, played_move_uci)
    is_capture_played = board.is_capture(played_move)

    candidates, eval_before_cp, analysis_meta = analyse_candidates(
        engine_path, board, depth=depth, multipv=multipv
    )
    if not candidates:
        raise RuntimeError("Engine returned no candidates.")

    # TODO[v2-prepare]: Store engine candidates for preparation detector
    analysis_meta.setdefault('engine_candidates', [])
    for idx, candidate in enumerate(candidates):
        analysis_meta['engine_candidates'].append({
            'move_uci': candidate.move.uci(),
            'score_cp': candidate.score_cp,
            'kind': candidate.kind,
            'multipv': idx,
            'depth': getattr(candidate, 'depth', depth)
        })

    phase_ratio = analysis_meta.get("phase_ratio", estimate_phase_ratio(board))

    best = candidates[0]
    in_band = [c for c in candidates if (best.score_cp - c.score_cp) <= cp_threshold]

    played_entry: Optional[Candidate] = next((c for c in in_band if c.move == played_move), None)
    if played_entry is None:
        played_score_cp = eval_specific_move(engine_path, board, played_move, depth=depth)
        played_kind = classify_move(board, played_move)
    else:
        played_score_cp = played_entry.score_cp
        played_kind = played_entry.kind

    eval_before = round(eval_before_cp / 100.0, 2)
    eval_played = round(played_score_cp / 100.0, 2)
    eval_best = round(best.score_cp / 100.0, 2)
    delta_eval = round((best.score_cp - played_score_cp) / 100.0, 2)
    eval_played_cp = played_score_cp
    eval_best_cp = best.score_cp

    has_dynamic_in_band = any(c.kind == "dynamic" for c in in_band)

    played_board = board.copy(stack=False)
    played_board.push(played_move)
    metrics_played, opp_metrics_played, evaluation_played = evaluation_and_metrics(played_board, actor)
    coverage_after = defended_square_count(played_board, actor)

    best_board = board.copy(stack=False)
    best_board.push(best.move)
    metrics_best, opp_metrics_best, evaluation_best = evaluation_and_metrics(best_board, actor)
    coverage_best = defended_square_count(best_board, actor)

    contact_ratio_before, _, _, _ = contact_profile(board)
    contact_ratio_played, _, _, _ = contact_profile(played_board)
    contact_ratio_best, _, _, _ = contact_profile(best_board)
    contact_delta_played = contact_ratio_played - contact_ratio_before
    contact_delta_best = contact_ratio_best - contact_ratio_before
    analysis_meta.setdefault("tension_support", {})
    analysis_meta["tension_support"].update(
        {
            "contact_ratio_before": round(contact_ratio_before, 3),
            "contact_ratio_played": round(contact_ratio_played, 3),
            "contact_ratio_best": round(contact_ratio_best, 3),
            "contact_delta_played": round(contact_delta_played, 3),
            "contact_delta_best": round(contact_delta_best, 3),
            "thresholds": {
                "tension_mobility_min": TENSION_MOBILITY_THRESHOLD,
                "tension_mobility_near": TENSION_MOBILITY_NEAR,
                "contact_ratio_min": TENSION_CONTACT_JUMP,
                "contact_ratio_delay": TENSION_CONTACT_DELAY,
                "tension_mobility_delay": TENSION_MOBILITY_DELAY,
                "tension_trend_self": TENSION_TREND_SELF,
                "tension_trend_opp": TENSION_TREND_OPP,
            },
        }
    )

    component_deltas = metrics_delta(metrics_played, metrics_best)
    change_played_vs_before = metrics_delta(metrics_before, metrics_played)
    opp_component_deltas = metrics_delta(opp_metrics_played, opp_metrics_best)
    opp_change_played_vs_before = metrics_delta(opp_metrics_before, opp_metrics_played)
    self_vs_best = {key: round(-component_deltas[key], 3) for key in STYLE_COMPONENT_KEYS}
    opp_vs_best = {key: round(-opp_component_deltas[key], 3) for key in STYLE_COMPONENT_KEYS}
    coverage_delta = coverage_after - coverage_before

    followup_steps = 3

    def _compute_delta_sequence(base: Dict[str, float], sequence: List[Dict[str, float]]) -> List[Dict[str, float]]:
        deltas: List[Dict[str, float]] = []
        for metrics in sequence:
            deltas.append({key: round(metrics[key] - base[key], 3) for key in STYLE_COMPONENT_KEYS})
        return deltas

    with chess.engine.SimpleEngine.popen_uci(engine_path) as follow_engine:
        base_self_before, base_opp_before, seq_self_before, seq_opp_before = simulate_followup_metrics(
            follow_engine, board, actor, steps=followup_steps
        )
        base_self_played, base_opp_played, seq_self_played, seq_opp_played = simulate_followup_metrics(
            follow_engine, played_board, actor, steps=followup_steps
        )
        base_self_best, base_opp_best, seq_self_best, seq_opp_best = simulate_followup_metrics(
            follow_engine, best_board, actor, steps=followup_steps
        )

    follow_self_deltas = _compute_delta_sequence(base_self_before, seq_self_played)
    follow_opp_deltas = _compute_delta_sequence(base_opp_before, seq_opp_played)
    follow_self_deltas_best = _compute_delta_sequence(base_self_before, seq_self_best)
    follow_opp_deltas_best = _compute_delta_sequence(base_opp_before, seq_opp_best)

    def _ema_trend(deltas: List[Dict[str, float]]) -> float:
        if not deltas:
            return 0.0
        weights = [0.6, 0.3, 0.1][: len(deltas)]
        total = sum(weights)
        trend = sum(w * deltas[idx]["mobility"] for idx, w in enumerate(weights))
        return trend / total if total else 0.0

    def _window_stats(deltas: List[Dict[str, float]], steps: int = 2) -> Tuple[float, float]:
        if len(deltas) < steps:
            return 0.0, 0.0
        window = deltas[:steps]
        values = [abs(entry["mobility"]) for entry in window]
        mean = sum(values) / len(values)
        variance = sum((val - mean) ** 2 for val in values) / len(values)
        return mean, variance

    self_trend = _ema_trend(follow_self_deltas)
    opp_trend = _ema_trend(follow_opp_deltas)
    self_trend_best = _ema_trend(follow_self_deltas_best)
    opp_trend_best = _ema_trend(follow_opp_deltas_best)
    follow_window_mean, follow_window_var = _window_stats(follow_self_deltas)

    delta_best_vs_before_cp = eval_best_cp - eval_before_cp
    delta_tactics_best_vs_before = (
        evaluation_best["components"]["tactics"] - evaluation_before["components"]["tactics"]
    )
    delta_structure_best_vs_before = (
        evaluation_best["components"]["structure"] - evaluation_before["components"]["structure"]
    )

    best_is_forcing = board.is_capture(best.move) or board.gives_check(best.move)
    played_is_forcing = board.is_capture(played_move) or board.gives_check(played_move)
    analysis_meta["best_is_forcing"] = best_is_forcing
    analysis_meta["played_is_forcing"] = played_is_forcing

    tactical_weight = compute_tactical_weight(
        delta_best_vs_before_cp,
        delta_tactics_best_vs_before,
        delta_structure_best_vs_before,
        analysis_meta["depth_jump_cp"],
        analysis_meta.get("deepening_gain_cp", 0),
        analysis_meta["score_gap_cp"],
        analysis_meta["contact_ratio"],
        analysis_meta.get("phase_ratio", estimate_phase_ratio(board)),
        best_is_forcing,
        played_is_forcing,
        analysis_meta.get("mate_threat", False),
    )

    if tactical_weight >= 0.65:
        mode = "tactical"
    elif tactical_weight <= 0.35:
        mode = "positional"
    else:
        mode = "blended"

    allow_positional = tactical_weight <= 0.7
    allow_tactical = tactical_weight >= 0.3
    allow_structural = True

    notes: Dict[str, str] = {}

    delta_self_mobility = change_played_vs_before["mobility"]
    delta_opp_mobility = opp_change_played_vs_before["mobility"]
    control_over_dynamics = False
    control_over_dynamics_subtype: Optional[str] = None
    cod_flags = {name: False for name in COD_SUBTYPES}
    control_flags = {name: False for name in CONTROL_TAGS}
    deferred_initiative = False
    risk_avoidance = False
    prophylactic_move = False
    prophylaxis_pattern_override = False
    prophylaxis_pattern_support = False
    prophylaxis_force_failure = False
    prophylaxis_score = 0.0
    preventive_score = 0.0
    adjusted_preventive = 0.0
    self_safety_bonus = 0.0
    analysis_meta.setdefault("prophylaxis", {})
    analysis_meta["prophylaxis"].setdefault("telemetry", {})
    structural_integrity = False
    structural_compromise_dynamic = False
    structural_compromise_static = False
    structural_compromise_forced = False
    tactical_sensitivity = False
    initiative_exploitation = False
    initiative_attempt = False
    tension_creation = False
    neutral_tension_creation = False
    premature_attack = False
    constructive_maneuver = False
    constructive_maneuver_prepare = False
    neutral_maneuver = False
    misplaced_maneuver = False
    maneuver_opening = False
    opening_central_pawn_move = False
    opening_rook_pawn_move = False
    tactical_sacrifice = False
    positional_sacrifice = False
    inaccurate_tactical_sacrifice = False
    speculative_sacrifice = False
    desperate_sacrifice = False
    tactical_combination_sacrifice = False
    tactical_initiative_sacrifice = False
    positional_structure_sacrifice = False
    positional_space_sacrifice = False
    file_pressure_c_flag = False
    first_choice = False
    missed_tactic = False
    conversion_precision = False
    panic_move = False
    tactical_recovery = False
    maneuver_precision_score = 0.0
    maneuver_timing_score = 0.0
    prepare_quality_score = 0.0
    prepare_consensus_score = 0.0
    behavior_scores: Dict[str, float] = {}
    plan_drop_result: Optional[PlanDropResult] = None

    delta_eval_cp = best.score_cp - played_score_cp
    delta_eval_played_vs_before = played_score_cp - eval_before_cp
    delta_eval_float = delta_eval_played_vs_before / 100.0
    drop_cp = delta_eval_played_vs_before
    structure_gain = change_played_vs_before["structure"]
    tactics_gain = change_played_vs_before["tactics"]
    center_gain = change_played_vs_before["center_control"]

    tau = compute_tau(eval_before)
    effective_delta = delta_eval_float / max(tau, 1e-6)
    material_before = material_balance(board, actor)
    material_after = material_balance(played_board, actor)
    material_delta_self = round(material_after - material_before, 3)

    analysis_meta.setdefault("material", {})
    analysis_meta["material"].update(
        {
            "before": material_before,
            "after": material_after,
            "delta": material_delta_self,
        }
    )
    analysis_meta.setdefault("context", {})
    analysis_meta["context"].update(
        {
            "tau": round(tau, 3),
            "eval_before": eval_before,
            "eval_delta": delta_eval_float,
            "effective_delta": round(effective_delta, 3),
        }
    )
    control_metrics = _collect_control_metrics(
        board,
        played_board,
        actor,
        played_move,
        phase_ratio,
        delta_eval_cp,
        drop_cp,
        change_played_vs_before,
        opp_change_played_vs_before,
        analysis_meta,
        material_delta_self,
    )
    control_meta = analysis_meta.setdefault("control_dynamics", {})
    control_meta.update(control_metrics)
    control_meta["enabled"] = control_enabled
    control_meta["strict_mode"] = control_strict
    config_snapshot = {
        "volatility_drop_cp": control_cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP),
        "opp_mobility_drop": control_cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP),
        "cooldown_plies": control_cfg.get("COOLDOWN_PLIES", CONTROL_COOLDOWN_PLIES),
    }
    if control_strict:
        strict_deltas = dict(
            control_cfg.get(
                "_strict_deltas",
                {
                    "VOLATILITY_DROP_CP": STRICT_MODE_VOL_DELTA,
                    "OP_MOBILITY_DROP": STRICT_MODE_MOB_DELTA,
                },
            )
        )
        config_snapshot["strict_deltas"] = strict_deltas
    control_meta["config_snapshot"] = config_snapshot
    notes["control_flags"] = f"control_v2 enabled={control_enabled} strict={control_strict}"
    snapshot_parts = [
        f"vol_drop_cp={config_snapshot['volatility_drop_cp']}",
        f"opp_mob_drop={config_snapshot['opp_mobility_drop']}",
        f"cooldown={config_snapshot['cooldown_plies']}",
    ]
    strict_deltas = config_snapshot.get("strict_deltas")
    if strict_deltas:
        vol_delta = strict_deltas.get("VOLATILITY_DROP_CP")
        mob_delta = strict_deltas.get("OP_MOBILITY_DROP")
        snapshot_parts.append(f"strict_delta(vol={vol_delta},mob={mob_delta})")
    notes["control_config_snapshot"] = ", ".join(snapshot_parts)
    ctx = control_meta.setdefault("context", {})
    ctx.clear()
    ctx["enabled"] = control_enabled
    ctx["strict_mode"] = control_strict
    ctx["config_snapshot"] = dict(config_snapshot)
    opp_passed_push_before, blockers_before = _count_passed_push_targets(board, not actor)
    opp_passed_push_after, blockers_after = _count_passed_push_targets(played_board, not actor)
    blockade_established = False
    blockade_file: Optional[str] = None
    moved_piece = board.piece_at(played_move.from_square)
    piece_type = moved_piece.piece_type if moved_piece else None
    moved_to = played_move.to_square
    blocker_entry = blockers_after.get(moved_to)
    blockade_front_see_non_positive = False
    if blocker_entry is not None:
        occupant = played_board.piece_at(moved_to)
        if occupant and occupant.color == actor:
            blockade_established = True
            blockade_file = chess.FILE_NAMES[chess.square_file(blocker_entry)]
            see_probe = getattr(played_board, "see", None)
            block_move = chess.Move(blocker_entry, moved_to)
            try:
                if played_board.is_legal(block_move):
                    if callable(see_probe):
                        try:
                            blockade_front_see_non_positive = float(see_probe(block_move)) <= 0.0
                        except Exception:
                            blockade_front_see_non_positive = False
                    else:
                        blockade_front_see_non_positive = False
                else:
                    # Opponent cannot immediately capture the blocker
                    blockade_front_see_non_positive = True
            except Exception:
                blockade_front_see_non_positive = False
    opp_passed_exists = bool(opp_passed_push_before or blockers_before)
    opp_passed_push_drop = float(opp_passed_push_before - opp_passed_push_after)
    if opp_passed_push_drop < 0:
        opp_passed_push_drop = 0.0
    opp_contact_before = control_metrics.get("opp_contact_before", {})
    opp_contact_after = control_metrics.get("opp_contact_after", {})
    opp_line_pressure_drop = float(
        max(
            0.0,
            (opp_contact_before.get("contact", 0.0) or 0.0)
            - (opp_contact_after.get("contact", 0.0) or 0.0),
        )
    )
    self_contact_before = control_metrics.get("self_contact_before", {})
    self_contact_after = control_metrics.get("self_contact_after", {})
    break_candidates_delta = float(
        (self_contact_after.get("captures", 0.0) or 0.0)
        - (self_contact_before.get("captures", 0.0) or 0.0)
    )
    plan_meta = analysis_meta.setdefault("prophylaxis_plan", {})
    raw_phase_bucket = control_metrics.get("phase_bucket", _phase_bucket(phase_ratio))
    normalized_phase = _normalize_phase_label(raw_phase_bucket)
    ctx.update(
        {
            "eval_drop_cp": delta_eval_cp,
            "vol_drop_cp": control_metrics.get("volatility_drop_cp", 0.0),
            "tension_delta": control_metrics.get("tension_delta", 0.0),
            "op_mob_drop": control_metrics.get("opp_mobility_drop", 0.0),
            "phase": normalized_phase,
            "phase_bucket": raw_phase_bucket,
            "phase_ratio": phase_ratio,
            "allow_positional": allow_positional,
            "has_dynamic_in_band": has_dynamic_in_band,
            "played_kind": played_kind,
            "exchange_count": int(max(0, control_metrics.get("active_piece_drop", 0))),
            "exchanged_rooks": int(
                1 if control_metrics.get("captured_piece_type") == chess.ROOK else 0
            ),
            "plan_drop_passed": bool(plan_meta.get("passed")),
            "prophylaxis_plan_drop": False,
            "prophylaxis_line_seal": False,
            "break_candidates_delta": break_candidates_delta,
            "opp_line_pressure_drop": opp_line_pressure_drop,
            "op_pins_increase": 0,
            "opp_passed_exists": opp_passed_exists,
            "blockade_established": blockade_established,
            "blockade_file": blockade_file,
            "opp_passed_push_drop": opp_passed_push_drop,
            "blockade_front_square_see_non_positive": blockade_front_see_non_positive,
            "king_safety_gain": control_metrics.get("king_safety_gain", 0.0),
            "opp_attackers_drop": 0,
            "own_space_gain": center_gain,
            "loose_pieces_drop": 0,
            "hanging_threats_drop": 0,
            "preventive_score": 0.0,
            "threat_delta": 0.0,
            "king_safety_tolerance": KING_SAFETY_TOLERANCE,
        }
    )
    ctx["strict_mode"] = control_strict
    # Aliases and derived metrics for downstream detectors and diagnostics.
    ctx["volatility_drop_cp"] = ctx["vol_drop_cp"]
    ctx["opp_mobility_drop"] = ctx["op_mob_drop"]
    ctx["self_mobility_change"] = control_metrics.get("self_mobility_change", 0.0)
    ctx["opp_mobility_change_eval"] = control_metrics.get("opp_mobility_change_eval", 0.0)
    ctx["opp_tactics_change_eval"] = control_metrics.get("opp_tactics_change_eval", 0.0)
    ctx["structure_gain"] = control_metrics.get("structure_gain", 0.0)
    ctx["center_gain"] = control_metrics.get("center_gain", center_gain)
    ctx["space_gain"] = ctx["own_space_gain"]
    ctx["space_control_gain"] = coverage_delta
    ctx["material_delta_self"] = control_metrics.get("material_delta_self", 0.0)
    ctx["material_delta_self_cp"] = control_metrics.get("material_delta_self_cp", 0)
    ctx["captured_value_cp"] = control_metrics.get("captured_value_cp", 0)
    ctx["captured_piece_type"] = control_metrics.get("captured_piece_type")
    ctx["is_capture"] = control_metrics.get("is_capture", False)
    ctx["active_piece_drop"] = control_metrics.get("active_piece_drop", 0)
    ctx["own_active_drop"] = control_metrics.get("own_active_drop", 0)
    ctx["opp_active_drop"] = control_metrics.get("opp_active_drop", 0)
    ctx["op_active_drop"] = ctx["opp_active_drop"]
    ctx["total_active_drop"] = control_metrics.get("total_active_drop", ctx["active_piece_drop"])
    ctx["captures_this_ply"] = control_metrics.get("captures_this_ply", 0)
    ctx["square_defended_by_opp"] = control_metrics.get("square_defended_by_opp", 0)
    ctx["square_defended_by_self"] = control_metrics.get("square_defended_by_self", 0)
    ctx["contact_ratio_before"] = control_metrics.get("self_contact_before", {}).get("ratio", 0.0)
    ctx["contact_ratio_after"] = control_metrics.get("self_contact_after", {}).get("ratio", 0.0)
    ctx["contact_ratio_drop"] = ctx["contact_ratio_after"] - ctx["contact_ratio_before"]
    ctx["opp_contact_ratio_before"] = control_metrics.get("opp_contact_before", {}).get("ratio", 0.0)
    ctx["opp_contact_ratio_after"] = control_metrics.get("opp_contact_after", {}).get("ratio", 0.0)
    ctx["volatility_before_cp"] = control_metrics.get("volatility_before_cp", 0.0)
    ctx["volatility_after_cp"] = control_metrics.get("volatility_after_cp", 0.0)
    ctx["played_move"] = played_move.uci()
    ctx["played_piece_type"] = piece_type

    intent_label, intent_signals = infer_intent_hint(
        delta_self_mobility,
        delta_opp_mobility,
        change_played_vs_before["king_safety"],
        center_gain,
        contact_delta_played,
        delta_eval_float,
    )
    analysis_meta.setdefault("intent_hint", {})
    analysis_meta["intent_hint"].update(
        {"label": intent_label, "signals": intent_signals}
    )
    ctx["tactical_weight"] = tactical_weight
    has_immediate_tactical_followup = bool(
        analysis_meta.get("played_is_forcing")
        or analysis_meta.get("mate_threat")
        or (tactical_weight >= 0.6 and ctx.get("has_dynamic_in_band", False))
    )
    ctx["has_immediate_tactical_followup"] = has_immediate_tactical_followup
    restriction_candidate = (
        intent_label == "restriction"
        and delta_opp_mobility <= -PLAN_DROP_OPP_MOBILITY_GATE
        and change_played_vs_before["king_safety"] >= 0.0
        and mode != "tactical"
    )
    passive_candidate = (
        intent_label == "passive"
        and (
            delta_eval_float <= PASSIVE_PLAN_EVAL_DROP
            or (
                delta_self_mobility <= PASSIVE_PLAN_MOBILITY_SELF
                and delta_opp_mobility >= PASSIVE_PLAN_MOBILITY_OPP
            )
        )
        and mode != "tactical"
    )
    plan_candidate = restriction_candidate or passive_candidate
    intent_meta = analysis_meta["intent_hint"]
    intent_meta["restriction_candidate"] = restriction_candidate
    intent_meta["passive_candidate"] = passive_candidate

    mover_piece = board.piece_at(played_move.from_square)
    is_pawn_move = bool(mover_piece and mover_piece.piece_type == chess.PAWN)
    is_center_pawn_push = bool(
        is_pawn_move
        and chess.square_file(played_move.to_square) in CENTER_FILES
        and chess.square_file(played_move.from_square) in CENTER_FILES
    )
    opening_central_pawn_move, opening_rook_pawn_move, opening_tags = detect_opening_pawn_tags(
        board, played_move
    )
    if opening_tags:
        analysis_meta.setdefault("opening_tags", []).extend(opening_tags)

    plan_meta.update(
        {
            "candidate": plan_candidate,
            "restriction_candidate": restriction_candidate,
            "passive_candidate": passive_candidate,
            "psi_threshold": PLAN_DROP_PSI_MIN,
            "plan_loss_threshold": PLAN_DROP_PLAN_LOSS_MIN,
            "eval_drop_cap": PLAN_DROP_EVAL_CAP,
        }
    )

    side_key = "white" if actor == chess.WHITE else "black"
    pawn_struct_before = evaluation_before["pawn_structure"][side_key]
    pawn_struct_played = evaluation_played["pawn_structure"][side_key]
    pawn_struct_best = evaluation_best["pawn_structure"][side_key]

    delta_isolated = len(pawn_struct_played["isolated_pawns"]) - len(pawn_struct_before["isolated_pawns"])
    delta_doubled = len(pawn_struct_played["doubled_pawns"]) - len(pawn_struct_before["doubled_pawns"])
    delta_backward_raw = len(pawn_struct_played["backward_pawns"]) - len(pawn_struct_before["backward_pawns"])
    delta_backward, backward_added = backward_delta(
        pawn_struct_before["backward_pawns"],
        pawn_struct_played["backward_pawns"],
        played_move,
        actor,
        played_board,
        contact_delta_played,
    )
    delta_islands = pawn_struct_played["pawn_islands"] - pawn_struct_before["pawn_islands"]
    delta_chains = len(pawn_struct_played["pawn_chains"]) - len(pawn_struct_before["pawn_chains"])

    delta_isolated_best = len(pawn_struct_best["isolated_pawns"]) - len(pawn_struct_before["isolated_pawns"])
    delta_doubled_best = len(pawn_struct_best["doubled_pawns"]) - len(pawn_struct_before["doubled_pawns"])
    delta_backward_best, backward_added_best = backward_delta(
        pawn_struct_before["backward_pawns"],
        pawn_struct_best["backward_pawns"],
        best.move,
        actor,
        best_board,
        contact_delta_best,
    )
    delta_islands_best = pawn_struct_best["pawn_islands"] - pawn_struct_before["pawn_islands"]
    delta_chains_best = len(pawn_struct_best["pawn_chains"]) - len(pawn_struct_before["pawn_chains"])

    king_before = evaluation_before["king_safety"][side_key]
    king_played = evaluation_played["king_safety"][side_key]
    king_best = evaluation_best["king_safety"][side_key]
    delta_shield = king_played["pawn_shield"] - king_before["pawn_shield"]
    delta_shield_best = king_best["pawn_shield"] - king_before["pawn_shield"]

    structural_counts_before = {
        "isolated": len(pawn_struct_before["isolated_pawns"]),
        "doubled": len(pawn_struct_before["doubled_pawns"]),
        "backward": len(pawn_struct_before["backward_pawns"]),
        "islands": pawn_struct_before["pawn_islands"],
        "chains": len(pawn_struct_before["pawn_chains"]),
        "shield": king_before["pawn_shield"],
    }

    structure_score_before = pawn_struct_before["score"]
    structure_score_played = pawn_struct_played["score"]
    structure_score_best = pawn_struct_best["score"]
    structure_score_gain = structure_score_played - structure_score_before
    structure_score_gain_best = structure_score_best - structure_score_before

    structural_event_details = {
        "isolated": delta_isolated,
        "doubled": delta_doubled,
        "backward": delta_backward,
        "islands": delta_islands,
        "chains": delta_chains,
        "shield": delta_shield,
        "structure_score": round(structure_score_gain, 3),
    }
    structural_event_details_best = {
        "isolated": delta_isolated_best,
        "doubled": delta_doubled_best,
        "backward": delta_backward_best,
        "islands": delta_islands_best,
        "chains": delta_chains_best,
        "shield": delta_shield_best,
        "structure_score": round(structure_score_gain_best, 3),
    }
    structural_event = any(
        [
            delta_isolated > 0,
            delta_doubled > 0,
            delta_backward > 0,
            delta_islands > 0,
            delta_chains < 0,
            delta_shield < 0,
        ]
    )

    structural_event_best = any(
        [
            delta_isolated_best > 0,
            delta_doubled_best > 0,
            delta_backward_best > 0,
            delta_islands_best > 0,
            delta_chains_best < 0,
            delta_shield_best < 0,
        ]
    )

    structural_shift_signal = any(
        [
            delta_isolated != 0,
            delta_doubled != 0,
            delta_backward != 0,
            delta_islands != 0,
            delta_chains != 0,
            delta_shield != 0,
        ]
    ) or abs(structure_score_gain) >= 0.1

    structure_drop_threshold = -0.12 * (1 + 0.3 * phase_ratio)
    if structure_score_gain <= structure_drop_threshold:
        structural_event = True
        structural_event_details.setdefault("structure_drop", round(structure_score_gain, 3))
    if structure_score_gain_best <= structure_drop_threshold:
        structural_event_best = True
        structural_event_details_best.setdefault("structure_drop", round(structure_score_gain_best, 3))

    blockage_threshold = STATIC_BLOCKAGE_THRESHOLD_BASE * (0.6 + 0.4 * phase_ratio)
    blockage_trigger_margin = blockage_threshold + STATIC_BLOCKAGE_MARGIN
    blockage_penalty_played, blockage_detail_played = blockage_penalty(
        evaluation_before,
        evaluation_played,
        board,
        played_move,
        actor,
        phase_ratio,
    )
    blockage_penalty_best, blockage_detail_best = blockage_penalty(
        evaluation_before,
        evaluation_best,
        board,
        best.move,
        actor,
        phase_ratio,
    )
    if blockage_penalty_played >= blockage_trigger_margin:
        structural_event = True
        structural_event_details.setdefault("blockage", blockage_penalty_played)
    elif blockage_penalty_played >= blockage_threshold:
        structural_event_details.setdefault(
            "blockage_soft", round(blockage_penalty_played * SOFT_BLOCK_SCALE, 3)
        )
    if blockage_penalty_best >= blockage_trigger_margin:
        structural_event_best = True
        structural_event_details_best.setdefault("blockage", blockage_penalty_best)
    elif blockage_penalty_best >= blockage_threshold:
        structural_event_details_best.setdefault(
            "blockage_soft", round(blockage_penalty_best * SOFT_BLOCK_SCALE, 3)
        )

    prophylactic_reasons: List[str] = []
    preventive_score = 0.0
    self_safety_bonus = 0.0
    threat_before = threat_after = None
    threat_delta = 0.0
    pattern_reason: Optional[str] = None
    threat_reduced = False
    opp_restrained = False
    self_solidified = False

    control_meta = analysis_meta["control_dynamics"]
    control_meta.setdefault("gates", {})

    if allow_positional:
        # Deferred initiative requires very specific conditions - make it more restrictive
        # It should indicate moves that consolidate while deferring active play
        if (
            is_quiet(board, played_move)
            and contact_delta_played < TENSION_CONTACT_DELAY
            and not board.gives_check(played_move)
            and delta_eval_float > -0.5
            and delta_self_mobility < 0.1  # Stricter: was 0.2, now 0.1
            and not is_center_pawn_push
            and abs(center_gain) <= 0.05  # Stricter: was 0.1, now 0.05
        ):
            deferred_initiative = True
            notes["deferred_initiative"] = (
                "quiet move maintained stability while reducing own activity to tighten the position"
            )

        if (
            not deferred_initiative
            and allow_positional
            and delta_self_mobility <= 0.08  # Stricter: was 0.12, now 0.08
            and drop_cp > -50  # Stricter: was -70, now -50
            and delta_eval_float >= -0.3  # Stricter: was -0.5, now -0.3
            and not is_capture_played
            and not board.gives_check(played_move)
            and not is_center_pawn_push
        ):
            deferred_initiative = True
            notes["deferred_initiative"] = (
                "consolidating move with minimal aggression kept the initiative alive"
            )

        king_safety_gain = change_played_vs_before["king_safety"]
        opp_tactics_change = opp_change_played_vs_before["tactics"]

        if not risk_avoidance:
            drop_cp_condition = drop_cp > -50  # -0.5 pawns
            if (
                delta_self_mobility <= -0.05
                and (king_safety_gain >= 0.05 or opp_tactics_change <= -0.05)
                and drop_cp_condition
            ):
                risk_avoidance = True
                notes["risk_avoidance"] = (
                    f"mobility {delta_self_mobility:+.2f} traded for safety {king_safety_gain:+.2f} "
                    f"and tactics {opp_tactics_change:+.2f}; eval change {drop_cp/100:+.2f}"
                )

        if structure_gain >= 0.25 and tactics_gain <= 0.1:
            structural_integrity = True
            notes["structural_integrity"] = (
                f"structure improved by {structure_gain:+.2f} while tactics change {tactics_gain:+.2f}"
            )

        if is_prophylaxis_candidate(board, played_move):
            self_ks_gain = max(self_vs_best["king_safety"], change_played_vs_before["king_safety"])
            self_structure_gain = max(self_vs_best["structure"], structure_gain)
            self_mobility_change = change_played_vs_before["mobility"]

            opp_mobility_change = opp_vs_best["mobility"]
            opp_tactics_change = opp_vs_best["tactics"]

            threat_before = estimate_opponent_threat(engine_path, board, actor, config=PROPHYLAXIS_CONFIG)
            threat_after = estimate_opponent_threat(engine_path, played_board, actor, config=PROPHYLAXIS_CONFIG)
            threat_delta = round(threat_before - threat_after, 3)
            threat_reduced = threat_delta >= PROPHYLAXIS_CONFIG.threat_drop

            opp_restrained = (
                opp_trend < 0.0
                or opp_mobility_change <= -0.05
                or opp_tactics_change <= -0.1
            )
            self_solidified = (self_structure_gain >= 0.0) or (center_gain >= 0.05)

            pattern_override_active = False
            pattern_reason = prophylaxis_pattern_reason(
                board,
                played_move,
                opp_trend,
                opp_change_played_vs_before["tactics"],
            )
            pattern_support = pattern_reason is not None
            if pattern_support:
                prophylactic_reasons.append(pattern_reason)
                prophylaxis_pattern_support = True

            if (
                self_structure_gain >= PROPHYLAXIS_CONFIG.structure_min
                and abs(self_mobility_change) <= PROPHYLAXIS_CONFIG.self_mobility_tol
            ):
                prophylactic_reasons.append(
                    f"self consolidation: structure {self_structure_gain:+.2f}, king safety {self_ks_gain:+.2f}, mobility {self_mobility_change:+.2f}"
                )

            preventive_score = round(
                max(0.0, threat_delta) * 0.5
                + max(0.0, -opp_mobility_change) * 0.3
                + max(0.0, -opp_tactics_change) * 0.2
                + max(0.0, -opp_trend) * 0.15,
                3,
            )
            ctx["preventive_score"] = preventive_score
            ctx["threat_delta"] = threat_delta
            safety_raw = (
                max(0.0, self_structure_gain) * 0.4
                + max(0.0, self_ks_gain) * 0.4
                + max(0.0, -self_mobility_change) * 0.2
            )
            self_safety_bonus = round(
                clamp_preventive_score(safety_raw, config=PROPHYLAXIS_CONFIG),
                3,
            )

            adjusted_preventive = preventive_score
            if pattern_support and preventive_score >= PROPHYLAXIS_CONFIG.preventive_trigger * 0.75:
                adjusted_preventive = max(preventive_score, PROPHYLAXIS_CONFIG.preventive_trigger)
                pattern_override_active = True
                prophylactic_reasons.append(
                    f"pattern support override (score {preventive_score:+.2f} → {adjusted_preventive:+.2f})"
                )

            defensive_consolidation = self_solidified or self_safety_bonus > 0
            clear_threat_response = threat_reduced or opp_restrained
            prophylactic_signal = clear_threat_response and defensive_consolidation
            if pattern_override_active:
                prophylactic_signal = True
            if adjusted_preventive >= PROPHYLAXIS_CONFIG.preventive_trigger and prophylactic_signal:
                prophylactic_move = True
                prophylactic_reasons.append(
                    f"preventive score {adjusted_preventive:+.2f} ≥ trigger {PROPHYLAXIS_CONFIG.preventive_trigger:+.2f}"
                )

            if self_safety_bonus > 0:
                prophylactic_reasons.append(
                    f"self safety bonus {self_safety_bonus:+.2f}"
                )

            prophylaxis_score = adjusted_preventive
            telemetry_entry = analysis_meta.setdefault("prophylaxis", {}).setdefault("telemetry", {})
            telemetry_entry["pattern_override"] = pattern_override_active
            if pattern_override_active:
                prophylaxis_pattern_override = True
            prophylaxis_force_failure = (
                pattern_support
                and threat_before is not None
                and threat_before >= PROPHYLAXIS_CONFIG.threat_drop
                and threat_delta <= PROPHYLAXIS_CONFIG.threat_drop * 0.25
                and drop_cp <= -50
            )
            analysis_meta["prophylaxis"]["force_failure"] = prophylaxis_force_failure

            if (threat_reduced or opp_restrained) and self_solidified:
                detail_parts = []
                if threat_reduced:
                    detail_parts.append(f"threat ↓{threat_delta:+.2f}")
                if opp_trend <= 0.0:
                    detail_parts.append(f"opp mobility trend {opp_trend:+.2f}")
                if opp_tactics_change <= -0.1:
                    detail_parts.append(f"opp tactics {opp_tactics_change:+.2f}")
                if center_gain >= 0.0:
                    detail_parts.append(f"center {center_gain:+.2f}")
                detail_text = ", ".join(detail_parts) if detail_parts else "preventive control"
                prophylactic_reasons.append(f"preventive context: {detail_text}")

            analysis_meta.setdefault("prophylaxis", {})
            analysis_meta["prophylaxis"].update(
                {
                    "threat_before": threat_before,
                    "threat_after": threat_after,
                    "threat_delta": threat_delta,
                    "pattern": pattern_reason,
                    "components": {
                        "preventive_score": preventive_score,
                        "self_safety_bonus": self_safety_bonus,
                    },
                    "telemetry": {
                        "self_structure_gain": round(self_structure_gain, 3),
                        "self_king_safety_gain": round(self_ks_gain, 3),
                        "self_mobility_change": round(self_mobility_change, 3),
                        "opp_mobility_change": round(opp_mobility_change, 3),
                        "opp_tactics_change": round(opp_tactics_change, 3),
                        "preventive_score": preventive_score,
                        "self_safety_bonus": self_safety_bonus,
                        "opp_trend": round(opp_trend, 3),
                        "self_trend": round(self_trend, 3),
                        "pattern_override": prophylaxis_pattern_override,
                    },
                }
            )
            if prophylactic_reasons:
                notes["prophylactic_move"] = " | ".join(prophylactic_reasons)
                analysis_meta["prophylaxis"]["reasons"] = prophylactic_reasons

            if prophylactic_move:
                if self_mobility_change > 0:
                    notes["prophylaxis_type"] = "active prophylaxis (reposition and restrict)"
                elif preventive_score >= PROPHYLAXIS_CONFIG.score_threshold:
                    notes["prophylaxis_type"] = "preventive prophylaxis (plan suppression)"

        plan_drop_result = None
        if PLAN_DROP_ENABLED and plan_candidate:
            plan_drop_result = detect_prophylaxis_plan_drop(
                engine_path,
                board,
                played_board,
                depth=PLAN_DROP_DEPTH,
                multipv=PLAN_DROP_MULTIPV,
                sample_rate=PLAN_DROP_SAMPLE_RATE,
                variance_cap=PLAN_DROP_VARIANCE_CAP,
                runtime_cap_ms=PLAN_DROP_RUNTIME_CAP_MS,
            )
        if plan_drop_result:
            plan_pass = (
                plan_drop_result.sampled
                and plan_drop_result.stable
                and plan_drop_result.psi >= PLAN_DROP_PSI_MIN
                and plan_drop_result.plan_loss >= PLAN_DROP_PLAN_LOSS_MIN
                and delta_eval_float >= PLAN_DROP_EVAL_CAP
                and "sample_skipped" not in plan_drop_result.reasons
            )
            plan_meta.update(
                {
                    "psi": plan_drop_result.psi,
                    "pei": plan_drop_result.pei,
                    "plan_loss": plan_drop_result.plan_loss,
                    "depth": plan_drop_result.depth,
                    "multipv": plan_drop_result.multipv,
                    "stable": plan_drop_result.stable,
                    "runtime_ms": plan_drop_result.runtime_ms,
                    "sampled": plan_drop_result.sampled,
                    "reasons": plan_drop_result.reasons,
                    "variance_before": plan_drop_result.variance_before,
                    "variance_after": plan_drop_result.variance_after,
                    "passed": plan_pass,
                }
            )
            if plan_pass and not prophylactic_move:
                prophylactic_move = True
            if plan_pass:
                plan_note = (
                    f"plan disruption: psi {plan_drop_result.psi:.2f}, loss {plan_drop_result.plan_loss:.2f}"
                )
                if "prophylactic_move" in notes:
                    notes["prophylactic_move"] = f"{notes['prophylactic_move']} | {plan_note}"
                else:
                    notes["prophylactic_move"] = plan_note
                existing = notes.get("prophylaxis_type")
                if existing:
                    notes["prophylaxis_type"] = f"{existing} | {plan_note}"
                else:
                    notes["prophylaxis_type"] = plan_note
        else:
            plan_meta.setdefault("sampled", False)
            plan_meta.setdefault("passed", None)

        ctx["prophylaxis_plan_drop"] = bool(plan_meta.get("passed"))
        prophylaxis_line_seal = False
        if prophylactic_move and not ctx["prophylaxis_plan_drop"]:
            if moved_piece and moved_piece.piece_type in {chess.ROOK, chess.QUEEN}:
                pressure_drop = ctx.get("opp_line_pressure_drop", 0.0)
                ratio_drop = (
                    (opp_contact_before.get("ratio", 0.0) or 0.0)
                    - (opp_contact_after.get("ratio", 0.0) or 0.0)
                )
                if pressure_drop >= 1.0 or ratio_drop >= 0.05:
                    prophylaxis_line_seal = True
        ctx["prophylaxis_line_seal"] = prophylaxis_line_seal
        if ctx["prophylaxis_plan_drop"]:
            ctx["plan_drop_passed"] = True
        elif ctx["prophylaxis_line_seal"]:
            ctx["opp_line_pressure_drop"] = max(
                ctx.get("opp_line_pressure_drop", 0.0),
                float(control_cfg.get("LINE_MIN", 0)),
            )
            ctx["break_candidates_delta"] = min(ctx.get("break_candidates_delta", 0.0), -1.0)
    else:
        analysis_meta.setdefault("prophylaxis", {})
        plan_meta.setdefault("sampled", False)
        plan_meta.setdefault("passed", None)

    analysis_meta["prophylaxis"].setdefault(
        "components", {"preventive_score": 0.0, "self_safety_bonus": 0.0}
    )
    analysis_meta["prophylaxis"].setdefault("telemetry", {})
    analysis_meta["prophylaxis"]["telemetry"].setdefault("pattern_override", False)

    recent_info = control_meta.get("recent") or {}
    previous_kind = recent_info.get("kind") if isinstance(recent_info, dict) else None
    current_ply_index = analysis_meta.get("ply_index")
    if current_ply_index is None:
        current_ply_index = _current_ply_index(board, actor)
    control_meta["current_ply"] = current_ply_index
    ctx["current_ply"] = current_ply_index
    ctx["cooldown_plies"] = control_cfg.get("COOLDOWN_PLIES", CONTROL_COOLDOWN_PLIES)

    selected_entry, suppressed_subtypes, cooldown_remaining, gate_log, detected_entries = select_cod_subtype(
        ctx,
        control_cfg,
        recent_info,
    )
    control_meta["gates"] = gate_log
    control_meta["candidates"] = detected_entries
    ctx = control_meta.setdefault("context", {})
    candidate_names: Set[str] = set()
    candidate_names.update(entry["name"] for entry in detected_entries)
    candidate_names.update(name for name in suppressed_subtypes if name in COD_SUBTYPES)
    if selected_entry:
        candidate_names.add(selected_entry["name"])
    candidates_map = {name: (name in candidate_names) for name in COD_SUBTYPES}
    ctx["candidates"] = candidates_map
    ctx["suppressed"] = list(suppressed_subtypes)
    ctx["cooldown_remaining"] = cooldown_remaining
    cooldown_hit = bool(
        previous_kind
        and previous_kind in suppressed_subtypes
        and previous_kind != (selected_entry["name"] if selected_entry else None)
        and cooldown_remaining > 0
    )
    ctx["cooldown_hit"] = cooldown_hit
    suppressed_by = suppressed_subtypes[0] if (not selected_entry and suppressed_subtypes) else None
    ctx["suppressed_by"] = suppressed_by

    if selected_entry:
        summary_metrics = dict(selected_entry.get("metrics", {}))
        summary_metrics.setdefault("volatility_drop_cp", ctx.get("volatility_drop_cp"))
        summary_metrics.setdefault("tension_delta", ctx.get("tension_delta"))
        summary_metrics.setdefault("opp_mobility_drop", ctx.get("opp_mobility_drop"))
        summary_metrics.setdefault("king_safety_gain", ctx.get("king_safety_gain"))
        summary_metrics.setdefault("opp_tactics_change_eval", ctx.get("opp_tactics_change_eval"))
        control_over_dynamics = True
        control_over_dynamics_subtype = selected_entry["name"]
        control_meta["subtype"] = control_over_dynamics_subtype
        control_meta["selected"] = {
            "kind": control_over_dynamics_subtype,
            "metrics": summary_metrics,
            "why": selected_entry.get("why"),
        }
        ctx["selected_kind"] = control_over_dynamics_subtype
        ctx["selected_metrics"] = summary_metrics
        suppressed_text = ",".join(suppressed_subtypes) if suppressed_subtypes else "-"
        gates_text = (
            f"evalΔ:{ctx.get('eval_drop_cp', 0)}, "
            f"volΔ:{ctx.get('vol_drop_cp', 0.0):.1f}, "
            f"tensionΔ:{ctx.get('tension_delta', 0.0):+.1f}, "
            f"opMobΔ:{ctx.get('op_mob_drop', 0.0):+.1f}"
        )
        base_note = (
            f"CoD.{control_over_dynamics_subtype}: {selected_entry['why']}; "
            f"gates=[{gates_text}] suppressed={suppressed_text or '-'} "
            f"cooldown={cooldown_remaining}"
        )
        if CONTROL.get("DEBUG_CONTEXT"):
            active_candidates = [name for name, active in candidates_map.items() if active]
            cand_text = ",".join(active_candidates)
            debug_suffix = (
                f" cand=[{cand_text}] suppressed_by={suppressed_by or '-'}"
            )
            notes["control_over_dynamics"] = base_note + debug_suffix
        else:
            notes["control_over_dynamics"] = base_note
        control_meta["recent"] = {
            "kind": control_over_dynamics_subtype,
            "ply": current_ply_index,
        }
        for key in cod_flags:
            cod_flags[key] = False
        if control_over_dynamics_subtype in cod_flags:
            cod_flags[control_over_dynamics_subtype] = True
        mapped_cod = LEGACY_COD_BRIDGE.get(control_over_dynamics_subtype)
        if mapped_cod and mapped_cod in cod_flags:
            cod_flags[mapped_cod] = True
    else:
        ctx["selected_kind"] = None
        ctx["selected_metrics"] = {}
        control_meta["selected"] = None
        control_meta["subtype"] = None
        if CONTROL.get("DEBUG_CONTEXT"):
            active_candidates = [name for name, active in candidates_map.items() if active]
            cand_text = ",".join(active_candidates)
            debug_note = (
                f"CoD.none cand=[{cand_text}] suppressed_by={suppressed_by or '-'} "
                f"cooldown={cooldown_remaining}"
            )
            notes["control_over_dynamics"] = debug_note
        control_meta["recent"] = {"kind": None, "ply": current_ply_index}

    control_over_dynamics = any(cod_flags.values())
    ctx["control_over_dynamics"] = control_over_dynamics
    ctx["control_subtype"] = control_over_dynamics_subtype
    ctx["cod_flags"] = dict(cod_flags)

    # Detect pure control semantics (no gating/cooldown); can coexist with cod_*
    control_semantic_results = detect_control_patterns(ctx, control_cfg)
    for tag_name in CONTROL_TAGS:
        if tag_name in control_semantic_results:
            control_flags[tag_name] = bool(control_semantic_results[tag_name].get("detected"))
    analysis_meta["control_semantics"] = {
        "enabled": bool(control_cfg.get("ENABLE_CONTROL_TAGS", True)),
        "results": control_semantic_results,
    }

    prophylaxis_quality = None
    prophylaxis_signal_score = max(adjusted_preventive or 0.0, preventive_score)
    signal_threshold = PROPHYLAXIS_CONFIG.preventive_trigger * 0.85
    # Check if pattern support exists (even if score is low)
    has_pattern_support = bool(analysis_meta.get("prophylaxis", {}).get("pattern"))
    has_prophylaxis_signal = (
        prophylactic_move
        or prophylaxis_pattern_override
        or prophylaxis_signal_score >= signal_threshold
        or has_pattern_support
    )
    if has_prophylaxis_signal:
        telemetry = analysis_meta["prophylaxis"].setdefault("telemetry", {})
        pattern_override = bool(telemetry.get("pattern_override"))
        # Check if any pattern was detected (for low-score prophylaxis classification)
        has_pattern = bool(analysis_meta.get("prophylaxis", {}).get("pattern"))
        soft_weight = _soft_gate_weight(effective_delta)
        effective_preventive = adjusted_preventive if adjusted_preventive else preventive_score
        if pattern_override and effective_preventive < PROPHYLAXIS_CONFIG.preventive_trigger:
            effective_preventive = PROPHYLAXIS_CONFIG.preventive_trigger
        prophylaxis_quality, quality_score = classify_prophylaxis_quality(
            has_prophylaxis_signal,
            effective_preventive,
            effective_delta,
            tactical_weight,
            soft_weight,
            eval_before_cp=eval_before_cp,
            drop_cp=drop_cp,
            threat_delta=ctx.get("threat_delta", 0.0),
            volatility_drop=ctx.get("volatility_drop_cp", 0.0),
            pattern_override=(pattern_override or has_pattern),
            config=PROPHYLAXIS_CONFIG,
        )
        if plan_candidate and plan_meta.get("passed") is False:
            prophylaxis_quality = "prophylactic_meaningless"
            quality_score = 0.0
        elif plan_candidate and plan_meta.get("passed") and prophylaxis_quality == "prophylactic_latent":
            prophylaxis_quality = "prophylactic_direct"
            quality_score = max(quality_score, 0.8)
        if prophylaxis_force_failure:
            prophylaxis_quality = "prophylactic_meaningless"
            quality_score = 0.0
        if prophylaxis_quality:
            analysis_meta["prophylaxis"]["quality"] = prophylaxis_quality
            analysis_meta["prophylaxis"]["quality_score"] = quality_score
            # Set prophylactic_move flag to ensure failed_prophylactic detector runs
            if not prophylactic_move:
                prophylactic_move = True
        else:
            analysis_meta["prophylaxis"].pop("quality", None)
            analysis_meta["prophylaxis"].pop("quality_score", None)
        analysis_meta["prophylaxis"]["components"].update(
            {
                "preventive_score": preventive_score,
                "effective_preventive": effective_preventive,
                "self_safety_bonus": self_safety_bonus,
                "soft_weight": round(soft_weight, 3),
                "effective_delta": round(effective_delta, 3),
                "pattern_override": pattern_override,
                "threat_delta": ctx.get("threat_delta", 0.0),
                "volatility_drop_cp": ctx.get("volatility_drop_cp", 0.0),
            }
        )
    prophylaxis_quality = analysis_meta["prophylaxis"].get("quality")
    quality_score = analysis_meta["prophylaxis"].get("quality_score")
    if prophylaxis_quality and quality_score is not None:
        notes.setdefault(
            "prophylaxis_quality",
            f"{prophylaxis_quality} (score {quality_score:+.2f})",
        )
    if prophylaxis_force_failure and "prophylaxis_quality" not in notes:
        analysis_meta["prophylaxis"]["quality"] = "prophylactic_meaningless"
        analysis_meta["prophylaxis"]["quality_score"] = 0.0
        notes.setdefault("prophylaxis_quality", "prophylactic_meaningless (score +0.00)")
        prophylaxis_quality = "prophylactic_meaningless"
        # Set prophylactic_move flag to True so that failed_prophylactic detector can run
        if not prophylactic_move:
            prophylactic_move = True

    # ----- Directional pressure (e.g., c-file) -----
    file_pressure_info: Dict[str, Any] = {}
    file_pressure_score = 0.0
    if board.piece_at(played_move.from_square):
        file_pressure_score, file_pressure_info = file_pressure(
            board,
            played_board,
            actor,
            chess.FILE_NAMES.index("c"),
            chess.C7 if actor == chess.WHITE else chess.C2,
        )
        analysis_meta.setdefault("directional_pressure", {})
        file_pressure_info["score"] = round(file_pressure_score, 3)
        file_pressure_info["triggered"] = file_pressure_score >= FILE_PRESSURE_THRESHOLD
        analysis_meta["directional_pressure"]["c"] = file_pressure_info

        c_file_idx = chess.FILE_NAMES.index("c")
        moved_on_c_file = (
            chess.square_file(played_move.from_square) == c_file_idx
            or chess.square_file(played_move.to_square) == c_file_idx
        )
        if file_pressure_score >= FILE_PRESSURE_THRESHOLD and moved_on_c_file:
            file_pressure_c_flag = True
            notes.setdefault(
                "file_pressure:c",
                f"pressure score {file_pressure_score:.2f} (AD={file_pressure_info.get('ad')}, xray={file_pressure_info.get('xray')})",
            )

    # ----- Risk avoidance detection -----
    eval_loss = abs(delta_eval_float)
    if detect_risk_avoidance(
        change_played_vs_before["king_safety"],
        eval_loss,
        opp_change_played_vs_before["tactics"],
        contact_delta_played,
    ):
        if not risk_avoidance:
            notes.setdefault(
                "risk_avoidance",
                f"risk avoidance: king safety {change_played_vs_before['king_safety']:+.2f}, eval loss {eval_loss:+.2f}"
            )
        risk_avoidance = True

    behavior_scores = compute_behavior_scores(
        change_played_vs_before["mobility"],
        change_played_vs_before["center_control"],
        effective_delta,
        file_pressure_info.get("delta", 0.0),
        max(0.0, -change_played_vs_before["structure"]),
        change_played_vs_before["king_safety"],
        opp_change_played_vs_before["mobility"],
    )
    analysis_meta.setdefault("behavior_scores", {}).update(behavior_scores)

    eval_bundles = EvalBundles(
        metrics_before=metrics_before,
        metrics_played=metrics_played,
        metrics_best=metrics_best,
        opp_before=opp_metrics_before,
        opp_played=opp_metrics_played,
        opp_best=opp_metrics_best,
        component_deltas=component_deltas,
        opp_component_deltas=opp_component_deltas,
    )
    followups_bundle = Followups(
        base_self_before=base_self_before,
        base_opp_before=base_opp_before,
        base_self_played=base_self_played,
        base_opp_played=base_opp_played,
        base_self_best=base_self_best,
        base_opp_best=base_opp_best,
        self_played=follow_self_deltas,
        opp_played=follow_opp_deltas,
        self_best=follow_self_deltas_best,
        opp_best=follow_opp_deltas_best,
    )
    structural_flags = analysis_meta.setdefault("structural_flags", {})
    structural_flags.update(
        {
            "dynamic": structural_compromise_dynamic,
            "static": structural_compromise_static,
            "forced": structural_compromise_forced,
        }
    )
    position_ctx = PositionContext(
        board=board,
        actor=actor,
        played=played_move,
        best=best.move,
        phase_ratio=phase_ratio,
        eval_before_cp=eval_before_cp,
        eval_played_cp=eval_played_cp,
        eval_best_cp=eval_best_cp,
        metrics_before=metrics_before,
        metrics_played=metrics_played,
        metrics_best=metrics_best,
        opp_before=opp_metrics_before,
        opp_played=opp_metrics_played,
        opp_best=opp_metrics_best,
        change_played_vs_before=change_played_vs_before,
        opp_change_played_vs_before=opp_change_played_vs_before,
        tactical_weight=tactical_weight,
        delta_eval_cp=delta_eval_cp,
        delta_eval_float=delta_eval_float,
        drop_cp=drop_cp,
        effective_delta=effective_delta,
        coverage_before=coverage_before,
        coverage_after=coverage_after,
        coverage_best=coverage_best,
        contact_ratio_before=contact_ratio_before,
        contact_ratio_played=contact_ratio_played,
        contact_ratio_best=contact_ratio_best,
        followups=followups_bundle,
        trends={
            "self_played": self_trend,
            "opp_played": opp_trend,
            "self_best": self_trend_best,
            "opp_best": opp_trend_best,
        },
        windows={
            "self_window_mean": follow_window_mean,
            "self_window_var": follow_window_var,
        },
        eval_bundles=eval_bundles,
        analysis_meta=analysis_meta,
        extras={
            "file_pressure": file_pressure_info,
            "structural_flags": structural_flags,
            "knight_bishop_exchange": analysis_meta.get("knight_bishop_exchange"),
        },
    )
    maneuver_flags, maneuver_notes, maneuver_extras = detect_maneuver(position_ctx, THRESHOLDS_VIEW)
    for key, value in maneuver_notes.items():
        notes.setdefault(key, value)
    if maneuver_extras.get("behavior_scores"):
        analysis_meta.setdefault("behavior_scores", {}).update(maneuver_extras["behavior_scores"])
    if "maneuver_details" in maneuver_extras:
        analysis_meta.setdefault("maneuver_details", {}).update(maneuver_extras["maneuver_details"])
    maneuver_precision_score = maneuver_extras.get("maneuver_precision_score", maneuver_precision_score)
    maneuver_timing_score = maneuver_extras.get("maneuver_timing_score", maneuver_timing_score)
    constructive_maneuver = constructive_maneuver or maneuver_flags.get("constructive_maneuver", False)
    neutral_maneuver = neutral_maneuver or maneuver_flags.get("neutral_maneuver", False)
    misplaced_maneuver = misplaced_maneuver or maneuver_flags.get("misplaced_maneuver", False)
    maneuver_opening = maneuver_opening or maneuver_flags.get("maneuver_opening", False)
    # TODO[v2-prepare]: Detect constructive maneuver preparation
    # Inject multipv and score_gap_cp into position_ctx.extras for prepare detector
    position_ctx_prepare = PositionContext(
        board=position_ctx.board,
        actor=position_ctx.actor,
        played=position_ctx.played,
        best=position_ctx.best,
        phase_ratio=position_ctx.phase_ratio,
        eval_before_cp=position_ctx.eval_before_cp,
        eval_played_cp=position_ctx.eval_played_cp,
        eval_best_cp=position_ctx.eval_best_cp,
        metrics_before=position_ctx.metrics_before,
        metrics_played=position_ctx.metrics_played,
        metrics_best=position_ctx.metrics_best,
        opp_before=position_ctx.opp_before,
        opp_played=position_ctx.opp_played,
        opp_best=position_ctx.opp_best,
        change_played_vs_before=position_ctx.change_played_vs_before,
        opp_change_played_vs_before=position_ctx.opp_change_played_vs_before,
        tactical_weight=position_ctx.tactical_weight,
        delta_eval_cp=position_ctx.delta_eval_cp,
        delta_eval_float=position_ctx.delta_eval_float,
        drop_cp=position_ctx.drop_cp,
        effective_delta=position_ctx.effective_delta,
        coverage_before=position_ctx.coverage_before,
        coverage_after=position_ctx.coverage_after,
        coverage_best=position_ctx.coverage_best,
        contact_ratio_before=position_ctx.contact_ratio_before,
        contact_ratio_played=position_ctx.contact_ratio_played,
        contact_ratio_best=position_ctx.contact_ratio_best,
        followups=position_ctx.followups,
        trends=position_ctx.trends,
        windows=position_ctx.windows,
        eval_bundles=position_ctx.eval_bundles,
        analysis_meta=position_ctx.analysis_meta,
        extras={
            **position_ctx.extras,
            "multipv": multipv,
            "score_gap_cp": analysis_meta.get("score_gap_cp", 0),
            "file_pressure": file_pressure_info,
        },
    )
    prepare_flags, prepare_notes, prepare_extras = detect_maneuver_prepare(position_ctx_prepare, THRESHOLDS_VIEW)
    for key, value in prepare_notes.items():
        notes.setdefault(key, value)
    if "prepare_diagnostics" in prepare_extras:
        analysis_meta.setdefault("prepare_diagnostics", {}).update(prepare_extras["prepare_diagnostics"])
    prepare_quality_score = prepare_extras.get("prepare_quality_score", 0.0)
    prepare_consensus_score = prepare_extras.get("prepare_consensus_score", 0.0)
    constructive_maneuver_prepare = prepare_flags.get("constructive_maneuver_prepare", False)

    # ----- Premature attack -----
    if is_attacking_pawn_push(board, played_move, actor):
        structure_drop = max(0.0, -structure_gain)
        king_attack_potential = max(file_pressure_score, max(0.0, contact_delta_played))
        piece_inflow = max(0.0, behavior_scores.get("aggression", 0.0))
        self_king_risk = max(0.0, -change_played_vs_before["king_safety"])
        opp_reinforce = max(0.0, opp_change_played_vs_before["mobility"])
        tactic_against = max(0.0, opp_change_played_vs_before["tactics"])
        comp = compute_premature_compensation(
            structure_drop,
            change_played_vs_before["mobility"],
            center_gain,
            king_attack_potential,
            piece_inflow,
            self_king_risk,
            opp_reinforce,
            tactic_against,
        )
        analysis_meta.setdefault("premature_attack", {})
        analysis_meta["premature_attack"].update(
            {
                "score": round(comp, 3),
                "structure_drop": round(structure_drop, 3),
                "mobility_gain": round(change_played_vs_before["mobility"], 3),
                "center_gain": round(center_gain, 3),
            }
        )
        low_comp = comp <= PREMATURE_ATTACK_THRESHOLD
        hard_flag = (delta_eval_float <= -0.6 and structure_drop >= 0.2) or comp <= PREMATURE_ATTACK_HARD
        if low_comp or hard_flag:
            premature_attack = True
            notes.setdefault("premature_attack", f"compensation {comp:+.2f}")
            if comp <= PREMATURE_ATTACK_HARD:
                initiative_attempt = False

    # Initiative attempt gating was moved later to take tension context into account.

    if tactics_gain >= 0.3:
        tactical_sensitivity = True
        notes["tactical_sensitivity"] = (
            f"tactics component increased by {tactics_gain:+.2f}"
        )

    if drop_cp >= INITIATIVE_BOOST and change_played_vs_before["mobility"] > 0:
        initiative_exploitation = True
        notes["initiative_exploitation"] = (
            f"eval improved by {delta_eval_played_vs_before/100:.2f} with mobility gain "
            f"{change_played_vs_before['mobility']:+.2f}"
        )

    structural_reasons: List[Dict[str, Any]] = []
    if allow_structural:
        structural_detail_parts = []
        if delta_isolated > 0:
            structural_detail_parts.append(f"isolated +{delta_isolated}")
            structural_reasons.append({"type": "isolated_increase", "value": delta_isolated})
        if delta_doubled > 0:
            structural_detail_parts.append(f"doubled +{delta_doubled}")
            structural_reasons.append({"type": "doubled_increase", "value": delta_doubled})
        if delta_backward > 0:
            structural_detail_parts.append(f"backward +{delta_backward}")
            for sq_name in backward_added:
                piece = played_board.piece_at(chess.parse_square(sq_name))
                file_label = chr(ord('a') + chess.square_file(chess.parse_square(sq_name)))
                structural_reasons.append(
                    {
                        "type": "backward_increase",
                        "square": sq_name,
                        "piece": chess.piece_name(piece.piece_type) if piece else None,
                        "file": file_label,
                    }
                )
        if delta_islands > 0:
            structural_detail_parts.append(f"islands +{delta_islands}")
            structural_reasons.append({"type": "islands_increase", "value": delta_islands})
        if delta_chains < 0:
            structural_detail_parts.append(f"chains {delta_chains:+}")
            structural_reasons.append({"type": "chains_drop", "value": delta_chains})
        if delta_shield < 0:
            structural_detail_parts.append(f"shield {delta_shield:+}")
            structural_reasons.append({"type": "shield_drop", "value": delta_shield})
        if structure_score_gain <= structure_drop_threshold:
            structural_detail_parts.append(f"structure_score {structure_score_gain:+.2f}")
            structural_reasons.append({"type": "structure_score_drop", "value": round(structure_score_gain, 3)})
        if blockage_penalty_played >= blockage_trigger_margin:
            structural_detail_parts.append(f"blockage {blockage_penalty_played:+.2f}")
            structural_reasons.append({"type": "blockage_hard", "value": round(blockage_penalty_played, 3)})
        elif blockage_penalty_played >= blockage_threshold:
            structural_detail_parts.append(
                f"blockage_soft {blockage_penalty_played * SOFT_BLOCK_SCALE:+.2f}"
            )
            structural_reasons.append(
                {
                    "type": "blockage_soft",
                    "value": round(blockage_penalty_played * SOFT_BLOCK_SCALE, 3),
                }
            )
        for square_name, delta, weight in blockage_detail_played:
            piece = played_board.piece_at(chess.parse_square(square_name))
            if not piece:
                continue
            structural_reasons.append(
                {
                    "type": "blockage_piece",
                    "square": square_name,
                    "piece": chess.piece_name(piece.piece_type),
                    "file": f"{chr(ord('a') + chess.square_file(chess.parse_square(square_name)))}-file",
                    "delta": round(delta, 3),
                }
            )

        shield_only = structural_reasons and all(reason.get("type") == "shield_drop" for reason in structural_reasons)
        if (
            shield_only
            and (structural_event or structural_event_best)
            and prophylactic_move
            and mover_piece
            and mover_piece.piece_type == chess.KING
        ):
            structural_event = False
            structural_event_best = False
            structural_compromise_dynamic = False
            structural_compromise_static = False
            structural_compromise_forced = False
            structural_detail_parts = [
                entry for entry in structural_detail_parts if not entry.startswith("shield ")
            ]
            structural_reasons = []

        if structural_event and not structural_event_best:
            mobility_gain_now = change_played_vs_before["mobility"]
            opp_mobility_change_now = opp_change_played_vs_before["mobility"]
            mobility_gain_future = follow_self_deltas[-1]["mobility"] if follow_self_deltas else 0.0
            opp_mobility_change_future = follow_opp_deltas[-1]["mobility"] if follow_opp_deltas else 0.0

            mobility_trend_threshold_self = 0.1 + 0.15 * (1 - phase_ratio)
            mobility_trend_threshold_opp = 0.1 + 0.12 * phase_ratio

            self_signal = max(mobility_gain_now, mobility_gain_future, self_trend)
            opp_signal = min(opp_mobility_change_now, opp_mobility_change_future, opp_trend)
            detail_text = ", ".join(structural_detail_parts) if structural_detail_parts else "structure compromised"

            structure_drop_signal = structure_score_gain <= -0.4
            if (
                self_signal >= mobility_trend_threshold_self
                or opp_signal <= -mobility_trend_threshold_opp
                or self_trend >= mobility_trend_threshold_self * 0.75
                or opp_trend <= -mobility_trend_threshold_opp * 0.75
                or tactics_gain >= 0.15
                or center_gain >= 0.15
                or structure_drop_signal
            ):
                structural_compromise_dynamic = True
                notes["structural_compromise_dynamic"] = (
                    f"{detail_text}; dynamic potential ↑ (self mobility now {mobility_gain_now:+.2f}, future {mobility_gain_future:+.2f}; "
                    f"opponent mobility now {opp_mobility_change_now:+.2f}, future {opp_mobility_change_future:+.2f}; "
                    f"tactics {tactics_gain:+.2f}, center {center_gain:+.2f}; trend self {self_trend:+.2f}, opp {opp_trend:+.2f})"
                )
            else:
                static_condition = (
                    mobility_gain_now <= -0.03
                    and opp_mobility_change_now >= 0.03
                ) or (
                    self_trend <= 0.0 and opp_trend >= 0.03
                )
                structural_compromise_static = True
                reason = (
                    "opponent mobility increases while own mobility falls"
                    if static_condition
                    else "structure weakened without dynamic compensation"
                )
                notes["structural_compromise_static"] = (
                    f"{detail_text}; {reason} (self mobility now {mobility_gain_now:+.2f}, future {mobility_gain_future:+.2f}; "
                    f"opponent mobility now {opp_mobility_change_now:+.2f}, future {opp_mobility_change_future:+.2f}; "
                    f"tactics {tactics_gain:+.2f}, center {center_gain:+.2f}; trend self {self_trend:+.2f}, opp {opp_trend:+.2f})"
                )
        elif structural_event and structural_event_best:
            detail_text = ", ".join(structural_detail_parts) if structural_detail_parts else "structure compromised"
            notes.setdefault(
                "structural_compromise_forced",
                f"{detail_text}; best move required similar structure concession"
            )
            structural_compromise_forced = True

        blockage_pieces = [
            reason for reason in structural_reasons if reason.get("type") == "blockage_piece"
        ]
        if blockage_pieces:
            blockage_text = ", ".join(
                f"{entry.get('piece')} {entry.get('square')} on {entry.get('file')}"
                for entry in blockage_pieces
                if entry.get("piece") and entry.get("square")
            )
            if blockage_text:
                for key in (
                    "structural_compromise_dynamic",
                    "structural_compromise_static",
                    "structural_compromise_forced",
                ):
                    if key in notes:
                        notes[key] = f"{notes[key]}; blocked {blockage_text}"

    structural_timing_bonus = THRESHOLDS_VIEW.get("maneuver_structural_timing_bonus", 0.7)
    eval_protect_cp = THRESHOLDS_VIEW.get("maneuver_ev_protect_cp", 20)
    if (
        not constructive_maneuver
        and (structural_compromise_dynamic or structural_compromise_static or structural_compromise_forced)
        and maneuver_timing_score >= structural_timing_bonus
        and drop_cp >= -eval_protect_cp
    ):
        constructive_maneuver = True
        neutral_maneuver = False
        notes.setdefault(
            "maneuver_structural_promote",
            "constructive promoted via structural pressure + timing gate",
        )
    if deferred_initiative and (structural_compromise_dynamic or structural_compromise_forced):
        deferred_initiative = False
        notes.pop("deferred_initiative", None)

    sacrifice_flags, sacrifice_context = classify_sacrifice(
        board,
        played_board,
        played_move,
        eval_before,
        eval_played,
        change_played_vs_before,
        opp_metrics_before,
        opp_metrics_played,
        tactical_weight,
        behavior_scores.get("aggression", 0.0),
    )

    if sacrifice_flags["tactical_sacrifice"]:
        tactical_sacrifice = True
        notes.setdefault(
            "tactical_sacrifice",
            (
                f"material loss {sacrifice_context['material_loss']:+.2f}, eval Δ {sacrifice_context['eval_loss']:+.2f}, "
                f"king safety Δ {sacrifice_context['king_drop']:+.2f}"
            ),
        )
    if sacrifice_flags["positional_sacrifice"]:
        positional_sacrifice = True
        notes.setdefault(
            "positional_sacrifice",
            (
                f"material loss {sacrifice_context['material_loss']:+.2f}, eval Δ {sacrifice_context['eval_loss']:+.2f}, "
                f"king safety Δ {sacrifice_context['king_drop']:+.2f}"
            ),
        )
    if sacrifice_flags["inaccurate_tactical_sacrifice"]:
        inaccurate_tactical_sacrifice = True
    if sacrifice_flags["speculative_sacrifice"]:
        speculative_sacrifice = True
    if sacrifice_flags["desperate_sacrifice"]:
        desperate_sacrifice = True
    if sacrifice_flags["tactical_combination_sacrifice"]:
        tactical_combination_sacrifice = True
    if sacrifice_flags["tactical_initiative_sacrifice"]:
        tactical_initiative_sacrifice = True
    if sacrifice_flags["positional_structure_sacrifice"]:
        positional_structure_sacrifice = True
    if sacrifice_flags["positional_space_sacrifice"]:
        positional_space_sacrifice = True

        top_gap_cp = analysis_meta["score_gap_cp"]
        played_is_best = played_move == best.move

        if mode == "tactical" and top_gap_cp >= TACTICAL_GAP_FIRST_CHOICE and played_is_best:
            first_choice = True
            notes["first_choice"] = (
                f"top gap {top_gap_cp/100:.2f}; player found only winning move"
            )

        if top_gap_cp >= TACTICAL_GAP_FIRST_CHOICE and not played_is_best and delta_eval_cp >= TACTICAL_MISS_LOSS:
            missed_tactic = True
            notes["missed_tactic"] = (
                f"missed winning move; loss {delta_eval_cp/100:.2f} after gap {top_gap_cp/100:.2f}"
            )

        if (
            eval_before_cp >= TACTICAL_DOMINANCE_THRESHOLD
            and eval_played_cp >= TACTICAL_DOMINANCE_THRESHOLD
            and abs(delta_eval_played_vs_before) <= CONTROL_EVAL_DROP
        ):
            conversion_precision = True
            notes["conversion_precision"] = "maintained winning evaluation during conversion"

        if delta_eval_played_vs_before <= -250 and change_played_vs_before["mobility"] <= -0.8:
            panic_move = True
            notes["panic_move"] = (
                f"eval dropped {delta_eval_played_vs_before/100:.2f} with mobility {change_played_vs_before['mobility']:+.2f}"
            )

        if eval_before_cp <= -300 and eval_played_cp >= -100:
            tactical_recovery = True
            notes["tactical_recovery"] = "evaluation recovered from near loss"

    if allow_positional or allow_structural:
        phase_ratio_current = analysis_meta.get("phase_ratio", phase_ratio)
        followup_tail_self = follow_self_deltas[-1]["mobility"] if follow_self_deltas else 0.0

        eval_band = TENSION_EVAL_MIN <= delta_eval_float <= TENSION_EVAL_MAX
        self_mag = abs(delta_self_mobility)
        opp_mag = abs(delta_opp_mobility)
        mobility_cross = delta_self_mobility * delta_opp_mobility
        symmetry_gap = abs(self_mag - opp_mag)

        effective_threshold = TENSION_MOBILITY_THRESHOLD * (0.85 + 0.25 * phase_ratio_current)
        near_threshold = max(TENSION_MOBILITY_NEAR, effective_threshold * 0.75)
        symmetry_ok = symmetry_gap <= TENSION_SYMMETRY_TOL

        contact_jump = contact_delta_played
        contact_trigger = contact_jump >= TENSION_CONTACT_JUMP
        contact_direct = contact_jump >= TENSION_CONTACT_DIRECT
        contact_descriptor = f"contact {contact_jump:+.2f}"

        sustain_self_mean, sustain_self_var = _window_stats(follow_self_deltas)
        sustain_opp_mean, sustain_opp_var = _window_stats(follow_opp_deltas)
        sustained_window = (
            sustain_self_mean >= TENSION_SUSTAIN_MIN
            and sustain_opp_mean >= TENSION_SUSTAIN_MIN
            and sustain_self_var <= TENSION_SUSTAIN_VAR_CAP
            and sustain_opp_var <= TENSION_SUSTAIN_VAR_CAP
        )
        window_ok = sustained_window or contact_direct

        mobility_core = (
            self_mag >= effective_threshold
            and opp_mag >= effective_threshold
            and mobility_cross < 0
            and symmetry_ok
        )
        mobility_struct = (
            self_mag >= near_threshold
            and opp_mag >= near_threshold
            and mobility_cross < 0
            and (structural_shift_signal or contact_trigger)
        )

        sustained = (
            delta_eval_float > -0.6
            or self_trend >= 0
            or followup_tail_self >= 0
        )

        analysis_meta["tension_support"].update(
            {
                "effective_threshold": round(effective_threshold, 3),
                "mobility_self": round(delta_self_mobility, 3),
                "mobility_opp": round(delta_opp_mobility, 3),
                "symmetry_gap": round(symmetry_gap, 3),
                "trend_self": round(self_trend, 3),
                "trend_opp": round(opp_trend, 3),
                "sustain_self_mean": round(sustain_self_mean, 3),
                "sustain_self_var": round(sustain_self_var, 3),
                "sustain_opp_mean": round(sustain_opp_mean, 3),
                "sustain_opp_var": round(sustain_opp_var, 3),
                "sustained": sustained_window,
            }
        )

        trigger_sources: List[str] = []
        triggered = False
        contact_eval_ok = delta_eval_float <= -0.2 and mobility_cross < 0

        if eval_band and phase_ratio_current > 0.5 and window_ok and (mobility_core or mobility_struct or (contact_trigger and contact_eval_ok)):
            if delta_eval_float <= TENSION_EVAL_MIN and structural_compromise_dynamic:
                pass
            elif delta_eval_float <= -0.6 and not sustained:
                pass
            else:
                triggered = True
                if contact_trigger:
                    base_label = "contact_direct" if contact_direct else "contact_comp"
                    trigger_sources.append(base_label)
                if mobility_core:
                    trigger_sources.append("symmetry_core")
                if mobility_struct and not mobility_core:
                    trigger_sources.append("structural_support")

        if not triggered and eval_band and phase_ratio_current > 0.5 and sustained_window:
            delayed_contact = contact_jump >= TENSION_CONTACT_DELAY
            delayed_mag = (
                self_mag >= TENSION_MOBILITY_DELAY
                and opp_mag >= TENSION_MOBILITY_DELAY
                and mobility_cross < 0
            )
            delayed_trend = (
                self_trend <= TENSION_TREND_SELF
                and opp_trend >= TENSION_TREND_OPP
            )
            delayed_eval = delta_eval_float <= -0.2 or contact_trigger
            if delayed_contact and delayed_mag and delayed_trend and delayed_eval:
                triggered = True
                trigger_sources.append("delayed_trend")
                if contact_trigger:
                    base_label = "contact_direct" if contact_direct else "contact_comp"
                    trigger_sources.append(base_label)

        unique_sources: List[str] = []
        for src in trigger_sources:
            if src not in unique_sources:
                unique_sources.append(src)
        ordered_sources = sorted(unique_sources, key=lambda name: TENSION_TRIGGER_PRIORITY.get(name, 999))
        treat_as_symmetry = (
            triggered
            and not contact_trigger
            and not structural_shift_signal
            and ordered_sources
            and all(src == "symmetry_core" for src in ordered_sources)
        )

        if triggered and not treat_as_symmetry:
            tension_creation = True
            note_parts = [
                f"tension creation: eval {delta_eval_float:+.2f}",
                f"mobility self {delta_self_mobility:+.2f}",
                f"opp {delta_opp_mobility:+.2f}",
            ]
            if contact_trigger:
                note_parts.append(contact_descriptor)
            if structural_shift_signal:
                note_parts.append("structural shift detected")
            trigger_text = " + ".join(ordered_sources) if ordered_sources else "core"
            note_parts.append(f"triggered via {trigger_text}")
            if self_trend > 0:
                note_parts.append(f"follow-up self trend {self_trend:+.2f}")
            elif followup_tail_self > 0:
                note_parts.append(f"next-step mobility {followup_tail_self:+.2f}")
            notes["tension_creation"] = "; ".join(note_parts)
        elif treat_as_symmetry:
            tension_creation = False
            notes.pop("tension_creation", None)
        analysis_meta["tension_support"]["trigger_sources"] = ordered_sources

        neutral_band_active = abs(delta_eval_float) <= NEUTRAL_TENSION_BAND
        mobility_cap = NEUTRAL_TENSION_MOBILITY_CAP
        mobility_window = (
            abs(delta_self_mobility) >= NEUTRAL_TENSION_MOBILITY_MIN
            and abs(delta_opp_mobility) >= NEUTRAL_TENSION_MOBILITY_MIN
            and abs(delta_self_mobility) <= mobility_cap
            and abs(delta_opp_mobility) <= mobility_cap
        )
        neutral_support = mobility_window and delta_self_mobility >= 0.0
        analysis_meta["tension_support"]["neutral_band"] = {
            "band_cp": NEUTRAL_TENSION_BAND,
            "delta_eval": round(delta_eval_float, 3),
            "active": neutral_band_active,
        }
        if neutral_band_active and neutral_support and not (tension_creation or contact_trigger or structural_shift_signal):
            neutral_tension_creation = True
            notes.setdefault(
                "neutral_tension_creation",
                f"|Δeval| ≤ {NEUTRAL_TENSION_BAND:.2f}; sources=none",
            )

    if risk_avoidance and not file_pressure_c_flag:
        if "tension_creation" in notes:
            notes.pop("tension_creation", None)
        tension_creation = False
        analysis_meta["tension_support"]["trigger_sources"] = []

    if prophylactic_move and tension_creation and tactical_weight < 0.4:
        if "tension_creation" in notes:
            notes.pop("tension_creation", None)
        tension_creation = False
        analysis_meta["tension_support"]["trigger_sources"] = []

    initiative_intents = {"expansion", "initiative"}
    restrained_intents = {"restriction", "neutral"}
    intent_candidates = initiative_intents | restrained_intents
    tension_signal = tension_creation or neutral_tension_creation
    soft_initiative_signal = (
        not tension_signal
        and delta_self_mobility >= 0.18
        and delta_opp_mobility < 0.05
        and delta_eval_float >= INITIATIVE_EVAL_MIN
        and intent_label in {"expansion", "initiative"}
    )
    initiative_signal = tension_signal or soft_initiative_signal
    base_initiative_gate = (
        not deferred_initiative
        and not prophylactic_move
        and not is_capture_played
        and drop_cp < 70
        and initiative_signal
        and intent_label in intent_candidates
    )

    if base_initiative_gate:
        if (
            intent_label in initiative_intents
            and delta_self_mobility > 0.22
            and drop_cp < 60
        ):
            initiative_attempt = True
            notes["initiative_attempt"] = (
                f"expansion attempt: mobility {delta_self_mobility:+.2f}, "
                f"eval {delta_eval_float:+.2f}"
            )
        elif (
            intent_label in restrained_intents
            and delta_self_mobility >= 0.18
            and delta_self_mobility <= 0.75
            and delta_opp_mobility < 0.05
        ):
            initiative_attempt = True
            notes["initiative_attempt"] = (
                f"restrained initiative push ({intent_label}); mobility {delta_self_mobility:+.2f}, "
                f"eval {delta_eval_float:+.2f}"
            )

    if initiative_attempt and deferred_initiative:
        deferred_initiative = False
        notes.pop("deferred_initiative", None)

    if (
        mover_piece
        and mover_piece.piece_type == chess.PAWN
        and contact_delta_played >= TENSION_CONTACT_DELAY
        and not tension_creation
        and not initiative_attempt
    ):
        notes.setdefault(
            "break_eval_flag",
            "pawn break did not trigger initiative/tension tags; review compensation",
        )

    notes.setdefault(
        "gating_weight",
        f"tactical_weight={tactical_weight:.2f} (mode={mode})"
    )

    analysis_meta.setdefault("structural_details", {})
    analysis_meta["structural_details"].update(
        {
            "before": structural_counts_before,
            "played_delta": structural_event_details,
            "best_delta": structural_event_details_best,
            "blockage_played": {
                "penalty": blockage_penalty_played,
                "details": blockage_detail_played,
                "threshold": round(blockage_threshold, 3),
                "trigger_margin": round(blockage_trigger_margin, 3),
                "soft_scale": SOFT_BLOCK_SCALE,
            },
            "blockage_best": {
                "penalty": blockage_penalty_best,
                "details": blockage_detail_best,
                "threshold": round(blockage_threshold, 3),
                "trigger_margin": round(blockage_trigger_margin, 3),
                "soft_scale": SOFT_BLOCK_SCALE,
            },
        }
    )
    analysis_meta["structural_details"]["reasons"] = structural_reasons
    analysis_meta.setdefault("structural_reasons", structural_reasons)
    analysis_meta.setdefault("followup", {})
    analysis_meta["followup"].update(
        {
            "steps": followup_steps,
            "self_base": base_self_played,
            "opp_base": base_opp_played,
            "self_seq": follow_self_deltas,
            "opp_seq": follow_opp_deltas,
            "self_seq_best": follow_self_deltas_best,
            "opp_seq_best": follow_opp_deltas_best,
            "self_trend": round(self_trend, 3),
            "opp_trend": round(opp_trend, 3),
            "self_trend_best": round(self_trend_best, 3),
            "opp_trend_best": round(opp_trend_best, 3),
        }
    )
    analysis_meta.setdefault("tension_support", {})
    analysis_meta["tension_support"].setdefault(
        "thresholds",
        {
            "tension_mobility_min": TENSION_MOBILITY_THRESHOLD,
            "tension_mobility_near": TENSION_MOBILITY_NEAR,
            "contact_ratio_min": TENSION_CONTACT_JUMP,
            "contact_ratio_delay": TENSION_CONTACT_DELAY,
            "tension_mobility_delay": TENSION_MOBILITY_DELAY,
            "tension_trend_self": TENSION_TREND_SELF,
            "tension_trend_opp": TENSION_TREND_OPP,
            "neutral_eval_band": NEUTRAL_TENSION_BAND,
        },
    )
    analysis_meta["ruleset_version"] = "rulestack_2025-11-03"
    telemetry = analysis_meta.setdefault("telemetry", {})
    telemetry["tension"] = {
        "triggered": tension_creation,
        "sources": analysis_meta["tension_support"].get("trigger_sources"),
        "sustained": analysis_meta["tension_support"].get("sustained"),
        "sustain_means": {
            "self": analysis_meta["tension_support"].get("sustain_self_mean"),
            "opp": analysis_meta["tension_support"].get("sustain_opp_mean"),
        },
        "neutral": {
            "active": neutral_tension_creation,
            "band_cp": NEUTRAL_TENSION_BAND,
            "band_state": analysis_meta["tension_support"].get("neutral_band"),
        },
    }
    telemetry["structural"] = {
        "event": structural_event,
        "reasons": structural_reasons,
        "blockage_penalty": blockage_penalty_played,
    }
    telemetry["directional_pressure"] = analysis_meta.get("directional_pressure")
    if "prophylaxis" in analysis_meta:
        telemetry["prophylaxis"] = analysis_meta["prophylaxis"].get("telemetry")
        telemetry["prophylaxis_components"] = analysis_meta["prophylaxis"].get("components")
    if "prophylaxis_plan" in analysis_meta:
        telemetry["plan_drop"] = analysis_meta["prophylaxis_plan"]
    telemetry["context"] = analysis_meta.get("context")
    telemetry["intent"] = analysis_meta.get("intent_hint")

    intent_label_final = analysis_meta.get("intent_hint", {}).get("label")
    intent_flags = {
        "expansion": intent_label_final == "expansion",
        "restriction": intent_label_final == "restriction",
        "passive": intent_label_final == "passive",
        "neutral": intent_label_final == "neutral",
    }
    analysis_meta["intent_flags"] = intent_flags

    context_label = None
    if tau > 1.05:
        context_label = "winning_position_handling"
    elif tau < 0.95:
        context_label = "losing_position_handling"
    analysis_meta["context"]["label"] = context_label

    tag_flags = {
        "control_over_dynamics": control_over_dynamics,
        "cod_simplify": cod_flags["simplify"],
        "cod_plan_kill": cod_flags["plan_kill"],
        "cod_freeze_bind": cod_flags["freeze_bind"],
        "cod_blockade_passed": cod_flags["blockade_passed"],
        "cod_file_seal": cod_flags["file_seal"],
        "cod_king_safety_shell": cod_flags["king_safety_shell"],
        "cod_space_clamp": cod_flags["space_clamp"],
        "cod_regroup_consolidate": cod_flags["regroup_consolidate"],
        "cod_slowdown": cod_flags["slowdown"],
        "control_simplify": control_flags["control_simplify"],
        "control_plan_kill": control_flags["control_plan_kill"],
        "control_freeze_bind": control_flags["control_freeze_bind"],
        "control_blockade_passed": control_flags["control_blockade_passed"],
        "control_file_seal": control_flags["control_file_seal"],
        "control_king_safety_shell": control_flags["control_king_safety_shell"],
        "control_space_clamp": control_flags["control_space_clamp"],
        "control_regroup_consolidate": control_flags["control_regroup_consolidate"],
        "control_slowdown": control_flags["control_slowdown"],
        "deferred_initiative": deferred_initiative,
        "risk_avoidance": risk_avoidance,
        "structural_integrity": structural_integrity,
        "structural_compromise_dynamic": structural_compromise_dynamic,
        "structural_compromise_static": structural_compromise_static,
        "tactical_sensitivity": tactical_sensitivity,
        # Suppress generic prophylactic_move flag when quality tags exist
        "prophylactic_move": (prophylactic_move and not prophylaxis_quality),
        "file_pressure_c": file_pressure_c_flag,
        "premature_attack": premature_attack,
        "neutral_tension_creation": neutral_tension_creation,
        "constructive_maneuver": constructive_maneuver,
        "neutral_maneuver": neutral_maneuver,
        "misplaced_maneuver": misplaced_maneuver,
        "maneuver_opening": maneuver_opening,
        "opening_central_pawn_move": opening_central_pawn_move,
        "opening_rook_pawn_move": opening_rook_pawn_move,
        "tactical_sacrifice": tactical_sacrifice,
        "positional_sacrifice": positional_sacrifice,
        "inaccurate_tactical_sacrifice": inaccurate_tactical_sacrifice,
        "speculative_sacrifice": speculative_sacrifice,
        "desperate_sacrifice": desperate_sacrifice,
        "tactical_combination_sacrifice": tactical_combination_sacrifice,
        "tactical_initiative_sacrifice": tactical_initiative_sacrifice,
        "positional_structure_sacrifice": positional_structure_sacrifice,
        "positional_space_sacrifice": positional_space_sacrifice,
        "initiative_exploitation": initiative_exploitation,
        "initiative_attempt": initiative_attempt,
        "tension_creation": tension_creation,
        "first_choice": first_choice,
        "missed_tactic": missed_tactic,
        "conversion_precision": conversion_precision,
        "panic_move": panic_move,
        "tactical_recovery": tactical_recovery,
    }
    analysis_meta.setdefault("tag_flags", tag_flags)

    persistent_opening_tags: List[str] = []
    if opening_central_pawn_move:
        persistent_opening_tags.append("opening_central_pawn_move")
    if opening_rook_pawn_move:
        persistent_opening_tags.append("opening_rook_pawn_move")

    raw_tags = assemble_tags(tag_flags, TAG_ALIAS_MAP)
    for tag in persistent_opening_tags:
        if tag not in raw_tags:
            raw_tags.append(tag)
    analysis_meta["tags_initial"] = raw_tags.copy()

    if prophylaxis_quality and prophylaxis_quality not in raw_tags:
        raw_tags.append(prophylaxis_quality)
        # Note: Not adding quality aliases (direct_prophylactic, latent_prophylactic)
        # as they are not expected in golden cases - only canonical forms are used

    # Add prophylactic_failed tag if force_failure is True
    if prophylaxis_force_failure and "prophylactic_failed" not in raw_tags:
        raw_tags.append("prophylactic_failed")

    # Remove generic prophylactic_move tag if quality tags exist
    # Quality tags are more specific and the generic tag becomes noise
    if prophylaxis_quality and "prophylactic_move" in raw_tags:
        raw_tags.remove("prophylactic_move")

    analysis_meta["tags_secondary"] = raw_tags.copy()
    if context_label:
        analysis_meta["tags_secondary"].append(context_label)

    gated_tags, gating_reason = apply_tactical_gating(
        raw_tags,
        effective_delta,
        material_delta_self,
        blockage_penalty_played,
        plan_meta.get("passed"),
    )
    if gated_tags is None:
        gated_tags = raw_tags.copy()

    raw_tags, gated_tags = _attach_persistent_opening_tags(raw_tags, gated_tags, persistent_opening_tags)

    gated_tags = list(dict.fromkeys(gated_tags))
    if neutral_tension_creation and "intent_neutral" in gated_tags:
        gated_tags = [tag for tag in gated_tags if tag != "intent_neutral"]
        notes.setdefault(
            "neutral_tension_override",
            "intent_neutral suppressed due to neutral tension classification",
        )

    analysis_meta["gating"] = {
        "reason": gating_reason,
        "material_delta": material_delta_self,
        "eval_delta": delta_eval_float,
        "tags_primary": gated_tags,
    }
    telemetry["gating"] = analysis_meta["gating"]
    if gating_reason:
        notes.setdefault("gating", gating_reason)

    for key in tag_flags:
        alias = TAG_ALIAS_MAP.get(key)
        tag_flags[key] = (key in gated_tags) or (alias in gated_tags if alias else False)

    trigger_order = sorted(
        gated_tags,
        key=lambda name: TAG_PRIORITY.get(name, 999),
    )
    analysis_meta["trigger_order"] = trigger_order

    _maybe_attach_control_context_snapshot(ctx, notes)

    return TagResult(
        played_move=played_move_uci,
        played_kind=played_kind,
        best_move=best.move.uci(),
        best_kind=best.kind,
        eval_before=eval_before,
        eval_played=eval_played,
        eval_best=eval_best,
        delta_eval=delta_eval,
        control_over_dynamics=control_over_dynamics,
        control_over_dynamics_subtype=control_over_dynamics_subtype,
        cod_simplify=cod_flags["simplify"],
        cod_plan_kill=cod_flags["plan_kill"],
        cod_freeze_bind=cod_flags["freeze_bind"],
        cod_blockade_passed=cod_flags["blockade_passed"],
        cod_file_seal=cod_flags["file_seal"],
        cod_king_safety_shell=cod_flags["king_safety_shell"],
        cod_space_clamp=cod_flags["space_clamp"],
        cod_regroup_consolidate=cod_flags["regroup_consolidate"],
        cod_slowdown=cod_flags["slowdown"],
        control_simplify=control_flags["control_simplify"],
        control_plan_kill=control_flags["control_plan_kill"],
        control_freeze_bind=control_flags["control_freeze_bind"],
        control_blockade_passed=control_flags["control_blockade_passed"],
        control_file_seal=control_flags["control_file_seal"],
        control_king_safety_shell=control_flags["control_king_safety_shell"],
        control_space_clamp=control_flags["control_space_clamp"],
        control_regroup_consolidate=control_flags["control_regroup_consolidate"],
        control_slowdown=control_flags["control_slowdown"],
        control_schema_version=2,
        deferred_initiative=deferred_initiative,
        risk_avoidance=risk_avoidance,
        structural_integrity=structural_integrity,
        structural_compromise_dynamic=structural_compromise_dynamic,
        structural_compromise_static=structural_compromise_static,
        tactical_sensitivity=tactical_sensitivity,
        # Suppress generic prophylactic_move when quality tags exist
        prophylactic_move=(prophylactic_move and not prophylaxis_quality),
        prophylaxis_score=prophylaxis_score,
        initiative_exploitation=initiative_exploitation,
        initiative_attempt=initiative_attempt,
        tension_creation=tension_creation,
        neutral_tension_creation=neutral_tension_creation,
        premature_attack=premature_attack,
        constructive_maneuver=constructive_maneuver,
        constructive_maneuver_prepare=constructive_maneuver_prepare,
        neutral_maneuver=neutral_maneuver,
        misplaced_maneuver=misplaced_maneuver,
        maneuver_opening=maneuver_opening,
        opening_central_pawn_move=opening_central_pawn_move,
        opening_rook_pawn_move=opening_rook_pawn_move,
        tactical_sacrifice=tactical_sacrifice,
        positional_sacrifice=positional_sacrifice,
        inaccurate_tactical_sacrifice=inaccurate_tactical_sacrifice,
        speculative_sacrifice=speculative_sacrifice,
        desperate_sacrifice=desperate_sacrifice,
        tactical_combination_sacrifice=tactical_combination_sacrifice,
        tactical_initiative_sacrifice=tactical_initiative_sacrifice,
        positional_structure_sacrifice=positional_structure_sacrifice,
        positional_space_sacrifice=positional_space_sacrifice,
        file_pressure_c=file_pressure_c_flag,
        first_choice=first_choice,
        missed_tactic=missed_tactic,
        conversion_precision=conversion_precision,
        panic_move=panic_move,
        tactical_recovery=tactical_recovery,
        accurate_knight_bishop_exchange=False,
        inaccurate_knight_bishop_exchange=False,
        bad_knight_bishop_exchange=False,
        failed_prophylactic=False,
        metrics_before=metrics_before,
        metrics_played=metrics_played,
        metrics_best=metrics_best,
        component_deltas=component_deltas,
        opp_metrics_before=opp_metrics_before,
        opp_metrics_played=opp_metrics_played,
        opp_metrics_best=opp_metrics_best,
        opp_component_deltas=opp_component_deltas,
        coverage_delta=coverage_delta,
        tactical_weight=tactical_weight,
        mode=mode,
        analysis_context={
            "before": evaluation_before,
            "played": evaluation_played,
            "best": evaluation_best,
            "engine_meta": analysis_meta,
            "tactical_weight": tactical_weight,
            # Use suppressed flag value (False when quality tags exist)
            "prophylactic_move": (prophylactic_move and not prophylaxis_quality),
            "prophylaxis_force_failure": prophylaxis_force_failure,
        },
        notes=notes,
        maneuver_precision_score=maneuver_precision_score,
        maneuver_timing_score=maneuver_timing_score,
        prepare_quality_score=prepare_quality_score,
        prepare_consensus_score=prepare_consensus_score,
    )
