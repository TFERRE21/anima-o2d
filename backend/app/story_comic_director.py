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
from PIL import Image, ImageDraw, ImageFont, ImageOps

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
    return ((176,208,247),(113,148,202),(245,203,124),'aurora')

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

def _balloon(d,text,center,anchor,wide=180):
    cx,cy=center;f=_font(23,True)
    text=str(text).upper()[:20]
    box=d.textbbox((0,0),text,font=f)
    width=min(wide,max(90,box[2]+35));height=46
    x=max(15,int(cx-width/2));y=max(12,int(cy-height/2))
    d.rounded_rectangle((x,y,x+width,y+height),radius=20,fill=(255,255,255),outline=(37,49,72),width=4)
    d.polygon([(int(cx),y+height-2),(int(cx)+14,y+height+16),(int(anchor[0]),int(anchor[1]))],fill=(255,255,255))
    d.line([(int(cx),y+height),(int(anchor[0]),int(anchor[1]))],fill=(37,49,72),width=2)
    d.text((x+width/2,y+height/2-1),text,font=f,fill=(37,49,72),anchor='mm')

def render_story_background(size,scene_index,planet,biome,scene):
    w,h=size
    theme=_scene_theme(scene_index,scene)
    palette=_world_palette(planet,biome)
    light,dark,accent,variant=palette
    rng=random.Random(seed_for(planet,scene_index,theme,str(scene.get('visual_action',''))))
    im=Image.new('RGB',(w,h),light);d=ImageDraw.Draw(im)
    ink=(37,54,76)
    # Composition changes per scene, with distinct terrain silhouettes.
    horizon=int(h*(.53+.05*(scene_index%4)))
    d.rectangle((0,0,w,horizon),fill=tuple(min(255,c+35) for c in light))
    for i in range(3):
        xx=int((i+.7)*w/3+rng.randrange(-90,90))
        yy=int(h*(.12+.08*(i%2)))
        d.ellipse((xx-65,yy-25,xx+70,yy+20),fill=(255,255,251),outline=ink,width=3)
    if theme=='nave':
        d.rounded_rectangle((80,150,w-80,h-80),radius=110,fill=(230,239,250),outline=ink,width=12)
        d.ellipse((150,190,w-150,h+170),fill=dark,outline=ink,width=7)
        d.ellipse((260,220,w-260,h+100),fill=light,outline=ink,width=4)
        d.line((140,h-85,w-140,h-85),fill=ink,width=14)
    elif theme in ('vila','praca','mercado','biblioteca','oficina'):
        for n in range(3):
            bx=40+n*420+rng.randrange(-35,35)
            by=horizon-rng.randint(140,240)
            d.rounded_rectangle((bx,by,bx+295,horizon+65),radius=34,fill=accent if n%2 else dark,outline=ink,width=7)
            d.ellipse((bx+96,by+25,bx+195,by+125),fill=(250,244,208),outline=ink,width=5)
            if theme=='biblioteca':
                for j in range(7):
                    d.rectangle((bx+20+j*33,by+145,bx+38+j*33,by+212),fill=(85+15*j,120,155),outline=ink,width=2)
            if theme=='oficina':
                d.ellipse((bx+120,by+140,bx+177,by+197),outline=ink,width=6)
    elif theme=='investigacao':
        for n in range(5):
            x=140+n*220+rng.randrange(-40,40)
            d.ellipse((x,horizon+25,x+55,horizon+50),fill=accent,outline=ink,width=3)
            d.line((x+20,horizon+30,x+35,horizon+45),fill=ink,width=4)
        d.rounded_rectangle((w-300,90,w-120,230),radius=15,fill=(255,247,217),outline=ink,width=6)
        d.line((w-265,125,w-155,125),fill=ink,width=4)
        d.line((w-265,160,w-195,160),fill=ink,width=4)
    elif theme=='jardim':
        for n in range(9):
            x=70+n*140+rng.randrange(-25,25); y=horizon+rng.randrange(-30,40)
            d.line((x,y+70,x,y-85),fill=dark,width=12)
            for angle in range(0,360,60):
                xx=x+55*math.cos(math.radians(angle))
                yy=y-85+55*math.sin(math.radians(angle))
                d.ellipse((xx-40,yy-40,xx+40,yy+40),fill=accent,outline=ink,width=3)
            d.ellipse((x-27,y-112,x+27,y-58),fill=(255,231,118),outline=ink,width=4)
    elif theme=='mar':
        d.rectangle((0,horizon,w,h),fill=dark)
        for n in range(3):
            d.arc((-60,horizon+n*75,w+100,horizon+130+n*75),0,180,fill=(247,253,253),width=8)
        for n in range(7):
            x=rng.randrange(50,w-50);y=rng.randrange(horizon+35,h-30)
            d.ellipse((x,y,x+23,y+23),outline=(243,249,250),width=3)
    else:
        for n in range(5):
            x=n*290-90+rng.randrange(-65,65);y=horizon+rng.randrange(-45,45)
            d.ellipse((x-180,y-120,x+220,y+160),fill=dark if n%2 else accent,outline=ink,width=5)
        if theme=='ponte':
            d.arc((100,130,w-100,h+250),180,360,fill=(252,248,221),width=50)
    # Different foreground props and visual accents every scene.
    for n in range(7):
        x=rng.randrange(20,w-20);y=rng.randrange(int(h*.83),h-15)
        d.ellipse((x-14,y-9,x+14,y+9),fill=accent,outline=ink,width=2)
    if scene_index%2:
        d.rounded_rectangle((20,h-65,245,h-15),radius=15,fill=(255,255,255),outline=ink,width=3)
        d.text((133,h-40),f'CENA {scene_index+1}',font=_font(20),fill=ink,anchor='mm')
    return im,theme,palette

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

def draw_story_scene(base,scene_index,planet,biome,scene,sprites):
    w,h=base.size; im=base.convert('RGBA');d=ImageDraw.Draw(im)
    scene_text=' '.join(str(scene.get(k,'')) for k in ('title','caption','visual_action','action'))
    emotion,word=emotions(scene_text)
    palette=_world_palette(planet,biome)
    theme=_scene_theme(scene_index,scene)
    # Inhabitants vary by planet but persist across scenes on the same planet.
    _,_,_,variant=palette
    if theme in ('vila','praca','mercado','festa','oficina','jardim','investigacao'):
        for n in range(2+(scene_index%2)):
            x=110+n*240+(scene_index%3)*15
            _alien(d,x,int(h*.70),32+n*5,variant,palette,emotion)
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
        # Color blocks under the approved black line art, preserving silhouettes.
        color={'luna':(247,135,190),'tomi':(98,178,243),'pipo':(252,211,102)}[name]
        rgba=Image.new('RGBA',sprite.size,(*color,0))
        rgba.putalpha(sprite.getchannel('A').point(lambda alpha: 32 if alpha>50 else 0))
        rgba.alpha_composite(sprite)
        if scene_index%5 in (1,3) and name!='pipo':
            rgba=ImageOps.mirror(rgba)
        x=int(w*cx-target_width/2);y=int(h*ground-target_height)
        im.alpha_composite(rgba,(x,y))
    d=ImageDraw.Draw(im)
    speaker=['luna','tomi','pipo'][scene_index%3]
    box_x=int(w*positions[scene_index%3][0])
    _balloon(d,word,(box_x,max(34,int(h*.10))),(box_x,int(h*.19)))
    return im.convert('RGB'),emotion,theme
