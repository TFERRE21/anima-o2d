#!/usr/bin/env python3
"""Anima Studio authenticated Windows render worker (pull model)."""
import argparse
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
    req = urllib.request.Request(base.rstrip("/") + route, data=pathlib.Path(path).read_bytes(),
        method="POST", headers={"Authorization": "Bearer " + token,
        "Content-Type": "application/zip"})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))

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
                    upload_zip(args.server, "/api/worker/tasks/" + task_id + "/complete",
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
