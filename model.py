"""Parametric concept model of a desk-size Ulm stop departure display (DFI).

Builds every part with build123d, in assembly position, and writes:
  out/stl/<part>.stl   one mesh per part (printed and bought parts)
  out/parts.json       part list with material, group and size (render.py reads it)
Units are millimetres. X = width (pole on the left), Y = depth (front is -Y), Z = up.

Run:  uv run python model.py
"""

import json
import pathlib

from build123d import (
    Axis,
    Box,
    Cylinder,
    Pos,
    Rot,
    Sphere,
    export_stl,
    fillet,
    scale,
)

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
STL = OUT / "stl"

# --- Display: 2x P2.5 64x64 HUB75 LED panels side by side -> 128x64 px --------
PANEL = 160.0  # one P2.5 64x64 panel is 160 x 160 mm
PANEL_T = 14.0  # PCB + plastic frame, without the M3 posts
N_PANELS = 2
DISP_W, DISP_H = PANEL * N_PANELS, PANEL  # 320 x 160 mm visible screen
ACRYLIC = 3.0  # smoked acrylic in front of the LEDs

# --- Housing ---------------------------------------------------------------------
BEZEL_L = 14.0  # frame on the pole side
SIDE_W = 80.0  # side panel with the round button (away from the pole)
BEZEL_TB = 24.0  # frame above and below the screen
HW = BEZEL_L + DISP_W + SIDE_W  # 414
HH = DISP_H + 2 * BEZEL_TB  # 208  (fits a 250 x 210 bed printed face-down)
HD = 66.0  # depth without the back cover
WALL = 2.4
FRONT = 3.0
R_EDGE = 6.0
BACK_T = 2.5

# --- Pole, mount and base --------------------------------------------------------
POLE_D = 40.0  # off-the-shelf 40 mm aluminium (or PVC) tube
POLE_R = POLE_D / 2
MOUNT_W = 26.0  # gap between the pole surface and the housing
BASE_H = 24.0
BASE_D = 180.0
TILE_W = 140.0
N_TILES = 4
BASE_X0 = -90.0
CLEAR = 260.0  # free pole between the base and the sign
POLE_TOP_ABOVE = 55.0
SOCKET = 20.0

# --- Derived positions -----------------------------------------------------------
XH0 = POLE_R + MOUNT_W  # housing left edge
XH1 = XH0 + HW
ZH0 = BASE_H + CLEAR  # housing bottom
ZH1 = ZH0 + HH
YF = -HD / 2  # front face
YB = HD / 2  # back edge of the housing tub
XS = XH0 + BEZEL_L + PANEL  # split line = seam between the two panels
WIN_X0 = XH0 + BEZEL_L
WIN_Z0 = ZH0 + BEZEL_TB
WIN_CX = WIN_X0 + DISP_W / 2
WIN_CZ = WIN_Z0 + DISP_H / 2
SIDE_X0 = WIN_X0 + DISP_W + 8
SIDE_X1 = XH1 - 8
SIDE_CX = (SIDE_X0 + SIDE_X1) / 2
BTN_Z = WIN_Z0 + DISP_H - 42
BTN_D = 24.0
PANEL_FRONT_Y = YF + FRONT + ACRYLIC  # LED face
PANEL_BACK_Y = PANEL_FRONT_Y + PANEL_T
POLE_TOP = ZH1 + POLE_TOP_ABOVE

parts = []


def add(name, shape, mat, group, explode=(0, 0, 0), printed=True, note=""):
    parts.append(
        dict(name=name, shape=shape, mat=mat, group=group, explode=list(explode), printed=printed, note=note)
    )


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def cyl_y(r, y0, y1, x, z):
    """Cylinder along Y."""
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(r, y1 - y0)


def cyl_x(r, x0, x1, y, z):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(r, x1 - x0)


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(r, z1 - z0)


# ================================ HOUSING ========================================
outer = box(XH0, XH1, YF, YB, ZH0, ZH1)
outer = fillet(outer.edges().filter_by(Axis.Y), R_EDGE)
inner = box(XH0 + WALL, XH1 - WALL, YF + FRONT, YB + 1, ZH0 + WALL, ZH1 - WALL)
inner = fillet(inner.edges().filter_by(Axis.Y), R_EDGE - WALL)
tub = outer - inner

