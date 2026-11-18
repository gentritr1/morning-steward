"""Steward, the dock character, as a 3D figure. Builds from an empty file and renders one still.

Geometry follows DESIGN.md section 6 and src/styles.css (.steward-*): a 48 px body, a 4x4 phosphor
grid inset 5 px with 4 px gaps, two eyes 9x13 px set 7 px apart and off the cell rhythm.
Scale: 1 px of the badge = 1 cm. Cells light row-major from the disk fill, as stewardFillPattern does.

Looks: clay (blockout) and a (instrument dark: the app's dark theme, chosen 2026-11-18 over a daylight look).

  Blender --background --python-exit-code 1 --threads 4 --python art/figure/steward.py -- \
      --look a --engine cycles --out out/a.png [--res 1600] [--samples 128] [--fill 62] [--cam hero|front]
"""
import argparse
import math
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--look", default="clay", choices=["clay", "a"])
ap.add_argument("--out", required=True)
ap.add_argument("--res", type=int, default=960)
ap.add_argument("--engine", default="eevee", choices=["eevee", "cycles"])
ap.add_argument("--samples", type=int, default=96)
ap.add_argument("--fill", type=float, default=62.0, help="disk used %%")
ap.add_argument("--cam", default="hero", choices=["hero", "front"])
ap.add_argument("--blend", default="", help="optional path to save the .blend")
args = ap.parse_args(argv)

PX = 0.01
BODY_W, BODY_H, BODY_D = 48 * PX, 48 * PX, 40 * PX
FRONT_Y = -BODY_D / 2
LOOK = args.look

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def oklch(l, c, h):
    """OKLCH -> linear sRGB (Blender works in linear)."""
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    return tuple(max(0.0, v) for v in rgb) + (1.0,)


def hexc(h):
    """#rrggbb -> linear sRGB."""
    v = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v) + (1.0,)


# the product's tokens (src/styles.css, dark theme)
SIGNAL = oklch(0.86, 0.2, 130)
VOID = oklch(0.17, 0.028, 264)


