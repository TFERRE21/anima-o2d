"""Image-first animated illustration scene for Blender 3.4+ (Cycles CPU).

The source of visual quality is the APPROVED PNG art. This renderer never
creates substitute geometric children, nor fetches unapproved images.

A single transparent character cutout supports parallax, camera, motion and
breathing. Full puppet articulation requires extra separated artwork/rigging.
"""
from __future__ import annotations
import json
import math
import os
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector


def progress(percent, message):
    print(f"ANIMA_PROGRESS:{percent}:{message}", flush=True)


def image_plane(name, image_path, width, height, x, y, z):
    path = Path(image_path).resolve()
    if not path.is_file() or path.suffix.lower() != ".png":
        raise RuntimeError("Arte PNG aprovada ausente: " + str(path))
    img = bpy.data.images.load(str(path), check_existing=True)
    # Flat card with real UV / transparent image texture.
    mesh = bpy.data.meshes.new(name + " plane")
    mesh.from_pydata(
        [(-width/2, y, -height/2), (width/2, y, -height/2),
         (width/2, y, height/2), (-width/2, y, height/2)],
        [], [(0, 1, 2, 3)]
    )
    mesh.update()
    uv = mesh.uv_layers.new()
    for loop, uvco in zip(mesh.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop.index].uv = uvco
    material = bpy.data.materials.new("Art / " + name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = img
    texture.interpolation = "Linear"
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    links = material.node_tree.links
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(texture.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    if hasattr(material, "blend_method"):
        material.blend_method = "BLEND"
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (x, 0, z)
    return obj


def render(config):
    asset = config.get("approved_art")
    if not asset or not asset.get("ready"):
        raise RuntimeError("O renderizador exige arte aprovada; não gera bonecos substitutos.")
    assets = asset.get("approved") or {}
    fmt = config["format"]
    width, height = (int(x) for x in config["resolution"])
    if fmt not in ("9:16", "16:9"):
        raise ValueError("Formato inválido")
    total_frames = int(config["total_frames"])
    fps = float(config["fps"])
    if not 1 <= total_frames <= 100_000 or not 0 < fps <= 30:
        raise ValueError("Frames/fps fora do limite.")
    output = Path(config["frames_dir"])
    output.mkdir(parents=True, exist_ok=True)
    for item in list(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    scene = bpy.context.scene
    # Cycles CPU renders image emission and transparency without initializing
    # the GPU/OpenGL viewport that crashed in the generic iContainer container.
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = max(1, min(4, int(os.getenv("ANIMA_ILLUSTRATION_SAMPLES", "1"))))
    scene.cycles.max_bounces = 1
    scene.cycles.transparent_max_bounces = 4
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = max(50, min(100, int(os.getenv("ANIMA_RENDER_SCALE", "75"))))
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 8
    scene.view_settings.view_transform = "Standard"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = max(1, min(os.cpu_count() or 2, int(os.getenv("ANIMA_BLENDER_THREADS", "4"))))
    # Orthographic stage. All artwork is plane-based; Blender drives the motion.
    cam_data = bpy.data.cameras.new("Storybook animation camera")
    camera = bpy.data.objects.new("Storybook animation camera", cam_data)
    bpy.context.collection.objects.link(camera)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 8.0
    camera.location = (0, -12, 0)
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    # Blender's orthographic scale is the view WIDTH in landscape and HEIGHT in
    # portrait. Choose the drawable rectangle for both aspect ratios.
    aspect = width / height
    stage_w, stage_h = (8 * aspect, 8) if aspect < 1 else (8, 8/aspect)
    bg_obj = {}
    chosen = config["scene_source_indices"]
    for source_idx in chosen:
        filename = assets.get(f"scene-{int(source_idx):02d}-background")
        if not filename:
            raise RuntimeError(f"Falta cenário aprovado da cena {source_idx}.")
        bg_obj[source_idx] = image_plane("Scene background " + str(source_idx), filename,
                                         stage_w * 1.04, stage_h * 1.04, 0, 2.0, 0)
    # Stable recurring character art. The same PNG identity is reused for
    # the whole episode, so the model cannot change their faces per shot.
    actors = {}
    positions = {"luna": -0.28, "tomi": 0.28, "pipo": 0.0}
    for idx, who in enumerate(("luna", "tomi", "pipo")):
        filename = assets.get(who)
        if not filename:
            raise RuntimeError(f"Falta personagem aprovado {who}.")
        # The PNG is loaded through bpy, so dimensions come from bpy.data.images.
        art = bpy.data.images.load(str(filename), check_existing=True)
        aw, ah = art.size
        drawn_h = stage_h * (0.46 if who != "pipo" else 0.28)
        drawn_w = drawn_h * aw / max(1, ah)
        base_x = stage_w * positions[who]
        # Pipo is slightly forward and stays in front of Luna and Tomi.
        base_z = -stage_h * 0.23 + drawn_h * 0.5
        if who == "pipo":
            base_z = -stage_h * 0.31 + drawn_h * 0.5
        obj = image_plane("Approved " + who, filename, drawn_w, drawn_h,
                          base_x, -0.2 if who == "pipo" else 0.0, base_z)
        actors[who] = {"object": obj, "base_x": base_x, "base_z": base_z}
    # Compose per storyboard beat and preserve the audio timestamps as actions.
    timeline = config.get("voice_timeline") or []
    schedule = []
    source_indices = [int(x) for x in chosen]
    if not source_indices:
        raise RuntimeError("O episódio não possui cenas.")
    duration = total_frames / fps
    step = duration / len(source_indices)
    for index, source_idx in enumerate(source_indices):
        intervals = [(float(x.get("start", 0)), float(x.get("end", 0)))
                     for x in timeline if int(x.get("scene", -1)) == source_idx]
        begin = min((v[0] for v in intervals), default=index * step)
        end = max((v[1] for v in intervals), default=(index+1) * step)
        schedule.append((source_idx, begin, end))
    # Monotonic scene boundaries even when the voice model gives odd timings.
    for frame in range(total_frames):
        t = frame / fps
        active = source_indices[min(int(t / step), len(source_indices) - 1)]
        speaker = next((str(v.get("speaker", "")) for v in timeline
                        if float(v.get("start", 0)) <= t < float(v.get("end", 0))), "")
        for idx, obj in bg_obj.items():
            obj.hide_render = idx != active
        for i, (name, actor) in enumerate(actors.items()):
            obj = actor["object"]
            phase = 2 * math.pi * (t * (0.65 + 0.04*i) + 0.28 * i)
            obj.location.x = actor["base_x"] + 0.055 * math.sin(phase)
            obj.location.z = actor["base_z"] + 0.038 * math.sin(phase * 1.5)
            obj.rotation_euler[1] = 0.014 * math.sin(phase)
            obj.scale = ((1.015 if speaker.lower() == name else 1.0),) * 3
        camera.location.x = 0.085 * math.sin(2 * math.pi * t / max(3, duration))
        scene.render.filepath = str(output / f"frame-{frame+1:06d}.png")
        bpy.ops.render.render(write_still=True)
        if frame == 0 or (frame + 1) % max(1, total_frames // 30) == 0 or frame+1 == total_frames:
            progress(18 + int(74 * (frame+1)/total_frames),
                     f"Animação de ilustrações aprovadas · quadro {frame+1}/{total_frames}")
    print("ANIMA_RENDER_RESULT:" + json.dumps({
        "frames": total_frames, "engine": "CYCLES_CPU_IMAGE_PLANES",
        "art_version": asset.get("art_version"), "source": "approved_art_only"
    }), flush=True)


def main():
    args = sys.argv
    args = args[args.index("--")+1:] if "--" in args else args[1:]
    if "--module" in args:
        args.remove("--module")
    config_path = Path(args[args.index("--config")+1])
    render(json.loads(config_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
