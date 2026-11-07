from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
STORAGE = Path(os.getenv("ANIMA_STORAGE", "/data/jobs"))
STORAGE.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    app_name: str = "Anima 2D"
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
app = FastAPI(title=settings.app_name, version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    story: str = Field(default="Luna e Tomi ajudam a escola a resolver um mistério com honestidade e amizade.", min_length=10, max_length=5000)
    formats: list[str] = Field(default_factory=lambda: ["16:9", "9:16"])
    episode: str = "original"

JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()

@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": "0.2.0", "ffmpeg": _has("ffmpeg")}

@app.get("/api/config")
def config():
    return {
        "formats": [
            {"id": "16:9", "width": 1920, "height": 1080, "label": "YouTube horizontal"},
            {"id": "9:16", "width": 1080, "height": 1920, "label": "YouTube Shorts"},
        ],
        "youtube_oauth_configured": bool(settings.youtube_client_id and settings.youtube_client_secret),
        "generation_enabled": _has("ffmpeg"),
        "engine": "Anima 2D procedural vector-cartoon MVP",
    }

@app.post("/api/generate", status_code=202)
def generate(payload: GenerateRequest):
    allowed = {"16:9", "9:16"}
    if not payload.formats or any(x not in allowed for x in payload.formats):
        raise HTTPException(400, "Selecione 16:9 e/ou 9:16.")
    if not _has("ffmpeg"):
        raise HTTPException(503, "FFmpeg não está instalado no servidor.")
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "title": payload.title, "status": "queued", "progress": 0,
        "message": "Na fila de produção", "formats": payload.formats, "outputs": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with LOCK:
        JOBS[job_id] = job
        _save(job_id, job)
    threading.Thread(target=_run_job, args=(job_id, payload), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/jobs")
def list_jobs():
    with LOCK:
        return {"jobs": sorted(JOBS.values(), key=lambda x: x["created_at"], reverse=True)}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = _get_job(job_id)
    return job

@app.get("/api/jobs/{job_id}/download/{fmt}")
def download(job_id: str, fmt: str):
    job = _get_job(job_id)
    if fmt not in job.get("outputs", {}):
        raise HTTPException(404, "Vídeo ainda não disponível.")
    path = Path(job["outputs"][fmt])
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(path, media_type="video/mp4", filename=f"{job['title']}-{fmt.replace(':','x')}.mp4")

def _has(binary: str) -> bool:
    from shutil import which
    return which(binary) is not None

def _save(job_id: str, job: dict):
    folder = STORAGE / job_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

def _get_job(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
    if job is None:
        p = STORAGE / job_id / "job.json"
        if p.exists():
            job = json.loads(p.read_text(encoding="utf-8"))
            with LOCK:
                JOBS[job_id] = job
    if job is None:
        raise HTTPException(404, "Projeto não encontrado.")
    return job

def _update(job_id: str, **changes):
    with LOCK:
        job = JOBS[job_id]
        job.update(changes)
        _save(job_id, job)

def _run_job(job_id: str, payload: GenerateRequest):
    try:
        from backend.app.renderer import render_episode
        for index, fmt in enumerate(payload.formats):
            _update(job_id, status="processing", progress=int(index * 100 / len(payload.formats)), message=f"Animando versão {fmt}…")
            output = STORAGE / job_id / f"episode-{fmt.replace(':','x')}.mp4"
            render_episode(payload.title, payload.story, fmt, output, STORAGE / job_id)
            current = _get_job(job_id)
            outputs = dict(current.get("outputs", {}))
            outputs[fmt] = str(output)
            _update(job_id, outputs=outputs, progress=int((index + 1) * 100 / len(payload.formats)), message=f"Versão {fmt} pronta.")
        _update(job_id, status="done", progress=100, message="Episódio renderizado com sucesso.")
    except Exception as exc:
        _update(job_id, status="failed", message=f"Falha na renderização: {exc}")

if WEB.exists():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
