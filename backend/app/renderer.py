from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FPS = 8
SCENE_SECONDS = 4
SCENES = [
    ("UM DIA NA ESCOLA", "Na escola do bairro, algumas mochilas aparecem trocadas.", "school"),
    ("UMA PISTA IMPORTANTE", "Luna observa as etiquetas. Tomi decide conferir os nomes.", "clue"),
    ("SEM ACUSAR NINGUÉM", "Antes de apontar alguém, os amigos procuram a professora.", "care"),
    ("A DESCOBERTA", "As mochilas eram parecidas. A troca aconteceu por engano!", "discovery"),
    ("JUNTOS É MELHOR", "Com ajuda, todos devolvem os pertences e criam etiquetas coloridas.", "team"),
    ("A LIÇÃO DO DIA", "Honestidade é falar a verdade. Responsabilidade é corrigir nossos erros.", "lesson"),
]

def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for name in candidates:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()

def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def draw_girl(d, x, y, s, t):
    bob = math.sin(t * 5) * 3 * s
    ink = "#432b43"
    # Boots, legs and gloves
    d.line((x-17*s,y+100*s+bob,x-23*s,y+143*s), fill="#533b78", width=max(5,int(13*s)))
    d.line((x+17*s,y+100*s+bob,x+23*s,y+143*s), fill="#533b78", width=max(5,int(13*s)))
    rounded(d,(x-43*s,y+136*s,x-7*s,y+157*s),8*s,"#332448",ink,max(1,int(3*s)))
    rounded(d,(x+7*s,y+136*s,x+43*s,y+157*s),8*s,"#332448",ink,max(1,int(3*s)))
    # Arms and gloves
    d.line((x-31*s,y+30*s+bob,x-62*s,y+73*s+math.sin(t*4)*7*s),fill="#e9aa88",width=max(6,int(15*s)))
    d.line((x+31*s,y+30*s+bob,x+59*s,y+69*s+math.cos(t*4)*7*s),fill="#e9aa88",width=max(6,int(15*s)))
    d.ellipse((x-70*s,y+65*s,x-52*s,y+83*s),fill="#ffcf55",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x+52*s,y+61*s,x+70*s,y+79*s),fill="#ffcf55",outline=ink,width=max(1,int(2*s)))
    # Suit, collar, belt and emblem
    rounded(d,(x-39*s,y+8*s+bob,x+39*s,y+113*s+bob),20*s,"#e83b9b",ink,max(2,int(3*s)))
    d.polygon([(x-17*s,y+12*s+bob),(x,y+31*s+bob),(x+17*s,y+12*s+bob)],fill="#ffd5ed")
    d.arc((x-26*s,y+48*s+bob,x+26*s,y+100*s+bob),5,175,fill="#ff91cf",width=max(1,int(3*s)))
    rounded(d,(x-38*s,y+91*s+bob,x+38*s,y+103*s+bob),5*s,"#713e91",ink,max(1,int(2*s)))
    d.ellipse((x-13*s,y+43*s+bob,x+13*s,y+69*s+bob),fill="#ffd54d",outline="#9a6321",width=max(1,int(2*s)))
    d.polygon([(x,y+46*s+bob),(x+5*s,y+55*s+bob),(x+12*s,y+56*s+bob),(x+5*s,y+62*s+bob),(x+7*s,y+68*s+bob),(x,y+64*s+bob),(x-7*s,y+68*s+bob),(x-5*s,y+61*s+bob),(x-12*s,y+56*s+bob),(x-4*s,y+55*s+bob)],fill="#fff8c8")
    # Hair silhouette and face
    d.ellipse((x-47*s,y-69*s+bob,x+47*s,y+33*s+bob),fill="#613c2e",outline=ink,width=max(1,int(3*s)))
    d.ellipse((x-35*s,y-56*s+bob,x+35*s,y+27*s+bob),fill="#f4c09d",outline="#b87962",width=max(1,int(2*s)))
    d.ellipse((x-43*s,y-43*s+bob,x-23*s,y+15*s+bob),fill="#613c2e")
    d.ellipse((x+23*s,y-43*s+bob,x+43*s,y+15*s+bob),fill="#613c2e")
    d.pieslice((x-39*s,y-73*s+bob,x+40*s,y-12*s+bob),180,355,fill="#704330",outline=ink,width=max(1,int(2*s)))
    # Side fringe and little star clip
    d.polygon([(x-34*s,y-54*s+bob),(x-5*s,y-65*s+bob),(x+5*s,y-36*s+bob),(x-17*s,y-28*s+bob)],fill="#704330")
    d.ellipse((x+29*s,y-53*s+bob,x+43*s,y-39*s+bob),fill="#ffcf54",outline=ink,width=max(1,int(2*s)))
    # Eyes, highlights, brows, cheeks and smile
    d.arc((x-25*s,y-33*s+bob,x-7*s,y-24*s+bob),185,350,fill=ink,width=max(1,int(2*s)))
    d.arc((x+7*s,y-33*s+bob,x+25*s,y-24*s+bob),185,350,fill=ink,width=max(1,int(2*s)))
    for ex in (-16,16):
        d.ellipse((x+(ex-5)*s,y-25*s+bob,x+(ex+5)*s,y-10*s+bob),fill="#fff")
        d.ellipse((x+(ex-2)*s,y-22*s+bob,x+(ex+3)*s,y-11*s+bob),fill="#342a35")
        d.ellipse((x+(ex-1)*s,y-21*s+bob,x+(ex+1)*s,y-18*s+bob),fill="#fff")
    d.ellipse((x-29*s,y-5*s+bob,x-19*s,y+2*s+bob),fill="#ee8c91")
    d.ellipse((x+19*s,y-5*s+bob,x+29*s,y+2*s+bob),fill="#ee8c91")
    d.arc((x-12*s,y-5*s+bob,x+12*s,y+12*s+bob),5,170,fill="#a64d58",width=max(1,int(3*s)))
    # Signature pink inventor goggles
    d.arc((x-37*s,y-62*s+bob,x+37*s,y-27*s+bob),185,355,fill="#ff70c1",width=max(4,int(7*s)))
    d.line((x-35*s,y-44*s+bob,x+35*s,y-44*s+bob),fill="#ff70c1",width=max(2,int(4*s)))
    d.ellipse((x-4*s,y-50*s+bob,x+4*s,y-42*s+bob),fill="#ffe8f6")

