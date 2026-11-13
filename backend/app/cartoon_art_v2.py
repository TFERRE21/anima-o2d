"""Pequenos Guardiões — Storybook Cartoon 3D character bible, v2.

This replaces the former toy/armor characters. Original authored procedural
stylized meshes; no third-party franchise or downloaded models.
Uses Blender-native meshes and curves so iContainer can render offline.
"""
from __future__ import annotations

import math
import json
import bpy


ART_VERSION = "storybook-human-v2.0"


def _color(name, rgba):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.93
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    return material


def _line(name, parent, points, material, thickness=0.012):
    """Smooth shallow curves (hair contours, smiles, eyebrows), not blobs."""
    data = bpy.data.curves.new(name, type="CURVE")
    data.dimensions = "3D"
    data.resolution_u = 12
    data.bevel_depth = thickness
    data.bevel_resolution = 2
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coords in zip(spline.bezier_points, points):
        point.co = coords
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    data.materials.append(material)
    return obj


def build_human(name, kind, origin, size, G, profiles):
    """Create two distinctly HUMAN animated children: not dolls, robots or bobbleheads."""
    sphere, cube, empty, pivot = (G[x] for x in ("sphere", "cube", "empty", "make_pivot"))
    is_luna = kind == "Luna"
    root = empty(name + " STORYBOOK V2 root", origin)
    root.scale = (size, size, size)
    profile = profiles.get(kind, {})
    root["character_profile_id"] = profile.get("id", kind.lower())
    root["art_version"] = ART_VERSION
    root["rig_controls"] = json.dumps(profile.get("rig", []))
    root["visemes"] = json.dumps(profile.get("visemes", []))

    # Linen, cotton and naturally shaded skin rather than shiny space armor.
    skin = _color("Storybook Luna skin", (0.91, 0.64, 0.47, 1)) if is_luna else _color("Storybook Tomi skin", (0.79, 0.51, 0.32, 1))
    skin_shadow = _color("Storybook warm nose", (0.78, 0.45, 0.34, 1))
    hair = _color("Storybook Luna mahogany", (0.19, 0.085, 0.07, 1)) if is_luna else _color("Storybook Tomi dark cocoa", (0.24, 0.15, 0.09, 1))
    hair_glow = _color("Storybook Luna highlighted strands", (0.30, 0.14, 0.10, 1)) if is_luna else _color("Storybook Tomi highlighted strands", (0.37, 0.235, 0.12, 1))
    jacket = _color("Storybook Luna rose jacket", (0.82, 0.27, 0.39, 1)) if is_luna else _color("Storybook Tomi teal hoodie", (0.12, 0.43, 0.55, 1))
    jacket_edge = _color("Storybook Luna coral cuffs", (0.98, 0.55, 0.54, 1)) if is_luna else _color("Storybook Tomi seafoam cuffs", (0.28, 0.68, 0.68, 1))
    shirt = _color("Storybook cotton shirt", (0.99, 0.88, 0.72, 1))
    pants = _color("Storybook Luna lavender leggings", (0.34, 0.32, 0.57, 1)) if is_luna else _color("Storybook Tomi ochre trousers", (0.49, 0.39, 0.28, 1))
    shoe = _color("Storybook soft leather shoes", (0.28, 0.19, 0.24, 1)) if is_luna else _color("Storybook Tomi leather shoes", (0.19, 0.26, 0.32, 1))
    whites = _color("Storybook ivory sclera", (0.985, 0.96, 0.90, 1))
    iris = _color("Storybook Luna hazel eyes", (0.32, 0.25, 0.16, 1)) if is_luna else _color("Storybook Tomi warm brown eyes", (0.24, 0.17, 0.11, 1))
    pupil = _color("Storybook eyes deep brown", (0.085, 0.07, 0.075, 1))
    smile_color = _color("Storybook soft smile", (0.43, 0.22, 0.18, 1))
    badge = _color("Storybook embroidery gold", (0.95, 0.69, 0.30, 1))

    # Natural child shape, narrower shoulders, longer legs and smaller head
    # relative to body. No superhero breastplate, jetpack, gloves or bobble eyes.
    sphere(name + " natural cotton jacket", root, (0, 0.02, 1.44), (0.38, 0.29, 0.56), jacket, 30, 20)
    sphere(name + " cream inner shirt", root, (0, -0.259, 1.53), (0.22, 0.040, 0.43), shirt, 24, 14)
    sphere(name + " jacket collar left", root, (-0.18, -0.22, 1.90), (0.12, 0.09, 0.18), jacket_edge, 18, 12)
    sphere(name + " jacket collar right", root, (0.18, -0.22, 1.90), (0.12, 0.09, 0.18), jacket_edge, 18, 12)
    if is_luna:
        sphere(name + " soft flared tunic", root, (0, 0.01, 1.01), (0.47, 0.35, 0.27), jacket, 26, 16)
        _line(name + " jacket seam", root, [(0, -0.299, 1.88), (0, -0.304, 1.51), (0, -0.322, 1.23)], shirt, 0.008)
    else:
        # The short explorer scarf is a recognizable part of Tomi's outfit.
        scarf = _color("Storybook Tomi rust scarf", (0.93, 0.51, 0.23, 1))
        sphere(name + " soft woven scarf", root, (0.03, -0.13, 1.97), (0.32, 0.26, 0.105), scarf, 26, 14)
        sphere(name + " scarf flap", root, (0.23, -0.29, 1.68), (0.105, 0.085, 0.32), scarf, 16, 10)
    sphere(name + " embroidered golden star", root, (0.0, -0.298, 1.53), (0.095, 0.024, 0.095), badge, 20, 12)

    legs = []
    for index, xx in enumerate((-0.19, 0.19)):
        leg = pivot(root, name + " animated leg " + str(index), (xx, 0.02, 1.04))
        sphere(name + " tailored trouser leg " + str(index), leg, (0, 0.00, -0.43), (0.155, 0.17, 0.50), pants, 20, 14)
        sphere(name + " soft ankle sock " + str(index), leg, (0, -0.015, -0.83), (0.15, 0.18, 0.10), shirt, 16, 12)
        sphere(name + " rounded canvas shoe " + str(index), leg, (0, -0.11, -0.94), (0.20, 0.29, 0.13), shoe, 22, 14)
        sphere(name + " woven shoe toe " + str(index), leg, (0, -0.32, -0.96), (0.15, 0.09, 0.075), jacket_edge, 16, 10)
        legs.append(leg)

    arms = []
    for index, xx in enumerate((-0.395, 0.395)):
        arm = pivot(root, name + " animated arm " + str(index), (xx, 0.02, 1.78))
        sphere(name + " fabric upper sleeve " + str(index), arm, (0, 0, -0.23), (0.17, 0.19, 0.33), jacket, 20, 14)
        sphere(name + " fitted sleeve " + str(index), arm, (0, -0.01, -0.53), (0.135, 0.16, 0.29), jacket, 18, 12)
        sphere(name + " cloth cuff " + str(index), arm, (0, -0.015, -0.74), (0.14, 0.165, 0.09), jacket_edge, 16, 12)
        sphere(name + " warm little hand " + str(index), arm, (0, -0.045, -0.82), (0.14, 0.14, 0.17), skin, 18, 12)
        arms.append(arm)

    sphere(name + " simple neck", root, (0, 0, 2.06), (0.16, 0.17, 0.23), skin, 20, 14)
    head = pivot(root, name + " expressive head", (0, -0.055, 2.49))
    # One calm rounded face, not multiple protruding cheek/pupil balls.
    sphere(name + " smoothly rounded face", head, (0, 0, -0.07), (0.55, 0.44, 0.59), skin, 40, 28)
    sphere(name + " small chin shape", head, (0, -0.22, -0.39), (0.24, 0.15, 0.13), skin, 22, 14)
    for side, xx in ((-1, -0.54), (1, 0.54)):
        sphere(name + " little ear " + str(side), head, (xx, -0.01, -0.12), (0.09, 0.085, 0.15), skin, 16, 12)

    # Silhouette-led hair sculpt: chestnut bob with a swept bang / side part.
    sphere(name + " sculpted hair volume", head, (0, 0.075, 0.29), (0.565, 0.44, 0.38), hair, 34, 24)
    if is_luna:
        sphere(name + " soft bob left", head, (-0.49, 0.025, -0.16), (0.17, 0.33, 0.42), hair, 28, 18)
        sphere(name + " long bob right", head, (0.48, 0.055, -0.22), (0.18, 0.35, 0.44), hair, 28, 18)
        swoop = sphere(name + " side-swept fringe", head, (-0.12, -0.235, 0.40), (0.40, 0.19, 0.20), hair, 28, 16)
        swoop.rotation_euler[1] = -0.24
        ribbon = _color("Storybook rose hair bow", (0.95, 0.42, 0.51, 1))
        sphere(name + " hair ribbon knot", head, (-0.48, -0.25, 0.34), (0.105, 0.085, 0.08), ribbon, 16, 12)
        sphere(name + " bow wing A", head, (-0.60, -0.24, 0.41), (0.15, 0.055, 0.10), ribbon, 18, 12)
        sphere(name + " bow wing B", head, (-0.40, -0.24, 0.47), (0.12, 0.05, 0.09), ribbon, 18, 12)
    else:
        # A broad side part is more human than several round hair spikes.
        fringe = sphere(name + " Tomi sweeping fringe", head, (0.11, -0.27, 0.38), (0.43, 0.18, 0.19), hair, 30, 20)
        fringe.rotation_euler[1] = 0.20
        sphere(name + " part volume", head, (-0.38, -0.08, 0.45), (0.19, 0.26, 0.24), hair_glow, 22, 14)
        sphere(name + " short sideburn left", head, (-0.51, -0.09, 0.02), (0.09, 0.21, 0.19), hair, 20, 14)
        sphere(name + " short sideburn right", head, (0.51, -0.09, 0.02), (0.09, 0.21, 0.19), hair, 20, 14)
    _line(name + " hair silhouette strand", head,
          [(-0.28, -0.391, 0.38), (-0.01, -0.447, 0.41), (0.24, -0.397, 0.40)],
          hair_glow, 0.012)

    # Eyes are almost flush to the face. White + iris occupy only ~1/6
    # of face width, without bulging eye rings or oversized sparkles.
    for side, xx in ((-1, -0.19), (1, 0.19)):
        sphere(name + " ivory almond eye " + str(side), head,
               (xx, -0.432, 0.03), (0.107, 0.026, 0.079), whites, 24, 16)
        sphere(name + " understated iris " + str(side), head,
               (xx + 0.006, -0.460, 0.028), (0.050, 0.013, 0.055), iris, 20, 14)
        sphere(name + " fine pupil " + str(side), head,
               (xx + 0.006, -0.475, 0.028), (0.024, 0.010, 0.034), pupil, 18, 12)
        _line(name + " gentle upper eyelid " + str(side), head,
              [(xx - 0.106, -0.441, 0.07), (xx, -0.464, 0.109), (xx + 0.10, -0.441, 0.069)],
              hair, 0.010)
        _line(name + " eyebrows " + str(side), head,
              [(xx - 0.105, -0.419, 0.205), (xx, -0.442, 0.22), (xx + 0.105, -0.419, 0.20)],
              hair, 0.012)
    sphere(name + " tiny natural nose", head, (0, -0.470, -0.17),
           (0.045, 0.035, 0.045), skin_shadow, 16, 12)
    _line(name + " relaxed smiling mouth curve", head,
          [(-0.12, -0.399, -0.315), (-0.06, -0.439, -0.34),
           (0, -0.452, -0.347), (0.06, -0.439, -0.34), (0.12, -0.399, -0.315)],
          smile_color, 0.011)
    if not is_luna:
        freckles = _color("Storybook subtle freckles", (0.55, 0.31, 0.23, 1))
        for sign in (-1, 1):
            for i in range(3):
                sphere(name + " freckle " + str(sign) + str(i), head,
                       (sign * (0.29 + i * 0.036), -0.384 + i * 0.025, -0.16 + (i % 2) * 0.026),
                       (0.012, 0.006, 0.011), freckles, 10, 8)
    # Animated low-profile vowel opening behind the static smile line.
    mouth = sphere(name + " speech viseme", head, (0, -0.451, -0.35),
                   (0.056, 0.014, 0.025), smile_color, 18, 12)
    tongue = None
    return {
        "root": root, "head": head, "mouth": mouth, "tongue": tongue,
        "arms": arms, "legs": legs, "kind": kind,
        "base_x": origin[0], "base_z": origin[2],
    }


