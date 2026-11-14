"""Authenticated pull queue for the local ComfyUI workstation.

The Windows agent polls this API; the ComfyUI HTTP API remains bound to localhost.
"""
from __future__ import annotations
import hmac, os, queue, time, uuid, json, threading
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/comfy", tags=["ComfyUI"])
_tasks: dict[str, dict] = {}
_queue: queue.Queue = queue.Queue()
_workers: dict[str, float] = {}

_tasks_lock = threading.RLock()
_store = Path(os.getenv("ANIMA_STORAGE", "/data/jobs")) / "comfyui" / "task-state.json"


def _save_tasks():
    with _tasks_lock:
        _store.parent.mkdir(parents=True, exist_ok=True)
        temp = _store.with_suffix(".tmp")
        temp.write_text(json.dumps(_tasks, ensure_ascii=False), encoding="utf-8")
        temp.replace(_store)


def _restore_tasks():
    if not _store.is_file():
        return
    try:
        state = json.loads(_store.read_text(encoding="utf-8"))
        for task_id, task in state.items():
            if not isinstance(task, dict) or not isinstance(task_id, str):
                continue
            if task.get("status") in {"running", "queued"}:
                task["status"] = "queued"
                _queue.put(task_id)
            _tasks[task_id] = task
    except (OSError, ValueError, TypeError) as exc:
        print("[comfyui] restore error: " + str(exc), flush=True)


_restore_tasks()


def worker_online() -> bool:
    return any(time.time() - seen < 75 for seen in _workers.values())


def art_tasks(job_id: str) -> list[dict]:
    return sorted([
        {"id": t["id"], "asset_id": t.get("asset_id"), "format": t.get("format"),
         "status": t.get("status"), "has_image": bool(t.get("image_file")
                       and Path(t["image_file"]).is_file()),
         "message": t.get("message", ""), "created_at": t.get("created_at")}
        for t in _tasks.values() if t.get("job_id") == job_id
    ], key=lambda t: t.get("created_at") or "", reverse=True)



class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    negative_prompt: str = Field(default="text, watermark, blurry, deformed anatomy", max_length=2000)
    checkpoint: str = Field(default="v1-5-pruned-emaonly.safetensors", max_length=180)
    width: int = Field(default=512, ge=256, le=1024)
    height: int = Field(default=512, ge=256, le=1024)
    steps: int = Field(default=20, ge=1, le=50)
    cfg: float = Field(default=7.0, ge=1, le=15)
    seed: int = Field(default=-1, ge=-1)

def _auth(authorization: str | None):
    expected = os.getenv("ANIMA_COMFY_TOKEN", "").strip()
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(503, "Configure ANIMA_COMFY_TOKEN na VPS.")
    if not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, "Token do agente ComfyUI inválido.")

@router.get("/status")
def status(authorization: str | None = Header(default=None)):
    _auth(authorization)
    now=time.time()
    online=[name for name,seen in _workers.items() if now-seen < 75]
    return {"enabled":True,"connected":bool(online),"workers":online,
            "queued":_queue.qsize(),
            "running":sum(t["status"]=="running" for t in _tasks.values())}

@router.post("/heartbeat")
def heartbeat(worker_id: str="windows-comfyui-rx580", authorization: str | None=Header(default=None)):
    _auth(authorization); _workers[worker_id]=time.time()
    return {"ok":True,"worker_id":worker_id}

@router.get("/next")
def next_task(worker_id: str="windows-comfyui-rx580", authorization: str | None=Header(default=None)):
    _auth(authorization); _workers[worker_id]=time.time()
    try: task_id=_queue.get(timeout=1)
    except queue.Empty: return {"task":None}
    task=_tasks.get(task_id)
    if not task or task["status"]!="queued": return {"task":None}
    task.update(status="running",worker_id=worker_id,started_at=datetime.now(timezone.utc).isoformat())
    _save_tasks()
    return {"task":{"id":task_id,"config":task["config"]}}

