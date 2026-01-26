"""
Unit tests for TensionDetector

Tests the tension creation detection logic extracted from legacy/core.py.
"""
import unittest
from typing import Dict, List

from rule_tagger2.detectors.tension import TensionDetector
from rule_tagger2.orchestration.context import AnalysisContext


class MockAnalysisContext:
    """Mock AnalysisContext for testing."""

    def __init__(self, **kwargs):
        # Set all attributes from kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Initialize required structures
        if not hasattr(self, 'analysis_meta'):
            self.analysis_meta = {}
        if not hasattr(self, 'notes'):
            self.notes = {}


class TestTensionDetector(unittest.TestCase):
    """Test cases for TensionDetector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = TensionDetector()

    def test_detector_name(self):
        """Test detector has correct name."""
        self.assertEqual(self.detector.name, "TensionDetector")

    def test_no_tension_outside_eval_band(self):
        """Test that no tension is detected outside eval band."""
        ctx = MockAnalysisContext(
            delta_eval_float=1.5,  # Outside TENSION_EVAL_MAX (0.1)
            delta_self_mobility=0.4,
            delta_opp_mobility=-0.4,
            contact_delta_played=0.0,
            phase_ratio=0.7,
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=0.0,
            opp_trend=0.0,
            follow_self_deltas=[],
            follow_opp_deltas=[],
            followup_tail_self=0.0,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertNotIn("tension_creation", tags)

    def test_no_tension_early_phase(self):
        """Test that tension requires phase_ratio > 0.5."""
        ctx = MockAnalysisContext(
            delta_eval_float=0.0,
            delta_self_mobility=0.4,
            delta_opp_mobility=-0.4,
            contact_delta_played=0.0,
            phase_ratio=0.3,  # Too early
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=0.0,
            opp_trend=0.0,
            follow_self_deltas=[],
            follow_opp_deltas=[],
            followup_tail_self=0.0,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertNotIn("tension_creation", tags)

    def test_no_tension_same_direction_mobility(self):
        """Test that mobility changes must be opposite directions."""
        ctx = MockAnalysisContext(
            delta_eval_float=0.0,
            delta_self_mobility=0.4,  # Both positive - same direction
            delta_opp_mobility=0.3,
            contact_delta_played=0.0,
            phase_ratio=0.7,
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=0.0,
            opp_trend=0.0,
            follow_self_deltas=[],
            follow_opp_deltas=[],
            followup_tail_self=0.0,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertNotIn("tension_creation", tags)

    def test_tension_creation_core_criteria(self):
        """Test tension detection via core mobility criteria."""
        ctx = MockAnalysisContext(
            delta_eval_float=0.0,
            delta_self_mobility=0.35,  # Above threshold, opposite directions
            delta_opp_mobility=-0.35,
            contact_delta_played=0.05,  # Direct contact
            phase_ratio=0.7,
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=0.1,
            opp_trend=-0.1,
            follow_self_deltas=[{"mobility": 0.3}, {"mobility": 0.35}],
            follow_opp_deltas=[{"mobility": 0.3}, {"mobility": 0.35}],
            followup_tail_self=0.1,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertIn("tension_creation", tags)
        self.assertIn("tension_creation", ctx.notes)

    def test_tension_creation_structural_support(self):
        """Test tension detection with structural shift."""
        ctx = MockAnalysisContext(
            delta_eval_float=-0.3,
            delta_self_mobility=0.32,  # Near threshold (0.3) with structural support
            delta_opp_mobility=-0.32,
            contact_delta_played=0.05,  # Direct contact to satisfy window_ok
            phase_ratio=0.8,
            structural_shift_signal=True,  # Structural shift provides support
            contact_trigger=False,
            self_trend=0.0,
            opp_trend=0.0,
            follow_self_deltas=[{"mobility": 0.32}, {"mobility": 0.32}],
            follow_opp_deltas=[{"mobility": 0.32}, {"mobility": 0.32}],
            followup_tail_self=0.0,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertIn("tension_creation", tags)
        # Check that structural support is mentioned in trigger sources
        self.assertTrue(len(ctx.analysis_meta["tension_support"]["trigger_sources"]) > 0)

    def test_neutral_tension_creation(self):
        """Test neutral tension detection (very small eval change)."""
        ctx = MockAnalysisContext(
            delta_eval_float=0.05,  # Within NEUTRAL_TENSION_BAND (0.13)
            delta_self_mobility=0.1,  # Below threshold
            delta_opp_mobility=-0.1,
            contact_delta_played=0.0,
            phase_ratio=0.7,
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=0.0,
            opp_trend=0.0,
            follow_self_deltas=[],
            follow_opp_deltas=[],
            followup_tail_self=0.0,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertIn("neutral_tension_creation", tags)
        self.assertNotIn("tension_creation", tags)

    def test_risk_avoidance_override(self):
        """Test that risk avoidance suppresses tension creation."""
        ctx = MockAnalysisContext(
            delta_eval_float=0.0,
            delta_self_mobility=0.35,
            delta_opp_mobility=-0.35,
            contact_delta_played=0.05,
            phase_ratio=0.7,
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=0.1,
            opp_trend=-0.1,
            follow_self_deltas=[{"mobility": 0.3}, {"mobility": 0.35}],
            follow_opp_deltas=[{"mobility": 0.3}, {"mobility": 0.35}],
            followup_tail_self=0.1,
            structural_compromise_dynamic=False,
            risk_avoidance=True,  # Risk avoidance blocks tension
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertNotIn("tension_creation", tags)

    def test_delayed_tension_trigger(self):
        """Test delayed tension detection via trend criteria."""
        ctx = MockAnalysisContext(
            delta_eval_float=-0.3,
            delta_self_mobility=0.26,  # Above TENSION_MOBILITY_DELAY (0.25)
            delta_opp_mobility=-0.26,
            contact_delta_played=0.035,  # Above TENSION_CONTACT_DELAY (0.03)
            phase_ratio=0.7,
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=-0.35,  # Below TENSION_TREND_SELF (-0.3)
            opp_trend=0.35,   # Above TENSION_TREND_OPP (0.3)
            follow_self_deltas=[{"mobility": 0.26}, {"mobility": 0.26}],  # Sustained
            follow_opp_deltas=[{"mobility": 0.26}, {"mobility": 0.26}],
            followup_tail_self=0.0,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        tags = self.detector.detect(ctx)
        self.assertIn("tension_creation", tags)
        # Check for delayed_trend in trigger sources
        trigger_sources = ctx.analysis_meta["tension_support"]["trigger_sources"]
        self.assertIn("delayed_trend", trigger_sources)

    def test_analysis_meta_population(self):
        """Test that analysis_meta is properly populated."""
        ctx = MockAnalysisContext(
            delta_eval_float=0.0,
            delta_self_mobility=0.35,
            delta_opp_mobility=-0.35,
            contact_delta_played=0.0,
            phase_ratio=0.7,
            structural_shift_signal=False,
            contact_trigger=False,
            self_trend=0.1,
            opp_trend=-0.1,
            follow_self_deltas=[{"mobility": 0.3}, {"mobility": 0.35}],
            follow_opp_deltas=[{"mobility": 0.3}, {"mobility": 0.35}],
            followup_tail_self=0.1,
            structural_compromise_dynamic=False,
            risk_avoidance=False,
            file_pressure_c_flag=False,
        )

        self.detector.detect(ctx)

        # Check that tension_support is populated
        self.assertIn("tension_support", ctx.analysis_meta)
        support = ctx.analysis_meta["tension_support"]
        self.assertIn("effective_threshold", support)
        self.assertIn("mobility_self", support)
        self.assertIn("mobility_opp", support)
        self.assertIn("symmetry_gap", support)
        self.assertIn("trigger_sources", support)
        self.assertIn("neutral_band", support)


if __name__ == "__main__":
    unittest.main()