def draw_boy(d, x, y, s, t):
    bob = math.sin(t*5+1)*3*s
    ink = "#23304f"
    d.line((x-17*s,y+100*s+bob,x-21*s,y+143*s),fill="#28406e",width=max(6,int(14*s)))
    d.line((x+17*s,y+100*s+bob,x+23*s,y+143*s),fill="#28406e",width=max(6,int(14*s)))
    rounded(d,(x-42*s,y+136*s,x-6*s,y+157*s),8*s,"#172a50",ink,max(1,int(3*s)))
    rounded(d,(x+6*s,y+136*s,x+42*s,y+157*s),8*s,"#172a50",ink,max(1,int(3*s)))
    d.line((x-31*s,y+29*s+bob,x-58*s,y+73*s+math.cos(t*4)*7*s),fill="#e5a780",width=max(6,int(15*s)))
    d.line((x+31*s,y+29*s+bob,x+58*s,y+70*s+math.sin(t*4)*7*s),fill="#e5a780",width=max(6,int(15*s)))
    d.ellipse((x-67*s,y+66*s,x-50*s,y+83*s),fill="#ffd04f",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x+50*s,y+63*s,x+67*s,y+80*s),fill="#ffd04f",outline=ink,width=max(1,int(2*s)))
    rounded(d,(x-39*s,y+8*s+bob,x+39*s,y+113*s+bob),20*s,"#2464ad",ink,max(2,int(3*s)))
    d.polygon([(x-17*s,y+12*s+bob),(x,y+30*s+bob),(x+17*s,y+12*s+bob)],fill="#e4f4ff")
    rounded(d,(x-38*s,y+91*s+bob,x+38*s,y+103*s+bob),5*s,"#f1b936",ink,max(1,int(2*s)))
    d.ellipse((x-13*s,y+42*s+bob,x+13*s,y+68*s+bob),fill="#ffd34d",outline="#966b23",width=max(1,int(2*s)))
    d.polygon([(x,y+45*s+bob),(x+5*s,y+54*s+bob),(x+12*s,y+55*s+bob),(x+5*s,y+61*s+bob),(x+7*s,y+67*s+bob),(x,y+63*s+bob),(x-7*s,y+67*s+bob),(x-5*s,y+60*s+bob),(x-12*s,y+55*s+bob),(x-4*s,y+54*s+bob)],fill="#fff8c8")
    # Face and layered swept hair
    d.ellipse((x-45*s,y-68*s+bob,x+45*s,y+31*s+bob),fill="#573624",outline=ink,width=max(1,int(3*s)))
    d.ellipse((x-35*s,y-55*s+bob,x+35*s,y+27*s+bob),fill="#efb68e",outline="#b87962",width=max(1,int(2*s)))
    d.polygon([(x-39*s,y-45*s+bob),(x-32*s,y-77*s+bob),(x-10*s,y-59*s+bob),(x+2*s,y-82*s+bob),(x+14*s,y-55*s+bob),(x+34*s,y-69*s+bob),(x+29*s,y-34*s+bob)],fill="#69412d",outline=ink)
    d.arc((x-26*s,y-33*s+bob,x-7*s,y-24*s+bob),185,350,fill=ink,width=max(1,int(2*s)))
    d.arc((x+7*s,y-33*s+bob,x+26*s,y-24*s+bob),185,350,fill=ink,width=max(1,int(2*s)))
    for ex in (-16,16):
        d.ellipse((x+(ex-5)*s,y-25*s+bob,x+(ex+5)*s,y-10*s+bob),fill="#fff")
        d.ellipse((x+(ex-2)*s,y-22*s+bob,x+(ex+3)*s,y-11*s+bob),fill="#27334b")
        d.ellipse((x+(ex-1)*s,y-21*s+bob,x+(ex+1)*s,y-18*s+bob),fill="#fff")
    d.ellipse((x-29*s,y-5*s+bob,x-19*s,y+2*s+bob),fill="#e9918c")
    d.ellipse((x+19*s,y-5*s+bob,x+29*s,y+2*s+bob),fill="#e9918c")
    d.arc((x-12*s,y-5*s+bob,x+12*s,y+12*s+bob),5,170,fill="#995047",width=max(1,int(3*s)))
    rounded(d,(x+27*s,y+29*s+bob,x+49*s,y+53*s+bob),7*s,"#56d7ef",ink,max(1,int(2*s)))
    d.line((x+31*s,y+34*s+bob,x+45*s,y+34*s+bob),fill="#e6ffff",width=max(1,int(2*s)))

