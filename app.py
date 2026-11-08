"""Entry point for ICP Python runtimes and Docker containers."""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port)
