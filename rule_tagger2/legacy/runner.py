"""
Batch/CLI helpers for the rule tagger.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .core import tag_position
from .engine import load_positions_from_json, load_positions_from_pgn
from .models import TagResult


def _extract_output_tags(engine_meta: Dict[str, Any], legacy_flags: Dict[str, bool]) -> Dict[str, bool]:
    tag_flags_v8 = engine_meta.get("tag_flags_v8")
    if tag_flags_v8:
        return {str(name): bool(value) for name, value in tag_flags_v8.items()}
    return dict(legacy_flags)


def _primary_tags(engine_meta: Dict[str, Any], tag_flags: Dict[str, bool]) -> List[str]:
    if "tags_final_v8" in engine_meta:
        return list(engine_meta["tags_final_v8"])
    gating = engine_meta.get("gating", {})
    if gating.get("tags_primary"):
        return list(gating["tags_primary"])
    return [name for name, active in tag_flags.items() if active]


def batch_tag_positions(
    engine_path: str,
    positions: Iterable[Dict[str, str]],
    *,
    depth: int = 12,
    multipv: int = 6,
    cp_threshold: int = 100,
    small_drop_cp: int = 30,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    total = len(positions) if isinstance(positions, list) else None
    tag_position_impl = tag_position
    for idx, entry in enumerate(positions, start=1):
        fen = entry["fen"]
        move = entry["move"]
        key = (fen, move)
        if key in seen:
            print(f"↩️  Skipping duplicate position {idx}: move {move}")
            continue
        try:
            if total:
                print(f"🧮 Analyzing position {idx}/{total}...")
            else:
                print(f"🧮 Analyzing position {idx}...")
            result = tag_position_impl(
                engine_path,
                fen,
                move,
                depth=depth,
                multipv=multipv,
                cp_threshold=cp_threshold,
                small_drop_cp=small_drop_cp,
            )
            seen.add(key)
            engine_meta = result.analysis_context.get("engine_meta", {})
            legacy_flags = {name: value for name, value in result.__dict__.items() if isinstance(value, bool)}
            tag_flags = _extract_output_tags(engine_meta, legacy_flags)
            tags_primary = _primary_tags(engine_meta, tag_flags)
            results.append(
                {
                    "fen": fen,
                    "move": move,
                    "mode": result.mode,
                    "tactical_weight": result.tactical_weight,
                    "eval": {
                        "before": result.eval_before,
                        "played": result.eval_played,
                        "best": result.eval_best,
                        "delta": result.delta_eval,
                    },
                    "metrics": {
                        "self_before": result.metrics_before,
                        "self_played": result.metrics_played,
                        "self_best": result.metrics_best,
                        "opp_before": result.opp_metrics_before,
                        "opp_played": result.opp_metrics_played,
                        "opp_best": result.opp_metrics_best,
                        "component_deltas": result.component_deltas,
                        "opp_component_deltas": result.opp_component_deltas,
                    },
                    "structural_details": engine_meta.get("structural_details"),
                    "coverage_delta": result.coverage_delta,
                    "engine_meta": engine_meta,
                    "tags": tag_flags,
                    "tags_final": tags_primary,
                    "notes": result.notes,
                }
            )
        except Exception as exc:
            print(f"⚠️ Failed on position {idx}: {exc}")
    return results


def _dump_results(results: List[Dict[str, Any]], output: Optional[Path]) -> None:
    if output:
        output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Saved batch analysis to {output}")
    else:
        for item in results:
            tags = item.get("tags_final") or [tag for tag, active in item["tags"].items() if active]
            print(
                f"\nMove: {item['move']} | Mode: {item['mode']} | "
                f"Tactical Weight: {item['tactical_weight']:.2f}\nTriggered tags: {tags}"
            )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Tag chess positions with stylistic labels.")
    parser.add_argument("--engine", default="/usr/local/bin/stockfish", help="Path to UCI engine (default: %(default)s)")
    parser.add_argument("--fen", help="Single-position FEN")
    parser.add_argument("--move", help="Move in UCI or SAN for the single FEN")
    parser.add_argument("--batch-json", type=Path, help="Path to JSON list of {fen, move} objects")
    parser.add_argument("--batch-pgn", type=Path, help="Path to PGN file to sample positions from")
    parser.add_argument("--sample-interval", type=int, default=3, help="Sample every N ply from PGN (default: %(default)s)")
    parser.add_argument("--limit", type=int, help="Limit number of sampled positions from PGN")
    parser.add_argument("--depth", type=int, default=12, help="Analysis depth (default: %(default)s)")
    parser.add_argument("--multipv", type=int, default=6, help="MultiPV count (default: %(default)s)")
    parser.add_argument("--cp-threshold", type=int, default=100, help="Candidate band threshold (default: %(default)s)")
    parser.add_argument("--small-drop", type=int, default=30, help="Small drop threshold in cp (default: %(default)s)")
    parser.add_argument("--output", type=Path, help="Optional JSON file to write batch results")
    args = parser.parse_args(argv)

    if args.batch_json or args.batch_pgn:
        positions: List[Dict[str, str]] = []
        if args.batch_json:
            positions.extend(load_positions_from_json(args.batch_json))
        if args.batch_pgn:
            positions.extend(load_positions_from_pgn(args.batch_pgn, sample_interval=args.sample_interval, limit=args.limit))
        if not positions:
            raise SystemExit("No positions found for batch processing.")
        results = batch_tag_positions(
            args.engine,
            positions,
            depth=args.depth,
            multipv=args.multipv,
            cp_threshold=args.cp_threshold,
            small_drop_cp=args.small_drop,
        )
        _dump_results(results, args.output)
    else:
        fen = args.fen or "r2q1rk1/1pp1bpp1/1n2p2p/p2pNb2/P2Pn3/1QP2NP1/1P2PPBP/R1B2RK1 w - - 2 12"
        move = args.move or "Rfe1"
        result = tag_position(
            args.engine,
            fen,
            move,
            depth=args.depth,
            multipv=args.multipv,
            cp_threshold=args.cp_threshold,
            small_drop_cp=args.small_drop,
        )
        payload = {
            "fen": fen,
            "move": move,
            "mode": result.mode,
            "tactical_weight": result.tactical_weight,
            "tags": [name for name, active in result.__dict__.items() if isinstance(active, bool) and active],
            "eval_before": result.eval_before,
            "eval_played": result.eval_played,
            "eval_best": result.eval_best,
        }
        if args.output:
            Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"✅ Saved single-position analysis to {args.output}")
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


__all__ = ["batch_tag_positions", "main"]
