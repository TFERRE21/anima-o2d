"""A reproducible visual character bible shipped with the Studio.

The approved Luna/Tomi/Pipo sprites are bundled in the repository. Build a
single compact full-color reference contact sheet to condition reference-aware
Cloudflare models. Nothing has to be manually uploaded per episode.
"""
from __future__ import annotations
import io
import hashlib
from PIL import Image, ImageDraw, ImageFont, ImageOps
from backend.app.approved_cast_embedded import character_sprite


def reference_sheet() -> bytes:
    canvas=Image.new("RGB",(480,480),(251,247,235))
    d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((4,4,476,476),radius=15,fill=(255,252,242),outline=(41,60,82),width=3)
    entries=[
        ("LUNA","luna",(255,112,183),15),
        ("TOMI","tomi",(87,174,246),172),
        ("PIPO","pipo",(253,211,94),330),
    ]
    for name,key,color,left in entries:
        d.rounded_rectangle((left+2,47,left+144,415),radius=16,
                            fill=(236,245,252),outline=(199,217,232),width=2)
        sprite=character_sprite(key).convert("RGBA")
        # Reuse the exact on-screen color-filling logic so the reference has
        # the same approved faces and costume colors as previous episodes.
        from backend.app.story_comic_director import _color_approved_ink
        fill=_color_approved_ink(sprite,key)
        fit_h=270 if key!="pipo" else 215
        fit_w=round(fill.width*fit_h/fill.height)
        fit=fill.resize((fit_w,fit_h),Image.Resampling.LANCZOS)
        left_sprite=left+73-fit.width//2
        top=112+(270-fit_h)
        canvas.paste(fit,(left_sprite,top),fit)
        d.text((left+73,82),name,fill=(38,53,75),anchor="mm")
        d.text((left+73,431),{"LUNA":"pink suit","TOMI":"blue suit","PIPO":"round robot"}[name],
               fill=(48,68,88),anchor="mm")
    result=io.BytesIO()
    canvas.save(result,format="PNG",optimize=True)
    return result.getvalue()


def reference_digest() -> str:
    return hashlib.sha256(reference_sheet()).hexdigest()[:16]


def stage_direction(scene:dict,index:int,planet:str,biome:str,theme:str,inhabitants:str) -> str:
    """Actual shot direction: scale/setting/visible alien species per scene."""
    text=" ".join(str(scene.get(k,"")) for k in
                  ("title","caption","visual_action","action","spoken_excerpt")).lower()
    people=("habitante","morador","povo","criatur","alien","receb","comunidade",
            "nativ","convers","ajuda","encontr")
    resident_focus=any(word in text for word in people)
    panorama=theme=="lookout" or any(word in text for word in ("panorama","vista de longe","horizonte"))
    village=theme in ("town","library","workshop")
    closeup=any(word in text for word in ("abraça","emoção","comemora","sussurra","expressão"))
    if panorama:
        scale="long distance establishing shot: protagonists are small foreground figures, 15-21 percent of canvas height, scenery dominates"
    elif village:
        scale="wide village perspective: protagonists are only 20-27 percent of image height, nearby houses at least twice their height, streets and plants visibly larger in depth"
    elif resident_focus:
        scale="balanced mid-wide interaction: protagonists 24-30 percent of image height, local residents in consistent scale with doorways and windows"
    elif closeup:
        scale="medium framing, protagonists 32-39 percent image height"
    else:
        scale="medium-wide framing, protagonists 24-32 percent of image height"
    native_rule=(
        "Show 1-3 endearing distinctive indigenous residents designed for this planet, "
        "with consistent color, anatomy and scale, interacting appropriately with the trio."
        if resident_focus and not panorama else
        "No extra indigenous residents in this shot; only Luna, Tomi and Pipo."
    )
    scene_words=str(scene.get("visual_action") or scene.get("action") or
                    scene.get("caption") or "")
    return (
        f"SCENE {index+1} PLANET {planet}, BIOME {biome}. "
        f"SHOW {theme.upper()}: {scene_words[:280]}. "
        f"{scale}. {native_rule} "
        "Use image 0 as the exact permanent identity reference: "
        "LUNA is the left girl with curly ponytail and pink spacesuit; "
        "TOMI is the middle boy with lifted hair and blue spacesuit; "
        "PIPO is the small round white-and-yellow robot at right. "
        "Maintain same distinctive faces, hair, uniform marks and proportions across episodes. "
        "Use the reference sheet for who they ARE, not for the rough line-art "
        "finish. REDRAW their same facial identity, hair and uniforms as lavishly "
        "colored premium storybook illustrations, with the EXACT SAME painterly "
        "finish as trees, houses and indigenous characters. Do not paste their "
        "flat outlines on top of a realistic scene. All three must stand on the "
        "ground at human-child scale compared with doors, bridges and tree trunks; "
        "Pipo is about 60 percent of Luna's height. "
        "Use expressive eyebrows, anatomically natural mouths, matched ambient "
        "light, contact shadows and shared perspective. "
        "Do not create duplicate protagonists, circular O mouths, any speech text, "
        "balloons, letters, captions, watermark, rectangular frames or TV borders. "
        "Illustrate the narrated event with a detailed city/vegetation/landscape in "
        "rich polished children's comic style, bright but balanced colors. "
        "Every scene changes composition and camera position while planet architecture "
        "and resident species remain recognizable."
    )
