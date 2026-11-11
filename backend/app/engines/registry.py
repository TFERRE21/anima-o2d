"""Independent production-engine registry for Anima Studio.

The 2D preview is intentionally isolated from the 3D production path.
A selected engine must be explicit; the registry never silently falls back
from Blender/RX580 to the 2D preview.
"""
from __future__ import annotations

import os
from typing import Any

ENGINE_CATALOG: dict[str, dict[str, Any]] = {
    "2d": {
        "id": "2d",
        "name": "Animação 2D",
        "purpose": "Prévia e produção 2D independente",
        "worker": "server",
        "render_backend": "cartoon2d",
        "production": True,
    },
    "3d": {
        "id": "3d",
        "name": "Animação 3D Blender",
        "purpose": "Episódios 3D com personagens rigados",
        "worker": "windows-rx580",
        "render_backend": "blender",
        "production": True,
    },
}

MODULE_ENGINES = {
    "characters": "character_engine",
    "motion": "motion_engine",
    "voice": "voice_engine",
    "environment": "environment_engine",
    "music": "music_engine",
    "composition": "composition_engine",
    "render_2d": "cartoon2d",
    "render_3d": "blender-rx580",
    "postproduction": "ffmpeg",
}


def selected_render_engine() -> str:
    value = os.getenv("ANIMA_RENDER_ENGINE", "2d").strip().lower()
    return value if value in ENGINE_CATALOG else "invalid"


def engine_catalog(worker_connected: bool = False) -> dict[str, Any]:
    selected = selected_render_engine()
    engines = []
    for engine_id, definition in ENGINE_CATALOG.items():
        is_3d = engine_id == "3d"
        ready = True if not is_3d else worker_connected
        engines.append({
            **definition,
            "selected": selected == engine_id,
            "ready": ready,
            "status": "ready" if ready else "waiting_for_rx580_worker",
            "requires": ["ANIMA_REMOTE_WORKER_ENABLED=true", "ANIMA_WORKER_TOKEN"]
            if is_3d else [],
        })
    return {
        "selected": selected,
        "engines": engines,
        "modules": MODULE_ENGINES.copy(),
        "separation": {
            "2d_preview_isolated": True,
            "3d_requires_blender_worker": True,
            "automatic_fallback_disabled": True,
        },
    }


def validate_engine(engine_id: str) -> str:
    value = str(engine_id or "").strip().lower()
    if value not in ENGINE_CATALOG:
        raise ValueError("Motor inválido. Escolha explicitamente '2d' ou '3d'.")
    return value
