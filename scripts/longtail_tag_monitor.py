"""
Long-tail Tag Monitoring with Anomaly Detection.

This script monitors tag distribution over time and detects anomalies using:
- Kullback-Leibler (KL) divergence: measures distribution shift from baseline
- Chi-squared (χ²) test: tests statistical significance of distribution changes

Long-tail tags (rare tags like positional_sacrifice, speculative_sacrifice, etc.)
are monitored more carefully as they can indicate model drift or config issues.

Usage:
    # Monitor tag distribution from a batch of positions
    python3 scripts/longtail_tag_monitor.py --input reports/batch_results.jsonl --baseline baseline_dist.json

    # Generate baseline from historical data
    python3 scripts/longtail_tag_monitor.py --generate-baseline --input historical_data.jsonl --output baseline_dist.json

    # Monitor with custom thresholds
    python3 scripts/longtail_tag_monitor.py --input current_data.jsonl --baseline baseline.json --kl-threshold 0.5 --chi2-threshold 0.01

    # Real-time monitoring mode (reads from stdin)
    python3 scripts/longtail_tag_monitor.py --realtime --baseline baseline.json
"""
import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Chi-squared critical values (α=0.05, df=degrees of freedom)
# Source: standard chi-squared distribution tables
CHI2_CRITICAL_VALUES = {
    1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070,
    10: 18.307, 15: 24.996, 20: 31.410, 25: 37.652, 30: 43.773,
}


def get_chi2_critical(df: int, alpha: float = 0.05) -> float:
    """Get chi-squared critical value for given degrees of freedom."""
    # Use hardcoded table for common alpha=0.05
    if alpha == 0.05 and df in CHI2_CRITICAL_VALUES:
        return CHI2_CRITICAL_VALUES[df]

    # Approximate for large df using Wilson-Hilferty transformation
    # χ²(α, df) ≈ df * (1 - 2/(9*df) + z_α * sqrt(2/(9*df)))^3
    # Map alpha to z-score (common values)
    alpha_to_z = {
        0.10: 1.282,
        0.05: 1.645,
        0.025: 1.960,
        0.01: 2.326,
        0.005: 2.576,
    }
    z_alpha = alpha_to_z.get(alpha, 1.645)  # Default to 0.05 if not in table

    term = 1 - 2/(9*df) + z_alpha * math.sqrt(2/(9*df))
    return df * (term ** 3)


