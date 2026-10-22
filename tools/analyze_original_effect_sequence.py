#!/usr/bin/env python3
"""Decode a hash-bound original GBA OBJ effect sequence from GPU dumps."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress


ROM_BASE = 0x08000000
ACTION_05_HIT_TILES_ADDRESS = 0x08342938
ACTION_05_HIT_PALETTE_ADDRESS = 0x08342DC8
ACTION_05_HIT_TILES_OFFSET = 0x342938
ACTION_05_HIT_PALETTE_OFFSET = 0x342DC8
OBJ_VRAM_OFFSET = 0x10000
OBJ_PALETTE_OFFSET = 0x200

_SHAPE_SIZES = (
    ((8, 8), (16, 16), (32, 32), (64, 64)),
    ((16, 8), (32, 8), (32, 16), (64, 32)),
    ((8, 16), (8, 32), (16, 32), (32, 64)),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_component(
    attr0: int,
    attr1: int,
    attr2: int,
    *,
    base_tile: int,
    tile_count: int,
    palette_bank: int,
    include_semi_transparent: bool,
) -> dict[str, Any] | None:
    affine = bool(attr0 & 0x0100)
    if not affine and attr0 & 0x0200:
        return None
    object_mode = (attr0 >> 10) & 0x03
    if object_mode != 0 and not (
        include_semi_transparent and object_mode == 1
    ):
        return None
    if attr0 & 0x2000:
        return None

    shape = (attr0 >> 14) & 0x03
    size = (attr1 >> 14) & 0x03
    if shape >= len(_SHAPE_SIZES):
        return None
    tile_index = attr2 & 0x03FF
    if not base_tile <= tile_index < base_tile + tile_count:
        return None
    if ((attr2 >> 12) & 0x0F) != palette_bank:
        return None

    x = attr1 & 0x01FF
    if x >= 256:
        x -= 512
    y = attr0 & 0x00FF
    if y >= 160:
        y -= 256
    width, height = _SHAPE_SIZES[shape][size]
    result = {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "tile_offset": tile_index - base_tile,
        "palette_bank": palette_bank,
        "priority": (attr2 >> 10) & 0x03,
        "horizontal_flip": bool(attr1 & 0x1000) if not affine else False,
        "vertical_flip": bool(attr1 & 0x2000) if not affine else False,
    }
    if object_mode == 1:
        result["semi_transparent"] = True
    return result


def decode_oam_components(
    oam: bytes,
    *,
    base_tile: int,
    tile_count: int,
    palette_bank: int,
    include_semi_transparent: bool = False,
) -> list[dict[str, Any]]:
    if len(oam) != 0x400:
        raise ValueError(f"expected 1024-byte OAM dump, got {len(oam)}")
    components = []
    for offset in range(0, len(oam), 8):
        attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, offset)
        component = _decode_component(
            attr0,
            attr1,
            attr2,
            base_tile=base_tile,
            tile_count=tile_count,
            palette_bank=palette_bank,
            include_semi_transparent=include_semi_transparent,
        )
        if component is not None:
            components.append(component)
    return components


def analyze_effect_sequence(
    rom_path: Path,
    trace_dir: Path,
    *,
    first_frame: int,
    last_frame: int,
    base_tile: int,
    tile_count: int,
    palette_bank: int,
    tiles_address: int = ACTION_05_HIT_TILES_ADDRESS,
    palette_address: int = ACTION_05_HIT_PALETTE_ADDRESS,
    include_semi_transparent: bool = False,
    output_path: Path | None = None,
) -> dict[str, Any]:
    if first_frame > last_frame:
        raise ValueError("first_frame must not exceed last_frame")

    rom = rom_path.read_bytes()
    if not ROM_BASE <= tiles_address < ROM_BASE + len(rom):
        raise ValueError(f"tiles_address is outside ROM: 0x{tiles_address:08X}")
    if not ROM_BASE <= palette_address < ROM_BASE + len(rom):
        raise ValueError(
            f"palette_address is outside ROM: 0x{palette_address:08X}"
        )
    tiles_offset = tiles_address - ROM_BASE
    palette_offset = palette_address - ROM_BASE
    tiles = lz77_decompress(rom, tiles_offset)
    palette = lz77_decompress(rom, palette_offset)
    expected_tile_bytes = tile_count * 32
    if len(tiles) != expected_tile_bytes:
        raise ValueError(
            f"tile_count covers {expected_tile_bytes} bytes, "
            f"but ROM resource has {len(tiles)}"
        )
    if len(palette) != 32:
        raise ValueError(
            f"expected one 16-color OBJ palette, got {len(palette)} bytes"
        )

    frames = []
    maximum_components = 0
    active_frames: list[int] = []
    tile_matches = []
    palette_matches = []
    for frame in range(first_frame, last_frame + 1):
        stem = trace_dir / f"gpu-frame-{frame:04d}"
        oam = (stem.with_name(stem.name + "-oam.bin")).read_bytes()
        vram = (stem.with_name(stem.name + "-vram.bin")).read_bytes()
        pram = (stem.with_name(stem.name + "-pram.bin")).read_bytes()
        components = decode_oam_components(
            oam,
            base_tile=base_tile,
            tile_count=tile_count,
            palette_bank=palette_bank,
            include_semi_transparent=include_semi_transparent,
        )
        maximum_components = max(maximum_components, len(components))
        if components:
            active_frames.append(frame)

        tile_start = OBJ_VRAM_OFFSET + base_tile * 32
        tile_match = (
            vram[tile_start : tile_start + len(tiles)] == tiles
        )
        palette_start = OBJ_PALETTE_OFFSET + palette_bank * 32
        palette_match = (
            pram[palette_start : palette_start + len(palette)] == palette
        )
        tile_matches.append(tile_match)
        palette_matches.append(palette_match)
        frames.append(
            {
                "original_frame": frame,
                "components": components,
                "oam_sha256": _sha256(oam),
                "resource_match": {
                    "tiles": tile_match,
                    "palette": palette_match,
                },
            }
        )

    trace_path = trace_dir / "presentation-trace.jsonl"
    result = {
        "schema": "original-oam-effect-sequence-v1",
        "rom_sha256": _sha256(rom),
        "trace_sha256": _sha256(trace_path.read_bytes()),
        "source_frame_range": [first_frame, last_frame],
        "active_frame_start": min(active_frames) if active_frames else None,
        "active_frame_end": max(active_frames) if active_frames else None,
        "active_frame_count": len(active_frames),
        "maximum_components": maximum_components,
        "oam_filter": {
            "base_tile": base_tile,
            "tile_count": tile_count,
            "palette_bank": palette_bank,
            "include_semi_transparent": include_semi_transparent,
            "obj_mapping": "1d",
        },
        "resources": {
            "tiles": {
                "address": f"0x{tiles_address:08X}",
                "decompressed_size": len(tiles),
                "sha256": _sha256(tiles),
                "vram_destination": (
                    f"0x{0x06000000 + OBJ_VRAM_OFFSET + base_tile * 32:08X}"
                ),
                "all_vram_matches": all(tile_matches),
            },
            "palette": {
                "address": f"0x{palette_address:08X}",
                "decompressed_size": len(palette),
                "sha256": _sha256(palette),
                "pram_destination": (
                    f"0x{0x05000000 + OBJ_PALETTE_OFFSET + palette_bank * 32:08X}"
                ),
                "all_pram_matches": all(palette_matches),
            },
        },
        "frames": frames,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("trace_dir", type=Path)
    parser.add_argument("--first-frame", type=int, required=True)
    parser.add_argument("--last-frame", type=int, required=True)
    parser.add_argument("--base-tile", type=int, required=True)
    parser.add_argument("--tile-count", type=int, required=True)
    parser.add_argument("--palette-bank", type=int, required=True)
    parser.add_argument(
        "--tiles-address",
        type=lambda value: int(value, 0),
        default=ACTION_05_HIT_TILES_ADDRESS,
    )
    parser.add_argument(
        "--palette-address",
        type=lambda value: int(value, 0),
        default=ACTION_05_HIT_PALETTE_ADDRESS,
    )
    parser.add_argument(
        "--include-semi-transparent",
        action="store_true",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = analyze_effect_sequence(
        args.rom,
        args.trace_dir,
        first_frame=args.first_frame,
        last_frame=args.last_frame,
        base_tile=args.base_tile,
        tile_count=args.tile_count,
        palette_bank=args.palette_bank,
        tiles_address=args.tiles_address,
        palette_address=args.palette_address,
        include_semi_transparent=args.include_semi_transparent,
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
