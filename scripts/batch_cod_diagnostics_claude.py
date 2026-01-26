#!/usr/bin/env python3
"""
Batch CoD Diagnostics Script (Claude Implementation)

This script runs Control over Dynamics v2 detection on a batch of positions
and generates detailed diagnostic reports.

IMPORTANT: This script is ISOLATED and does NOT modify any existing code.
It only runs when CLAUDE_COD_V2=1 is set.

Usage:
    CLAUDE_COD_V2=1 python scripts/batch_cod_diagnostics_claude.py --input positions.json
    CLAUDE_COD_V2=1 python scripts/batch_cod_diagnostics_claude.py --test-suite
    CLAUDE_COD_V2=1 python scripts/batch_cod_diagnostics_claude.py --compare-legacy
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import chess

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rule_tagger2.cod_v2 import (
    CoDContext,
    CoDMetrics,
    ControlOverDynamicsV2Detector,
)
from rule_tagger2.cod_v2.config import is_cod_v2_enabled


def check_feature_flag():
    """Ensure the feature flag is enabled."""
    if not is_cod_v2_enabled():
        print("❌ ERROR: CLAUDE_COD_V2=1 environment variable not set", file=sys.stderr)
        print("", file=sys.stderr)
        print("This script requires the CoD v2 feature flag to be enabled.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Usage:", file=sys.stderr)
        print("  CLAUDE_COD_V2=1 python scripts/batch_cod_diagnostics_claude.py [OPTIONS]", file=sys.stderr)
        sys.exit(1)


def create_test_cases() -> List[Dict[str, Any]]:
    """
    Create a set of test cases for CoD detection.

    Returns:
        List of test case dictionaries
    """
    return [
        {
            "id": "prophylaxis_strong",
            "name": "Strong Prophylaxis",
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "move": "d3",
            "expected_subtype": "prophylaxis",
            "metrics": {
                "volatility_drop_cp": 120.0,
                "opp_mobility_drop": 0.25,
                "tension_delta": -0.15,
                "preventive_score": 0.35,
                "tactical_weight": 0.3,
            },
        },
        {
            "id": "piece_control",
            "name": "Piece Control",
            "fen": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            "move": "exd5",
            "expected_subtype": "piece_control",
            "metrics": {
                "volatility_drop_cp": 90.0,
                "opp_mobility_drop": 0.20,
                "self_mobility_change": 0.05,
                "tactical_weight": 0.4,
            },
        },
        {
            "id": "pawn_control",
            "name": "Pawn Control",
            "fen": "rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 2 2",
            "move": "e4",
            "expected_subtype": "pawn_control",
            "metrics": {
                "opp_mobility_drop": 0.12,
                "tension_delta": -0.20,
                "volatility_drop_cp": 60.0,
                "tactical_weight": 0.35,
            },
        },
        {
            "id": "simplification",
            "name": "Simplification",
            "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 0 5",
            "move": "O-O",
            "expected_subtype": "simplification",
            "metrics": {
                "king_safety_gain": 0.25,
                "eval_drop_cp": 0.3,
                "tactical_weight": 0.25,
            },
        },
        {
            "id": "tactical_block",
            "name": "Tactical Block (Should Fail)",
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "move": "Ng5",
            "expected_subtype": "none",
            "metrics": {
                "volatility_drop_cp": 150.0,
                "opp_mobility_drop": 0.30,
                "tactical_weight": 0.9,  # Too high!
            },
        },
    ]


def run_diagnostic(
    detector: ControlOverDynamicsV2Detector,
    test_case: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run diagnostic on a single test case.

    Args:
        detector: CoD v2 detector instance
        test_case: Test case dictionary

    Returns:
        Diagnostic result dictionary
    """
    # Parse FEN and move
    board = chess.Board(test_case["fen"])
    move = chess.Move.from_uci(test_case["move"])

    # Create metrics from test case
    metrics_dict = test_case.get("metrics", {})
    metrics = CoDMetrics(
        volatility_drop_cp=metrics_dict.get("volatility_drop_cp", 0.0),
        opp_mobility_drop=metrics_dict.get("opp_mobility_drop", 0.0),
        self_mobility_change=metrics_dict.get("self_mobility_change", 0.0),
        tension_delta=metrics_dict.get("tension_delta", 0.0),
        preventive_score=metrics_dict.get("preventive_score", 0.0),
        king_safety_gain=metrics_dict.get("king_safety_gain", 0.0),
        eval_drop_cp=metrics_dict.get("eval_drop_cp", 0.0),
    )

    # Create context
    context = CoDContext(
        board=board,
        played_move=move,
        actor=board.turn,
        metrics=metrics,
        tactical_weight=metrics_dict.get("tactical_weight", 0.0),
        current_ply=10,
    )

    # Run detection
    result = detector.detect(context)

    # Check if result matches expectation
    expected = test_case.get("expected_subtype", "none")
    actual = result.subtype.value

    return {
        "test_case": test_case,
        "result": result.to_dict(),
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def print_diagnostic_report(diagnostics: List[Dict[str, Any]]):
    """
    Print a formatted diagnostic report.

    Args:
        diagnostics: List of diagnostic results
    """
    print("\n" + "=" * 80)
    print("CoD v2 Diagnostic Report")
    print("=" * 80)

    total = len(diagnostics)
    passed = sum(1 for d in diagnostics if d["passed"])

    print(f"\nTest Cases: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed / total * 100:.1f}%")

    print("\n" + "-" * 80)
    print("Individual Results:")
    print("-" * 80)

    for i, diag in enumerate(diagnostics, 1):
        tc = diag["test_case"]
        result = diag["result"]

        status = "✓" if diag["passed"] else "✗"
        print(f"\n{status} Test {i}: {tc['name']} ({tc['id']})")
        print(f"  FEN: {tc['fen']}")
        print(f"  Move: {tc['move']}")
        print(f"  Expected: {diag['expected']}")
        print(f"  Actual: {diag['actual']}")

        if result["detected"]:
            print(f"  Confidence: {result['confidence']:.2f}")
            print(f"  Tags: {', '.join(result['tags'])}")
        else:
            print(f"  Detection: None")
            if result["gates_failed"]:
                print(f"  Failed Gates: {', '.join(result['gates_failed'])}")

        # Show evidence
        if "evidence" in result and result["evidence"]:
            print(f"  Evidence:")
            for key, value in result["evidence"].items():
                if isinstance(value, float):
                    print(f"    {key}: {value:.3f}")
                else:
                    print(f"    {key}: {value}")

        # Show diagnostic info
        if not diag["passed"] and "diagnostic" in result:
            print(f"  Diagnostic:")
            for key, value in result["diagnostic"].items():
                print(f"    {key}: {value}")

    print("\n" + "=" * 80)


def save_json_report(diagnostics: List[Dict[str, Any]], output_path: Path):
    """
    Save diagnostic report as JSON.

    Args:
        diagnostics: List of diagnostic results
        output_path: Path to save JSON file
    """
    with open(output_path, "w") as f:
        json.dump(
            {
                "version": "2.0.0-alpha",
                "total_cases": len(diagnostics),
                "passed": sum(1 for d in diagnostics if d["passed"]),
                "diagnostics": diagnostics,
            },
            f,
            indent=2,
        )

    print(f"\n✓ JSON report saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CoD v2 Batch Diagnostics (Claude Implementation)"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input JSON file with test cases",
    )
    parser.add_argument(
        "--test-suite",
        action="store_true",
        help="Run built-in test suite",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("cod_v2_diagnostics.json"),
        help="Output JSON file for results",
    )
    parser.add_argument(
        "--compare-legacy",
        action="store_true",
        help="Compare with legacy CoD detection (not implemented yet)",
    )

    args = parser.parse_args()

    # Check feature flag
    check_feature_flag()

    print("✓ CoD v2 feature flag enabled")
    print(f"  CLAUDE_COD_V2={os.environ.get('CLAUDE_COD_V2')}")

    # Load test cases
    if args.input:
        print(f"\n→ Loading test cases from: {args.input}")
        with open(args.input) as f:
            test_cases = json.load(f)
    elif args.test_suite:
        print("\n→ Using built-in test suite")
        test_cases = create_test_cases()
    else:
        print("\n❌ ERROR: Either --input or --test-suite must be specified", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    print(f"  Loaded {len(test_cases)} test cases")

    # Create detector
    print("\n→ Creating CoD v2 detector")
    detector = ControlOverDynamicsV2Detector()
    print(f"  Detector: {detector.name} v{detector.version}")

    # Run diagnostics
    print("\n→ Running diagnostics...")
    diagnostics = []

    for i, tc in enumerate(test_cases, 1):
        print(f"  [{i}/{len(test_cases)}] {tc.get('name', tc.get('id', f'Case {i}'))}")
        try:
            diag = run_diagnostic(detector, tc)
            diagnostics.append(diag)
        except Exception as e:
            print(f"    ❌ Error: {e}")
            diagnostics.append({
                "test_case": tc,
                "error": str(e),
                "passed": False,
            })

    # Print report
    print_diagnostic_report(diagnostics)

    # Save JSON report
    save_json_report(diagnostics, args.output)

    # Exit with appropriate code
    all_passed = all(d.get("passed", False) for d in diagnostics)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
