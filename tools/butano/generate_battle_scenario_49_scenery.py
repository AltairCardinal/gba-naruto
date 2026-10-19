#!/usr/bin/env python3
"""Generate scenario 49's camera-bound scenery from original GPU evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.butano.indexed_bmp import write_4bpp_bmp
from tools.extract_tileset import decode_4bpp_tiles
from tools.inspect_mgba_savestate import load_gba_state


WIDTH = 32
HEIGHT = 32
TILE_BYTES = 32
TILES_PER_ROW = WIDTH // 8
SOURCE_COMMIT = "c16018a282d00f32ec8323877df68918cc478d8d"
SOURCE_STATE = "artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9"
SOURCE_STATE_SHA256 = "a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1"
SOURCE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expand_five_bit(value: int) -> int:
    return (value << 3) | (value >> 2)


def _decode_palette(data: bytes) -> list[tuple[int, int, int]]:
    if len(data) != 32:
        raise ValueError("scenario 49 chest palette must be 32 bytes")
    result = []
    for index in range(16):
        value = int.from_bytes(data[index * 2 : index * 2 + 2], "little")
        result.append(
            (
                _expand_five_bit(value & 0x1F),
                _expand_five_bit((value >> 5) & 0x1F),
                _expand_five_bit((value >> 10) & 0x1F),
            )
        )
    return result


def _decode_tiles(data: bytes) -> bytes:
    if len(data) != 16 * TILE_BYTES:
        raise ValueError("scenario 49 chest graphics must be 16 OBJ tiles")
    pixels = bytearray(WIDTH * HEIGHT)
    for tile_index in range(16):
        tile_x = tile_index % TILES_PER_ROW
        tile_y = tile_index // TILES_PER_ROW
        tile = data[
            tile_index * TILE_BYTES : (tile_index + 1) * TILE_BYTES
        ]
        for y in range(8):
            for x in range(8):
                packed = tile[y * 4 + x // 2]
                color = (
                    packed & 0x0F if x % 2 == 0 else packed >> 4
                )
                pixels[
                    (tile_y * 8 + y) * WIDTH + tile_x * 8 + x
                ] = color
    return bytes(pixels)


def _destination_cursor_outputs(state: Any, output_dir: Path) -> dict[str, Any]:
    # Two original OBJ tiles, four radii. Frame selection belongs to the runtime;
    # the frozen checkpoint proves the pixels and palette, not animation timing.
    tiles_bytes = state.read_memory(0x06017060, 64)
    tiles = decode_4bpp_tiles(tiles_bytes)
    palette_bytes = state.read_memory(0x050003E0, 32)
    pixels = bytearray(64 * 128)
    for distance in range(4):
        tile = tiles[1 if distance == 3 else 0]
        for vertical in range(2):
            for horizontal in range(2):
                left = 40 + distance if horizontal else 16 - distance
                top = 16 + distance if vertical else 8 - distance
                for y in range(8):
                    for x in range(8):
                        source_x = 7 - x if horizontal else x
                        source_y = 7 - y if vertical else y
                        pixels[(distance * 32 + top + y) * 64 + left + x] = tile[source_y * 8 + source_x]
    write_4bpp_bmp(output_dir / "battle_scenario_49_destination_cursor.bmp",
                  64, 128, bytes(pixels), _decode_palette(palette_bytes))
    metadata = {
        "type": "sprite", "height": 32,
        "source": SOURCE_STATE, "source_commit": SOURCE_COMMIT,
        "source_state_sha256": SOURCE_STATE_SHA256,
    }
    (output_dir / "battle_scenario_49_destination_cursor.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {
        "tile_addresses": ["0x06017060", "0x06017080"],
        "palette_address": "0x050003E0",
        "tiles_sha256": _sha256(tiles_bytes),
        "palette_sha256": _sha256(palette_bytes),
        "frame_count": 4, "sprite_size": [64, 32],
        "anchor": "map cell center",
    }


def generate_outputs(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root)
    output_dir = Path(output_dir)
    if _sha256((root / "rom/base.gba").read_bytes()) != SOURCE_ROM_SHA256:
        raise ValueError("scenario 49 source ROM hash mismatch")
    state_path = root / SOURCE_STATE
    if _sha256(state_path.read_bytes()) != SOURCE_STATE_SHA256:
        raise ValueError("scenario 49 source checkpoint hash mismatch")
    state = load_gba_state(state_path)
    attr0, attr1, attr2, _ = struct.unpack(
        "<4H", state.read_memory(0x07000000 + 12 * 8, 8)
    )
    # This frozen source uses a regular square 32x32 4bpp OBJ in 1D tile mode.
    # Other scenes and OAM layouts need their own consumer-bound source contract.
    if (attr0 & 0xE300) or (attr1 & 0xF000) != 0x8000:
        raise ValueError("scenario 49 chest OBJ layout mismatch")
    display_control = int.from_bytes(state.read_memory(0x04000000, 2), "little")
    if not (display_control & 0x40):
        raise ValueError("scenario 49 chest requires 1D OBJ tile mapping")
    tile_index = attr2 & 0x3FF
    palette_index = attr2 >> 12
    tiles = state.read_memory(0x06010000 + tile_index * TILE_BYTES, 512)
    palette_bytes = state.read_memory(0x05000200 + palette_index * 32, 32)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_4bpp_bmp(
        output_dir / "battle_scenario_49_chest.bmp",
        WIDTH,
        HEIGHT,
        _decode_tiles(tiles),
        _decode_palette(palette_bytes),
    )
    metadata = {
        "type": "sprite",
        "height": HEIGHT,
        "source": (
            "original scenario 49 battle 14 entry OAM 12; "
            + SOURCE_STATE
        ),
        "source_commit": SOURCE_COMMIT,
        "source_state_sha256": SOURCE_STATE_SHA256,
    }
    (
        output_dir / "battle_scenario_49_chest.json"
    ).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": 1,
        "destination_cursor": _destination_cursor_outputs(state, output_dir),
        "battle_id": 14,
        "oam_index": 12,
        "tile_index": tile_index,
        "palette_index": palette_index,
        "world_center": [176, -176],
        "source_commit": SOURCE_COMMIT,
        "source_state_sha256": SOURCE_STATE_SHA256,
        "source_rom_sha256": SOURCE_ROM_SHA256,
        "tiles_sha256": _sha256(tiles),
        "palette_sha256": _sha256(palette_bytes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("butano-sequel/graphics"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            generate_outputs(args.root, args.output_dir),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
