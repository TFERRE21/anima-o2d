"""Automatic high-quality still-image provider for the cartoon episode pipeline.

Use an available hosted image generator inside the VPS (Runway or OpenAI),
otherwise the existing authenticated ComfyUI agent. Never create fake images.
API-based generation may incur provider charges; credentials stay on the VPS.
"""
from __future__ import annotations

import base64
import io
import json
import hashlib
import os
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, UnidentifiedImageError

_thread: threading.Thread | None = None
_lock = threading.Lock()
_wake = threading.Event()
_stop = threading.Event()
_MAX_RESPONSE = 32 * 1024 * 1024
_ERR_LIMIT = 350
_block_lock = threading.RLock()
_CREDIT_MARKERS = ('you do not have enough credits', 'not enough credits', 'insufficient_quota', 'billing_hard_limit_reached', 'insufficient credits', 'credit balance is too low')



def is_credit_error(error: object) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in _CREDIT_MARKERS)


def _credential(provider: str) -> str:
    if provider == "runway":
        return (os.getenv("RUNWAYML_API_SECRET") or os.getenv("RUNWAY_API_KEY") or "").strip()
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY", "").strip()
    return ""


def _block_file() -> Path:
    from backend.app import comfy_worker
    return comfy_worker._store.parent / "provider-blocks.json"


def _read_blocks() -> dict:
    path = _block_file()
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return {}


def _blocked(provider: str) -> bool:
    key = _credential(provider)
    if not key:
        return False
    with _block_lock:
        state = _read_blocks().get(provider) or {}
    fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return (state.get("key_fingerprint") == fingerprint
            and float(state.get("blocked_until", 0)) > time.time())


def _mark_out_of_credits(provider: str) -> None:
    key = _credential(provider)
    if not key:
        return
    try:
        delay = int(os.getenv("ANIMA_CREDIT_RECHECK_SECONDS", "1800"))
    except ValueError:
        delay = 1800
    delay = max(300, min(delay, 86400))
    with _block_lock:
        blocks = _read_blocks()
        blocks[provider] = {
            "reason": "insufficient_credits",
            "key_fingerprint": hashlib.sha256(key.encode("utf-8")).hexdigest(),
            "blocked_until": time.time() + delay,
        }
        path = _block_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(blocks), encoding="utf-8")
        temp.replace(path)


def configured_provider() -> str:
    """Select a configured, not-yet-credit-blocked provider."""
    mode = os.getenv("ANIMA_IMAGE_PROVIDER", "auto").strip().lower()
    if mode not in {"auto", "runway", "openai", "comfyui"}:
        return "unavailable"
    if mode == "runway":
        return "runway" if _credential("runway") and not _blocked("runway") else "unavailable"
    if mode == "openai":
        return "openai" if _credential("openai") and not _blocked("openai") else "unavailable"
    if mode == "comfyui":
        return "comfyui"
    if _credential("runway") and not _blocked("runway"):
        return "runway"
    if _credential("openai") and not _blocked("openai"):
        return "openai"
    from backend.app import comfy_worker
    return "comfyui" if comfy_worker.worker_online() else "unavailable"


def engine_state() -> dict:
    from backend.app import comfy_worker
    provider = configured_provider()
    exhausted = [p for p in ("runway", "openai") if _blocked(p)]
    online = comfy_worker.worker_online()
    available = provider in {"runway", "openai"} or (provider == "comfyui" and online)
    if available:
        detail = ("Runway sem créditos; motor alternativo " + provider + " selecionado."
                  if "runway" in exhausted and provider != "runway"
                  else "Motor de imagens pronto para produzir automaticamente.")
    elif exhausted:
        detail = ("Créditos de geração de imagens esgotados: "
                  + ", ".join(exhausted)
                  + ". As tarefas estão salvas. Configure outra API com créditos "
                    "ou conecte o agente ComfyUI.")
    else:
        detail = ("Nenhum motor de imagens disponível. Configure uma API de imagens "
                  "com créditos ou conecte o agente ComfyUI à VPS.")
    return {
        "provider": provider,
        "ready": available,
        "credits_exhausted": exhausted,
        "image_model": (
            os.getenv("ANIMA_RUNWAY_IMAGE_MODEL", "nano_banana_2.1") if provider == "runway"
            else os.getenv("ANIMA_OPENAI_IMAGE_MODEL", "gpt-image-1.5") if provider == "openai"
            else "ComfyUI workstation" if provider == "comfyui" else "none"
        ),
        "detail": detail,
    }


def wake() -> None:
    _wake.set()


def start() -> None:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, daemon=True, name="anima-image-engine")
        _thread.start()
        wake()


def stop() -> None:
    _stop.set()
    _wake.set()


