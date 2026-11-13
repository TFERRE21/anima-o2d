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
import time
from pathlib import Path

# Make the canonical character bible importable inside Blender background mode.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from mathutils import Vector

# Shared character bible is optional for older local RX580 checkouts; the scene
# remains backward-compatible until the Windows worker syncs the repository.
try:
    from character_profiles import CHARACTER_PROFILES
except Exception:
    CHARACTER_PROFILES = {}


STAGE_GAP = 24.0


def report(percent: int, message: str) -> None:
    print(f"ANIMA_PROGRESS:{max(0, min(100, int(percent)))}:{message}", flush=True)


def material(name: str, color: tuple[float, float, float, float]):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.62
        if "Metallic" in principled.inputs:
            principled.inputs["Metallic"].default_value = 0.02
    return mat


print("ANIMA_BOOT: iniciando criação dos materiais 3D", flush=True)

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
print("ANIMA_BOOT: materiais 3D carregados", flush=True)


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


# Version 2 uses fully redesigned Storybook Cartoon humans and puppy.
# No code path can instantiate the deprecated armored toy/bobblehead models.
from cartoon_art_v2 import ART_VERSION, build_human, build_dog, dress_stage


def human_character(name, kind, origin, size=1.0):
    return build_human(name, kind, origin, size, globals(), CHARACTER_PROFILES)


def dog_character(origin, size=0.92):
    return build_dog(origin, size, globals(), CHARACTER_PROFILES)


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


def add_landmark(cx, y, landmark):
    name = str(landmark or "").lower()
    x = cx + 5.4
    if any(k in name for k in ("gruta", "caverna", "caverna", "montanha")):
        cube("Landmark cave pillar L", None, (x - 1.15, y, 1.25), (0.55, 1.0, 2.5), M["stone"], 0.18)
        cube("Landmark cave pillar R", None, (x + 1.15, y, 1.25), (0.55, 1.0, 2.5), M["stone"], 0.18)
        sphere("Landmark cave arch", None, (x, y, 2.25), (1.65, 0.8, 1.1), M["ice"])
        cube("Cave entrance shadow", None, (x, y - 0.56, 1.0), (1.35, 0.12, 1.9), M["sky"], 0.28)
    elif any(k in name for k in ("farol", "observat")):
        cylinder("Landmark lighthouse tower", None, (x, y, 1.5), 0.42, 3.0, M["metal"])
        sphere("Landmark lighthouse lantern", None, (x, y - 0.02, 3.25), (0.65, 0.58, 0.55), M["gold"])
        cone("Landmark lighthouse roof", None, (x, y, 3.75), 0.72, 0.6, M["house"])
    elif any(k in name for k in ("estação", "estacao", "lua", "anel")):
        sphere("Landmark space station core", None, (x, y, 2.15), (1.0, 0.8, 0.9), M["metal"])
        bpy.ops.mesh.primitive_torus_add(major_segments=48, minor_segments=10, major_radius=1.75, minor_radius=0.10, location=(x, y, 2.15))
        ring = bpy.context.object
        ring.name = "Landmark orbital ring"
        ring.data.materials.append(M["gold"])
        sphere("Station observation window", None, (x, y - 0.76, 2.2), (0.34, 0.08, 0.28), M["blue_light"])
        for xx in (-1.6, 1.6):
            cube("Station solar panel", None, (x + xx, y, 2.2), (0.85, 0.12, 0.55), M["blue"])
    elif any(k in name for k in ("campo", "pétala", "petala", "flor")):
        for j in range(3):
            xx = x + (j - 1) * 1.05
            cylinder("Landmark flower stalk", None, (xx, y, 1.1), 0.08, 2.2, M["leaf"])
            sphere("Landmark giant blossom", None, (xx, y, 2.4), (0.62, 0.50, 0.62), M["pink_light"])
            sphere("Landmark flower heart", None, (xx, y - 0.45, 2.4), (0.22, 0.10, 0.22), M["gold"])
    elif "ponte" in name:
        cube("Landmark bridge deck", None, (x, y, 0.95), (4.6, 1.1, 0.25), M["gold"])
        for xx in (-1.9, -0.95, 0, 0.95, 1.9):
            cylinder("Landmark bridge support", None, (x + xx, y + 0.1, 1.65), 0.11, 1.4, M["metal"])
        cube("Landmark bridge arch", None, (x, y + 0.25, 2.6), (4.0, 0.18, 0.18), M["ice"])
    else:
        cylinder("Landmark monument", None, (x, y, 1.55), 0.5, 3.1, M["metal"])
        cone("Landmark monument crown", None, (x, y, 3.5), 0.8, 0.9, M["gold"])
        sphere("Landmark monument beacon", None, (x, y - 0.52, 2.8), (0.18, 0.08, 0.18), M["blue_light"])


