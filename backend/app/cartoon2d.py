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

W, H, FPS, SECONDS = 1280, 720, 24, 10


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
    """Polished original 2D storybook mascot: layered shapes, expressive face and acting."""
    ink = "#573747"
    def q(v): return int(v * scale)
    def box(x1,y1,x2,y2): return (int(x1),int(y1),int(x2),int(y2))
    def oval(b, fill, outline=ink, width=5):
        d.ellipse(box(*b), fill=fill, outline=outline, width=max(2,q(width)) if outline else 1)
    def stroke(points, fill, width=12):
        d.line([(int(a),int(b)) for a,b in points], fill=fill, width=max(2,q(width)), joint="curve")
    bob = math.sin(phase*3.0)*q(4)
    walk = math.sin(phase*5.2)*q(18)
    if dog:
        wag = math.sin(phase*7)*q(24)
        # Tail behind body, animated wag
        stroke([(x-q(40),floor-q(95)),(x-q(78),floor-q(130)+wag),(x-q(88),floor-q(112)+wag)],"#a95f39",q(17))
        oval((x-q(70),floor-q(228),x+q(70),floor-q(68)),"#c77b45",ink,5)
        # legs and paws
        for dx,off in [(-34,-walk*.35),(34,walk*.35)]:
            stroke([(x+q(dx),floor-q(100)),(x+q(dx)+off,floor-q(20))],"#a95f39",17)
            oval((x+q(dx)+off-q(23),floor-q(30),x+q(dx)+off+q(25),floor+q(2)),"#f3d6b4",ink,3)
        # floppy ears and head
        oval((x-q(75),floor-q(270)+bob,x-q(20),floor-q(155)+bob),"#98552f",ink,5)
        oval((x+q(20),floor-q(270)+bob,x+q(75),floor-q(155)+bob),"#98552f",ink,5)
        oval((x-q(66),floor-q(300)+bob,x+q(66),floor-q(160)+bob),"#d99557",ink,6)
        # forehead patch and muzzle
        oval((x-q(24),floor-q(292)+bob,x+q(24),floor-q(228)+bob),"#f4d6ad",None,0)
        oval((x-q(48),floor-q(218)+bob,x+q(48),floor-q(158)+bob),"#f8e4c6",ink,3)
        for dx in (-25,25):
            oval((x+q(dx-10),floor-q(255)+bob,x+q(dx+10),floor-q(224)+bob),"#fffdf8",None,0)
            oval((x+q(dx-5),floor-q(250)+bob,x+q(dx+6),floor-q(226)+bob),"#493747",None,0)
            oval((x+q(dx-2),floor-q(248)+bob,x+q(dx+2),floor-q(240)+bob),"#ffffff",None,0)
        oval((x-q(19),floor-q(206)+bob,x+q(19),floor-q(185)+bob),"#392b35",None,0)
        d.arc(box(x-q(27),floor-q(194)+bob,x+q(28),floor-q(153)+bob),5,170,fill="#a64d5b",width=q(5))
        # collar and tag
        stroke([(x-q(48),floor-q(145)),(x,floor-q(132)),(x+q(48),floor-q(145))],"#df465b",q(13))
        oval((x-q(17),floor-q(143),x+q(17),floor-q(108)),"#ffcf54","#fff2c8",3)
        d.text((x-q(10),floor-q(139),"♥"),font=_font(q(17),True),fill="#a63f56")
        return

    skin="#f6c49e"; hair="#70412e" if name=="LUNA" else "#75472e"
    shirt, shorts, accent=palette
    # Backpack visible behind the torso
    d.rounded_rectangle(box(x-q(55),floor-q(258),x+q(73),floor-q(110)),radius=q(25),fill=accent,outline=ink,width=q(5))
    # Legs, socks and chunky sneakers
    for side,offset in [(-1,-walk),(1,walk)]:
        sx=x+q(side*27)
        stroke([(sx,floor-q(128)),(sx+offset,floor-q(35))],shorts,22)
        d.rounded_rectangle(box(sx+offset-q(24),floor-q(51),sx+offset+q(23),floor-q(22)),radius=q(10),fill="#ffdf8a",outline=ink,width=q(3))
        d.rounded_rectangle(box(sx+offset-q(39),floor-q(35),sx+offset+q(34),floor+q(2)),radius=q(14),fill="#704b53",outline=ink,width=q(5))
        stroke([(sx+offset-q(22),floor-q(23)),(sx+offset+q(18),floor-q(23))],"#fff1cf",q(5))
    # Arms behind body, with a clear wave / point gesture
    arm=math.sin(phase*4.5)*q(13)
    if pointing:
        stroke([(x+q(43),floor-q(235)),(x+q(86),floor-q(290)+arm),(x+q(129),floor-q(303)+arm)],skin,25)
        oval((x+q(116),floor-q(323)+arm,x+q(151),floor-q(287)+arm),skin,ink,4)
        for k in range(3):
            stroke([(x+q(140+k*2),floor-q(302)+arm),(x+q(154+k*2),floor-q(312)+arm)],skin,5)
    else:
        stroke([(x-q(45),floor-q(235)),(x-q(90),floor-q(177)+arm)],skin,24)
        oval((x-q(106),floor-q(192)+arm,x-q(73),floor-q(158)+arm),skin,ink,4)
        stroke([(x+q(45),floor-q(235)),(x+q(90),floor-q(180)-arm)],skin,24)
        oval((x+q(74),floor-q(196)-arm,x+q(108),floor-q(160)-arm),skin,ink,4)
    # Torso with layered shirt and emblem
    d.rounded_rectangle(box(x-q(68),floor-q(274),x+q(68),floor-q(104)),radius=q(42),fill=shirt,outline=ink,width=q(6))
    d.rounded_rectangle(box(x-q(54),floor-q(257),x+q(54),floor-q(116)),radius=q(30),fill=shirt,outline=None)
    # central golden explorer badge
    oval((x-q(34),floor-q(214),x+q(34),floor-q(146)),"#ffd34e","#fff0b0",4)
    d.polygon([(x,floor-q(204)),(x+q(8),floor-q(185)),(x+q(27),floor-q(183)),(x+q(12),floor-q(169)),(x+q(17),floor-q(151)),(x,floor-q(161)),(x-q(17),floor-q(151)),(x-q(12),floor-q(169)),(x-q(27),floor-q(183)),(x-q(8),floor-q(185))],fill="#fff7d7")
    # Neck and oversized head
    d.rounded_rectangle(box(x-q(22),floor-q(318),x+q(22),floor-q(255)),radius=q(14),fill=skin,outline=ink,width=q(3))
    head_top=floor-q(490)+bob
    oval((x-q(91),head_top,x+q(91),floor-q(265)+bob),skin,ink,6)
    # Hair silhouette, side locks and fringe
    oval((x-q(96),floor-q(503)+bob,x+q(96),floor-q(365)+bob),hair,ink,5)
    d.polygon([(x-q(92),floor-q(442)+bob),(x-q(70),floor-q(475)+bob),(x-q(40),floor-q(449)+bob),(x-q(10),floor-q(479)+bob),(x+q(18),floor-q(449)+bob),(x+q(48),floor-q(476)+bob),(x+q(91),floor-q(439)+bob),(x+q(84),floor-q(380)+bob),(x-q(86),floor-q(380)+bob)],fill=hair)
    d.rounded_rectangle(box(x-q(92),floor-q(432)+bob,x-q(66),floor-q(300)+bob),radius=q(13),fill=hair)
    d.rounded_rectangle(box(x+q(66),floor-q(432)+bob,x+q(92),floor-q(300)+bob),radius=q(13),fill=hair)
    if name=="LUNA":
        d.arc(box(x-q(89),floor-q(500)+bob,x+q(89),floor-q(350)+bob),190,350,fill="#ff75b5",width=q(15))
        oval((x+q(49),floor-q(478)+bob,x+q(88),floor-q(439)+bob),"#ffcf4e","#fff4c8",3)
        oval((x+q(59),floor-q(469)+bob,x+q(78),floor-q(450)+bob),"#f28bb3",None,0)
    else:
        # soft curls along the top
        for dx in (-58,-20,20,58):
            oval((x+q(dx-23),floor-q(509)+bob,x+q(dx+23),floor-q(457)+bob),hair,ink,3)
    # Big expressive eyes with irises, pupils and highlights
    eye_y=floor-q(397)+bob
    for dx in (-36,36):
        oval((x+q(dx-24),eye_y-q(34),x+q(dx+24),eye_y+q(35)),"#fffdf8",ink,3)
        oval((x+q(dx-13),eye_y-q(18),x+q(dx+13),eye_y+q(23)),"#5a91c8",None,0)
        oval((x+q(dx-8),eye_y-q(13),x+q(dx+9),eye_y+q(22)),"#352b3c",None,0)
        oval((x+q(dx-7),eye_y-q(12),x+q(dx-1),eye_y-q(4)),"#ffffff",None,0)
        d.arc(box(x+q(dx-25),eye_y-q(47),x+q(dx+24),eye_y-q(18)),190,345,fill=hair,width=q(5))
    # eyebrows and nose
    d.arc(box(x-q(67),floor-q(456)+bob,x-q(10),floor-q(420)+bob),195,330,fill=hair,width=q(7))
    d.arc(box(x+q(10),floor-q(456)+bob,x+q(67),floor-q(420)+bob),210,345,fill=hair,width=q(7))
    oval((x-q(9),floor-q(353)+bob,x+q(9),floor-q(339)+bob),"#df987a",None,0)
    # Smile with mouth cavity and tongue
    d.ellipse(box(x-q(26),floor-q(337)+bob,x+q(26),floor-q(296)+bob),fill="#6b354b")
    d.arc(box(x-q(22),floor-q(323)+bob,x+q(22),floor-q(299)+bob),5,175,fill="#fff4e8",width=q(4))
    d.arc(box(x-q(10),floor-q(313)+bob,x+q(10),floor-q(297)+bob),5,170,fill="#ef7c91",width=q(5))
    # Blush cheeks and small freckles
    oval((x-q(82),floor-q(353)+bob,x-q(48),floor-q(325)+bob),"#ef9294",None,0)
    oval((x+q(48),floor-q(353)+bob,x+q(82),floor-q(325)+bob),"#ef9294",None,0)
    for dx in (-60,60):
        for dy in (-3,8):
            oval((x+q(dx),floor-q(342+dy)+bob,x+q(dx+3),floor-q(339+dy)+bob),"#d9787f",None,0)


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
