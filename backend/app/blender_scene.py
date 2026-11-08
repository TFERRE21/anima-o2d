"""Procedural 3D character and planet renderer for Blender 3.4+.

Creates original, low-poly/stylized 3D characters and 12 distinct scene stages.
No third-party character or franchise assets are used.
Run with: blender -b --python blender_scene.py -- --config /path/config.json
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

STAGE_GAP = 24.0


def report(percent: int, message: str) -> None:
    print(f"ANIMA_PROGRESS:{max(0, min(100, int(percent)))}:{message}", flush=True)


def material(name: str, color: tuple[float, float, float, float]):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = color
    return mat


M = {
    "skin": material("Skin warm peach", (0.93, 0.57, 0.39, 1)),
    "skin_light": material("Skin highlight", (1.0, 0.74, 0.57, 1)),
    "hair": material("Warm chestnut hair", (0.20, 0.085, 0.045, 1)),
    "hair_light": material("Chestnut highlight", (0.38, 0.16, 0.075, 1)),
    "pink": material("Luna magenta suit", (0.88, 0.055, 0.38, 1)),
    "pink_light": material("Luna pink trim", (1.0, 0.30, 0.65, 1)),
    "blue": material("Tomi blue suit", (0.055, 0.25, 0.67, 1)),
    "blue_light": material("Tomi blue trim", (0.24, 0.65, 0.95, 1)),
    "gold": material("Guardian gold", (1.0, 0.62, 0.055, 1)),
    "gold_light": material("Star cream", (1.0, 0.91, 0.57, 1)),
    "white": material("Eye whites", (1.0, 0.98, 0.91, 1)),
    "black": material("Deep pupils", (0.025, 0.035, 0.07, 1)),
    "mouth": material("Mouth", (0.16, 0.025, 0.055, 1)),
    "dog": material("Pipo caramel fur", (0.62, 0.29, 0.11, 1)),
    "dog_light": material("Pipo muzzle", (0.96, 0.72, 0.49, 1)),
    "dog_dark": material("Pipo ears", (0.34, 0.15, 0.075, 1)),
    "green": material("Alien mint", (0.23, 0.80, 0.62, 1)),
    "green_dark": material("Alien forest", (0.055, 0.35, 0.29, 1)),
    "sky": material("Planet night sky", (0.025, 0.065, 0.16, 1)),
    "stone": material("Stone blue", (0.12, 0.23, 0.34, 1)),
    "leaf": material("Planet foliage", (0.12, 0.48, 0.31, 1)),
    "leaf_light": material("Foliage highlight", (0.35, 0.76, 0.43, 1)),
    "ice": material("Ice crystal", (0.48, 0.88, 0.98, 1)),
    "sand": material("Desert sand", (0.76, 0.48, 0.25, 1)),
    "water": material("Ocean teal", (0.025, 0.45, 0.59, 1)),
    "wood": material("Warm wood", (0.35, 0.18, 0.09, 1)),
    "house": material("Village coral", (0.91, 0.36, 0.28, 1)),
    "window": material("Warm windows", (1.0, 0.78, 0.30, 1)),
    "metal": material("Soft silver", (0.47, 0.61, 0.69, 1)),
    "purple": material("Hologram purple", (0.42, 0.23, 0.82, 1)),
}


def set_parent(obj, parent, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0)):
    obj.parent = parent
    obj.location = loc
    obj.scale = scale
    obj.rotation_euler = rot
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    if parent:
        obj.parent = parent
    obj.location = loc
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.12
    return obj


def sphere(name, parent, loc, scale, mat, segments=20, rings=14):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    set_parent(obj, parent, loc, scale)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def cylinder(name, parent, loc, radius, depth, mat, rot=(0, 0, 0), vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    set_parent(obj, parent, loc, (1, 1, 1), rot)
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("Soft rounded edges", "BEVEL")
    bevel.width = min(radius * 0.22, 0.08)
    bevel.segments = 2
    obj.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")
    return obj


def cone(name, parent, loc, radius, depth, mat, rot=(0, 0, 0), vertices=12):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=0.0, depth=depth, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    set_parent(obj, parent, loc, (1, 1, 1), rot)
    obj.data.materials.append(mat)
    return obj


def cube(name, parent, loc, scale, mat, bevel=0.06, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    set_parent(obj, parent, loc, scale, rot)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Rounded edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def star_mesh(name, parent, x, y, z, radius, mat):
    verts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = radius if i % 2 == 0 else radius * 0.44
        verts.append((math.cos(a) * r, 0, z + math.sin(a) * r))
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(verts, [], [list(range(10))])
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.location = (x, y, 0)
    solid = obj.modifiers.new("Star thickness", "SOLIDIFY")
    solid.thickness = 0.055
    bevel = obj.modifiers.new("Star soft edge", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    return obj


def make_pivot(parent, name, loc):
    pivot = empty(name, loc, parent)
    return pivot


def human_character(name, kind, origin, size=1.0):
    root = empty(name + " root", origin)
    root.scale = (size, size, size)
    is_luna = kind == "Luna"
    suit = M["pink"] if is_luna else M["blue"]
    trim = M["pink_light"] if is_luna else M["blue_light"]
    # Rounded torso, collar, utility belt and badge.
    sphere(name + " torso", root, (0, 0, 1.28), (0.49, 0.34, 0.67), suit)
    sphere(name + " chest trim", root, (0, -0.29, 1.51), (0.34, 0.045, 0.38), trim, 16, 10)
    sphere(name + " chest panel", root, (0, -0.325, 1.48), (0.285, 0.035, 0.32), suit, 16, 10)
    cube(name + " belt", root, (0, -0.015, 0.82), (0.88, 0.69, 0.13), M["gold"], 0.045)
    sphere(name + " badge", root, (0, -0.374, 1.35), (0.23, 0.065, 0.23), M["gold"])
    star_mesh(name + " guardian star", root, 0, -0.434, 1.29, 0.18, M["gold_light"])
    # Neck and head pivot support eye, mouth and expressive look animation.
    cylinder(name + " neck", root, (0, 0, 1.91), 0.17, 0.25, M["skin"])
    head = make_pivot(root, name + " head pivot", (0, -0.025, 2.28))
    sphere(name + " head", head, (0, 0, 0), (0.62, 0.49, 0.66), M["skin"])
    sphere(name + " cheek left", head, (-0.34, -0.365, -0.13), (0.17, 0.10, 0.20), M["skin_light"])
    sphere(name + " cheek right", head, (0.34, -0.365, -0.13), (0.17, 0.10, 0.20), M["skin_light"])
    # Hair volume and character-specific silhouette.
    sphere(name + " hair cap", head, (0, 0.055, 0.43), (0.66, 0.50, 0.34), M["hair"])
    sphere(name + " hair side L", head, (-0.52, 0.015, -0.05), (0.16, 0.40, 0.48), M["hair"])
    sphere(name + " hair side R", head, (0.52, 0.015, -0.05), (0.16, 0.40, 0.48), M["hair"])
    if is_luna:
        sphere(name + " front fringe", head, (0, -0.36, 0.35), (0.50, 0.16, 0.19), M["hair_light"])
        # Pink inventor headband and golden side clip.
        bpy.ops.mesh.primitive_torus_add(major_segments=32, minor_segments=10, major_radius=0.43, minor_radius=0.065, location=(0, 0, 0))
        band = bpy.context.object
        band.name = name + " pink goggles band"
        set_parent(band, head, (0, -0.425, 0.36), (1.0, 0.45, 0.72), (math.radians(90), 0, 0))
        band.data.materials.append(M["pink_light"])
        sphere(name + " hair clip", head, (0.47, -0.43, 0.31), (0.12, 0.08, 0.12), M["gold"])
    else:
        # Distinct chunky swept spikes: a clear Tomi silhouette.
        for i, (xx, zz, angle) in enumerate([
            (-0.40, 0.45, -0.25), (-0.20, 0.60, -0.10), (0.04, 0.66, 0.0),
            (0.28, 0.57, 0.12), (0.47, 0.43, 0.28)
        ]):
            cone(name + " hair spike " + str(i), head, (xx, -0.01, zz), 0.18, 0.48, M["hair_light"], (0, angle, 0))
        cube(name + " wrist communicator", root, (0.45, -0.12, 1.58), (0.19, 0.15, 0.23), M["blue_light"], 0.045)
    # Eyes, pupils, brows and animated mouth, all facing the camera (-Y).
    for side, xx in (("L", -0.22), ("R", 0.22)):
        sphere(name + " eye white " + side, head, (xx, -0.442, 0.05), (0.115, 0.065, 0.17), M["white"])
        sphere(name + " pupil " + side, head, (xx, -0.501, 0.035), (0.054, 0.027, 0.105), M["black"])
        sphere(name + " eye sparkle " + side, head, (xx - 0.018, -0.527, 0.075), (0.023, 0.015, 0.035), M["white"], 12, 8)
        brow = sphere(name + " brow " + side, head, (xx, -0.438, 0.27), (0.14, 0.045, 0.035), M["hair_light"], 12, 8)
        brow.rotation_euler[1] = -0.08 if side == "L" else 0.08
    nose = sphere(name + " nose", head, (0, -0.505, -0.085), (0.055, 0.035, 0.04), M["skin_light"], 12, 8)
    mouth = sphere(name + " talking mouth", head, (0, -0.498, -0.22), (0.085, 0.035, 0.032), M["mouth"], 16, 10)
    # Articulated legs with boots.
    legs = []
    for side, xx in (("L", -0.22), ("R", 0.22)):
        pivot = make_pivot(root, name + " leg pivot " + side, (xx, 0, 0.79))
        sphere(name + " leg " + side, pivot, (0, 0, -0.32), (0.16, 0.18, 0.40), M["blue"] if not is_luna else M["pink"])
        sphere(name + " boot " + side, pivot, (0, -0.07, -0.64), (0.21, 0.29, 0.16), M["blue"] if not is_luna else M["hair"])
        legs.append(pivot)
    # Articulated arms with gloves.
    arms = []
    for side, xx in (("L", -0.47), ("R", 0.47)):
        pivot = make_pivot(root, name + " arm pivot " + side, (xx, 0, 1.69))
        sphere(name + " upper arm " + side, pivot, (0, 0, -0.29), (0.15, 0.17, 0.37), M["skin"])
        sphere(name + " glove " + side, pivot, (0, -0.02, -0.65), (0.16, 0.16, 0.16), M["gold"])
        arms.append(pivot)
    return {"root": root, "head": head, "mouth": mouth, "arms": arms, "legs": legs, "kind": kind, "base_x": origin[0], "base_z": origin[2]}


def dog_character(origin, size=0.82):
    root = empty("Pipo root", origin)
    root.scale = (size, size, size)
    sphere("Pipo body", root, (0, 0, 0.86), (0.48, 0.39, 0.51), M["dog"])
    sphere("Pipo chest", root, (0, -0.30, 0.78), (0.30, 0.10, 0.36), M["dog_light"])
    sphere("Pipo blue vest", root, (0, -0.10, 0.92), (0.45, 0.34, 0.27), M["blue"])
    sphere("Pipo vest badge", root, (0, -0.425, 0.96), (0.12, 0.035, 0.12), M["gold"])
    head = make_pivot(root, "Pipo head pivot", (0, -0.02, 1.48))
    sphere("Pipo head", head, (0, 0, 0), (0.51, 0.43, 0.52), M["dog"])
    sphere("Pipo muzzle", head, (0, -0.39, -0.17), (0.30, 0.16, 0.21), M["dog_light"])
    sphere("Pipo nose", head, (0, -0.54, -0.08), (0.095, 0.07, 0.07), M["black"])
    ears = []
    for side, xx in (("L", -0.43), ("R", 0.43)):
        ear = sphere("Pipo floppy ear " + side, head, (xx, 0.02, -0.05), (0.20, 0.25, 0.43), M["dog_dark"])
        ear.rotation_euler[1] = -0.25 if side == "L" else 0.25
        sphere("Pipo eye white " + side, head, (xx * 0.46, -0.39, 0.14), (0.09, 0.06, 0.13), M["white"])
        sphere("Pipo pupil " + side, head, (xx * 0.46, -0.445, 0.13), (0.042, 0.027, 0.082), M["black"])
        ears.append(ear)
    mouth = sphere("Pipo talking mouth", head, (0, -0.49, -0.30), (0.095, 0.035, 0.032), M["mouth"])
    legs = []
    for side, xx in (("L", -0.27), ("R", 0.27)):
        pivot = make_pivot(root, "Pipo leg pivot " + side, (xx, 0, 0.64))
        sphere("Pipo paw " + side, pivot, (0, -0.04, -0.28), (0.17, 0.20, 0.29), M["dog"])
        legs.append(pivot)
    tail = make_pivot(root, "Pipo wagging tail", (0.38, 0.15, 1.03))
    sphere("Pipo tail", tail, (0.22, 0, 0.05), (0.28, 0.14, 0.14), M["dog"])
    arms = []
    for side, xx in (("L", -0.35), ("R", 0.35)):
        pivot = make_pivot(root, "Pipo foreleg pivot " + side, (xx, 0, 1.02))
        sphere("Pipo foreleg " + side, pivot, (0, -0.02, -0.20), (0.13, 0.15, 0.27), M["dog"])
        arms.append(pivot)
    return {"root": root, "head": head, "mouth": mouth, "arms": arms, "legs": legs, "tail": tail, "kind": "Pipo", "base_x": origin[0], "base_z": origin[2]}


def alien_character(origin, variant=0):
    root = empty("Local friend root", origin)
    skin = M["green"] if variant == 0 else M["purple"]
    sphere("Local friend body", root, (0, 0, 0.82), (0.40, 0.32, 0.52), skin)
    head = make_pivot(root, "Local friend head", (0, -0.01, 1.52))
    sphere("Local friend head shape", head, (0, 0, 0), (0.48, 0.40, 0.48), skin)
    for side, xx in (("L", -0.17), ("R", 0.17)):
        sphere("Local friend eye " + side, head, (xx, -0.355, 0.06), (0.10, 0.06, 0.16), M["white"])
        sphere("Local friend pupil " + side, head, (xx, -0.405, 0.06), (0.04, 0.03, 0.09), M["black"])
        cone("Local friend antenna " + side, head, (xx * 1.6, 0, 0.52), 0.08, 0.30, skin)
    mouth = sphere("Local friend mouth", head, (0, -0.41, -0.17), (0.07, 0.03, 0.03), M["mouth"])
    return {"root": root, "head": head, "mouth": mouth, "arms": [], "legs": [], "kind": "Alien", "base_x": origin[0], "base_z": origin[2]}


def add_tree(cx, y, z, variant=0):
    trunk = cylinder("Alien tree trunk", None, (cx, y, z + 0.85), 0.16, 1.7, M["wood"])
    crown_mat = M["leaf"] if variant == 0 else M["leaf_light"]
    sphere("Alien tree crown", None, (cx, y, z + 2.0), (0.95, 0.75, 1.05), crown_mat)
    sphere("Tree crown highlight", None, (cx - 0.28, y - 0.58, z + 2.22), (0.35, 0.10, 0.35), M["leaf_light"])


def add_mission_object(center, y, mission, scene_index):
    obj = str(mission or "").lower()
    x = center + (2.8 if scene_index % 2 else -2.8)
    z = 0.75
    if any(k in obj for k in ("farol", "observ", "luz", "sinal")):
        cylinder("Mission beacon base", None, (x, y, z + 0.6), 0.24, 1.2, M["metal"])
        sphere("Mission beacon light", None, (x, y, z + 1.35), (0.39, 0.39, 0.39), M["gold"])
        cone("Mission beacon roof", None, (x, y, z + 1.78), 0.43, 0.45, M["house"])
    elif any(k in obj for k in ("semente", "jardim", "flor", "planta")):
        for j in range(5):
            xx = x + (j - 2) * 0.44
            cylinder("Flower stem", None, (xx, y, z + 0.65), 0.035, 1.3, M["leaf"])
            sphere("Planet flower", None, (xx, y, z + 1.35), (0.26, 0.26, 0.26), M["pink_light"])
            sphere("Flower center", None, (xx, y - 0.22, z + 1.35), (0.10, 0.08, 0.10), M["gold"])
    elif any(k in obj for k in ("ponte", "canal", "agua", "água")):
        cube("Community bridge", None, (x, y, z + 0.55), (3.6, 1.0, 0.20), M["wood"], 0.10)
        for j in range(6):
            cube("Bridge rail post", None, (x - 1.5 + j * 0.6, y, z + 0.92), (0.10, 0.12, 0.8), M["gold"], 0.04)
    elif any(k in obj for k in ("biblioteca", "livro")):
        cube("Library shelf", None, (x, y, z + 1.15), (2.3, 0.5, 2.3), M["wood"], 0.08)
        for j, bookmat in enumerate((M["pink"], M["blue"], M["gold"], M["leaf"], M["purple"])):
            cube("Story book", None, (x - 0.78 + j * 0.38, y - 0.31, z + 1.15), (0.27, 0.15, 1.1), bookmat, 0.025)
    elif any(k in obj for k in ("recicl", "caixa", "placa", "mensagem", "recado")):
        for j, mat in enumerate((M["leaf"], M["blue"], M["gold"])):
            cube("Community sorting station", None, (x + (j - 1) * 0.9, y, z + 0.65), (0.75, 0.7, 1.3), mat, 0.10)
            sphere("Sorting station indicator", None, (x + (j - 1) * 0.9, y - 0.39, z + 1.0), (0.11, 0.05, 0.11), M["white"])
    elif any(k in obj for k in ("coral", "concha", "musical")):
        sphere("Giant musical shell", None, (x, y, z + 1.0), (1.2, 0.7, 0.85), M["pink_light"])
        for j in range(5):
            cylinder("Shell rib", None, (x - 0.65 + j * 0.32, y - 0.66, z + 1.2), 0.045, 1.1, M["gold"], (0, math.pi / 2, 0))
    elif any(k in obj for k in ("rob", "ajudante")):
        cube("Friendly robot", None, (x, y, z + 1.15), (1.15, 0.7, 1.55), M["metal"], 0.20)
        for xx in (-0.25, 0.25):
            sphere("Robot eye", None, (x + xx, y - 0.40, z + 1.35), (0.11, 0.08, 0.14), M["blue_light"])
        sphere("Robot status light", None, (x, y - 0.42, z + 0.82), (0.13, 0.06, 0.07), M["gold"])
    else:
        cylinder("Mission artifact stand", None, (x, y, z + 0.45), 0.55, 0.9, M["metal"])
        sphere("Mission artifact", None, (x, y, z + 1.30), (0.6, 0.6, 0.7), M["purple"])
        sphere("Artifact glow", None, (x, y - 0.52, z + 1.4), (0.16, 0.08, 0.18), M["gold"])


def make_stage(stage_index, plan, scene, portrait):
    cx = stage_index * STAGE_GAP
    biome = str(plan.get("biome", "")).lower()
    mission = plan.get("mission_object", "")
    # Ground platform and a curved-looking backdrop.
    ground_mat = M["water"] if any(k in biome for k in ("oceano", "mar", "água", "agua")) else M["sand"] if any(k in biome for k in ("deserto", "areia", "vulc")) else M["ice"] if any(k in biome for k in ("gelo", "neve", "polar", "montanha")) else M["leaf"] if any(k in biome for k in ("floresta", "jardim", "flor")) else M["stone"]
    cube("Stage ground", None, (cx, 1.0, -0.35), (17, 16, 0.55), ground_mat, 0.3)
    cube("Stage backdrop", None, (cx, 5.2, 3.6), (18, 0.35, 11), M["sky"], 0.25)
    # Distant terrain silhouettes, using true 3D meshes with depth.
    for j in range(7):
        mx = cx - 8 + j * 2.6
        mat = M["ice"] if "gelo" in biome or "neve" in biome else M["sand"] if "deserto" in biome else M["stone"]
        cone("Distant mountain", None, (mx, 3.4, 1.2), 1.65 + (j % 3) * 0.3, 3.6 + (j % 2) * 1.1, mat, (0, (j % 2) * 0.17, 0), 7)
    # A distinct biome layer is visible in every shot.
    if any(k in biome for k in ("floresta", "jardim", "flor", "bosque")):
        for j in range(8):
            add_tree(cx - 7.0 + j * 2.0, 2.1 + (j % 2) * 0.5, 0, j % 2)
    elif any(k in biome for k in ("oceano", "mar", "água", "agua")):
        for j in range(8):
            xx = cx - 7 + j * 2
            cylinder("Ocean coral", None, (xx, 2.0, 0.7), 0.11, 1.4, M["pink_light"], (0.3, 0, (j % 2) * .2))
            for a in (-0.6, 0.6):
                cone("Coral branch", None, (xx + a, 2.0, 1.3), 0.22, 1.0, M["gold"], (0.0, 0.0, a))
    elif any(k in biome for k in ("nuvem", "ilha flutuante", "arco-íris", "arco-iris")):
        for j in range(6):
            sphere("Floating cloud island", None, (cx - 7 + j * 2.8, 3.1, 2.1 + (j % 2) * 1.1), (1.3, 0.65, 0.55), M["white"])
            cone("Island hanging rock", None, (cx - 7 + j * 2.8, 3.1, 1.45 + (j % 2) * 1.1), 0.65, 1.1, M["stone"])
    elif any(k in biome for k in ("gelo", "neve", "polar")):
        for j in range(8):
            xx = cx - 7 + j * 2
            cone("Ice spire", None, (xx, 2.3, 1.0), 0.58, 2.1 + (j % 3) * 0.5, M["ice"], (0, .12 * (j % 2), 0), 6)
    else:
        for j in range(9):
            sphere("Scattered planet boulder", None, (cx - 7 + j * 1.8, 2.4, 0.25), (0.55, 0.45, 0.36 + (j % 2) * .2), M["stone"], 12, 8)
    # Star points, rendered as small spheres rather than flat symbols.
    for j in range(24):
        xx = cx - 8 + ((j * 37) % 160) / 10
        zz = 4.0 + ((j * 19) % 55) / 10
        sphere("Distant star", None, (xx, 4.94, zz), (0.035, 0.035, 0.035), M["gold_light"], 8, 6)
    # Scene-specific set dressing.
    if stage_index in (2, 8, 10):
        for j in range(4):
            hx = cx - 6 + j * 4
            cube("Friendly village home", None, (hx, 2.0, 1.05), (1.65, 1.2, 2.1), M["house"], 0.16)
            cone("Village roof", None, (hx, 2.0, 2.45), 1.25, 1.1, M["pink_light"], (0, 0, 0), 4)
            cube("Village door", None, (hx, 1.36, 0.66), (0.42, 0.08, 0.95), M["wood"], 0.06)
            for wx in (-0.48, 0.48):
                cube("Village window", None, (hx + wx, 1.34, 1.45), (0.34, 0.08, 0.38), M["window"], 0.04)
    if stage_index in (3, 4, 6, 7, 9):
        add_mission_object(cx, 1.2, mission, stage_index)
    if stage_index == 0 or stage_index == 11:
        # Original small spaceship for arrival and departure shots.
        cone("Little starship nose", None, (cx, -1.5, 4.5), 0.85, 2.3, M["white"], (math.pi / 2, 0, 0), 12)
        sphere("Starship window", None, (cx, -2.0, 4.9), (0.32, 0.12, 0.32), M["blue_light"])
        for wing in (-1, 1):
            cone("Starship wing", None, (cx + wing * 0.95, -1.3, 4.0), 0.55, 1.7, M["pink"], (math.pi / 2, 0, wing * .22), 6)
    # One or two local residents join conversations on the village scenes.
    natives = []
    if stage_index in (2, 8, 10):
        natives.append(alien_character((cx + 5.1, -0.1, 0), 0))
        natives.append(alien_character((cx - 5.1, 0.7, 0), 1))
    # The same hero designs are rebuilt for each shot but retain fixed shape, colors and costumes.
    if portrait:
        positions = ((cx - 1.25, -1.0, 0), (cx + 1.25, -0.75, 0), (cx, -2.0, 0))
        size_h, size_d = 1.48, 1.05
    else:
        positions = ((cx - 3.1, -0.8, 0), (cx + 2.5, -0.55, 0), (cx + 0.2, -2.0, 0))
        size_h, size_d = 1.0, 0.78
    luna = human_character("Luna scene " + str(stage_index), "Luna", positions[0], size_h)
    tomi = human_character("Tomi scene " + str(stage_index), "Tomi", positions[1], size_h)
    pipo = dog_character(positions[2], size_d)
    return {"Luna": luna, "Tomi": tomi, "Pipo": pipo, "Natives": natives, "center": cx}


def animate_actor(actor, global_time, local_time, action, speaking=False, side=0):
    root = actor["root"]
    phase = local_time * 2.0 * math.pi * 1.25 + side * 1.7
    walk = action in {"walk", "explore", "work", "sniff"}
    if walk:
        root.location.x = actor["base_x"] + math.sin(local_time * math.pi * 2 + side) * 0.30 + (local_time - 0.5) * (0.58 if side == 0 else -0.42)
        root.location.z = actor["base_z"] + abs(math.sin(phase)) * 0.055
        swing = math.sin(phase) * 0.58
        actor["legs"][0].rotation_euler[1] = swing
        actor["legs"][1].rotation_euler[1] = -swing
        if actor["kind"] != "Pipo":
            actor["arms"][0].rotation_euler[1] = -swing * 0.78
            actor["arms"][1].rotation_euler[1] = swing * 0.78
        else:
            actor["arms"][0].rotation_euler[1] = -swing * 0.65
            actor["arms"][1].rotation_euler[1] = swing * 0.65
    else:
        actor["root"].location.x = actor["base_x"] + math.sin(local_time * 2.3 + side) * 0.08
        actor["root"].location.z = actor["base_z"] + abs(math.sin(global_time * 2.4 + side)) * 0.018
        actor["legs"][0].rotation_euler[1] = math.sin(global_time * 2.4 + side) * 0.035
        actor["legs"][1].rotation_euler[1] = -math.sin(global_time * 2.4 + side) * 0.035
    # Gesture language changes with each beat: investigate, explain, react, cooperate.
    if actor["kind"] == "Luna":
        if walk:
            actor["arms"][0].rotation_euler[1] = math.sin(phase) * 0.42
            actor["arms"][1].rotation_euler[1] = -math.sin(phase) * 0.42
        elif action in {"talk", "converse"}:
            actor["arms"][1].rotation_euler[1] = -0.45 + math.sin(global_time * 4.0) * 0.25
            actor["arms"][0].rotation_euler[1] = 0.18
        elif action == "discover":
            actor["arms"][1].rotation_euler[1] = -1.15 + math.sin(global_time * 4.5) * 0.12
        elif action == "surprise":
            actor["arms"][0].rotation_euler[1] = 0.95
            actor["arms"][1].rotation_euler[1] = -0.95
        elif action == "celebrate":
            actor["arms"][0].rotation_euler[1] = 2.1 + math.sin(global_time * 6) * 0.22
            actor["arms"][1].rotation_euler[1] = -2.1 - math.sin(global_time * 6) * 0.22
        else:
            actor["arms"][0].rotation_euler[1] = math.sin(global_time * 3) * 0.15
            actor["arms"][1].rotation_euler[1] = math.sin(global_time * 3 + 1) * 0.15
    elif actor["kind"] == "Tomi":
        if walk:
            actor["arms"][0].rotation_euler[1] = -math.sin(phase) * 0.42
            actor["arms"][1].rotation_euler[1] = math.sin(phase) * 0.42
        elif action in {"talk", "converse"}:
            actor["arms"][0].rotation_euler[1] = 0.5 + math.sin(global_time * 4.2) * 0.28
            actor["arms"][1].rotation_euler[1] = -0.25
        elif action in {"discover", "work"}:
            actor["arms"][0].rotation_euler[1] = 0.8
            actor["arms"][1].rotation_euler[1] = -0.55
        elif action == "surprise":
            actor["arms"][0].rotation_euler[1] = 0.95
            actor["arms"][1].rotation_euler[1] = -0.95
        elif action == "celebrate":
            actor["arms"][0].rotation_euler[1] = 2.0 + math.sin(global_time * 6) * 0.18
            actor["arms"][1].rotation_euler[1] = -2.0
        else:
            actor["arms"][0].rotation_euler[1] = math.sin(global_time * 3 + 1) * 0.16
            actor["arms"][1].rotation_euler[1] = math.sin(global_time * 3) * 0.16
    elif actor["kind"] == "Pipo":
        actor["head"].rotation_euler[1] = math.sin(global_time * 2.1) * (0.18 if action == "sniff" else 0.05)
        actor["tail"].rotation_euler[0] = math.sin(global_time * 11) * 0.75
        actor["arms"][0].rotation_euler[1] = math.sin(phase) * 0.25
        actor["arms"][1].rotation_euler[1] = -math.sin(phase) * 0.25
    else:
        actor["head"].rotation_euler[1] = math.sin(global_time * 2.2) * 0.12
    # Turn the two humans subtly toward one another when they are talking.
    if actor["kind"] == "Luna":
        actor["root"].rotation_euler[2] = 0.10 if action in {"talk", "converse"} else math.sin(global_time * .9) * .025
    elif actor["kind"] == "Tomi":
        actor["root"].rotation_euler[2] = -0.10 if action in {"talk", "converse"} else -math.sin(global_time * .9) * .025
    # Dialogue-driven mouth: each saved voice interval activates only its speaker.
    mouth = actor["mouth"]
    if speaking and math.sin(global_time * 18.0) > -0.25:
        mouth.scale.z = 0.125
    else:
        mouth.scale.z = 0.035


def create_camera(portrait, cx):
    data = bpy.data.cameras.new("Cinematic follow camera")
    camera = bpy.data.objects.new("Cinematic follow camera", data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.lens = 50
    data.ortho_scale = 7.6 if portrait else 14.2
    camera.location = (cx, -19.5, 5.5)
    target = Vector((cx, 0.4, 2.25))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def render(config: dict):
    portrait = config["format"] == "9:16"
    width, height = config["resolution"]
    fps = float(config["fps"])
    total_frames = int(config["total_frames"])
    scenes = config["scenes"]
    source_indices = config["scene_source_indices"]
    plan = config.get("story_plan", {})
    timeline = config.get("voice_timeline", [])
    out_dir = Path(config["frames_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = int(width)
    scene.render.resolution_y = int(height)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.background_type = "WORLD"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.25
    scene.display.shading.curvature_valley_factor = 1.15
    scene.display.shading.show_specular_highlight = True
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = max(1, min(4, os.cpu_count() or 2))
    scene.render.fps = 24
    scene.render.resolution_percentage = 100
    # Workbench is an actual 3D renderer with studio shading, cavity, silhouettes and depth.
    scene.world.color = (0.018, 0.04, 0.11)

    stage_models = []
    for i, shot in enumerate(scenes):
        source_index = int(source_indices[i])
        models = make_stage(source_index, plan, shot, portrait)
        models["source_index"] = source_index
        stage_models.append(models)

    camera = create_camera(portrait, 0)
    camera.data.ortho_scale = 6.8 if portrait else 14.2
    report(18, "Personagens 3D, cenário e câmera preparados.")

    # Scene cuts follow the actual storyboard; actors move and interact inside each shot.
    action_by_scene = {
        0: "walk", 1: "explore", 2: "converse", 3: "surprise",
        4: "discover", 5: "talk", 6: "sniff", 7: "surprise",
        8: "converse", 9: "work", 10: "celebrate", 11: "walk",
    }
    frame_duration = max(1.0, total_frames / max(1, len(scenes)))
    for frame in range(total_frames):
        scene_slot = min(len(scenes) - 1, int(frame / frame_duration))
        local_progress = (frame - scene_slot * frame_duration) / frame_duration
        local_progress = max(0.0, min(1.0, local_progress))
        global_time = frame / fps
        shot = stage_models[scene_slot]
        source_index = shot["source_index"]
        action = action_by_scene.get(source_index, "walk")
        # Camera follows the active set with a mild lateral drift and story beat zoom.
        center = shot["center"] + math.sin(local_progress * math.pi) * (0.32 if not portrait else 0.12)
        camera.location.x = center
        camera.location.z = 5.3 + math.sin(local_progress * math.pi) * 0.12
        close = source_index in (4, 7, 10)
        base_scale = 6.8 if portrait else 14.0
        camera.data.ortho_scale = base_scale * (0.88 if close else 1.0)
        target = Vector((center, 0.25, 2.25))
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()

        active = ""
        for line in timeline:
            if float(line.get("start", 0)) <= global_time < float(line.get("end", 0)):
                line_scene = int(line.get("scene", -1))
                if line_scene in (-1, source_index):
                    active = str(line.get("speaker", "Narrador"))
                    break
        for side, name in enumerate(("Luna", "Tomi", "Pipo")):
            actor = shot[name]
            animate_actor(actor, global_time, local_progress, action, active == name, side)
        for n, actor in enumerate(shot["Natives"]):
            animate_actor(actor, global_time, local_progress, "converse", active == "Moradora", n)

        scene.render.filepath = str(out_dir / f"frame-{frame + 1:06d}.png")
        scene.frame_set(1)
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        if frame % max(1, total_frames // 35) == 0 or frame == total_frames - 1:
            pct = 18 + int((frame + 1) / total_frames * 76)
            report(pct, f"Renderizando cena 3D {scene_slot + 1}/{len(scenes)} · quadro {frame + 1}/{total_frames}")

    report(96, "Render 3D concluído.")
    return {"frames": total_frames, "scene_count": len(scenes), "engine": "Blender Workbench 3D"}


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--version-check" in args:
        print("ANIMA_BLENDER_READY:" + bpy.app.version_string, flush=True)
        return
    if "--config" not in args:
        raise SystemExit("Uso: blender -b --python blender_scene.py -- --config config.json")
    path = Path(args[args.index("--config") + 1])
    config = json.loads(path.read_text(encoding="utf-8"))
    result = render(config)
    print("ANIMA_RENDER_RESULT:" + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
