from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from codex_utils import DEFAULT_ENGINE_PATH
from core.engine_utils import fetch_engine_moves
from core.file_utils import load_player_summaries
from core.predictor import compute_move_probability
from core.tagger_utils import tag_moves

router = APIRouter()


class ImitatorRequest(BaseModel):
    fen: str = Field(..., min_length=1)
    player: Optional[str] = None
    top_n: int = Field(5, ge=1, le=10)
    depth: int = Field(14, ge=1, le=30)
    engine_path: Optional[str] = None


class ImitatorMove(BaseModel):
    move: str
    uci: str
    score_cp: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    probability: float


class ImitatorResponse(BaseModel):
    player: str
    moves: List[ImitatorMove]
    meta: Dict[str, Any]


def _ensure_engine_path(path: Optional[str]) -> str:
    engine_path = path or DEFAULT_ENGINE_PATH
    if not engine_path:
        raise HTTPException(status_code=400, detail="Engine path not configured.")
    return engine_path


def _extract_probabilities(tagged: List[dict], player_summary: Dict[str, Any]) -> List[ImitatorMove]:
    probabilities = compute_move_probability(tagged, player_summary["tag_distribution"])
    if probabilities.size == 0:
        return []
    ranked = sorted(
        zip(tagged, probabilities),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    output: List[ImitatorMove] = []
    for entry, prob in ranked:
        output.append(
            ImitatorMove(
                move=entry["move"],
                uci=entry["uci"],
                score_cp=entry.get("score_cp"),
                tags=list(entry.get("tags") or []),
                probability=float(prob),
            )
        )
    return output


@router.get("/tagger/imitator/players")
def list_imitator_players() -> Dict[str, Any]:
    summaries = load_player_summaries("reports")
    return {"players": sorted(summaries.keys())}


@router.post("/tagger/imitator", response_model=ImitatorResponse)
def run_imitator(payload: ImitatorRequest) -> ImitatorResponse:
    try:
        chess.Board(payload.fen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {exc}") from exc

    summaries = load_player_summaries("reports")
    if not summaries:
        raise HTTPException(status_code=404, detail="No player summaries found.")

    player = payload.player or next(iter(summaries.keys()))
    if player not in summaries:
        raise HTTPException(status_code=404, detail=f"Unknown player: {player}")

    engine_path = _ensure_engine_path(payload.engine_path)
    top_moves = fetch_engine_moves(payload.fen, engine_path=engine_path, top_n=payload.top_n, depth=payload.depth)
    tagged = tag_moves(payload.fen, top_moves, engine_path=engine_path)
    moves = _extract_probabilities(tagged, summaries[player])

    response_moves = moves[: payload.top_n]
    return ImitatorResponse(
        player=player,
        moves=response_moves,
        meta={
            "depth": payload.depth,
            "top_n": payload.top_n,
            "engine_path": engine_path,
        },
    )
