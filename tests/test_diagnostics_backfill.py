"""
Test diagnostic information backfill to analysis_meta.

Verifies that suppressed_by, cooldown_hit, tension_support, and cod_support
are correctly written to analysis_context["engine_meta"].
"""
import os
import unittest

import chess

from rule_tagger2.orchestration.pipeline import TagDetectionPipeline


class TestDiagnosticsBackfill(unittest.TestCase):
    """Test diagnostic information is backfilled to analysis_meta."""

    def setUp(self):
        """Set up test pipeline."""
        # Disable CONTROL to avoid strict mode issues in tests
        os.environ["CONTROL_ENABLED"] = "0"
        os.environ["CONTROL_STRICT_MODE"] = "0"
        # Use use_legacy=False to trigger new detector path with diagnostics
        self.pipeline = TagDetectionPipeline(use_legacy=False)

    def test_tension_diagnostics_backfill(self):
        """Test TensionDetector diagnostics are backfilled when USE_NEW_TENSION=1."""
        os.environ["USE_NEW_TENSION"] = "1"

        # Test position with potential tension (middlegame)
        fen = "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        move = "d2d3"

        result = self.pipeline.run_pipeline(
            engine_path=os.environ.get("ENGINE", "/usr/local/bin/stockfish"),
            fen=fen,
            played_move_uci=move,
            depth=15,
            multipv=3,
        )

        # Verify analysis_context exists
        self.assertTrue(hasattr(result, "analysis_context"))
        self.assertIn("engine_meta", result.analysis_context)

        # Verify tension_v2_diagnostics was backfilled
        self.assertIn("tension_v2_diagnostics", result.analysis_context)
        tension_diag = result.analysis_context["tension_v2_diagnostics"]

        # Check diagnostic structure
        self.assertIn("tags_found", tension_diag)
        self.assertIn("diagnostic_info", tension_diag)
        self.assertIsInstance(tension_diag["tags_found"], list)
        self.assertIsInstance(tension_diag["diagnostic_info"], dict)

        # Verify tension_support is in engine_meta (if detected)
        if "tension_support" in result.analysis_context["engine_meta"]:
            tension_support = result.analysis_context["engine_meta"]["tension_support"]
            self.assertIsInstance(tension_support, dict)

    def test_prophylaxis_diagnostics_backfill(self):
        """Test ProphylaxisDetector diagnostics are backfilled when USE_NEW_COD=0."""
        os.environ["USE_NEW_TENSION"] = "0"
        os.environ["USE_NEW_COD"] = "0"  # Use ProphylaxisDetector

        # Test position with potential prophylaxis
        fen = "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 8"
        move = "h2h3"  # Preventive king safety move

        result = self.pipeline.run_pipeline(
            engine_path=os.environ.get("ENGINE", "/usr/local/bin/stockfish"),
            fen=fen,
            played_move_uci=move,
            depth=15,
            multipv=3,
        )

        # Convert result to dict if needed
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        elif hasattr(result, '__dict__'):
            result_dict = vars(result)
        elif isinstance(result, dict):
            result_dict = result
        else:
            self.fail(f"Unexpected result type: {type(result)}")

        # Verify analysis_context exists
        self.assertIn("analysis_context", result_dict)
        self.assertIn("engine_meta", result_dict["analysis_context"])

        # Verify prophylaxis_diagnostics was backfilled
        self.assertIn("prophylaxis_diagnostics", result_dict["analysis_context"])
        prop_diag = result_dict["analysis_context"]["prophylaxis_diagnostics"]

        # Check diagnostic structure
        self.assertIn("tags_found", prop_diag)
        self.assertIn("diagnostic_info", prop_diag)
        self.assertIsInstance(prop_diag["tags_found"], list)
        self.assertIsInstance(prop_diag["diagnostic_info"], dict)

        # Verify cod_support is in engine_meta
        self.assertIn("cod_support", result_dict["analysis_context"]["engine_meta"])
        cod_support = result_dict["analysis_context"]["engine_meta"]["cod_support"]

        # Check cod_support structure
        self.assertIn("suppressed_by", cod_support)
        self.assertIn("cooldown_hit", cod_support)
        self.assertIn("all_detected", cod_support)
        self.assertIn("gate_log", cod_support)

        # Verify types
        self.assertIsInstance(cod_support["suppressed_by"], list)
        self.assertIsInstance(cod_support["cooldown_hit"], bool)
        self.assertIsInstance(cod_support["all_detected"], list)
        self.assertIsInstance(cod_support["gate_log"], dict)

    def test_cod_v2_diagnostics_backfill(self):
        """Test ControlOverDynamicsV2 diagnostics are backfilled when USE_NEW_COD=1."""
        os.environ["USE_NEW_TENSION"] = "0"
        os.environ["USE_NEW_COD"] = "1"  # Use CoD v2

        # Test position with potential control dynamics
        fen = "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 8"
        move = "h2h3"

        result = self.pipeline.run_pipeline(
            engine_path=os.environ.get("ENGINE", "/usr/local/bin/stockfish"),
            fen=fen,
            played_move_uci=move,
            depth=15,
            multipv=3,
        )

        # Verify analysis_context exists
        self.assertTrue(hasattr(result, "analysis_context"))
        self.assertIn("engine_meta", result.analysis_context)

        # Verify cod_v2_result was backfilled
        self.assertIn("cod_v2_result", result.analysis_context)
        cod_v2 = result.analysis_context["cod_v2_result"]

        # Check CoD v2 diagnostic structure
        self.assertIn("detected", cod_v2)
        self.assertIn("subtype", cod_v2)
        self.assertIn("gates_passed", cod_v2)
        self.assertIn("gates_failed", cod_v2)
        self.assertIn("diagnostic", cod_v2)

        # Verify types
        self.assertIsInstance(cod_v2["detected"], bool)
        self.assertIsInstance(cod_v2["subtype"], str)
        self.assertIsInstance(cod_v2["gates_passed"], list)
        self.assertIsInstance(cod_v2["gates_failed"], list)
        self.assertIsInstance(cod_v2["diagnostic"], dict)

    def test_pipeline_metadata_tracking(self):
        """Test pipeline metadata tracks which detectors were used."""
        os.environ["USE_NEW_TENSION"] = "1"
        os.environ["USE_NEW_COD"] = "0"

        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        move = "e2e4"

        result = self.pipeline.run_pipeline(
            engine_path=os.environ.get("ENGINE", "/usr/local/bin/stockfish"),
            fen=fen,
            played_move_uci=move,
            depth=15,
            multipv=3,
        )

        # Verify pipeline metadata
        engine_meta = result.analysis_context["engine_meta"]
        self.assertEqual(engine_meta["__pipeline_mode__"], "hybrid_p2_day3")
        self.assertTrue(engine_meta["__tension_detector_v2__"])
        self.assertTrue(engine_meta["__prophylaxis_detector_v2__"])
        self.assertIn("TensionDetector", engine_meta["__new_detectors__"])
        self.assertIn("ProphylaxisDetector", engine_meta["__new_detectors__"])


if __name__ == "__main__":
    unittest.main()
