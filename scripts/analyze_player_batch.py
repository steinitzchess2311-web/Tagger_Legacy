"""Persistent, resumable batch analysis for Kasparov games."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import chess
import chess.pgn

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from codex_utils import analyze_position
from core.score_engine import collapse_failure_severity, compute_performance
from core.tag_categories import categories as tag_categories
from core.style_evaluator import detect_style

from tag_postprocess import normalize_candidate_tags

logging.getLogger("chess.engine").setLevel(logging.ERROR)


def _canonicalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _matches_player(name: str, target_tokens: Iterable[str]) -> bool:
    canon = _canonicalize(name)
    return any(token in canon for token in target_tokens)


def _phase_label(phase_ratio: Optional[float]) -> str:
    if phase_ratio is None:
        return "unknown"
    if phase_ratio >= 1.5:
        return "opening"
    if phase_ratio >= 0.75:
        return "middlegame"
    return "endgame"


def _sanitize_identifier(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_")).strip("_")


def _build_game_id(opponent: str, date: str) -> str:
    year = (date or "")[:4]
    opp = _sanitize_identifier(opponent or "Unknown")
    year = year if year and year.isdigit() else "UnknownYear"
    return f"Kasparov_vs_{opp}_{year}"


def _archive_report_files(paths: Iterable[Path], archive_root: Path) -> Tuple[Optional[Path], list[str]]:
    """
    Move existing report artifacts into an archive folder so a fresh run
    can regenerate results without clobbering prior data.
    """
    archive_dir: Optional[Path] = None
    moved: list[str] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for path in paths:
        if not path.exists():
            continue
        if archive_dir is None:
            archive_dir = archive_root / timestamp
            archive_dir.mkdir(parents=True, exist_ok=True)
        destination = archive_dir / path.name
        path.replace(destination)
        moved.append(path.name)

    return archive_dir, moved


CATEGORY_OVERRIDES = {
    "king_safety_risk_avoidance": "Prophylaxis",
    "piece_control_over_dynamics": "Prophylaxis",
    "pawn_control_over_dynamics": "Prophylaxis",
    "premature_attack": "Initiative",
    "control_over_dynamics": "Initiative",
    "tactical_dominance": "Tactical",
    "tactical_theme": "Tactical",
}

CATEGORY_RULES = [
    ("Prophylaxis", ("prophylactic", "risk_avoidance", "control_over_dynamics")),
    ("Maneuver", ("maneuver", "regroup")),
    ("Tension", ("tension",)),
    ("Initiative", ("initiative",)),
    ("Exchange", ("exchange",)),
    ("Sacrifice", ("sacrifice",)),
    ("Intent", ("intent_",)),
    ("Structural", ("structural",)),
    ("Tactical", ("tactical", "first_choice", "missed_tactic", "conversion_precision", "panic_move", "tactical_recovery")),
]

CATEGORY_ORDER = [
    "Prophylaxis",
    "Maneuver",
    "Tension",
    "Initiative",
    "Exchange",
    "Sacrifice",
    "Intent",
    "Structural",
    "Tactical",
    "Other",
]


def _categorize_tag(tag: str) -> str:
    tag_lower = tag.lower()
    if tag_lower in CATEGORY_OVERRIDES:
        return CATEGORY_OVERRIDES[tag_lower]
    for category, prefixes in CATEGORY_RULES:
        for prefix in prefixes:
            if prefix.endswith("_"):
                if tag_lower.startswith(prefix):
                    return category
            elif prefix in tag_lower:
                return category
    return "Other"


FINE_GRAINED_TAGS = {tag for tags in tag_categories().values() for tag in tags}


def _write_summary_tables(
    distribution: Dict[str, Dict[str, float]],
    score_payload: Dict[str, object],
    output_path: Path,
) -> None:
    entries = [
        (tag, int(info.get("count", 0)), float(info.get("ratio", 0.0)))
        for tag, info in distribution.items()
    ]
    if not entries:
        output_path.write_text("No tag data available.\n", encoding="utf-8")
        return

    entries.sort(key=lambda item: (-item[2], item[0]))
    entry_map = {tag: (count, ratio) for tag, count, ratio in entries}
    parent_entries = [entry for entry in entries if entry[0] not in FINE_GRAINED_TAGS]
    child_entries = [entry for entry in entries if entry[0] in FINE_GRAINED_TAGS]

    def _ratio_str(value: float) -> str:
        return f"{value:.4f}"

    def _render_table(
        title: str,
        table_entries: list[tuple[str, int, float]],
        *,
        tag_width: int | None = None,
        count_width: int | None = None,
    ) -> tuple[list[str], int, int]:
        tag_width = tag_width or max(len("tag"), max(len(tag) for tag, _, _ in table_entries))
        count_width = count_width or max(len("count"), max(len(str(count)) for _, count, _ in table_entries))
        rows = [
            title,
            f"{'tag':<{tag_width}}  {'count':>{count_width}}  ratio",
            f"{'-' * tag_width}  {'-' * count_width}  {'-' * 5}",
        ]
        for tag, count, ratio in table_entries:
            rows.append(f"{tag:<{tag_width}}  {count:>{count_width}}  {_ratio_str(ratio)}")
        return rows, tag_width, count_width

    lines: list[str] = []

    if parent_entries:
        parent_entries.sort(key=lambda item: (-item[2], item[0]))
        parent_rows, _, _ = _render_table("Aggregate tag distribution (parent tags)", parent_entries)
        lines.extend(parent_rows)
        lines.append("")

    if child_entries:
        child_entries.sort(key=lambda item: (-item[2], item[0]))
        child_rows, child_tag_width, child_count_width = _render_table(
            "Fine-grained tag distribution (ratio desc)",
            child_entries,
        )
        lines.extend(child_rows)
        lines.append("")
        lines.append("Structured distribution (by category)")
    else:
        lines.append("No fine-grained tag data available.")
        lines.append("")
        child_tag_width = len("tag")
        child_count_width = len("count")

    categorize_map: Dict[str, list[tuple[str, int, float]]] = {category: [] for category in CATEGORY_ORDER}
    for tag, count, ratio in child_entries:
        category = _categorize_tag(tag)
        categorize_map.setdefault(category, []).append((tag, count, ratio))

    for category in CATEGORY_ORDER:
        subset = categorize_map.get(category) or []
        if not subset:
            continue
        lines.append(f"[{category}]")
        subset.sort(key=lambda item: (-item[2], item[0]))
        for tag, count, ratio in subset:
            lines.append(f"  {tag:<{child_tag_width}}  {count:>{child_count_width}}  {_ratio_str(ratio)}")
        lines.append("")

    severity_summary = {
        "true": {"count": 0, "ratio": 0.0},
        "strategic": {"count": 0, "ratio": 0.0},
        "temporary": {"count": 0, "ratio": 0.0},
    }
    severity_suffix_map = {
        "true": ".true",
        "strategic": ".strategic",
        "temporary": ".temporary",
    }
    failure_bases = (
        "failed_maneuver",
        "failed_direction_maneuver",
        "failed_blocked_maneuver",
        "failed_redundant_maneuver",
    )
    for base in failure_bases:
        for label, suffix in severity_suffix_map.items():
            tag = f"{base}{suffix}"
            if tag in entry_map:
                count, ratio = entry_map[tag]
                severity_summary[label]["count"] += count
                severity_summary[label]["ratio"] += ratio

    if any(bucket["count"] for bucket in severity_summary.values()):
        label_width = max(10, len("temporary"))
        lines.append("Maneuver failure severity (aggregated)")
        for label in ("true", "strategic", "temporary"):
            bucket = severity_summary[label]
            if bucket["count"]:
                lines.append(
                    f"  {label:<{label_width}}  {bucket['count']:>{child_count_width}}  {_ratio_str(bucket['ratio'])}"
                )
        lines.append("")

    mix = score_payload.get("style_mix", {"BalancedModel": 1.0})
    mix_text = ", ".join(f"{style} {weight * 100:.1f}%" for style, weight in mix.items())
    penalties = score_payload.get("penalties", {})
    lines.append("Scoring kernel v9")
    lines.append(f"  style_mix: {mix_text or 'BalancedModel 100.0%'}")
    lines.append(f"  raw_score: {score_payload.get('raw_score', 0.0):.4f}")
    lines.append(f"  net_score: {score_payload.get('net_score', 0.0):.4f}")
    lines.append(f"  performance_percent: {score_payload.get('performance_percent', 0.0):.2f}")
    lines.append(f"  estimated_fide_elo: {score_payload.get('estimated_elo', 1200.0):.1f}")
    neutral_penalty = float(penalties.get("neutral_penalty", 0.0))
    redundant_penalty = float(penalties.get("redundant_penalty", 0.0))
    lines.append(
        f"  penalties: neutral {neutral_penalty:.4f} | redundant {redundant_penalty:.4f}"
    )

    def _format_contrib(entries: Iterable[dict]) -> list[str]:
        formatted = []
        for entry in entries:
            formatted.append(
                f"    {entry['tag']}: {entry['contribution']:+.4f} "
                f"(ratio {entry['ratio']:.3f}, weight {entry['base_weight']:.2f}, mult {entry['style_multiplier']:.2f})"
            )
        return formatted

    top_positive = score_payload.get("top_positive", [])
    top_negative = score_payload.get("top_negative", [])
    if top_positive:
        lines.append("  top_positive:")
        lines.extend(_format_contrib(top_positive))
    if top_negative:
        lines.append("  top_negative:")
        lines.extend(_format_contrib(top_negative))

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_existing_results(
    results_path: Path,
) -> Tuple[Dict[int, int], Dict[int, Counter], int, int, int]:
    processed_moves: Dict[int, int] = defaultdict(int)
    tag_counters: Dict[int, Counter] = defaultdict(Counter)
    total_moves = 0
    last_game_index = 0
    last_move_index = 0

    if not results_path.exists():
        return processed_moves, tag_counters, total_moves, last_game_index, last_move_index

    with results_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            game_index = record.get("game_index")
            move_index = record.get("move_index", 0)
            tags = record.get("tags", [])
            if isinstance(game_index, int):
                processed_moves[game_index] += 1
                counter = tag_counters[game_index]
                for tag in tags:
                    counter[tag] += 1
                total_moves += 1
                last_game_index = game_index
                last_move_index = move_index
    return processed_moves, tag_counters, total_moves, last_game_index, last_move_index


def load_summary(summary_path: Path) -> list[Dict[str, Any]]:
    if not summary_path.exists():
        return []
    try:
        with summary_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, list):
                return data
    except json.JSONDecodeError:
        pass
    return []


def load_progress(progress_path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    if not progress_path.exists():
        return info
    with progress_path.open(encoding="utf-8") as handle:
        for line in handle:
            if "=" not in line:
                continue
            key, value = line.strip().split("=", 1)
            info[key.strip()] = value.strip()
    return info


def write_progress(progress_path: Path, game_index: int, move_index: int) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with progress_path.open("w", encoding="utf-8") as handle:
        handle.write(f"last_game={game_index}\n")
        handle.write(f"last_move={move_index}\n")
        handle.write(f"timestamp={timestamp}\n")


def flush_summary(summary_entries: list[Dict[str, Any]], summary_path: Path) -> None:
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_entries, handle, indent=2)
        handle.flush()


def write_global_summary(
    player: str,
    summary_entries: list[Dict[str, Any]],
    output_json: Path,
    output_csv: Optional[Path] = None,
) -> Tuple[int, int]:
    games = len(summary_entries)
    tag_totals: Counter[str] = Counter()
    moves_total = 0

    for entry in summary_entries:
        moves = entry.get("moves_analyzed", 0)
        if isinstance(moves, int):
            moves_total += moves
        for tag, info in entry.get("tag_distribution", {}).items():
            count = info.get("count", 0)
            if isinstance(count, int):
                tag_totals[tag] += count

    ordered_tags = sorted(tag_totals.items(), key=lambda item: (-item[1], item[0]))
    distribution = {
        tag: {
            "count": count,
            "ratio": round(count / moves_total, 4) if moves_total else 0.0,
        }
        for tag, count in ordered_tags
    }

    tag_ratios_raw = {tag: info.get("ratio", 0.0) for tag, info in distribution.items()}
    tag_ratios_scoring = collapse_failure_severity(tag_ratios_raw)
    style_mix = detect_style(tag_ratios_scoring)
    score_payload = compute_performance(tag_ratios_scoring, style=style_mix)

    payload = {
        "player": player,
        "games_analyzed": games,
        "moves_total": moves_total,
        "global_tag_distribution": distribution,
        "tag_ratios_raw": tag_ratios_raw,
        "maneuver_failure_true_ratio": tag_ratios_scoring.get("failed_maneuver", 0.0),
        "style_performance": {
            "style_mix": score_payload["style_mix"],
            "raw_score": score_payload["raw_score"],
            "net_score": score_payload["net_score"],
            "performance_percent": score_payload["performance_percent"],
            "estimated_fide_elo": score_payload["estimated_elo"],
            "penalties": score_payload["penalties"],
            "top_positive": score_payload["top_positive"],
            "top_negative": score_payload["top_negative"],
            "ratios_used": score_payload.get("ratios_used", tag_ratios_scoring),
        },
        "estimated_fide_elo": score_payload["estimated_elo"],
    }
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    tables_path = output_json.with_name(f"{output_json.stem}_tables.txt")
    _write_summary_tables(distribution, score_payload, tables_path)

    if output_csv:
        with output_csv.open("w", encoding="utf-8") as handle:
            handle.write("tag,count,ratio\n")
            for tag, count in ordered_tags:
                ratio = count / moves_total if moves_total else 0.0
                handle.write(f"{tag},{count},{ratio:.6f}\n")

    return games, moves_total


class PipelineState:
    def __init__(
        self,
        jsonl_handle,
        summary_entries: list[Dict[str, Any]],
        summary_path: Path,
        total_moves: int,
        games_completed: int,
        last_game: int,
        last_move: int,
        initial_total: int,
    ) -> None:
        self.jsonl_handle = jsonl_handle
        self.summary_entries = summary_entries
        self.summary_path = summary_path
        self.total_moves = total_moves
        self.games_completed = games_completed
        self.last_game = last_game
        self.last_move = last_move
        self.initial_total = initial_total


def analyze_game(
    game_index: int,
    game: chess.pgn.Game,
    player_color: chess.Color,
    player_name: str,
    opponent_name: str,
    start_fullmove: int,
    skip_moves: int,
    state: PipelineState,
    results_handle,
    per_game_counter: Counter,
    global_counter: Counter,
    max_new_moves: Optional[int] = None,
    use_new: Optional[bool] = None,
) -> Tuple[int, int, bool]:
    board = game.board()
    moves_added = 0
    last_move_index = state.last_move
    completed = True

    for node in game.mainline():
        move = node.move
        fen_before = board.fen()

        if board.turn == player_color and board.fullmove_number >= start_fullmove:
            if (
                max_new_moves is not None
                and (state.total_moves - state.initial_total) >= max_new_moves
            ):
                completed = False
                return moves_added, last_move_index, completed

            move_index = board.ply()
            if skip_moves > 0:
                skip_moves -= 1
            else:
                try:
                    analysis = analyze_position(fen_before, move.uci(), use_new=use_new)
                except Exception as exc:  # skip problematic move
                    print(f"[Codex] Warning: move analysis failed (game {game_index}, move {move_index}): {exc}", file=sys.stderr)
                    board.push(move)
                    continue

                primary_tags = list(analysis.get("tags", {}).get("primary", []))
                tags = normalize_candidate_tags(primary_tags, analysis)
                phase_ratio = analysis.get("engine_meta", {}).get("phase_ratio")
                phase = _phase_label(phase_ratio)

                record = {
                    "game_id": _build_game_id(opponent_name, game.headers.get("Date", "")),
                    "game_index": game_index,
                    "move_index": move_index,
                    "fen_before": fen_before,
                    "move": move.uci(),
                    "tags": tags,
                    "eval": analysis["eval"],
                    "metrics": {
                        "component_deltas": analysis["metrics"]["component_deltas"],
                        "opp_component_deltas": analysis["metrics"]["opp_component_deltas"],
                    },
                    "phase": phase,
                    "ruleset_version": analysis["engine_meta"].get("ruleset_version"),
                }
                json.dump(record, results_handle)
                results_handle.write("\n")
                results_handle.flush()

                for tag in tags:
                    per_game_counter[tag] += 1
                    global_counter[tag] += 1

                moves_added += 1
                state.total_moves += 1
                state.last_game = game_index
                state.last_move = move_index
                last_move_index = move_index

                if state.total_moves % 50 == 0:
                    results_handle.flush()
                    flush_summary(state.summary_entries, state.summary_path)
                if (
                    max_new_moves is not None
                    and (state.total_moves - state.initial_total) >= max_new_moves
                ):
                    completed = False
                    return moves_added, last_move_index, completed
        board.push(move)
    return moves_added, last_move_index, completed


def build_game_summary(game_index: int, tag_counter: Counter, move_total: int) -> Dict[str, Any]:
    distribution = {
        tag: {
            "count": count,
            "ratio": round(count / move_total, 4) if move_total else 0.0,
        }
        for tag, count in sorted(tag_counter.items(), key=lambda item: (-item[1], item[0]))
    }
    return {
        "game_index": game_index,
        "player": "Kasparov",
        "moves_analyzed": move_total,
        "tag_distribution": distribution,
    }


def enumerate_games(input_path: Path) -> Iterable[Tuple[Path, chess.pgn.Game]]:
    if input_path.is_file():
        files = [input_path]
    else:
        files = sorted(input_path.glob("*.pgn"))
    for pgn_file in files:
        with pgn_file.open(encoding="utf-8") as handle:
            while True:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break
                yield pgn_file, game


def main() -> None:
    parser = argparse.ArgumentParser(description="Persistent Kasparov batch analysis.")
    parser.add_argument("--player", default="Kasparov", help="Player name to match.")
    parser.add_argument("--input-dir", default="Test_players", help="Directory with PGN files.")
    parser.add_argument("--start-fullmove", type=int, default=1, help="Analyze moves from this fullmove onwards.")
    parser.add_argument("--max-games", type=int, default=0, help="Optional limit on number of games (testing only).")
    parser.add_argument("--max-moves", type=int, default=0, help="Optional limit on number of moves (testing only).")
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Prefix for output files (default derives from player name).",
    )
    parser.add_argument(
        "--fresh-run",
        action="store_true",
        help="Ignore existing reports for this prefix and recompute everything from scratch.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing reports (keeps prior moves and summaries).",
    )
    pipeline_group = parser.add_mutually_exclusive_group()
    pipeline_group.add_argument(
        "--new-pipeline",
        action="store_true",
        help="Force new orchestrator pipeline (overrides NEW_PIPELINE env var).",
    )
    pipeline_group.add_argument(
        "--legacy",
        action="store_true",
        help="Force legacy pipeline (overrides NEW_PIPELINE env var).",
    )
    args = parser.parse_args()

    if args.fresh_run and args.resume:
        parser.error("--fresh-run and --resume cannot be used together.")

    # Determine pipeline version: None=use env var, True=force new, False=force legacy
    use_new_pipeline = None
    if args.new_pipeline:
        use_new_pipeline = True
    elif args.legacy:
        use_new_pipeline = False

    output_prefix = args.output_prefix or _canonicalize(args.player) or "summary"

    reports_dir = BASE_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    results_path = reports_dir / f"{output_prefix}_moves.jsonl"
    summary_path = reports_dir / f"{output_prefix}_summary.json"
    progress_path = reports_dir / f"{output_prefix}_progress.log"

    report_paths = (results_path, summary_path, progress_path)
    archive_root = reports_dir / "archive" / _sanitize_identifier(output_prefix or "summary")
    fresh_mode = args.fresh_run or not args.resume

    if fresh_mode:
        archive_dir, archived_files = _archive_report_files(report_paths, archive_root)
        if archived_files:
            archive_label = f"{archive_dir.relative_to(BASE_DIR)}" if archive_dir else "<unknown>"
            cleared_list = ", ".join(archived_files)
            print(f"[Codex] Starting fresh run; archived {cleared_list} to {archive_label}")
    else:
        print("[Codex] Resume mode requested; keeping existing report artifacts.")

    processed_moves, existing_tag_counters, total_moves_existing, last_game_idx, last_move_idx = load_existing_results(results_path)
    if args.resume and processed_moves:
        cached_games = len(processed_moves)
        print(f"[Codex] Resume mode: found cached moves for {cached_games} games.")
    summary_entries = load_summary(summary_path)
    completed_games = {entry.get("game_index") for entry in summary_entries if isinstance(entry.get("game_index"), int)}
    global_tag_counter = Counter()
    for entry in summary_entries:
        for tag, info in entry.get("tag_distribution", {}).items():
            count = info.get("count", 0)
            if isinstance(count, int):
                global_tag_counter[tag] += count

    progress_info = load_progress(progress_path)
    if progress_info:
        try:
            resume_game = int(progress_info.get("last_game", 0))
            resume_move = int(progress_info.get("last_move", 0))
            if resume_game > 0:
                print(f"[Codex] Resuming from Game {resume_game}, Move {resume_move}")
        except ValueError:
            pass
    elif last_game_idx:
        print(f"[Codex] Resuming from Game {last_game_idx}, Move {last_move_idx}")

    results_handle = results_path.open("a", encoding="utf-8")
    state = PipelineState(
        results_handle,
        summary_entries,
        summary_path,
        total_moves_existing,
        len(completed_games),
        last_game_idx,
        last_move_idx,
        total_moves_existing,
    )

    target_tokens = [_canonicalize(args.player)]
    input_dir = Path(args.input_dir)

    player_detected_logged = False
    kasparov_game_index = 0
    stop_processing = False
    max_games_limit = args.max_games if args.max_games > 0 else None
    max_moves_limit = args.max_moves if args.max_moves > 0 else None

    try:
        for _, game in enumerate_games(input_dir):
            if stop_processing:
                break
            white = game.headers.get("White", "")
            black = game.headers.get("Black", "")
            player_color: Optional[chess.Color] = None
            opponent_name = ""

            if _matches_player(white, target_tokens):
                player_color = chess.WHITE
                opponent_name = black
                player_name = white
            elif _matches_player(black, target_tokens):
                player_color = chess.BLACK
                opponent_name = white
                player_name = black
            else:
                continue

            if not player_detected_logged:
                print(f"[Codex] Player detected: {args.player}")
                player_detected_logged = True

            kasparov_game_index += 1
            game_index = kasparov_game_index

            if max_games_limit is not None and kasparov_game_index > max_games_limit:
                stop_processing = True
                break

            if game_index in completed_games:
                continue

            skip_moves = processed_moves.get(game_index, 0)
            existing_move_total = skip_moves
            per_game_counter = existing_tag_counters.get(game_index, Counter()).copy()

            moves_added, last_move, completed = analyze_game(
                game_index=game_index,
                game=game,
                player_color=player_color,
                player_name=player_name,
                opponent_name=opponent_name,
                start_fullmove=args.start_fullmove,
                skip_moves=skip_moves,
                state=state,
                results_handle=results_handle,
                per_game_counter=per_game_counter,
                global_counter=global_tag_counter,
                max_new_moves=max_moves_limit,
                use_new=use_new_pipeline,
            )

            total_moves_for_game = existing_move_total + moves_added
            processed_moves[game_index] = total_moves_for_game
            existing_tag_counters[game_index] = per_game_counter

            if moves_added > 0 or (skip_moves and total_moves_for_game == skip_moves):
                state.last_move = last_move

            if completed:
                summary_entry = build_game_summary(game_index, per_game_counter, total_moves_for_game)
                state.summary_entries.append(summary_entry)
                completed_games.add(game_index)
                state.games_completed = len(completed_games)
                flush_summary(state.summary_entries, summary_path)
                if moves_added == 0 and existing_move_total > 0:
                    print(f"[Codex] Game {game_index} reused cached results ({summary_entry['moves_analyzed']} moves)")
                else:
                    print(f"[Codex] Game {game_index} finished ({summary_entry['moves_analyzed']} moves)")

            if max_moves_limit is not None and (state.total_moves - state.initial_total) >= max_moves_limit:
                stop_processing = True
                break

        results_handle.flush()
        flush_summary(state.summary_entries, summary_path)
        global_json = reports_dir / f"universal_{output_prefix}_summary.json"
        global_csv = reports_dir / f"universal_{output_prefix}_summary.csv"
        games_total, moves_total = write_global_summary(
            args.player,
            state.summary_entries,
            global_json,
            global_csv,
        )
        if progress_path.exists():
            progress_path.unlink()
        print(f"[Codex] Global summary written ({games_total} games, {moves_total} moves)")
        print(f"[Codex] Total processed: {len(completed_games)} games, {state.total_moves} moves")
    except KeyboardInterrupt:
        results_handle.flush()
        flush_summary(state.summary_entries, summary_path)
        write_progress(progress_path, state.last_game, state.last_move)
        print("\n[Codex] Interrupted. Progress saved to reports/progress.log")
    finally:
        results_handle.close()


if __name__ == "__main__":
    main()
