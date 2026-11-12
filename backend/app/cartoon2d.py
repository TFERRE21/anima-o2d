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
    def bezier(p0, p1, p2=None, p3=None, steps=18):
        # Normalize quadratic and straight segments to cubic Bezier curves.
        # The artwork contains 2-, 3- and 4-point segments.
        if p3 is None and p2 is not None:
            control, end = p1, p2
            p1 = (p0[0] + (2.0/3.0)*(control[0]-p0[0]),
                  p0[1] + (2.0/3.0)*(control[1]-p0[1]))
            p2 = (end[0] + (2.0/3.0)*(control[0]-end[0]),
                  end[1] + (2.0/3.0)*(control[1]-end[1]))
            p3 = end
        elif p3 is None and p2 is None:
            end = p1
            p1 = (p0[0] + (end[0]-p0[0])/3.0,
                  p0[1] + (end[1]-p0[1])/3.0)
            p2 = (p0[0] + 2.0*(end[0]-p0[0])/3.0,
                  p0[1] + 2.0*(end[1]-p0[1])/3.0)
            p3 = end
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
    """Organic 2D cartoon world: curved landscapes, layered foliage and illustrated props."""
    im=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(im)
    palettes={
        "aurora":((41,70,139),(167,139,205),"#5bc8b0","#377c70"),
        "red":((117,61,57),(246,174,112),"#f0c06d","#a95d50"),
        "ocean":((16,91,139),(121,211,220),"#55d3df","#267d9a"),
        "flora":((55,111,83),(226,174,198),"#f18bb8","#4c9b69"),
        "cloud":((101,137,199),(255,216,181),"#d8c4ff","#7198ca"),
        "ice":((42,91,137),(179,228,242),"#b7f1ff","#5488ad"),
        "volcano":((89,56,73),(237,154,104),"#edbd67","#557c5d"),
        "sapphire":((42,57,126),(131,150,214),"#79d9e8","#5874ad"),
        "petal":((121,91,139),(255,199,205),"#f58fb7","#75ad79"),
        "moon":((43,50,89),(159,164,192),"#c5c9e9","#66718e"),
    }
    top,bottom,accent,ground=palettes.get(palette,palettes["aurora"])
    _gradient(d,top,bottom)
    # Distant planets, soft clouds and drifting lights
    d.ellipse((1010,45,1170,205),fill="#fff0bd")
    d.ellipse((1040,75,1140,175),fill="#fff7d9")
    for i in range(5):
        cx=(i*310+int(t*9))%(W+250)-120; cy=92+(i%3)*45
        d.ellipse((cx,cy+18,cx+100,cy+62),fill="#fff4ed")
        d.ellipse((cx+28,cy,cx+105,cy+65),fill="#fff4ed")
        d.ellipse((cx+65,cy+16,cx+150,cy+63),fill="#fff4ed")
    # Far hills drawn as continuous curved silhouettes, never triangular peaks
    def curve(points,fill,outline=None,width=3):
        pts=[]
        for seg in points:
            part=[]
            p0,p1,p2,p3=seg
            for k in range(17):
                z=k/16; u=1-z
                part.append((int(u**3*p0[0]+3*u*u*z*p1[0]+3*u*z*z*p2[0]+z**3*p3[0]),
                             int(u**3*p0[1]+3*u*u*z*p1[1]+3*u*z*z*p2[1]+z**3*p3[1])))
            pts.extend(part if not pts else part[1:])
        d.polygon(pts,fill=fill)
        if outline: d.line(pts+[pts[0]],fill=outline,width=width,joint="curve")
    curve([((0,440),(170,330),(300,360),(430,430)),
           ((430,430),(600,505),(760,320),(930,400)),
           ((930,400),(1080,465),(1180,365),(1280,405)),
           ((1280,405),(1280,720),(0,720),(0,440))],"#7184b5")
    curve([((0,500),(190,410),(340,470),(500,500)),
           ((500,500),(680,545),(850,405),(1010,475)),
           ((1010,475),(1130,520),(1200,450),(1280,470)),
           ((1280,470),(1280,720),(0,720),(0,500))],ground)
    # The scene index changes the setting's visual language and props.
    idx=max(0,int(scene_index))
    if idx in (0,13):
        # Curved spaceship interior with large portholes and glowing controls
        d.rounded_rectangle((65,145,1215,585),radius=115,fill="#263e69",outline="#a6e5f2",width=12)
        d.rounded_rectangle((135,195,1145,485),radius=82,fill="#122c50",outline="#70d5e8",width=8)
        for i in range(9):
            cx=220+i*105; cy=310+math.sin(t*2+i)*15
            d.ellipse((cx-8,cy-8,cx+8,cy+8),fill=("#fff2b0","#8ce7ef","#f8a9ce")[i%3])
        d.text((440,205),"NAVE ESTRELINHA",font=_font(35,True),fill="#fff4c9")
    elif idx==1:
        # Planet reveal: softly curved planet surface and atmospheric rings
        d.ellipse((335,135,955,755),fill=ground,outline=accent,width=14)
        for k in range(3):
            d.arc((360-k*30,230-k*14,930+k*30,650+k*18),195,340,fill=accent,width=8)
    elif idx==2 or idx==12:
        # Friendly village with rounded roofs, doors and organic windows
        for i in range(5):
            bx=60+i*250; by=425+(i%2)*18
            d.rounded_rectangle((bx,by-115,bx+165,by+48),radius=35,fill="#f7d9a7",outline="#66516a",width=5)
            d.ellipse((bx-8,by-155,bx+173,by-62),fill=accent,outline="#66516a",width=5)
            d.rounded_rectangle((bx+62,by-38,bx+105,by+48),radius=18,fill="#91614e")
            for wx in (bx+22,bx+120):
                d.rounded_rectangle((wx,by-83,wx+26,by-48),radius=10,fill="#8bd9ed",outline="#66516a",width=3)
        if idx==12:
            d.rounded_rectangle((300,145,980,560),radius=40,fill="#f8e8c6",outline="#8d674f",width=10)
            for i in range(4): d.line((385,250+i*65,895,250+i*65),fill="#c1a77e",width=4)
            d.text((460,175),"DIÁRIO DA MISSÃO",font=_font(30,True),fill="#75503e")
    elif idx in (3,4,5,6,7,8,9,10,11,14):
        # Story locations: lush forest, river, cave and meadow all use curved forms
        if idx in (3,4,5,9):
            for tx,base,sz in [(65,535,1.1),(260,560,.8),(1030,555,1.0),(1200,550,.85)]:
                d.rounded_rectangle((int(tx-12*sz),int(base-195*sz),int(tx+12*sz),int(base+30)),radius=12,fill="#80513d")
                for ox,oy,rad in [(-28,-195,57),(18,-218,65),(53,-173,58),(-5,-145,62)]:
                    d.ellipse((int(tx+(ox-rad)*sz),int(base+(oy-rad)*sz),int(tx+(ox+rad)*sz),int(base+(oy+rad)*sz)),fill=accent,outline="#356b56",width=4)
        if idx in (6,8):
            curve([((0,505),(220,465),(340,520),(500,560)),
                   ((500,560),(720,610),(840,470),(1030,500)),
                   ((1030,500),(1150,525),(1210,490),(1280,475)),
                   ((1280,475),(1280,720),(0,720),(0,505))],"#4db9d0")
            for k in range(8):
                yy=555+k*23+int(t*22%23)
                d.arc((300-k*20,yy,950+k*20,yy+38),5,175,fill="#d8fbff",width=4)
        if idx==7:
            d.ellipse((210,110,1070,790),fill="#26334e",outline="#9bd9e9",width=16)
            for k in range(6):
                cx=330+k*125
                d.ellipse((cx,420+(k%2)*35,cx+45,470+(k%2)*35),fill=accent)
        if idx==8:
            d.rounded_rectangle((130,470,1150,535),radius=30,fill="#d9ad70",outline="#6a4b4a",width=5)
            for bx in range(180,1100,110):
                d.rounded_rectangle((bx,430,bx+18,535),radius=8,fill="#9d704f")
        if idx==10 or idx==11 or idx==14:
            for k in range(26):
                px=(k*83+int(t*24))%W; py=(k*47+int(t*35))%510
                d.ellipse((px,py,px+8,py+12),fill=("#fff0a8","#ff9fc5","#8be5ed")[k%3])
            d.ellipse((430,285,850,705),fill="#fff0bb",outline="#fff8dc",width=9)
            if idx==14:
                d.rounded_rectangle((250,100,1030,270),radius=38,fill="#203a66",outline="#fff4d7",width=8)
                d.text((365,145),"A MORAL DA HISTÓRIA",font=_font(40,True),fill="#fff4d7")
    # Layered foreground meadow, flowers and soft stones
    curve([((0,625),(220,565),(390,640),(600,615)),
           ((600,615),(850,585),(1030,660),(1280,600)),
           ((1280,600),(1280,720),(0,720),(0,625))],"#65ad70")
    for k in range(30):
        fx=(k*173+int(t*7))%W; fy=625+(k%3)*28
        col=("#ffdb72","#f48fbd","#fff0d4")[k%3]
        for p in range(5):
            ang=p*math.tau/5
            px=fx+math.cos(ang)*7; py=fy+math.sin(ang)*7
            d.ellipse((px-5,py-5,px+5,py+5),fill=col)
        d.ellipse((fx-3,fy-3,fx+3,fy+3),fill="#ffbd45")
    # Cast staging; organic illustrated characters remain consistent between scenes.
    positions=[(350,665,.91),(640,665,.91),(930,665,.83)]
    if portrait: positions=[(445,665,.68),(640,665,.68),(835,665,.63)]
    if idx in (0,1,12,13): positions=[(px,py-42,sc) for px,py,sc in positions]
    if idx==7: positions=[(px,py+5,sc) for px,py,sc in positions]
    _character(d,positions[0][0]+int(math.sin(t*1.4)*18),positions[0][1],positions[0][2],
               ("#e94e9b","#8f4e9a","#ffd04d"),"LUNA",t,pointing=idx in (1,4,9),
               speaking=active_speaker=="Luna",walking=action in ("walk","explore","run"))
    _character(d,positions[1][0]+int(math.sin(t*1.3+1)*16),positions[1][1],positions[1][2],
               ("#287cc6","#554d9a","#f2a34d"),"TOMI",t+1,pointing=idx in (5,8,9),
               speaking=active_speaker=="Tomi",walking=action in ("walk","explore","run"))
    _character(d,positions[2][0]+int(math.sin(t*1.7+2)*12),positions[2][1],positions[2][2],
               ("#d58a48","#fff","#287cc6"),"PIPO",t,dog=True,walking=action in ("walk","explore","run"))
    if portrait: im=im.crop((360,0,920,720)).resize((720,1280),Image.Resampling.LANCZOS)
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
