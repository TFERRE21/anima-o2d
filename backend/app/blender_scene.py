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


def human_character(name, kind, origin, size=1.0):
    """Original rounded 3D child-hero design with expressive face and adventure suit."""
    root = empty(name + " root", origin)
    root.scale = (size, size, size)
    profile = CHARACTER_PROFILES.get(kind, {})
    root["character_profile_id"] = profile.get("id", kind.lower() + "-legacy")
    root["rig_controls"] = json.dumps(profile.get("rig", []))
    root["visemes"] = json.dumps(profile.get("visemes", []))
    is_luna = kind == "Luna"
    suit = M["pink"] if is_luna else M["blue"]
    trim = M["pink_light"] if is_luna else M["blue_light"]
    skin = M["skin"] if is_luna else M["skin_light"]
    hair = M["hair"] if is_luna else M["hair_light"]
    accent = M["gold"] if is_luna else M["gold_light"]

    # Rounded, slightly oversized child proportions with layered suit geometry.
    sphere(name + " rounded torso", root, (0, 0, 1.28), (0.53, 0.37, 0.68), suit, 28, 18)
    sphere(name + " chest armor", root, (0, -0.315, 1.48), (0.38, 0.105, 0.43), trim, 24, 16)
    sphere(name + " chest inset", root, (0, -0.398, 1.47), (0.30, 0.045, 0.34), suit, 22, 14)
    sphere(name + " collar", root, (0, -0.015, 1.87), (0.28, 0.30, 0.13), M["gold_light"], 20, 12)
    cube(name + " utility belt", root, (0, -0.01, 0.82), (0.93, 0.72, 0.16), M["gold"], 0.07)
    cube(name + " belt buckle", root, (0, -0.385, 0.84), (0.23, 0.07, 0.16), M["gold_light"], 0.045)
    for side, xx in (("L", -0.36), ("R", 0.36)):
        cube(name + " belt pouch " + side, root, (xx, -0.33, 0.83), (0.18, 0.10, 0.21), trim, 0.05)
        sphere(name + " shoulder armor " + side, root, (xx * 1.12, 0, 1.70), (0.23, 0.27, 0.21), trim, 18, 12)
        sphere(name + " knee pad " + side, root, (xx * 0.60, -0.17, 0.36), (0.18, 0.08, 0.12), accent, 16, 10)

    # Backpack and side equipment create a readable explorer silhouette.
    cube(name + " explorer backpack", root, (0, 0.37, 1.38), (0.72, 0.34, 0.86), M["metal"], 0.16)
    cube(name + " backpack color panel", root, (0, 0.555, 1.42), (0.48, 0.055, 0.54), suit, 0.09)
    for side, xx in (("L", -0.23), ("R", 0.23)):
        cylinder(name + " backpack thruster " + side, root, (xx, 0.48, 1.02), 0.10, 0.30, trim, (math.pi / 2, 0, 0), 14)
    sphere(name + " backpack signal", root, (0, 0.60, 1.83), (0.10, 0.08, 0.11), M["gold_light"])

    # Neck and independently animated head.
    cylinder(name + " neck", root, (0, 0, 1.94), 0.18, 0.24, skin, vertices=20)
    head = make_pivot(root, name + " head pivot", (0, -0.055, 2.34))
    sphere(name + " soft face", head, (0, 0, 0), (0.66, 0.52, 0.69), skin, 32, 24)
    sphere(name + " chin", head, (0, -0.28, -0.37), (0.35, 0.20, 0.19), skin, 20, 14)
    for side, xx in (("L", -0.60), ("R", 0.60)):
        sphere(name + " ear " + side, head, (xx, -0.035, -0.05), (0.14, 0.13, 0.22), skin, 18, 12)
        sphere(name + " cheek " + side, head, (xx * 0.58, -0.405, -0.19), (0.17, 0.075, 0.13), M["pink_light"], 18, 12)

    # Layered hair, with distinct silhouettes for Luna and Tomi.
    sphere(name + " hair cap", head, (0, 0.055, 0.47), (0.68, 0.53, 0.36), hair, 28, 18)
    sphere(name + " hair side L", head, (-0.56, 0.00, 0.04), (0.16, 0.40, 0.47), M["hair"], 18, 12)
    sphere(name + " hair side R", head, (0.56, 0.00, 0.04), (0.16, 0.40, 0.47), M["hair"], 18, 12)
    if is_luna:
        for i, xx in enumerate((-0.34, -0.12, 0.12, 0.34)):
            sphere(name + " soft fringe " + str(i), head, (xx, -0.355, 0.36 + (0.04 if i in (1, 2) else 0)), (0.19, 0.15, 0.19), M["hair_light"], 16, 12)
        # Signature inventor band and a small glowing side star.
        bpy.ops.mesh.primitive_torus_add(major_segments=40, minor_segments=12, major_radius=0.48, minor_radius=0.065, location=(0, 0, 0))
        band = bpy.context.object
        band.name = name + " pink inventor headband"
        set_parent(band, head, (0, -0.435, 0.40), (1.12, 0.45, 0.78), (math.radians(90), 0, 0))
        band.data.materials.append(M["pink_light"])
        sphere(name + " golden headband star", head, (0.50, -0.45, 0.36), (0.13, 0.09, 0.13), M["gold"])
        sphere(name + " tiny blue communicator", head, (-0.50, -0.20, 0.15), (0.10, 0.10, 0.13), M["blue_light"])
    else:
        # Swept hair locks give Tomi his own silhouette, not a crown/helmet copy.
        for i, (xx, zz, tilt) in enumerate([
            (-0.43, 0.42, -0.30), (-0.24, 0.56, -0.18), (0.00, 0.62, 0.02),
            (0.24, 0.55, 0.18), (0.43, 0.40, 0.30)
        ]):
            lock = sphere(name + " swept hair lock " + str(i), head, (xx, -0.01, zz), (0.22, 0.23, 0.34), M["hair"], 18, 12)
            lock.rotation_euler[1] = tilt
        sphere(name + " blue ear communicator", head, (0.55, -0.15, 0.10), (0.12, 0.13, 0.16), M["blue_light"], 16, 10)

    # Large, bright eyes with irises, pupils, brows and multiple catchlights.
    iris = M["blue"] if is_luna else M["hair"]
    for side, xx in (("L", -0.235), ("R", 0.235)):
        sphere(name + " eye socket " + side, head, (xx, -0.444, 0.035), (0.175, 0.085, 0.235), M["skin_light"], 20, 14)
        sphere(name + " eye white " + side, head, (xx, -0.505, 0.045), (0.145, 0.075, 0.195), M["white"], 24, 16)
        sphere(name + " iris " + side, head, (xx, -0.566, 0.035), (0.082, 0.038, 0.125), iris, 20, 14)
        sphere(name + " pupil " + side, head, (xx, -0.595, 0.03), (0.044, 0.025, 0.086), M["black"], 16, 12)
        sphere(name + " eye sparkle large " + side, head, (xx - 0.026, -0.619, 0.083), (0.031, 0.018, 0.040), M["white"], 12, 8)
        sphere(name + " eye sparkle small " + side, head, (xx + 0.030, -0.616, -0.005), (0.014, 0.012, 0.018), M["white"], 10, 8)
        brow = sphere(name + " expressive brow " + side, head, (xx, -0.47, 0.30), (0.17, 0.055, 0.045), hair, 16, 10)
        brow.rotation_euler[1] = -0.10 if side == "L" else 0.10

    sphere(name + " button nose", head, (0, -0.565, -0.105), (0.075, 0.060, 0.065), skin, 16, 10)
    mouth = sphere(name + " animated smile mouth", head, (0, -0.525, -0.285), (0.105, 0.052, 0.075), M["mouth"], 20, 12)
    sphere(name + " lower lip", head, (0, -0.505, -0.355), (0.085, 0.035, 0.026), M["pink_light"], 16, 10)
    tongue = sphere(name + " talking tongue", head, (0, -0.572, -0.335), (0.045, 0.022, 0.018), M["pink_light"], 12, 8)

    # Articulated legs: suit trousers, rounded boots, soles and boot highlights.
    legs = []
    for side, xx in (("L", -0.23), ("R", 0.23)):
        pivot = make_pivot(root, name + " leg pivot " + side, (xx, 0, 0.79))
        sphere(name + " upper leg " + side, pivot, (0, 0, -0.30), (0.18, 0.20, 0.39), suit, 18, 12)
        sphere(name + " boot cuff " + side, pivot, (0, -0.02, -0.55), (0.19, 0.22, 0.12), trim, 16, 10)
        sphere(name + " rounded boot " + side, pivot, (0, -0.10, -0.68), (0.23, 0.30, 0.17), M["hair"] if is_luna else M["blue"], 20, 12)
        cube(name + " boot sole " + side, pivot, (0, -0.10, -0.80), (0.43, 0.52, 0.055), M["gold"], 0.025)
        legs.append(pivot)

    # Articulated arms with shoulder caps, wrist cuffs and rounded explorer gloves.
    arms = []
    for side, xx in (("L", -0.49), ("R", 0.49)):
        pivot = make_pivot(root, name + " arm pivot " + side, (xx, 0, 1.68))
        sphere(name + " upper arm " + side, pivot, (0, 0, -0.25), (0.16, 0.18, 0.34), skin, 18, 12)
        sphere(name + " forearm " + side, pivot, (0, -0.015, -0.49), (0.135, 0.15, 0.25), skin, 18, 12)
        cylinder(name + " wrist cuff " + side, pivot, (0, -0.02, -0.57), 0.15, 0.15, trim, vertices=16)
        sphere(name + " rounded glove " + side, pivot, (0, -0.04, -0.68), (0.19, 0.19, 0.17), M["gold"], 18, 12)
        for finger in range(3):
            sphere(name + " glove finger " + side + " " + str(finger), pivot,
                   ((finger - 1) * 0.09, -0.10, -0.78),
                   (0.055, 0.075, 0.075), M["gold_light"], 10, 8)
        arms.append(pivot)

    badge = sphere(name + " guardian badge", root, (0, -0.415, 1.34), (0.23, 0.075, 0.23), M["gold"], 24, 16)
    star_mesh(name + " guardian star", root, 0, -0.485, 1.29, 0.18, M["gold_light"])
    return {
        "root": root, "head": head, "mouth": mouth, "tongue": tongue,
        "arms": arms, "legs": legs, "kind": kind, "base_x": origin[0],
        "base_z": origin[2],
    }


