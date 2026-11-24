"""Render concept images of the mini DFI with Blender (bpy, Cycles).

Needs out/ from `model.py`. Writes out/render/<view>.png (with labels drawn on top).

Run:  uv run python render.py [hero front back exploded night] [--fast]
"""

import json
import math
import pathlib
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

import display

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
REN = OUT / "render"
DATA = json.loads((OUT / "parts.json").read_text())
P = DATA["params"]
MM = 0.001
FAST = "--fast" in sys.argv
VIEWS = [a for a in sys.argv[1:] if not a.startswith("--")] or ["hero", "front", "back", "exploded", "night"]

SIGN_GROUPS = {"housing", "back", "display", "electronics"}
SIGN_SHIFT = (80, 0, 30)
LIFT = 70  # exploded view: lift pole and sign off the base tiles  # exploded view: move the sign away from the pole first
EXPLODE = {  # mm, by exact name or by prefix ending in "_"
    "housing_left": (-25, -150, 0),
    "housing_right": (25, -150, 0),
    "splice_": (0, -105, 0),
    "side_insert": (25, -215, 0),
    "label": (25, -222, 0),
    "button_ring": (25, -245, 0),
    "button_cap": (25, -245, 0),
    "button_body": (0, 0, 0),
    "roof_left": (-25, 0, 115),
    "roof_right": (25, 0, 115),
    "acrylic": (0, -80, 0),
    "ribbon": (0, 50, 0),
    "esp32_": (0, 50, 0),
    "wires_": (0, 50, 0),
    "spacers_": (0, 100, 0),
    "back_left": (-25, 180, 0),
    "back_right": (25, 180, 0),
    "pole_cap": (0, 0, 75),
}


def explode_of(name):
    if name in EXPLODE:
        return Vector(EXPLODE[name]) + Vector((0, 0, LIFT))
    if name.startswith(("base_tile_", "tactile_")):
        i = int(name.rsplit("_", 1)[1])
        return Vector(((i - 1.5) * 30, -12 if name.startswith("tactile") else 0, 0 if name.startswith("base") else 45))
    for k, v in EXPLODE.items():
        if k.endswith("_") and name.startswith(k):
            return Vector(v) + Vector((0, 0, LIFT))
    return Vector((0, 0, LIFT))


def lin(hexcol):
    h = hexcol.lstrip("#")
    c = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


MATS = {
    "anthracite": dict(color="#3a3e44", rough=0.42, coat=0.25),
    "black": dict(color="#151618", rough=0.5),
    "red": dict(color="#c4161c", rough=0.4),
    "steel": dict(color="#cfd2d6", rough=0.22, metal=1.0),
    "button": dict(color="#30353b", rough=0.3, metal=0.4),
    "black_plastic": dict(color="#121314", rough=0.55),
    "white": dict(color="#e9e8e3", rough=0.5),
    "smoked": dict(color="#30363c", rough=0.03, alpha=0.45),
    "ribbon": dict(color="#9a9ea3", rough=0.6),
    "pcb": dict(color="#17191c", rough=0.35),
    "green_plastic": dict(color="#2f8a4a", rough=0.5),
    "wire_red": dict(color="#c0141a", rough=0.4),
    "wire_black": dict(color="#141414", rough=0.4),
    "wire_yellow": dict(color="#e2b500", rough=0.4),
    "alu": dict(color="#b9bdc2", rough=0.3, metal=1.0),
    "alu_printed": dict(color="#b1b5ba", rough=0.38, metal=0.8),
    "lightgrey": dict(color="#a7abb0", rough=0.45),
    "concrete": dict(color="#8f908d", rough=0.85, noise=True),
    "red_plastic": dict(color="#b3261e", rough=0.5),
    "floor": dict(color="#d4d5d7", rough=0.75),
    "asphalt": dict(color="#16181c", rough=0.22, noise=True),
    "can": dict(color="#b3121b", rough=0.25, metal=0.85),
    "can_top": dict(color="#d0d3d6", rough=0.25, metal=1.0),
}


