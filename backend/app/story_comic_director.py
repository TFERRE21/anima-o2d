"""Story-responsive comic staging with the approved recurring characters.

Deterministic per-planet inhabitant designs and per-scene layouts. No external
image service, no per-scene upload, and no replacement of Luna/Tomi/Pipo.
"""
from __future__ import annotations

import hashlib
import math
import random
import re
import unicodedata
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

def normal(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(text)).lower() if not unicodedata.combining(c))

def seed_for(*parts):
    return int.from_bytes(hashlib.sha256('|'.join(map(str,parts)).encode('utf8')).digest()[:8],'big')

def emotions(text):
    t=normal(text)
    if any(x in t for x in ('surpresa','inesperad','uau','espant','descobri','inesperad')): return 'surpresa','UAU!'
    if any(x in t for x in ('preocup','perigo','falhou','problema','nao funciona','medo')): return 'preocupacao','OH!'
    if any(x in t for x in ('pista','observ','procura','pergunta','investig','como','curios')): return 'curiosidade','HUM...'
    if any(x in t for x in ('consegu','comemor','feliz','vitória','agradec','sorrir')): return 'alegria','OBA!'
    if any(x in t for x in ('plano','organiza','anota','escreve','registra')): return 'concentracao','AHÁ!'
    return 'alegria','VAMOS!'

def _font(size,bold=True):
    from backend.app.cartoon2d import _font
    return _font(size,bold)

def _scene_theme(scene_index, story):
    t=normal(' '.join(str(story.get(k,'')) for k in ('title','caption','visual_action','action')))
    categories={
        'nave':('nave','partida','cinto','estrel','viagem','volta','janela'),
        'vila':('vila','habitante','comunidade','amigo','morador','ouve','escuta'),
        'investigacao':('pista','indicio','observ','procura','investig','marca','detalhe'),
        'oficina':('plano','monta','organiza','sistema','solucao','conser','tecnic','equipamento'),
        'festa':('consegu','festa','comemor','sorrir','agradec','lição','convite'),
        'biblioteca':('livro','biblioteca','diario','registro'),
        'ponte':('ponte','caminho','placa','estrada'),
        'jardim':('semente','flor','jardim','arvore','natureza'),
        'mar':('agua','canal','oceano','concha','lago'),
    }
    matches=[name for name,keywords in categories.items() if any(word in t for word in keywords)]
    return matches[0] if matches else ['paisagem','mercado','mirante','bosque','praca'][scene_index%5]

def _world_palette(planet,biome):
    v=normal(planet+' '+biome)
    if any(s in v for s in ('ocean','mar','aquat','azul')): return ((113,211,233),(30,110,172),(244,197,99),'ocean')
    if any(s in v for s in ('gel','gelo','ice','glaci')): return ((173,229,250),(86,153,207),(245,250,255),'ice')
    if any(s in v for s in ('vulc','vermelh','deserto')): return ((247,192,128),(186,79,87),(255,225,150),'volcano')
    if any(s in v for s in ('flora','petala','flor','jardim')): return ((188,231,154),(87,160,111),(251,170,205),'flora')
    if 'nuvem' in v: return ((185,215,250),(135,157,216),(246,212,255),'cloud')
    # Give even similar biomes their own reproducible species coloration.
    choices=[
        ((176,208,247),(113,148,202),(245,203,124),'aurora'),
        ((218,184,249),(137,107,189),(255,213,142),'sapphire'),
        ((235,215,184),(161,133,184),(150,232,219),'moon'),
        ((174,222,206),(85,160,154),(254,200,131),'crystal'),
    ]
    return choices[seed_for(planet)%len(choices)]