# screen window + rebate for the acrylic
tub -= box(WIN_X0, WIN_X0 + DISP_W, YF - 1, YF + FRONT + 1, WIN_Z0, WIN_Z0 + DISP_H)
# side panel pocket (a separate black insert sits in it), button hole
tub -= box(SIDE_X0, SIDE_X1, YF - 1, YF + 1.5, WIN_Z0, WIN_Z0 + DISP_H)
tub -= cyl_y(BTN_D / 2 + 0.3, YF - 1, YF + FRONT + 1, SIDE_CX, BTN_Z)
# cable entry from the pole bracket
tub -= cyl_x(6, XH0 - 1, XH0 + WALL + 1, 0, (ZH0 + ZH1) / 2)

# screw bosses for the back cover (corners + next to the split)
boss_pts = []
for bx in (XH0 + 10, XS - 8, XS + 8, XH1 - 10):
    for bz in (ZH0 + 10, ZH1 - 10):
        boss_pts.append((bx, bz))
for bx, bz in boss_pts:
    tub += cyl_y(4.5, YF + FRONT, YB, bx, bz)
    tub -= cyl_y(1.6, YF + FRONT + 4, YB + 1, bx, bz)

housing_l = tub & box(XH0 - 1, XS, YF - 1, YB + 1, ZH0 - 1, ZH1 + 1)
housing_r = tub & box(XS, XH1 + 1, YF - 1, YB + 1, ZH0 - 1, ZH1 + 1)
add("housing_left", housing_l, "anthracite", "housing", (-30, -70, 0), note="front tub, left half")
add("housing_right", housing_r, "anthracite", "housing", (30, -70, 0), note="front tub, right half")

# splice plates that join the halves inside (top and bottom)
for i, zc in enumerate((ZH1 - WALL - 6, ZH0 + WALL + 6)):
    sp = box(XS - 30, XS + 30, YF + FRONT + 8, YF + FRONT + 11, zc - 5, zc + 5)
    add(f"splice_{i}", sp, "white", "housing", (0, -20, 0), note="joins the halves")

# side panel insert (print in black) + small red label
insert = box(SIDE_X0 + 0.2, SIDE_X1 - 0.2, YF - 0.2, YF + 1.5, WIN_Z0 + 0.2, WIN_Z0 + DISP_H - 0.2)
insert -= cyl_y(BTN_D / 2 + 0.3, YF - 1, YF + 3, SIDE_CX, BTN_Z)
# speaker-style slots under the button
for k in range(5):
    insert -= box(SIDE_CX - 16, SIDE_CX + 16, YF - 1, YF + 0.6, BTN_Z - 34 - k * 6, BTN_Z - 32 - k * 6)
add("side_insert", insert, "black", "housing", (30, -120, 0), note="print in black")
label = box(SIDE_CX - 14, SIDE_CX + 14, YF - 0.8, YF + 0.01, WIN_Z0 + 8, WIN_Z0 + 14)
add("label", label, "red", "housing", (30, -130, 0), note="print in red")

# button: ring + cap (a 24 mm momentary push button)
btn_ring = cyl_y(BTN_D / 2 + 2.5, YF - 1.6, YF - 0.2, SIDE_CX, BTN_Z) - cyl_y(
    BTN_D / 2 - 0.5, YF - 3, YF + 1, SIDE_CX, BTN_Z
)
add("button_ring", btn_ring, "steel", "electronics", (30, -140, 0), printed=False)
btn_cap = cyl_y(BTN_D / 2 - 1, YF - 2.4, YF + 2, SIDE_CX, BTN_Z)
add("button_cap", btn_cap, "button", "electronics", (30, -140, 0), printed=False)
btn_body = cyl_y(11, YF + FRONT, YF + FRONT + 22, SIDE_CX, BTN_Z)
add("button_body", btn_body, "black_plastic", "electronics", (30, 40, 0), printed=False)

# ================================ ROOF ===========================================
roof = box(XH0 - 3, XH1 + 5, YF - 5, YB + BACK_T + 3, ZH1, ZH1 + 6)
roof = fillet(roof.edges().filter_by(Axis.Z), 4)
for nx in (XH0 + 70, XH1 - 70):
    roof += cyl_z(6, ZH1 + 6, ZH1 + 12, nx, 0)
    roof += Pos(nx, 0, ZH1 + 12) * scale(Sphere(6), by=(1, 1, 0.5))