def setin(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value


def material(name, spec):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    setin(bsdf, "Base Color", lin(spec["color"]))
    setin(bsdf, "Roughness", spec.get("rough", 0.5))
    setin(bsdf, "Metallic", spec.get("metal", 0.0))
    setin(bsdf, "Coat Weight", spec.get("coat", 0.0))
    setin(bsdf, "Coat Roughness", 0.15)
    if "alpha" in spec:
        setin(bsdf, "Alpha", spec["alpha"])
    if spec.get("noise"):
        tex = nt.nodes.new("ShaderNodeTexNoise")
        setin(tex, "Scale", 140.0)
        setin(tex, "Detail", 8.0)
        bump = nt.nodes.new("ShaderNodeBump")
        setin(bump, "Strength", 0.12)
        nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = tuple(c * 0.85 for c in lin(spec["color"])[:3]) + (1,)
        ramp.color_ramp.elements[1].color = tuple(min(1, c * 1.15) for c in lin(spec["color"])[:3]) + (1,)
        nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def display_material(strength):
    img_path = OUT / "display.png"
    rgb = (display.texture(display.frame()) * 255).astype(np.uint8)
    Image.fromarray(rgb).save(img_path)
    m = bpy.data.materials.new("display")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(img_path))
    tex.interpolation = "Cubic"
    setin(bsdf, "Base Color", (0.004, 0.004, 0.005, 1))
    setin(bsdf, "Roughness", 0.35)
    setin(bsdf, "Coat Weight", 0.3)
    setin(bsdf, "Coat Roughness", 0.05)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    setin(bsdf, "Emission Strength", strength)
    return m, bsdf


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def area_light(name, loc, target, size, energy, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size = size
    ld.energy = energy
    ld.color = color
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    look_at(o, target)
    return o


# ------------------------------------------------------------------ scene setup
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.04 if FAST else 0.025
scene.cycles.samples = 24 if FAST else 56
scene.cycles.use_denoising = True
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass

mats = {k: material(k, v) for k, v in MATS.items()}

objs = {}
for p in DATA["parts"]:
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=str(ROOT / p["stl"]), global_scale=MM)
    (o,) = set(bpy.data.objects) - before
    o.name = p["name"]
    o.data.materials.append(mats[p["mat"]])
    try:
        o.data.shade_smooth()
        o.data.set_sharp_from_angle(angle=math.radians(35))
    except AttributeError:
        pass
    objs[p["name"]] = (o, p)

# LED screen: a plane just in front of the panels, facing -Y
disp_mat, disp_bsdf = display_material(3.0)
bpy.ops.mesh.primitive_plane_add(
    size=1,
    location=((P["WIN_X0"] + P["DISP_W"] / 2) * MM, (P["PANEL_FRONT_Y"] - 0.2) * MM, (P["WIN_Z0"] + P["DISP_H"] / 2) * MM),
)
screen = bpy.context.active_object
screen.name = "screen"
screen.scale = (P["DISP_W"] * MM, P["DISP_H"] * MM, 1)
screen.rotation_euler = (math.radians(90), 0, 0)
screen.data.materials.append(disp_mat)
objs["screen"] = (screen, {"group": "display", "explode": [0, 0, 0], "name": "screen"})

# floor + scale-reference can (330 ml: 66 mm x 115 mm)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
floor.data.materials.append(mats["floor"])
can_loc = ((P["BASE_X1"] + 55) * MM, -0.035, 0)
bpy.ops.mesh.primitive_cylinder_add(radius=0.033, depth=0.115, vertices=96, location=(can_loc[0], can_loc[1], 0.0575))
can = bpy.context.active_object
can.data.materials.append(mats["can"])
bev = can.modifiers.new("bevel", "BEVEL")
bev.width = 0.004
bev.segments = 4
bpy.ops.mesh.primitive_cylinder_add(radius=0.027, depth=0.002, vertices=96, location=(can_loc[0], can_loc[1], 0.1155))
can_top = bpy.context.active_object
can_top.data.materials.append(mats["can_top"])
for o in (can, can_top):
    o.data.shade_smooth()

# world
world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]