def _alien(d,x,y,scale,variant,palette,emotion):
    """Planet inhabitants keep their distinct morphology throughout an episode."""
    x=int(x);y=int(y);s=max(1,int(scale))
    ink=(34,47,70);light,dark,accent,_=palette
    def oval(b,fill,outline=ink,width=3):
        d.ellipse(tuple(int(v) for v in b),fill=fill,outline=outline,width=width)
    if variant=='ocean':
        d.polygon([(x,y-s),(x-s,y+s),(x+s,y+s)],fill=accent)
        oval((x-s,y-s,x+s,y+s),light)
        d.arc((x-s*1.2,y-s*.5,x+s*1.2,y+s*1.3),0,180,fill=dark,width=4)
    elif variant=='ice':
        d.polygon([(x,y-s*1.6),(x-s,y),(x-s*.6,y+s),(x+s*.6,y+s),(x+s,y)],fill=light)
        d.line([(x,y-s*1.6),(x-s,y),(x-s*.6,y+s),(x+s*.6,y+s),(x+s,y),(x,y-s*1.6)],fill=ink,width=3)
    elif variant=='volcano':
        d.rounded_rectangle((x-s,y-s,x+s,y+s),radius=s//3,fill=accent,outline=ink,width=3)
        d.polygon([(x-s,y-s),(x,y-s*1.6),(x+s,y-s)],fill=dark)
    elif variant=='flora':
        for a in range(0,360,60):
            xx=x+math.cos(math.radians(a))*s*.8
            yy=y-s*.4+math.sin(math.radians(a))*s*.8
            oval((xx-s*.48,yy-s*.48,xx+s*.48,yy+s*.48),accent)
        oval((x-s*.8,y-s*1.1,x+s*.8,y+s*.65),light)
    else:
        oval((x-s,y-s,x+s,y+s),light)
        for dx in (-s*.55,s*.55):
            d.line([(x+dx,y-s*.7),(x+dx*1.3,y-s*1.6)],fill=ink,width=3)
            oval((x+dx*1.3-s*.13,y-s*1.8,x+dx*1.3+s*.13,y-s*1.5),accent)
    oval((x-s*.44,y-s*.25,x-s*.24,y+s*.04),ink,ink,1)
    oval((x+s*.24,y-s*.25,x+s*.44,y+s*.04),ink,ink,1)
    if emotion=='surpresa':
        oval((x-s*.10,y+s*.16,x+s*.1,y+s*.39),ink,ink,1)
    else:
        d.arc((x-s*.28,y,x+s*.28,y+s*.5),5,175,fill=ink,width=3)
    d.line([(x-s*.45,y+s*.9),(x-s*.57,y+s*1.32)],fill=ink,width=4)
    d.line([(x+s*.45,y+s*.9),(x+s*.57,y+s*1.32)],fill=ink,width=4)

def _balloon(d, text, center, anchor, canvas_size=(1280,720)):
    """Cloud-shaped speech bubble with a single clean perimeter and a tail.

    Text stays inside the white cloud and the tail points to the speaking
    character. The transparent mask avoids overlapping ellipse outlines.
    """
    w,h=canvas_size
    label=str(text or '').strip().upper()[:15]
    if not label:
        return
    size=max(14,min(26,round(w/51)))
    font=_font(size,True)
    ink=(30,48,78)
    bounds=d.textbbox((0,0),label,font=font)
    tw=bounds[2]-bounds[0]
    bubble_w=max(112,min(w-28,tw+80))
    bubble_h=max(75,round(bubble_w*.43))
    cx=max(bubble_w//2+12,min(w-bubble_w//2-12,int(center[0])))
    cy=max(bubble_h//2+12,min(int(h*.26),int(center[1])))
    left=int(cx-bubble_w/2)
    top=int(cy-bubble_h/2)
    mask=Image.new('L',(w,h),0)
    painter=ImageDraw.Draw(mask)
    # Overlapping lobes union into a single silhouette; no interior outlines.
    lobes=[
        (.18,.51,.19),(.34,.30,.19),(.53,.27,.21),
        (.73,.34,.20),(.87,.55,.15),(.70,.70,.19),(.44,.75,.19),(.24,.70,.17)
    ]
    for px,py,radius in lobes:
        x=left+bubble_w*px;y=top+bubble_h*py
        rx=bubble_w*radius;ry=bubble_h*radius
        painter.ellipse((int(x-rx),int(y-ry),int(x+rx),int(y+ry)),fill=255)
    painter.ellipse((left+int(.12*bubble_w),top+int(.30*bubble_h),
                     left+int(.88*bubble_w),top+int(.80*bubble_h)),fill=255)
    tx=max(8,min(w-8,int(anchor[0])))
    ty=max(top+bubble_h+6,min(h-8,int(anchor[1])))
    painter.polygon([(cx-10,top+int(.72*bubble_h)),
                     (cx+12,top+int(.75*bubble_h)),(tx,ty)],fill=255)
    # Stroke only the outer edge of the cloud and its tail.
    border=mask.filter(ImageFilter.MaxFilter(9))
    d.bitmap((0,0),border,fill=ink)
    d.bitmap((0,0),mask,fill=(255,255,255))
    d.text((cx,cy),label,font=font,fill=ink,anchor='mm')


def render_story_background(size, scene_index, planet, biome, scene):
    """Planet owns its world bible; action controls each unique shot."""
    from backend.app.planet_art_direction import draw_background
    img,theme,world_type,world=draw_background(
        size,planet,biome,str(scene.get("world_inhabitants") or ""),
        scene,scene_index,
    )
    # The legacy palette interface is preserved for existing call sites.
    palette=(world["sky"],world["hill"],world["accent"],world_type)
    return img,theme,palette


def _expressive_sprite(sprite, character, emotion):
    """Subtle mouth and eyebrow variants over the approved facial design."""
    if emotion=='alegria':
        return sprite
    image=sprite.copy().convert('RGBA')
    w,h=image.size
    # Approximate mouth centers taken from the approved official silhouettes.
    anchors={'luna':(.715,.395),'tomi':(.615,.386),'pipo':(.455,.525)}
    cx,cy=anchors[character];x=round(w*cx);y=round(h*cy)
    rx=max(5,round(w*.095));ry=max(4,round(h*.056))
    d=ImageDraw.Draw(image)
    # Remove only the old mouth, preserving the rest of the face.
    d.ellipse((x-rx,y-ry,x+rx,y+ry),fill=(252,249,238,255))
    ink=(28,40,54,255)
    if emotion=='surpresa':
        d.ellipse((x-5,y-8,x+5,y+9),fill=(255,255,252,255),outline=ink,width=3)
        d.arc((x-27,y-27,x-9,y-16),180,350,fill=ink,width=2)
    elif emotion=='preocupacao':
        d.arc((x-9,y-1,x+9,y+13),195,350,fill=ink,width=3)
    elif emotion=='curiosidade':
        d.arc((x-9,y-4,x+9,y+4),5,160,fill=ink,width=3)
    else:
        d.arc((x-10,y-7,x+10,y+8),10,168,fill=ink,width=3)
    return image

def _color_approved_ink(sprite, name):
    """Flood-fill enclosed regions inside the authentic approved line art.

    It colors the interiors of inked shapes while retaining the original
    contour pixels. An outside flood-fill prevents painted rectangles.
    """
    from PIL import ImageDraw, ImageFilter, ImageOps
    rgba=sprite.convert('RGBA')
    w,h=rgba.size
    ink=rgba.getchannel('A').point(lambda value:255 if value>=80 else 0)
    ink=ink.filter(ImageFilter.MaxFilter(5))
    empty=ImageOps.invert(ink)
    # Clear every outside region touching the crop boundary. Starting only
    # at (0,0) is unsafe when that pixel happens to contain a stray ink line.
    border=[(x,0) for x in range(w)]+[(x,h-1) for x in range(w)]
    border += [(0,y) for y in range(h)]+[(w-1,y) for y in range(h)]
    for position in border:
        if empty.getpixel(position)==255:
            ImageDraw.floodfill(empty,position,128,thresh=0)
    inside=empty.point(lambda p:255 if p==255 else 0)
    fills={
        'luna':((255,224,201),(255,95,185)),
        'tomi':((255,221,198),(70,165,255)),
        'pipo':((248,251,255),(255,205,70)),
    }
    skin,costume=fills[name]
    underlay=Image.new('RGBA',(w,h),(0,0,0,0))
    d=ImageDraw.Draw(underlay)
    split=int(h*(.51 if name!='pipo' else .66))
    d.rectangle((0,0,w,split),fill=(*skin,255))
    d.rectangle((0,split,w,h),fill=(*costume,255))
    underlay.putalpha(inside)
    underlay.alpha_composite(rgba)
    return underlay

def draw_story_scene(base,scene_index,planet,biome,scene,sprites):
    w,h=base.size; im=base.convert('RGBA');d=ImageDraw.Draw(im)
    scene_text=' '.join(str(scene.get(k,'')) for k in ('title','caption','visual_action','action','spoken_excerpt'))
    emotion,word=emotions(scene_text)
    from backend.app.planet_art_direction import (
        profile_for, scene_theme, draw_resident,
    )
    theme=scene_theme(scene,scene_index)
    _,planet_style=profile_for(
        planet,biome,str(scene.get("world_inhabitants") or ""))
    # Native residents have a consistent species in this planet, but appear
    # only when the scene describes the people or local interaction.
    scene_text_lower=normal(scene_text)
    natives_requested=any(word in scene_text_lower for word in (
        "habitante","morador","amigo","pessoa","comunidade","receb",
        "ajud","todos","equipe","especialista","convers","cumpriment"
    ))
    if theme != "flight" and natives_requested and not scene.get("illustrated_native_residents"):
        for n in range(1 + scene_index%2):
            x=round(w*(.10+n*.15))
            draw_resident(d,x,round(h*.71),planet_style["species"],
                          planet_style,n,emotion)
    # Preserve original approved faces, costume contours and proportions.
    if theme=='nave':
        positions=[(.27,.82,.48),(.49,.82,.48),(.75,.84,.34)]
    elif scene_index%4==1:
        positions=[(.19,.86,.48),(.52,.84,.51),(.81,.85,.31)]
    elif scene_index%4==2:
        positions=[(.36,.85,.49),(.65,.85,.43),(.83,.84,.28)]
    elif scene_index%4==3:
        positions=[(.18,.87,.43),(.49,.84,.54),(.76,.85,.35)]
    else:
        positions=[(.25,.84,.50),(.53,.84,.49),(.76,.84,.36)]
    for idx,name in enumerate(('luna','tomi','pipo')):
        cx,ground,height_fraction=positions[idx]
        sprite=_expressive_sprite(sprites[name],name,emotion)
        target_height=max(80,int(h*height_fraction))
        target_width=max(50,int(sprite.width*target_height/max(sprite.height,1)))
        sprite=sprite.resize((target_width,target_height),Image.Resampling.LANCZOS)
        # Fill enclosed face/costume regions, never repaint the black ink.
        rgba=_color_approved_ink(sprite,name)
        if scene_index%5 in (1,3) and name!='pipo':
            rgba=ImageOps.mirror(rgba)
        x=int(w*cx-target_width/2);y=int(h*ground-target_height)
        # Soft contact shadow seats the sprite on the illustrated terrain.
        shadow=Image.new('RGBA',im.size,(0,0,0,0))
        shadow_draw=ImageDraw.Draw(shadow)
        base_y=y+target_height-4
        shadow_draw.ellipse((x+target_width*.12,base_y-13,
                             x+target_width*.88,base_y+18),fill=(21,43,63,95))
        shadow=shadow.filter(ImageFilter.GaussianBlur(9))
        im.alpha_composite(shadow)
        im.alpha_composite(rgba,(x,y))
    d=ImageDraw.Draw(im)
    speaker=scene.get('bubble_speaker') or ['luna','tomi','pipo'][scene_index%3]
    if speaker not in ('luna','tomi','pipo'):
        speaker='luna'
    box_x=int(w*positions[('luna','tomi','pipo').index(speaker)][0])
    _balloon(d,word,(box_x,max(60,int(h*.13))),(box_x,int(h*.27)),canvas_size=(w,h))
    image=im.convert('RGB')
    image=ImageEnhance.Color(image).enhance(1.24)
    image=ImageEnhance.Contrast(image).enhance(1.10)
    image=ImageEnhance.Brightness(image).enhance(1.02)
    image=ImageEnhance.Sharpness(image).enhance(1.06)
    return image,emotion,theme
