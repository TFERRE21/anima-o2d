"""Narrated 2D storybook video production with fixed cast and live preview.

When an image API is configured, each scene receives a detailed illustrated
planetary background from the story and narration. Without one, the legacy
local procedural background is used and visibly labeled as basic quality.
The approved Luna/Tomi/Pipo artwork is composited after background creation.
Pillow and FFmpeg produce the progressive coloring and final video on the VPS.
"""
from __future__ import annotations

import hashlib

import math
import os
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from backend.app import cartoon2d, comic_panels
from backend.app.renderer import (
    _ffmpeg_executable, _fit_narration, _probe_duration, _run,
    _run_ffmpeg_with_progress, _synthesize_segments,
)

DRAW_ENGINE = "Anima 2D · desenho narrado na VPS (CPU)"
DRAW_ART_VERSION = "reference-aware-proportional-cast-v12"
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
    scripted_dialogue = {
        (int(line.get("scene",-1)),str(line.get("speaker","")),str(line.get("text","")).strip())
        for line in plan.get("dialogues", [])
    }
    for item in raw:
        original_text = str(item.get("text") or "").strip()
        if not original_text:
            continue
        original_speaker = str(item.get("speaker") or "Narrador").strip()
        scene_number = int(item.get("scene",0))
        # Only actual scripted dialogue is a speech balloon. Legacy Shorts
        # used speaker='Luna' for narrative summaries ("Na parte mais difícil
        # da missão..."), which must NEVER appear in a character's balloon.
        is_real_dialogue = (
            original_speaker != "Narrador" and
            (item.get("visual_dialogue") is True or
             (scene_number,original_speaker,original_text) in scripted_dialogue)
        )
        spoken_audio = original_text
        if original_speaker != "Narrador":
            display_name = "uma moradora" if original_speaker == "Moradora" else original_speaker
            spoken_audio = f"{display_name} disse: {original_text}"
        segments.append({
            "speaker":"Narrador", "scene":scene_number,
            "text":spoken_audio,
            "original_speaker":original_speaker if is_real_dialogue else "Narrador",
            "dialogue_text":original_text if is_real_dialogue else "",
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
    """Sketch stage preserving the approved comic ink instead of edge-detection noise."""
    colored = colored.convert("RGB")
    paper = Image.new("RGB", colored.size, "#faf5e9")
    gray = ImageOps.grayscale(colored)
    # Pencil tracing uses the same clean contour geometry as the final image.
    pencil = ImageOps.colorize(gray, black="#777a7d", white="#faf5e9").convert("RGB")
    return Image.blend(paper, pencil, 0.82)


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


def artwork_for_scene(
    plan: dict, scene_index: int, fmt: str,
    width: int, height: int, ordinal: int, count: int,
    workdir: Path | None = None,
) -> tuple[Image.Image, Image.Image]:
    """Prefer original professionally curated illustrations; never enlarge fake pixels.

    The fallback is the existing authored 2D cartoon renderer, not an
    AI-generated scene. An exact match to a reference requires curated art.
    """
    scenes = plan.get("scenes") or []
    scene = dict(scenes[scene_index]) if scene_index < len(scenes) else {}
    # Link the visual reaction to the actual character speaking in this scene.
    dialogues = [line for line in plan.get("dialogues", [])
                 if int(line.get("scene", -1)) == scene_index
                 and line.get("speaker") in {"Luna", "Tomi", "Pipo"}]
    if dialogues:
        scene["bubble_speaker"] = dialogues[0]["speaker"].lower()
        scene["spoken_excerpt"] = str(dialogues[0].get("text", ""))
    # World identity is fixed across the entire episode; the scene's own
    # action/narration determines which part of that world is visible.
    scene["world_inhabitants"] = str(plan.get("inhabitants") or "")
    scene["world_landmark"] = str(plan.get("landmark") or "")
    scene["mission_object"] = str(plan.get("mission_object") or "")
    if not scene.get("spoken_excerpt"):
        track = plan.get("audio_segments_long") or []
        for passage in track:
            if passage.get("scene") == scene_index:
                scene["spoken_excerpt"] = str(passage.get("text") or "")[:260]
                break
    # Premium illustrated worlds are generated automatically when an API key
    # is configured. Both scene and model are versioned independently.
    from backend.app.official_comic_2d import draw_official_scene, model_path
    from backend.app.illustrated_scene_engine import (
        enabled as image_api_enabled, required as premium_required,
        illustrated_background, cache_tag, character_mode,
    )
    has_premium = image_api_enabled()
    ai_cast = has_premium and character_mode()=="reference_ai"
    if premium_required() and not has_premium:
        raise RuntimeError(
            "O motor ilustrado precisa de CLOUDFLARE_API_TOKEN e "
            "CLOUDFLARE_ACCOUNT_ID, ou uma API de imagens configurada. "
            "Não é preciso enviar imagens."
        )
    if workdir is not None:
        if has_premium:
            official_dir = workdir / ("story-comic-reference-v12-" + cache_tag())
        else:
            official_dir = workdir / "story-comic-reference-local-v12"
    else:
        official_dir = None
    official_image = official_dir / f"scene-{scene_index:02d}.png" if official_dir else None
    if official_image and official_image.is_file() and (
        not model_path().is_file()
        or official_image.stat().st_mtime >= model_path().stat().st_mtime
    ):
        with Image.open(official_image) as im:
            image = im.convert("RGB")
    else:
        scene_action = str(
            scene.get("visual_action") or scene.get("action")
            or scene.get("caption") or scene.get("description")
            or scene.get("title") or ""
        )
        illustrated = (
            illustrated_background(plan, scene, int(scene_index), workdir,
                                   output_size=(1280,720))
            if has_premium and workdir is not None else None
        )
        image = draw_official_scene(
            int(scene_index),
            str(plan.get("planet") or "Novo planeta"),
            scene_action, width=1280, height=720,
            scene=scene, biome=str(plan.get("biome") or ""),
            illustrated_background=illustrated,
            generated_cast=ai_cast,
        )
        if official_dir is not None:
            official_dir.mkdir(parents=True, exist_ok=True)
            tmp = official_dir / f".scene-{scene_index:02d}-{os.getpid()}.png"
            try:
                image.save(tmp, format="PNG")
                os.replace(tmp, official_image)
            finally:
                tmp.unlink(missing_ok=True)
    image = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
    return image, _sketch_image(image)



def _preview(output_dir: Path, fmt: str, illustration: Image.Image) -> None:
    preview = output_dir / ("preview-" + fmt.replace(":", "x") + ".jpg")
    tmp = preview.with_suffix(".partial.jpg")
    image = illustration.copy()
    image.thumbnail((480, 854) if fmt == "9:16" else (854, 480))
    image.save(tmp, format="JPEG", quality=83)
    os.replace(tmp, preview)


def _render_scene_clip(
    ffmpeg: str, paper: Path, sketch: Path, colored: Path,
    pencil: Path | None, output: Path, seconds: float, fps: int,
    active_panel: tuple[int, int, int, int] | None = None,
    preview_path: Path | None = None,
    draw_progress: Callable[[float], None] | None = None,
) -> None:
    """Draw the *active panel* and color it; no flying cartoon pencil.

    A one-time RGBA photograph of a real hand is composited only when the
    user provides it. Without that file, the video shows the drawings alone.
    """
    seconds = max(0.7, float(seconds))
    ink_seconds = min(35.0, max(0.18, seconds * .32))
    color_seconds = min(30.0, max(0.18, seconds * .27))
    ink_offset = min(0.18, seconds*.07)
    color_offset = ink_offset + ink_seconds
    draw_ends = color_offset + color_seconds
    input_seconds = seconds + 1.0
    inputs = []
    for still in (paper, sketch, colored):
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{input_seconds:.4f}", "-i", str(still)]
    filter_parts = [
        f"[0:v]fps={fps},format=yuv420p,setsar=1[a]",
        f"[1:v]fps={fps},format=yuv420p,setsar=1[b]",
        f"[2:v]fps={fps},format=yuv420p,setsar=1[c]",
        f"[a][b]xfade=transition=wipeleft:duration={ink_seconds:.4f}:offset={ink_offset:.4f}[ink]",
        f"[ink][c]xfade=transition=wipeleft:duration={color_seconds:.4f}:offset={color_offset:.4f}[painting]",
    ]
    result = "[painting]"
    if pencil is not None:
        if active_panel is None:
            raise ValueError("A mão real precisa da posição do quadro em desenho.")
        x0,y0,x1,y1=active_panel
        panel_width=max(1,x1-x0)
        # Hand's index-finger / pen point follows the active comic panel.
        is_video = pencil.suffix.lower() in {".mp4", ".mov", ".webm"}
        if is_video:
            inputs += ["-stream_loop", "-1", "-i", str(pencil)]
        else:
            inputs += ["-loop", "1", "-framerate", str(fps), "-t",
                       f"{input_seconds:.4f}", "-i", str(pencil)]
        hand_size=max(90,int(panel_width*.42))
        if is_video:
            # Real film recorded against a clean green backdrop; key out
            # green while retaining the hand and its natural finger motion.
            filter_parts.append(
                f"[3:v]fps={fps},scale={hand_size}:-1,"
                "format=rgba,colorkey=0x00ff00:0.21:0.06[hand]"
            )
        else:
            # Cropped/transparent photograph: less faithful than real video.
            filter_parts.append(f"[3:v]scale={hand_size}:-1,format=rgba[hand]")
        px=(x1-x0-hand_size)*.85
        x_expression=f"{x0}+{px:.2f}*min(1\\,t/{max(.4,draw_ends):.4f})"
        y_expression=f"{y0}+{max(2,int((y1-y0)*.12))}+sin(t*2.1)*{max(4,int((y1-y0)*.12))}"
        filter_parts.append(
            f"[painting][hand]overlay=x='{x_expression}':y='{y_expression}':"
            f"enable='between(t\\,0\\,{draw_ends:.4f})':shortest=1:format=auto[out]"
        )
        result="[out]"
    filt=";".join(filter_parts)
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        *inputs, "-filter_complex", filt, "-map", result,
        "-t", f"{seconds:.4f}", "-r", str(fps),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-an",
        "-progress", "pipe:1", "-nostats", str(output),
    ]
    # FFmpeg supplies true encoded timestamps: the preview follows actual
    # production and never advances while the encoder is stopped.
    if preview_path is None:
        _run(command)
    else:
        with Image.open(paper) as p, Image.open(sketch) as s, Image.open(colored) as f:
            still_paper = p.convert("RGB")
            still_sketch = s.convert("RGB")
            still_color = f.convert("RGB")
        if active_panel is None:
            raise ValueError("Prévia progressiva requer coordenadas do quadrinho.")
        x0, y0, x1, y1 = active_panel
        preview_size = still_paper.size
        last_step = -1
        def publish_preview(position: float) -> None:
            nonlocal last_step
            step = max(0, min(30, round(position/max(.01, seconds)*30)))
            if step <= last_step:
                return
            last_step = step
            if draw_progress is not None:
                draw_progress(min(1.0, max(0.0, position / max(.01, seconds))))
            ink_ratio = max(0.0, min(1.0, (position-ink_offset)/max(.01,ink_seconds)))
            color_ratio = max(0.0, min(1.0, (position-color_offset)/max(.01,color_seconds)))
            mask_ink = Image.new("L", preview_size, 0)
            mask_color = Image.new("L", preview_size, 0)
            draw_ink = ImageDraw.Draw(mask_ink)
            draw_color = ImageDraw.Draw(mask_color)
            if ink_ratio:
                draw_ink.rectangle((x0,y0,x0+round((x1-x0)*ink_ratio),y1),fill=255)
            if color_ratio:
                draw_color.rectangle((x0,y0,x0+round((x1-x0)*color_ratio),y1),fill=255)
            working = Image.composite(still_sketch, still_paper, mask_ink)
            working = Image.composite(still_color, working, mask_color)
            working.thumbnail((480,854) if preview_size[1]>preview_size[0] else (854,480))
            temp = preview_path.with_suffix(".partial.jpg")
            working.save(temp,format="JPEG",quality=84)
            os.replace(temp,preview_path)
        publish_preview(0.0)
        proc = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                text=True,bufsize=1)
        try:
            for line in proc.stdout:
                if line.startswith(("out_time_ms=","out_time_us=")):
                    try:
                        position = max(0.0,int(line.partition("=")[2])/1_000_000)
                        publish_preview(position)
                    except ValueError:
                        continue
            stderr = proc.stderr.read() if proc.stderr else ""
            if proc.wait() != 0:
                raise RuntimeError("FFmpeg falhou ao desenhar a cena: "+stderr[-1600:])
            publish_preview(seconds)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
    if not output.is_file() or output.stat().st_size < 1000:
        raise RuntimeError("Falha ao desenhar a cena 2D: " + output.name)



