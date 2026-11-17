"""Deterministic planet art bible for the 2D comic renderer.

The planet owns geography, vegetation, architecture and indigenous species.
The scene owns action, camera and visible props. The same planet retains a
recognisable identity while consecutive scenes have different compositions.
All artwork is local Pillow drawing; no GPU or upload is necessary.
"""
from __future__ import annotations

import hashlib
import math
import random
import unicodedata
from PIL import Image, ImageDraw

INK=(45,49,77)

def clean(text):
    return ''.join(ch for ch in unicodedata.normalize("NFKD",str(text)).lower()
                   if not unicodedata.combining(ch))

def seed(*values):
    return int.from_bytes(hashlib.sha256(
        "|".join(str(v) for v in values).encode()).digest()[:8],"big")

PROFILES={
    "crystal": {"words":("aurora","cristal","lumin"),
        "sky":(122,157,237),"ground":(93,183,159),"hill":(85,125,175),
        "accent":(255,205,122),"flora":"crystal","home":"crystal","species":"lumin"},
    "canyon":{"words":("vermelhao","canion","deserto","rochins"),
        "sky":(171,151,221),"ground":(236,156,108),"hill":(175,101,117),
        "accent":(250,204,126),"flora":"succulent","home":"dome","species":"rochin"},
    "ocean":{"words":("oceania","oceano","neris","marinho"),
        "sky":(110,198,226),"ground":(105,198,198),"hill":(67,137,190),
        "accent":(255,225,154),"flora":"coral","home":"shell","species":"neri"},
    "garden":{"words":("flora","petala","florins","jardim","flor"),
        "sky":(158,201,237),"ground":(117,193,127),"hill":(93,159,127),
        "accent":(251,166,204),"flora":"flower","home":"leaf","species":"florin"},
    "cloud":{"words":("nuvem","nuvins","planador"),
        "sky":(149,188,239),"ground":(184,171,223),"hill":(156,153,206),
        "accent":(249,216,155),"flora":"fluffy","home":"floating","species":"nuvin"},
    "ice":{"words":("gelus","glacis","gelo","glacial"),
        "sky":(145,207,237),"ground":(180,227,239),"hill":(109,159,202),
        "accent":(254,241,199),"flora":"ice","home":"igloo","species":"glaci"},
    "volcano":{"words":("vulcania","vulcan","termic"),
        "sky":(184,163,208),"ground":(189,148,130),"hill":(127,109,135),
        "accent":(246,181,112),"flora":"fern","home":"stone","species":"vulcan"},
    "sapphire":{"words":("safira","safirins","anel"),
        "sky":(145,157,233),"ground":(151,167,204),"hill":(89,104,177),
        "accent":(255,218,143),"flora":"crystal","home":"tower","species":"safirin"},
    "moon":{"words":("eco-lua","lunar","memorias","ecos"),
        "sky":(127,157,190),"ground":(186,190,211),"hill":(131,143,173),
        "accent":(255,231,177),"flora":"moon","home":"dome","species":"eco"},
}
def profile_for(planet,biome="",inhabitants=""):
    text=clean(planet+" "+biome+" "+inhabitants)
    # planet name takes precedence over general 'flowers' etc in descriptions
    planet_text=clean(planet)
    for key,profile in PROFILES.items():
        if any(word in planet_text for word in profile["words"]):
            return key,profile
    for key,profile in PROFILES.items():
        if any(word in text for word in profile["words"]):
            return key,profile
    keys=tuple(PROFILES)
    key=keys[seed(planet)%len(keys)]
    return key,PROFILES[key]

THEMES={
    "flight":("nave","partida","decolar","espaco","cinto","viagem de volta","pousar"),
    "river":("rio","fonte","cachoeira","canal","agua","lago","concha"),
    "bridge":("ponte","travessia","passagem","atravessar"),
    "forest":("floresta","arvore","bosque","trilha","vegetacao","mata"),
    "garden":("semente","flor","jardim","planta","cultivar"),
    "town":("morador","habitante","amigo","vila","comunidade","receb","casas"),
    "workshop":("equipamento","consert","tecnico","maquina","sistema","ligacao","painel"),
    "library":("biblioteca","livro","diario","anotacoes","caderno"),
    "clue":("pista","pegada","investig","indicio","descob","observ"),
    "celebration":("comemor","consegu","agrade","festa","sorrir"),
    "lookout":("paisagem","janela","observatorio","horizonte","montanha"),
}
def scene_theme(scene, scene_index):
    text=clean(" ".join(str(scene.get(key,"")) for key in (
        "title","caption","visual_action","spoken_excerpt","action")))
    # Distinct actions take precedence over generic descriptions of inhabitants.
    for name in ("river","bridge","forest","garden","workshop","library","clue","celebration","flight","town","lookout"):
        if any(term in text for term in THEMES[name]):
            return name
    return ("lookout","forest","town","river","clue","workshop")[scene_index%6]

