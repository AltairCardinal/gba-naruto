#!/usr/bin/env python3
"""Rebuild the 「開始」 opening title's Butano sprite items, correctly.

Why this tool exists
--------------------
``tools/s49_opening_title/make_title_assets.py`` cuts the recovered 「始」
calligraphy into four cells with ``frame_cell()``::

    for y in range(min(height, cell_h - offset_y)):
        for x in range(min(width, cell_w - offset_x)):

Both upper bounds are written the wrong way round: the loop has to stop at
``min(height - offset_y, cell_h)`` and ``min(width - offset_x, cell_w)``.
With the shipped offsets the broken form gives a negative bound as soon as a
cell starts past column 32 or row 32, so the loop body never runs and the
cell comes out empty.  The three pieces that start past that point are
therefore fully transparent:

    battle_opening_title_shi_right   64x64  -> 4096 transparent pixels, 0 ink
    battle_opening_title_shi_bottom  128x32  -> 4096 transparent pixels, 0 ink
    battle_opening_title_shi_corner   64x32  -> 2048 transparent pixels, 0 ink

Only ``kai`` and ``shi_top`` (both with a zero offset) came out right, which
is why the title never appeared: 「始」 was missing its last six columns and
its last six rows.

The generator also could not write into the remake's ``graphics/`` directory
(it is another stream's), so this tool writes the items into a staging
directory and prints the copy command.  The piece table is read out of
``battle_opening_title.h`` so the cells and the offsets cannot drift apart
from the header the runtime places the sprites with.

Usage::

    python tools/s49_v3_dialogue/regenerate_title_assets.py \\
        --out build/s49-v3/title-assets
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

# The remake repository's shared indexed BMP writer (read only).
REMAKE_TOOLS = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\tools\butano")
if str(REMAKE_TOOLS) not in sys.path:
    sys.path.insert(0, str(REMAKE_TOOLS))

from indexed_bmp import write_4bpp_bmp  # noqa: E402

HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\battle_opening_title.h")
ART_DIR = REPO / "tools" / "s49_opening_title"
GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")

# The four opaque colours of the original's title, as 8 bit greys: the GBA's
# 5 bit values 4 / 13 / 22 / 31 expanded, so the sprite palette reproduces
# the original's colours exactly.
GREYS = [(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)]
TRANSPARENT = (255, 0, 255)

# The recovered art of each glyph, and the file of each animation phase.
GLYPH_ART = {
    "kai": ("kai.png", "kai-phase1.png"),
    "shi": ("shi.png", "shi-phase1.png"),
}

GLYPH_RE = re.compile(
    r"battle_opening_title_glyph\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)")
PIECE_DEF_RE = re.compile(
    r"static constexpr battle_opening_title_piece (\w+) =\s*\{\s*"
    r'"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}')
PIECES_RE = re.compile(
    r"std::array<battle_opening_title_piece,\s*(\d+)>\s*pieces\s*=\s*\{\{(.*?)\}\};",
    re.S)


def read_header(path: pathlib.Path) -> dict:
    """The glyph boxes and the piece table of the runtime's header."""
    text = path.read_text(encoding="utf-8")
    glyphs = [
        {"x": int(m[0]), "y": int(m[1]),
         "width": int(m[2]), "height": int(m[3])}
        for m in GLYPH_RE.findall(text)
    ]
    if len(glyphs) != 2:
        raise ValueError("the header does not hold two title glyphs")
    definitions = {
        name: {"item": item, "cell_width": int(width),
               "cell_height": int(height),
               "art_offset_x": int(offset_x),
               "art_offset_y": int(offset_y)}
        for name, item, width, height, offset_x, offset_y
        in PIECE_DEF_RE.findall(text)
    }
    match = PIECES_RE.search(text)
    if not match:
        raise ValueError("the header does not hold a piece table")
    order = re.findall(r"(\w+)", match.group(2))
    pieces = []
    for name in order:
        if name not in definitions:
            raise ValueError(f"the piece table names an unknown piece: {name}")
        pieces.append(definitions[name])
    return {"glyphs": glyphs, "pieces": pieces}


def snap_to_greys(pixels, path: pathlib.Path) -> list[int]:
    """Index the art with the four greys; drop every other opaque colour.

    An opaque pixel that is not one of the four greys cannot belong to the
    glyph: it is a background pixel the difference mask picked up because the
    bird moved.  It has to become transparent, because the remake's own
    battlefield has to show through it.
    """
    indices = []
    dropped = 0
    for color in pixels:
        if color[3] == 0:
            indices.append(0)
            continue
        if color[:3] in GREYS:
            indices.append(GREYS.index(color[:3]) + 1)
            continue
        dropped += 1
        indices.append(0)
    if dropped:
        print(f"  {path.name}: dropped {dropped} non-grey pixels to transparent")
    return indices


def load_phase(path: pathlib.Path) -> tuple[list[int], int, int]:
    image = Image.open(path).convert("RGBA")
    pixels = list(image.getdata())
    indices = snap_to_greys(pixels, path)
    return indices, image.size[0], image.size[1]


def frame_cell(indices, width, height, cell_w, cell_h, offset_x, offset_y):
    """One cell of ``cell_w`` x ``cell_h`` pixels, transparent outside the art.

    The upper bounds of the two loops are the fix of this tool: the cell
    holds the art from ``(offset_x, offset_y)`` on, so the loops have to
    stop at ``min(width - offset_x, cell_w)`` and
    ``min(height - offset_y, cell_h)``.
    """
    cell = [0] * (cell_w * cell_h)
    for y in range(min(height - offset_y, cell_h)):
        for x in range(min(width - offset_x, cell_w)):
            value = indices[(y + offset_y) * width + (x + offset_x)]
            cell[y * cell_w + x] = value
    return cell