@router.post("/generate",status_code=202)
def generate(payload: GenerateRequest, authorization: str | None=Header(default=None)):
    _auth(authorization)
    if not any(time.time()-seen < 75 for seen in _workers.values()):
        raise HTTPException(503,"Agente ComfyUI desconectado. Inicie o agente Windows pelo painel.")
    task_id=uuid.uuid4().hex[:16]
    _tasks[task_id]={"id":task_id,"status":"queued","config":payload.model_dump(),
        "created_at":datetime.now(timezone.utc).isoformat()}
    _queue.put(task_id)
    _save_tasks()
    return {"task_id":task_id,"status":"queued"}

def queue_art_image(payload: dict, job_id: str, asset_id: str, fmt: str,
                    identity_lock: str, *, force: bool = False) -> dict:
    """Persistently queue image generation, even if the Windows worker is offline."""
    with _tasks_lock:
        if not force:
            for task in _tasks.values():
                if (task.get("job_id") == job_id and task.get("asset_id") == asset_id
                        and task.get("format") == fmt and task.get("identity_lock") == identity_lock
                        and task.get("status") in {"queued", "running", "done"}):
                    return {"task_id": task["id"], "status": task["status"],
                            "asset_id": asset_id, "format": fmt, "reused": True}
        config = GenerateRequest(**payload).model_dump()
        task_id = uuid.uuid4().hex[:16]
        _tasks[task_id] = {
            "id": task_id, "status": "queued", "config": config,
            "job_id": job_id, "asset_id": asset_id, "format": fmt,
            "identity_lock": identity_lock,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_tasks()
        _queue.put(task_id)
    return {"task_id": task_id, "status": "queued", "asset_id": asset_id,
            "format": fmt, "reused": False,
            "message": "Imagem agendada; aguardando o agente ComfyUI se estiver offline."}


def get_art_task(task_id: str, job_id: str) -> dict:
    task = _tasks.get(task_id)
    if not task or task.get("job_id") != job_id:
        raise HTTPException(404, "Tarefa de arte não encontrada neste episódio.")
    return task


@router.post("/tasks/{task_id}/result")
def result(task_id: str, payload: dict, authorization: str | None=Header(default=None)):
    _auth(authorization)
    task=_tasks.get(task_id)
    if not task: raise HTTPException(404,"Tarefa não encontrada.")
    task.update(status=payload.get("status","failed"),message=str(payload.get("message",""))[:2000],
                output=payload.get("output"),completed_at=datetime.now(timezone.utc).isoformat())
    _save_tasks()
    return {"ok":True}

@router.get("/tasks")
def tasks(authorization: str | None=Header(default=None)):
    _auth(authorization)
    return {"tasks":sorted(_tasks.values(),key=lambda t:t["created_at"],reverse=True)[:50]}

@router.post("/tasks/{task_id}/image")
async def upload_image(task_id: str, request: Request, authorization: str | None=Header(default=None)):
    _auth(authorization)
    task=_tasks.get(task_id)
    if not task: raise HTTPException(404,"Tarefa não encontrada.")
    data=await request.body()
    if not data or len(data)>30*1024*1024: raise HTTPException(400,"Imagem vazia ou maior que 30 MB.")
    storage=Path(os.getenv("ANIMA_STORAGE","/data/jobs"))/"comfyui"
    storage.mkdir(parents=True,exist_ok=True)
    target=storage/(task_id+".png")
    temp=target.with_suffix(".tmp")
    temp.write_bytes(data); temp.replace(target)
    task["image_file"]=str(target)
    task["image_url"]="/api/comfy/tasks/"+task_id+"/image"
    _save_tasks()
    return {"ok":True,"image_url":task["image_url"],"bytes":len(data)}

@router.get("/tasks/{task_id}/image")
def get_image(task_id: str, authorization: str | None=Header(default=None)):
    _auth(authorization)
    task=_tasks.get(task_id)
    if not task or not task.get("image_file"): raise HTTPException(404,"Imagem ainda não disponível.")
    return FileResponse(task["image_file"],media_type="image/png",filename=task_id+".png")
