import pytest
from backend.app.engines.registry import engine_catalog, selected_render_engine, validate_engine


def test_narrated_2d_is_the_only_production_engine():
    catalog = engine_catalog()
    assert catalog["selected"] == "2d"
    assert catalog["separation"]["gpu_required"] is False
    assert catalog["separation"]["blender_required"] is False
    assert catalog["separation"]["image_api_required"] is False
    assert catalog["engines"][0]["id"] == "2d"
    assert catalog["engines"][0]["worker"] == "vps-cpu"


def test_selection_does_not_require_image_api_or_gpu_worker():
    assert engine_catalog(worker_connected=False)["selected"] == "2d"
    assert engine_catalog(worker_connected=True)["selected"] == "2d"


def test_render_engine_validation_is_strict():
    assert selected_render_engine() == "2d"
    assert validate_engine("2d") == "2d"
    with pytest.raises(ValueError):
        validate_engine("3d")
