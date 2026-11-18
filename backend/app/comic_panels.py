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
MAX_PANELS_PORTRAIT = 3
MAX_PANELS_LANDSCAPE = 1


def layout(width: int, height: int, portrait: bool) -> list[tuple[int, int, int, int]]:
    """Return inset panel rectangles in logical reading order."""
    m = max(15, round(min(width, height) * .025))
    gutter = max(10, round(m * .65))
    top = max(58, round(height * (.075 if portrait else .115)))
    bottom = max(24, round(height * .035))
    if portrait:
        row_h = (height - top - bottom - 2*gutter) // 3
        return [
            (m, top + i*(row_h+gutter), width-m, top + i*(row_h+gutter)+row_h)
            for i in range(MAX_PANELS_PORTRAIT)
        ]
    # Horizontal YouTube uses one immersive panel rather than a 2x2 comic
    # grid. Multi-panel 16:9 pages previously left most of the frame blank.
    visual_top=max(52,round(height*.095))
    visual_bottom=max(12,round(height*.020))
    available_height=height-visual_top-visual_bottom
    available_width=width-2*m
    panel_width=min(available_width,round(available_height*16/9))
    panel_height=min(available_height,round(panel_width*9/16))
    x0=(width-panel_width)//2
    y0=visual_top+(available_height-panel_height)//2
    return [(x0,y0,x0+panel_width,y0+panel_height)]


def comic_page(
    panels: list[Image.Image],
    size: tuple[int, int],
    title: str,
    portrait: bool,
    stage: str,
    previous_count: int,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Render inked comic panels while revealing exactly the next story frame.

    panels contains frames from the *current page*, last is the active frame.
    stage=paper leaves the current panel empty, stage=sketch shows grayscale
    pencil contours (only if supplied by caller), stage=color finishes it.
    """
    w, h = size
    rects = layout(w, h, portrait)
    page = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(page)
    d.rectangle((0, 0, w-1, h-1), outline=INK, width=5)
    header_y = max(8, round(h * .017))
    header_height = max(38, round(h * (.058 if portrait else .085)))
    d.rounded_rectangle((17, header_y, w-17, header_y+header_height),
                        radius=15, fill=INK, outline=BORDER, width=3)
    title = title.upper().strip()[:48] or "UMA NOVA AVENTURA"
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                              max(15, min(29, w//34))) if os.path.isfile(
                                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") else ImageFont.load_default()
    text_box = d.textbbox((0, 0), title, font=font)
    if text_box[2] > w-60:
        while title and d.textbbox((0, 0), title, font=font)[2] > w-60:
            title = title[:-1]
    d.text((max(18, (w-d.textbbox((0,0), title, font=font)[2])//2),
            header_y+max(4, (header_height-(text_box[3]-text_box[1]))//2)),
           title, font=font, fill="#ffffff")
    if not panels or len(panels) > len(rects):
        raise ValueError("O número de quadros não cabe nesta página.")
    active_rect = rects[len(panels)-1]
    for i, source in enumerate(panels):
        x0,y0,x1,y1=rects[i]
        d.rounded_rectangle((x0-4,y0-4,x1+4,y1+4),radius=9,
                            fill="#fffefe",outline=INK,width=4)
        if i == len(panels)-1 and stage == "paper":
            continue
        image = ImageOps.fit(source.convert("RGB"), (x1-x0, y1-y0),
                             Image.Resampling.LANCZOS)
        page.paste(image, (x0,y0))
        d.rectangle((x0,y0,x1,y1),outline=INK,width=4)
    return page,active_rect


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
