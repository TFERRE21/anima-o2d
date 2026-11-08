"""Runtime binary discovery shared by API health checks and media workers."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_blender_binary() -> str | None:
    """Resolve Blender even when the host PATH omits the standard system directory.

    BLENDER_BIN may be either an absolute/relative executable path or a command
    name. The standard Debian paths are checked as a fallback, while PATH lookup
    remains supported for containers and local development.
    """
    configured = os.getenv("BLENDER_BIN", "").strip()
    candidates = []
    if configured:
        candidates.append(configured)
    candidates.extend(["blender", "/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"])

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
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
