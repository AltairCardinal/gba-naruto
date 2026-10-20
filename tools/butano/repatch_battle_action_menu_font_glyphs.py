#!/usr/bin/env python3
"""Repatch the S49 action-menu glyph cells from the original frame.

The identity generator records where every action-menu glyph was cut from in
``ACTION_MENU_ORIGINAL_GLYPH_SOURCES``.  For the S49 action menu it points at
one screenshot, ``scenario-49-battle-14-original-ui-boundaries-v1/
turn4-skill-menu/frame.png``, which was never committed and is gone, so the
full generator cannot be re-run: it aborts, and a successful run would also
overwrite the 39 hand-fixed cells of the atlas.

This tool repatches only the action-menu cells, byte for byte, out of the
original frame that is still on disk:

* the character-to-position map is taken from the generator's own source
  table, so the mapping is owned by the generator and not restated here;
* the original frame is cut with the colour mapping the generator uses, so the
  cut lands on the atlas' own palette indices;
* the atlas is spliced at the byte level, so the header, the palette and every
  other cell stay byte identical;
* the splice is verified *before* it is written: if any byte outside the
  repatched cells would change, the tool exits non-zero without writing.

A note on a measurement that looked like a defect
-----------------------------------------------
The S49 ledger receipt ``artifacts/s49-ledger-evidence-v1/action-menu-glyphs.json``
reported two differing cells (隐 and 年, 105/128 and 69/128) and called them
bold-stroke defects.  They are not.  The ledger tool transcribed the S49 menu
as ``隐身术``/``十年手里剑`` and compared the frame cells at (8,40) and (16,88)
with the atlas cells of 隐 and 年; the original draws 瞬 and 字 there.  Both of
those cells already match the original exactly, and so do all 46 cells this
tool covers.  The ledger's own source table has it right.

The tool fails closed.  A missing original frame, a character order that does
not close, or an atlas whose layout the tool does not understand is an error,
never a silent skip.

Usage::

    python3 tools/butano/repatch_battle_action_menu_font_glyphs.py
    python3 tools/butano/repatch_battle_action_menu_font_glyphs.py --check
    python3 tools/butano/repatch_battle_action_menu_font_glyphs.py \\
        --output /tmp/action_menu_font.bmp
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]

FONT_PATH = ROOT / "butano-sequel/graphics/battle_action_menu_font.bmp"
ORIGINAL_FRAME = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-21-A.png"
)
FONT_HEADER = (
    ROOT
    / "butano-sequel/game/include/konoha/battle_action_menu_sprite_font.h"
)

GLYPH_WIDTH = 8
GLYPH_HEIGHT = 16
ASCII_GLYPH_COUNT = 94


class RepatchError(RuntimeError):
    """The atlas could not be repatched as requested."""


@dataclass(frozen=True)
class BmpLayout:
    """The parts of the atlas' BMP header the splice needs."""

    pixel_offset: int
    width: int
    height: int
    bits: int
    row_stride: int
    tiles: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _generator():
    """The identity generator, which owns the action-menu source table."""

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from tools import generate_butano_battle_identity_content as generator
    except Exception as error:  # pragma: no cover - defensive
        raise RepatchError(
            f"the identity generator could not be imported: {error}"
        ) from error
    return generator


