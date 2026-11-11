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


def _character(d, x, floor, scale, palette, name, phase, pointing=False, dog=False, speaking=False, walking=False):
    """Organic, hand-illustrated 2D mascot artwork with smooth silhouette curves."""
    ink = "#493044"
    def q(v): return int(v * scale)
    def bezier(p0, p1, p2, p3, steps=18):
        pts=[]
        for i in range(steps+1):
            t=i/steps; u=1-t
            px=u*u*u*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t*t*t*p3[0]
            py=u*u*u*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t*t*t*p3[1]
            pts.append((int(x+q(px)),int(floor+q(py))))
        return pts
    def shape(segments, fill, outline=ink, width=5):
        pts=[]
        for seg in segments:
            part=bezier(*seg)
            pts.extend(part if not pts else part[1:])
        if len(pts)>2 and pts[-1]!=pts[0]: pts.append(pts[0])
        d.polygon(pts,fill=fill)
        if outline: d.line(pts,fill=outline,width=max(2,q(width)),joint="curve")
    def line(segments, fill, width=12):
        pts=[]
        for seg in segments:
            part=bezier(*seg)
            pts.extend(part if not pts else part[1:])
        d.line(pts,fill=fill,width=max(2,q(width)),joint="curve")
        rad=max(2,q(width)//2)
        for px,py in (pts[0],pts[-1]):
            d.ellipse((px-rad,py-rad,px+rad,py+rad),fill=fill)
    def oval(cx,cy,rx,ry,fill,outline=None,width=2):
        b=(int(x+q(cx-rx)),int(floor+q(cy-ry)),int(x+q(cx+rx)),int(floor+q(cy+ry)))
        d.ellipse(b,fill=fill,outline=outline,width=max(2,q(width)) if outline else 1)
    bob=math.sin(phase*3.0)*q(3.5)
    walk=math.sin(phase*5.2)*q(13 if walking else 1.2)
    if dog:
        wag=math.sin(phase*7)*q(18)
        line([((-42,-103),(-62,-117),(-79,-137+wag),(-91,-128+wag)),
              ((-91,-128+wag),(-96,-121+wag),(-89,-111+wag),(-80,-111+wag))],"#a85e38",17)
        # Soft pear-shaped body and short articulated legs
        shape([((-48,-177),(-76,-166),(-76,-111),(-57,-80)),
               ((-57,-80),(-31,-57),(31,-57),(57,-80)),
               ((57,-80),(76,-111),(76,-166),(48,-177)),
               ((48,-177),(22,-194),(-22,-194),(-48,-177))],"#b97643",ink,5)
        for dx,off in [(-30,-walk*.25),(30,walk*.25)]:
            line([((dx,-94),(dx+off*.3,-69),(dx+off,-43),(dx+off,-27))],"#965333",17)
            oval(dx+off,-25,19,10,"#f4d6b7",ink,3)
        # Drooping ears with asymmetrical curved silhouettes
        shape([((-43,-253),(-81,-268),(-83,-202),(-57,-174)),
               ((-57,-174),(-39,-165),(-31,-196),(-35,-220)),
               ((-35,-220),(-36,-237),(-39,-249),(-43,-253))],"#87492f",ink,4)
        shape([((43,-253),(81,-268),(83,-202),(57,-174)),
               ((57,-174),(39,-165),(31,-196),(35,-220)),
               ((35,-220),(36,-237),(39,-249),(43,-253))],"#87492f",ink,4)
        shape([((-56,-258),(-59,-302),(-23,-318),(0,-314)),
               ((0,-314),(42,-319),(61,-286),(55,-250)),
               ((55,-250),(51,-207),(37,-178),(0,-176)),
               ((0,-176),(-38,-177),(-53,-207),(-56,-258))],"#d18a53",ink,5)
        shape([((-31,-207),(-28,-230),(-11,-239),(0,-236)),
               ((0,-236),(20,-241),(33,-225),(31,-205)),
               ((31,-205),(26,-187),(11,-181),(0,-182)),
               ((0,-182),(-17,-181),(-28,-190),(-31,-207))],"#f7dfbd",ink,3)
        for dx in (-20,20):
            oval(dx,-264,10,17,"#fffaf2",ink,2); oval(dx+2,-262,5,11,"#403044")
            oval(dx+3,-268,2.5,4,"#ffffff")
        oval(0,-218,8,5,"#403044")
        oval(0,-195,16,9,"#6d3946")
        line([((-35,-145),(-15,-132),(15,-132),(35,-145))],"#d94b62",11)
        oval(0,-143,10,13,"#ffd15c","#fff0b4",2)
        return
    shirt, shorts, accent=palette
    skin="#f5c49f"; hair="#70412e" if name=="LUNA" else "#75472e"
    # Legs are separate curved limbs with soft shoes and visible ankle cuffs
    for side,offset in [(-1,-walk),(1,walk)]:
        sx=side*25+offset
        line([((side*25,-119),(side*27,-91),(sx,-62),(sx,-34))],shorts,23)
        shape([((sx-22,-38),(sx-29,-30),(sx-34,-17),(sx-28,-12)),
               ((sx-28,-12),(sx-9,-5),(sx+22,-8),(sx+29,-17)),
               ((sx+29,-17),(sx+32,-26),(sx+24,-35),(sx+18,-38)),
               ((sx+18,-38),(sx+1,-41),(sx-12,-41),(sx-22,-38))],"#73505a",ink,4)
        line([((sx-17,-20),(sx-5,-17),(sx+9,-17),(sx+17,-20))],"#fff0cf",4)
    # Arms are curved, tapered illustrations; gestures change with the action
    arm=math.sin(phase*4.5)*8
    if pointing:
        line([((43,-225),(65,-243),(83,-274),(112,-285+arm)),
              ((112,-285+arm),(124,-290+arm),(136,-291+arm),(144,-286+arm))],skin,23)
        oval(145,-286+arm,12,13,skin,ink,3)
    else:
        for side in (-1,1):
            line([((side*47,-220),(side*73,-206+arm*side),(side*86,-180+arm*side),(side*91,-164+arm*side))],skin,22)
            oval(side*92,-161+arm*side,12,14,skin,ink,3)
    # Torso: one tailored silhouette, with collar, folds and fabric accents
    shape([((-49,-254),(-68,-246),(-70,-220),(-65,-194)),
           ((-65,-194),(-64,-159),(-57,-111),(-40,-103)),
           ((-40,-103),(-17,-91),(18,-92),(41,-104)),
           ((41,-104),(61,-116),(65,-158),(66,-194)),
           ((66,-194),(71,-224),(64,-247),(47,-254)),
           ((47,-254),(18,-266),(-19,-266),(-49,-254))],shirt,ink,6)
    line([((-40,-240),(-25,-249),(25,-249),(40,-240))],"#ffffff",3)
    # Backpack peeks naturally over the shoulders
    shape([((-48,-245),(-70,-238),(-73,-207),(-61,-179)),
           ((-61,-179),(-53,-170),(-46,-179),(-44,-198)),
           ((-44,-198),(-42,-217),(-43,-234),(-48,-245))],accent,ink,4)
    # Neck and oversized soft face silhouette
    shape([((-18,-281),(-19,-263),(-15,-248),(0,-246)),
           ((0,-246),(16,-246),(20,-263),(18,-281)),
           ((18,-281),(8,-291),(-8,-291),(-18,-281))],skin,ink,3)
    shape([((-88,-387),(-94,-446),(-57,-501),(0,-502)),
           ((0,-502),(61,-502),(96,-452),(88,-387)),
           ((88,-387),(85,-320),(55,-274),(0,-270)),
           ((0,-270),(-58,-272),(-86,-320),(-88,-387))],skin,ink,6)
    # Hair cap with flowing fringe and side locks, not separate geometric blocks
    shape([((-91,-397),(-102,-445),(-75,-498),(-30,-510)),
           ((-30,-510),(-5,-518),(23,-510),(39,-501)),
           ((39,-501),(80,-495),(103,-451),(91,-400)),
           ((91,-400),(83,-413),(79,-432),(72,-442)),
           ((72,-442),(49,-426),(32,-431),(17,-451)),
           ((17,-451),(0,-429),(-20,-428),(-35,-449)),
           ((-35,-449),(-52,-426),(-70,-430),(-78,-408)),
           ((-78,-408),(-82,-400),(-85,-395),(-91,-397))],hair,ink,5)
    # Hair framing cheeks with curved side tufts
    for side in (-1,1):
        shape([((side*83,-427),(side*100,-411),(side*91,-351),(side*72,-336)),
               ((side*72,-336),(side*61,-329),(side*59,-355),(side*63,-383)),
               ((side*63,-383),(side*65,-406),(side*72,-420),(side*83,-427))],hair,ink,4)
    if name=="LUNA":
        line([((-80,-469),(-62,-505),(-22,-510),(18,-493))],"#ff78b6",13)
        oval(78,-475,16,17,"#ffce55","#fff2c6",3)
    else:
        # Individual curved locks, integrated into the hairline
        for dx,dy in [(-53,-490),(-20,-510),(18,-512),(52,-490)]:
            oval(dx,dy,17,22,hair,ink,2)
    # Eyes: shaped whites, iris gradients simulated with layered highlights
    for dx in (-34,34):
        shape([((dx-21,-410),(dx-27,-430),(dx-18,-450),(dx,-451)),
               ((dx,-451),(dx+20,-451),(dx+27,-429),(dx+21,-410)),
               ((dx+21,-410),(dx+14,-397),(dx-14,-397),(dx-21,-410))],"#fffdf8",ink,2)
        oval(dx+1,-424,11,18,"#5594c8",None)
        oval(dx+1,-421,6,12,"#302b3d",None)
        oval(dx-2,-432,4,6,"#ffffff",None)
        line([((dx-23,-456),(dx-11,-464),(dx+5,-464),(dx+18,-456))],hair,4)
    # Eyebrows, nose, cheek blush and freckles
    line([((-59,-465),(-48,-474),(-31,-475),(-22,-468))],hair,5)
    line([((22,-468),(34,-476),(50,-475),(60,-465))],hair,5)
    oval(0,-365,7,5,"#df987a",None)
    oval(-68,-361,15,12,"#ef9297",None); oval(68,-361,15,12,"#ef9297",None)
    # Mouth swaps between closed smile and open phoneme pose
    if speaking and math.sin(phase*13)>-0.15:
        shape([((-23,-348),(-22,-365),(-9,-375),(0,-375)),
               ((0,-375),(12,-375),(23,-364),(23,-348)),
               ((23,-348),(18,-328),(-17,-328),(-23,-348))],"#552b42",ink,2)
        line([((-12,-340),(-4,-336),(5,-336),(12,-340))],"#f18b9c",4)
    else:
        line([((-22,-348),(-13,-331),(13,-331),(22,-348))],"#8c4357",5)
        line([((-13,-341),(-5,-337),(5,-337),(13,-341))],"#fff1e8",3)
    # Soft cheek highlights and small clothing details
    line([((-48,-124),(-31,-115),(-18,-113),(-9,-117))],"#ffffff",3)
    oval(0,-185,31,32,"#ffd34e","#fff0b0",3)
    # Custom star emblem, gently rounded with curved rays
    line([((0,-207),(6,-191),(20,-188),(7,-177))],"#fff8dc",4)
    line([((7,-177),(10,-162),(0,-169),(-10,-162))],"#fff8dc",4)
    line([((-10,-162),(-7,-177),(-20,-188),(-6,-191))],"#fff8dc",4)


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
        _character(d,825+int(math.sin(t*1.1+2)*9),665,.62,("#d58a48","#fff","#287cc6"),"PIPO",t,dog=True,speaking=active_speaker == "Pipo",walking=action in ("walk","explore","run"))
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
               ("#e94e9b","#8f4e9a","#ffd04d"),"LUNA",t,pointing=idx in (1,4,9),speaking=active_speaker == "Luna",walking=action in ("walk","explore","run"))
    _character(d,positions[1][0]+int(math.sin(t*1.3+1)*18),positions[1][1],positions[1][2],
               ("#287cc6","#554d9a","#f2a34d"),"TOMI",t+1,pointing=idx in (5,8,9),speaking=active_speaker == "Tomi",walking=action in ("walk","explore","run"))
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
