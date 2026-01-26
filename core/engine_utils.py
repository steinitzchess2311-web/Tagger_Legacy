"""Engine helper utilities."""
from __future__ import annotations

import os
from typing import List, Optional

import chess
import chess.engine

from codex_utils import DEFAULT_ENGINE_PATH
from connect.http_engine import fetch_http_candidates


def fetch_engine_moves(
    fen: str,
    engine_path: Optional[str] = None,
    top_n: int = 7,
    depth: int = 14,
) -> List[dict]:
    """Return top moves suggested by the engine for the given FEN."""
    board = chess.Board(fen)
    engine_url = os.getenv("ENGINE_URL")
    if engine_url:
        moves, scores = fetch_http_candidates(engine_url, board, depth, min(top_n, 7))
        candidates: List[dict] = []
        for mv, sc in list(zip(moves, scores))[:top_n]:
            try:
                san = board.san(mv)
            except ValueError:
                san = mv.uci()
            candidates.append({"san": san, "uci": mv.uci(), "score_cp": sc})
        return candidates

    engine_bin = engine_path or DEFAULT_ENGINE_PATH

    with chess.engine.SimpleEngine.popen_uci(engine_bin) as engine:
        info = engine.analyse(
            board,
            chess.engine.Limit(depth=depth),
            multipv=min(top_n, 7),
        )

    infos = info if isinstance(info, list) else [info]

    candidates: List[dict] = []
    for entry in infos[:top_n]:
        pv = entry.get("pv")
        if not pv:
            continue
        move = pv[0]
        try:
            san = board.san(move)
        except ValueError:
            san = move.uci()
        score = entry.get("score")
        score_cp = None
        if isinstance(score, chess.engine.PovScore):
            score_cp = score.white().score(mate_score=10000)
        candidates.append(
            {
                "san": san,
                "uci": move.uci(),
                "score_cp": score_cp,
            }
        )
    return candidates
