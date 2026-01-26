"""
Stockfish-backed engine client implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import chess

from ..legacy.engine import analyse_candidates, eval_specific_move, simulate_followup_metrics
from ..models import Candidate, EngineCandidates, EngineMove
from .protocol import EngineClient


@dataclass
class StockfishConfig:
    engine_path: str
    default_depth: int = 14
    default_multipv: int = 6
    default_depth_low: int = 6


class StockfishEngineClient(EngineClient):
    """Adapter that reuses the legacy Stockfish helpers via the EngineClient protocol."""

    def __init__(self, config: StockfishConfig):
        self._cfg = config

    def analyze(
        self,
        fen: str,
        *,
        depth: int,
        multipv: int,
        depth_low: int = 0,
    ) -> EngineCandidates:
        board = chess.Board(fen)
        used_depth = depth or self._cfg.default_depth
        used_multipv = multipv or self._cfg.default_multipv
        used_depth_low = depth_low if depth_low else self._cfg.default_depth_low

        candidates, eval_before_cp, meta = analyse_candidates(
            self._cfg.engine_path,
            board,
            depth=used_depth,
            multipv=used_multipv,
            depth_low=used_depth_low,
        )
        engine_moves = [self._convert_candidate(cand) for cand in candidates]
        return EngineCandidates(
            fen=fen,
            side_to_move=board.turn,
            candidates=engine_moves,
            eval_before_cp=eval_before_cp,
            analysis_meta=meta,
        )

    def eval_move(self, fen: str, move_uci: str, *, depth: int) -> int:
        board = chess.Board(fen)
        move = chess.Move.from_uci(move_uci)
        return eval_specific_move(
            self._cfg.engine_path,
            board,
            move,
            depth=max(depth, 1),
        )

    def simulate_followup(
        self,
        fen: str,
        actor: chess.Color,
        *,
        steps: int,
        depth: int,
    ) -> Tuple[
        Dict[str, float],
        Dict[str, float],
        List[Dict[str, float]],
        List[Dict[str, float]],
    ]:
        board = chess.Board(fen)
        with chess.engine.SimpleEngine.popen_uci(self._cfg.engine_path) as eng:
            return simulate_followup_metrics(
                eng,
                board,
                actor,
                steps=steps,
                depth=depth,
            )

    def identifier(self) -> str:
        return self._cfg.engine_path

    @staticmethod
    def _convert_candidate(cand: Candidate) -> EngineMove:
        return EngineMove(
            move=cand.move,
            score_cp=cand.score_cp,
            kind=cand.kind,
            info={},
        )
