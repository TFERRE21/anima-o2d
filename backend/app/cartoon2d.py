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


def _character(d, x, floor, scale, palette, name, phase, pointing=False, dog=False, speaking=False):
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
        if speaking and math.sin(phase*13.0) > -0.15:
            d.ellipse(box(x-q(22),floor-q(194)+bob,x+q(22),floor-q(151)+bob),fill="#4a2638",outline="#7e3c48",width=q(3))
            d.ellipse(box(x-q(12),floor-q(161)+bob,x+q(12),floor-q(153)+bob),fill="#f08a98")
        else:
            d.arc(box(x-q(27),floor-q(194)+bob,x+q(28),floor-q(153)+bob),5,170,fill="#a64d5b",width=q(5))
        # collar and tag
        stroke([(x-q(48),floor-q(145)),(x,floor-q(132)),(x+q(48),floor-q(145))],"#df465b",q(13))
        oval((x-q(17),floor-q(143),x+q(17),floor-q(108)),"#ffcf54","#fff2c8",3)
        d.text((x-q(10),floor-q(139)),"♥",font=_font(q(17),True),fill="#a63f56")
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
    # Mouth changes shape in sync with the active voice segment.
    if speaking and math.sin(phase*13.0) > -0.15:
        d.ellipse(box(x-q(29),floor-q(342)+bob,x+q(29),floor-q(285)+bob),fill="#54283d",outline="#7a4052",width=q(3))
        d.ellipse(box(x-q(14),floor-q(300)+bob,x+q(14),floor-q(289)+bob),fill="#f18a9a")
    else:
        d.ellipse(box(x-q(26),floor-q(337)+bob,x+q(26),floor-q(296)+bob),fill="#6b354b")
        d.arc(box(x-q(22),floor-q(323)+bob,x+q(22),floor-q(299)+bob),5,175,fill="#fff4e8",width=q(4))
        d.arc(box(x-q(10),floor-q(313)+bob,x+q(10),floor-q(297)+bob),5,170,fill="#ef7c91",width=q(5))
    # Blush cheeks and small freckles
    oval((x-q(82),floor-q(353)+bob,x-q(48),floor-q(325)+bob),"#ef9294",None,0)
    oval((x+q(48),floor-q(353)+bob,x+q(82),floor-q(325)+bob),"#ef9294",None,0)
    for dx in (-60,60):
        for dy in (-3,8):
            oval((x+q(dx),floor-q(342+dy)+bob,x+q(dx+3),floor-q(339+dy)+bob),"#d9787f",None,0)


