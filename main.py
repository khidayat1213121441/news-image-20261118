#!/usr/bin/env python3
"""The World in One Image - 18 November 2026.

A procedural front page drawn by a pure-Python software 3D renderer.
Standard library only: no network, no installed packages, deterministic
(two runs write identical bytes).

Design: a newspaper front page. The hero is a 3D globe (a shaded sphere
mesh with a latitude/longitude graticule) carrying glowing pins on the
day's four hot spots - the Gulf, Shenzhen, Kerch and Congo - beside the
two lead headlines. Below it, three extruded 3D story blocks (the Kerch
bridge, the Senate 56-44 bars, the Voyager 1 probe) and a news ticker.

The day's news (Wednesday 18 November 2026), as reported that day:
  1. U.S. jets strike a Revolutionary Guards missile site on Qeshm
     Island; Iran answers with drone attacks on U.S. bases in Kuwait
     (Ali Al Salem) and Bahrain.
  2. Xi Jinping meets Vladimir Putin in Shenzhen at APEC, a day before
     their trilateral summit with Donald Trump; both denounce trade
     protectionism and Western sanctions.
  3. Ukraine hits the Kerch Bridge again; part of the road span
     collapses into the strait.
  4. Democrat Mary Peltola wins Alaska's Senate race; Democrats take
     a 56-44 Senate majority.
  5. Voyager 1 reaches one light-day from Earth - 16 billion miles,
     a distance no human-made object has crossed before.
  Also: the U.S. loses its measles elimination status after 26 years
  (5,412 cases); the Ebola outbreak in DR Congo passes 11,000 cases;
  cold stalks the tents of Gaza's displaced.

Run: MAKEFUN_OUTPUT_DIR=. python3 main.py  ->  writes entry.png
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# --- palette ---------------------------------------------------------------
PAPER = (246, 241, 227)
INK = (26, 26, 26)
NAVY = (22, 35, 63)
NAVY_LT = (38, 56, 92)
GOLD = (201, 162, 39)
GOLD_LT = (226, 190, 90)
RED = (179, 38, 30)
BLUE = (29, 78, 216)
TEAL = (15, 118, 110)
ORANGE = (214, 110, 30)
GREY = (107, 114, 128)
GREY_LT = (200, 196, 182)
OCEAN = (43, 108, 176)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# --- framebuffer -----------------------------------------------------------
fb = bytearray(W * H * 3)


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def px(x, y, c):
    x = int(x)
    y = int(y)
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        fb[i] = c[0]
        fb[i + 1] = c[1]
        fb[i + 2] = c[2]


def blend_px(x, y, c, a):
    """Alpha-blend colour c (alpha a in 0..1) over the pixel."""
    x = int(x)
    y = int(y)
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        fb[i] = int(fb[i] + (c[0] - fb[i]) * a)
        fb[i + 1] = int(fb[i + 1] + (c[1] - fb[i + 1]) * a)
        fb[i + 2] = int(fb[i + 2] + (c[2] - fb[i + 2]) * a)


def fill_rect(x0, y0, x1, y1, c):
    x0 = _clip(int(x0), 0, W)
    x1 = _clip(int(x1), 0, W)
    y0 = _clip(int(y0), 0, H)
    y1 = _clip(int(y1), 0, H)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(c) * (x1 - x0)
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        fb[i:i + len(row)] = row


def shade(c, f):
    return (_clip(int(c[0] * f), 0, 255),
            _clip(int(c[1] * f), 0, 255),
            _clip(int(c[2] * f), 0, 255))


def mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def hline(x0, x1, y, c):
    if x1 < x0:
        x0, x1 = x1, x0
    for x in range(int(x0), int(x1) + 1):
        px(x, y, c)


def vline(x, y0, y1, c):
    if y1 < y0:
        y0, y1 = y1, y0
    for y in range(int(y0), int(y1) + 1):
        px(x, y, c)


def line(x0, y0, x1, y1, c):
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        px(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def fill_circle(cx, cy, r, c):
    cx = int(cx)
    cy = int(cy)
    r = int(r)
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        hline(cx - dx, cx + dx, cy + dy, c)


def glow_circle(cx, cy, r, c):
    """Soft halo: concentric blended rings, bright core."""
    for k in range(4, 0, -1):
        blend_px_ring(cx, cy, r * k, c, 0.10)
    fill_circle(cx, cy, r, c)
    fill_circle(cx, cy, max(1, r // 2), WHITE)


def blend_px_ring(cx, cy, r, c, a):
    cx = int(cx)
    cy = int(cy)
    r = int(r)
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        for x in range(cx - dx, cx + dx + 1):
            blend_px(x, cy + dy, c, a)


def fill_tri(p0, p1, p2, c):
    pts = sorted([p0, p1, p2], key=lambda p: p[1])
    (x0, y0), (x1, y1), (x2, y2) = pts
    if y0 == y2:
        return
    for y in range(int(math.ceil(y0)), int(math.floor(y2)) + 1):
        if y < y1:
            xa = x0 + (x1 - x0) * (y - y0) / (y1 - y0) if y1 != y0 else x0
            xb = x0 + (x2 - x0) * (y - y0) / (y2 - y0)
        else:
            xa = x1 + (x2 - x1) * (y - y1) / (y2 - y1) if y2 != y1 else x1
            xb = x0 + (x2 - x0) * (y - y0) / (y2 - y0)
        hline(min(xa, xb), max(xa, xb), y, c)


def write_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw.extend(fb[y * stride:(y + 1) * stride])
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)

# --- 5x7 bitmap font -------------------------------------------------------
# Each glyph: 7 rows of 5 bits ('#' = on).
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ";": (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    "(": ("...##", "..#..", ".#...", ".#...", ".#...", "..#..", "...##"),
    ")": ("##...", "..#..", "...#.", "...#.", "...#.", "..#..", "##..."),
    "&": (".##..", "#..#.", "#..#.", ".#...", "#.#.#", "#..#.", ".##.#"),
    "/": ("....#", "....#", "...#.", "...#.", "..#..", ".#...", "#...."),
    "%": ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.#.#", "#..##"),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    '"': (".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."),
    "$": ("..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "*": (".....", ".#.#.", "..#..", "#####", "..#..", ".#.#.", "....."),
    "=": (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    "<": ("...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."),
    ">": (".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."),
}

CHAR_W = 6  # 5 pixels + 1 spacing, times scale


def text_w(s, scale):
    return len(s) * CHAR_W * scale - scale


def draw_glyph(x, y, ch, scale, c):
    g = FONT.get(ch)
    if g is None:
        return
    for r in range(7):
        row = g[r]
        for col in range(5):
            if row[col] == "#":
                fill_rect(x + col * scale, y + r * scale,
                          x + (col + 1) * scale, y + (r + 1) * scale, c)


def draw_text(x, y, s, scale, c, align="left"):
    s = s.upper()
    w = text_w(s, scale)
    if align == "center":
        x -= w // 2
    elif align == "right":
        x -= w
    for ch in s:
        draw_glyph(x, y, ch, scale, c)
        x += CHAR_W * scale
    return w


def wrap_text(s, max_w, scale):
    """Greedy word wrap; returns list of lines."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_w(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_para(x, y, s, scale, c, max_w, lh=None, align="left"):
    lh = lh if lh is not None else 7 * scale + 4 * scale // 2
    for ln in wrap_text(s, max_w, scale):
        draw_text(x, y, ln, scale, c, align=align)
        y += lh
    return y

