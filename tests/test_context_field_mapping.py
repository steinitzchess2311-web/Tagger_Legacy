"""
Unit tests for AnalysisContext field mapping from legacy TagResult.

Tests verify that all critical fields from legacy analysis_context and engine_meta
are correctly mapped to the new AnalysisContext structure (fail-fast).
"""
import unittest
from unittest.mock import MagicMock
import chess

from rule_tagger2.orchestration.pipeline import TagDetectionPipeline
from rule_tagger2.orchestration.context import AnalysisContext


class MockTagResult:
    """Mock legacy TagResult for testing field mapping."""

    def __init__(self, analysis_context: dict):
        self.analysis_context = analysis_context
        self.tags = []
        self.mode = "normal"


class TestContextFieldMapping(unittest.TestCase):
    """Test cases for field mapping from legacy to new context."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = TagDetectionPipeline()
        self.board = chess.Board()
        self.played_move = chess.Move.from_uci("e2e4")

    def test_engine_meta_basic_fields_mapping(self):
        """Test that basic engine_meta fields are correctly mapped to ctx.metadata."""
        legacy_result = MockTagResult({
            "engine_meta": {
                "score_gap_cp": 50,
                "depth_jump_cp": 10,
                "deepening_gain_cp": 5,
                "contact_ratio": 0.3,
                "contact_moves": 8,
                "capture_moves": 4,
                "checking_moves": 2,
                "total_moves": 20,
                "mate_threat": False,
                "depth_used": 16,
                "multipv": 6,
                "depth_low": 8,
                "depth_high": 20,
            }
        })

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify all basic engine_meta fields are in metadata
        self.assertEqual(ctx.metadata['score_gap_cp'], 50)
        self.assertEqual(ctx.metadata['depth_jump_cp'], 10)
        self.assertEqual(ctx.metadata['deepening_gain_cp'], 5)
        self.assertAlmostEqual(ctx.metadata['contact_ratio'], 0.3)
        self.assertEqual(ctx.metadata['contact_moves'], 8)
        self.assertEqual(ctx.metadata['capture_moves'], 4)
        self.assertEqual(ctx.metadata['checking_moves'], 2)
        self.assertEqual(ctx.metadata['total_moves'], 20)
        self.assertEqual(ctx.metadata['mate_threat'], False)
        self.assertEqual(ctx.metadata['depth_used'], 16)
        self.assertEqual(ctx.metadata['multipv'], 6)
        self.assertEqual(ctx.metadata['depth_low'], 8)
        self.assertEqual(ctx.metadata['depth_high'], 20)

    def test_engine_meta_support_structures_mapping(self):
        """Test that complex support structures from engine_meta are mapped correctly."""
        tension_support_data = {
            "trigger_sources": ["mobility_symmetry", "contact_ratio"],
            "sustained": True,
            "neutral_band": {"band_cp": 10, "delta_eval": 5.0}
        }

        prophylaxis_data = {
            "quality": "excellent",
            "preventive_score": 0.8,
            "telemetry": {"pattern_override": False}
        }

        legacy_result = MockTagResult({
            "engine_meta": {
                "tension_support": tension_support_data,
                "cod_support": {"cooldown_remaining": 0},
                "prophylaxis": prophylaxis_data,
                "control_dynamics": {"gates": {"volatility": True}},
                "structural_details": {"before": {"pawns": 8}},
                "telemetry": {"tension": {"triggered": True}},
            }
        })

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify complex structures are mapped
        self.assertEqual(ctx.metadata['tension_support'], tension_support_data)
        self.assertIn('cod_support', ctx.metadata)
        self.assertEqual(ctx.metadata['prophylaxis'], prophylaxis_data)
        self.assertIn('control_dynamics', ctx.metadata)
        self.assertIn('structural_details', ctx.metadata)
        self.assertIn('telemetry', ctx.metadata)

    def test_tension_detector_fields_mapping(self):
        """Test that TensionDetector-specific fields are correctly mapped."""
        legacy_result = MockTagResult({
            "delta_eval_float": 0.05,
            "delta_self_mobility": 0.3,
            "delta_opp_mobility": -0.25,
            "contact_delta_played": 0.1,
            "phase_ratio": 0.7,
            "structural_shift_signal": True,
            "contact_trigger": False,
            "self_trend": 0.15,
            "opp_trend": -0.12,
            "follow_self_deltas": [0.1, 0.15, 0.2],
            "follow_opp_deltas": [-0.1, -0.15, -0.18],
            "followup_tail_self": 0.18,
            "structural_compromise_dynamic": False,
            "risk_avoidance": True,
            "file_pressure_c_flag": False,
        })

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify TensionDetector fields are directly accessible
        self.assertAlmostEqual(ctx.delta_eval_float, 0.05)
        self.assertAlmostEqual(ctx.delta_self_mobility, 0.3)
        self.assertAlmostEqual(ctx.delta_opp_mobility, -0.25)
        self.assertAlmostEqual(ctx.contact_delta_played, 0.1)
        self.assertAlmostEqual(ctx.phase_ratio, 0.7)
        self.assertEqual(ctx.structural_shift_signal, True)
        self.assertEqual(ctx.contact_trigger, False)
        self.assertAlmostEqual(ctx.self_trend, 0.15)
        self.assertAlmostEqual(ctx.opp_trend, -0.12)
        self.assertEqual(ctx.follow_self_deltas, [0.1, 0.15, 0.2])
        self.assertEqual(ctx.follow_opp_deltas, [-0.1, -0.15, -0.18])
        self.assertAlmostEqual(ctx.followup_tail_self, 0.18)
        self.assertEqual(ctx.structural_compromise_dynamic, False)
        self.assertEqual(ctx.risk_avoidance, True)
        self.assertEqual(ctx.file_pressure_c_flag, False)

    def test_prophylaxis_detector_fields_mapping(self):
        """Test that ProphylaxisDetector-specific fields are correctly mapped."""
        legacy_result = MockTagResult({
            "phase_bucket": "endgame",
            "volatility_drop_cp": 25.0,
            "tension_delta": 0.15,
            "opp_mobility_drop": 0.35,
            "structure_gain": 0.1,
            "king_safety_gain": 0.2,
            "space_gain": 0.05,
            "preventive_score": 0.75,
            "threat_delta": 0.3,
            "plan_drop_passed": True,
            "allow_positional": True,
        })

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify ProphylaxisDetector fields
        self.assertEqual(ctx.phase_bucket, "endgame")
        self.assertAlmostEqual(ctx.metadata['volatility_drop_cp'], 25.0)
        self.assertAlmostEqual(ctx.metadata['tension_delta'], 0.15)
        self.assertAlmostEqual(ctx.metadata['opp_mobility_drop'], 0.35)
        self.assertAlmostEqual(ctx.metadata['structure_gain'], 0.1)
        self.assertAlmostEqual(ctx.metadata['king_safety_gain'], 0.2)
        self.assertAlmostEqual(ctx.metadata['space_gain'], 0.05)
        self.assertAlmostEqual(ctx.metadata['preventive_score'], 0.75)
        self.assertAlmostEqual(ctx.metadata['threat_delta'], 0.3)
        self.assertEqual(ctx.metadata['plan_drop_passed'], True)
        self.assertEqual(ctx.metadata['allow_positional'], True)

    def test_active_drop_fields_mapping(self):
        """Test that active piece drop fields (for simplify detector) are mapped."""
        legacy_result = MockTagResult({
            "captures_this_ply": 2,
            "square_defended_by_opp": 5,
            "has_immediate_tactical_followup": True,
            "is_capture": True,
            "total_active_drop": 3,
            "own_active_drop": 1,
            "opp_active_drop": 2,
            "exchange_count": 1,
            "material_delta_self_cp": -50,
            "material_delta_self": -1.5,
            "captured_value_cp": 300,
            "blockade_file": "d",
        })

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify active drop fields
        self.assertEqual(ctx.metadata['captures_this_ply'], 2)
        self.assertEqual(ctx.metadata['square_defended_by_opp'], 5)
        self.assertEqual(ctx.metadata['has_immediate_tactical_followup'], True)
        self.assertEqual(ctx.metadata['is_capture'], True)
        self.assertEqual(ctx.metadata['total_active_drop'], 3)
        self.assertEqual(ctx.metadata['own_active_drop'], 1)
        self.assertEqual(ctx.metadata['opp_active_drop'], 2)
        self.assertEqual(ctx.metadata['exchange_count'], 1)
        self.assertEqual(ctx.metadata['material_delta_self_cp'], -50)
        self.assertAlmostEqual(ctx.metadata['material_delta_self'], -1.5)
        self.assertEqual(ctx.metadata['captured_value_cp'], 300)
        self.assertEqual(ctx.metadata['blockade_file'], "d")

    def test_full_analysis_context_preserved(self):
        """Test that the full analysis_context (including engine_meta) is preserved."""
        full_context = {
            "delta_eval_float": 0.08,
            "phase_ratio": 0.6,
            "engine_meta": {
                "score_gap_cp": 75,
                "tension_support": {"triggered": True},
                "ruleset_version": "rulestack_2025-11-03",
            },
            "custom_field": "custom_value",
        }

        legacy_result = MockTagResult(full_context)

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify full context is in analysis_meta
        self.assertIn("delta_eval_float", ctx.analysis_meta)
        self.assertIn("engine_meta", ctx.analysis_meta)
        self.assertEqual(ctx.analysis_meta["engine_meta"]["score_gap_cp"], 75)
        self.assertEqual(ctx.analysis_meta["custom_field"], "custom_value")

    def test_missing_fields_use_defaults(self):
        """Test that missing fields use appropriate default values (fail-safe)."""
        legacy_result = MockTagResult({})

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify default values
        self.assertEqual(ctx.delta_eval_float, 0.0)
        self.assertEqual(ctx.delta_self_mobility, 0.0)
        self.assertEqual(ctx.delta_opp_mobility, 0.0)
        self.assertEqual(ctx.phase_bucket, "middlegame")
        self.assertEqual(ctx.structural_shift_signal, False)
        self.assertEqual(ctx.notes, {})

    def test_backward_compatibility_all_fields_accessible(self):
        """Test backward compatibility: all analysis_ctx fields remain in metadata."""
        legacy_result = MockTagResult({
            "custom_legacy_field_1": 123,
            "custom_legacy_field_2": "test",
            "delta_eval_float": 0.05,
            "engine_meta": {
                "score_gap_cp": 40,
            }
        })

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify all legacy fields are accessible via metadata
        self.assertEqual(ctx.metadata['custom_legacy_field_1'], 123)
        self.assertEqual(ctx.metadata['custom_legacy_field_2'], "test")
        self.assertEqual(ctx.metadata['score_gap_cp'], 40)

    def test_field_mapping_critical_paths_fail_fast(self):
        """Test critical field mapping paths (fail-fast on missing critical fields)."""
        # This test ensures that if critical fields are missing in the mapping,
        # detectors can still access them via metadata

        critical_fields = [
            "score_gap_cp", "depth_jump_cp", "contact_ratio",
            "tension_support", "prophylaxis", "control_dynamics",
            "delta_eval_float", "delta_self_mobility", "delta_opp_mobility",
            "volatility_drop_cp", "preventive_score", "phase_ratio"
        ]

        # Build full test data
        test_data = {
            "delta_eval_float": 0.05,
            "delta_self_mobility": 0.3,
            "delta_opp_mobility": -0.25,
            "phase_ratio": 0.7,
            "volatility_drop_cp": 20.0,
            "preventive_score": 0.6,
            "engine_meta": {
                "score_gap_cp": 60,
                "depth_jump_cp": 8,
                "contact_ratio": 0.25,
                "tension_support": {},
                "prophylaxis": {},
                "control_dynamics": {},
            }
        }

        legacy_result = MockTagResult(test_data)

        ctx = self.pipeline._build_context_from_legacy(
            legacy_result, self.board, self.played_move
        )

        # Verify all critical fields are accessible
        for field in critical_fields:
            # Check if field is in ctx attributes or metadata
            has_field = (
                hasattr(ctx, field) or
                field in ctx.metadata
            )
            self.assertTrue(
                has_field,
                f"Critical field '{field}' not found in context or metadata"
            )


if __name__ == '__main__':
    unittest.main()
