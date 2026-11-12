"""Remote OpenToonz render queue for the Windows GPU agent.

The Windows agent pulls .tnz render jobs, renders PNG frames with tcomposer,
uploads a ZIP in bounded chunks, and this API assembles an MP4 with FFmpeg.
"""
from __future__ import annotations

import hmac
import os
import queue
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/opentoonz", tags=["OpenToonz"])
TASKS: dict[str, dict] = {}
TASK_QUEUE: queue.Queue[str] = queue.Queue()
WORKERS_SEEN: dict[str, float] = {}
CHUNK_LIMIT = 12 * 1024 * 1024
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024


def _storage() -> Path:
    root = Path(os.getenv("ANIMA_STORAGE", "/app/data/jobs")) / "opentoonz"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _auth(authorization: str | None) -> None:
    expected = (os.getenv("ANIMA_OPENTOONZ_TOKEN") or os.getenv("ANIMA_WORKER_TOKEN") or "").strip()
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(503, "Configure ANIMA_OPENTOONZ_TOKEN na VPS.")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "Token inválido.")


def _safe_task(task_id: str) -> dict:
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Tarefa OpenToonz não encontrada.")
    return task


@router.get("/worker/status")
def worker_status(authorization: str | None = Header(default=None)):
    _auth(authorization)
    now = time.time()
    connected = [name for name, seen in WORKERS_SEEN.items() if now - seen < 75]
    return {
        "engine": "opentoonz",
        "enabled": True,
        "connected": bool(connected),
        "workers": connected,
        "queued": TASK_QUEUE.qsize(),
        "active": sum(t.get("status") == "running" for t in TASKS.values()),
    }


@router.get("/worker/next")
def next_task(worker_id: str = "windows-opentoonz",
              authorization: str | None = Header(default=None)):
    _auth(authorization)
    WORKERS_SEEN[worker_id] = time.time()
    try:
        task_id = TASK_QUEUE.get(timeout=20)
    except queue.Empty:
        return {"task": None, "heartbeat": True}
    task = TASKS.get(task_id)
    if not task or task.get("status") != "queued":
        return {"task": None, "heartbeat": True}
    task.update(status="running", worker_id=worker_id,
                started_at=datetime.now(timezone.utc).isoformat())
    return {"task": {"id": task_id, "config": task["config"]}}


