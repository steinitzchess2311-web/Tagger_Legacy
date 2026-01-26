#!/usr/bin/env python3
"""Refresh `current_tags` for the targeted golden cases via the current rule_tagger pipeline."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional

import chess

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from players.tagger_bridge import tag_candidates_payload  # noqa: E402
from rule_tagger_lichessbot.codex_utils import DEFAULT_ENGINE_PATH  # noqa: E402

CASE_FILES = [
    Path(__file__).resolve().parent / "golden_cases" / "cases1.json",
    Path(__file__).resolve().parent / "golden_cases" / "cases2.json",
]


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine",
        default=os.getenv("STOCKFISH_PATH", DEFAULT_ENGINE_PATH),
        help="Path to the Stockfish binary (default: env STOCKFISH_PATH or rule_tagger default).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Silence per-case summaries.",
    )
    return parser.parse_args(argv)


def _looks_like_uci(move: Any) -> bool:
    if not isinstance(move, str):
        return False
    return len(move) in (4, 5) and move[0].islower() and move[2].islower()


def _ensure_move_uci(case: dict) -> Optional[str]:
    move_uci = case.get("move_uci")
    if move_uci:
        return move_uci
    move = case.get("move")
    fen = case.get("fen")
    if not move or not fen:
        return None

    if _looks_like_uci(move):
        case["move_uci"] = move
        return move

    try:
        board = chess.Board(fen)
        parsed = board.parse_san(move).uci()
    except Exception:
        return None
    case["move_uci"] = parsed
    return parsed


def run_tagger_for_case(fen: str, move_uci: str, engine_path: str) -> List[str]:
    payload = {
        "fen": fen,
        "candidates": [
            {
                "uci": move_uci,
                "engine_meta": {"engine_path": engine_path},
            }
        ],
    }
    tagged = tag_candidates_payload(payload)
    candidate = tagged["candidates"][0]
    return candidate.get("tags", [])


def relabel_file(path: Path, engine_path: str, *, quiet: bool = False) -> int:
    with path.open("r", encoding="utf-8") as handle:
        cases = json.load(handle)

    updated = 0
    for idx, case in enumerate(cases, start=1):
        fen = case.get("fen")
        move_uci = _ensure_move_uci(case)
        case_id = case.get("id") or f"case_{idx:03d}"

        if not fen or not move_uci:
            print(f"[WARN] {case_id}: missing fen or move (skipping)", file=sys.stderr)
            continue

        try:
            tags = run_tagger_for_case(fen, move_uci, engine_path)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[ERROR] {case_id}: tagging failed ({exc})", file=sys.stderr)
            continue

        case["current_tags"] = tags
        updated += 1
        if not quiet:
            print(f"[{case_id}] current_tags -> {tags}")

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return updated


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    total = 0
    for path in CASE_FILES:
        if not path.exists():
            print(f"❌ Input file not found: {path}", file=sys.stderr)
            return 1
        updated = relabel_file(path, args.engine, quiet=args.quiet)
        total += updated
    print(f"Updated current_tags for {total} cases across {len(CASE_FILES)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
