"""Engine helper utilities."""
from __future__ import annotations

from typing import List, Optional

import chess
import chess.engine

from codex_utils import DEFAULT_ENGINE_PATH


def fetch_engine_moves(
    fen: str,
    engine_path: Optional[str] = None,
    top_n: int = 7,
    depth: int = 14,
) -> List[dict]:
    """Return top moves suggested by the engine for the given FEN."""
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
