"""Narrated 2D 'drawing comes to life' video production without GPU or Blender.

Uses the existing authored 2D cartoon cast and scene illustrations, sketches them
as pencil line art, and progressively reveals drawing and color while the
narrator tells the story. All image/animation computation runs on the VPS CPU.
It does not generate new AI artwork, claim image diffusion, or require ComfyUI.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from backend.app import cartoon2d
from backend.app.renderer import (
    _ffmpeg_executable, _fit_narration, _probe_duration, _run,
    _run_ffmpeg_with_progress, _synthesize_segments,
)

DRAW_ENGINE = "Anima 2D · desenho narrado na VPS (CPU)"
DRAW_ART_VERSION = "storybook-narrated-draw-2d-v1"
DEFAULT_FPS = 8


def narrator_segments(plan: dict, fmt: str, story: str) -> list[dict]:
    """One female narrator tells the entire story including any quoted lines.

    Existing character-dialogue scripts are preserved, but the narrator
    introduces each speech instead of abruptly changing cast voices.
    """
    raw = (plan.get("audio_segments_short") if fmt == "9:16"
           else plan.get("audio_segments_long")) or []
    if not raw:
        raw = [{"scene": 0, "speaker": "Narrador", "text": story}]
    segments = []
    for item in raw:
        words = str(item.get("text") or "").strip()
        if not words:
            continue
        who = str(item.get("speaker") or "Narrador").strip()
        if who != "Narrador":
            who = "uma moradora" if who == "Moradora" else who
            words = f"{who} disse: {words}"
        segments.append({
            "speaker": "Narrador", "scene": int(item.get("scene", 0)),
            "text": words,
        })
    if not segments:
        raise ValueError("O roteiro não contém narração.")
    return segments


def scene_index_order(plan: dict, fmt: str) -> list[int]:
    scenes = plan.get("scenes") or []
    indices = list(range(len(scenes)))
    if fmt == "9:16":
        requested = plan.get("short_scene_indices") or indices
        indices = [int(index) for index in requested if 0 <= int(index) < len(scenes)]
    return indices or [0]


def scene_seconds(indices: list[int], voice_timeline: list[dict],
                  total_seconds: float) -> list[float]:
    """Place drawing beats in narration order, rather than unrelated slides."""
    durations = defaultdict(float)
    for item in voice_timeline:
        scene = int(item.get("scene", 0))
        durations[scene] += max(0.0, float(item.get("end", 0)) - float(item.get("start", 0)))
    # A scene without a spoken segment receives an economical visible beat.
    weights = [max(1.0, durations[index]) for index in indices]
    divisor = max(0.01, sum(weights))
    return [total_seconds * w / divisor for w in weights]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    return cartoon2d._font(size, bold=bold)


def _with_caption(image: Image.Image, title: str, scene_no: int, total: int) -> Image.Image:
    image = image.convert("RGB")
    w, h = image.size
    d = ImageDraw.Draw(image)
    margin = int(w * .035)
    label_h = max(39, int(h * .085))
    y = h - label_h - margin
    d.rounded_rectangle((margin, y, w-margin, y+label_h), radius=12,
                        fill="#263d5e", outline="#d6e4f3", width=2)
    font_size = max(15, min(28, int(w / 29)))
    label = re.sub(r"\s+", " ", title.strip()).upper()[:48]
    # Keep the narrator-led story readable on both screen formats.
    while label and d.textbbox((0, 0), label, font=_font(font_size, True))[2] > w - margin * 4:
        label = label[:-1]
    d.text((margin + 17, y + max(5, (label_h - font_size) // 2 - 2)),
           label or f"CENA {scene_no}", font=_font(font_size, True), fill="#ffffff")
    d.text((margin + 7, margin + 5), f"{scene_no:02d}/{total:02d}",
           font=_font(max(13, font_size - 2), True), fill="#ffffff",
           stroke_width=2, stroke_fill="#263d5e")
    return image


def _sketch_image(colored: Image.Image) -> Image.Image:
    """Ink-paper stage made from actual illustrated outlines, not placeholders."""
    colored = colored.convert("RGB")
    gray = ImageOps.grayscale(colored)
    # FIND_EDGES produces bright lines; invert to ink on pale sketchbook paper.
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Contrast(edges).enhance(2.2)
    edges = ImageOps.invert(edges)
    edges = edges.point(lambda x: 24 if x < 156 else 244)
    ink = ImageOps.colorize(edges, black="#343944", white="#faf5e9")
    return ink.convert("RGB")


def _pencil_image() -> Image.Image:
    image = Image.new("RGBA", (100, 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    # Pencil tip at lower left; diagonal gold shaft, eraser and graphite.
    d.polygon(((7, 94), (31, 86), (52, 104)), fill="#c49a6c")
    d.polygon(((7, 94), (21, 91), (20, 100)), fill="#263349")
    d.polygon(((28, 85), (74, 8), (98, 25), (52, 104)),
              fill="#f5bb52", outline="#745c56", width=3)
    d.line(((36, 85), (83, 17)), fill="#ffe4a0", width=6)
    d.polygon(((74, 8), (80, -1), (100, 14), (98, 25)), fill="#ea8a9e")
    d.line(((74, 8), (98, 25)), fill="#a9a9b4", width=5)
    return image


def artwork_for_scene(plan: dict, scene_index: int, fmt: str,
                      width: int, height: int, ordinal: int, count: int) -> tuple[Image.Image, Image.Image]:
    scenes = plan.get("scenes") or []
    scene = scenes[scene_index] if scene_index < len(scenes) else {}
    portrait = fmt == "9:16"
    image = cartoon2d._draw_story_scene(
        0.45, str(plan.get("planet") or "Novo planeta"),
        str(plan.get("biome") or ""),
        str(plan.get("palette") or "aurora"),
        int(scene_index), str(scene.get("action") or ""),
        portrait, "",
    )
    image = image.convert("RGB")
    image = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
    colored = _with_caption(image, str(scene.get("title") or "Nova descoberta"), ordinal, count)
    return colored, _sketch_image(colored)


def _preview(output_dir: Path, fmt: str, illustration: Image.Image) -> None:
    preview = output_dir / ("preview-" + fmt.replace(":", "x") + ".jpg")
    tmp = preview.with_suffix(".partial.jpg")
    image = illustration.copy()
    image.thumbnail((480, 854) if fmt == "9:16" else (854, 480))
    image.save(tmp, format="JPEG", quality=83)
    os.replace(tmp, preview)


def _render_scene_clip(ffmpeg: str, paper: Path, sketch: Path, colored: Path,
                       pencil: Path, output: Path, seconds: float, fps: int) -> None:
    """Two animated drawing passes: ink strokes, then watercolored illustration."""
    seconds = max(1.5, float(seconds))
    # FFmpeg xfade requires each transition to be <=60 seconds.
    # Extended single-scene narratives hold the final illustration afterward.
    ink_seconds = min(35.0, max(0.35, seconds * .37))
    color_seconds = min(30.0, max(0.35, seconds * .33))
    ink_offset = 0.18
    color_offset = ink_offset + ink_seconds
    draw_ends = color_offset + color_seconds
    input_seconds = seconds + 1.0
    inputs = []
    for still in (paper, sketch, colored, pencil):
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{input_seconds:.4f}", "-i", str(still)]
    filt = (
        f"[0:v]fps={fps},format=yuv420p,setsar=1[a];"
        f"[1:v]fps={fps},format=yuv420p,setsar=1[b];"
        f"[2:v]fps={fps},format=yuv420p,setsar=1[c];"
        f"[a][b]xfade=transition=wipeleft:duration={ink_seconds:.4f}:offset={ink_offset:.4f}[ink];"
        f"[ink][c]xfade=transition=wipeleft:duration={color_seconds:.4f}:offset={color_offset:.4f}[painting];"
        f"[3:v]format=rgba[pen];"
        f"[painting][pen]overlay=x='(W-w)*t/{max(.5,draw_ends):.4f}':"
        f"y='H*0.26+sin(t*2.6)*H*0.13':enable='lt(t\\,{draw_ends:.4f})':"
        f"shortest=1:format=auto[out]"
    )
    _run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        *inputs, "-filter_complex", filt, "-map", "[out]",
        "-t", f"{seconds:.4f}", "-r", str(fps),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "23", "-pix_fmt", "yuv420p", "-an", str(output),
    ])
    if not output.is_file() or output.stat().st_size < 1000:
        raise RuntimeError("Falha ao desenhar a cena 2D: " + output.name)


def _video_from_scenes(workdir: Path, fmt: str, plan: dict, indices: list[int],
                       seconds_per_scene: list[float], fps: int,
                       progress_callback: Callable[[int, str], None] | None) -> Path:
    target = workdir / ("silent-" + fmt.replace(":", "x") + ".mp4")
    scenes_dir = workdir / ("draw2d-" + fmt.replace(":", "x"))
    scenes_dir.mkdir(parents=True, exist_ok=True)
    portrait = fmt == "9:16"
    w, h = (480, 854) if portrait else (854, 480)
    paper = scenes_dir / "paper.png"
    pencil = scenes_dir / "pencil.png"
    Image.new("RGB", (w, h), "#faf5e9").save(paper)
    _pencil_image().save(pencil)
    ffmpeg = _ffmpeg_executable()
    clips = []
    for j, index in enumerate(indices):
        art, sketch = artwork_for_scene(plan, index, fmt, w, h, j+1, len(indices))
        painting = scenes_dir / f"paint-{j:02d}.png"
        outline = scenes_dir / f"sketch-{j:02d}.png"
        art.save(painting, optimize=False)
        sketch.save(outline, optimize=False)
        # A real still (not a cosmetic spinner) appears in the dashboard during rendering.
        _preview(workdir, fmt, sketch)
        clip = scenes_dir / f"scene-{j:02d}.mp4"
        _render_scene_clip(
            ffmpeg, paper, outline, painting, pencil,
            clip, seconds_per_scene[j], fps,
        )
        clips.append(clip)
        _preview(workdir, fmt, art)
        if progress_callback:
            progress_callback(
                18 + int(69*(j+1)/max(1,len(indices))),
                f"Narradora contando e desenhando: cena {j+1}/{len(indices)}.",
            )

    manifest = scenes_dir / "concat.txt"
    def ffmpeg_escape(p: Path) -> str:
        return p.resolve().as_posix().replace("'", "'\\''")
    manifest.write_text(
        "".join("file '" + ffmpeg_escape(p) + "'\n" for p in clips),
        encoding="utf-8"
    )
    _run([
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c", "copy", str(target),
    ])
    return target


def render_narrated_draw_episode(title: str, story: str, fmt: str,
                                 output: Path, workdir: Path,
                                 planet_name: str = "Aurora-7",
                                 story_plan: dict | None = None,
                                 progress_callback: Callable[[int, str], None] | None = None) -> dict:
    if fmt not in {"16:9", "9:16"}:
        raise ValueError("Formato 2D inválido.")
    if not _ffmpeg_executable():
        raise RuntimeError("FFmpeg não disponível na VPS.")
    workdir.mkdir(parents=True, exist_ok=True)
    plan = story_plan or {}
    narration_segments = narrator_segments(plan, fmt, story)
    if progress_callback:
        progress_callback(2, "Narradora preparando as falas da história.")
    from backend.app.renderer import _synthesize_segments, _probe_duration, _fit_narration
    speech_rate = 145 if fmt == "9:16" else 140
    raw, fitted, timeline = _synthesize_segments(narration_segments, workdir, fmt, speech_rate)
    raw_seconds = _probe_duration(raw)
    minimum, maximum, target = (60, 88.5, 75) if fmt == "9:16" else (301, 598.5, 420)
    if minimum <= raw_seconds <= maximum:
        shutil.copyfile(raw, fitted)
        narration_seconds = _probe_duration(fitted)
    else:
        narration_seconds = _fit_narration(raw, fitted, target)
    if not minimum <= narration_seconds <= maximum:
        raise RuntimeError(
            f"Narração fora da duração {minimum}-{maximum}s: {narration_seconds:.1f}s."
        )
    duration = narration_seconds + 1.2
    # Match the fitted speech track; one word appears on screen with its scene.
    ratio = narration_seconds / max(raw_seconds, .001)
    timeline = [
        {**segment, "start": segment["start"]*ratio, "end": segment["end"]*ratio}
        for segment in timeline
    ]
    indices = scene_index_order(plan, fmt)
    seconds = scene_seconds(indices, timeline, duration)
    fps = int(os.getenv("ANIMA_DRAW_FPS", str(DEFAULT_FPS)))
    if not 4 <= fps <= 15:
        raise ValueError("ANIMA_DRAW_FPS deve ficar entre 4 e 15.")
    if progress_callback:
        progress_callback(15, "Narração pronta. Preparando os desenhos de cada cena.")
    silent = _video_from_scenes(workdir, fmt, plan, indices, seconds, fps, progress_callback)

    if progress_callback:
        progress_callback(90, "Unindo o desenho progressivo e a voz da narradora.")
    target_size = "1080:1920" if fmt == "9:16" else "1920:1080"
    output.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg_with_progress([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(silent), "-i", str(fitted),
        "-filter_complex",
        f"[0:v]scale={target_size}:flags=lanczos,setsar=1[v];"
        "[1:a]apad=pad_dur=2,loudnorm=I=-16:TP=-1.5:LRA=11[a]",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "22", "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", str(output),
    ], progress_callback, duration)
    if not output.is_file() or output.stat().st_size < 10000:
        raise RuntimeError("O vídeo 2D não foi gerado.")
    measured = _probe_duration(output)
    if fmt == "9:16" and not 60 <= measured <= 90:
        raise RuntimeError(f"Shorts fora do tempo: {measured:.1f}s.")
    if fmt == "16:9" and not 300 < measured <= 600:
        raise RuntimeError(f"Episódio fora do tempo: {measured:.1f}s.")
    return {
        "duration_seconds": round(measured, 2),
        "narration_seconds": round(narration_seconds, 2),
        "resolution": "1080x1920" if fmt == "9:16" else "1920x1080",
        "scene_count": len(indices),
        "render_engine": DRAW_ENGINE,
        "art_version": DRAW_ART_VERSION,
        "narration_word_count": sum(len(x["text"].split()) for x in narration_segments),
        "speakers": ["Narrador"],
        "drawing_style": "progressive-pencil-and-watercolor",
        "gpu_required": False,
    }
