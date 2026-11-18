"""Google-authorized YouTube uploads, publication slots and duplicate protection."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BRAZIL=ZoneInfo("America/Sao_Paulo")
WEEKDAY={"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,
         "Friday":4,"Saturday":5,"Sunday":6}

def next_publish_time(config:dict,number:int=0,now:datetime|None=None)->str:
    """Distinct slot per format. Explicit São Paulo timezone; store UTC ISO."""
    local=(now or datetime.now(timezone.utc)).astimezone(BRAZIL)
    hour,minute=map(int,str(config.get("publish_time","18:00")).split(":"))
    days=config.get("publish_days") or ["Tuesday","Thursday","Saturday"]
    selected={WEEKDAY[name] for name in days if name in WEEKDAY}
    if not selected:
        raise ValueError("Selecione pelo menos um dia de publicação.")
    # Multiple formats publish 15 min apart, not at exactly the same instant.
    for offset in range(1,16):
        trial=local.replace(hour=hour,minute=minute,second=0,microsecond=0)
        trial=trial+timedelta(days=offset-1,minutes=number*15)
        if trial.weekday() in selected and trial>local+timedelta(minutes=2):
            return trial.astimezone(timezone.utc).isoformat()
    raise RuntimeError("Calendário não contém dia válido.")

def upload_authorized(credentials,video:Path,metadata:dict,
                      privacy:str="public",scheduled_at:str|None=None)->dict:
    """Resumable upload; do not auto-retry an uncertain completed upload."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    if not video.is_file() or video.stat().st_size<10000:
        raise ValueError("Arquivo de vídeo inexistente ou vazio.")
    if privacy not in ("private","unlisted","public"):
        raise ValueError("Privacidade inválida.")
    status={"privacyStatus":privacy,"selfDeclaredMadeForKids":True}
    if scheduled_at:
        future=datetime.fromisoformat(scheduled_at.replace("Z","+00:00"))
        if future.tzinfo is None or future.astimezone(timezone.utc)<=datetime.now(timezone.utc):
            raise ValueError("Agendamento deve ser futuro, com fuso informado.")
        status["privacyStatus"]="private"
        status["publishAt"]=future.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    snippet={
        "title":str(metadata["title"])[:100],
        "description":str(metadata["description"])[:4800],
        "categoryId":str(metadata.get("categoryId","1")),
        "defaultLanguage":"pt-BR",
        "tags":list(metadata.get("tags") or [])[:35],
    }
    youtube=build("youtube","v3",credentials=credentials,cache_discovery=False)
    request=youtube.videos().insert(
        part="snippet,status",body={"snippet":snippet,"status":status},
        media_body=MediaFileUpload(str(video),mimetype="video/mp4",
                                  chunksize=8*1024*1024,resumable=True))
    # Retry only when server provides a clear chunk status. A network timeout
    # after finalization can be uncertain; don't blindly duplicate uploads.
    response=None
    while response is None:
        _,response=request.next_chunk()
    video_id=response.get("id")
    if not video_id:
        raise RuntimeError("YouTube não retornou identificador do vídeo.")
    thumbnail=Path(metadata.get("thumbnail_path") or "")
    thumbnail_status="unavailable"
    if thumbnail.is_file() and thumbnail.suffix.lower() in (".jpg",".jpeg",".png"):
        try:
            from googleapiclient.http import MediaFileUpload as ThumbUpload
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=ThumbUpload(str(thumbnail),mimetype="image/jpeg")
            ).execute()
            thumbnail_status="uploaded"
        except Exception as exc:
            thumbnail_status="failed: "+str(exc)[:180]
    return {
        "video_id":video_id,
        "url":"https://www.youtube.com/watch?v="+video_id,
        "format":metadata["format"],
        "status":"scheduled" if scheduled_at else privacy,
        "scheduled_at":scheduled_at,
        "uploaded_at":datetime.now(timezone.utc).isoformat(),
        "thumbnail_status":thumbnail_status,
        "made_for_kids":True,
        "title":snippet["title"],
    }
