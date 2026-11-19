"""Professional comic-page layout for narrator-led 2D videos.

Presents original panel artwork in a framed comic-page layout. A real human
hand is rendered only when an actual photographed transparent hand PNG is
provided; it never substitutes a floating cartoon pencil. The page engine
does not purport to produce generative, illustrator-quality new drawings.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

PAPER = "#fff9ef"
INK = "#263143"
BORDER = "#f3c85d"
MAX_PANELS_PORTRAIT = 1
MAX_PANELS_LANDSCAPE = 1


def layout(width: int, height: int, portrait: bool) -> list[tuple[int, int, int, int]]:
    """One scene = one complete video frame in both formats.

    Return the full-frame canvas for the drawing progress mask. Unlike the
    old comic-book pages, no 2x1/2x2/3-panel layout is ever permitted.
    """
    if width < 1 or height < 1:
        raise ValueError("O vídeo precisa ter largura e altura positivas.")
    return [(0, 0, width, height)]


def _fill_scene(image: Image.Image, size: tuple[int, int], portrait: bool) -> Image.Image:
    """Fill every pixel, while keeping all characters when source is wide.

    9:16 often receives a landscape AI illustration containing the full trio.
    An aggressive center-crop would remove Luna or Pipo. Instead fill the
    canvas with a blurred version of the scene and place the complete
    illustration across its full width in the central focal area. There are
    no beige/black bars and no additional comic panels.
    """
    source=image.convert("RGB")
    w,h=size
    if not portrait:
        return ImageOps.fit(source,size,Image.Resampling.LANCZOS,
                            centering=(.5,.5))
    if abs(source.width/source.height - w/h) < .08:
        return ImageOps.fit(source,size,Image.Resampling.LANCZOS)
    from PIL import ImageFilter
    bg=ImageOps.fit(source,size,Image.Resampling.LANCZOS).filter(
        ImageFilter.GaussianBlur(radius=max(10,int(w*.045))))
    foreground=ImageOps.contain(source,size,Image.Resampling.LANCZOS)
    x=(w-foreground.width)//2
    y=(h-foreground.height)//2
    bg.paste(foreground,(x,y))
    return bg


def comic_page(
    panels: list[Image.Image],
    size: tuple[int, int],
    title: str,
    portrait: bool,
    stage: str,
    previous_count: int,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Draw one immersive scene, no paper margins or accumulated panels.

    Preserves the original sketch/paint reveal and the authentic speech
    balloons already drawn into the input artwork by the narrator engine.
    """
    if len(panels) != 1:
        raise ValueError("Cada cena deve ocupar a tela inteira, sem quadros anteriores.")
    w,h=size
    image=_fill_scene(panels[0],size,portrait)
    rect=layout(w,h,portrait)[0]
    if stage=="paper":
        # Start with the same scene colors softly obscured; progressive
        # drawing reveals the ink and original vivid color in this area.
        from PIL import ImageFilter, ImageEnhance
        image=ImageEnhance.Color(
            image.filter(ImageFilter.GaussianBlur(radius=max(6,w//55)))
        ).enhance(.25)
    return image,rect


def hand_asset() -> Path | None:
    """One-time optional asset must be a real transparent photograph of a hand.

    No imaginary/photo-looking synthetic hand is substituted silently.
    """
    raw = os.getenv("ANIMA_REAL_HAND_PNG", "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_file():
        raise FileNotFoundError(
            "Mão real não encontrada em ANIMA_REAL_HAND_PNG: " + str(path)
            + ". Informe um PNG RGBA recortado de uma fotografia real."
        )
    with Image.open(path) as hand:
        if hand.mode != "RGBA" or hand.getchannel("A").getextrema()[0] >= 245:
            raise ValueError(
                "ANIMA_REAL_HAND_PNG precisa ser um PNG RGBA com fundo transparente, "
                "preferencialmente uma fotografia da mão segurando uma caneta."
            )
        if hand.width < 150 or hand.height < 150:
            raise ValueError("PNG da mão real pequeno demais para Full HD.")
    return path


def real_hand_video() -> Path | None:
    """Optional real filming of a hand drawing against a green-screen backdrop.

    Video should have consistent lighting, no copyrighted branding, and a
    saturated green screen (#00ff00) for the CPU FFmpeg chromakey pipeline.
    The same clip can be reused across the whole series.
    """
    raw=os.getenv("ANIMA_REAL_HAND_VIDEO","").strip()
    if not raw:
        return None
    path=Path(raw)
    if not path.is_file() or path.suffix.lower() not in {".mp4",".mov",".webm"}:
        raise FileNotFoundError(
            "Filmagem da mão real não encontrada em ANIMA_REAL_HAND_VIDEO. "
            "Forneça MP4/MOV/WebM gravado com fundo verde."
        )
    if path.stat().st_size < 1024:
        raise ValueError("Filmagem da mão não contém dados suficientes.")
    return path


def scene_art_path(workdir: Path, scene_index: int) -> Path | None:
    """Optional one-time curated illustration library for each episode.

    Assets are never fake-generated via CPU edge effects. Keeping a stable
    curated illustration source is essential to matching a visual reference.
    """
    folder = workdir / "comic-art"
    for ext in ("png", "webp", "jpg"):
        file = folder / f"scene-{scene_index:02d}.{ext}"
        if file.is_file():
            return file
    return None
