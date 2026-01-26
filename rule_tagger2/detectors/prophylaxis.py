"""
Prophylaxis & Control over Dynamics Detector

This detector identifies preventive moves and control-oriented play through 9 subtypes:
1. simplify - Simplification through exchanges
2. plan_kill - Plan disruption/prevention
3. freeze_bind - Structure lock and mobility freeze
4. blockade_passed - Blockade opponent's passed pawns
5. file_seal - Seal files, reduce line pressure
6. king_safety_shell - King safety improvement
7. space_clamp - Space advantage with mobility restriction
8. regroup_consolidate - Regroup pieces, consolidate position
9. slowdown - Dampen dynamics

Extracted from legacy/core.py lines 554-1067.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from rule_tagger2.detectors.base import DetectorMetadata, TagDetector
from rule_tagger2.orchestration.context import AnalysisContext

# Import thresholds from legacy config and core
from rule_tagger2.legacy.config import (
    CONTROL_COOLDOWN_PLIES,
    CONTROL_DEFAULTS,
    CONTROL_EVAL_DROP,
    CONTROL_OPP_MOBILITY_DROP,
    CONTROL_PHASE_WEIGHTS,
    CONTROL_SIMPLIFY_MIN_EXCHANGE,
    CONTROL_TENSION_DELTA,
    CONTROL_TENSION_DELTA_ENDGAME,
    CONTROL_VOLATILITY_DROP_CP,
)

# Import prophylaxis-specific constants from legacy core
from rule_tagger2.legacy.core import (
    PROPHYLAXIS_PREVENTIVE_TRIGGER,
    PROPHYLAXIS_THREAT_DROP,
)


# COD Subtype priority order (from legacy config)
COD_SUBTYPES = [
    "simplify",
    "plan_kill",
    "freeze_bind",
    "blockade_passed",
    "file_seal",
    "king_safety_shell",
    "space_clamp",
    "regroup_consolidate",
    "slowdown",
]

STRICT_MODE_VOL_DELTA = 33.0
STRICT_MODE_MOB_DELTA = 2.0


def _control_tension_threshold(phase_bucket: str) -> float:
    """
    Compute phase-dependent tension threshold.

    Args:
        phase_bucket: One of "opening", "middlegame", "endgame"

    Returns:
        Phase-adjusted tension threshold
    """
    weight = CONTROL_PHASE_WEIGHTS.get(phase_bucket, 1.0)
    base = CONTROL_TENSION_DELTA * weight
    if phase_bucket == "endgame":
        base = min(base, CONTROL_TENSION_DELTA_ENDGAME)
    return base


def _phase_bonus(ctx: AnalysisContext, cfg: Dict[str, Any]) -> Dict[str, float]:
    """
    Compute phase-based threshold bonuses for strict mode.

    Returns:
        Dict with VOL_BONUS and OP_MOB_DROP adjustments
    """
    phase_bucket = ctx.phase_bucket
    vol_base = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP)
    mob_base = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)

    strict_mode = ctx.metadata.get("strict_mode", False)

    vol_bonus = 0.0
    mob_bonus = 0.0

    if strict_mode and phase_bucket == "middlegame":
        if vol_base < CONTROL_VOLATILITY_DROP_CP + STRICT_MODE_VOL_DELTA:
            vol_bonus = STRICT_MODE_VOL_DELTA
        if mob_base < CONTROL_OPP_MOBILITY_DROP + STRICT_MODE_MOB_DELTA:
            mob_bonus = STRICT_MODE_MOB_DELTA

    return {
        "VOL_BONUS": vol_bonus,
        "OP_MOB_DROP": mob_bonus,
    }


class ProphylaxisDetector(TagDetector):
    """
    Detects prophylactic moves and control-oriented play.

    This detector implements 9 COD (Control over Dynamics) subtypes,
    each checking different preventive patterns. It uses cooldown
    to avoid over-tagging the same subtype repeatedly.
    """

    def __init__(self):
        self._metadata = DetectorMetadata(detector_name="Prophylaxis")
        self._last_detection: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "Prophylaxis"

    def detect(self, ctx: AnalysisContext) -> List[str]:
        """
        Detect prophylaxis/control tags.

        Returns list of tags like:
        - "control_over_dynamics" (generic)
        - "control_over_dynamics:simplify"
        - "control_over_dynamics:plan_kill"
        etc.
        """
        # Reset metadata
        self._metadata.tags_found = []
        self._metadata.diagnostic_info = {}

        # Build config dict from context
        cfg = self._build_config(ctx)

        # Get last state for cooldown
        last_state = ctx.metadata.get("last_cod_state")

        # Run COD detector pipeline
        selected, suppressed, cooldown_remaining, gate_log, all_detected = self._select_cod_subtype(
            ctx, cfg, last_state
        )

        # Store diagnostic info
        self._metadata.diagnostic_info = {
            "gate_log": gate_log,
            "all_detected": [d["name"] for d in all_detected],
            "suppressed": suppressed,
            "cooldown_remaining": cooldown_remaining,
        }

        tags = []

        if selected:
            # Add generic tag
            tags.append("control_over_dynamics")

            # Add specific subtype tag
            subtype_name = selected["name"]
            tags.append(f"control_over_dynamics:{subtype_name}")

            # Store state for next detection (cooldown tracking)
            current_ply = ctx.metadata.get("current_ply", 0)
            ctx.metadata["last_cod_state"] = {
                "kind": subtype_name,
                "ply": current_ply,
            }

            # Store notes
            if "why" in selected:
                if "prophylaxis_notes" not in ctx.metadata:
                    ctx.metadata["prophylaxis_notes"] = []
                ctx.metadata["prophylaxis_notes"].append(selected["why"])

        self._metadata.tags_found = tags
        return tags

    def get_metadata(self) -> DetectorMetadata:
        return self._metadata

    def _build_config(self, ctx: AnalysisContext) -> Dict[str, Any]:
        """Build configuration dict from context (matching legacy interface)."""
        return ctx.metadata.get("control_cfg", CONTROL_DEFAULTS.copy())

    def _select_cod_subtype(
        self,
        ctx: AnalysisContext,
        cfg: Dict[str, Any],
        last_state: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], List[str], int, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Collect detector outputs, apply cooldown, and pick one subtype.

        Returns:
            (selected_candidate, suppressed_names, cooldown_remaining, gate_log, all_detected)
        """
        priority = COD_SUBTYPES
        gate_log: Dict[str, Any] = {}
        detected: List[Dict[str, Any]] = []

        # Run all 9 COD detectors
        for subtype in priority:
            candidate, gate = self._run_cod_detector(subtype, ctx, cfg)
            if gate:
                gate_log[subtype] = gate
            if candidate:
                detected.append(candidate)

        # Apply cooldown
        cooldown_plies = int(cfg.get("COOLDOWN_PLIES", CONTROL_COOLDOWN_PLIES))
        current_ply = ctx.metadata.get("current_ply", 0)
        cooldown_remaining = 0
        removed_by_cooldown: Set[str] = set()

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
                    before = len(detected)
                    detected = [cand for cand in detected if cand["name"] != last_kind]
                    if len(detected) != before:
                        removed_by_cooldown.add(last_kind)

        # Sort by priority and score
        index_map = {name: idx for idx, name in enumerate(priority)}
        detected.sort(key=lambda item: (index_map.get(item["name"], 999), -item.get("score", 0.0)))

        if not detected:
            suppressed = list(removed_by_cooldown)
            return None, suppressed, cooldown_remaining, gate_log, []

        selected = detected[0]
        suppressed = [entry["name"] for entry in detected[1:]]
        for name in removed_by_cooldown:
            if name not in suppressed:
                suppressed.append(name)

        supported, signal_details = self._control_signal_status(ctx)
        if not supported:
            gate_log["control_signal"] = {
                "passed": False,
                **signal_details,
            }
            if selected["name"] not in suppressed:
                suppressed.append(selected["name"])
            return None, suppressed, cooldown_remaining, gate_log, detected

        return selected, suppressed, cooldown_remaining, gate_log, detected

    def _control_signal_status(
        self,
        ctx: AnalysisContext,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate whether follow-up + eval info confirms control intent."""
        eval_delta = getattr(ctx, "delta_eval_float", 0.0)
        followup = ctx.metadata.get("followup", {}) or {}
        opp_deltas = followup.get("opp_deltas") or []
        opp_trend = followup.get("opp_trend", 0.0)
        tension_support = ctx.metadata.get("tension_support", {}) or {}
        tension_active = bool(tension_support.get("trigger_sources"))
        control_ctx = ctx.metadata.get("control_dynamics", {}) or {}
        context = control_ctx.get("context", {}) or {}
        tension_delta = context.get("tension_delta", 0.0)
        opp_mobility_drop = context.get("opp_mobility_drop", 0.0)

        future_mobility_signal = (
            (len(opp_deltas) > 0 and opp_trend <= 0.0)
            or opp_mobility_drop >= 0.1
            or tension_delta <= 0.0
        )
        passed = eval_delta >= -0.2 and (future_mobility_signal or tension_active)
        details: Dict[str, Any] = {
            "delta_eval": round(eval_delta, 3),
            "opp_trend": round(opp_trend, 3),
            "opp_mobility_drop": round(opp_mobility_drop, 3),
            "future_signal": future_mobility_signal,
            "tension_active": tension_active,
        }
        return passed, details

    def _run_cod_detector(
        self, subtype: str, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Dispatch to specific COD detector."""
        detectors = {
            "simplify": self._detect_simplify,
            "plan_kill": self._detect_plan_kill,
            "freeze_bind": self._detect_freeze_bind,
            "blockade_passed": self._detect_blockade_passed,
            "file_seal": self._detect_file_seal,
            "king_safety_shell": self._detect_king_safety_shell,
            "space_clamp": self._detect_space_clamp,
            "regroup_consolidate": self._detect_regroup_consolidate,
            "slowdown": self._detect_slowdown,
        }

        detector_func = detectors.get(subtype)
        if detector_func is None:
            return None, {}

        return detector_func(ctx, cfg)

    def _get_field(self, ctx: AnalysisContext, key: str, default: Any = 0.0) -> Any:
        """Helper to get field from context with fallback to metadata."""
        # Try direct attribute access first
        if hasattr(ctx, key):
            return getattr(ctx, key)
        # Fall back to metadata dict
        return ctx.metadata.get(key, default)

    # ========== 9 COD Detector Implementations ==========

    def _detect_simplify(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Detect simplification through exchanges."""
        phase_adjust = _phase_bonus(ctx, cfg)
        vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + phase_adjust["VOL_BONUS"]
        tension_threshold = cfg.get("TENSION_DEC_MIN", CONTROL_TENSION_DELTA)
        mobility_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)

        strict_mode = bool(self._get_field(ctx, "strict_mode"))
        captures_this_ply = self._get_field(ctx, "captures_this_ply", 0)
        square_defended_by_opp = self._get_field(ctx, "square_defended_by_opp", 0)
        has_followup = self._get_field(ctx, "has_immediate_tactical_followup", False)

        expected_recapture_pairs = (
            1 if self._get_field(ctx, "is_capture", False) and square_defended_by_opp >= 1 and not has_followup else 0
        )

        total_active_drop = self._get_field(ctx, "total_active_drop")
        if total_active_drop is None:
            own_drop = self._get_field(ctx, "own_active_drop", 0)
            opp_drop = self._get_field(ctx, "opp_active_drop", 0)
            total_active_drop = max(0, (own_drop or 0)) + max(0, (opp_drop or 0))

        exchange_pairs = min(2, captures_this_ply + expected_recapture_pairs)
        exchange_count = self._get_field(ctx, "exchange_count", 0)

        transaction_ok = (
            exchange_pairs >= 1
            or exchange_count >= 1
            or (total_active_drop or 0) >= 1
        )

        if strict_mode and exchange_pairs < max(2, cfg.get("SIMPLIFY_MIN_EXCHANGE", CONTROL_SIMPLIFY_MIN_EXCHANGE)) and exchange_count < 1:
            transaction_ok = False

        volatility_drop = self._get_field(ctx, "volatility_drop_cp", 0.0)
        tension_delta = self._get_field(ctx, "tension_delta", 0.0)
        opp_mobility_drop = self._get_field(ctx, "opp_mobility_drop", 0.0)

        env_ok = (
            volatility_drop >= vol_threshold
            and tension_delta <= tension_threshold
            and opp_mobility_drop >= mobility_threshold * 0.8
        )

        material_delta_self_cp = self._get_field(ctx, "material_delta_self_cp")
        if material_delta_self_cp is None:
            material_delta_self_cp = int(round(self._get_field(ctx, "material_delta_self", 0.0) * 100))

        captured_value_cp = self._get_field(ctx, "captured_value_cp", 0)
        if expected_recapture_pairs:
            window_cp = max(30, int(round(captured_value_cp * 1.1)))
        else:
            window_cp = 30

        material_ok = abs(material_delta_self_cp or 0) <= window_cp

        gate = {
            "subtype": "simplify",
            "passed": env_ok and transaction_ok and material_ok,
        }

        if not gate["passed"]:
            return None, gate

        metrics = {
            "volatility_drop_cp": volatility_drop,
            "opp_mobility_drop": opp_mobility_drop,
            "tension_delta": tension_delta,
            "exchange_pairs": exchange_pairs,
        }

        score = (
            volatility_drop
            + max(0, opp_mobility_drop) * 10
            + exchange_pairs * 40
            - abs(tension_delta) * 2
        )

        why = f"simplify via exchange (pairs={exchange_pairs}), vol={volatility_drop:.1f}cp, tensionΔ={tension_delta:+.1f}"

        return {
            "name": "simplify",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_plan_kill(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Detect plan disruption/prevention."""
        preventive_score = self._get_field(ctx, "preventive_score", 0.0)
        threat_delta = self._get_field(ctx, "threat_delta", 0.0)
        plan_drop = bool(self._get_field(ctx, "plan_drop_passed"))
        mobility_drop = self._get_field(ctx, "opp_mobility_drop", 0.0)
        volatility_drop = self._get_field(ctx, "volatility_drop_cp", 0.0)

        gate = {"subtype": "plan_kill"}

        trigger = PROPHYLAXIS_PREVENTIVE_TRIGGER
        passed = plan_drop or (
            self._get_field(ctx, "allow_positional", False)
            and preventive_score >= trigger
            and (
                threat_delta >= PROPHYLAXIS_THREAT_DROP
                or mobility_drop >= cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
                or volatility_drop >= cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) * 0.75
            )
        )

        gate["passed"] = passed

        if not passed:
            return None, gate

        source = "plan drop" if plan_drop else "preventive squeeze"
        why = f"{source} killed opponent plan (preventive={preventive_score:+.2f}, threatΔ={threat_delta:+.2f})"

        metrics = {
            "preventive_score": preventive_score,
            "threat_delta": threat_delta,
            "opp_mobility_drop": mobility_drop,
        }

        score = preventive_score * 120 + max(mobility_drop, 0.0) * 20 + (10 if plan_drop else 0)

        return {
            "name": "plan_kill",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_freeze_bind(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Lock structure and freeze opponent mobility."""
        structure_gain = self._get_field(ctx, "structure_gain", 0.0)
        opp_mob_eval = self._get_field(ctx, "opp_mobility_change_eval", 0.0)
        tension_delta = self._get_field(ctx, "tension_delta", 0.0)
        phase_bucket = ctx.phase_bucket
        threshold = _control_tension_threshold(phase_bucket)

        gate = {"subtype": "freeze_bind"}

        passed = (
            self._get_field(ctx, "allow_positional", False)
            and structure_gain >= 0.18
            and opp_mob_eval <= -0.18
            and tension_delta <= threshold - 0.2
        )

        gate["passed"] = passed

        if not passed:
            return None, gate

        metrics = {
            "structure_gain": structure_gain,
            "opp_mobility_drop": self._get_field(ctx, "opp_mobility_drop", 0.0),
            "tension_delta": tension_delta,
        }

        why = f"locked structure (+{structure_gain:.2f}) and froze opp mobility ({opp_mob_eval:+.2f})"
        score = structure_gain * 80 + abs(opp_mob_eval) * 60

        return {
            "name": "freeze_bind",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_blockade_passed(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Blockade opponent's passed pawns."""
        opp_passed_exists = self._get_field(ctx, "opp_passed_exists", False)
        blockade_established = self._get_field(ctx, "blockade_established", False)
        push_drop = self._get_field(ctx, "opp_passed_push_drop", 0.0)
        min_drop = max(1.0, float(cfg.get("PASSED_PUSH_MIN", CONTROL_DEFAULTS["PASSED_PUSH_MIN"])))

        gate = {"subtype": "blockade_passed"}
        passed = opp_passed_exists and blockade_established and push_drop >= min_drop
        gate["passed"] = passed

        if not passed:
            return None, gate

        metrics = {
            "opp_passed_push_drop": push_drop,
            "blockade_file": self._get_field(ctx, "blockade_file"),
        }

        file_label = self._get_field(ctx, "blockade_file") or ""
        why = f"blockaded passed pawn{(' on ' + file_label) if file_label else ''}"
        score = push_drop * 50

        return {
            "name": "blockade_passed",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_file_seal(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Seal files, reduce opponent line pressure."""
        pressure_drop = self._get_field(ctx, "opp_line_pressure_drop", 0.0)
        break_delta = self._get_field(ctx, "break_candidates_delta", 0.0)
        mobility_drop = self._get_field(ctx, "opp_mobility_drop", 0.0)
        vol_drop = self._get_field(ctx, "volatility_drop_cp", 0.0)
        line_min = float(cfg.get("LINE_MIN", CONTROL_DEFAULTS["LINE_MIN"]))

        gate = {"subtype": "file_seal"}

        passed = (
            pressure_drop >= line_min
            or break_delta <= -1.0
        )
        passed = passed and vol_drop >= cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) * 0.5

        gate["passed"] = passed

        if not passed:
            return None, gate

        metrics = {
            "opp_line_pressure_drop": pressure_drop,
            "break_candidates_delta": break_delta,
        }

        why = f"sealed files (pressureΔ={pressure_drop:+.1f}, breakΔ={break_delta:+.0f})"
        score = pressure_drop * 40 + abs(min(break_delta, 0)) * 30

        return {
            "name": "file_seal",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_king_safety_shell(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Improve king safety, reduce opponent tactics."""
        ks_gain = self._get_field(ctx, "king_safety_gain", 0.0)
        opp_tactics = self._get_field(ctx, "opp_tactics_change_eval", 0.0)
        mobility_drop = self._get_field(ctx, "opp_mobility_drop", 0.0)
        self_mobility_change = self._get_field(ctx, "self_mobility_change", 0.0)
        threshold = float(cfg.get("KS_MIN", CONTROL_DEFAULTS["KS_MIN"])) / 100.0

        gate = {"subtype": "king_safety_shell"}

        passed = (
            ks_gain >= threshold
            and (
                opp_tactics <= -0.1
                or mobility_drop >= cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP)
                or (opp_tactics <= 0.0 and self_mobility_change >= -0.1)
            )
        )

        gate["passed"] = passed

        if not passed:
            return None, gate

        metrics = {
            "king_safety_gain": ks_gain,
            "opp_tactics_change_eval": opp_tactics,
        }

        why = f"king shelter improved {ks_gain:+.2f}, opp tactics {opp_tactics:+.2f}"
        score = ks_gain * 100 + abs(min(opp_tactics, 0.0)) * 40

        return {
            "name": "king_safety_shell",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_space_clamp(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Space advantage with mobility restriction."""
        space_gain = self._get_field(ctx, "space_gain", 0.0)
        mobility_drop = self._get_field(ctx, "opp_mobility_drop", 0.0)
        tension_delta = self._get_field(ctx, "tension_delta", 0.0)
        space_threshold = float(cfg.get("SPACE_MIN", CONTROL_DEFAULTS["SPACE_MIN"])) / 10.0

        gate = {"subtype": "space_clamp"}

        passed = (
            self._get_field(ctx, "allow_positional", False)
            and space_gain >= space_threshold
            and mobility_drop >= cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP) * 0.6
            and tension_delta <= 0.0
        )

        gate["passed"] = passed

        if not passed:
            return None, gate

        metrics = {
            "space_gain": space_gain,
            "opp_mobility_drop": mobility_drop,
        }

        why = f"space clamp {space_gain:+.2f} with opp mobility drop {mobility_drop:+.1f}"
        score = space_gain * 90 + mobility_drop * 10

        return {
            "name": "space_clamp",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_regroup_consolidate(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Regroup pieces, consolidate position."""
        ks_gain = self._get_field(ctx, "king_safety_gain", 0.0)
        structure_gain = self._get_field(ctx, "structure_gain", 0.0)
        self_mobility_change = self._get_field(ctx, "self_mobility_change", 0.0)
        vol_drop = self._get_field(ctx, "volatility_drop_cp", 0.0)

        gate = {"subtype": "regroup_consolidate"}

        passed = (
            self._get_field(ctx, "allow_positional", False)
            and vol_drop >= cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) * 0.6
            and self_mobility_change <= 0.05
            and (ks_gain >= 0.05 or structure_gain >= 0.1)
        )

        gate["passed"] = passed

        if not passed:
            return None, gate

        metrics = {
            "king_safety_gain": ks_gain,
            "structure_gain": structure_gain,
        }

        why = f"regrouped to consolidate safety ({ks_gain:+.2f}) and structure ({structure_gain:+.2f})"
        score = vol_drop + ks_gain * 80 + structure_gain * 60

        return {
            "name": "regroup_consolidate",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate

    def _detect_slowdown(
        self, ctx: AnalysisContext, cfg: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Dampen dynamics when dynamics available."""
        if not self._get_field(ctx, "allow_positional", False):
            return None, {}

        has_dynamic = self._get_field(ctx, "has_dynamic_in_band", False)
        played_kind = self._get_field(ctx, "played_kind")
        eval_drop_cp = self._get_field(ctx, "eval_drop_cp", 0)

        phase_adjust = _phase_bonus(ctx, cfg)
        vol_threshold = cfg.get("VOLATILITY_DROP_CP", CONTROL_VOLATILITY_DROP_CP) + phase_adjust["VOL_BONUS"]
        mob_threshold = cfg.get("OP_MOBILITY_DROP", CONTROL_OPP_MOBILITY_DROP) + phase_adjust["OP_MOB_DROP"]

        phase_bucket = ctx.phase_bucket
        tension_threshold = _control_tension_threshold(phase_bucket)

        tension_delta = self._get_field(ctx, "tension_delta", 0.0)
        opp_mobility_drop = self._get_field(ctx, "opp_mobility_drop", 0.0)
        volatility_drop = self._get_field(ctx, "volatility_drop_cp", 0.0)

        gate = {"subtype": "slowdown"}

        passed = (
            has_dynamic
            and played_kind == "positional"
            and eval_drop_cp <= cfg.get("EVAL_DROP_CP", CONTROL_EVAL_DROP)
            and volatility_drop >= vol_threshold
            and tension_delta <= tension_threshold
            and opp_mobility_drop >= mob_threshold
        )

        gate["passed"] = passed

        if not passed:
            return None, gate

        metrics = {
            "eval_drop_cp": eval_drop_cp,
            "volatility_drop_cp": volatility_drop,
            "tension_delta": tension_delta,
            "opp_mobility_drop": opp_mobility_drop,
        }

        why = f"slowdown dampened dynamics (vol={volatility_drop:.1f}cp, opp mobility={opp_mobility_drop:+.0f})"
        score = volatility_drop + opp_mobility_drop * 5

        return {
            "name": "slowdown",
            "metrics": metrics,
            "why": why,
            "score": score,
            "gate": gate,
        }, gate
