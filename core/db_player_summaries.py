from __future__ import annotations

import os
from typing import Any, Dict

from sqlalchemy import create_engine, text


def load_player_summaries_from_db(
    dsn: str | None = None,
    *,
    only_success: bool = True,
) -> Dict[str, Dict[str, Any]]:
    url = dsn or os.getenv("TAGGER_DATABASE_URL", "")
    if not url:
        return {}

    engine = create_engine(url)
    summaries: Dict[str, Dict[str, Any]] = {}

    with engine.connect() as conn:
        if only_success:
            players = conn.execute(
                text(
                    """
                    SELECT DISTINCT p.id, p.display_name
                    FROM player_profiles p
                    JOIN tag_stats ts ON ts.player_id = p.id
                    WHERE ts.scope = 'total' AND ts.total_positions > 0
                    """
                )
            ).fetchall()
        else:
            players = conn.execute(
                text("SELECT id, display_name FROM player_profiles")
            ).fetchall()
        player_map = {str(row.id): row.display_name for row in players}

        games_rows = conn.execute(
            text("SELECT player_id, COUNT(*) AS games FROM pgn_games GROUP BY player_id")
        ).fetchall()
        games_map = {str(row.player_id): int(row.games) for row in games_rows}

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
        total_positions = totals.get(player_id, 0)
        tags = tag_counts.get(player_id, {})
        if total_positions <= 0:
            tag_distribution = {tag: 0.0 for tag in tags}
        else:
            tag_distribution = {
                tag: float(count) / float(total_positions) for tag, count in tags.items()
            }

        summaries[player_key] = {
            "meta": {
                "player": display_name,
                "player_id": player_id,
                "games": games_map.get(player_id, 0),
                "moves": total_positions,
            },
            "tag_distribution": tag_distribution,
        }

    return summaries


def load_player_summary_by_id(
    player_id: str,
    dsn: str | None = None,
    *,
    only_success: bool = True,
) -> Dict[str, Any] | None:
    url = dsn or os.getenv("TAGGER_DATABASE_URL", "")
    if not url:
        return None

    engine = create_engine(url)

    with engine.connect() as conn:
        player_row = conn.execute(
            text("SELECT id, display_name FROM player_profiles WHERE id = :pid"),
            {"pid": player_id},
        ).fetchone()
        if not player_row:
            return None

        if only_success:
            stats_rows = conn.execute(
                text(
                    """
                    SELECT tag_name, SUM(tag_count) AS tag_count, MAX(total_positions) AS total_positions
                    FROM tag_stats
                    WHERE player_id = :pid AND scope = 'total' AND total_positions > 0
                    GROUP BY tag_name
                    """
                ),
                {"pid": player_id},
            ).fetchall()
        else:
            stats_rows = conn.execute(
                text(
                    """
                    SELECT tag_name, SUM(tag_count) AS tag_count, MAX(total_positions) AS total_positions
                    FROM tag_stats
                    WHERE player_id = :pid AND scope = 'total'
                    GROUP BY tag_name
                    """
                ),
                {"pid": player_id},
            ).fetchall()

        games_row = conn.execute(
            text("SELECT COUNT(*) AS games FROM pgn_games WHERE player_id = :pid"),
            {"pid": player_id},
        ).fetchone()

    total_positions = 0
    tag_counts: Dict[str, int] = {}
    for row in stats_rows:
        total_positions = max(total_positions, int(row.total_positions or 0))
        tag_counts[row.tag_name] = int(row.tag_count or 0)

    if only_success and total_positions <= 0:
        return None

    if total_positions <= 0:
        tag_distribution = {tag: 0.0 for tag in tag_counts}
    else:
        tag_distribution = {
            tag: float(count) / float(total_positions) for tag, count in tag_counts.items()
        }

    return {
        "meta": {
            "player": player_row.display_name,
            "player_id": str(player_row.id),
            "games": int(games_row.games) if games_row else 0,
            "moves": total_positions,
        },
        "tag_distribution": tag_distribution,
    }
