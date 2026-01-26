#!/usr/bin/env python3
"""
Standalone test runner for CoD v2 (no pytest required).

This script runs all tests without external dependencies.

Usage:
    CLAUDE_COD_V2=1 python rule_tagger2/cod_v2/run_tests.py
"""
import os
import sys
import traceback
from pathlib import Path

import chess

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from rule_tagger2.cod_v2 import (
    CoDContext,
    CoDMetrics,
    CoDSubtype,
    ControlOverDynamicsV2Detector,
)
from rule_tagger2.cod_v2.config import CoDThresholds, is_cod_v2_enabled


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def test(self, name: str, func):
        """Run a single test."""
        self.tests_run += 1
        try:
            func()
            self.tests_passed += 1
            print(f"  ✓ {name}")
        except AssertionError as e:
            self.tests_failed += 1
            self.failures.append((name, str(e)))
            print(f"  ✗ {name}: {e}")
        except Exception as e:
            self.tests_failed += 1
            self.failures.append((name, traceback.format_exc()))
            print(f"  ✗ {name}: {e}")

    def report(self):
        """Print test report."""
        print("\n" + "=" * 70)
        print(f"Tests run: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print("=" * 70)

        if self.failures:
            print("\nFailures:")
            for name, error in self.failures:
                print(f"\n{name}:")
                print(f"  {error}")

        return self.tests_failed == 0


def main():
    """Run all tests."""
    print("CoD v2 Test Suite")
    print("=" * 70)

    # Check feature flag
    if not is_cod_v2_enabled():
        print("\n❌ CLAUDE_COD_V2=1 not set!")
        print("Run with: CLAUDE_COD_V2=1 python rule_tagger2/cod_v2/run_tests.py")
        sys.exit(1)

    print("✓ Feature flag enabled\n")

    runner = TestRunner()

    # Test 1: Feature flag
    print("Feature Flag Tests:")

    def test_flag_enabled():
        assert is_cod_v2_enabled()

    runner.test("Feature flag is enabled", test_flag_enabled)

    # Test 2: Thresholds
    print("\nThreshold Tests:")

    def test_default_thresholds():
        t = CoDThresholds()
        assert t.tactical_weight_ceiling > 0
        assert t.volatility_drop_cp > 0

    runner.test("Default thresholds are valid", test_default_thresholds)

    def test_thresholds_to_dict():
        t = CoDThresholds()
        d = t.to_dict()
        assert isinstance(d, dict)
        assert "tactical_weight_ceiling" in d

    runner.test("Thresholds can be serialized", test_thresholds_to_dict)

    # Test 3: Detector initialization
    print("\nDetector Initialization Tests:")

    def test_detector_init():
        detector = ControlOverDynamicsV2Detector()
        assert detector.name == "ControlOverDynamicsV2"
        assert detector.thresholds is not None

    runner.test("Detector initializes correctly", test_detector_init)

    # Test 4: Basic detection
    print("\nBasic Detection Tests:")

    def test_no_detection_by_default():
        detector = ControlOverDynamicsV2Detector()
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        context = CoDContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            metrics=CoDMetrics(),
            current_ply=10,
        )
        result = detector.detect(context)
        assert not result.detected
        assert result.subtype == CoDSubtype.NONE

    runner.test("No detection with minimal metrics", test_no_detection_by_default)

    def test_tactical_gate():
        detector = ControlOverDynamicsV2Detector()
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        context = CoDContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            metrics=CoDMetrics(
                volatility_drop_cp=150.0,
                opp_mobility_drop=0.3,
            ),
            tactical_weight=0.9,  # Too high!
            current_ply=10,
        )
        result = detector.detect(context)
        assert not result.detected
        assert "tactical_gate" in result.gates_passed
        assert not result.gates_passed["tactical_gate"]

    runner.test("Tactical gate blocks detection", test_tactical_gate)

    # Test 5: Prophylaxis detection
    print("\nProphylaxis Detection Tests:")

    def test_prophylaxis_detection():
        detector = ControlOverDynamicsV2Detector()
        board = chess.Board()
        move = chess.Move.from_uci("d2d3")
        context = CoDContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            metrics=CoDMetrics(
                volatility_drop_cp=120.0,
                opp_mobility_drop=0.25,
                tension_delta=-0.15,
                preventive_score=0.35,
            ),
            tactical_weight=0.3,
            current_ply=10,
        )
        result = detector.detect(context)
        assert result.detected
        assert result.subtype == CoDSubtype.PROPHYLAXIS
        assert result.confidence > 0.5
        assert "control_over_dynamics" in result.tags

    runner.test("Prophylaxis detection works", test_prophylaxis_detection)

    # Test 6: Piece control detection
    print("\nPiece Control Detection Tests:")

    def test_piece_control():
        detector = ControlOverDynamicsV2Detector()
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        context = CoDContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            metrics=CoDMetrics(
                opp_mobility_drop=0.20,
                volatility_drop_cp=90.0,
                self_mobility_change=0.05,
            ),
            tactical_weight=0.4,
            current_ply=10,
        )
        result = detector.detect(context)
        assert result.detected
        assert result.subtype == CoDSubtype.PIECE_CONTROL

    runner.test("Piece control detection works", test_piece_control)

    # Test 7: Serialization
    print("\nSerialization Tests:")

    def test_result_serialization():
        detector = ControlOverDynamicsV2Detector()
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        context = CoDContext(
            board=board,
            played_move=move,
            actor=chess.WHITE,
            metrics=CoDMetrics(volatility_drop_cp=100.0),
            tactical_weight=0.3,
            current_ply=10,
        )
        result = detector.detect(context)
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "detected" in result_dict
        assert "subtype" in result_dict

    runner.test("Result serialization works", test_result_serialization)

    # Print report
    success = runner.report()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
