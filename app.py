"""Entry point for ICP Python runtimes and Docker containers."""
import os
from threading import Thread

import uvicorn


def _repair_blender_system_libraries() -> None:
    """Install missing Debian native libraries without blocking API startup."""
    try:
        from backend.app.system_deps import ensure_blender_native_libraries
        status = ensure_blender_native_libraries()
        print("ANIMA_NATIVE_LIBRARIES:", status, flush=True)
        # A health request may have cached the pre-install import error.
        from backend.app.runtime import inspect_bpy_module
        inspect_bpy_module.cache_clear()
    except Exception as exc:
        print(
            f"ANIMA_NATIVE_LIBRARIES_BOOTSTRAP_ERROR: {type(exc).__name__}: {exc}",
            flush=True,
        )


def main() -> None:
    # ICP Standalone runs in an isolated container but may not build this repo's
    # Dockerfile. Repair native Blender libraries in the background when possible.
    Thread(
        target=_repair_blender_system_libraries,
        name="anima-blender-native-deps",
        daemon=True,
    ).start()

    port = int(os.environ.get("PORT", "5000"))
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
