"""Registry do único motor de produção ativo: Cartoon 2D."""
from __future__ import annotations

from typing import Any

ENGINE_CATALOG: dict[str, dict[str, Any]] = {
    "2d": {
        "id": "2d",
        "name": "Anima Studio Cartoon 2D",
        "purpose": "Produção integral de episódios infantis",
        "worker": "server",
        "render_backend": "cartoon2d-full-production",
        "production": True,
        "selected": True,
        "ready": True,
        "status": "ready",
        "requires": ["FFmpeg", "Pillow", "Edge TTS ou espeak-ng"],
    }
}

MODULE_ENGINES = {
    "characters": "character_profiles",
    "motion": "cartoon2d",
    "voice": "edge-tts",
    "environment": "cartoon2d",
    "music": "audio-mix",
    "composition": "ffmpeg",
    "render": "cartoon2d-full-production",
}


def selected_render_engine() -> str:
    # Blender/3D não pode ser reativado por variáveis antigas do deploy.
    return "2d"


def engine_catalog(worker_connected: bool = False) -> dict[str, Any]:
    return {
        "selected": "2d",
        "engines": [dict(ENGINE_CATALOG["2d"])],
        "modules": MODULE_ENGINES.copy(),
        "separation": {
            "production_engine": "cartoon-2d",
            "blender_required": False,
            "bpy_required": False,
            "gpu_optional_for_assets_and_encoding": True,
        },
    }


def validate_engine(engine_id: str) -> str:
    if str(engine_id or "").strip().lower() != "2d":
        raise ValueError("O único motor ativo é o Anima Studio Cartoon 2D.")
    return "2d"
