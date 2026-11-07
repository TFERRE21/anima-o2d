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
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
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
    youtube_redirect_uri: str = "http://localhost:8000/api/youtube/callback"
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
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_TOKEN_FILE = STORAGE / "youtube-token.json"
OAUTH_STATES: set[str] = set()

class PublishRequest(BaseModel):
    format: str
    scheduled_at: str | None = None
    privacy_status: str = "public"
    description: str = ""

LOCK = threading.Lock()
SETTINGS_FILE = STORAGE / "studio-settings.json"
DEFAULT_STUDIO_SETTINGS = {"auto_generate_formats": ["16:9", "9:16"], "require_review_before_publish": True, "auto_publish_enabled": False, "publish_days": ["Tuesday", "Thursday", "Saturday"], "publish_time": "18:00"}

def _studio_settings():
    if not SETTINGS_FILE.exists():
        return DEFAULT_STUDIO_SETTINGS.copy()
    try:
        return {**DEFAULT_STUDIO_SETTINGS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return DEFAULT_STUDIO_SETTINGS.copy()

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
        "review_status": "pending_review",
        "publication_status": "not_connected",
        "story": payload.story,
        "episode": payload.episode,
    }
    with LOCK:
        JOBS[job_id] = job
        _save(job_id, job)
    threading.Thread(target=_run_job, args=(job_id, payload), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}




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
    return HTMLResponse("<h2>Canal conectado com sucesso!</h2><p>Volte ao Anima 2D Studio. Esta janela pode ser fechada.</p>")

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
    if set(payload) - allowed:
        raise HTTPException(400, "Configuração desconhecida.")
    current = _studio_settings()
    current.update(payload)
    if current["auto_publish_enabled"]:
        current["auto_publish_enabled"] = False
        raise HTTPException(409, "A publicação automática será liberada após a integração OAuth segura do canal YouTube.")
    if not isinstance(current["auto_generate_formats"], list) or any(x not in {"16:9", "9:16"} for x in current["auto_generate_formats"]):
        raise HTTPException(400, "Formatos automáticos inválidos.")
    SETTINGS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
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
