"""
testing_random_pick.py
=======================

Batch-testing helper that:
  • scans `random_test/` for PGN files,
  • randomly samples positions according to the provided heuristics,
  • stores the gathered FEN/move pairs in `random_test/positions.json`,
  • invokes an external `pipeline.py` script to analyse each sample,
  • writes grouped result packets (≤60 entries each) into
    `random_test/random_test_results/`.

Requirements:
  pip install python-chess

Usage:
  python3 testing_random_pick.py [--limit 120]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import chess
import chess.pgn

# ===============================
# CONFIG
# ===============================
BASE_DIR = Path("random_test")
OUT_DIR = BASE_DIR / "random_test_results"
POSITION_FILE = BASE_DIR / "positions.json"
ENGINE_PATH = "/usr/local/bin/stockfish"  # Adjust if needed.
PIPELINE_SCRIPT = Path("pipeline.py")
BATCH_LIMIT = 60  # Max entries per result bundle.
PGN_DIR = OUT_DIR / "random_results_pgn"
DEFAULT_DEPTH = 10

# Random sampling is inherently stochastic; set a seed if repeatability is desired.
RNG = random.Random()


# ===============================
# STEP 1 · 提取随机局面
# ===============================
def extract_positions_from_pgn(pgn_path: Path) -> List[Dict[str, str]]:
    """Extract candidate positions from a single PGN file."""
    positions: List[Dict[str, str]] = []
    with pgn_path.open(encoding="utf-8", errors="ignore") as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break

            headers = game.headers
            has_fen = bool(headers.get("FEN", "").strip())
            moves = list(game.mainline_moves())
            total = len(moves)
            if total == 0:
                continue

            if not has_fen:
                if total <= 12:
                    continue
                start = 7
                valid = list(range(start, total))
                if not valid:
                    continue
                sample_count = min(2, len(valid))
                picks = sorted(RNG.sample(valid, sample_count))
            else:
                if total > 6:
                    color = RNG.choice([chess.WHITE, chess.BLACK])
                    move_indices = [i for i in range(total) if (i % 2 == 0) == color]
                    if not move_indices:
                        move_indices = list(range(total))
                    sample_count = min(4, len(move_indices))
                    picks = sorted(RNG.sample(move_indices, sample_count))
                else:
                    picks = list(range(total))

            board = game.board()
            for idx in picks:
                board = game.board()
                for ply in range(idx):
                    board.push(moves[ply])
                fen = board.fen()
                move_san = board.san(moves[idx])
                positions.append({"fen": fen, "move": move_san})
    return positions


# ===============================
# STEP 2 · 主执行流程
# ===============================
def gather_positions(limit: Optional[int] = None) -> List[Dict[str, str]]:
    """Aggregate sampled positions from every PGN within BASE_DIR."""
    if not BASE_DIR.exists():
        raise FileNotFoundError(f"Base directory {BASE_DIR} not found.")

    all_positions: List[Dict[str, str]] = []
    print("📂 Scanning random_test folder...")
    for entry in sorted(BASE_DIR.iterdir()):
        if entry.suffix.lower() != ".pgn":
            continue
        print(f"🧩 Processing {entry.name} ...")
        all_positions.extend(extract_positions_from_pgn(entry))
        if limit and len(all_positions) >= limit:
            break
    if limit:
        return all_positions[:limit]
    return all_positions


def write_positions(positions: List[Dict[str, str]]) -> None:
    """Persist sampled positions into POSITION_FILE."""
    POSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with POSITION_FILE.open("w", encoding="utf-8") as handle:
        json.dump(positions, handle, indent=2)
    print(f"✅ Extracted {len(positions)} total positions → {POSITION_FILE}")


# ===============================
# STEP 3 · 调用 pipeline.py 分析
# ===============================
def run_pipeline(positions: List[Dict[str, str]], depth: int) -> None:
    """Invoke pipeline.py on position batches and store bundled outputs."""
    if not PIPELINE_SCRIPT.exists():
        raise FileNotFoundError(
            f"pipeline script not found at {PIPELINE_SCRIPT}. "
            "Please ensure pipeline.py is available before running this tool."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PGN_DIR.mkdir(parents=True, exist_ok=True)

    existing = sorted(OUT_DIR.glob("random_results_package_*.json"))
    start_index = len(existing) + 1

    print("⚙️ Running engine analysis through pipeline.py ...")
    for batch_idx, start in enumerate(range(0, len(positions), BATCH_LIMIT), start=start_index):
        chunk = positions[start:start + BATCH_LIMIT]
        if not chunk:
            continue
        temp_input = OUT_DIR / f"_temp_positions_{batch_idx}.json"
        temp_input.write_text(json.dumps(chunk, indent=2), encoding="utf-8")

        output_json = OUT_DIR / f"random_results_package_{batch_idx}.json"
        cmd = [
            sys.executable,
            str(PIPELINE_SCRIPT),
            "--input",
            str(temp_input),
            "--output",
            str(output_json),
            "--depth",
            str(depth),
        ]
        subprocess.run(cmd, check=False)
        temp_input.unlink(missing_ok=True)

        if not output_json.exists():
            print(f"⚠️ Pipeline did not produce {output_json}", file=sys.stderr)
            continue

        try:
            results = json.loads(output_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"⚠️ Failed to parse {output_json}: {exc}", file=sys.stderr)
            continue

        print(f"📦 Saved {len(results)} results → {output_json}")
        write_pgn(output_json.with_suffix(".pgn"), results)

    print("🎯 All done. Results stored in random_test_results/")


def write_pgn(pgn_path: Path, results: List[Dict[str, str]]) -> None:
    """Generate a PGN file mirroring the JSON package (one mini-game per entry)."""
    PGN_DIR.mkdir(parents=True, exist_ok=True)
    # Align with json naming (same filename, .pgn extension) inside PGN_DIR
    pgn_file = PGN_DIR / pgn_path.name
    lines: List[str] = []
    for idx, record in enumerate(results, start=1):
        fen = record.get("fen")
        move = record.get("move")
        if not fen or not move:
            continue
        lines.append(f'[Event "RandomTest {idx}"]')
        lines.append('[Site "Codex random_test"]')
        lines.append('[Round "-"]')
        lines.append('[White "?"]')
        lines.append('[Black "?"]')
        lines.append(f'[SetUp "1"]')
        lines.append(f'[FEN "{fen}"]')
        lines.append("")
        try:
            board = chess.Board(fen)
            move_obj = board.parse_san(move)
            board.push(move_obj)
            san_move = move
        except Exception:
            san_move = move
        lines.append(f"1. {san_move} *")
        lines.append("")
    pgn_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"📝 PGN saved → {pgn_file}")


# ===============================
# EXECUTION
# ===============================
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Random sampler + pipeline runner")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of sampled positions (default: all).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help=f"Engine depth passed to pipeline.py (default: {DEFAULT_DEPTH}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible sampling.",
    )
    return parser.parse_args(argv)


def main(limit: Optional[int], depth: int, seed: Optional[int]) -> None:
    if seed is not None:
        RNG.seed(seed)
    positions = gather_positions(limit=limit)
    write_positions(positions)
    if positions:
        run_pipeline(positions, depth=depth)
    else:
        print("⚠️ No positions extracted – skipping pipeline execution.")


if __name__ == "__main__":
    cli_args = parse_args()
    main(limit=cli_args.limit, depth=cli_args.depth, seed=cli_args.seed)
