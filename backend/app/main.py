from __future__ import annotations

import json
import math
import queue
import time
import os
import subprocess
import shutil
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from backend.app.worlds import WORLDS, build_episode_plan
from backend.app.cartoon2d import render_preview as render_2d_preview
from backend.app.runtime import find_blender_binary, find_blender_runtime, has_bpy_module, inspect_bpy_module, blender_available, reset_bpy_import_state
from backend.app.system_deps import native_library_status, ensure_blender_native_libraries

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
from backend.app.storage import storage_root
STORAGE = storage_root()

class Settings(BaseSettings):
    app_name: str = "Anima Studio 3D"
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_redirect_uri: str = "https://animacao2d.vps11710.panel.icontainer.work/api/youtube/callback"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
app = FastAPI(title=settings.app_name, version="0.2.2")
from backend.app.comfy_worker import router as comfy_router
from backend.app.opentoonz_worker import router as opentoonz_router
app.include_router(comfy_router)
app.include_router(opentoonz_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


NATIVE_LIBRARY_BOOTSTRAP: dict[str, Any] = {
    "ok": False,
    "installed": False,
    "missing": [],
    "error": "Aguardando verificação de dependências nativas.",
}


@app.on_event("startup")
def repair_blender_native_dependencies_before_serving():
    """
    Ensure Blender's shared libraries are ready before the API accepts jobs.
    This must be synchronous: a background repair allowed /api/diagnostics and
    render requests to race the bpy import and report a false missing engine.
    """
    global NATIVE_LIBRARY_BOOTSTRAP
    try:
        NATIVE_LIBRARY_BOOTSTRAP = ensure_blender_native_libraries()
        reset_bpy_import_state()
        # Force a real import after the OS packages and linker cache are ready.
        bpy_ready = has_bpy_module()
        NATIVE_LIBRARY_BOOTSTRAP = {
            **NATIVE_LIBRARY_BOOTSTRAP,
            "bpy_available": bpy_ready,
        }
        if not bpy_ready:
            from backend.app.runtime import inspect_bpy_module
            NATIVE_LIBRARY_BOOTSTRAP["bpy_import_error"] = inspect_bpy_module()["error"]
        print("ANIMA_NATIVE_LIBRARIES:", NATIVE_LIBRARY_BOOTSTRAP, flush=True)
    except Exception as exc:
        NATIVE_LIBRARY_BOOTSTRAP = {
            "ok": False,
            "installed": False,
            "missing": native_library_status().get("missing", []),
            "error": f"{type(exc).__name__}: {exc}",
        }
        print("ANIMA_NATIVE_LIBRARIES_BOOTSTRAP_ERROR:", NATIVE_LIBRARY_BOOTSTRAP, flush=True)

class GenerateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    story: str = Field(default="Aventura educativa dos Pequenos Guardiões.", min_length=10, max_length=12000)
    formats: list[str] = Field(default_factory=lambda: ["16:9", "9:16"])
    episode: str = "planet-journey"
    planet: str = "Aurora-7"

class StoryRequest(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["16:9", "9:16"])
    topic: str = Field(default="aventura surpresa", max_length=120)

class RenderRequest(BaseModel):
    formats: list[str] | None = None

JOBS: dict[str, dict[str, Any]] = {}
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_TOKEN_FILE = STORAGE / "youtube-token.json"
OAUTH_STATES: set[str] = set()

class PublishRequest(BaseModel):
    format: str
    scheduled_at: str | None = None
    privacy_status: str = "public"
    description: str = ""

LOCK = threading.Lock()

# Authenticated pull-based Windows render workers. The worker initiates every
# connection; no inbound port is required on the Windows machine.
WORKER_TASKS: dict[str, dict[str, Any]] = {}
WORKER_QUEUE: queue.Queue = queue.Queue()
WORKER_LAST_SEEN: dict[str, float] = {}

def _require_worker_token(authorization: str | None):
    expected = os.getenv("ANIMA_WORKER_TOKEN", "").strip()
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(503, "Render worker remoto desativado: configure ANIMA_WORKER_TOKEN na VPS.")
    if not supplied or not __import__("hmac").compare_digest(supplied, expected):
        raise HTTPException(401, "Token do trabalhador inválido.")

@app.get("/api/worker/status")
def worker_status(authorization: str | None = Header(default=None)):
    _require_worker_token(authorization)
    now = time.time()
    connected = [name for name, seen in WORKER_LAST_SEEN.items() if now - seen < 75]
    return {"enabled": True, "connected": bool(connected), "workers": connected,
            "queued": WORKER_QUEUE.qsize(),
            "active": sum(1 for item in WORKER_TASKS.values() if item.get("status") == "running")}

@app.post("/api/worker/tasks", status_code=202)
async def create_worker_task(request: Request, authorization: str | None = Header(default=None)):
    _require_worker_token(authorization)
    payload = await request.json()
    config = payload.get("config")
    if not isinstance(config, dict) or int(config.get("total_frames", 0)) < 1:
        raise HTTPException(400, "Configuração de renderização inválida.")
    task_id = uuid.uuid4().hex
    task = {"id": task_id, "status": "queued", "config": config,
            "created_at": datetime.now(timezone.utc).isoformat()}
    WORKER_TASKS[task_id] = task
    WORKER_QUEUE.put(task_id)
    return {"task_id": task_id, "status": "queued"}

@app.post("/api/worker/heartbeat")
def worker_heartbeat(worker_id: str = "windows-rx580",
                     authorization: str | None = Header(default=None)):
    _require_worker_token(authorization)
    WORKER_LAST_SEEN[worker_id] = time.time()
    return {"ok": True, "worker_id": worker_id}

@app.get("/api/worker/next")
def claim_worker_task(worker_id: str = "windows-rx580",
                      authorization: str | None = Header(default=None)):
    _require_worker_token(authorization)
    WORKER_LAST_SEEN[worker_id] = time.time()
    try:
        task_id = WORKER_QUEUE.get(timeout=20)
    except queue.Empty:
        return {"task": None, "heartbeat": True}
    task = WORKER_TASKS.get(task_id)
    if not task or task.get("status") != "queued":
        return {"task": None, "heartbeat": True}
    task["status"] = "running"
    task["worker_id"] = worker_id
    task["started_at"] = datetime.now(timezone.utc).isoformat()
    return {"task": {"id": task_id, "config": task["config"]}}

@app.post("/api/worker/tasks/{task_id}/chunks/{chunk_index}", status_code=202)
async def upload_worker_chunk(task_id: str, chunk_index: int, request: Request,
                              authorization: str | None = Header(default=None)):
    """Receive one bounded ZIP part; small requests avoid proxy limits on large uploads."""
    _require_worker_token(authorization)
    task = WORKER_TASKS.get(task_id)
    if not task or task.get("status") != "running":
        raise HTTPException(404, "Trabalho remoto não encontrado ou não está ativo.")
    if chunk_index < 0 or chunk_index > 10000:
        raise HTTPException(400, "Índice de bloco inválido.")
    chunk = await request.body()
    if not chunk or len(chunk) > 12 * 1024 * 1024:
        raise HTTPException(400, "Bloco vazio ou maior que 12 MB.")
    folder = STORAGE / "remote-worker" / task_id / "chunks"
    folder.mkdir(parents=True, exist_ok=True)
    chunk_path = folder / f"{chunk_index:06d}.part"
    temp_path = chunk_path.with_suffix(".tmp")
    temp_path.write_bytes(chunk)
    temp_path.replace(chunk_path)
    task["upload_chunks"] = max(int(task.get("upload_chunks", 0)), chunk_index + 1)
    return {"status": "chunk_received", "chunk_index": chunk_index, "bytes": len(chunk)}


@app.post("/api/worker/tasks/{task_id}/finalize", status_code=200)
def finalize_worker_upload(task_id: str, payload: dict,
                           authorization: str | None = Header(default=None)):
    """Assemble uploaded parts atomically and mark the render task complete."""
    _require_worker_token(authorization)
    task = WORKER_TASKS.get(task_id)
    if not task or task.get("status") != "running":
        raise HTTPException(404, "Trabalho remoto não encontrado ou não está ativo.")
    total_chunks = int(payload.get("total_chunks", 0))
    if total_chunks < 1 or total_chunks > 10001:
        raise HTTPException(400, "Quantidade de blocos inválida.")
    folder = STORAGE / "remote-worker" / task_id
    chunks_dir = folder / "chunks"
    result_path = folder / f"{task_id}.zip"
    if not chunks_dir.is_dir():
        raise HTTPException(400, "Nenhum bloco recebido.")
    temp_path = folder / f"{task_id}.zip.part"
    try:
        with temp_path.open("wb") as output:
            for index in range(total_chunks):
                part = chunks_dir / f"{index:06d}.part"
                if not part.is_file():
                    raise HTTPException(400, f"Bloco {index} ausente.")
                with part.open("rb") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        if temp_path.stat().st_size == 0:
            raise HTTPException(400, "Pacote de quadros vazio.")
        temp_path.replace(result_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    task.update(status="done", result_path=str(result_path),
                completed_at=datetime.now(timezone.utc).isoformat(),
                uploaded_bytes=result_path.stat().st_size)
    shutil.rmtree(chunks_dir, ignore_errors=True)
    return {"status": "done", "bytes": result_path.stat().st_size,
            "chunks": total_chunks}


@app.post("/api/worker/tasks/{task_id}/complete")
async def complete_worker_task(task_id: str, request: Request,
                               authorization: str | None = Header(default=None)):
    """Backward-compatible endpoint for older workers; new workers use chunk upload."""
    _require_worker_token(authorization)
    task = WORKER_TASKS.get(task_id)
    if not task or task.get("status") != "running":
        raise HTTPException(404, "Trabalho remoto não encontrado ou não está ativo.")
    archive = await request.body()
    if not archive or len(archive) > 2_000_000_000:
        raise HTTPException(400, "Pacote de quadros vazio ou maior que 2 GB.")
    folder = STORAGE / "remote-worker"
    folder.mkdir(parents=True, exist_ok=True)
    result_path = folder / f"{task_id}.zip"
    result_path.write_bytes(archive)
    task.update(status="done", result_path=str(result_path),
                completed_at=datetime.now(timezone.utc).isoformat())
    return {"status": "done", "bytes": len(archive)}

@app.post("/api/worker/tasks/{task_id}/fail")
async def fail_worker_task(task_id: str, request: Request,
                           authorization: str | None = Header(default=None)):
    _require_worker_token(authorization)
    task = WORKER_TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Trabalho remoto não encontrado.")
    payload = await request.json()
    task.update(status="failed", error=str(payload.get("error", "Falha no worker"))[:2000])
    return {"status": "failed"}

@app.get("/api/worker/tasks/{task_id}")
def worker_task_status(task_id: str, authorization: str | None = Header(default=None)):
    _require_worker_token(authorization)
    task = WORKER_TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Trabalho remoto não encontrado.")
    return {"status": task.get("status"), "result_path": task.get("result_path"),
            "error": task.get("error")}

SETTINGS_FILE = STORAGE / "studio-settings.json"
DEFAULT_STUDIO_SETTINGS = {"auto_generate_formats": ["16:9", "9:16"], "require_review_before_publish": True, "auto_publish_enabled": False, "auto_production_enabled": False, "production_days": ["Tuesday", "Thursday", "Saturday"], "production_time": "10:00", "publish_days": ["Tuesday", "Thursday", "Saturday"], "publish_time": "18:00"}

def _studio_settings():
    if not SETTINGS_FILE.exists():
        return DEFAULT_STUDIO_SETTINGS.copy()
    try:
        return {**DEFAULT_STUDIO_SETTINGS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return DEFAULT_STUDIO_SETTINGS.copy()

@app.post("/api/2d/preview")
def create_2d_preview(planet: str = "AURORA-7"):
    """Render an isolated 8-second 2D cartoon proof-of-concept without Blender."""
    safe_planet = "".join(ch for ch in planet if ch.isalnum() or ch in " -_")[:28].strip() or "AURORA-7"
    filename = f"2d-preview-{uuid.uuid4().hex[:10]}.mp4"
    output = STORAGE / filename
    try:
        result = render_2d_preview(output, safe_planet.upper())
    except Exception as exc:
        raise HTTPException(500, f"Falha na prévia 2D: {type(exc).__name__}: {exc}")
    return {"status": "done", "engine": result["engine"], "seconds": result["seconds"],
            "frames": result["frames"], "planet": result["planet"],
            "video_url": f"/api/2d/preview/{filename}"}


@app.get("/api/2d/preview/{filename}")
def get_2d_preview(filename: str):
    if not filename.startswith("2d-preview-") or not filename.endswith(".mp4") or Path(filename).name != filename:
        raise HTTPException(400, "Nome de arquivo inválido.")
    target = STORAGE / filename
    if not target.is_file():
        raise HTTPException(404, "Prévia 2D não encontrada.")
    return FileResponse(target, media_type="video/mp4", filename=filename)


@app.get("/api/health")
def health():
    blender_runtime = find_blender_runtime()
    blender_script = Path(__file__).with_name("blender_scene.py")
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.3.0",
        "runtime": "docker-3d" if blender_runtime else "python-no-3d-engine",
        "container_runtime": "docker" if Path("/.dockerenv").exists() else "unknown",
        "python_version": sys.version.split()[0],
        "port": int(os.getenv("PORT", "5000")),
        "ffmpeg": _has("ffmpeg"),
        "tts": _has("tts"),
        "storage_writable": os.access(STORAGE, os.W_OK),
        "blender": bool(blender_runtime),
        "blender_backend": blender_runtime["backend"] if blender_runtime else None,
        "blender_path": blender_runtime["executable"] if blender_runtime else None,
        "bpy_module_available": has_bpy_module(),
        "blender_scene_file": blender_script.is_file(),
        "render_engine": "2d",
    }


@app.get("/api/health/3d")
def health_3d():
    """Readiness probe: both Blender runtime and the 3D scene must be present."""
    blender_runtime = find_blender_runtime()
    blender_script = Path(__file__).with_name("blender_scene.py")
    if not blender_runtime:
        raise HTTPException(
            503,
            "Motor 3D indisponível: instale Blender ou bpy==5.2.3 para Python 3.13."
        )
    if not blender_script.is_file():
        raise HTTPException(503, f"Arquivo ausente: {blender_script}")
    return {
        "status": "ready",
        "engine": "blender-3d-only",
        "backend": blender_runtime["backend"],
        "blender_path": blender_runtime["executable"],
        "scene_script": str(blender_script.resolve()),
    }


@app.get("/api/diagnostics")
def diagnostics():
    """Non-secret runtime diagnostics for Blender 3D binary/module and media assets."""
    blender_runtime = find_blender_runtime()
    bpy_info = inspect_bpy_module()
    blender_script = Path(__file__).with_name("blender_scene.py")
    blender_path = find_blender_binary()
    return {
        "ok": bool(blender_runtime and blender_script.is_file()),
        "container_runtime": "docker" if Path("/.dockerenv").exists() else "unknown",
        "python_version": sys.version.split()[0],
        "working_directory": str(Path.cwd()),
        "app_file": str(Path(__file__).resolve()),
        "blender_backend": blender_runtime["backend"] if blender_runtime else None,
        "blender_bin_setting": os.getenv("BLENDER_BIN") or "(not set)",
        "blender_path": blender_path,
        "blender_executable": bool(blender_path and os.access(blender_path, os.X_OK)),
        "bpy_module_available": bpy_info["available"],
        "bpy_version": bpy_info["version"],
        "bpy_import_error": bpy_info["error"],
        "native_libraries": native_library_status(),
        "native_library_bootstrap": NATIVE_LIBRARY_BOOTSTRAP,
        "blender_scene_path": str(blender_script.resolve()),
        "blender_scene_exists": blender_script.is_file(),
        "render_engine": "2d-cartoon-default",
        "ffmpeg_available": _has("ffmpeg"),
        "tts_available": _has("tts"),
        "storage_path": str(STORAGE.resolve()),
        "storage_writable": os.access(STORAGE, os.W_OK),
    }

@app.get("/api/config")
def config():
    return {
        "formats": [
            {"id": "16:9", "width": 1920, "height": 1080, "label": "YouTube horizontal"},
            {"id": "9:16", "width": 1080, "height": 1920, "label": "YouTube Shorts"},
        ],
        "youtube_oauth_configured": bool(settings.youtube_client_id and settings.youtube_client_secret),
        "generation_enabled": _has("ffmpeg") and _has("tts"),
        "media": {"ffmpeg": _has("ffmpeg"), "tts": _has("tts"), "blender_3d": blender_available()},
        "engine": "Anima Studio — Cartoon 2D vetorial",
    }

@app.post("/api/stories/generate", status_code=201)
def generate_story(payload: StoryRequest):
    allowed = {"16:9", "9:16"}
    if not payload.formats or any(x not in allowed for x in payload.formats):
        raise HTTPException(400, "Selecione 16:9 e/ou 9:16.")
    existing = list_jobs()["jobs"]
    planet_jobs = [j for j in existing if j.get("episode") == "planet-journey"]
    used_planets = {j.get("planet") for j in planet_jobs if j.get("planet")}
    plan = build_episode_plan(len(planet_jobs), used_planets)
    if payload.topic and payload.topic.strip().lower() not in {"aventura surpresa", "surpresa", "livre"}:
        topic = payload.topic.strip()
        topic_text = f" Nesta missão, os amigos também praticam {topic}: cada decisão é uma oportunidade de demonstrar esse valor com atitudes concretas e respeitosas."
        plan["topic"] = topic
        plan["synopsis"] += " Tema especial: " + topic + "."
        plan["long_script"] += topic_text
        plan["story"] = plan["long_script"] + " " + plan.get("dialogue_script", "")
        plan.setdefault("audio_segments_long", []).append({"speaker": "Narrador", "text": topic_text.strip()})
        short_extra = f" O tema especial desta aventura é {topic}; procure uma maneira gentil de praticá-lo hoje."
        plan["short_script"] += short_extra
        plan.setdefault("audio_segments_short", []).append({"speaker": "Narrador", "text": short_extra.strip()})
        plan["word_count_long"] = sum(len(item.get("text", "").split()) for item in plan["audio_segments_long"])
        plan["word_count_short"] = sum(len(item.get("text", "").split()) for item in plan["audio_segments_short"])
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "title": plan["title"], "status": "story_ready", "stage": "story_written",
        "progress": 5, "message": "História original criada. Revise o roteiro antes de renderizar.",
        "formats": payload.formats, "outputs": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "story_review", "publication_status": "not_ready",
        "story": plan["long_script"], "short_story": plan["short_script"],
        "story_plan": plan, "episode": "planet-journey", "planet": plan["planet"],
        "value": plan["value"], "synopsis": plan["synopsis"],
        "duration_targets": plan["duration_targets"], "topic": payload.topic,
    }
    with LOCK:
        JOBS[job_id] = job
        _save(job_id, job)
    return {"job_id": job_id, "status": "story_ready", "story": plan, "message": "Roteiro criado antes da animação."}

@app.post("/api/generate", status_code=201)
def generate(payload: GenerateRequest):
    # Compatibility endpoint: create a story draft first; never render immediately.
    result = generate_story(StoryRequest(formats=payload.formats, topic=payload.story[:120]))
    job_id = result["job_id"]
    if payload.title and payload.title.strip():
        plan = result["story"]
        plan["title"] = payload.title.strip()
        _update(job_id, title=payload.title.strip(), story_plan=plan)
        result["story"] = plan
    return result

@app.get("/api/jobs/{job_id}/story")
def get_story(job_id: str):
    job = _get_job(job_id)
    if not job.get("story_plan"):
        raise HTTPException(404, "Este episódio não possui roteiro estruturado.")
    return {"id": job_id, "title": job["title"], "planet": job.get("planet"),
            "synopsis": job.get("synopsis"), "value": job.get("value"),
            "story": job["story_plan"], "status": job.get("status")}

@app.post("/api/jobs/{job_id}/render", status_code=202)
def render_story(job_id: str, payload: RenderRequest):
    job = _get_job(job_id)
    if not job.get("story_plan"):
        raise HTTPException(409, "Crie o roteiro antes da animação.")
    if job.get("status") not in {"story_ready", "failed"}:
        raise HTTPException(409, "O episódio já está em renderização ou foi finalizado.")
    formats = payload.formats or job.get("formats", ["16:9", "9:16"])
    if not formats or any(x not in {"16:9", "9:16"} for x in formats):
        raise HTTPException(400, "Formatos inválidos.")
    if not _has("ffmpeg") or not _has("tts"):
        raise HTTPException(503, "Motor de mídia incompleto. É necessário FFmpeg e voz (espeak-ng ou edge-tts).")
    # O motor 3D remoto executa Blender diretamente no Windows/RX580.
    # Nesse modo, a VPS não precisa ter Blender/bpy instalado localmente.
    selected_engine = "2d"
    if selected_engine not in {"2d", "3d"}:
        raise HTTPException(503, "ANIMA_RENDER_ENGINE inválido. Configure 2d ou 3d.")
    if selected_engine == "3d":
        blender_script = Path(__file__).with_name("blender_scene.py")
        if not blender_script.is_file():
            raise HTTPException(503, "Arquivo da cena Blender não encontrado na VPS.")
        remote_enabled = True  # Episódios usam exclusivamente o worker Windows/RX580.
        if remote_enabled:
            if not os.getenv("ANIMA_WORKER_TOKEN", "").strip():
                raise HTTPException(503, "Render RX 580 ativado, mas ANIMA_WORKER_TOKEN não foi configurado.")
            now = time.time()
            connected_workers = [name for name, seen in WORKER_LAST_SEEN.items() if now - seen < 75]
            if not connected_workers:
                raise HTTPException(503, "Computador RX 580 desconectado. Abra iniciar-worker.ps1 no Windows e tente novamente.")
        elif not find_blender_runtime():
            raise HTTPException(503, "Blender local indisponível e worker remoto desativado. Ative ANIMA_REMOTE_WORKER_ENABLED=true para usar a RX 580.")
    _update(job_id, status="queued", stage="render_queued", progress=8,
            message="Roteiro aprovado. Preparando cenas e narração.", formats=formats,
            review_status="pending_review", outputs={}, error=None)
    render_payload = GenerateRequest(title=job["title"], story=job["story"],
                                     formats=formats, episode="planet-journey",
                                     planet=job["planet"])
    threading.Thread(target=_run_job, args=(job_id, render_payload), daemon=True).start()
    return {"job_id": job_id, "status": "queued", "message": "Renderização iniciada após a criação do roteiro."}



def _youtube_credentials():
    if not YOUTUBE_TOKEN_FILE.exists():
        raise HTTPException(409, "Conecte o canal do YouTube antes de publicar.")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    credentials = Credentials.from_authorized_user_file(str(YOUTUBE_TOKEN_FILE), YOUTUBE_SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        YOUTUBE_TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    if not credentials.valid:
        raise HTTPException(401, "Autorização do YouTube expirada. Conecte o canal novamente.")
    return credentials

@app.get("/api/youtube/status")
def youtube_status():
    configured = bool(settings.youtube_client_id and settings.youtube_client_secret)
    connected = YOUTUBE_TOKEN_FILE.exists()
    return {"configured": configured, "connected": connected, "publishing_enabled": connected}

@app.get("/api/youtube/connect")
def youtube_connect():
    if not settings.youtube_client_id or not settings.youtube_client_secret:
        raise HTTPException(409, "Configure YOUTUBE_CLIENT_ID e YOUTUBE_CLIENT_SECRET no ambiente do servidor.")
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {"web": {"client_id": settings.youtube_client_id, "client_secret": settings.youtube_client_secret,
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token",
                 "redirect_uris": [settings.youtube_redirect_uri]}},
        scopes=YOUTUBE_SCOPES,
    )
    flow.redirect_uri = settings.youtube_redirect_uri
    url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    OAUTH_STATES.add(state)
    return RedirectResponse(url)

@app.get("/api/youtube/callback")
def youtube_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return HTMLResponse("<h2>Conexão com YouTube não autorizada.</h2><p>Você pode fechar esta janela.</p>", status_code=400)
    if not state or state not in OAUTH_STATES:
        raise HTTPException(400, "Estado OAuth inválido. Inicie a conexão novamente.")
    OAUTH_STATES.discard(state)
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {"web": {"client_id": settings.youtube_client_id, "client_secret": settings.youtube_client_secret,
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token",
                 "redirect_uris": [settings.youtube_redirect_uri]}},
        scopes=YOUTUBE_SCOPES, state=state,
    )
    flow.redirect_uri = settings.youtube_redirect_uri
    flow.fetch_token(code=code)
    YOUTUBE_TOKEN_FILE.write_text(flow.credentials.to_json(), encoding="utf-8")
    return HTMLResponse("<h2>Canal conectado com sucesso!</h2><p>Volte ao Anima Studio 3D. Esta janela pode ser fechada.</p>")