backfill = area_light("backfill", (0.35, 0.9, 0.85), (0.25, 0, 0.38), 0.8, 14)
backfill.hide_render = True
lights = [
    area_light("key", (-0.7, -1.2, 1.3), (0.2, 0, 0.3), 1.4, 38),
    area_light("fill", (1.5, -0.9, 0.7), (0.2, 0, 0.3), 1.8, 14),
    area_light("rim", (0.3, 1.4, 1.2), (0.2, 0, 0.35), 1.4, 26),
]

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

FONT = None
for f in (
    "/usr/share/fonts/noto/NotoSans-SemiBold.ttf",
    "/usr/share/fonts/noto/NotoSans-Medium.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
):
    if pathlib.Path(f).exists():
        FONT = f
        break


def font(size):
    return ImageFont.truetype(FONT, size) if FONT else ImageFont.load_default()


def set_explode(on):
    for name, (o, p) in objs.items():
        off = explode_of(name) if on else Vector((0, 0, 0))
        if on and p["group"] in SIGN_GROUPS:
            off += Vector(SIGN_SHIFT)
        if name == "screen":
            base = Vector(((P["WIN_X0"] + P["DISP_W"] / 2), (P["PANEL_FRONT_Y"] - 0.2), (P["WIN_Z0"] + P["DISP_H"] / 2)))
            o.location = (base + off) * MM
        else:
            o.location = off * MM


def hide(names, state=True):
    for n in names:
        if n in objs:
            objs[n][0].hide_render = state


def center_of(name):
    o = objs[name][0]
    v = [o.matrix_world @ Vector(x) for x in o.bound_box]
    return (sum(v, Vector()) / 8) / MM


def proj(pt_mm, size):
    co = world_to_camera_view(scene, cam, Vector(pt_mm) * MM)
    return (co.x * size[0], (1 - co.y) * size[1])


def render(view, res):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 50 if FAST else 100
    REN.mkdir(parents=True, exist_ok=True)
    path = REN / f"{view}.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def pill(draw, xy, text, size=26, fg=(25, 27, 30), bg=(255, 255, 255, 235), anchor="mm"):
    f = font(size)
    l, t, r, b = draw.textbbox(xy, text, font=f, anchor=anchor)
    draw.rounded_rectangle((l - 10, t - 7, r + 10, b + 7), radius=10, fill=bg)
    draw.text(xy, text, font=f, fill=fg, anchor=anchor)


def callout(draw, anchor, at, text, size=26):
    draw.line([anchor, at], fill=(30, 32, 36), width=3)
    r = 6
    draw.ellipse((anchor[0] - r, anchor[1] - r, anchor[0] + r, anchor[1] + r), fill=(230, 60, 40))
    pill(draw, at, text, size=size, anchor="mm")


def callouts(img, items, size=24, top=80, margin=28):
    """items: [(anchor_px, text)]. Labels go in a column on the nearer side, without crossing."""
    d = ImageDraw.Draw(img, "RGBA")
    W, H = img.size
    f = font(size)
    gap = size * 2.0
    sides = {"L": [], "R": []}
    mid = sum(a[0] for a, _ in items) / len(items)
    for a, t in items:
        sides["L" if a[0] < mid else "R"].append((a, t))
    for side, group in sides.items():
        group.sort(key=lambda it: it[0][1])
        ys = [min(max(a[1], top), H - margin - size) for a, _ in group]
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + gap)
        over = ys[-1] - (H - margin - size) if ys else 0
        if over > 0:
            ys[-1] -= over
            for i in range(len(ys) - 2, -1, -1):
                ys[i] = min(ys[i], ys[i + 1] - gap)
        for (a, t), y in zip(group, ys):
            tw = d.textlength(t, font=f)
            if side == "L":
                tx, lx = margin + 10, margin + 10 + tw + 12
            else:
                tx, lx = W - margin - 10 - tw, W - margin - 10 - tw - 12
            d.line([a, (lx, y)], fill=(30, 32, 36, 220), width=3)
            r = 6
            d.ellipse((a[0] - r, a[1] - r, a[0] + r, a[1] + r), fill=(230, 60, 40))
            pill(d, (tx, y), t, size=size, anchor="lm")


def caption(img, text):
    d = ImageDraw.Draw(img, "RGBA")
    f = font(int(img.width * 0.018))
    pad = int(img.width * 0.012)
    d.text((pad, pad), text, font=f, fill=(40, 42, 46))


