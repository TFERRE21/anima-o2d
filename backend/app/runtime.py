"""Resolve the real Blender 3D engine in binary or embedded-Python form."""
from __future__ import annotations

import importlib.util
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


def has_bpy_module() -> bool:
    """Check whether the official Blender Python module is installed for this Python."""
    try:
        return importlib.util.find_spec("bpy") is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def find_blender_runtime() -> dict | None:
    """Return the preferred actual Blender runtime, not a 2D drawing substitute."""
    binary = find_blender_binary()
    if binary:
        return {"backend": "binary", "executable": binary, "module": "bpy"}
    if has_bpy_module():
        return {"backend": "python-module", "executable": None, "module": "bpy"}
    return None


def blender_available() -> bool:
    return find_blender_runtime() is not None