@app.post("/api/jobs/{job_id}/publish")
def publish_job(job_id: str, payload: PublishRequest):
    job = _get_job(job_id)
    if job.get("status") != "done":
        raise HTTPException(409, "O episódio precisa estar renderizado antes do envio.")
    if job.get("review_status") != "approved":
        raise HTTPException(409, "Aprove o episódio na revisão editorial antes de publicar.")
    if payload.format not in job.get("outputs", {}):
        raise HTTPException(404, "Formato de vídeo não encontrado.")
    if payload.privacy_status not in {"public", "unlisted", "private"}:
        raise HTTPException(400, "Privacidade inválida.")
    credentials = _youtube_credentials()
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    video_path = Path(job["outputs"][payload.format])
    if not video_path.exists():
        raise HTTPException(404, "Arquivo de vídeo não encontrado.")
    status = {"privacyStatus": payload.privacy_status, "selfDeclaredMadeForKids": True}
    if payload.scheduled_at:
        try:
            scheduled = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
            if scheduled.tzinfo is None:
                raise ValueError("Informe o fuso horário.")
            if scheduled <= datetime.now(timezone.utc):
                raise ValueError("A data precisa estar no futuro.")
            status = {"privacyStatus": "private", "publishAt": scheduled.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), "selfDeclaredMadeForKids": True}
        except ValueError as exc:
            raise HTTPException(400, f"Agendamento inválido: {exc}")
    title = job["title"][:85] + (" #Shorts" if payload.format == "9:16" else "")
    description = (payload.description or "Uma aventura dos Pequenos Guardiões — A Liga do Bem!\\n\\nUma história que ensina amizade, honestidade, respeito e responsabilidade.").strip()
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        request = youtube.videos().insert(
            part="snippet,status",
            body={"snippet": {"title": title, "description": description, "categoryId": "22", "defaultLanguage": "pt-BR"},
                  "status": status},
            media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True),
        )
        response = request.execute()
    except Exception as exc:
        raise HTTPException(502, f"Falha no envio ao YouTube: {exc}")
    video_id = response.get("id", "")
    publication = {"video_id": video_id, "url": "https://www.youtube.com/watch?v=" + video_id,
                   "format": payload.format, "status": "scheduled" if payload.scheduled_at else payload.privacy_status,
                   "scheduled_at": payload.scheduled_at, "uploaded_at": datetime.now(timezone.utc).isoformat()}
    publications = list(job.get("publications", []))
    publications.append(publication)
    _update(job_id, publications=publications, publication_status=publication["status"])
    return publication