def dog_character(origin, size=0.92):
    """Friendly quadruped puppy with soft proportions and a custom explorer vest."""
    root = empty("Pipo quadruped root", origin)
    root.scale = (size, size, size)
    profile = CHARACTER_PROFILES.get("Pipo", {})
    root["character_profile_id"] = profile.get("id", "pipo-legacy")
    root["rig_controls"] = json.dumps(profile.get("rig", []))
    root["visemes"] = json.dumps(profile.get("visemes", []))
    sphere("Pipo soft puppy body", root, (0, 0.06, 0.94), (0.48, 0.77, 0.43), M["dog"], 28, 18)
    sphere("Pipo cream chest bib", root, (0, -0.45, 0.90), (0.35, 0.22, 0.34), M["dog_light"], 22, 14)
    sphere("Pipo explorer vest", root, (0, -0.02, 1.02), (0.51, 0.69, 0.31), M["blue"], 24, 16)
    sphere("Pipo vest side panel L", root, (-0.40, -0.08, 1.02), (0.12, 0.46, 0.27), M["blue_light"], 16, 10)
    sphere("Pipo vest side panel R", root, (0.40, -0.08, 1.02), (0.12, 0.46, 0.27), M["blue_light"], 16, 10)
    cube("Pipo gold rescue collar", root, (0, -0.51, 1.30), (0.68, 0.16, 0.17), M["gold"], 0.07)
    sphere("Pipo round vest badge", root, (0, -0.535, 1.08), (0.19, 0.065, 0.19), M["gold"], 20, 12)
    star_mesh("Pipo little guardian star", root, 0, -0.594, 1.03, 0.13, M["gold_light"])
    cube("Pipo puppy pack", root, (0, 0.55, 1.03), (0.52, 0.38, 0.56), M["metal"], 0.13)
    sphere("Pipo pack signal", root, (0, 0.77, 1.16), (0.10, 0.06, 0.10), M["gold_light"])

    # Puppy head points toward the camera, with floppy ears and a broad muzzle.
    head = make_pivot(root, "Pipo head pivot", (0, -0.62, 1.44))
    sphere("Pipo rounded puppy head", head, (0, 0, 0), (0.55, 0.48, 0.52), M["dog"], 30, 20)
    sphere("Pipo forehead marking", head, (0, -0.35, 0.26), (0.23, 0.12, 0.18), M["dog_light"], 18, 12)
    for side, xx in (("L", -0.48), ("R", 0.48)):
        ear = sphere("Pipo floppy ear " + side, head, (xx, 0.02, -0.04), (0.22, 0.25, 0.43), M["dog_dark"], 20, 14)
        ear.rotation_euler[1] = -0.28 if side == "L" else 0.28
        sphere("Pipo inner ear " + side, head, (xx, -0.19, -0.05), (0.12, 0.075, 0.27), M["dog_light"], 16, 10)
        sphere("Pipo eye white " + side, head, (xx * 0.48, -0.405, 0.12), (0.125, 0.075, 0.17), M["white"], 20, 14)
        sphere("Pipo iris " + side, head, (xx * 0.48, -0.466, 0.11), (0.065, 0.035, 0.105), M["hair"], 16, 10)
        sphere("Pipo pupil " + side, head, (xx * 0.48, -0.493, 0.105), (0.035, 0.02, 0.072), M["black"], 14, 10)
        sphere("Pipo eye sparkle " + side, head, (xx * 0.48 - 0.02, -0.513, 0.145), (0.025, 0.015, 0.03), M["white"], 10, 8)
        sphere("Pipo brow " + side, head, (xx * 0.48, -0.405, 0.31), (0.13, 0.045, 0.035), M["dog_dark"], 12, 8)
    sphere("Pipo left muzzle", head, (-0.14, -0.43, -0.18), (0.23, 0.19, 0.18), M["dog_light"], 18, 12)
    sphere("Pipo right muzzle", head, (0.14, -0.43, -0.18), (0.23, 0.19, 0.18), M["dog_light"], 18, 12)
    sphere("Pipo puppy nose", head, (0, -0.602, -0.11), (0.12, 0.08, 0.085), M["black"], 18, 12)
    mouth = sphere("Pipo animated puppy mouth", head, (0, -0.535, -0.33), (0.11, 0.045, 0.06), M["mouth"], 18, 12)
    sphere("Pipo pink tongue", head, (0, -0.58, -0.39), (0.075, 0.035, 0.045), M["pink_light"], 14, 10)

    # Four separate articulated legs: front legs use the arm controls,
    # rear legs use the leg controls, so a trot can alternate diagonally.
    legs = []
    for side, xx in (("L", -0.27), ("R", 0.27)):
        pivot = make_pivot(root, "Pipo hind leg pivot " + side, (xx, 0.46, 0.72))
        sphere("Pipo hind leg " + side, pivot, (0, 0.04, -0.26), (0.16, 0.19, 0.34), M["dog"], 16, 10)
        sphere("Pipo hind paw " + side, pivot, (0, -0.06, -0.54), (0.20, 0.24, 0.15), M["dog"], 16, 10)
        sphere("Pipo hind paw pad " + side, pivot, (0, -0.26, -0.55), (0.11, 0.035, 0.07), M["dog_light"], 12, 8)
        legs.append(pivot)
    arms = []
    for side, xx in (("L", -0.27), ("R", 0.27)):
        pivot = make_pivot(root, "Pipo front leg pivot " + side, (xx, -0.45, 0.78))
        sphere("Pipo front leg " + side, pivot, (0, -0.03, -0.28), (0.15, 0.18, 0.36), M["dog"], 16, 10)
        sphere("Pipo front paw " + side, pivot, (0, -0.13, -0.56), (0.20, 0.24, 0.15), M["dog"], 16, 10)
        sphere("Pipo front paw pad " + side, pivot, (0, -0.32, -0.57), (0.11, 0.035, 0.07), M["dog_light"], 12, 8)
        arms.append(pivot)
    tail = make_pivot(root, "Pipo wagging tail", (0, 0.68, 1.06))
    sphere("Pipo fluffy tail", tail, (0, 0.27, 0.08), (0.16, 0.38, 0.17), M["dog"], 16, 10)
    return {
        "root": root, "head": head, "mouth": mouth, "arms": arms,
        "legs": legs, "tail": tail, "kind": "Pipo",
        "base_x": origin[0], "base_z": origin[2],
    }


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
    camera.location = (cx, -19.5, 5.5)
    target = Vector((cx, 0.4, 2.25))
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
    # One directional sun plus soft key/fill area lights per set gives the
    # characters readable volume, rounded highlights and grounded shadows.
    bpy.ops.object.light_add(type="SUN", location=(0, -10, 14))
    sun = bpy.context.object
    sun.name = "Adventure studio sun"
    sun.data.energy = 1.6
    sun.data.angle = math.radians(18)
    sun.rotation_euler = (math.radians(28), math.radians(-22), math.radians(-24))
    for index, center in enumerate(stage_centers):
        bpy.ops.object.light_add(type="AREA", location=(center - 2.5, -8.0, 9.5))
        key = bpy.context.object
        key.name = "Soft key light " + str(index)
        key.data.energy = 720
        key.data.shape = "DISK"
        key.data.size = 7.5
        key.data.color = (1.0, 0.82, 0.68)
        key.rotation_euler = (math.radians(20), 0, math.radians(-12))
        bpy.ops.object.light_add(type="AREA", location=(center + 4.5, 1.0, 7.5))
        fill = bpy.context.object
        fill.name = "Soft blue fill " + str(index)
        fill.data.energy = 360
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

    report(5, "Carregando modelos 3D e materiais.")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    engine_ids = {
        item.identifier
        for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    }
    if "BLENDER_EEVEE_NEXT" in engine_ids:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in engine_ids:
        scene.render.engine = "BLENDER_EEVEE"
    else:
        scene.render.engine = "BLENDER_WORKBENCH"
    report(7, "Motor Blender Eevee selecionado para renderização acelerada pela GPU.")
    print("ANIMA_RENDER_DEVICE: EEVEE_GPU", flush=True)
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
    scene.world.color = (0.018, 0.04, 0.11)
    scene.world.use_nodes = True
    world_bg = scene.world.node_tree.nodes.get("Background")
    if world_bg:
        world_bg.inputs["Color"].default_value = (0.025, 0.045, 0.10, 1)
        world_bg.inputs["Strength"].default_value = 0.24

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
        camera.location.z = 5.3 + math.sin(local_progress * math.pi) * 0.12
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
            target_z = 2.30
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
