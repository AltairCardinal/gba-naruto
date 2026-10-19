#!/usr/bin/env python3
"""Compare scenario-49's original BG2 range elements with the runtime style."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Sequence


ORIGINAL = Path(
    "artifacts/scenario-49-battle-14-original-ui-boundaries-v1/"
    "turn4-target-selection"
)
STYLE_HEADER = Path(
    "butano-sequel/game/include/konoha/battle_range_ui_style.h"
)
RUNTIME_SOURCE = Path("butano-sequel/game/src/battle_runtime_scene.cpp")
CELL_BASE_TILES = (256, 262, 266, 270, 274, 278)
COLOR_NAMES = (
    "grid_secondary",
    "move_primary",
    "move_secondary",
    "attack_primary",
    "attack_secondary",
    "cursor_primary",
    "cursor_secondary",
    "target_primary",
    "target_secondary",
    "blocked_primary",
    "blocked_secondary",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _decode_4bpp_tile(vram: bytes, tile_index: int) -> list[int]:
    offset = tile_index * 32
    packed = vram[offset : offset + 32]
    if len(packed) != 32:
        raise ValueError(f"tile {tile_index} is outside original VRAM")
    pixels: list[int] = []
    for value in packed:
        pixels.extend((value & 0x0F, value >> 4))
    return pixels


def _original_cell(vram: bytes, base_tile: int) -> list[int]:
    if base_tile == 256:
        # The transparent role keeps six source tiles because the original
        # uploader preserves distinct all-zero top/interior and bottom
        # entries even though their decoded pixels are identical.
        tile_indices = (256, 257, 257, 258, 259, 260, 260, 261)
    else:
        tile_indices = (
            base_tile,
            base_tile,
            base_tile,
            base_tile + 1,
            base_tile + 2,
            base_tile + 2,
            base_tile + 2,
            base_tile + 3,
        )
    tiles = [_decode_4bpp_tile(vram, index) for index in tile_indices]
    output: list[int] = []
    for cell_y in range(16):
        tile_row = cell_y // 8
        local_y = cell_y % 8
        for tile_x in range(4):
            tile = tiles[tile_row * 4 + tile_x]
            start = local_y * 8
            output.extend(tile[start : start + 8])
    return output


def _expected_cell(role_index: int) -> list[int]:
    primary = role_index * 2
    secondary = primary + 1
    output: list[int] = []
    for y in range(16):
        for x in range(32):
            if x == 31 or y == 15:
                output.append(secondary)
            else:
                output.append(primary)
    return output


def _parse_style_colors(source: str) -> dict[str, tuple[int, int, int]]:
    colors: dict[str, tuple[int, int, int]] = {}
    for name in COLOR_NAMES:
        match = re.search(
            rf"battle_range_ui_{name}_color\s*=\s*\{{"
            rf"\s*(\d+),\s*(\d+),\s*(\d+),?\s*\}}",
            source,
        )
        if not match:
            raise ValueError(f"runtime style has no {name} color")
        colors[name] = tuple(int(value) for value in match.groups())
    return colors


def _parse_palette_indices(source: str) -> dict[str, int]:
    indices: dict[str, int] = {}
    for name in COLOR_NAMES:
        match = re.search(rf"\b{name}\s*=\s*(\d+)", source)
        if not match:
            raise ValueError(f"runtime style has no {name} palette index")
        indices[name] = int(match.group(1))
    return indices


def verify_range_ui(root: Path | str) -> dict[str, object]:
    root = Path(root)
    original = root / ORIGINAL
    io_path = original / "io.bin"
    pram_path = original / "pram.bin"
    vram_path = original / "vram.bin"
    io = io_path.read_bytes()
    pram = pram_path.read_bytes()
    vram = vram_path.read_bytes()
    if (len(io), len(pram), len(vram)) != (0x400, 0x400, 0x18000):
        raise ValueError("original GPU region sizes are invalid")

    dispcnt = _u16(io, 0)
    bg2_control = _u16(io, 0x0C)
    blend_alpha = _u16(io, 0x52)
    if not dispcnt & (1 << 10):
        raise ValueError("original target-selection state has BG2 disabled")
    if bg2_control != 0x0202:
        raise ValueError(f"unexpected original BG2CNT 0x{bg2_control:04X}")

    original_cells: list[int] = []
    expected_cells: list[int] = []
    for role_index, base_tile in enumerate(CELL_BASE_TILES):
        original_cells.extend(_original_cell(vram, base_tile))
        expected_cells.extend(_expected_cell(role_index))

    original_colors = []
    for palette_index in range(1, 12):
        color = _u16(pram, (12 * 16 + palette_index) * 2)
        original_colors.append(
            (color & 0x1F, (color >> 5) & 0x1F, (color >> 10) & 0x1F)
        )

    style_source = (root / STYLE_HEADER).read_text(encoding="utf-8")
    runtime_source = (root / RUNTIME_SOURCE).read_text(encoding="utf-8")
    style_colors = _parse_style_colors(style_source)
    style_indices = _parse_palette_indices(style_source)
    runtime_colors = [style_colors[name] for name in COLOR_NAMES]
    expected_indices = list(range(225, 236))
    actual_indices = [style_indices[name] for name in COLOR_NAMES]

    return {
        "schema": "scenario-49-range-ui-element-comparison-v1",
        "original_gpu": {
            "directory": ORIGINAL.as_posix(),
            "io_sha256": _sha256(io_path),
            "pram_sha256": _sha256(pram_path),
            "vram_sha256": _sha256(vram_path),
        },
        "original_bg2": {
            "control": f"0x{bg2_control:04X}",
            "palette_bank": 12,
            "blend_weights": [blend_alpha & 0x1F, (blend_alpha >> 8) & 0x1F],
        },
        "cell_pixels": {
            "compared": len(expected_cells),
            "different": sum(
                left != right
                for left, right in zip(
                    original_cells,
                    expected_cells,
                    strict=True,
                )
            ),
            "roles": [
                "grid",
                "move",
                "attack_range",
                "cursor",
                "target",
                "blocked",
            ],
        },
        "palette_entries": {
            "compared": len(original_colors),
            "different": sum(
                left != right
                for left, right in zip(
                    original_colors,
                    runtime_colors,
                    strict=True,
                )
            ),
            "original_rgb5": original_colors,
            "runtime_rgb5": runtime_colors,
            "runtime_indices": actual_indices,
            "runtime_indices_expected": expected_indices,
            "runtime_indices_match": actual_indices == expected_indices,
        },
        "runtime_contract": {
            "cell_kind_count": 6,
            "blocked_rows": "state.blocked_overlay_rows[" in runtime_source,
            "full_grid": (
                "if(! in_move_range && ! in_range && ! legal_target)"
                not in runtime_source
            ),
            "range_palette_first": 224,
            "panel_palette_first": 240,
            "separate_palette_reservations": (
                "range_palette_first_color = 224" in runtime_source
                and "action_palette_first_color = 240" in runtime_source
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = verify_range_ui(args.root)
    if (
        report["cell_pixels"]["different"]
        or report["palette_entries"]["different"]
        or not report["palette_entries"]["runtime_indices_match"]
        or not report["runtime_contract"]["blocked_rows"]
        or not report["runtime_contract"]["full_grid"]
        or not report["runtime_contract"]["separate_palette_reservations"]
    ):
        raise ValueError("scenario-49 range UI comparison failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
