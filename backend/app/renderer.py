from __future__ import annotations

import asyncio
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable
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

def _jointed_limb(d, points, fill, width):
    d.line(points, fill=fill, width=max(3, int(width)), joint="curve")
    radius=max(3, int(width*.52))
    for px,py in (points[1:-1]):
        d.ellipse((px-radius,py-radius,px+radius,py+radius),fill=fill)


def draw_girl(d, x, y, s, t, pose="idle", speaking=False):
    bounce = math.sin(t*5.8)*4*s
    if pose == "celebrate":
        bounce += abs(math.sin(t*4.4))*13*s
    stride = math.sin(t*7.2)*12*s if pose in {"walk","run","work"} else math.sin(t*2.3)*2*s
    ink="#34223e"
    skin="#f4c09d"
    # Soft character shadow and boots
    d.ellipse((x-56*s,y+145*s,x+56*s,y+164*s),fill="#142a3d")
    d.ellipse((x-43*s+stride,y+133*s+bounce,x-5*s+stride,y+158*s+bounce),fill="#352448",outline=ink,width=max(2,int(3*s)))
    d.ellipse((x+5*s-stride,y+133*s+bounce,x+43*s-stride,y+158*s+bounce),fill="#352448",outline=ink,width=max(2,int(3*s)))
    _jointed_limb(d,[(x-17*s,y+99*s+bounce),(x-20*s+stride*.55,y+124*s+bounce),(x-24*s+stride,y+143*s+bounce)],"#633e83",max(6,11*s))
    _jointed_limb(d,[(x+17*s,y+99*s+bounce),(x+20*s-stride*.55,y+124*s+bounce),(x+24*s-stride,y+143*s+bounce)],"#633e83",max(6,11*s))
    # Arms react to each scene
    left_hand=(x-67*s,y+72*s+math.sin(t*6)*9*s)
    right_hand=(x+67*s,y+72*s+math.cos(t*6)*9*s)
    if pose in {"wave","celebrate"}:
        right_hand=(x+57*s,y-24*s+math.sin(t*8)*8*s)
    elif pose=="point":
        right_hand=(x+102*s,y+2*s)
    elif pose=="think":
        right_hand=(x+39*s,y-35*s)
    elif pose=="surprised":
        left_hand=(x-69*s,y-12*s); right_hand=(x+69*s,y-12*s)
    elif pose=="work":
        left_hand=(x-78*s,y+64*s); right_hand=(x+82*s,y+50*s)
    _jointed_limb(d,[(x-31*s,y+31*s+bounce),(x-52*s,y+52*s+bounce),left_hand],skin,max(8,13*s))
    _jointed_limb(d,[(x+31*s,y+31*s+bounce),(x+53*s,y+52*s+bounce),right_hand],skin,max(8,13*s))
    for hx,hy in (left_hand,right_hand):
        d.ellipse((hx-9*s,hy-9*s,hx+9*s,hy+9*s),fill="#ffd45c",outline=ink,width=max(1,int(2*s)))
    # Suit, collar, shoulder panels and reflective highlights
    rounded(d,(x-42*s,y+7*s+bounce,x+42*s,y+112*s+bounce),23*s,"#e9369b",ink,max(2,int(3*s)))
    rounded(d,(x-34*s,y+17*s+bounce,x-22*s,y+79*s+bounce),6*s,"#ff77c1")
    rounded(d,(x+23*s,y+17*s+bounce,x+34*s,y+79*s+bounce),6*s,"#bf267d")
    d.polygon([(x-18*s,y+9*s+bounce),(x,y+29*s+bounce),(x+18*s,y+9*s+bounce)],fill="#ffe4f3")
    rounded(d,(x-39*s,y+91*s+bounce,x+39*s,y+104*s+bounce),5*s,"#743a8c",ink,max(1,int(2*s)))
    # Gold star badge
    d.ellipse((x-17*s,y+42*s+bounce,x+17*s,y+76*s+bounce),fill="#f5b92f",outline="#8c5b21",width=max(1,int(2*s)))
    d.polygon([(x,y+45*s+bounce),(x+5*s,y+55*s+bounce),(x+15*s,y+56*s+bounce),(x+7*s,y+63*s+bounce),(x+9*s,y+73*s+bounce),(x,y+67*s+bounce),(x-9*s,y+73*s+bounce),(x-7*s,y+63*s+bounce),(x-15*s,y+56*s+bounce),(x-5*s,y+55*s+bounce)],fill="#fff9d5")
    # Head, hair and face
    head_y=y-30*s+bounce
    d.ellipse((x-50*s,head_y-48*s,x+50*s,head_y+58*s),fill="#573628",outline=ink,width=max(2,int(3*s)))
    d.ellipse((x-39*s,head_y-38*s,x+39*s,head_y+49*s),fill=skin,outline="#ae765f",width=max(1,int(2*s)))
    d.ellipse((x-46*s,head_y-20*s,x-27*s,head_y+40*s),fill="#603a2b")
    d.ellipse((x+27*s,head_y-20*s,x+46*s,head_y+40*s),fill="#603a2b")
    d.pieslice((x-44*s,head_y-56*s,x+45*s,head_y+3*s),180,355,fill="#71412e",outline=ink,width=max(1,int(2*s)))
    d.polygon([(x-35*s,head_y-32*s),(x-10*s,head_y-52*s),(x+9*s,head_y-25*s),(x-16*s,head_y-9*s)],fill="#71412e")
    # Brows, bright eyes, cheeks and nose
    d.line((x-26*s,head_y-13*s,x-9*s,head_y-16*s),fill="#432b35",width=max(1,int(2*s)))
    d.line((x+9*s,head_y-16*s,x+26*s,head_y-13*s),fill="#432b35",width=max(1,int(2*s)))
    for ex in (-17,17):
        d.ellipse((x+(ex-7)*s,head_y-9*s,x+(ex+7)*s,head_y+10*s),fill="#fff")
        d.ellipse((x+(ex-3)*s,head_y-6*s,x+(ex+4)*s,head_y+9*s),fill="#33283b")
        d.ellipse((x+(ex-2)*s,head_y-5*s,x+(ex+1)*s,head_y-1*s),fill="#fff")
    d.ellipse((x-31*s,head_y+14*s,x-18*s,head_y+23*s),fill="#ed8999")
    d.ellipse((x+18*s,head_y+14*s,x+31*s,head_y+23*s),fill="#ed8999")
    if speaking and math.sin(t*18)>-.15:
        d.ellipse((x-8*s,head_y+22*s,x+8*s,head_y+38*s),fill="#7b3549",outline="#8f4a57",width=max(1,int(1*s)))
    else:
        d.arc((x-13*s,head_y+18*s,x+13*s,head_y+39*s),8,170,fill="#a64d58",width=max(1,int(3*s)))
    # Signature pink inventor goggles and star clip
    d.arc((x-39*s,head_y-51*s,x+39*s,head_y-16*s),185,355,fill="#ff75c4",width=max(4,int(7*s)))
    d.line((x-37*s,head_y-34*s,x+37*s,head_y-34*s),fill="#ff75c4",width=max(2,int(4*s)))
    d.ellipse((x+30*s,head_y-43*s,x+44*s,head_y-29*s),fill="#ffd45c",outline=ink,width=max(1,int(2*s)))


