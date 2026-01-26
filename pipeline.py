#!/usr/bin/env python3
"""
Minimal pipeline runner that exercises the rule_tagger2 facade on a single
FEN + move or on positions.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Any

import chess  # type: ignore

from rule_tagger2.core.facade import tag_position

ENGINE_PATH_DEFAULT = "/usr/local/bin/stockfish"


def analyse_position(engine_path: str, fen: str, move: str, *, depth: int = 10, multipv: int = 6) -> Dict[str, Any]:
    """Run tagger and return a compact result dictionary."""
    chess.Board(fen)  # raises if invalid; keeps behaviour explicit
    result = tag_position(engine_path, fen, move, depth=depth, multipv=multipv)
    engine_meta = getattr(result, "analysis_context", {}).get("engine_meta", {}) if hasattr(result, "analysis_context") else {}
    tags_final = (
        engine_meta.get("tags_final_v8")
        or engine_meta.get("tags_final")
        or engine_meta.get("gating", {}).get("tags_primary")
        or []
    )
    return {
        "fen": fen,
        "move": move,
        "mode": result.mode,
        "tactical_weight": result.tactical_weight,
        "tags": list(tags_final),
        "eval_before": result.eval_before,
        "eval_played": result.eval_played,
        "delta": result.eval_played - result.eval_before,
    }


def run_single(args: argparse.Namespace) -> int:
    if not args.fen or not args.move:
        print("❌ --fen and --move are required for single analysis", file=sys.stderr)
        return 1
    try:
        payload = analyse_position(
            args.stockfish,
            args.fen,
            args.move,
            depth=args.depth,
            multipv=args.multipv,
        )
    except Exception as exc:  # pragma: no cover - runtime guard
        print(f"❌ Failed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload))
    return 0


def _load_positions(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} does not contain a list of positions")
    return raw


def run_batch(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input {input_path} not found", file=sys.stderr)
        return 1

    try:
        positions = _load_positions(input_path)
    except Exception as exc:
        print(f"❌ Failed to read {input_path}: {exc}", file=sys.stderr)
        return 1

    results: List[Dict[str, Any]] = []
    total = len(positions)
    for idx, item in enumerate(positions, start=1):
        fen = item.get("fen")
        move = item.get("move")
        if not fen or not move:
            print(f"⚠️  Skipping entry {idx}: missing fen/move", file=sys.stderr)
            continue
        try:
            results.append(
                analyse_position(
                    args.stockfish,
                    fen,
                    move,
                    depth=args.depth,
                    multipv=args.multipv,
                )
            )
        except Exception as exc:
            print(f"⚠️  Error at {idx}: {exc}", file=sys.stderr)
        if idx % 5 == 0 or idx == total:
            print(f"Progress: {idx}/{total}...", flush=True)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"✅ Done: {len(results)} results written to {output_path}")
    else:
        print(json.dumps(results))
    return 0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="rule_tagger2 pipeline runner")
    parser.add_argument("--fen", help="FEN string for single analysis")
    parser.add_argument("--move", help="Move (SAN or UCI) to analyse")
    parser.add_argument("--stockfish", default=ENGINE_PATH_DEFAULT, help="Path to Stockfish binary")
    parser.add_argument("--depth", type=int, default=10, help="Engine depth (default: 10)")
    parser.add_argument("--multipv", type=int, default=6, help="MultiPV setting (default: 6)")
    parser.add_argument("--input", "-i", default="random_test/positions.json", help="Positions JSON for batch mode")
    parser.add_argument("--output", "-o", help="Output file path (batch mode writes JSON; single mode optional)")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.fen or args.move:
        return run_single(args)
    return run_batch(args)


if __name__ == "__main__":
    raise SystemExit(main())