def _concat_legacy_short(clips: list[Path], target: Path) -> None:
    """Shorts 9:16: preserve the previously working lightweight FFmpeg path.

    All drawing beats are encoded with the same settings. This route does
    not depend on ffprobe or the new multi-input re-encoding pipeline used
    by horizontal episodes.
    """
    if not clips:
        raise RuntimeError("Nenhum trecho de Shorts para juntar.")
    def quote(path: Path) -> str:
        return path.resolve().as_posix().replace("'", "'\\''")
    manifest=target.with_suffix(".concat.txt")
    manifest.write_text(
        "".join("file '"+quote(Path(path))+"'\n" for path in clips),
        encoding="utf-8")
    _run([_ffmpeg_executable(),"-y","-hide_banner","-loglevel","error",
          "-f","concat","-safe","0","-i",str(manifest),
          "-c","copy","-movflags","+faststart",str(target)])
    if not target.is_file() or target.stat().st_size<1000:
        raise RuntimeError("A montagem do Shorts não produziu um vídeo válido.")


def _video_from_scenes(
    workdir: Path, fmt: str, plan: dict, indices: list[int],
    seconds_per_scene: list[float], fps: int,
    progress_callback: Callable[[int, str], None] | None,
    voice_timeline: list[dict] | None = None,
    narration_segments: list[dict] | None = None,
) -> Path:
    """Render each spoken dialogue beat with exactly its own real balloon.

    A narrator passage displays the art without a speech balloon. Dialogue
    text comes only from the recorded script; one panel changes its bubble
    while narration continues, without redrawing the characters each time.
    """
    from backend.app.dialogue_timeline import (
        dialogue_beats, draw_balloon, speaker_coordinates,
    )
    target = workdir / ("silent-" + fmt.replace(":", "x") + ".mp4")
    scenes_dir = workdir / ("draw2d-" + fmt.replace(":", "x"))
    scenes_dir.mkdir(parents=True, exist_ok=True)
    portrait = fmt == "9:16"
    w, h = (720, 1280) if portrait else (1280, 720)
    # Both 16:9 and 9:16 use exactly one full-frame illustration.
    actual_hand = comic_panels.real_hand_video() or comic_panels.hand_asset()
    timeline_beats = dialogue_beats(
        narration_segments or [], voice_timeline or [], indices, fmt)
    clips = []
    title = str(plan.get("title") or "Pequenos Guardiões")
    for j, index in enumerate(indices):
        if progress_callback:
            from backend.app.illustrated_scene_engine import enabled as illustration_ready
            progress_callback(
                16 + int(65*j/max(1,len(indices))),
                ("Criando ilustração detalhada" if illustration_ready()
                 else "Preparando cenário local") +
                f" do planeta {plan.get('planet','')} — cena {j+1}/{len(indices)}.",
            )
        art, sketch = artwork_for_scene(
            plan,index,fmt,1280,720,j+1,len(indices),workdir=workdir)
        beats = timeline_beats.get(index) or [
            {"speaker":None,"text":"","start":0.0,"end":1.0}]
        raw_durations = [max(.01,float(beat["end"])-float(beat["start"]))
                         for beat in beats]
        total_weight=sum(raw_durations)
        clip_parts=[]
        preview_path = workdir / ("preview-" + fmt.replace(":", "x") + ".jpg")
        paper_page, panel_rect = comic_panels.comic_page(
            [art],(w,h),title,portrait,
            stage="paper",previous_count=0)
        for beat_idx,beat in enumerate(beats):
            # Narrator expository lines deliberately have no speech balloons.
            # Compose the artwork at its final display size FIRST.
            # Drawing balloons before 9:16 fitting reduced them to tiny
            # illegible captions in a narrow center strip.
            colored_page,_ = comic_panels.comic_page(
                [art],(w,h),title,portrait,
                stage="color",previous_count=0)
            if beat.get("speaker") and beat.get("text"):
                anchor,center=speaker_coordinates(index,beat["speaker"],(w,h))
                colored_page=draw_balloon(
                    colored_page,beat["text"],beat["speaker"],anchor,center)
            if beat_idx==0:
                sketch_scene = _sketch_image(art)
                sketch_page,_=comic_panels.comic_page(
                    [sketch_scene],(w,h),title,portrait,
                    stage="sketch",previous_count=0)
                frame_paper=paper_page
            else:
                # The characters/scenario are already drawn. Only the exact
                # spoken bubble changes with the next narration segment.
                sketch_page=colored_page
                frame_paper=colored_page
            clip_duration=float(seconds_per_scene[j]) * raw_durations[beat_idx]/total_weight
            frame_prefix=f"{j:02d}-{beat_idx:03d}"
            paper=scenes_dir/f"paper-{frame_prefix}.png"
            outline=scenes_dir/f"sketch-{frame_prefix}.png"
            painting=scenes_dir/f"paint-{frame_prefix}.png"
            frame_paper.save(paper)
            sketch_page.save(outline)
            colored_page.save(painting)
            if beat_idx==0:
                _preview(workdir,fmt,sketch_page)
            beat_clip=scenes_dir/f"beat-{frame_prefix}.mp4"
            start_weight=sum(raw_durations[:beat_idx])/total_weight
            beat_weight=raw_durations[beat_idx]/total_weight
            def report_live(fraction: float) -> None:
                if progress_callback:
                    scene_fraction=start_weight+fraction*beat_weight
                    overall=18+int(69*(j+scene_fraction)/max(1,len(indices)))
                    progress_callback(
                        overall,f"Quadrinho {j+1}/{len(indices)} — "
                        f"fala {beat_idx+1}/{len(beats)}, {round(fraction*100)}%."
                    )
            _render_scene_clip(
                _ffmpeg_executable(),paper,outline,painting,
                actual_hand if beat_idx==0 else None,
                beat_clip,clip_duration,fps,active_panel=panel_rect,
                preview_path=preview_path,draw_progress=report_live,
            )
            clip_parts.append(beat_clip)
            _preview(workdir,fmt,colored_page)
        clip=scenes_dir/f"scene-{j:02d}.mp4"
        if len(clip_parts)==1:
            shutil.copyfile(clip_parts[0],clip)
        elif portrait:
            _concat_legacy_short(clip_parts,clip)
        else:
            from backend.app.video_integrity import concat_video_only
            concat_video_only(clip_parts,clip,fps)
        clips.append(clip)
        # Each scene gets its own complete canvas. Nothing from a preceding
        # scene is stacked, scaled down, or carried over as a second panel.
        if progress_callback:
            progress_callback(
                18+int(69*(j+1)/max(1,len(indices))),
                f"Cena {j+1}/{len(indices)} finalizada, com falas sincronizadas."
            )
    if portrait:
        _concat_legacy_short(clips,target)
    else:
        from backend.app.video_integrity import concat_video_only
        concat_video_only(clips,target,fps)
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
    # Validate recorded voice before the background music is mixed in.
    # Otherwise a silent TTS file could appear to pass final audio checks
    # simply because the generated instrumental bed is audible.
    from backend.app.video_integrity import verify_narration_source
    verify_narration_source(fitted)
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
    silent = _video_from_scenes(
        workdir,fmt,plan,indices,seconds,fps,progress_callback,
        voice_timeline=timeline,narration_segments=narration_segments,
    )

    if fmt=="16:9":
        from backend.app.video_integrity import validate_video
        validate_video(silent,require_audio=False,
                       expected_seconds=sum(seconds),
                       tolerance_seconds=max(1.5,len(indices)/fps+.5))
    else:
        # The stable Shorts assembly is checked by the existing FFmpeg-based
        # duration probe, which works even when ffprobe is unavailable.
        from backend.app.renderer import _probe_duration
        if _probe_duration(silent)<1:
            raise RuntimeError("Shorts sem quadros de vídeo.")
    if progress_callback:
        progress_callback(90, "Unindo desenho, narradora e música infantil suave.")
    from backend.app.children_music import create_music, soundtrack_identity
    # Episode-specific soundtrack. Preserve one coherent theme across long
    # and short edits of the same adventure, but never reuse it next episode.
    theme_seed=" | ".join((
        str(plan.get("planet") or planet_name),
        str(plan.get("title") or title),
        str(plan.get("challenge") or plan.get("synopsis") or story[:150]),
    ))
    music = create_music(workdir / ("music-v2-" + fmt.replace(":","x") + ".wav"),
                         duration, theme_seed)
    target_size = "1080:1920" if fmt == "9:16" else "1920:1080"
    output.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg_with_progress([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(silent), "-i", str(fitted), "-i", str(music),
        "-filter_complex",
        f"[0:v]scale={target_size}:flags=lanczos,setsar=1[v];"
        "[1:a]apad=pad_dur=2,loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[voice][key];"
        "[2:a]volume=0.68,lowpass=f=4800[music];"
        "[music][key]sidechaincompress=threshold=0.015:ratio=8:attack=55:release=430[duck];"
        "[voice][duck]amix=inputs=2:duration=first:weights='1 0.48':normalize=0,"
        "alimiter=limit=0.94[a]",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "22", "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", str(output),
    ], progress_callback, duration)
    if not output.is_file() or output.stat().st_size < 10000:
        raise RuntimeError("O vídeo 2D não foi gerado.")
    if fmt=="9:16":
        measured = _probe_duration(output)
    else:
        from backend.app.video_integrity import validate_video
        validated = validate_video(output,require_audio=True,
                                   expected_seconds=duration,
                                   tolerance_seconds=2.0)
        measured = validated["duration"]
    # A valid AAC track alone is insufficient: check decoded audio in the
    # narrated middle, not just the beginning or a musical intro.
    from backend.app.video_integrity import verify_audible_audio
    verify_audible_audio(output,segment_seconds=12)
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
        "soundtrack": "original-playful-music-box-v2-with-narration-ducking",
        "soundtrack_theme": soundtrack_identity(theme_seed)["theme_id"],
        "art_version": DRAW_ART_VERSION,
        "narration_word_count": sum(len(x["text"].split()) for x in narration_segments),
        "speakers": ["Narrador"],
        "drawing_style": "sequential-comic-panels-with-real-hand-if-supplied",
        "real_hand_asset_used": bool(comic_panels.real_hand_video() or comic_panels.hand_asset()),
        "real_hand_film_used": bool(comic_panels.real_hand_video()),
        "curated_art_required": os.getenv("ANIMA_COMIC_REQUIRE_CURATED_ART", "0") == "1",
        "gpu_required": False,
    }
