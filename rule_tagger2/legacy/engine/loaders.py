"""
Position loading utilities.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess
import chess.pgn


def load_positions_from_json(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError('JSON must contain a list of {"fen", "move"} objects.')
    positions: List[Dict[str, str]] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict) or "fen" not in item or "move" not in item:
            raise ValueError(f"Invalid item at index {idx}: expected keys 'fen' and 'move'.")
        positions.append({"fen": item["fen"], "move": item["move"]})
    return positions


def load_positions_from_pgn(
    path: Path,
    sample_interval: int = 3,
    limit: Optional[int] = None,
) -> List[Dict[str, str]]:
    positions: List[Dict[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            board = game.board()
            for ply, move in enumerate(game.mainline_moves(), start=1):
                if sample_interval > 0 and ply % sample_interval != 0:
                    board.push(move)
                    continue
                positions.append({"fen": board.fen(), "move": move.uci()})
                board.push(move)
                if limit and len(positions) >= limit:
                    return positions
    return positions


__all__ = ["load_positions_from_json", "load_positions_from_pgn"]
