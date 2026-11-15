"""Anima Studio ComfyUI image-generation worker (Windows)."""
import io
import json
import os
import pathlib
import re
import socket
import subprocess
import threading
import time
import uuid

import requests
from PIL import Image, ImageOps

SERVER = os.environ["ANIMA_STUDIO_URL"].rstrip("/")
TOKEN = os.environ["ANIMA_COMFY_TOKEN"]
COMFY = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
WORKER = os.getenv("ANIMA_COMFY_WORKER_ID", os.getenv("COMPUTERNAME", "windows") + "-comfyui")
ROOT = pathlib.Path(__file__).resolve().parent
WF = pathlib.Path(os.getenv("COMFYUI_API_WORKFLOW", str(ROOT / "workflow_api.json")))
OUT = pathlib.Path(os.getenv("ANIMA_COMFY_OUTPUT", str(ROOT / "generated")))
OUT.mkdir(parents=True, exist_ok=True)
PROFILE_VERSION = "rx580-memory-safe-v1"
FP16_PROFILE_VERSION = "rx580-unet-fp16-v2"
DIRECTML_PROFILE_VERSION = "rx580-directml-v3"
_RX580_MODE = False
_DIRECTML_MODE = False
SESSION = requests.Session()
SESSION.headers["Authorization"] = "Bearer " + TOKEN
_HEARTBEAT_THREAD = None
_LOCAL_READY = threading.Event()
_LAST_COMFY_START = float('-inf')
_COMFY_START_ATTEMPTS = []
_COMFY_ROOT = pathlib.Path(os.getenv("COMFYUI_INSTALL_DIR", r"C:\ComfyUI-Zluda\ComfyUI-Zluda"))
_COMFY_LAUNCHER = _COMFY_ROOT / "comfyui.bat"
_COMFY_AUTOSTART = os.name == "nt" and os.getenv("ANIMA_COMFY_AUTOSTART", "1").strip().lower() not in {"0", "false", "off"}
_COMFY_START_COOLDOWN_SECONDS = 90
_COMFY_START_ATTEMPTS_LIMIT = 3
_COMFY_START_WINDOW_SECONDS = 3600


def _profile_version():
    """Report the backend actually running, not the requested backend."""
    if _DIRECTML_MODE:
        return DIRECTML_PROFILE_VERSION
    if not _RX580_MODE:
        return ""
    try:
        launcher = _COMFY_LAUNCHER
        lines = launcher.read_text(encoding="latin-1").splitlines()
        active = [
            line for line in lines
            if not re.match(r"^\s*(?:rem\b|::)", line, re.IGNORECASE)
        ]
        has_fp16 = any(re.search(r"--fp16-unet\b", line, re.IGNORECASE) for line in active)
        has_fp32 = any(re.search(r"--(?:fp32-unet|force-fp32)\b", line, re.IGNORECASE) for line in active)
        if has_fp16 and not has_fp32:
            return FP16_PROFILE_VERSION
    except OSError:
        pass
    return PROFILE_VERSION


def _heartbeats_while_rendering():
    """Keep the VPS worker marked online while a slow RX 580 draws a frame."""
    was_connected = True
    while True:
        # The VPS must not consider an offline ComfyUI to be ready just
        # because this agent process is still running.
        if not _LOCAL_READY.wait(timeout=5):
            continue
        try:
            reply = requests.post(
                SERVER + "/api/comfy/heartbeat",
                params={"worker_id": WORKER, "profile_version": _profile_version()},
                headers={"Authorization": "Bearer " + TOKEN},
                timeout=20,
            )
            reply.raise_for_status()
            if not was_connected:
                print("Conexão de monitoramento com a VPS recuperada.", flush=True)
            was_connected = True
        except requests.RequestException as error:
            if was_connected:
                print("Monitoramento da VPS interrompido:", type(error).__name__, str(error)[:200], flush=True)
            was_connected = False
        time.sleep(25)


def _ensure_heartbeat():
    global _HEARTBEAT_THREAD
    if _HEARTBEAT_THREAD is not None and _HEARTBEAT_THREAD.is_alive():
        return
    _HEARTBEAT_THREAD = threading.Thread(
        target=_heartbeats_while_rendering,
        name="anima-comfy-heartbeat", daemon=True,
    )
    _HEARTBEAT_THREAD.start()


