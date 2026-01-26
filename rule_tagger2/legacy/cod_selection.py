"""
Control over Dynamics v2 - CoD subtype selection logic.

Extracted from core.py to improve modularity.
Contains the select_cod_subtype function which orchestrates all CoD detectors
and applies priority, cooldown, and suppression logic.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from .cod_detectors import COD_DETECTORS
from .control_helpers import (
    _current_ply_index,
    _format_control_summary,
    _maybe_attach_control_context_snapshot,
    _normalize_phase_label,
    reason,
)
from .config import CONTROL_COOLDOWN_PLIES

# Import COD_SUBTYPES constant
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

def select_cod_subtype(
    ctx: Dict[str, Any],
    cfg: Dict[str, Any],
    last_state: Optional[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], List[str], int, Dict[str, Any], List[Dict[str, Any]]]:
    """Collect detector outputs, apply cooldown, and pick one subtype."""
    phase_name = ctx.get("phase")
    if phase_name == "END":
        priority = list(cfg.get("PRIORITY_END", cfg.get("PRIORITY", COD_SUBTYPES)))
    else:
        priority = list(cfg.get("PRIORITY", COD_SUBTYPES))

    def _gate_compact_score(gate: Dict[str, Any]) -> float:
        if not isinstance(gate, dict):
            return 0.0
        score = 0.0
        if "env_ok" in gate:
            score += 1.0 if gate.get("env_ok") else 0.0
        else:
            vol_value = gate.get("volatility_drop_cp")
            vol_threshold = gate.get("volatility_threshold")
            if vol_value is not None and vol_threshold is not None and vol_value >= vol_threshold:
                score += 1.0
        if "mobility_ok" in gate:
            score += 1.0 if gate.get("mobility_ok") else 0.0
        else:
            mob_value = gate.get("opp_mobility_drop", gate.get("mobility_drop"))
            mob_threshold = gate.get("mobility_threshold")
            if mob_value is not None and mob_threshold is not None and mob_value >= mob_threshold:
                score += 1.0
        if "t_ok" in gate:
            score += 1.0 if gate.get("t_ok") else 0.0
        elif "tension_ok" in gate:
            score += 1.0 if gate.get("tension_ok") else 0.0
        else:
            tension_delta = gate.get("tension_delta")
            tension_threshold = gate.get("tension_threshold")
            if tension_delta is not None and tension_threshold is not None and tension_delta <= tension_threshold:
                score += 1.0
        return score
    gate_log: Dict[str, Any] = {}
    detected: List[Dict[str, Any]] = []
    for subtype in priority:
        detector = COD_DETECTORS.get(subtype)
        if detector is None:
            continue
        candidate, gate = detector(ctx, cfg)
        if gate:
            gate_log[subtype] = gate
        if candidate:
            detected.append(candidate)
    cooldown_plies = int(cfg.get("COOLDOWN_PLIES", CONTROL_COOLDOWN_PLIES))
    current_ply = ctx.get("current_ply")
    cooldown_remaining = 0
    removed_by_cooldown: List[str] = []
    if last_state:
        last_kind = last_state.get("kind")
        last_ply = last_state.get("ply")
        if (
            last_kind
            and isinstance(last_ply, int)
            and isinstance(current_ply, int)
        ):
            diff = current_ply - last_ply
            if diff <= cooldown_plies:
                cooldown_remaining = max(0, cooldown_plies - diff)
                if detected:
                    remaining: List[Dict[str, Any]] = []
                    for cand in detected:
                        if cand["name"] == last_kind:
                            if last_kind not in removed_by_cooldown:
                                removed_by_cooldown.append(last_kind)
                        else:
                            remaining.append(cand)
                    detected = remaining
    index_map = {name: idx for idx, name in enumerate(priority)}
    detected.sort(key=lambda item: (index_map.get(item["name"], 999), -item.get("score", 0.0)))
    if not detected:
        suppressed = list(removed_by_cooldown)
        return None, suppressed, cooldown_remaining, gate_log, []
    rare_types: Set[str] = set(cfg.get("RARE_TYPES", []))
    phase_weights_cfg = cfg.get("PHASE_WEIGHTS", {})
    phase_key = phase_name if isinstance(phase_name, str) else ctx.get("phase")
    phase_weights = phase_weights_cfg.get(phase_key, {})
    tie_delta = float(cfg.get("TIE_BREAK_DELTA", 0.0))
    eval_info: List[Dict[str, Any]] = []
    for idx, candidate in enumerate(detected):
        name = candidate.get("name")
        priority_rank = index_map.get(name, len(priority))
        phase_weight = float(phase_weights.get(name, 0.0)) if isinstance(phase_weights, dict) else 0.0
        gate_score = _gate_compact_score(candidate.get("gate", {}))
        composite = float(priority_rank) - phase_weight - gate_score
        eval_info.append(
            {
                "index": idx,
                "candidate": candidate,
                "name": name,
                "priority_rank": priority_rank,
                "phase_weight": phase_weight,
                "gate_score": gate_score,
                "composite": composite,
                "is_rare": name in rare_types,
            }
        )
    selected_index = 0
    best_entry = eval_info[0]
    rare_candidates = [info for info in eval_info if info["is_rare"]]
    if rare_candidates and not best_entry["is_rare"]:
        rare_best = min(rare_candidates, key=lambda info: info["composite"])
        gate_gap = abs(best_entry["gate_score"] - rare_best["gate_score"])
        if (
            rare_best["phase_weight"] > 0.0
            and gate_gap <= 1.0
            and rare_best["composite"] <= best_entry["composite"] + tie_delta
        ):
            selected_index = rare_best["index"]
            if selected_index != 0:
                selected_candidate = detected.pop(selected_index)
                detected.insert(0, selected_candidate)
                selected_index = 0
    selected = detected[selected_index]
    suppressed = [entry["name"] for idx, entry in enumerate(detected) if idx != selected_index]
    for name in removed_by_cooldown:
        if name not in suppressed:
            suppressed.append(name)
    return selected, suppressed, cooldown_remaining, gate_log, detected


# ===================== 标签判定主函数 =====================