class LongTailMonitor:
    """Monitor long-tail tag distribution and detect anomalies."""

    # Define long-tail tags (rare tags requiring special attention)
    LONGTAIL_TAGS = {
        "positional_sacrifice",
        "speculative_sacrifice",
        "desperate_sacrifice",
        "inaccurate_tactical_sacrifice",
        "premature_attack",
        "misplaced_maneuver",
        "initiative_exploitation",
    }

    # All possible tags
    ALL_TAGS = {
        "initiative_exploitation",
        "initiative_attempt",
        "file_pressure_c",
        "tension_creation",
        "neutral_tension_creation",
        "premature_attack",
        "constructive_maneuver",
        "neutral_maneuver",
        "misplaced_maneuver",
        "maneuver_opening",
        "prophylactic_move",
        "control_over_dynamics",
        "tactical_sacrifice",
        "positional_sacrifice",
        "inaccurate_tactical_sacrifice",
        "speculative_sacrifice",
        "desperate_sacrifice",
    }

    def __init__(self, baseline: Optional[Dict[str, Any]] = None):
        """
        Initialize monitor.

        Args:
            baseline: Baseline distribution dict with structure:
                {
                    "total_positions": int,
                    "tag_counts": {tag_name: count, ...},
                    "tag_frequencies": {tag_name: frequency, ...}
                }
        """
        self.baseline = baseline

    def generate_baseline(self, tag_results: List[List[str]]) -> Dict[str, Any]:
        """
        Generate baseline distribution from historical tag results.

        Args:
            tag_results: List of tag lists, each representing one position's tags

        Returns:
            Baseline dict with tag counts and frequencies
        """
        total_positions = len(tag_results)
        tag_counter = Counter()

        for tags in tag_results:
            for tag in tags:
                tag_counter[tag] += 1

        # Calculate frequencies
        tag_frequencies = {
            tag: count / total_positions
            for tag, count in tag_counter.items()
        }

        baseline = {
            "total_positions": total_positions,
            "tag_counts": dict(tag_counter),
            "tag_frequencies": tag_frequencies,
            "generated_at": None,  # TODO: add timestamp
        }

        return baseline

    def compute_kl_divergence(
        self,
        observed: Dict[str, float],
        expected: Dict[str, float],
        epsilon: float = 1e-10,
    ) -> float:
        """
        Compute Kullback-Leibler divergence: KL(P||Q) = Σ P(i) * log(P(i)/Q(i))

        Args:
            observed: Observed distribution (P)
            expected: Expected distribution (Q) - baseline
            epsilon: Small constant to avoid log(0)

        Returns:
            KL divergence value (non-negative, 0 means identical distributions)
        """
        # Get all tags in either distribution
        all_tags = set(observed.keys()) | set(expected.keys())

        kl_div = 0.0
        for tag in all_tags:
            p = observed.get(tag, 0.0)
            q = expected.get(tag, 0.0)

            # Add epsilon to avoid log(0)
            p = max(p, epsilon)
            q = max(q, epsilon)

            kl_div += p * math.log(p / q)

        return kl_div

    def compute_chi_squared(
        self,
        observed_counts: Dict[str, int],
        expected_freqs: Dict[str, float],
        total_observed: int,
        alpha: float = 0.05,
    ) -> Tuple[float, int, float]:
        """
        Compute chi-squared statistic: χ² = Σ (O_i - E_i)² / E_i

        Args:
            observed_counts: Observed tag counts
            expected_freqs: Expected tag frequencies (from baseline)
            total_observed: Total number of positions in observed data
            alpha: Significance level for chi-squared test (default: 0.05)

        Returns:
            (chi2_statistic, degrees_of_freedom, critical_value)
        """
        all_tags = set(observed_counts.keys()) | set(expected_freqs.keys())

        chi2_stat = 0.0
        valid_categories = 0

        for tag in all_tags:
            observed = observed_counts.get(tag, 0)
            expected_freq = expected_freqs.get(tag, 0.0)
            expected = expected_freq * total_observed

            # Skip if expected count is too small (< 5 is common rule of thumb)
            if expected < 1.0:
                continue

            chi2_stat += ((observed - expected) ** 2) / expected
            valid_categories += 1

        # Degrees of freedom = number of categories - 1
        df = max(1, valid_categories - 1)

        # Get critical value for significance test using caller's alpha
        critical_value = get_chi2_critical(df, alpha=alpha)

        # Approximate p-value (simplified: just compare to critical value)
        # True p-value would require chi2 CDF, but this is sufficient for alerting
        is_significant = chi2_stat > critical_value

        return chi2_stat, df, critical_value

    def detect_anomalies(
        self,
        current_results: List[List[str]],
        kl_threshold: float = 0.3,
        chi2_alpha: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Detect anomalies in current tag distribution compared to baseline.

        Args:
            current_results: Current tag results
            kl_threshold: KL divergence threshold for alerting (default: 0.3)
            chi2_alpha: Significance level for chi-squared test (default: 0.05)

        Returns:
            Anomaly detection report with:
            {
                "kl_divergence": float,
                "kl_alert": bool,
                "chi2_statistic": float,
                "chi2_df": int,
                "chi2_critical": float,
                "chi2_alert": bool,
                "longtail_shifts": {...},
                "overall_assessment": str,
            }
        """
        if not self.baseline:
            raise ValueError("Baseline not set. Call set_baseline() first.")

        # Compute current distribution
        total_current = len(current_results)
        current_counter = Counter()
        for tags in current_results:
            for tag in tags:
                current_counter[tag] += 1

        current_freqs = {
            tag: count / total_current
            for tag, count in current_counter.items()
        }

        # Get baseline frequencies
        baseline_freqs = self.baseline["tag_frequencies"]

        # Compute KL divergence
        kl_div = self.compute_kl_divergence(current_freqs, baseline_freqs)
        kl_alert = kl_div > kl_threshold

        # Compute chi-squared statistic
        chi2_stat, df, critical = self.compute_chi_squared(
            dict(current_counter),
            baseline_freqs,
            total_current,
            alpha=chi2_alpha,
        )
        chi2_alert = chi2_stat > critical

        # Check long-tail tag shifts
        longtail_shifts = {}
        for tag in self.LONGTAIL_TAGS:
            baseline_freq = baseline_freqs.get(tag, 0.0)
            current_freq = current_freqs.get(tag, 0.0)
            shift = current_freq - baseline_freq

            # Calculate relative change only if baseline > threshold
            if baseline_freq > 0.001:  # Ignore if baseline is too small
                relative_change = (shift / baseline_freq * 100)
                # Flag if shift is > 50% relative change or > 0.05 absolute change
                is_anomaly = abs(relative_change) > 50 or abs(shift) > 0.05
            else:
                relative_change = None
                # For zero baseline, only flag if current frequency is significant
                is_anomaly = current_freq > 0.05

            longtail_shifts[tag] = {
                "baseline_freq": baseline_freq,
                "current_freq": current_freq,
                "absolute_shift": shift,
                "relative_change_pct": relative_change,
                "is_anomaly": is_anomaly,
            }

        # Overall assessment
        alert_count = sum([kl_alert, chi2_alert])
        longtail_anomaly_count = sum(1 for shift in longtail_shifts.values() if shift["is_anomaly"])

        if alert_count >= 2 or longtail_anomaly_count >= 3:
            assessment = "CRITICAL: Significant distribution shift detected"
        elif alert_count == 1 or longtail_anomaly_count >= 2:
            assessment = "WARNING: Moderate distribution shift detected"
        elif longtail_anomaly_count == 1:
            assessment = "NOTICE: Minor long-tail tag shift detected"
        else:
            assessment = "OK: Distribution within expected range"

        return {
            "total_positions": total_current,
            "kl_divergence": kl_div,
            "kl_threshold": kl_threshold,
            "kl_alert": kl_alert,
            "chi2_statistic": chi2_stat,
            "chi2_df": df,
            "chi2_critical": critical,
            "chi2_alert": chi2_alert,
            "longtail_shifts": longtail_shifts,
            "current_distribution": current_freqs,
            "baseline_distribution": baseline_freqs,
            "overall_assessment": assessment,
        }

    def format_report(self, anomaly_report: Dict[str, Any]) -> str:
        """Format anomaly detection report as text."""
        lines = []
        lines.append("=" * 80)
        lines.append("LONG-TAIL TAG MONITORING REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Overall assessment
        assessment = anomaly_report["overall_assessment"]
        status_symbol = "⚠️ " if "WARNING" in assessment or "CRITICAL" in assessment else "✓ "
        lines.append(f"{status_symbol}{assessment}")
        lines.append("")

        # Sample size
        lines.append(f"Positions analyzed: {anomaly_report['total_positions']}")
        lines.append("")

        # KL Divergence
        lines.append("-" * 80)
        lines.append("KULLBACK-LEIBLER DIVERGENCE")
        lines.append("-" * 80)
        kl_div = anomaly_report["kl_divergence"]
        kl_threshold = anomaly_report["kl_threshold"]
        kl_alert = anomaly_report["kl_alert"]
        kl_status = "⚠️  ALERT" if kl_alert else "✓ OK"
        lines.append(f"KL(current || baseline): {kl_div:.4f}")
        lines.append(f"Threshold: {kl_threshold:.4f}")
        lines.append(f"Status: {kl_status}")
        lines.append("")

        # Chi-squared test
        lines.append("-" * 80)
        lines.append("CHI-SQUARED TEST")
        lines.append("-" * 80)
        chi2_stat = anomaly_report["chi2_statistic"]
        chi2_df = anomaly_report["chi2_df"]
        chi2_crit = anomaly_report["chi2_critical"]
        chi2_alert = anomaly_report["chi2_alert"]
        chi2_status = "⚠️  ALERT" if chi2_alert else "✓ OK"
        lines.append(f"χ² statistic: {chi2_stat:.4f}")
        lines.append(f"Degrees of freedom: {chi2_df}")
        lines.append(f"Critical value (α=0.05): {chi2_crit:.4f}")
        lines.append(f"Status: {chi2_status}")
        lines.append("")

        # Long-tail tag shifts
        lines.append("-" * 80)
        lines.append("LONG-TAIL TAG SHIFTS")
        lines.append("-" * 80)
        longtail_shifts = anomaly_report["longtail_shifts"]
        has_anomalies = any(shift["is_anomaly"] for shift in longtail_shifts.values())

        if has_anomalies:
            lines.append("Detected anomalies in long-tail tags:")
            lines.append("")
            for tag, shift in sorted(longtail_shifts.items(), key=lambda x: abs(x[1]["absolute_shift"]), reverse=True):
                if shift["is_anomaly"]:
                    baseline = shift["baseline_freq"]
                    current = shift["current_freq"]
                    abs_shift = shift["absolute_shift"]
                    rel_change = shift["relative_change_pct"]

                    lines.append(f"  • {tag}")
                    lines.append(f"    Baseline:  {baseline:.4f}")
                    lines.append(f"    Current:   {current:.4f}")
                    lines.append(f"    Shift:     {abs_shift:+.4f} ({rel_change:+.1f}% relative change)" if rel_change else f"    Shift:     {abs_shift:+.4f}")
                    lines.append("")
        else:
            lines.append("No anomalies detected in long-tail tags")
            lines.append("")

        # Top distribution changes (non-long-tail)
        lines.append("-" * 80)
        lines.append("TOP DISTRIBUTION CHANGES")
        lines.append("-" * 80)
        current_dist = anomaly_report["current_distribution"]
        baseline_dist = anomaly_report["baseline_distribution"]

        all_tags = set(current_dist.keys()) | set(baseline_dist.keys())
        changes = []
        for tag in all_tags:
            if tag in self.LONGTAIL_TAGS:
                continue  # Already reported above
            baseline = baseline_dist.get(tag, 0.0)
            current = current_dist.get(tag, 0.0)
            shift = current - baseline
            if abs(shift) > 0.01:  # Only show significant changes
                changes.append((tag, baseline, current, shift))

        if changes:
            changes.sort(key=lambda x: abs(x[3]), reverse=True)
            for tag, baseline, current, shift in changes[:10]:  # Top 10
                lines.append(f"  {tag:30s}: {baseline:.4f} → {current:.4f} ({shift:+.4f})")
        else:
            lines.append("No significant changes in other tags")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def set_baseline(self, baseline: Dict[str, Any]):
        """Set baseline distribution."""
        self.baseline = baseline


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file (one JSON object per line)."""
    results = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def extract_tags_from_results(results: List[Dict[str, Any]]) -> List[List[str]]:
    """
    Extract tag lists from TagResult dicts.

    Supports two formats:
    1. Boolean fields format: {"tension_creation": True, "prophylactic_move": False, ...}
    2. List format: {"tags": ["tension_creation", "prophylactic_move"]}
    """
    tag_results = []

    TAG_FIELDS = [
        "initiative_exploitation",
        "initiative_attempt",
        "file_pressure_c",
        "tension_creation",
        "neutral_tension_creation",
        "premature_attack",
        "constructive_maneuver",
        "neutral_maneuver",
        "misplaced_maneuver",
        "maneuver_opening",
        "prophylactic_move",
        "control_over_dynamics",
        "tactical_sacrifice",
        "positional_sacrifice",
        "inaccurate_tactical_sacrifice",
        "speculative_sacrifice",
        "desperate_sacrifice",
    ]

    for result in results:
        tags = []

        # Check if "tags" list exists (format 2)
        if "tags" in result and isinstance(result["tags"], list):
            tags = result["tags"]
        else:
            # Check boolean fields (format 1)
            for field in TAG_FIELDS:
                if result.get(field, False):
                    tags.append(field)

            # Add CoD subtype if present
            if result.get("control_over_dynamics") and result.get("cod_subtype"):
                tags.append(f"control_over_dynamics_{result['cod_subtype']}")

        tag_results.append(tags)

    return tag_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", help="Input JSONL file with tag results")
    parser.add_argument("--baseline", help="Baseline distribution JSON file")
    parser.add_argument("--generate-baseline", action="store_true", help="Generate baseline from input data")
    parser.add_argument("--output", help="Output file path (for baseline generation or report)")
    parser.add_argument("--kl-threshold", type=float, default=0.3, help="KL divergence alert threshold (default: 0.3)")
    parser.add_argument("--chi2-alpha", type=float, default=0.05, help="Chi-squared significance level (default: 0.05)")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--realtime", action="store_true", help="Real-time monitoring mode (read from stdin)")

    args = parser.parse_args()

    # Validate input
    if not args.input and not args.realtime:
        parser.error("Either --input or --realtime must be specified")

    if args.generate_baseline:
        # Generate baseline mode
        if not args.input:
            parser.error("--input is required for baseline generation")

        print(f"Loading data from {args.input}...", file=sys.stderr)
        results = load_jsonl(Path(args.input))
        tag_results = extract_tags_from_results(results)

        print(f"Generating baseline from {len(tag_results)} positions...", file=sys.stderr)
        monitor = LongTailMonitor()
        baseline = monitor.generate_baseline(tag_results)

        output_path = args.output or "baseline_dist.json"
        with open(output_path, 'w') as f:
            json.dump(baseline, f, indent=2)

        print(f"✓ Baseline generated: {output_path}", file=sys.stderr)
        print(f"  Total positions: {baseline['total_positions']}", file=sys.stderr)
        print(f"  Unique tags: {len(baseline['tag_frequencies'])}", file=sys.stderr)

        return 0

    # Monitoring mode
    if not args.baseline:
        parser.error("--baseline is required for monitoring")

    # Load baseline
    print(f"Loading baseline from {args.baseline}...", file=sys.stderr)
    with open(args.baseline, 'r') as f:
        baseline = json.load(f)

    monitor = LongTailMonitor(baseline=baseline)

    # Load current data
    if args.realtime:
        # TODO: Implement real-time stdin reading
        print("ERROR: Real-time mode not yet implemented", file=sys.stderr)
        return 1
    else:
        print(f"Loading current data from {args.input}...", file=sys.stderr)
        results = load_jsonl(Path(args.input))
        tag_results = extract_tags_from_results(results)

    # Detect anomalies
    print(f"Analyzing {len(tag_results)} positions...", file=sys.stderr)
    anomaly_report = monitor.detect_anomalies(
        tag_results,
        kl_threshold=args.kl_threshold,
        chi2_alpha=args.chi2_alpha,
    )

    # Output report
    if args.format == "json":
        output = json.dumps(anomaly_report, indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"✓ Report written to {args.output}", file=sys.stderr)
        else:
            print(output)
    else:  # text
        report_text = monitor.format_report(anomaly_report)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report_text)
            print(f"✓ Report written to {args.output}", file=sys.stderr)
        else:
            print(report_text)

    # Exit with error code if critical alert
    if "CRITICAL" in anomaly_report["overall_assessment"]:
        return 2
    elif "WARNING" in anomaly_report["overall_assessment"]:
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