def draw_boy(d, x, y, s, t, pose="idle", speaking=False):
    bounce=math.sin(t*5.8+1)*4*s
    if pose=="celebrate": bounce+=abs(math.sin(t*4.2))*12*s
    stride=math.sin(t*7.2+1)*12*s if pose in {"walk","run","work"} else math.sin(t*2.1)*2*s
    ink="#20304d"; skin="#efb68e"
    d.ellipse((x-55*s,y+145*s,x+55*s,y+164*s),fill="#142a3d")
    d.ellipse((x-43*s+stride,y+133*s+bounce,x-5*s+stride,y+158*s+bounce),fill="#172949",outline=ink,width=max(2,int(3*s)))
    d.ellipse((x+5*s-stride,y+133*s+bounce,x+43*s-stride,y+158*s+bounce),fill="#172949",outline=ink,width=max(2,int(3*s)))
    _jointed_limb(d,[(x-17*s,y+100*s+bounce),(x-20*s+stride*.55,y+124*s+bounce),(x-24*s+stride,y+143*s+bounce)],"#29477b",max(6,11*s))
    _jointed_limb(d,[(x+17*s,y+100*s+bounce),(x+20*s-stride*.55,y+124*s+bounce),(x+24*s-stride,y+143*s+bounce)],"#29477b",max(6,11*s))
    left_hand=(x-66*s,y+71*s+math.cos(t*6)*9*s)
    right_hand=(x+66*s,y+70*s+math.sin(t*6)*9*s)
    if pose in {"wave","celebrate"}: right_hand=(x+60*s,y-24*s+math.sin(t*8)*8*s)
    elif pose=="point": right_hand=(x+104*s,y+1*s)
    elif pose=="think": right_hand=(x+40*s,y-35*s)
    elif pose=="surprised": left_hand=(x-70*s,y-12*s); right_hand=(x+70*s,y-12*s)
    elif pose=="work": left_hand=(x-80*s,y+62*s); right_hand=(x+80*s,y+48*s)
    _jointed_limb(d,[(x-31*s,y+30*s+bounce),(x-52*s,y+52*s+bounce),left_hand],skin,max(8,13*s))
    _jointed_limb(d,[(x+31*s,y+30*s+bounce),(x+52*s,y+52*s+bounce),right_hand],skin,max(8,13*s))
    for hx,hy in (left_hand,right_hand):
        d.ellipse((hx-9*s,hy-9*s,hx+9*s,hy+9*s),fill="#ffd45c",outline=ink,width=max(1,int(2*s)))
    rounded(d,(x-42*s,y+7*s+bounce,x+42*s,y+112*s+bounce),23*s,"#2467b4",ink,max(2,int(3*s)))
    rounded(d,(x-34*s,y+17*s+bounce,x-22*s,y+79*s+bounce),6*s,"#68b7ed")
    rounded(d,(x+23*s,y+17*s+bounce,x+34*s,y+79*s+bounce),6*s,"#174e96")
    d.polygon([(x-18*s,y+9*s+bounce),(x,y+29*s+bounce),(x+18*s,y+9*s+bounce)],fill="#e7f7ff")
    rounded(d,(x-39*s,y+91*s+bounce,x+39*s,y+104*s+bounce),5*s,"#f0b52f",ink,max(1,int(2*s)))
    d.ellipse((x-17*s,y+42*s+bounce,x+17*s,y+76*s+bounce),fill="#f5bc35",outline="#8c6222",width=max(1,int(2*s)))
    d.polygon([(x,y+45*s+bounce),(x+5*s,y+55*s+bounce),(x+15*s,y+56*s+bounce),(x+7*s,y+63*s+bounce),(x+9*s,y+73*s+bounce),(x,y+67*s+bounce),(x-9*s,y+73*s+bounce),(x-7*s,y+63*s+bounce),(x-15*s,y+56*s+bounce),(x-5*s,y+55*s+bounce)],fill="#fff9d5")
    head_y=y-30*s+bounce
    d.ellipse((x-49*s,head_y-48*s,x+49*s,head_y+58*s),fill="#563522",outline=ink,width=max(2,int(3*s)))
    d.ellipse((x-39*s,head_y-38*s,x+39*s,head_y+49*s),fill=skin,outline="#ae765f",width=max(1,int(2*s)))
    d.polygon([(x-43*s,head_y-28*s),(x-36*s,head_y-62*s),(x-12*s,head_y-45*s),(x+3*s,head_y-69*s),(x+18*s,head_y-45*s),(x+42*s,head_y-58*s),(x+37*s,head_y-18*s)],fill="#69412d",outline=ink)
    d.line((x-27*s,head_y-14*s,x-9*s,head_y-17*s),fill="#432b35",width=max(1,int(2*s)))
    d.line((x+9*s,head_y-17*s,x+27*s,head_y-14*s),fill="#432b35",width=max(1,int(2*s)))
    for ex in (-17,17):
        d.ellipse((x+(ex-7)*s,head_y-9*s,x+(ex+7)*s,head_y+10*s),fill="#fff")
        d.ellipse((x+(ex-3)*s,head_y-6*s,x+(ex+4)*s,head_y+9*s),fill="#27334b")
        d.ellipse((x+(ex-2)*s,head_y-5*s,x+(ex+1)*s,head_y-1*s),fill="#fff")
    d.ellipse((x-31*s,head_y+14*s,x-18*s,head_y+23*s),fill="#e9918c")
    d.ellipse((x+18*s,head_y+14*s,x+31*s,head_y+23*s),fill="#e9918c")
    if speaking and math.sin(t*18)>-.15:
        d.ellipse((x-8*s,head_y+22*s,x+8*s,head_y+38*s),fill="#7b3549",outline="#8f4a57",width=max(1,int(1*s)))
    else:
        d.arc((x-13*s,head_y+18*s,x+13*s,head_y+39*s),8,170,fill="#995047",width=max(1,int(3*s)))
    # Fixed wrist communicator is part of Tomi's model sheet
    rounded(d,(x+27*s,y+26*s+bounce,x+51*s,y+52*s+bounce),7*s,"#56d7ef",ink,max(1,int(2*s)))
    d.line((x+31*s,y+33*s+bounce,x+46*s,y+33*s+bounce),fill="#e6ffff",width=max(1,int(2*s)))


