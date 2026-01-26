#!/usr/bin/env python3
"""
Validate that all golden test case moves are legal.

Usage:
    python3 scripts/check_golden_legality.py
"""
import json
import sys
from pathlib import Path

import chess

def main():
    golden_path = Path("tests/golden_cases/cases.json")

    if not golden_path.exists():
        print(f"❌ Golden cases file not found: {golden_path}")
        sys.exit(1)

    with golden_path.open() as f:
        cases = json.load(f)

    bad = []

    for case in cases:
        case_id = case.get("id", "unknown")
        fen = case.get("fen")
        move_str = case.get("move")

        if not fen or not move_str:
            bad.append((case_id, move_str, fen, "Missing FEN or move"))
            continue

        try:
            board = chess.Board(fen)
        except Exception as e:
            bad.append((case_id, move_str, fen, f"Invalid FEN: {e}"))
            continue

        try:
            # Try parsing as SAN first (handles most cases including "exd5", "Nf3", "O-O")
            move = board.parse_san(move_str)

            # Check if move is legal (parse_san already validates this, but double-check)
            if move not in board.legal_moves:
                bad.append((case_id, move_str, fen, "Parsed but not in legal moves"))
        except Exception as e:
            bad.append((case_id, move_str, fen, f"Cannot parse move: {e}"))

    if bad:
        print("❌ Illegal cases found:")
        print()
        for case_id, move_str, fen, error in bad:
            print(f"  {case_id}:")
            print(f"    Move: {move_str}")
            print(f"    FEN:  {fen}")
            print(f"    Error: {error}")
            print()
        sys.exit(1)

    print(f"✅ All {len(cases)} golden moves are legal")
    sys.exit(0)


if __name__ == "__main__":
    main()
