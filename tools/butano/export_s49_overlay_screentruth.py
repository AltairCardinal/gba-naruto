#!/usr/bin/env python3
"""Export the original's battle overlay in **screen space**, as ground truth.

Round 26 established that the original's move-range screen is not "one extra
grid layer" but a **baked battlefield layout map** the game writes into BG2's
tilemap when the battle starts; the move-range screen merely enables BG2
(``DISPCNT`` bit 10).  Reproducing that overlay 1:1 in the remake needs more
than "which tile family belongs to which logical cell": it needs to know
**which 8x8 tile of that map lands on which pixel of the screen**.

This exporter answers that from the captured evidence, with no ROM run:

* ``artifacts/s49-original-battlefield-overlay-v1/bg2-tilemap-{field,movegrid}.bin``
  -- 32x32 tilemap entries, 16 bit little endian (tile index 10 bit, palette
  bank 4 bit, hflip bit 10, vflip bit 11);
* ``artifacts/s49-original-battlefield-overlay-v1/manifest.json`` -- the
  signed hashes and the changed-entry count;
* ``artifacts/s49-original-movegrid-tilemap-v1/bg2-tiles-4bpp.bin`` -- the 32
  tiles (4bpp, two pixels per byte, **high nibble is the LEFT pixel**);
* ``artifacts/s49-original-movegrid-tilemap-v1/bg2-palette.bin`` -- the 16
  colours of palette bank 12 (15 bit BGR555 little endian);
* ``artifacts/s49-original-battlefield-overlay-v1/visible-cells.json`` -- the
  scroll registers (hoff 240, voff 24) and the screen lookup.

The visible window of a 32x32 tile map scrolled to (240, 24) is 30x20 tiles
= the whole 240x160 screen, and the lookup is::

    screen cell (sx, sy) -> tilemap cell (((sx + hoffs) // 8) mod 32,
                                           ((sy + voffs) // 8) mod 32)

The exporter also **attributes the remake's remaining pixel difference** to
the original's tile families, when both recorded frames are present.  That
attribution is what tells the remake which part of the overlay is missing
rather than merely "different".

Every output is deterministic: re-running the exporter reproduces each file
byte for byte, and no timestamp is written anywhere.

Usage::

    /usr/local/bin/python3 tools/butano/export_s49_overlay_screentruth.py
    /usr/local/bin/python3 tools/butano/export_s49_overlay_screentruth.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

OVERLAY_DIR = ROOT / "artifacts/s49-original-battlefield-overlay-v1"
TILEMAP_DIR = ROOT / "artifacts/s49-original-movegrid-tilemap-v1"
OUT_DIR = ROOT / "artifacts/s49-original-overlay-screentruth-v1"

FIELD_BIN = OVERLAY_DIR / "bg2-tilemap-field.bin"
MOVEGRID_BIN = OVERLAY_DIR / "bg2-tilemap-movegrid.bin"
OVERLAY_MANIFEST = OVERLAY_DIR / "manifest.json"
VISIBLE_CELLS = OVERLAY_DIR / "visible-cells.json"
TILES_BIN = TILEMAP_DIR / "bg2-tiles-4bpp.bin"
PALETTE_BIN = TILEMAP_DIR / "bg2-palette.bin"

ORIGINAL_FRAME = (
    ROOT / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-19-A.png"
)
REMAKE_FRAME = ROOT / "artifacts/s49-remake-walk-20261021-v1/step-20-A.png"

SCHEMA = "konoha.s49-overlay-screentruth.v1"
TILEMAP_COLUMNS = 32
TILEMAP_ROWS = 32
TILEMAP_ENTRIES = TILEMAP_COLUMNS * TILEMAP_ROWS
TILE_MASK = 0x03FF
BANK_SHIFT = 12
HFLIP_BIT = 10
VFLIP_BIT = 11
TILE_COUNT = 32
FIRST_TILE = 256
PALETTE_ENTRIES = 16
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
FIELD_AREA = (0, 0, 240, 128)

#: The tile families of the original's overlay, keyed by the first tile index
#: of the family.  The family is the 2x2 block of 8x8 tiles that makes up one
#: 16x16 px logical cell.
FAMILIES: tuple[tuple[int, int, str], ...] = (
    (256, 2, "none"),
    (258, 4, "grid_web"),
    (262, 4, "move_lens"),
    (266, 4, "attack_cursor"),
    (270, 4, "cursor"),
    (274, 4, "target"),
    (278, 4, "blocked"),
)


class ScreentruthError(RuntimeError):
    """Raised when the evidence contradicts the signed manifest."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _entries(data: bytes) -> list[int]:
    return [
        int.from_bytes(data[index:index + 2], "little")
        for index in range(0, len(data), 2)
    ]


