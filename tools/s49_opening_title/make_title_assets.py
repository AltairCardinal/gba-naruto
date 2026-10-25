#!/usr/bin/env python3
"""Turn the recovered 「開始」 calligraphy into Butano sprite items.

What this tool does
-------------------
Stream Y2 recovered the original's 「開始」 title art from the original's own
frames (tools/s49_opening_title/{kai,shi,kai-phase1,shi-phase1}.png, RGBA, four
opaque greys plus transparency) and measured where it belongs on the screen:

    「開」  screen box (41, 49)   art 59x62
    「始」  screen box (135, 42)  art 70x70

GBA OBJ sprites are at most 64x64, so 「始」 (70 rows) does not fit into one
sprite item: it is cut into a 64x64 top piece and a 64x32 bottom piece.  Both
glyphs have two animation phases, and Butano sprite items carry one item per
frame set, so each item's bitmap holds two frames side by side.

The tool

  1. cleans the recovered art: every opaque pixel that is not one of the
     four greys is a stray background pixel picked up by the difference mask,
     and is snapped to the nearest grey so the glyph keeps its shape,
  2. writes three Butano sprite items (bitmap + json sidecar) into the
     remake's graphics/ directory,
  3. re-projects the *cleaned* art onto the remake's battlefield and reports
     the residual the remake would reach with the shipped art, and
  4. reports the VRAM cost of the title in OBJ tiles.

Usage::

    python tools/s49_opening_title/make_title_assets.py \
        --graphics "D:\\Shell\\Github\\gba-naruto-butano\\butano-sequel\\graphics" \
        --out build/s49-opening-title/title-assets.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

# The remake repository's shared indexed BMP writer (read only).
REMAKE_TOOLS = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\tools\butano")
if str(REMAKE_TOOLS) not in sys.path:
    sys.path.insert(0, str(REMAKE_TOOLS))

from indexed_bmp import write_4bpp_bmp  # noqa: E402

# The four opaque colours of the original's title, as 8 bit greys.  They are
# the GBA's 5 bit values 4 / 13 / 22 / 31 expanded, so the sprite palette
# reproduces the original's colours exactly.
GREYS = [(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)]
TRANSPARENT = (255, 0, 255)

# The screen boxes the art belongs in, and the source file of each phase.
GLYPHS = {
    "kai": {
        "screen_box": (41, 49, 100, 111),
        "phases": ("kai.png", "kai-phase1.png"),
    },
    "shi": {
        "screen_box": (135, 42, 205, 112),
        "phases": ("shi.png", "shi-phase1.png"),
    },
}

# The Butano sprite item cells.  A GBA sprite is at most 64x64, and the
# valid sizes are 8x8, 16x16, 32x32, 64x64, 16x8, 32x8, 32x16, 8x16, 8x32,
# 16x32 and 32x64.
#
# 「開」 is 59x62 and fits into one 64x64 cell.  「始」 is 70x70, so it is
# cut into four pieces that cover all 70 columns and all 70 rows:
#
#   main           64x64   rows  0..63, columns  0..63
#   right          32x64   rows  0..63, columns 64..95
#   bottom         64x32   rows 64..95, columns  0..63
#   corner         32x32   rows 64..95, columns 64..95
#
# (16x64 and 16x32 are not valid GBA sprite sizes, so the narrow column has
# to be a 32 wide one.)
PIECES = {
    "kai": [("kai", 64, 64, 0, 0)],
    "shi": [("shi_top", 64, 64, 0, 0), ("shi_right", 32, 64, 64, 0),
            ("shi_bottom", 64, 32, 0, 64), ("shi_corner", 32, 32, 64, 64)],
}


def snap_to_greys(pixels, path: pathlib.Path) -> tuple[list[int], int]:
    """Index the art with the four greys; drop every other opaque colour.

    The original's title uses exactly four opaque colours (Y2's measurement),
    so an opaque pixel that is not one of the four greys cannot belong to the
    glyph: it is a background pixel that the difference mask picked up because
    the bird moved.  Such a pixel has to become transparent, because the
    remake's own battlefield has to show through it.
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
    return indices, dropped


def load_phase(path: pathlib.Path) -> tuple[list[int], int, int]:
    image = Image.open(path).convert("RGBA")
    pixels = list(image.get_flattened_data())
    indices, _ = snap_to_greys(pixels, path)
    return indices, image.size[0], image.size[1]


def frame_cell(indices, width, height, cell_w, cell_h, offset_x, offset_y):
    """One cell of ``cell_w`` x ``cell_h`` pixels, transparent outside the art."""
    cell = [0] * (cell_w * cell_h)
    for y in range(min(height, cell_h - offset_y)):
        for x in range(min(width, cell_w - offset_x)):
            value = indices[(y + offset_y) * width + (x + offset_x)]
            cell[y * cell_w + x] = value
    return cell


def palette16() -> list[tuple[int, int, int]]:
    entries = [TRANSPARENT] + GREYS
    entries += [(0, 0, 0)] * (16 - len(entries))
    return entries


