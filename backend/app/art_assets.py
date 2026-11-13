"""Persisted approval gate for the image-first cartoon animation engine.

All files live below ANIMA_STORAGE/<12-char-job>/art. The server does not
pretend that raw diffusion output is rigged or that flattened photos have alpha.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from backend.app.art_director import create_art_plan

_JOB = re.compile(r"^[a-f0-9]{12}$")
_ASSET = re.compile(r"^(luna|tomi|pipo|scene-\d{2}-background|scene-\d{2}-foreground)$")
_MAX_BYTES = 25 * 1024 * 1024


def art_root(storage: Path, job_id: str) -> Path:
    if not _JOB.fullmatch(job_id):
        raise ValueError("Identificador de episódio inválido.")
    return storage / job_id / "art"


def art_path(storage: Path, job_id: str, asset_id: str, fmt: str, kind: str = "approved") -> Path:
    if not _ASSET.fullmatch(asset_id):
        raise ValueError("Identificador de material artístico inválido.")
    if fmt not in ("9:16", "16:9"):
        raise ValueError("Formato artístico inválido.")
    # Characters are shared across both edits. Backgrounds are format-specific.
    folder = art_root(storage, job_id) / kind / ("cast" if asset_id in ("luna", "tomi", "pipo") else fmt.replace(":", "x"))
    return folder / (asset_id + ".png")


def inspect_png(data: bytes, asset_id: str, fmt: str) -> dict:
    if not data or len(data) > _MAX_BYTES:
        raise ValueError("Envie uma imagem PNG de até 25 MB.")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.format != "PNG":
                raise ValueError("Envie um arquivo PNG, sem JPEG renomeado.")
            opened.load()
            w, h = opened.size
            if w < 256 or h < 256 or w * h > 16_000_000:
                raise ValueError("A imagem precisa ter entre 256 px e 16 megapixels.")
            char = asset_id in {"luna", "tomi", "pipo"}
            if char:
                if opened.mode not in {"RGBA", "LA", "P"} or (
                    opened.mode == "P" and "transparency" not in opened.info
                ):
                    raise ValueError("Personagem exige PNG com transparência real, não fundo branco.")
                alpha = opened.convert("RGBA").getchannel("A")
                low, high = alpha.getextrema()
                if low > 50 or high < 200:
                    raise ValueError("O personagem deve ter fundo transparente e partes visíveis.")
            else:
                ratio = w / h
                if fmt == "9:16" and not 0.43 <= ratio <= 0.70:
                    raise ValueError("Cenário vertical precisa de enquadramento próximo de 9:16.")
                if fmt == "16:9" and not 1.55 <= ratio <= 2.05:
                    raise ValueError("Cenário horizontal precisa de enquadramento próximo de 16:9.")
            return {"width": w, "height": h, "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest()}
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Arquivo de imagem inválido ou corrompido.") from exc


def approve_art(storage: Path, job_id: str, asset_id: str, fmt: str,
                data: bytes, story: dict) -> dict:
    plan = create_art_plan(story, fmt)
    allowed = set(("luna", "tomi", "pipo"))
    allowed |= {f"scene-{scene['index']:02d}-background" for scene in plan["scenes"]}
    allowed |= {f"scene-{scene['index']:02d}-foreground" for scene in plan["scenes"]}
    if asset_id not in allowed:
        raise ValueError("Material não corresponde a uma cena deste roteiro.")
    meta = inspect_png(data, asset_id, fmt)
    destination = art_path(storage, job_id, asset_id, fmt)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(destination)
    # Keep the original identity lock with approvals; changing the bible
    # invalidates old approvals instead of silently mixing character styles.
    record = dict(meta, asset_id=asset_id, identity_lock=plan["identity_lock"],
                  format="shared" if asset_id in ("luna", "tomi", "pipo") else fmt,
                  approved=True)
    destination.with_suffix(".json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def approved_path(storage: Path, job_id: str, asset_id: str, fmt: str,
                  identity_lock: str) -> Path | None:
    candidate = art_path(storage, job_id, asset_id, fmt)
    record_file = candidate.with_suffix(".json")
    if not candidate.is_file() or not record_file.is_file():
        return None
    try:
        record = json.loads(record_file.read_text(encoding="utf-8"))
        if record.get("identity_lock") != identity_lock or not record.get("approved"):
            return None
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != record.get("sha256"):
            return None
        return candidate
    except (OSError, ValueError, TypeError):
        return None


def readiness(storage: Path, job_id: str, story: dict, fmt: str,
              scene_indices: list[int] | None = None) -> dict:
    plan = create_art_plan(story, fmt)
    selected = set(scene_indices) if scene_indices is not None else None
    wanted = ["luna", "tomi", "pipo"]
    wanted += [f"scene-{scene['index']:02d}-background" for scene in plan["scenes"]
               if selected is None or scene["index"] in selected]
    existing = {}
    missing = []
    for asset_id in wanted:
        path = approved_path(storage, job_id, asset_id, fmt, plan["identity_lock"])
        if path:
            existing[asset_id] = str(path.resolve())
        else:
            missing.append(asset_id)
    return {"ready": not missing, "identity_lock": plan["identity_lock"],
            "format": fmt, "required": wanted, "missing": missing,
            "approved": existing, "art_version": plan["version"]}
