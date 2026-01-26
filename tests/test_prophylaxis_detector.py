"""
Unit tests for ProphylaxisDetector.

Tests all 9 COD subtypes, cooldown mechanism, priority selection, and edge cases.
"""
import chess
import pytest

from rule_tagger2.detectors.prophylaxis import ProphylaxisDetector
from rule_tagger2.orchestration.context import AnalysisContext


def create_mock_context(**overrides) -> AnalysisContext:
    """
    Create a mock AnalysisContext for testing.

    Args:
        **overrides: Fields to override in the context or metadata

    Returns:
        AnalysisContext with default values and overrides applied
    """
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    ctx = AnalysisContext(
        board=board,
        played_move=move,
        actor=chess.WHITE,
        phase_bucket="middlegame",
        phase_ratio=1.0,
        metadata={},
    )

    # Apply overrides to metadata
    for key, value in overrides.items():
        if key in ["board", "played_move", "actor", "phase_bucket", "phase_ratio"]:
            setattr(ctx, key, value)
        else:
            ctx.metadata[key] = value

    return ctx


class TestProphylaxisDetectorBasics:
    """Test basic detector interface."""

    def test_detector_name(self):
        """Test that detector has correct name."""
        detector = ProphylaxisDetector()
        assert detector.name == "Prophylaxis"

    def test_no_detection_when_no_criteria_met(self):
        """Test that no tags are returned when no criteria are met."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context()

        tags = detector.detect(ctx)

        assert tags == []
        metadata = detector.get_metadata()
        assert metadata.detector_name == "Prophylaxis"
        assert metadata.tags_found == []


class TestSimplifyDetector:
    """Test simplify COD subtype."""

    def test_simplify_detection(self):
        """Test simplify detection with valid criteria."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            volatility_drop_cp=50.0,  # > 12
            tension_delta=-1.5,  # < -1.0
            opp_mobility_drop=2.5,  # > 2.0 * 0.8
            captures_this_ply=1,
            exchange_count=0,
            total_active_drop=2,
            material_delta_self_cp=10,  # Small material change
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:simplify" in tags
        metadata = detector.get_metadata()
        assert "simplify" in metadata.diagnostic_info["all_detected"]

    def test_simplify_rejected_low_volatility(self):
        """Test simplify rejection when volatility drop is too small."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            volatility_drop_cp=5.0,  # Too low
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
        )

        tags = detector.detect(ctx)

        assert tags == []

    def test_simplify_strict_mode(self):
        """Test simplify with strict mode enabled."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            strict_mode=True,
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,  # Only 1 pair, need 2 in strict mode
            exchange_count=0,
            total_active_drop=2,
        )

        tags = detector.detect(ctx)

        # Should fail in strict mode with only 1 exchange pair
        assert tags == []


