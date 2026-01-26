from __future__ import annotations

from typing import Any, Dict, List, Optional

import os
import chess
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from codex_utils import DEFAULT_ENGINE_PATH
from core.db_player_summaries import load_player_summaries_from_db
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
    source: str = Field("library", description="library, user, or all")


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
    if os.getenv("ENGINE_URL"):
        return path or DEFAULT_ENGINE_PATH
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


def _load_summaries(source: str) -> Dict[str, Dict[str, Any]]:
    if source == "library":
        return load_player_summaries("reports")
    if source == "user":
        return load_player_summaries_from_db()
    if source == "all":
        combined = load_player_summaries("reports")
        combined.update(load_player_summaries_from_db())
        return combined
    raise HTTPException(status_code=400, detail="Invalid source. Use library, user, or all.")


@router.get("/tagger/imitator/players")
def list_imitator_players(source: str = Query("library")) -> Dict[str, Any]:
    summaries = _load_summaries(source)
    return {"players": sorted(summaries.keys()), "source": source}


@router.post("/tagger/imitator", response_model=ImitatorResponse)
def run_imitator(payload: ImitatorRequest) -> ImitatorResponse:
    try:
        chess.Board(payload.fen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {exc}") from exc

    summaries = _load_summaries(payload.source)
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
