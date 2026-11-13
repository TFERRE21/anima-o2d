from __future__ import annotations

import re
import asyncio
import json
import math
import os
import queue
import threading
import urllib.request
import urllib.error
import zipfile
import time
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable
from PIL import Image
from backend.app.runtime import find_blender_runtime

FPS = 24
def _ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg não encontrado. Instale imageio-ffmpeg ou FFmpeg no sistema.") from exc

def _run(cmd):
    command = list(cmd)
    if command and command[0] == "ffmpeg":
        command[0] = _ffmpeg_executable()
    p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-1800:])
    return p


def _run_ffmpeg_with_progress(cmd, progress_callback, total_seconds: float):
    command=list(cmd)
    if command and command[0]=="ffmpeg":
        command[0]=_ffmpeg_executable()
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    last_percent=-1
    try:
        if process.stdout:
            for line in process.stdout:
                if "=" not in line:
                    continue
                key,value=line.strip().split("=",1)
                if key=="out_time_ms":
                    try:
                        current_seconds=int(value)/1_000_000
                    except ValueError:
                        continue
                    percent=max(0,min(100,int(current_seconds/max(.1,total_seconds)*100)))
                    if progress_callback:
                        mapped=95+int(percent*.04)
                        if mapped>last_percent:
                            last_percent=mapped
                            progress_callback(mapped,"Codificando MP4 1080p: "+str(percent)+"%")
        stderr=process.stderr.read() if process.stderr else ""
        code=process.wait()
        if code:
            raise RuntimeError(stderr[-1800:])
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

