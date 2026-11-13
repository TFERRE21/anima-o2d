"""Idempotent Blender bootstrap for iContainer's generic Python Docker runtime.

iContainer may recreate containers from python:3.13.0 and ignore this repo's
Dockerfile. A manually installed /usr/bin/blender then disappears. This module
repairs *only this application container* at FastAPI startup, when permitted.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading

from backend.app.runtime import blender_available

_lock = threading.Lock()
_status = {"state": "not_started", "detail": "Inicialização ainda não executada.", "error": None}
_started = False


def _set(state: str, detail: str, error: str | None = None) -> None:
    with _lock:
        _status.update(state=state, detail=detail, error=error)
    print(f"[cartoon3d-blender] {state}: {detail}", flush=True)


def blender_bootstrap_status() -> dict:
    with _lock:
        result = dict(_status)
    if blender_available():
        result.update(state="ready", detail="Blender disponível no container.", error=None)
    return result


def _install_blender() -> None:
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    env["APT_LISTCHANGES_FRONTEND"] = "none"
    commands = [
        (["apt-get", "update"], "Atualizando índices de pacotes"),
        (["apt-get", "-o", "DPkg::Lock::Timeout=180", "install", "-y",
          "--no-install-recommends", "blender", "xvfb", "xauth", "ffmpeg",
          "espeak-ng"], "Instalando Blender e dependências 3D"),
    ]
    for command, title in commands:
        if blender_available():
            break
        _set("installing", title)
        try:
            process = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", env=env, timeout=1200,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            _set("failed", "A instalação automática falhou. Consulte os logs da aplicação.", str(exc)[:500])
            return
        if process.returncode != 0:
            tail = (process.stdout or "")[-1600:]
            _set("failed", "O gerenciador de pacotes retornou erro.", tail)
            return
    if blender_available():
        _set("ready", "Blender instalado e encontrado dentro do container.")
    else:
        _set("failed", "Instalação concluída, mas o executável Blender não foi encontrado.")


def start_blender_bootstrap() -> None:
    """Launch one non-blocking install attempt; no host or other containers touched."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    if blender_available():
        _set("ready", "Blender já está instalado na imagem atual.")
        return
    enabled = os.getenv("ANIMA_AUTO_INSTALL_BLENDER", "1").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        _set("disabled", "Instalação automática desativada por ANIMA_AUTO_INSTALL_BLENDER.")
        return
    if not os.path.exists("/.dockerenv"):
        _set("skipped", "Fora de Docker; instalar Blender no ambiente local.")
        return
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        _set("failed", "O container não executa como root e não pode usar apt-get.")
        return
    if not shutil.which("apt-get"):
        _set("failed", "A imagem do container não possui apt-get.")
        return
    _set("starting", "Blender ausente: iniciando instalação automática no container.")
    threading.Thread(target=_install_blender, name="cartoon3d-blender-bootstrap", daemon=True).start()
