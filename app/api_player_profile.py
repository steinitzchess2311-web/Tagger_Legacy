from __future__ import annotations

import json
import os
import threading
import uuid
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
REPORTS_DIR = BASE_DIR / "reports"
JOBS_DIR = REPORTS_DIR / "jobs"
JOBS_FILE = JOBS_DIR / "jobs.json"

_JOBS_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_jobs() -> None:
    if not JOBS_FILE.exists():
        return
    try:
        payload = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(payload, dict):
        _JOBS.update(payload)


def _save_jobs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(_JOBS, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass
class JobSpec:
    player: str
    input_dir: str
    output_prefix: str
    status: str
    created_at: str
    updated_at: str
    log_path: str
    job_id: str
    error: Optional[str] = None
    finished_at: Optional[str] = None
    command: Optional[List[str]] = None


class PlayerProfileRequest(BaseModel):
    player: str = Field(..., min_length=1)
    pgn_text: Optional[str] = None
    pgn_base64: Optional[str] = None
    pgn_url: Optional[str] = None
    start_fullmove: int = Field(1, ge=1)
    max_games: int = Field(0, ge=0)
    max_moves: int = Field(0, ge=0)
    output_prefix: Optional[str] = None
    fresh_run: bool = False
    resume: bool = False
    pipeline_mode: Optional[str] = Field(
        default=None, description="new, legacy, or auto (default)"
    )


class PlayerProfileResponse(BaseModel):
    job_id: str
    status: str
    output_prefix: str
    log_path: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    player: str
    output_prefix: str
    log_path: str
    created_at: str
    updated_at: str
    finished_at: Optional[str]
    error: Optional[str]
    command: Optional[List[str]]


def _canonicalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _write_job_pgn(job_dir: Path, payload: PlayerProfileRequest) -> Path:
    job_dir.mkdir(parents=True, exist_ok=True)
    pgn_path = job_dir / "input.pgn"

    if payload.pgn_text:
        pgn_path.write_text(payload.pgn_text, encoding="utf-8")
        return pgn_path

    if payload.pgn_base64:
        import base64

        decoded = base64.b64decode(payload.pgn_base64)
        pgn_path.write_bytes(decoded)
        return pgn_path

    if payload.pgn_url:
        import requests

        resp = requests.get(payload.pgn_url, timeout=20)
        resp.raise_for_status()
        pgn_path.write_bytes(resp.content)
        return pgn_path

    raise HTTPException(status_code=400, detail="PGN input is required.")


def _start_job(job: JobSpec) -> None:
    job_dir = Path(job.input_dir)
    log_path = Path(job.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with _JOBS_LOCK:
        current = _JOBS.get(job.job_id, {})
        current.update({"status": "running", "updated_at": _utc_now()})
        _JOBS[job.job_id] = current
        _save_jobs()

    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            job.command,
            cwd=str(BASE_DIR),
            stdout=handle,
            stderr=handle,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        exit_code = proc.wait()

    with _JOBS_LOCK:
        current = _JOBS.get(job.job_id, {})
        status = "completed" if exit_code == 0 else "failed"
        current.update(
            {
                "status": status,
                "updated_at": _utc_now(),
                "finished_at": _utc_now(),
                "error": None if exit_code == 0 else f"Process exited with {exit_code}",
            }
        )
        _JOBS[job.job_id] = current
        _save_jobs()


@router.post("/tagger/playerProfile", response_model=PlayerProfileResponse)
def enqueue_player_profile(payload: PlayerProfileRequest) -> PlayerProfileResponse:
    job_id = uuid.uuid4().hex
    output_prefix = payload.output_prefix or _canonicalize(payload.player) or f"profile_{job_id[:8]}"

    job_dir = JOBS_DIR / job_id
    _write_job_pgn(job_dir, payload)

    cmd = [
        os.environ.get("PYTHON_EXECUTABLE") or os.sys.executable,
        "scripts/analyze_player_batch.py",
        "--player",
        payload.player,
        "--input-dir",
        str(job_dir),
        "--output-prefix",
        output_prefix,
        "--start-fullmove",
        str(payload.start_fullmove),
    ]

    if payload.max_games:
        cmd.extend(["--max-games", str(payload.max_games)])
    if payload.max_moves:
        cmd.extend(["--max-moves", str(payload.max_moves)])
    if payload.fresh_run:
        cmd.append("--fresh-run")
    if payload.resume:
        cmd.append("--resume")
    if payload.pipeline_mode == "new":
        cmd.append("--new-pipeline")
    elif payload.pipeline_mode == "legacy":
        cmd.append("--legacy")

    job = JobSpec(
        job_id=job_id,
        player=payload.player,
        input_dir=str(job_dir),
        output_prefix=output_prefix,
        status="queued",
        created_at=_utc_now(),
        updated_at=_utc_now(),
        log_path=str(job_dir / "run.log"),
        command=cmd,
    )

    with _JOBS_LOCK:
        _JOBS[job_id] = asdict(job)
        _save_jobs()

    thread = threading.Thread(target=_start_job, args=(job,), daemon=True)
    thread.start()

    return PlayerProfileResponse(
        job_id=job_id,
        status="queued",
        output_prefix=output_prefix,
        log_path=job.log_path,
    )


@router.get("/tagger/playerProfile/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(**job)