@router.post("/tasks", status_code=202)
async def create_task(request: Request, authorization: str | None = Header(default=None)):
    _auth(authorization)
    payload = await request.json()
    config = payload.get("config") if isinstance(payload, dict) else None
    if not isinstance(config, dict):
        raise HTTPException(400, "Informe a configuração da cena.")
    scene = str(config.get("scene_path", "")).strip()
    if not scene.lower().endswith(".tnz") or len(scene) > 1024:
        raise HTTPException(400, "Informe o caminho de uma cena .tnz no computador Windows.")
    try:
        start, end = int(config.get("frame_start", 1)), int(config.get("frame_end", 1))
        fps = int(config.get("fps", 24))
    except (TypeError, ValueError):
        raise HTTPException(400, "Quadros e FPS precisam ser números inteiros.")
    if start < 1 or end < start or end - start > 20000 or fps < 1 or fps > 60:
        raise HTTPException(400, "Intervalo de quadros ou FPS inválido.")
    task_id = uuid.uuid4().hex
    TASKS[task_id] = {
        "id": task_id, "status": "queued", "config": {
            "scene_path": scene, "frame_start": start, "frame_end": end,
            "fps": fps, "timeout_seconds": min(max(int(config.get("timeout_seconds", 7200)), 60), 14400),
        }, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    TASK_QUEUE.put(task_id)
    return {"task_id": task_id, "status": "queued", "engine": "opentoonz"}


@router.post("/tasks/{task_id}/chunks/{chunk_index}", status_code=202)
async def upload_chunk(task_id: str, chunk_index: int, request: Request,
                       authorization: str | None = Header(default=None)):
    _auth(authorization)
    task = _safe_task(task_id)
    if task.get("status") != "running":
        raise HTTPException(409, "A tarefa não está em execução.")
    if chunk_index < 0 or chunk_index > 10000:
        raise HTTPException(400, "Índice de bloco inválido.")
    data = await request.body()
    if not data or len(data) > CHUNK_LIMIT:
        raise HTTPException(413, "Bloco vazio ou maior que 12 MB.")
    folder = _storage() / task_id / "chunks"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{chunk_index:06d}.part"
    temp = target.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(target)
    task["upload_chunks"] = max(int(task.get("upload_chunks", 0)), chunk_index + 1)
    return {"status": "chunk_received", "chunk_index": chunk_index, "bytes": len(data)}


@router.post("/tasks/{task_id}/finalize")
def finalize_upload(task_id: str, payload: dict,
                    authorization: str | None = Header(default=None)):
    _auth(authorization)
    task = _safe_task(task_id)
    if task.get("status") != "running":
        raise HTTPException(409, "A tarefa não está em execução.")
    try:
        total = int(payload.get("total_chunks", 0))
    except (TypeError, ValueError):
        total = 0
    if total < 1 or total > 10001:
        raise HTTPException(400, "Quantidade de blocos inválida.")
    root = _storage() / task_id
    chunks = root / "chunks"
    archive = root / "frames.zip"
    temp_archive = root / "frames.zip.part"
    try:
        with temp_archive.open("wb") as output:
            for index in range(total):
                part = chunks / f"{index:06d}.part"
                if not part.is_file():
                    raise HTTPException(400, f"Bloco {index} ausente.")
                with part.open("rb") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        if not temp_archive.stat().st_size or temp_archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise HTTPException(413, "Arquivo ZIP vazio ou maior que 2 GB.")
        temp_archive.replace(archive)
        frames_dir = root / "frames"
        frames_dir.mkdir(exist_ok=True)
        expected_start = task["config"]["frame_start"]
        expected_end = task["config"]["frame_end"]
        expected_names = {f"frame-{n:06d}.png" for n in range(expected_start, expected_end + 1)}
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            if len(names) != len(expected_names) or set(names) != expected_names:
                raise HTTPException(400, "O ZIP não contém exatamente todos os quadros PNG esperados.")
            for info in zf.infolist():
                if info.file_size > 100 * 1024 * 1024 or not re.fullmatch(r"frame-\d{6}\.png", info.filename):
                    raise HTTPException(400, "Arquivo inválido dentro do ZIP.")
                with zf.open(info) as source, (frames_dir / info.filename).open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
        output_mp4 = root / f"{task_id}.mp4"
        pattern = frames_dir / "frame-%06d.png"
        command = [
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(task["config"]["fps"]),
            "-start_number", str(expected_start), "-i", str(pattern),
            "-frames:v", str(expected_end - expected_start + 1),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_mp4),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode or not output_mp4.is_file() or output_mp4.stat().st_size < 1024:
            raise RuntimeError((result.stderr or "FFmpeg não gerou o MP4.")[-3000:])
        shutil.rmtree(chunks, ignore_errors=True)
        shutil.rmtree(frames_dir, ignore_errors=True)
        task.update(status="done", result_path=str(output_mp4),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    output_bytes=output_mp4.stat().st_size,
                    total_frames=expected_end - expected_start + 1)
        return {"status": "done", "bytes": output_mp4.stat().st_size,
                "frames": task["total_frames"], "download_url": f"/api/opentoonz/tasks/{task_id}/download"}
    except Exception as exc:
        task.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:3000])
        temp_archive.unlink(missing_ok=True)
        raise


@router.post("/tasks/{task_id}/fail")
async def fail_task(task_id: str, request: Request,
                    authorization: str | None = Header(default=None)):
    _auth(authorization)
    task = _safe_task(task_id)
    payload = await request.json()
    task.update(status="failed", error=str(payload.get("error", "Falha no worker"))[:3000])
    return {"status": "failed"}


@router.get("/tasks/{task_id}")
def task_status(task_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    task = _safe_task(task_id)
    return {key: task.get(key) for key in (
        "id", "status", "error", "created_at", "started_at", "completed_at",
        "worker_id", "output_bytes", "total_frames",
    )}


@router.get("/tasks/{task_id}/download")
def download_result(task_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    task = _safe_task(task_id)
    if task.get("status") != "done" or not task.get("result_path"):
        raise HTTPException(409, "O vídeo ainda não está pronto.")
    path = Path(task["result_path"])
    if not path.is_file():
        raise HTTPException(404, "Arquivo final não encontrado.")
    return FileResponse(path, media_type="video/mp4", filename=f"opentoonz-{task_id[:8]}.mp4")
