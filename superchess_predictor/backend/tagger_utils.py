"""Tagging utilities for backend."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from codex_utils import analyze_position


def tag_moves(fen: str, candidates: List[dict], engine_path: Optional[str] = None) -> List[dict]:
    tagged: List[dict] = []
    for entry in candidates:
        move_uci = entry["uci"]
        analysis = analyze_position(fen, move_uci, engine_path=engine_path)
        active_tags = analysis["tags"]["active"]
        if not active_tags:
            active_tags = analysis["tags"]["primary"]
        tagged.append(
            {
                "san": entry["san"],
                "uci": move_uci,
                "score_cp": entry.get("score_cp"),
                "tags": active_tags,
                "analysis": analysis,
            }
        )
    return tagged
