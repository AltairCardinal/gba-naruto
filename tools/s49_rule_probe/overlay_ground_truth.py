#!/usr/bin/env python3
"""Shared loader for the original game's BG2 overlay ground truth.

The original's battle overlay lives on BG2:

* 4bpp, palette bank 12, char base block 0, screen base block 2
* tilemap = 1024 entries of 16 bits (tile index 10 bit, palette bank 4 bit,
  hflip/vflip 2 bit) at VRAM 0x06001000
* the overlay tile set is 32 tiles starting at tile index 256; the tiles are
  read back from VRAM with a **32 byte stride** and decoded as 4bpp (4 bytes
  per tile row), which is what the original actually stores
* one *logical* cell of the overlay is 16x16 px = 2x2 of the 8x8 tilemap
  entries, so the map is a 16x16 grid of logical cells

Family vocabulary (from the original's own tile indices) and the palette role
each family paints (bank 12 index -> the remake's palette slot 225..235):

    blank    256, 257      nothing (palette index 0, transparent)
    edge     258..261      grid lattice   (palette index 1  = (8,13,17))
    hatch    262..265      move range     (palette index 2/3)
    line_alt 266..269      attack range   (palette index 4/5 = orange)
    band     270..273      cursor         (palette index 6/7 = yellow)
    solid    278..281      blocked cell   (palette index 10/11 = grey)
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

GT_DIR = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
)

MOMENTS = (
    "field-frame-v1",
    "movegrid-frame-v1",
    "grid16-frame-v1",
    "banner-frame-v1",
)

TILE_BASE_INDEX = 256
TILE_COUNT = 32
TILE_STRIDE = 32  # bytes per tile in VRAM (read back as 4bpp, 4 bytes/row)

MAP_COLS = 32  # 8x8 tilemap columns
MAP_ROWS = 32
LOGICAL_COLS = 16  # 16x16 px logical cells
LOGICAL_ROWS = 16

BLANK_TILES = frozenset({256, 257})

# tile index -> family
TILE_FAMILY: dict[int, str] = {}
for _t in (256, 257, 282, 283, 284, 285, 286, 287):
    TILE_FAMILY[_t] = "blank"
for _t in (258, 259, 260, 261):
    TILE_FAMILY[_t] = "edge"
for _t in (262, 263, 264, 265):
    TILE_FAMILY[_t] = "hatch"
for _t in (266, 267, 268, 269):
    TILE_FAMILY[_t] = "line_alt"
for _t in (270, 271, 272, 273):
    TILE_FAMILY[_t] = "band"
for _t in (274, 275, 276, 277):
    TILE_FAMILY[_t] = "hatch_shift"
for _t in (278, 279, 280, 281):
    TILE_FAMILY[_t] = "solid"

# family -> palette role name (the remake's battle_range_ui_tile_kind)
FAMILY_ROLE = {
    "blank": "grid-nothing",
    "edge": "grid",
    "hatch": "move",
    "line_alt": "attack_range",
    "band": "cursor",
    "solid": "blocked",
    "hatch_shift": "move_shift",
}

FAMILY_SHORT = {
    "blank": ".",
    "edge": "E",
    "hatch": "H",
    "line_alt": "A",
    "band": "B",
    "solid": "S",
    "hatch_shift": "h",
}


def tile_family(tile: int) -> str:
    return TILE_FAMILY.get(tile, "other")


@dataclass(frozen=True)
class Moment:
    name: str
    cells: list          # the exporter's per-8x8-cell records
    lit: list            # the exporter's lit (non blank tile) records
    registers: dict
    screen_window: dict
    counts: dict

    # -- logical (16x16 px) cell view ------------------------------------
    def quadrants(self, lx: int, ly: int) -> list[tuple[int, int, str, int]]:
        """The four 8x8 entries of logical cell (lx, ly), row major.

        Returns a list of (tile_x, tile_y, family, tile).
        """
        out = []
        for ty in range(2):
            for tx in range(2):
                map_x = lx * 2 + tx
                map_y = ly * 2 + ty
                cell = self.cells[map_y * MAP_COLS + map_x]
                out.append((tx, ty, cell["family"], cell["tile"]))
        return out

    def cell_family(self, lx: int, ly: int) -> str:
        """The family that dominates logical cell (lx, ly).

        A logical cell is 'painted' by whichever family contributes the most
        of its four quadrants; ties are broken by a fixed priority so the
        result is deterministic.
        """
        quads = self.quadrants(lx, ly)
        counts: dict[str, int] = {}
        for _tx, _ty, fam, _tile in quads:
            counts[fam] = counts.get(fam, 0) + 1
        priority = {"solid": 6, "hatch": 5, "band": 4, "line_alt": 3,
                    "edge": 2, "hatch_shift": 2, "blank": 0}
        best = max(counts.items(), key=lambda kv: (kv[1], priority.get(kv[0], 1)))
        return best[0]

    def cell_tiles(self, lx: int, ly: int) -> tuple[int, int, int, int]:
        quads = self.quadrants(lx, ly)
        return tuple(q[3] for q in quads)  # type: ignore[return-value]

    def logical_grid(self) -> list[list[str]]:
        return [[self.cell_family(x, y) for x in range(LOGICAL_COLS)]
                for y in range(LOGICAL_ROWS)]

    def lit_logical(self) -> set[tuple[int, int]]:
        """Logical cells that paint at least one non-blank quadrant."""
        out = set()
        for y in range(LOGICAL_ROWS):
            for x in range(LOGICAL_COLS):
                for _tx, _ty, fam, _tile in self.quadrants(x, y):
                    if fam != "blank":
                        out.add((x, y))
                        break
        return out


def load_moment(name: str, gt_dir: pathlib.Path = GT_DIR) -> Moment:
    data = json.loads(
        (gt_dir / f"{name}.bg2-tilemap.json").read_text(encoding="utf-8"))
    return Moment(
        name=name,
        cells=data["cells"],
        lit=data["lit_cells"],
        registers=data.get("registers", {}),
        screen_window=data.get("screen_window", {}),
        counts=data.get("counts", {}),
    )


def load_all(gt_dir: pathlib.Path = GT_DIR) -> dict[str, Moment]:
    return {name: load_moment(name, gt_dir) for name in MOMENTS}


def load_tiles(gt_dir: pathlib.Path = GT_DIR) -> dict[int, list[list[int]]]:
    """Decode the 32 overlay tiles.

    The tile graphics are read back from VRAM with a 32 byte stride and
    decoded as 4bpp (4 bytes per tile row, low nibble = left pixel).
    """
    raw = (gt_dir / "bg2-tiles-4bpp.bin").read_bytes()
    tiles: dict[int, list[list[int]]] = {}
    for index in range(TILE_COUNT):
        base = index * TILE_STRIDE
        rows: list[list[int]] = []
        for row in range(8):
            rb = base + row * 4
            pixels: list[int] = []
            for byte_index in range(4):
                byte = raw[rb + byte_index]
                pixels.append(byte & 0x0F)
                pixels.append((byte >> 4) & 0x0F)
            rows.append(pixels)
        tiles[TILE_BASE_INDEX + index] = rows
    return tiles


def load_palette(gt_dir: pathlib.Path = GT_DIR) -> list[tuple[int, int, int]]:
    data = json.loads((gt_dir / "bg2-palette.json").read_text(encoding="utf-8"))
    return [tuple(e["rgb8"]) for e in data["entries"]]


def ascii_map(moment: Moment) -> str:
    grid = moment.logical_grid()
    lines = []
    for y, row in enumerate(grid):
        lines.append(f"  r{y:2d} " + " ".join(FAMILY_SHORT.get(f, "?") for f in row))
    return "\n".join(lines)


if __name__ == "__main__":
    for name in MOMENTS:
        m = load_moment(name)
        print("=" * 78)
        print(f"{name}   lit(8x8)={len(m.lit)}  lit(logical 16x16)={len(m.lit_logical())}")
        print(f"  bg2_enabled={m.registers.get('bg2_enabled')} "
              f"dispcnt={m.registers.get('dispcnt')} "
              f"hoffs={m.registers.get('bg_hoffs')} voffs={m.registers.get('bg_voffs')}")
        print(ascii_map(m))
        print()