def _json_request(url: str, method: str = "GET", body: dict | None = None,
                  headers: dict | None = None, timeout: int = 150) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, data=data, method=method,
                  headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_RESPONSE)
            return json.loads(raw)
    except HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"Provedor respondeu HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Não foi possível acessar o motor de imagens: " + str(exc)) from exc


def _download_image(url: str) -> bytes:
    uri = urlparse(url)
    if uri.scheme != "https" or not uri.hostname:
        raise ValueError("O provedor devolveu URL de imagem inválida.")
    # Downloads are authorized only from the HTTPS URL returned by our
    # authenticated external image-generation service.
    with urlopen(Request(url, headers={"User-Agent": "AnimaStudio/1.0"}), timeout=140) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type:
            raise ValueError("Resposta HTML inesperada em vez de imagem.")
        data = resp.read(_MAX_RESPONSE + 1)
    if len(data) > _MAX_RESPONSE:
        raise ValueError("Imagem maior que o limite seguro.")
    return data


def _runway_image(task: dict) -> bytes:
    key = (os.getenv("RUNWAYML_API_SECRET") or os.getenv("RUNWAY_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Chave Runway ausente no container.")
    config = task["config"]
    asset = task.get("asset_id") or ""
    fmt = task.get("format") or "9:16"
    model = os.getenv("ANIMA_RUNWAY_IMAGE_MODEL", "nano_banana_2.1")
    headers = {"Authorization": "Bearer " + key, "X-Runway-Version": "2024-11-06"}
    # 1K generation keeps cost predictable; approved images will be cropped to
    # production aspect rather than stretched.
    ratio = ("1024:1024" if asset in {"luna", "tomi", "pipo"}
             else "720:1280" if fmt == "9:16" else "1280:720")
    payload = {"model": model, "promptText": config["prompt"][:5000], "ratio": ratio}
    begun = _json_request("https://api.dev.runwayml.com/v1/text_to_image",
                          "POST", payload, headers, timeout=80)
    runway_id = begun.get("id")
    if not runway_id or not isinstance(runway_id, str):
        raise RuntimeError("Runway não devolveu identificador da imagem.")
    # Task status is polled without creating duplicate chargeable requests.
    deadline = time.monotonic() + max(60, min(int(os.getenv("ANIMA_IMAGE_TIMEOUT", "600")), 1800))
    while time.monotonic() < deadline and not _stop.is_set():
        detail = _json_request("https://api.dev.runwayml.com/v1/tasks/" + runway_id,
                               headers=headers, timeout=45)
        status = detail.get("status")
        if status == "SUCCEEDED":
            outputs = detail.get("output") or []
            if not outputs or not isinstance(outputs[0], str):
                raise RuntimeError("Runway concluiu mas não devolveu URL de imagem.")
            return _download_image(outputs[0])
        if status in {"FAILED", "CANCELLED", "ABORTED"}:
            raise RuntimeError("Runway falhou: " + str(detail.get("failure") or status)[:250])
        time.sleep(3)
    raise TimeoutError("Runway excedeu o limite definido para gerar a imagem.")


def _openai_image(task: dict) -> bytes:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY ausente no container.")
    config = task["config"]
    asset = task.get("asset_id") or ""
    fmt = task.get("format") or "9:16"
    cast = asset in {"luna", "tomi", "pipo"}
    body = {
        "model": os.getenv("ANIMA_OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
        "prompt": config["prompt"][:12000],
        "n": 1,
        "size": ("1024x1536" if cast or fmt == "9:16" else "1536x1024"),
        "quality": os.getenv("ANIMA_IMAGE_QUALITY", "medium"),
        "background": "transparent" if cast else "opaque",
        "output_format": "png",
    }
    result = _json_request("https://api.openai.com/v1/images/generations",
                           "POST", body,
                           {"Authorization": "Bearer " + key},
                           timeout=max(120, min(int(os.getenv("ANIMA_IMAGE_TIMEOUT", "600")), 900)))
    output = (result.get("data") or [{}])[0]
    b64 = output.get("b64_json")
    if not b64:
        raise RuntimeError("A API de imagem não devolveu um PNG válido.")
    return base64.b64decode(b64, validate=True)


def _normalize_image(data: bytes, task: dict) -> bytes:
    """Convert provider output into a lossless PNG with the requested ratio."""
    if len(data) > _MAX_RESPONSE:
        raise ValueError("Imagem excedeu tamanho máximo.")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("O motor devolveu arquivo que não é uma imagem.") from exc
    if image.width < 256 or image.height < 256:
        raise ValueError("Imagem gerada pequena demais.")
    cast = task.get("asset_id") in {"luna", "tomi", "pipo"}
    fmt = task.get("format") or "9:16"
    if cast:
        # Leave the full silhouette intact; character approval validates alpha
        # or removes a uniform white background.
        image.thumbnail((1024, 1536), Image.Resampling.LANCZOS)
        result = image.convert("RGBA")
    else:
        target = (576, 1024) if fmt == "9:16" else (1024, 576)
        result = ImageOps.fit(image.convert("RGB"), target, Image.Resampling.LANCZOS,
                              centering=(0.5, 0.5))
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()



def _task_key(task: dict) -> tuple:
    # Series protagonists are shared; episode backgrounds are unique.
    asset = task.get("asset_id")
    if asset in {"luna", "tomi", "pipo"}:
        return ("cast", task.get("identity_lock"), asset)
    return ("scene", task.get("job_id"), task.get("format"), asset)


def reconcile_credit_tasks() -> bool:
    """Recover quota-blocked and historical failed assets without duplicates."""
    from backend.app import comfy_worker
    changed = False
    choice = configured_provider()
    with comfy_worker._tasks_lock:
        tasks = list(comfy_worker._tasks.values())
        credit_tasks = [
            t for t in tasks
            if t.get("asset_id") and t.get("status") in {"failed", "blocked"}
            and (t.get("provider_error_code") == "insufficient_credits"
                 or is_credit_error(t.get("message") or "")
                 or is_credit_error(t.get("auto_error") or ""))
        ]
        for task in credit_tasks:
            key = _task_key(task)
            others_active = any(
                t is not task and _task_key(t) == key
                and t.get("status") in {"queued", "running", "done"}
                for t in tasks
            )
            others_newer = any(
                t is not task and _task_key(t) == key and t in credit_tasks
                and (t.get("created_at") or "", t.get("id") or "")
                    > (task.get("created_at") or "", task.get("id") or "")
                for t in tasks
            )
            if others_active or others_newer:
                task.update(status="cancelled", auto_state="superseded")
                changed = True
                continue
            task["provider_error_code"] = "insufficient_credits"
            if choice in {"runway", "openai", "comfyui"}:
                task.update(status="queued", provider=choice,
                            auto_state="resuming", auto_error=None,
                            message="Tarefa retomada no motor disponível.")
                if choice == "comfyui":
                    comfy_worker._queue.put(task["id"])
                changed = True
            elif task.get("status") != "blocked" or task.get("auto_state") != "waiting_provider":
                task.update(status="blocked", auto_state="waiting_provider",
                            message="Provedor sem créditos. Aguardando outro motor.")
                changed = True
        if changed:
            comfy_worker._save_tasks()
    return changed


def _claim_one() -> dict | None:
    from backend.app import comfy_worker
    reconcile_credit_tasks()
    with comfy_worker._tasks_lock:
        mode = configured_provider()
        if mode not in {"runway", "openai"}:
            return None
        # Cloud service also rescues legacy queued image jobs created when only
        # ComfyUI was configured or no image API key was previously available.
        for task in comfy_worker._tasks.values():
            if not task.get("asset_id") or task.get("status") != "queued":
                continue
            if task.get("provider") not in (None, "comfyui", "unavailable", mode):
                continue
            task["provider"] = mode
            task["status"] = "running"
            task["started_at"] = time.time()
            comfy_worker._save_tasks()
            return task
    return None


def process_one() -> bool:
    """Run exactly one cloud image job; useful for isolated integration tests."""
    from backend.app import comfy_worker
    task = _claim_one()
    if task is None:
        return False
    try:
        raw = (_runway_image(task) if task["provider"] == "runway"
               else _openai_image(task))
        png = _normalize_image(raw, task)
        storage = comfy_worker._store.parent
        storage.mkdir(parents=True, exist_ok=True)
        target = storage / (task["id"] + ".png")
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(png)
        tmp.replace(target)
        with comfy_worker._tasks_lock:
            task.update(
                image_file=str(target), status="done",
                message="Imagem criada automaticamente com " + task["provider"],
                completed_at=time.time(),
            )
            comfy_worker._save_tasks()
    except Exception as exc:
        with comfy_worker._tasks_lock:
            provider = task.get("provider") or "unavailable"
            if is_credit_error(exc):
                _mark_out_of_credits(provider)
                task.update(
                    status="blocked", auto_state="waiting_provider",
                    provider_error_code="insufficient_credits",
                    message=provider.capitalize() + " sem créditos disponíveis.",
                    completed_at=time.time(),
                )
            else:
                task.update(
                    status="failed",
                    message=(type(exc).__name__ + ": " + str(exc))[:_ERR_LIMIT],
                    completed_at=time.time(),
                )
            comfy_worker._save_tasks()
        if is_credit_error(exc):
            reconcile_credit_tasks()
    finally:
        from backend.app.auto_production import notify
        notify()
    return True


def _loop() -> None:
    while not _stop.is_set():
        if not process_one():
            _wake.wait(timeout=6)
            _wake.clear()