def _cloud(d,x,y,s,colour):
    ink=(224,224,248)
    d.ellipse((x-s*.85,y-s*.12,x-s*.13,y+s*.4),fill=colour)
    d.ellipse((x-s*.35,y-s*.52,x+s*.33,y+s*.36),fill=colour)
    d.ellipse((x+s*.12,y-s*.23,x+s*.90,y+s*.4),fill=colour)
    d.arc((x-s*.86,y-s*.55,x+s*.9,y+s*.42),6,168,fill=ink,width=2)

def _vegetation(d,x,y,scale,style,p,rng):
    s=scale;dark=p["hill"];accent=p["accent"]
    if style=="crystal":
        for offset in (-.65,0,.67):
            px=x+offset*s
            d.polygon([(px-s*.22,y),(px-s*.27,y-s*.92),
                       (px,y-s*(1.45+offset*.15)),(px+s*.27,y-s*.86),
                       (px+s*.24,y)],fill=accent if offset else (134,238,222),
                      outline=INK,width=3)
    elif style in ("coral","ice"):
        for i in range(3):
            px=x+(i-1)*s*.5
            d.line((px,y,px+(i-1)*s*.13,y-s*1.2),fill=dark,width=max(3,int(s*.14)))
            d.ellipse((px-s*.2,y-s*1.65,px+s*.3,y-s*1.1),fill=accent,outline=INK,width=2)
    elif style in ("succulent","fern"):
        d.line((x,y,x,y-s*1.16),fill=dark,width=max(4,int(s*.17)))
        for i in (-1,1):
            d.ellipse((x+i*s*.12,y-s*.9,x+i*s*.8,y-s*.37),
                      fill=(120,164,106) if style=="succulent" else (108,186,133),
                      outline=INK,width=3)
        d.ellipse((x-s*.27,y-s*1.4,x+s*.27,y-s*.95),fill=(102,169,117),outline=INK,width=3)
    elif style=="flower":
        d.line((x,y,x,y-s),fill=(72,139,102),width=max(3,int(s*.1)))
        for a in range(0,360,60):
            angle=math.radians(a)
            px=x+math.cos(angle)*s*.39
            py=y-s+math.sin(angle)*s*.39
            d.ellipse((px-s*.25,py-s*.25,px+s*.25,py+s*.25),
                      fill=accent,outline=INK,width=2)
        d.ellipse((x-s*.2,y-s*1.2,x+s*.2,y-s*.8),fill=(255,231,126),outline=INK,width=2)
    elif style=="fluffy":
        for i in (-1,0,1):
            d.ellipse((x+i*s*.45-s*.42,y-s*1.2,x+i*s*.45+s*.42,y-s*.45),
                      fill=(234,231,252),outline=INK,width=2)
    else:
        d.line((x,y,x,y-s*.8),fill=dark,width=max(4,int(s*.13)))
        for i in (-1,1):
            d.ellipse((x+i*s*.12,y-s*1.1,x+i*s*.65,y-s*.55),
                      fill=accent,outline=INK,width=2)

def _house(d,x,ground,s,style,p,variant):
    sky=p["sky"];accent=p["accent"]
    body=(251,225,203) if style not in ("igloo","tower") else (215,239,252)
    left=int(x-s*.6);right=int(x+s*.6)
    top=int(ground-s*1.05);bottom=int(ground)
    if style in ("dome","igloo","shell","floating"):
        d.ellipse((left,top-s*.35,right,bottom+s*.3),
                  fill=body,outline=INK,width=4)
        d.rectangle((left,top+s*.55,right,bottom+s*.3),fill=p["ground"])
        d.arc((left,top-s*.35,right,bottom+s*.3),185,355,fill=INK,width=4)
    elif style=="crystal":
        d.polygon([(left,bottom),(left,top+s*.3),(x,top-s*.4),
                   (right,top+s*.3),(right,bottom)],fill=body,outline=INK,width=4)
    elif style=="leaf":
        d.ellipse((left,top-s*.2,right,bottom+s*.1),fill=body,outline=INK,width=4)
        d.ellipse((left-s*.35,top-s*.5,right+s*.35,top+s*.15),
                  fill=(113,186,123),outline=INK,width=4)
    else:
        d.rounded_rectangle((left,top,right,bottom),radius=22,fill=body,outline=INK,width=4)
        d.polygon([(left-s*.15,top+s*.1),(x,top-s*.42),
                   (right+s*.15,top+s*.1)],fill=accent,outline=INK,width=3)
    # The door and windows change arrangement with the individual building.
    door_x=x+(variant%3-1)*s*.12
    d.rounded_rectangle((door_x-s*.15,ground-s*.38,door_x+s*.15,ground),
                        radius=12,fill=(153,94,104),outline=INK,width=3)
    for sign in (-1,1):
        px=x+sign*s*.33
        d.ellipse((px-s*.10,top+s*.37,px+s*.10,top+s*.58),
                  fill=(255,232,141),outline=INK,width=2)

