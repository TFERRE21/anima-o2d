"""Install native Debian libraries needed by the Blender bpy wheel.

The Dockerfile installs these at image-build time. This bootstrap is also used
by ICP Python Standalone containers that start the repository with python app.py
and do not execute the repository Dockerfile.
"""
from __future__ import annotations

import ctypes.util
import os
import shutil
import subprocess
from pathlib import Path

PACKAGES = [
    "libxfixes3", "libx11-6", "libxi6", "libxrender1", "libxkbcommon0",
    "libsm6", "libxext6", "libxrandr2", "libxinerama1", "libxcursor1",
    "libxxf86vm1", "libdbus-1-3", "libfontconfig1", "libfreetype6",
    "libwayland-client0", "libwayland-egl1", "libglib2.0-0", "libstdc++6",
    "libgomp1", "libgl1", "libegl1", "libosmesa6",
]
REQUIRED_LIBRARIES = {
    "Xfixes": "libXfixes.so.3",
    "X11": "libX11.so.6",
    "Xrender": "libXrender.so.1",
}


def _missing_libraries() -> list[str]:
    missing = []
    for key, filename in REQUIRED_LIBRARIES.items():
        if ctypes.util.find_library(key):
            continue
        candidates = (
            Path("/lib") / "x86_64-linux-gnu" / filename,
            Path("/usr/lib") / "x86_64-linux-gnu" / filename,
            Path("/lib") / "aarch64-linux-gnu" / filename,
            Path("/usr/lib") / "aarch64-linux-gnu" / filename,
        )
        if not any(path.is_file() for path in candidates):
            missing.append(filename)
    return missing


def ensure_blender_native_libraries() -> dict:
    """Best-effort native dependency repair before Uvicorn imports the API."""
    missing = _missing_libraries()
    if not missing:
        return {"ok": True, "installed": False, "missing": []}

    apt = shutil.which("apt-get")
    if not apt:
        return {
            "ok": False, "installed": False, "missing": missing,
            "error": "apt-get não está disponível neste runtime.",
        }
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        return {
            "ok": False, "installed": False, "missing": missing,
            "error": "O processo não é root; não pode instalar bibliotecas do sistema.",
        }

    try:
        update = subprocess.run(
            [apt, "update"],
            check=False, capture_output=True, text=True, timeout=120,
        )
        if update.returncode != 0:
            return {
                "ok": False, "installed": False, "missing": missing,
                "error": (update.stderr or update.stdout or "apt-get update falhou")[-1800:],
            }

        install = subprocess.run(
            [apt, "install", "-y", "--no-install-recommends", *PACKAGES],
            check=False, capture_output=True, text=True, timeout=180,
        )
        if install.returncode != 0:
            return {
                "ok": False, "installed": False, "missing": _missing_libraries(),
                "error": (install.stderr or install.stdout or "apt-get install falhou")[-1800:],
            }

        ldconfig = shutil.which("ldconfig")
        if ldconfig:
            subprocess.run([ldconfig], check=False, capture_output=True, text=True, timeout=15)

        remaining = _missing_libraries()
        return {
            "ok": not remaining,
            "installed": True,
            "missing": remaining,
            "error": None if not remaining else "Algumas bibliotecas continuam ausentes.",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False, "installed": False, "missing": _missing_libraries(),
            "error": f"{type(exc).__name__}: {exc}",
        }


def native_library_status() -> dict:
    return {
        "libxfixes": ctypes.util.find_library("Xfixes"),
        "libx11": ctypes.util.find_library("X11"),
        "libxrender": ctypes.util.find_library("Xrender"),
        "missing": _missing_libraries(),
        "apt_get_available": bool(shutil.which("apt-get")),
        "running_as_root": bool(hasattr(os, "geteuid") and os.geteuid() == 0),
    }
