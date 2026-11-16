"""Official recurring cast: render story panels from the approved reference sheet.

Set ANIMA_OFFICIAL_MODEL to a persistent PNG containing the approved Luna,
Tomi and Pipo character sheet. This is an asset-based renderer, NOT a
generative image model: characters remain recognisable but poses are limited
until individual pose sheets are provided.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

MODEL_DEFAULT = "/data/jobs/series/official-model.png"
REFERENCE_SIZE = (1122, 1402)
# Coordinates in the approved 1122x1402 reference sheet, not in video pixels.
CAST = {
    "luna": (185, 180, 465, 570),
    "tomi": (470, 175, 702, 570),
    "pipo": (705, 290, 925, 570),
}
INK = (29, 41, 57)
PAPER = (255, 249, 237)


def model_path() -> Path:
    return Path(os.getenv("ANIMA_OFFICIAL_MODEL", MODEL_DEFAULT))


def has_official_model() -> bool:
    return model_path().is_file()


def _typeface(size: int, bold: bool = False):
    from backend.app.cartoon2d import _font
    return _font(size, bold)


def _character_from_sheet(sheet: Image.Image, character: str) -> Image.Image:
    """Extract ink, keeping the sheet's authentic contours and facial details.

    Light paper is made transparent, while black and grey ink remains opaque.
    This avoids a hard rectangular crop and allows colored scenic backgrounds.
    """
    bounds = CAST[character]
    sx = sheet.width / REFERENCE_SIZE[0]
    sy = sheet.height / REFERENCE_SIZE[1]
    box = tuple(round(value * (sx if i % 2 == 0 else sy))
                for i, value in enumerate(bounds))
    crop = sheet.convert("RGB").crop(box)
    grayscale = ImageOps.grayscale(crop)
    # A curve keeps anti-aliased line art while clearing the source paper.
    alpha = grayscale.point(lambda intensity: max(0, min(255, int((235-intensity)*2.1))))
    # Knock out stray scenic lines outside the approximate figure outline.
    w, h = crop.size
    if character == "luna":
        polygon = [(0,.30),(.05,.18),(.24,.06),(.45,.03),(.70,.03),(.87,.12),
                   (.96,.23),(.94,.38),(.84,.46),(.96,.58),(.98,.72),
                   (.87,.80),(.96,1),(.06,1),(.13,.80),(.06,.66),
                   (.12,.56),(0,.50)]
    elif character == "tomi":
        polygon = [(.08,.22),(.19,.10),(.47,.02),(.70,.02),(.93,.15),
                   (.98,.32),(.88,.45),(.97,.56),(1,.73),(.88,.78),
                   (.98,1),(.02,1),(.12,.81),(.02,.73),(.13,.51),
                   (.01,.36)]
    else:
        polygon = [(.17,.16),(.32,.06),(.59,.02),(.67,.10),(.87,.17),
                   (1,.36),(.99,.69),(.86,.79),(.95,.96),(.02,.96),
                   (.10,.78),(0,.59),(.02,.37)]
    mask = Image.new("L", (w,h), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([(round(px*w), round(py*h)) for px,py in polygon], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.0))
    from PIL import ImageChops
    alpha = ImageChops.multiply(alpha, mask)
    rgba = Image.new("RGBA", crop.size, (*INK, 0))
    rgba.putalpha(alpha)
    return rgba


def _scene_background(size: tuple[int,int], scene_index: int, planet: str,
                      action: str) -> Image.Image:
    w, h = size
    background = Image.new("RGB", size, PAPER)
    d = ImageDraw.Draw(background)
    # Professional comic ink: restrained contours, colored paper, scene depth.
    line = (53, 61, 72)
    horizon = int(h*.67)
    sky_variations = [(244,241,226),(237,244,240),(245,238,241),(241,242,250)]
    d.rectangle((0, 0, w, horizon), fill=sky_variations[scene_index % 4])
    radius = int(h*.10)
    sun_x = int(w*(.77 + .04*math.sin(scene_index)))
    sun_y = int(h*.17)
    d.ellipse((sun_x-radius,sun_y-radius,sun_x+radius,sun_y+radius),
              fill=(255,249,225), outline=line, width=3)
    for ring in (1.0, .75):
        ry = int(h * (.39 + .09*ring))
        d.arc((-int(w*.25), ry-int(h*.36), int(w*1.25),ry+int(h*.45)),
              184, 355, fill=(112,116,122), width=2)
    for n in range(3):
        x=int(w*(.13 + .32*n+.04*math.sin(scene_index+n)))
        y=int(h*(.19 + .035*(n%2)))
        d.ellipse((x-45,y-12,x+40,y+12), outline=line, width=2)
        d.ellipse((x-20,y-22,x+12,y+6), fill=sky_variations[scene_index%4],
                  outline=line,width=2)
    for j in range(5):
        cx = round(w*(j/4-.03))
        cy = round(h*(.70 + .035*math.sin(j+scene_index)))
        d.ellipse((cx-int(w*.25),cy-int(h*.18),cx+int(w*.25),cy+int(h*.14)),
                  fill=(241,237,220),outline=line,width=3)
    d.rectangle((0,int(h*.84),w,h),fill=(243,238,222))
    d.line((0,int(h*.84),w,int(h*.84)),fill=line,width=3)
    for i in range(12):
        x=int((i+.5)*w/12)
        y=int(h*(.86+.085*((i*7+scene_index)%5)/5))
        d.arc((x-15,y-13,x+15,y+16),0,180,fill=line,width=2)
        d.ellipse((x-5,y-17,x+5,y-7),outline=line,width=2)
    # Episode-specific label replaces recycled title cards.
    title = str(action or planet or "Nossa aventura").strip().upper()[:62]
    if title:
        d.rounded_rectangle((int(w*.04),int(h*.025),int(w*.96),int(h*.115)),
                            radius=16,fill=(20,43,68),outline=(221,174,70),width=3)
        font = _typeface(max(17,int(w*.025)),True)
        while title and d.textbbox((0,0),title,font=font)[2] > w*.84:
            title=title[:-1]
        d.text((w//2,int(h*.067)),title,font=font,fill="white",anchor="mm")
    return background


def draw_official_scene(scene_index: int, planet: str, action: str,
                        width: int = 1280, height: int = 720) -> Image.Image:
    path = model_path()
    if not path.is_file():
        raise FileNotFoundError(
            "O modelo oficial Luna/Tomi/Pipo ainda não foi instalado. "
            f"Coloque o PNG aprovado em {path} (ou configure ANIMA_OFFICIAL_MODEL). "
            "A produção foi bloqueada para não voltar aos bonecos antigos."
        )
    with Image.open(path) as source:
        source.load()
        if source.width < 800 or source.height < 1000:
            raise ValueError("A prancha oficial deve ter pelo menos 800x1000 pixels.")
        sprites = {name:_character_from_sheet(source,name) for name in CAST}
    scene = _scene_background((width,height),scene_index,planet,action)
    page = scene.convert("RGBA")
    # Cast remains exactly the same from one panel to the next.
    roster = ["luna","tomi","pipo"]
    positions = [(.21,.66,.37),(.47,.66,.34),(.72,.66,.26)]
    if scene_index % 3 == 1:
        positions=[(.13,.68,.32),(.43,.65,.39),(.73,.69,.24)]
    elif scene_index % 3 == 2:
        positions=[(.27,.68,.34),(.53,.68,.32),(.77,.70,.27)]
    for name,(cx,base,scale) in zip(roster,positions):
        sprite=sprites[name]
        target_height=round(height*scale)
        target_width=round(sprite.width*target_height/max(1,sprite.height))
        sprite=sprite.resize((target_width,target_height),Image.Resampling.LANCZOS)
        x=round(width*cx-target_width*.5)
        y=round(height*base-target_height)
        page.alpha_composite(sprite,(x,y))
    return page.convert("RGB")
