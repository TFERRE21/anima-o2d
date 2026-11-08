"""Resolve the real Blender 3D engine in binary or embedded-Python form."""
from __future__ import annotations

import importlib.util
import functools
import os
import shutil
from pathlib import Path


def find_blender_binary() -> str | None:
    configured = os.getenv("BLENDER_BIN", "").strip()
    candidates = ([configured] if configured else []) + [
        "blender", "/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"
    ]
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        located = shutil.which(candidate)
        if located:
            path = Path(located)
            if path.is_file() and os.access(path, os.X_OK):
                return str(path.resolve())
        if os.path.sep in candidate:
            path = Path(candidate).expanduser()
            if path.is_file() and os.access(path, os.X_OK):
                return str(path.resolve())
    return None


@functools.lru_cache(maxsize=1)
def inspect_bpy_module() -> dict:
    """Import bpy for real; find_spec alone misses missing native shared libraries."""
    try:
        if importlib.util.find_spec("bpy") is None:
            return {"available": False, "version": None, "error": "módulo bpy não instalado"}
        import bpy
        version = str(getattr(bpy.app, "version_string", "unknown"))
        return {"available": True, "version": version, "error": None}
    except Exception as exc:
        return {
            "available": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def reset_bpy_import_state() -> None:
    """Remove failed partial imports after native libraries have been installed."""
    import sys
    for name in list(sys.modules):
        if name == "bpy" or name.startswith("bpy."):
            sys.modules.pop(name, None)
    inspect_bpy_module.cache_clear()


def has_bpy_module() -> bool:
    return bool(inspect_bpy_module()["available"])


def find_blender_runtime() -> dict | None:
    """Return a tested Blender runtime, not merely a package that has metadata."""
    binary = find_blender_binary()
    if binary:
        return {"backend": "binary", "executable": binary, "module": "bpy"}
    module = inspect_bpy_module()
    if module["available"]:
        return {
            "backend": "python-module",
            "executable": None,
            "module": "bpy",
            "version": module["version"],
        }
    return None


def blender_available() -> bool:
    return find_blender_runtime() is not None
