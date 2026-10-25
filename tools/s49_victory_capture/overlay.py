#!/usr/bin/env python3
"""Read the original game's battle overlay (BG2) out of VRAM.

Stream F (notes/s49-fidelity/F-rule.md) established the vocabulary of the
original's overlay tile set by decoding the original's own tile graphics and
its bank-12 palette.  The families are re-stated here so this tool does not
have to import anything from the F stream:

    blank      256, 257      nothing (transparent)
    edge       258..261      1 px grid lattice
    hatch      262..265      move range (cyan)
    line_alt   266..269      attack range / move destination (orange)
    band       270..273      cursor cell (yellow)
    hatch_shift 274..277     legal target (green)
    solid      278..281      blocked cell (grey dither)

The overlay lives on BG2:

* 4bpp, palette bank 12, char base block 0, screen base block 2
* tilemap = 1024 entries of 16 bit (tile index 10 bit, palette bank 4 bit,
  hflip/vflip 2 bit) at VRAM 0x06001000
* one *logical* cell of the overlay is 16x16 px = 2x2 of the 8x8 tilemap
  entries, so the overlay map is a 16x16 grid of logical cells

A logical cell is painted by one family; the family of a cell is the one that
owns the most of its four quadrants (ties broken by a fixed priority).
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

BG2_TILEMAP_ADDRESS = 0x06001000
BG2_TILEMAP_LENGTH = 2048

TILE_BASE_INDEX = 256
TILE_COUNT = 32

MAP_COLS = 32          # 8x8 tilemap columns
MAP_ROWS = 32
LOGICAL_COLS = 16      # 16x16 px logical cells
LOGICAL_ROWS = 16

FAMILY_TILES: dict[str, tuple[int, ...]] = {
    "blank": (256, 257),
    "edge": (258, 259, 260, 261),
    "hatch": (262, 263, 264, 265),
    "line_alt": (266, 267, 268, 269),
    "band": (270, 271, 272, 273),
    "hatch_shift": (274, 275, 276, 277),
    "solid": (278, 279, 280, 281),
}

TILE_FAMILY: dict[int, str] = {}
for _family, _tiles in FAMILY_TILES.items():
    for _tile in _tiles:
        TILE_FAMILY[_tile] = _family

FAMILY_SHORT = {
    "blank": ".",
    "edge": "E",
    "hatch": "H",
    "line_alt": "A",
    "band": "B",
    "solid": "S",
    "hatch_shift": "h",
    "other": "?",
}

# Tie break priority when a logical cell mixes families.
FAMILY_PRIORITY = {
    "band": 7,
    "hatch_shift": 6,
    "line_alt": 5,
    "hatch": 4,
    "solid": 3,
    "edge": 2,
    "blank": 1,
    "other": 0,
}


def tile_of(entry: int) -> int:
    """Tile index of a raw 16 bit tilemap entry."""
    return entry & 0x03FF


def tile_family(tile: int) -> str:
    return TILE_FAMILY.get(tile, "other")


@dataclass(frozen=True)
class Overlay:
    """The decoded overlay map of one frame."""

    entries: tuple[int, ...]

    @classmethod
    def from_blob(cls, blob: bytes) -> "Overlay":
        if len(blob) != BG2_TILEMAP_LENGTH:
            raise ValueError(
                f"expected {BG2_TILEMAP_LENGTH} bytes of tilemap, got {len(blob)}")
        entries = []
        for index in range(MAP_COLS * MAP_ROWS):
            low = blob[index * 2]
            high = blob[index * 2 + 1]
            entries.append(low | (high << 8))
        return cls(entries=tuple(entries))

    def quadrants(self, lx: int, ly: int) -> list[tuple[int, int, str, int]]:
        out = []
        for ty in range(2):
            for tx in range(2):
                entry = self.entries[(ly * 2 + ty) * MAP_COLS + (lx * 2 + tx)]
                tile = tile_of(entry)
                out.append((tx, ty, tile_family(tile), tile))
        return out

    def cell_family(self, lx: int, ly: int) -> str:
        counts: dict[str, int] = {}
        for _tx, _ty, family, _tile in self.quadrants(lx, ly):
            counts[family] = counts.get(family, 0) + 1
        best = max(counts.items(),
                   key=lambda kv: (kv[1], FAMILY_PRIORITY.get(kv[0], 0)))
        return best[0]

    def grid(self) -> list[list[str]]:
        return [[self.cell_family(x, y) for x in range(LOGICAL_COLS)]
                for y in range(LOGICAL_ROWS)]

    def cells_of(self, family: str) -> list[tuple[int, int]]:
        return [(x, y) for y in range(LOGICAL_ROWS) for x in range(LOGICAL_COLS)
                if self.cell_family(x, y) == family]

    def ascii(self, only_lit: bool = True) -> str:
        lines = []
        for y in range(LOGICAL_ROWS):
            row = []
            for x in range(LOGICAL_COLS):
                family = self.cell_family(x, y)
                if only_lit and family == "blank":
                    row.append(" ")
                else:
                    row.append(FAMILY_SHORT.get(family, "?"))
            lines.append(f"  r{y:2d} " + " ".join(row))
        return "\n".join(lines)

    def lit(self) -> list[tuple[int, int]]:
        return [(x, y) for y in range(LOGICAL_ROWS) for x in range(LOGICAL_COLS)
                if self.cell_family(x, y) != "blank"]

    def to_json(self) -> dict:
        return {
            "entries": list(self.entries),
            "grid": self.grid(),
        }


def read_overlay(probe) -> Overlay:
    """Read the BG2 tilemap of the current frame out of the probe."""
    return Overlay.from_blob(probe.dump(BG2_TILEMAP_ADDRESS, BG2_TILEMAP_LENGTH))


def overlay_from_file(path: str | pathlib.Path) -> Overlay:
    return Overlay.from_blob(pathlib.Path(path).read_bytes())
