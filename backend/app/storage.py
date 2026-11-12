"""Canonical persistent storage for Anima Studio.

The iContainer deployment bind-mounts /home/apps/animacao2d at /app.
Older deployments explicitly set ANIMA_STORAGE=/data/jobs, which is container
ephemeral storage. Migrate that legacy directory once into /app/data/jobs.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


PERSISTENT_ROOT = Path("/app/data/jobs")
LEGACY_ROOT = Path("/data/jobs")


def storage_root() -> Path:
    configured = Path(os.getenv("ANIMA_STORAGE", str(PERSISTENT_ROOT))).expanduser()
    # Correct the known legacy iContainer value instead of silently writing
    # new episodes to the container's non-persistent filesystem.
    if configured == LEGACY_ROOT and Path("/app").is_dir():
        target = PERSISTENT_ROOT
        target.mkdir(parents=True, exist_ok=True)
        if LEGACY_ROOT.is_dir() and LEGACY_ROOT.resolve() != target.resolve():
            for item in LEGACY_ROOT.iterdir():
                destination = target / item.name
                if destination.exists():
                    continue
                try:
                    if item.is_dir():
                        shutil.move(str(item), str(destination))
                    else:
                        shutil.move(str(item), str(destination))
                except OSError:
                    # Keep the legacy source intact if a file is busy or
                    # cannot be migrated; never prevent the API from starting.
                    pass
        return target
    configured.mkdir(parents=True, exist_ok=True)
    return configured
