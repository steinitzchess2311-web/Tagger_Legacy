from __future__ import annotations

from typing import Any, Dict, List, Optional

import os
import time
import chess
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from codex_utils import DEFAULT_ENGINE_PATH
from core.blunder_gate import evaluate_engine_gap, forced_probabilities
from core.db_player_summaries import load_player_summaries_from_db, load_player_summary_by_id
from core.engine_utils import fetch_engine_moves
from core.file_utils import load_player_profiles, load_player_summaries
from core.predictor import compute_move_probability
from core.tagger_utils import tag_moves
from faster import FastTaggerSession

router = APIRouter()


class ImitatorRequest(BaseModel):
    fen: str = Field(..., min_length=1)
    player: Optional[str] = None
    player_id: Optional[str] = None
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


def _load_summaries(source: str, *, only_success: bool = True) -> Dict[str, Dict[str, Any]]:
    if source == "library":
        return load_player_profiles("players")
    if source == "user":
        return load_player_summaries_from_db(only_success=only_success)
    if source == "all":
        combined = load_player_profiles("players")
        combined.update(load_player_summaries_from_db(only_success=only_success))
        return combined
    raise HTTPException(status_code=400, detail="Invalid source. Use library, user, or all.")


@router.get("/tagger/imitator/players")
def list_imitator_players(
    source: str = Query("library"),
    include_ids: bool = Query(False),
    status: str = Query("success"),
) -> Dict[str, Any]:
    only_success = status == "success"
    summaries = _load_summaries(source, only_success=only_success)

    if include_ids and source in ("user", "all"):
        # When include_ids requested for user data, rebuild from DB to include IDs.
        db_summaries = load_player_summaries_from_db(only_success=only_success)
        if source == "all":
            library = load_player_profiles("players")
            db_summaries.update(library)
        items = [
            {"id": meta.get("player_id"), "name": name}
            for name, meta in ((n, v.get("meta", {})) for n, v in db_summaries.items())
        ]
        return {"players": items, "source": source, "status": status}

    return {"players": sorted(summaries.keys()), "source": source, "status": status}


@router.post("/tagger/imitator", response_model=ImitatorResponse)
def run_imitator(payload: ImitatorRequest) -> ImitatorResponse:
    t0 = time.perf_counter()
    try:
        chess.Board(payload.fen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {exc}") from exc

    summaries = _load_summaries(payload.source)
    if not summaries:
        raise HTTPException(status_code=404, detail="No player summaries found.")

    player = payload.player or next(iter(summaries.keys()))
    player_summary = summaries.get(player)

    if payload.player_id:
        player_summary = load_player_summary_by_id(payload.player_id)
        if player_summary is None:
            raise HTTPException(status_code=404, detail="Unknown player_id.")
        player = player_summary["meta"]["player"]

    if player_summary is None:
        raise HTTPException(status_code=404, detail=f"Unknown player: {player}")

    engine_path = _ensure_engine_path(payload.engine_path)
    t_fetch_start = time.perf_counter()
    top_moves = fetch_engine_moves(payload.fen, engine_path=engine_path, top_n=payload.top_n, depth=payload.depth)
    t_fetch = (time.perf_counter() - t_fetch_start) * 1000.0
    gate = evaluate_engine_gap(top_moves, threshold_cp=200)
    if gate["triggered"]:
        forced = forced_probabilities(top_moves, engine1_index=int(gate["engine1_index"]))
        moves: List[ImitatorMove] = []
        for entry, prob in zip(top_moves, forced):
            moves.append(
                ImitatorMove(
                    move=entry["san"],
                    uci=entry["uci"],
                    score_cp=entry.get("score_cp"),
                    tags=[],
                    probability=float(prob),
                )
            )
        response_moves = moves[: payload.top_n]
        return ImitatorResponse(
            player=player,
            moves=response_moves,
            meta={
                "depth": payload.depth,
                "top_n": payload.top_n,
                "engine_path": engine_path,
                "blunder_gate": gate,
            },
        )
    if os.getenv("ENGINE_URL"):
        t_tag_start = time.perf_counter()
        tagged = tag_moves(payload.fen, top_moves, engine_path=engine_path)
        t_tag = (time.perf_counter() - t_tag_start) * 1000.0
    else:
        tagged = []
        t_tag_start = time.perf_counter()
        with FastTaggerSession(engine_path) as session:
            for entry in top_moves:
                move_uci = entry["uci"]
                analysis = session.tag_position(
                    payload.fen,
                    move_uci,
                    depth=payload.depth,
                    multipv=6,
                )
                active_tags = analysis["tags"]["active"]
                if not active_tags:
                    active_tags = analysis["tags"]["primary"]
                tagged.append(
                    {
                        "move": entry["san"],
                        "uci": move_uci,
                        "score_cp": entry.get("score_cp"),
                        "tags": active_tags,
                    "analysis": analysis,
                }
            )
        t_tag = (time.perf_counter() - t_tag_start) * 1000.0
    t_prob_start = time.perf_counter()
    moves = _extract_probabilities(tagged, player_summary)
    t_prob = (time.perf_counter() - t_prob_start) * 1000.0
    t_total = (time.perf_counter() - t0) * 1000.0
    print(
        f"[imitator] timing total={t_total:.1f}ms fetch={t_fetch:.1f}ms "
        f"tag={t_tag:.1f}ms prob={t_prob:.1f}ms moves={len(top_moves)} "
        f"engine_url={bool(os.getenv('ENGINE_URL'))}"
    )

    response_moves = moves[: payload.top_n]
    return ImitatorResponse(
        player=player,
        moves=response_moves,
        meta={
            "depth": payload.depth,
            "top_n": payload.top_n,
            "engine_path": engine_path,
            "blunder_gate": gate,
        },
    )