def make_stage(stage_index, plan, scene, portrait):
    cx = stage_index * STAGE_GAP
    biome = str(plan.get("biome", "")).lower()
    mission = plan.get("mission_object", "")
    # The entire former night-wall / low-poly planet set is retired.
    # Each shot now receives an original pastel, daylit Storybook 3D environment.
    dress_stage(cx, biome, globals())
    # Scene-specific set dressing.
    if stage_index in (1, 2, 8, 10, 11):
        add_landmark(cx, 2.7, plan.get("landmark", ""))
    if stage_index in (2, 8, 10):
        for j in range(4):
            hx = cx - 6 + j * 4
            cube("Friendly village home", None, (hx, 2.0, 1.05), (1.65, 1.2, 2.1), M["house"], 0.16)
            cone("Village roof", None, (hx, 2.0, 2.45), 1.25, 1.1, M["pink_light"], (0, 0, 0), 4)
            cube("Village door", None, (hx, 1.36, 0.66), (0.42, 0.08, 0.95), M["wood"], 0.06)
            for wx in (-0.48, 0.48):
                cube("Village window", None, (hx + wx, 1.34, 1.45), (0.34, 0.08, 0.38), M["window"], 0.04)
    if stage_index == 3:
        add_mission_object(cx, 1.2, mission, stage_index)
    elif stage_index == 4:
        # Close-up investigation: a 3D magnifying glass and a luminous clue.
        bpy.ops.mesh.primitive_torus_add(major_segments=40, minor_segments=12, major_radius=0.55, minor_radius=0.10, location=(cx - 3.3, -0.65, 1.8))
        lens = bpy.context.object
        lens.name = "Luna magnifying glass lens"
        lens.rotation_euler[0] = math.radians(90)
        lens.data.materials.append(M["blue_light"])
        cylinder("Magnifier handle", None, (cx - 2.65, -0.58, 1.12), 0.10, 1.15, M["wood"], (0, -0.65, 0))
        sphere("Clue crystal", None, (cx + 2.7, 0.15, 1.1), (0.40, 0.34, 0.42), M["gold"])
        sphere("Clue sparkle", None, (cx + 2.55, -0.22, 1.55), (0.10, 0.08, 0.10), M["white"])
    elif stage_index == 5:
        # Tomi's plan: a raised holographic map with connected waypoints.
        cube("Tomi hologram map base", None, (cx, 0.9, 0.75), (3.9, 1.4, 0.18), M["metal"], 0.08)
        cube("Tomi hologram screen", None, (cx, 0.25, 1.65), (3.2, 0.10, 1.4), M["purple"], 0.05)
        for j in range(4):
            sphere("Hologram waypoint", None, (cx - 1.05 + j * 0.70, 0.12, 1.68 + math.sin(j) * 0.35), (0.14, 0.09, 0.14), M["gold_light"])
    elif stage_index == 6:
        # Pipo's discovery: a trail of paw prints leads toward the hidden clue.
        for j in range(7):
            px = cx - 3.0 + j * 0.72
            pz = 0.10 + (j % 2) * 0.025
            sphere("Pipo paw print", None, (px, -0.35, pz), (0.16, 0.08, 0.10), M["dog_light"])
            for toe in (-0.15, 0, 0.15):
                sphere("Pipo toe print", None, (px + toe, -0.42, pz + 0.12), (0.065, 0.05, 0.06), M["dog_light"], 10, 8)
        sphere("Hidden clue glow", None, (cx + 3.5, 0.4, 1.25), (0.30, 0.3, 0.30), M["gold"])
    elif stage_index == 7:
        # The twist is a cinematic reveal, not a repeated copy of the mission prop.
        for j in range(4):
            bpy.ops.mesh.primitive_torus_add(major_segments=40, minor_segments=8, major_radius=0.7 + j * 0.34, minor_radius=0.045, location=(cx, 1.9, 2.0))
            ring = bpy.context.object
            ring.name = "Surprise energy ring"
            ring.data.materials.append(M["purple"] if j % 2 else M["blue_light"])
        sphere("Surprise energy core", None, (cx, 1.8, 2.0), (0.48, 0.48, 0.48), M["gold"])
    elif stage_index == 12:
        # A holographic mission journal makes the narrated reflection visible.
        cube("Mission journal tablet", None, (cx, -0.7, 1.25), (2.4, 0.18, 1.55), M["purple"], 0.12)
        for j in range(3):
            sphere("Mission journal memory icon", None, (cx - 0.62 + j * 0.62, -0.83, 1.45), (0.17, 0.06, 0.17), (M["gold"], M["pink_light"], M["blue_light"])[j])
        for j in range(4):
            cube("Mission journal writing line", None, (cx, -0.84, 1.08 - j * 0.16), (1.25 - j * 0.10, 0.025, 0.025), M["white"], 0.01)
    elif stage_index == 14:
        # The final call-to-action has a warm, stage-like welcoming set.
        cylinder("Finale stage", None, (cx, 1.5, 0.05), 4.5, 0.18, M["gold"], vertices=48)
        for j in range(7):
            xx = cx - 3.0 + j
            sphere("Finale floating star", None, (xx, 2.5, 3.6 + (j % 2) * 0.45), (0.12, 0.12, 0.12), M["gold_light"], 12, 8)
    elif stage_index == 9:
        # Worksite props make the teamwork scene visibly different from discovery.
        add_mission_object(cx, 1.2, mission, stage_index)
        for j in range(4):
            xx = cx - 3.3 + j * 2.2
            cylinder("Teamwork tool stand", None, (xx, 1.5, 0.72), 0.10, 1.3, M["metal"])
            cube("Teamwork work light", None, (xx, 1.35, 1.50), (0.45, 0.20, 0.22), M["gold"], 0.06)
    ship_root = None
    if stage_index in (0, 2, 11, 13):
        # A reusable 3D shuttle is visible at take-off, landing and return.
        ship_root = empty("Estrelinha shuttle stage " + str(stage_index), (cx, -1.5, 0))
        cone("Little starship nose", ship_root, (0, 0, 4.5), 0.85, 2.3, M["white"], (math.pi / 2, 0, 0), 12)
        sphere("Starship window", ship_root, (0, -0.5, 4.9), (0.32, 0.12, 0.32), M["blue_light"])
        for wing in (-1, 1):
            cone("Starship wing", ship_root, (wing * 0.95, 0.2, 4.0), 0.55, 1.7, M["pink"], (math.pi / 2, 0, wing * .22), 6)
        for flame_index in range(3):
            cone("Starship engine flame", ship_root, ((flame_index - 1) * 0.20, 0.5, 3.25), 0.13, 0.65, M["gold"], (0, 0, 0), 8)
    # One or two local residents join conversations on the village scenes.
    natives = []
    if stage_index in (2, 8, 10):
        resident_offset = 2.6 if portrait else 5.1
        natives.append(alien_character((cx + resident_offset, -0.1, 0), 0))
        natives.append(alien_character((cx - resident_offset, 0.7, 0), 1))
    # Every scene uses the NEW Storybook v2 characters, not the deprecated toy cast.
    if portrait:
        positions = ((cx - 1.25, -1.0, 0), (cx + 1.25, -0.75, 0), (cx, -2.0, 0))
        size_h, size_d = 1.24, 0.88
    else:
        positions = ((cx - 3.1, -0.8, 0), (cx + 2.5, -0.55, 0), (cx + 0.2, -2.0, 0))
        size_h, size_d = 1.05, 0.80
    luna = human_character("Luna scene " + str(stage_index), "Luna", positions[0], size_h)
    tomi = human_character("Tomi scene " + str(stage_index), "Tomi", positions[1], size_h)
    pipo = dog_character(positions[2], size_d)
    return {"Luna": luna, "Tomi": tomi, "Pipo": pipo, "Natives": natives, "center": cx, "ship": ship_root}


