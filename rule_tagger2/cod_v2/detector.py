"""
Control over Dynamics v2 Detector.

This detector implements a refined version of CoD detection with:
1. Clear subtype classification (prophylaxis, piece control, pawn control, simplification)
2. Detailed diagnostic output
3. Gate checks with evidence trails
4. Threshold transparency

IMPORTANT: This is a NEW implementation, not a modification of legacy code.
"""
from typing import List, Tuple

from .config import get_thresholds
from .cod_types import CoDContext, CoDMetrics, CoDResult, CoDSubtype


class ControlOverDynamicsV2Detector:
    """
    Control over Dynamics v2 Detector.

    Detects moves that control game dynamics through:
    - Prophylaxis: Preventing opponent plans
    - Piece control: Restricting opponent mobility via piece activity
    - Pawn control: Restricting opponent mobility via pawn structure
    - Simplification: Reducing complexity via exchanges
    """

    def __init__(self):
        """Initialize detector with thresholds."""
        self.thresholds = get_thresholds()
        self.name = "ControlOverDynamicsV2"
        self.version = "2.0.0-alpha"

    def detect(self, context: CoDContext) -> CoDResult:
        """
        Detect Control over Dynamics in the given context.

        Args:
            context: CoDContext with position and metrics

        Returns:
            CoDResult with detection outcome and diagnostics
        """
        # Step 1: Gate checks (tactical weight, mate threat, blunder)
        gates_result = self._check_gates(context)
        if not gates_result[0]:
            return CoDResult(
                detected=False,
                subtype=CoDSubtype.NONE,
                gates_passed={"tactical_gate": False},
                gates_failed=gates_result[1],
                diagnostic={"reason": "failed_gates", "details": gates_result[1]},
                thresholds_used=self.thresholds.to_dict(),
            )

        # Step 2: Cooldown check
        if self._is_in_cooldown(context):
            return CoDResult(
                detected=False,
                subtype=CoDSubtype.NONE,
                gates_passed={"tactical_gate": True, "cooldown_gate": False},
                gates_failed=["cooldown"],
                diagnostic={
                    "reason": "cooldown",
                    "current_ply": context.current_ply,
                    "last_ply": context.last_cod_ply,
                },
                thresholds_used=self.thresholds.to_dict(),
            )

        # Step 3: Try each subtype in priority order
        candidates = []

        # 3a. Prophylaxis (highest priority)
        proph_result = self._detect_prophylaxis(context)
        if proph_result.detected:
            candidates.append(("prophylaxis", proph_result))

        # 3b. Piece control
        piece_result = self._detect_piece_control(context)
        if piece_result.detected:
            candidates.append(("piece_control", piece_result))

        # 3c. Pawn control
        pawn_result = self._detect_pawn_control(context)
        if pawn_result.detected:
            candidates.append(("pawn_control", pawn_result))

        # 3d. Simplification
        simpl_result = self._detect_simplification(context)
        if simpl_result.detected:
            candidates.append(("simplification", simpl_result))

        # Step 4: Select best candidate
        if not candidates:
            return CoDResult.no_detection()

        # Use priority order (already sorted)
        selected_name, selected_result = candidates[0]

        # Add metadata
        selected_result.diagnostic["all_candidates"] = [name for name, _ in candidates]
        selected_result.diagnostic["selected"] = selected_name
        selected_result.thresholds_used = self.thresholds.to_dict()
        selected_result.gates_passed = {"tactical_gate": True, "cooldown_gate": True}

        return selected_result

    def _check_gates(self, context: CoDContext) -> Tuple[bool, List[str]]:
        """
        Check tactical gates.

        Returns:
            (passed, list_of_failed_gates)
        """
        failed = []

        # Gate 1: Tactical weight ceiling
        if context.tactical_weight > self.thresholds.tactical_weight_ceiling:
            failed.append(
                f"tactical_weight={context.tactical_weight:.2f} > {self.thresholds.tactical_weight_ceiling}"
            )

        # Gate 2: Mate threat
        if context.mate_threat and self.thresholds.mate_threat_gate:
            failed.append("mate_threat=True")

        # Gate 3: Blunder threat
        if context.blunder_threat_drop >= self.thresholds.blunder_threat_thresh:
            failed.append(
                f"blunder_threat={context.blunder_threat_drop:.2f} >= {self.thresholds.blunder_threat_thresh}"
            )

        return (len(failed) == 0, failed)

    def _is_in_cooldown(self, context: CoDContext) -> bool:
        """Check if we're in cooldown period."""
        if context.last_cod_ply is None:
            return False

        ply_diff = context.current_ply - context.last_cod_ply
        return ply_diff <= self.thresholds.cooldown_plies

    def _detect_prophylaxis(self, context: CoDContext) -> CoDResult:
        """
        Detect prophylactic moves.

        Criteria:
        - Volatility drop >= threshold OR
        - Opponent mobility drop >= threshold OR
        - Tension delta <= threshold (negative)
        - Preventive score above trigger
        """
        m = context.metrics
        t = self.thresholds

        evidence = {
            "volatility_drop_cp": m.volatility_drop_cp,
            "opp_mobility_drop": m.opp_mobility_drop,
            "tension_delta": m.tension_delta,
            "preventive_score": m.preventive_score,
            "threat_delta": m.threat_delta,
        }

        # Tension threshold varies by phase
        tension_threshold = (
            t.tension_delta_end
            if context.phase_bucket == "endgame"
            else t.tension_delta_mid
        )

        # Check criteria
        volatility_check = m.volatility_drop_cp >= t.volatility_drop_cp
        mobility_check = m.opp_mobility_drop >= t.opp_mobility_drop
        tension_check = m.tension_delta <= tension_threshold
        preventive_check = m.preventive_score >= t.preventive_trigger

        any_signal = volatility_check or mobility_check or tension_check

        if not any_signal:
            return CoDResult(
                detected=False,
                subtype=CoDSubtype.PROPHYLAXIS,
                evidence=evidence,
                diagnostic={
                    "volatility_check": volatility_check,
                    "mobility_check": mobility_check,
                    "tension_check": tension_check,
                    "preventive_check": preventive_check,
                },
            )

        # Compute confidence
        confidence = 0.0
        if volatility_check:
            confidence += 0.4
        if mobility_check:
            confidence += 0.35
        if tension_check:
            confidence += 0.25
        if preventive_check:
            confidence += 0.3

        confidence = min(1.0, confidence)

        return CoDResult(
            detected=True,
            subtype=CoDSubtype.PROPHYLAXIS,
            confidence=confidence,
            tags=["control_over_dynamics", "cod_prophylaxis"],
            evidence=evidence,
            diagnostic={
                "volatility_check": volatility_check,
                "mobility_check": mobility_check,
                "tension_check": tension_check,
                "preventive_check": preventive_check,
                "tension_threshold": tension_threshold,
            },
        )

    def _detect_piece_control(self, context: CoDContext) -> CoDResult:
        """
        Detect piece control over dynamics.

        Criteria:
        - Opponent mobility drop >= threshold
        - Volatility drop >= threshold
        - Self mobility not too negative
        """
        m = context.metrics
        t = self.thresholds

        evidence = {
            "opp_mobility_drop": m.opp_mobility_drop,
            "volatility_drop_cp": m.volatility_drop_cp,
            "self_mobility_change": m.self_mobility_change,
        }

        mobility_check = m.opp_mobility_drop >= t.opp_mobility_drop
        volatility_check = m.volatility_drop_cp >= t.volatility_drop_cp * 0.8
        self_not_worse = m.self_mobility_change >= -0.1

        if not (mobility_check and volatility_check and self_not_worse):
            return CoDResult(
                detected=False,
                subtype=CoDSubtype.PIECE_CONTROL,
                evidence=evidence,
                diagnostic={
                    "mobility_check": mobility_check,
                    "volatility_check": volatility_check,
                    "self_not_worse": self_not_worse,
                },
            )

        confidence = 0.6 + (m.opp_mobility_drop / 0.3) * 0.3
        confidence = min(1.0, confidence)

        return CoDResult(
            detected=True,
            subtype=CoDSubtype.PIECE_CONTROL,
            confidence=confidence,
            tags=["control_over_dynamics", "piece_control_over_dynamics"],
            evidence=evidence,
            diagnostic={
                "mobility_check": mobility_check,
                "volatility_check": volatility_check,
                "self_not_worse": self_not_worse,
            },
        )

    def _detect_pawn_control(self, context: CoDContext) -> CoDResult:
        """
        Detect pawn control over dynamics.

        Criteria:
        - Opponent mobility drop (moderate)
        - Tension delta negative
        - Volatility drop
        """
        m = context.metrics
        t = self.thresholds

        evidence = {
            "opp_mobility_drop": m.opp_mobility_drop,
            "tension_delta": m.tension_delta,
            "volatility_drop_cp": m.volatility_drop_cp,
        }

        tension_threshold = (
            t.tension_delta_end
            if context.phase_bucket == "endgame"
            else t.tension_delta_mid
        )

        mobility_check = m.opp_mobility_drop >= t.opp_mobility_drop * 0.6
        tension_check = m.tension_delta <= tension_threshold
        volatility_check = m.volatility_drop_cp >= t.volatility_drop_cp * 0.5

        if not (mobility_check and tension_check and volatility_check):
            return CoDResult(
                detected=False,
                subtype=CoDSubtype.PAWN_CONTROL,
                evidence=evidence,
                diagnostic={
                    "mobility_check": mobility_check,
                    "tension_check": tension_check,
                    "volatility_check": volatility_check,
                },
            )

        confidence = 0.5 + (abs(m.tension_delta) / tension_threshold) * 0.3
        confidence = min(1.0, confidence)

        return CoDResult(
            detected=True,
            subtype=CoDSubtype.PAWN_CONTROL,
            confidence=confidence,
            tags=["control_over_dynamics", "pawn_control_over_dynamics"],
            evidence=evidence,
            diagnostic={
                "mobility_check": mobility_check,
                "tension_check": tension_check,
                "volatility_check": volatility_check,
                "tension_threshold": tension_threshold,
            },
        )

    def _detect_simplification(self, context: CoDContext) -> CoDResult:
        """
        Detect simplification-based control.

        Criteria:
        - King safety gain >= threshold
        - Eval drop within tolerance
        - Significant piece exchange implied
        """
        m = context.metrics
        t = self.thresholds

        evidence = {
            "king_safety_gain": m.king_safety_gain,
            "eval_drop_cp": m.eval_drop_cp,
        }

        king_safety_check = m.king_safety_gain >= t.king_safety_thresh
        eval_ok = m.eval_drop_cp <= t.eval_drop

        if not (king_safety_check and eval_ok):
            return CoDResult(
                detected=False,
                subtype=CoDSubtype.SIMPLIFICATION,
                evidence=evidence,
                diagnostic={
                    "king_safety_check": king_safety_check,
                    "eval_ok": eval_ok,
                },
            )

        confidence = 0.5 + (m.king_safety_gain / 0.3) * 0.4
        confidence = min(1.0, confidence)

        return CoDResult(
            detected=True,
            subtype=CoDSubtype.SIMPLIFICATION,
            confidence=confidence,
            tags=["control_over_dynamics", "control_simplification"],
            evidence=evidence,
            diagnostic={
                "king_safety_check": king_safety_check,
                "eval_ok": eval_ok,
            },
        )
