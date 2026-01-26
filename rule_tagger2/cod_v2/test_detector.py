"""
Unit tests for Control over Dynamics v2 Detector.

These tests are ISOLATED from the rest of the codebase.
They only test the cod_v2 module without any dependencies on legacy code.

Run with: CLAUDE_COD_V2=1 pytest rule_tagger2/cod_v2/test_detector.py -v
"""
import os

import chess
import pytest

from .config import CoDThresholds, is_cod_v2_enabled
from .detector import ControlOverDynamicsV2Detector
from .cod_types import CoDContext, CoDMetrics, CoDResult, CoDSubtype


class TestCoDV2FeatureFlag:
    """Test the feature flag mechanism."""

    def test_feature_flag_disabled_by_default(self):
        """Test that CoD v2 is disabled by default."""
        # Save current value
        old_value = os.environ.get("CLAUDE_COD_V2")

        try:
            # Remove flag
            if "CLAUDE_COD_V2" in os.environ:
                del os.environ["CLAUDE_COD_V2"]

            assert not is_cod_v2_enabled()
        finally:
            # Restore
            if old_value is not None:
                os.environ["CLAUDE_COD_V2"] = old_value

    def test_feature_flag_can_be_enabled(self):
        """Test that CoD v2 can be enabled."""
        old_value = os.environ.get("CLAUDE_COD_V2")

        try:
            os.environ["CLAUDE_COD_V2"] = "1"
            assert is_cod_v2_enabled()
        finally:
            if old_value is not None:
                os.environ["CLAUDE_COD_V2"] = old_value
            else:
                if "CLAUDE_COD_V2" in os.environ:
                    del os.environ["CLAUDE_COD_V2"]


class TestCoDThresholds:
    """Test threshold configuration."""

    def test_default_thresholds(self):
        """Test that default thresholds are reasonable."""
        t = CoDThresholds()

        assert t.tactical_weight_ceiling > 0
        assert t.volatility_drop_cp > 0
        assert t.opp_mobility_drop > 0
        assert t.cooldown_plies >= 0

    def test_thresholds_to_dict(self):
        """Test conversion to dictionary."""
        t = CoDThresholds()
        d = t.to_dict()

        assert isinstance(d, dict)
        assert "tactical_weight_ceiling" in d
        assert "volatility_drop_cp" in d


