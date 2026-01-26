from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import chess
import requests


def _parse_uci_info(line: str) -> Optional[Dict[str, Any]]:
    parts = line.split()
    if "multipv" not in parts or "score" not in parts or "pv" not in parts:
        return None
    try:
        multipv_idx = parts.index("multipv")
        score_idx = parts.index("score")
        pv_idx = parts.index("pv")
        multipv_num = int(parts[multipv_idx + 1])
        score_type = parts[score_idx + 1]
        score_value = int(parts[score_idx + 2])
        pv_moves = parts[pv_idx + 1 :]
    except (ValueError, IndexError):
        return None

    if score_type == "mate":
        score_cp = 10000 - abs(score_value) * 100 if score_value > 0 else -10000 + abs(score_value) * 100
    else:
        score_cp = score_value

    return {"multipv": multipv_num, "score_cp": score_cp, "pv": pv_moves}


def _post_analyze(engine_url: str, fen: str, depth: int, multipv: int) -> Dict[int, Dict[str, Any]]:
    headers = {}
    token = os.getenv("WORKER_API_TOKEN") or os.getenv("ENGINE_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.post(
        engine_url,
        json={"fen": fen, "depth": depth, "multipv": multipv},
        timeout=10,
        headers=headers,
    )
    resp.raise_for_status()
    payload = resp.json()
    info_lines = payload.get("info", [])
    data: Dict[int, Dict[str, Any]] = {}
    for line in info_lines:
        if not isinstance(line, str):
            continue
        if line.startswith("info "):
            parsed = _parse_uci_info(line)
            if parsed:
                data[parsed["multipv"]] = parsed
    return data


def fetch_http_candidates(
    engine_url: str,
    board: chess.Board,
    depth: int,
    multipv: int,
) -> Tuple[List[chess.Move], List[int]]:
    data = _post_analyze(engine_url, board.fen(), depth, multipv)
    moves: List[chess.Move] = []
    scores: List[int] = []
    for entry in sorted(data.values(), key=lambda x: x["multipv"]):
        pv = entry.get("pv") or []
        if not pv:
            continue
        mv = chess.Move.from_uci(pv[0])
        moves.append(mv)
        scores.append(int(entry["score_cp"]))
    return moves, scores


def install_http_engine_shims(engine_url: Optional[str] = None) -> None:
    url = engine_url or os.getenv("ENGINE_URL", "")
    if not url:
        raise RuntimeError("ENGINE_URL is required for HTTP engine mode.")

    try:
        import rule_tagger2.legacy.core as legacy_core
        import rule_tagger2.legacy.core_v8 as legacy_core_v8
        import rule_tagger2.legacy.engine.analysis as legacy_analysis
        import rule_tagger2.legacy.engine as legacy_engine
    except Exception as exc:
        raise ImportError("Failed to import rule_tagger2 modules for HTTP engine shims.") from exc

    from rule_tagger2.models import Candidate

    def _http_analyse_candidates(
        engine_path: str,
        board: chess.Board,
        depth: int = 14,
        multipv: int = 6,
        depth_low: int = 6,
    ) -> Tuple[List[Candidate], int, Dict[str, Any]]:
        _ = engine_path
        moves, scores = fetch_http_candidates(url, board, depth, multipv)
        candidates: List[Candidate] = []
        for mv, sc in zip(moves, scores):
            candidates.append(Candidate(move=mv, score_cp=sc, kind=legacy_analysis.classify_move(board, mv)))

        eval_before_cp = scores[0] if scores else 0
        low_cp = eval_before_cp
        if depth_low and depth_low < depth:
            _, low_scores = fetch_http_candidates(url, board, depth_low, 1)
            if low_scores:
                low_cp = low_scores[0]

        depth_high = max(depth + 4, depth + 2)
        high_cp = eval_before_cp
        if depth_high > depth:
            _, high_scores = fetch_http_candidates(url, board, depth_high, 1)
            if high_scores:
                high_cp = high_scores[0]

        score_gap_cp = candidates[0].score_cp - candidates[1].score_cp if len(candidates) > 1 else 0
        depth_jump_cp = eval_before_cp - low_cp
        deepening_gain_cp = high_cp - eval_before_cp
        contact_ratio, total_moves, capture_count, checking_count = legacy_analysis.contact_profile(board)
        phase_ratio = legacy_analysis.estimate_phase_ratio(board)
        mate_threat = abs(eval_before_cp) >= 9000 or abs(high_cp) >= 9000

        analysis_meta: Dict[str, Any] = {
            "score_gap_cp": score_gap_cp,
            "depth_jump_cp": depth_jump_cp,
            "deepening_gain_cp": deepening_gain_cp,
            "contact_ratio": contact_ratio,
            "contact_moves": capture_count + checking_count,
            "capture_moves": capture_count,
            "checking_moves": checking_count,
            "total_moves": total_moves,
            "phase_ratio": round(phase_ratio, 3),
            "mate_threat": mate_threat,
        }
        analysis_meta.setdefault("engine_meta", {})
        analysis_meta["engine_meta"].update(
            {
                "depth_used": depth,
                "multipv": multipv,
                "depth_low": depth_low,
                "depth_high": depth_high,
                "engine_url": url,
                "engine_mode": "http",
            }
        )

        return candidates, eval_before_cp, analysis_meta

    def _http_eval_specific_move(
        engine_path: str,
        board: chess.Board,
        move: chess.Move,
        depth: int = 14,
    ) -> int:
        _ = engine_path
        board_copy = board.copy(stack=False)
        board_copy.push(move)
        _, scores = fetch_http_candidates(url, board_copy, depth, 1)
        return scores[0] if scores else 0

    def _http_simulate_followup_metrics(
        engine: chess.engine.SimpleEngine,
        board: chess.Board,
        actor: chess.Color,
        steps: int = 3,
        depth: int = 6,
    ) -> Tuple[Dict[str, float], Dict[str, float], list[Dict[str, float]], list[Dict[str, float]]]:
        _ = engine
        future_board = board.copy(stack=False)
        base_metrics, base_opp_metrics, _ = legacy_analysis.evaluation_and_metrics(future_board, actor)
        metrics_seq: list[Dict[str, float]] = []
        opp_seq: list[Dict[str, float]] = []
        for _ in range(steps):
            if future_board.is_game_over():
                break
            moves, _scores = fetch_http_candidates(url, future_board, depth, 1)
            if not moves:
                break
            future_board.push(moves[0])
            metrics, opp_metrics, _ = legacy_analysis.evaluation_and_metrics(future_board, actor)
            metrics_seq.append(metrics)
            opp_seq.append(opp_metrics)
        return base_metrics, base_opp_metrics, metrics_seq, opp_seq

    for module in (legacy_analysis, legacy_engine):
        module.analyse_candidates = _http_analyse_candidates
        module.eval_specific_move = _http_eval_specific_move
        module.simulate_followup_metrics = _http_simulate_followup_metrics

    for module in (legacy_core, legacy_core_v8):
        module.analyse_candidates = _http_analyse_candidates
        module.eval_specific_move = _http_eval_specific_move
        module.simulate_followup_metrics = _http_simulate_followup_metrics