def draw_dog(d,x,y,s,t,pose="idle",speaking=False):
    bob=math.sin(t*6)*4*s
    if pose=="celebrate": bob+=abs(math.sin(t*4))*7*s
    ink="#75452b"
    tail_swing=math.sin(t*10)*28
    d.arc((x+25*s,y+7*s+bob,x+82*s,y+68*s+bob),190+tail_swing,330+tail_swing,fill="#9f5f32",width=max(6,int(12*s)))
    d.ellipse((x-55*s,y+40*s+bob,x-13*s,y+77*s+bob),fill="#a96635",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x+13*s,y+40*s+bob,x+55*s,y+77*s+bob),fill="#a96635",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x-53*s,y-5*s+bob,x+53*s,y+68*s+bob),fill="#c98243",outline=ink,width=max(1,int(3*s)))
    d.ellipse((x-23*s,y+14*s+bob,x+23*s,y+66*s+bob),fill="#f5d7a7")
    rounded(d,(x-38*s,y+9*s+bob,x+38*s,y+34*s+bob),10*s,"#24528a",ink,max(1,int(2*s)))
    d.ellipse((x-10*s,y+13*s+bob,x+10*s,y+31*s+bob),fill="#f5bd39")
    d.ellipse((x-55*s,y-58*s+bob,x-18*s,y+15*s+bob),fill="#89512e",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x+18*s,y-58*s+bob,x+55*s,y+15*s+bob),fill="#89512e",outline=ink,width=max(1,int(2*s)))
    d.ellipse((x-42*s,y-68*s+bob,x+42*s,y+22*s+bob),fill="#d99655",outline=ink,width=max(1,int(3*s)))
    d.ellipse((x-24*s,y-14*s+bob,x+24*s,y+22*s+bob),fill="#f6d7ae")
    for ex in (-15,15):
        d.ellipse((x+(ex-6)*s,y-38*s+bob,x+(ex+6)*s,y-20*s+bob),fill="#fff")
        d.ellipse((x+(ex-3)*s,y-35*s+bob,x+(ex+3)*s,y-21*s+bob),fill="#241a17")
    d.ellipse((x-6*s,y-17*s+bob,x+6*s,y-6*s+bob),fill="#34211c")
    if speaking and math.sin(t*18)>-.15:
        d.ellipse((x-8*s,y+1*s+bob,x+8*s,y+17*s+bob),fill="#5a2430")
    else:
        d.arc((x-11*s,y-1*s+bob,x+11*s,y+17*s+bob),0,180,fill="#8c5140",width=max(1,int(2*s)))


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

def _mix_hex(a: str, b: str, amount: float) -> str:
    amount=max(0.0,min(1.0,amount))
    av=[int(a[i:i+2],16) for i in (1,3,5)]
    bv=[int(b[i:i+2],16) for i in (1,3,5)]
    values=[int(av[i]*(1-amount)+bv[i]*amount) for i in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*values)


def _draw_flower(d,x,y,r,petal,center):
    for angle in range(0,360,60):
        rad=math.radians(angle)
        px=x+math.cos(rad)*r*.66; py=y+math.sin(rad)*r*.66
        d.ellipse((px-r*.38,py-r*.38,px+r*.38,py+r*.38),fill=petal)
    d.ellipse((x-r*.28,y-r*.28,x+r*.28,y+r*.28),fill=center)