def _create_scheduled_episode():
    cfg = _studio_settings()
    if not cfg.get("auto_production_enabled"):
        return
    all_jobs = list_jobs()["jobs"]
    planet_jobs = [j for j in all_jobs if j.get("episode") == "planet-journey"]
    used_planets = {j.get("planet") for j in planet_jobs if j.get("planet")}
    plan = build_episode_plan(len(planet_jobs), used_planets)
    formats = cfg.get("auto_generate_formats", ["16:9", "9:16"])
    payload = GenerateRequest(title=plan["title"], story=plan["long_script"],
                              formats=formats, episode="planet-journey", planet=plan["planet"])
    job_id = uuid.uuid4().hex[:12]
    # The complete story is generated and persisted before the render worker starts.
    job = {
        "id": job_id, "title": plan["title"], "status": "queued", "stage": "story_written",
        "progress": 5, "message": "Roteiro original concluído; preparando a animação automática.",
        "formats": formats, "outputs": {}, "created_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "pending_review", "publication_status": "awaiting_review",
        "story": plan["long_script"], "short_story": plan["short_script"],
        "story_plan": plan, "episode": "planet-journey", "planet": plan["planet"],
        "value": plan["value"], "synopsis": plan["synopsis"],
        "duration_targets": plan["duration_targets"],
    }
    with LOCK:
        JOBS[job_id] = job
        _save(job_id, job)
    threading.Thread(target=_run_job, args=(job_id, payload), daemon=True).start()