def draw_dog(d,x,y,s,t):
    bob=math.sin(t*6)*3*s
    ink="#75452b"
    # tail wag
    d.arc((x+27*s,y+12*s+bob,x+78*s,y+66*s+bob),190+math.sin(t*8)*20,330+math.sin(t*8)*20,fill="#b8753e",width=max(5,int(11*s)))
    # paws and body
    d.ellipse((x-42*s,y+39*s+bob,x-15*s,y+72*s+bob),fill="#a96635",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x+15*s,y+39*s+bob,x+42*s,y+72*s+bob),fill="#a96635",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x-49*s,y-5*s+bob,x+49*s,y+65*s+bob),fill="#c98243",outline=ink,width=max(1,int(3*s)))
    # chest patch and blue hero vest
    d.ellipse((x-18*s,y+14*s+bob,x+18*s,y+59*s+bob),fill="#f5d7a7")
    rounded(d,(x-35*s,y+9*s+bob,x+35*s,y+31*s+bob),9*s,"#24528a",ink,max(1,int(2*s)))
    d.ellipse((x-9*s,y+12*s+bob,x+9*s,y+29*s+bob),fill="#ffd34d")
    # ears behind head
    d.ellipse((x-50*s,y-54*s+bob,x-20*s,y+11*s+bob),fill="#89512e",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x+20*s,y-54*s+bob,x+50*s,y+11*s+bob),fill="#89512e",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x-39*s,y-65*s+bob,x+39*s,y+18*s+bob),fill="#d99655",outline=ink,width=max(1,int(3*s)))
    # muzzle
    d.ellipse((x-22*s,y-15*s+bob,x+22*s,y+17*s+bob),fill="#f6d7ae")
    d.ellipse((x-21*s,y-36*s+bob,x-10*s,y-21*s+bob),fill="#241a17")
    d.ellipse((x+10*s,y-36*s+bob,x+21*s,y-21*s+bob),fill="#241a17")
    d.ellipse((x-5*s,y-17*s+bob,x+5*s,y-8*s+bob),fill="#34211c")
    d.arc((x-10*s,y-12*s+bob,x+10*s,y+7*s+bob),0,180,fill="#8c5140",width=max(1,int(2*s)))
    d.ellipse((x-17*s,y-31*s+bob,x-13*s,y-27*s+bob),fill="#fff")
    d.ellipse((x+13*s,y-31*s+bob,x+17*s,y-27*s+bob),fill="#fff")