def build_dog(origin, size, G, profiles):
    """Pipo is a small caramel PUPPY, not an anthropomorphic teddy-bear figure."""
    sphere, empty, pivot = (G[x] for x in ("sphere", "empty", "make_pivot"))
    fur = _color("Storybook Pipo caramel fur", (0.66, 0.36, 0.18, 1))
    cream = _color("Storybook Pipo warm cream fur", (0.94, 0.75, 0.54, 1))
    ear_fur = _color("Storybook Pipo chocolate ears", (0.33, 0.16, 0.10, 1))
    vest = _color("Storybook Pipo stitched teal harness", (0.22, 0.53, 0.61, 1))
    eye = _color("Storybook Pipo friendly dark eyes", (0.13, 0.10, 0.095, 1))
    nose = _color("Storybook Pipo nose", (0.15, 0.115, 0.105, 1))
    badge = _color("Storybook Pipo medallion gold", (0.94, 0.71, 0.31, 1))
    root = empty("Pipo STORYBOOK V2 root", origin)
    root.scale = (size, size, size)
    profile = profiles.get("Pipo", {})
    root["art_version"] = ART_VERSION
    root["character_profile_id"] = profile.get("id", "pipo")
    root["rig_controls"] = json.dumps(profile.get("rig", []))
    root["visemes"] = json.dumps(profile.get("visemes", []))

    sphere("Pipo tapered puppy body", root, (0, 0.13, 0.82), (0.38, 0.65, 0.38), fur, 32, 20)
    sphere("Pipo soft blue harness panel", root, (0, 0.16, 0.94),
           (0.39, 0.39, 0.25), vest, 28, 18)
    sphere("Pipo cream chest", root, (0, -0.45, 0.91),
           (0.30, 0.18, 0.32), cream, 20, 14)
    sphere("Pipo small golden collar tag", root, (0, -0.597, 1.09),
           (0.085, 0.045, 0.085), badge, 16, 12)

    head = pivot(root, "Pipo expressive puppy head", (0, -0.47, 1.35))
    sphere("Pipo genuine rounded dog face", head, (0, 0, -0.045),
           (0.43, 0.38, 0.43), fur, 32, 24)
    sphere("Pipo white blaze", head, (0, -0.321, 0.07),
           (0.17, 0.065, 0.25), cream, 24, 16)
    for sign in (-1, 1):
        xx = 0.39 * sign
        flap = sphere("Pipo floppy ear " + str(sign), head,
               (xx, 0.04, -0.08), (0.18, 0.19, 0.35), ear_fur, 28, 18)
        flap.rotation_euler[1] = -0.24 * sign
        sphere("Pipo unobtrusive dog eye " + str(sign), head,
               (0.17 * sign, -0.365, 0.075), (0.076, 0.03, 0.075), eye, 22, 16)
        sphere("Pipo tiny catchlight " + str(sign), head,
               (0.17 * sign - 0.023, -0.396, 0.112),
               (0.014, 0.009, 0.017), cream, 12, 8)
    sphere("Pipo integrated muzzle", head, (0, -0.325, -0.205),
           (0.26, 0.225, 0.16), cream, 26, 18)
    sphere("Pipo dark rounded nose", head, (0, -0.533, -0.14),
           (0.10, 0.06, 0.070), nose, 24, 16)
    _line("Pipo happy soft smile", head,
          [(-0.145, -0.482, -0.269), (0, -0.516, -0.315),
           (0.145, -0.482, -0.269)], eye, 0.013)
    mouth = sphere("Pipo talking mouth", head, (0, -0.501, -0.316),
                   (0.068, 0.016, 0.035), nose, 16, 10)

    # Four articulated short legs, visible as a real puppy stance.
    arms, legs = [], []
    for sign in (-1, 1):
        for front in (True, False):
            x = sign * 0.245
            y = -0.38 if front else 0.52
            part = "fore" if front else "hind"
            limb = pivot(root, "Pipo " + part + " leg pivot " + str(sign), (x, y, 0.68))
            sphere("Pipo " + part + " lower leg", limb, (0, -0.015, -0.26),
                   (0.145, 0.16, 0.33), fur, 18, 14)
            sphere("Pipo " + part + " cream paw", limb, (0, -0.1, -0.51),
                   (0.18, 0.215, 0.13), cream, 18, 14)
            (arms if front else legs).append(limb)
    tail = pivot(root, "Pipo tail wag pivot", (0, 0.65, 1.01))
    wag = sphere("Pipo upward waving tail", tail, (0, 0.26, 0.12),
                 (0.14, 0.35, 0.16), fur, 20, 14)
    wag.rotation_euler[0] = 0.46
    return {
        "root": root, "head": head, "mouth": mouth, "tongue": None,
        "arms": arms, "legs": legs, "tail": tail, "kind": "Pipo",
        "base_x": origin[0], "base_z": origin[2],
    }


