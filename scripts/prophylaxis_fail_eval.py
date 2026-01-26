"""
Prophylaxis Failure Evaluation Script

This script analyzes a set of positions to evaluate the effectiveness of
prophylactic move detection and measure the failure rate (false positives).

It reports:
- Total prophylactic moves detected
- Number of failed prophylactic moves (strong opponent refutation found)
- Failure rate (percentage)
- Sample list of failed cases with details

Usage:
    python3 scripts/prophylaxis_fail_eval.py --sample-size 20 --verbose
    python3 scripts/prophylaxis_fail_eval.py --input tests/golden_cases/cases.json

Environment variables:
- ENGINE: Path to chess engine (default: /usr/local/bin/stockfish)
- PROPHY_FAIL_CP: Evaluation drop threshold (default: 50)
- PROPHY_FAIL_TOPN: Number of top moves to check (default: 3)
"""
import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import chess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rule_tagger2.core.facade import tag_position


@dataclass
class ProhylaxisCase:
    """Represents a test case for prophylaxis evaluation."""
    fen: str
    move: str
    description: str
    phase: str = "middlegame"


@dataclass
class EvalResult:
    """Results from evaluating a single prophylactic move."""
    case_id: int
    fen: str
    move: str
    description: str
    prophylactic_detected: bool
    failed: bool
    eval_drop_cp: int
    failing_move: str
    threshold_cp: int


