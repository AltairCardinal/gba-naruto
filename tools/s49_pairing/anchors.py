"""The dense content anchor -- what the machine state says about a frame.

The judgment bench's anchor was thin: brightness, the display registers (with
only the **horizontal** camera) and the overlay's cell count.  It could say
"the camera moved" but not "which moment is this", because the vertical scroll
was unreadable and the overlay is empty in the middle of the original's walk.

This module reads the anchor straight out of the savestate next to each
frame, so it is both **denser** and **free of the probe**:

``camera``
    The two dimensional camera position: ``BG0..BG2`` horizontal *and*
    vertical scroll, masked to the nine bits the hardware keeps.

    The **map layer** is not the same background in the two ROMs: the
    original scrolls ``BG1`` (with ``BG0`` following it), the remake scrolls
    ``BG2``.  The comparable camera is therefore the vertical scroll of the
    background layer that actually scrolls -- the one that takes the most
    distinct values over the walk, which is measured, not assumed.

``registers``
    ``DISPCNT`` and the four background control registers.

``overlay``
    The set of **non blank** overlay families, the lit cell count and a digest
    of the whole family map.

``screen``
    The brightness facts of the frame itself: non black share, mean RGB,
    the number of distinct colours and the share of "bright paper" pixels in
    the lower half (the dialogue box).

``acting``
    The acting unit pointer.  Both ROMs keep it, but their numbering differs
    by one (the original counts from 1, the remake counts from 0), so it is
    a **per side phase index** and not a directly comparable number.

``scene``
    The machine readable scene class: ``fade`` (the screen is fading out),
    ``dialogue`` (the dialogue box is open) or ``map`` (the battlefield).
    This is the coarse moment key that is comparable across the two ROMs
    everywhere, including the parts of the walk where the camera is not.
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageChops

from . import savestate as savestate_module

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_fidelity_report import overlay as overlay_module  # noqa: E402
from s49_fidelity_report.pixels import outline_shades, screen_stats  # noqa: E402

# The acting unit pointer, found by the sweep search in ``tools/s49_pairing``
# (the byte whose value walks 1..9 while the units are introduced).
ACTING_OFFSET = {
    "original": 0x26A76,
    "remake": 0x0382C,
}
# The original counts the units from 1, the remake from 0.
ACTING_BASE = {
    "original": 1,
    "remake": 0,
}

ANCHOR_SCHEMA = "s49-pairing-anchor/1"

# A frame is a fade frame when less than this share of its pixels is lit.
FADE_LIMIT = 0.05
# The dialogue box: the share of "bright paper" pixels in this row band.
DIALOGUE_BAND = (96, 144)
DIALOGUE_BRIGHT_LIMIT = 0.50
# A lit frame with a big bright box is the *menu* scene, not a dialogue box:
# the remake's pre-battle screen is fully lit, a dialogue frame is not.
DIALOGUE_NON_BLACK_LIMIT = 0.95


def _bright_share(image: Image.Image) -> float:
    """The share of "bright paper" pixels in the lower band of the frame."""
    crop = image.crop((0, DIALOGUE_BAND[0], image.width, DIALOGUE_BAND[1]))
    red, green, blue = crop.split()
    mask = ImageChops.darker(
        ImageChops.darker(red.point(lambda value: 255 if value >= 200 else 0),
                          green.point(lambda value: 255 if value >= 200 else 0)),
        blue.point(lambda value: 255 if value >= 190 else 0))
    return sum(mask.histogram()[1:]) / (crop.width * crop.height)


def scene_of(screen: dict, bright_share: float) -> str:
    """The machine readable scene class of a frame."""
    if screen["non_black_fraction"] < FADE_LIMIT:
        return "fade"
    if (bright_share > DIALOGUE_BRIGHT_LIMIT
            and screen["non_black_fraction"] < DIALOGUE_NON_BLACK_LIMIT):
        return "dialogue"
    return "map"


def _overlay_grid(side: str, vram: bytes):
    if side == "original":
        return overlay_module.original_grid(vram), {
            "overlay_map": overlay_module.ORIGINAL_OVERLAY_OFFSET}
    grid, info = overlay_module.remake_grid(vram)
    return grid, info


def frame_anchor(side: str, frame_path: pathlib.Path,
                  state_path: pathlib.Path) -> dict:
    """The content anchor of one captured frame."""
    state = savestate_module.load(state_path)
    data = savestate_module.regions(state)
    registers = savestate_module.io_registers(data["io"])
    image = savestate_module.load_rgb(frame_path)
    screen = screen_stats(image)
    bright = _bright_share(image)
    grid, info = _overlay_grid(side, data["vram"])
    families = overlay_module.grid_counts(grid) if grid else {}
    non_blank = {name: count for name, count in families.items()
                  if name != "blank"}
    acting_offset = ACTING_OFFSET.get(side)
    acting = None
    if acting_offset is not None:
        raw = data["ewram"][acting_offset]
        acting = {"raw": raw, "index": raw - ACTING_BASE[side]}
    return {
        "frame": frame_path.name,
        "screen": screen,
        "bright_share": round(bright, 4),
        "scene": scene_of(screen, bright),
        "outline_shades": outline_shades(image, (112, 24, 144, 88)),
        "registers": {
            "dispcnt": registers["dispcnt"],
            "dispcnt_hex": f"0x{registers['dispcnt']:04X}",
            "bg_cnt": registers["bg_cnt"],
            "bg_hofs_raw": registers["bg_hofs_raw"],
            "bg_hofs": registers["bg_hofs"],
            "bg_vofs_raw": registers["bg_vofs_raw"],
            "bg_vofs": registers["bg_vofs"],
        },
        "camera": {
            "h": registers["bg_hofs"],
            "v": registers["bg_vofs"],
        },
        "overlay": {
            "map": info.get("overlay_map"),
            "lit_cells": overlay_module.lit_cells(grid) if grid else 0,
            "family_counts": families,
            "non_blank_families": sorted(non_blank),
            "family_digest": overlay_module.grid_digest(grid) if grid else "",
        },
        "acting": acting,
    }


def side_anchors(side: str, capture_dir: pathlib.Path) -> dict:
    """The content anchor of every captured frame of one side."""
    frames = {}
    for png in sorted(capture_dir.glob("step-*.png")):
        ss9 = png.with_suffix(".ss9")
        if not ss9.exists():
            continue
        frames[png.name] = frame_anchor(side, png, ss9)
    return {
        "schema": ANCHOR_SCHEMA,
        "side": side,
        "status": "ok" if frames else "empty",
        "frames": frames,
    }


def camera_layer(anchors: dict) -> int:
    """Which background layer carries the camera, measured from the walk.

    The original scrolls ``BG1`` (and ``BG0`` follows it), the remake scrolls
    ``BG2``: the two ROMs put the map on different layers.  The layer that
    takes the most distinct vertical scroll values over the walk is the one
    that moves, so it is measured instead of assumed.
    """
    distinct = [set() for _ in range(3)]
    for frame in anchors["frames"].values():
        for index, value in enumerate(frame["registers"]["bg_vofs"]):
            distinct[index].add(value)
    return max(range(3), key=lambda index: (len(distinct[index]), -index))


def camera_v(anchor: dict, layer: int) -> int:
    return anchor["registers"]["bg_vofs"][layer]


def camera_v_sequence(anchors: dict) -> list:
    """The camera vertical of every frame of a side, in capture order."""
    layer = camera_layer(anchors)
    return [camera_v(frame, layer) for frame in anchors["frames"].values()]
