"""
Threshold loading utilities for the rule tagger.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from .config import DEFAULT_THRESHOLDS, THRESHOLD_FILE


def _load_thresholds(path: Path) -> Dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    if not path.exists():
        return thresholds
    try:
        with path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip()
                if key not in thresholds:
                    continue
                try:
                    thresholds[key] = float(value.strip())
                except ValueError:
                    continue
    except OSError:
        return thresholds
    return thresholds


THRESHOLDS = _load_thresholds(THRESHOLD_FILE)

TENSION_MOBILITY_THRESHOLD = THRESHOLDS["tension_mobility_min"]
TENSION_MOBILITY_NEAR = THRESHOLDS.get("tension_mobility_near", TENSION_MOBILITY_THRESHOLD * 0.8)
TENSION_CONTACT_JUMP = THRESHOLDS["contact_ratio_min"]
TENSION_CONTACT_DELAY = THRESHOLDS["contact_ratio_delay"]
TENSION_MOBILITY_DELAY = THRESHOLDS["tension_mobility_delay"]
TENSION_TREND_SELF = THRESHOLDS["tension_trend_self"]
TENSION_TREND_OPP = THRESHOLDS["tension_trend_opp"]
TENSION_SUSTAIN_MIN = THRESHOLDS["tension_sustain_min"]
TENSION_SUSTAIN_VAR_CAP = THRESHOLDS["tension_sustain_var_cap"]
TENSION_CONTACT_DIRECT = max(TENSION_CONTACT_JUMP, 0.05)
STATIC_BLOCKAGE_THRESHOLD_BASE = THRESHOLDS["static_blockage_threshold"]
STATIC_BLOCKAGE_MARGIN = THRESHOLDS["static_blockage_hysteresis"]
SOFT_BLOCK_SCALE = THRESHOLDS["soft_block_scale"]
PLAN_DROP_ENABLED = THRESHOLDS["prophylaxis_plan_drop_enabled"] > 0.5
PLAN_DROP_PSI_MIN = THRESHOLDS["plan_drop_psi_min"]
PLAN_DROP_EVAL_CAP = THRESHOLDS["plan_drop_eval_cap"]
PLAN_DROP_MULTIPV = int(THRESHOLDS["plan_drop_multipv"])
PLAN_DROP_DEPTH = int(THRESHOLDS["plan_drop_depth"])
PLAN_DROP_SAMPLE_RATE = max(0.0, min(1.0, THRESHOLDS["plan_drop_sample_rate"]))
PLAN_DROP_VARIANCE_CAP = THRESHOLDS["plan_drop_variance_cap"]
PLAN_DROP_RUNTIME_CAP_MS = THRESHOLDS["plan_drop_runtime_cap_ms"]
PLAN_DROP_PLAN_LOSS_MIN = THRESHOLDS["plan_drop_plan_loss_min"]
PLAN_DROP_OPP_MOBILITY_GATE = 0.25
PASSIVE_PLAN_EVAL_DROP = -0.4
PASSIVE_PLAN_MOBILITY_SELF = -0.3
PASSIVE_PLAN_MOBILITY_OPP = 0.3

WINNING_TAU_MAX = THRESHOLDS["winning_tau_max"]
WINNING_TAU_SCALE = THRESHOLDS["winning_tau_scale"]
LOSING_TAU_MIN = THRESHOLDS["losing_tau_min"]
LOSING_TAU_SCALE = THRESHOLDS["losing_tau_scale"]
SOFT_GATE_MIDPOINT = THRESHOLDS["soft_gate_midpoint"]
SOFT_GATE_WIDTH = THRESHOLDS["soft_gate_width"]
MANEUVER_CONSTRUCTIVE = THRESHOLDS["maneuver_constructive_threshold"]
MANEUVER_NEUTRAL = THRESHOLDS["maneuver_neutral_threshold"]
MANEUVER_MISPLACED = THRESHOLDS["maneuver_misplaced_threshold"]
MANEUVER_EV_FAIL_CP = THRESHOLDS.get("maneuver_ev_fail_cp", 60.0)
MANEUVER_EV_PROTECT_CP = THRESHOLDS.get("maneuver_ev_protect_cp", 20.0)
MANEUVER_EVAL_TOLERANCE = THRESHOLDS.get("maneuver_eval_tolerance", 0.12)
MANEUVER_TIMING_NEUTRAL = THRESHOLDS.get("maneuver_timing_neutral", 0.5)
MANEUVER_TREND_NEUTRAL = THRESHOLDS.get("maneuver_trend_neutral", 0.08)
MANEUVER_ALLOW_LIGHT_CAPTURE = THRESHOLDS.get("maneuver_allow_light_capture", 0.0) > 0.5
MANEUVER_OPENING_CUTOFF = int(THRESHOLDS.get("maneuver_opening_fullmove_cutoff", 12.0))
AGGRESSION_THRESHOLD = THRESHOLDS["aggression_threshold"]
RISK_AVOIDANCE_MOBILITY_DROP = THRESHOLDS["risk_avoidance_mobility_drop"]
STRUCTURE_WEAKEN_LIMIT = THRESHOLDS["structure_weaken_limit"]
MOBILITY_SELF_LIMIT = THRESHOLDS["mobility_self_limit"]
FILE_PRESSURE_THRESHOLD = THRESHOLDS["file_pressure_threshold"]
VOLATILITY_DROP_TOL = THRESHOLDS["volatility_drop_tolerance"]
PREMATURE_ATTACK_THRESHOLD = THRESHOLDS["premature_attack_threshold"]
PREMATURE_ATTACK_HARD = THRESHOLDS["premature_attack_hard"]

__all__ = [
    "AGGRESSION_THRESHOLD",
    "FILE_PRESSURE_THRESHOLD",
    "LOSING_TAU_MIN",
    "LOSING_TAU_SCALE",
    "MANEUVER_CONSTRUCTIVE",
    "MANEUVER_MISPLACED",
    "MANEUVER_NEUTRAL",
    "MANEUVER_EVAL_TOLERANCE",
    "MANEUVER_EV_FAIL_CP",
    "MANEUVER_EV_PROTECT_CP",
    "MANEUVER_TIMING_NEUTRAL",
    "MANEUVER_TREND_NEUTRAL",
    "MANEUVER_ALLOW_LIGHT_CAPTURE",
    "MANEUVER_OPENING_CUTOFF",
    "MOBILITY_SELF_LIMIT",
    "PASSIVE_PLAN_EVAL_DROP",
    "PASSIVE_PLAN_MOBILITY_OPP",
    "PASSIVE_PLAN_MOBILITY_SELF",
    "PLAN_DROP_DEPTH",
    "PLAN_DROP_ENABLED",
    "PLAN_DROP_EVAL_CAP",
    "PLAN_DROP_MULTIPV",
    "PLAN_DROP_PLAN_LOSS_MIN",
    "PLAN_DROP_PSI_MIN",
    "PLAN_DROP_RUNTIME_CAP_MS",
    "PLAN_DROP_SAMPLE_RATE",
    "PLAN_DROP_VARIANCE_CAP",
    "PLAN_DROP_OPP_MOBILITY_GATE",
    "PREMATURE_ATTACK_HARD",
    "PREMATURE_ATTACK_THRESHOLD",
    "RISK_AVOIDANCE_MOBILITY_DROP",
    "SOFT_BLOCK_SCALE",
    "SOFT_GATE_MIDPOINT",
    "SOFT_GATE_WIDTH",
    "STATIC_BLOCKAGE_MARGIN",
    "STATIC_BLOCKAGE_THRESHOLD_BASE",
    "STRUCTURE_WEAKEN_LIMIT",
    "TENSION_CONTACT_DELAY",
    "TENSION_CONTACT_DIRECT",
    "TENSION_CONTACT_JUMP",
    "TENSION_MOBILITY_DELAY",
    "TENSION_MOBILITY_NEAR",
    "TENSION_MOBILITY_THRESHOLD",
    "TENSION_SUSTAIN_MIN",
    "TENSION_SUSTAIN_VAR_CAP",
    "TENSION_TREND_OPP",
    "TENSION_TREND_SELF",
    "THRESHOLDS",
    "VOLATILITY_DROP_TOL",
    "WINNING_TAU_MAX",
    "WINNING_TAU_SCALE",
]