# --- tiny 3D engine --------------------------------------------------------
# Right-handed: x east, y north (up on screen is -y after projection),
# z toward the viewer. Yaw turns around y, pitch around x, roll around z.

def rot_y(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x * c + z * s, y, -x * s + z * c)


def rot_x(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x, y * c - z * s, y * s + z * c)


def rot_z(p, a):
    x, y, z = p
    c, s = math.cos(a), math.sin(a)
    return (x * c - y * s, x * s + y * c, z)


def rotate(p, yaw, pitch, roll):
    return rot_z(rot_x(rot_y(p, yaw), pitch), roll)


def project(p, cx, cy, focal, scale):
    x, y, z = p
    d = focal / (focal + z)
    return (cx + x * scale * d, cy - y * scale * d, z)


def tri_normal(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / n, ny / n, nz / n)


LIGHT = (-0.45, 0.62, 0.64)
_LN = math.sqrt(sum(v * v for v in LIGHT))
LIGHT = tuple(v / _LN for v in LIGHT)


def lambert(n):
    d = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
    return 0.52 + 0.48 * max(0.0, d)


def draw_mesh(tris, base, cx, cy, focal, scale):
    """tris: list of (a, b, c) 3D points. Painter-sorted, lambert-shaded."""
    items = []
    for a, b, c in tris:
        n = tri_normal(a, b, c)
        if n[2] <= 0.02:
            continue  # backface
        depth = (a[2] + b[2] + c[2]) / 3.0
        items.append((depth, a, b, c, lambert(n)))
    items.sort(key=lambda it: it[0])
    for _, a, b, c, f in items:
        pa = project(a, cx, cy, focal, scale)
        pb = project(b, cx, cy, focal, scale)
        pc = project(c, cx, cy, focal, scale)
        fill_tri((pa[0], pa[1]), (pb[0], pb[1]), (pc[0], pc[1]),
                 shade(base, f))


