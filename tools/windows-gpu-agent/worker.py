#!/usr/bin/env python3
"""Anima Studio authenticated Windows render worker (pull model)."""
import argparse
import threading
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

def request_json(base, route, token, method="GET", payload=None, timeout=35):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(base.rstrip("/") + route, data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

def upload_zip(base, route, token, path):
    """Upload a ZIP in small retryable chunks to survive reverse-proxy limits."""
    chunk_size = 8 * 1024 * 1024
    file_size = pathlib.Path(path).stat().st_size
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    if total_chunks < 1:
        raise RuntimeError("Pacote ZIP vazio.")

    def send_chunk(index, chunk):
        url = base.rstrip("/") + route + "/chunks/" + str(index)
        last_error = None
        for attempt in range(5):
            req = urllib.request.Request(url, data=chunk, method="POST",
                headers={"Authorization": "Bearer " + token,
                         "Content-Type": "application/octet-stream"})
            try:
                with urllib.request.urlopen(req, timeout=120) as response:
                    response.read()
                return
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt == 4:
                    break
                delay = min(20, 2 ** attempt)
                print("ANIMA_UPLOAD_RETRY chunk=" + str(index) +
                      " attempt=" + str(attempt + 1) + " wait=" + str(delay) +
                      "s error=" + str(exc), flush=True)
                time.sleep(delay)
        raise RuntimeError("Falha ao enviar bloco " + str(index) +
                           "/" + str(total_chunks) + ": " + str(last_error))

    with pathlib.Path(path).open("rb") as source:
        for index in range(total_chunks):
            chunk = source.read(chunk_size)
            if not chunk:
                raise RuntimeError("Arquivo ZIP terminou antes do esperado.")
            send_chunk(index, chunk)
            print("ANIMA_UPLOAD_PROGRESS " + str(index + 1) + "/" +
                  str(total_chunks), flush=True)

    result = request_json(base, route + "/finalize", token, method="POST",
                          payload={"total_chunks": total_chunks}, timeout=120)
    if result.get("status") != "done":
        raise RuntimeError("VPS não confirmou a montagem do ZIP: " + str(result))
    return result

def main():
    parser = argparse.ArgumentParser(description="Anima Studio 3D RX580 worker")
    parser.add_argument("--server", default=os.getenv("ANIMA_WORKER_SERVER", ""))
    parser.add_argument("--token", default=os.getenv("ANIMA_WORKER_TOKEN", ""))
    parser.add_argument("--blender", default=os.getenv("ANIMA_BLENDER_PATH",
        r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"))
    parser.add_argument("--scene-script", default=os.getenv("ANIMA_SCENE_SCRIPT",
        str(pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "blender_scene.py")))
    parser.add_argument("--worker-id", default=os.getenv("ANIMA_WORKER_ID", "windows-rx580"))
    args = parser.parse_args()
    if not args.server or not args.token:
        parser.error("Configure --server e --token (ou ANIMA_WORKER_SERVER / ANIMA_WORKER_TOKEN).")
    blender = pathlib.Path(args.blender)
    script = pathlib.Path(args.scene_script)
    if not blender.is_file():
        parser.error("Blender não encontrado: " + str(blender))
    if not script.is_file():
        parser.error("blender_scene.py não encontrado: " + str(script))
    print("ANIMA_WORKER_ONLINE " + args.worker_id, flush=True)
    def heartbeat_loop():
        while True:
            try:
                request_json(args.server, "/api/worker/heartbeat?worker_id=" + args.worker_id,
                             args.token, method="POST", timeout=15)
            except Exception as exc:
                print("ANIMA_WORKER_HEARTBEAT: " + str(exc), flush=True)
            time.sleep(20)
    threading.Thread(target=heartbeat_loop, name="anima-worker-heartbeat", daemon=True).start()
    while True:
        try:
            result = request_json(args.server, "/api/worker/next?worker_id=" + args.worker_id,
                                  args.token, timeout=30)
            task = result.get("task")
            if not task:
                continue
            task_id = task["id"]
            print("ANIMA_WORKER_TASK " + task_id, flush=True)
            try:
                with tempfile.TemporaryDirectory(prefix="anima-rx580-") as temp:
                    root = pathlib.Path(temp)
                    frames = root / "frames"
                    frames.mkdir()
                    config = dict(task["config"])
                    config["frames_dir"] = str(frames.resolve())
                    config_path = root / "config.json"
                    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
                    env = os.environ.copy()
                    env.setdefault("ANIMA_EEVEE_SAMPLES", "8")
                    env.setdefault("ANIMA_RENDER_SCALE", "100")
                    env.setdefault("ANIMA_BLENDER_THREADS", "6")
                    command = [str(blender), "--background", "--factory-startup",
                               "--python-exit-code", "1", "--python", str(script),
                               "--", "--config", str(config_path)]
                    log_path = root / "blender.log"
                    with log_path.open("w", encoding="utf-8", errors="replace") as log:
                        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", env=env)
                        for line in proc.stdout:
                            print(line.rstrip(), flush=True)
                            log.write(line)
                        code = proc.wait()
                    expected = int(config["total_frames"])
                    actual = len(list(frames.glob("frame-*.png")))
                    if code != 0 or actual != expected:
                        raise RuntimeError("Blender exit=" + str(code) +
                            "; quadros=" + str(actual) + "/" + str(expected) +
                            "; log=" + log_path.read_text(encoding="utf-8", errors="replace")[-3000:])
                    archive = root / "frames.zip"
                    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
                        for frame in sorted(frames.glob("frame-*.png")):
                            zf.write(frame, frame.name)
                    upload_zip(args.server, "/api/worker/tasks/" + task_id,
                               args.token, archive)
                    print("ANIMA_WORKER_DONE " + task_id + " (" + str(actual) + " frames)", flush=True)
            except Exception as exc:
                try:
                    request_json(args.server, "/api/worker/tasks/" + task_id + "/fail",
                                 args.token, method="POST", payload={"error": str(exc)})
                except Exception:
                    pass
                print("ANIMA_WORKER_ERROR " + task_id + ": " + str(exc), flush=True)
        except KeyboardInterrupt:
            print("ANIMA_WORKER_STOPPED", flush=True)
            return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print("ANIMA_WORKER_CONNECTION: " + str(exc), flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
