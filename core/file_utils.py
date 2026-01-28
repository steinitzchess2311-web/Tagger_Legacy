"""Utilities for loading persisted player summaries."""
from __future__ import annotations

import json
import re
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


def _normalize_player_label(stem: str, player_name: str | None) -> str:
    if isinstance(player_name, str) and " " in player_name.strip():
        return player_name.strip()
    base = stem if any(ch.isupper() for ch in stem) else (player_name or stem)
    label = base.replace("_", " ").replace("-", " ")
    label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label)
    return " ".join(part.capitalize() if part.islower() else part for part in label.split())


def _extract_tag_distribution(payload: dict) -> Dict[str, float]:
    if isinstance(payload.get("global_tag_distribution"), dict):
        distribution = payload.get("global_tag_distribution") or {}
        return {
            tag: float(info.get("ratio", 0.0)) if isinstance(info, dict) else 0.0
            for tag, info in distribution.items()
        }
    if isinstance(payload.get("tag_distribution"), dict):
        distribution = payload.get("tag_distribution") or {}
        if all(isinstance(v, dict) for v in distribution.values()):
            return {
                tag: float(info.get("ratio", 0.0)) if isinstance(info, dict) else 0.0
                for tag, info in distribution.items()
            }
        return {
            tag: float(weight) if isinstance(weight, (int, float)) else 0.0
            for tag, weight in distribution.items()
        }
    tag_weights = payload.get("tag_weights") or {}
    if not isinstance(tag_weights, dict):
        return {}
    return {
        tag: float(weight) if isinstance(weight, (int, float)) else 0.0
        for tag, weight in tag_weights.items()
    }


def load_player_profiles(players_path: str = "players") -> Dict[str, Dict[str, object]]:
    """Load player profiles from JSON files in the players directory."""
    summaries: Dict[str, Dict[str, object]] = {}
    base = Path(players_path)
    if not base.exists():
        return summaries

    for path in base.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        raw_player_name = payload.get("player_name")
        player_label = _normalize_player_label(path.stem, raw_player_name)
        tag_ratios = _extract_tag_distribution(payload)

        summaries[player_label] = {
            "meta": {
                "player": player_label,
                "raw_player_name": raw_player_name,
                "source": "players",
                "file": path.name,
            },
            "tag_distribution": tag_ratios,
        }
    return summaries
