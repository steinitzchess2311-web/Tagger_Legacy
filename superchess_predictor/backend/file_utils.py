"""Utilities for loading player summaries."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict


def _format_player_name(stem: str) -> str:
    parts = [p for p in stem.replace("universal_", "").replace("_summary", "").split("_") if p]
    if not parts:
        return stem
    return " ".join(part.capitalize() for part in parts)


@lru_cache(maxsize=32)
def load_player_summaries(reports_path: str = "reports") -> Dict[str, Dict[str, object]]:
    base = Path(reports_path)
    summaries: Dict[str, Dict[str, object]] = {}
    if not base.exists():
        return summaries

    for path in base.glob("universal_*_summary.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        distribution = payload.get("global_tag_distribution") or {}
        tag_ratios = {
            tag: float(info.get("ratio", 0.0)) if isinstance(info, dict) else 0.0
            for tag, info in distribution.items()
        }
        summaries[_format_player_name(path.stem)] = {
            "meta": {
                "player": payload.get("player", path.stem),
                "games": payload.get("games_analyzed", 0),
                "moves": payload.get("moves_total", 0),
            },
            "tag_distribution": tag_ratios,
        }
    return summaries
