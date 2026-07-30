#!/usr/bin/env python3
"""Export the previously unbound aligned-pointer-reachable ROM LZ77 records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
from typing import Any, Iterator
import uuid


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from tools.thumb_branch import decode_thumb_bl  # noqa: E402


SCHEMA = "rom-pointer-lz77-inventory-v1"
VERIFY_SCHEMA = "rom-pointer-lz77-inventory-verification-v1"
PAYLOAD_NAME = "rom-pointer-lz77-inventory.json"
COMPRESSED_NAME = "uncovered-records.lz77.bin"
DECOMPRESSED_NAME = "uncovered-payloads.bin"
EXPECTED_FILES = {PAYLOAD_NAME, COMPRESSED_NAME, DECOMPRESSED_NAME}
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
LITERAL_LOOKBACK = 0x400
DIRECT_CALL_LOOKAHEAD = 0x10
ADDRESS_PATTERN = re.compile(r"^0[xX][0-9A-Fa-f]{8}$")
LIST_ITEM = "[]"
UPSTREAM_BINDING_METHOD = (
    "hash-pinned artifact JSON schema allowlist of semantic resource-start fields"
)

UPSTREAM_FILES = {
    "artifacts/battle-presentation-glyphs-v1/manifest.json": (
        "ecc44fde0d886b75397d34181112f5b86dbb791b09e3b85797e9b4013f4e74a7"
    ),
    "artifacts/battle-status-bars-v1/battle-status-bars.json": (
        "c8ff2c231c5a0ac111f10c7ca545d285cde0e23c4fca706815ee40277086d4eb"
    ),
    "artifacts/battle-effect-resource-pairs-v1/manifest.json": (
        "716ac580326077127797c634d1f19bbc0aadcfd4db9c577730728b112f002963"
    ),
    "artifacts/battle-effect-sprite-animations-v1/manifest.json": (
        "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848"
    ),
    "artifacts/battle-visual-catalog-v1/manifest.json": (
        "1ccbdfda751953328104c845e061074150324ca69a569330a25263e5be787bcc"
    ),
    "artifacts/bg-resource-canvases-v1/manifest.json": (
        "27096c9129823cc7d4f98aeb1fde304419a1c6abfadaf1cff6e13b80bf2fa99e"
    ),
    "artifacts/cutscene-obj-v1/manifest.json": (
        "b8e1341172decef9f07080879cd8369bc5308274d84383d5c706de72a0b781e7"
    ),
    "artifacts/dialogue-font-v2/manifest.json": (
        "818684d7533ae44bbe4f56b4b6df9a6d6f69612a43ae041dfb5a7b0b0698e69c"
    ),
    "artifacts/initializer-resource-pack-v1/initializer-resource-pack.json": (
        "c096e70c033f804548446272c47d43bfefa72eed173841e152c630c5436efba8"
    ),
    "artifacts/map-canvases-v1/manifest.json": (
        "12a231a570a1cb9e56bec7e2f87cb6de4ac48d673765b1ba536bbc5b0137e19c"
    ),
    "artifacts/menu-portraits-v1/manifest.json": (
        "cd54c20d774a2aa69c7a41db396ca344157320882602b03a00ccd83851a791b3"
    ),
    "artifacts/scene-visual-packs-v1/manifest.json": (
        "4bb40dff9ac2e5641b5e13f46b1dc90bdaa28b9b5615deab7e2a914ae002d5f4"
    ),
    "artifacts/sprite-definition-assets-v2/manifest.json": (
        "ee36523b6a02edb4b803f1835da3dd0d5e460102fc18507b121854d43b882e68"
    ),
    "artifacts/story-visual-layers-v1/manifest.json": (
        "556a7319ce57699e2542c578ce0bd1331b93efda58fde1f364271f12f5052fd8"
    ),
    "artifacts/tile-assets-bg-v1/manifest.json": (
        "ac72a25f412fbcc72d3f29c438a2b13070425cf39cd28ae6cf9e2a66e47e0063"
    ),
    "artifacts/tile-assets-bg-v2/manifest.json": (
        "1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749"
    ),
    "artifacts/world-map-backgrounds-v1/manifest.json": (
        "b9b879841b7605af80e143a9f2f9bbe2e64754d6390b708033f92cc831bd4dd3"
    ),
}

UPSTREAM_BINDING_PATHS = {
    "artifacts/battle-effect-resource-pairs-v1/manifest.json": (
        ("entries", LIST_ITEM, "graphics", "gba_address"),
        ("entries", LIST_ITEM, "palette", "gba_address"),
    ),
    "artifacts/battle-effect-sprite-animations-v1/manifest.json": (
        ("groups", LIST_ITEM, "graphics", "gba_address"),
        ("groups", LIST_ITEM, "palette", "gba_address"),
    ),
    "artifacts/battle-presentation-glyphs-v1/manifest.json": (
        ("glyphs", LIST_ITEM, "pointer"),
    ),
    "artifacts/battle-status-bars-v1/battle-status-bars.json": (
        ("generator", "literals", "palette_lz77"),
    ),
    "artifacts/battle-visual-catalog-v1/manifest.json": tuple(
        ("entries", LIST_ITEM, "descriptor", "layers", LIST_ITEM, resource, field)
        for resource in ("gfx", "tilemap")
        for field in ("gba_address", f"{resource}_pointer")
    ),
    "artifacts/bg-resource-canvases-v1/manifest.json": tuple(
        ("entries", LIST_ITEM, resource, "gba_pointer")
        for resource in ("graphics", "palette", "tilemap")
    ),
    "artifacts/cutscene-obj-v1/manifest.json": (
        ("resources", LIST_ITEM, "gfx_pointer"),
        ("resources", LIST_ITEM, "palette_pointer"),
        ("resources", LIST_ITEM, "gfx", "gba_address"),
        ("resources", LIST_ITEM, "palette", "gba_address"),
    ),
    "artifacts/dialogue-font-v2/manifest.json": (),
    "artifacts/initializer-resource-pack-v1/initializer-resource-pack.json": tuple(
        ("resources", resource, "gba_pointer")
        for resource in ("bg_graphics", "bg_palette", "obj_graphics", "obj_palette")
    ),
    "artifacts/map-canvases-v1/manifest.json": tuple(
        ("entries", LIST_ITEM, "resources", resource, "gba_address")
        for resource in (
            "tile_graphics",
            "bg_palette",
            "primary_layout",
            "alternate_layout",
            "metatile_definitions",
            "collision_grid",
        )
    ),
    "artifacts/menu-portraits-v1/manifest.json": (
        ("portraits", LIST_ITEM, "gfx_pointer"),
        ("unique_resources", LIST_ITEM, "gfx_pointer"),
    ),
    "artifacts/scene-visual-packs-v1/manifest.json": (
        ("packs", LIST_ITEM, "background", "graphics_pointer"),
        ("packs", LIST_ITEM, "background", "tilemap_pointer"),
        ("packs", LIST_ITEM, "obj", "graphics_pointer"),
    ),
    "artifacts/sprite-definition-assets-v2/manifest.json": (
        ("static_resources", "graphics", "gba_address"),
        ("static_resources", "palette", "gba_address"),
        ("runtime_chain", "graphics_source"),
        ("runtime_chain", "palette_source"),
    ),
    "artifacts/story-visual-layers-v1/manifest.json": tuple(
        [
            ("layers", LIST_ITEM, resource, "gba_address")
            for resource in ("gfx", "palette", "tilemap")
        ]
        + [
            ("layers", LIST_ITEM, f"{resource}_pointer")
            for resource in ("gfx", "palette", "tilemap")
        ]
    ),
    "artifacts/tile-assets-bg-v1/manifest.json": tuple(
        ("descriptors", LIST_ITEM, "layers", LIST_ITEM, resource, field)
        for resource in ("gfx", "tilemap")
        for field in ("gba_address", f"{resource}_pointer")
    ),
    "artifacts/tile-assets-bg-v2/manifest.json": tuple(
        ("descriptors", LIST_ITEM, "layers", LIST_ITEM, resource, field)
        for resource in ("gfx", "tilemap")
        for field in ("gba_address", f"{resource}_pointer")
    ),
    "artifacts/world-map-backgrounds-v1/manifest.json": (
        ("pages", LIST_ITEM, "background", "graphics_pointer"),
        ("pages", LIST_ITEM, "background", "tilemap_pointer"),
    ),
}

SCOPE = {
    "strict_lz77_syntax_scan_complete": True,
    "aligned_pointer_reachable_lz77_denominator_complete": True,
    "all_denominator_records_artifact_bound": True,
    "uncovered_records_losslessly_exported": True,
    "all_records_are_graphics": False,
    "raw_uncompressed_graphics_complete": False,
    "raw_palettes_complete": False,
    "procedural_graphics_complete": False,
    "runtime_reachability_complete": False,
    "natural_language_identity_complete": False,
    "generic_image_writeback_complete": False,
    "all_game_visual_states_complete": False,
}

GRAPHICS_DESTINATIONS = {
    0x0B9E94: ["0x06002000"],
    0x12C8B0: ["0x06016FE0"],
    0x12D134: ["0x06017060"],
    0x12D2F0: ["0x06016400"],
    0x3481E0: ["0x060170A0"],
    0x348A3C: ["0x06014000"],
    0x348F00: ["0x06004000"],
    0x349368: ["0x06001000"],
    0x34943C: ["0x06017100"],
    0x3496F8: ["0x06017580"],
    0x3F00C8: ["0x06004000"],
    0x3F08F4: ["0x06000000"],
    0x3F21E4: ["0x06010000"],
    0x3F2A18: ["0x06010900"],
    0x405EA4: ["0x0600E800", "0x06006800"],
    0x405F10: ["0x06000800", "0x06001000", "0x06000000"],
    0x457D3C: ["0x06017780", "dynamic_obj_vram_slot"],
    0x4580C8: ["0x06014000"],
    0x463688: ["0x06009780"],
    0x5B6000: ["0x06016600", "0x06010000", "dynamic_obj_vram_slot"],
    0x5B6880: ["0x0600C000"],
}
PALETTE_DESTINATIONS = {
    0x0B9F5C: ["0x05000180"],
    0x348668: ["0x050003C0"],
    0x3F0AC8: ["0x05000000"],
}
VISUAL_METADATA_OFFSETS = {
    0x34928C,
    0x3F1C98,
    0x3F2108,
    0x4634B8,
    0x46356C,
    0x4635D8,
    0x5B67E0,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _parse_lz77(
    rom: bytes, offset: int, *, materialize: bool
) -> tuple[int, bytes | None] | None:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        return None
    declared = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    if declared <= 0:
        return None
    cursor = offset + 4
    produced = 0
    output = bytearray() if materialize else None
    try:
        while produced < declared:
            flags = rom[cursor]
            cursor += 1
            for bit in range(7, -1, -1):
                if produced >= declared:
                    break
                if flags & (1 << bit):
                    first = rom[cursor]
                    second = rom[cursor + 1]
                    cursor += 2
                    length = (first >> 4) + 3
                    distance = (((first & 0x0F) << 8) | second) + 1
                    if distance > produced or produced + length > declared:
                        return None
                    if output is not None:
                        for _ in range(length):
                            output.append(output[-distance])
                    produced += length
                else:
                    value = rom[cursor]
                    cursor += 1
                    if output is not None:
                        output.append(value)
                    produced += 1
    except IndexError:
        return None
    return cursor, bytes(output) if output is not None else None


def _strict_lz77_offsets(rom: bytes) -> list[int]:
    return [
        offset
        for offset in range(len(rom) - 3)
        if rom[offset] == 0x10
        and _parse_lz77(rom, offset, materialize=False) is not None
    ]


def _aligned_rom_pointer_references(rom: bytes) -> dict[int, list[int]]:
    references: dict[int, list[int]] = {}
    mapped_end = ROM_BASE + len(rom)
    for pointer_offset in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, pointer_offset)[0]
        if ROM_BASE <= value < mapped_end:
            references.setdefault(value - ROM_BASE, []).append(pointer_offset)
    return references


def _values_at_path(value: Any, path: tuple[str, ...]) -> Iterator[Any]:
    if not path:
        yield value
        return
    head, *tail = path
    if head == LIST_ITEM:
        if isinstance(value, list):
            for child in value:
                yield from _values_at_path(child, tuple(tail))
        return
    if isinstance(value, dict) and head in value:
        yield from _values_at_path(value[head], tuple(tail))


def _upstream_registry(
    root: Path, denominator: set[int]
) -> tuple[dict[str, Any], set[int]]:
    files = []
    bound_union: set[int] = set()
    for relative, expected_sha in sorted(UPSTREAM_FILES.items()):
        path = root / relative
        raw = path.read_bytes()
        actual_sha = _sha256(raw)
        if actual_sha != expected_sha:
            raise ValueError(f"upstream artifact changed: {relative}")
        document = json.loads(raw)
        if relative not in UPSTREAM_BINDING_PATHS:
            raise ValueError(f"missing upstream binding schema: {relative}")
        values = (
            value
            for path_pattern in UPSTREAM_BINDING_PATHS[relative]
            for value in _values_at_path(document, path_pattern)
        )
        addresses = {
            int(value, 16) - ROM_BASE
            for value in values
            if isinstance(value, str)
            and ADDRESS_PATTERN.fullmatch(value)
            and ROM_BASE <= int(value, 16) < ROM_BASE + 0x01000000
            and int(value, 16) - ROM_BASE in denominator
        }
        if not addresses and UPSTREAM_BINDING_PATHS[relative]:
            raise ValueError(
                f"upstream artifact binds no denominator record: {relative}"
            )
        bound_union.update(addresses)
        files.append(
            {
                "path": relative,
                "sha256": actual_sha,
                "bound_record_count": len(addresses),
                "bound_addresses": [
                    _address(ROM_BASE + offset) for offset in sorted(addresses)
                ],
            }
        )
    return (
        {
            "method": UPSTREAM_BINDING_METHOD,
            "files": files,
            "bound_record_count": len(bound_union),
        },
        bound_union,
    )


def _literal_load_users(
    rom: bytes, pointer_reference_offsets: list[int]
) -> list[int]:
    users: set[int] = set()
    for literal_offset in pointer_reference_offsets:
        literal_address = ROM_BASE + literal_offset
        for instruction_offset in range(
            max(0, literal_offset - LITERAL_LOOKBACK), literal_offset, 2
        ):
            halfword = struct.unpack_from("<H", rom, instruction_offset)[0]
            if halfword & 0xF800 != 0x4800:
                continue
            target = (
                ((ROM_BASE + instruction_offset + 4) & ~3)
                + (halfword & 0xFF) * 4
            )
            if target == literal_address:
                users.add(ROM_BASE + instruction_offset)
    return sorted(users)


def _nearby_direct_calls(rom: bytes, users: list[int]) -> list[dict[str, Any]]:
    calls: dict[tuple[int, int], dict[str, Any]] = {}
    for user in users:
        start = user - ROM_BASE
        end = min(len(rom) - 3, start + DIRECT_CALL_LOOKAHEAD)
        for offset in range(start + 2, end + 1, 2):
            first, second = struct.unpack_from("<HH", rom, offset)
            target = decode_thumb_bl(ROM_BASE + offset, first, second)
            if target is None:
                continue
            calls[(ROM_BASE + offset, target)] = {
                "callsite": _address(ROM_BASE + offset),
                "target": _address(target),
                "known_route": {
                    0x0809C0E8: "LZ77UnCompVram_wrapper",
                    0x0809C0EC: "LZ77UnCompWram_wrapper",
                }.get(target),
            }
    return [calls[key] for key in sorted(calls)]


def _text_bg_tilemap_metadata(
    decompressed: bytes, destinations: list[str]
) -> dict[str, Any] | None:
    if len(decompressed) != 32 * 20 * 2 or not destinations:
        return None
    numeric_destinations = [
        int(destination, 16)
        for destination in destinations
        if destination.startswith("0x")
    ]
    if (
        len(numeric_destinations) != len(destinations)
        or any(
            not 0x06000000 <= destination < 0x06010000
            or (destination - 0x06000000) % 0x800
            for destination in numeric_destinations
        )
    ):
        return None
    entries = struct.unpack("<640H", decompressed)
    tile_indices = [entry & 0x03FF for entry in entries]
    palette_banks = sorted({entry >> 12 for entry in entries})
    if max(tile_indices) > 0x3F or len(palette_banks) != 1:
        return None
    return {
        "width_entries": 32,
        "height_entries": 20,
        "entry_count": len(entries),
        "entry_size": 2,
        "tile_index_min": min(tile_indices),
        "tile_index_max": max(tile_indices),
        "palette_banks": palette_banks,
        "horizontal_flip_count": sum(bool(entry & 0x0400) for entry in entries),
        "vertical_flip_count": sum(bool(entry & 0x0800) for entry in entries),
    }


def _classification(
    rom: bytes, offset: int, users: list[int], decompressed: bytes
) -> dict[str, Any]:
    if offset in GRAPHICS_DESTINATIONS:
        destinations = GRAPHICS_DESTINATIONS[offset]
        tilemap = _text_bg_tilemap_metadata(decompressed, destinations)
        if tilemap is not None:
            result = {
                "kind": "visual_metadata",
                "subtype": "text_bg_tilemap",
                "load_route": "LZ77UnCompVram_wrapper",
                "destination_domain": "VRAM_screenblock",
                "destination_addresses": destinations,
                "evidence_type": "static_code_and_payload_shape",
                "tilemap": tilemap,
            }
        else:
            result = {
                "kind": "graphics",
                "load_route": "LZ77UnCompVram_wrapper",
                "destination_domain": "VRAM",
                "destination_addresses": destinations,
                "evidence_type": "static_code",
            }
    elif offset in PALETTE_DESTINATIONS:
        result = {
            "kind": "palette",
            "load_route": "LZ77UnCompVram_wrapper",
            "destination_domain": "PRAM",
            "destination_addresses": PALETTE_DESTINATIONS[offset],
            "evidence_type": "static_code",
        }
    elif offset in VISUAL_METADATA_OFFSETS:
        result = {
            "kind": "visual_metadata",
            "load_route": "LZ77UnCompWram_wrapper",
            "destination_domain": "WRAM_dynamic",
            "destination_addresses": [],
            "evidence_type": "static_code",
        }
    else:
        raise ValueError(
            f"missing static classification for {_address(ROM_BASE + offset)}"
        )
    result["code_windows"] = [
        {
            "gba_start": _address(user),
            "size": 16,
            "sha256": _sha256(rom[user - ROM_BASE : user - ROM_BASE + 16]),
        }
        for user in users
    ]
    return result


def _build_payload(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom_path = root / ROM_PATH
    rom = rom_path.read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")

    strict_offsets = _strict_lz77_offsets(rom)
    pointer_references = _aligned_rom_pointer_references(rom)
    denominator = {
        offset
        for offset in strict_offsets
        if offset % 4 == 0 and offset in pointer_references
    }
    registry, previously_bound = _upstream_registry(root, denominator)
    uncovered = sorted(denominator - previously_bound)
    if (
        len(strict_offsets) != 1099
        or len(denominator) != 896
        or len(previously_bound) != 865
        or len(uncovered) != 31
    ):
        raise ValueError("ROM LZ77 inventory denominator changed")

    compressed_bundle = bytearray()
    decompressed_bundle = bytearray()
    records = []
    for offset in uncovered:
        parsed = _parse_lz77(rom, offset, materialize=True)
        if parsed is None or parsed[1] is None:
            raise ValueError(f"failed to reconstruct {_address(ROM_BASE + offset)}")
        end, decompressed = parsed
        compressed = rom[offset:end]
        references = pointer_references[offset]
        users = _literal_load_users(rom, references)
        if not users:
            raise ValueError(
                f"no literal-load consumer for {_address(ROM_BASE + offset)}"
            )
        record = {
            "gba_address": _address(ROM_BASE + offset),
            "file_offset": offset,
            "compressed_size": len(compressed),
            "compressed_sha256": _sha256(compressed),
            "compressed_bundle_offset": len(compressed_bundle),
            "decompressed_size": len(decompressed),
            "decompressed_sha256": _sha256(decompressed),
            "decompressed_bundle_offset": len(decompressed_bundle),
            "aligned_pointer_references": [
                _address(ROM_BASE + value) for value in references
            ],
            "literal_load_users": [_address(value) for value in users],
            "nearby_direct_calls": _nearby_direct_calls(rom, users),
            "classification": _classification(
                rom, offset, users, decompressed
            ),
        }
        records.append(record)
        compressed_bundle.extend(compressed)
        decompressed_bundle.extend(decompressed)

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha256(Path(__file__).read_bytes()),
            "verifier_sha256": _sha256(
                (root / "tools/verify_rom_pointer_lz77_inventory.py").read_bytes()
            ),
            "test_sha256": _sha256(
                (root / "tests/test_export_rom_pointer_lz77_inventory.py").read_bytes()
            ),
        },
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "selection_rule": {
            "syntax": (
                "valid GBA type-0x10 stream with exact declared-size termination, "
                "in-range back-references, and no output overrun"
            ),
            "source_alignment": 4,
            "pointer_reference_alignment": 4,
            "pointer_domain": "mapped ROM u32 values",
            "runtime_reachability_claimed": False,
        },
        "summary": {
            "strict_lz77_record_count": len(strict_offsets),
            "aligned_pointer_reachable_record_count": len(denominator),
            "previously_bound_record_count": len(previously_bound),
            "newly_exported_record_count": len(records),
            "remaining_unbound_record_count": len(
                denominator - previously_bound - set(uncovered)
            ),
        },
        "upstream_binding_registry": registry,
        "new_records": records,
        "classification_counts": {
            kind: sum(
                record["classification"]["kind"] == kind for record in records
            )
            for kind in ("graphics", "palette", "visual_metadata")
        },
        "bundles": {
            "compressed": {
                "file": COMPRESSED_NAME,
                "size": len(compressed_bundle),
                "sha256": _sha256(compressed_bundle),
            },
            "decompressed": {
                "file": DECOMPRESSED_NAME,
                "size": len(decompressed_bundle),
                "sha256": _sha256(decompressed_bundle),
            },
        },
        "scope": SCOPE,
    }
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files = {
        PAYLOAD_NAME: payload_bytes,
        COMPRESSED_NAME: bytes(compressed_bundle),
        DECOMPRESSED_NAME: bytes(decompressed_bundle),
    }
    return payload, files


def _promotion(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    summary = payload["summary"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "payload_schema": payload["schema"],
        "payload_file": PAYLOAD_NAME,
        "files": {
            relative: _sha256(data) for relative, data in sorted(files.items())
        },
        "scope": payload["scope"],
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_pointer_lz77_inventory.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/rom-pointer-lz77-inventory-v1",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_pointer_lz77_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-pointer-lz77-inventory-v1",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                **summary,
            },
        },
    }


def _validate_output_target(root: Path, output: Path) -> Path:
    root = root.resolve()
    if output.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = output.expanduser().resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be repository or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("existing output target is not a directory")
    actual_paths = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file() or path.is_symlink() or path.is_dir()
    }
    if actual_paths != EXPECTED_FILES | {"manifest.json"}:
        raise ValueError("refusing to replace output with unexpected inventory")
    if any(path.is_symlink() for path in target.rglob("*")):
        raise ValueError("refusing to replace output containing symbolic links")
    try:
        manifest = json.loads(
            (target / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_id") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or set(manifest.get("files", {})) != EXPECTED_FILES
    ):
        raise ValueError("refusing to replace foreign output")
    for relative, expected in manifest["files"].items():
        if _sha256((target / relative).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted existing output")
    return target


def _replace_output(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup: Path | None = None
    try:
        for relative, data in sorted(files.items()):
            (temporary / relative).write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and output.exists():
            shutil.rmtree(backup)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    target = _validate_output_target(root, output)
    payload, files = _build_payload(root)
    _replace_output(target, files, _promotion(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/rom-pointer-lz77-inventory-v1"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(
        json.dumps(
            {
                "artifact": str(output),
                "summary": payload["summary"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
