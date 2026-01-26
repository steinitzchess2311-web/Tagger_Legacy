"""
Tension Creation Detector

This detector identifies moves that create tension through:
- Symmetrical mobility changes (opposite directions)
- Contact ratio changes
- Structural shifts
- Sustained mobility patterns

Extracted from legacy/core.py lines 256-264, 1750-1936.

A/B Testing:
- USE_SPLIT_TENSION_V2=0 (default): Legacy evidence gates (0.05 mobility, 0.005 contact)
- USE_SPLIT_TENSION_V2=1: Stricter boundary v2 (0.10 mobility, 0.01 contact)
"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

from rule_tagger2.detectors.base import DetectorMetadata, TagDetector
from rule_tagger2.orchestration.context import AnalysisContext

# Import thresholds from legacy config
from rule_tagger2.legacy.config import (
    CONTROL_PHASE_WEIGHTS,
    CONTROL_TENSION_DELTA,
    CONTROL_TENSION_DELTA_ENDGAME,
    NEUTRAL_TENSION_BAND,
    TENSION_EVAL_MAX,
    TENSION_EVAL_MIN,
    TENSION_SYMMETRY_TOL,
)
from rule_tagger2.legacy.thresholds import (
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
)
from rule_tagger2.models import TENSION_TRIGGER_PRIORITY


def _window_stats(deltas: List[Dict[str, float]], steps: int = 2) -> Tuple[float, float]:
    """
    Compute mean and variance of mobility changes over a window.

    Args:
        deltas: List of delta dictionaries containing 'mobility' key
        steps: Window size (default 2)

    Returns:
        Tuple of (mean, variance) of absolute mobility values
    """
    if len(deltas) < steps:
        return 0.0, 0.0
    window = deltas[:steps]
    values = [abs(entry["mobility"]) for entry in window]
    mean = sum(values) / len(values)
    variance = sum((val - mean) ** 2 for val in values) / len(values)
    return mean, variance


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


class TensionDetector(TagDetector):
    """
    Detects tension creation through mobility symmetry and contact changes.

    This detector looks for positions where both players' mobility changes
    in opposite directions, creating dynamic tension. It considers:
    - Eval band constraints
    - Mobility magnitude and symmetry
    - Contact ratio changes
    - Structural shifts
    - Sustained mobility patterns
    - Follow-up trends

    A/B Testing:
    Set USE_SPLIT_TENSION_V2=1 to enable stricter boundary v2 evidence gates.
    """

    def __init__(self):
        super().__init__()
        self._last_metadata: DetectorMetadata = DetectorMetadata(detector_name="TensionDetector")

        # A/B switch: Use stricter evidence gates when v2 is enabled
        self._use_v2_boundary = bool(int(os.getenv("USE_SPLIT_TENSION_V2", "0")))

        # Evidence gate thresholds (v2 vs legacy)
        if self._use_v2_boundary:
            self._min_mobility_evidence = 0.10  # v2: stricter gate
            self._min_contact_evidence = 0.01   # v2: stricter gate
        else:
            self._min_mobility_evidence = 0.05  # legacy: more permissive
            self._min_contact_evidence = 0.005  # legacy: more permissive

    @property
    def name(self) -> str:
        """Return detector name."""
        return "TensionDetector"

    def get_metadata(self) -> DetectorMetadata:
        """Return metadata from the most recent detection."""
        return self._last_metadata

    def detect(self, ctx: AnalysisContext) -> List[str]:
        """
        Detect tension creation tags.

        Args:
            ctx: Analysis context with position metrics

        Returns:
            List of tags: ["tension_creation"] or ["neutral_tension_creation"] or []
        """
        tags = []

        # Extract required metrics from context
        delta_eval_float = getattr(ctx, 'delta_eval_float', 0.0)
        delta_self_mobility = getattr(ctx, 'delta_self_mobility', 0.0)
        delta_opp_mobility = getattr(ctx, 'delta_opp_mobility', 0.0)
        contact_delta_played = getattr(ctx, 'contact_delta_played', 0.0)
        phase_ratio = getattr(ctx, 'phase_ratio', 0.0)
        structural_shift_signal = getattr(ctx, 'structural_shift_signal', False)
        contact_trigger_from_ctx = getattr(ctx, 'contact_trigger', False)  # May be pre-computed by legacy
        self_trend = getattr(ctx, 'self_trend', 0.0)
        opp_trend = getattr(ctx, 'opp_trend', 0.0)
        follow_self_deltas = getattr(ctx, 'follow_self_deltas', [])
        follow_opp_deltas = getattr(ctx, 'follow_opp_deltas', [])
        followup_tail_self = getattr(ctx, 'followup_tail_self', 0.0)
        structural_compromise_dynamic = getattr(ctx, 'structural_compromise_dynamic', False)
        risk_avoidance = getattr(ctx, 'risk_avoidance', False)
        file_pressure_c_flag = getattr(ctx, 'file_pressure_c_flag', False)

        # Get phase ratio if available from analysis_meta
        analysis_meta = getattr(ctx, 'analysis_meta', {})
        phase_ratio_current = analysis_meta.get("phase_ratio", phase_ratio)

        # Initialize tension support dict if not present
        if "tension_support" not in analysis_meta:
            analysis_meta["tension_support"] = {}

        # Step 1: Eval band check
        eval_band = TENSION_EVAL_MIN <= delta_eval_float <= TENSION_EVAL_MAX

        # Step 2: Mobility symmetry metrics
        self_mag = abs(delta_self_mobility)
        opp_mag = abs(delta_opp_mobility)
        mobility_cross = delta_self_mobility * delta_opp_mobility
        symmetry_gap = abs(self_mag - opp_mag)

        # Step 3: Phase-adjusted thresholds
        effective_threshold = TENSION_MOBILITY_THRESHOLD * (0.85 + 0.25 * phase_ratio_current)
        near_threshold = max(TENSION_MOBILITY_NEAR, effective_threshold * 0.75)
        symmetry_ok = symmetry_gap <= TENSION_SYMMETRY_TOL

        # Step 4: Contact metrics
        contact_jump = contact_delta_played
        contact_trigger_local = contact_jump >= TENSION_CONTACT_JUMP
        contact_direct = contact_jump >= TENSION_CONTACT_DIRECT
        contact_descriptor = f"contact {contact_jump:+.2f}"

        # Step 5: Sustained window analysis
        sustain_self_mean, sustain_self_var = _window_stats(follow_self_deltas)
        sustain_opp_mean, sustain_opp_var = _window_stats(follow_opp_deltas)
        sustained_window = (
            sustain_self_mean >= TENSION_SUSTAIN_MIN
            and sustain_opp_mean >= TENSION_SUSTAIN_MIN
            and sustain_self_var <= TENSION_SUSTAIN_VAR_CAP
            and sustain_opp_var <= TENSION_SUSTAIN_VAR_CAP
        )
        window_ok = sustained_window or contact_direct

        # Step 6: Core mobility criteria
        mobility_core = (
            self_mag >= effective_threshold
            and opp_mag >= effective_threshold
            and mobility_cross < 0
            and symmetry_ok
        )

        # Step 7: Structural mobility criteria
        mobility_struct = (
            self_mag >= near_threshold
            and opp_mag >= near_threshold
            and mobility_cross < 0
            and (structural_shift_signal or contact_trigger_local)
        )

        # Step 8: Sustained eval check
        sustained = (
            delta_eval_float > -0.6
            or self_trend >= 0
            or followup_tail_self >= 0
        )

        # Update analysis metadata
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

        # Step 9: Trigger detection - primary path
        trigger_sources: List[str] = []
        triggered = False
        contact_eval_ok = delta_eval_float <= -0.2 and mobility_cross < 0

        if eval_band and phase_ratio_current > 0.5 and window_ok and (mobility_core or mobility_struct or (contact_trigger_local and contact_eval_ok)):
            if delta_eval_float <= TENSION_EVAL_MIN and structural_compromise_dynamic:
                pass  # Skip if too negative eval with structural compromise
            elif delta_eval_float <= -0.6 and not sustained:
                pass  # Skip if deep negative eval without sustainability
            else:
                triggered = True
                if contact_trigger_local:
                    base_label = "contact_direct" if contact_direct else "contact_comp"
                    trigger_sources.append(base_label)
                if mobility_core:
                    trigger_sources.append("symmetry_core")
                if mobility_struct and not mobility_core:
                    trigger_sources.append("structural_support")

        alt_mobility_threshold = max(0.25, near_threshold * 0.65)
        if not triggered and eval_band and phase_ratio_current > 0.5:
            alt_condition = (
                self_mag >= alt_mobility_threshold
                and opp_mag >= alt_mobility_threshold
                and mobility_cross < 0
                and delta_eval_float >= -0.4
            )
            if alt_condition:
                triggered = True
                trigger_sources.append("alt_mobility")

        # Step 10: Delayed trigger path
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
            delayed_eval = delta_eval_float <= -0.2 or contact_trigger_local
            if delayed_contact and delayed_mag and delayed_trend and delayed_eval:
                triggered = True
                trigger_sources.append("delayed_trend")
                if contact_trigger_local:
                    base_label = "contact_direct" if contact_direct else "contact_comp"
                    trigger_sources.append(base_label)

        # Step 11: Sort trigger sources by priority
        unique_sources: List[str] = []
        for src in trigger_sources:
            if src not in unique_sources:
                unique_sources.append(src)
        ordered_sources = sorted(unique_sources, key=lambda name: TENSION_TRIGGER_PRIORITY.get(name, 999))

        # Step 12: Build notes if triggered
        notes = {}
        if triggered:
            note_parts = [
                f"tension creation: eval {delta_eval_float:+.2f}",
                f"mobility self {delta_self_mobility:+.2f}",
                f"opp {delta_opp_mobility:+.2f}",
            ]
            if contact_trigger_local:
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
            tags.append("tension_creation")

        analysis_meta["tension_support"]["trigger_sources"] = ordered_sources

        # Step 13: Neutral tension band check (ONLY as fallback when primary/delayed didn't trigger)
        # Match legacy logic exactly: lines 1802-1813 in core_v8.py
        neutral_band_active = abs(delta_eval_float) <= NEUTRAL_TENSION_BAND
        analysis_meta["tension_support"]["neutral_band"] = {
            "band_cp": NEUTRAL_TENSION_BAND,
            "delta_eval": round(delta_eval_float, 3),
            "active": neutral_band_active,
        }

        # Minimum evidence gate: require at least SOME mobility or contact change
        # to avoid firing on trivial/opening moves with no dynamic content
        # Thresholds adjust based on USE_SPLIT_TENSION_V2
        min_mobility_evidence = max(self_mag, opp_mag) >= self._min_mobility_evidence
        min_contact_evidence = abs(contact_jump) >= self._min_contact_evidence
        has_minimal_evidence = min_mobility_evidence or min_contact_evidence

        # Neutral fires when:
        # 1. Within neutral eval band AND
        # 2. NOT (tension_creation triggered OR contact_trigger OR structural_shift_signal) AND
        # 3. Has minimal evidence of dynamic change (mobility or contact)
        # This matches legacy core_v8.py line 1808 with added evidence gate
        # Use contact_trigger_from_ctx (legacy-computed) for consistency with legacy
        contact_trigger_for_neutral = contact_trigger_from_ctx or contact_trigger_local
        if neutral_band_active and not (triggered or contact_trigger_for_neutral or structural_shift_signal) and has_minimal_evidence:
            tags.append("neutral_tension_creation")
            notes.setdefault(
                "neutral_tension_creation",
                f"|Δeval| ≤ {NEUTRAL_TENSION_BAND:.2f}; mobility={max(self_mag, opp_mag):.2f}, contact={abs(contact_jump):.2f}",
            )

        # Store evidence check in metadata for debugging
        analysis_meta["tension_support"]["neutral_evidence"] = {
            "min_mobility_evidence": min_mobility_evidence,
            "min_contact_evidence": min_contact_evidence,
            "has_minimal_evidence": has_minimal_evidence,
            "v2_boundary_active": self._use_v2_boundary,
            "mobility_threshold": self._min_mobility_evidence,
            "contact_threshold": self._min_contact_evidence,
        }

        # Step 14: Risk avoidance override
        if risk_avoidance and not file_pressure_c_flag:
            if "tension_creation" in tags:
                tags.remove("tension_creation")
                notes.pop("tension_creation", None)
            analysis_meta["tension_support"]["trigger_sources"] = []

        # Store notes in context if available
        if hasattr(ctx, 'notes'):
            ctx.notes.update(notes)

        # Update metadata
        self._last_metadata = DetectorMetadata(
            detector_name="TensionDetector",
            tags_found=tags,
            diagnostic_info={
                "tension_support": analysis_meta.get("tension_support", {}),
                "notes": notes,
            }
        )

        return tags
