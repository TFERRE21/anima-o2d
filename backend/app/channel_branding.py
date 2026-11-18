"""Original animated branding for the Pequenos Guardiões children's channel.

No external stock music, copyrighted graphics or image API is used. The
already-approved fixed cast is used ONLY in this channel ident, while the
episode's scenes continue being generated independently by the image engine.
"""
from __future__ import annotations

import hashlib
import math
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.app.children_music import create_music

CHANNEL_NAME="Luna, Tomi e Pipo"
CHANNEL_SUBTITLE="PEQUENOS GUARDIÕES"
CHANNEL_PROMISE="Grandes aventuras, grandes aprendizados!"

def _font(size,bold=False):
    from backend.app.cartoon2d import _font
    return _font(max(12,int(size)),bold)

def _cast_sprite(name,height):
    from backend.app.approved_cast_embedded import character_sprite
    from backend.app.story_comic_director import _color_approved_ink
    source=_color_approved_ink(character_sprite(name),name)
    width=max(1,round(source.width*height/source.height))
    return source.resize((width,height),Image.Resampling.LANCZOS)

def brand_frame(fmt:str,ending:bool,phase:float,title:str=""):
    """Single 16:9 or portrait frame, accessible readable type and moving cast."""
    portrait=fmt=="9:16"
    w,h=(720,1280) if portrait else (1280,720)
    im=Image.new("RGB",(w,h));d=ImageDraw.Draw(im)
    for y in range(h):
        t=y/max(1,h-1)
        d.line((0,y,w,y),fill=(
            round(19+30*t),round(36+50*t),round(98+60*t)))
    key=hashlib.sha256((CHANNEL_NAME+"brand").encode()).digest()
    for i in range(90):
        x=(i*167+key[i%len(key)]*13)%w
        y=(i*83+key[(i+9)%len(key)]*11)%h
        r=1+(i%3==0)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(215,236,254))
    center_x=w//2
    glow_y=round(h*(.51 if portrait else .54))
    rr=round(min(w,h)*(.30+.017*math.sin(phase*math.pi*2)))
    d.ellipse((center_x-rr,glow_y-rr,center_x+rr,glow_y+rr),
              fill=(41,94,166),outline=(127,217,240),width=7)
    d.arc((center_x-rr-35,glow_y-rr//2,center_x+rr+35,glow_y+rr//2),
          5,175,fill=(255,213,119),width=8)
    unit=min(w,h)
    if portrait:
        height=int(h*.20)
        centers=(int(w*.24),int(w*.56),int(w*.81))
        foot=int(h*.72)
    else:
        height=int(h*.34)
        centers=(int(w*.33),int(w*.50),int(w*.65))
        foot=int(h*.83)
    for i,name in enumerate(("luna","tomi","pipo")):
        hh=int(height*(.67 if name=="pipo" else 1.0))
        sprite=_cast_sprite(name,hh)
        bob=round(8*math.sin(phase*math.pi*2+i*.8))
        x=centers[i]-sprite.width//2
        y=foot-hh+bob
        im.paste(sprite,(x,y),sprite)
    d=ImageDraw.Draw(im)
    title_size=int(unit*(.058 if portrait else .062))
    caption_size=int(unit*(.039 if portrait else .039))
    if not ending:
        d.text((center_x,int(h*.09)),CHANNEL_NAME,font=_font(title_size,True),
               anchor="mt",fill=(255,255,255),stroke_width=2,stroke_fill=(20,45,83))
        d.text((center_x,int(h*.18)),CHANNEL_SUBTITLE,font=_font(caption_size,True),
               anchor="mt",fill=(255,220,119))
        d.text((center_x,int(h*.89)),CHANNEL_PROMISE,font=_font(int(unit*.028),True),
               anchor="mm",fill=(245,252,255))
    else:
        d.text((center_x,int(h*.11)),"GOSTOU DA AVENTURA?",font=_font(int(unit*.053),True),
               anchor="mt",fill=(255,238,144),stroke_width=2,stroke_fill=(12,29,68))
        d.text((center_x,int(h*.22)),"INSCREVA-SE NO CANAL!",font=_font(int(unit*.052),True),
               anchor="mt",fill=(255,255,255),stroke_width=2,stroke_fill=(12,29,68))
        d.text((center_x,int(h*.87)),"E acompanhe nossas próximas histórias!",
               font=_font(int(unit*.027),True),anchor="mm",fill=(245,248,255))
    return im

def _render_ident(workdir:Path,fmt:str,ending:bool,ffmpeg:str)->Path:
    tag=("outro" if ending else "intro")+"-"+fmt.replace(":","x")
    folder=workdir/"brand-sequence-v1"/tag
    folder.mkdir(parents=True,exist_ok=True)
    target=workdir/(tag+".mp4")
    if target.is_file() and target.stat().st_size>5000:
        return target
    fps=12
    duration=5 if ending else 4
    for frame in range(fps*duration):
        brand_frame(fmt,ending,frame/(fps*duration)).save(
            folder/f"frame-{frame:04d}.png",format="PNG")
    music=create_music(folder/"music.wav",duration,tag+"original")
    subprocess.run([
        ffmpeg,"-y","-hide_banner","-loglevel","error",
        "-framerate",str(fps),"-i",str(folder/"frame-%04d.png"),
        "-i",str(music),"-t",str(duration),"-r","24",
        "-vf",("scale=1080:1920" if fmt=="9:16" else "scale=1920:1080")+",format=yuv420p",
        "-c:v","libx264","-preset","veryfast","-crf","22",
        "-c:a","aac","-b:a","160k","-ar","48000",
        "-movflags","+faststart",str(target)
    ],check=True,timeout=180)
    return target

def finish_episode(output:Path,fmt:str,workdir:Path)->dict:
    """Append original ident(s) without replacing or modifying story footage."""
    from backend.app.renderer import _ffmpeg_executable, _probe_duration
    ffmpeg=_ffmpeg_executable()
    clips=[]
    if fmt=="16:9":
        clips.append(_render_ident(workdir,fmt,False,ffmpeg))
    clips.append(output)
    clips.append(_render_ident(workdir,fmt,True,ffmpeg))
    manifest=workdir/("channel-sequence-"+fmt.replace(":","x")+".txt")
    def escape(p:Path)->str:
        return p.resolve().as_posix().replace("'","'\\''")
    manifest.write_text("".join("file '"+escape(p)+"'\n" for p in clips),encoding="utf8")
    target=output.with_name(output.stem+"-branded.mp4")
    subprocess.run([ffmpeg,"-y","-loglevel","error","-f","concat",
                    "-safe","0","-i",str(manifest),"-c","copy",
                    "-movflags","+faststart",str(target)],check=True,timeout=300)
    if not target.exists() or target.stat().st_size<10000:
        raise RuntimeError("Falha na vinheta e encerramento do episódio.")
    result_seconds=_probe_duration(target)
    if result_seconds<=_probe_duration(output):
        raise RuntimeError("Montagem da vinheta ficou sem duração adicional.")
    os.replace(target,output)
    return {"duration_seconds":round(result_seconds,2),
            "channel_intro":fmt=="16:9","channel_outro":True,
            "brand_version":"original-channel-ident-v1"}
