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
CAST_IDS = frozenset(("luna", "tomi", "pipo"))


def official_cast_path(storage: Path, asset_id: str) -> Path:
    """Season-wide canonical cast shared by ALL planets and episodes."""
    if asset_id not in CAST_IDS:
        raise ValueError("Somente protagonistas podem ter aparência oficial fixa.")
    return storage / "series" / "characters" / "official" / (asset_id + ".png")


def locked_cast_path(storage: Path, asset_id: str, identity_lock: str) -> Path | None:
    try:
        candidate = official_cast_path(storage, asset_id)
    except ValueError:
        return None
    manifest = candidate.with_suffix(".json")
    if not candidate.is_file() or not manifest.is_file():
        return None
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if (not record.get("approved") or record.get("identity_lock") != identity_lock
                or hashlib.sha256(candidate.read_bytes()).hexdigest() != record.get("sha256")):
            return None
    except (OSError, ValueError, TypeError):
        return None
    return candidate


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


def cutout_white_background(data: bytes) -> bytes:
    """Remove connected near-white border on an isolated character illustration.

    If the source has complex background colors, do not invent a mask: request
    a real transparent PNG instead. Does not imply a perfect hair matte.
    """
    from collections import deque
    with Image.open(io.BytesIO(data)) as original:
        original.load()
        image = original.convert("RGBA")
    w, h = image.size
    if w * h > 3_000_000:
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        w, h = image.size
    px = image.load()
    corners = (px[0, 0], px[w-1, 0], px[0, h-1], px[w-1, h-1])
    if not all(min(p[0], p[1], p[2]) >= 228 for p in corners):
        raise ValueError("Não foi possível isolar o personagem: fundo não é branco uniforme.")
    mask = Image.new("L", (w, h), 255)
    alpha = mask.load()
    flood = deque([(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)])
    while flood:
        x, y = flood.popleft()
        if not 0 <= x < w or not 0 <= y < h or alpha[x, y] == 0:
            continue
        red, green, blue, _ = px[x, y]
        if min(red, green, blue) < 224 or max(red, green, blue)-min(red, green, blue) > 25:
            continue
        alpha[x, y] = 0
        flood.extend(((x+1, y), (x-1, y), (x, y+1), (x, y-1)))
    image.putalpha(mask)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def approve_art(storage: Path, job_id: str, asset_id: str, fmt: str,
                data: bytes, story: dict, auto_cutout: bool = False) -> dict:
    plan = create_art_plan(story, fmt)
    allowed = set(("luna", "tomi", "pipo"))
    allowed |= {f"scene-{scene['index']:02d}-background" for scene in plan["scenes"]}
    allowed |= {f"scene-{scene['index']:02d}-foreground" for scene in plan["scenes"]}
    if asset_id not in allowed:
        raise ValueError("Material não corresponde a uma cena deste roteiro.")
    if auto_cutout and asset_id in {"luna", "tomi", "pipo"}:
        # A hosted AI image model can generate a genuine transparent PNG.
        # Preserve that alpha matte; white-background removal is only needed
        # for opaque ComfyUI/Runway candidates.
        with Image.open(io.BytesIO(data)) as candidate:
            rgba = candidate.convert("RGBA")
            alpha_min, alpha_max = rgba.getchannel("A").getextrema()
            already_cut_out = alpha_min < 50 and alpha_max > 200
        if not already_cut_out:
            data = cutout_white_background(data)
    meta = inspect_png(data, asset_id, fmt)
    is_cast = asset_id in CAST_IDS
    destination = (official_cast_path(storage, asset_id) if is_cast
                   else art_path(storage, job_id, asset_id, fmt))
    if is_cast and locked_cast_path(storage, asset_id, plan["identity_lock"]):
        raise ValueError(
            "Personagem oficial já está aprovado e fixo para toda a série. "
            "Não é permitido recriá-lo em outro episódio."
        )
    if is_cast and destination.exists():
        raise ValueError(
            "Já existe uma versão oficial deste personagem. Atualização exige "
            "migração administrativa da biblioteca, não aprovação de episódio."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if is_cast:
        # File-level O_EXCL ensures even simultaneous approvals cannot replace
        # an existing official hero across FastAPI threads or app processes.
        try:
            with destination.open("xb") as output:
                output.write(data)
        except FileExistsError as exc:
            raise ValueError("Personagem oficial já existe e está bloqueado na série.") from exc
    else:
        tmp = destination.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(destination)
    record = dict(meta, asset_id=asset_id, identity_lock=plan["identity_lock"],
                  format="series" if is_cast else fmt,
                  official=bool(is_cast), approved=True)
    destination.with_suffix(".json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def approved_path(storage: Path, job_id: str, asset_id: str, fmt: str,
                  identity_lock: str) -> Path | None:
    if asset_id in CAST_IDS:
        # Never accept an episode-local protagonist: only the locked
        # season-wide file is valid, independent of planet, edit or job.
        return locked_cast_path(storage, asset_id, identity_lock)
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
