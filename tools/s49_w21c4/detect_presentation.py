#!/usr/bin/env python3
"""Wave 21 / C4 -- when does the ORIGINAL draw the three things the remake
draws too early?

The three things (E3, ``notes/s49-fidelity/W20-E3-camera-mapping.md`` section
3.4):

    1. the move grid / range overlay (移動格子: the lattice + the coloured
       range cells),
    2. the red facing indicator (a small red triangle above the acting unit),
    3. the "SELECT 詳細" HUD (white text in the top right corner).

Everything is measured on the **original ROM's own** frames.  Two frame
sources are used:

* the **per-frame dense captures** (``build/w20-e3/dense/<window>/f###.png``,
  91 frames per window, three windows = 273 frames) recorded by E3 with
  ``tools/s49_w20e/dense_camera_curve.py`` -- these give the *timing*;
* the **settled beats** (``capture-original/step-##-A.png``) -- these give the
  phase level truth.

The detectors are **measured signatures**, not guesses:

``red_arrow``
    the facing indicator is exactly ``(255, 0, 0)``; a 4-connected component
    of >= 10 such pixels is the arrow (24 px, a 6x6 head).  One pixel strays
    are the unit's own red clothing detail and are ignored.

``move_grid``
    the overlay's own colours, read off the frame difference ``f077 -> f078``
    (the frame where the overlay disappears):

        move range (mint, the 移動格子 fill):
            (123,236,190) (138,252,200) (97,246,190) (91,226,185)
            (112,255,200) (107,221,180)
        attack range (orange):  (255,143,30)
        cursor     (yellow):     (255,226,30) (255,241,41)

    The lattice lines are painted by the *same* BG2 overlay layer (the
    original's BG2 tilemap carries the ``edge`` family together with the
    ``hatch`` family -- see ``tools/s49_rule_probe/overlay_ground_truth.py``),
    so "the overlay is drawn" and "the lattice is drawn" share the same
    interval.

``select_hud``
    the original's ``SELECT 詳細`` HUD is **pixel identical** to the remake's
    (original ``step-23-A.png`` and remake ``step-26-A.png`` both carry 140
    bright pixels in the box ``(193,13)-(231,22)``), so the detector is an
    exact template match against the original's own HUD crop.

Usage
-----
    python tools/s49_w21c4/detect_presentation.py \
        --dense  build/w20-e3/dense \
        --remake build/w20-e3/capture-remake \
        --original build/s49-package-w18/work/s49-report/capture-original \
        --out build/w21-c4/original-presentation-timing.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
from collections import Counter, deque

from PIL import Image

# --------------------------------------------------------------------------
# measured signatures
# --------------------------------------------------------------------------
RED_ARROW_RGB = (255, 0, 0)
RED_ARROW_MIN_PIXELS = 10

MOVE_MINT_RGB = frozenset({
    (123, 236, 190), (138, 252, 200), (97, 246, 190),
    (91, 226, 185), (112, 255, 200), (107, 221, 180),
})
ATTACK_ORANGE_RGB = frozenset({(255, 143, 30)})
CURSOR_YELLOW_RGB = frozenset({(255, 226, 30), (255, 241, 41)})
LATTICE_RGB = frozenset({(118, 159, 190), (97, 133, 154)})

# The "SELECT 詳細" HUD lives in this box; the template is cut from the
# original's own step-23-A (which carries it).
HUD_BOX = (190, 10, 236, 26)
HUD_TEMPLATE_SOURCE = "step-23-A.png"
HUD_TEMPLATE_STEP = 23


def load_rgb(path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def pixel_digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def red_clusters(image: Image.Image, minimum: int = RED_ARROW_MIN_PIXELS) -> list[dict]:
    """4-connected components of exactly (255, 0, 0)."""
    width, height = image.size
    px = image.load()
    seen = set()
    out = []
    for y in range(height):
        for x in range(width):
            if px[x, y] != RED_ARROW_RGB or (x, y) in seen:
                continue
            queue = deque([(x, y)])
            seen.add((x, y))
            component = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if (0 <= nx < width and 0 <= ny < height
                            and (nx, ny) not in seen
                            and px[nx, ny] == RED_ARROW_RGB):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            if len(component) >= minimum:
                xs = [p[0] for p in component]
                ys = [p[1] for p in component]
                out.append({"pixels": len(component),
                            "bbox": [min(xs), min(ys), max(xs), max(ys)]})
    return sorted(out, key=lambda c: c["bbox"])


def features(image: Image.Image, hud_template=None) -> dict:
    width, height = image.size
    px = image.load()
    counts = Counter(image.getdata())

    mint = sum(n for c, n in counts.items() if c in MOVE_MINT_RGB)
    orange = sum(n for c, n in counts.items() if c in ATTACK_ORANGE_RGB)
    yellow = sum(n for c, n in counts.items() if c in CURSOR_YELLOW_RGB)
    lattice = sum(n for c, n in counts.items() if c in LATTICE_RGB)

    x0, y0, x1, y1 = HUD_BOX
    hud_bright = 0
    for y in range(y0, min(y1, height)):
        for x in range(x0, min(x1, width)):
            if sum(px[x, y]) > 600:
                hud_bright += 1
    hud_diff = None
    if hud_template is not None:
        template_px = hud_template.load()
        hud_diff = 0
        for y in range(y0, min(y1, height)):
            for x in range(x0, min(x1, width)):
                if px[x, y] != template_px[x, y]:
                    hud_diff += 1

    arrows = red_clusters(image)
    return {
        "red_arrow_px": sum(a["pixels"] for a in arrows),
        "red_arrow_clusters": arrows,
        "mint_cell_px": mint,
        "yellow_cell_px": yellow,
        "orange_cell_px": orange,
        "lattice_px": lattice,
        "overlay_px": mint + yellow + orange,
        "hud_bright_px": hud_bright,
        "hud_template_diff": hud_diff,
    }


def flags(row: dict) -> dict:
    return {
        "move_grid": row["mint_cell_px"] > 0,
        "cursor_cell": row["yellow_cell_px"] > 0,
        "attack_range": row["orange_cell_px"] > 0,
        "red_arrow": row["red_arrow_px"] > 0,
        "select_hud": (row["hud_template_diff"] == 0
                       if row["hud_template_diff"] is not None
                       else row["hud_bright_px"] > 0),
        "hud_any": row["hud_bright_px"] > 0,
    }


def runs(values: list[bool]) -> list[list[int]]:
    out = []
    start = None
    for index, value in enumerate(values):
        if value and start is None:
            start = index
        elif not value and start is not None:
            out.append([start, index - 1])
            start = None
    if start is not None:
        out.append([start, len(values) - 1])
    return out


def frame_names(directory: pathlib.Path, prefix: str = "f") -> list[str]:
    return sorted(name for name in os.listdir(directory)
                  if name.startswith(prefix) and name.endswith(".png"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dense", type=pathlib.Path,
                        default=pathlib.Path(r"D:\Github\gba-naruto\build\w20-e3\dense"))
    parser.add_argument("--remake", type=pathlib.Path,
                        default=pathlib.Path(r"D:\Github\gba-naruto\build\w20-e3\capture-remake"))
    parser.add_argument("--original", type=pathlib.Path,
                        default=pathlib.Path(
                            r"D:\Github\gba-naruto\build\s49-package-w18\work\s49-report"
                            r"\capture-original"))
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    # the HUD template: cut from the original's own step-23-A
    template_source = args.original / HUD_TEMPLATE_SOURCE
    hud_template = load_rgb(template_source) if template_source.is_file() else None

    document = {
        "schema": "konoha.s49-original-presentation-timing.v1",
        "source": "original ROM (base.gba) -- dense per-frame captures + settled beats",
        "detectors": {
            "red_arrow": f"exact RGB {RED_ARROW_RGB}, 4-connected component >= "
                         f"{RED_ARROW_MIN_PIXELS} px",
            "move_grid": "mint cell colours "
                         f"{sorted(MOVE_MINT_RGB)} (the 移動格子 fill)",
            "cursor_cell": f"{sorted(CURSOR_YELLOW_RGB)}",
            "attack_range": f"{sorted(ATTACK_ORANGE_RGB)}",
            "lattice": f"{sorted(LATTICE_RGB)} (the BG2 'edge' family over grass)",
            "select_hud": f"exact template match in box {HUD_BOX}, template cut "
                          f"from the original's {HUD_TEMPLATE_SOURCE}",
        },
        "windows": {},
        "original_beats": {},
        "remake_beats": {},
    }

    # ---- 1. the original's per-frame dense windows ----------------------
    for entry in sorted(os.listdir(args.dense)):
        directory = args.dense / entry
        if not directory.is_dir():
            continue
        rows = []
        for name in frame_names(directory):
            image = load_rgb(directory / name)
            row = {"frame": name}
            row.update(features(image, hud_template))
            row["sha256"] = pixel_digest(image)
            rows.append(row)
        per_frame = [{**row, **flags(row)} for row in rows]
        document["windows"][entry] = {
            "frames": len(rows),
            "per_frame": per_frame,
            "presence_runs": {
                key: runs([row[key] for row in per_frame])
                for key in ("move_grid", "cursor_cell", "attack_range",
                            "red_arrow", "select_hud", "hud_any")
            },
        }

    # ---- 2. the original's settled beats --------------------------------
    for name in sorted(os.listdir(args.original)):
        if not name.endswith(".png"):
            continue
        image = load_rgb(args.original / name)
        row = {"frame": name}
        row.update(features(image, hud_template))
        row["sha256"] = pixel_digest(image)
        document["original_beats"][name] = {**row, **flags(row)}

    # ---- 3. the remake's settled beats (control) ------------------------
    for name in sorted(os.listdir(args.remake)):
        if not name.endswith(".png"):
            continue
        image = load_rgb(args.remake / name)
        row = {"frame": name}
        row.update(features(image, hud_template))
        row["sha256"] = pixel_digest(image)
        document["remake_beats"][name] = {**row, **flags(row)}

    # ---- 4. which dense frame equals which settled beat -----------------
    digest_index: dict[str, list[str]] = {}
    for entry, data in document["windows"].items():
        for row in data["per_frame"]:
            digest_index.setdefault(row["sha256"], []).append(f"{entry}/{row['frame']}")
    for side in ("original_beats", "remake_beats"):
        for name, row in document[side].items():
            row["dense_frames"] = digest_index.get(row["sha256"], [])

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=1)
        print(f"wrote {args.out}")

    for entry, data in document["windows"].items():
        print(f"{entry}: " + json.dumps(data["presence_runs"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
