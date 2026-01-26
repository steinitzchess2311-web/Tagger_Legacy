"""Analyze a Kasparov PGN and generate tag reports."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import chess
import chess.pgn

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from codex_utils import analyze_position


def extract_white_moves(pgn_path: Path, start_fullmove: int = 7) -> Dict[str, Any]:
    with pgn_path.open(encoding="utf-8") as handle:
        game = chess.pgn.read_game(handle)
    if game is None:
        raise ValueError(f"No game found in {pgn_path}")

    game_info = {
        "event": game.headers.get("Event", ""),
        "site": game.headers.get("Site", ""),
        "date": game.headers.get("Date", ""),
        "white": game.headers.get("White", ""),
        "black": game.headers.get("Black", ""),
        "result": game.headers.get("Result", ""),
        "round": game.headers.get("Round", ""),
    }

    board = game.board()
    entries: List[Dict[str, Any]] = []
    for move in game.mainline_moves():
        fen_before = board.fen()
        if board.turn == chess.WHITE and board.fullmove_number >= start_fullmove:
            entries.append(
                {
                    "fullmove": board.fullmove_number,
                    "fen_before": fen_before,
                    "move_uci": move.uci(),
                    "move_san": board.san(move),
                }
            )
        board.push(move)

    return {"info": game_info, "moves": entries}


def analyze_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for entry in entries:
        analysis = analyze_position(entry["fen_before"], entry["move_uci"])
        eval_info = analysis["eval"]
        metrics = analysis["metrics"]
        results.append(
            {
                "fullmove": entry["fullmove"],
                "move_san": entry["move_san"],
                "move_uci": entry["move_uci"],
                "fen_before": entry["fen_before"],
                "eval_before": eval_info["before"],
                "eval_played": eval_info["played"],
                "eval_best": eval_info["best"],
                "eval_delta": eval_info["delta"],
                "tactical_weight": round(analysis["tactical_weight"], 3),
                "mode": analysis["mode"],
                "tags_primary": analysis["tags"]["primary"],
                "tags_active": analysis["tags"]["active"],
                "tags_all": analysis["tags"]["all"],
                "metrics": metrics,
                "notes": analysis["notes"],
                "engine_meta": analysis["engine_meta"],
            }
        )
    return results


def build_summary(per_move: List[Dict[str, Any]]) -> Dict[str, Any]:
    tag_counts = Counter()
    eval_by_tag: Dict[str, List[float]] = defaultdict(list)
    for move in per_move:
        delta = move["eval_delta"]
        for tag, active in move["tags_all"].items():
            if active:
                tag_counts[tag] += 1
                eval_by_tag[tag].append(delta)

    total_moves = len(per_move)
    tag_frequencies = {}
    for tag in tag_counts:
        values = eval_by_tag[tag]
        tag_frequencies[tag] = {
            "count": tag_counts[tag],
            "ratio": round(tag_counts[tag] / total_moves, 3) if total_moves else 0.0,
            "avg_eval_delta": round(sum(values) / len(values), 3) if values else 0.0,
        }

    tag_frequencies = dict(
        sorted(tag_frequencies.items(), key=lambda item: item[1]["count"], reverse=True)
    )

    return {
        "total_moves_analyzed": total_moves,
        "tag_frequencies": tag_frequencies,
    }


def render_html(data: Dict[str, Any]) -> str:
    moves = data["moves"]
    summary = data["summary"]
    info = data["game_info"]

    rows = []
    for idx, move in enumerate(moves, start=1):
        primary_tags = ", ".join(move["tags_primary"]) or "(none)"
        rows.append(
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{move['fullmove']}</td>"
            f"<td>{move['move_san']}</td>"
            f"<td><code>{move['move_uci']}</code></td>"
            f"<td><small>{move['fen_before']}</small></td>"
            f"<td>{move['eval_before']:.2f}</td>"
            f"<td>{move['eval_played']:.2f}</td>"
            f"<td>{move['eval_delta']:+.2f}</td>"
            f"<td>{primary_tags}</td>"
            "</tr>"
        )

    summary_rows = []
    for tag, info_block in summary["tag_frequencies"].items():
        summary_rows.append(
            f"<tr><td>{tag}</td><td>{info_block['count']}</td><td>{info_block['ratio']:.3f}</td><td>{info_block['avg_eval_delta']:+.2f}</td></tr>"
        )

    html = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Kasparov Game Analysis</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    h1, h2 {{ margin-bottom: 0.5rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem; text-align: left; }}
    th {{ background: #f5f5f5; }}
    code {{ background: #eee; padding: 0 0.25rem; }}
    small {{ font-size: 0.8rem; }}
  </style>
</head>
<body>
  <h1>Kasparov Game Analysis</h1>
  <section>
    <h2>Game Info</h2>
    <ul>
      <li><strong>Event:</strong> {info.get('event', '')}</li>
      <li><strong>Date:</strong> {info.get('date', '')}</li>
      <li><strong>Round:</strong> {info.get('round', '')}</li>
      <li><strong>Site:</strong> {info.get('site', '')}</li>
      <li><strong>White:</strong> {info.get('white', '')}</li>
      <li><strong>Black:</strong> {info.get('black', '')}</li>
      <li><strong>Result:</strong> {info.get('result', '')}</li>
    </ul>
  </section>
  <section>
    <h2>Summary</h2>
    <p>Total white moves analyzed (from move 7 onwards): {summary['total_moves_analyzed']}</p>
    <table>
      <thead><tr><th>Tag</th><th>Count</th><th>Ratio</th><th>Avg Eval Δ</th></tr></thead>
      <tbody>{''.join(summary_rows)}</tbody>
    </table>
  </section>
  <section>
    <h2>Per-Move Detail</h2>
    <table>
      <thead><tr><th>#</th><th>Move</th><th>SAN</th><th>UCI</th><th>FEN (before)</th><th>Eval</th><th>Eval (played)</th><th>Δ</th><th>Primary Tags</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
</body>
</html>
"""
    return html


def write_text_summary(summary: Dict[str, Any], output: Path) -> None:
    lines = [f"Total moves analyzed: {summary['total_moves_analyzed']}", "Tag frequencies:"]
    for tag, info in summary["tag_frequencies"].items():
        lines.append(
            f"  - {tag}: count={info['count']}, ratio={info['ratio']:.3f}, avg_eval_delta={info['avg_eval_delta']:+.2f}"
        )
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    pgn_path = base_dir / "Test_players" / "test_kasparov_garry.pgn"
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    extracted = extract_white_moves(pgn_path, start_fullmove=7)
    per_move = analyze_entries(extracted["moves"])
    summary = build_summary(per_move)

    result = {
        "game_info": extracted["info"],
        "moves": per_move,
        "summary": summary,
    }

    json_path = reports_dir / "kasparov_game_test.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    html_content = render_html(result)
    (reports_dir / "kasparov_game_test.html").write_text(html_content, encoding="utf-8")

    write_text_summary(summary, reports_dir / "kasparov_game_test_summary.txt")

    print(f"[Codex] Parsed: {extracted['info'].get('white')} vs {extracted['info'].get('black')}")
    print(f"[Codex] White moves analyzed from move 7 onward: {len(per_move)}")
    top_tags = list(summary["tag_frequencies"].items())[:5]
    if top_tags:
        print("[Codex] Top tags:")
        for tag, info in top_tags:
            print(
                f"    {tag}: count={info['count']}, ratio={info['ratio']:.3f}, avg_eval_delta={info['avg_eval_delta']:+.2f}"
            )
    print(f"[Codex] Reports saved to {reports_dir}")


if __name__ == "__main__":
    main()
