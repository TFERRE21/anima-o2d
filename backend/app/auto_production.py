"""Automatic story-to-illustration-to-video pipeline.

A single script approval enables the pipeline. The ComfyUI image worker does
not need to be connected at approval time; tasks remain queued on disk. All
generated images pass technical validation; existing official protagonists are
never replaced. Once every asset is ready, the existing Blender/FFmpeg episode
renderer starts without a second click.

These are technical checks, not a claim of human-level artistic evaluation.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import HTTPException

from backend.app.art_assets import CAST_IDS, approve_art, approved_path
from backend.app.art_director import create_art_plan

_lock = threading.RLock()
_wakeup = threading.Event()
_stopping = threading.Event()
_thread: threading.Thread | None = None
_RETRIES = 2


def notify() -> None:
    """Wake the production coordinator after ComfyUI uploads/results."""
    _wakeup.set()


def start() -> None:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _stopping.clear()
        _thread = threading.Thread(target=_loop, name="cartoon-auto-production", daemon=True)
        _thread.start()
    notify()


def stop() -> None:
    _stopping.set()
    _wakeup.set()


def _loop() -> None:
    while not _stopping.is_set():
        try:
            process_pending()
        except Exception as exc:
            print("[cartoon-auto] coordination error:", type(exc).__name__, str(exc), flush=True)
        _wakeup.wait(timeout=8)
        _wakeup.clear()


def _task_relevant(task: dict, job_id: str, lock: str) -> bool:
    return (task.get("job_id") == job_id or
            (task.get("asset_id") in CAST_IDS and task.get("identity_lock") == lock))


def _image_for(task: dict) -> Path | None:
    image_file = task.get("image_file")
    if not image_file:
        return None
    image = Path(image_file)
    if not image.is_file():
        return None
    # No arbitrary path or external file can be silently approved as artwork.
    from backend.app import comfy_worker
    safe_root = comfy_worker._store.parent.resolve()
    resolved = image.resolve()
    return resolved if resolved.is_relative_to(safe_root) else None


def _retry(task: dict, why: str) -> None:
    from backend.app import comfy_worker
    attempts = int(task.get("attempt", 1))
    task["auto_error"] = why[:600]
    if attempts <= _RETRIES and not task.get("auto_retry_queued"):
        task["auto_retry_queued"] = True
        config = dict(task["config"])
        if task.get("asset_id") in CAST_IDS:
            config["prompt"] += (
                "; mandatory full-body cutout, plain pure-white background in all "
                "corners, no props, no extra subjects, clearly bounded silhouette"
            )
        result = comfy_worker.queue_art_image(
            config, task["job_id"], task["asset_id"],
            task["format"], task["identity_lock"], force=True,
        )
        comfy_worker._tasks[result["task_id"]]["attempt"] = attempts + 1
        comfy_worker._tasks[result["task_id"]]["auto_retry_of"] = task["id"]
        task["auto_state"] = "retry_queued"
    else:
        task["auto_state"] = "failed"
    comfy_worker._save_tasks()


def _approve_candidate(task: dict, story: dict, storage: Path) -> None:
    from backend.app import comfy_worker
    if task.get("approved"):
        return
    image = _image_for(task)
    if image is None:
        return
    identity = create_art_plan(story, task["format"])["identity_lock"]
    if identity != task.get("identity_lock"):
        task.update(auto_state="failed", auto_error="Identidade visual oficial não corresponde à versão da tarefa.")
        comfy_worker._save_tasks()
        return
    asset = task["asset_id"]
    # A previous episode may already have approved the series-wide character.
    if asset in CAST_IDS and approved_path(storage, task["job_id"], asset, task["format"], identity):
        task.update(approved=True, auto_state="official_character_reused")
        comfy_worker._save_tasks()
        return
    try:
        approve_art(
            storage, task["job_id"], asset, task["format"],
            image.read_bytes(), story, auto_cutout=asset in CAST_IDS,
        )
        task.update(approved=True, auto_state="technically_validated", auto_error=None)
        comfy_worker._save_tasks()
    except (ValueError, OSError) as exc:
        if asset in CAST_IDS and approved_path(storage, task["job_id"], asset, task["format"], identity):
            task.update(approved=True, auto_state="official_character_reused")
            comfy_worker._save_tasks()
        else:
            _retry(task, str(exc))


def _process_job(job_id: str) -> None:
    from backend.app import comfy_worker, main
    job = main._get_job(job_id)
    if not job.get("auto_production_requested") or not job.get("story_approved"):
        return
    if job.get("status") in {"queued", "processing", "done"}:
        return
    if job.get("status") not in {"story_ready", "failed"}:
        return
    # A real Blender failure must NOT start the same expensive video again
    # every eight seconds. An interrupted deployment may resume only once.
    if job.get("status") == "failed":
        if job.get("stage") == "render_error":
            return
        if (job.get("stage") == "interrupted"
                and int(job.get("auto_video_recovery_count", 0)) >= 1):
            return
    story = job.get("story_plan") or {}
    if not story:
        return
    formats = job.get("formats") or ["9:16"]
    identity = create_art_plan(story)["identity_lock"]
    tasks = [t for t in list(comfy_worker._tasks.values()) if _task_relevant(t, job_id, identity)]

    # Process completed images before inspecting readiness.
    for task in tasks:
        if task.get("approved") or task.get("auto_state") in {"failed", "retry_queued"}:
            continue
        if task.get("status") == "done":
            _approve_candidate(task, story, main.STORAGE)
        elif task.get("status") == "failed":
            _retry(task, str(task.get("message") or "ComfyUI não conseguiu gerar a imagem."))

    boards = {fmt: main.get_episode_art_status(job_id, fmt) for fmt in formats}
    if not all(state["ready"] for state in boards.values()):
        missing = {(fmt, asset) for fmt, state in boards.items() for asset in state["missing"]}
        # A failed task cannot be automatically accepted; keep the error visible
        # and stop, rather than making fake or blank replacement cartoon art.
        def still_missing(task):
            return ((task.get("format"), task.get("asset_id")) in missing
                    or (task.get("asset_id") in CAST_IDS
                        and any(asset == task.get("asset_id") for _, asset in missing)))
        def newer_attempt(task):
            return any(t is not task and t.get("asset_id") == task.get("asset_id")
                       and (task.get("asset_id") in CAST_IDS
                            or t.get("format") == task.get("format"))
                       and (t.get("auto_retry_of") == task.get("id")
                            or t.get("status") in {"queued", "running"})
                       for t in tasks)
        failed = [t for t in tasks if t.get("auto_state") == "failed"
                  and still_missing(t) and not newer_attempt(t)]
        if failed:
            reason = "; ".join(f"{t['asset_id']}: {t.get('auto_error', 'falha')}" for t in failed[:3])
            if job.get("art_stage") != "error" or job.get("art_error") != reason:
                main._update(job_id, art_stage="error", art_error=reason,
                             message="Motor de imagens encontrou uma falha: " + reason)
            return
        stage = "waiting_image_engine" if not comfy_worker.worker_online() else "generating_images"
        if job.get("art_stage") != stage:
            main._update(job_id, art_stage=stage, art_error=None,
                         message=("Aguardando motor de imagens conectado para continuar."
                                  if stage == "waiting_image_engine" else
                                  "Gerando imagens e cenários do planeta automaticamente."))
        return

    # All season heroes and all required scenes are technically valid.
    if not main._has("ffmpeg") or not main._has("tts") or not main.blender_available():
        if job.get("art_stage") != "waiting_video_engine":
            main._update(job_id, art_stage="waiting_video_engine",
                         message="Imagens concluídas. Aguardando Blender/FFmpeg/vozes no container.")
        return
    # Rendering is scheduled only by the server after image completion.
    if job.get("status") == "failed" and job.get("stage") == "interrupted":
        main._update(job_id,
                     auto_video_recovery_count=int(job.get("auto_video_recovery_count", 0)) + 1)
    try:
        main.render_story(job_id, main.RenderRequest(formats=formats))
    except HTTPException as exc:
        main._update(job_id, art_stage="waiting_video_engine",
                     message="Imagens concluídas; aguardando motor de vídeo: " + str(exc.detail)[:350])
        return
    main._update(job_id, art_stage="rendering", art_error=None,
                 auto_video_started=True,
                 message="Imagens prontas. Montagem e renderização do vídeo iniciadas automaticamente.")
    print("[cartoon-auto] video started for job", job_id, flush=True)


def process_pending() -> None:
    """Also used by tests; serialized to avoid duplicate rendering starts."""
    from backend.app import main
    with _lock:
        with main.LOCK:
            job_ids = [
                identifier for identifier, job in main.JOBS.items()
                if job.get("auto_production_requested") and job.get("status") in {"story_ready", "failed"}
            ]
        for job_id in job_ids:
            try:
                _process_job(job_id)
            except Exception as exc:
                print("[cartoon-auto] error for", job_id, type(exc).__name__, str(exc), flush=True)
