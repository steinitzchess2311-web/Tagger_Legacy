"""
Golden Regression Test Runner for P2 Day 2

Use this script to run the golden test cases through the currently configured
rule-tagger pipeline (legacy or new).

The default mode (`--pipeline auto`) respects NEW_PIPELINE, which keeps the
batch analyses and Lichess bot in sync without extra flags. Pass `--compare` if
you still need to exercise both pipelines for a regression sanity check.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add project root to the path so relative imports work from the scripts folder.
sys.path.insert(0, str(Path(__file__).parent.parent))

import chess

from rule_tagger_lichessbot.codex_utils import analyze_position
from rule_tagger_lichessbot.pipeline_mode import (
    PIPELINE_AUTO,
    PIPELINE_LEGACY,
    PIPELINE_NEW,
    pipeline_mode_from_env,
    use_new_from_mode,
)

TENSION_FLAGS = ("tension_creation", "neutral_tension_creation")


def san_to_uci(fen: str, san_move: str) -> str:
    """
    Convert SAN move to UCI format.
    """
    board = chess.Board(fen)
    try:
        move = board.parse_san(san_move)
        return move.uci()
    except ValueError as exc:
        try:
            chess.Move.from_uci(san_move)
            return san_move
        except ValueError:
            raise ValueError(f"Cannot parse move '{san_move}' for FEN '{fen}': {exc}")


def load_golden_cases(path: Path) -> List[Dict[str, Any]]:
    """
    Load golden cases and normalize every move into UCI.
    """
    with path.open("r", encoding="utf-8") as handle:
        cases = json.load(handle)

    for case in cases:
        original_move = case.get("move")
        try:
            case["move_uci"] = san_to_uci(case["fen"], original_move)
            case["move_san"] = original_move
        except Exception as exc:
            print(f"Warning: Cannot convert move '{original_move}' in case {case.get('id')}: {exc}")
            case["move_uci"] = original_move
            case["move_san"] = original_move

    return cases


def run_case(case: Dict[str, Any], engine_path: str, mode: str) -> Dict[str, Any]:
    """
    Run the provided golden case through a single pipeline mode.
    """
    analysis = analyze_position(
        case["fen"],
        case["move_uci"],
        engine_path=engine_path,
        use_new=use_new_from_mode(mode),
    )
    tags_all = analysis.get("tags", {}).get("all", {})
    tension_flags = {tag: bool(tags_all.get(tag)) for tag in TENSION_FLAGS}
    return {"analysis": analysis, "tension_flags": tension_flags}


def compare_results(
    case_id: str,
    legacy: Dict[str, Any],
    new: Dict[str, Any],
    verbose: bool = False,
) -> Tuple[bool, str]:
    """
    Compare legacy and new pipeline flags for a golden case.
    """
    legacy_flags = legacy["tension_flags"]
    new_flags = new["tension_flags"]
    tension_match = legacy_flags["tension_creation"] == new_flags["tension_creation"]
    neutral_match = legacy_flags["neutral_tension_creation"] == new_flags["neutral_tension_creation"]
    if tension_match and neutral_match:
        if verbose:
            active_flags = [name for name, active in legacy_flags.items() if active]
            if active_flags:
                return True, f"✓ Tension flags match: {active_flags}"
            return True, "✓ No tension detected (both)"
        return True, "✓"

    msg_parts = ["✗ Tension flags mismatch:"]
    msg_parts.append(
        f"  tension_creation: legacy={legacy_flags['tension_creation']}, new={new_flags['tension_creation']} {'✓' if tension_match else '✗'}"
    )
    msg_parts.append(
        f"  neutral_tension:  legacy={legacy_flags['neutral_tension_creation']}, new={new_flags['neutral_tension_creation']} {'✓' if neutral_match else '✗'}"
    )
    return False, "\n".join(msg_parts)


def print_summary(total: int, passed: int, failed: int) -> None:
    """
    Print the regression summary when comparing two pipelines.
    """
    print("\n" + "=" * 60)
    print("GOLDEN REGRESSION TEST SUMMARY")
    print("=" * 60)
    print(f"Total cases:  {total}")
    print(f"Passed:       {passed} ({100 * passed / total:.1f}%)")
    print(f"Failed:       {failed} ({100 * failed / total:.1f}%)")
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - 100% tension tag match!")
        print("   TensionDetector is ready for production.")
    else:
        print(f"\n❌ {failed} test(s) failed")
        print("   Review failures above and fix TensionDetector logic.")
    print("=" * 60)


def print_single_mode_summary(total: int, errors: int, mode: str) -> None:
    """
    Print a quick summary when only one pipeline mode is exercised.
    """
    print("\n" + "=" * 60)
    print("GOLDEN REGRESSION TEST SUMMARY")
    print("=" * 60)
    print(f"Pipeline mode: {mode}")
    print(f"Cases analysed: {total}")
    print(f"Errors: {errors}")
    if errors == 0:
        print("\n✅ No runtime errors detected.")
    else:
        print("\n⚠️  See failures file for details.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run golden regression tests.")
    parser.add_argument(
        "--engine",
        default="/opt/homebrew/bin/stockfish",
        help="Path to Stockfish engine",
    )
    parser.add_argument(
        "--cases",
        default="tests/golden_cases/cases.json",
        help="Path to golden cases JSON (default: tests/golden_cases/cases.json)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--filter", help="Filter cases by ID substring (e.g., 'tension' or 'case_001')")
    parser.add_argument(
        "--pipeline",
        choices=(PIPELINE_AUTO, PIPELINE_NEW, PIPELINE_LEGACY),
        default=PIPELINE_AUTO,
        help="Select which pipeline to exercise (auto=use NEW_PIPELINE).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both pipelines and compare their tension flags (overrides --pipeline).",
    )

    args = parser.parse_args()

    engine_path = Path(args.engine)
    if not engine_path.exists():
        print(f"❌ Engine not found: {engine_path}")
        print("   Please specify with --engine /path/to/stockfish")
        sys.exit(1)

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"❌ Golden cases not found: {cases_path}")
        sys.exit(1)

    cases = load_golden_cases(cases_path)
    if args.filter:
        cases = [case for case in cases if args.filter in case.get("id", "")]
        print(f"Filtered to {len(cases)} case(s) matching '{args.filter}'")

    if not cases:
        print("No golden cases to run.")
        sys.exit(0)

    if args.compare:
        pipelines = [PIPELINE_LEGACY, PIPELINE_NEW]
        print("Comparing legacy vs new pipeline on golden cases.")
    else:
        selected = pipeline_mode_from_env() if args.pipeline == PIPELINE_AUTO else args.pipeline
        pipelines = [selected]
        print(f"Running golden cases through the '{selected}' pipeline (NEW_PIPELINE env={pipeline_mode_from_env()}).")

    print(f"Starting {len(cases)} golden test case(s)...")
    print(f"Engine: {engine_path}")
    print("-" * 60)

    total = len(cases)
    passed = 0
    failed = 0
    failures: List[Dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        case_id = case.get("id", f"case_{index}")
        description = case.get("description", "")

        print(f"\n[{index}/{total}] {case_id}")
        if description:
            print(f"    {description}")

        case_results: Dict[str, Dict[str, Any]] = {}
        for mode in pipelines:
            if args.verbose:
                print(f"    Running {mode} pipeline...")
            try:
                case_results[mode] = run_case(case, str(engine_path), mode)
            except Exception as exc:
                failed += 1
                print(f"    ✗ Exception in {mode} pipeline: {exc}")
                if args.verbose:
                    import traceback

                    traceback.print_exc()
                failures.append(
                    {
                        "case_id": case_id,
                        "description": description,
                        "pipeline": mode,
                        "error": str(exc),
                    }
                )
                case_results.clear()
                break

        if not case_results:
            continue

        if len(case_results) == 2:
            legacy = case_results[PIPELINE_LEGACY]
            new = case_results[PIPELINE_NEW]
            match, msg = compare_results(case_id, legacy, new, args.verbose)
            if match:
                passed += 1
                print(f"    {msg}")
            else:
                failed += 1
                print(f"    {msg}")
                failures.append(
                    {
                        "case_id": case_id,
                        "description": description,
                        "legacy_flags": legacy["tension_flags"],
                        "new_flags": new["tension_flags"],
                    }
                )
        else:
            mode = pipelines[0]
            if args.verbose:
                active = [name for name, active in case_results[mode]["tension_flags"].items() if active]
                flag_list = active or ["none"]
                print(f"    [{mode}] tension flags: {', '.join(flag_list)}")

    if args.compare:
        print_summary(total, passed, failed)
    else:
        print_single_mode_summary(total, failed, pipelines[0])

    if failures:
        report_path = Path("test_failures_tension.json")
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(failures, handle, indent=2, ensure_ascii=False)
        print(f"\nFailures saved to: {report_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