def _draw_mission_prop(d,w,h,mission_object,accent,light,t,index):
    obj=(mission_object or "").lower()
    cx=w*(.73 if index%2 else .27)
    cy=h*.62
    scale=h*.001
    glow=_mix_hex(accent,light,.48)
    if any(k in obj for k in ("farol","observat","luz","sinal")):
        d.ellipse((cx-h*.09,cy-h*.09,cx+h*.09,cy+h*.09),fill=glow,outline="#fff7d6",width=max(2,int(h*.006)))
        d.rounded_rectangle((cx-h*.035,cy+h*.04,cx+h*.035,cy+h*.28),radius=int(h*.02),fill="#f4e8c2",outline="#263b57",width=max(2,int(h*.006)))
        for ray in range(8):
            a=math.radians(ray*45+t*15)
            d.line((cx+math.cos(a)*h*.12,cy+math.sin(a)*h*.12,cx+math.cos(a)*h*.20,cy+math.sin(a)*h*.20),fill=light,width=max(2,int(h*.008)))
    elif any(k in obj for k in ("semente","jardim","flor","planta")):
        for j in range(5):
            fx=cx+(j-2)*h*.065
            stem_y=cy+h*.21
            d.line((fx,stem_y,fx+math.sin(t+j)*h*.012,cy-h*.03),fill="#68b777",width=max(3,int(h*.009)))
            _draw_flower(d,fx+math.sin(t+j)*h*.012,cy-h*.06,h*.045,light,"#ffd45a")
    elif any(k in obj for k in ("ponte","canal","água","agua")):
        d.polygon([(cx-h*.28,cy+h*.08),(cx-h*.20,cy-h*.08),(cx+h*.20,cy-h*.08),(cx+h*.28,cy+h*.08)],fill="#b88a58",outline="#503e44")
        for j in range(5):
            bx=cx-h*.19+j*h*.095
            d.line((bx,cy-h*.07,bx,cy+h*.07),fill="#f1d29a",width=max(2,int(h*.009)))
        d.arc((cx-h*.31,cy+h*.05,cx+h*.31,cy+h*.27),0,180,fill=light,width=max(3,int(h*.014)))
    elif any(k in obj for k in ("biblioteca","livro")):
        for j,col in enumerate(("#e85d87","#4c96c9","#e4b94c","#7ac18b")):
            bx=cx-h*.20+j*h*.10
            d.rounded_rectangle((bx,cy-h*.13,bx+h*.085,cy+h*.13),radius=int(h*.012),fill=col,outline="#26334d",width=max(2,int(h*.005)))
            d.line((bx+h*.014,cy-h*.09,bx+h*.014,cy+h*.09),fill="#fff1c7",width=max(1,int(h*.003)))
    elif any(k in obj for k in ("recicl","caixa","placa","mensagem","recado")):
        for j,col in enumerate(("#55b8a6","#e8bd58","#ee806c")):
            bx=cx+(j-1)*h*.12
            d.rounded_rectangle((bx-h*.045,cy-h*.12,bx+h*.045,cy+h*.14),radius=int(h*.014),fill=col,outline="#243c55",width=max(2,int(h*.005)))
            d.ellipse((bx-h*.015,cy-h*.04,bx+h*.015,cy-h*.01),fill="#fff3d2")
    elif any(k in obj for k in ("coral","concha","musical")):
        d.arc((cx-h*.22,cy-h*.20,cx+h*.22,cy+h*.20),180,360,fill="#ffe9c8",width=max(5,int(h*.018)))
        for j in range(5):
            bx=cx+(j-2)*h*.055
            d.line((bx,cy,bx+math.sin(t+j)*h*.03,cy-h*(.12+.025*(j%2))),fill=light,width=max(2,int(h*.006)))
    elif any(k in obj for k in ("robô","robo","ajudante")):
        d.rounded_rectangle((cx-h*.16,cy-h*.18,cx+h*.16,cy+h*.18),radius=int(h*.05),fill="#9ed7e6",outline="#283c59",width=max(3,int(h*.009)))
        d.ellipse((cx-h*.10,cy-h*.10,cx-h*.035,cy-h*.035),fill="#24405f")
        d.ellipse((cx+h*.035,cy-h*.10,cx+h*.10,cy-h*.035),fill="#24405f")
        d.arc((cx-h*.07,cy-h*.015,cx+h*.07,cy+h*.11),0,180,fill="#34516a",width=max(3,int(h*.008)))
    else:
        d.ellipse((cx-h*.11,cy-h*.11,cx+h*.11,cy+h*.11),fill=glow,outline="#fff7d6",width=max(2,int(h*.006)))
        d.arc((cx-h*.24,cy-h*.17,cx+h*.24,cy+h*.22),190,350,fill=light,width=max(3,int(h*.012)))


