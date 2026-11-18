"""Prepare metadata, cover and children's audience information before upload."""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from backend.app.channel_branding import CHANNEL_NAME,CHANNEL_SUBTITLE,_font

BASE_TAGS=[
    "Pequenos Guardiões","Luna Tomi e Pipo","desenho infantil",
    "aventura infantil","história educativa","animação 2D","planetas",
    "amizade","trabalho em equipe","aprendizado infantil",
]

def _clean(value:str,limit:int=200):
    return re.sub(r"\s+"," ",str(value or "")).strip()[:limit]

def content_metadata(plan:dict,fmt:str)->dict:
    """Never invent plot points: derive all episode SEO from approved story plan."""
    planet=_clean(plan.get("planet") or "Novo Planeta",60)
    episode=_clean(plan.get("title") or f"A Missão de {planet}",90)
    value=_clean(plan.get("value") or "amizade e cooperação",100)
    synopsis=_clean(plan.get("synopsis") or
                    f"Luna, Tomi e Pipo visitam {planet} e aprendem sobre {value}.",380)
    is_short=fmt=="9:16"
    title=(f"{episode} | Luna, Tomi e Pipo" if not is_short else
           f"{episode} | Pequenos Guardiões #Shorts")
    title=title[:100]
    tags=list(dict.fromkeys(BASE_TAGS+[planet,_clean(value,60),
                                       "aventuras espaciais","desenhos para crianças"]))
    normalized=re.sub(r"[^A-Za-z0-9À-ÿ]","",planet)
    hashtags=["#PequenosGuardioes","#LunaTomiPipo","#DesenhoInfantil",
              "#HistoriasInfantis"]
    if normalized:
        hashtags.append("#"+normalized)
    if is_short:
        hashtags.insert(0,"#Shorts")
    description=(
        f"🚀 {episode}\n\n{synopsis}\n\n"
        f"🪐 Planeta: {planet}\n"
        f"💛 Aprendizado: {value}\n\n"
        "Luna, Tomi e Pipo vivem novas aventuras em planetas incríveis, "
        "descobrem pistas e aprendem a ajudar os amigos com respeito e imaginação.\n\n"
        "🌟 Acompanhe as próximas histórias de Luna, Tomi e Pipo — Pequenos Guardiões!\n\n"
        + " ".join(hashtags)
    )
    return {"title":title,"description":description[:4800],"tags":tags,
            "categoryId":"1","defaultLanguage":"pt-BR",
            "selfDeclaredMadeForKids":True,"hashtags":hashtags,
            "format":fmt}

def _thumbnail(video:Path,destination:Path,metadata:dict):
    from backend.app.renderer import _ffmpeg_executable
    destination.parent.mkdir(parents=True,exist_ok=True)
    raw=destination.with_name("frame-thumbnail.jpg")
    subprocess.run([_ffmpeg_executable(),"-y","-loglevel","error",
                    "-ss","1","-i",str(video),"-frames:v","1",
                    "-vf","scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
                    str(raw)],timeout=60,check=True)
    with Image.open(raw) as source:
        cover=ImageOps.fit(source.convert("RGB"),(1280,720))
    d=ImageDraw.Draw(cover,"RGBA")
    d.rounded_rectangle((45,460,1235,680),radius=28,fill=(12,29,66,210))
    short=metadata["title"].split(" | ")[0].strip()
    # Fit title rather than printing over characters or outside the frame.
    size=66
    while size>25 and d.textbbox((0,0),short,font=_font(size,True))[2]>1120:
        size-=3
    d.text((82,490),short,fill=(255,255,255),font=_font(size,True),
           stroke_width=2,stroke_fill=(15,39,87))
    d.text((82,607),CHANNEL_NAME+" · "+CHANNEL_SUBTITLE,
           fill=(255,217,128),font=_font(31,True))
    # Use under 2 MB when possible; API may reject oversized images.
    cover.save(destination,format="JPEG",quality=85,optimize=True)
    raw.unlink(missing_ok=True)
    if destination.stat().st_size>2*1024*1024:
        cover.save(destination,format="JPEG",quality=72,optimize=True)
    return destination

def prepare_package(plan:dict,fmt:str,video:Path,workdir:Path)->dict:
    metadata=content_metadata(plan,fmt)
    folder=workdir/"youtube-ready"/fmt.replace(":","x")
    folder.mkdir(parents=True,exist_ok=True)
    thumbnail=folder/"thumbnail.jpg"
    _thumbnail(video,thumbnail,metadata)
    metadata["thumbnail_path"]=str(thumbnail)
    metadata["video_path"]=str(video)
    (folder/"metadata.json").write_text(
        json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf8")
    return metadata
