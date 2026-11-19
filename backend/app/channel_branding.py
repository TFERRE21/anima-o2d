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

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

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

def brand_frame(fmt:str,ending:bool,phase:float,title:str="",
                backdrop:Image.Image|None=None):
    """Single 16:9 or portrait frame with the current episode's illustrated cast."""
    portrait=fmt=="9:16"
    w,h=(720,1280) if portrait else (1280,720)
    if backdrop is None:
        im=Image.new("RGB",(w,h))
    else:
        # Reuse the actual AI-rendered episode style: no old low-detail cast.
        art=ImageOps.fit(backdrop.convert("RGB"),(w,h),
                         Image.Resampling.LANCZOS)
        art=art.filter(ImageFilter.GaussianBlur(1.6)).convert("RGBA")
        veil=Image.new("RGBA",(w,h),(14,28,68,105 if ending else 118))
        im=Image.alpha_composite(art,veil).convert("RGB")
    d=ImageDraw.Draw(im)
    if backdrop is None:
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
    if backdrop is None:
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

def _render_ident(workdir:Path,fmt:str,ending:bool,ffmpeg:str,
                  backdrop:Image.Image|None=None)->Path:
    tag=("outro" if ending else "intro")+"-v5-"+fmt.replace(":","x")
    folder=workdir/"brand-sequence-v5"/tag
    folder.mkdir(parents=True,exist_ok=True)
    target=workdir/(tag+".mp4")
    if target.is_file() and target.stat().st_size>5000:
        return target
    fps=12
    duration=5 if ending else 4
    for frame in range(fps*duration):
        brand_frame(fmt,ending,frame/(fps*duration),backdrop=backdrop).save(
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

def _episode_backdrop(video:Path,ffmpeg:str,ending:bool)->Image.Image|None:
    """Sample one original illustrated frame, preserving AI scene art style."""
    from backend.app.renderer import _probe_duration
    length=_probe_duration(video)
    moment=max(2,min(length-2,length*.85 if ending else length*.18))
    candidate=video.parent / ("brand-backdrop-end.jpg" if ending else "brand-backdrop-start.jpg")
    try:
        subprocess.run([ffmpeg,"-y","-loglevel","error","-ss",str(moment),
                        "-i",str(video),"-frames:v","1",str(candidate)],
                       check=True,timeout=45)
        with Image.open(candidate) as photo:
            photo.load()
            return photo.convert("RGB")
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        return None


def _append_short_outro(ffmpeg:str,short_video:Path,outro:Path,target:Path) -> float:
    """Join Short + outro through normalized A/V timestamps, without ffprobe.

    Stream-copy does not reliably append the 5-second outro when the narrator
    and bumper use different encoder timestamps. This only runs on 9:16.
    """
    from backend.app.renderer import _probe_duration
    base=_probe_duration(short_video)
    ending=_probe_duration(outro)
    # One 9:16 stream at constant FPS; no duration extrapolation or -c copy.
    filters=(
        "[0:v]settb=AVTB,setpts=PTS-STARTPTS,"
        "scale=1080:1920:flags=lanczos,setsar=1,"
        "fps=24,format=yuv420p[v0];"
        "[1:v]settb=AVTB,setpts=PTS-STARTPTS,"
        "scale=1080:1920:flags=lanczos,setsar=1,"
        "fps=24,format=yuv420p[v1];"
        "[0:a]aresample=async=1:first_pts=0,"
        "asetpts=PTS-STARTPTS,"
        "aformat=sample_rates=48000:channel_layouts=stereo[a0];"
        "[1:a]aresample=async=1:first_pts=0,"
        "asetpts=PTS-STARTPTS,"
        "aformat=sample_rates=48000:channel_layouts=stereo[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    proc=subprocess.run([
        ffmpeg,"-y","-hide_banner","-loglevel","error",
        "-i",str(short_video),"-i",str(outro),
        "-filter_complex",filters,
        "-map","[v]","-map","[a]",
        "-c:v","libx264","-preset","ultrafast","-crf","22",
        "-r","24","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","160k","-ar","48000",
        "-movflags","+faststart",str(target),
    ],capture_output=True,text=True,timeout=900)
    if proc.returncode:
        raise RuntimeError("Falha ao acrescentar encerramento ao Short: "+
                           proc.stderr[-1200:])
    measured=_probe_duration(target)
    expected=base+ending
    if abs(measured-expected)>2.0:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"Encerramento do Short incompleto: {measured:.1f}s; "
            f"esperado aproximadamente {expected:.1f}s."
        )
    return measured


def finish_episode(output:Path,fmt:str,workdir:Path)->dict:
    """Append original ident(s) without replacing or modifying story footage."""
    from backend.app.renderer import _ffmpeg_executable, _probe_duration
    ffmpeg=_ffmpeg_executable()
    clips=[]
    if fmt=="16:9":
        clips.append(_render_ident(workdir,fmt,False,ffmpeg,
                                  _episode_backdrop(output,ffmpeg,False)))
    clips.append(output)
    clips.append(_render_ident(workdir,fmt,True,ffmpeg,
                               _episode_backdrop(output,ffmpeg,True)))
    # Keep 9:16 on the lightweight, previously working Short pipeline.
    # FFprobe validation and full re-encoding remain restricted to 16:9.
    from backend.app.renderer import _probe_duration
    target=output.with_name(output.stem+"-branded.mp4")
    if fmt=="9:16":
        # Re-encode ONLY the final 5-second outro join. Character drawings,
        # narration synthesis, music and live scene preview are untouched.
        expected=_probe_duration(output)+_probe_duration(clips[-1])
        result_seconds=_append_short_outro(ffmpeg,output,clips[-1],target)
    else:
        # Long episodes require audio-safe timestamp normalization because
        # their old final copy caused broken duration and silent playback.
        from backend.app.video_integrity import concat_with_audio, validate_video
        story_info=validate_video(output,require_audio=True,min_seconds=15)
        expected=story_info["duration"]+9
        result=concat_with_audio(clips,target,fps=24)
        result_seconds=result["duration"]
    if abs(result_seconds-expected)>2.0:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"Vídeo final com duração incorreta: {result_seconds:.1f}s "
            f"(esperado aproximadamente {expected:.1f}s)."
        )
    # Never overwrite an otherwise valid story with an invalid or silent file.
    os.replace(target,output)
    return {"duration_seconds":round(result_seconds,2),
            "channel_intro":fmt=="16:9","channel_outro":True,
            "brand_version":"original-channel-ident-v5"}