def _draw_frame(t: float, planet: str, portrait: bool = False):
    """Rich layered storybook world with parallax-like motion and an expressive hero group."""
    im=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(im)
    _gradient(d,(52,91,171),(255,190,143))
    # soft glowing sun and drifting clouds
    d.ellipse((970,52,1128,210),fill="#ffe7a1")
    d.ellipse((1000,82,1098,180),fill="#fff2bd")
    for i in range(5):
        cx=(i*295+int(t*13))%(W+220)-100
        cy=95+(i%3)*52
        for ox,oy,rx,ry in [(0,12,64,25),(42,0,54,34),(82,15,58,24)]:
            d.ellipse((cx+ox-rx,cy+oy-ry,cx+ox+rx,cy+oy+ry),fill="#fff1e5")
    # distant floating islands and mountains
    d.polygon([(0,438),(115,300),(245,425),(390,278),(570,435),(760,290),(945,425),(1110,302),(1280,430),(1280,720),(0,720)],fill="#687eaa")
    d.polygon([(0,493),(160,370),(310,500),(490,355),(690,500),(875,370),(1070,495),(1280,385),(1280,720),(0,720)],fill="#397f83")
    # little glowing windows / trees in distant village
    for i in range(8):
        x=70+i*165
        y=432+(i%3)*17
        d.rounded_rectangle((x,y-58,x+48,y+8),radius=9,fill="#f5d69d",outline="#5c5876",width=3)
        d.polygon([(x-8,y-58),(x+24,y-91),(x+56,y-58)],fill="#c96d77",outline="#5c5876")
        d.rectangle((x+18,y-25,x+31,y+8),fill="#80604e")
    # waterfall, river and banks
    d.polygon([(525,420),(750,420),(930,720),(360,720)],fill="#69cde0")
    d.polygon([(590,430),(675,430),(760,720),(505,720)],fill="#a2edf0")
    for k in range(7):
        yy=470+k*34+int((t*38)%34)
        d.arc((500-k*18,yy,780+k*20,yy+50),5,175,fill="#e4ffff",width=4)
    d.polygon([(0,555),(250,510),(430,570),(640,535),(870,570),(1080,505),(1280,550),(1280,720),(0,720)],fill="#68ad63")
    # lush foreground trees
    for x,base,sz in [(45,590,1.2),(1200,585,1.25),(255,610,.8),(1040,615,.85)]:
        d.rectangle((x-13*sz,base-150*sz,x+13*sz,base+35),fill="#80503b")
        for ox,oy,r in [(-35,-165,58),(20,-190,66),(58,-145,54),(-5,-115,58)]:
            d.ellipse((x+(ox-r)*sz,base+(oy-r)*sz,x+(ox+r)*sz,base+(oy+r)*sz),fill="#378b61",outline="#276849",width=4)
    # foreground flowers and stones
    for i in range(34):
        x=(i*173+int(t*9))%W
        y=600+(i%4)*28
        col=("#ffdc67","#f58db9","#fff0d0")[i%3]
        for k in range(5):
            ang=k*math.pi*2/5
            px=x+math.cos(ang)*10; py=y+math.sin(ang)*10
            d.ellipse((px-7,py-7,px+7,py+7),fill=col)
        d.ellipse((x-5,y-5,x+5,y+5),fill="#ffbd45")
    for x,y,r in [(165,665,38),(1110,674,47),(980,630,24)]:
        d.ellipse((x-r,y-r*.45,x+r,y+r*.45),fill="#9b9b9a",outline="#66717a",width=4)
        d.arc((x-r+8,y-r*.3,x+r-8,y+r*.3),180,350,fill="#d6d2c7",width=4)
    # planet title plaque
    d.rounded_rectangle((34,28,465,111),radius=22,fill="#203a66",outline="#fff4d7",width=4)
    d.text((58,43),"PEQUENOS GUARDIÕES",font=_font(27,True),fill="#ffffff")
    d.text((60,78),f"AVENTURA EM {planet[:18]}",font=_font(15,True),fill="#ffdf8c")
    if portrait:
        # compact centered group so all three friends fit the vertical crop
        _character(d,475+int(math.sin(t*1.1)*12),665,.67,("#e94e9b","#8f4e9a","#ffd04d"),"LUNA",t,pointing=(t%5<2.5))
        _character(d,650+int(math.sin(t*1.1+1)*10),665,.67,("#287cc6","#554d9a","#f2a34d"),"TOMI",t+1,pointing=(t%6>3))
        _character(d,825+int(math.sin(t*1.1+2)*9),665,.62,("#d58a48","#fff","#287cc6"),"PIPO",t,dog=True,speaking=active_speaker == "Pipo")
        return im.crop((438,0,843,720)).resize((720,1280),Image.Resampling.LANCZOS)
    _character(d,350+int(math.sin(t*1.1)*22),665,.91,("#e94e9b","#8f4e9a","#ffd04d"),"LUNA",t,pointing=(t%5<2.5))
    _character(d,640+int(math.sin(t*1.1+1)*18),665,.91,("#287cc6","#554d9a","#f2a34d"),"TOMI",t+1,pointing=(t%6>3))
    _character(d,910+int(math.sin(t*1.1+2)*15),665,.83,("#d58a48","#fff","#287cc6"),"PIPO",t,dog=True)
    return im