class ProphylaxisFailEvaluator:
    """Evaluates prophylactic moves and measures failure rate."""

    def __init__(self, engine_path: str, sample_size: int = 20, verbose: bool = False):
        """
        Initialize evaluator.

        Args:
            engine_path: Path to chess engine
            sample_size: Number of test cases to evaluate
            verbose: Print detailed output
        """
        self.engine_path = engine_path
        self.sample_size = sample_size
        self.verbose = verbose
        self.results: List[EvalResult] = []

    def load_test_cases(self, input_file: str = None) -> List[ProhylaxisCase]:
        """
        Load test cases from file or generate defaults.

        Args:
            input_file: Optional path to JSON file with test cases

        Returns:
            List of ProhylaxisCase objects
        """
        if input_file and os.path.exists(input_file):
            with open(input_file, "r") as f:
                data = json.load(f)

            # Parse golden cases format (list of test cases)
            cases = []
            for item in data:
                # Filter for cases with prophylactic_move in expected_tags
                expected = item.get("expected_tags", [])
                if "prophylactic_move" in expected or "failed_prophylactic" in expected:
                    # Convert SAN to UCI if needed
                    move_str = item["move"]
                    # Check if it's already UCI (4-5 chars, starting with a letter followed by a digit)
                    is_uci = len(move_str) in [4, 5] and move_str[0].islower() and move_str[1].isdigit()
                    if not is_uci:
                        # Looks like SAN, need to convert to UCI
                        board = chess.Board(item["fen"])
                        try:
                            move = board.parse_san(move_str)
                            move_str = move.uci()
                        except Exception as e:
                            # If conversion fails, keep original
                            if self.verbose:
                                print(f"  Warning: Could not convert move '{move_str}': {e}")
                            pass

                    cases.append(ProhylaxisCase(
                        fen=item["fen"],
                        move=move_str,
                        description=item.get("description", ""),
                        phase=item.get("phase", "middlegame")
                    ))

            if cases:
                print(f"📝 Loaded {len(cases)} prophylactic cases from {input_file}")
                return cases[:self.sample_size]
            else:
                print(f"⚠️  No prophylactic cases found in {input_file}, using defaults")
                cases = self._default_test_cases()
        else:
            cases = self._default_test_cases()

        return cases[:self.sample_size]

    def _default_test_cases(self) -> List[ProhylaxisCase]:
        """Generate default test cases with prophylactic themes."""
        return [
            ProhylaxisCase(
                fen="r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 5 5",
                move="d2d3",
                description="Quiet prophylactic pawn move preventing Ng4",
                phase="opening"
            ),
            ProhylaxisCase(
                fen="r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQ - 0 7",
                move="h2h3",
                description="Luft move (h3) preventing back rank threats",
                phase="middlegame"
            ),
            ProhylaxisCase(
                fen="r2q1rk1/ppp2ppp/2np1n2/2b1p1B1/2B1P3/2NP1N2/PPP2PPP/R2QK2R w KQ - 0 9",
                move="c1e3",
                description="Bishop retreat preventing pin",
                phase="middlegame"
            ),
            ProhylaxisCase(
                fen="r1bqk2r/pppp1ppp/2n2n2/4p3/1bB1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 4 6",
                move="a2a3",
                description="a3 forcing bishop decision",
                phase="opening"
            ),
            ProhylaxisCase(
                fen="r2qk2r/ppp2ppp/2np1n2/2b1p1B1/2B1P1b1/2NP1N2/PPP2PPP/R2QK2R w KQkq - 2 8",
                move="f1e1",
                description="Rook to e1 adding pressure/defense",
                phase="middlegame"
            ),
        ]

    def evaluate(self, input_file: str = None) -> Dict[str, Any]:
        """
        Run evaluation on all test cases.

        Args:
            input_file: Optional path to test cases JSON

        Returns:
            Dictionary with evaluation metrics
        """
        cases = self.load_test_cases(input_file)

        print(f"Evaluating {len(cases)} prophylactic positions...")
        print(f"Threshold: {os.getenv('PROPHY_FAIL_CP', '50')}cp")
        print(f"Top-N checked: {os.getenv('PROPHY_FAIL_TOPN', '3')}")
        print()

        for idx, case in enumerate(cases):
            if self.verbose:
                print(f"[{idx+1}/{len(cases)}] {case.description}")

            result = self._evaluate_case(idx, case)
            self.results.append(result)

            if self.verbose and result.prophylactic_detected:
                status = "FAILED" if result.failed else "PASSED"
                print(f"  → {status} (Δcp: {result.eval_drop_cp})")

        return self._generate_summary()

    def _evaluate_case(self, case_id: int, case: ProhylaxisCase) -> EvalResult:
        """
        Evaluate a single prophylactic case.

        Args:
            case_id: Case index
            case: ProhylaxisCase to evaluate

        Returns:
            EvalResult with detection and failure status
        """
        try:
            # Call tag_position with the real pipeline
            result = tag_position(
                engine_path=self.engine_path,
                fen=case.fen,
                played_move_uci=case.move,
                use_new=True,  # Use new detector pipeline
            )

            # Extract prophylactic detection status
            prophylactic_detected = getattr(result, "prophylactic_move", False)

            # Extract failed_prophylactic status
            failed = getattr(result, "failed_prophylactic", False)

            # Extract diagnostics from analysis_context
            analysis_ctx = getattr(result, "analysis_context", {})
            prophy_diag = analysis_ctx.get("prophylaxis_diagnostics", {})
            failure_check = prophy_diag.get("failure_check", {})

            eval_drop_cp = failure_check.get("worst_eval_drop_cp", 0)
            failing_move = failure_check.get("failing_move_uci", "")

            return EvalResult(
                case_id=case_id,
                fen=case.fen,
                move=case.move,
                description=case.description,
                prophylactic_detected=prophylactic_detected,
                failed=failed,
                eval_drop_cp=eval_drop_cp,
                failing_move=failing_move,
                threshold_cp=int(os.getenv("PROPHY_FAIL_CP", "50")),
            )

        except Exception as e:
            # Handle errors gracefully
            if self.verbose:
                print(f"  ⚠️  Error evaluating case: {e}")
                import traceback
                traceback.print_exc()

            return EvalResult(
                case_id=case_id,
                fen=case.fen,
                move=case.move,
                description=case.description,
                prophylactic_detected=False,
                failed=False,
                eval_drop_cp=0,
                failing_move="",
                threshold_cp=int(os.getenv("PROPHY_FAIL_CP", "50")),
            )

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate evaluation summary statistics."""
        total_cases = len(self.results)
        prophylactic_detected = sum(1 for r in self.results if r.prophylactic_detected)
        failed_count = sum(1 for r in self.results if r.failed)

        failure_rate = (failed_count / prophylactic_detected * 100) if prophylactic_detected > 0 else 0.0

        failed_cases = [
            {
                "case_id": r.case_id,
                "description": r.description,
                "move": r.move,
                "eval_drop_cp": r.eval_drop_cp,
                "failing_move": r.failing_move,
            }
            for r in self.results if r.failed
        ]

        summary = {
            "total_cases": total_cases,
            "prophylactic_detected": prophylactic_detected,
            "failed_count": failed_count,
            "failure_rate_pct": round(failure_rate, 2),
            "threshold_cp": int(os.getenv("PROPHY_FAIL_CP", "50")),
            "failed_cases": failed_cases,
            "timestamp": datetime.now().isoformat(),
        }

        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """Print human-readable summary."""
        print("\n" + "="*60)
        print("PROPHYLAXIS FAILURE EVALUATION SUMMARY")
        print("="*60)
        print(f"Total cases evaluated:       {summary['total_cases']}")
        print(f"Prophylactic moves detected: {summary['prophylactic_detected']}")
        print(f"Failed prophylactic moves:   {summary['failed_count']}")
        print(f"Failure rate:                {summary['failure_rate_pct']}%")
        print(f"Eval drop threshold:         {summary['threshold_cp']}cp")
        print()

        if summary['failed_cases']:
            print("FAILED CASES:")
            print("-" * 60)
            for case in summary['failed_cases']:
                print(f"[{case['case_id']}] {case['description']}")
                print(f"    Move: {case['move']} | Drop: {case['eval_drop_cp']}cp | Refutation: {case['failing_move']}")
                print()
        else:
            print("✅ No failed prophylactic moves detected!")

    def export_json(self, output_file: str, summary: Dict[str, Any]):
        """Export results to JSON file."""
        with open(output_file, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n📝 Results exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate prophylactic move detection and measure failure rate"
    )
    parser.add_argument(
        "--engine",
        type=str,
        default=os.getenv("ENGINE", "/usr/local/bin/stockfish"),
        help="Path to chess engine"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Number of test cases to evaluate (default: 20)"
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to JSON file with test cases (optional)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: reports/prophylaxis_fail_eval_{timestamp}.json)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output during evaluation"
    )

    args = parser.parse_args()

    # Set default output path
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"reports/prophylaxis_fail_eval_{timestamp}.json"

    # Create reports directory if needed
    os.makedirs("reports", exist_ok=True)

    evaluator = ProphylaxisFailEvaluator(
        engine_path=args.engine,
        sample_size=args.sample_size,
        verbose=args.verbose,
    )

    summary = evaluator.evaluate(input_file=args.input)
    evaluator.print_summary(summary)
    evaluator.export_json(args.output, summary)


if __name__ == "__main__":
    main()
