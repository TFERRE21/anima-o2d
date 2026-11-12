"""Anima Studio ComfyUI image-generation worker (Windows)."""
import json
import os
import pathlib
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

    checkpoint = config.get("checkpoint", "").strip()
    if checkpoint:
        inputs("CheckpointLoaderSimple")["ckpt_name"] = checkpoint
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
    prompt_id = requests.post(
        COMFY + "/prompt",
        json={"prompt": make_workflow(task["config"]), "client_id": str(uuid.uuid4())},
        timeout=60,
    ).json()["prompt_id"]
    deadline = time.time() + int(os.getenv("COMFY_TASK_TIMEOUT", "900"))
    while time.time() < deadline:
        time.sleep(2)
        history = requests.get(COMFY + "/history/" + prompt_id, timeout=30).json()
        record = history.get(prompt_id)
        if not record:
            continue
        if record.get("status", {}).get("status_str") == "error":
            raise RuntimeError("ComfyUI marcou a execução como erro.")
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


def main():
    print("Anima Studio / ComfyUI conectado:", COMFY, flush=True)
    requests.get(COMFY + "/system_stats", timeout=15).raise_for_status()
    while True:
        try:
            SESSION.post(SERVER + "/api/comfy/heartbeat", params={"worker_id": WORKER}, timeout=20).raise_for_status()
            response = SESSION.get(SERVER + "/api/comfy/next", params={"worker_id": WORKER}, timeout=35)
            response.raise_for_status()
            task = response.json().get("task")
            if not task:
                continue
            try:
                generate(task)
            except Exception as error:
                report(task["id"], "failed", f"{type(error).__name__}: {error}")
                print("Falha na tarefa:", error, flush=True)
        except KeyboardInterrupt:
            raise
        except Exception as error:
            print("Falha de conexão/ComfyUI:", error, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