def write_item(graphics_dir: pathlib.Path, name: str, cells, cell_w, cell_h,
               phase_count: int) -> dict:
    """Write a multi frame Butano sprite item."""
    frames_per_row = phase_count
    bitmap_width = cell_w * frames_per_row
    bitmap_height = cell_h
    pixels = []
    for frame in range(phase_count):
        pixels.extend(cells[frame])
    bmp_path = graphics_dir / f"{name}.bmp"
    write_4bpp_bmp(bmp_path, bitmap_width, bitmap_height, pixels, palette16())
    json_path = graphics_dir / f"{name}.json"
    json_path.write_text(
        json.dumps({"type": "sprite", "width": cell_w, "height": cell_h},
                   indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return {
        "name": name,
        "bitmap": str(bmp_path),
        "json": str(json_path),
        "cell": [cell_w, cell_h],
        "frames": phase_count,
        "bitmap_size": [bitmap_width, bitmap_height],
        "tiles_per_frame": (cell_w // 8) * (cell_h // 8),
        "sha256": hashlib.sha256(bmp_path.read_bytes()).hexdigest(),
    }


def difference_mask(left: Image.Image, right: Image.Image):
    from PIL import ImageChops

    delta = ImageChops.difference(left.crop((0, 0, 240, 128)),
                                  right.crop((0, 0, 240, 128)))
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return mask.point(lambda value: 255 if value else 0)


def residual(left: Image.Image, right: Image.Image) -> int:
    return sum(difference_mask(left, right).histogram()[1:])


def project(original_dir: pathlib.Path, remake_dir: pathlib.Path,
            cleaned: dict[str, list[list[int]]]) -> dict:
    """Residual the remake would reach with the cleaned art."""
    original = Image.open(original_dir / "step-0207-beat.png").convert("RGB")
    original_next = Image.open(original_dir / "step-0230-beat.png").convert("RGB")
    before = Image.open(original_dir / "step-0184-beat.png").convert("RGB")
    remake = Image.open(remake_dir / "step-0292-in.png").convert("RGB")

    def phase_image(phase: int) -> Image.Image:
        image = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
        for name, phases in cleaned.items():
            box = GLYPHS[name]["screen_box"]
            width = box[2] - box[0]
            height = box[3] - box[1]
            indices = phases[phase]
            pixels = []
            for y in range(height):
                for x in range(width):
                    index = indices[y * width + x]
                    if index == 0:
                        pixels.append((0, 0, 0, 0))
                    else:
                        value = GREYS[index - 1]
                        pixels.append((value[0], value[1], value[2], 255))
            tile = Image.new("RGBA", (width, height))
            tile.putdata(pixels)
            image.paste(tile, (box[0], box[1]), tile)
        return image

    results = {}
    for phase, reference in ((0, original), (1, original_next)):
        projected = remake.copy()
        art = phase_image(phase)
        projected.paste(art, (0, 0), art)
        text_mask = difference_mask(before, remake).crop((0, 0, 70, 40))
        projected.paste(before.crop((0, 0, 70, 40)), (0, 0), text_mask)
        results[f"projected_phase{phase}"] = residual(reference, projected)
    results["original_title_vs_remake_screen"] = residual(original, remake)
    results["original_before_vs_remake_screen"] = residual(before, remake)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphics", required=True,
                        help="the remake's butano-sequel/graphics directory")
    parser.add_argument("--art", default=str(HERE),
                        help="directory with the recovered art")
    parser.add_argument("--out", required=True)
    parser.add_argument("--original-dir",
                        default=str(REPO / "build" / "s49-pairing" / "walk5" /
                                    "dense-original"))
    parser.add_argument("--remake-dir",
                        default=str(REPO / "build" / "s49-pairing" / "walk5" /
                                    "dense-remake"))
    args = parser.parse_args(argv)

    art_dir = pathlib.Path(args.art)
    graphics_dir = pathlib.Path(args.graphics)
    graphics_dir.mkdir(parents=True, exist_ok=True)

    cleaned: dict[str, list[list[int]]] = {}
    snapped_total = 0
    for name, spec in GLYPHS.items():
        phases = []
        for file_name in spec["phases"]:
            indices, width, height = load_phase(art_dir / file_name)
            snapped_total += sum(
                1 for index in indices
                if index and GREYS[index - 1] not in GREYS)
            phases.append(indices)
            print(f"{name}: {file_name} {width}x{height}")
        cleaned[name] = phases

    # Every piece of every glyph becomes its own Butano sprite item.
    items = []
    for name, spec in GLYPHS.items():
        box = spec["screen_box"]
        art_w = box[2] - box[0]
        art_h = box[3] - box[1]
        for index, (suffix, cell_w, cell_h, art_x, art_y) in enumerate(
                PIECES[name]):
            cells = [
                frame_cell(cleaned[name][phase], art_w, art_h, cell_w, cell_h,
                           art_x, art_y)
                for phase in (0, 1)
            ]
            items.append(write_item(graphics_dir,
                                    f"battle_opening_title_{suffix}",
                                    cells, cell_w, cell_h, 2))

    tiles_per_phase = sum(item["tiles_per_frame"] for item in items)
    report = {
        "schema": "konoha.s49-opening-title-assets.v1",
        "graphics_dir": str(graphics_dir),
        "art_dir": str(art_dir),
        "items": items,
        "glyphs": {
            name: {
                "screen_box": list(spec["screen_box"]),
                "art_size": [spec["screen_box"][2] - spec["screen_box"][0],
                             spec["screen_box"][3] - spec["screen_box"][1]],
                "phases": list(spec["phases"]),
            }
            for name, spec in GLYPHS.items()
        },
        "greys": [list(color) for color in GREYS],
        "transparent": list(TRANSPARENT),
        "tiles_per_phase": tiles_per_phase,
        "tiles_bytes_per_phase": tiles_per_phase * 32,
    }

    original_dir = pathlib.Path(args.original_dir)
    remake_dir = pathlib.Path(args.remake_dir)
    if original_dir.is_dir() and remake_dir.is_dir():
        report["residual_with_cleaned_art"] = project(original_dir, remake_dir,
                                                       cleaned)
    else:
        report["residual_with_cleaned_art"] = None

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
