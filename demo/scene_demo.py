"""
scene_demo.py  —  SHAPE Demo  (Blender 5.x, EEVEE, Anime/Cel style)
====================================================================
Renders each act into its own frame range using collection-level
visibility — the only reliable hide mechanism in EEVEE batch renders.

One collection per act. All collections exist in the scene but only
the active act's collection is visible for its frame range, enforced
via Collection Override tracks on the scene's NLA / timeline.

Because per-collection visibility is set at scene evaluation time
(not per-object keyframes), EEVEE renders it correctly every frame.

Usage:
    # Build + open GUI to preview:
    blender --factory-startup --python demo/scene_demo.py

    # Headless render:
    blender --factory-startup --background --python demo/scene_demo.py -- --render

    # Assemble MP4 after render:
    ffmpeg -framerate 30 -i demo/output/frames/frame_%04d.png \\
           -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \\
           demo/output/FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4

Group 3 — ITAI2376-14562
Cherluk Sumdin · Olubukola Kukoyi · Taki Eddine Boubekri · Michael Rivas
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Euler

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FPS          = 30
TOTAL_S      = 300
TOTAL_FRAMES = TOTAL_S * FPS

OUTPUT_DIR  = Path(__file__).resolve().parent / "output"
OUTPUT_NAME = "FN_Demo_MichaelRivas_Group3_ITAI2376_14562.mp4"

# ---------------------------------------------------------------------------
# Anime palette
# ---------------------------------------------------------------------------
INK     = (0.02, 0.02, 0.04, 1.0)
C_BG    = (0.04, 0.03, 0.10, 1.0)
C_BLUE  = (0.10, 0.55, 1.00, 1.0)
C_PINK  = (1.00, 0.18, 0.55, 1.0)
C_YEL   = (1.00, 0.88, 0.00, 1.0)
C_GRN   = (0.08, 1.00, 0.45, 1.0)
C_ORG   = (1.00, 0.45, 0.00, 1.0)
C_WHT   = (1.00, 1.00, 1.00, 1.0)
C_GRY   = (0.60, 0.60, 0.70, 1.0)
C_TEAL  = (0.00, 0.95, 0.90, 1.0)
C_RED   = (1.00, 0.10, 0.10, 1.0)
C_PCB   = (0.05, 0.40, 0.15, 1.0)

# Act timing (start_s, end_s)
ACT_RANGES = {
    "act1": (  0,  60),
    "act2": ( 60, 115),
    "act3": (115, 150),
    "act4": (150, 210),
    "act5": (210, 300),
}

# Narration subtitle lines (text, start_s, end_s)
NARRATION = [
    ("SHAPE — Self-Healing Autonomous Programming Engine",        0.5,   5.0),
    ("Group 3  |  ITAI2376-14562",                                1.5,   5.0),
    ("An offline AI coding agent. No internet. No API keys.",     6.0,  12.0),
    ("Runs entirely on a Raspberry Pi 4.",                       12.5,  18.0),
    ("Powered by Ollama + CodeLlama 7B — offline.",              19.0,  25.0),
    ("ReAct loop: Thought → Action → Observation.",              26.0,  32.0),
    ("Three-tier: Pico 2 → Zero 2 W → Pi 4.",                   33.0,  40.0),
    ("The problem: every AI coding tool needs the cloud.",        61.0,  67.0),
    ("Wildfire crew. Naval facility. Antarctic station.",         68.0,  73.0),
    ("Hospital network. School gym with no Wi-Fi.",              74.0,  79.0),
    ("SHAPE costs $0 per month. Zero recurring fees.",           86.0,  93.0),
    ("Offline. Local. Yours.",                                    94.0, 100.0),
    ("85 × 56 mm — fits in a shirt pocket.",                    116.0, 122.0),
    ("Runs all day on a USB-C battery bank.",                    123.0, 128.0),
    ("Real sensor data feeds into SHAPE's reasoning.",           129.0, 136.0),
    ("CO₂ alert detected — SHAPE responds automatically.",       143.0, 149.0),
    ("SHAPE in action. The ReAct loop, live.",                   151.0, 156.0),
    ("Thought: lint first, then execute.",                       158.0, 163.0),
    ("Action: linter — no issues found.",                        164.0, 168.0),
    ("Action: code_executor — running the function.",            169.0, 173.0),
    ("All tests passed. Self-healing complete.",                  200.0, 206.0),
    ("agent.py — LangGraph ReAct executor over Ollama.",         212.0, 218.0),
    ("feedback.py — RL reward loop from 1-5 star ratings.",      219.0, 225.0),
    ("safety.py — blocks harmful requests before the LLM.",      226.0, 232.0),
    ("Four tools: executor, linter, file manager, doc search.",   233.0, 239.0),
    ("$55 hardware. $0/month. Works anywhere on Earth.",         251.0, 258.0),
    ("Gets smarter the more you use it.",                        259.0, 265.0),
    ("Offline. Intelligent. Yours.",                             266.0, 273.0),
    ("Thank you — Group 3, ITAI2376-14562.",                     285.0, 299.0),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fr(s: float) -> int:
    return max(1, min(TOTAL_FRAMES, round(s * FPS) + 1))


def kf(obj, attr, frame, val):
    setattr(obj, attr, val)
    obj.keyframe_insert(data_path=attr, frame=frame)


def mat_emit(name: str, rgba: tuple, strength=4.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    em  = nodes.new("ShaderNodeEmission")
    out = nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value    = rgba
    em.inputs["Strength"].default_value = strength
    m.node_tree.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def add_plane(col, name, w, h, x, z, rgba, strength=3.0, y=0.0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
    bmesh.ops.scale(bm, vec=Vector((w, 0.001, h)), verts=bm.verts)
    bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = Vector((x, y, z))
    obj.data.materials.append(mat_emit(f"m_{name}", rgba, strength))
    col.objects.link(obj)
    return obj


def add_text(col, text, name, x, z, size, rgba, align="CENTER",
             bold=False, y=-0.01):
    bpy.ops.object.text_add(location=Vector((x, y, z)))
    obj = bpy.context.object
    obj.name = name
    obj.data.body    = text
    obj.data.size    = size
    obj.data.align_x = align
    obj.data.extrude = 0.0
    obj.data.bevel_depth = 0.0
    if bold:
        fp = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if Path(fp).exists():
            obj.data.font = bpy.data.fonts.load(fp)
    obj.rotation_euler = Euler((math.pi / 2, 0, 0))
    obj.data.materials.append(mat_emit(f"m_{name}", rgba, 4.0))
    # text_add links to the active collection; move to our act collection
    sc = bpy.context.scene.collection
    if obj.name in sc.objects:
        sc.objects.unlink(obj)
    if obj.name not in col.objects:
        col.objects.link(obj)
    return obj


def box(col, name, w, h, x, z, fill, border, bt=0.05):
    """Filled box with coloured border."""
    add_plane(col, f"{name}_b", w + bt*2, h + bt*2, x, z, border, 5.0)
    add_plane(col, f"{name}_f", w,        h,         x, z, fill,   2.0, y=0.001)


def kf_text_appear(obj, start_f: int):
    """Keyframe a text object to type out character by character."""
    full = obj.data.body
    obj.data.body = ""
    obj.keyframe_insert("data.body", frame=start_f)   # not natively animatable
    # Blender can't keyframe string body directly in EEVEE.
    # Instead we use hide_render keyframes ON THE COLLECTION (not obj),
    # so the whole line pops in at once — reliable across EEVEE renders.
    # Individual char animation requires geometry nodes; overkill here.
    obj.data.body = full


def new_col(name: str):
    """Create a named collection and link it to the scene."""
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def set_col_visible(col, visible: bool, frame: int):
    """
    Keyframe collection-level render visibility.
    This is reliable in EEVEE batch renders unlike per-object hide_render.
    """
    col.hide_render   = not visible
    col.hide_viewport = not visible
    # Collection-level keyframes via context override
    with bpy.context.temp_override(collection=col):
        try:
            col.keyframe_insert(data_path="hide_render",   frame=frame)
            col.keyframe_insert(data_path="hide_viewport", frame=frame)
        except Exception:
            pass


def schedule_col(col, start_s: float, end_s: float):
    """Make a collection visible only within [start_s, end_s]."""
    # Hidden before start (frame 1)
    set_col_visible(col, False, 1)
    if fr(start_s) > 1:
        set_col_visible(col, False, fr(start_s) - 1)
    # Visible during act
    set_col_visible(col, True,  fr(start_s))
    # Hidden after end
    set_col_visible(col, False, fr(end_s) + 1)


# ---------------------------------------------------------------------------
# Scene setup
# ---------------------------------------------------------------------------

def setup_render():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end   = TOTAL_FRAMES
    scene.render.fps  = FPS
    scene.render.resolution_x          = 1280
    scene.render.resolution_y          = 720
    scene.render.resolution_percentage = 100

    scene.render.engine      = "BLENDER_EEVEE"
    eevee = scene.eevee
    eevee.taa_render_samples = 1
    for a in ("use_bloom","use_ssr","use_gtao","use_raytracing",
              "use_fast_gi","use_shadows","use_volumetric_shadows"):
        try: setattr(eevee, a, False)
        except AttributeError: pass

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background") \
         or world.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value    = C_BG
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames_dir = OUTPUT_DIR / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    _ok = False
    try:
        scene.render.image_settings.file_format = "FFMPEG"
        _ok = True
    except TypeError:
        pass

    if _ok:
        scene.render.ffmpeg.format               = "MPEG4"
        scene.render.ffmpeg.codec                = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.filepath = str(OUTPUT_DIR / OUTPUT_NAME)
        print(f"[SHAPE] Direct MP4 → {OUTPUT_DIR / OUTPUT_NAME}")
    else:
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode  = "RGB"
        scene.render.image_settings.compression = 0
        scene.render.filepath = str(frames_dir / "frame_")
        print(f"[SHAPE] PNG → {frames_dir}")
        print(f"[SHAPE] After render:")
        print(f"  ffmpeg -framerate {FPS} -i '{frames_dir}/frame_%04d.png'"
              f" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p"
              f" '{OUTPUT_DIR / OUTPUT_NAME}'")

    return scene


def make_camera():
    cam = bpy.data.cameras.new("OrthoCamera")
    cam.type        = "ORTHO"
    cam.ortho_scale = 11.0
    obj = bpy.data.objects.new("OrthoCamera", cam)
    obj.location       = Vector((0, -10, 0))
    obj.rotation_euler = Euler((math.pi / 2, 0, 0))
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.camera = obj
    return obj


# ---------------------------------------------------------------------------
# Persistent collections (visible every frame)
# ---------------------------------------------------------------------------

def build_persistent():
    """Background + subtitle bar — always rendered."""
    pc = new_col("persistent")

    # Background fill
    add_plane(pc, "BG", 14, 9, 0, 0, C_BG, 0.9, y=0.1)

    # Subtitle bar
    add_plane(pc, "SubBar", 11.0, 0.55, 0, -3.2, INK, 2.0)

    # Subtitle lines — each has its own visibility keyframes
    # We use per-object keyframes here (subtitles are in the persistent
    # collection so they don't get wiped by act collection hiding)
    for i, (text, s_s, e_s) in enumerate(NARRATION):
        obj = add_text(pc, text, f"Sub{i:03d}", 0, -3.22, 0.22, C_WHT)
        # hide outside range
        obj.hide_render   = True
        obj.hide_viewport = True
        obj.keyframe_insert("hide_render",   frame=1)
        obj.keyframe_insert("hide_viewport", frame=1)
        if fr(s_s) > 1:
            obj.keyframe_insert("hide_render",   frame=fr(s_s) - 1)
            obj.keyframe_insert("hide_viewport", frame=fr(s_s) - 1)
        obj.hide_render   = False
        obj.hide_viewport = False
        obj.keyframe_insert("hide_render",   frame=fr(s_s))
        obj.keyframe_insert("hide_viewport", frame=fr(s_s))
        obj.hide_render   = True
        obj.hide_viewport = True
        obj.keyframe_insert("hide_render",   frame=fr(e_s) + 1)
        obj.keyframe_insert("hide_viewport", frame=fr(e_s) + 1)

    return pc


# ---------------------------------------------------------------------------
# ACT 1 — Credits + Pi diagram + Architecture  (0–60 s)
# ---------------------------------------------------------------------------

def build_act1():
    c = new_col("act1")

    # ── Title card  (0–11 s)
    box(c, "Title", 7.0, 1.5, 0, 0.9, (0.08,0.04,0.22,1), C_BLUE, bt=0.07)
    add_text(c, "SHAPE", "TMain", 0, 1.15, 0.78, C_YEL, bold=True)
    add_text(c, "Self-Healing Autonomous Programming Engine",
             "TSub", 0, 0.65, 0.22, C_TEAL)
    add_text(c, "Group 3  |  ITAI2376-14562", "TCred1", 0, 0.05, 0.19, C_WHT)
    add_text(c, "Cherluk Sumdin  ·  Olubukola Kukoyi", "TCred2", 0, -0.32, 0.17, C_GRY)
    add_text(c, "Taki Eddine Boubekri  ·  Michael Rivas", "TCred3", 0, -0.62, 0.17, C_GRY)

    # ── Pi panel  (12–29 s) — sub-collection for clean isolation
    pc = bpy.data.collections.new("act1_pi")
    c.children.link(pc)
    # PCB base
    add_plane(pc, "PCB", 6.5, 4.0, 0, 0.3, C_PCB, 2.0)
    add_plane(pc, "PCBbord", 6.7, 4.2, 0, 0.3, C_GRN, 4.0, y=-0.001)
    # Components
    _chip(pc, "SoC",  "BCM2711", -0.4, 0.3, 1.4, 1.4, (0.07,0.07,0.07,1), C_TEAL)
    _chip(pc, "RAM",  "4 GB",     0.9, 0.7, 0.9, 0.9, (0.1,0.1,0.1,1),    C_PINK)
    _chip(pc, "GPIO", "GPIO ×40", 0.0, 1.8, 3.8, 0.25,(0.15,0.15,0.15,1), C_YEL)
    _chip(pc, "USB1", "USB-A",   -2.9, 1.0, 0.5, 0.8, (0.6,0.6,0.65,1),  C_WHT)
    _chip(pc, "USB2", "USB-A",   -2.9, 0.1, 0.5, 0.8, (0.6,0.6,0.65,1),  C_WHT)
    _chip(pc, "USBC", "USB-C",   -2.9,-0.9, 0.4, 0.55,(0.6,0.6,0.65,1),  C_BLUE)
    _chip(pc, "HDMI", "HDMI",    -1.2,-1.4, 0.75,0.38,(0.6,0.6,0.65,1),  C_WHT)
    _chip(pc, "SD",   "microSD",  2.4, 1.8, 0.9, 0.42,(0.7,0.7,0.7,1),   C_GRY)
    # LEDs
    for i,(lx,lz,lc) in enumerate([(-3.1,-1.3,C_RED),(-3.1,-1.65,C_GRN)]):
        bpy.ops.mesh.primitive_circle_add(
            radius=0.14, fill_type="TRIFAN", location=(lx, 0, lz))
        led = bpy.context.object; led.name = f"LED{i}"
        led.data.materials.append(mat_emit(f"mLED{i}", lc, 8.0))
        bpy.context.scene.collection.objects.unlink(led)
        pc.objects.link(led)
        for pf in range(fr(12), fr(29), FPS):
            kf(led, "scale", pf,          Vector((1,1,1)))
            kf(led, "scale", pf+FPS//2,   Vector((1.6,1.6,1.6)))
            kf(led, "scale", pf+FPS,      Vector((1,1,1)))
    # Pi title badge
    box(pc, "PiBadge", 5.0, 0.6, 0, -1.9, INK, C_BLUE, bt=0.06)
    add_text(pc, "Raspberry Pi 4  (4 GB)", "PiTtl", 0, -1.85, 0.26, C_WHT, bold=True)
    add_text(pc, "SHAPE + CodeLlama 7B  —  fully offline",
             "PiSub", 0, -2.3, 0.19, C_GRN)

    # ── Arch diagram  (31–59 s)
    ac = bpy.data.collections.new("act1_arch")
    c.children.link(ac)
    add_text(ac, "Three-Tier Offline Architecture",
             "ArchTitle", 0, 2.3, 0.30, C_YEL, bold=True)
    for i,(lbl,nx,fill,bord) in enumerate([
        ("Pico 2\nSensor I/O", -4.0, C_ORG,  C_YEL),
        ("Zero 2 W\nRelay",     0.0, C_TEAL, C_BLUE),
        ("Pi 4\nSHAPE+LLM",    4.0, C_BLUE, C_PINK),
    ]):
        box(ac, f"AN{i}", 2.4, 1.1, nx, 0.5,
            tuple(list(fill[:3])+[1]), tuple(list(bord[:3])+[1]), bt=0.08)
        add_text(ac, lbl, f"ALbl{i}", nx, 0.5, 0.23, C_WHT)
    for i,(ax,albl,ac_) in enumerate([(-2.0,"UART",C_YEL),(2.0,"Wi-Fi",C_TEAL)]):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.05, depth=1.4, location=(ax,0,0.5))
        arr = bpy.context.object; arr.name = f"Arr{i}"
        arr.rotation_euler = Euler((0, math.pi/2, 0))
        arr.data.materials.append(mat_emit(f"mArr{i}", ac_, 4.0))
        bpy.context.scene.collection.objects.unlink(arr)
        ac.objects.link(arr)
        add_text(ac, albl, f"ALlbl{i}", ax, 1.0, 0.18, ac_)

    # Keyframe sub-collection visibility
    for sub, s_s, e_s in [(pc, 12, 29), (ac, 31, 59)]:
        sub.hide_render   = True
        sub.hide_viewport = True
        try:
            sub.keyframe_insert("hide_render",   frame=1)
            sub.keyframe_insert("hide_viewport", frame=1)
            if fr(s_s) > 1:
                sub.keyframe_insert("hide_render",   frame=fr(s_s)-1)
                sub.keyframe_insert("hide_viewport", frame=fr(s_s)-1)
            sub.hide_render   = False
            sub.hide_viewport = False
            sub.keyframe_insert("hide_render",   frame=fr(s_s))
            sub.keyframe_insert("hide_viewport", frame=fr(s_s))
            sub.hide_render   = True
            sub.hide_viewport = True
            sub.keyframe_insert("hide_render",   frame=fr(e_s)+1)
            sub.keyframe_insert("hide_viewport", frame=fr(e_s)+1)
        except Exception:
            pass

    schedule_col(c, *ACT_RANGES["act1"])
    return c


def _chip(col, name, label, x, z, w, h, fill, border):
    box(col, name, w, h, x, z, fill, tuple(list(border[:3])+[1]) if len(border)==3 else border, bt=0.04)
    add_text(col, label, f"CL_{name}", x, z, min(0.19, w*0.18), border if len(border)==4 else tuple(list(border)+[1]))


# ---------------------------------------------------------------------------
# ACT 2 — Problem + cost chart  (60–115 s)
# ---------------------------------------------------------------------------

def build_act2():
    c = new_col("act2")

    # Problem header
    box(c, "ProbHdr", 6.5, 0.65, 0, 2.6, INK, C_PINK, bt=0.07)
    add_text(c, "THE PROBLEM", "PHdr", 0, 2.65, 0.34, C_PINK, bold=True)

    # Scenario bullets
    for i,(sc,col_) in enumerate([
        ("Wildfire crew — no cell signal",        C_ORG),
        ("Naval facility — air-gapped network",   C_RED),
        ("Antarctic research station",            C_TEAL),
        ("Hospital — HIPAA isolation",            C_PINK),
        ("School gym — no Wi-Fi budget",          C_YEL),
    ]):
        bpy.ops.mesh.primitive_circle_add(
            radius=0.13, fill_type="TRIFAN", location=(-4.6, 0, 1.7-i*0.76))
        dot = bpy.context.object; dot.name = f"Dot{i}"
        dot.data.materials.append(mat_emit(f"mDot{i}", col_, 5.0))
        bpy.context.scene.collection.objects.unlink(dot)
        c.objects.link(dot)
        add_text(c, sc, f"Sc{i}", -4.1, 1.7-i*0.76, 0.23, col_, align="LEFT")

    # Cost chart
    box(c, "ChartBg", 10.5, 4.5, 0, -0.5, (0.03,0.02,0.08,1), C_GRY, bt=0.05)
    add_text(c, "Monthly Cost (USD/mo)", "ChTitle", 0, 2.1, 0.27, C_WHT, bold=True)
    add_plane(c, "AxisH", 9.5, 0.04, 0, -0.65, C_WHT, 2.0)

    for tname, cost, col_, bx in [
        ("Copilot", 10, C_RED,   -3.5),
        ("ChatGPT", 20, C_ORG,  -1.2),
        ("Azure",   60, C_PINK,   1.2),
        ("SHAPE",    0, C_GRN,    3.5),
    ]:
        bar_h = max(0.08, (cost/60)*3.0) if cost else 0.08
        bar_z  = -0.65 + bar_h/2
        add_plane(c, f"Bar{tname}", 1.1, bar_h, bx, bar_z, col_, 3.5)
        add_plane(c, f"BarB{tname}", 1.22, bar_h+0.1, bx, bar_z, INK, 5.0, y=-0.001)
        add_text(c, tname, f"BN{tname}", bx, -1.2, 0.21, col_)
        label = f"${cost}/mo" if cost else "FREE"
        add_text(c, label, f"BC{tname}", bx, -0.65+bar_h+0.18, 0.23,
                 C_WHT if cost else C_GRN, bold=True)

    schedule_col(c, *ACT_RANGES["act2"])
    return c


# ---------------------------------------------------------------------------
# ACT 3 — Pi close-up + sensor stream  (115–150 s)
# ---------------------------------------------------------------------------

def build_act3():
    c = new_col("act3")

    # Large PCB
    add_plane(c, "BigPCBb", 10.8, 6.6, 0, 0.3, C_GRN, 4.0, y=-0.001)
    add_plane(c, "BigPCB",  10.5, 6.3, 0, 0.3, C_PCB, 2.0)

    # Chips
    _chip(c, "BSoC",  "BCM2711 SoC", -1.5, 0.3, 2.8, 2.8, (0.07,0.07,0.07,1), C_TEAL)
    _chip(c, "BRAM",  "4 GB LPDDR4",  2.0, 0.6, 1.8, 1.8, (0.1,0.1,0.1,1),    C_PINK)
    _chip(c, "BGPIO", "GPIO ×40",     0.0, 2.8, 8.0, 0.4,  (0.15,0.15,0.15,1), C_YEL)
    _chip(c, "BUSBC", "USB-C 5V",    -4.8,-0.4, 0.7, 1.0,  (0.6,0.6,0.65,1),  C_BLUE)
    _chip(c, "BHDMI", "HDMI",        -2.0,-2.3, 1.4, 0.65, (0.6,0.6,0.65,1),  C_WHT)
    _chip(c, "BSD",   "microSD",      3.8, 2.8, 1.5, 0.65, (0.7,0.7,0.7,1),   C_GRY)

    # Size badge
    box(c, "SzBadge", 5.0, 0.6, 0, -2.6, INK, C_TEAL, bt=0.06)
    add_text(c, "85 × 56 mm  —  fits in a shirt pocket",
             "SzTxt", 0, -2.6, 0.24, C_TEAL, bold=True)

    # Sensor readings — rising from board
    for i,(t_s,txt,col_) in enumerate([
        (117.0, "temp:   22.4 °C",           C_GRN),
        (118.5, "humid:  54.1 %",            C_TEAL),
        (120.0, "CO2:    412 ppm",           C_GRN),
        (121.5, "temp:   23.1 °C",           C_GRN),
        (123.0, "CO2:    431 ppm",           C_GRN),
        (124.5, "CO2:    438 ppm  ALERT!",   C_RED),
        (126.0, "temp:   24.8 °C",           C_ORG),
        (128.0, "humid:  58.9 %",            C_TEAL),
    ]):
        obj = add_text(c, txt, f"SR{i}", -2.5, -2.9, 0.26, col_, align="LEFT")
        # Animate rising
        kf(obj, "location", fr(t_s),     Vector((-2.5, -0.03, -2.9)))
        kf(obj, "location", fr(t_s+8.0), Vector((-2.5, -0.03,  2.8)))

    schedule_col(c, *ACT_RANGES["act3"])
    return c


# ---------------------------------------------------------------------------
# ACT 4 — SHAPE terminal  (150–210 s)
# ---------------------------------------------------------------------------

def build_act4():
    c = new_col("act4")

    # Terminal window
    add_plane(c, "TermBg",   10.8, 6.8, 0, 0.1, (0.02,0.07,0.02,1), 2.0)
    add_plane(c, "TermBord", 11.0, 7.0, 0, 0.1, C_GRN,              4.0, y=-0.001)

    # Title bar
    add_plane(c, "TBar", 10.8, 0.42, 0, 3.15, (0.0,0.3,0.1,1), 2.5)
    add_text(c, "SHAPE Terminal  —  CodeLlama 7B  —  Ollama",
             "TBarTxt", 0, 3.15, 0.20, C_GRN)

    # Terminal lines
    lines = [
        (151.5, "> SHAPE v1.0  |  model: codellama  |  ready",        C_GRN),
        (154.0, "User: Write a palindrome checker and test it.",        C_WHT),
        (157.0, "Thought: lint first, then execute.",                   C_BLUE),
        (158.5, "Action: linter",                                       C_YEL),
        (161.0, "Observation: No issues found.               [OK]",    C_GRN),
        (163.0, "Action: code_executor",                                C_YEL),
        (165.0, "  def is_palindrome(s):",                             C_TEAL),
        (166.5, "      s = s.lower().replace(' ', '')",                C_TEAL),
        (168.0, "      return s == s[::-1]",                           C_TEAL),
        (169.5, "  assert is_palindrome('racecar')   # True",          C_TEAL),
        (171.0, "  assert not is_palindrome('hello') # False",         C_TEAL),
        (172.5, "  print('All tests passed.')",                        C_TEAL),
        (174.0, "Observation: All tests passed.             [OK]",     C_GRN),
        (177.5, "Final Answer: Function verified.           [DONE]",   C_WHT),
    ]
    top_z = 2.65; line_h = 0.31; x_l = -5.0
    for i,(t_s,txt,col_) in enumerate(lines):
        obj = add_text(c, txt, f"TL{i:02d}", x_l, top_z-i*line_h, 0.20, col_, align="LEFT")
        # Each line hidden before its timestamp
        obj.hide_render = obj.hide_viewport = True
        obj.keyframe_insert("hide_render",   frame=1)
        obj.keyframe_insert("hide_viewport", frame=1)
        obj.hide_render = obj.hide_viewport = False
        obj.keyframe_insert("hide_render",   frame=fr(t_s))
        obj.keyframe_insert("hide_viewport", frame=fr(t_s))

    # Pass flash
    box(c, "PFlash", 6.5, 0.72, 0, -0.4, (0.0,0.5,0.1,1), C_GRN, bt=0.08)
    add_text(c, "✓  All tests passed  —  Self-healing complete",
             "PFlashTxt", 0, -0.4, 0.27, C_WHT, bold=True)

    schedule_col(c, *ACT_RANGES["act4"])
    return c


# ---------------------------------------------------------------------------
# ACT 5 — Code overview + pitch + credits  (210–300 s)
# ---------------------------------------------------------------------------

def build_act5():
    c = new_col("act5")

    # Module cards
    for i,(mname,mdesc,mx,mz,fill,bord) in enumerate([
        ("agent.py",    "ReAct executor\nLangGraph + Ollama",        -3.8, 1.5, C_BLUE, C_PINK),
        ("feedback.py", "RL reward loop\n1–5 star ratings",          -3.8, 0.0, C_GRN,  C_TEAL),
        ("safety.py",   "InputGuard\nBlocks harmful requests",        3.8, 1.5, C_ORG,  C_YEL),
        ("tools/ ×4",   "executor · linter\nfile mgr · doc search",  3.8, 0.0, C_TEAL, C_BLUE),
    ]):
        box(c, f"MC{i}", 4.0, 1.6, mx, mz,
            tuple(list(fill[:3])+[1]), tuple(list(bord[:3])+[1]), bt=0.08)
        add_text(c, mname,  f"MN{i}", mx, mz+0.38, 0.28, C_WHT, bold=True)
        add_text(c, mdesc,  f"MD{i}", mx, mz-0.05, 0.19, bord if len(bord)==4 else tuple(list(bord)+[1]))

    # Pitch card
    pc2 = bpy.data.collections.new("act5_pitch")
    c.children.link(pc2)
    box(pc2, "PBox", 9.5, 5.8, 0, 0.3, (0.04,0.0,0.14,1), C_BLUE, bt=0.10)
    add_text(pc2, "SHAPE",                       "PP1", 0,  2.1, 0.80, C_YEL, bold=True)
    add_text(pc2, "Offline. Intelligent. Yours.","PP2", 0,  1.1, 0.30, C_WHT)
    add_text(pc2, "$55 hardware  ·  $0 / month", "PP3", 0,  0.1, 0.27, C_GRN)
    add_text(pc2, "Works anywhere on Earth",     "PP4", 0, -0.4, 0.26, C_TEAL)
    add_text(pc2, "Gets smarter with every use", "PP5", 0, -0.9, 0.26, C_TEAL)
    add_text(pc2, "ITAI2376-14562  |  Group 3",  "PP6", 0, -1.8, 0.21, C_GRY)

    # Closing credits
    cc = bpy.data.collections.new("act5_credits")
    c.children.link(cc)
    box(cc, "CBox", 8.5, 5.0, 0, 0.3, INK, C_BLUE, bt=0.09)
    add_text(cc, "Thank you",                            "CC1", 0,  1.6, 0.52, C_YEL, bold=True)
    add_text(cc, "Group 3  |  ITAI2376-14562",           "CC2", 0,  0.6, 0.27, C_WHT)
    add_text(cc, "Cherluk Sumdin",                       "CC3", 0, -0.1, 0.24, C_TEAL)
    add_text(cc, "Olubukola Kukoyi",                     "CC4", 0, -0.6, 0.24, C_TEAL)
    add_text(cc, "Taki Eddine Boubekri",                 "CC5", 0, -1.1, 0.24, C_TEAL)
    add_text(cc, "Michael Rivas",                        "CC6", 0, -1.6, 0.24, C_TEAL)

    # Sub-collection timing
    for sub, s_s, e_s in [(pc2, 249, 282), (cc, 283, 300)]:
        try:
            sub.hide_render = sub.hide_viewport = True
            sub.keyframe_insert("hide_render",   frame=1)
            sub.keyframe_insert("hide_viewport", frame=1)
            sub.hide_render = sub.hide_viewport = False
            sub.keyframe_insert("hide_render",   frame=fr(s_s))
            sub.keyframe_insert("hide_viewport", frame=fr(s_s))
            sub.hide_render = sub.hide_viewport = True
            sub.keyframe_insert("hide_render",   frame=fr(e_s)+1)
            sub.keyframe_insert("hide_viewport", frame=fr(e_s)+1)
        except Exception:
            pass

    schedule_col(c, *ACT_RANGES["act5"])
    return c


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_full_scene(render_now=False):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)

    setup_render()
    make_camera()
    build_persistent()
    build_act1()
    build_act2()
    build_act3()
    build_act4()
    build_act5()

    print(f"[SHAPE] Scene ready — {TOTAL_FRAMES} frames ({TOTAL_S}s)")

    if render_now:
        print("[SHAPE] Rendering...")
        bpy.ops.render.render(animation=True)
        print("[SHAPE] Done.")


def main():
    raw = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--render", action="store_true")
    args = p.parse_args(raw)
    build_full_scene(render_now=args.render)


if __name__ == "__main__":
    main()