def _draw_story_scene(t: float, planet: str, biome: str, palette: str,
                      scene_index: int, action: str = "", portrait: bool = False,
                      active_speaker: str = ""):
    """Purpose-built storyboard backgrounds: every beat cuts to a visibly new location."""
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    idx = max(0, int(scene_index))
    # Distinct art direction per planet biome.
    biome_colors = {
        "aurora": ((28,45,112),(128,104,190),"#43c8b6","#315b70"),
        "red": ((101,42,35),(246,153,75),"#e6ae51","#9d513d"),
        "ocean": ((8,70,119),(75,194,215),"#42c9db","#176c91"),
        "flora": ((50,91,65),(213,158,190),"#ef83b6","#4b9b68"),
        "cloud": ((92,119,190),(255,208,167),"#d9c5ff","#7897ce"),
        "ice": ((26,73,119),(167,222,241),"#b4efff","#477eaa"),
        "volcano": ((75,45,57),(230,139,84),"#e6b35e","#4c7655"),
        "sapphire": ((30,43,104),(111,125,204),"#72d5e8","#5368a5"),
        "petal": ((100,79,125),(255,188,199),"#f38ab4","#69a96a"),
        "moon": ((35,40,77),(154,154,183),"#a7a9cb","#596078"),
    }
    top, bottom, accent, ground = biome_colors.get(palette, biome_colors["aurora"])
    _gradient(d, top, bottom)
    # Stars, drifting particles and distant planet/moon
    for i in range(34):
        x=(i*197+int(t*(5+i%3)))%W
        y=(i*83+19)%390
        r=1+(i%3)
        d.ellipse((x-r,y-r,x+r,y+r),fill="#fff4d0")
    d.ellipse((1010,55,1150,195),fill="#fff0bc",outline="#fff9dc",width=4)
    # Establish a unique location for each beat.
    if idx == 0:  # spaceship interior
        d.rectangle((0,510,W,H),fill="#26364e")
        d.rounded_rectangle((70,90,1210,555),radius=65,fill="#263b62",outline="#9bd9ed",width=12)
        d.rounded_rectangle((160,145,1120,440),radius=40,fill="#102b4d",outline="#77d7ec",width=8)
        for i in range(9):
            x=205+i*105
            d.ellipse((x,220+(i%3)*35,x+18,238+(i%3)*35),fill="#fff1ad")
        d.polygon([(0,620),(1280,620),(1280,720),(0,720)],fill="#19283d")
        d.text((470,110),"NAVE ESTRELINHA",font=_font(35,True),fill="#fff4c9")
    elif idx == 1:  # aerial approach / planet reveal
        d.ellipse((300,155,980,835),fill=ground,outline=accent,width=14)
        for i in range(7):
            x=390+i*82
            d.arc((x,300,x+180,570),190,340,fill=accent,width=9)
        d.polygon([(0,570),(260,470),(470,565),(700,420),(960,560),(1280,440),(1280,720),(0,720)],fill=ground)
    elif idx == 2:  # settlement
        d.rectangle((0,500,W,H),fill=ground)
        for i in range(6):
            x=50+i*210
            d.rectangle((x,320,x+140,560),fill="#f5d49a",outline="#493b56",width=7)
            d.polygon([(x-18,320),(x+70,235),(x+158,320)],fill=accent,outline="#493b56")
            d.rectangle((x+50,420,x+90,560),fill="#865b4b")
            for wx in (x+20,x+100):
                d.rectangle((wx,360,wx+24,400),fill="#78d5ed",outline="#493b56",width=3)
    elif idx in (3,4,5):  # forest / investigation / planning
        d.rectangle((0,510,W,H),fill=ground)
        for i in range(7):
            x=i*205-40
            d.rectangle((x+45,250,x+85,625),fill="#79513c")
            for ox,oy,rad in [(0,220,100),(55,175,95),(-55,280,85)]:
                d.ellipse((x+ox-rad,oy-rad,x+ox+rad,oy+rad),fill=accent,outline="#244e50",width=5)
        if idx == 4:
            for i in range(5):
                x=250+i*170
                d.polygon([(x,510),(x+35,370),(x+70,510)],fill="#a9f4e6",outline="#e9fff4")
                d.ellipse((x+20,405,x+50,435),fill="#fff2a1")
        if idx == 5:
            d.rounded_rectangle((390,420,890,590),radius=28,fill="#f1d29a",outline="#634a4a",width=6)
            d.line((440,500,830,500),fill="#a06d4d",width=8)
            for x in (510,650,780):
                d.ellipse((x-20,470,x+20,510),fill=accent,outline="#fff4d5",width=4)
    elif idx in (6,7,8):  # river, cave, bridge
        d.rectangle((0,500,W,H),fill=ground)
        if idx == 6:
            d.polygon([(0,460),(300,480),(500,720),(0,720)],fill="#52c9e3")
            d.polygon([(800,470),(1280,420),(1280,720),(1000,720)],fill="#52c9e3")
            for i in range(6):
                x=120+i*180
                d.ellipse((x,545+(i%2)*45,x+75,585+(i%2)*45),fill="#a8e7ef")
        elif idx == 7:
            d.rectangle((0,0,W,H),fill="#182c4c")
            d.ellipse((180,90,1100,880),fill=ground,outline=accent,width=18)
            for i in range(6):
                x=260+i*145
                d.polygon([(x,525),(x+40,350),(x+80,525)],fill=accent,outline="#e6f9ff")
        else:
            d.polygon([(0,500),(1280,500),(1280,720),(0,720)],fill="#317b9a")
            d.polygon([(150,470),(1130,470),(1050,540),(230,540)],fill="#e7b86c",outline="#5c3e4d")
            for x in range(220,1100,110):
                d.rectangle((x,430,x+18,540),fill="#a46e4b")
    elif idx in (9,10):  # worksite then celebration
        d.rectangle((0,500,W,H),fill=ground)
        for i in range(5):
            x=170+i*230
            d.rounded_rectangle((x,370,x+120,520),radius=22,fill=accent,outline="#fff0c8",width=6)
            d.ellipse((x+38,410,x+82,454),fill="#fff0a8")
        if idx == 10:
            for i in range(24):
                x=(i*83+int(t*28))%W
                y=(i*47+int(t*45))%500
                d.ellipse((x,y,x+9,y+14),fill=("#fff0a8","#ff8fc1","#8be5ed")[i%3])
    elif idx in (11,14):  # moral / closing tableau
        d.rectangle((0,500,W,H),fill="#315b52")
        d.ellipse((430,300,850,720),fill="#fff0bb",outline="#fff8dc",width=10)
        for i in range(8):
            x=120+i*145
            d.ellipse((x,560,x+35,595),fill=accent)
        if idx == 14:
            d.rounded_rectangle((250,100,1030,285),radius=38,fill="#203a66",outline="#fff4d7",width=8)
            d.text((360,145),"A MORAL DA HISTÓRIA",font=_font(42,True),fill="#fff4d7")
    elif idx == 12:  # mission journal
        d.rectangle((0,500,W,H),fill="#263c55")
        d.rounded_rectangle((300,190,980,590),radius=28,fill="#f7e7bf",outline="#8b644c",width=12)
        for i in range(4):
            d.line((380,275+i*65,890,275+i*65),fill="#b8a27e",width=4)
        d.text((450,215),"DIÁRIO DA MISSÃO",font=_font(30,True),fill="#75503e")
    else:  # departure / spaceship window
        d.rectangle((0,500,W,H),fill="#1d2b48")
        d.rounded_rectangle((180,70,1100,610),radius=210,fill="#243b60",outline="#b8e8f4",width=15)
        d.ellipse((450,190,830,570),fill=ground,outline=accent,width=12)
    # scene-specific camera framing and foreground
    if idx not in (0,7,11,12,14):
        d.polygon([(0,620),(280,570),(500,635),(790,565),(1040,630),(1280,570),(1280,720),(0,720)],fill=ground)
    # Distinct cast staging: characters move and react in each scene.
    portrait_positions = [(440,650,.62),(640,650,.62),(840,660,.57)]
    landscape_positions = [(350,665,.86),(640,665,.86),(930,665,.78)]
    positions = portrait_positions if portrait else landscape_positions
    if idx in (0,1,12,13):
        positions = [(x,y-45,sc) for x,y,sc in positions]
    if idx == 7:
        positions = [(x,y+5,sc) for x,y,sc in positions]
    _character(d,positions[0][0]+int(math.sin(t*1.4)*22),positions[0][1],positions[0][2],
               ("#e94e9b","#8f4e9a","#ffd04d"),"LUNA",t,pointing=idx in (1,4,9),speaking=active_speaker == "Luna")
    _character(d,positions[1][0]+int(math.sin(t*1.3+1)*18),positions[1][1],positions[1][2],
               ("#287cc6","#554d9a","#f2a34d"),"TOMI",t+1,pointing=idx in (5,8,9),speaking=active_speaker == "Tomi")
    _character(d,positions[2][0]+int(math.sin(t*1.7+2)*14),positions[2][1],positions[2][2],
               ("#d58a48","#fff","#287cc6"),"PIPO",t,dog=True)
    if portrait:
        im=im.crop((360,0,920,720)).resize((720,1280),Image.Resampling.LANCZOS)
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
