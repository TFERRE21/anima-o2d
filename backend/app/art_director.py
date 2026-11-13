"""Illustration-first Cartoon studio: an art bible and image-generation briefs.

Only describes and validates image assets. It does not pretend that an AI image
alone is a rigged 3D character, or that an image generation worker is connected.
Rendering/animation will use approved assets in a separate stage.
"""
from __future__ import annotations
import hashlib
import re

ART_PIPELINE_VERSION = "illustration-first-v1"
ART_STYLE = (
    "original professional children's cartoon series illustration, premium hand-painted "
    "storybook look, expressive recognizable faces, beautifully painted environmental "
    "depth, appealing soft character silhouettes, cohesive art direction, "
    "warm colorful palette, natural anatomy, detailed fabric, clean character acting"
)
NEGATIVE = (
    "plastic toy, bobblehead, spherical eyes protruding, primitive mesh, armor, "
    "3D doll, uncanny face, glossy materials, duplicated limbs, disfigured hands, "
    "text, logo, watermark, photorealism, blurred, low detail"
)
CAST = {
    "Luna": (
        "curious Brazilian girl child, medium warm brown complexion, long dark brown "
        "hair with softly side swept fringe and small pink bow, gentle brown eyes, "
        "rose-colored inventor jacket with embroidered golden star, practical child "
        "adventure clothing; confident curious smile"
    ),
    "Tomi": (
        "Brazilian boy child, warm medium brown complexion, short swept chestnut "
        "hair, warm brown eyes and subtle freckles, blue explorer jacket, "
        "small orange neck scarf, golden star emblem; thoughtful friendly expression"
    ),
    "Pipo": (
        "small natural four-legged caramel puppy, soft cream muzzle, "
        "floppy chocolate-brown ears, happy brown eyes, wagging tail, "
        "simple blue cloth vest and tiny golden star tag; unmistakably a dog"
    ),
}
POSES = ("neutral-front", "three-quarter", "walking", "talking", "happy", "surprised")


def _scene_name(index: int) -> str:
    return f"scene-{index:02d}"


def _safe_text(value: object, limit: int = 450) -> str:
    text = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
    return re.sub(r"\s{2,}", " ", text)[:limit]


def create_art_plan(story: dict, fmt: str = "9:16") -> dict:
    """One canonical character look and scene brief per storyboard beat."""
    if fmt not in ("9:16", "16:9"):
        raise ValueError("Formato de cena não suportado")
    aspect = "vertical 9:16 composition" if fmt == "9:16" else "wide 16:9 composition"
    base = _safe_text(story.get("planet", "Aurora-7"), 80)
    biome = _safe_text(story.get("biome", "fantasy garden"), 100)
    cast = []
    for name, identity in CAST.items():
        cast.append({
            "id": name.lower(), "name": name, "identity": identity,
            "reference_asset": f"cast/{name.lower()}/approved-reference.png",
            "layers_required": ["body", "head", "eyes", "mouth", "arms", "legs"],
            "poses_required": list(POSES),
            "prompt": (
                f"{ART_STYLE}; same recurring character in every scene: "
                f"{identity}; original production character reference sheet, "
                "full-body views, front and three-quarter, consistent costume and scale, "
                "bright flat reference background, no captions"
            ),
            "render_prompt": (
                f"{ART_STYLE}; one and only one original full-body character, {identity}; "
                "facing camera in neutral standing pose, all limbs visible, consistent design, "
                "clean clearly separated silhouette, no other people or viewpoints, "
                "uniform white RGB 255 255 255 backdrop in all four corners, "
                "no ground, no background shadows, no text"
            ),
            "negative_prompt": NEGATIVE,
        })
    scenes = []
    for index, scene in enumerate(story.get("scenes") or []):
        if not isinstance(scene, dict):
            continue
        title = _safe_text(scene.get("title"), 100)
        action = _safe_text(scene.get("visual_action") or scene.get("caption"), 450)
        scenes.append({
            "id": _scene_name(index),
            "index": index,
            "title": title,
            "action": action,
            "background_asset": f"scenes/{_scene_name(index)}/background.png",
            "foreground_asset": f"scenes/{_scene_name(index)}/foreground.png",
            "characters": [c["id"] for c in cast],
            "prompt": (
                f"{ART_STYLE}; magnificent layered background for a children's adventure, "
                f"{aspect}, world {base}, biome {biome}, scene {title}; {action}. "
                "Produce environment art WITHOUT characters and WITHOUT text, "
                "separable foreground and background, cinematic composition, "
                "visually distinct from all other scenes"
            ),
            "negative_prompt": NEGATIVE,
        })
    identity = hashlib.sha256(
        ("|".join(CAST.values()) + ART_STYLE).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "version": ART_PIPELINE_VERSION,
        "format": fmt,
        "style": ART_STYLE,
        "identity_lock": identity,
        "generation": "ComfyUI worker or other configured image generator",
        "status": "awaiting_approved_assets",
        "characters": cast,
        "scenes": scenes,
        "animation_requirements": (
            "Generate approved, separated layers for character limbs, faces and "
            "background; Blender can animate those layers with camera, rig, "
            "parallax and lip sync. A single flattened JPG is not enough for "
            "natural full-body acting."
        ),
        "quality_gate": (
            "No episode may advertise professional art without approved identity "
            "references, stable appearance across scenes, and working alpha masks."
        ),
    }