def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def material(name, base, rough=0.5, metallic=0.0, emit=0.0, coat=0.0, bump=None):
    """bump = (scale, strength): fine noise grain so no surface is one flat colour."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = principled(m)
    p.inputs["Base Color"].default_value = base
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metallic
    if emit:
        p.inputs["Emission Color"].default_value = base
        p.inputs["Emission Strength"].default_value = emit
    if coat:
        p.inputs["Coat Weight"].default_value = coat
        p.inputs["Coat Roughness"].default_value = 0.05
    if bump:
        nt = m.node_tree
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = bump[0]
        noise.inputs["Detail"].default_value = 8
        b = nt.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = bump[1]
        nt.links.new(noise.outputs["Fac"], b.inputs["Height"])
        nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
        # roughness wanders by under +-0.05 (larger reads as smoke at page size)
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = rough - 0.04
        rr.inputs["To Max"].default_value = rough + 0.04
        nt.links.new(noise.outputs["Fac"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], p.inputs["Roughness"])
    return m


def box(name, size, loc, bevel=0.0, segs=3, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segs
        mod.limit_method = "NONE"
        o.modifiers.new("wn", "WEIGHTED_NORMAL")
    bpy.ops.object.shade_smooth()
    if mat:
        o.data.materials.append(mat)
    return o


# ---- materials per look ----
if LOOK == "clay":
    grey = (0.42, 0.42, 0.42, 1)
    M = dict(body=material("body", grey, 0.6), lit=material("lit", (0.75,) * 3 + (1,), 0.5),
             dark=material("dark", (0.5,) * 3 + (1,), 0.5), eye=material("eye", (0.92,) * 3 + (1,), 0.4),
             floor=material("floor", (0.55,) * 3 + (1,), 0.8), wall=material("wall", (0.55,) * 3 + (1,), 0.8))
    cell_proud, eye_proud, frame = 0.6 * PX, 1.6 * PX, False
elif LOOK == "a":
    # instrument dark: anodised navy, lime phosphor behind frosted acrylic, recessed cell windows
    M = dict(body=material("body", hexc("#252a40"), 0.48, metallic=0.5, bump=(900, 0.04)),
             frame=material("frame", hexc("#0c0d14"), 0.7),
             lit=material("lit", hexc("#b4ec1f"), 0.3, emit=0.9),
             dark=material("dark", hexc("#5c606b"), 0.35, bump=(1400, 0.03)),
             eye=material("eye", hexc("#c2f52a"), 0.3, emit=1.4),
             floor=material("floor", hexc("#20222f"), 0.62, bump=(300, 0.02)),
             wall=material("wall", hexc("#181a25"), 0.8))
    cell_proud, eye_proud, frame = 0.4 * PX, 3.5 * PX, True

# ---- the figure ----
box("body", (BODY_W, BODY_D, BODY_H), (0, 0, BODY_H / 2), bevel=6 * PX, segs=6, mat=M["body"])

lit = round(min(100, max(0, args.fill)) / 100 * 16)
CELL = 6.5 * PX
for i in range(16):
    r, c = divmod(i, 4)
    x = -BODY_W / 2 + (5 + c * 10.5 + 3.25) * PX
    z = BODY_H - (5 + r * 10.5 + 3.25) * PX
    if frame:  # a dark window the cell sits in, so it reads as recessed glass
        box(f"frame_{i:02d}", (CELL + 1.4 * PX, 0.3 * PX, CELL + 1.4 * PX), (x, FRONT_Y - 0.1 * PX, z),
            bevel=0.6 * PX, segs=2, mat=M["frame"])
    box(f"cell_{i:02d}", (CELL, cell_proud * 2, CELL), (x, FRONT_Y, z),
        bevel=min(0.8 * PX, cell_proud * 0.9), segs=3, mat=M["lit"] if i < lit else M["dark"])

EYE_W, EYE_H, EYE_GAP = 9 * PX, 13 * PX, 7 * PX
eye_z = BODY_H - (0.32 * 48 + 5) * PX
for side in (-1, 1):
    x = side * (EYE_GAP / 2 + EYE_W / 2)
    box("eye_l" if side < 0 else "eye_r", (EYE_W, eye_proud * 2, EYE_H), (x, FRONT_Y, eye_z),
        bevel=2.6 * PX, segs=5, mat=M["eye"])

# ---- set: a floor and a far wall (out of focus), no horizon line in frame ----
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 2.0, 0))
bpy.context.object.data.materials.append(M["floor"])
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 3.2, 3.0), rotation=(math.radians(90), 0, 0))
bpy.context.object.data.materials.append(M["wall"])

# ---- camera ----
target = bpy.data.objects.new("target", None)
scene.collection.objects.link(target)
target.location = (0, 0, BODY_H * 0.48)
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 85
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.location = (1.15, -2.55, 0.7) if args.cam == "hero" else (0, -2.9, BODY_H * 0.5)
tr = cam.constraints.new("TRACK_TO")
tr.target, tr.track_axis, tr.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
scene.camera = cam
if LOOK != "clay":
    cam_data.dof.use_dof = True
    # focus on the face, not the body's centre: the eyes are the sharpest thing in frame
    cam_data.dof.focus_distance = (cam.location - target.location).length - BODY_D / 2
    cam_data.dof.aperture_fstop = 4.0


def light(kind, name, loc, energy, size=1.0, color=(1, 1, 1), aim=True):
    d = bpy.data.lights.new(name, kind)
    d.energy, d.color = energy, color
    if kind == "AREA":
        d.size = size
    if kind == "SUN":
        d.angle = math.radians(size)
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    o.location = loc
    if aim:
        c = o.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    return o


world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")

if LOOK == "clay":
    light("AREA", "key", (-1.6, -1.8, 2.0), 120, 1.6)
    light("AREA", "rim", (1.2, 1.6, 1.2), 60, 0.8)
    bg.inputs["Color"].default_value, bg.inputs["Strength"].default_value = (0.5, 0.5, 0.5, 1), 0.6
elif LOOK == "a":
    # one large soft key upper left, a thin cool rim back right; the cells light the floor themselves
    light("AREA", "key", (-1.7, -1.6, 2.2), 110, 1.8, (1.0, 0.97, 0.94))
    light("AREA", "rim", (1.3, 1.5, 1.0), 60, 0.6, (0.75, 0.85, 1.0))
    bg.inputs["Color"].default_value, bg.inputs["Strength"].default_value = VOID, 0.15

# ---- render ----
engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
if args.engine == "cycles":
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"  # Metal crashed headless 5.2 in 2 of 7 runs (blender-worlds-route)
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
else:
    scene.render.engine = next(e for e in engines if e.startswith("BLENDER_EEVEE"))
try:
    scene.view_settings.view_transform = "AgX"
    if LOOK == "a":  # AgX Base bleaches bright lime toward mint; Punchy keeps the phosphor saturated
        looks = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["look"].enum_items]
        scene.view_settings.look = next((l for l in looks if "Punchy" in l), "None")
except TypeError:
    pass
scene.render.resolution_x = args.res
scene.render.resolution_y = round(args.res * 0.75)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = args.out
print(f"steward: look={LOOK} engine={scene.render.engine} fill={args.fill}% lit={lit}/16 -> {args.out}")
if args.blend:
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)
bpy.ops.render.render(write_still=True)
print("steward: done")