WORLD_VISUALS = {
 "Aurora-7": ("#132b62","#63e4ce","#b5f7db","#244d62"),
 "Vermelhão": ("#572e55","#ff9b68","#ffd18a","#a74f4a"),
 "Oceânia Azul": ("#073b63","#39c9df","#9cf4ed","#087d91"),
 "Flora-Lume": ("#244b48","#a6df76","#f3e79b","#397a55"),
 "Nuvem Doce": ("#5966a7","#e4c9ff","#fff0c8","#a9a5dc"),
 "Gelus-9": ("#183e69","#8ee8ff","#d8f7ff","#6caccb"),
 "Vulcânia Verde": ("#46314d","#ff9b55","#b9e58c","#6d7750"),
 "Anel de Safira": ("#263b70","#9fb9ff","#f7d78b","#536b9e"),
 "Pétala-3": ("#5c3970","#ffb8d8","#f8e7a5","#a96e9d"),
 "Eco-Lua": ("#303b62","#c1c9e8","#f5e9b5","#727b9c"),
}

def draw_alien(d, x, y, s, t, accent):
    bob=math.sin(t*4+1.2)*4*s
    ink="#263452"
    # friendly tiny local creature with antennae
    d.line((x-12*s,y-35*s+bob,x-23*s,y-59*s+bob),fill=ink,width=max(2,int(4*s)))
    d.line((x+12*s,y-35*s+bob,x+23*s,y-59*s+bob),fill=ink,width=max(2,int(4*s)))
    d.ellipse((x-28*s,y-67*s+bob,x-17*s,y-56*s+bob),fill=accent,outline=ink,width=max(1,int(2*s)))
    d.ellipse((x+17*s,y-67*s+bob,x+28*s,y-56*s+bob),fill=accent,outline=ink,width=max(1,int(2*s)))
    d.ellipse((x-36*s,y-48*s+bob,x+36*s,y+22*s+bob),fill=accent,outline=ink,width=max(2,int(3*s)))
    d.ellipse((x-20*s,y-25*s+bob,x-8*s,y-9*s+bob),fill="#fff")
    d.ellipse((x+8*s,y-25*s+bob,x+20*s,y-9*s+bob),fill="#fff")
    d.ellipse((x-16*s,y-22*s+bob,x-10*s,y-12*s+bob),fill="#24304b")
    d.ellipse((x+10*s,y-22*s+bob,x+16*s,y-12*s+bob),fill="#24304b")
    d.arc((x-12*s,y-7*s+bob,x+12*s,y+9*s+bob),0,180,fill=ink,width=max(2,int(2*s)))
    d.line((x-18*s,y+17*s+bob,x-25*s,y+34*s+bob),fill=ink,width=max(3,int(5*s)))
    d.line((x+18*s,y+17*s+bob,x+25*s,y+34*s+bob),fill=ink,width=max(3,int(5*s)))