def _terrain(d,w,h,profile,rng,scene_index,theme):
    hill=profile["hill"];ground=profile["ground"]
    for layer in range(3):
        baseline=int(h*(.44+layer*.12))
        pts=[(-50,h)]
        for j in range(9):
            x=int(j*w/8)
            y=baseline+int(math.sin(j*1.6+scene_index*.9+layer)*26)+rng.randint(-22,22)
            pts.append((x,y))
        pts.extend([(w+50,h),(-50,h)])
        color=hill if layer==0 else ground if layer==2 else tuple(
            min(255,int((a+b)/2)+10) for a,b in zip(ground,hill))
        d.polygon(pts,fill=color)
    if theme in ("river","bridge"):
        y=int(h*.59)
        river=[(int(w*.45),y),(int(w*.70),y+70),(int(w*.62),h),
               (int(w*.22),h),(int(w*.38),y+75)]
        d.polygon(river,fill=(77,179,222),outline=INK,width=4)
        for n in range(6):
            x=int(w*(.30+n*.075));yy=int(y+55+(n%3)*20)
            d.arc((x,yy,x+90,yy+22),0,155,fill=(232,249,255),width=3)
        if theme=="bridge":
            d.arc((int(w*.25),y-90,int(w*.78),y+125),180,360,fill=(133,99,119),width=16)
            d.arc((int(w*.25),y-92,int(w*.78),y+115),180,360,fill=(255,226,163),width=8)
    if theme=="flight":
        d.ellipse((-int(w*.2),int(h*.72),int(w*1.2),int(h*1.5)),
                  fill=(82,122,189),outline=(250,250,255),width=8)
        d.arc((-int(w*.17),int(h*.78),int(w*1.17),int(h*1.45)),
              183,355,fill=(234,243,251),width=8)

def draw_background(size,planet,biome,inhabitants,scene,scene_index):
    """Return scene-appropriate image + semantic environment metadata."""
    w,h=size
    key,p=profile_for(planet,biome,inhabitants)
    theme=scene_theme(scene,scene_index)
    rng=random.Random(seed(planet,scene_index,scene.get("visual_action",""),theme))
    image=Image.new("RGB",(w,h),p["sky"])
    d=ImageDraw.Draw(image)
    # Colored sky gradient rather than repeated white ellipses.
    sky=p["sky"]
    for y in range(int(h*.48)):
        blend=y/(h*.48)
        col=tuple(min(255,int(c*(1-blend)+(c+35)*blend)) for c in sky)
        d.line((0,y,w,y),fill=col)
    for i in range(3+(scene_index%2)):
        cx=rng.randint(35,w-35);cy=rng.randint(44,int(h*.31))
        _cloud(d,cx,cy,rng.randint(28,64),(255,245,241))
    d.ellipse((int(w*.76),int(h*.075),int(w*.89),int(h*.26)),
              fill=p["accent"],outline=(251,242,214),width=4)
    _terrain(d,w,h,p,rng,scene_index,theme)
    # Distant geography shares the same planet identity, not the same staging.
    if key in ("canyon","volcano","ice"):
        for i in range(3):
            x=int(w*(i*.38-.1)) + rng.randrange(-45,45)
            y=int(h*.53)
            d.polygon([(x-150,y+30),(x-40,y-110-rng.randint(0,85)),
                       (x+70,y-50),(x+170,y+30)],
                      fill=p["hill"],outline=INK,width=3)
    if theme in ("town","workshop","library","celebration","lookout"):
        count=2+(scene_index%2)
        for i in range(count):
            x=int(w*(.15+i*(.68/max(1,count-1))))
            _house(d,x,int(h*.59),rng.randint(80,120),p["home"],p,i+scene_index)
    if theme=="workshop":
        x=int(w*.80);y=int(h*.60)
        d.ellipse((x-46,y-93,x+46,y-1),fill=p["accent"],outline=INK,width=5)
        d.line((x,y-80,x,y-14),fill=INK,width=8)
    if theme=="library":
        for i in range(2):
            x=int(w*(.65+i*.14));yy=int(h*.61)
            d.polygon([(x,yy-60),(x+40,yy-60),(x+40,yy)],fill=p["accent"],outline=INK,width=3)
    if theme=="clue":
        for i in range(5):
            x=rng.randint(int(w*.14),int(w*.84));y=rng.randint(int(h*.7),int(h*.84))
            d.ellipse((x-13,y-8,x+13,y+8),outline=INK,width=3)
            d.ellipse((x+5,y-15,x+13,y-7),fill=p["accent"],outline=INK,width=2)
    vegetation_count=4 if theme=="flight" else 11 if theme in ("forest","garden") else 7
    for i in range(vegetation_count):
        x=rng.randint(10,w-10)
        ground=int(h*(.66+rng.random()*.17))
        _vegetation(d,x,ground,rng.randint(15,43),p["flora"],p,rng)
    # Foreground flora varies in every image, with no boxes behind cast.
    for i in range(8):
        x=rng.randint(0,w);y=rng.randint(int(h*.89),h-8)
        d.ellipse((x-10,y-5,x+10,y+5),fill=p["accent"],outline=INK,width=1)
    return image,theme,key,p

