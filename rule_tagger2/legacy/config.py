"""
Rule tagger numeric configuration constants and defaults.
"""
from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Sequence, Set, Tuple

MOBILITY_TOLERANCE = 0.35
CENTER_TOLERANCE = 0.25
KING_SAFETY_TOLERANCE = 0.25
KING_SAFETY_GAIN = 0.3
MOBILITY_RISK_TRADEOFF = 1.2
STRUCTURE_THRESHOLD = 0.2
TACTICAL_THRESHOLD = 0.15
TACTICAL_DOMINANCE_THRESHOLD = 300  # cp
TACTICAL_SLOPE_THRESHOLD = 50       # cp
TACTICAL_DELTA_TACTICS = 0.3
STRUCTURE_DOMINANCE_LIMIT = 0.4

DELTA_EVAL_POSITIONAL = 300  # cp
CONTROL_EVAL_DROP = 25       # cp
CONTROL_VOLATILITY_DROP_CP = 36  # cp
CONTROL_TENSION_DELTA = -1.0
CONTROL_TENSION_DELTA_ENDGAME = -2.0
CONTROL_OPP_MOBILITY_DROP = 3
CONTROL_COOLDOWN_PLIES = 3
CONTROL_TACTICAL_WEIGHT_CEILING = 0.55
CONTROL_PHASE_WEIGHTS = {
    "opening": 1.0,
    "middlegame": 1.0,
    "endgame": 1.2,
}
CONTROL_SIMPLIFY_MIN_EXCHANGE = 2
CONTROL_KING_SAFETY_THRESH = 0.15
CONTROL_BLUNDER_THREAT_THRESH = 120  # cp

RISK_SMALL_LOSS = 50         # cp
INITIATIVE_BOOST = 50        # cp

TACTICAL_GAP_FIRST_CHOICE = 80   # cp
TACTICAL_MISS_LOSS = 150         # cp

STYLE_COMPONENT_KEYS: Tuple[str, ...] = (
    "mobility",
    "center_control",
    "king_safety",
    "structure",
    "tactics",
)

CENTER_FILES: Set[int] = {3, 4}  # d/e files

TENSION_EVAL_MIN = -0.9
TENSION_EVAL_MAX = 0.1
TENSION_SYMMETRY_TOL = 0.23
NEUTRAL_TENSION_BAND = 0.12

THRESHOLD_FILE = Path(__file__).resolve().parents[1] / "metrics_thresholds.yml"

CONTROL_DEFAULTS: Dict[str, Any] = {
    "ENABLED": True,
    "STRICT_MODE": False,
    "DEBUG_CONTEXT": False,
    "EVAL_DROP_CP": CONTROL_EVAL_DROP,
    "VOLATILITY_DROP_CP": CONTROL_VOLATILITY_DROP_CP,
    "OP_MOBILITY_DROP": CONTROL_OPP_MOBILITY_DROP,
    "TENSION_DEC_MIN": 0,
    "KS_MIN": 15,
    "SPACE_MIN": 1,
    "PASSED_PUSH_MIN": 0,
    "ALLOW_SEE_BLOCKADE": True,
    "LINE_MIN": 2,
    "COOLDOWN_PLIES": CONTROL_COOLDOWN_PLIES,
    "TACTICAL_WEIGHT_MAX_FOR_PRO_CO": CONTROL_TACTICAL_WEIGHT_CEILING,
    "PHASE_ADJUST": {
        "OPEN": {"VOL_BONUS": 0, "OP_MOB_DROP": 2},
        "MID": {"VOL_BONUS": 0, "OP_MOB_DROP": 2},
        "END": {"VOL_BONUS": 5, "OP_MOB_DROP": 3},
    },
    "PLAN_KILL_STRICT": True,
    "VOL_GATE_FOR_PLAN": True,
    "PRIORITY": [
        "simplify",
        "plan_kill",
        "freeze_bind",
        "blockade_passed",
        "file_seal",
        "king_safety_shell",
        "space_clamp",
        "regroup_consolidate",
        "slowdown",
    ],
    "PRIORITY_END": [
        "simplify",
        "blockade_passed",
        "king_safety_shell",
        "space_clamp",
        "file_seal",
        "freeze_bind",
        "plan_kill",
        "regroup_consolidate",
        "slowdown",
    ],
    "RARE_TYPES": {"freeze_bind", "space_clamp", "blockade_passed"},
    "TIE_BREAK_DELTA": 1,
    "PHASE_WEIGHTS": {
        "OPEN": {"space_clamp": 2, "freeze_bind": 2},
        "MID": {"space_clamp": 2, "freeze_bind": 2},
        "END": {"blockade_passed": 3, "king_safety_shell": 3},
    },
}

