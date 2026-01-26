"""
Regression Alignment Test for Tension/COD Detectors.

This script compares legacy vs new detector outputs and generates:
- Trigger rate comparison (legacy vs new)
- Precision/Recall metrics
- Notes coverage comparison
- Detailed diagnostic output

Usage:
    # Test Tension detector
    python3 scripts/regression_alignment_test.py --detector tension --sample-size 100

    # Test CoD detector
    python3 scripts/regression_alignment_test.py --detector cod --sample-size 100

    # Test both with custom game file
    python3 scripts/regression_alignment_test.py --detector both --games my_games.pgn
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from rule_tagger2.core.facade import tag_position


class RegressionTester:
    """Test framework for comparing legacy vs new detectors."""

    def __init__(self, detector: str, sample_size: int = 100):
        """
        Initialize tester.

        Args:
            detector: "tension", "cod", or "both"
            sample_size: Number of positions to test
        """
        self.detector = detector
        self.sample_size = sample_size
        self.engine_path = os.getenv("ENGINE", "/usr/local/bin/stockfish")

        # Test cases (will load from file or use defaults)
        self.test_cases: List[Dict] = []

        # Results tracking
        self.results: Dict[str, Dict] = {
            "tension": {"legacy": [], "new": []},
            "cod": {"legacy": [], "new": []},
        }

    def load_test_cases(self, games_file: str = None):
        """
        Load test cases from PGN file or use defaults.

        Args:
            games_file: Optional path to PGN file with games
        """
        if games_file and Path(games_file).exists():
            print(f"Loading test cases from {games_file}...")
            # TODO: Parse PGN and extract positions
            # For now, use default test cases
            self._load_default_cases()
        else:
            print("Using default test cases...")
            self._load_default_cases()

    def _load_default_cases(self):
        """Load default test cases covering various scenarios."""
        # Starting position
        self.test_cases.append({
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move": "e2e4",
            "description": "Opening e4 - should NOT trigger neutral_tension (no evidence)"
        })

        # Middlegame tactical position
        self.test_cases.append({
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "move": "d2d3",
            "description": "Middlegame quiet move"
        })

        # Position with tension
        self.test_cases.append({
            "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
            "move": "d2d4",
            "description": "Central tension creation"
        })

        # Position with control dynamics
        self.test_cases.append({
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "move": "b1c3",
            "description": "Development with control"
        })

        # Endgame position
        self.test_cases.append({
            "fen": "8/5k2/8/3K4/8/8/8/8 w - - 0 1",
            "move": "d5e5",
            "description": "King endgame"
        })

        # Limit to sample size
        self.test_cases = self.test_cases[:self.sample_size]
        print(f"Loaded {len(self.test_cases)} test cases")

    def run_tests(self):
        """Run all test cases and collect results."""
        print(f"\nRunning tests for {self.detector} detector...")
        print(f"Engine: {self.engine_path}")
        print("=" * 80)

        for i, case in enumerate(self.test_cases, 1):
            print(f"\n[{i}/{len(self.test_cases)}] {case['description']}")
            print(f"  FEN: {case['fen'][:50]}...")
            print(f"  Move: {case['move']}")

            # Run legacy
            if self.detector in ["tension", "both"]:
                legacy_result = self._run_legacy_tension(case)
                new_result = self._run_new_tension(case)
                self.results["tension"]["legacy"].append(legacy_result)
                self.results["tension"]["new"].append(new_result)

            if self.detector in ["cod", "both"]:
                legacy_cod = self._run_legacy_cod(case)
                new_cod = self._run_new_cod(case)
                self.results["cod"]["legacy"].append(legacy_cod)
                self.results["cod"]["new"].append(new_cod)

        print("\n" + "=" * 80)
        print("Tests complete!")

    def _run_legacy_tension(self, case: Dict) -> Dict:
        """Run legacy tension detector."""
        try:
            # Disable new detectors
            os.environ["USE_NEW_TENSION"] = "0"
            result = tag_position(
                engine_path=self.engine_path,
                fen=case["fen"],
                played_move_uci=case["move"],
                use_new=True,  # Use hybrid pipeline but with legacy detector
            )
            return {
                "tension_creation": result.tension_creation,
                "neutral_tension_creation": result.neutral_tension_creation,
                "notes": getattr(result, 'notes', {}),
                "error": None,
            }
        except Exception as e:
            return {
                "tension_creation": False,
                "neutral_tension_creation": False,
                "notes": {},
                "error": str(e),
            }

    def _run_new_tension(self, case: Dict) -> Dict:
        """Run new tension detector."""
        try:
            # Enable new detector
            os.environ["USE_NEW_TENSION"] = "1"
            result = tag_position(
                engine_path=self.engine_path,
                fen=case["fen"],
                played_move_uci=case["move"],
                use_new=True,
            )
            return {
                "tension_creation": result.tension_creation,
                "neutral_tension_creation": result.neutral_tension_creation,
                "notes": getattr(result, 'notes', {}),
                "error": None,
            }
        except Exception as e:
            return {
                "tension_creation": False,
                "neutral_tension_creation": False,
                "notes": {},
                "error": str(e),
            }

    def _run_legacy_cod(self, case: Dict) -> Dict:
        """Run legacy CoD detector (ProphylaxisDetector)."""
        try:
            os.environ["USE_NEW_COD"] = "0"
            result = tag_position(
                engine_path=self.engine_path,
                fen=case["fen"],
                played_move_uci=case["move"],
                use_new=True,
            )
            return {
                "control_over_dynamics": result.control_over_dynamics,
                "notes": getattr(result, 'notes', {}),
                "error": None,
            }
        except Exception as e:
            return {
                "control_over_dynamics": False,
                "notes": {},
                "error": str(e),
            }

    def _run_new_cod(self, case: Dict) -> Dict:
        """Run new CoD v2 detector."""
        try:
            os.environ["USE_NEW_COD"] = "1"
            result = tag_position(
                engine_path=self.engine_path,
                fen=case["fen"],
                played_move_uci=case["move"],
                use_new=True,
            )
            return {
                "control_over_dynamics": result.control_over_dynamics,
                "notes": getattr(result, 'notes', {}),
                "error": None,
            }
        except Exception as e:
            return {
                "control_over_dynamics": False,
                "notes": {},
                "error": str(e),
            }

    def generate_report(self) -> str:
        """
        Generate comparison report.

        Returns:
            Report as formatted string
        """
        lines = []
        lines.append("\n" + "=" * 80)
        lines.append("REGRESSION ALIGNMENT TEST REPORT")
        lines.append("=" * 80)

        if self.detector in ["tension", "both"]:
            lines.append("\n## TENSION DETECTOR COMPARISON")
            lines.append("-" * 80)
            report = self._compare_tension()
            lines.append(report)

        if self.detector in ["cod", "both"]:
            lines.append("\n## CONTROL OVER DYNAMICS DETECTOR COMPARISON")
            lines.append("-" * 80)
            report = self._compare_cod()
            lines.append(report)

        return "\n".join(lines)

    def _compare_tension(self) -> str:
        """Compare tension detector results."""
        legacy = self.results["tension"]["legacy"]
        new = self.results["tension"]["new"]

        # Count triggers
        legacy_tension_count = sum(1 for r in legacy if r["tension_creation"])
        new_tension_count = sum(1 for r in new if r["tension_creation"])
        legacy_neutral_count = sum(1 for r in legacy if r["neutral_tension_creation"])
        new_neutral_count = sum(1 for r in new if r["neutral_tension_creation"])

        # Calculate agreement
        tension_matches = sum(1 for l, n in zip(legacy, new) if l["tension_creation"] == n["tension_creation"])
        neutral_matches = sum(1 for l, n in zip(legacy, new) if l["neutral_tension_creation"] == n["neutral_tension_creation"])

        total = len(legacy)

        # Precision/Recall (using legacy as ground truth)
        tp_tension = sum(1 for l, n in zip(legacy, new) if l["tension_creation"] and n["tension_creation"])
        fp_tension = sum(1 for l, n in zip(legacy, new) if not l["tension_creation"] and n["tension_creation"])
        fn_tension = sum(1 for l, n in zip(legacy, new) if l["tension_creation"] and not n["tension_creation"])

        tp_neutral = sum(1 for l, n in zip(legacy, new) if l["neutral_tension_creation"] and n["neutral_tension_creation"])
        fp_neutral = sum(1 for l, n in zip(legacy, new) if not l["neutral_tension_creation"] and n["neutral_tension_creation"])
        fn_neutral = sum(1 for l, n in zip(legacy, new) if l["neutral_tension_creation"] and not n["neutral_tension_creation"])

        precision_tension = tp_tension / (tp_tension + fp_tension) if (tp_tension + fp_tension) > 0 else 0.0
        recall_tension = tp_tension / (tp_tension + fn_tension) if (tp_tension + fn_tension) > 0 else 0.0

        precision_neutral = tp_neutral / (tp_neutral + fp_neutral) if (tp_neutral + fp_neutral) > 0 else 0.0
        recall_neutral = tp_neutral / (tp_neutral + fn_neutral) if (tp_neutral + fn_neutral) > 0 else 0.0

        # Notes coverage
        legacy_notes_count = sum(1 for r in legacy if "tension_creation" in r["notes"] or "neutral_tension_creation" in r["notes"])
        new_notes_count = sum(1 for r in new if "tension_creation" in r["notes"] or "neutral_tension_creation" in r["notes"])

        lines = []
        lines.append(f"\nTrigger Rates:")
        lines.append(f"  tension_creation:")
        lines.append(f"    Legacy: {legacy_tension_count}/{total} ({100*legacy_tension_count/total:.1f}%)")
        lines.append(f"    New:    {new_tension_count}/{total} ({100*new_tension_count/total:.1f}%)")
        lines.append(f"    Match:  {tension_matches}/{total} ({100*tension_matches/total:.1f}%)")
        lines.append(f"\n  neutral_tension_creation:")
        lines.append(f"    Legacy: {legacy_neutral_count}/{total} ({100*legacy_neutral_count/total:.1f}%)")
        lines.append(f"    New:    {new_neutral_count}/{total} ({100*new_neutral_count/total:.1f}%)")
        lines.append(f"    Match:  {neutral_matches}/{total} ({100*neutral_matches/total:.1f}%)")

        lines.append(f"\nPrecision & Recall (legacy as ground truth):")
        lines.append(f"  tension_creation:")
        lines.append(f"    Precision: {precision_tension:.3f} (TP={tp_tension}, FP={fp_tension})")
        lines.append(f"    Recall:    {recall_tension:.3f} (TP={tp_tension}, FN={fn_tension})")
        lines.append(f"\n  neutral_tension_creation:")
        lines.append(f"    Precision: {precision_neutral:.3f} (TP={tp_neutral}, FP={fp_neutral})")
        lines.append(f"    Recall:    {recall_neutral:.3f} (TP={tp_neutral}, FN={fn_neutral})")

        lines.append(f"\nNotes Coverage:")
        lines.append(f"  Legacy: {legacy_notes_count}/{total} ({100*legacy_notes_count/total:.1f}%)")
        lines.append(f"  New:    {new_notes_count}/{total} ({100*new_notes_count/total:.1f}%)")

        return "\n".join(lines)

    def _compare_cod(self) -> str:
        """Compare CoD detector results."""
        legacy = self.results["cod"]["legacy"]
        new = self.results["cod"]["new"]

        # Count triggers
        legacy_count = sum(1 for r in legacy if r["control_over_dynamics"])
        new_count = sum(1 for r in new if r["control_over_dynamics"])

        # Calculate agreement
        matches = sum(1 for l, n in zip(legacy, new) if l["control_over_dynamics"] == n["control_over_dynamics"])
        total = len(legacy)

        # Precision/Recall
        tp = sum(1 for l, n in zip(legacy, new) if l["control_over_dynamics"] and n["control_over_dynamics"])
        fp = sum(1 for l, n in zip(legacy, new) if not l["control_over_dynamics"] and n["control_over_dynamics"])
        fn = sum(1 for l, n in zip(legacy, new) if l["control_over_dynamics"] and not n["control_over_dynamics"])

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        # Notes coverage
        legacy_notes = sum(1 for r in legacy if "control_over_dynamics" in r["notes"])
        new_notes = sum(1 for r in new if "control_over_dynamics" in r["notes"])

        lines = []
        lines.append(f"\nTrigger Rates:")
        lines.append(f"  control_over_dynamics:")
        lines.append(f"    Legacy: {legacy_count}/{total} ({100*legacy_count/total:.1f}%)")
        lines.append(f"    New:    {new_count}/{total} ({100*new_count/total:.1f}%)")
        lines.append(f"    Match:  {matches}/{total} ({100*matches/total:.1f}%)")

        lines.append(f"\nPrecision & Recall (legacy as ground truth):")
        lines.append(f"  Precision: {precision:.3f} (TP={tp}, FP={fp})")
        lines.append(f"  Recall:    {recall:.3f} (TP={tp}, FN={fn})")

        lines.append(f"\nNotes Coverage:")
        lines.append(f"  Legacy: {legacy_notes}/{total} ({100*legacy_notes/total:.1f}%)")
        lines.append(f"  New:    {new_notes}/{total} ({100*new_notes/total:.1f}%)")

        return "\n".join(lines)

    def save_results(self, output_path: str):
        """Save detailed results to JSON file."""
        data = {
            "detector": self.detector,
            "sample_size": len(self.test_cases),
            "test_cases": self.test_cases,
            "results": self.results,
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\nDetailed results saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Regression alignment test for detectors")
    parser.add_argument(
        "--detector",
        choices=["tension", "cod", "both"],
        default="tension",
        help="Which detector to test (default: tension)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="Number of test positions (default: 5)",
    )
    parser.add_argument(
        "--games",
        type=str,
        help="Path to PGN file with games (optional)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for detailed results (default: reports/regression_test_{detector}.json)",
    )

    args = parser.parse_args()

    # Auto-generate output path based on detector if not specified
    if args.output is None:
        import os
        os.makedirs("reports", exist_ok=True)
        args.output = f"reports/regression_test_{args.detector}.json"

    # Create tester
    tester = RegressionTester(detector=args.detector, sample_size=args.sample_size)

    # Load test cases
    tester.load_test_cases(games_file=args.games)

    # Run tests
    tester.run_tests()

    # Generate and print report
    report = tester.generate_report()
    print(report)

    # Save results
    tester.save_results(args.output)

    print("\n✅ Regression test complete!")


if __name__ == "__main__":
    main()
