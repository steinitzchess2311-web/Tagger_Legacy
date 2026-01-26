"""
Tag Distribution Monitoring Script.

This script monitors and compares tag distribution between legacy and new detectors:
- Overall trigger rates (legacy vs new)
- Neutral vs tension tag ratios
- Tag type distribution (prophylaxis, control, sacrifice, etc.)
- Statistical comparison (chi-squared test)

Usage:
    # Monitor tension detector distribution
    python3 scripts/tag_distribution_monitor.py --detector tension --sample-size 100

    # Monitor CoD detector distribution
    python3 scripts/tag_distribution_monitor.py --detector cod --sample-size 100

    # Monitor both detectors with custom game file
    python3 scripts/tag_distribution_monitor.py --detector both --games my_games.pgn --sample-size 200

    # Generate comparison report
    python3 scripts/tag_distribution_monitor.py --detector both --output reports/tag_distribution.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Any
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

from rule_tagger2.core.facade import tag_position


class TagDistributionMonitor:
    """Monitor and compare tag distribution across detector versions."""

    def __init__(self, detector: str, sample_size: int = 100):
        """
        Initialize monitor.

        Args:
            detector: "tension", "cod", or "both"
            sample_size: Number of positions to analyze
        """
        self.detector = detector
        self.sample_size = sample_size
        self.engine_path = os.getenv("ENGINE", "/usr/local/bin/stockfish")

        # Test positions
        self.test_positions: List[Dict[str, Any]] = []

        # Distribution tracking
        self.distributions = {
            "legacy": defaultdict(int),
            "new": defaultdict(int),
        }

        # Tag type tracking
        self.tag_types = {
            "legacy": defaultdict(int),
            "new": defaultdict(int),
        }

        # Neutral vs tension tracking
        self.neutral_tension_ratio = {
            "legacy": {"neutral": 0, "tension": 0, "other": 0},
            "new": {"neutral": 0, "tension": 0, "other": 0},
        }

    def load_test_positions(self, games_file: str = None):
        """
        Load test positions from PGN file or generate defaults.

        Args:
            games_file: Optional path to PGN file
        """
        if games_file and Path(games_file).exists():
            print(f"Loading positions from {games_file}...")
            self._load_from_pgn(games_file)
        else:
            print("Generating default test positions...")
            self._generate_default_positions()

    def _generate_default_positions(self):
        """Generate diverse test positions covering various game phases."""
        positions = [
            # Opening positions
            {
                "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "move": "e2e4",
                "phase": "opening",
                "description": "Standard e4 opening"
            },
            {
                "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "move": "d2d4",
                "phase": "opening",
                "description": "Standard d4 opening"
            },
            {
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "move": "e7e5",
                "phase": "opening",
                "description": "Symmetric e5 response"
            },
            # Early middlegame
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "move": "d2d3",
                "phase": "early_middle",
                "description": "Quiet development"
            },
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
                "move": "d2d4",
                "phase": "early_middle",
                "description": "Central tension creation"
            },
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                "move": "b1c3",
                "phase": "early_middle",
                "description": "Development with control"
            },
            # Middlegame tactical
            {
                "fen": "r2qkb1r/ppp2ppp/2np1n2/4p1B1/2B1P1b1/2NP1N2/PPP2PPP/R2QK2R w KQkq - 0 7",
                "move": "c4f7",
                "phase": "middlegame",
                "description": "Tactical sacrifice"
            },
            {
                "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 0 5",
                "move": "e1g1",
                "phase": "middlegame",
                "description": "Castling for king safety"
            },
            {
                "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/3P1N2/PPP2PPP/RNBQKB1R w KQkq - 0 4",
                "move": "b1c3",
                "phase": "middlegame",
                "description": "Development, control"
            },
            # Prophylaxis / CoD positions
            {
                "fen": "r1bqkb1r/ppp2ppp/2np1n2/4p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
                "move": "c1e3",
                "phase": "middlegame",
                "description": "Prophylaxis - prevent d5"
            },
            {
                "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
                "move": "h2h3",
                "phase": "middlegame",
                "description": "King safety shell - prevent Bg4"
            },
            {
                "fen": "rnbqkb1r/pp3ppp/3p1n2/2pPp3/8/5N2/PPP1PPPP/RNBQKB1R w KQkq - 0 5",
                "move": "c2c4",
                "phase": "middlegame",
                "description": "Blockade - lock center"
            },
            # Complex middlegame
            {
                "fen": "r2q1rk1/ppp1bppp/2np1n2/4p1B1/2B1P1b1/2NP1N2/PPP1QPPP/R3K2R w KQ - 0 10",
                "move": "e1c1",
                "phase": "complex_middle",
                "description": "Long castling - regroup"
            },
            {
                "fen": "r1bq1rk1/ppp2ppp/2np1n2/4p1B1/1bB1P3/2NP1N2/PPP1QPPP/R3K2R w KQ - 0 9",
                "move": "c4e6",
                "phase": "complex_middle",
                "description": "Exchange to simplify"
            },
            # Endgame transitions
            {
                "fen": "4r1k1/pp3ppp/2p5/4P3/2P5/6P1/P4P1P/3R2K1 w - - 0 25",
                "move": "d1d7",
                "phase": "endgame",
                "description": "Active rook - control 7th"
            },
        ]

        # Replicate to reach sample size
        while len(self.test_positions) < self.sample_size:
            self.test_positions.extend(positions)

        # Shuffle and trim to exact size
        random.shuffle(self.test_positions)
        self.test_positions = self.test_positions[:self.sample_size]

    def _load_from_pgn(self, pgn_file: str):
        """Load positions from PGN file."""
        # TODO: Implement PGN parsing
        print("PGN parsing not yet implemented, using defaults...")
        self._generate_default_positions()

    def run_comparison(self):
        """Run tag distribution comparison between legacy and new detectors."""
        print(f"\n{'=' * 60}")
        print(f"TAG DISTRIBUTION MONITORING")
        print(f"{'=' * 60}")
        print(f"Detector: {self.detector}")
        print(f"Sample size: {self.sample_size}")
        print(f"Engine: {self.engine_path}")
        print(f"{'=' * 60}\n")

        for i, pos in enumerate(self.test_positions, 1):
            if i % 10 == 0:
                print(f"Processing position {i}/{self.sample_size}...", end="\r")

            fen = pos["fen"]
            move = pos["move"]

            # Run legacy detector
            legacy_result = self._run_legacy(fen, move)
            self._track_distribution(legacy_result, "legacy")

            # Run new detector
            new_result = self._run_new(fen, move)
            self._track_distribution(new_result, "new")

        print(f"Processing position {self.sample_size}/{self.sample_size}... Done!\n")

    def _run_legacy(self, fen: str, move: str) -> Dict[str, Any]:
        """Run legacy detector on position."""
        # Set environment variables for legacy detector
        old_tension = os.environ.get("USE_NEW_TENSION")
        old_cod = os.environ.get("USE_NEW_COD")

        os.environ["USE_NEW_TENSION"] = "0"
        os.environ["USE_NEW_COD"] = "0"

        try:
            result = tag_position(
                engine_path=self.engine_path,
                fen=fen,
                played_move_uci=move,
                use_new=False,
            )
            return self._extract_result(result)
        except Exception as e:
            print(f"Legacy error: {e}")
            return {"tension_tag": None}
        finally:
            # Restore original environment
            if old_tension is not None:
                os.environ["USE_NEW_TENSION"] = old_tension
            else:
                os.environ.pop("USE_NEW_TENSION", None)
            if old_cod is not None:
                os.environ["USE_NEW_COD"] = old_cod
            else:
                os.environ.pop("USE_NEW_COD", None)

    def _run_new(self, fen: str, move: str) -> Dict[str, Any]:
        """Run new detector on position."""
        # Set environment variables based on detector mode
        old_tension = os.environ.get("USE_NEW_TENSION")
        old_cod = os.environ.get("USE_NEW_COD")

        if self.detector in ["tension", "both"]:
            os.environ["USE_NEW_TENSION"] = "1"
        if self.detector in ["cod", "both"]:
            os.environ["USE_NEW_COD"] = "1"

        try:
            result = tag_position(
                engine_path=self.engine_path,
                fen=fen,
                played_move_uci=move,
                use_new=True,
            )
            return self._extract_result(result)
        except Exception as e:
            print(f"New error: {e}")
            return {"tension_tag": None}
        finally:
            # Restore original environment
            if old_tension is not None:
                os.environ["USE_NEW_TENSION"] = old_tension
            else:
                os.environ.pop("USE_NEW_TENSION", None)
            if old_cod is not None:
                os.environ["USE_NEW_COD"] = old_cod
            else:
                os.environ.pop("USE_NEW_COD", None)

    def _extract_result(self, result: Any) -> Dict[str, Any]:
        """Extract tag information from TagResult object."""
        if isinstance(result, dict):
            return result

        # Derive tag name from TagResult boolean fields
        tag_name = None

        # Priority order matches TAG_PRIORITY in models.py
        if hasattr(result, "initiative_exploitation") and result.initiative_exploitation:
            tag_name = "initiative_exploitation"
        elif hasattr(result, "initiative_attempt") and result.initiative_attempt:
            tag_name = "initiative_attempt"
        elif hasattr(result, "file_pressure_c") and result.file_pressure_c:
            tag_name = "file_pressure_c"
        elif hasattr(result, "tension_creation") and result.tension_creation:
            tag_name = "tension_creation"
        elif hasattr(result, "neutral_tension_creation") and result.neutral_tension_creation:
            tag_name = "neutral_tension_creation"
        elif hasattr(result, "premature_attack") and result.premature_attack:
            tag_name = "premature_attack"
        elif hasattr(result, "constructive_maneuver") and result.constructive_maneuver:
            tag_name = "constructive_maneuver"
        elif hasattr(result, "neutral_maneuver") and result.neutral_maneuver:
            tag_name = "neutral_maneuver"
        elif hasattr(result, "misplaced_maneuver") and result.misplaced_maneuver:
            tag_name = "misplaced_maneuver"
        elif hasattr(result, "maneuver_opening") and result.maneuver_opening:
            tag_name = "maneuver_opening"
        elif hasattr(result, "prophylactic_move") and result.prophylactic_move:
            tag_name = "prophylactic_move"
        elif hasattr(result, "control_over_dynamics") and result.control_over_dynamics:
            # Include subtype if available
            if hasattr(result, "control_over_dynamics_subtype") and result.control_over_dynamics_subtype:
                tag_name = f"control_over_dynamics_{result.control_over_dynamics_subtype}"
            else:
                tag_name = "control_over_dynamics"
        elif hasattr(result, "tactical_sacrifice") and result.tactical_sacrifice:
            tag_name = "tactical_sacrifice"
        elif hasattr(result, "positional_sacrifice") and result.positional_sacrifice:
            tag_name = "positional_sacrifice"
        elif hasattr(result, "inaccurate_tactical_sacrifice") and result.inaccurate_tactical_sacrifice:
            tag_name = "inaccurate_tactical_sacrifice"
        elif hasattr(result, "speculative_sacrifice") and result.speculative_sacrifice:
            tag_name = "speculative_sacrifice"
        elif hasattr(result, "desperate_sacrifice") and result.desperate_sacrifice:
            tag_name = "desperate_sacrifice"

        return {"tension_tag": tag_name}

    def _track_distribution(self, result: Dict[str, Any], version: str):
        """Track tag distribution statistics."""
        tension_tag = result.get("tension_tag")

        if tension_tag:
            # Track overall distribution
            self.distributions[version][tension_tag] += 1

            # Track tag types
            if "neutral" in tension_tag.lower():
                self.neutral_tension_ratio[version]["neutral"] += 1
                self.tag_types[version]["neutral"] += 1
            elif any(t in tension_tag.lower() for t in ["tension", "initiative", "aggression"]):
                self.neutral_tension_ratio[version]["tension"] += 1
                self.tag_types[version]["tension"] += 1
            elif "prophylaxis" in tension_tag.lower():
                self.tag_types[version]["prophylaxis"] += 1
                self.neutral_tension_ratio[version]["other"] += 1
            elif "control" in tension_tag.lower():
                self.tag_types[version]["control"] += 1
                self.neutral_tension_ratio[version]["other"] += 1
            elif "sacrifice" in tension_tag.lower():
                self.tag_types[version]["sacrifice"] += 1
                self.neutral_tension_ratio[version]["other"] += 1
            elif "king_safety" in tension_tag.lower():
                self.tag_types[version]["king_safety"] += 1
                self.neutral_tension_ratio[version]["other"] += 1
            else:
                self.neutral_tension_ratio[version]["other"] += 1
        else:
            self.distributions[version]["no_tag"] += 1

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive distribution report."""
        report = {
            "config": {
                "detector": self.detector,
                "sample_size": self.sample_size,
                "engine_path": self.engine_path,
            },
            "trigger_rates": {},
            "neutral_tension_ratio": {},
            "tag_type_distribution": {},
            "statistical_comparison": {},
        }

        # Calculate trigger rates
        for version in ["legacy", "new"]:
            total = sum(self.distributions[version].values())
            triggered = total - self.distributions[version].get("no_tag", 0)
            trigger_rate = (triggered / total * 100) if total > 0 else 0

            report["trigger_rates"][version] = {
                "total_positions": total,
                "triggered": triggered,
                "not_triggered": self.distributions[version].get("no_tag", 0),
                "trigger_rate_pct": round(trigger_rate, 2),
            }

        # Calculate neutral vs tension ratios
        for version in ["legacy", "new"]:
            neutral = self.neutral_tension_ratio[version]["neutral"]
            tension = self.neutral_tension_ratio[version]["tension"]
            other = self.neutral_tension_ratio[version]["other"]
            total = neutral + tension + other

            if total > 0:
                report["neutral_tension_ratio"][version] = {
                    "neutral": neutral,
                    "neutral_pct": round(neutral / total * 100, 2),
                    "tension": tension,
                    "tension_pct": round(tension / total * 100, 2),
                    "other": other,
                    "other_pct": round(other / total * 100, 2),
                    "neutral_to_tension_ratio": round(neutral / tension, 2) if tension > 0 else float('inf'),
                }

        # Tag type distribution
        for version in ["legacy", "new"]:
            report["tag_type_distribution"][version] = dict(self.tag_types[version])

        # Statistical comparison (chi-squared)
        report["statistical_comparison"] = self._calculate_chi_squared()

        return report

    def _calculate_chi_squared(self) -> Dict[str, Any]:
        """Calculate chi-squared statistic for distribution comparison."""
        # Collect all unique tags
        all_tags = set(self.distributions["legacy"].keys()) | set(self.distributions["new"].keys())

        # Build contingency table
        observed_legacy = []
        observed_new = []

        for tag in sorted(all_tags):
            observed_legacy.append(self.distributions["legacy"].get(tag, 0))
            observed_new.append(self.distributions["new"].get(tag, 0))

        # Calculate chi-squared statistic manually
        chi_squared = 0.0
        total_legacy = sum(observed_legacy)
        total_new = sum(observed_new)
        grand_total = total_legacy + total_new

        for legacy_count, new_count in zip(observed_legacy, observed_new):
            row_total = legacy_count + new_count
            if row_total == 0:
                continue

            # Expected frequencies
            expected_legacy = (row_total * total_legacy) / grand_total
            expected_new = (row_total * total_new) / grand_total

            # Chi-squared contribution
            if expected_legacy > 0:
                chi_squared += ((legacy_count - expected_legacy) ** 2) / expected_legacy
            if expected_new > 0:
                chi_squared += ((new_count - expected_new) ** 2) / expected_new

        degrees_of_freedom = len(all_tags) - 1

        return {
            "chi_squared": round(chi_squared, 4),
            "degrees_of_freedom": degrees_of_freedom,
            "interpretation": self._interpret_chi_squared(chi_squared, degrees_of_freedom),
        }

    def _interpret_chi_squared(self, chi_squared: float, df: int) -> str:
        """Interpret chi-squared statistic."""
        # Critical values for alpha=0.05 (approximate)
        critical_values = {1: 3.84, 2: 5.99, 3: 7.81, 4: 9.49, 5: 11.07, 10: 18.31, 15: 25.00, 20: 31.41}

        # Find nearest df
        nearest_df = min(critical_values.keys(), key=lambda x: abs(x - df))
        critical_value = critical_values.get(nearest_df, 31.41)

        if chi_squared < critical_value:
            return f"No significant difference (χ² = {chi_squared:.2f} < {critical_value:.2f})"
        else:
            return f"Significant difference detected (χ² = {chi_squared:.2f} > {critical_value:.2f})"

    def print_report(self, report: Dict[str, Any]):
        """Print formatted report to console."""
        print(f"\n{'=' * 60}")
        print(f"TAG DISTRIBUTION REPORT")
        print(f"{'=' * 60}\n")

        # Trigger rates
        print("TRIGGER RATES:")
        print("-" * 60)
        for version in ["legacy", "new"]:
            data = report["trigger_rates"][version]
            print(f"{version.upper():>10}: {data['trigger_rate_pct']:>6.2f}% "
                  f"({data['triggered']}/{data['total_positions']} positions)")
        print()

        # Neutral vs Tension ratios
        print("NEUTRAL vs TENSION RATIOS:")
        print("-" * 60)
        for version in ["legacy", "new"]:
            if version in report["neutral_tension_ratio"]:
                data = report["neutral_tension_ratio"][version]
                print(f"{version.upper():>10}:")
                print(f"  Neutral:  {data['neutral']:>4} ({data['neutral_pct']:>5.1f}%)")
                print(f"  Tension:  {data['tension']:>4} ({data['tension_pct']:>5.1f}%)")
                print(f"  Other:    {data['other']:>4} ({data['other_pct']:>5.1f}%)")
                ratio = data['neutral_to_tension_ratio']
                ratio_str = f"{ratio:.2f}" if ratio != float('inf') else "∞"
                print(f"  N/T Ratio: {ratio_str}")
                print()

        # Tag type distribution
        print("TAG TYPE DISTRIBUTION:")
        print("-" * 60)
        for version in ["legacy", "new"]:
            print(f"{version.upper():>10}:")
            for tag_type, count in sorted(report["tag_type_distribution"][version].items()):
                print(f"  {tag_type:>20}: {count:>4}")
            print()

        # Statistical comparison
        print("STATISTICAL COMPARISON:")
        print("-" * 60)
        stat = report["statistical_comparison"]
        print(f"Chi-squared: {stat['chi_squared']}")
        print(f"Degrees of freedom: {stat['degrees_of_freedom']}")
        print(f"Interpretation: {stat['interpretation']}")
        print()

        print(f"{'=' * 60}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor and compare tag distribution between detector versions"
    )
    parser.add_argument(
        "--detector",
        choices=["tension", "cod", "both"],
        default="tension",
        help="Which detector to monitor (default: tension)"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help="Number of positions to analyze (default: 100)"
    )
    parser.add_argument(
        "--games",
        type=str,
        default=None,
        help="Optional PGN file with games to analyze"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional JSON output file for report (default: reports/tag_distribution_{detector}.json)"
    )

    args = parser.parse_args()

    # Create monitor
    monitor = TagDistributionMonitor(
        detector=args.detector,
        sample_size=args.sample_size
    )

    # Load test positions
    monitor.load_test_positions(args.games)

    # Run comparison
    monitor.run_comparison()

    # Generate report
    report = monitor.generate_report()

    # Print report to console
    monitor.print_report(report)

    # Save to file
    output_file = args.output
    if output_file is None:
        output_dir = Path(__file__).parent.parent / "reports"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"tag_distribution_{args.detector}.json"

    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to: {output_file}")


if __name__ == "__main__":
    main()