def draw_scene_frame(size, scene, index, frame, portrait, planet_name="Aurora-7",
                     biome="", mission_object="", landmark="", active_speaker=""):
    """Cinematic scene art: varied composition, no subtitles, expressive character animation."""
    w,h=size
    t=frame/FPS
    base_planet=next((name for name in WORLD_VISUALS if planet_name==name or planet_name.startswith(name+" ")), "Aurora-7")
    palette=WORLD_VISUALS.get(base_planet,WORLD_VISUALS["Aurora-7"])
    sky,accent,light,terrain=palette
    scene_sky=[
        "#101d49","#182c59","#1b4560","#27395a",
        "#1b3d4d","#233e55","#18294e","#362d58",
        "#24465a","#1d4b4b","#314164","#111b40"
    ][index%12]
    sky=_mix_hex(sky,scene_sky,.32)
    im=Image.new("RGB",(w,h),sky)
    d=ImageDraw.Draw(im)
    # Smooth atmospheric gradient and cinematic horizon glow
    for yy in range(0,h,3):
        mix=yy/h
        col=_mix_hex(sky,terrain,.20+mix*.46)
        d.line((0,yy,w,yy),fill=col)
    glow_layer=Image.new("RGBA",(w,h),(0,0,0,0))
    gd=ImageDraw.Draw(glow_layer)
    glow_x=w*(.70 if index%2 else .28)+math.sin(t*.28)*w*.025
    glow_y=h*(.29 if index in (0,1,11) else .49)
    radius=int(h*.24)
    gd.ellipse((glow_x-radius,glow_y-radius,glow_x+radius,glow_y+radius),fill=(100,230,218,32))
    glow_layer=glow_layer.filter(__import__("PIL.ImageFilter",fromlist=["GaussianBlur"]).GaussianBlur(max(8,int(h*.055))))
    im=Image.alpha_composite(im.convert("RGBA"),glow_layer)
    d=ImageDraw.Draw(im)
    # Layered distant planet, moons and moving starfield
    for k in range(68):
        sx=(k*137+int(t*(5+k%4)*(.4 if k%3 else 1.0)))%w
        sy=(k*71)%int(h*.72)
        r=max(1,int(h*(.0015 if k%5 else .0035)))
        d.ellipse((sx-r,sy-r,sx+r,sy+r),fill="#fffdf4" if k%4 else light)
    if index in (0,1,11):
        px,py=w*(.76 if index!=11 else .20),h*(.25 if index!=0 else .20)
        pr=h*(.18 if portrait else .25)
        d.ellipse((px-pr,py-pr,px+pr,py+pr),fill=accent,outline=light,width=max(2,int(h*.007)))
        d.arc((px-pr*1.48,py-pr*.36,px+pr*1.48,py+pr*.80),190,350,fill="#d7fff2",width=max(3,int(h*.012)))
        d.ellipse((px-pr*.30,py-pr*.40,px-pr*.10,py-pr*.20),fill=_mix_hex(accent,"#ffffff",.45))
    # Biome-aware scenery: ocean, jungle, ice, desert, clouds or alien hills
    bio=(biome or "").lower()
    ground=h*.72
    if any(k in bio for k in ("oceano","mar","água","agua")):
        d.polygon([(0,h*.53),(w,h*.50),(w,h),(0,h)],fill="#087d91")
        for layer in range(4):
            yy=h*(.58+layer*.105)+math.sin(t*1.8+layer)*h*.008
            d.arc((-w*.2,yy-h*.07,w*1.2,yy+h*.08),0,180,fill=_mix_hex(accent,light,.35+layer*.10),width=max(2,int(h*.009)))
        ground=h*.70
    elif any(k in bio for k in ("floresta","jardim","flor","árvore","arvore")):
        d.polygon([(0,h*.70),(w*.18,h*.54),(w*.35,h*.67),(w*.55,h*.50),(w*.80,h*.67),(w,h*.55),(w,h),(0,h)],fill=terrain)
        for j in range(11):
            tx=w*(j/10)+math.sin(t*.45+j)*w*.009
            ty=h*(.57+(j%3)*.035)
            d.line((tx,ty+h*.16,tx,ty-h*.06),fill="#614d52",width=max(3,int(h*.018)))
            d.ellipse((tx-h*.065,ty-h*.14,tx+h*.065,ty+h*.015),fill=_mix_hex(accent,light,.18+(j%3)*.12))
            _draw_flower(d,tx+math.sin(t+j)*h*.02,ty-h*.07,h*.025,light,"#ffd45a")
        ground=h*.73
    elif any(k in bio for k in ("gelo","ice","neve","montanha","polar")):
        d.polygon([(0,h*.73),(w*.18,h*.32),(w*.36,h*.69),(w*.57,h*.28),(w*.79,h*.68),(w*.93,h*.41),(w,h*.72),(w,h),(0,h)],fill="#567f9f")
        for mx in (w*.18,w*.57,w*.93):
            d.polygon([(mx-h*.10,h*.47),(mx,h*.32),(mx+h*.11,h*.49),(mx,h*.45)],fill="#ecfbff")
        ground=h*.73
    elif any(k in bio for k in ("deserto","cânion","canion","areia")):
        d.polygon([(0,h*.63),(w*.15,h*.51),(w*.35,h*.62),(w*.52,h*.47),(w*.76,h*.61),(w,h*.50),(w,h),(0,h)],fill="#9a5e59")
        for layer in range(3):
            yy=h*(.70+layer*.08)+math.sin(t*.9+layer)*h*.014
            d.arc((-w*.2,yy-h*.10,w*1.2,yy+h*.12),180,355,fill=_mix_hex(terrain,light,.22+layer*.18),width=max(3,int(h*.012)))
        ground=h*.74
    elif any(k in bio for k in ("nuvem","ilha flutuante","arco-íris","arco-iris")):
        for j in range(4):
            cx=w*(.12+j*.26)+math.sin(t*.35+j)*w*.012
            cy=h*(.47+(j%2)*.12)
            d.ellipse((cx-w*.12,cy-h*.045,cx+w*.12,cy+h*.045),fill="#e9f4ff")
            d.polygon([(cx-w*.08,cy+h*.03),(cx+w*.08,cy+h*.03),(cx+w*.045,cy+h*.17),(cx-w*.045,cy+h*.17)],fill=terrain)
        ground=h*.72
    else:
        d.polygon([(0,h*.70),(w*.14,h*.57),(w*.28,h*.68),(w*.46,h*.49),(w*.64,h*.69),(w*.82,h*.55),(w,h*.68),(w,h),(0,h)],fill=terrain)
        ground=h*.72
    # Foreground is redesigned for each story beat; no fixed repeated crystal layout
    if index==0:
        # Departure from orbit: glowing engine trails and a large moving rocket
        for j in range(5):
            yy=h*(.60+j*.045)
            d.line((w*.12,yy,w*.53,yy+math.sin(t*3+j)*h*.018),fill=_mix_hex(accent,light,.55),width=max(2,int(h*.007)))
    elif index==1:
        # Grand reveal: a sweeping luminous landing path
        d.polygon([(w*.40,h*.66),(w*.60,h*.66),(w*.83,h),(w*.17,h)],fill=_mix_hex(accent,light,.52))
    elif index in (2,8,10):
        # Community village with rounded houses, warm windows, balconies and walkways
        for j in range(5):
            bx=w*(.06+j*.20)
            bh=h*(.13+(j%3)*.035)
            d.rounded_rectangle((bx,ground-bh,bx+w*.14,ground),radius=int(h*.025),fill=_mix_hex(terrain,accent,.30),outline=light,width=max(1,int(h*.004)))
            d.polygon([(bx-w*.015,ground-bh),(bx+w*.07,ground-bh-h*.075),(bx+w*.155,ground-bh)],fill=_mix_hex(accent,light,.45))
            for wx in (bx+w*.035,bx+w*.09):
                d.rounded_rectangle((wx,ground-bh*.68,wx+w*.022,ground-bh*.42),radius=3,fill="#fff0b5")
        d.polygon([(0,ground+h*.04),(w*.38,ground-h*.02),(w*.62,ground-h*.02),(w,ground+h*.04),(w,h),(0,h)],fill=_mix_hex(terrain,"#f4d69b",.14))
    elif index in (3,4,6,7,9):
        _draw_mission_prop(d,w,h,mission_object,accent,light,t,index)
    elif index==5:
        # Floating holographic mission map
        rounded(d,(w*.22,h*.53,w*.78,h*.72),int(h*.035),"#173a59",light,max(2,int(h*.007)))
        d.polygon([(w*.32,h*.65),(w*.45,h*.56),(w*.58,h*.66),(w*.70,h*.57)],fill="#36b9bd")
        for j in range(4):
            d.ellipse((w*(.34+j*.095),h*(.58+(j%2)*.06),w*(.36+j*.095),h*(.60+(j%2)*.06)),fill="#fff2a4")
        d.line((w*.37,h*.63,w*.66,h*.60),fill="#fff4bd",width=max(2,int(h*.006)))
    elif index==11:
        # Farewell and launch back into orbit
        for j in range(7):
            xx=w*(.12+j*.12)
            d.ellipse((xx,ground-h*.14-math.sin(t*2+j)*h*.02,xx+h*.028,ground-h*.11),fill=light)
    # Small details, drifting particles and foreground plants add depth
    for j in range(15):
        xx=(j*w/15+math.sin(t*.8+j)*w*.012)%w
        yy=h*(.48+(j%5)*.065)+math.cos(t*1.4+j)*h*.008
        rr=max(2,int(h*.004))
        d.ellipse((xx-rr,yy-rr,xx+rr,yy+rr),fill=light)
    for j in range(7):
        tx=w*(.04+j*.15)
        d.ellipse((tx,ground+h*.04,tx+h*.016,ground+h*.06),fill=_mix_hex(accent,light,.6))
    # Hero blocking changes with the scene; they no longer hold one identical lineup.
    poses=[
        ("wave","look","idle"),
        ("look","look","idle"),
        ("wave","wave","idle"),
        ("surprised","surprised","surprised"),
        ("point","think","sniff"),
        ("think","point","idle"),
        ("look","point","sniff"),
        ("surprised","surprised","surprised"),
        ("talk","talk","idle"),
        ("work","work","work"),
        ("celebrate","celebrate","celebrate"),
        ("wave","wave","idle"),
    ]
    girl_pose,boy_pose,dog_pose=poses[index%len(poses)]
    luna_speaks=active_speaker=="Luna"
    tomi_speaks=active_speaker=="Tomi"
    pipo_speaks=active_speaker=="Pipo"
    camera_sway=math.sin(t*.75)*w*.006
    if portrait:
        base_y=h*.66+math.sin(t*2.1)*h*.008
        scale=h/800
        gx=w*.28+camera_sway
        bx=w*.72-camera_sway
        draw_girl(d,gx,base_y,scale,t,girl_pose,luna_speaks)
        draw_boy(d,bx,base_y,scale,t,boy_pose,tomi_speaks)
        draw_dog(d,w*.50,h*.84,h/1000,t,dog_pose,pipo_speaks)
        if index in (2,8,10):
            draw_alien(d,w*.10,h*.77,h/1900,t,light)
            draw_alien(d,w*.90,h*.77,h/1900,t,accent)
        if index in (0,11):
            draw_rocket(d,w*.50,h*.25,h/1100,t)
    else:
        base_y=h*.66+math.sin(t*2.1)*h*.008
        scale=h/500
        gx=w*.30+camera_sway
        bx=w*.65-camera_sway
        draw_girl(d,gx,base_y,scale,t,girl_pose,luna_speaks)
        draw_boy(d,bx,base_y,scale,t,boy_pose,tomi_speaks)
        draw_dog(d,w*.83,h*.80,h/720,t,dog_pose,pipo_speaks)
        if index in (2,8,10):
            draw_alien(d,w*.91,h*.73,h/1250,t,light)
        if index in (0,11):
            draw_rocket(d,w*.13,h*.34,h/1100,t)
    # Subtle camera particles and foreground sparkle; deliberately no titles or subtitles.
    for j in range(9):
        xx=(w*(.10+j*.10)+math.sin(t*1.6+j)*w*.012)%w
        yy=h*(.15+(j%4)*.07)+math.cos(t*1.3+j)*h*.01
        rr=max(1,int(h*.003))
        d.ellipse((xx-rr,yy-rr,xx+rr,yy+rr),fill="#fff8d8" if j%3 else light)
    return im.convert("RGB")


