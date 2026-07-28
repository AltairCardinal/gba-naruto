#!/usr/bin/env python3
"""Independently verify the complete battle-effect resource-pair export."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x59911C
TABLE_ADDRESS = ROM_BASE + TABLE_OFFSET
ENTRY_COUNT = 19
ENTRY_SIZE = 8
TABLE_SHA256 = "7d9f94e05b975940bd2e17f55681120782cb7b6f07d0ab6245adef7260d24130"
CODE_SLICES = (
    {
        "name": "effect_resource_builder",
        "file_offset": 0x07FDCC,
        "gba_start": "0x0807FDCC",
        "gba_end": "0x0807FE2C",
        "sha256": "2715bad870d8d7ea84bd03c537f08200be80b178c0dd570aea30155bb9431a84",
    },
    {
        "name": "effect_sequence_selector",
        "file_offset": 0x07FE2C,
        "gba_start": "0x0807FE2C",
        "gba_end": "0x080800A4",
        "sha256": "690232cbbed4b7f9d19602e91feca3299191cccb8369a10d3235b2d415751c94",
    },
)
# Golden decompressed digests recorded independently of the exporter. These
# ensure a shared LZ77 implementation error cannot silently redefine the
# expected ROM payloads.
EXPECTED_GRAPHICS_SHA256 = (
    "d2bdbe77b17e8ab4031f0a100851dffbbe5a8acf3a8b245ce1b6349d758221d3",
    "eb9589427babaaa4d746b365cf1ea3083a5accd5cc408d53ac9c83131fb82475",
    "eb9589427babaaa4d746b365cf1ea3083a5accd5cc408d53ac9c83131fb82475",
    "20ba57e9b2eead364b30e256ec03aa1ec28b068849c47bba98972f44e68a0617",
    "6628fdc3365f8d6f16b134797be5f9a1c7cb48662ffeeea634ace058c659bb32",
    "483d47b29f6fbdde039ccf91e3141025896269f2b0a329a2864c6c06bf898036",
    "4839e96e137469eb2a4ddc02c14e9c2f3b197a77b62467f9a19f70fea5ff2188",
    "42f39b22b077c6e33349f89436b07aa7d4e83527023b43e5d3347f7d4eb76749",
    "d0474020d782fc88a6eeaa25768b09d367f3d9566354d713246b51d2179ede05",
    "942c4ee118b7c21375ee8386fc253f0820dc0297105b5b0a4edb574188ef0906",
    "0b5d70562a4c656a0d11ab0e59b89479a7237be924d8a0765578dd132459e54a",
    "e1da042b138c01ac462f756407cf05c73fc003da9952c7de059946e347141b03",
    "64033fc15513e33c63e1d9cdb9a7e5cd4f3d90f84e305463dd652a64f7a38d8a",
    "878505bd0d11d88fb0c72d9feeee8c4604625985cf9e496a3becb21a5165e867",
    "caf034cec9cf78cf35763eb7416d25ef431f76f06252221390ef05ab21c0407a",
    "1ba47dbc5ca54b40027b00c9baae52b3ce966b239b89e70c6eea483a8bcd0aad",
    "842b8ef56a357e93a0f88ca5cdf2839d360663463809a129560a6e98d6e2c37e",
    "9162bda2e90536bbe5982e94b4d4de9b18111538b548137ca057701d36b7bc55",
)
EXPECTED_PALETTE_SHA256 = (
    "baf6d16005215ced81fbddd5597f08cbc12441e468e737be9a3fb9a89ac04b67",
    "70c511e326da6ce384f358d0dfe798d71dd44f181f6bcaa693e77aa456f5422e",
    "c0e21753834c2ca38588891ecf78596fa7234012bb0c1a3f69ceb2ccc7619f95",
    "4d7cc7492e047b370eff00378883b6b7f818c6961aa277495381b81d2a56daff",
    "c00b7ea1d6748f60c387c12d2083da584a65a7e654e61a95bdfe25d1a803dc61",
    "6393b73a92bf5e950fdf7640a26ba76ea995c53aa8b984bc376559f0004d1aa5",
    "ade17055c76ef587fea1acb9a01737ee10c199754b961c3dfc4d2a874fac85a4",
    "609fd93993e4e4222154a44932ba1d634c070864d5e2ac3de7e186216cd8a9d0",
    "04cfd54690521de6ca3649fe20c743c0c439273a66860671bb3614a00db6c413",
    "5c973ed0591a365d58cf976cb8bd6b5cf176bd620c79416475f3c4f98782cd0c",
    "29df643a21db41dd57a89be093d1fd7415717856dc018da65bc40926d5109b0c",
    "79c80aa69e19aa0034f6b9828a5d9b7b6d9499b67b93c72f04d3ffcd0c7a8e43",
    "afb5d06c793a020bbc7d21d56aceaf842e2c994c36d3adae2e458875baa1a4db",
    "2a4e16536349b52f028284eacbaa3e6047b02047b6e77af7d26914320b514d29",
    "cb86625b5c5d976d388d055aeeb9cbae97effd7efb021bce01e252030b54d1e1",
    "3856b4b91a67ee3e5bc2149a3d3cca18c1b2c922396fe8382a3ddeb620b26073",
    "3856b4b91a67ee3e5bc2149a3d3cca18c1b2c922396fe8382a3ddeb620b26073",
    "d53a7a56bded0b6727002a3fb4ad69454dccee15e8f849ad3a16c3b5639244c1",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer {_address(pointer)} is outside the ROM")
    return offset


def _read_lz77(rom: bytes, offset: int) -> tuple[bytes, bytes]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"resource is not GBA LZ77 at 0x{offset:06X}")
    output_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    output = bytearray()
    cursor = offset + 4
    while len(output) < output_size:
        if cursor >= len(rom):
            raise ValueError(f"truncated LZ77 flags at 0x{cursor:06X}")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= output_size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError(
                        f"truncated LZ77 back-reference at 0x{cursor:06X}"
                    )
                first = rom[cursor]
                second = rom[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                distance = ((first & 0x0F) << 8) + second + 1
                if distance > len(output):
                    raise ValueError(
                        f"invalid LZ77 distance {distance} at 0x{cursor - 2:06X}"
                    )
                if len(output) + length > output_size:
                    raise ValueError("LZ77 copy exceeds declared output size")
                source = len(output) - distance
                for _ in range(length):
                    output.append(output[source])
                    source += 1
            else:
                if cursor >= len(rom):
                    raise ValueError(f"truncated LZ77 literal at 0x{cursor:06X}")
                output.append(rom[cursor])
                cursor += 1
    return rom[offset:cursor], bytes(output)


def _palette_rgb(palette: bytes) -> list[int]:
    rgb: list[int] = []
    for offset in range(0, len(palette), 2):
        color = int.from_bytes(palette[offset : offset + 2], "little") & 0x7FFF
        for shift in (0, 5, 10):
            value = (color >> shift) & 0x1F
            rgb.append((value << 3) | (value >> 2))
    return rgb


def _atlas_pixels(graphics: bytes) -> tuple[bytes, int, int, int]:
    tile_count = len(graphics) // 32
    tiles_per_row = min(16, tile_count)
    width = tiles_per_row * 8
    height = ((tile_count + tiles_per_row - 1) // tiles_per_row) * 8
    pixels = bytearray(width * height)
    for tile_index in range(tile_count):
        tile_x = tile_index % tiles_per_row
        tile_y = tile_index // tiles_per_row
        tile_start = tile_index * 32
        for y in range(8):
            destination = (tile_y * 8 + y) * width + tile_x * 8
            for x in range(8):
                packed = graphics[tile_start + y * 4 + x // 2]
                pixels[destination + x] = (
                    packed >> (4 if x & 1 else 0)
                ) & 0x0F
    return bytes(pixels), width, height, tiles_per_row


def _compare(
    expected: Any,
    actual: Any,
    path: str,
    errors: list[str],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: expected object, got {type(actual).__name__}")
            return
        for key in expected:
            if key not in actual:
                errors.append(f"{path}.{key}: missing")
            else:
                _compare(expected[key], actual[key], f"{path}.{key}", errors)
        for key in actual.keys() - expected.keys():
            errors.append(f"{path}.{key}: unexpected")
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(f"{path}: expected list, got {type(actual).__name__}")
            return
        if len(expected) != len(actual):
            errors.append(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            _compare(expected_item, actual_item, f"{path}[{index}]", errors)
    elif expected != actual:
        errors.append(f"{path}: {actual!r} != {expected!r}")


def _expected_manifest(rom: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    table = rom[TABLE_OFFSET : TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE]
    if _sha256(table) != TABLE_SHA256:
        raise ValueError("battle-effect resource-pair table SHA-256 mismatch")
    if table[:ENTRY_SIZE] != b"\0" * ENTRY_SIZE:
        raise ValueError("battle-effect resource group zero is not the sentinel")
    entries: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for group_id in range(1, ENTRY_COUNT):
        graphics_pointer, palette_pointer = struct.unpack_from(
            "<II",
            table,
            group_id * ENTRY_SIZE,
        )
        graphics_compressed, graphics = _read_lz77(
            rom,
            _rom_offset(graphics_pointer, len(rom)),
        )
        palette_compressed, palette = _read_lz77(
            rom,
            _rom_offset(palette_pointer, len(rom)),
        )
        if not graphics or len(graphics) % 32:
            raise ValueError(f"group {group_id} graphics are not 4bpp tile aligned")
        if len(palette) != 32:
            raise ValueError(f"group {group_id} palette size is not 32")
        graphics_sha256 = _sha256(graphics)
        palette_sha256 = _sha256(palette)
        if graphics_sha256 != EXPECTED_GRAPHICS_SHA256[group_id - 1]:
            raise ValueError(
                f"group {group_id} graphics differ from the golden digest"
            )
        if palette_sha256 != EXPECTED_PALETTE_SHA256[group_id - 1]:
            raise ValueError(
                f"group {group_id} palette differs from the golden digest"
            )
        pixels, width, height, tiles_per_row = _atlas_pixels(graphics)
        graphics_name = f"group-{group_id:02d}-graphics-4bpp.bin"
        palette_name = f"group-{group_id:02d}-palette-bgr555.bin"
        atlas_name = f"group-{group_id:02d}-atlas.png"
        payloads[graphics_name] = graphics
        payloads[palette_name] = palette
        entries.append(
            {
                "group_id": group_id,
                "table_entry_file_offset": TABLE_OFFSET + group_id * ENTRY_SIZE,
                "table_entry_gba_address": _address(
                    TABLE_ADDRESS + group_id * ENTRY_SIZE
                ),
                "pair_raw_hex": table[
                    group_id * ENTRY_SIZE : (group_id + 1) * ENTRY_SIZE
                ].hex(),
                "graphics": {
                    "gba_address": _address(graphics_pointer),
                    "file_offset": graphics_pointer - ROM_BASE,
                    "compressed_size": len(graphics_compressed),
                    "compressed_sha256": _sha256(graphics_compressed),
                    "decompressed_size": len(graphics),
                    "decompressed_sha256": graphics_sha256,
                    "tile_count": len(graphics) // 32,
                    "output_bin": graphics_name,
                },
                "palette": {
                    "gba_address": _address(palette_pointer),
                    "file_offset": palette_pointer - ROM_BASE,
                    "compressed_size": len(palette_compressed),
                    "compressed_sha256": _sha256(palette_compressed),
                    "decompressed_size": len(palette),
                    "decompressed_sha256": palette_sha256,
                    "color_count": 16,
                    "transparent_index": 0,
                    "output_bin": palette_name,
                },
                "atlas": {
                    "png": atlas_name,
                    "width": width,
                    "height": height,
                    "tiles_per_row": tiles_per_row,
                    "tile_order": (
                        "GBA 4bpp tiles, row-major, "
                        f"{tiles_per_row} tiles per row"
                    ),
                },
            }
        )
        payloads[f"{atlas_name}.pixels"] = pixels

    code_slices: list[dict[str, Any]] = []
    for expected in CODE_SLICES:
        item = dict(expected)
        start = int(item["file_offset"])
        end = int(str(item["gba_end"]), 16) - ROM_BASE
        if _sha256(rom[start:end]) != item["sha256"]:
            raise ValueError(f"{item['name']} SHA-256 mismatch")
        code_slices.append(item)
    manifest = {
        "schema": "battle-effect-resource-pairs-v1",
        "rom": {
            "path": "rom/base.gba",
            "sha256": _sha256(rom),
        },
        "resource_pair_table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": _address(TABLE_ADDRESS),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "valid_group_ids": list(range(1, ENTRY_COUNT)),
            "sha256": _sha256(table),
        },
        "valid_resource_pair_count": len(entries),
        "entries": entries,
        "consumer_code_slices": code_slices,
        "scope": {
            "canonical_static_graphics_exported": True,
            "canonical_static_palettes_exported": True,
            "resource_group_to_sequence_mapping_complete": False,
            "oam_composition_complete": False,
            "frame_hold_timing_complete": False,
            "audio_binding_complete": False,
        },
    }
    return manifest, payloads


def verify_battle_effect_resource_pairs(
    root: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    artifact_dir = Path(artifact_dir)
    errors: list[str] = []
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        return {
            "verified_resource_pairs": 0,
            "verified_atlases": 0,
            "errors": ["rom.sha256: unexpected base ROM"],
        }
    try:
        expected, payloads = _expected_manifest(rom)
    except ValueError as error:
        return {
            "verified_resource_pairs": 0,
            "verified_atlases": 0,
            "errors": [str(error)],
        }

    manifest_path = artifact_dir / "manifest.json"
    try:
        actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "verified_resource_pairs": 0,
            "verified_atlases": 0,
            "errors": [f"manifest.json: {error}"],
        }

    expected_files = {"manifest.json"}
    verified_atlases = 0
    for entry in expected["entries"]:
        graphics_name = entry["graphics"]["output_bin"]
        palette_name = entry["palette"]["output_bin"]
        atlas_name = entry["atlas"]["png"]
        expected_files.update((graphics_name, palette_name, atlas_name))
        for name in (graphics_name, palette_name):
            path = artifact_dir / name
            try:
                content = path.read_bytes()
            except OSError as error:
                errors.append(f"{name}: {error}")
                continue
            if content != payloads[name]:
                errors.append(f"{name}: bytes differ from ROM")

        atlas_path = artifact_dir / atlas_name
        try:
            with Image.open(atlas_path) as image:
                image.load()
                pixels = payloads[f"{atlas_name}.pixels"]
                expected_size = (entry["atlas"]["width"], entry["atlas"]["height"])
                if image.mode != "P":
                    errors.append(f"{atlas_name}: mode {image.mode} != P")
                if image.size != expected_size:
                    errors.append(
                        f"{atlas_name}: size {image.size} != {expected_size}"
                    )
                if image.tobytes() != pixels:
                    errors.append(f"{atlas_name}: indexed pixels differ from ROM")
                if image.info.get("transparency") != 0:
                    errors.append(f"{atlas_name}: transparent index is not 0")
                actual_palette = image.getpalette()
                expected_palette = _palette_rgb(
                    payloads[palette_name]
                )
                if (
                    actual_palette is None
                    or actual_palette[: len(expected_palette)] != expected_palette
                ):
                    errors.append(f"{atlas_name}: RGB palette differs from ROM")
            entry["atlas"]["sha256"] = _sha256(atlas_path.read_bytes())
            verified_atlases += 1
        except (OSError, ValueError) as error:
            errors.append(f"{atlas_name}: {error}")

    actual_files = {path.name for path in artifact_dir.iterdir() if path.is_file()}
    for missing in sorted(expected_files - actual_files):
        errors.append(f"{missing}: missing")
    for unexpected in sorted(actual_files - expected_files):
        errors.append(f"{unexpected}: unexpected")
    _compare(expected, actual, "manifest", errors)
    return {
        "verified_resource_pairs": len(expected["entries"]),
        "verified_atlases": verified_atlases,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/battle-effect-resource-pairs-v1"),
    )
    args = parser.parse_args()
    result = verify_battle_effect_resource_pairs(args.root, args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
