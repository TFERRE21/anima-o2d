"""Speech balloons are the real dialogue on the active narration timeline.

No generic exclamations and no invented lines. Narrator descriptions have
no speech balloon. Pages break long spoken turns at natural word boundaries.
"""
from __future__ import annotations
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SPEAKERS={"Luna":"luna","Tomi":"tomi","Pipo":"pipo","Moradora":"resident",
          "luna":"luna","tomi":"tomi","pipo":"pipo","moradora":"resident"}

def balloon_parts(text: str, max_words: int = 8) -> list[str]:
    words=re.findall(r"\S+", str(text or "").strip())
    if not words:
        return []
    # Preserve every word exactly; only insert line/balloon boundaries.
    parts=[]
    for start in range(0,len(words),max_words):
        parts.append(" ".join(words[start:start+max_words]))
    return parts

def dialogue_beats(segments: list[dict], timeline: list[dict],
                   selected_scenes: list[int], fmt: str) -> dict[int,list[dict]]:
    """Return timeline-relative speaking beats for each active visual scene.

    Audio sources are authoritative. A narrator segment is always silent
    visually. A character's spoken line is split, without rewriting a word,
    and allocated in time proportional to each chunk's word count.
    """
    beats={int(index):[] for index in selected_scenes}
    selected=set(beats)
    for entry, timing in zip(segments,timeline):
        scene=int(timing.get("scene",-1))
        if scene not in selected:
            continue
        speaker=str(entry.get("original_speaker") or "Narrador")
        if speaker not in SPEAKERS:
            beats[scene].append({
                "speaker":None,"text":"",
                "start":float(timing["start"]),"end":float(timing["end"]),
            })
            continue
        raw=str(entry.get("dialogue_text") or "").strip()
        chunks=balloon_parts(raw,8)
        start=float(timing["start"]);end=float(timing["end"])
        total=max(1,sum(len(chunk.split()) for chunk in chunks))
        offset=start
        for i,chunk in enumerate(chunks):
            portion=(end-start)*len(chunk.split())/total
            next_time=end if i==len(chunks)-1 else offset+portion
            beats[scene].append({
                "speaker":SPEAKERS[speaker],"text":chunk,
                "start":offset,"end":next_time,
            })
            offset=next_time
    return beats

def draw_balloon(canvas: Image.Image,text: str,speaker: str,
                 anchor: tuple[int,int],center: tuple[int,int]) -> Image.Image:
    """Draw a proper wrapped comic cloud on the completed active scene."""
    if not text or not speaker:
        return canvas
    img=canvas.convert("RGB").copy()
    d=ImageDraw.Draw(img)
    w,h=img.size
    font=_font(max(18,int(w*.021)))
    words=text.split()
    lines=[];line=""
    max_text_width=int(w*.28)
    for word in words:
        candidate=(line+" "+word).strip()
        if line and d.textbbox((0,0),candidate,font=font)[2]>max_text_width:
            lines.append(line)
            line=word
        else:
            line=candidate
    if line:lines.append(line)
    if not lines:return img
    line_h=max(24,int(w*.028))
    text_w=max(d.textbbox((0,0),t,font=font)[2] for t in lines)
    bw=max(110,min(int(w*.34),text_w+55))
    bh=34+len(lines)*line_h
    cx=max(bw//2+15,min(w-bw//2-15,int(center[0])))
    cy=max(bh//2+13,min(int(h*.37),int(center[1])))
    left=cx-bw//2;top=cy-bh//2
    ink=(37,50,77)
    mask=Image.new("L",(w,h),0)
    m=ImageDraw.Draw(mask)
    lobes=[(.15,.48,.22),(.34,.30,.21),(.55,.28,.23),
           (.79,.41,.20),(.84,.70,.17),(.60,.76,.21),(.34,.77,.20)]
    for px,py,r in lobes:
        x=left+bw*px;y=top+bh*py
        m.ellipse((x-bw*r,y-bh*r,x+bw*r,y+bh*r),fill=255)
    m.rounded_rectangle((left+int(bw*.09),top+int(bh*.19),
                         left+int(bw*.92),top+int(bh*.84)),
                        radius=max(8,int(bh*.20)),fill=255)
    tx=max(10,min(w-10,int(anchor[0])))
    ty=max(top+bh,min(h-8,int(anchor[1])))
    m.polygon([(cx-8,top+int(bh*.78)),(cx+10,top+int(bh*.77)),(tx,ty)],fill=255)
    d.bitmap((0,0),mask.filter(ImageFilter.MaxFilter(7)),fill=ink)
    d.bitmap((0,0),mask,fill="white")
    first_y=cy-(len(lines)*line_h)//2
    for i,line in enumerate(lines):
        d.text((cx,first_y+i*line_h),line,font=font,fill=ink,anchor="mt")
    return img

def speaker_coordinates(scene_index: int, speaker: str, size: tuple[int,int]):
    """Track cast positions used by story_comic_director for each shot."""
    w,h=size
    if scene_index % 4==1:
        positions={"luna":.19,"tomi":.52,"pipo":.81,"resident":.12}
    elif scene_index % 4==2:
        positions={"luna":.36,"tomi":.65,"pipo":.83,"resident":.12}
    elif scene_index % 4==3:
        positions={"luna":.18,"tomi":.49,"pipo":.76,"resident":.12}
    else:
        positions={"luna":.25,"tomi":.53,"pipo":.76,"resident":.12}
    x=int(w*positions.get(speaker,.53))
    # Distribute balloons across the upper sky to avoid collisions.
    if speaker=="luna": center=(int(w*.21),int(h*.17))
    elif speaker=="tomi":center=(int(w*.56),int(h*.12))
    elif speaker=="pipo":center=(int(w*.79),int(h*.22))
    else:center=(int(w*.16),int(h*.13))
    return (x,int(h*.44)),center


def _font(size:int):
    from backend.app.cartoon2d import _font as font
    return font(size,True)
