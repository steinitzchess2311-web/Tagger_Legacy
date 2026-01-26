#!/usr/bin/env python3
"""
Convert annotated golden PGN files into JSON bundles for comparison.

Usage:
    python3 random_test/convert_golden_pgn.py \
        --input Golden_sample \
        --output random_test/golden_sample

The script expects each PGN game to contain a single key move with a
comment listing target tags separated by commas. It writes a JSON array
per PGN file with entries:
  {
      "fen": "...",
      "move": "a4",
      "tags": ["intent_expansion", ...],
      "comment": "original comment text"
  }
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, List, Optional

import chess
import chess.pgn


TAG_TOKEN_RE = re.compile(r"[A-Za-z0-9_.]+")


def extract_tags(comment: str) -> List[str]:
    """
    Parse a comment string and extract tag tokens.

    The comment format is expected to be a comma-separated list, possibly
    with parenthetical notes. Example:
        "intent_expansion, neutral_tension_creation (new tag ...), ..."
    """
    tags: List[str] = []
    normalized_comment = comment.replace("\n", ",")
    for raw in normalized_comment.split(","):
        token = raw.strip()
        if not token:
            continue
        token = token.split("(")[0].strip()
        if not token:
            continue
        matches = TAG_TOKEN_RE.findall(token)
        for candidate in matches:
            if "_" in candidate:
                tags.append(candidate)
    return tags


def convert_pgn(pgn_path: Path) -> List[dict]:
    """Read a PGN file and convert games into JSON-ready dicts."""
    entries: List[dict] = []
    with pgn_path.open(encoding="utf-8", errors="ignore") as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            if game.next() is None:
                continue

            board = game.board()
            fen = game.headers.get("FEN") or board.fen()
            node = game.next()
            if node is None:
                continue
            move = node.san()
            raw_comment = node.comment.strip()
            primary_line = raw_comment.splitlines()[0] if raw_comment else ""
            tags = extract_tags(primary_line)
            entries.append(
                {
                    "fen": fen,
                    "move": move,
                    "tags": tags,
                    "comment": raw_comment,
                }
            )
    return entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert golden PGN annotations to JSON.")
    parser.add_argument(
        "--input",
        default="Golden_sample",
        help="Directory containing golden_sample_*.pgn files.",
    )
    parser.add_argument(
        "--output",
        default="random_test/golden_sample",
        help="Directory to write golden_sample_*.json files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing JSON files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    pgn_files = sorted(input_dir.glob("golden_sample_*.pgn"))
    if not pgn_files:
        print(f"⚠️  No PGN files matching golden_sample_*.pgn in {input_dir}")
        return

    for pgn_file in pgn_files:
        entries = convert_pgn(pgn_file)
        if not entries:
            print(f"⚠️  No entries extracted from {pgn_file}")
            continue
        output_path = output_dir / f"{pgn_file.stem}.json"
        if output_path.exists() and not args.overwrite:
            print(f"⏭️  Skipping {output_path} (exists). Use --overwrite to replace.")
            continue
        output_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        print(f"✅ Converted {pgn_file.name} → {output_path} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