def animate_actor(actor, global_time, local_time, action, speaking=False, side=0):
    root = actor["root"]
    phase = global_time * 6.4 + side * math.pi
    walk = action in {"walk", "explore", "work", "sniff"}
    if walk:
        root.location.x = actor["base_x"] + math.sin(local_time * math.pi * 2 + side) * 0.30 + (local_time - 0.5) * (0.58 if side == 0 else -0.42)
        root.location.z = actor["base_z"] + abs(math.sin(phase)) * 0.055
        swing = math.sin(phase) * 0.58
        if actor["kind"] == "Pipo":
            # Pipo is a four-legged puppy: swing legs in the front/back plane.
            actor["legs"][0].rotation_euler[0] = swing
            actor["legs"][1].rotation_euler[0] = -swing
            actor["arms"][0].rotation_euler[0] = -swing * 0.90
            actor["arms"][1].rotation_euler[0] = swing * 0.90
        else:
            actor["legs"][0].rotation_euler[1] = swing
            actor["legs"][1].rotation_euler[1] = -swing
            actor["arms"][0].rotation_euler[1] = -swing * 0.78
            actor["arms"][1].rotation_euler[1] = swing * 0.78
    else:
        actor["root"].location.x = actor["base_x"] + math.sin(local_time * 2.3 + side) * 0.08
        actor["root"].location.z = actor["base_z"] + abs(math.sin(global_time * 2.4 + side)) * 0.018
        if actor["legs"]:
            actor["legs"][0].rotation_euler[1] = math.sin(global_time * 2.4 + side) * 0.035
            actor["legs"][1].rotation_euler[1] = -math.sin(global_time * 2.4 + side) * 0.035
    # Gesture language changes with each beat: investigate, explain, react, cooperate.
    if actor["kind"] == "Luna":
        if walk:
            actor["arms"][0].rotation_euler[1] = math.sin(phase) * 0.42
            actor["arms"][1].rotation_euler[1] = -math.sin(phase) * 0.42
        elif action in {"talk", "converse"}:
            if speaking:
                actor["arms"][1].rotation_euler[1] = -0.45 + math.sin(global_time * 4.0) * 0.25
                actor["arms"][0].rotation_euler[1] = 0.18
                actor["head"].rotation_euler[1] = 0.10
            else:
                actor["arms"][0].rotation_euler[1] = 0.05
                actor["arms"][1].rotation_euler[1] = -0.05
                actor["head"].rotation_euler[1] = -0.12
        elif action == "write":
            actor["arms"][1].rotation_euler[1] = -0.78 + math.sin(global_time * 5.2) * 0.10
            actor["arms"][0].rotation_euler[1] = 0.30
            actor["head"].rotation_euler[1] = -0.18
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
            if speaking:
                actor["arms"][0].rotation_euler[1] = 0.5 + math.sin(global_time * 4.2) * 0.28
                actor["arms"][1].rotation_euler[1] = -0.25
                actor["head"].rotation_euler[1] = -0.10
            else:
                actor["arms"][0].rotation_euler[1] = 0.04
                actor["arms"][1].rotation_euler[1] = -0.04
                actor["head"].rotation_euler[1] = 0.12
        elif action == "write":
            actor["arms"][0].rotation_euler[1] = 0.72
            actor["arms"][1].rotation_euler[1] = -0.72 + math.sin(global_time * 5.2) * 0.10
            actor["head"].rotation_euler[1] = -0.16
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
        actor["tail"].rotation_euler[2] = math.sin(global_time * 11) * 0.55
        if not walk:
            actor["arms"][0].rotation_euler[0] = math.sin(global_time * 2.6) * 0.06
            actor["arms"][1].rotation_euler[0] = -math.sin(global_time * 2.6) * 0.06
            actor["legs"][0].rotation_euler[0] = math.sin(global_time * 2.2) * 0.035
            actor["legs"][1].rotation_euler[0] = -math.sin(global_time * 2.2) * 0.035
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
        if actor.get("tongue"):
            actor["tongue"].scale.z = 0.065
    else:
        mouth.scale.z = 0.035
        if actor.get("tongue"):
            actor["tongue"].scale.z = 0.018


