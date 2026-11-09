"""Diagnostic render for Blender Eevee/OpenGL on Windows; does not modify project files."""
import json
import os
import sys
import time
import traceback
from pathlib import Path

def arg_after(flag, default):
    try:
        return sys.argv[sys.argv.index(flag) + 1]
    except (ValueError, IndexError):
        return default

out = Path(arg_after("--output", str(Path.cwd() / "anima-rx580-probe.json"))).resolve()
result = {
    "status": "starting",
    "blender_version": None,
    "render_engine": None,
    "gpu_backend": None,
    "gpu_vendor": None,
    "gpu_renderer": None,
    "gpu_version": None,
    "render_seconds": None,
    "resolution": "640x360",
    "error": None,
}
try:
    import bpy
    result["blender_version"] = bpy.app.version_string
    engines = [item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    result["available_engines"] = engines
    result["render_engine"] = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else (
        "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else None
    )
    try:
        import gpu
        # Blender 5.2 supports explicit GPU module initialization in background mode.
        # Without this call, platform queries can fail even when Eevee rendered successfully.
        try:
            gpu.init()
            result["gpu_init"] = "ok"
        except Exception as exc:
            result["gpu_init"] = "failed: " + str(exc)
        platform = gpu.platform
        for key, fn in (
            ("gpu_backend", "backend_type_get"),
            ("gpu_device_type", "device_type_get"),
            ("gpu_vendor", "vendor_get"),
            ("gpu_renderer", "renderer_get"),
            ("gpu_version", "version_get"),
        ):
            try:
                result[key] = getattr(platform, fn)()
            except Exception as exc:
                result[key] = "unavailable: " + str(exc)
    except Exception as exc:
        result["gpu_probe_error"] = str(exc)

    if not result["render_engine"]:
        raise RuntimeError("Esta versão do Blender não oferece Eevee.")

    scene = bpy.context.scene
    scene.render.engine = result["render_engine"]
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(out.with_suffix(".png"))

    # A tiny scene isolates Blender startup + Eevee rendering from the project.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_monkey_add(location=(0, 0, 0))
    bpy.ops.object.shade_smooth()
    bpy.ops.object.light_add(type="AREA", location=(3, -4, 5))
    bpy.context.object.data.energy = 900
    bpy.ops.object.camera_add(location=(4, -6, 3))
    camera = bpy.context.object
    camera.rotation_euler = (1.15, 0, 0.58)
    scene.camera = camera
    scene.world.color = (0.08, 0.08, 0.08)

    start = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    result["render_seconds"] = round(time.perf_counter() - start, 3)
    result["status"] = "ok"
    result["output_image"] = str(out.with_suffix(".png"))
except Exception as exc:
    result["status"] = "error"
    result["error"] = type(exc).__name__ + ": " + str(exc)
    result["traceback"] = traceback.format_exc()[-4000:]
finally:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ANIMA_RX580_PROBE:" + json.dumps(result, ensure_ascii=False), flush=True)
    if result["status"] != "ok":
        sys.exit(2)