def draw_rocket(d, x, y, s, t):
    wobble=math.sin(t*2)*3*s
    d.polygon([(x,y-48*s+wobble),(x+24*s,y+22*s+wobble),(x,y+12*s+wobble),(x-24*s,y+22*s+wobble)],fill="#fff3d4",outline="#243452")
    d.ellipse((x-9*s,y-14*s+wobble,x+9*s,y+4*s+wobble),fill="#57cbe7",outline="#243452",width=max(1,int(2*s)))
    d.polygon([(x-17*s,y+16*s+wobble),(x-32*s,y+34*s+wobble),(x-12*s,y+28*s+wobble)],fill="#f16b72")
    d.polygon([(x+17*s,y+16*s+wobble),(x+32*s,y+34*s+wobble),(x+12*s,y+28*s+wobble)],fill="#f16b72")
    flame=18+int((math.sin(t*13)+1)*7)
    d.polygon([(x-8*s,y+20*s+wobble),(x,y+(20+flame)*s+wobble),(x+8*s,y+20*s+wobble)],fill="#ffbd4a")

def draw_scene_frame(size, scene, index, frame, portrait, planet_name="Aurora-7"):
    w,h=size
    t=frame/FPS
    sky,accent,light,terrain=WORLD_VISUALS.get(planet_name,WORLD_VISUALS["Aurora-7"])
    im=Image.new("RGB",(w,h),sky)
    d=ImageDraw.Draw(im)
    # soft atmospheric glow and distant stars
    for yy in range(0,h,4):
        mix=yy/h
        col=tuple(int(int(sky[i:i+2],16)*(1-mix*.25)+int(terrain[i:i+2],16)*mix*.25) for i in (1,3,5))
        d.line((0,yy,w,yy),fill=col)
    for k in range(38):
        sx=(k*97+int(t*8*(k%3+1)))%w
        sy=(k*53)%int(h*.64)
        r=max(1,int(h*(.0025 if k%4 else .004)))
        d.ellipse((sx-r,sy-r,sx+r,sy+r),fill="#ffffff" if k%3 else light)
    # giant ringed planet and two moons
    px,py=w*.78,h*.24
    d.ellipse((px-w*.17,py-h*.18,px+w*.17,py+h*.18),fill=accent,outline=light,width=max(1,int(h*.004)))
    d.arc((px-w*.23,py-h*.08,px+w*.23,py+h*.15),190,350,fill=light,width=max(2,int(h*.012)))
    d.ellipse((w*.13,h*.17,w*.18,h*.22),fill=light)
    d.ellipse((w*.89,h*.43,w*.92,h*.46),fill=accent)
    # floating rock shelves / alien landscape
    d.polygon([(0,h*.68),(w*.12,h*.57),(w*.25,h*.66),(w*.42,h*.55),(w*.58,h*.67),(w*.76,h*.56),(w,h*.66),(w,h),(0,h)],fill=terrain)
    d.polygon([(0,h*.79),(w*.22,h*.71),(w*.42,h*.78),(w*.62,h*.69),(w*.82,h*.78),(w,h*.72),(w,h),(0,h)],fill=accent)
    # scene-specific environmental landmark and mission props
    if index in (0,1):
        # glowing crystal grove
        for cx,cy,cs in [(w*.12,h*.64,.08),(w*.87,h*.62,.10),(w*.25,h*.73,.05),(w*.72,h*.73,.06)]:
            d.polygon([(cx,cy-h*cs),(cx+w*cs*.35,cy),(cx,cy+h*cs*.5),(cx-w*cs*.35,cy)],fill=light,outline="#ffffff")
            d.line((cx,cy-h*cs*.7,cx,cy+h*cs*.35),fill="#ffffff",width=max(1,int(h*.003)))
    elif index in (2,3):
        # local settlement and glowing windows
        for bx in (w*.12,w*.78):
            rounded(d,(bx,h*.48,bx+w*.12,h*.72),int(h*.03),accent,light,max(1,int(h*.004)))
            d.polygon([(bx-w*.02,h*.49),(bx+w*.06,h*.37),(bx+w*.14,h*.49)],fill=light)
            for wx in (bx+w*.025,bx+w*.075):
                rounded(d,(wx,h*.54,wx+w*.025,h*.59),4,sky)
    else:
        # mission beacon / community garden
        d.ellipse((w*.78,h*.48,w*.88,h*.58),fill=light,outline="#ffffff",width=max(1,int(h*.004)))
        d.line((w*.83,h*.57,w*.83,h*.72),fill=light,width=max(2,int(h*.01)))
        for k in range(5):
            xx=w*(.12+k*.07)
            d.ellipse((xx,h*.69,xx+w*.025,h*.73),fill=light)
    # glowing path and small craters
    d.polygon([(w*.42,h*.68),(w*.58,h*.68),(w*.72,h),(w*.28,h)],fill=light)
    for cx,cy,rx in [(w*.18,h*.86,w*.035),(w*.83,h*.88,w*.045),(w*.63,h*.75,w*.02)]:
        d.ellipse((cx-rx,cy-h*.012,cx+rx,cy+h*.012),outline=terrain,width=max(1,int(h*.004)))
    # heroes: same proportions, signature clothes and badges in every frame
    if portrait:
        base_y=h*.61
        draw_girl(d,w*.29,base_y,w/900,t)
        draw_boy(d,w*.70,base_y,w/900,t)
        draw_dog(d,w*.50,h*.78,w/1500,t)
        draw_alien(d,w*.84,h*.75,w/2100,t,light)
        draw_rocket(d,w*.50,h*.30,w/1500,t)
        header_y=h*.055; sub_y=h*.845
    else:
        base_y=h*.63
        draw_girl(d,w*.34,base_y,h/720*.9,t)
        draw_boy(d,w*.57,base_y,h/720*.9,t)
        draw_dog(d,w*.78,h*.78,h/1300,t)
        draw_alien(d,w*.90,h*.75,h/1500,t,light)
        draw_rocket(d,w*.16,h*.31,h/1500,t)
        header_y=h*.045; sub_y=h*.835
    # little emotional/action cue changes each scene, keeping model sheets stable
    cue=["✦","?","!","♥","★","✓"][index]
    cue_font=font(max(20,int(h*.075)),True)
    d.text((w*.08,h*.31),cue,font=cue_font,fill=light,stroke_width=1,stroke_fill=sky)
    # cinematic title ribbon
    rounded(d,(w*.055,header_y,w*.945,header_y+h*.105),int(h*.026),"#10264f","#f7d77a",max(1,int(h*.003)))
    title=scene[0]
    f=font(max(15,int(h*.039)),True)
    box=d.textbbox((0,0),title,font=f)
    d.text(((w-(box[2]-box[0]))/2,header_y+h*.02),title,font=f,fill="#ffffff",stroke_width=1,stroke_fill="#102044")
    # legible caption with wrapped lines and safe margins
    rounded(d,(w*.045,sub_y,w*.955,sub_y+h*.135),int(h*.025),"#fffdf4","#f3cb63",max(1,int(h*.004)))
    text=scene[1]
    f2=font(max(12,int(h*(.025 if portrait else .029))),True)
    max_width=w*.82
    words=text.split(); lines=[]; line=""
    for word in words:
        test=(line+" "+word).strip()
        if d.textlength(test,font=f2)<=max_width: line=test
        else:
            if line: lines.append(line)
            line=word
    if line: lines.append(line)
    line_h=int(h*.036)
    total=min(len(lines),3)*line_h
    start_y=sub_y+(h*.135-total)/2
    for j,line in enumerate(lines[:3]):
        tw=d.textlength(line,font=f2)
        d.text(((w-tw)/2,start_y+j*line_h),line,font=f2,fill="#17294a")
    # subtle drifting sparkles add life without changing character designs
    for k in range(8):
        sx=(w*(.08+k*.12)+math.sin(t*1.7+k)*w*.009)%w
        sy=h*(.23+(k%3)*.055)+math.cos(t*2+k)*h*.008
        r=max(2,int(h*.005))
        d.ellipse((sx-r,sy-r,sx+r,sy+r),fill=light)
    return im