_CONTROL_OVERRIDE_SPECS: Sequence[Tuple[Sequence[str], str, str]] = (
    (("ENABLED",), "control_enabled", "bool"),
    (("ENABLED",), "CONTROL.enabled", "bool"),
    (("STRICT_MODE",), "control_strict_mode", "bool"),
    (("STRICT_MODE",), "CONTROL.strict_mode", "bool"),
    (("DEBUG_CONTEXT",), "control_debug_context", "bool"),
    (("EVAL_DROP_CP",), "control_eval_drop_cp", "int"),
    (("VOLATILITY_DROP_CP",), "control_volatility_drop_cp", "int"),
    (("OP_MOBILITY_DROP",), "control_op_mobility_drop", "int"),
    (("TENSION_DEC_MIN",), "control_tension_dec_min", "float"),
    (("KS_MIN",), "control_ks_min", "float"),
    (("SPACE_MIN",), "control_space_min", "int"),
    (("PASSED_PUSH_MIN",), "control_passed_push_min", "int"),
    (("ALLOW_SEE_BLOCKADE",), "control_allow_see_blockade", "bool"),
    (("LINE_MIN",), "control_line_min", "int"),
    (("COOLDOWN_PLIES",), "control_cooldown_plies", "int"),
    (("TACTICAL_WEIGHT_MAX_FOR_PRO_CO",), "control_tactical_weight_max", "float"),
    (("PHASE_ADJUST", "OPEN", "VOL_BONUS"), "control_phase_adjust_open_vol_bonus", "int"),
    (("PHASE_ADJUST", "OPEN", "OP_MOB_DROP"), "control_phase_adjust_open_op_mob_drop", "int"),
    (("PHASE_ADJUST", "MID", "VOL_BONUS"), "control_phase_adjust_mid_vol_bonus", "int"),
    (("PHASE_ADJUST", "MID", "OP_MOB_DROP"), "control_phase_adjust_mid_op_mob_drop", "int"),
    (("PHASE_ADJUST", "END", "VOL_BONUS"), "control_phase_adjust_end_vol_bonus", "int"),
    (("PHASE_ADJUST", "END", "OP_MOB_DROP"), "control_phase_adjust_end_op_mob_drop", "int"),
    (("PRIORITY",), "control_priority", "list"),
    (("PRIORITY_END",), "control_priority_end", "list"),
    (("PLAN_KILL_STRICT",), "control_plan_kill_strict", "bool"),
    (("VOL_GATE_FOR_PLAN",), "control_vol_gate_for_plan", "bool"),
)


def _read_override_file(path: Path) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if not path.exists():
        return overrides
    try:
        with path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                cleaned = value.split("#", 1)[0].strip()
                overrides[key.strip()] = cleaned
    except OSError:
        return {}
    return overrides