def draw_resident(d,x,y,species,profile,individual,emotion):
    """Distinct planet-native silhouette: no square blocks or generic mascots."""
    r=random.Random(seed(species,individual))
    size=34+individual*5;ink=INK
    skin=profile["accent"]
    robe=(247,224,203) if individual%2 else profile["sky"]
    def ellipse(a,b,c,e,fill,width=3):
        d.ellipse((a,b,c,e),fill=fill,outline=ink,width=width)
    x=int(x);y=int(y)
    # Flowing rounded body and feet; characters sit on the ground.
    ellipse(x-size*.48,y-size*.65,x+size*.48,y+size*.60,robe)
    for dx in (-.29,.29):
        ellipse(x+dx*size-size*.16,y+size*.40,
                x+dx*size+size*.16,y+size*.79,robe,2)
    if species in ("lumin","safirin"):
        d.polygon([(x-size*.9,y-size*.45),(x-size*.55,y-size*1.6),
                   (x,y-size*1.97),(x+size*.55,y-size*1.6),
                   (x+size*.9,y-size*.45)],fill=skin,outline=ink,width=4)
    elif species=="rochin":
        ellipse(x-size*.84,y-size*1.80,x+size*.84,y-size*.35,skin,4)
        for dx in (-.5,.5):
            ellipse(x+dx*size-size*.18,y-size*1.87,
                    x+dx*size+size*.18,y-size*1.59,profile["hill"],2)
    elif species=="neri":
        d.polygon([(x-size*.75,y-size*.65),(x-size*.96,y-size*1.0),
                   (x-size*.70,y-size*1.28),(x-size*.93,y-size*1.63),
                   (x,y-size*1.96),(x+size*.93,y-size*1.63),
                   (x+size*.70,y-size*1.28),(x+size*.96,y-size*1.0),
                   (x+size*.75,y-size*.65)],fill=skin,outline=ink,width=4)
    elif species=="florin":
        for k in range(6):
            angle=k*math.pi/3
            px=x+size*.55*math.cos(angle)
            py=y-size*1.25+size*.55*math.sin(angle)
            ellipse(px-size*.28,py-size*.28,px+size*.28,py+size*.28,skin,2)
        ellipse(x-size*.70,y-size*1.93,x+size*.70,y-size*.55,robe,4)
    elif species=="glaci":
        d.polygon([(x,y-size*2),(x-size*.83,y-size*.9),
                   (x-size*.54,y-size*.4),(x+size*.54,y-size*.4),
                   (x+size*.83,y-size*.9)],fill=skin,outline=ink,width=4)
    elif species=="nuvin":
        for px,py in [(-.45,-1.2),(0,-1.65),(.45,-1.15)]:
            ellipse(x+size*(px-.38),y+size*(py-.40),
                    x+size*(px+.38),y+size*(py+.40),skin,3)
    else:
        ellipse(x-size*.72,y-size*1.85,x+size*.72,y-size*.46,skin,4)
        for dx in (-.45,.45):
            d.line((x+dx*size,y-size*1.53,
                    x+dx*size*1.22,y-size*2),fill=ink,width=3)
    # Friendly eyes and face, with emotions shared with story.
    for dx in (-.27,.27):
        ellipse(x+size*dx-size*.12,y-size*1.30,
                x+size*dx+size*.12,y-size*1.12,(29,45,72),1)
    if emotion=="surpresa":
        ellipse(x-size*.09,y-size*1.04,x+size*.09,y-size*.82,(77,48,73),2)
    else:
        d.arc((x-size*.26,y-size*1.17,x+size*.26,y-size*.80),
              10,170,fill=ink,width=3)
    # Tiny accessory tied to the planet's local culture.
    d.ellipse((x-size*.13,y-size*.36,x+size*.13,y-size*.10),
              fill=profile["hill"],outline=ink,width=2)