scheduler = None
def _refresh_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    cfg = _studio_settings()
    if cfg.get("auto_production_enabled") and cfg.get("production_days"):
        day_map={"Monday":"mon","Tuesday":"tue","Wednesday":"wed","Thursday":"thu","Friday":"fri","Saturday":"sat","Sunday":"sun"}
        hour,minute=cfg.get("production_time","10:00").split(":")
        trigger=CronTrigger(day_of_week=",".join(day_map[x] for x in cfg["production_days"]),hour=int(hour),minute=int(minute),timezone="America/Sao_Paulo")
        scheduler.add_job(_create_scheduled_episode,trigger,id="weekly_episode_production",replace_existing=True,max_instances=1,coalesce=True)
    scheduler.start()

def _recover_interrupted_jobs():
    """Jobs marked active before a process restart cannot still have a live worker."""
    for folder in STORAGE.iterdir():
        meta = folder / "job.json"
        if not folder.is_dir() or not meta.exists():
            continue
        try:
            job = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if job.get("status") in {"queued", "processing"}:
            job.update({
                "status": "failed",
                "stage": "interrupted",
                "error": "O processo foi reiniciado antes de concluir a renderização.",
                "message": "Renderização interrompida por reinicialização. O roteiro foi preservado; abra o episódio e tente gerar novamente.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            meta.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        JOBS[folder.name] = job


@app.on_event("startup")
def start_studio_scheduler():
    _recover_interrupted_jobs()
    _refresh_scheduler()

@app.on_event("shutdown")
def stop_studio_scheduler():
    if scheduler:
        scheduler.shutdown(wait=False)

@app.get("/api/dashboard")
def dashboard():
    jobs = list_jobs()["jobs"]
    total = len(jobs)
    completed = [j for j in jobs if j.get("status") == "done"]
    failed = [j for j in jobs if j.get("status") == "failed"]
    active = [j for j in jobs if j.get("status") in {"queued", "processing"}]
    approved = [j for j in jobs if j.get("review_status") == "approved"]
    return {
        "metrics": {
            "episodes_total": total, "episodes_ready": len(completed),
            "episodes_processing": len(active), "episodes_failed": len(failed),
            "awaiting_review": sum(1 for j in completed if j.get("review_status") != "approved"),
            "approved": len(approved),
            "posts_published": sum(len(j.get("publications", [])) for j in jobs),
        },
        "recent_episodes": jobs[:8],
        "settings": _studio_settings(),
        "youtube": {"configured": bool(settings.youtube_client_id and settings.youtube_client_secret), "connected": YOUTUBE_TOKEN_FILE.exists(), "publishing_enabled": YOUTUBE_TOKEN_FILE.exists()},
    }

@app.get("/api/studio-settings")
def get_studio_settings():
    return _studio_settings()

@app.put("/api/studio-settings")
def update_studio_settings(payload: dict[str, Any]):
    allowed = {"auto_generate_formats", "require_review_before_publish", "auto_publish_enabled", "publish_days", "publish_time"}
    allowed |= {"auto_production_enabled", "production_days", "production_time"}
    if set(payload) - allowed:
        raise HTTPException(400, "Configuração desconhecida.")
    current = _studio_settings()
    current.update(payload)
    if current["auto_publish_enabled"]:
        current["auto_publish_enabled"] = False
        raise HTTPException(409, "A publicação automática será liberada após a integração OAuth segura do canal YouTube.")
    if not isinstance(current["auto_generate_formats"], list) or not current["auto_generate_formats"] or any(x not in {"16:9", "9:16"} for x in current["auto_generate_formats"]):
        raise HTTPException(400, "Formatos automáticos inválidos.")
    valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    for field in ("production_days", "publish_days"):
        if not isinstance(current[field], list) or any(day not in valid_days for day in current[field]):
            raise HTTPException(400, f"Dias inválidos em {field}.")
    for field in ("production_time", "publish_time"):
        try:
            datetime.strptime(current[field], "%H:%M")
        except (TypeError, ValueError):
            raise HTTPException(400, f"Horário inválido em {field}.")
    SETTINGS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    _refresh_scheduler()
    return current

@app.post("/api/jobs/{job_id}/review")
def review_job(job_id: str, payload: dict[str, str]):
    job = _get_job(job_id)
    decision = payload.get("decision")
    if decision not in {"approved", "changes_requested"}:
        raise HTTPException(400, "Decisão deve ser approved ou changes_requested.")
    if job.get("status") != "done":
        raise HTTPException(409, "Só é possível revisar episódios finalizados.")
    _update(job_id, review_status=decision, reviewed_at=datetime.now(timezone.utc).isoformat())
    return _get_job(job_id)

@app.get("/api/jobs")
def list_jobs():
    # Recarrega jobs persistidos mesmo depois de reiniciar o container.
    for folder in STORAGE.iterdir():
        meta = folder / "job.json"
        if folder.is_dir() and meta.exists() and folder.name not in JOBS:
            try:
                JOBS[folder.name] = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    with LOCK:
        return {"jobs": sorted(JOBS.values(), key=lambda x: x["created_at"], reverse=True)}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = _get_job(job_id)
    return job

@app.get("/api/jobs/{job_id}/preview/{fmt}")
def job_preview(job_id: str, fmt: str):
    """Return the latest rendered frame for the live studio preview."""
    job = _get_job(job_id)
    if fmt not in {"16:9", "9:16"}:
        raise HTTPException(400, "Formato de prévia inválido.")
    preview = STORAGE / job_id / f"preview-{fmt.replace(':', 'x')}.jpg"
    if not preview.is_file():
        raise HTTPException(404, "Aguardando o primeiro quadro da animação.")
    return FileResponse(preview, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store, max-age=0"})


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
    if binary == "blender":
        return blender_available()
    if binary == "ffmpeg":
        if which("ffmpeg"):
            return True
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            return bool(get_ffmpeg_exe())
        except Exception:
            return False
    if binary in {"tts", "espeak-ng"}:
        if which("espeak-ng"):
            return True
        try:
            import importlib.util
            return importlib.util.find_spec("edge_tts") is not None
        except (ImportError, ValueError):
            return False
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
        total_formats = max(1, len(payload.formats))
        for index, fmt in enumerate(payload.formats):
            stage = "rendering_long" if fmt == "16:9" else "rendering_short"
            _update(job_id, status="processing", stage=stage,
                    progress=int(index * 100 / total_formats),
                    message=f"Preparando versão {fmt} com roteiro e falas próprias…")
            output = STORAGE / job_id / f"episode-{fmt.replace(':','x')}.mp4"
            current = _get_job(job_id)

            def report(local_progress: int, message: str):
                overall = min(99, int((index * 100 + max(0, min(100, local_progress))) / total_formats))
                _update(job_id, status="processing", stage=stage, progress=overall, message=message)

            metadata = render_episode(
                payload.title, payload.story, fmt, output, STORAGE / job_id,
                planet_name=payload.planet, story_plan=current.get("story_plan"),
                progress_callback=report,
            )
            current = _get_job(job_id)
            outputs = dict(current.get("outputs", {}))
            outputs[fmt] = str(output)
            durations = dict(current.get("rendered_durations", {}))
            durations[fmt] = metadata.get("duration_seconds")
            _update(job_id, outputs=outputs, rendered_durations=durations,
                    progress=int((index + 1) * 100 / total_formats),
                    message=f"Versão {fmt} pronta ({metadata.get('duration_seconds', 0):.0f} segundos).")
        _update(job_id, status="done", stage="ready_for_review", progress=100,
                message="Episódio completo: roteiro, vozes, animação e narrações renderizados.")
    except Exception as exc:
        _update(job_id, status="failed", stage="render_error", error=str(exc),
                message=f"Falha na renderização: {exc}")

if WEB.exists():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")


@app.get("/api/engines/catalog")
def animation_engines_catalog():
    """List independent render engines and supporting production modules."""
    from backend.app.engines.registry import engine_catalog
    now = time.time()
    connected = any(now - seen < 75 for seen in WORKER_LAST_SEEN.values())
    return engine_catalog(worker_connected=connected)


@app.get("/api/engines/status")
def animation_engines_status():
    """Expose independent engine readiness without starting a render job."""
    from backend.app.engines.orchestrator import EpisodeOrchestrator
    return EpisodeOrchestrator().health()


@app.get("/api/characters")
def animation_character_library():
    """Return the canonical identity and rig manifest for Luna, Tomi and Pipo."""
    from backend.app.character_profiles import CHARACTER_PROFILES
    return {"characters": CHARACTER_PROFILES}