def palette16() -> list[tuple[int, int, int]]:
    entries = [TRANSPARENT] + GREYS
    entries += [(0, 0, 0)] * (16 - len(entries))
    return entries


def write_item(out_dir: pathlib.Path, name: str, cells, cell_w, cell_h,
               phase_count: int) -> dict:
    """Write a multi frame Butano sprite item.

    The frames sit side by side in the bitmap, which is what Butano's asset
    compiler expects: it reads the item's width and height from the json
    sidecar, hands GRIT the item's tile size as the metatile size
    (``-Mw width/8 -Mh height/8``) and splits the bitmap into
    ``bmp.width / item_width * bmp.height / item_height`` frames.  The
    metatile of a 64x64 item is 8x8 tiles, so the bitmap's 16x8 tiles are
    read as two 8x8 blocks: the left half of the bitmap is frame 0 and the
    right half is frame 1.

    The pixels therefore have to be written row by row over the *whole*
    bitmap, not frame by frame: a frame major pixel list would put the
    second frame's rows into the first frame's tile block.
    """
    bitmap_width = cell_w * phase_count
    pixels = []
    for y in range(cell_h):
        for x in range(bitmap_width):
            frame = x // cell_w
            pixels.append(cells[frame][y * cell_w + (x - frame * cell_w)])
    bmp_path = out_dir / f"{name}.bmp"
    write_4bpp_bmp(bmp_path, bitmap_width, cell_h, pixels, palette16())
    json_path = out_dir / f"{name}.json"
    json_path.write_text(
        json.dumps({"type": "sprite", "width": cell_w, "height": cell_h},
                   indent=2) + "\n",
        encoding="utf-8", newline="\n")
    ink = sum(1 for pixel in pixels if pixel != 0)
    return {
        "name": name,
        "bitmap": bmp_path.name,
        "json": json_path.name,
        "cell": [cell_w, cell_h],
        "frames": phase_count,
        "bitmap_size": [bitmap_width, cell_h],
        "ink": ink,
        "tiles_total": (bitmap_width // 8) * (cell_h // 8),
        "tiles_per_frame": (cell_w // 8) * (cell_h // 8),
        "sha256": hashlib.sha256(bmp_path.read_bytes()).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True,
                        help="the staging directory for the items")
    parser.add_argument("--header", default=str(HEADER))
    parser.add_argument("--art", default=str(ART_DIR))
    parser.add_argument("--graphics", default=str(GRAPHICS),
                        help="the remake's graphics directory (copy target)")
    args = parser.parse_args(argv)

    header = read_header(pathlib.Path(args.header))
    art_dir = pathlib.Path(args.art)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cleaned: dict[str, list[list[int]]] = {}
    for name, (first, second) in GLYPH_ART.items():
        phases = []
        for file_name in (first, second):
            indices, width, height = load_phase(art_dir / file_name)
            phases.append(indices)
            print(f"{name}: {file_name} {width}x{height}")
        cleaned[name] = phases

    # 「開」 is the first glyph, 「始」 the second one; the piece table is in
    # the same order as the runtime draws the pieces.
    glyph_of_item = {}
    for piece in header["pieces"]:
        glyph_of_item[piece["item"]] = "kai" if "_kai" in piece["item"] else "shi"

    items = []
    for piece in header["pieces"]:
        glyph = glyph_of_item[piece["item"]]
        box = header["glyphs"][0 if glyph == "kai" else 1]
        art_w = box["width"]
        art_h = box["height"]
        cells = [
            frame_cell(cleaned[glyph][phase], art_w, art_h,
                       piece["cell_width"], piece["cell_height"],
                       piece["art_offset_x"], piece["art_offset_y"])
            for phase in (0, 1)
        ]
        item = write_item(out_dir, piece["item"], cells,
                          piece["cell_width"], piece["cell_height"], 2)
        item["glyph"] = glyph
        item["art_offset"] = [piece["art_offset_x"], piece["art_offset_y"]]
        items.append(item)
        print(f"{piece['item']}: {piece['cell_width']}x{piece['cell_height']} "
              f"cell, offset ({piece['art_offset_x']}, {piece['art_offset_y']}), "
              f"ink {item['ink']}")

    manifest = {
        "schema": "konoha.s49-opening-title-assets.v2",
        "graphics_dir": args.graphics,
        "items": items,
        "greys": [list(color) for color in GREYS],
        "transparent": list(TRANSPARENT),
        "tiles_total": sum(item["tiles_total"] for item in items),
        "tiles_per_phase": sum(item["tiles_per_frame"] for item in items),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")

    # The corner cell of 「始」 is empty in both phases of the recovered art,
    # so its item carries no ink at all.  It is kept, because the runtime
    # draws five pieces, but it can be dropped to save 32 tiles and one OAM
    # slot.
    empty = [item["name"] for item in items if item["ink"] == 0]

    print()
    print(f"-> {out_dir}")
    print(f"tiles total {manifest['tiles_total']}, "
          f"per phase {manifest['tiles_per_phase']}")
    if empty:
        print("items without ink: " + ", ".join(empty))
    print()
    print("copy the items into the remake's graphics directory with:")
    print(f'  Copy-Item "{out_dir}\\*.bmp","{out_dir}\\*.json" '
          f'"{args.graphics}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