def _execution_error(record):
    """Extract the failing ComfyUI node and exception from /history."""
    status = record.get("status") or {}
    errors = []
    for event in status.get("messages") or []:
        if not isinstance(event, (list, tuple)) or len(event) < 2:
            continue
        name, data = event[0], event[1]
        if name != "execution_error" or not isinstance(data, dict):
            continue
        parts = [
            "Nó " + str(data.get("node_id") or "?") + " (" + str(data.get("node_type") or "?") + ")",
            str(data.get("exception_type") or "erro"),
            str(data.get("exception_message") or "").strip(),
        ]
        errors.append(": ".join(p for p in parts if p))
    if errors:
        return " | ".join(errors)[:1800]
    return "ComfyUI informou erro na execução. Confira o terminal do ComfyUI e o histórico do prompt."


def _prompt_response(response):
    """Do not hide checkpoint, node-validation or model loading errors."""
    try:
        body = response.json()
    except ValueError as error:
        raise RuntimeError("ComfyUI devolveu resposta não-JSON: HTTP " + str(response.status_code)) from error
    if response.status_code >= 400 or "prompt_id" not in body:
        reason = body.get("error") or {}
        if isinstance(reason, dict):
            reason = str(reason.get("message") or reason.get("type") or reason)
        node_errors = body.get("node_errors") or {}
        details = []
        if isinstance(node_errors, dict):
            for node_id, item in list(node_errors.items())[:3]:
                if not isinstance(item, dict):
                    continue
                for problem in (item.get("errors") or [])[:2]:
                    details.append("nó " + str(node_id) + ": " + str(problem.get("message") or problem.get("details") or problem)[:250])
        raise RuntimeError(
            "ComfyUI rejeitou workflow (HTTP " + str(response.status_code) + "): "
            + str(reason)[:400] + (" | " + " | ".join(details) if details else "")
        )
    return body["prompt_id"]


def report(task_id, status, message="", output=None):
    response = SESSION.post(
        f"{SERVER}/api/comfy/tasks/{task_id}/result",
        json={"status": status, "message": str(message)[:2000], "output": output,
              "profile_version": _profile_version()},
        timeout=30,
    )
    response.raise_for_status()


def _is_oom(error):
    message = str(error).lower()
    return ("out of memory" in message or "hip error: out of memory" in message
            or "cuda error: out of memory" in message)


def _sizes_for(config):
    """Try two modest diffusion resolutions for RX 580 8GB + FP32/ZLUDA.

    Result is upscaled on CPU to the originally requested size; the 1080p
    video canvas remains unchanged. CPU resizing does not restore details.
    """
    width = int(config.get("width") or 512)
    height = int(config.get("height") or 512)
    if not _RX580_MODE:
        return [(width, height)]
    ratio = width / max(1, height)
    if ratio >= 1.3:
        choices = [(704, 384), (576, 320)]
    elif ratio <= 0.64:
        choices = [(384, 704), (320, 576)]
    else:
        choices = [(448, 640), (384, 512)]
    # A small original request should never be made larger by RX580 mode.
    if width * height <= choices[0][0] * choices[0][1]:
        return [(width, height)]
    return choices


def _clear_gpu_memory():
    try:
        response = requests.post(
            COMFY + "/free", json={"unload_models": True, "free_memory": True},
            timeout=25,
        )
        if response.status_code >= 400:
            print("ComfyUI não conseguiu liberar modelos; reinicie o processo se persistir OOM.", flush=True)
    except requests.RequestException as error:
        print("Falha não fatal ao solicitar liberação de VRAM:", str(error)[:180], flush=True)


