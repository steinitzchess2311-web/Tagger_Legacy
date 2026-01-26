"""Batch diagnostics for Control-over-Dynamics detections.

Usage example::

    python3 scripts/batch_cod_diagnostics.py \
        --input Test_players/test_petrosian.pgn \
        --limit 500 \
        --out reports/cod_diag.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

import chess
import chess.pgn

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from codex_utils import analyze_position, DEFAULT_ENGINE_PATH  # noqa: E402

# Columns exported for every record (in order).
COD_SUBTYPES = [
    "simplify",
    "plan_kill",
    "freeze_bind",
    "blockade_passed",
    "file_seal",
    "king_safety_shell",
    "space_clamp",
    "regroup_consolidate",
    "slowdown",
]

COD_COLUMNS = ["control_over_dynamics", *[f"cod_{name}" for name in COD_SUBTYPES]]

CANDIDATE_COLUMNS = [
    *[f"cand_{name}" for name in COD_SUBTYPES]
]

PlayerDetectedCallback = Callable[[str], None]
GameProgressCallback = Callable[[str, int, List[str]], None]


def _canonicalize_player_name(name: str) -> str:
    return name.strip().lower()


def _match_player_in_game(game: chess.pgn.Game, target_lower: str) -> Optional[str]:
    for role in ("White", "Black"):
        candidate = game.headers.get(role)
        if isinstance(candidate, str) and target_lower in _canonicalize_player_name(candidate):
            return candidate
    return None


def _game_identifier(game: chess.pgn.Game, index: int) -> str:
    event = game.headers.get("Event") or "UnknownEvent"
    site = game.headers.get("Site") or "UnknownSite"
    date = game.headers.get("Date") or "UnknownDate"
    return f"{event}_{site}_{date}_{index}"


def _active_cod_flags(result: Dict[str, Any]) -> List[str]:
    tag_flags = result.get("tags", {}).get("all", {})
    active = [name for name in COD_COLUMNS if tag_flags.get(name, False)]
    return active


def _extract_row(
    game_id: str,
    ply_index: int,
    board: chess.Board,
    move: chess.Move,
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    control_ctx = analysis.get("analysis_context", {}).get("control_dynamics", {})
    control_context = control_ctx.get("context", {}) if isinstance(control_ctx, dict) else {}
    notes = analysis.get("notes", {})
    tag_flags = analysis.get("tags", {}).get("all", {})

    candidate_map = control_context.get("candidates") if isinstance(control_context, dict) else {}
    candidate_map = candidate_map if isinstance(candidate_map, dict) else {}

    row: Dict[str, Any] = {
        "game_id": game_id,
        "ply": ply_index,
        "side": "white" if board.turn == chess.WHITE else "black",
        "move": move.uci(),
        "fen_before": board.fen(),
        "note_control": notes.get("control_over_dynamics", ""),
        "suppressed": ",".join(control_context.get("suppressed", []) or []),
        "cooldown_remaining": control_context.get("cooldown_remaining", 0),
        "phase": control_context.get("phase"),
        "volatility_drop_cp": control_context.get("volatility_drop_cp"),
        "opp_mobility_drop": control_context.get("opp_mobility_drop"),
        "tension_delta": control_context.get("tension_delta"),
        "preventive_score": control_context.get("preventive_score"),
    }
    row["suppressed_by"] = control_context.get("suppressed_by")
    row["cooldown_hit"] = bool(control_context.get("cooldown_hit", False))

    row["control_over_dynamics"] = bool(tag_flags.get("control_over_dynamics", False))
    row["control_over_dynamics_subtype"] = control_ctx.get("subtype") if isinstance(control_ctx, dict) else None
    for column in COD_COLUMNS:
        row[column] = bool(tag_flags.get(column, False))
    for subtype in COD_SUBTYPES:
        key = f"cand_{subtype}"
        row[key] = bool(candidate_map.get(subtype, False))
    row["active_cod_flags"] = ",".join(_active_cod_flags(analysis))

    return row


def _iter_positions(
    handle: Iterable[chess.pgn.Game],
    limit: Optional[int],
    engine_path: str,
    target_player: Optional[str] = None,
    player_detected_callback: Optional[PlayerDetectedCallback] = None,
    game_progress_callback: Optional[GameProgressCallback] = None,
) -> Iterable[Dict[str, Any]]:
    total = 0
    for index, game in enumerate(handle):
        if game is None:
            break
        if target_player:
            matched_player = _match_player_in_game(game, target_player)
            if matched_player is None:
                continue
            if player_detected_callback:
                player_detected_callback(matched_player)
        board = game.board()
        game_id = _game_identifier(game, index)
        active_tags_in_game: Set[str] = set()
        moves_in_game = 0
        for ply_index, move in enumerate(game.mainline_moves()):
            if limit is not None and total >= limit:
                return
            analysis = analyze_position(board.fen(), move.uci(), engine_path)
            row = _extract_row(game_id, ply_index, board, move, analysis)
            active_flags = row.get("active_cod_flags", "")
            if active_flags:
                for tag in (flag.strip() for flag in active_flags.split(",") if flag.strip()):
                    active_tags_in_game.add(tag)
            yield row
            board.push(move)
            total += 1
            moves_in_game += 1
        if game_progress_callback and moves_in_game > 0:
            game_progress_callback(game_id, moves_in_game, sorted(active_tags_in_game))


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("game_id,ply,side,move\n", encoding="utf-8")
        return
    columns = [
        "game_id",
        "ply",
        "side",
        "move",
        "fen_before",
        "control_over_dynamics",
        "control_over_dynamics_subtype",
        *COD_COLUMNS,
        *CANDIDATE_COLUMNS,
        "suppressed_by",
        "cooldown_hit",
        "active_cod_flags",
        "suppressed",
        "cooldown_remaining",
        "phase",
        "volatility_drop_cp",
        "opp_mobility_drop",
        "tension_delta",
        "preventive_score",
        "note_control",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def _write_parquet(path: Path, rows: List[Dict[str, Any]]) -> None:
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Parquet output requires pandas to be installed") from exc

    frame = pd.DataFrame(rows)
    frame.to_parquet(path, index=False)


def _print_summary(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    if total == 0:
        return
    overall_cod = sum(1 for row in rows if row.get("control_over_dynamics")) / total
    end_cod = sum(
        1 for row in rows if row.get("control_over_dynamics") and row.get("phase") == "END"
    )
    mid_cod = sum(
        1 for row in rows if row.get("control_over_dynamics") and row.get("phase") == "MID"
    )
    end_total = sum(1 for row in rows if row.get("phase") == "END")
    mid_total = sum(1 for row in rows if row.get("phase") == "MID")
    end_rate = (end_cod / end_total) if end_total else 0.0
    mid_rate = (mid_cod / mid_total) if mid_total else 0.0
    ratio = (end_rate / mid_rate) if mid_rate else float("inf")
    print(f"Overall CoD rate: {overall_cod:.3f}")
    print(f"END rate: {end_rate:.3f} MID rate: {mid_rate:.3f} END/MID ratio: {ratio:.2f}")
    print("Subtype metrics (per total plies):")
    for subtype in COD_SUBTYPES:
        cand_key = f"cand_{subtype}"
        cand_count = sum(1 for row in rows if row.get(cand_key))
        final_count = sum(
            1 for row in rows if row.get("control_over_dynamics_subtype") == subtype
        )
        suppressed_count = sum(
            1
            for row in rows
            if row.get(cand_key) and row.get("control_over_dynamics_subtype") != subtype
        )
        cand_rate = cand_count / total
        final_rate = final_count / total
        suppressed_rate = suppressed_count / total
        suppressed_share = (suppressed_count / cand_count) if cand_count else 0.0
        print(
            f"  {subtype:>22}: cand={cand_rate:.3f} "
            f"suppressed={suppressed_rate:.3f} (share={suppressed_share:.2f}) "
            f"final={final_rate:.3f}"
        )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Batch Control-over-Dynamics diagnostics")
    parser.add_argument("--input", required=True, type=Path, help="PGN file with games")
    parser.add_argument("--out", required=True, type=Path, help="Output file (.csv or .parquet)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of plies (default: all)")
    parser.add_argument("--engine", type=str, default=DEFAULT_ENGINE_PATH, help="Path to UCI engine")
    parser.add_argument("--player", type=str, default=None, help="Player name to filter games")
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"Input PGN not found: {args.input}")

    target_player = _canonicalize_player_name(args.player) if args.player else None
    player_detected_logged = False

    def _log_player_detected(name: str) -> None:
        nonlocal player_detected_logged
        if not player_detected_logged:
            print(f"[Codex] Player detected: {name}")
            player_detected_logged = True

    games_finished = 0

    def _log_game_finished(game_id: str, moves: int, tags: List[str]) -> None:
        nonlocal games_finished
        games_finished += 1
        tag_info = f" (tags: {', '.join(tags)})" if tags else ""
        print(f"[Codex] Game {games_finished} finished ({moves} moves){tag_info}")

    player_callback = _log_player_detected if target_player else None

    rows: List[Dict[str, Any]] = []
    with args.input.open("r", encoding="utf-8") as handle:
        game_iter = iter(lambda: chess.pgn.read_game(handle), None)
        for row in _iter_positions(
            game_iter,
            args.limit,
            args.engine,
            target_player=target_player,
            player_detected_callback=player_callback,
            game_progress_callback=_log_game_finished,
        ):
            rows.append(row)

    if args.player and not player_detected_logged:
        print(f"[Codex] Player not found in input: {args.player}")

    output_path = args.out
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if suffix == ".parquet":
        _write_parquet(output_path, rows)
    else:
        _write_csv(output_path, rows)

    print(f"Wrote {len(rows)} rows to {output_path}")
    _print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
