from __future__ import annotations

import os
from typing import Any, Dict

from sqlalchemy import create_engine, text


def load_player_summaries_from_db(dsn: str | None = None) -> Dict[str, Dict[str, Any]]:
    url = dsn or os.getenv("TAGGER_DATABASE_URL", "")
    if not url:
        return {}

    engine = create_engine(url)
    summaries: Dict[str, Dict[str, Any]] = {}

    with engine.connect() as conn:
        players = conn.execute(
            text("SELECT id, display_name FROM player_profiles")
        ).fetchall()
        player_map = {row.id: row.display_name for row in players}

        games_rows = conn.execute(
            text("SELECT player_id, COUNT(*) AS games FROM pgn_games GROUP BY player_id")
        ).fetchall()
        games_map = {row.player_id: int(row.games) for row in games_rows}

        tag_rows = conn.execute(
            text(
                """
                SELECT player_id, tag_name,
                       SUM(tag_count) AS tag_count,
                       MAX(total_positions) AS total_positions
                FROM tag_stats
                WHERE scope = 'total'
                GROUP BY player_id, tag_name
                """
            )
        ).fetchall()

    totals: Dict[str, int] = {}
    tag_counts: Dict[str, Dict[str, int]] = {}
    for row in tag_rows:
        player_id = str(row.player_id)
        totals[player_id] = max(totals.get(player_id, 0), int(row.total_positions or 0))
        tag_counts.setdefault(player_id, {})
        tag_counts[player_id][row.tag_name] = int(row.tag_count or 0)

    for player_id, display_name in player_map.items():
        player_key = str(display_name)
        total_positions = totals.get(str(player_id), 0)
        tags = tag_counts.get(str(player_id), {})
        if total_positions <= 0:
            tag_distribution = {tag: 0.0 for tag in tags}
        else:
            tag_distribution = {
                tag: float(count) / float(total_positions) for tag, count in tags.items()
            }

        summaries[player_key] = {
            "meta": {
                "player": display_name,
                "games": games_map.get(player_id, 0),
                "moves": total_positions,
            },
            "tag_distribution": tag_distribution,
        }

    return summaries