def studio(img):
    w, h = img.size
    t = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array([244, 245, 247]), np.array([214, 217, 221])
    grad = (top * (1 - t) + bot * t).astype(np.uint8) * np.ones((1, w, 1), np.uint8)
    bgimg = Image.fromarray(grad, "RGB").convert("RGBA")
    return Image.alpha_composite(bgimg, img)


def finish(path, fn=None, cap=None):
    img = Image.open(path).convert("RGBA")
    if scene.render.film_transparent:
        img = studio(img)
    if fn:
        fn(img)
    if cap:
        caption(img, cap)
    img.convert("RGB").save(path)
    print("wrote", path)


# ------------------------------------------------------------------ lighting presets
def day():
    bg.inputs["Color"].default_value = lin("#dfe2e6")
    bg.inputs["Strength"].default_value = 0.8
    scene.render.film_transparent = True
    floor.is_shadow_catcher = True
    floor.data.materials[0] = mats["floor"]
    for l in lights:
        l.hide_render = False
    disp_bsdf.inputs["Emission Strength"].default_value = 3.0
    floor.hide_render = False
    scene.view_settings.exposure = 0.0


def night():
    bg.inputs["Color"].default_value = lin("#0b1430")
    bg.inputs["Strength"].default_value = 0.35
    scene.render.film_transparent = False
    floor.is_shadow_catcher = False
    floor.data.materials[0] = mats["asphalt"]
    for l in lights:
        l.hide_render = True
    disp_bsdf.inputs["Emission Strength"].default_value = 9.0
    scene.view_settings.exposure = 0.3


lamp = None


def street_lamp(on):
    global lamp
    if lamp is None:
        ld = bpy.data.lights.new("lamp", "SPOT")
        ld.energy = 60
        ld.color = (1.0, 0.78, 0.5)
        ld.spot_size = math.radians(80)
        ld.shadow_soft_size = 0.05
        lamp = bpy.data.objects.new("lamp", ld)
        scene.collection.objects.link(lamp)
        lamp.location = (-0.6, -0.5, 1.2)
        look_at(lamp, (0.2, 0, 0.3))
    lamp.hide_render = not on


# ------------------------------------------------------------------ views
CAP = "Ulm DFI mini, concept v0.1"

