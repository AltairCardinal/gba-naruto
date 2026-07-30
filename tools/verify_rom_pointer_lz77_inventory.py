#!/usr/bin/env python3
"""Independently verify rom-pointer-lz77-inventory-v1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any, Iterator


SCHEMA = "rom-pointer-lz77-inventory-v1"
PAYLOAD_NAME = "rom-pointer-lz77-inventory.json"
COMPRESSED_NAME = "uncovered-records.lz77.bin"
DECOMPRESSED_NAME = "uncovered-payloads.bin"
EXPECTED_FILES = {PAYLOAD_NAME, COMPRESSED_NAME, DECOMPRESSED_NAME}
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ADDRESS_PATTERN = re.compile(r"^0[xX][0-9A-Fa-f]{8}$")
LIST_ITEM = "[]"
UPSTREAM_BINDING_METHOD = (
    "hash-pinned artifact JSON schema allowlist of semantic resource-start fields"
)
SELECTION_RULE = {
    "syntax": (
        "valid GBA type-0x10 stream with exact declared-size termination, "
        "in-range back-references, and no output overrun"
    ),
    "source_alignment": 4,
    "pointer_reference_alignment": 4,
    "pointer_domain": "mapped ROM u32 values",
    "runtime_reachability_claimed": False,
}

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

VRAM_WRAPPER = 0x0809C0E8
WRAM_WRAPPER = 0x0809C0EC


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _decode_lz77(rom: bytes, offset: int) -> tuple[int, bytes] | None:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        return None
    size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    if size <= 0:
        return None
    cursor = offset + 4
    result = bytearray()
    try:
        while len(result) < size:
            flags = rom[cursor]
            cursor += 1
            for mask in (0x80, 0x40, 0x20, 0x10, 8, 4, 2, 1):
                if len(result) >= size:
                    break
                if flags & mask:
                    token = (rom[cursor] << 8) | rom[cursor + 1]
                    cursor += 2
                    length = (token >> 12) + 3
                    distance = (token & 0x0FFF) + 1
                    if distance > len(result) or len(result) + length > size:
                        return None
                    for _ in range(length):
                        result.append(result[-distance])
                else:
                    result.append(rom[cursor])
                    cursor += 1
    except IndexError:
        return None
    return cursor, bytes(result)


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


def _decode_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _literal_users(rom: bytes, references: list[int]) -> list[int]:
    result = set()
    for literal_offset in references:
        literal_address = ROM_BASE + literal_offset
        for offset in range(max(0, literal_offset - 0x400), literal_offset, 2):
            instruction = struct.unpack_from("<H", rom, offset)[0]
            if instruction & 0xF800 != 0x4800:
                continue
            target = ((ROM_BASE + offset + 4) & ~3) + (instruction & 0xFF) * 4
            if target == literal_address:
                result.add(ROM_BASE + offset)
    return sorted(result)


def _direct_calls(rom: bytes, users: list[int]) -> list[dict[str, Any]]:
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for user in users:
        start = user - ROM_BASE
        for offset in range(start + 2, min(len(rom) - 3, start + 0x10) + 1, 2):
            first, second = struct.unpack_from("<HH", rom, offset)
            target = _decode_bl(ROM_BASE + offset, first, second)
            if target is None:
                continue
            result[(ROM_BASE + offset, target)] = {
                "callsite": _addr(ROM_BASE + offset),
                "target": _addr(target),
                "known_route": {
                    0x0809C0E8: "LZ77UnCompVram_wrapper",
                    0x0809C0EC: "LZ77UnCompWram_wrapper",
                }.get(target),
            }
    return [result[key] for key in sorted(result)]


Symbol = tuple[int, bool]


def _add_symbols(left: Symbol, right: Symbol) -> Symbol:
    return left[0] + right[0], left[1] or right[1]


def _classify_user(rom: bytes, user: int) -> tuple[str, str | None]:
    registers: list[Symbol] = [(0, True) for _ in range(16)]
    start = user - ROM_BASE
    for offset in range(start, min(len(rom) - 3, start + 0x20), 2):
        instruction = struct.unpack_from("<H", rom, offset)[0]
        address = ROM_BASE + offset
        if instruction & 0xF800 == 0x4800:
            register = (instruction >> 8) & 7
            literal = ((address + 4) & ~3) + (instruction & 0xFF) * 4
            value = struct.unpack_from("<I", rom, literal - ROM_BASE)[0]
            registers[register] = (value, False)
            continue
        if instruction & 0xF800 == 0x2000:
            register = (instruction >> 8) & 7
            registers[register] = (instruction & 0xFF, False)
            continue
        if instruction & 0xF800 in (0x0000, 0x0800):
            shift = (instruction >> 6) & 0x1F
            source = (instruction >> 3) & 7
            destination = instruction & 7
            base, dynamic = registers[source]
            if instruction & 0xF800 == 0x0000:
                registers[destination] = (base << shift, dynamic)
            else:
                registers[destination] = (base >> (shift or 32), dynamic)
            continue
        if instruction & 0xF800 == 0x1800:
            immediate = bool(instruction & 0x0400)
            subtract = bool(instruction & 0x0200)
            operand = (instruction >> 6) & 7
            source = (instruction >> 3) & 7
            destination = instruction & 7
            right = (operand, False) if immediate else registers[operand]
            if subtract:
                right = (-right[0], right[1])
            registers[destination] = _add_symbols(registers[source], right)
            continue
        if instruction & 0xFC00 == 0x4400:
            operation = (instruction >> 8) & 3
            destination = ((instruction >> 4) & 8) | (instruction & 7)
            source = ((instruction >> 3) & 0xF)
            if operation == 0:
                registers[destination] = _add_symbols(
                    registers[destination], registers[source]
                )
            elif operation == 2:
                registers[destination] = registers[source]
            continue
        if instruction & 0xF800 == 0xF000:
            second = struct.unpack_from("<H", rom, offset + 2)[0]
            target = _decode_bl(address, instruction, second)
            if target not in (VRAM_WRAPPER, WRAM_WRAPPER):
                continue
            if target == WRAM_WRAPPER:
                return "visual_metadata", None
            destination, dynamic = registers[1]
            if 0x05000000 <= destination < 0x05000400 and not dynamic:
                return "palette", _addr(destination)
            if 0x06000000 <= destination < 0x06020000:
                if dynamic:
                    return "graphics", "dynamic_obj_vram_slot"
                return "graphics", _addr(destination)
            raise ValueError(
                f"unresolved VRAM wrapper destination at {_addr(address)}"
            )
    raise ValueError(f"no LZ77 wrapper call near {_addr(user)}")


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


def _expected_classification(
    rom: bytes, offset: int, users: list[int], decompressed: bytes
) -> dict[str, Any]:
    observations = [_classify_user(rom, user) for user in users]
    kinds = {kind for kind, _ in observations}
    if len(kinds) != 1:
        raise ValueError(
            f"inconsistent consumer classifications for {_addr(ROM_BASE + offset)}"
        )
    kind = next(iter(kinds))
    destinations = list(
        dict.fromkeys(
            destination
            for _, destination in observations
            if destination is not None
        )
    )
    tilemap = (
        _text_bg_tilemap_metadata(decompressed, destinations)
        if kind == "graphics"
        else None
    )
    if tilemap is not None:
        kind = "visual_metadata"
        route = "LZ77UnCompVram_wrapper"
        domain = "VRAM_screenblock"
    elif kind == "graphics":
        route = "LZ77UnCompVram_wrapper"
        domain = "VRAM"
    elif kind == "palette":
        route = "LZ77UnCompVram_wrapper"
        domain = "PRAM"
    else:
        route = "LZ77UnCompWram_wrapper"
        domain = "WRAM_dynamic"
    result = {
        "kind": kind,
        "load_route": route,
        "destination_domain": domain,
        "destination_addresses": destinations,
        "evidence_type": (
            "static_code_and_payload_shape"
            if tilemap is not None
            else "static_code"
        ),
    }
    if tilemap is not None:
        result["subtype"] = "text_bg_tilemap"
        result["tilemap"] = tilemap
    result["code_windows"] = [
        {
            "gba_start": _addr(user),
            "size": 16,
            "sha256": _sha(rom[user - ROM_BASE : user - ROM_BASE + 16]),
        }
        for user in users
    ]
    return result


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    root = root.resolve()
    artifact = artifact.resolve()
    actual_paths = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file() or path.is_symlink() or path.is_dir()
    } if artifact.is_dir() else set()
    if actual_paths != EXPECTED_FILES | {"manifest.json"}:
        errors.append("artifact file inventory mismatch")
    if artifact.is_dir() and any(path.is_symlink() for path in artifact.rglob("*")):
        errors.append("artifact contains symbolic links")

    try:
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
    except Exception as error:
        errors.append(f"manifest unreadable: {error}")
        manifest = {}
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_id") != SCHEMA
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("payload_schema") != SCHEMA
        or manifest.get("payload_file") != PAYLOAD_NAME
        or set(manifest.get("files", {})) != EXPECTED_FILES
    ):
        errors.append("manifest contract mismatch")
    for relative, expected in manifest.get("files", {}).items():
        try:
            if _sha((artifact / relative).read_bytes()) != expected:
                errors.append(f"manifest hash mismatch: {relative}")
        except OSError as error:
            errors.append(f"artifact file unreadable: {relative}: {error}")
    if errors:
        return {
            "schema": "rom-pointer-lz77-inventory-verification-v1",
            "verified": False,
            "errors": errors,
        }

    try:
        payload = json.loads(
            (artifact / PAYLOAD_NAME).read_text(encoding="utf-8")
        )
        compressed_bundle = (artifact / COMPRESSED_NAME).read_bytes()
        decompressed_bundle = (artifact / DECOMPRESSED_NAME).read_bytes()
        rom = (root / ROM_PATH).read_bytes()
    except Exception as error:
        return {
            "schema": "rom-pointer-lz77-inventory-verification-v1",
            "verified": False,
            "errors": [f"payload input unreadable: {error}"],
        }
    if payload.get("schema") != SCHEMA:
        errors.append("payload schema mismatch")
    expected_implementation = {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_pointer_lz77_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_pointer_lz77_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_pointer_lz77_inventory.py").read_bytes()
        ),
    }
    if payload.get("implementation") != expected_implementation:
        errors.append("implementation identity mismatch")
    expected_producer = {
        "command": [
            "python3",
            "tools/export_rom_pointer_lz77_inventory.py",
            "--root",
            ".",
            "--output-dir",
            "artifacts/rom-pointer-lz77-inventory-v1",
        ],
        **expected_implementation,
    }
    if manifest.get("producer") != expected_producer:
        errors.append("producer evidence mismatch")
    if payload.get("scope") != SCOPE or manifest.get("scope") != SCOPE:
        errors.append("scope mismatch")
    expected_rom = {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }
    if _sha(rom) != ROM_SHA256 or payload.get("rom") != expected_rom:
        errors.append("ROM identity mismatch")
    if payload.get("selection_rule") != SELECTION_RULE:
        errors.append("selection rule mismatch")
    for key, data in (
        ("compressed", compressed_bundle),
        ("decompressed", decompressed_bundle),
    ):
        item = payload.get("bundles", {}).get(key, {})
        expected_file = (
            COMPRESSED_NAME if key == "compressed" else DECOMPRESSED_NAME
        )
        if (
            item.get("file") != expected_file
            or item.get("size") != len(data)
            or item.get("sha256") != _sha(data)
            or set(item) != {"file", "size", "sha256"}
        ):
            errors.append(f"{key} bundle identity mismatch")

    strict = []
    for offset in range(len(rom) - 3):
        if rom[offset] == 0x10 and _decode_lz77(rom, offset) is not None:
            strict.append(offset)
    refs: dict[int, list[int]] = {}
    for pointer_offset in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, pointer_offset)[0]
        if ROM_BASE <= value < ROM_BASE + len(rom):
            refs.setdefault(value - ROM_BASE, []).append(pointer_offset)
    denominator = {
        offset for offset in strict if offset % 4 == 0 and offset in refs
    }

    registry = payload.get("upstream_binding_registry", {})
    listed = registry.get("files", [])
    if registry.get("method") != UPSTREAM_BINDING_METHOD:
        errors.append("upstream registry method mismatch")
    listed_paths = [item.get("path") for item in listed]
    if (
        len(listed_paths) != len(UPSTREAM_FILES)
        or len(set(listed_paths)) != len(listed_paths)
        or set(listed_paths) != set(UPSTREAM_FILES)
    ):
        errors.append("upstream registry path set mismatch")
    registry_by_path = {item.get("path"): item for item in listed}
    bound: set[int] = set()
    for relative, expected_sha in sorted(UPSTREAM_FILES.items()):
        try:
            raw = (root / relative).read_bytes()
            if _sha(raw) != expected_sha:
                errors.append(f"upstream identity mismatch: {relative}")
                continue
            document = json.loads(raw)
        except Exception as error:
            errors.append(f"upstream unreadable: {relative}: {error}")
            continue
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
        expected_item = {
            "path": relative,
            "sha256": expected_sha,
            "bound_record_count": len(addresses),
            "bound_addresses": [
                _addr(ROM_BASE + offset) for offset in sorted(addresses)
            ],
        }
        if registry_by_path.get(relative) != expected_item:
            errors.append(f"upstream registry semantics mismatch: {relative}")
        bound.update(addresses)
    if registry.get("bound_record_count") != len(bound):
        errors.append("upstream union count mismatch")

    uncovered = sorted(denominator - bound)
    records = payload.get("new_records", [])
    if [item.get("file_offset") for item in records] != uncovered:
        errors.append("new record address set mismatch")
    expected_compressed_bundle = bytearray()
    expected_decompressed_bundle = bytearray()
    for record in records:
        offset = record.get("file_offset")
        if not isinstance(offset, int):
            errors.append("record file offset is not an integer")
            continue
        decoded = _decode_lz77(rom, offset)
        if decoded is None:
            errors.append(f"record no longer decodes: {_addr(ROM_BASE + offset)}")
            continue
        end, decompressed = decoded
        compressed = rom[offset:end]
        co = record.get("compressed_bundle_offset")
        do = record.get("decompressed_bundle_offset")
        if not isinstance(co, int) or not isinstance(do, int):
            errors.append(f"record bundle offsets invalid: {_addr(ROM_BASE + offset)}")
            continue
        if co != len(expected_compressed_bundle):
            errors.append(
                f"compressed bundle layout mismatch: {_addr(ROM_BASE + offset)}"
            )
        if do != len(expected_decompressed_bundle):
            errors.append(
                f"decompressed bundle layout mismatch: {_addr(ROM_BASE + offset)}"
            )
        if (
            record.get("gba_address") != _addr(ROM_BASE + offset)
            or record.get("compressed_size") != len(compressed)
            or record.get("compressed_sha256") != _sha(compressed)
            or compressed_bundle[co : co + len(compressed)] != compressed
            or record.get("decompressed_size") != len(decompressed)
            or record.get("decompressed_sha256") != _sha(decompressed)
            or decompressed_bundle[do : do + len(decompressed)] != decompressed
        ):
            errors.append(f"record payload mismatch: {_addr(ROM_BASE + offset)}")
        users = _literal_users(rom, refs[offset])
        if record.get("aligned_pointer_references") != [
            _addr(ROM_BASE + value) for value in refs[offset]
        ]:
            errors.append(f"pointer evidence mismatch: {_addr(ROM_BASE + offset)}")
        if record.get("literal_load_users") != [_addr(value) for value in users]:
            errors.append(f"literal evidence mismatch: {_addr(ROM_BASE + offset)}")
        if record.get("nearby_direct_calls") != _direct_calls(rom, users):
            errors.append(f"call evidence mismatch: {_addr(ROM_BASE + offset)}")
        expected_classification = _expected_classification(
            rom, offset, users, decompressed
        )
        if record.get("classification") != expected_classification:
            errors.append(f"classification mismatch: {_addr(ROM_BASE + offset)}")
        expected_compressed_bundle.extend(compressed)
        expected_decompressed_bundle.extend(decompressed)

    if compressed_bundle != expected_compressed_bundle:
        errors.append("compressed bundle does not exactly match ROM records")
    if decompressed_bundle != expected_decompressed_bundle:
        errors.append("decompressed bundle does not exactly match ROM records")

    expected_summary = {
        "strict_lz77_record_count": len(strict),
        "aligned_pointer_reachable_record_count": len(denominator),
        "previously_bound_record_count": len(bound),
        "newly_exported_record_count": len(uncovered),
        "remaining_unbound_record_count": 0,
    }
    if payload.get("summary") != expected_summary:
        errors.append("summary mismatch")
    expected_verifier = {
        "command": [
            "python3",
            "tools/verify_rom_pointer_lz77_inventory.py",
            "--root",
            ".",
            "--artifact-dir",
            "artifacts/rom-pointer-lz77-inventory-v1",
        ],
        "verifier_sha256": expected_implementation["verifier_sha256"],
        "exit_code": 0,
        "report": {
            "schema": "rom-pointer-lz77-inventory-verification-v1",
            "verified": True,
            "errors": [],
            **expected_summary,
        },
    }
    if manifest.get("verifier") != expected_verifier:
        errors.append("verifier evidence mismatch")
    expected_counts = {
        kind: sum(
            _expected_classification(
                rom,
                offset,
                _literal_users(rom, refs[offset]),
                _decode_lz77(rom, offset)[1],
            )["kind"]
            == kind
            for offset in uncovered
        )
        for kind in ("graphics", "palette", "visual_metadata")
    }
    if payload.get("classification_counts") != expected_counts:
        errors.append("classification counts mismatch")
    if (
        len(strict) != 1099
        or len(denominator) != 896
        or len(bound) != 865
        or len(uncovered) != 31
    ):
        errors.append("expected denominator constants changed")

    return {
        "schema": "rom-pointer-lz77-inventory-verification-v1",
        "verified": not errors,
        "errors": errors,
        "strict_lz77_record_count": len(strict),
        "aligned_pointer_reachable_record_count": len(denominator),
        "previously_bound_record_count": len(bound),
        "newly_exported_record_count": len(uncovered),
        "remaining_unbound_record_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-pointer-lz77-inventory-v1"),
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