class TestCoDDetector:
    """Test the CoD v2 detector."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        return ControlOverDynamicsV2Detector()

    @pytest.fixture
    def minimal_context(self):
        """Create a minimal context for testing."""
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")

        return CoDContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            metrics=CoDMetrics(),
            current_ply=10,
        )

    def test_detector_initialization(self, detector):
        """Test detector initializes correctly."""
        assert detector.name == "ControlOverDynamicsV2"
        assert detector.version.startswith("2.0")
        assert detector.thresholds is not None

    def test_no_detection_by_default(self, detector, minimal_context):
        """Test that minimal context produces no detection."""
        result = detector.detect(minimal_context)

        assert isinstance(result, CoDResult)
        assert not result.detected
        assert result.subtype == CoDSubtype.NONE

    def test_tactical_gate_blocks_detection(self, detector, minimal_context):
        """Test that high tactical weight blocks detection."""
        minimal_context.tactical_weight = 0.9  # Above ceiling

        # Even with strong signals, should be blocked
        minimal_context.metrics.volatility_drop_cp = 150.0
        minimal_context.metrics.opp_mobility_drop = 0.3

        result = detector.detect(minimal_context)

        assert not result.detected
        assert "tactical_gate" in result.gates_passed
        assert not result.gates_passed["tactical_gate"]
        assert len(result.gates_failed) > 0

    def test_prophylaxis_detection(self, detector, minimal_context):
        """Test prophylaxis detection with strong signals."""
        # Set tactical weight low (pass gate)
        minimal_context.tactical_weight = 0.3

        # Strong prophylaxis signals
        minimal_context.metrics.volatility_drop_cp = 120.0
        minimal_context.metrics.opp_mobility_drop = 0.25
        minimal_context.metrics.tension_delta = -0.1
        minimal_context.metrics.preventive_score = 0.35

        result = detector.detect(minimal_context)

        assert result.detected
        assert result.subtype == CoDSubtype.PROPHYLAXIS
        assert result.confidence > 0.5
        assert "control_over_dynamics" in result.tags
        assert "cod_prophylaxis" in result.tags

    def test_piece_control_detection(self, detector, minimal_context):
        """Test piece control detection."""
        minimal_context.tactical_weight = 0.4

        # Piece control signals
        minimal_context.metrics.opp_mobility_drop = 0.20
        minimal_context.metrics.volatility_drop_cp = 90.0
        minimal_context.metrics.self_mobility_change = 0.05

        result = detector.detect(minimal_context)

        assert result.detected
        assert result.subtype == CoDSubtype.PIECE_CONTROL
        assert "piece_control_over_dynamics" in result.tags

    def test_pawn_control_detection(self, detector, minimal_context):
        """Test pawn control detection."""
        minimal_context.tactical_weight = 0.35
        minimal_context.phase_bucket = "middlegame"

        # Pawn control signals
        minimal_context.metrics.opp_mobility_drop = 0.12
        minimal_context.metrics.tension_delta = -0.2
        minimal_context.metrics.volatility_drop_cp = 60.0

        result = detector.detect(minimal_context)

        assert result.detected
        assert result.subtype == CoDSubtype.PAWN_CONTROL
        assert "pawn_control_over_dynamics" in result.tags

    def test_simplification_detection(self, detector, minimal_context):
        """Test simplification detection."""
        minimal_context.tactical_weight = 0.25

        # Simplification signals
        minimal_context.metrics.king_safety_gain = 0.20
        minimal_context.metrics.eval_drop_cp = 0.3

        result = detector.detect(minimal_context)

        assert result.detected
        assert result.subtype == CoDSubtype.SIMPLIFICATION
        assert "control_simplification" in result.tags

    def test_cooldown_mechanism(self, detector, minimal_context):
        """Test that cooldown prevents repeated detections."""
        minimal_context.tactical_weight = 0.3
        minimal_context.current_ply = 20
        minimal_context.last_cod_ply = 18  # 2 plies ago
        minimal_context.last_cod_subtype = CoDSubtype.PROPHYLAXIS

        # Strong signals
        minimal_context.metrics.volatility_drop_cp = 120.0

        result = detector.detect(minimal_context)

        assert not result.detected
        assert "cooldown" in result.gates_failed

    def test_result_serialization(self, detector, minimal_context):
        """Test that result can be serialized to dict."""
        minimal_context.tactical_weight = 0.3
        minimal_context.metrics.volatility_drop_cp = 100.0
        minimal_context.metrics.opp_mobility_drop = 0.2

        result = detector.detect(minimal_context)

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "detected" in result_dict
        assert "subtype" in result_dict
        assert "confidence" in result_dict
        assert "tags" in result_dict
        assert "diagnostic" in result_dict

    def test_metrics_serialization(self):
        """Test that metrics can be serialized."""
        metrics = CoDMetrics(
            volatility_drop_cp=100.5,
            opp_mobility_drop=0.234,
            tension_delta=-0.123,
        )

        d = metrics.to_dict()

        assert isinstance(d, dict)
        assert d["volatility_drop_cp"] == 100.5
        assert abs(d["opp_mobility_drop"] - 0.234) < 0.001

    def test_multiple_candidates_priority(self, detector, minimal_context):
        """Test that prophylaxis has priority over other detections."""
        minimal_context.tactical_weight = 0.3

        # Set up signals for multiple subtypes
        minimal_context.metrics.volatility_drop_cp = 100.0
        minimal_context.metrics.opp_mobility_drop = 0.25
        minimal_context.metrics.tension_delta = -0.2
        minimal_context.metrics.preventive_score = 0.30
        minimal_context.metrics.king_safety_gain = 0.20
        minimal_context.metrics.eval_drop_cp = 0.3

        result = detector.detect(minimal_context)

        # Prophylaxis should win due to priority
        assert result.detected
        assert result.subtype == CoDSubtype.PROPHYLAXIS
        assert "all_candidates" in result.diagnostic


@pytest.mark.skipif(
    not is_cod_v2_enabled(),
    reason="CoD v2 tests require CLAUDE_COD_V2=1"
)
class TestCoDV2Integration:
    """
    Integration tests that only run when feature flag is enabled.

    These tests verify the detector works correctly when activated.
    """

    def test_feature_flag_integration(self):
        """Test that feature flag is properly detected."""
        assert is_cod_v2_enabled()

    def test_detector_can_run_when_enabled(self):
        """Test that detector runs when feature flag is on."""
        detector = ControlOverDynamicsV2Detector()

        board = chess.Board()
        move = chess.Move.from_uci("e2e4")

        context = CoDContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            metrics=CoDMetrics(),
            current_ply=5,
            tactical_weight=0.3,
        )

        # Should not crash
        result = detector.detect(context)
        assert isinstance(result, CoDResult)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