def _run(cmd):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-1800:])
    return p

def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode:
        raise RuntimeError("Não foi possível medir a duração do áudio: " + result.stderr[-600:])
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("Duração do áudio inválida.") from exc

def _fit_narration(source: Path, output: Path, target_seconds: float) -> float:
    """Stretch/compress narration only as needed to satisfy the format duration contract."""
    actual = _probe_duration(source)
    if actual <= 0:
        raise RuntimeError("A narração foi gerada vazia.")
    factor = actual / target_seconds
    if 0.96 <= factor <= 1.04:
        output.write_bytes(source.read_bytes())
        return _probe_duration(output)
    factor = min(2.0, max(0.5, factor))
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
          "-filter:a", f"atempo={factor:.5f}", "-ar", "44100", str(output)])
    return _probe_duration(output)

def render_episode(title: str, story: str, fmt: str, output: Path, workdir: Path,
                   planet_name: str = "Aurora-7", story_plan: dict | None = None):
    """Render separate long-form and vertical-short edits from one approved story plan."""
    plan = story_plan or {}
    portrait = fmt == "9:16"
    if fmt not in {"16:9", "9:16"}:
        raise ValueError("Formato de renderização não reconhecido.")

    # A 16:9 episode is a full-length narrated story (>5 min).
    # The 9:16 Short receives its own condensed narration and scene timing (60–90 s).
    if portrait:
        narration_text = plan.get("short_script") or story
        speech_rate = 136
        min_duration, max_duration, target_duration = 60.0, 90.0, 74.0
    else:
        narration_text = plan.get("long_script") or story
        speech_rate = 132
        min_duration, max_duration, target_duration = 301.0, None, 315.0

    voice_raw = workdir / f"narration-source-{fmt.replace(':','x')}.wav"
    voice_fit = workdir / f"narration-final-{fmt.replace(':','x')}.wav"
    _run(["espeak-ng", "-v", "pt-br", "-s", str(speech_rate), "-p", "48", "-a", "165",
          "-w", str(voice_raw), narration_text])
    initial_duration = _probe_duration(voice_raw)

    if portrait:
        if initial_duration < 70:
            fitted_duration = _fit_narration(voice_raw, voice_fit, 72.0)
        elif initial_duration > 88:
            fitted_duration = _fit_narration(voice_raw, voice_fit, 87.0)
        else:
            voice_fit.write_bytes(voice_raw.read_bytes())
            fitted_duration = _probe_duration(voice_fit)
        if not (60 <= fitted_duration <= 90):
            raise RuntimeError(f"A narração Shorts ficou fora da faixa de 1:00 a 1:30 ({fitted_duration:.1f}s).")
    else:
        if initial_duration < 305:
            fitted_duration = _fit_narration(voice_raw, voice_fit, 310.0)
        else:
            voice_fit.write_bytes(voice_raw.read_bytes())
            fitted_duration = _probe_duration(voice_fit)
        if fitted_duration <= 300:
            raise RuntimeError(f"A narração horizontal ficou abaixo de 5 minutos ({fitted_duration:.1f}s).")

    # Give the final scene a short visual tail after the last spoken line.
    duration_seconds = fitted_duration + 1.2
    width, height = (405, 720) if portrait else (720, 405)
    frames = workdir / f"frames-{fmt.replace(':','x')}"
    frames.mkdir(parents=True, exist_ok=True)

    planned_scenes = plan.get("scenes") or []
    if planned_scenes:
        render_scenes = [(item.get("title", f"CENA {i+1}"),
                          item.get("caption", item.get("visual_action", "")),
                          item.get("visual_action", ""))
                         for i, item in enumerate(planned_scenes)]
    else:
        render_scenes = [
            ("A NOVA MISSÃO", "Os Pequenos Guardiões chegam a um planeta diferente.", ""),
            ("CONHECENDO O LUGAR", "Luna, Tomi e Pipo observam o novo mundo.", ""),
            ("NOVOS AMIGOS", "Os habitantes contam o que está acontecendo.", ""),
            ("A DESCOBERTA", "Luna encontra uma pista importante.", ""),
            ("UM PLANO SEGURO", "Tomi organiza a equipe e pede ajuda.", ""),
            ("A SOLUÇÃO", "Todos trabalham juntos para ajudar a comunidade.", ""),
            ("A LIÇÃO", "Amizade e cooperação fazem a diferença.", ""),
        ]
    if not render_scenes:
        raise RuntimeError("O roteiro não contém cenas para animar.")

    total_frames = max(1, int(math.ceil(duration_seconds * FPS)))
    scene_count = len(render_scenes)
    for frame_number in range(total_frames):
        scene_index = min(scene_count - 1, int(frame_number * scene_count / total_frames))
        scene_start = int(scene_index * total_frames / scene_count)
        local_frame = frame_number - scene_start
        scene = render_scenes[scene_index]
        image = draw_scene_frame((width, height), scene, scene_index, local_frame,
                                 portrait, planet_name)
        image.save(frames / f"frame-{frame_number:06d}.jpg", quality=91)

    low_video = workdir / f"silent-{fmt.replace(':','x')}.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
          "-i", str(frames / "frame-%06d.jpg"), "-c:v", "libx264",
          "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-r", "24", str(low_video)])

    output.parent.mkdir(parents=True, exist_ok=True)
    output_duration = duration_seconds
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(low_video), "-i", str(voice_fit),
          "-filter_complex", "[1:a]apad=pad_dur=2, loudnorm=I=-16:TP=-1.5:LRA=11, highpass=f=90, lowpass=f=9000[a]",
          "-map", "0:v:0", "-map", "[a]", "-t", f"{output_duration:.3f}",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
          str(output)])
    if not output.exists() or output.stat().st_size < 10000:
        raise RuntimeError("O arquivo de vídeo não foi gerado corretamente.")
    actual_video_duration = _probe_duration(output)
    if portrait and not (60 <= actual_video_duration <= 90):
        raise RuntimeError(f"O vídeo Shorts ficou fora da faixa de 1:00 a 1:30 ({actual_video_duration:.1f}s).")
    if not portrait and actual_video_duration <= 300:
        raise RuntimeError(f"O episódio horizontal ficou abaixo de 5 minutos ({actual_video_duration:.1f}s).")
    return {
        "duration_seconds": round(actual_video_duration, 2),
        "narration_seconds": round(fitted_duration, 2),
        "resolution": "1080x1920" if portrait else "1920x1080",
        "scene_count": scene_count,
        "narration_word_count": len(narration_text.split()),
    }
