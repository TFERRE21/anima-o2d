"""Anima Studio ComfyUI image-generation worker (Windows)."""
import json
import os
import pathlib
import threading
import time
import uuid

import requests

SERVER = os.environ["ANIMA_STUDIO_URL"].rstrip("/")
TOKEN = os.environ["ANIMA_COMFY_TOKEN"]
COMFY = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
WORKER = os.getenv("ANIMA_COMFY_WORKER_ID", os.getenv("COMPUTERNAME", "windows") + "-comfyui")
ROOT = pathlib.Path(__file__).resolve().parent
WF = pathlib.Path(os.getenv("COMFYUI_API_WORKFLOW", str(ROOT / "workflow_api.json")))
OUT = pathlib.Path(os.getenv("ANIMA_COMFY_OUTPUT", str(ROOT / "generated")))
OUT.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.headers["Authorization"] = "Bearer " + TOKEN
_HEARTBEAT_THREAD = None


def _heartbeats_while_rendering():
    """Keep the VPS worker marked online while a slow RX 580 draws a frame."""
    was_connected = True
    while True:
        try:
            reply = requests.post(
                SERVER + "/api/comfy/heartbeat",
                params={"worker_id": WORKER},
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
        json={"status": status, "message": str(message)[:2000], "output": output},
        timeout=30,
    )
    response.raise_for_status()


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
    print("Iniciando geração da imagem", task_id, flush=True)
    response = requests.post(
        COMFY + "/prompt",
        json={"prompt": make_workflow(task["config"]), "client_id": str(uuid.uuid4())},
        timeout=60,
    )
    prompt_id = _prompt_response(response)
    print("ComfyUI aceitou a tarefa; identificador:", prompt_id, flush=True)
    deadline = time.time() + int(os.getenv("COMFY_TASK_TIMEOUT", "900"))
    while time.time() < deadline:
        time.sleep(2)
        history = requests.get(COMFY + "/history/" + prompt_id, timeout=30).json()
        record = history.get(prompt_id)
        if not record:
            continue
        if record.get("status", {}).get("status_str") == "error":
            raise RuntimeError(_execution_error(record))
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
        image_data = requests.get(COMFY + "/view", params=image_info, timeout=120).content
        if not image_data:
            raise RuntimeError("ComfyUI devolveu uma imagem vazia.")
        filename = pathlib.Path(image_info["filename"]).name
        local_path = OUT / f"{task_id}_{filename}"
        local_path.write_bytes(image_data)
        upload = SESSION.post(
            f"{SERVER}/api/comfy/tasks/{task_id}/image",
            data=image_data,
            headers={"Content-Type": "application/octet-stream"},
            timeout=180,
        )
        upload.raise_for_status()
        report(task_id, "done", "Imagem gerada pelo ComfyUI e enviada ao Anima Studio.", upload.json()["image_url"])
        print("Imagem gerada:", local_path, flush=True)
        return
    raise TimeoutError("ComfyUI excedeu o limite de 15 minutos para esta imagem.")


def check_local_comfy():
    """Do not claim a GPU connection before the local HTTP server responds."""
    try:
        response = requests.get(COMFY + "/system_stats", timeout=10)
        response.raise_for_status()
        data = response.json()
        devices = data.get("devices") or []
        if devices:
            print("ComfyUI detectou dispositivo(s):", ", ".join(
                str(device.get("name") or device.get("type") or "sem nome")
                for device in devices if isinstance(device, dict)
            ), flush=True)
        return True
    except (requests.RequestException, ValueError) as error:
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
        return False


def main():
    print("Iniciando agente de imagens do Anima Studio.", flush=True)
    print("ComfyUI local:", COMFY, flush=True)
    print("VPS do Anima Studio:", SERVER, flush=True)
    was_ready = False
    while True:
        try:
            if not was_ready and not check_local_comfy():
                time.sleep(5)
                continue
            if not was_ready:
                print("ComfyUI local respondeu com sucesso. Conectando ao Anima Studio...", flush=True)
                was_ready = True
            SESSION.post(
                SERVER + "/api/comfy/heartbeat",
                params={"worker_id": WORKER}, timeout=20,
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