for view in VIEWS:
    set_explode(False)
    hide(objs.keys(), False)
    hide(["acrylic"])
    backfill.hide_render = True
    can.hide_render = can_top.hide_render = False
    cam_data.type = "PERSP"
    day()
    street_lamp(False)

    if view == "hero":
        cam.location = (-0.44, -1.04, 0.53)
        look_at(cam, (0.22, 0.0, 0.29))
        cam_data.lens = 50
        path = render(view, (1600, 1200))
        finish(path, cap=f"{CAP}  ·  3/4 view, 330 ml can for scale")

    elif view == "front":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 0.84
        cam.location = (0.215, -3.0, 0.285)
        look_at(cam, (0.215, 0.0, 0.285))
        size = (1600, 1500)
        path = render(view, size)

        def dims(img):
            d = ImageDraw.Draw(img, "RGBA")
            s = img.size
            ink = (30, 32, 36)

            def hdim(x0, x1, z, text, y_mm=-120):
                a, b = proj((x0, y_mm, z), s), proj((x1, y_mm, z), s)
                d.line([a, b], fill=ink, width=3)
                for p in (a, b):
                    d.line([(p[0], p[1] - 12), (p[0], p[1] + 12)], fill=ink, width=3)
                pill(d, ((a[0] + b[0]) / 2, a[1]), text)

            def vdim(x, z0, z1, text, y_mm=-120):
                a, b = proj((x, y_mm, z0), s), proj((x, y_mm, z1), s)
                d.line([a, b], fill=ink, width=3)
                for p in (a, b):
                    d.line([(p[0] - 12, p[1]), (p[0] + 12, p[1])], fill=ink, width=3)
                pill(d, (a[0], (a[1] + b[1]) / 2), text)

            hdim(P["XH0"], P["XH1"], P["ZH1"] + 45, f"housing {P['HW']:.0f} × {P['HH']:.0f} × {P['HD'] + P['BACK_T']:.0f} mm")
            hdim(P["WIN_X0"], P["WIN_X0"] + P["DISP_W"], P["ZH0"] - 28, f"screen {P['DISP_W']:.0f} × {P['DISP_H']:.0f} mm, 128 × 64 LEDs")
            vdim(P["XH1"] + 35, P["ZH0"], P["ZH1"], f"{P['HH']:.0f}")
            vdim(P["BASE_X0"] - 28, 0, P["POLE_TOP"] + 7, f"{P['POLE_TOP'] + 7:.0f} mm")
            hdim(P["BASE_X0"], P["BASE_X1"], -22, f"base {P['BASE_X1'] - P['BASE_X0']:.0f} × {P['BASE_D']:.0f} mm")
            pill(d, proj((P["BASE_X1"] + 55, -120, 150), s), "330 ml can", size=22)

        finish(path, dims, cap=f"{CAP}  ·  front")

    elif view == "back":
        hide(["back_left", "back_right"])
        cam.location = (0.50, 1.38, 0.80)
        look_at(cam, (0.25, 0.0, 0.36))
        cam_data.lens = 40
        can.hide_render = can_top.hide_render = True
        backfill.hide_render = False
        size = (1800, 1200)
        path = render(view, size)

        def labels(img):
            s = img.size
            pts = [
                (center_of("esp32_module"), "ESP32-S3 board"),
                (center_of("panel_1") + Vector((40, 8, 45)), "2× LED panel 64×64"),
                (center_of("ribbon"), "ribbon cable"),
                (Vector((P["XH0"] + 3, 0, (P["ZH0"] + P["ZH1"]) / 2)), "5 V in, via the pole"),
                (center_of("button_body"), "24 mm button"),
                (Vector((P["WIN_X0"] + 215, P["YB"], P["WIN_Z0"] + 135)), "spacers to the panels"),
                (Vector((P["XH1"] - 10, P["YB"], P["ZH1"] - 10)), "back-cover screw bosses"),
            ]
            callouts(img, [(proj(pt, s), t) for pt, t in pts])

        finish(path, labels, cap=f"{CAP}  ·  back, cover off")

    elif view == "exploded":
        set_explode(True)
        hide(["acrylic"], False)
        can.hide_render = can_top.hide_render = True
        cam.location = (1.05, -1.25, 0.90)
        look_at(cam, (0.26, -0.03, 0.37))
        cam_data.lens = 40
        size = (1900, 1300)
        path = render(view, size)

        def labels(img):
            s = img.size
            pts = [
                (center_of("roof_right"), "rain cap (2 parts)"),
                (center_of("housing_right") + Vector((0, -30, -60)), "front housing (2 halves)"),
                (center_of("side_insert"), "side panel insert (black)"),
                (center_of("button_cap"), "24 mm push button"),
                (center_of("acrylic") + Vector((60, 0, -60)), "3 mm smoked acrylic"),
                (center_of("panel_1") + Vector((40, 0, -50)), "2× LED panel 64×64"),
                (center_of("esp32_module"), "ESP32-S3 board"),
                (center_of("back_right"), "back cover (2 halves)"),
                (center_of("mount"), "pole bracket"),
                (Vector((0, 0, P["ZH0"] - 80)), "Ø40 mm alu tube"),
                (center_of("pole_cap"), "pole cap"),
                (center_of("base_tile_3") + Vector((0, 0, 12)), "4 platform tiles (weighted)"),
                (center_of("tactile_2"), "white tactile strips"),
            ]
            callouts(img, [(proj(pt, s), t) for pt, t in pts])

        finish(path, labels, cap=f"{CAP}  ·  exploded: printed parts fit a 25 cm bed")

    elif view == "night":
        night()
        street_lamp(True)
        floor.hide_render = False
        can.hide_render = can_top.hide_render = True
        cam.location = (-0.30, -0.62, 0.17)
        look_at(cam, (0.25, 0.0, 0.42))
        cam_data.lens = 28
        path = render(view, (1200, 1600))
        finish(path, cap=None)