def _probe_duration(path: Path) -> float:
    """Measure duration even when the runtime has FFmpeg but no separate ffprobe."""
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Arquivo de mídia ausente ou vazio: " + str(path.name))
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            try:
                duration = float(result.stdout.strip())
                if duration > 0:
                    return duration
            except ValueError:
                pass
    try:
        from mutagen import File as MutagenFile
        media = MutagenFile(str(path))
        duration = float(media.info.length) if media and media.info else 0.0
        if duration > 0:
            return duration
    except Exception:
        pass

    # The portable imageio-ffmpeg package ships ffmpeg but not ffprobe.
    # FFmpeg prints container/stream duration as soon as it opens the file.
    process = subprocess.Popen(
        [_ffmpeg_executable(), "-hide_banner", "-i", str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, errors="replace"
    )
    details = []
    try:
        if process.stderr:
            for line in process.stderr:
                details.append(line.strip())
                match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
                if match:
                    hours, minutes, seconds = match.groups()
                    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                    process.terminate()
                    process.wait(timeout=3)
                    if duration > 0:
                        return duration
                    break
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    raise RuntimeError(
        "Não foi possível medir a duração de " + path.name +
        ". FFmpeg informou: " + " | ".join(details[-4:])
    )


DEFAULT_VOICE_PROFILE = {
    "Narrador": {"voice": "pt-BR-ThalitaMultilingualNeural", "rate": "+0%", "pitch": "+0Hz", "espeak_pitch": 48},
    "Luna": {"voice": "pt-BR-FranciscaNeural", "rate": "+2%", "pitch": "+5Hz", "espeak_pitch": 60},
    "Tomi": {"voice": "pt-BR-AntonioNeural", "rate": "+0%", "pitch": "-3Hz", "espeak_pitch": 43},
    "Pipo": {"voice": "pt-BR-AntonioNeural", "rate": "+8%", "pitch": "+22Hz", "espeak_pitch": 76},
    "Moradora": {"voice": "pt-BR-ThalitaMultilingualNeural", "rate": "+4%", "pitch": "+8Hz", "espeak_pitch": 66},
}
VOICE_PROFILE_FILE = Path(os.getenv("ANIMA_STORAGE", "/data/jobs")) / "voice-profiles.json"


def load_voice_profiles() -> dict:
    """Persist one stable cast voice map so every episode reuses the same identities."""
    profiles = {key: dict(value) for key, value in DEFAULT_VOICE_PROFILE.items()}
    try:
        VOICE_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if VOICE_PROFILE_FILE.exists():
            saved = json.loads(VOICE_PROFILE_FILE.read_text(encoding="utf-8"))
            needs_upgrade = False
            for name in profiles:
                if isinstance(saved.get(name), dict):
                    profiles[name].update(saved[name])
                else:
                    needs_upgrade = True
            if needs_upgrade:
                VOICE_PROFILE_FILE.write_text(
                    json.dumps(profiles, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        else:
            VOICE_PROFILE_FILE.write_text(
                json.dumps(profiles, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except (OSError, json.JSONDecodeError, TypeError):
        # A read-only volume should not prevent preview or rendering.
        pass
    return profiles


VOICE_PROFILE = load_voice_profiles()


async def _edge_tts_save(text: str, output: Path, speaker: str = "Narrador") -> None:
    import edge_tts
    profile = VOICE_PROFILE.get(speaker, VOICE_PROFILE["Narrador"])
    communicate = edge_tts.Communicate(
        text=text,
        voice=profile["voice"],
        rate=profile["rate"],
        volume="+0%",
        pitch=profile["pitch"],
    )
    await communicate.save(str(output))


def _concat_audio_files(files: list[Path], output: Path, audio_codec: str) -> Path:
    if not files:
        raise RuntimeError("O roteiro não possui falas para sintetizar.")
    manifest = output.parent / (output.stem + "-concat.txt")
    def quote_path(path: Path) -> str:
        return path.resolve().as_posix().replace("'", "'\\''")
    manifest.write_text(
        "".join("file '" + quote_path(item) + "'\n" for item in files),
        encoding="utf-8"
    )
    if audio_codec == "pcm_s16le":
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", str(manifest), "-c:a", "pcm_s16le", str(output)])
    else:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", str(manifest), "-c:a", "aac", "-b:a", "160k", str(output)])
    if not output.exists() or output.stat().st_size < 1000:
        raise RuntimeError("Não foi possível montar as falas dos personagens.")
    return output


async def _synthesize_edge_segments(segments: list[dict], files: list[Path], progress_callback=None) -> None:
    semaphore = asyncio.Semaphore(2)
    completed = 0

    async def render_one(segment: dict, path: Path):
        nonlocal completed
        text = str(segment.get("text", "")).strip()
        speaker = str(segment.get("speaker", "Narrador"))
        if not text:
            raise RuntimeError("Foi encontrada uma fala vazia no roteiro.")
        async with semaphore:
            last_error = None
            for attempt in range(2):
                try:
                    await asyncio.wait_for(_edge_tts_save(text, path, speaker), timeout=45)
                    if path.exists() and path.stat().st_size > 500:
                        completed += 1
                        if progress_callback:
                            progress_callback(int(completed * 10 / max(1, len(files))), f"Gerando falas: {completed}/{len(files)}")
                        return
                    raise RuntimeError("O serviço de voz retornou um arquivo vazio.")
                except Exception as exc:
                    last_error = exc
                    if attempt < 1:
                        await asyncio.sleep(1.5)
            raise RuntimeError(f"Falha na voz de {speaker}: {last_error}")

    await asyncio.gather(*(render_one(segment, path) for segment, path in zip(segments, files)))


def _synthesize_segments(segments: list[dict], workdir: Path, fmt: str,
                         speech_rate: int, progress_callback=None) -> tuple[Path, Path, list[dict]]:
    """Create one continuous track by alternating narrator and distinct character voices."""
    suffix = fmt.replace(":", "x")
    use_espeak = bool(shutil.which("espeak-ng"))
    extension = "wav" if use_espeak else "mp3"
    parts_dir = workdir / f"voice-parts-{suffix}"
    parts_dir.mkdir(parents=True, exist_ok=True)
    files = [
        parts_dir / f"part-{index:03d}.{extension}"
        for index in range(len(segments))
    ]

    if use_espeak:
        for segment, path in zip(segments, files):
            speaker = str(segment.get("speaker", "Narrador"))
            profile = VOICE_PROFILE.get(speaker, VOICE_PROFILE["Narrador"])
            pitch = int(profile["espeak_pitch"])
            rate = speech_rate + (8 if speaker == "Pipo" else 0)
            _run([
                "espeak-ng", "-v", "pt-br", "-s", str(rate), "-p", str(pitch),
                "-a", "165", "-w", str(path), str(segment.get("text", ""))
            ])
            if progress_callback:
                progress_callback(int((len(files) and (files.index(path) + 1) * 10 / len(files)) or 0), f"Gerando falas: {files.index(path) + 1}/{len(files)}")
    else:
        try:
            asyncio.run(_synthesize_edge_segments(segments, files, progress_callback))
        except Exception as exc:
            raise RuntimeError(
                "Não foi possível gerar as falas com voz neural. Verifique a conexão de saída "
                "do servidor e a disponibilidade do Edge TTS: " + str(exc)
            ) from exc

    raw = workdir / f"narration-source-{suffix}.{'wav' if use_espeak else 'm4a'}"
    fitted = workdir / f"narration-final-{suffix}.{'wav' if use_espeak else 'm4a'}"
    timeline = []
    cursor = 0.0
    for segment, part in zip(segments, files):
        part_duration = _probe_duration(part)
        timeline.append({
            "start": cursor,
            "end": cursor + part_duration,
            "speaker": str(segment.get("speaker", "Narrador")),
            "scene": int(segment.get("scene", -1)),
        })
        cursor += part_duration
    _concat_audio_files(files, raw, "pcm_s16le" if use_espeak else "aac")
    if progress_callback:
        progress_callback(12, "Áudio das personagens montado. Preparando animação.")
    return raw, fitted, timeline


def _synthesize_narration(text: str, workdir: Path, fmt: str, speech_rate: int):
    # Backward-compatible route for jobs generated before character dialogue was added.
    return _synthesize_segments([{"speaker": "Narrador", "text": text}], workdir, fmt, speech_rate)


def _fit_narration(source: Path, output: Path, target_seconds: float) -> float:
    """Stretch/compress narration only as needed to satisfy the format duration contract."""
    actual = _probe_duration(source)
    if actual <= 0:
        raise RuntimeError("A narração foi gerada vazia.")
    factor = actual / target_seconds
    if 0.96 <= factor <= 1.04:
        output.write_bytes(source.read_bytes())
        return _probe_duration(output)
    factor = min(2.0, max(0.5, factor))
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
          "-filter:a", f"atempo={factor:.5f}", "-ar", "44100", str(output)])
    return _probe_duration(output)

def _render_blender_frames_remote(frames: Path, config: dict, progress_callback=None) -> None:
    """Send the real Blender scene to an authenticated pull worker and collect PNGs."""
    base = os.getenv("ANIMA_WORKER_API_URL", "http://127.0.0.1:5000").rstrip("/")
    token = os.getenv("ANIMA_WORKER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Render remoto selecionado, mas ANIMA_WORKER_TOKEN não está configurado na VPS.")
    def call(route: str, method="GET", payload=None, timeout=30):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(base + route, data=data, method=method,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    created = call("/api/worker/tasks", "POST", {"config": config})
    task_id = created["task_id"]
    if progress_callback:
        progress_callback(18, "Trabalho enviado ao computador RX 580. Aguardando renderização.")
    started = time.monotonic()
    timeout_seconds = int(os.getenv("ANIMA_REMOTE_WORKER_TIMEOUT", "10800"))
    while time.monotonic() - started < timeout_seconds:
        status = call("/api/worker/tasks/" + task_id, timeout=30)
        if status.get("status") == "failed":
            raise RuntimeError("Worker RX 580 falhou: " + str(status.get("error", "erro sem detalhes")))
        if status.get("status") == "done":
            archive_path = Path(status["result_path"])
            if not archive_path.is_file():
                raise RuntimeError("Pacote de quadros não encontrado na VPS.")
            frames.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path, "r") as archive:
                names = archive.namelist()
                expected = int(config["total_frames"])
                valid = [name for name in names if Path(name).name == name and
                         name.startswith("frame-") and name.endswith(".png")]
                if len(valid) != expected:
                    raise RuntimeError(f"Pacote RX 580 contém {len(valid)} de {expected} quadros.")
                for name in valid:
                    (frames / Path(name).name).write_bytes(archive.read(name))
            if progress_callback:
                progress_callback(92, "Quadros recebidos do computador RX 580. Preparando o vídeo.")
            return
        time.sleep(3)
    raise RuntimeError(f"Tempo limite aguardando o worker RX 580 ({timeout_seconds}s).")


def _render_blender_frames(frames: Path, fmt: str, width: int, height: int,
                          total_frames: int, scene_list: list, scene_source_indices: list,
                          plan: dict, voice_timeline: list, progress_callback=None,
                          capture_fps: float = FPS) -> None:
    remote_worker = False  # Production now uses the installed Blender binary in the 3D Cartoon runtime.
    runtime = find_blender_runtime()
    if not runtime and not remote_worker:
        raise RuntimeError(
            "Motor Blender 3D ausente. Instale o executável Blender no container "
            "ou disponibilize o executável Blender; não existe renderizador alternativo."
        )
    script = Path(__file__).with_name("blender_scene.py")
    if not script.is_file():
        raise RuntimeError(f"Arquivo 3D obrigatório não encontrado: {script}")
    if frames.exists():
        shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True, exist_ok=True)
    config_path = frames.parent / f"blender-config-{fmt.replace(':', 'x')}.json"
    config = {
        "format": fmt,
        "resolution": [int(width), int(height)],
        "fps": float(capture_fps),
        "total_frames": int(total_frames),
        "frames_dir": str(frames.resolve()),
        "scenes": [
            {
                "title": str(scene_list[index][0]),
                "caption": str(scene_list[index][1]),
                "visual_action": str(scene_list[index][2]),
                "action": str(
                    (plan.get("scenes") or [{}])[source_index].get("action", "")
                ),
            }
            for index, source_index in enumerate(scene_source_indices)
        ],
        "scene_source_indices": [int(x) for x in scene_source_indices],
        "story_plan": {
            "planet": plan.get("planet", "Unknown planet"),
            "biome": plan.get("biome", ""),
            "mission_object": plan.get("mission_object", ""),
            "landmark": plan.get("landmark", ""),
            "inhabitants": plan.get("inhabitants", ""),
            "palette": plan.get("palette", ""),
        },
        "voice_timeline": voice_timeline,
    }
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    # New attempt: do not show a stale frame from an earlier failed render.
    (frames.parent / f"preview-{fmt.replace(':', 'x')}.jpg").unlink(missing_ok=True)
    render_log_path = frames.parent / f"render-log-{fmt.replace(':', 'x')}.txt"
    render_log_path.write_text("ANIMA: starting new Cartoon 3D render\n", encoding="utf-8")
    if remote_worker:
        _render_blender_frames_remote(frames, config, progress_callback)
        return
    if runtime["backend"] == "binary":
        command = [
            runtime["executable"], "--background", "--factory-startup",
            "--python-exit-code", "1", "--python", str(script),
            "--", "--config", str(config_path),
        ]
    else:
        # Run the official Blender Python module inside the exact CPython
        # version used by the app (Python 3.13 in the current container).
        # Start with -c so Python keeps the application working directory
        # at sys.path[0]. Executing the .py file directly moves its directory
        # to sys.path[0], which can hide bpy's native _bpy extension in some
        # container layouts. Import bpy first, then execute the scene script.
        bootstrap = (
            "import bpy, runpy, sys; "
            "print('ANIMA_BLENDER_BACKEND:python-module', flush=True); "
            "script=sys.argv[1]; "
            "sys.argv=[script, *sys.argv[2:]]; "
            "runpy.run_path(script, run_name='__main__')"
        )
        command = [
            sys.executable, "-c", bootstrap, str(script),
            "--module", "--config", str(config_path)
        ]
    xvfb = shutil.which("xvfb-run")
    if xvfb:
        command = [xvfb, "-a"] + command
    env = os.environ.copy()
    env.setdefault("BLENDER_USER_CONFIG", str(frames.parent / "blender-user-config"))
    env.setdefault("OMP_NUM_THREADS", "4")
    if runtime["backend"] == "python-module":
        # bpy can be importable in the API process but absent in a child process
        # when the panel starts Python with a customized sys.path. Forward the
        # exact import paths used by this process to the Blender worker.
        inherited_paths = [entry for entry in sys.path if entry]
        existing_paths = [entry for entry in env.get("PYTHONPATH", "").split(os.pathsep) if entry]
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(inherited_paths + existing_paths))
        probe = subprocess.run(
            [sys.executable, "-c", "import bpy; print(bpy.app.version_string)"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        if probe.returncode:
            raise RuntimeError(
                "O processo da API encontrou bpy, mas o worker Python não conseguiu importar "
                "o módulo Blender. Executável=" + sys.executable +
                "; sys.path=" + repr(inherited_paths[-8:]) +
                "; erro=" + (probe.stderr or probe.stdout)[-1200:]
            )
        print("ANIMA_BLENDER_WORKER_READY: " + probe.stdout.strip(), flush=True)
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", bufsize=1, env=env,
    )
    tail: list[str] = []
    lines: queue.Queue = queue.Queue()

    def collect_output():
        try:
            if process.stdout:
                for output_line in process.stdout:
                    lines.put(output_line.rstrip())
        finally:
            lines.put(None)

    reader = threading.Thread(target=collect_output, name="anima-blender-log-reader", daemon=True)
    reader.start()
    last_output = time.monotonic()
    last_heartbeat = 0.0
    last_preview_written = 0.0
    highest_reported_progress = 18
    idle_timeout = int(os.getenv("ANIMA_BLENDER_IDLE_TIMEOUT", "900"))
    total_timeout = int(os.getenv("ANIMA_BLENDER_TOTAL_TIMEOUT", "10800"))
    first_frame_timeout = max(60, int(os.getenv("ANIMA_FIRST_FRAME_TIMEOUT", "360")))
    started = time.monotonic()
    try:
        finished_reading = False
        while not finished_reading:
            try:
                line = lines.get(timeout=15)
            except queue.Empty:
                elapsed = time.monotonic() - started
                idle = time.monotonic() - last_output
                if process.poll() is not None and not reader.is_alive():
                    break
                if elapsed > first_frame_timeout and not next(frames.glob("frame-*.png"), None):
                    raise RuntimeError(
                        f"Blender não produziu o primeiro quadro após {int(elapsed)}s. "
                        "O renderizador 3D da VPS está travado ou lento demais; "
                        "verifique render-log-9x16.txt/16x9.txt, OpenGL e RAM. "
                        "Defina ANIMA_3D_RENDER_MODE=workbench se estiver usando Eevee sem GPU."
                    )
                if elapsed > total_timeout:
                    raise RuntimeError(
                        f"Tempo máximo de renderização Blender excedido ({total_timeout}s). "
                        "O processo foi encerrado para liberar o worker."
                    )
                if idle > idle_timeout:
                    raise RuntimeError(
                        f"Blender sem produzir logs/progresso por {idle_timeout}s. "
                        "Últimas mensagens: " + " | ".join(tail[-8:])
                    )
                if progress_callback and time.monotonic() - last_heartbeat >= 30:
                    last_heartbeat = time.monotonic()
                    rendered_count = len(list(frames.glob("frame-*.png")))
                    if rendered_count:
                        mapped_frames = 18 + int(73 * rendered_count / max(1, total_frames))
                        highest_reported_progress = max(highest_reported_progress, min(91, mapped_frames))
                    progress_callback(
                        highest_reported_progress,
                        f"Blender trabalhando na montagem/renderização 3D; "
                        f"{rendered_count}/{total_frames} quadros disponíveis; "
                        f"última saída há {int(idle)}s."
                    )
                continue
            if line is None:
                finished_reading = True
                continue
            last_output = time.monotonic()
            if line:
                tail.append(line)
                if len(tail) > 40:
                    tail.pop(0)
                print("ANIMA_BLENDER_LOG: " + line, flush=True)
                with render_log_path.open("a", encoding="utf-8") as audit:
                    audit.write(line + "\n")
            # Every saved Blender PNG can update the existing live preview endpoint.
            # Publish atomically so the web dashboard never reads a partial JPEG.
            if "Saved:" in line and "frame-" in line:
                match = re.search(r"(frame-\d{6}\.png)", line)
                if match and time.monotonic() - last_preview_written >= 2:
                    source = frames / match.group(1)
                    if source.is_file():
                        preview_path = frames.parent / f"preview-{fmt.replace(':', 'x')}.jpg"
                        temporary = preview_path.with_suffix(".partial.jpg")
                        try:
                            with Image.open(source) as still:
                                still = still.convert("RGB")
                                still.thumbnail((480, 854) if fmt == "9:16" else (854, 480))
                                still.save(temporary, format="JPEG", quality=80)
                            os.replace(temporary, preview_path)
                            last_preview_written = time.monotonic()
                        except (OSError, ValueError) as exc:
                            print("ANIMA_PREVIEW_WARNING: " + str(exc), flush=True)
            if line.startswith("ANIMA_PROGRESS:"):
                try:
                    _, pct, message = line.split(":", 2)
                    if progress_callback:
                        mapped = 14 + int(float(pct) * 0.77)
                        highest_reported_progress = max(highest_reported_progress, mapped)
                        progress_callback(highest_reported_progress, message)
                except (ValueError, TypeError):
                    pass
            elif line.startswith("ANIMA_BOOT:"):
                if progress_callback:
                    highest_reported_progress = max(highest_reported_progress, 16)
                    progress_callback(highest_reported_progress, line.replace("ANIMA_BOOT:", "").strip())
        code = process.wait(timeout=30)
        if code:
            raise RuntimeError("Blender 3D falhou: " + " | ".join(tail[-12:]))
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        if process.stdout:
            process.stdout.close()
    png_frames = list(frames.glob("frame-*.png"))
    if len(png_frames) != total_frames:
        raise RuntimeError(
            f"Renderizador 3D gerou {len(png_frames)} de {total_frames} quadros."
        )
    if progress_callback:
        progress_callback(92, "Cenas 3D renderizadas. Preparando o vídeo.")



def render_episode(title: str, story: str, fmt: str, output: Path, workdir: Path,
                   planet_name: str = "Aurora-7", story_plan: dict | None = None,
                   progress_callback: Callable[[int, str], None] | None = None):
    """Render separate long-form and vertical-short edits from one approved story plan."""
    plan = story_plan or {}
    portrait = fmt == "9:16"
    if fmt not in {"16:9", "9:16"}:
        raise ValueError("Formato de renderização não reconhecido.")

    # Horizontal episodes are kept between 5 and 10 minutes; Shorts are
    # a focused highlight (clue -> twist -> team solution), not a recap.
    if portrait:
        narration_text = plan.get("short_script") or story
        audio_segments = plan.get("audio_segments_short") or [{"speaker": "Narrador", "text": narration_text}]
        speech_rate = 145
        min_duration, max_duration, target_duration = 60.0, 88.5, 75.0
    else:
        narration_text = plan.get("long_script") or story
        audio_segments = plan.get("audio_segments_long") or [{"speaker": "Narrador", "text": narration_text}]
        speech_rate = 140
        min_duration, max_duration, target_duration = 301.0, 598.5, 420.0

    if progress_callback:
        progress_callback(1, "Preparando vozes e diálogos dos personagens.")
    voice_raw, voice_fit, voice_timeline = _synthesize_segments(audio_segments, workdir, fmt, speech_rate, progress_callback)
    initial_duration = _probe_duration(voice_raw)
    if progress_callback:
        progress_callback(14, "Vozes prontas. Ajustando duração e cenas.")

    if portrait:
        if initial_duration < min_duration or initial_duration > max_duration:
            fitted_duration = _fit_narration(voice_raw, voice_fit, target_duration)
        else:
            voice_fit.write_bytes(voice_raw.read_bytes())
            fitted_duration = _probe_duration(voice_fit)
        if not (min_duration <= fitted_duration <= max_duration):
            raise RuntimeError(
                f"O áudio do Shorts ficou fora da faixa de 1:00 a 1:30 ({fitted_duration:.1f}s)."
            )
    else:
        if initial_duration < min_duration or initial_duration > max_duration:
            fitted_duration = _fit_narration(voice_raw, voice_fit, target_duration)
        else:
            voice_fit.write_bytes(voice_raw.read_bytes())
            fitted_duration = _probe_duration(voice_fit)
        if not (min_duration <= fitted_duration <= max_duration):
            raise RuntimeError(
                f"O episódio horizontal precisa ficar entre 5 e 10 minutos ({fitted_duration:.1f}s)."
            )

    # Give the final scene a short visual tail after the last spoken line.
    duration_seconds = fitted_duration + 1.2
    timeline_scale = initial_duration / max(.001, fitted_duration)
    for item in voice_timeline:
        item["start"] /= timeline_scale
        item["end"] /= timeline_scale
    width, height = (480, 854) if portrait else (854, 480)
    frames = workdir / f"frames-{fmt.replace(':','x')}"
    frames.mkdir(parents=True, exist_ok=True)

    planned_scenes = plan.get("scenes") or []
    if planned_scenes:
        render_scenes = [(item.get("title", f"CENA {i+1}"),
                          item.get("caption", item.get("visual_action", "")),
                          item.get("visual_action", ""))
                         for i, item in enumerate(planned_scenes)]
    else:
        render_scenes = [
            ("A NOVA MISSÃO", "Os Pequenos Guardiões chegam a um planeta diferente.", ""),
            ("CONHECENDO O LUGAR", "Luna, Tomi e Pipo observam o novo mundo.", ""),
            ("NOVOS AMIGOS", "Os habitantes contam o que está acontecendo.", ""),
            ("A DESCOBERTA", "Luna encontra uma pista importante.", ""),
            ("UM PLANO SEGURO", "Tomi organiza a equipe e pede ajuda.", ""),
            ("A SOLUÇÃO", "Todos trabalham juntos para ajudar a comunidade.", ""),
            ("A LIÇÃO", "Amizade e cooperação fazem a diferença.", ""),
        ]
    if not render_scenes:
        raise RuntimeError("O roteiro não contém cenas para animar.")
    scene_source_indices = list(range(len(render_scenes)))
    if portrait:
        highlight_indices = plan.get("short_scene_indices") or scene_source_indices
        scene_source_indices = [index for index in highlight_indices if 0 <= index < len(render_scenes)]
        render_scenes = [render_scenes[index] for index in scene_source_indices]
        if not render_scenes:
            raise RuntimeError("O roteiro não contém cenas para o destaque do Shorts.")

    scene_count = len(render_scenes)
    # Traditional Cartoon animation often uses drawings on twos (12 unique
    # frames per second). Render only those true 3D poses, then encode at
    # 24 fps to reduce CPU-only VPS render work without reducing image detail.
    configured_fps = float(os.getenv("ANIMA_CARTOON_CAPTURE_FPS", "12"))
    if not 1 <= configured_fps <= 24:
        raise ValueError("ANIMA_CARTOON_CAPTURE_FPS deve ficar entre 1 e 24.")
    capture_fps = min(float(FPS), configured_fps)
    total_frames = max(1, int(math.ceil(duration_seconds * capture_fps)))
    engine = "3d"
    if engine != "3d":
        raise RuntimeError("O motor 2D foi removido. Apenas Cartoon 3D pode renderizar episódios.")
    _render_blender_frames(
        frames, fmt, width, height, total_frames,
        render_scenes, scene_source_indices, plan, voice_timeline, progress_callback,
        capture_fps=capture_fps
    )
    frame_pattern = frames / "frame-%06d.png"

    low_video = workdir / f"silent-{fmt.replace(':','x')}.mp4"
    if progress_callback:
        progress_callback(93, "Montando sequência de imagens em vídeo.")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(capture_fps),
          "-start_number", "1",
          "-i", str(frame_pattern), "-c:v", "libx264",
          "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-r", "24", "-g", "24", "-keyint_min", "24", "-sc_threshold", "0", str(low_video)])

    if progress_callback:
        progress_callback(95, "Sincronizando vídeo e áudio final.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output_duration = duration_seconds
    target_size = "1080:1920" if portrait else "1920:1080"
    _run_ffmpeg_with_progress(["ffmpeg", "-y", "-loglevel", "error", "-i", str(low_video), "-i", str(voice_fit),
          "-filter_complex", f"[0:v]scale={target_size}:flags=lanczos,setsar=1[v];[1:a]apad=pad_dur=2,loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=90,lowpass=f=9000[a]",
          "-map", "[v]", "-map", "[a]", "-t", f"{output_duration:.3f}",
          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-r", "24", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
          "-progress", "pipe:1", "-nostats", str(output)], progress_callback, output_duration)
    if not output.exists() or output.stat().st_size < 10000:
        raise RuntimeError("O arquivo de vídeo não foi gerado corretamente.")
    actual_video_duration = _probe_duration(output)
    if progress_callback:
        progress_callback(99, "Validando arquivo, áudio e duração.")
    if portrait and not (60 <= actual_video_duration <= 90):
        raise RuntimeError(f"O vídeo Shorts ficou fora da faixa de 1:00 a 1:30 ({actual_video_duration:.1f}s).")
    if not portrait and not (300 < actual_video_duration <= 600):
        raise RuntimeError(f"O episódio horizontal precisa ficar entre 5 e 10 minutos ({actual_video_duration:.1f}s).")
    shutil.rmtree(frames, ignore_errors=True)
    return {
        "duration_seconds": round(actual_video_duration, 2),
        "narration_seconds": round(fitted_duration, 2),
        "resolution": "1080x1920" if portrait else "1920x1080",
        "scene_count": scene_count,
        "render_engine": "Blender 3D Cartoon infantil",
        "narration_word_count": sum(len(str(item.get("text", "")).split()) for item in audio_segments),
        "speakers": sorted({str(item.get("speaker", "Narrador")) for item in audio_segments}),
        "voice_profiles_file": str(VOICE_PROFILE_FILE),
    }