def _rgb5(value: int) -> tuple[int, int, int]:
    """15 bit BGR555 -> 8 bit RGB, the way mGBA scales it."""
    return (
        (value & 31) * 255 // 31,
        ((value >> 5) & 31) * 255 // 31,
        ((value >> 10) & 31) * 255 // 31,
    )


def family_of(tile: int) -> str:
    for first, size, name in FAMILIES:
        if first <= tile < first + size:
            return name
    return "unknown"


def load_evidence() -> dict[str, Any]:
    for path in (
        FIELD_BIN,
        MOVEGRID_BIN,
        OVERLAY_MANIFEST,
        VISIBLE_CELLS,
        TILES_BIN,
        PALETTE_BIN,
    ):
        if not path.is_file():
            raise ScreentruthError(f"missing evidence: {path}")
    manifest = json.loads(OVERLAY_MANIFEST.read_text(encoding="utf-8"))
    field = FIELD_BIN.read_bytes()
    movegrid = MOVEGRID_BIN.read_bytes()
    tiles = TILES_BIN.read_bytes()
    palette = PALETTE_BIN.read_bytes()
    if len(field) != TILEMAP_ENTRIES * 2 or len(movegrid) != TILEMAP_ENTRIES * 2:
        raise ScreentruthError("the tilemaps must be 2048 bytes each")
    if len(tiles) != TILE_COUNT * 32:
        raise ScreentruthError("the tile blob must be 1024 bytes")
    if len(palette) != PALETTE_ENTRIES * 2:
        raise ScreentruthError("the palette blob must be 32 bytes")
    if sha256_bytes(field) != manifest["field_tilemap_sha256"]:
        raise ScreentruthError("field tilemap hash does not match the manifest")
    if sha256_bytes(movegrid) != manifest["movegrid_tilemap_sha256"]:
        raise ScreentruthError("movegrid tilemap hash does not match the manifest")
    changed = [
        index
        for index in range(TILEMAP_ENTRIES)
        if _entries(field)[index] != _entries(movegrid)[index]
    ]
    if changed != list(manifest["changed_entries"]):
        raise ScreentruthError(
            "the changed entry list does not match the signed manifest"
        )
    if len(changed) != int(manifest["changed_entries_vs_field"]):
        raise ScreentruthError(
            f"changed entry count {len(changed)} != "
            f"{manifest['changed_entries_vs_field']}"
        )
    visible = json.loads(VISIBLE_CELLS.read_text(encoding="utf-8"))
    hoffs = int(visible["movegrid-frame-v1"]["hoffs"])
    voffs = int(visible["movegrid-frame-v1"]["voffs"])
    columns = int(visible["movegrid-frame-v1"]["screen_window"]["cols"])
    rows = int(visible["movegrid-frame-v1"]["screen_window"]["rows"])
    if (columns, rows) != (SCREEN_WIDTH // 8, SCREEN_HEIGHT // 8):
        raise ScreentruthError(
            f"unexpected visible window {columns}x{rows}"
        )
    return {
        "manifest": manifest,
        "field": _entries(field),
        "movegrid": _entries(movegrid),
        "tiles": tiles,
        "palette": [
            _rgb5(int.from_bytes(palette[index:index + 2], "little"))
            for index in range(0, len(palette), 2)
        ],
        "palette_raw": [
            int.from_bytes(palette[index:index + 2], "little")
            for index in range(0, len(palette), 2)
        ],
        "hoffs": hoffs,
        "voffs": voffs,
        "changed": changed,
    }


def screen_lookup(
    evidence: dict[str, Any],
    entries: list[int],
    screen_x: int,
    screen_y: int,
) -> tuple[int, int, int]:
    """Return (palette index, tile index, tilemap cell index) at a pixel."""
    hoffs = evidence["hoffs"]
    voffs = evidence["voffs"]
    tilemap_column = ((screen_x + hoffs) // 8) % TILEMAP_COLUMNS
    tilemap_row = ((screen_y + voffs) // 8) % TILEMAP_ROWS
    cell_index = tilemap_row * TILEMAP_COLUMNS + tilemap_column
    entry = entries[cell_index]
    tile = entry & TILE_MASK
    local = tile - FIRST_TILE
    if local < 0 or local >= TILE_COUNT:
        return -1, tile, cell_index
    pixel_x = screen_x % 8
    pixel_y = screen_y % 8
    if entry & (1 << HFLIP_BIT):
        pixel_x = 7 - pixel_x
    if entry & (1 << VFLIP_BIT):
        pixel_y = 7 - pixel_y
    byte = evidence["tiles"][local * 32 + pixel_y * 4 + (pixel_x // 2)]
    # GBA 4bpp: the LOW nibble is the left pixel.  Pinned against the
    # original's own pixels in round 26 (see the sibling exporter's
    # ``tile_pixels`` docstring); the high nibble is the right one.
    value = (byte & 0x0F) if pixel_x % 2 == 0 else (byte >> 4)
    return value, tile, cell_index


def render_layer(evidence: dict[str, Any], entries: list[int]):
    """Render one frame's overlay in screen space as an RGBA image."""
    from PIL import Image

    image = Image.new("RGBA", (SCREEN_WIDTH, SCREEN_HEIGHT), (0, 0, 0, 0))
    pixels = image.load()
    palette = evidence["palette"]
    for screen_y in range(SCREEN_HEIGHT):
        for screen_x in range(SCREEN_WIDTH):
            value, _, _ = screen_lookup(evidence, entries, screen_x, screen_y)
            if value < 0:
                continue
            colour = palette[value]
            if colour == (0, 0, 0):
                # Palette entry 0 is 0x0000, which the GBA renders transparent.
                continue
            pixels[screen_x, screen_y] = (*colour, 255)
    return image


def family_map(evidence: dict[str, Any], entries: list[int]) -> list[str]:
    """The 30x20 grid of tile families that is visible on the screen."""
    rows: list[str] = []
    for screen_row in range(SCREEN_HEIGHT // 8):
        line = ""
        for screen_column in range(SCREEN_WIDTH // 8):
            _, tile, _ = screen_lookup(
                evidence, entries, screen_column * 8, screen_row * 8
            )
            line += family_of(tile)[0]
        rows.append(line)
    return rows


def footprint(evidence: dict[str, Any], entries: list[int]) -> dict[str, Any]:
    painted = 0
    box = [SCREEN_WIDTH, SCREEN_HEIGHT, -1, -1]
    per_row = [0] * SCREEN_HEIGHT
    per_column = [0] * SCREEN_WIDTH
    cells: set[tuple[int, int]] = set()
    palette = evidence["palette"]
    for screen_y in range(SCREEN_HEIGHT):
        for screen_x in range(SCREEN_WIDTH):
            value, _, cell_index = screen_lookup(
                evidence, entries, screen_x, screen_y
            )
            if value < 0 or palette[value] == (0, 0, 0):
                continue
            painted += 1
            per_row[screen_y] += 1
            per_column[screen_x] += 1
            cells.add((cell_index % TILEMAP_COLUMNS, cell_index // TILEMAP_COLUMNS))
            box[0] = min(box[0], screen_x)
            box[1] = min(box[1], screen_y)
            box[2] = max(box[2], screen_x)
            box[3] = max(box[3], screen_y)
    return {
        "painted_pixels": painted,
        "bounding_box": box,
        "painted_tilemap_cells": len(cells),
        "visible_cells": (SCREEN_WIDTH // 8) * (SCREEN_HEIGHT // 8),
        "per_row_painted": per_row,
        "per_column_painted": per_column,
    }


def attribute_residual(
    evidence: dict[str, Any],
    entries: list[int],
) -> dict[str, Any] | None:
    """Split the remake's pixel difference by the original's tile family."""
    if not ORIGINAL_FRAME.is_file() or not REMAKE_FRAME.is_file():
        return None
    from PIL import Image

    original = Image.open(ORIGINAL_FRAME).convert("RGB").load()
    remake = Image.open(REMAKE_FRAME).convert("RGB").load()
    by_family: dict[str, int] = {}
    by_family_cells: dict[str, int] = {}
    cell_detail: list[dict[str, Any]] = []
    total = 0
    x0, y0, x1, y1 = FIELD_AREA
    for screen_y in range(y0, y1):
        for screen_x in range(x0, x1):
            if original[screen_x, screen_y] == remake[screen_x, screen_y]:
                continue
            total += 1
            _, tile, _ = screen_lookup(
                evidence, entries, screen_x, screen_y
            )
            name = family_of(tile)
            by_family[name] = by_family.get(name, 0) + 1
            by_family_cells[name] = by_family_cells.get(name, 0) + 1
    for screen_row in range(SCREEN_HEIGHT // 8):
        for screen_column in range(SCREEN_WIDTH // 8):
            differing = 0
            for screen_y in range(screen_row * 8, screen_row * 8 + 8):
                for screen_x in range(screen_column * 8, screen_column * 8 + 8):
                    if (
                        screen_y >= y1
                        or screen_x >= x1
                        or original[screen_x, screen_y] == remake[screen_x, screen_y]
                    ):
                        continue
                    differing += 1
            if not differing:
                continue
            _, tile, _ = screen_lookup(
                evidence, entries, screen_column * 8, screen_row * 8
            )
            cell_detail.append(
                {
                    "screen_column": screen_column,
                    "screen_row": screen_row,
                    "differing_pixels": differing,
                    "original_tile": tile,
                    "original_family": family_of(tile),
                }
            )
    return {
        "total_differing_pixels": total,
        "by_family": dict(sorted(by_family.items())),
        "cells_with_difference": len(cell_detail),
        "cell_detail": cell_detail,
        "original_frame": str(ORIGINAL_FRAME.relative_to(ROOT)),
        "remake_frame": str(REMAKE_FRAME.relative_to(ROOT)),
    }


def build_outputs() -> dict[str, bytes]:
    evidence = load_evidence()
    outputs: dict[str, bytes] = {}
    for name, entries in (
        ("movegrid", evidence["movegrid"]),
        ("field", evidence["field"]),
    ):
        image = render_layer(evidence, entries)
        import io

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        outputs[f"overlay-{name}-screen.png"] = buffer.getvalue()
    screen_truth = {
        "schema": SCHEMA,
        "scroll": {"hoffs": evidence["hoffs"], "voffs": evidence["voffs"]},
        "lookup": (
            "screen cell (sx, sy) -> tilemap cell "
            "(((sx + hoffs) // 8) mod 32, ((sy + voffs) // 8) mod 32)"
        ),
        "palette_rgb5_to_rgb8": evidence["palette_raw"],
        "palette_rgb8": evidence["palette"],
        "families": [
            {"first_tile": first, "size": size, "name": name}
            for first, size, name in FAMILIES
        ],
        "family_map": {
            "legend": {
                "n": "none (256/257)",
                "g": "grid web (258-261)",
                "m": "move lens (262-265)",
                "a": "attack/cursor (266-269)",
                "c": "cursor (270-273)",
                "t": "target (274-277)",
                "b": "blocked (278-281)",
            },
            "movegrid": family_map(evidence, evidence["movegrid"]),
            "field": family_map(evidence, evidence["field"]),
        },
        "footprint": {
            "movegrid": footprint(evidence, evidence["movegrid"]),
            "field": footprint(evidence, evidence["field"]),
        },
        "field_to_movegrid": {
            "changed_tilemap_entries": len(evidence["changed"]),
            "changed_screen_cells": len(
                {
                    (index % TILEMAP_COLUMNS, index // TILEMAP_COLUMNS)
                    for index in evidence["changed"]
                }
            ),
        },
    }
    residual = attribute_residual(evidence, evidence["movegrid"])
    if residual is not None:
        screen_truth["remake_residual_attribution"] = residual
    outputs["screen-truth.json"] = (
        json.dumps(screen_truth, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    return outputs


def build_manifest(outputs: dict[str, bytes]) -> bytes:
    inputs = {}
    for path in (
        FIELD_BIN,
        MOVEGRID_BIN,
        OVERLAY_MANIFEST,
        VISIBLE_CELLS,
        TILES_BIN,
        PALETTE_BIN,
    ):
        inputs[str(path.relative_to(ROOT))] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    manifest = {
        "schema": SCHEMA,
        "what": (
            "The original's battle overlay (BG2) rendered in screen space, "
            "with the remake's remaining pixel difference attributed to the "
            "original's tile families."
        ),
        "exporter": "tools/butano/export_s49_overlay_screentruth.py",
        "inputs": inputs,
        "outputs": {
            name: {"sha256": sha256_bytes(data), "bytes": len(data)}
            for name, data in sorted(outputs.items())
        },
    }
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the exported artifacts are not up to date",
    )
    args = parser.parse_args(argv)
    try:
        outputs = build_outputs()
        manifest = build_manifest(outputs)
    except ScreentruthError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    outputs["manifest.json"] = manifest
    if args.check:
        problems = []
        for name, data in sorted(outputs.items()):
            path = OUT_DIR / name
            if not path.is_file():
                problems.append(f"missing: {path}")
            elif path.read_bytes() != data:
                problems.append(f"stale: {path}")
        if problems:
            print("\n".join(problems), file=sys.stderr)
            print(
                "run tools/butano/export_s49_overlay_screentruth.py",
                file=sys.stderr,
            )
            return 1
        print(f"{len(outputs)} artifacts are up to date")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(outputs.items()):
        (OUT_DIR / name).write_bytes(data)
    print(f"wrote {len(outputs)} artifacts to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
