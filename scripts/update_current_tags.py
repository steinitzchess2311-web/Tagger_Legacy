#!/usr/bin/env python3
"""Refresh the `current_tags` field in tests/golden_cases/cases.json via the pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import chess

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from pipeline import ENGINE_PATH_DEFAULT, analyse_position


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="tests/golden_cases/cases.json",
        help="Path to the golden cases JSON file (default: tests/golden_cases/cases.json).",
    )
    parser.add_argument(
        "--stockfish",
        default=ENGINE_PATH_DEFAULT,
        help=f"Path to the Stockfish binary (default: {ENGINE_PATH_DEFAULT}).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=10,
        help="Search depth used by the pipeline (default: 10).",
    )
    parser.add_argument(
        "--multipv",
        type=int,
        default=6,
        help="MultiPV setting passed to the pipeline (default: 6).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-case updates; still prints a final summary.",
    )
    return parser.parse_args(argv)


def load_cases(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} does not contain a list of cases")
    return raw


def update_current_tags(
    cases: List[Dict[str, Any]],
    *,
    stockfish: str,
    depth: int,
    multipv: int,
    quiet: bool,
) -> int:
    updated = 0
    for idx, case in enumerate(cases, start=1):
        fen = case.get("fen")
        move = case.get("move_uci") or case.get("move")
        case_id = case.get("id") or f"case_{idx:03d}"

        if not fen or not move:
            print(f"Skipping {case_id}: missing fen or move.", file=sys.stderr)
            continue

        # Ensure move is UCI; golden files often store SAN for readability.
        if not _looks_like_uci(move):
            try:
                board = chess.Board(fen)
                move = board.parse_san(move).uci()
                case["move_uci"] = move
            except Exception as exc:
                print(
                    f"Skipping {case_id}: cannot convert move '{case.get('move')}' to UCI ({exc}).",
                    file=sys.stderr,
                )
                continue

        try:
            payload = analyse_position(
                stockfish,
                fen,
                move,
                depth=depth,
                multipv=multipv,
            )
        except Exception as exc:
            print(f"Failed to analyse {case_id}: {exc}", file=sys.stderr)
            continue

        case["current_tags"] = payload.get("tags", [])
        updated += 1
        if not quiet:
            print(f"[{case_id}] current_tags -> {case['current_tags']}")

    return updated


def _looks_like_uci(move: str) -> bool:
    """Heuristic check for UCI strings (e2e4, e7e8q, etc.)."""
    if not isinstance(move, str):
        return False
    return len(move) in (4, 5) and move[0].islower() and move[2].islower()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser().resolve()

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        cases = load_cases(input_path)
    except Exception as exc:
        print(f"Failed to read {input_path}: {exc}", file=sys.stderr)
        return 1

    updated = update_current_tags(
        cases,
        stockfish=args.stockfish,
        depth=args.depth,
        multipv=args.multipv,
        quiet=args.quiet,
    )

    input_path.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(f"Updated current_tags for {updated}/{len(cases)} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