roof_l = roof & box(XH0 - 10, XS, -100, 100, ZH1 - 1, ZH1 + 30)
roof_r = roof & box(XS, XH1 + 10, -100, 100, ZH1 - 1, ZH1 + 30)
add("roof_left", roof_l, "anthracite", "housing", (-30, 0, 90), note="rain cap, left half")
add("roof_right", roof_r, "anthracite", "housing", (30, 0, 90), note="rain cap, right half")

# ================================ BACK COVER =====================================
back = box(XH0, XH1, YB, YB + BACK_T, ZH0, ZH1)
back = fillet(back.edges().filter_by(Axis.Y), R_EDGE)
for bx, bz in boss_pts:
    back -= cyl_y(1.7, YB - 1, YB + BACK_T + 1, bx, bz)
# vent slots
for x0 in list(range(int(XH0 + 30), int(XS - 20), 14)) + list(range(int(XS + 20), int(XH1 - 30), 14)):
    for zc in (ZH0 + 26, ZH1 - 26):
        back -= box(x0, x0 + 5, YB - 1, YB + BACK_T + 1, zc - 9, zc + 9)
back_l = back & box(XH0 - 1, XS, YB - 1, YB + 5, ZH0 - 1, ZH1 + 1)
back_r = back & box(XS, XH1 + 1, YB - 1, YB + 5, ZH0 - 1, ZH1 + 1)
add("back_left", back_l, "anthracite", "back", (-30, 190, 0), note="back cover (or 3 mm plywood/ABS sheet)")
add("back_right", back_r, "anthracite", "back", (30, 190, 0), note="back cover (or 3 mm plywood/ABS sheet)")

# ================================ DISPLAY ========================================
POSTS = [(-55, -55), (55, -55), (-55, 55), (55, 55)]
for i in range(N_PANELS):
    cx = WIN_X0 + PANEL / 2 + i * PANEL
    pnl = box(cx - PANEL / 2, cx + PANEL / 2, PANEL_FRONT_Y, PANEL_BACK_Y, WIN_Z0, WIN_Z0 + DISP_H)
    # stiffening ribs on the back of the plastic frame
    for dz in (-40, 0, 40):
        pnl += box(cx - PANEL / 2 + 6, cx + PANEL / 2 - 6, PANEL_BACK_Y, PANEL_BACK_Y + 2, WIN_CZ + dz - 1, WIN_CZ + dz + 1)
    add(f"panel_{i}", pnl, "black_plastic", "display", (0, 0, 0), printed=False, note="P2.5 64x64 HUB75")
    posts = None
    spacers = None
    for px, pz in POSTS:
        p = cyl_y(3, PANEL_BACK_Y, PANEL_BACK_Y + 6, cx + px, WIN_CZ + pz)
        posts = p if posts is None else posts + p
        s = cyl_y(4.5, PANEL_BACK_Y + 6, YB, cx + px, WIN_CZ + pz) - cyl_y(1.7, PANEL_BACK_Y, YB + 1, cx + px, WIN_CZ + pz)
        spacers = s if spacers is None else spacers + s
    add(f"panel_posts_{i}", posts, "steel", "display", (0, 0, 0), printed=False)
    add(f"spacers_{i}", spacers, "white", "display", (0, 110, 0), note="spacers: back cover screws into the panel posts")
    # HUB75 in / out connectors and the power connector
    for j, dx in enumerate((-30, 30)):
        con = box(cx + dx - 10, cx + dx + 10, PANEL_BACK_Y, PANEL_BACK_Y + 9, WIN_CZ - 4.5, WIN_CZ + 4.5)
        add(f"hub75_{i}_{j}", con, "black_plastic", "display", (0, 0, 0), printed=False)
    pwr = box(cx - 6, cx + 6, PANEL_BACK_Y, PANEL_BACK_Y + 7, WIN_CZ + 22, WIN_CZ + 30)
    add(f"panel_power_{i}", pwr, "red_plastic", "display", (0, 0, 0), printed=False)

acrylic = box(WIN_X0 - 4, WIN_X0 + DISP_W + 4, YF + FRONT, YF + FRONT + ACRYLIC, WIN_Z0 - 4, WIN_Z0 + DISP_H + 4)
add("acrylic", acrylic, "smoked", "display", (0, -40, 0), printed=False, note="3 mm smoked acrylic 328 x 168")

