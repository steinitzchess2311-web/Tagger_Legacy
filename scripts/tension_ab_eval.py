#!/usr/bin/env python3
"""
Tension A/B Evaluation Script

Compares old vs new tension boundary (USE_SPLIT_TENSION_V2) and generates:
- Trigger rate comparison (legacy vs v2 boundary)
- Precision/Recall metrics (using legacy as baseline)
- Notes coverage comparison
- Neutral/Tension ratio analysis
- Detailed diagnostic output with sample positions

Output: reports/tension_ab_{YYYYMMDD_HHMMSS}.json

Usage:
    # Run with default test cases
    python3 scripts/tension_ab_eval.py --sample-size 50

    # Run with custom output path
    python3 scripts/tension_ab_eval.py --sample-size 100 --output my_report.json

    # Run in verbose mode
    python3 scripts/tension_ab_eval.py --sample-size 50 --verbose
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from rule_tagger2.core.facade import tag_position


class TensionABEvaluator:
    """A/B test framework for tension boundary versions."""

    def __init__(self, sample_size: int = 50, verbose: bool = False):
        """
        Initialize evaluator.

        Args:
            sample_size: Number of positions to test
            verbose: Enable verbose output
        """
        self.sample_size = sample_size
        self.verbose = verbose
        self.engine_path = os.getenv("ENGINE", "/usr/local/bin/stockfish")

        # Test cases
        self.test_cases: List[Dict] = []

        # Results tracking
        self.results = {
            "legacy": [],  # USE_SPLIT_TENSION_V2=0
            "v2": [],      # USE_SPLIT_TENSION_V2=1
        }

    def load_test_cases(self):
        """Load test cases covering various game phases and tension scenarios."""
        print("Loading test cases...")

        # Opening positions (low tension, book moves)
        self.test_cases.extend([
            {
                "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "move": "e2e4",
                "description": "Opening e4 - should NOT trigger (no evidence)",
                "phase": "opening",
            },
            {
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "move": "c7c5",
                "description": "Sicilian Defense c5 - minimal tension",
                "phase": "opening",
            },
            {
                "fen": "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2",
                "move": "g1f3",
                "description": "Nf3 development - quiet",
                "phase": "opening",
            },
        ])

        # Middlegame positions (various tension levels)
        self.test_cases.extend([
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
                "move": "d2d4",
                "description": "Central tension creation d4 - high tension",
                "phase": "middlegame",
            },
            {
                "fen": "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 1 2",
                "move": "c2c4",
                "description": "c4 space control - moderate tension",
                "phase": "middlegame",
            },
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "move": "d2d3",
                "description": "d3 quiet consolidation - low tension",
                "phase": "middlegame",
            },
            {
                "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 5",
                "move": "b1c3",
                "description": "Nc3 development - neutral dynamics",
                "phase": "middlegame",
            },
            {
                "fen": "r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQ - 6 6",
                "move": "c1g5",
                "description": "Bg5 pin - active tension",
                "phase": "middlegame",
            },
        ])

        # Endgame positions (king activity, pawn breaks)
        self.test_cases.extend([
            {
                "fen": "8/5k2/8/3K4/8/8/8/8 w - - 0 1",
                "move": "d5e5",
                "description": "King endgame Ke5 - low complexity",
                "phase": "endgame",
            },
            {
                "fen": "8/4kp2/8/3KP3/8/8/8/8 w - - 0 1",
                "move": "e5e6",
                "description": "Pawn break e6 - forcing",
                "phase": "endgame",
            },
            {
                "fen": "8/4kp2/4p3/3K4/8/8/8/8 w - - 0 1",
                "move": "d5e5",
                "description": "King centralization - neutral",
                "phase": "endgame",
            },
        ])

        # Tactical positions (forcing moves, threats)
        self.test_cases.extend([
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "move": "e1g1",
                "description": "Castling O-O - safety move",
                "phase": "middlegame",
            },
            {
                "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R b KQkq - 0 4",
                "move": "d7d6",
                "description": "d6 solid defense - preventive",
                "phase": "middlegame",
            },
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "move": "f1c4",
                "description": "Bc4 Italian Game - developing with pressure",
                "phase": "opening",
            },
        ])

        # Total built-in cases: 14
        built_in_count = len(self.test_cases)

        # If sample_size exceeds built-in cases, try to load from external file
        if self.sample_size > built_in_count:
            loaded_extra = self._load_extra_positions(self.sample_size - built_in_count)
            if loaded_extra > 0:
                print(f"📝 Loaded {loaded_extra} additional positions from external source")
            else:
                print(f"⚠️  Warning: Requested {self.sample_size} samples but only {built_in_count} available")
                print(f"   (No external position file found)")

        # Limit to sample size
        self.test_cases = self.test_cases[:self.sample_size]
        print(f"✅ Loaded {len(self.test_cases)} test cases")

    def _load_extra_positions(self, count: int) -> int:
        """
        Load additional positions from external file if available.

        Args:
            count: Number of additional positions needed

        Returns:
            Number of positions actually loaded
        """
        # Try common position files
        position_files = [
            "tests/positions.json",
            "tests/golden_cases/cases.json",
            "tests/golden_cases.json",  # legacy fallback
            "data/test_positions.json",
        ]

        for file_path in position_files:
            if not Path(file_path).exists():
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract positions (handle different formats)
                positions = []
                if isinstance(data, list):
                    positions = data
                elif isinstance(data, dict):
                    # Try common keys
                    for key in ["positions", "test_cases", "cases"]:
                        if key in data:
                            positions = data[key]
                            break

                # Convert to our format
                loaded = 0
                for pos in positions[:count]:
                    # Skip if missing required fields
                    if not all(k in pos for k in ["fen", "move"]):
                        continue

                    # Determine phase from FEN if not provided
                    phase = pos.get("phase", "middlegame")

                    self.test_cases.append({
                        "fen": pos["fen"],
                        "move": pos["move"],
                        "description": pos.get("description", f"Position from {file_path}"),
                        "phase": phase,
                    })
                    loaded += 1

                    if loaded >= count:
                        break

                if loaded > 0:
                    return loaded

            except (json.JSONDecodeError, KeyError) as e:
                # Skip this file and try next
                continue

        return 0

    def run_evaluation(self):
        """Run all test cases and collect results."""
        print(f"\n{'='*80}")
        print(f"TENSION A/B EVALUATION")
        print(f"{'='*80}")
        print(f"Engine: {self.engine_path}")
        print(f"Sample size: {len(self.test_cases)}")
        print(f"{'='*80}\n")

        for i, case in enumerate(self.test_cases, 1):
            if self.verbose:
                print(f"\n[{i}/{len(self.test_cases)}] {case['description']}")
                print(f"  Phase: {case['phase']}")
                print(f"  FEN: {case['fen'][:60]}...")
                print(f"  Move: {case['move']}")

            # Run with legacy boundary (USE_SPLIT_TENSION_V2=0)
            legacy_result = self._run_with_boundary(case, boundary_version="legacy")
            self.results["legacy"].append(legacy_result)

            # Run with v2 boundary (USE_SPLIT_TENSION_V2=1)
            v2_result = self._run_with_boundary(case, boundary_version="v2")
            self.results["v2"].append(v2_result)

            if self.verbose:
                self._print_case_comparison(legacy_result, v2_result)

        print(f"\n{'='*80}")
        print("✅ Evaluation complete!")

    def _run_with_boundary(self, case: Dict, boundary_version: str) -> Dict:
        """
        Run tag_position with specific boundary version.

        Args:
            case: Test case dict
            boundary_version: "legacy" or "v2"

        Returns:
            Result dict with tags and diagnostics
        """
        try:
            # Set boundary version
            if boundary_version == "legacy":
                os.environ["USE_SPLIT_TENSION_V2"] = "0"
            else:
                os.environ["USE_SPLIT_TENSION_V2"] = "1"

            # Always use new tension detector (TensionDetector)
            os.environ["USE_NEW_TENSION"] = "1"

            result = tag_position(
                engine_path=self.engine_path,
                fen=case["fen"],
                played_move_uci=case["move"],
                use_new=True,
            )

            # Extract tension tags
            tension_creation = getattr(result, 'tension_creation', False)
            neutral_tension = getattr(result, 'neutral_tension_creation', False)

            # Extract notes
            notes = getattr(result, 'notes', {})
            tension_notes = notes.get('tension_creation', '')
            neutral_notes = notes.get('neutral_tension_creation', '')

            # Extract diagnostics if available
            analysis_meta = getattr(result, 'analysis_meta', {})
            tension_diagnostics = analysis_meta.get('tension_v2_diagnostics', {})

            return {
                "case_id": case.get("description", ""),
                "phase": case.get("phase", "unknown"),
                "tension_creation": tension_creation,
                "neutral_tension_creation": neutral_tension,
                "has_notes": bool(tension_notes or neutral_notes),
                "tension_notes": tension_notes,
                "neutral_notes": neutral_notes,
                "boundary_version": tension_diagnostics.get('version', boundary_version),
                "thresholds": tension_diagnostics.get('boundary_thresholds', {}),
                "error": None,
            }
        except Exception as e:
            return {
                "case_id": case.get("description", ""),
                "phase": case.get("phase", "unknown"),
                "tension_creation": False,
                "neutral_tension_creation": False,
                "has_notes": False,
                "tension_notes": "",
                "neutral_notes": "",
                "boundary_version": boundary_version,
                "thresholds": {},
                "error": str(e),
            }

    def _print_case_comparison(self, legacy: Dict, v2: Dict):
        """Print comparison for a single test case."""
        print(f"  Legacy: T={legacy['tension_creation']}, N={legacy['neutral_tension_creation']}")
        print(f"  V2:     T={v2['tension_creation']}, N={v2['neutral_tension_creation']}")

        if legacy['tension_creation'] != v2['tension_creation']:
            print("    ⚠️  Tension creation MISMATCH")
        if legacy['neutral_tension_creation'] != v2['neutral_tension_creation']:
            print("    ⚠️  Neutral tension MISMATCH")

    def generate_report(self) -> Dict:
        """
        Generate comprehensive A/B comparison report.

        Returns:
            Report dict with all metrics
        """
        legacy = self.results["legacy"]
        v2 = self.results["v2"]
        total = len(legacy)

        # 1. Trigger rate comparison
        legacy_tension_count = sum(1 for r in legacy if r["tension_creation"])
        v2_tension_count = sum(1 for r in v2 if r["tension_creation"])

        legacy_neutral_count = sum(1 for r in legacy if r["neutral_tension_creation"])
        v2_neutral_count = sum(1 for r in v2 if r["neutral_tension_creation"])

        # 2. Agreement metrics
        tension_matches = sum(
            1 for l, v in zip(legacy, v2)
            if l["tension_creation"] == v["tension_creation"]
        )
        neutral_matches = sum(
            1 for l, v in zip(legacy, v2)
            if l["neutral_tension_creation"] == v["neutral_tension_creation"]
        )

        # 3. Precision/Recall (using legacy as ground truth)
        tp_tension = sum(
            1 for l, v in zip(legacy, v2)
            if l["tension_creation"] and v["tension_creation"]
        )
        fp_tension = sum(
            1 for l, v in zip(legacy, v2)
            if not l["tension_creation"] and v["tension_creation"]
        )
        fn_tension = sum(
            1 for l, v in zip(legacy, v2)
            if l["tension_creation"] and not v["tension_creation"]
        )

        tp_neutral = sum(
            1 for l, v in zip(legacy, v2)
            if l["neutral_tension_creation"] and v["neutral_tension_creation"]
        )
        fp_neutral = sum(
            1 for l, v in zip(legacy, v2)
            if not l["neutral_tension_creation"] and v["neutral_tension_creation"]
        )
        fn_neutral = sum(
            1 for l, v in zip(legacy, v2)
            if l["neutral_tension_creation"] and not v["neutral_tension_creation"]
        )

        precision_tension = (
            tp_tension / (tp_tension + fp_tension) if (tp_tension + fp_tension) > 0 else 0.0
        )
        recall_tension = (
            tp_tension / (tp_tension + fn_tension) if (tp_tension + fn_tension) > 0 else 0.0
        )

        precision_neutral = (
            tp_neutral / (tp_neutral + fp_neutral) if (tp_neutral + fp_neutral) > 0 else 0.0
        )
        recall_neutral = (
            tp_neutral / (tp_neutral + fn_neutral) if (tp_neutral + fn_neutral) > 0 else 0.0
        )

        # 4. Neutral/Tension ratio
        legacy_ratio = (
            legacy_neutral_count / legacy_tension_count
            if legacy_tension_count > 0 else 0.0
        )
        v2_ratio = (
            v2_neutral_count / v2_tension_count
            if v2_tension_count > 0 else 0.0
        )

        # 5. Notes coverage
        legacy_notes_count = sum(1 for r in legacy if r["has_notes"])
        v2_notes_count = sum(1 for r in v2 if r["has_notes"])

        # 6. Phase-wise breakdown
        phases = set(r["phase"] for r in legacy)
        phase_breakdown = {}

        for phase in phases:
            phase_legacy = [r for r in legacy if r["phase"] == phase]
            phase_v2 = [r for r in v2 if r["phase"] == phase]

            phase_breakdown[phase] = {
                "total_cases": len(phase_legacy),
                "legacy_tension": sum(1 for r in phase_legacy if r["tension_creation"]),
                "v2_tension": sum(1 for r in phase_v2 if r["tension_creation"]),
                "legacy_neutral": sum(1 for r in phase_legacy if r["neutral_tension_creation"]),
                "v2_neutral": sum(1 for r in phase_v2 if r["neutral_tension_creation"]),
            }

        # 7. Sample mismatches (for debugging)
        mismatches = []
        for i, (l, v) in enumerate(zip(legacy, v2)):
            if (l["tension_creation"] != v["tension_creation"] or
                l["neutral_tension_creation"] != v["neutral_tension_creation"]):
                mismatches.append({
                    "case_id": l["case_id"],
                    "phase": l["phase"],
                    "legacy": {
                        "tension": l["tension_creation"],
                        "neutral": l["neutral_tension_creation"],
                    },
                    "v2": {
                        "tension": v["tension_creation"],
                        "neutral": v["neutral_tension_creation"],
                    },
                })

        # Build report
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_cases": total,
                "engine_path": self.engine_path,
                "boundary_versions": ["legacy", "v2"],
            },
            "trigger_rates": {
                "tension_creation": {
                    "legacy": {
                        "count": legacy_tension_count,
                        "rate": legacy_tension_count / total if total > 0 else 0.0,
                    },
                    "v2": {
                        "count": v2_tension_count,
                        "rate": v2_tension_count / total if total > 0 else 0.0,
                    },
                    "delta": v2_tension_count - legacy_tension_count,
                },
                "neutral_tension_creation": {
                    "legacy": {
                        "count": legacy_neutral_count,
                        "rate": legacy_neutral_count / total if total > 0 else 0.0,
                    },
                    "v2": {
                        "count": v2_neutral_count,
                        "rate": v2_neutral_count / total if total > 0 else 0.0,
                    },
                    "delta": v2_neutral_count - legacy_neutral_count,
                },
            },
            "agreement": {
                "tension_creation": {
                    "matches": tension_matches,
                    "agreement_rate": tension_matches / total if total > 0 else 0.0,
                },
                "neutral_tension_creation": {
                    "matches": neutral_matches,
                    "agreement_rate": neutral_matches / total if total > 0 else 0.0,
                },
            },
            "precision_recall": {
                "tension_creation": {
                    "precision": precision_tension,
                    "recall": recall_tension,
                    "f1": (
                        2 * precision_tension * recall_tension / (precision_tension + recall_tension)
                        if (precision_tension + recall_tension) > 0 else 0.0
                    ),
                    "tp": tp_tension,
                    "fp": fp_tension,
                    "fn": fn_tension,
                },
                "neutral_tension_creation": {
                    "precision": precision_neutral,
                    "recall": recall_neutral,
                    "f1": (
                        2 * precision_neutral * recall_neutral / (precision_neutral + recall_neutral)
                        if (precision_neutral + recall_neutral) > 0 else 0.0
                    ),
                    "tp": tp_neutral,
                    "fp": fp_neutral,
                    "fn": fn_neutral,
                },
            },
            "neutral_tension_ratio": {
                "legacy": legacy_ratio,
                "v2": v2_ratio,
                "delta": v2_ratio - legacy_ratio,
            },
            "notes_coverage": {
                "legacy": {
                    "count": legacy_notes_count,
                    "coverage": legacy_notes_count / total if total > 0 else 0.0,
                },
                "v2": {
                    "count": v2_notes_count,
                    "coverage": v2_notes_count / total if total > 0 else 0.0,
                },
            },
            "phase_breakdown": phase_breakdown,
            "sample_mismatches": mismatches[:10],  # Show first 10
            "total_mismatches": len(mismatches),
        }

        return report

    def print_summary(self, report: Dict):
        """Print human-readable summary of the report."""
        print(f"\n{'='*80}")
        print("TENSION A/B EVALUATION SUMMARY")
        print(f"{'='*80}")

        meta = report["metadata"]
        print(f"\nGenerated: {meta['generated_at']}")
        print(f"Total cases: {meta['total_cases']}")

        # Trigger rates
        print(f"\n{'─'*80}")
        print("TRIGGER RATES")
        print(f"{'─'*80}")

        tr = report["trigger_rates"]
        print(f"\ntension_creation:")
        print(f"  Legacy: {tr['tension_creation']['legacy']['count']:3d} ({tr['tension_creation']['legacy']['rate']*100:5.1f}%)")
        print(f"  V2:     {tr['tension_creation']['v2']['count']:3d} ({tr['tension_creation']['v2']['rate']*100:5.1f}%)")
        print(f"  Delta:  {tr['tension_creation']['delta']:+3d}")

        print(f"\nneutral_tension_creation:")
        print(f"  Legacy: {tr['neutral_tension_creation']['legacy']['count']:3d} ({tr['neutral_tension_creation']['legacy']['rate']*100:5.1f}%)")
        print(f"  V2:     {tr['neutral_tension_creation']['v2']['count']:3d} ({tr['neutral_tension_creation']['v2']['rate']*100:5.1f}%)")
        print(f"  Delta:  {tr['neutral_tension_creation']['delta']:+3d}")

        # Neutral/Tension ratio
        print(f"\n{'─'*80}")
        print("NEUTRAL/TENSION RATIO")
        print(f"{'─'*80}")
        ratio = report["neutral_tension_ratio"]
        print(f"  Legacy: {ratio['legacy']:.2f}")
        print(f"  V2:     {ratio['v2']:.2f}")
        print(f"  Delta:  {ratio['delta']:+.2f}")

        # Precision/Recall
        print(f"\n{'─'*80}")
        print("PRECISION / RECALL (legacy as baseline)")
        print(f"{'─'*80}")

        pr = report["precision_recall"]
        print(f"\ntension_creation:")
        print(f"  Precision: {pr['tension_creation']['precision']:.3f}")
        print(f"  Recall:    {pr['tension_creation']['recall']:.3f}")
        print(f"  F1:        {pr['tension_creation']['f1']:.3f}")
        print(f"  (TP={pr['tension_creation']['tp']}, FP={pr['tension_creation']['fp']}, FN={pr['tension_creation']['fn']})")

        print(f"\nneutral_tension_creation:")
        print(f"  Precision: {pr['neutral_tension_creation']['precision']:.3f}")
        print(f"  Recall:    {pr['neutral_tension_creation']['recall']:.3f}")
        print(f"  F1:        {pr['neutral_tension_creation']['f1']:.3f}")
        print(f"  (TP={pr['neutral_tension_creation']['tp']}, FP={pr['neutral_tension_creation']['fp']}, FN={pr['neutral_tension_creation']['fn']})")

        # Agreement
        print(f"\n{'─'*80}")
        print("AGREEMENT RATE")
        print(f"{'─'*80}")
        ag = report["agreement"]
        print(f"  tension_creation:         {ag['tension_creation']['agreement_rate']*100:5.1f}%")
        print(f"  neutral_tension_creation: {ag['neutral_tension_creation']['agreement_rate']*100:5.1f}%")

        # Notes coverage
        print(f"\n{'─'*80}")
        print("NOTES COVERAGE")
        print(f"{'─'*80}")
        nc = report["notes_coverage"]
        print(f"  Legacy: {nc['legacy']['count']:3d} ({nc['legacy']['coverage']*100:5.1f}%)")
        print(f"  V2:     {nc['v2']['count']:3d} ({nc['v2']['coverage']*100:5.1f}%)")

        # Phase breakdown
        print(f"\n{'─'*80}")
        print("PHASE BREAKDOWN")
        print(f"{'─'*80}")
        for phase, data in sorted(report["phase_breakdown"].items()):
            print(f"\n{phase.upper()} ({data['total_cases']} cases):")
            print(f"  tension_creation:         L={data['legacy_tension']:2d}, V2={data['v2_tension']:2d}")
            print(f"  neutral_tension_creation: L={data['legacy_neutral']:2d}, V2={data['v2_neutral']:2d}")

        # Mismatches
        if report["total_mismatches"] > 0:
            print(f"\n{'─'*80}")
            print(f"SAMPLE MISMATCHES ({report['total_mismatches']} total, showing first {len(report['sample_mismatches'])}):")
            print(f"{'─'*80}")
            for mm in report["sample_mismatches"]:
                print(f"\n  • {mm['case_id']} ({mm['phase']})")
                print(f"      Legacy: T={mm['legacy']['tension']}, N={mm['legacy']['neutral']}")
                print(f"      V2:     T={mm['v2']['tension']}, N={mm['v2']['neutral']}")

        print(f"\n{'='*80}")

    def export_json(self, report: Dict, output_path: str):
        """Export report to JSON file."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n✅ JSON report exported to: {output_path}")


