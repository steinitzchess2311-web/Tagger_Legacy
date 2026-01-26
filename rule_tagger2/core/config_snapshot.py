"""
Configuration snapshot utility for runtime threshold verification.

This module provides build_config_snapshot() to capture all active thresholds
from YAML, environment variables, and code defaults. Used for:
- Debugging threshold issues
- Ensuring YAML values are correctly loaded
- Preventing silent fallback to defaults
- A/B testing validation
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Import all threshold constants from config
from rule_tagger2.legacy.config import (
    CENTER_FILES,
    CENTER_TOLERANCE,
    CONTROL_BLUNDER_THREAT_THRESH,
    CONTROL_COOLDOWN_PLIES,
    CONTROL_DEFAULTS,
    CONTROL_EVAL_DROP,
    CONTROL_KING_SAFETY_THRESH,
    CONTROL_OPP_MOBILITY_DROP,
    CONTROL_PHASE_WEIGHTS,
    CONTROL_SIMPLIFY_MIN_EXCHANGE,
    CONTROL_TACTICAL_WEIGHT_CEILING,
    CONTROL_TENSION_DELTA,
    CONTROL_TENSION_DELTA_ENDGAME,
    CONTROL_VOLATILITY_DROP_CP,
    DEFAULT_THRESHOLDS,
    DELTA_EVAL_POSITIONAL,
    INITIATIVE_BOOST,
    KING_SAFETY_GAIN,
    KING_SAFETY_TOLERANCE,
    MOBILITY_RISK_TRADEOFF,
    MOBILITY_TOLERANCE,
    NEUTRAL_TENSION_BAND,
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
    THRESHOLD_FILE,
    _read_override_file,
)

from rule_tagger2.legacy.thresholds import (
    AGGRESSION_THRESHOLD as LEGACY_AGGRESSION_THRESHOLD,
    FILE_PRESSURE_THRESHOLD,
    LOSING_TAU_MIN,
    LOSING_TAU_SCALE,
    MANEUVER_ALLOW_LIGHT_CAPTURE,
    MANEUVER_CONSTRUCTIVE,
    MANEUVER_EV_FAIL_CP,
    MANEUVER_EV_PROTECT_CP,
    MANEUVER_EVAL_TOLERANCE,
    MANEUVER_MISPLACED,
    MANEUVER_NEUTRAL,
    MANEUVER_OPENING_CUTOFF,
    MANEUVER_TIMING_NEUTRAL,
    MANEUVER_TREND_NEUTRAL,
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
    TENSION_CONTACT_JUMP,
    TENSION_MOBILITY_DELAY,
    TENSION_MOBILITY_NEAR,
    TENSION_MOBILITY_THRESHOLD,
    TENSION_SUSTAIN_MIN,
    TENSION_SUSTAIN_VAR_CAP,
    TENSION_TREND_OPP,
    TENSION_TREND_SELF,
    VOLATILITY_DROP_TOL,
    WINNING_TAU_MAX,
    WINNING_TAU_SCALE,
)


def build_config_snapshot(
    include_hash: bool = True,
    include_env: bool = True,
    include_control: bool = True,
) -> Dict[str, Any]:
    """
    Build a complete snapshot of all active configuration thresholds.

    This function captures:
    1. All Python default constants
    2. YAML overrides from metrics_thresholds.yml
    3. Environment variable overrides
    4. Control dynamics configuration
    5. A hash of the snapshot for comparison

    Args:
        include_hash: If True, compute and include a SHA256 hash of the config
        include_env: If True, include environment variable info
        include_control: If True, include full CONTROL config

    Returns:
        Dictionary with all active thresholds and metadata

    Example:
        >>> snapshot = build_config_snapshot()
        >>> print(f"Tension mobility min: {snapshot['tension']['mobility_min']}")
        >>> print(f"Config hash: {snapshot['_metadata']['hash']}")
    """
    # Read YAML overrides
    yaml_overrides = _read_override_file(THRESHOLD_FILE)

    # Helper to get value with YAML override
    def get_value(yaml_key: str, default: Any) -> Any:
        if yaml_key in yaml_overrides:
            raw = yaml_overrides[yaml_key]
            # Try to coerce to same type as default
            if isinstance(default, bool):
                return raw.lower() in {"1", "true", "yes", "on"}
            elif isinstance(default, int):
                try:
                    return int(float(raw))
                except (ValueError, TypeError):
                    return default
            elif isinstance(default, float):
                try:
                    return float(raw)
                except (ValueError, TypeError):
                    return default
            else:
                return raw
        return default

    # Build the snapshot
    snapshot: Dict[str, Any] = {
        # === Tension Detection ===
        "tension": {
            "mobility_min": get_value("tension_mobility_min", TENSION_MOBILITY_THRESHOLD),
            "mobility_near": get_value("tension_mobility_near", TENSION_MOBILITY_NEAR),
            "mobility_delay": get_value("tension_mobility_delay", TENSION_MOBILITY_DELAY),
            "contact_ratio_min": get_value("contact_ratio_min", TENSION_CONTACT_JUMP),
            "contact_ratio_delay": get_value("contact_ratio_delay", TENSION_CONTACT_DELAY),
            "trend_self": get_value("tension_trend_self", TENSION_TREND_SELF),
            "trend_opp": get_value("tension_trend_opp", TENSION_TREND_OPP),
            "sustain_min": get_value("tension_sustain_min", TENSION_SUSTAIN_MIN),
            "sustain_var_cap": get_value("tension_sustain_var_cap", TENSION_SUSTAIN_VAR_CAP),
            "eval_min": TENSION_EVAL_MIN,
            "eval_max": TENSION_EVAL_MAX,
            "symmetry_tol": TENSION_SYMMETRY_TOL,
            "neutral_band": NEUTRAL_TENSION_BAND,
        },
        # === Structural ===
        "structural": {
            "blockage_threshold": get_value("static_blockage_threshold", STATIC_BLOCKAGE_THRESHOLD_BASE),
            "blockage_hysteresis": get_value("static_blockage_hysteresis", STATIC_BLOCKAGE_MARGIN),
            "soft_block_scale": get_value("soft_block_scale", SOFT_BLOCK_SCALE),
            "weaken_limit": get_value("structure_weaken_limit", STRUCTURE_WEAKEN_LIMIT),
            "threshold": STRUCTURE_THRESHOLD,
            "dominance_limit": STRUCTURE_DOMINANCE_LIMIT,
        },
        # === Prophylaxis ===
        "prophylaxis": {
            "preventive_trigger": get_value("prophylaxis_preventive_trigger", DEFAULT_THRESHOLDS["prophylaxis_preventive_trigger"]),
            "safety_bonus_cap": get_value("prophylaxis_safety_bonus_cap", DEFAULT_THRESHOLDS["prophylaxis_safety_bonus_cap"]),
            "plan_drop_enabled": get_value("prophylaxis_plan_drop_enabled", PLAN_DROP_ENABLED),
            "plan_drop_psi_min": get_value("plan_drop_psi_min", PLAN_DROP_PSI_MIN),
            "plan_drop_eval_cap": get_value("plan_drop_eval_cap", PLAN_DROP_EVAL_CAP),
            "plan_drop_multipv": get_value("plan_drop_multipv", PLAN_DROP_MULTIPV),
            "plan_drop_depth": get_value("plan_drop_depth", PLAN_DROP_DEPTH),
            "plan_drop_sample_rate": get_value("plan_drop_sample_rate", PLAN_DROP_SAMPLE_RATE),
            "plan_drop_variance_cap": get_value("plan_drop_variance_cap", PLAN_DROP_VARIANCE_CAP),
            "plan_drop_runtime_cap_ms": get_value("plan_drop_runtime_cap_ms", PLAN_DROP_RUNTIME_CAP_MS),
            "plan_drop_plan_loss_min": get_value("plan_drop_plan_loss_min", PLAN_DROP_PLAN_LOSS_MIN),
            "plan_drop_opp_mobility_gate": PLAN_DROP_OPP_MOBILITY_GATE,
        },
        # === Mobility & Positioning ===
        "mobility": {
            "tolerance": MOBILITY_TOLERANCE,
            "self_limit": get_value("mobility_self_limit", MOBILITY_SELF_LIMIT),
            "risk_tradeoff": MOBILITY_RISK_TRADEOFF,
            "risk_avoidance_drop": get_value("risk_avoidance_mobility_drop", RISK_AVOIDANCE_MOBILITY_DROP),
        },
        # === Tactical ===
        "tactical": {
            "threshold": TACTICAL_THRESHOLD,
            "dominance_threshold": TACTICAL_DOMINANCE_THRESHOLD,
            "slope_threshold": TACTICAL_SLOPE_THRESHOLD,
            "delta_tactics": TACTICAL_DELTA_TACTICS,
            "gap_first_choice": TACTICAL_GAP_FIRST_CHOICE,
            "miss_loss": TACTICAL_MISS_LOSS,
        },
        # === Soft Gate & Tau ===
        "soft_gate": {
            "midpoint": get_value("soft_gate_midpoint", SOFT_GATE_MIDPOINT),
            "width": get_value("soft_gate_width", SOFT_GATE_WIDTH),
        },
        "tau": {
            "winning_max": get_value("winning_tau_max", WINNING_TAU_MAX),
            "winning_scale": get_value("winning_tau_scale", WINNING_TAU_SCALE),
            "losing_min": get_value("losing_tau_min", LOSING_TAU_MIN),
            "losing_scale": get_value("losing_tau_scale", LOSING_TAU_SCALE),
        },
        # === Maneuver ===
        "maneuver": {
            "constructive_threshold": get_value("maneuver_constructive_threshold", MANEUVER_CONSTRUCTIVE),
            "neutral_threshold": get_value("maneuver_neutral_threshold", MANEUVER_NEUTRAL),
            "misplaced_threshold": get_value("maneuver_misplaced_threshold", MANEUVER_MISPLACED),
            "eval_tolerance": get_value("maneuver_eval_tolerance", MANEUVER_EVAL_TOLERANCE),
            "timing_neutral": get_value("maneuver_timing_neutral", MANEUVER_TIMING_NEUTRAL),
            "trend_neutral": get_value("maneuver_trend_neutral", MANEUVER_TREND_NEUTRAL),
            "ev_fail_cp": get_value("maneuver_ev_fail_cp", MANEUVER_EV_FAIL_CP),
            "ev_protect_cp": get_value("maneuver_ev_protect_cp", MANEUVER_EV_PROTECT_CP),
            "allow_light_capture": get_value("maneuver_allow_light_capture", MANEUVER_ALLOW_LIGHT_CAPTURE),
            "opening_fullmove_cutoff": get_value("maneuver_opening_fullmove_cutoff", MANEUVER_OPENING_CUTOFF),
        },
        # === Other Thresholds ===
        "other": {
            "aggression_threshold": get_value("aggression_threshold", LEGACY_AGGRESSION_THRESHOLD),
            "file_pressure_threshold": get_value("file_pressure_threshold", FILE_PRESSURE_THRESHOLD),
            "volatility_drop_tolerance": get_value("volatility_drop_tolerance", VOLATILITY_DROP_TOL),
            "premature_attack_threshold": get_value("premature_attack_threshold", PREMATURE_ATTACK_THRESHOLD),
            "premature_attack_hard": get_value("premature_attack_hard", PREMATURE_ATTACK_HARD),
            "delta_eval_positional": DELTA_EVAL_POSITIONAL,
            "risk_small_loss": RISK_SMALL_LOSS,
            "initiative_boost": INITIATIVE_BOOST,
            "king_safety_gain": KING_SAFETY_GAIN,
            "king_safety_tolerance": KING_SAFETY_TOLERANCE,
            "center_tolerance": CENTER_TOLERANCE,
        },
        # === Passive Plan ===
        "passive_plan": {
            "eval_drop": PASSIVE_PLAN_EVAL_DROP,
            "mobility_opp": PASSIVE_PLAN_MOBILITY_OPP,
            "mobility_self": PASSIVE_PLAN_MOBILITY_SELF,
        },
    }

    # Add Control Dynamics config if requested
    if include_control:
        from rule_tagger2.legacy.config import CONTROL
        snapshot["control"] = CONTROL.copy() if hasattr(CONTROL, 'copy') else dict(CONTROL_DEFAULTS)

    # Add metadata
    snapshot["_metadata"] = {
        "yaml_file": str(THRESHOLD_FILE),
        "yaml_exists": THRESHOLD_FILE.exists(),
        "yaml_keys_loaded": len(yaml_overrides),
        "yaml_keys": list(yaml_overrides.keys()) if yaml_overrides else [],
    }

    # Add environment variable info if requested
    if include_env:
        env_vars = {}
        for key in os.environ:
            if key.startswith("CONTROL_") or key.startswith("TENSION_") or key.startswith("USE_NEW_"):
                env_vars[key] = os.environ[key]
        snapshot["_metadata"]["env_vars"] = env_vars

    # Compute hash if requested
    if include_hash:
        # Create a deterministic JSON string (sorted keys)
        config_str = json.dumps(
            {k: v for k, v in snapshot.items() if k != "_metadata"},
            sort_keys=True,
            default=str
        )
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]
        snapshot["_metadata"]["hash"] = config_hash

    return snapshot


def print_config_snapshot(
    snapshot: Optional[Dict[str, Any]] = None,
    sections: Optional[list] = None
) -> None:
    """
    Print config snapshot in a readable format.

    Args:
        snapshot: Pre-built snapshot, or None to build one
        sections: List of section names to print, or None for all
    """
    if snapshot is None:
        snapshot = build_config_snapshot()

    all_sections = [k for k in snapshot.keys() if not k.startswith("_")]
    sections_to_print = sections if sections else all_sections

    print("=" * 80)
    print("CONFIGURATION SNAPSHOT")
    print("=" * 80)

    # Print metadata first
    if "_metadata" in snapshot:
        meta = snapshot["_metadata"]
        print(f"\nYAML File: {meta.get('yaml_file', 'N/A')}")
        print(f"YAML Exists: {meta.get('yaml_exists', False)}")
        print(f"YAML Keys Loaded: {meta.get('yaml_keys_loaded', 0)}")
        if "hash" in meta:
            print(f"Config Hash: {meta['hash']}")
        if "env_vars" in meta and meta["env_vars"]:
            print(f"\nEnvironment Variables ({len(meta['env_vars'])}):")
            for k, v in sorted(meta["env_vars"].items()):
                print(f"  {k} = {v}")
        print()

    # Print each section
    for section in sections_to_print:
        if section not in snapshot:
            continue
        print(f"\n[{section.upper()}]")
        print("-" * 80)
        data = snapshot[section]
        if isinstance(data, dict):
            for key, value in sorted(data.items()):
                if isinstance(value, (dict, list)) and len(str(value)) > 60:
                    print(f"  {key}: {type(value).__name__} (omitted for brevity)")
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"  {data}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # When run as a script, print the full config snapshot
    snapshot = build_config_snapshot()
    print_config_snapshot(snapshot)