# ribbon cable panel 0 OUT -> panel 1 IN
x_out = WIN_X0 + PANEL / 2 + 30
x_in = WIN_X0 + PANEL + PANEL / 2 - 30
ribbon = box(x_out - 8, x_in + 8, PANEL_BACK_Y + 9, PANEL_BACK_Y + 10.2, WIN_CZ - 4, WIN_CZ + 4)
add("ribbon", ribbon, "ribbon", "electronics", (0, 60, 0), printed=False)

# ESP32-S3 HUB75 board (e.g. Adafruit MatrixPortal S3, 65 x 51 mm) on the IN connector
mp_cx, mp_cz = WIN_X0 + PANEL / 2 - 30, WIN_CZ
mp_y = PANEL_BACK_Y + 10
mp = box(mp_cx - 32.5, mp_cx + 32.5, mp_y, mp_y + 1.6, mp_cz - 25.5, mp_cz + 25.5)
add("esp32_board", mp, "pcb", "electronics", (0, 60, 0), printed=False, note="ESP32-S3 HUB75 driver board")
module = box(mp_cx - 9, mp_cx + 9, mp_y + 1.6, mp_y + 4.6, mp_cz - 2, mp_cz + 22)
add("esp32_module", module, "steel", "electronics", (0, 60, 0), printed=False)
usb = box(mp_cx - 34, mp_cx - 26, mp_y + 1.6, mp_y + 4.8, mp_cz - 5, mp_cz + 5)
add("esp32_usb", usb, "steel", "electronics", (0, 60, 0), printed=False)
term = box(mp_cx + 18, mp_cx + 30, mp_y + 1.6, mp_y + 9, mp_cz - 20, mp_cz - 10)
add("esp32_terminal", term, "green_plastic", "electronics", (0, 60, 0), printed=False)

# 5 V wires: pole -> cable hole -> board terminal and panel power plugs
zc_mid = (ZH0 + ZH1) / 2
wires_r = cyl_x(1.3, XH0 + WALL, mp_cx + 24, mp_y + 13, zc_mid + 2)
wires_r += cyl_z(1.3, mp_cz - 15, zc_mid + 2, mp_cx + 24, mp_y + 13)
wires_b = cyl_x(1.3, XH0 + WALL, mp_cx + 22, mp_y + 16, zc_mid - 2)
wires_b += cyl_z(1.3, mp_cz - 15, zc_mid - 2, mp_cx + 22, mp_y + 16)
for i in range(N_PANELS):
    cx = WIN_X0 + PANEL / 2 + i * PANEL
    wires_r += cyl_x(1.3, mp_cx + 24, cx + 2, mp_y + 13, WIN_CZ + 26)
    wires_r += cyl_y(1.3, PANEL_BACK_Y + 7, mp_y + 13, cx + 2, WIN_CZ + 26)
wires_r += cyl_z(1.3, zc_mid + 2, WIN_CZ + 26, mp_cx + 24, mp_y + 13)
add("wires_5v", wires_r, "wire_red", "electronics", (0, 60, 0), printed=False)
add("wires_gnd", wires_b, "wire_black", "electronics", (0, 60, 0), printed=False)
# button wires
bw = cyl_y(0.9, YF + FRONT + 22, mp_y + 22, SIDE_CX, BTN_Z)
bw += cyl_x(0.9, mp_cx + 10, SIDE_CX, mp_y + 22, BTN_Z)
bw += cyl_z(0.9, mp_cz + 20, BTN_Z, mp_cx + 10, mp_y + 22)
add("wires_button", bw, "wire_yellow", "electronics", (0, 60, 0), printed=False)

# ================================ POLE + MOUNT ===================================
pole = cyl_z(POLE_R, BASE_H - SOCKET, POLE_TOP) - cyl_z(POLE_R - 2, BASE_H - SOCKET - 1, POLE_TOP + 1)
add("pole", pole, "alu", "pole", (0, 0, 0), printed=False, note=f"40 mm tube, {POLE_TOP - BASE_H + SOCKET:.0f} mm long")
cap = cyl_z(POLE_R + 0.6, POLE_TOP, POLE_TOP + 4) + Pos(0, 0, POLE_TOP + 4) * scale(Sphere(POLE_R + 0.6), by=(1, 1, 0.35))
cap = cap & box(-30, 30, -30, 30, POLE_TOP, POLE_TOP + 20)
add("pole_cap", cap, "alu_printed", "pole", (0, 0, 60), note="print in silver")

mount = box(POLE_R - 4, XH0, -19, 19, ZH0 + 6, ZH1 - 6)
mount = fillet(mount.edges().filter_by(Axis.Z), 3)
for z0 in (ZH0, ZH1 - 24):
    mount += cyl_z(POLE_R + 6, z0, z0 + 24)
