"""Engine helper utilities for the FastAPI backend."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

import chess
import chess.engine

DEFAULT_ENGINE_PATH = "/usr/local/bin/stockfish"


@lru_cache(maxsize=128)
def fetch_engine_moves(
    fen: str,
    engine_path: Optional[str] = None,
    top_n: int = 7,
    depth: int = 14,
) -> List[dict]:
    """Fetch top engine moves for the given FEN."""
    board = chess.Board(fen)
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
