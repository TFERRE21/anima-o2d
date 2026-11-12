"""Real cloud AI animation test using fal.ai FLUX + Kling.

This is an explicit online-AI path; it never silently falls back to the procedural renderer.
Set FAL_KEY on the server. Generated files are stored in canonical persistent storage.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.storage import storage_root

router = APIRouter(prefix="/api/ai-video", tags=["AI Video"])
JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()

IMAGE_MODEL = "fal-ai/flux-pro/v1.1"
VIDEO_MODEL = "fal-ai/kling-video/v3/pro/image-to-video"


class AITestRequest(BaseModel):
    topic: str = Field(default="Luna, Tomi e Pipo ajudam um amigo em uma aventura na floresta encantada", min_length=10, max_length=1200)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9)$")
    duration: int = Field(default=5, ge=5, le=15)


def _request(url: str, method: str = "GET", body: dict | None = None, timeout: int = 90):
    key = os.getenv("FAL_KEY", "").strip()
    if not key:
        raise RuntimeError("FAL_KEY não configurada no servidor. Configure a chave fal.ai no ambiente do Anima Studio.")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1200]
        raise RuntimeError(f"fal.ai HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Falha na comunicação fal.ai: {type(exc).__name__}: {exc}") from exc


def _queue(model: str, payload: dict, update):
    base = f"https://queue.fal.run/{model}"
    submitted = _request(base, "POST", payload)
    request_id = submitted.get("request_id")
    status_url = submitted.get("status_url") or f"{base}/requests/{request_id}/status"
    response_url = submitted.get("response_url") or f"{base}/requests/{request_id}"
    if not request_id:
        raise RuntimeError(f"fal.ai não retornou request_id: {submitted}")
    update(provider_request_id=request_id)
    deadline = time.time() + 900
    while time.time() < deadline:
        status = _request(status_url)
        state = status.get("status", "")
        if state == "COMPLETED":
            return _request(response_url)
        if state in {"FAILED", "CANCELLED"}:
            raise RuntimeError(f"fal.ai {model} terminou com status {state}: {status}")
        time.sleep(4)
    raise RuntimeError(f"Tempo limite aguardando o modelo {model}.")


def _download(url: str, destination: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "AnimaStudio/1.0"})
    with urllib.request.urlopen(req, timeout=180) as response, destination.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    if not destination.exists() or destination.stat().st_size < 100_000:
        raise RuntimeError("O arquivo de vídeo recebido está vazio ou incompleto.")


def _run(job_id: str, payload: AITestRequest):
    jobdir = storage_root() / "ai-video" / job_id
    jobdir.mkdir(parents=True, exist_ok=True)

    def update(**fields):
        with _LOCK:
            JOBS[job_id].update(fields, updated_at=time.time())

    try:
        update(status="running", progress=5, stage="image", message="Gerando quadro cinematográfico com FLUX.")
        ratio = "portrait_16_9" if payload.aspect_ratio == "9:16" else "landscape_16_9"
        image_prompt = (
            "Premium high-end 3D animated family film still, polished stylized feature animation, "
            "beautiful expressive child-friendly characters, cinematic global illumination, detailed lush environment, "
            "rich color grading, professional character design, clean composition, no text, no subtitles. "
            "Three recurring heroes: Luna, a cheerful little girl with long dark brown hair, pink headband and bright pink outfit; "
            "Tomi, a cheerful little boy with short tousled dark brown hair and bright blue outfit; "
            "Pipo, a small adorable brown floppy-eared puppy with a teal collar. "
            "Keep all three characters fully visible, consistent proportions, appealing expressive faces. "
            f"Scene: {payload.topic}"
        )
        image_result = _queue(IMAGE_MODEL, {
            "prompt": image_prompt, "image_size": ratio, "num_images": 1,
            "output_format": "png", "enable_safety_checker": True
        }, update)
        images = image_result.get("images") or []
        image_url = images[0].get("url") if images else None
        if not image_url:
            raise RuntimeError(f"FLUX não retornou imagem válida: {image_result}")
        update(progress=45, stage="video", message="Imagem pronta. Animando a cena com Kling 3.0.")
        video_prompt = (
            f"Animate this exact image as a polished 3D family animation. {payload.topic}. "
            "Preserve the exact identity, clothing, colors and proportions of Luna, Tomi and Pipo. "
            "Natural coordinated body motion, blinking, expressive gestures, subtle hair and clothing movement, "
            "gentle cinematic camera dolly, lively environment, smooth continuous motion. "
            "No morphing, no extra characters, no text, no logos."
        )
        video_result = _queue(VIDEO_MODEL, {
            "prompt": video_prompt,
            "start_image_url": image_url,
            "duration": str(payload.duration),
            "aspect_ratio": payload.aspect_ratio,
            "generate_audio": False,
            "enable_safety_checker": True,
            "negative_prompt": "character identity changes, deformed faces, extra limbs, flicker, blur, text, watermark"
        }, update)
        video_url = (video_result.get("video") or {}).get("url")
        if not video_url:
            raise RuntimeError(f"Kling não retornou MP4: {video_result}")
        image_path = jobdir / "keyframe.png"
        video_path = jobdir / "ai-scene.mp4"
        _download(image_url, image_path)
        _download(video_url, video_path)
        update(status="completed", progress=100, stage="completed",
               message="Cena de IA concluída. MP4 e quadro original salvos.",
               image=f"/api/ai-video/{job_id}/image",
               video=f"/api/ai-video/{job_id}/video",
               file_path=str(video_path), image_path=str(image_path),
               video_bytes=video_path.stat().st_size)
    except Exception as exc:
        update(status="failed", stage="failed", message=str(exc), error=str(exc))


@router.post("/test", status_code=202)
def start_test(payload: AITestRequest):
    if not os.getenv("FAL_KEY", "").strip():
        raise HTTPException(503, "Configure FAL_KEY no ambiente do servidor para ativar a geração online.")
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        JOBS[job_id] = {"id": job_id, "status": "queued", "progress": 0,
                        "stage": "queued", "message": "Teste de IA online na fila.",
                        "created_at": time.time()}
    threading.Thread(target=_run, args=(job_id, payload), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_test(job_id: str):
    with _LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Teste não encontrado nesta sessão.")
        return {k: v for k, v in job.items() if k not in {"file_path", "image_path"}}


@router.get("/{job_id}/video")
def get_video(job_id: str):
    from fastapi.responses import FileResponse
    job = JOBS.get(job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(404, "Vídeo ainda não está pronto.")
    path = Path(job["file_path"])
    if not path.is_file():
        raise HTTPException(404, "Arquivo MP4 não encontrado.")
    return FileResponse(path, media_type="video/mp4", filename=f"anima-ai-{job_id}.mp4")


@router.get("/{job_id}/image")
def get_image(job_id: str):
    from fastapi.responses import FileResponse
    job = JOBS.get(job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(404, "Imagem ainda não está pronta.")
    path = Path(job["image_path"])
    if not path.is_file():
        raise HTTPException(404, "Imagem não encontrada.")
    return FileResponse(path, media_type="image/png", filename=f"anima-ai-{job_id}.png")
