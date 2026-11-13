"""Registry do motor único de produção: Cartoon 3D infantil com Blender."""
from __future__ import annotations
from typing import Any
from backend.app.runtime import blender_available

ENGINE_CATALOG: dict[str, dict[str, Any]] = {
    "3d": {
        "id": "3d", "name": "Anima Studio Cartoon 3D",
        "purpose": "Produção de animações infantis tridimensionais",
        "worker": "blender-local", "render_backend": "blender-eevee-cartoon3d",
        "production": True, "selected": True,
        "ready": blender_available(), "status": "ready" if blender_available() else "unavailable",
        "requires": ["Blender 3D", "Eevee", "FFmpeg", "Edge TTS ou espeak-ng"],
    }
}
MODULE_ENGINES = {
    "characters": "blender_scene:3d-model-library",
    "motion": "blender_scene:character-animation",
    "voice": "edge-tts", "environment": "blender_scene:3d-worlds",
    "music": "audio-mix", "composition": "blender-camera", "render": "blender-eevee",
}
def selected_render_engine() -> str:
    return "3d"
def engine_catalog(worker_connected: bool = False) -> dict[str, Any]:
    ready = blender_available()
    engine = dict(ENGINE_CATALOG["3d"])
    engine.update(ready=ready, status="ready" if ready else "unavailable")
    return {"selected":"3d","engines":[engine],"modules":MODULE_ENGINES.copy(),
            "separation":{"production_engine":"cartoon-3d","blender_required":True,
                          "bpy_required":False,"render_backend":"Blender executable",
                          "gpu_optional_for_rendering":True}}
def validate_engine(engine_id: str) -> str:
    if str(engine_id or "").strip().lower() != "3d":
        raise ValueError("O único motor ativo é o Anima Studio Cartoon 3D infantil.")
    return "3d"
