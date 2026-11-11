import os
from backend.app.engines.registry import engine_catalog, selected_render_engine, validate_engine


def test_2d_and_3d_are_separate():
    catalog = engine_catalog(worker_connected=False)
    assert catalog["separation"]["2d_preview_isolated"] is True
    assert catalog["separation"]["3d_requires_blender_worker"] is True
    engines = {item["id"]: item for item in catalog["engines"]}
    assert engines["2d"]["ready"] is True
    assert engines["3d"]["ready"] is False
    assert engines["3d"]["worker"] == "windows-rx580"


def test_3d_readiness_tracks_worker():
    catalog = engine_catalog(worker_connected=True)
    engines = {item["id"]: item for item in catalog["engines"]}
    assert engines["3d"]["ready"] is True
    assert engines["3d"]["status"] == "ready"


def test_engine_selection_is_explicit(monkeypatch):
    monkeypatch.setenv("ANIMA_RENDER_ENGINE", "3d")
    assert selected_render_engine() == "3d"
    assert validate_engine("3d") == "3d"


def test_invalid_engine_does_not_silently_fallback(monkeypatch):
    monkeypatch.setenv("ANIMA_RENDER_ENGINE", "gpu-magic")
    assert selected_render_engine() == "invalid"
