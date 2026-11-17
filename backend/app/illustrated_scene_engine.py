"""High-quality illustrated planetary backgrounds using the Images API.

The chatbot image tool used in this chat does not run inside the VPS. This
adapter uses an explicitly configured image API key instead. Luna, Tomi and
Pipo are composited from the project's own fixed sprites after generation.
No manual upload and no per-scene approval are needed.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
from pathlib import Path

import httpx
from PIL import Image, ImageEnhance, ImageOps

from backend.app.planet_art_direction import profile_for, scene_theme

ART_VERSION = "illustrated-worlds-cloudflare-v10"
SUPPORTED = {"gpt-image-2.5-flare", "gpt-image-2.5-sunburst",
             "gpt-image-2", "gpt-image-1.5", "gpt-image-1-mini"}

def provider() -> str:
    explicit=os.getenv("ANIMA_SCENE_IMAGE_PROVIDER", "").strip().lower()
    if explicit in {"cloudflare","openai"}:
        return explicit
    # Prefer the Cloudflare free-tier connector when credentials exist.
    if (os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
            and os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()):
        return "cloudflare"
    return "openai"

def selected_model() -> str:
    if provider()=="cloudflare":
        return os.getenv("CLOUDFLARE_AI_MODEL",
                         "@cf/black-forest-labs/flux-1-schnell").strip()
    return os.getenv("ANIMA_SCENE_IMAGE_MODEL","gpt-image-2.5-flare").strip()

def cache_tag() -> str:
    model=selected_model()
    quality=(os.getenv("CLOUDFLARE_AI_STEPS","4") if provider()=="cloudflare"
             else os.getenv("ANIMA_SCENE_IMAGE_QUALITY","medium"))
    return hashlib.sha256((ART_VERSION+"|"+provider()+"|"+model+"|"+quality
                           ).encode()).hexdigest()[:12]

def _cloudflare_call(prompt: str, scene_index: int, planet: str) -> bytes:
    account=os.getenv("CLOUDFLARE_ACCOUNT_ID","").strip()
    token=os.getenv("CLOUDFLARE_API_TOKEN","").strip()
    if not account or not token:
        raise RuntimeError("Configure CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN.")
    if not all(c.isalnum() or c in "-_" for c in account):
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID inválido.")
    model=selected_model()
    if model!="@cf/black-forest-labs/flux-1-schnell":
        raise RuntimeError("Modelo Cloudflare não suportado: "+model)
    steps=int(os.getenv("CLOUDFLARE_AI_STEPS","4"))
    if not 1 <= steps <= 8:
        raise RuntimeError("CLOUDFLARE_AI_STEPS deve estar entre 1 e 8.")
    url=("https://api.cloudflare.com/client/v4/accounts/"+account+
         "/ai/run/"+model)
    # The FLUX model accepts up to 2048 prompt characters.
    # Place the specific scene/planet context at the start.
    body={"prompt":prompt[:2048],"steps":steps,
          "seed":int(hashlib.sha256((planet+"|"+str(scene_index)).encode()
                       ).hexdigest()[:8],16)}
    with httpx.Client(timeout=httpx.Timeout(180,connect=15)) as client:
        response=client.post(url,json=body,headers={
            "Authorization":"Bearer "+token,
            "Content-Type":"application/json"})
    response.raise_for_status()
    result=response.json()
    if not result.get("success",False):
        raise RuntimeError("Cloudflare rejeitou a geração da imagem: "+
                           str(result.get("errors",[]))[:240])
    value=result.get("result") or {}
    encoded=value.get("image") if isinstance(value,dict) else None
    if not encoded:
        raise RuntimeError("Cloudflare retornou resposta sem imagem.")
    return base64.b64decode(encoded,validate=True)


def enabled() -> bool:
    # A dedicated key opts in. A generic OpenAI key may already serve another
    # subsystem; never start billable image jobs with it without explicit opt-in.
    if provider()=="cloudflare":
        return bool(os.getenv("CLOUDFLARE_API_TOKEN","").strip()
                    and os.getenv("CLOUDFLARE_ACCOUNT_ID","").strip())
    dedicated = bool(os.getenv("ANIMA_SCENE_IMAGE_API_KEY", "").strip())
    generic_opt_in = (os.getenv("ANIMA_SCENE_IMAGE_ENABLED", "0") == "1"
                      and bool(os.getenv("OPENAI_API_KEY", "").strip()))
    return dedicated or generic_opt_in

def required() -> bool:
    return os.getenv("ANIMA_REQUIRE_ILLUSTRATED_SCENES", "0") == "1"

def _key() -> str:
    if os.getenv("ANIMA_SCENE_IMAGE_API_KEY", "").strip():
        return os.getenv("ANIMA_SCENE_IMAGE_API_KEY", "").strip()
    if os.getenv("ANIMA_SCENE_IMAGE_ENABLED", "0") == "1":
        return os.getenv("OPENAI_API_KEY", "").strip()
    return ""

def scene_prompt(plan: dict, scene: dict, index: int) -> str:
    planet = str(plan.get("planet") or "Planeta desconhecido")
    biome = str(plan.get("biome") or "")
    natives = str(plan.get("inhabitants") or "")
    key, profile = profile_for(planet, biome, natives)
    theme = scene_theme(scene, index)
    world = {
        "crystal": "lush luminous crystal forest, sparkling giant crystalline trees, bioluminescent ferns, fantasy architecture with transparent crystal roofs",
        "canyon": "warm red sandstone canyons, beautiful rounded adobe and mushroom-like homes, terracotta village paths, succulents, colorful native desert flowers",
        "ocean": "underwater coral forests, glass dome cities, glowing shell houses, turquoise waterways, coral gardens and sea plants",
        "garden": "giant blossoms, leafy tree houses, ornate blooming gardens, emerald hills, winding paths and vivid floral architecture",
        "cloud": "floating pastel islands, airy cloud villages, rainbow bridges, soft drifting gardens and sky balloons",
        "ice": "blue ice mountains, glowing aurora skies, exquisite ice cottages, crystalline snow plants and frozen rivers",
        "volcano": "colorful safe volcanic plateau, orange rock landscapes, unusual heat-resistant plants, warm glowing stone homes",
        "sapphire": "sapphire towers and luminous orbital settlement, sweeping rings in the sky, alien mineral gardens",
        "moon": "serene moonlit valleys, silver lakes, luminous memory lanterns, curious moon flora and warm little observatories",
    }.get(key, "magical alien world with coherent geography, buildings and flora")
    shot = {
        "flight": "spaceship arrival or departure, breathtaking exterior view across the destination landscape; NO rectangular cockpit or giant box frame",
        "river": "detailed winding river, vivid flowing water, stepping stones, waterfalls when relevant",
        "bridge": "beautiful safe bridge and two distinct shores or settlements",
        "forest": "lush forest paths, varied treetops, leaves, bushes and distant depth",
        "garden": "close view of exotic flowers and cultivated beds, natural winding paths",
        "town": "detailed welcoming village with inviting houses, windows, doors, plazas and paths",
        "workshop": "village repair area with tools and the story's equipment, charming architecture",
        "library": "story library filled with books, carved shelves, memorable local architecture",
        "clue": "exploration site with visible clues, details and props specific to the story",
        "celebration": "festive town square with garlands, families and joyful setting",
        "lookout": "wide panoramic view of the landscape and famous local landmark",
    }.get(theme, "rich scenic composition with visible details")
    action = str(scene.get("visual_action") or scene.get("action") or "")
    narration = str(scene.get("spoken_excerpt") or scene.get("caption") or "")
    landmark = str(plan.get("landmark") or "")
    mission = str(plan.get("mission_object") or "")
    inhabitants = str(plan.get("inhabitants") or "")
    return (
        "Create ONE exquisitely rendered 2D children's comic background, an "
        "original educational fantasy space adventure storybook illustration. "
        "Visual quality: detailed premium full-color storybook illustration, "
        "crisp hand-inked shapes, soft sophisticated painterly shading, layered "
        "foreground/middle/distance depth, charming architecture, lively plants, "
        "cinematic sunlight, harmonious vibrant colors, lovingly designed small details. "
        "Avoid bland vector clip art, simple circles, rectangles, flat gradients, "
        "plain colored hills, tiny repeating dots and primitive geometric props. "
        "Environment identity must stay CONSISTENT across this planet's episode. "
        f"PLANET: {planet}. BIOME: {biome}. VISUAL BIBLE: {world}. "
        f"LANDMARK: {landmark}. NATIVE CULTURE: {inhabitants}. "
        f"SCENE {index+1}: {scene.get('title','')}. SHOT: {shot}. "
        f"STORY ACTION: {action}. NARRATION: {narration[:650]}. "
        f"IMPORTANT STORY PROP: {mission}. "
        "The environment and visual objects must explicitly illustrate the action "
        "in the narration, not a generic background. Every scene must have a "
        "distinct camera angle and specific composition. "
        "Add one or two very cute original native alien inhabitants ONLY if the "
        "story scene calls for them; their appearance should embody this planet's "
        "biome and remain consistent within the planet. "
        "Keep CENTRAL AND LOWER-CENTRAL foreground mostly clear so the production "
        "engine can overlay three existing recurring protagonists. "
        "Do NOT draw Luna, Tomi, Pipo, astronauts, protagonist children or their robot. "
        "Do NOT draw speech balloons, words, lettering, captions, panels, frames, "
        "watermarks, any TV or rectangular border around characters. "
        "One seamless landscape illustration occupying the full canvas."
    )

def _cached(scene_dir: Path, signature: str) -> Image.Image | None:
    path = scene_dir / "background.png"
    meta = scene_dir / "manifest.json"
    if not path.is_file() or not meta.is_file():
        return None
    try:
        state = json.loads(meta.read_text("utf8"))
        if state.get("signature") != signature:
            return None
        with Image.open(path) as original:
            original.load()
            return original.convert("RGB")
    except (OSError, ValueError, json.JSONDecodeError):
        return None

def illustrated_background(plan: dict, scene: dict, index: int,
                           workdir: Path, output_size=(1280,720)) -> Image.Image | None:
    """Generate/cache only a background. Return None if no API was configured.

    Provider failures are raised, never silently replaced with basic shapes.
    """
    if not enabled():
        if required():
            raise RuntimeError(
                "Ilustrações avançadas precisam da chave ANIMA_SCENE_IMAGE_API_KEY "
                "ou ANIMA_SCENE_IMAGE_ENABLED=1 com OPENAI_API_KEY na VPS. Nunca no GitHub."
            )
        return None
    engine=provider()
    model=selected_model()
    quality=(os.getenv("CLOUDFLARE_AI_STEPS","4") if engine=="cloudflare"
             else os.getenv("ANIMA_SCENE_IMAGE_QUALITY","medium").strip())
    if engine=="openai":
        if model not in SUPPORTED:
            raise RuntimeError("Modelo de imagens não permitido: "+model)
        if quality not in ("low","medium","high","auto","xhigh","max"):
            raise RuntimeError("Qualidade inválida para imagens.")
        if quality in ("xhigh","max") and not model.startswith("gpt-image-2.5"):
            raise RuntimeError("Qualidade xhigh/max exige modelo compatível.")
    prompt = scene_prompt(plan,scene,index)
    signature = hashlib.sha256(
        (ART_VERSION+"|"+engine+"|"+model+"|"+quality+"|"+prompt).encode("utf8")).hexdigest()
    scene_dir = workdir / "illustrated-backgrounds-v9" / ("scene-%02d" % index)
    cached = _cached(scene_dir, signature)
    if cached is not None:
        return ImageOps.fit(cached,output_size,Image.Resampling.LANCZOS)
    scene_dir.mkdir(parents=True,exist_ok=True)
    endpoint = os.getenv("ANIMA_SCENE_IMAGE_ENDPOINT",
                         "https://api.openai.com/v1/images/generations")
    if engine=="openai" and not endpoint.startswith("https://"):
        raise RuntimeError("A API de imagens deve usar HTTPS.")
    request = {
        "model":model, "prompt":prompt, "size":"1536x1024",
        "quality":quality, "output_format":"png",
        "n":1,
    }
    headers={"Authorization":"Bearer "+_key(),"Content-Type":"application/json"}
    last=None
    for attempt in range(3):
        try:
            if engine=="cloudflare":
                blob=_cloudflare_call(prompt,index,str(plan.get("planet") or ""))
            else:
                with httpx.Client(timeout=httpx.Timeout(240,connect=20)) as client:
                    response = client.post(endpoint,json=request,headers=headers)
                response.raise_for_status()
                item=(response.json().get("data") or [{}])[0]
                encoded=item.get("b64_json")
                if not encoded:
                    raise RuntimeError("Serviço de imagens retornou resposta sem PNG.")
                blob=base64.b64decode(encoded,validate=True)
            with Image.open(io.BytesIO(blob)) as image:
                image.load()
                artwork=image.convert("RGB")
            if artwork.width < 640 or artwork.height < 480:
                raise RuntimeError("Ilustração gerada em resolução insuficiente.")
            temporary=scene_dir / "background.partial.png"
            artwork.save(temporary,format="PNG")
            os.replace(temporary,scene_dir / "background.png")
            manifest=scene_dir / "manifest.partial.json"
            manifest.write_text(json.dumps({
                "signature":signature,"model":model,"provider":engine,"quality":quality,
                "planet":plan.get("planet"),"scene_index":index,
                "image_size":list(artwork.size)
            },ensure_ascii=False),encoding="utf8")
            os.replace(manifest,scene_dir / "manifest.json")
            return ImageOps.fit(artwork,output_size,Image.Resampling.LANCZOS)
        except (httpx.HTTPError,ValueError,OSError,RuntimeError) as exc:
            last=exc
            if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code in (
                400,401,403,404,422):
                break
            if attempt < 2:
                time.sleep(2*(attempt+1))
    raise RuntimeError(
        "Falha ao gerar ilustração da cena "+str(index+1)+" em "+str(plan.get("planet"))+
        ": "+str(last)[:180]
    )