def main():
    """Main entry point for tension A/B evaluation."""
    parser = argparse.ArgumentParser(
        description="Tension A/B Evaluation - Compare legacy vs v2 boundary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python3 scripts/tension_ab_eval.py

  # Run with custom sample size
  python3 scripts/tension_ab_eval.py --sample-size 100

  # Run in verbose mode
  python3 scripts/tension_ab_eval.py --sample-size 50 --verbose

  # Custom output path
  python3 scripts/tension_ab_eval.py --output my_report.json
        """,
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=50,
        help="Number of test positions (default: 50)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: reports/tension_ab_<timestamp>.json)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output (show each test case)",
    )

    args = parser.parse_args()

    # Default output path with timestamp
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"reports/tension_ab_{timestamp}.json"

    # Initialize evaluator
    evaluator = TensionABEvaluator(
        sample_size=args.sample_size,
        verbose=args.verbose,
    )

    # Load test cases
    evaluator.load_test_cases()

    # Run evaluation
    evaluator.run_evaluation()

    # Generate report
    report = evaluator.generate_report()

    # Print summary
    evaluator.print_summary(report)

    # Export JSON
    evaluator.export_json(report, args.output)

    print("\n✅ Tension A/B evaluation complete!")


if __name__ == "__main__":
    main()