def _ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg não encontrado. Instale imageio-ffmpeg ou FFmpeg no sistema.") from exc

def _run(cmd):
    command = list(cmd)
    if command and command[0] == "ffmpeg":
        command[0] = _ffmpeg_executable()
    p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-1800:])
    return p

def _probe_duration(path: Path) -> float:
    """Measure duration even when the runtime has FFmpeg but no separate ffprobe."""
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Arquivo de mídia ausente ou vazio: " + str(path.name))
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            try:
                duration = float(result.stdout.strip())
                if duration > 0:
                    return duration
            except ValueError:
                pass
    try:
        from mutagen import File as MutagenFile
        media = MutagenFile(str(path))
        duration = float(media.info.length) if media and media.info else 0.0
        if duration > 0:
            return duration
    except Exception:
        pass

    # The portable imageio-ffmpeg package ships ffmpeg but not ffprobe.
    # FFmpeg prints container/stream duration as soon as it opens the file.
    process = subprocess.Popen(
        [_ffmpeg_executable(), "-hide_banner", "-i", str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, errors="replace"
    )
    details = []
    try:
        if process.stderr:
            for line in process.stderr:
                details.append(line.strip())
                match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
                if match:
                    hours, minutes, seconds = match.groups()
                    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                    process.terminate()
                    process.wait(timeout=3)
                    if duration > 0:
                        return duration
                    break
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    raise RuntimeError(
        "Não foi possível medir a duração de " + path.name +
        ". FFmpeg informou: " + " | ".join(details[-4:])
    )


DEFAULT_VOICE_PROFILE = {
    "Narrador": {"voice": "pt-BR-ThalitaMultilingualNeural", "rate": "+0%", "pitch": "+0Hz", "espeak_pitch": 48},
    "Luna": {"voice": "pt-BR-FranciscaNeural", "rate": "+2%", "pitch": "+5Hz", "espeak_pitch": 60},
    "Tomi": {"voice": "pt-BR-AntonioNeural", "rate": "+0%", "pitch": "-3Hz", "espeak_pitch": 43},
    "Pipo": {"voice": "pt-BR-AntonioNeural", "rate": "+8%", "pitch": "+22Hz", "espeak_pitch": 76},
}
VOICE_PROFILE_FILE = Path(os.getenv("ANIMA_STORAGE", "/data/jobs")) / "voice-profiles.json"


def load_voice_profiles() -> dict:
    """Persist one stable cast voice map so every episode reuses the same identities."""
    profiles = {key: dict(value) for key, value in DEFAULT_VOICE_PROFILE.items()}
    try:
        VOICE_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if VOICE_PROFILE_FILE.exists():
            saved = json.loads(VOICE_PROFILE_FILE.read_text(encoding="utf-8"))
            for name in profiles:
                if isinstance(saved.get(name), dict):
                    profiles[name].update(saved[name])
        else:
            VOICE_PROFILE_FILE.write_text(
                json.dumps(profiles, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except (OSError, json.JSONDecodeError, TypeError):
        # A read-only volume should not prevent preview or rendering.
        pass
    return profiles


VOICE_PROFILE = load_voice_profiles()


async def _edge_tts_save(text: str, output: Path, speaker: str = "Narrador") -> None:
    import edge_tts
    profile = VOICE_PROFILE.get(speaker, VOICE_PROFILE["Narrador"])
    communicate = edge_tts.Communicate(
        text=text,
        voice=profile["voice"],
        rate=profile["rate"],
        volume="+0%",
        pitch=profile["pitch"],
    )
    await communicate.save(str(output))


def _concat_audio_files(files: list[Path], output: Path, audio_codec: str) -> Path:
    if not files:
        raise RuntimeError("O roteiro não possui falas para sintetizar.")
    manifest = output.parent / (output.stem + "-concat.txt")
    def quote_path(path: Path) -> str:
        return path.resolve().as_posix().replace("'", "'\\''")
    manifest.write_text(
        "".join("file '" + quote_path(item) + "'\n" for item in files),
        encoding="utf-8"
    )
    if audio_codec == "pcm_s16le":
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", str(manifest), "-c:a", "pcm_s16le", str(output)])
    else:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", str(manifest), "-c:a", "aac", "-b:a", "160k", str(output)])
    if not output.exists() or output.stat().st_size < 1000:
        raise RuntimeError("Não foi possível montar as falas dos personagens.")
    return output


async def _synthesize_edge_segments(segments: list[dict], files: list[Path], progress_callback=None) -> None:
    semaphore = asyncio.Semaphore(2)
    completed = 0

    async def render_one(segment: dict, path: Path):
        nonlocal completed
        text = str(segment.get("text", "")).strip()
        speaker = str(segment.get("speaker", "Narrador"))
        if not text:
            raise RuntimeError("Foi encontrada uma fala vazia no roteiro.")
        async with semaphore:
            last_error = None
            for attempt in range(2):
                try:
                    await asyncio.wait_for(_edge_tts_save(text, path, speaker), timeout=45)
                    if path.exists() and path.stat().st_size > 500:
                        completed += 1
                        if progress_callback:
                            progress_callback(int(completed * 10 / max(1, len(files))), f"Gerando falas: {completed}/{len(files)}")
                        return
                    raise RuntimeError("O serviço de voz retornou um arquivo vazio.")
                except Exception as exc:
                    last_error = exc
                    if attempt < 1:
                        await asyncio.sleep(1.5)
            raise RuntimeError(f"Falha na voz de {speaker}: {last_error}")

    await asyncio.gather(*(render_one(segment, path) for segment, path in zip(segments, files)))


def _synthesize_segments(segments: list[dict], workdir: Path, fmt: str,
                         speech_rate: int, progress_callback=None) -> tuple[Path, Path, list[dict]]:
    """Create one continuous track by alternating narrator and distinct character voices."""
    suffix = fmt.replace(":", "x")
    use_espeak = bool(shutil.which("espeak-ng"))
    extension = "wav" if use_espeak else "mp3"
    parts_dir = workdir / f"voice-parts-{suffix}"
    parts_dir.mkdir(parents=True, exist_ok=True)
    files = [
        parts_dir / f"part-{index:03d}.{extension}"
        for index in range(len(segments))
    ]

    if use_espeak:
        for segment, path in zip(segments, files):
            speaker = str(segment.get("speaker", "Narrador"))
            profile = VOICE_PROFILE.get(speaker, VOICE_PROFILE["Narrador"])
            pitch = int(profile["espeak_pitch"])
            rate = speech_rate + (8 if speaker == "Pipo" else 0)
            _run([
                "espeak-ng", "-v", "pt-br", "-s", str(rate), "-p", str(pitch),
                "-a", "165", "-w", str(path), str(segment.get("text", ""))
            ])
            if progress_callback:
                progress_callback(int((len(files) and (files.index(path) + 1) * 10 / len(files)) or 0), f"Gerando falas: {files.index(path) + 1}/{len(files)}")
    else:
        try:
            asyncio.run(_synthesize_edge_segments(segments, files, progress_callback))
        except Exception as exc:
            raise RuntimeError(
                "Não foi possível gerar as falas com voz neural. Verifique a conexão de saída "
                "do servidor e a disponibilidade do Edge TTS: " + str(exc)
            ) from exc

    raw = workdir / f"narration-source-{suffix}.{'wav' if use_espeak else 'm4a'}"
    fitted = workdir / f"narration-final-{suffix}.{'wav' if use_espeak else 'm4a'}"
    timeline = []
    cursor = 0.0
    for segment, part in zip(segments, files):
        part_duration = _probe_duration(part)
        timeline.append({
            "start": cursor,
            "end": cursor + part_duration,
            "speaker": str(segment.get("speaker", "Narrador")),
            "scene": int(segment.get("scene", -1)),
        })
        cursor += part_duration
    _concat_audio_files(files, raw, "pcm_s16le" if use_espeak else "aac")
    if progress_callback:
        progress_callback(12, "Áudio das personagens montado. Preparando animação.")
    return raw, fitted, timeline


def _synthesize_narration(text: str, workdir: Path, fmt: str, speech_rate: int):
    # Backward-compatible route for jobs generated before character dialogue was added.
    return _synthesize_segments([{"speaker": "Narrador", "text": text}], workdir, fmt, speech_rate)


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
                   planet_name: str = "Aurora-7", story_plan: dict | None = None,
                   progress_callback: Callable[[int, str], None] | None = None):
    """Render separate long-form and vertical-short edits from one approved story plan."""
    plan = story_plan or {}
    portrait = fmt == "9:16"
    if fmt not in {"16:9", "9:16"}:
        raise ValueError("Formato de renderização não reconhecido.")

    # Horizontal episodes are kept between 5 and 10 minutes; Shorts are
    # a focused highlight (clue -> twist -> team solution), not a recap.
    if portrait:
        narration_text = plan.get("short_script") or story
        audio_segments = plan.get("audio_segments_short") or [{"speaker": "Narrador", "text": narration_text}]
        speech_rate = 145
        min_duration, max_duration, target_duration = 60.0, 88.5, 75.0
    else:
        narration_text = plan.get("long_script") or story
        audio_segments = plan.get("audio_segments_long") or [{"speaker": "Narrador", "text": narration_text}]
        speech_rate = 140
        min_duration, max_duration, target_duration = 301.0, 598.5, 420.0

    if progress_callback:
        progress_callback(1, "Preparando vozes e diálogos dos personagens.")
    voice_raw, voice_fit, voice_timeline = _synthesize_segments(audio_segments, workdir, fmt, speech_rate, progress_callback)
    initial_duration = _probe_duration(voice_raw)
    if progress_callback:
        progress_callback(14, "Vozes prontas. Ajustando duração e cenas.")

    if portrait:
        if initial_duration < min_duration or initial_duration > max_duration:
            fitted_duration = _fit_narration(voice_raw, voice_fit, target_duration)
        else:
            voice_fit.write_bytes(voice_raw.read_bytes())
            fitted_duration = _probe_duration(voice_fit)
        if not (min_duration <= fitted_duration <= max_duration):
            raise RuntimeError(
                f"O áudio do Shorts ficou fora da faixa de 1:00 a 1:30 ({fitted_duration:.1f}s)."
            )
    else:
        if initial_duration < min_duration or initial_duration > max_duration:
            fitted_duration = _fit_narration(voice_raw, voice_fit, target_duration)
        else:
            voice_fit.write_bytes(voice_raw.read_bytes())
            fitted_duration = _probe_duration(voice_fit)
        if not (min_duration <= fitted_duration <= max_duration):
            raise RuntimeError(
                f"O episódio horizontal precisa ficar entre 5 e 10 minutos ({fitted_duration:.1f}s)."
            )

    # Give the final scene a short visual tail after the last spoken line.
    duration_seconds = fitted_duration + 1.2
    timeline_scale = initial_duration / max(.001, fitted_duration)
    for item in voice_timeline:
        item["start"] /= timeline_scale
        item["end"] /= timeline_scale
    width, height = (480, 854) if portrait else (854, 480)
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
    scene_source_indices = list(range(len(render_scenes)))
    if portrait:
        highlight_indices = plan.get("short_scene_indices") or scene_source_indices
        scene_source_indices = [index for index in highlight_indices if 0 <= index < len(render_scenes)]
        render_scenes = [render_scenes[index] for index in scene_source_indices]
        if not render_scenes:
            raise RuntimeError("O roteiro não contém cenas para o destaque do Shorts.")

    scene_count = len(render_scenes)
    total_frames = max(1, int(math.ceil(duration_seconds * FPS)))
    last_reported = -1
    for frame_number in range(total_frames):
        scene_index = min(scene_count - 1, int(frame_number * scene_count / total_frames))
        scene_start = int(scene_index * total_frames / scene_count)
        local_frame = frame_number - scene_start
        scene = render_scenes[scene_index]
        frame_time = frame_number / FPS
        active_speaker = next((item["speaker"] for item in voice_timeline if item["start"] <= frame_time < item["end"]), "")
        visual_scene_index = scene_source_indices[scene_index]
        image = draw_scene_frame(
            (width, height), scene, visual_scene_index, local_frame, portrait, planet_name,
            biome=plan.get("biome", ""),
            mission_object=plan.get("mission_object", ""),
            landmark=plan.get("landmark", ""),
            active_speaker=active_speaker,
        )
        image.save(frames / f"frame-{frame_number:06d}.jpg", quality=88)
        frame_progress = int((frame_number + 1) * 75 / total_frames)
        if progress_callback and frame_progress >= last_reported + 2:
            last_reported = frame_progress
            progress_callback(14 + frame_progress, f"Desenhando cenas 2D: {int((frame_number + 1) * 100 / total_frames)}%")

    low_video = workdir / f"silent-{fmt.replace(':','x')}.mp4"
    if progress_callback:
        progress_callback(91, "Montando sequência de imagens em vídeo.")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
          "-i", str(frames / "frame-%06d.jpg"), "-c:v", "libx264",
          "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-r", "24", "-g", "24", "-keyint_min", "24", "-sc_threshold", "0", str(low_video)])

    if progress_callback:
        progress_callback(95, "Sincronizando vídeo e áudio final.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output_duration = duration_seconds
    target_size = "1080:1920" if portrait else "1920:1080"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(low_video), "-i", str(voice_fit),
          "-filter_complex", f"[0:v]scale={target_size}:flags=lanczos,setsar=1[v];[1:a]apad=pad_dur=2,loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=90,lowpass=f=9000[a]",
          "-map", "[v]", "-map", "[a]", "-t", f"{output_duration:.3f}",
          "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
          "-r", "24", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
          str(output)])
    if not output.exists() or output.stat().st_size < 10000:
        raise RuntimeError("O arquivo de vídeo não foi gerado corretamente.")
    actual_video_duration = _probe_duration(output)
    if progress_callback:
        progress_callback(99, "Validando arquivo, áudio e duração.")
    if portrait and not (60 <= actual_video_duration <= 90):
        raise RuntimeError(f"O vídeo Shorts ficou fora da faixa de 1:00 a 1:30 ({actual_video_duration:.1f}s).")
    if not portrait and not (300 < actual_video_duration <= 600):
        raise RuntimeError(f"O episódio horizontal precisa ficar entre 5 e 10 minutos ({actual_video_duration:.1f}s).")
    return {
        "duration_seconds": round(actual_video_duration, 2),
        "narration_seconds": round(fitted_duration, 2),
        "resolution": "1080x1920" if portrait else "1920x1080",
        "scene_count": scene_count,
        "narration_word_count": sum(len(str(item.get("text", "")).split()) for item in audio_segments),
        "speakers": sorted({str(item.get("speaker", "Narrador")) for item in audio_segments}),
        "voice_profiles_file": str(VOICE_PROFILE_FILE),
    }
