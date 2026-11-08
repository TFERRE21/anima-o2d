"""Entry point for ICP Python runtimes and Docker containers."""
import os
import uvicorn


def main() -> None:
    # ICP Standalone may run inside Docker without using this repository's
    # Dockerfile. Repair missing Blender system libraries before importing FastAPI.
    try:
        from backend.app.system_deps import ensure_blender_native_libraries
        status = ensure_blender_native_libraries()
        print("ANIMA_NATIVE_LIBRARIES:", status, flush=True)
    except Exception as exc:
        # Keep the API available so /api/diagnostics can explain the failure.
        print(
            f"ANIMA_NATIVE_LIBRARIES_BOOTSTRAP_ERROR: {type(exc).__name__}: {exc}",
            flush=True,
        )

    port = int(os.environ.get("PORT", "5000"))
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