mount -= cyl_z(POLE_R + 0.3, ZH0 - 1, ZH1 + 1)
mount -= cyl_x(6, POLE_R - 10, XH0 + 1, 0, (ZH0 + ZH1) / 2)
add("mount", mount, "lightgrey", "pole", (0, 0, 0), note="slides down the pole, grub screws")

# ================================ BASE ===========================================
for i in range(N_TILES):
    x0 = BASE_X0 + i * TILE_W
    t = box(x0 + 0.5, x0 + TILE_W - 0.5, -BASE_D / 2, BASE_D / 2, 0, BASE_H)
    t = fillet(t.edges().filter_by(Axis.X).group_by(Axis.Z)[-1], 1.5)
    # paving joints
    for k in range(1, 3):
        t -= box(x0 - 1, x0 + TILE_W + 1, -BASE_D / 2 + 34 + k * 48 - 0.6, -BASE_D / 2 + 34 + k * 48 + 0.6, BASE_H - 1, BASE_H + 1)
    t -= box(x0 + TILE_W / 2 - 0.6, x0 + TILE_W / 2 + 0.6, -BASE_D / 2 + 34, BASE_D / 2 + 1, BASE_H - 1, BASE_H + 1)
    # pocket for the white tactile strip
    t -= box(x0 - 1, x0 + TILE_W + 1, -BASE_D / 2 + 6, -BASE_D / 2 + 30, BASE_H - 2, BASE_H + 1)
    if x0 <= 0 < x0 + TILE_W:
        t -= cyl_z(POLE_R + 0.3, BASE_H - SOCKET, BASE_H + 1)
        t -= cyl_y(4, 0, BASE_D / 2 + 1, 0, 10)  # DC jack channel to the back
    add(f"base_tile_{i}", t, "concrete", "base", ((i - 1.5) * 25, 0, -60), note="fill with sand / steel washers")
    strip = box(x0 + 0.7, x0 + TILE_W - 0.7, -BASE_D / 2 + 6.3, -BASE_D / 2 + 29.7, BASE_H - 2, BASE_H - 0.6)
    for r in range(4):
        y0 = -BASE_D / 2 + 8 + r * 5.6
        strip += box(x0 + 0.7, x0 + TILE_W - 0.7, y0, y0 + 2.6, BASE_H - 0.6, BASE_H + 1.2)
    add(f"tactile_{i}", strip, "white", "base", ((i - 1.5) * 25, -30, -40), note="print in white")

# ================================ EXPORT =========================================
STL.mkdir(parents=True, exist_ok=True)
meta = []
for p in parts:
    path = STL / f"{p['name']}.stl"
    export_stl(p["shape"], str(path), tolerance=0.05, angular_tolerance=0.15)
    bb = p["shape"].bounding_box()
    size = [round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)]
    meta.append({k: v for k, v in p.items() if k != "shape"} | {"size": size, "stl": str(path.relative_to(ROOT))})

params = dict(
    DISP_W=DISP_W, DISP_H=DISP_H, WIN_X0=WIN_X0, WIN_Z0=WIN_Z0, PANEL_FRONT_Y=PANEL_FRONT_Y, YF=YF, YB=YB,
    XH0=XH0, XH1=XH1, ZH0=ZH0, ZH1=ZH1, HW=HW, HH=HH, HD=HD, BACK_T=BACK_T, BASE_X0=BASE_X0,
    BASE_X1=BASE_X0 + N_TILES * TILE_W, BASE_D=BASE_D, BASE_H=BASE_H, POLE_TOP=POLE_TOP, POLE_D=POLE_D,
    SIDE_CX=SIDE_CX, BTN_Z=BTN_Z, XS=XS,
)
(OUT / "parts.json").write_text(json.dumps({"params": params, "parts": meta}, indent=1))

print(f"{len(parts)} parts -> {STL}")
print(f"housing {HW:.0f} x {HH:.0f} x {HD + BACK_T:.0f} mm, screen {DISP_W:.0f} x {DISP_H:.0f} mm")
print(f"total height {POLE_TOP + 10:.0f} mm, base {N_TILES * TILE_W:.0f} x {BASE_D:.0f} mm")
for m in meta:
    if m["printed"]:
        print(f"  print  {m['name']:<16} {m['size']}")