def create_camera(portrait, cx):
    data = bpy.data.cameras.new("Cinematic follow camera")
    camera = bpy.data.objects.new("Cinematic follow camera", data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    # Perspective camera creates real foreground/background scale and depth.
    camera.data.type = "PERSP"
    camera.data.sensor_fit = "VERTICAL" if portrait else "HORIZONTAL"
    camera.data.lens = 50
    camera.location = (cx, -16.0 if portrait else -18.0, 4.8)
    target = Vector((cx, 0.4, 1.85))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return camera


def build_scene_schedule(scene_source_indices, voice_timeline, total_duration):
    """Map every scene to the exact start/end times of its narration and dialogue."""
    allowed = [int(value) for value in scene_source_indices]
    spans = {value: [float("inf"), 0.0] for value in allowed}
    for line in voice_timeline:
        scene_id = int(line.get("scene", -1))
        if scene_id not in spans:
            # Older drafts or appended topic lines belong to the final visible beat.
            scene_id = allowed[-1]
        start = max(0.0, float(line.get("start", 0.0)))
        end = max(start, float(line.get("end", start)))
        spans[scene_id][0] = min(spans[scene_id][0], start)
        spans[scene_id][1] = max(spans[scene_id][1], end)

    schedule = []
    cursor = 0.0
    fallback = total_duration / max(1, len(allowed))
    for scene_id in allowed:
        start, end = spans[scene_id]
        if not math.isfinite(start) or end <= start:
            start, end = cursor, cursor + fallback
        start = min(max(cursor, start), total_duration)
        end = min(max(start + 0.02, end), total_duration)
        if schedule and start > cursor:
            start = cursor
        schedule.append({"scene_index": scene_id, "start": start, "end": end})
        cursor = end
    if schedule:
        schedule[0]["start"] = 0.0
        schedule[-1]["end"] = max(schedule[-1]["end"], total_duration)
    return schedule


def add_stage_lighting(stage_centers):
    # Daytime studio lighting for original Storybook art: smooth warm bounce.
    # One directional sun plus soft key/fill area lights per set gives the
    # characters readable volume, rounded highlights and grounded shadows.
    bpy.ops.object.light_add(type="SUN", location=(0, -10, 14))
    sun = bpy.context.object
    sun.name = "Adventure studio sun"
    sun.data.energy = 2.0
    sun.data.angle = math.radians(18)
    sun.rotation_euler = (math.radians(28), math.radians(-22), math.radians(-24))
    for index, center in enumerate(stage_centers):
        bpy.ops.object.light_add(type="AREA", location=(center - 2.5, -8.0, 9.5))
        key = bpy.context.object
        key.name = "Soft key light " + str(index)
        key.data.energy = 920
        key.data.shape = "DISK"
        key.data.size = 7.5
        key.data.color = (1.0, 0.82, 0.68)
        key.rotation_euler = (math.radians(20), 0, math.radians(-12))
        bpy.ops.object.light_add(type="AREA", location=(center + 4.5, 1.0, 7.5))
        fill = bpy.context.object
        fill.name = "Soft blue fill " + str(index)
        fill.data.energy = 460
        fill.data.size = 8.5
        fill.data.color = (0.56, 0.75, 1.0)
        fill.rotation_euler = (math.radians(24), 0, math.radians(155))


def render(config: dict):
    report(2, "Iniciando motor Blender e preparando a cena 3D.")
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

    report(5, "Carregando Cartoon Storybook 3D v2: novos personagens e cenários.")
    print("ANIMA_ART_VERSION:" + ART_VERSION, flush=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    engine_ids = {
        item.identifier
        for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    }
    # A hosted VPS commonly exposes Mesa llvmpipe instead of a physical GPU.
    # Eevee may spend minutes compiling its first frame on software OpenGL.
    # Workbench is a genuine 3D mesh renderer and offers an optional lightweight
    # studio-lighted cartoon look; it is NOT the retired 2D image pipeline.
    mode = os.getenv("ANIMA_3D_RENDER_MODE", "auto").strip().lower()
    if mode not in {"auto", "eevee", "workbench"}:
        raise ValueError("ANIMA_3D_RENDER_MODE deve ser auto, eevee ou workbench")
    gpu_renderer = "unknown"
    try:
        import gpu
        gpu_renderer = str(gpu.platform.renderer_get())
    except Exception as exc:
        print("ANIMA_GPU_PROBE_WARNING:" + str(exc), flush=True)
    software_gl = any(token in gpu_renderer.lower() for token in
                      ("llvmpipe", "softpipe", "software", "swrast", "lavapipe"))
    # Headless iContainer without a mapped GPU should not run the full Eevee
    # pipeline when OpenGL device detection is unavailable.
    has_render_device = Path("/dev/dri").is_dir() and any(Path("/dev/dri").glob("renderD*"))
    nvidia_device = os.getenv("NVIDIA_VISIBLE_DEVICES", "").strip().lower()
    has_nvidia_device = nvidia_device not in {"", "none", "void"}
    if gpu_renderer == "unknown" and not (has_render_device or has_nvidia_device):
        software_gl = True
    use_workbench = mode == "workbench" or (mode == "auto" and software_gl)
    if use_workbench:
        scene.render.engine = "BLENDER_WORKBENCH"
        report(7, "Renderizador 3D Cartoon leve: GPU física indisponível; usando Workbench com iluminação de estúdio.")
    elif "BLENDER_EEVEE_NEXT" in engine_ids:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        report(7, "Renderizador Cartoon 3D Eevee selecionado.")
    elif "BLENDER_EEVEE" in engine_ids:
        scene.render.engine = "BLENDER_EEVEE"
        report(7, "Renderizador Cartoon 3D Eevee selecionado.")
    else:
        raise RuntimeError("Blender não possui Eevee. Configure ANIMA_3D_RENDER_MODE=workbench para renderização 3D leve.")
    print("ANIMA_RENDER_DEVICE:" + json.dumps({
        "opengl_renderer": gpu_renderer,
        "software_gl": software_gl,
        "selected_backend": scene.render.engine,
        "requested_mode": mode,
    }), flush=True)
    scene.render.resolution_x = int(width)
    scene.render.resolution_y = int(height)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    # Faster PNG writes reduce CPU overhead while keeping lossless frame intermediates.
    scene.render.image_settings.compression = 5
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
    if hasattr(scene, "eevee"):
        # Six temporal samples are a quality/speed compromise for the 3D Shorts.
        # Keep this configurable so a higher-quality render can be requested later.
        sample_count = max(2, min(16, int(os.getenv("ANIMA_EEVEE_SAMPLES", "8"))))
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = sample_count
        elif hasattr(scene.eevee, "taa_samples"):
            scene.eevee.taa_samples = sample_count
        if hasattr(scene.eevee, "use_gtao"):
            scene.eevee.use_gtao = True
            scene.eevee.gtao_distance = 3.0
            scene.eevee.gtao_factor = 1.25
        if hasattr(scene.eevee, "use_soft_shadows"):
            scene.eevee.use_soft_shadows = True
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.threads_mode = "FIXED"
    cpu_count = os.cpu_count() or 2
    requested_threads = int(os.getenv("ANIMA_BLENDER_THREADS", str(min(6, cpu_count))))
    scene.render.threads = max(1, min(cpu_count, requested_threads))
    scene.render.fps = 24
    # Render slightly below the already-small working resolution, then upscale
    # to 1080p in FFmpeg. The final output dimensions and aspect ratio do not change.
    render_scale = max(70, min(100, int(os.getenv("ANIMA_RENDER_SCALE", "100"))))
    scene.render.resolution_percentage = render_scale
    # Eevee renders the original 3D models with studio lighting, material response and depth;
    # Workbench remains a compatibility fallback on Blender builds without Eevee.
    scene.world.color = (0.42, 0.63, 0.77)
    scene.world.use_nodes = True
    world_bg = scene.world.node_tree.nodes.get("Background")
    if world_bg:
        world_bg.inputs["Color"].default_value = (0.52, 0.72, 0.82, 1)
        world_bg.inputs["Strength"].default_value = 0.65

    setup_started = time.perf_counter()
    stage_timings = []
    stage_models = []
    stage_total = max(1, len(scenes))
    for i, shot in enumerate(scenes):
        source_index = int(source_indices[i])
        report(6 + int((i / stage_total) * 6),
               f"Montando cenário 3D {i + 1}/{stage_total}: {shot.get('title', 'cena')}")
        stage_started = time.perf_counter()
        models = make_stage(source_index, plan, shot, portrait)
        stage_seconds = time.perf_counter() - stage_started
        stage_timings.append({"stage": i + 1, "source_index": source_index, "seconds": round(stage_seconds, 3)})
        print("ANIMA_STAGE_TIMING:" + json.dumps(stage_timings[-1]), flush=True)
        models["source_index"] = source_index
        stage_models.append(models)
        report(6 + int(((i + 1) / stage_total) * 6),
               f"Cenário 3D {i + 1}/{stage_total} concluído.")

    report(12, "Montando iluminação e câmeras dos cenários.")
    lighting_started = time.perf_counter()
    add_stage_lighting([model["center"] for model in stage_models])
    lighting_seconds = time.perf_counter() - lighting_started
    camera_started = time.perf_counter()
    camera = create_camera(portrait, 0)
    camera_seconds = time.perf_counter() - camera_started
    setup_seconds = time.perf_counter() - setup_started
    print("ANIMA_SETUP_TIMING:" + json.dumps({
        "setup_seconds": round(setup_seconds, 3),
        "stage_seconds": round(sum(item["seconds"] for item in stage_timings), 3),
        "lighting_seconds": round(lighting_seconds, 3),
        "camera_seconds": round(camera_seconds, 3),
        "stages": stage_timings,
    }), flush=True)
    report(18, "Personagens 3D, cenário e câmera preparados.")

    # A small authentic 3D frame becomes visible on the existing live preview
    # before the full-resolution frame sequence is rendered.
    if stage_models and os.getenv("ANIMA_EARLY_PREVIEW", "1").strip().lower() in {"1", "true", "yes"}:
        first = stage_models[0]
        center = first["center"]
        camera.location.x = center
        camera.location.z = 4.8
        target = Vector((center, 0.25, 1.92))
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        for side, name in enumerate(("Luna", "Tomi", "Pipo")):
            animate_actor(first[name], 0.0, 0.0, "explore", False, side)
        preview_file = out_dir.parent / ("preview-" + config["format"].replace(":", "x") + ".jpg")
        render_percent = scene.render.resolution_percentage
        render_format = scene.render.image_settings.file_format
        render_filepath = scene.render.filepath
        try:
            report(18, "Criando primeira prévia 3D em resolução reduzida.")
            scene.render.resolution_percentage = min(render_percent, 35)
            scene.render.image_settings.file_format = "JPEG"
            scene.render.image_settings.quality = 78
            scene.render.filepath = str(preview_file)
            bpy.ops.render.render(write_still=True)
            print("ANIMA_PREVIEW_READY:" + str(preview_file), flush=True)
            report(19, "Primeira prévia Cartoon 3D disponível no painel.")
        except Exception as exc:
            raise RuntimeError("Não foi possível renderizar nem a prévia 3D. Verifique OpenGL, Xvfb, GPU e recursos do container: " + str(exc)) from exc
        finally:
            scene.render.resolution_percentage = render_percent
            scene.render.image_settings.file_format = render_format
            scene.render.filepath = render_filepath

    render_started = time.perf_counter()

    # Scene cuts follow the actual storyboard; actors move and interact inside each shot.
    action_by_scene = {
        0: "walk", 1: "explore", 2: "converse", 3: "converse",
        4: "discover", 5: "talk", 6: "sniff", 7: "surprise",
        8: "converse", 9: "work", 10: "celebrate", 11: "talk",
        12: "talk", 13: "walk", 14: "celebrate",
    }
    scene_schedule = build_scene_schedule(source_indices, timeline, total_frames / fps)
    for frame in range(total_frames):
        global_time = frame / fps
        current = next(
            (item for item in scene_schedule if item["start"] <= global_time < item["end"]),
            scene_schedule[-1],
        )
        source_index = current["scene_index"]
        scene_slot = source_indices.index(source_index)
        span = max(0.02, current["end"] - current["start"])
        local_progress = max(0.0, min(1.0, (global_time - current["start"]) / span))
        shot = stage_models[scene_slot]
        shot_spec = scenes[scene_slot] if scene_slot < len(scenes) else {}
        action = (
            str(shot_spec.get("action") or action_by_scene.get(source_index, "walk"))
            if isinstance(shot_spec, dict)
            else action_by_scene.get(source_index, "walk")
        )
        active = ""
        for line in timeline:
            if float(line.get("start", 0)) <= global_time < float(line.get("end", 0)):
                line_scene = int(line.get("scene", -1))
                if line_scene in (-1, source_index):
                    active = str(line.get("speaker", "Narrador"))
                    break

        # Camera follows the active set and gently favors the character speaking.
        center = shot["center"] + math.sin(local_progress * math.pi) * (0.32 if not portrait else 0.12)
        if action in {"talk", "converse"}:
            speaker_actor = shot.get(active)
            if not speaker_actor and active == "Moradora" and shot["Natives"]:
                speaker_actor = shot["Natives"][0]
            if speaker_actor:
                center = center * 0.72 + speaker_actor["root"].location.x * 0.28
        camera.location.x = center
        camera.location.z = 4.8 + math.sin(local_progress * math.pi) * 0.12
        close = source_index in (4, 7, 10)
        camera.data.lens = 62 if close else (48 if portrait else 50)
        # A slight camera tilt and dolly-style scale change make the beat read
        # like a children's adventure series, not a locked slideshow frame.
        if action in {"discover", "sniff"}:
            target_z = 1.75
        elif action == "surprise":
            target_z = 2.65
        elif action in {"converse", "talk"}:
            target_z = 2.15
        else:
            target_z = 1.92
        target = Vector((center, 0.25, target_z))
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = 50 + (3 if action in {"discover", "surprise"} else 0)

        for side, name in enumerate(("Luna", "Tomi", "Pipo")):
            actor = shot[name]
            animate_actor(actor, global_time, local_progress, action, active == name, side)
        for n, actor in enumerate(shot["Natives"]):
            animate_actor(actor, global_time, local_progress, "converse", active == "Moradora", n)

        # Shuttle motion follows the spoken action: launch, arrival, farewell.
        ship = shot.get("ship")
        if ship:
            if source_index == 0:
                ship.location.z = 0.15 + local_progress * 1.55
                ship.rotation_euler[1] = math.sin(local_progress * math.pi) * 0.12
            elif source_index == 2:
                ship.location.z = 1.7 * (1.0 - local_progress)
                ship.rotation_euler[1] = -0.08 + local_progress * 0.08
            else:
                ship.location.z = 0.15 + local_progress * 1.25
                ship.rotation_euler[1] = math.sin(local_progress * math.pi) * 0.10

        scene.render.filepath = str(out_dir / f"frame-{frame + 1:06d}.png")
        # render() evaluates the dependency graph itself; forcing frame_set(1)
        # and view_layer.update() on every frame caused redundant scene updates.
        bpy.ops.render.render(write_still=True)
        if frame % max(1, total_frames // 35) == 0 or frame == total_frames - 1:
            pct = 18 + int((frame + 1) / total_frames * 76)
            report(pct, f"Renderizando cena 3D {scene_slot + 1}/{len(scenes)} · quadro {frame + 1}/{total_frames}")

    render_seconds = time.perf_counter() - render_started
    timing = {
        "setup_seconds": round(setup_seconds, 3),
        "render_seconds": round(render_seconds, 3),
        "seconds_per_frame": round(render_seconds / max(1, total_frames), 4),
        "total_seconds": round(setup_seconds + render_seconds, 3),
        "frames": total_frames,
    }
    print("ANIMA_RENDER_TIMING:" + json.dumps(timing), flush=True)
    report(96, "Render 3D concluído.")
    return {"frames": total_frames, "scene_count": len(scenes), "engine": scene.render.engine, "timing": timing}


def main():
    # Supports both: blender -b --python script.py -- --config file.json
    # and: python backend/app/blender_scene.py --module --config file.json
    raw_args = sys.argv[1:]
    args = raw_args[raw_args.index("--") + 1:] if "--" in raw_args else raw_args
    if "--module" in args:
        args.remove("--module")
        print("ANIMA_BLENDER_BACKEND:python-module", flush=True)
    if "--version-check" in args:
        print("ANIMA_BLENDER_READY:" + bpy.app.version_string, flush=True)
        return
    if "--config" not in args:
        raise SystemExit(
            "Uso: blender -b --python blender_scene.py -- --config config.json "
            "ou python blender_scene.py --module --config config.json"
        )
    path = Path(args[args.index("--config") + 1])
    config = json.loads(path.read_text(encoding="utf-8"))
    result = render(config)
    print("ANIMA_RENDER_RESULT:" + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
