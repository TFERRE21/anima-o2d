from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from backend.app.cartoon2d import W, H, _character, _draw_story_scene, _font, _gradient

OUT = ROOT / "docs" / "images" / "character-sheet-cartoon2d.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

WIDTH, CARD_H, HEADER_H, GROUP_H = 1920, 700, 150, 1080
sheet = Image.new("RGB", (WIDTH, HEADER_H + CARD_H + GROUP_H), "#f5f0e8")
draw = ImageDraw.Draw(sheet)
draw.rectangle((0, 0, WIDTH, HEADER_H), fill="#182b49")
draw.text((70, 34), "PEQUENOS GUARDIÕES", font=_font(52, True), fill="#fff4d8")
draw.text((74, 100), "Prancha oficial • arte gerada pelo renderizador Cartoon 2D do Anima Studio",
          font=_font(23), fill="#c9d9ef")

characters = [
    ("LUNA", "Inventora e exploradora", ("#e94e9b", "#8f4e9a", "#ffd04d"), "#fff0f6"),
    ("TOMI", "Planejador e explorador", ("#287cc6", "#554d9a", "#f2a34d"), "#edf6ff"),
    ("PIPO", "Companheiro farejador", ("#d58a48", "#fff", "#287cc6"), "#fff5e8"),
]
card_w = WIDTH // 3
for index, (name, role, palette, bg) in enumerate(characters):
    left = index * card_w
    card = Image.new("RGB", (card_w, CARD_H), bg)
    cd = ImageDraw.Draw(card)
    _gradient(cd, (250, 247, 241), (222, 231, 241) if name != "PIPO" else (247, 229, 205))
    # The individual portrait calls the exact character drawing routine used by episode frames.
    _character(cd, card_w // 2, 675, 1.12, palette, name, 0.8 + index * 0.6,
               pointing=(name == "LUNA"), dog=(name == "PIPO"),
               speaking=(name == "TOMI"), walking=False)
    cd.rounded_rectangle((24, 24, card_w-24, 104), radius=22, fill="#ffffff", outline="#d7d1c8", width=3)
    cd.text((48, 36), name, font=_font(34, True), fill="#26344e")
    cd.text((50, 76), role, font=_font(19), fill="#5b6371")
    sheet.paste(card, (left, HEADER_H))

group = _draw_story_scene(2.4, "AURORA-7", "floresta", "aurora", 4,
                          "walk", portrait=False, active_speaker="Luna")
group = group.resize((WIDTH, GROUP_H), Image.Resampling.LANCZOS)
sheet.paste(group, (0, HEADER_H + CARD_H))
gd = ImageDraw.Draw(sheet)
gd.rounded_rectangle((36, HEADER_H + CARD_H + 28, 520, HEADER_H + CARD_H + 92),
                     radius=18, fill="#182b49", outline="#fff0cf", width=2)
gd.text((58, HEADER_H + CARD_H + 43), "CENA DE GRUPO • MOTOR REAL", font=_font(23, True), fill="#fff4d8")

sheet.save(OUT, format="PNG", optimize=True)
print(f"Imagem gerada pelo motor real: {OUT}")