def parse_bmp_layout(data: bytes) -> BmpLayout:
    """Read the atlas' BMP layout, or refuse to guess at it."""

    if len(data) < 54 or data[0:2] != b"BM":
        raise RepatchError("the action menu font is not a BMP file")
    dib_size = int.from_bytes(data[14:18], "little")
    if dib_size < 40:
        raise RepatchError(f"unexpected DIB header size {dib_size}")
    pixel_offset = int.from_bytes(data[10:14], "little")
    width = int.from_bytes(data[18:22], "little")
    height = int.from_bytes(data[22:26], "little", signed=True)
    bits = int.from_bytes(data[28:30], "little")
    if bits != 8:
        raise RepatchError(
            f"the action menu font must be 8 bit, got {bits}"
        )
    if width != GLYPH_WIDTH:
        raise RepatchError(
            f"unexpected action menu font width {width}; expected "
            f"{GLYPH_WIDTH}"
        )
    if height <= 0 or height % GLYPH_HEIGHT:
        raise RepatchError(
            f"unexpected action menu font height {height}; expected a "
            f"multiple of {GLYPH_HEIGHT}"
        )
    row_stride = ((width * bits + 31) // 32) * 4
    if row_stride != GLYPH_WIDTH:
        raise RepatchError(
            f"unexpected action menu font row stride {row_stride}; the tile "
            f"splice needs {GLYPH_WIDTH} bytes per row"
        )
    tiles = height // GLYPH_HEIGHT
    if pixel_offset + row_stride * height != len(data):
        raise RepatchError(
            f"the action menu font's pixel data does not fill the file "
            f"({pixel_offset} + {row_stride}*{height} != {len(data)})"
        )
    return BmpLayout(
        pixel_offset=pixel_offset,
        width=width,
        height=height,
        bits=bits,
        row_stride=row_stride,
        tiles=tiles,
    )


def tile_byte_range(layout: BmpLayout, tile: int) -> tuple[int, int]:
    """The byte range a tile occupies in the file.

    A BMP stores its rows bottom up, so the tile the generator pastes at the
    top of the image is the last block of the pixel data.
    """

    if tile < 0 or tile >= layout.tiles:
        raise RepatchError(
            f"tile {tile} is outside the atlas' {layout.tiles} tiles"
        )
    block = layout.row_stride * GLYPH_HEIGHT
    start = layout.pixel_offset + (layout.tiles - 1 - tile) * block
    return start, start + block


def atlas_tile_indices(data: bytes, layout: BmpLayout, tile: int) -> list[int]:
    """The palette indices a tile holds, read straight out of the file."""

    start, end = tile_byte_range(layout, tile)
    block = data[start:end]
    indices: list[int] = []
    for row in range(GLYPH_HEIGHT - 1, -1, -1):
        base = row * layout.row_stride
        indices.extend(block[base:base + GLYPH_WIDTH])
    return indices


def encode_tile(indices: list[int]) -> bytes:
    """Encode one tile's indices into the atlas' bottom-up byte order."""

    if len(indices) != GLYPH_WIDTH * GLYPH_HEIGHT:
        raise RepatchError(
            f"a tile holds {GLYPH_WIDTH * GLYPH_HEIGHT} indices, got "
            f"{len(indices)}"
        )
    block = bytearray()
    for row in range(GLYPH_HEIGHT - 1, -1, -1):
        base = row * GLYPH_WIDTH
        block.extend(indices[base:base + GLYPH_WIDTH])
    return bytes(block)


def splice_tiles(
    data: bytes, layout: BmpLayout, tiles: dict[int, bytes]
) -> bytes:
    """Replace whole tiles; every other byte of the atlas is kept as is."""

    result = bytearray(data)
    for tile, payload in sorted(tiles.items()):
        start, end = tile_byte_range(layout, tile)
        if len(payload) != end - start:
            raise RepatchError(
                f"tile {tile} needs {end - start} bytes, got {len(payload)}"
            )
        result[start:end] = payload
    return bytes(result)


def assert_only_tiles_changed(
    before: bytes,
    after: bytes,
    layout: BmpLayout,
    tiles: list[int],
) -> list[int]:
    """Return the changed offsets, or refuse when a foreign byte moved."""

    if len(before) != len(after):
        raise RepatchError(
            f"the patched atlas has {len(after)} bytes, the original has "
            f"{len(before)}"
        )
    allowed: set[int] = set()
    for tile in tiles:
        start, end = tile_byte_range(layout, tile)
        allowed.update(range(start, end))
    changed = [
        offset
        for offset, (old, new) in enumerate(zip(before, after))
        if old != new
    ]
    outside = [offset for offset in changed if offset not in allowed]
    if outside:
        raise RepatchError(
            f"{len(outside)} byte(s) outside the repatched cells would "
            f"change (first at offset {outside[0]}); refusing to write"
        )
    return changed


def cut_glyph_indices(pixels, left: int, top: int) -> list[int]:
    """Cut one glyph cell out of the original frame as palette indices."""

    generator = _generator()
    background = generator.ORIGINAL_UI_BACKGROUND_COLOR
    shadow = set(generator.ORIGINAL_UI_SHADOW_COLORS)
    midtone = set(generator.ORIGINAL_UI_MIDTONE_COLORS)
    indices: list[int] = []
    for dy in range(GLYPH_HEIGHT):
        for dx in range(GLYPH_WIDTH):
            color = pixels[left + dx, top + dy]
            if color == background:
                indices.append(0)
            elif color in shadow:
                indices.append(generator.ORIGINAL_UI_SHADOW_INDEX)
            elif color in midtone:
                indices.append(generator.ORIGINAL_UI_MIDTONE_INDEX)
            else:
                indices.append(generator.ORIGINAL_UI_FOREGROUND_INDEX)
    return indices


def header_characters(root: Path = ROOT) -> list[str]:
    """The character order the shipped font header declares."""

    header = root / FONT_HEADER.relative_to(ROOT)
    if not header.is_file():
        raise RepatchError(f"missing font header: {header}")
    text = header.read_text(encoding="utf-8")
    match = re.search(
        r"battle_action_menu_font_utf8_characters\[\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    if not match:
        raise RepatchError(
            f"battle_action_menu_font_utf8_characters not found in {header}"
        )
    return [
        value.encode().decode("unicode_escape") if "\\u" in value else value
        for value in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    ]


def generator_characters(root: Path = ROOT) -> list[str]:
    """The character order the identity generator builds the atlas from."""

    generator = _generator()
    return [
        str(item) for item in generator.load_identity_content(root)[
            "utf8_characters"
        ]
    ]


def resolved_characters(root: Path = ROOT) -> list[str]:
    """The character order, only when the header and the generator agree."""

    header = header_characters(root)
    generator = generator_characters(root)
    if header != generator:
        raise RepatchError(
            "the shipped font header and the identity generator disagree "
            "about the character order; the character-to-cell mapping is not "
            "closed"
        )
    return header


def cell_index(character: str, characters: list[str]) -> int:
    """The atlas cell the character is stored in."""

    if character not in characters:
        raise RepatchError(
            f"{character!r} is not in the action menu font character list"
        )
    return ASCII_GLYPH_COUNT + characters.index(character)


def action_menu_cells(root: Path = ROOT) -> list[dict[str, object]]:
    """The S49 action menu's glyph cells and where they sit in the frame.

    The map comes from the generator's own source table, so it is owned by
    the generator and cannot drift from it.  Only the entries of the S49
    action-menu screenshot are used: the other sources of the table are a
    different screen or a screenshot that is still missing.
    """

    generator = _generator()
    characters = resolved_characters(root)
    cells: list[dict[str, object]] = []
    for character, (
        source,
        left,
        top,
    ) in generator.ACTION_MENU_ORIGINAL_GLYPH_SOURCES.items():
        if source != generator.SCENARIO_49_ACTION_MENU_SOURCE:
            continue
        if character not in characters:
            raise RepatchError(
                f"{character!r} is cut from the S49 action menu but is not in "
                f"the action menu font character list"
            )
        cells.append(
            {
                "character": character,
                "cell": cell_index(character, characters),
                "left": left,
                "top": top,
            }
        )
    if not cells:
        raise RepatchError(
            "the identity generator names no S49 action menu glyph cells"
        )
    cells.sort(key=lambda cell: (int(cell["top"]), int(cell["left"])))
    return cells


def repatch(
    font_path: Path = FONT_PATH,
    output_path: Path | None = None,
    original_path: Path = ORIGINAL_FRAME,
    root: Path = ROOT,
    check_only: bool = False,
) -> dict[str, object]:
    """Repatch the action-menu cells that differ and return the receipt."""

    font_path = Path(font_path)
    original_path = Path(original_path)
    if not font_path.is_file():
        raise RepatchError(f"missing action menu font: {font_path}")
    if not original_path.is_file():
        raise RepatchError(f"missing original frame: {original_path}")

    data = font_path.read_bytes()
    layout = parse_bmp_layout(data)

    with Image.open(original_path) as frame:
        pixels = frame.convert("RGB").load()

    cells = action_menu_cells(root)
    patches: dict[int, bytes] = {}
    report_cells: list[dict[str, object]] = []
    for cell in cells:
        wanted = cut_glyph_indices(
            pixels, int(cell["left"]), int(cell["top"])
        )
        before = atlas_tile_indices(data, layout, int(cell["cell"]))
        difference = sum(1 for a, b in zip(before, wanted) if a != b)
        start, end = tile_byte_range(layout, int(cell["cell"]))
        report_cells.append(
            {
                **cell,
                "byte_range": [start, end],
                "different_pixels_before": difference,
                "cell_pixels": GLYPH_WIDTH * GLYPH_HEIGHT,
            }
        )
        if difference:
            patches[int(cell["cell"])] = encode_tile(wanted)

    patched = splice_tiles(data, layout, patches)
    changed = assert_only_tiles_changed(
        data, patched, layout, sorted(patches)
    )

    # Re-read the spliced atlas and confirm every cell now carries the cut.
    for cell in report_cells:
        actual = atlas_tile_indices(patched, layout, int(cell["cell"]))
        wanted = cut_glyph_indices(
            pixels, int(cell["left"]), int(cell["top"])
        )
        if actual != wanted:
            raise RepatchError(
                f"the spliced atlas does not carry the original's "
                f"{cell['character']}"
            )
        cell["different_pixels_after"] = 0

    output_path = Path(output_path) if output_path else font_path
    written = False
    if not check_only:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(patched)
        written = True

    return {
        "schema": "konoha.s49-action-menu-font-repatch.v2",
        "inputs": {
            "font": str(font_path),
            "font_sha256_before": sha256_bytes(data),
            "original_frame": str(original_path),
            "original_frame_sha256": sha256_bytes(original_path.read_bytes()),
        },
        "output": str(output_path),
        "written": written,
        "cells_checked": len(report_cells),
        "cells_repatched": len(patches),
        "changed_bytes": len(changed),
        "changed_byte_ranges": [
            [start, end]
            for start, end in sorted(
                tile_byte_range(layout, cell) for cell in patches
            )
        ],
        "cells": report_cells,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=FONT_PATH)
    parser.add_argument("--original", type=Path, default=ORIGINAL_FRAME)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="measure the cells and report, without writing anything",
    )
    parser.add_argument("--report", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = repatch(
            font_path=args.font,
            output_path=args.output,
            original_path=args.original,
            check_only=args.check,
        )
    except (RepatchError, OSError, ValueError, KeyError) as error:
        print(
            f"repatch_battle_action_menu_font_glyphs: {error}",
            file=sys.stderr,
        )
        return 2
    if args.report:
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "output": result["output"],
                "written": result["written"],
                "cells_checked": result["cells_checked"],
                "cells_repatched": result["cells_repatched"],
                "changed_bytes": result["changed_bytes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
