"""
Detector Evidence Report Generator.

Generates a visual report showing:
- Evidence bars for each tag detection (scores, thresholds, metrics)
- Suppression reasons for non-selected tags
- Gating diagnostics (volatility, mobility, tension checks)
- Tag priority and cooldown information
- Diagnostic metadata from tension_support and cod_support

This report layer helps understand WHY certain tags were or weren't applied.

Usage:
    # Generate report for a single position
    python3 scripts/detector_evidence_report.py --fen "..." --move "e2e4"

    # Generate report from test file
    python3 scripts/detector_evidence_report.py --input tests/golden_cases/cases.json --case-id case_001

    # Generate HTML report
    python3 scripts/detector_evidence_report.py --fen "..." --move "e2e4" --format html

    # Batch mode - generate evidence for multiple positions
    python3 scripts/detector_evidence_report.py --input tests/golden_cases/cases.json --batch --output reports/evidence_report.html
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import chess

from rule_tagger2.orchestration.pipeline import TagDetectionPipeline


class EvidenceReportGenerator:
    """Generate evidence reports for tag detections."""

    def __init__(self, engine_path: str = "/usr/local/bin/stockfish"):
        """Initialize report generator."""
        self.engine_path = engine_path
        self.pipeline = TagDetectionPipeline(use_legacy=False)

    def _convert_to_uci(self, fen: str, move: str) -> str:
        """Convert move from SAN to UCI if needed."""
        # Check if already UCI format (length 4-5, e.g., "e2e4" or "e7e8q")
        if len(move) in (4, 5) and move[0].islower() and move[1].isdigit():
            return move

        # Parse as SAN
        try:
            board = chess.Board(fen)
            parsed_move = board.parse_san(move)
            return parsed_move.uci()
        except Exception as e:
            # If parsing fails, assume it's already UCI
            return move

    def analyze_position(
        self,
        fen: str,
        move: str,
        depth: int = 15,
        multipv: int = 3,
    ) -> Dict[str, Any]:
        """
        Analyze a position and extract evidence data.

        Args:
            fen: FEN position string
            move: Move in UCI (e.g., "e2e4") or SAN (e.g., "e4") format
            depth: Analysis depth
            multipv: MultiPV setting

        Returns:
            Dictionary with evidence structure:
            {
                "position": {"fen": ..., "move": ...},
                "tags_applied": [...],
                "tension_evidence": {...},
                "cod_evidence": {...},
                "suppression_info": {...},
                "gating_info": {...}
            }
        """
        # Convert SAN to UCI if needed
        move_uci = self._convert_to_uci(fen, move)

        # Run pipeline with diagnostics
        result = self.pipeline.run_pipeline(
            engine_path=self.engine_path,
            fen=fen,
            played_move_uci=move_uci,
            depth=depth,
            multipv=multipv,
        )

        # Convert result to dict
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        elif hasattr(result, '__dict__'):
            result_dict = vars(result)
        elif isinstance(result, dict):
            result_dict = result
        else:
            raise ValueError(f"Unexpected result type: {type(result)}")

        # Extract applied tags
        tags_applied = self._extract_applied_tags(result_dict)

        # Extract evidence from diagnostics
        tension_evidence = self._extract_tension_evidence(result_dict)
        cod_evidence = self._extract_cod_evidence(result_dict)
        kbe_evidence = self._extract_kbe_evidence(result_dict)
        suppression_info = self._extract_suppression_info(result_dict)
        gating_info = self._extract_gating_info(result_dict)

        return {
            "position": {"fen": fen, "move": move},
            "tags_applied": tags_applied,
            "tension_evidence": tension_evidence,
            "cod_evidence": cod_evidence,
            "kbe_evidence": kbe_evidence,
            "suppression_info": suppression_info,
            "gating_info": gating_info,
            "raw_diagnostics": {
                "tension": result_dict.get("analysis_context", {}).get("tension_v2_diagnostics"),
                "prophylaxis": result_dict.get("analysis_context", {}).get("prophylaxis_diagnostics"),
                "cod": result_dict.get("analysis_context", {}).get("cod_v2_diagnostics"),
                "kbe": result_dict.get("analysis_context", {}).get("knight_bishop_exchange"),
                "engine_meta": result_dict.get("analysis_context", {}).get("engine_meta", {}),
            }
        }

    def _extract_applied_tags(self, result_dict: Dict[str, Any]) -> List[str]:
        """Extract list of applied tag names from result."""
        tags = []

        # Check boolean fields in priority order
        tag_fields = [
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

        for field in tag_fields:
            if result_dict.get(field, False):
                tags.append(field)

        # Add CoD subtype if present
        if result_dict.get("control_over_dynamics") and result_dict.get("cod_subtype"):
            tags.append(f"control_over_dynamics_{result_dict['cod_subtype']}")

        return tags

    def _extract_tension_evidence(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tension detector evidence."""
        analysis_ctx = result_dict.get("analysis_context", {})
        tension_diag = analysis_ctx.get("tension_v2_diagnostics", {})
        engine_meta = analysis_ctx.get("engine_meta", {})
        tension_support = engine_meta.get("tension_support", {})

        evidence = {
            "detected": False,
            "tags_found": tension_diag.get("tags_found", []),
            "metrics": {},
            "thresholds": {},
            "notes": tension_diag.get("diagnostic_info", {}).get("notes", ""),
        }

        # Extract metrics from tension_support
        if tension_support:
            evidence["detected"] = True
            evidence["metrics"] = {
                "mobility_delta": tension_support.get("mobility_delta", 0.0),
                "contact_delta": tension_support.get("contact_delta", 0.0),
                "volatility_after": tension_support.get("volatility_after", 0.0),
                "score_gap_cp": tension_support.get("score_gap_cp", 0),
                "eval_drop_cp": tension_support.get("eval_drop_cp", 0),
            }
            evidence["thresholds"] = {
                "min_mobility_evidence": 0.10,
                "min_contact_evidence": 0.01,
                "tension_creation_threshold": 0.15,
            }

        return evidence

    def _extract_cod_evidence(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract CoD/Prophylaxis detector evidence."""
        analysis_ctx = result_dict.get("analysis_context", {})
        prop_diag = analysis_ctx.get("prophylaxis_diagnostics", {})
        cod_diag = analysis_ctx.get("cod_v2_diagnostics", {})
        engine_meta = analysis_ctx.get("engine_meta", {})
        cod_support = engine_meta.get("cod_support", {})

        evidence = {
            "detected": False,
            "tags_found": [],
            "subtype": result_dict.get("cod_subtype"),
            "all_detected": [],
            "metrics": {},
            "notes": "",
        }

        # Try prophylaxis diagnostics first
        if prop_diag:
            evidence["detected"] = bool(prop_diag.get("tags_found"))
            evidence["tags_found"] = prop_diag.get("tags_found", [])
            evidence["notes"] = prop_diag.get("diagnostic_info", {}).get("notes", "")

        # Try CoD v2 diagnostics
        if cod_diag:
            evidence["detected"] = bool(cod_diag.get("tags_found"))
            evidence["tags_found"] = cod_diag.get("tags_found", [])
            evidence["notes"] = cod_diag.get("diagnostic_info", {}).get("notes", "")

        # Extract cod_support structure
        if cod_support:
            evidence["detected"] = True
            evidence["all_detected"] = cod_support.get("all_detected", [])
            evidence["metrics"] = {
                "volatility_drop_cp": engine_meta.get("volatility_drop_cp", 0),
                "opp_mobility_drop": engine_meta.get("opp_mobility_drop", 0.0),
                "tension_delta": engine_meta.get("tension_delta", 0.0),
            }

        return evidence

    def _extract_kbe_evidence(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Knight-Bishop Exchange detector evidence."""
        analysis_ctx = result_dict.get("analysis_context", {})
        kbe_diag = analysis_ctx.get("knight_bishop_exchange", {})

        evidence = {
            "detected": kbe_diag.get("detected", False),
            "subtype": kbe_diag.get("subtype", None),  # accurate/inaccurate/bad
            "eval_delta_cp": kbe_diag.get("eval_delta_cp", 0),
            "recapture_rank": kbe_diag.get("recapture_rank", None),
            "recapture_square": kbe_diag.get("recapture_square", None),
            "depth_used": kbe_diag.get("depth_used", None),
            "topn_checked": kbe_diag.get("topn_checked", None),
            "opponent_candidates": kbe_diag.get("opponent_candidates", []),
            "thresholds": [10, 30],  # Default thresholds
        }

        # Extract thresholds from env if available
        threshold_str = os.getenv("KBE_THRESHOLDS", "10,30")
        try:
            evidence["thresholds"] = [int(x) for x in threshold_str.split(",")]
        except:
            pass

        return evidence

    def _extract_suppression_info(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract suppression reasons for non-selected tags."""
        analysis_ctx = result_dict.get("analysis_context", {})
        engine_meta = analysis_ctx.get("engine_meta", {})
        cod_support = engine_meta.get("cod_support", {})

        suppression = {
            "suppressed_by": cod_support.get("suppressed_by", []),
            "cooldown_hit": cod_support.get("cooldown_hit", False),
            "cooldown_remaining": 0,  # TODO: extract if available
        }

        # Add reason descriptions
        reasons = []
        for item in suppression["suppressed_by"]:
            if isinstance(item, str):
                reasons.append({"tag": item, "reason": "lower_priority"})
            elif isinstance(item, dict):
                reasons.append(item)

        suppression["reasons"] = reasons

        return suppression

    def _extract_gating_info(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Extract gating check results."""
        analysis_ctx = result_dict.get("analysis_context", {})
        engine_meta = analysis_ctx.get("engine_meta", {})
        cod_support = engine_meta.get("cod_support", {})
        gate_log = cod_support.get("gate_log", {})

        gating = {
            "gate_log": gate_log,
            "gates_passed": {},
        }

        # Parse gate log to determine which gates passed
        # Use the recorded "passed" flag directly instead of reconstructing
        for subtype, gate in gate_log.items():
            if isinstance(gate, dict):
                # Use the recorded passed flag from the gate log
                overall_passed = gate.get("passed", False)

                # Count individual gate checks for detailed metrics
                checks = []

                # Check volatility gate
                if "env_ok" in gate:
                    checks.append(("volatility", gate["env_ok"]))
                elif "volatility_drop_cp" in gate and "volatility_threshold" in gate:
                    vol_value = gate["volatility_drop_cp"]
                    vol_threshold = gate["volatility_threshold"]
                    checks.append(("volatility", vol_value >= vol_threshold))

                # Check mobility gate
                if "mobility_ok" in gate:
                    checks.append(("mobility", gate["mobility_ok"]))
                elif ("opp_mobility_drop" in gate or "mobility_drop" in gate) and "mobility_threshold" in gate:
                    mob_value = gate.get("opp_mobility_drop", gate.get("mobility_drop", 0))
                    mob_threshold = gate["mobility_threshold"]
                    checks.append(("mobility", mob_value >= mob_threshold))

                # Check tension gate
                if "t_ok" in gate:
                    checks.append(("tension", gate["t_ok"]))
                elif "tension_ok" in gate:
                    checks.append(("tension", gate["tension_ok"]))
                elif "tension_delta" in gate and "tension_threshold" in gate:
                    tension_delta = gate["tension_delta"]
                    tension_threshold = gate["tension_threshold"]
                    checks.append(("tension", tension_delta <= tension_threshold))

                # Calculate pass/total from individual checks
                total = len(checks)
                passed = sum(1 for _, check_passed in checks if check_passed)

                gating["gates_passed"][subtype] = {
                    "passed": passed,
                    "total": total,
                    "percentage": (passed / total * 100) if total > 0 else 0,
                    "overall_passed": overall_passed,  # Record the actual detector decision
                    "gate_data": gate,
                    "checks": checks,  # Preserve individual check results
                }

        return gating

    def format_text_report(self, evidence: Dict[str, Any]) -> str:
        """Format evidence as text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("DETECTOR EVIDENCE REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Check pipeline version and warn if legacy
        engine_meta = evidence["raw_diagnostics"].get("engine_meta", {})
        new_pipeline = engine_meta.get("__new_pipeline__", None)
        if new_pipeline is False:
            lines.append("⚠️  WARNING: Legacy pipeline detected!")
            lines.append("   KBE and other v2 detectors are NOT available in legacy mode.")
            lines.append("   To enable new detectors, run with: NEW_PIPELINE=1")
            lines.append("   Or set use_new=True when calling tag_position()")
            lines.append("")
        elif new_pipeline is True:
            lines.append("✅ New pipeline active (v2 detectors enabled)")
            lines.append("")

        # Position info
        pos = evidence["position"]
        lines.append(f"Position: {pos['fen']}")
        lines.append(f"Move: {pos['move']}")
        lines.append("")

        # Tags applied
        lines.append("TAGS APPLIED:")
        if evidence["tags_applied"]:
            for tag in evidence["tags_applied"]:
                lines.append(f"  ✓ {tag}")
        else:
            lines.append("  (none)")
        lines.append("")

        # Tension evidence
        lines.append("-" * 80)
        lines.append("TENSION DETECTOR EVIDENCE")
        lines.append("-" * 80)
        tension = evidence["tension_evidence"]
        if tension["detected"]:
            lines.append(f"Status: DETECTED")
            lines.append(f"Tags found: {', '.join(tension['tags_found']) if tension['tags_found'] else 'none'}")
            lines.append("")
            lines.append("Metrics:")
            for key, value in tension["metrics"].items():
                threshold = tension["thresholds"].get(f"min_{key}", "N/A")
                bar = self._make_progress_bar(value, 1.0, width=30)
                lines.append(f"  {key:25s}: {value:7.3f} {bar} (threshold: {threshold})")
            if tension["notes"]:
                lines.append(f"\nNotes: {tension['notes']}")
        else:
            lines.append("Status: NOT DETECTED")
        lines.append("")

        # CoD evidence
        lines.append("-" * 80)
        lines.append("COD/PROPHYLAXIS DETECTOR EVIDENCE")
        lines.append("-" * 80)
        cod = evidence["cod_evidence"]
        if cod["detected"]:
            lines.append(f"Status: DETECTED")
            lines.append(f"Selected subtype: {cod['subtype'] or 'N/A'}")
            lines.append(f"Tags found: {', '.join(cod['tags_found']) if cod['tags_found'] else 'none'}")
            if cod["all_detected"]:
                lines.append(f"All detected subtypes: {', '.join(cod['all_detected'])}")
            lines.append("")
            lines.append("Metrics:")
            for key, value in cod["metrics"].items():
                bar = self._make_progress_bar(abs(value), 200.0, width=30)
                lines.append(f"  {key:25s}: {value:7.1f} {bar}")
            if cod["notes"]:
                lines.append(f"\nNotes: {cod['notes']}")
        else:
            lines.append("Status: NOT DETECTED")
        lines.append("")

        # KBE evidence
        lines.append("-" * 80)
        lines.append("KNIGHT-BISHOP EXCHANGE DETECTOR EVIDENCE")
        lines.append("-" * 80)
        kbe = evidence["kbe_evidence"]
        if kbe["detected"]:
            lines.append(f"Status: DETECTED")
            lines.append(f"Subtype: {kbe['subtype'] or 'N/A'}")
            lines.append(f"Eval delta: {kbe['eval_delta_cp']}cp")

            # Thresholds and classification
            t1, t2 = kbe["thresholds"]
            lines.append(f"Thresholds: <{t1}cp = accurate, {t1}-{t2}cp = inaccurate, ≥{t2}cp = bad")
            lines.append("")

            # Recapture info
            if kbe["recapture_rank"] is not None:
                lines.append(f"Recapture details:")
                lines.append(f"  Rank in opponent's top-N: #{kbe['recapture_rank']}")
                if kbe["recapture_square"]:
                    lines.append(f"  Recapture square: {kbe['recapture_square']}")
                lines.append(f"  Depth used: {kbe['depth_used']}")
                lines.append(f"  Top-N checked: {kbe['topn_checked']}")
                lines.append("")

            # Opponent candidates
            if kbe["opponent_candidates"]:
                lines.append("Opponent top moves:")
                for idx, cand in enumerate(kbe["opponent_candidates"][:5], 1):
                    if isinstance(cand, dict):
                        move_str = cand.get("move", "?")
                        score_cp = cand.get("score_cp", 0)
                        lines.append(f"  #{idx}: {move_str} ({score_cp:+d}cp)")
                    elif isinstance(cand, tuple) and len(cand) == 2:
                        lines.append(f"  #{idx}: {cand[0]} ({cand[1]:+d}cp)")
        else:
            lines.append("Status: NOT DETECTED")
            lines.append("(Not a minor piece exchange or recapture not found in top-N)")
        lines.append("")

        # Suppression info
        lines.append("-" * 80)
        lines.append("SUPPRESSION INFO")
        lines.append("-" * 80)
        supp = evidence["suppression_info"]
        if supp["suppressed_by"]:
            lines.append("Suppressed tags:")
            for reason in supp["reasons"]:
                tag_name = reason.get("tag", "unknown")
                reason_text = reason.get("reason", "unknown")
                lines.append(f"  ✗ {tag_name} (reason: {reason_text})")
        else:
            lines.append("No tags suppressed")

        if supp["cooldown_hit"]:
            lines.append(f"\n⏱ Cooldown active (remaining: {supp['cooldown_remaining']} plies)")
        lines.append("")

        # Gating info
        lines.append("-" * 80)
        lines.append("GATING DIAGNOSTICS")
        lines.append("-" * 80)
        gating = evidence["gating_info"]
        if gating["gates_passed"]:
            lines.append("Gate check results:")
            for subtype, gate_result in gating["gates_passed"].items():
                passed = gate_result["passed"]
                total = gate_result["total"]
                pct = gate_result["percentage"]
                overall_passed = gate_result.get("overall_passed", False)
                bar = self._make_progress_bar(passed, total, width=20)
                # Use overall_passed flag to determine PASS/FAIL status
                status = "✓ PASS" if overall_passed else "✗ FAIL"
                lines.append(f"  {subtype:20s}: {passed}/{total} {bar} {pct:5.1f}% {status}")
        else:
            lines.append("No gate checks recorded")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def _make_progress_bar(self, value: float, max_value: float, width: int = 30) -> str:
        """Create a text progress bar."""
        if max_value <= 0:
            return "[" + " " * width + "]"

        ratio = min(value / max_value, 1.0)
        filled = int(ratio * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"

    def format_html_report(self, evidence_list: List[Dict[str, Any]]) -> str:
        """Format evidence as HTML report (for batch mode)."""
        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html>")
        html.append("<head>")
        html.append("<title>Detector Evidence Report</title>")
        html.append("<style>")
        html.append("body { font-family: 'Courier New', monospace; margin: 20px; background: #1e1e1e; color: #d4d4d4; }")
        html.append("h1 { color: #4ec9b0; }")
        html.append("h2 { color: #9cdcfe; margin-top: 30px; }")
        html.append("h3 { color: #dcdcaa; }")
        html.append(".position { background: #252526; padding: 15px; margin: 20px 0; border-left: 4px solid #4ec9b0; }")
        html.append(".tag-applied { color: #4fc1ff; font-weight: bold; }")
        html.append(".tag-suppressed { color: #f48771; }")
        html.append(".metric { margin: 5px 0; }")
        html.append(".progress-bar { display: inline-block; width: 300px; height: 20px; background: #3c3c3c; border: 1px solid #555; }")
        html.append(".progress-fill { height: 100%; background: linear-gradient(90deg, #4ec9b0, #4fc1ff); }")
        html.append(".notes { background: #2d2d30; padding: 10px; margin: 10px 0; border-left: 3px solid #007acc; }")
        html.append(".gate-pass { color: #4ec9b0; }")
        html.append(".gate-fail { color: #f48771; }")
        html.append("</style>")
        html.append("</head>")
        html.append("<body>")
        html.append("<h1>🔍 Detector Evidence Report</h1>")
        html.append(f"<p>Generated {len(evidence_list)} position report(s)</p>")

        for idx, evidence in enumerate(evidence_list, 1):
            pos = evidence["position"]
            html.append(f'<div class="position">')
            html.append(f"<h2>Position {idx}</h2>")
            html.append(f"<p><strong>FEN:</strong> {pos['fen']}</p>")
            html.append(f"<p><strong>Move:</strong> {pos['move']}</p>")

            # Tags applied
            html.append("<h3>Tags Applied</h3>")
            if evidence["tags_applied"]:
                html.append("<ul>")
                for tag in evidence["tags_applied"]:
                    html.append(f'<li class="tag-applied">✓ {tag}</li>')
                html.append("</ul>")
            else:
                html.append("<p>(none)</p>")

            # Tension evidence
            tension = evidence["tension_evidence"]
            html.append("<h3>Tension Detector</h3>")
            if tension["detected"]:
                html.append(f"<p><strong>Status:</strong> DETECTED</p>")
                html.append(f"<p><strong>Tags:</strong> {', '.join(tension['tags_found']) if tension['tags_found'] else 'none'}</p>")
                for key, value in tension["metrics"].items():
                    threshold = tension["thresholds"].get(f"min_{key}", "N/A")
                    pct = min(value * 100, 100)
                    html.append(f'<div class="metric">')
                    html.append(f'<strong>{key}:</strong> {value:.3f} ')
                    html.append(f'<div class="progress-bar"><div class="progress-fill" style="width: {pct}%"></div></div>')
                    html.append(f' (threshold: {threshold})')
                    html.append(f'</div>')
                if tension["notes"]:
                    html.append(f'<div class="notes">{tension["notes"]}</div>')
            else:
                html.append("<p><strong>Status:</strong> NOT DETECTED</p>")

            # CoD evidence
            cod = evidence["cod_evidence"]
            html.append("<h3>CoD/Prophylaxis Detector</h3>")
            if cod["detected"]:
                html.append(f"<p><strong>Status:</strong> DETECTED</p>")
                html.append(f"<p><strong>Subtype:</strong> {cod['subtype'] or 'N/A'}</p>")
                html.append(f"<p><strong>Tags:</strong> {', '.join(cod['tags_found']) if cod['tags_found'] else 'none'}</p>")
                if cod["all_detected"]:
                    html.append(f"<p><strong>All detected:</strong> {', '.join(cod['all_detected'])}</p>")
                if cod["notes"]:
                    html.append(f'<div class="notes">{cod["notes"]}</div>')
            else:
                html.append("<p><strong>Status:</strong> NOT DETECTED</p>")

            # Suppression
            supp = evidence["suppression_info"]
            html.append("<h3>Suppression Info</h3>")
            if supp["suppressed_by"]:
                html.append("<ul>")
                for reason in supp["reasons"]:
                    tag_name = reason.get("tag", "unknown")
                    reason_text = reason.get("reason", "unknown")
                    html.append(f'<li class="tag-suppressed">✗ {tag_name} (reason: {reason_text})</li>')
                html.append("</ul>")
            else:
                html.append("<p>No tags suppressed</p>")

            html.append("</div>")

        html.append("</body>")
        html.append("</html>")

        return "\n".join(html)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fen", help="FEN position string")
    parser.add_argument("--move", help="Move in UCI format (e.g., e2e4)")
    parser.add_argument("--input", help="Input JSON file with test cases (golden cases format)")
    parser.add_argument("--case-id", help="Specific case ID to analyze from input file")
    parser.add_argument("--batch", action="store_true", help="Process all cases in input file")
    parser.add_argument("--format", choices=["text", "html"], default="text", help="Output format (default: text)")
    parser.add_argument("--output", help="Output file path (default: stdout for text, reports/evidence_report.html for html)")
    parser.add_argument("--engine", default=os.getenv("ENGINE", "/usr/local/bin/stockfish"), help="Stockfish path")
    parser.add_argument("--depth", type=int, default=15, help="Analysis depth (default: 15)")
    parser.add_argument("--multipv", type=int, default=3, help="MultiPV setting (default: 3)")

    args = parser.parse_args()

    # Validate input
    if not args.fen and not args.input:
        parser.error("Either --fen or --input must be specified")

    if args.fen and not args.move:
        parser.error("--move is required when using --fen")

    generator = EvidenceReportGenerator(engine_path=args.engine)

    # Collect test cases
    test_cases = []

    if args.input:
        with open(args.input, 'r') as f:
            cases = json.load(f)

        if args.case_id:
            # Find specific case
            for case in cases:
                if case.get("id") == args.case_id:
                    test_cases.append({"fen": case["fen"], "move": case["move"], "id": case["id"]})
                    break
            if not test_cases:
                print(f"Error: Case ID '{args.case_id}' not found in {args.input}", file=sys.stderr)
                return 1
        elif args.batch:
            # Process all cases
            for case in cases:
                if case.get("fen") and case.get("move"):
                    test_cases.append({"fen": case["fen"], "move": case["move"], "id": case.get("id", "unknown")})
        else:
            # Process first case by default
            if cases and cases[0].get("fen") and cases[0].get("move"):
                test_cases.append({"fen": cases[0]["fen"], "move": cases[0]["move"], "id": cases[0].get("id", "unknown")})
    else:
        # Single position from command line
        test_cases.append({"fen": args.fen, "move": args.move, "id": "cli"})

    if not test_cases:
        print("Error: No valid test cases found", file=sys.stderr)
        return 1

    # Generate evidence for all cases
    evidence_list = []
    for case in test_cases:
        print(f"Analyzing {case['id']}: {case['move']}...", file=sys.stderr)
        evidence = generator.analyze_position(
            fen=case["fen"],
            move=case["move"],
            depth=args.depth,
            multipv=args.multipv,
        )
        evidence_list.append(evidence)

    # Format and output
    if args.format == "text":
        # Text format - one report per case
        output = []
        for evidence in evidence_list:
            output.append(generator.format_text_report(evidence))

        output_text = "\n\n".join(output)

        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, 'w') as f:
                f.write(output_text)
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(output_text)

    elif args.format == "html":
        # HTML format - single report with all cases
        html = generator.format_html_report(evidence_list)

        output_path = args.output or "reports/evidence_report.html"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html)
        print(f"HTML report written to {output_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
