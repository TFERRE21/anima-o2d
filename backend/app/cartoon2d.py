"""Independent 2D cartoon preview renderer for Anima Studio.
Uses Pillow drawing + FFmpeg; does not import or alter Blender/bpy or the RX580 worker.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SECONDS = 1280, 720, 24, 8


def _font(size: int, bold: bool = False):
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for item in candidates:
        if Path(item).exists():
            return ImageFont.truetype(item, size)
    return ImageFont.load_default()


def _gradient(draw, top, bottom):
    for y in range(H):
        t = y / H
        color = tuple(int(top[i] * (1-t) + bottom[i] * t) for i in range(3))
        draw.line((0, y, W, y), fill=color)


def _character(d, x, floor, scale, palette, name, phase, pointing=False, dog=False):
    """Original flat 2D mascot with bold clean outlines and independently posed limbs."""
    outline = "#49324a"
    def p(v): return int(v * scale)
    def ell(box, fill, width=4):
        b = tuple(int(v) for v in box)
        d.ellipse(b, fill=fill, outline=outline, width=max(2,p(width)))
    def line(points, fill, width=12):
        d.line([(int(a),int(b)) for a,b in points], fill=fill,
               width=max(2,p(width)), joint="curve")
    if dog:
        # wagging tail, four legs, body and floppy ears
        wag = math.sin(phase*5)*p(16)
        line([(x-p(30),floor-p(85)),(x-p(68),floor-p(112)+wag)], "#a75d31", 13)
        ell((x-p(65),floor-p(205),x+p(65),floor-p(72)), "#d58a48")
        ell((x-p(65),floor-p(220),x-p(15),floor-p(125)), "#a75d31")
        ell((x+p(15),floor-p(220),x+p(65),floor-p(125)), "#a75d31")
        ell((x-p(57),floor-p(250),x+p(57),floor-p(145)), "#f4d7ad")
        ell((x-p(35),floor-p(220),x-p(12),floor-p(190)), "#fff8e9", 2)
        ell((x+p(12),floor-p(220),x+p(35),floor-p(190)), "#fff8e9", 2)
        ell((x-p(24),floor-p(214),x-p(14),floor-p(200)), "#382b32", 1)
        ell((x+p(14),floor-p(214),x+p(24),floor-p(200)), "#382b32", 1)
        ell((x-p(15),floor-p(183),x+p(15),floor-p(163)), "#382b32", 2)
        d.arc((x-p(24),floor-p(180),x+p(24),floor-p(140)), 10, 165, fill="#a83c54", width=p(5))
        for dx in (-28,28):
            line([(x+p(dx),floor-p(80)),(x+p(dx+math.sin(phase*5)*5),floor)], "#a75d31", 14)
        return

    skin = "#f2bd91"
    hair = "#573323" if name == "LUNA" else "#6a402c"
    shirt, shorts, accent = palette
    bob = math.sin(phase*3)*p(5)
    # legs and shoes
    stride = math.sin(phase*5)*p(20)
    for side, offset in [(-1,-stride),(1,stride)]:
        sx=x+p(side*25)
        line([(sx,floor-p(95)),(sx+offset,floor-p(24))], shorts, 17)
        ell((sx+offset-p(24),floor-p(34),sx+offset+p(25),floor-p(5)), "#563b32", 3)
    # body, backpack
    d.rounded_rectangle((x-p(58),floor-p(235),x+p(58),floor-p(85)), radius=p(34), fill=shirt, outline=outline, width=p(5))
    d.rounded_rectangle((x-p(78),floor-p(220),x-p(48),floor-p(112)), radius=p(12), fill=accent, outline=outline, width=p(4))
    # arms: pointing gesture alternates, with waving hand
    arm_swing=math.sin(phase*5)*p(18)
    if pointing:
        line([(x+p(43),floor-p(205)),(x+p(88),floor-p(250)),(x+p(135),floor-p(260))],skin,17)
        ell((x+p(125),floor-p(275),x+p(150),floor-p(250)),skin,3)
    else:
        line([(x-p(48),floor-p(205)),(x-p(82),floor-p(155)+arm_swing)],skin,16)
        line([(x+p(48),floor-p(205)),(x+p(82),floor-p(155)-arm_swing)],skin,16)
        ell((x-p(94),floor-p(170)+arm_swing,x-p(72),floor-p(145)+arm_swing),skin,3)
        ell((x+p(70),floor-p(170)-arm_swing,x+p(94),floor-p(145)-arm_swing),skin,3)
    # neck and large head
    d.rectangle((x-p(18),floor-p(270),x+p(18),floor-p(220)),fill=skin)
    ell((x-p(77),floor-p(390)+bob,x+p(77),floor-p(235)+bob),skin,5)
    # hair cap and side locks
    ell((x-p(80),floor-p(405)+bob,x+p(80),floor-p(295)+bob),hair,4)
    d.rectangle((x-p(78),floor-p(350)+bob,x-p(54),floor-p(270)+bob),fill=hair)
    d.rectangle((x+p(54),floor-p(350)+bob,x+p(78),floor-p(270)+bob),fill=hair)
    if name == "LUNA":
        d.arc((x-p(72),floor-p(397)+bob,x+p(72),floor-p(285)+bob),180,355,fill="#f15b9b",width=p(12))
        ell((x+p(42),floor-p(375)+bob,x+p(76),floor-p(340)+bob),"#ffd04d",2)
    # eyes, brows, smile
    for dx in (-29,29):
        ell((x+p(dx-15),floor-p(345)+bob,x+p(dx+15),floor-p(298)+bob),"#fffdf6",2)
        ell((x+p(dx-7),floor-p(333)+bob,x+p(dx+8),floor-p(306)+bob),"#5b8fc7",1)
        ell((x+p(dx-3),floor-p(328)+bob,x+p(dx+5),floor-p(311)+bob),"#302b36",1)
        d.arc((x+p(dx-17),floor-p(365)+bob,x+p(dx+15),floor-p(340)+bob),190,345,fill=hair,width=p(5))
    d.arc((x-p(25),floor-p(305)+bob,x+p(25),floor-p(260)+bob),10,170,fill="#9b4052",width=p(5))
    ell((x-p(62),floor-p(300)+bob,x-p(42),floor-p(280)+bob),"#ee8f91",1)
    ell((x+p(42),floor-p(300)+bob,x+p(62),floor-p(280)+bob),"#ee8f91",1)


def _draw_frame(t: float, planet: str):
    im=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(im)
    _gradient(d,(30,65,135),(255,177,127))
    # distant planets and star field
    for i in range(48):
        x=(i*197+31)%W; y=(i*83+24)%390
        r=2+(i%3)
        d.ellipse((x-r,y-r,x+r,y+r),fill="#fff0bd")
    d.ellipse((930,45,1100,215),fill="#f6c56b",outline="#fff0c9",width=5)
    # distant layered hills
    d.polygon([(0,440),(130,300),(270,420),(420,270),(590,430),(770,290),(980,430),(1120,315),(1280,430),(1280,720),(0,720)],fill="#496b87")
    d.polygon([(0,500),(180,385),(330,500),(520,365),(720,510),(920,375),(1110,500),(1280,410),(1280,720),(0,720)],fill="#327f70")
    # river / landing path
    d.polygon([(420,720),(570,470),(740,470),(930,720)],fill="#49b8d0")
    d.polygon([(0,600),(1280,600),(1280,720),(0,720)],fill="#63a95f")
    # flowers and alien foliage
    for i in range(30):
        x=(i*173+30)%W; y=560+(i%4)*38
        d.ellipse((x-8,y-20,x+8,y+20),fill=("#ffdc68" if i%2 else "#f78cbd"))
        d.ellipse((x-5,y-5,x+5,y+5),fill="#ffe9a3")
    # planet sign
    d.rounded_rectangle((955,310,1220,455),radius=22,fill="#f3d49a",outline="#573d43",width=7)
    d.text((980,330),planet[:20],font=_font(27,True),fill="#4a3941")
    d.text((980,380),"MISSÃO: AJUDAR!",font=_font(20,True),fill="#9a4a4c")
    # three friends enter frame and animate
    bob=math.sin(t*3)*7
    _character(d,390+int(math.sin(t*1.1)*35),650,1.0,("#e94e9b","#8f4e9a","#ffd04d"),"LUNA",t,pointing=(t%5<2.5))
    _character(d,620+int(math.sin(t*1.1+1)*30),650,1.0,("#287cc6","#554d9a","#f2a34d"),"TOMI",t+1,pointing=False)
    _character(d,790+int(math.sin(t*1.1+2)*24),650,0.9,("#d58a48","#fff","#287cc6"),"PIPO",t, dog=True)
    # title plate
    d.rounded_rectangle((38,35,440,105),radius=18,fill="#203a66",outline="#ffffff",width=3)
    d.text((62,54),"PEQUENOS GUARDIÕES",font=_font(27,True),fill="#ffffff")
    return im


def render_preview(output: str | Path, planet: str = "AURORA-7"):
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg não encontrado para renderizar a prévia 2D.")
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="anima-2d-") as tmp:
        temp=Path(tmp)
        for frame in range(FPS*SECONDS):
            image=_draw_frame(frame/FPS,planet)
            image.save(temp/f"frame-{frame:05d}.png",compress_level=2)
        cmd=[ffmpeg,"-y","-loglevel","error","-framerate",str(FPS),
             "-i",str(temp/"frame-%05d.png"),"-c:v","libx264","-pix_fmt","yuv420p",
             "-crf","20","-movflags","+faststart",str(output)]
        subprocess.run(cmd,check=True,capture_output=True,text=True)
    return {"output":str(output),"seconds":SECONDS,"fps":FPS,"frames":FPS*SECONDS,
            "engine":"2d-pillow-ffmpeg","planet":planet}
