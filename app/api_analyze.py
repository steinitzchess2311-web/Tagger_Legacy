from __future__ import annotations

from typing import Any, Dict, Optional

import os
from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel, Field

from codex_utils import analyze_position

router = APIRouter()


class AnalyzeRequest(BaseModel):
    fen: str = Field(..., min_length=1)
    move: Optional[str] = None
    played_move_uci: Optional[str] = None
    depth: int = Field(14, ge=1, le=30)
    multipv: int = Field(6, ge=1, le=10)
    use_new: Optional[bool] = None
    engine_path: Optional[str] = None


def _extract_primary_tags(payload: Dict[str, Any]) -> list[str]:
    tags = payload.get("tags") or {}
    if isinstance(tags, dict):
        primary = tags.get("primary")
        if isinstance(primary, list):
            return primary
    if isinstance(payload.get("primary_tags"), list):
        return payload.get("primary_tags") or []
    return []


@router.post("/tagger/analyze", dependencies=[Depends(_auth_guard)])
def analyze(payload: AnalyzeRequest) -> Dict[str, Any]:
    move = payload.played_move_uci or payload.move
    if not move:
        raise HTTPException(status_code=400, detail="move or played_move_uci is required.")

    analysis = analyze_position(
        payload.fen,
        move,
        engine_path=payload.engine_path,
        use_new=payload.use_new,
        depth=payload.depth,
        multipv=payload.multipv,
    )

    primary = _extract_primary_tags(analysis)
    active = analysis.get("tags", {}).get("active") or []

    flat_tags = active or primary
    return {
        "fen": analysis.get("fen"),
        "move": analysis.get("move"),
        "tags": {
            "primary": primary,
            "active": active,
        },
        "tags_list": flat_tags,
        "primary_tags": primary,
        "active_tags": active,
        "analysis": analysis,
    }
def _auth_guard(authorization: str | None = Header(default=None)) -> None:
    token = os.getenv("TAGGER_API_TOKEN", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="TAGGER_API_TOKEN not set.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization.")
    if authorization.split(" ", 1)[1] != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token.")