def dress_stage(cx, biome, G):
    """Daylit layered 3D environments with open sky and organic rolling terrain."""
    sphere, cube, cylinder = (G[x] for x in ("sphere", "cube", "cylinder"))
    b = str(biome or "").lower()
    desert = any(x in b for x in ("deserto", "areia", "vulc"))
    snow = any(x in b for x in ("neve", "gelo", "polar"))
    sea = any(x in b for x in ("oceano", "mar", "agua", "água"))
    sky = _color("Storybook apricot blue sky", (0.47, 0.70, 0.84, 1))
    distant = _color("Storybook distant rolling hills", (0.59, 0.78, 0.67, 1)) if not desert else _color("Storybook distant sandstone hills", (0.90, 0.71, 0.53, 1))
    middle = _color("Storybook middle hills", (0.30, 0.65, 0.53, 1)) if not desert else _color("Storybook terracotta hills", (0.78, 0.47, 0.33, 1))
    ground = _color("Storybook lush earth", (0.38, 0.64, 0.48, 1))
    if snow:
        distant = _color("Storybook snowy mountain haze", (0.75, 0.87, 0.92, 1))
        middle = _color("Storybook ice valley", (0.52, 0.77, 0.83, 1))
        ground = _color("Storybook soft snow", (0.79, 0.89, 0.87, 1))
    if sea:
        distant = _color("Storybook ocean horizon", (0.38, 0.76, 0.78, 1))
        middle = _color("Storybook shore grass", (0.43, 0.67, 0.56, 1))
    if desert:
        ground = _color("Storybook desert clay", (0.84, 0.62, 0.43, 1))
    cloud = _color("Storybook ivory clouds", (0.98, 0.96, 0.86, 1))
    leaf = _color("Storybook jade canopy", (0.22, 0.53, 0.38, 1))
    leaf_alt = _color("Storybook chartreuse foliage", (0.48, 0.70, 0.42, 1))
    bark = _color("Storybook tree bark", (0.37, 0.25, 0.18, 1))
    flower = _color("Storybook wildflower petals", (0.99, 0.82, 0.54, 1))
    flower_pink = _color("Storybook wildflower coral", (0.95, 0.48, 0.44, 1))
    cube("Storybook wide open SKY", None, (cx, 10.0, 4.0), (27, 0.25, 16), sky, 0.0)
    cube("Storybook ground plane", None, (cx, 1.0, -0.41), (19, 20, 0.6), ground, 0.07)
    for i in range(5):
        xx = cx - 9 + i * 4.4
        sphere("Storybook soft faraway hill " + str(i), None, (xx, 7.8, 1.8 + i % 2 * 0.3),
               (3.9, 1.15, 2.15), distant, 22, 16)
        sphere("Storybook meadow ridge " + str(i), None, (xx + 0.6, 5.8, 0.56 + (i % 3) * 0.2),
               (3.4, 1.2, 1.25), middle, 22, 16)
    for i, (xx, zz) in enumerate(((-6.3, 5.9), (-3.0, 6.3), (2.7, 6.6), (6.5, 5.95))):
        for j, offset in enumerate((-0.50, 0, 0.6)):
            sphere("Storybook drifting cloud " + str(i) + "-" + str(j), None,
                   (cx + xx + offset, 9.1, zz + (0.1 if j == 1 else 0.0)),
                   (0.72, 0.32, 0.31 + (0.13 if j == 1 else 0)), cloud, 18, 12)
    # Trees stay to the edges so actors and facial expressions remain readable.
    if not (desert or snow or sea):
        for i, xx in enumerate((-7.5, -5.1, 5.3, 7.7)):
            yy = 1.6 + (i % 2) * 1.5
            cylinder("Storybook slender tree", None, (cx + xx, yy, 1.15), 0.20, 2.5, bark)
            for j, xoff in enumerate((-0.7, 0.0, 0.72)):
                sphere("Storybook layered leaf crown " + str(j), None,
                       (cx + xx + xoff, yy + 0.08, 2.55 + j % 2 * 0.25),
                       (0.95, 0.70, 0.92), leaf if (i+j) % 2 else leaf_alt, 22, 16)
    else:
        for i, xx in enumerate((-7.6, -5.5, 5.5, 7.6)):
            sphere("Storybook biome scenic rock", None, (cx+xx, 1.8 + i % 2, 0.25),
                   (0.65, 0.50, 0.43), middle, 18, 12)
    # Lush little flowers create foreground parallax and more convincing scale.
    for i in range(15):
        xx = cx - 7.4 + i * 1.03
        yy = -3.45 + (i % 3) * 0.37
        if abs(xx-cx) < 2.5:
            continue
        cylinder("Storybook flower stem", None, (xx, yy, 0.13), 0.023, 0.28, leaf_alt, vertices=8)
        for j in range(4):
            angle = j * math.pi * 0.5
            sphere("Storybook flower petal", None,
                   (xx + 0.10 * math.cos(angle), yy + 0.10 * math.sin(angle), 0.28),
                   (0.095, 0.065, 0.06), flower if i % 2 else flower_pink, 10, 8)
        sphere("Storybook flower heart", None, (xx, yy, 0.28),
               (0.046, 0.047, 0.043), flower, 10, 8)
