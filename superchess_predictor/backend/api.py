"""FastAPI backend for Superchess Predictor."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .engine_utils import fetch_engine_moves
from .file_utils import load_player_summaries
from .predictor import compute_move_probabilities
from .tagger_utils import tag_moves

app = FastAPI(title="Superchess Predictor API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FENRequest(BaseModel):
    fen: str
    engine_path: Optional[str] = None


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: FENRequest) -> dict:
    try:
        tagged_moves = tag_moves(
            request.fen,
            fetch_engine_moves(
                request.fen,
                engine_path=request.engine_path,
            ),
            engine_path=request.engine_path,
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    player_summaries = load_player_summaries(
        Path(__file__).resolve().parents[1] / "reports"
    )

    if not player_summaries:
        raise HTTPException(status_code=500, detail="No player summaries found.")

    probabilities = compute_move_probabilities(
        tagged_moves,
        {name: summary["tag_distribution"] for name, summary in player_summaries.items()},
    )

    moves_output = []
    for move, probs in zip(tagged_moves, probabilities):
        moves_output.append(
            {
                "san": move["san"],
                "uci": move["uci"],
                "score_cp": move.get("score_cp"),
                "tags": move.get("tags", []),
                "tag_flags": move.get("analysis", {}).get("tags", {}).get("all", {}),
                "probabilities": probs,
            }
        )

    payload = {
        "players": list(player_summaries.keys()),
        "moves": moves_output,
        "metadata": {
            "engine_depth": 14,
            "top_n": 7,
        },
    }
    # best-effort logging (non-blocking)
    try:
        log_dir = Path(__file__).resolve().parents[4] / "website_predictor" / "loglog"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / f"log_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        entry = {
            "ts_utc": datetime.utcnow().isoformat() + "Z",
            "fen": request.fen,
            "engine_path": request.engine_path,
            "payload": payload,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return payload