def _set_nested(mapping: Dict[str, Any], path: Sequence[str], value: Any) -> None:
    cursor = mapping
    for key in path[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[path[-1]] = value


def _coerce_value(raw: str, kind: str) -> Any:
    if kind == "int":
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return None
    if kind == "float":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    if kind == "bool":
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return None
    if kind == "list":
        text = raw.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            inner = text[1:-1].strip()
            if not inner:
                return []
            return [item.strip() for item in inner.split(",") if item.strip()]
        return [item.strip() for item in text.split(",") if item.strip()]
    return raw


def _apply_yaml_overrides(config: Dict[str, Any], entries: Dict[str, str]) -> None:
    for path, yaml_key, kind in _CONTROL_OVERRIDE_SPECS:
        raw = entries.get(yaml_key)
        if raw is None:
            continue
        coerced = _coerce_value(raw, kind)
        if coerced is not None:
            _set_nested(config, path, coerced)


def _apply_env_overrides(config: Dict[str, Any]) -> None:
    for path, _yaml_key, kind in _CONTROL_OVERRIDE_SPECS:
        env_key = "CONTROL_" + "_".join(path)
        raw = os.environ.get(env_key)
        if raw is None:
            continue
        coerced = _coerce_value(raw, kind)
        if coerced is not None:
            _set_nested(config, path, coerced)


def _normalize_flag(config: Dict[str, Any], canonical: str, alias: str, default: bool) -> bool:
    value = config.get(alias)
    if value is None:
        value = config.get(canonical, default)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            normalized = True
        elif lowered in {"0", "false", "no", "off"}:
            normalized = False
        else:
            normalized = default
    elif isinstance(value, bool):
        normalized = value
    elif isinstance(value, (int, float)):
        normalized = bool(value)
    else:
        normalized = default if value is None else bool(value)
    config[canonical] = normalized
    config[alias] = normalized
    return normalized


def _load_control_config() -> Dict[str, Any]:
    config = deepcopy(CONTROL_DEFAULTS)
    overrides = _read_override_file(THRESHOLD_FILE)
    if overrides:
        _apply_yaml_overrides(config, overrides)
    _apply_env_overrides(config)
    # ensure priority remains list to avoid accidental tuple conversions
    config["PRIORITY"] = list(config.get("PRIORITY", []))
    _normalize_flag(config, "ENABLED", "enabled", True)
    _normalize_flag(config, "STRICT_MODE", "strict_mode", False)
    _normalize_flag(config, "DEBUG_CONTEXT", "debug_context", False)
    return config


CONTROL: Dict[str, Any] = _load_control_config()

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "tension_mobility_min": 0.38,
    "tension_mobility_near": 0.3,
    "contact_ratio_min": 0.04,
    "contact_ratio_delay": 0.03,
    "tension_mobility_delay": 0.25,
    "tension_trend_self": -0.3,
    "tension_trend_opp": 0.3,
    "tension_sustain_min": 0.15,
    "tension_sustain_var_cap": 0.2,
    "static_blockage_threshold": 1.2,
    "static_blockage_hysteresis": 0.05,
    "soft_block_scale": 0.75,
    "prophylaxis_plan_drop_enabled": 0.0,
    "plan_drop_psi_min": 0.6,
    "plan_drop_eval_cap": -0.3,
    "plan_drop_multipv": 5.0,
    "plan_drop_depth": 8.0,
    "plan_drop_sample_rate": 0.3,
    "plan_drop_variance_cap": 0.2,
    "plan_drop_runtime_cap_ms": 800.0,
    "plan_drop_plan_loss_min": 0.15,
    "prophylaxis_preventive_trigger": 0.08,
    "prophylaxis_safety_bonus_cap": 0.6,
    "prophylaxis_threat_drop": 0.3,
    "winning_tau_max": 2.0,
    "winning_tau_scale": 0.2,
    "losing_tau_min": 0.6,
    "losing_tau_scale": 0.2,
    "soft_gate_midpoint": -0.25,
    "soft_gate_width": 0.1,
    "maneuver_constructive_threshold": 0.25,
    "maneuver_neutral_threshold": 0.0,
    "maneuver_misplaced_threshold": -0.25,
    "maneuver_eval_tolerance": 0.12,
    "maneuver_timing_constructive_bonus": 0.9,
    "maneuver_precision_bonus_threshold": 0.18,
    "maneuver_eval_bonus_tolerance": 0.12,
    "maneuver_bonus_center_threshold": 0.2,
    "maneuver_bonus_structure_threshold": 0.15,
    "maneuver_bonus_mobility_threshold": 0.1,
    "maneuver_low_impact_center": 0.08,
    "maneuver_low_impact_structure": 0.05,
    "maneuver_low_impact_mobility": 0.05,
    "maneuver_structural_timing_bonus": 0.7,
    "maneuver_timing_neutral": 0.5,
    "maneuver_trend_neutral": 0.08,
    "maneuver_allow_light_capture": 0.0,
    "maneuver_opening_fullmove_cutoff": 12.0,
    "maneuver_ev_fail_cp": 60.0,
    "maneuver_ev_protect_cp": 20.0,
    "aggression_threshold": 0.4,
    "risk_avoidance_mobility_drop": 0.1,
    "structure_weaken_limit": -0.2,
    "mobility_self_limit": 0.25,
    "file_pressure_threshold": 0.35,
    "volatility_drop_tolerance": 0.05,
    "premature_attack_threshold": -0.25,
    "premature_attack_hard": -0.4,
}

__all__ = [
    "CONTROL",
    "CONTROL_DEFAULTS",
    "CENTER_FILES",
    "CENTER_TOLERANCE",
    "CONTROL_EVAL_DROP",
    "DEFAULT_THRESHOLDS",
    "DELTA_EVAL_POSITIONAL",
    "INITIATIVE_BOOST",
    "KING_SAFETY_GAIN",
    "CONTROL_VOLATILITY_DROP_CP",
    "CONTROL_TENSION_DELTA",
    "CONTROL_TENSION_DELTA_ENDGAME",
    "CONTROL_OPP_MOBILITY_DROP",
    "CONTROL_COOLDOWN_PLIES",
    "CONTROL_TACTICAL_WEIGHT_CEILING",
    "CONTROL_PHASE_WEIGHTS",
    "CONTROL_SIMPLIFY_MIN_EXCHANGE",
    "CONTROL_KING_SAFETY_THRESH",
    "CONTROL_BLUNDER_THREAT_THRESH",
    "KING_SAFETY_TOLERANCE",
    "MOBILITY_RISK_TRADEOFF",
    "MOBILITY_TOLERANCE",
    "NEUTRAL_TENSION_BAND",
    "RISK_SMALL_LOSS",
    "STRUCTURE_DOMINANCE_LIMIT",
    "STRUCTURE_THRESHOLD",
    "STYLE_COMPONENT_KEYS",
    "TACTICAL_DELTA_TACTICS",
    "TACTICAL_DOMINANCE_THRESHOLD",
    "TACTICAL_GAP_FIRST_CHOICE",
    "TACTICAL_MISS_LOSS",
    "TACTICAL_SLOPE_THRESHOLD",
    "TACTICAL_THRESHOLD",
    "TENSION_EVAL_MAX",
    "TENSION_EVAL_MIN",
    "TENSION_SYMMETRY_TOL",
    "THRESHOLD_FILE",
]
