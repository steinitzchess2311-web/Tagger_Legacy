from __future__ import annotations

import os
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api_analyze import router as analyze_router
from .api_imitator import router as imitator_router
from .api_player_profile import router as player_profile_router, init_jobs


app = FastAPI(title="Rule Tagger Imitator API", version="1.0")

origins = os.getenv("CORS_ORIGINS", "*")
origins_list = [origin.strip() for origin in origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list if origins_list else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_jobs()
    try:
        from connect.http_engine import install_http_engine_shims

        install_http_engine_shims()
    except Exception:
        # Keep service up even if HTTP engine isn't configured.
        pass


@app.get("/health")
def health() -> Dict[str, object]:
    return {
        "status": "ok",
        "env": {
            "TAGGER_API_TOKEN": bool(os.getenv("TAGGER_API_TOKEN")),
            "WORKER_API_TOKEN": bool(os.getenv("WORKER_API_TOKEN")),
            "ENGINE_URL": bool(os.getenv("ENGINE_URL")),
        },
    }

app.include_router(analyze_router)
app.include_router(imitator_router)
app.include_router(player_profile_router)
