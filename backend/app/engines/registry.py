"""Production engine registry — 2D narration and progressive drawing, CPU only."""
from __future__ import annotations

import os
from typing import Any


ENGINE_CATALOG: dict[str, dict[str, Any]] = {
    "2d": {
        "id": "2d",
        "name": "Anima Studio 2D — histórias desenhadas",
        "purpose": "Narradora em português com personagens e cenários desenhados em tempo real",
        "worker": "vps-cpu",
        "render_backend": "Pillow + FFmpeg",
        "production": True,
        "selected": True,
        "ready": True,
        "status": "ready",
        "requires": ["Pillow", "FFmpeg", "Edge TTS ou espeak-ng"],
    },
}
MODULE_ENGINES = {
    "characters": "cartoon2d:stable-series-character-design",
    "motion": "narrated_draw_2d:progressive-ink-and-color",
    "voice": "female-narrator-pt-BR",
    "environment": "cartoon2d:original-story-illustrations",
    "music": "audio-mix",
    "composition": "narrated_draw_2d:ffmpeg",
    "render": "ffmpeg-cpu",
}


def selected_render_engine() -> str:
    return "2d"


def engine_catalog(worker_connected: bool = False) -> dict[str, Any]:
    import shutil
    ready = bool(shutil.which("ffmpeg") and (shutil.which("espeak-ng")
                 or __import__("importlib").util.find_spec("edge_tts")))
    engine = dict(ENGINE_CATALOG["2d"])
    engine.update(ready=ready, status="ready" if ready else "unavailable")
    return {
        "selected": "2d",
        "engines": [engine],
        "modules": MODULE_ENGINES.copy(),
        "separation": {
            "production_engine": "narrated-draw-2d",
            "blender_required": False, "gpu_required": False,
            "image_api_required": False,
            "render_backend": "Pillow + FFmpeg on the VPS",
        },
    }


def validate_engine(engine_id: str) -> str:
    if str(engine_id or "").strip().lower() != "2d":
        raise ValueError("O motor ativo é desenho 2D narrado, executado na VPS sem GPU.")
    return "2d"
