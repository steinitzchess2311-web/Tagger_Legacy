"""Utilities for loading persisted player summaries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple


def _format_player_name(raw: str) -> str:
    parts = [part for part in raw.replace("universal_", "").replace("_summary", "").split("_") if part]
    if not parts:
        return raw
    return " ".join(p.capitalize() for p in parts)


def load_player_summaries(reports_path: str = "reports") -> Dict[str, Dict[str, object]]:
    """Load universal summaries for available players."""
    summaries: Dict[str, Dict[str, object]] = {}
    base = Path(reports_path)
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

        player_key = _format_player_name(path.stem)
        summaries[player_key] = {
            "meta": {
                "player": payload.get("player", player_key),
                "games": payload.get("games_analyzed", 0),
                "moves": payload.get("moves_total", 0),
            },
            "tag_distribution": tag_ratios,
        }
    return summaries