def _image_for_upload(data, config):
    """Keep all approved-art output sizes valid, using CPU to resize PNG."""
    with Image.open(io.BytesIO(data)) as original:
        original.load()
        rgba = original.convert("RGBA")
    width, height = int(config.get("width") or rgba.width), int(config.get("height") or rgba.height)
    is_cast = bool(config.get("_asset_id") in {"luna", "tomi", "pipo"})
    if rgba.size != (width, height):
        if is_cast:
            # Maintain silhouette geometry and pure-white cutout corners.
            subject = ImageOps.contain(rgba, (width, height), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
            canvas.alpha_composite(subject, ((width - subject.width) // 2,
                                             (height - subject.height) // 2))
            rgba = canvas
        else:
            rgba = ImageOps.fit(rgba, (width, height), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    rgba.save(output, format="PNG")
    return output.getvalue()


def make_workflow(config):
    if not WF.is_file():
        raise RuntimeError("workflow_api.json não encontrado ao lado do agente.")
    workflow = json.loads(WF.read_text(encoding="utf-8"))
    nodes = list(workflow.values())

    def inputs(node_type):
        for node in nodes:
            if node.get("class_type") == node_type:
                return node["inputs"]
        raise RuntimeError("Nó ausente no workflow ComfyUI: " + node_type)

    available = requests.get(COMFY + "/object_info/CheckpointLoaderSimple", timeout=30).json()
    choices = available.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
    if not choices:
        raise RuntimeError("Nenhum checkpoint instalado no ComfyUI. Instale um modelo .safetensors em ComfyUI/models/checkpoints.")
    requested = config.get("checkpoint", "").strip()
    if requested and requested not in choices:
        raise RuntimeError(
            "Checkpoint solicitado não instalado: " + requested
            + ". Coloque o modelo .safetensors em ComfyUI/models/checkpoints, "
            "ou ajuste ANIMA_ART_CHECKPOINT na VPS. Modelos disponíveis: "
            + ", ".join(choices[:5])
        )
    inputs("CheckpointLoaderSimple")["ckpt_name"] = requested or choices[0]
    text_nodes = [node["inputs"] for node in nodes if node.get("class_type") == "CLIPTextEncode"]
    if len(text_nodes) < 2:
        raise RuntimeError("O workflow precisa de CLIP positivo e negativo.")
    text_nodes[0]["text"] = config["prompt"]
    text_nodes[1]["text"] = config.get("negative_prompt", "low quality, blurry, deformed anatomy, text, watermark")
    sampler = inputs("KSampler")
    sampler.update(
        steps=int(config.get("steps", 28)),
        cfg=float(config.get("cfg", 7.0)),
        seed=int(config["seed"]) if int(config.get("seed", -1)) >= 0 else int(time.time() * 1000) % 2147483647,
    )
    inputs("EmptyLatentImage").update(
        width=int(config.get("width", 768)),
        height=int(config.get("height", 768)),
        batch_size=1,
    )
    inputs("SaveImage")["filename_prefix"] = "AnimaStudio"
    return workflow


def generate(task):
    task_id = task["id"]
    original_config = dict(task["config"])
    original_config["_asset_id"] = task.get("asset_id")
    sizes = _sizes_for(original_config)
    print("Iniciando geração", task_id, "| perfil:",
          ("RX580-FP32" if _RX580_MODE else "padrão"),
          "| tamanhos:", sizes, flush=True)
    deadline = time.time() + int(os.getenv("COMFY_TASK_TIMEOUT", "1200"))
    for attempt, (width, height) in enumerate(sizes):
        config = dict(original_config, width=width, height=height)
        if _RX580_MODE:
            config["steps"] = min(24, int(config.get("steps", 24)))
        print("ComfyUI: etapa", attempt + 1, "de", len(sizes),
              "| difusão", width, "x", height, flush=True)
        response = requests.post(
            COMFY + "/prompt",
            json={"prompt": make_workflow(config), "client_id": str(uuid.uuid4())},
            timeout=60,
        )
        prompt_id = _prompt_response(response)
        print("ComfyUI aceitou a tarefa:", prompt_id, flush=True)
        retry_after_oom = False
        while time.time() < deadline:
            time.sleep(2)
            history_response = requests.get(COMFY + "/history/" + prompt_id, timeout=30)
            history_response.raise_for_status()
            record = history_response.json().get(prompt_id)
            if not record:
                continue
            if record.get("status", {}).get("status_str") == "error":
                reason = _execution_error(record)
                if _is_oom(reason) and attempt < len(sizes) - 1:
                    print("RX 580 sem VRAM no KSampler; liberando memória e "
                          "reduzindo automaticamente a resolução da difusão.", flush=True)
                    _clear_gpu_memory()
                    time.sleep(3)
                    retry_after_oom = True
                    break
                if _is_oom(reason):
                    raise RuntimeError(
                        "RX 580 sem VRAM mesmo com resolução reduzida: " + reason[:1100]
                    )
                raise RuntimeError(reason)
            images = [
                image
                for node_output in record.get("outputs", {}).values()
                for image in node_output.get("images", [])
            ]
            if not images:
                if record.get("status", {}).get("completed"):
                    raise RuntimeError("ComfyUI concluiu sem produzir imagem.")
                continue
            image_info = images[0]
            result = requests.get(COMFY + "/view", params=image_info, timeout=120)
            result.raise_for_status()
            if not result.content:
                raise RuntimeError("ComfyUI devolveu uma imagem vazia.")
            image_data = _image_for_upload(result.content, original_config)
            filename = pathlib.Path(image_info["filename"]).name
            local_path = OUT / (task_id + "_" + filename)
            local_path.write_bytes(image_data)
            upload = SESSION.post(
                SERVER + "/api/comfy/tasks/" + task_id + "/image",
                data=image_data,
                headers={"Content-Type": "application/octet-stream"},
                timeout=180,
            )
            upload.raise_for_status()
            report(task_id, "done",
                   "Imagem ComfyUI gerada e ampliada na CPU para o tamanho do episódio.",
                   upload.json()["image_url"])
            print("Imagem enviada à VPS:", local_path, flush=True)
            return
        if not retry_after_oom:
            raise TimeoutError("ComfyUI excedeu o limite para esta imagem.")
    raise RuntimeError("Todas as resoluções disponíveis falharam na RX 580.")



def _comfy_port_in_use():
    # Do not start a second ComfyUI while its listener is booting.
    try:
        with socket.create_connection(("127.0.0.1", 8188), timeout=1):
            return True
    except OSError:
        return False


def _autostart_comfyui():
    """Bounded Windows recovery: don't launch duplicate or infinite processes.

    Runs only after the actual local HTTP readiness check has failed.
    Requires the already-installed ComfyUI-ZLUDA launcher.
    """
    global _LAST_COMFY_START
    if not _COMFY_AUTOSTART or not _COMFY_LAUNCHER.is_file():
        return False
    now = time.monotonic()
    _COMFY_START_ATTEMPTS[:] = [
        item for item in _COMFY_START_ATTEMPTS
        if now - item < _COMFY_START_WINDOW_SECONDS
    ]
    if now - _LAST_COMFY_START < _COMFY_START_COOLDOWN_SECONDS:
        return False
    if len(_COMFY_START_ATTEMPTS) >= _COMFY_START_ATTEMPTS_LIMIT:
        # A GPU OOM or damaged ZLUDA environment should not start forever.
        return False
    if _comfy_port_in_use():
        return False
    _LAST_COMFY_START = now
    _COMFY_START_ATTEMPTS.append(now)
    try:
        subprocess.Popen(
            ["cmd.exe", "/k", str(_COMFY_LAUNCHER)],
            cwd=str(_COMFY_ROOT),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        print("ComfyUI estava desligado. Iniciando automaticamente "
              + str(_COMFY_LAUNCHER) + " em uma nova janela.", flush=True)
        return True
    except OSError as error:
        print("Não consegui iniciar ComfyUI automaticamente: "
              + str(error)[:260], flush=True)
        return False


def check_local_comfy():
    """Do not claim a GPU connection before the local HTTP server responds."""
    try:
        response = requests.get(COMFY + "/system_stats", timeout=10)
        response.raise_for_status()
        data = response.json()
        devices = data.get("devices") or []
        global _RX580_MODE, _DIRECTML_MODE
        force = os.getenv("ANIMA_RX580_MEMORY_PROFILE", "auto").strip().lower()
        names = " ".join(
            str(item.get("name") or "") + " " + str(item.get("type") or "")
            for item in devices if isinstance(item, dict)
        ).lower()
        _DIRECTML_MODE = ("privateuseone" in names or "directml" in names)
        requested_backend = os.getenv("ANIMA_GPU_BACKEND", "").strip().lower()
        if requested_backend == "directml" and not _DIRECTML_MODE:
            raise ValueError(
                "DirectML selecionado, mas a porta 8188 pertence ao ComfyUI "
                "ZLUDA ou a outro backend. Encerre essa instancia antes de iniciar DirectML."
            )
        _RX580_MODE = (
            force == "1" or force == "true"
            or (force not in {"0", "false"} and ("rx 580" in names or _DIRECTML_MODE))
        )
        if _DIRECTML_MODE:
            print("Motor DirectML ativo na GPU AMD. Operacoes de IA nao usam CUDA/ZLUDA.", flush=True)
        if _RX580_MODE:
            print("Perfil RX 580 ativo:", _profile_version(), flush=True)
            if _profile_version() == FP16_PROFILE_VERSION:
                print("UNet FP16 configurado no launcher. Esta opção requer ComfyUI "
                      "reiniciado e compatibilidade do ZLUDA; não é garantia de sucesso.", flush=True)
            else:
                print("FP32 ativo: este modo já excedeu a VRAM nas tentativas anteriores. "
                      "Use o ajuste reversível perfil-rx580-zluda.ps1 se desejar "
                      "testar UNet FP16.", flush=True)
        if devices:
            print("ComfyUI detectou dispositivo(s):", ", ".join(
                str(device.get("name") or device.get("type") or "sem nome")
                for device in devices if isinstance(device, dict)
            ), flush=True)
        _LOCAL_READY.set()
        return True
    except (requests.RequestException, ValueError) as error:
        _LOCAL_READY.clear()
        print(
            "ComfyUI local indisponível em " + COMFY
            + " (" + type(error).__name__ + ": " + str(error)[:300] + ").",
            flush=True,
        )
        print(
            "Abra o ComfyUI-ZLUDA primeiro e confirme no navegador "
            "http://127.0.0.1:8188/system_stats. "
            "Este agente tentará conectar novamente em 5 segundos.",
            flush=True,
        )
        _autostart_comfyui()
        return False


def main():
    print("Iniciando agente de imagens do Anima Studio.", flush=True)
    print("ComfyUI local:", COMFY, flush=True)
    print("VPS do Anima Studio:", SERVER, flush=True)
    if _COMFY_AUTOSTART:
        print("Inicialização automática do ComfyUI habilitada.", flush=True)
    was_ready = False
    next_health_check = 0.0
    while True:
        try:
            now = time.monotonic()
            if not was_ready or now >= next_health_check:
                if not check_local_comfy():
                    was_ready = False
                    main._registered = False
                    time.sleep(5)
                    continue
                next_health_check = time.monotonic() + 15
            if not was_ready:
                print("ComfyUI local respondeu com sucesso. Conectando ao Anima Studio...", flush=True)
                was_ready = True
            SESSION.post(
                SERVER + "/api/comfy/heartbeat",
                params={"worker_id": WORKER, "profile_version": _profile_version()}, timeout=20,
            ).raise_for_status()
            _ensure_heartbeat()
            if not getattr(main, "_registered", False):
                print("Agente conectado à VPS: pronto para receber imagens.", flush=True)
                main._registered = True
            response = SESSION.get(
                SERVER + "/api/comfy/next",
                params={"worker_id": WORKER}, timeout=35,
            )
            response.raise_for_status()
            task = response.json().get("task")
            if not task:
                continue
            try:
                generate(task)
            except Exception as error:
                try:
                    report(task["id"], "failed", f"{type(error).__name__}: {error}")
                except requests.RequestException as upload_error:
                    print("Falha ao reportar erro à VPS:", upload_error, flush=True)
                print("Falha na geração da imagem:", type(error).__name__, str(error)[:400], flush=True)
        except KeyboardInterrupt:
            print("Agente encerrado pelo operador.", flush=True)
            raise
        except requests.RequestException as error:
            main._registered = False
            print(
                "Falha de comunicação com a VPS ("
                + type(error).__name__ + "): " + str(error)[:450],
                flush=True,
            )
            print(
                "Confira ANIMA_STUDIO_URL, HTTPS, ANIMA_COMFY_TOKEN "
                "e se a aplicação animacao2d está ativa.",
                flush=True,
            )
            time.sleep(5)
        except Exception as error:
            main._registered = False
            print(
                "Falha no agente (" + type(error).__name__ + "): "
                + str(error)[:450], flush=True
            )
            time.sleep(5)

if __name__ == "__main__":
    main()