def draw_polyline_3d(pts, c, cx, cy, focal, scale):
    prev = None
    for p in pts:
        q = project(p, cx, cy, focal, scale)
        if q[2] > 0.02:
            if prev is not None:
                line(prev[0], prev[1], q[0], q[1], c)
            prev = q
        else:
            prev = None


def draw_box3d(center, size, yaw, pitch, roll, top_c, front_c, side_c,
               cx, cy, focal, scale):
    """A shaded rectangular box. center/size in 3D units."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = rotate((sx * hx, sy * hy, sz * hz), yaw, pitch, roll)
                corners.append((center[0] + p[0], center[1] + p[1],
                                center[2] + p[2]))
    # corners index: sx,sy,sz -> (sx+1)*4 + (sy+1)*2 + (sz+1)
    def ci(sx, sy, sz):
        return ((sx + 1) // 2) * 4 + ((sy + 1) // 2) * 2 + (sz + 1) // 2

    faces = [
        ([ci(-1, 1, -1), ci(1, 1, -1), ci(1, 1, 1), ci(-1, 1, 1)], top_c),
        ([ci(-1, -1, 1), ci(1, -1, 1), ci(1, 1, 1), ci(-1, 1, 1)], front_c),
        ([ci(1, -1, -1), ci(1, -1, 1), ci(1, 1, 1), ci(1, 1, -1)], side_c),
        ([ci(-1, -1, -1), ci(-1, -1, 1), ci(-1, 1, 1), ci(-1, 1, -1)],
         shade(side_c, 0.75)),
    ]
    items = []
    for idxs, col in faces:
        pts = [corners[i] for i in idxs]
        n = tri_normal(pts[0], pts[1], pts[2])
        if n[2] <= 0.0:
            continue
        depth = sum(p[2] for p in pts) / 4.0
        items.append((depth, pts, col))
    items.sort(key=lambda it: it[0])
    for _, pts, col in items:
        pp = [project(p, cx, cy, focal, scale) for p in pts]
        fill_tri((pp[0][0], pp[0][1]), (pp[1][0], pp[1][1]),
                 (pp[2][0], pp[2][1]), col)
        fill_tri((pp[0][0], pp[0][1]), (pp[2][0], pp[2][1]),
                 (pp[3][0], pp[3][1]), col)


# --- the globe ---------------------------------------------------------------
def latlon_to_xyz(lat_deg, lon_deg, r=1.0):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    return (r * math.cos(lat) * math.sin(lon),
            r * math.sin(lat),
            r * math.cos(lat) * math.cos(lon))


def draw_globe(cx, cy, r_px, yaw, pitch):
    """Shaded sphere + graticule + hotspot pins. Returns pin screen points."""
    focal = 3.2
    scale = r_px
    # sphere mesh
    tris = []
    step = 10
    for la0 in range(-90, 90, step):
        la1 = la0 + step
        for lo0 in range(-180, 180, step):
            lo1 = lo0 + step
            a = rotate(latlon_to_xyz(la0, lo0), yaw, pitch, 0)
            b = rotate(latlon_to_xyz(la0, lo1), yaw, pitch, 0)
            c = rotate(latlon_to_xyz(la1, lo1), yaw, pitch, 0)
            d = rotate(latlon_to_xyz(la1, lo0), yaw, pitch, 0)
            tris.append((a, b, c))
            tris.append((a, c, d))
    draw_mesh(tris, OCEAN, cx, cy, focal, scale)
    # graticule: latitude circles
    grat = (168, 205, 232)
    for la in range(-60, 61, 30):
        pts = [rotate(latlon_to_xyz(la, lo), yaw, pitch, 0)
               for lo in range(-180, 181, 6)]
        draw_polyline_3d(pts, grat, cx, cy, focal, scale)
    for lo in range(-180, 180, 30):
        pts = [rotate(latlon_to_xyz(la, lo), yaw, pitch, 0)
               for la in range(-90, 91, 6)]
        draw_polyline_3d(pts, grat, cx, cy, focal, scale)
    # rim
    rim_pts = []
    for k in range(73):
        ang = 2 * math.pi * k / 72
        rim_pts.append((math.cos(ang), math.sin(ang), 0.0))
    draw_polyline_3d(rim_pts, NAVY, cx, cy, focal, scale)
    return focal, scale


def globe_pin(lat, lon, yaw, pitch, cx, cy, focal, scale, color, r=7):
    p = rotate(latlon_to_xyz(lat, lon), yaw, pitch, 0)
    if p[2] <= 0.05:
        return None
    q = project(p, cx, cy, focal, scale)
    glow_circle(q[0], q[1], r, color)
    return (q[0], q[1])

# --- scene -------------------------------------------------------------------
def paper_texture():
    """Deterministic print speckle (fixed seed, no time, no randomness)."""
    s = 123456789
    for _ in range(900):
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        x = s % W
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        y = s % H
        blend_px(x, y, (120, 110, 85), 0.05)


def masthead():
    fill_rect(24, 24, 1000, 112, NAVY)
    draw_text(512, 38, "THE WORLD IN ONE IMAGE", 4, WHITE, align="center")
    fill_rect(48, 80, 976, 83, GOLD)
    draw_text(512, 90, "WEDNESDAY - 18 NOVEMBER 2026", 2, GOLD_LT,
              align="center")


def hero():
    # globe drop shadow
    for k in range(3):
        blend_px_ring(250, 540, 190 - k * 8, (60, 50, 30), 0.05)
    focal, scale = draw_globe(250, 345, 175, math.radians(-50),
                              math.radians(-12))
    pins = [
        (27.0, 52.0, RED, "GULF"),
        (22.5, 114.0, GOLD, "SHENZHEN"),
        (45.3, 36.5, ORANGE, "KERCH"),
        (-2.0, 23.0, TEAL, "CONGO"),
    ]
    for lat, lon, col, _name in pins:
        globe_pin(lat, lon, math.radians(-50), math.radians(-12),
                  250, 345, focal, scale, col)
    # legend under the globe
    lx = 78
    for _lat, _lon, col, name in pins:
        fill_circle(lx + 5, 556, 5, col)
        draw_text(lx + 15, 552, name, 1, INK)
        lx += 15 + text_w(name, 1) + 22

    # right column: lead stories
    x = 470
    draw_text(x, 140, "THE GULF ERUPTS", 2, RED)
    draw_text(x, 166, "GULF IN FLAMES", 5, INK)
    fill_rect(x, 212, 1000, 215, GOLD)
    draw_para(x, 230,
              "U.S. jets strike a missile site on Qeshm Island. Iran "
              "answers with drones on U.S. bases in Kuwait and Bahrain.",
              2, INK, 530)
    fill_rect(x, 306, 1000, 308, GREY_LT)
    draw_text(x, 326, "XI MEETS PUTIN IN SHENZHEN", 3, INK)
    draw_para(x, 362,
              "A day before the trilateral with Trump, the two leaders "
              "denounce protectionism and sanctions at APEC.",
              2, INK, 530)
    fill_rect(x, 436, 1000, 438, GREY_LT)
    draw_text(x, 456, "IN BRIEF", 2, NAVY)
    draw_para(x, 482,
              "Israel: parliament elects Matan Kahana speaker. "
              "Gaza: cold stalks the tents of the displaced. "
              "Myanmar: junta reviews its ASEAN ties.",
              2, GREY, 530)


def panel_frame(x0, y0, x1, y1):
    fill_rect(x0 + 5, y0 + 6, x1 + 5, y1 + 6, (203, 196, 178))
    fill_rect(x0, y0, x1, y1, (253, 250, 242))
    for xx in (x0, x1 - 1):
        vline(xx, y0, y1, NAVY)
    for yy in (y0, y1 - 1):
        hline(x0, x1, yy, NAVY)


def bridge_icon(x0, x1, y0):
    """Kerch bridge: deck with a collapsed middle span, 3D-shaded."""
    deck_y = y0 + 40
    # towers
    fill_rect(x0 + 52, y0 + 8, x0 + 60, deck_y, NAVY)
    fill_rect(x1 - 60, y0 + 8, x1 - 52, deck_y, NAVY)
    # deck side (darker, offset down = 3D thickness)
    pts = [(x0 + 16, deck_y), (x0 + 108, deck_y), (x0 + 132, deck_y + 30),
           (x0 + 156, deck_y), (x1 - 16, deck_y)]
    for i in range(len(pts) - 1):
        line(pts[i][0], pts[i][1] + 7, pts[i + 1][0], pts[i + 1][1] + 7,
             shade(NAVY, 0.55))
    # deck top
    for i in range(len(pts) - 1):
        for t in range(5):
            line(pts[i][0], pts[i][1] + t, pts[i + 1][0],
                 pts[i + 1][1] + t, NAVY_LT if i != 2 else RED)
    # blast star at the break
    bx, by = x0 + 132, deck_y + 30
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        line(bx, by, bx + 12 * math.cos(a), by + 12 * math.sin(a), RED)
    # water
    for k in range(3):
        yy = deck_y + 52 + k * 9
        for xx in range(x0 + 16, x1 - 16, 14):
            line(xx, yy, xx + 7, yy + 3, TEAL)


def senate_bars(x0, x1, y0):
    """Two extruded 3D bars: Democrats 56 (blue), Republicans 44 (red)."""
    base_y = y0 + 100
    cy = base_y
    draw_box3d((0, 40, 0), (34, 80, 34), 0.6, -0.35, 0,
               shade(BLUE, 1.25), BLUE, shade(BLUE, 0.6),
               x0 + 88, cy, 400.0, 1.0)
    draw_box3d((72, 31, 0), (34, 62, 34), 0.6, -0.35, 0,
               shade(RED, 1.25), RED, shade(RED, 0.6),
               x0 + 88, cy, 400.0, 1.0)
    hline(x0 + 40, x1 - 40, base_y + 1, INK)
    draw_text(x0 + 88, base_y - 102, "56", 2, BLUE, align="center")
    draw_text(x0 + 154, base_y - 96, "44", 2, RED, align="center")
    draw_text(x0 + 88, base_y + 6, "DEM", 1, INK, align="center")
    draw_text(x0 + 154, base_y + 6, "GOP", 1, INK, align="center")


def voyager_icon(x0, x1, y0):
    """Voyager 1 probe on a dotted trajectory away from Earth."""
    ex, ey = x0 + 42, y0 + 88
    fill_circle(ex, ey, 12, BLUE)
    fill_circle(ex - 4, ey - 4, 5, shade(BLUE, 1.4))
    draw_text(ex, ey + 16, "EARTH", 1, INK, align="center")
    # dotted trajectory
    for k in range(12):
        t = k / 11.0
        tx = ex + t * 190
        ty = ey - t * 74 - 12 * math.sin(t * math.pi)
        fill_circle(tx, ty, 2, GOLD)
    # probe body: small 3D box + dish
    px0, py0 = x0 + 232, y0 + 18
    draw_box3d((0, 0, 0), (26, 14, 14), 0.6, -0.35, 0,
               shade(GOLD, 1.25), GOLD, shade(GOLD, 0.6),
               px0, py0 + 10, 400.0, 1.0)
    # dish: gold disc with dark rim, left of the body
    fill_circle(px0 - 20, py0 + 2, 9, GOLD_LT)
    for k in range(25):
        a = 2 * math.pi * k / 24
        px(px0 - 20 + 9 * math.cos(a), py0 + 2 + 9 * math.sin(a), INK)
    line(px0 - 12, py0 + 4, px0 + 2, py0 + 8, INK)
    line(px0 + 8, py0 - 2, px0 + 34, py0 - 22, INK)
    fill_circle(px0 + 36, py0 - 24, 3, RED)


def story_row():
    panels = [
        (24, 340, "KERCH BRIDGE", "BRIDGE DOWN",
         "Ukraine strike drops part of the span into the strait.", "bridge"),
        (354, 670, "THE SENATE", "PELTOLA WINS",
         "Democrats take Alaska - and the Senate, 56-44.", "senate"),
        (684, 1000, "DEEP SPACE", "ONE LIGHT-DAY",
         "Voyager 1, 16 billion miles from Earth.", "voyager"),
    ]
    for x0, x1, kicker, head, deck, kind in panels:
        panel_frame(x0, 570, x1, 810)
        draw_text(x0 + 16, 586, kicker, 2, RED)
        if kind == "bridge":
            bridge_icon(x0, x1, 606)
        elif kind == "senate":
            senate_bars(x0, x1, 606)
        else:
            voyager_icon(x0, x1, 606)
        draw_text(x0 + 16, 724, head, 3, INK)
        draw_para(x0 + 16, 758, deck, 2, INK, x1 - x0 - 32)


def ticker():
    fill_rect(24, 830, 1000, 900, NAVY)
    draw_text(48, 845,
              "MEASLES: U.S. LOSES ELIMINATION STATUS, 5,412 CASES",
              2, WHITE)
    draw_text(48, 868,
              "EBOLA: DRC PASSES 11,000 * GAZA: COLD IN THE TENTS",
              2, GOLD_LT)


def footer():
    draw_text(512, 922, "THE WORLD IN ONE IMAGE - 18 NOVEMBER 2026",
              2, INK, align="center")
    draw_text(512, 950, "DRAWN BY A PROGRAM - NO PHOTOGRAPH - MAKE.FUN",
              1, GREY, align="center")


def main():
    fill_rect(0, 0, W, H, PAPER)
    paper_texture()
    for d in (12, 13):
        hline(d, W - d, d, NAVY)
        hline(d, W - d, H - 1 - d, NAVY)
        vline(d, d, H - d, NAVY)
        vline(W - 1 - d, d, H - d, NAVY)
    masthead()
    hero()
    story_row()
    ticker()
    footer()
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "entry.png")
    write_png(path)
    print("wrote", path)


if __name__ == "__main__":
    main()