class TestPlanKillDetector:
    """Test plan_kill COD subtype."""

    def test_plan_kill_via_plan_drop(self):
        """Test plan_kill detection via plan_drop_passed flag."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            plan_drop_passed=True,
            preventive_score=0.05,  # Below trigger, but plan_drop overrides
            threat_delta=0.1,
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:plan_kill" in tags

    def test_plan_kill_via_preventive_score(self):
        """Test plan_kill detection via high preventive score."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            preventive_score=0.10,  # > 0.08 trigger
            threat_delta=0.35,  # > 0.3 threshold
            opp_mobility_drop=0.5,
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:plan_kill" in tags

    def test_plan_kill_rejected_low_preventive(self):
        """Test plan_kill rejection when preventive score is too low."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            preventive_score=0.05,  # Below trigger
            threat_delta=0.1,  # Below threshold
            plan_drop_passed=False,
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestFreezeBindDetector:
    """Test freeze_bind COD subtype."""

    def test_freeze_bind_detection(self):
        """Test freeze_bind detection with structure gain and mobility freeze."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            structure_gain=0.20,  # > 0.18
            opp_mobility_change_eval=-0.25,  # < -0.18
            tension_delta=-1.5,  # Well below threshold
            phase_bucket="middlegame",
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:freeze_bind" in tags

    def test_freeze_bind_rejected_no_structure_gain(self):
        """Test freeze_bind rejection when structure gain is insufficient."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            structure_gain=0.10,  # Too low
            opp_mobility_change_eval=-0.25,
            tension_delta=-1.5,
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestBlockadePassedDetector:
    """Test blockade_passed COD subtype."""

    def test_blockade_passed_detection(self):
        """Test blockade detection of opponent's passed pawn."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            opp_passed_exists=True,
            blockade_established=True,
            opp_passed_push_drop=2.5,  # > 1.0 minimum
            blockade_file="d",
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:blockade_passed" in tags

    def test_blockade_rejected_no_passed_pawn(self):
        """Test blockade rejection when no opponent passed pawn exists."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            opp_passed_exists=False,
            blockade_established=True,
            opp_passed_push_drop=2.5,
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestFileSealDetector:
    """Test file_seal COD subtype."""

    def test_file_seal_via_pressure_drop(self):
        """Test file_seal detection via line pressure drop."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            opp_line_pressure_drop=1.5,  # > LINE_MIN (typically 1.0)
            break_candidates_delta=0,
            volatility_drop_cp=10.0,  # > 12 * 0.5
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:file_seal" in tags

    def test_file_seal_via_break_candidates(self):
        """Test file_seal detection via reduced break candidates."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            opp_line_pressure_drop=0.5,  # Low, but break_delta compensates
            break_candidates_delta=-2.0,  # Significant drop
            volatility_drop_cp=10.0,
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:file_seal" in tags

    def test_file_seal_rejected_low_volatility(self):
        """Test file_seal rejection when volatility drop is insufficient."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            opp_line_pressure_drop=1.5,
            break_candidates_delta=-2.0,
            volatility_drop_cp=2.0,  # Too low (< 12 * 0.5)
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestKingSafetyShellDetector:
    """Test king_safety_shell COD subtype."""

    def test_king_safety_shell_via_tactics_drop(self):
        """Test king_safety detection via opponent tactics reduction."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            king_safety_gain=0.18,  # > 0.15 threshold
            opp_tactics_change_eval=-0.15,  # < -0.1
            opp_mobility_drop=0.5,
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:king_safety_shell" in tags

    def test_king_safety_shell_via_mobility_drop(self):
        """Test king_safety detection via opponent mobility drop."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            king_safety_gain=0.18,
            opp_tactics_change_eval=0.0,  # Neutral
            opp_mobility_drop=2.5,  # > 2.0 threshold
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:king_safety_shell" in tags

    def test_king_safety_rejected_low_gain(self):
        """Test king_safety rejection when gain is too small."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            king_safety_gain=0.10,  # Too low
            opp_tactics_change_eval=-0.15,
            opp_mobility_drop=2.5,
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestSpaceClampDetector:
    """Test space_clamp COD subtype."""

    def test_space_clamp_detection(self):
        """Test space_clamp detection with space gain and mobility drop."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            space_gain=0.4,  # > 0.3 (SPACE_MIN / 10)
            opp_mobility_drop=1.5,  # > 2.0 * 0.6
            tension_delta=-0.5,  # <= 0
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:space_clamp" in tags

    def test_space_clamp_rejected_positive_tension(self):
        """Test space_clamp rejection when tension increases."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            space_gain=0.4,
            opp_mobility_drop=1.5,
            tension_delta=0.5,  # Positive, should reject
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestRegroupConsolidateDetector:
    """Test regroup_consolidate COD subtype."""

    def test_regroup_via_king_safety(self):
        """Test regroup detection via king safety improvement."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            volatility_drop_cp=10.0,  # > 12 * 0.6
            self_mobility_change=0.03,  # <= 0.05
            king_safety_gain=0.10,  # > 0.05
            structure_gain=0.05,
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:regroup_consolidate" in tags

    def test_regroup_via_structure(self):
        """Test regroup detection via structure improvement."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            volatility_drop_cp=10.0,
            self_mobility_change=0.03,
            king_safety_gain=0.03,
            structure_gain=0.12,  # > 0.1
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:regroup_consolidate" in tags

    def test_regroup_rejected_high_self_mobility(self):
        """Test regroup rejection when self-mobility increases too much."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            volatility_drop_cp=10.0,
            self_mobility_change=0.10,  # Too high
            king_safety_gain=0.10,
            structure_gain=0.12,
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestSlowdownDetector:
    """Test slowdown COD subtype."""

    def test_slowdown_detection(self):
        """Test slowdown detection when dampening dynamics."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            has_dynamic_in_band=True,
            played_kind="positional",
            eval_drop_cp=15,  # <= 20
            volatility_drop_cp=15.0,  # > 12
            tension_delta=-1.5,  # <= threshold
            opp_mobility_drop=2.5,  # > 2.0
            phase_bucket="middlegame",
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "control_over_dynamics:slowdown" in tags

    def test_slowdown_rejected_no_dynamic_available(self):
        """Test slowdown rejection when no dynamic move is available."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            has_dynamic_in_band=False,  # No dynamic alternative
            played_kind="positional",
            eval_drop_cp=15,
            volatility_drop_cp=15.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
        )

        tags = detector.detect(ctx)

        assert tags == []

    def test_slowdown_rejected_played_dynamic(self):
        """Test slowdown rejection when played move is dynamic."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            allow_positional=True,
            has_dynamic_in_band=True,
            played_kind="dynamic",  # Played dynamic, not positional
            eval_drop_cp=15,
            volatility_drop_cp=15.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
        )

        tags = detector.detect(ctx)

        assert tags == []


class TestCooldownMechanism:
    """Test cooldown mechanism to prevent over-tagging."""

    def test_cooldown_suppresses_same_subtype(self):
        """Test that cooldown suppresses the same subtype within cooldown window."""
        detector = ProphylaxisDetector()

        # First detection at ply 10
        ctx1 = create_mock_context(
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
            current_ply=10,
        )

        tags1 = detector.detect(ctx1)
        assert "control_over_dynamics:simplify" in tags1

        # Second detection at ply 12 (within cooldown of 3 plies)
        last_state = ctx1.metadata.get("last_cod_state")
        ctx2 = create_mock_context(
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
            current_ply=12,
            last_cod_state=last_state,
        )

        tags2 = detector.detect(ctx2)
        # Should be suppressed
        assert tags2 == [] or "simplify" not in tags2[1]

        metadata = detector.get_metadata()
        assert "simplify" in metadata.diagnostic_info.get("suppressed", [])

    def test_cooldown_expires_after_window(self):
        """Test that cooldown expires after cooldown window."""
        detector = ProphylaxisDetector()

        # First detection at ply 10
        ctx1 = create_mock_context(
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
            current_ply=10,
        )

        tags1 = detector.detect(ctx1)
        assert "control_over_dynamics:simplify" in tags1

        # Second detection at ply 15 (cooldown expired: 15 - 10 = 5 > 3)
        last_state = ctx1.metadata.get("last_cod_state")
        ctx2 = create_mock_context(
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
            current_ply=15,
            last_cod_state=last_state,
        )

        tags2 = detector.detect(ctx2)
        # Should NOT be suppressed (cooldown expired)
        assert "control_over_dynamics:simplify" in tags2


class TestPrioritySelection:
    """Test priority-based selection when multiple subtypes match."""

    def test_priority_selects_highest(self):
        """Test that highest priority subtype is selected when multiple match."""
        detector = ProphylaxisDetector()

        # Create context where both simplify and plan_kill match
        # simplify has higher priority (earlier in COD_SUBTYPES list)
        ctx = create_mock_context(
            # Simplify criteria
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
            # Plan_kill criteria
            allow_positional=True,
            preventive_score=0.10,
            threat_delta=0.35,
        )

        tags = detector.detect(ctx)

        # simplify should be selected (higher priority)
        assert "control_over_dynamics:simplify" in tags

        metadata = detector.get_metadata()
        detected = metadata.diagnostic_info["all_detected"]
        # Both should be detected
        assert "simplify" in detected
        assert "plan_kill" in detected
        # plan_kill should be suppressed
        assert "plan_kill" in metadata.diagnostic_info.get("suppressed", [])


class TestMetadataPopulation:
    """Test that detector populates metadata correctly."""

    def test_metadata_gate_log(self):
        """Test that gate_log is populated with detector results."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
        )

        detector.detect(ctx)

        metadata = detector.get_metadata()
        gate_log = metadata.diagnostic_info["gate_log"]

        # Should have entries for all 9 subtypes
        assert "simplify" in gate_log
        assert gate_log["simplify"]["passed"] is True

    def test_metadata_notes(self):
        """Test that notes are added to context metadata."""
        detector = ProphylaxisDetector()
        ctx = create_mock_context(
            volatility_drop_cp=50.0,
            tension_delta=-1.5,
            opp_mobility_drop=2.5,
            captures_this_ply=1,
            total_active_drop=2,
        )

        tags = detector.detect(ctx)

        assert "control_over_dynamics" in tags
        assert "prophylaxis_notes" in ctx.metadata
        assert len(ctx.metadata["prophylaxis_notes"]) > 0
        # Note should mention "simplify"
        assert "simplify" in ctx.metadata["prophylaxis_notes"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
