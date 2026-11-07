from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FPS = 10
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

def draw_scene_frame(size, scene, index, frame, portrait):
    w,h=size
    t=frame/FPS
    palettes=[
        ("#9bd8ff","#fff0c7","#61b77a"),
        ("#9bd8ff","#ffe3a1","#64b87b"),
        ("#a6dfff","#fff0ca","#65b67c"),
        ("#a4ddff","#ffe4a7","#65b77c"),
        ("#93d5ff","#fff0c6","#65b77c"),
        ("#8ccaff","#ffe9a8","#5eaf73"),
    ]
    sky,sun,ground=palettes[index]
    im=Image.new("RGB",(w,h),sky)
    d=ImageDraw.Draw(im)
    d.ellipse((w*.72,-h*.18,w*1.05,h*.18),fill=sun)
    # soft clouds
    for cx,cy in [(w*.12,h*.17),(w*.72,h*.22)]:
        d.ellipse((cx-45,cy-18,cx+45,cy+20),fill="#f7fbff")
        d.ellipse((cx-20,cy-32,cx+28,cy+22),fill="#f7fbff")
    # school building and windows
    d.rectangle((w*.08,h*.28,w*.92,h*.72),fill="#f7c66e",outline="#a86e45",width=3)
    d.polygon([(w*.04,h*.30),(w*.5,h*.12),(w*.96,h*.30)],fill="#d96f54")
    for col in range(5):
        for row in range(2):
            xx=w*(.16+col*.15); yy=h*(.38+row*.14)
            rounded(d,(xx,yy,xx+w*.075,yy+h*.09),6,"#83c9e9","#fff4d2",2)
    d.rectangle((w*.43,h*.49,w*.57,h*.72),fill="#7e4b38")
    d.rectangle((0,h*.72,w,h),fill=ground)
    # path
    d.polygon([(w*.40,h*.72),(w*.60,h*.72),(w*.78,h),(w*.22,h)],fill="#e8d4aa")
    # props: backpacks
    for bx,by,col in [(w*.16,h*.68,"#3389e8"),(w*.79,h*.68,"#d94c9c")]:
        rounded(d,(bx-w*.035,by-h*.08,bx+w*.035,by+h*.015),10,col,"#28395e",2)
        d.ellipse((bx-w*.012,by-h*.045,bx+w*.012,by-h*.01),fill="#ffd34e")
    # heroes move gently, composition changes by aspect
    if portrait:
        base_y=h*.62
        draw_girl(d,w*.30,base_y,w/900,t)
        draw_boy(d,w*.70,base_y,w/900,t)
        draw_dog(d,w*.50,h*.79,w/1500,t)
        header_y=h*.07
        sub_y=h*.86
    else:
        base_y=h*.61
        draw_girl(d,w*.38,base_y,h/720*.9,t)
        draw_boy(d,w*.62,base_y,h/720*.9,t)
        draw_dog(d,w*.79,h*.77,h/1300,t)
        header_y=h*.055
        sub_y=h*.83
    # title banner
    rounded(d,(w*.07,header_y,w*.93,header_y+h*.10),int(h*.025),"#102e60")
    title=scene[0]
    f=font(max(15,int(h*.042)),True)
    box=d.textbbox((0,0),title,font=f)
    d.text(((w-(box[2]-box[0]))/2,header_y+h*.018),title,font=f,fill="#ffffff",stroke_width=1,stroke_fill="#102044")
    # subtitle panel
    rounded(d,(w*.055,sub_y,w*.945,sub_y+h*.125),int(h*.022),"#fffdf2","#e5b94c",max(1,int(h*.004)))
    text=scene[1]
    f2=font(max(13,int(h*(.027 if portrait else .031))),True)
    max_width=w*.82
    words=text.split()
    lines=[]; line=""
    for word in words:
        test=(line+" "+word).strip()
        if d.textlength(test,font=f2)<=max_width: line=test
        else:
            if line: lines.append(line)
            line=word
    if line: lines.append(line)
    line_h=int(h*.038)
    total=len(lines)*line_h
    start_y=sub_y+(h*.125-total)/2
    for j,line in enumerate(lines[:3]):
        tw=d.textlength(line,font=f2)
        d.text(((w-tw)/2,start_y+j*line_h),line,font=f2,fill="#17294a")
    # animated sparkles
    for k in range(5):
        sx=(w*(.12+k*.18)+math.sin(t*2+k)*w*.012)
        sy=h*(.24+(k%2)*.08)
        r=max(2,int(h*.006))
        d.ellipse((sx-r,sy-r,sx+r,sy+r),fill="#fff5a6")
    return im

def _run(cmd):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-1800:])
    return p

def render_episode(title: str, story: str, fmt: str, output: Path, workdir: Path):
    portrait=fmt=="9:16"
    width,height=(405,720) if portrait else (720,405)
    frames=workdir/f"frames-{fmt.replace(':','x')}"
    frames.mkdir(parents=True,exist_ok=True)
    sentences=[x.strip() for x in story.replace("!", ".").replace("?", ".").split(".") if x.strip()]
    captions=(sentences + [scene[1] for scene in SCENES])[:6]
    episode_scenes=[(title if i==0 else SCENES[i][0], captions[i], SCENES[i][2]) for i in range(6)]
    total=SCENE_SECONDS*FPS
    for scene_index,scene in enumerate(episode_scenes):
        for f in range(total):
            image=draw_scene_frame((width,height),scene,scene_index,f,portrait)
            number=scene_index*total+f
            image.save(frames/f"frame-{number:05d}.jpg",quality=88)
    low_video=workdir/f"silent-{fmt.replace(':','x')}.mp4"
    _run(["ffmpeg","-y","-loglevel","error","-framerate",str(FPS),"-i",str(frames/"frame-%05d.jpg"),"-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p","-vf",f"scale={1920 if not portrait else 1080}:{1080 if not portrait else 1920}:flags=lanczos","-r","30",str(low_video)])
    narration=" ".join(captions)
    wav=workdir/"narration.wav"
    voice_ok=False
    try:
        _run(["espeak-ng","-v","pt-br","-s","145","-w",str(wav),narration])
        voice_ok=wav.exists() and wav.stat().st_size>1000
    except (FileNotFoundError,RuntimeError):
        voice_ok=False
    output.parent.mkdir(parents=True,exist_ok=True)
    if voice_ok:
        _run(["ffmpeg","-y","-loglevel","error","-i",str(low_video),"-i",str(wav),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","128k","-shortest","-movflags","+faststart",str(output)])
    else:
        _run(["ffmpeg","-y","-loglevel","error","-i",str(low_video),"-c:v","copy","-movflags","+faststart",str(output)])
    if not output.exists() or output.stat().st_size<10000:
        raise RuntimeError("O arquivo de vídeo não foi gerado corretamente.")
