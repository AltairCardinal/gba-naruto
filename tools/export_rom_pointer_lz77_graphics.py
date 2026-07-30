#!/usr/bin/env python3
"""Export candidate atlases for the newly cataloged pointer-reachable graphics."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from tools.gba_image_export import (  # noqa: E402
    indexed_png_from_bgr555,
    render_4bpp_tile_atlas_indices,
)
from tools.inspect_mgba_savestate import load_gba_state  # noqa: E402
from tools.thumb_branch import decode_thumb_bl  # noqa: E402


SCHEMA = "rom-pointer-lz77-graphics-v1"
VERIFY_SCHEMA = "rom-pointer-lz77-graphics-verification-v1"
CATALOG_NAME = "graphics-catalog.json"
RAW_PALETTE_BUNDLE_NAME = "raw-palettes.bgr555.bin"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_ROOT = Path("artifacts/rom-pointer-lz77-inventory-v1")
SOURCE_MANIFEST_SHA256 = (
    "d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33"
)
SOURCE_PAYLOAD_SHA256 = (
    "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
)
CHECKPOINT_DIRECTORY = Path("artifacts/runtime-checkpoints")
CPU_FAST_SET = 0x0809C0DC
CPU_SET = 0x0809C0E0
LZ77_VRAM = 0x0809C0E8
OBJ_VRAM_BASE = 0x06010000
OBJ_VRAM_END = 0x06018000
OBJ_PALETTE_BASE = 0x05000200
OAM_SIZES = {
    0: ((8, 8), (16, 16), (32, 32), (64, 64)),
    1: ((16, 8), (32, 8), (32, 16), (64, 32)),
    2: ((8, 16), (8, 32), (16, 32), (32, 64)),
}
SCOPE = {
    "new_pointer_reachable_graphics_records_cataloged": True,
    "source_palette_bound_subset_previewed": True,
    "unresolved_palette_records_index_previewed": True,
    "all_previews_are_final_visible_images": False,
    "tilemap_or_oam_composition_complete": False,
    "all_raw_graphics_complete": False,
    "all_game_visual_states_complete": False,
    "generic_image_writeback_complete": False,
}
SELECTION_RULE = {
    "window_bytes": 32,
    "sources": (
        "all literal_load_users of the 20 source-inventory graphics records"
    ),
    "accepted_operations": [
        "r0 ROM LZ77 source -> LZ77UnCompVram -> PRAM, size 32",
        (
            "r0 ROM raw source -> CpuSet/CpuFastSet -> PRAM, "
            "exact unit count"
        ),
    ],
    "runtime_oam_rule": (
        "scan every tracked .ss9 in lexical order; require the full graphics "
        "payload at its statically proven OBJ VRAM destination, an active "
        "hardware OAM object whose 4bpp tile range intersects it, one "
        "consistent attr2 palette bank, and one unique exact 32-byte ROM "
        "palette source"
    ),
    "runtime_conflict_policy": (
        "different selected palette bytes or non-unique ROM source leave the "
        "record unresolved"
    ),
    "unknown_instruction_policy": "invalidate r0-r3 (fail closed)",
    "call_policy": "record actual arguments at BL, then invalidate r0-r3",
    "unresolved_rule": (
        "no accepted static palette operation and no accepted runtime OAM "
        "binding"
    ),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _load_source(root: Path) -> tuple[dict[str, Any], bytes]:
    source = root / SOURCE_ROOT
    manifest_bytes = (source / "manifest.json").read_bytes()
    payload_bytes = (source / "rom-pointer-lz77-inventory.json").read_bytes()
    if _sha(manifest_bytes) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source inventory manifest changed")
    if _sha(payload_bytes) != SOURCE_PAYLOAD_SHA256:
        raise ValueError("source inventory payload changed")
    manifest = json.loads(manifest_bytes)
    payload = json.loads(payload_bytes)
    for relative, expected in manifest["files"].items():
        if _sha((source / relative).read_bytes()) != expected:
            raise ValueError(f"source inventory file changed: {relative}")
    if (
        payload.get("schema") != "rom-pointer-lz77-inventory-v1"
        or payload.get("classification_counts", {}).get("graphics") != 20
    ):
        raise ValueError("source inventory graphics contract changed")
    return payload, (source / "uncovered-payloads.bin").read_bytes()


def _tracked_checkpoints(root: Path) -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--",
            f"{CHECKPOINT_DIRECTORY.as_posix()}/*.ss9",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise ValueError(
            "cannot enumerate tracked checkpoints: "
            + completed.stderr.decode("utf-8", "replace").strip()
        )
    paths = sorted(
        root / raw.decode("utf-8")
        for raw in completed.stdout.split(b"\0")
        if raw
    )
    if not paths:
        raise ValueError("no tracked runtime checkpoints found")
    if any(not path.is_file() for path in paths):
        raise ValueError("tracked runtime checkpoint is missing")
    return paths


def _active_4bpp_oam_intersections(
    oam: bytes, *, resource_tile_start: int, resource_tile_end: int
) -> list[dict[str, int]]:
    observations = []
    for index in range(128):
        attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, index * 8)
        affine = bool(attr0 & 0x0100)
        if not affine and attr0 & 0x0200:
            continue
        if attr0 & 0x2000:
            continue
        shape = (attr0 >> 14) & 3
        size = (attr1 >> 14) & 3
        if shape not in OAM_SIZES:
            continue
        width, height = OAM_SIZES[shape][size]
        tile_start = attr2 & 0x03FF
        tile_end = tile_start + width * height // 64
        if tile_start >= resource_tile_end or tile_end <= resource_tile_start:
            continue
        observations.append(
            {
                "oam_index": index,
                "object_tile_start": tile_start,
                "object_tile_end": tile_end,
                "palette_bank": (attr2 >> 12) & 0xF,
                "width": width,
                "height": height,
            }
        )
    return observations


def _discover_runtime_oam_binding(
    root: Path,
    rom: bytes,
    record: dict[str, Any],
    graphics: bytes,
    checkpoints: list[Path],
) -> tuple[int, list[dict[str, Any]]] | None:
    if not graphics or len(graphics) % 32:
        return None
    destinations = [
        int(destination, 16)
        for destination in record["classification"]["destination_addresses"]
        if destination.startswith("0x")
        and OBJ_VRAM_BASE <= int(destination, 16) < OBJ_VRAM_END
        and (int(destination, 16) - OBJ_VRAM_BASE) % 32 == 0
    ]
    accepted = []
    selected: set[tuple[int, bytes]] = set()
    for checkpoint in checkpoints:
        raw = checkpoint.read_bytes()
        state = load_gba_state(checkpoint)
        io = state.read_memory(0x04000000, 0x400)
        if not struct.unpack_from("<H", io, 0)[0] & 0x40:
            continue
        oam = state.read_memory(0x07000000, 0x400)
        for destination in destinations:
            if state.read_memory(destination, len(graphics)) != graphics:
                continue
            tile_start = (destination - OBJ_VRAM_BASE) // 32
            tile_end = tile_start + len(graphics) // 32
            observations = _active_4bpp_oam_intersections(
                oam,
                resource_tile_start=tile_start,
                resource_tile_end=tile_end,
            )
            if not observations:
                continue
            banks = {item["palette_bank"] for item in observations}
            if len(banks) != 1:
                return None
            bank = next(iter(banks))
            palette_address = OBJ_PALETTE_BASE + bank * 32
            palette = state.read_memory(palette_address, 32)
            selected.add((bank, palette))
            accepted.append(
                {
                    "kind": "runtime_oam_raw_rom",
                    "checkpoint_path": checkpoint.relative_to(root).as_posix(),
                    "checkpoint_sha256": _sha(raw),
                    "savestate_version_magic": (
                        f"0x{state.version_magic:08X}"
                    ),
                    "destination": f"0x{destination:08X}",
                    "tile_start": tile_start,
                    "tile_end": tile_end,
                    "oam_observation_count": len(observations),
                    "oam_observations": observations,
                    "palette_bank": bank,
                    "palette_address": f"0x{palette_address:08X}",
                    "palette_sha256": _sha(palette),
                }
            )
    if not accepted or len(selected) != 1:
        return None
    _, palette = next(iter(selected))
    source_offset = rom.find(palette)
    if source_offset < 0 or rom.find(palette, source_offset + 1) >= 0:
        return None
    canonical = accepted[0]
    canonical["matching_checkpoint_count"] = len(
        {item["checkpoint_path"] for item in accepted}
    )
    canonical["scanned_checkpoint_count"] = len(checkpoints)
    canonical["unique_rom_palette_source"] = _address(source_offset)
    return source_offset, [canonical]


def _literal_value(rom: bytes, instruction_offset: int) -> tuple[int, int] | None:
    instruction = struct.unpack_from("<H", rom, instruction_offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    address = ROM_BASE + instruction_offset
    literal = ((address + 4) & ~3) + (instruction & 0xFF) * 4
    if not ROM_BASE <= literal < ROM_BASE + len(rom) - 3:
        return None
    return (instruction >> 8) & 7, struct.unpack_from(
        "<I", rom, literal - ROM_BASE
    )[0]


Symbol = tuple[int, bool, int | None]
UNKNOWN: Symbol = (0, True, None)


def _add(left: Symbol, right: Symbol) -> Symbol:
    origin = left[2] if right[0] == 0 and not right[1] else None
    if left[0] == 0 and left[1]:
        origin = right[2]
    return left[0] + right[0], left[1] or right[1], origin


def discover_palette_operations(
    rom: bytes, graphics_user: int
) -> list[dict[str, Any]]:
    """Discover actual palette calls in one fail-closed 32-byte loader window."""
    start = graphics_user - ROM_BASE
    if start < 0 or start + 2 > len(rom):
        raise ValueError("graphics user is outside the ROM")
    registers: list[Symbol] = [UNKNOWN for _ in range(16)]
    operations = []
    offset = start
    end = min(len(rom) - 3, start + 0x20)
    while offset < end:
        instruction = struct.unpack_from("<H", rom, offset)[0]
        address = ROM_BASE + offset
        literal = _literal_value(rom, offset)
        if literal is not None:
            register, value = literal
            registers[register] = (value, False, address)
            offset += 2
            continue
        if instruction & 0xF800 == 0x2000:
            register = (instruction >> 8) & 7
            registers[register] = (instruction & 0xFF, False, address)
            offset += 2
            continue
        if instruction & 0xF800 in (0x0000, 0x0800):
            shift = (instruction >> 6) & 0x1F
            source = (instruction >> 3) & 7
            destination = instruction & 7
            value, dynamic, origin = registers[source]
            if instruction & 0xF800 == 0:
                registers[destination] = (value << shift, dynamic, origin)
            else:
                registers[destination] = (
                    value >> (shift or 32),
                    dynamic,
                    origin,
                )
            offset += 2
            continue
        if instruction & 0xF800 == 0x1800:
            immediate = bool(instruction & 0x0400)
            subtract = bool(instruction & 0x0200)
            operand = (instruction >> 6) & 7
            source = (instruction >> 3) & 7
            destination = instruction & 7
            right = (operand, False, address) if immediate else registers[operand]
            if subtract:
                right = (-right[0], right[1], right[2])
            registers[destination] = _add(registers[source], right)
            offset += 2
            continue
        if instruction & 0xFC00 == 0x4400:
            operation = (instruction >> 8) & 3
            destination = ((instruction >> 4) & 8) | (instruction & 7)
            source = (instruction >> 3) & 0xF
            if operation == 0:
                registers[destination] = _add(
                    registers[destination], registers[source]
                )
            elif operation == 2:
                registers[destination] = registers[source]
            else:
                for register in range(4):
                    registers[register] = UNKNOWN
            offset += 2
            continue
        if instruction & 0xF800 == 0xF000:
            second = struct.unpack_from("<H", rom, offset + 2)[0]
            target = decode_thumb_bl(address, instruction, second)
            source, source_dynamic, source_load = registers[0]
            destination, destination_dynamic, _ = registers[1]
            count, count_dynamic, _ = registers[2]
            if (
                target == LZ77_VRAM
                and not source_dynamic
                and source_load is not None
                and ROM_BASE <= source < ROM_BASE + len(rom) - 3
                and not destination_dynamic
                and 0x05000000 <= destination < 0x05000400
                and rom[source - ROM_BASE] == 0x10
            ):
                size = int.from_bytes(
                    rom[source - ROM_BASE + 1 : source - ROM_BASE + 4],
                    "little",
                )
                if size == 32:
                    operations.append(
                        {
                            "kind": "lz77_rom",
                            "graphics_user": f"0x{graphics_user:08X}",
                            "source_address": f"0x{source:08X}",
                            "source_load": f"0x{source_load:08X}",
                            "callsite": f"0x{address:08X}",
                            "loader": "LZ77UnCompVram",
                            "size": size,
                            "destination": f"0x{destination:08X}",
                            "code_size": offset + 4 - (source_load - ROM_BASE),
                            "code_sha256": _sha(
                                rom[source_load - ROM_BASE : offset + 4]
                            ),
                        }
                    )
            elif (
                target in (CPU_SET, CPU_FAST_SET)
                and not source_dynamic
                and source_load is not None
                and ROM_BASE <= source < ROM_BASE + len(rom)
                and not destination_dynamic
                and 0x05000000 <= destination < 0x05000400
                and not count_dynamic
                and count > 0
            ):
                operations.append(
                    {
                        "kind": "raw_rom",
                        "graphics_user": f"0x{graphics_user:08X}",
                        "source_address": f"0x{source:08X}",
                        "source_load": f"0x{source_load:08X}",
                        "callsite": f"0x{address:08X}",
                        "loader": (
                            "CpuSet" if target == CPU_SET else "CpuFastSet"
                        ),
                        "unit_count": count,
                        "size": count * (2 if target == CPU_SET else 4),
                        "destination": f"0x{destination:08X}",
                        "code_size": offset + 4 - (source_load - ROM_BASE),
                        "code_sha256": _sha(
                            rom[source_load - ROM_BASE : offset + 4]
                        ),
                    }
                )
            for register in range(4):
                registers[register] = UNKNOWN
            offset += 4
            continue

        # Unsupported instructions fail closed for argument registers.
        for register in range(4):
            registers[register] = UNKNOWN
        offset += 2
    return operations


def _synthetic_palette() -> bytes:
    output = bytearray()
    for index in range(16):
        component = round(index * 31 / 15)
        output.extend(
            struct.pack("<H", component | component << 5 | component << 10)
        )
    return bytes(output)


def _build(
    root: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM changed")
    source, decompressed_bundle = _load_source(root)
    source_records = {
        record["file_offset"]: record for record in source["new_records"]
    }
    graphics_records = [
        record
        for record in source["new_records"]
        if record["classification"]["kind"] == "graphics"
    ]
    if len(graphics_records) != 20:
        raise ValueError("graphics palette denominator changed")
    checkpoints = _tracked_checkpoints(root)

    discovered: dict[int, tuple[str, list[int], list[dict[str, Any]]]] = {}
    raw_operations: dict[int, dict[str, dict[str, Any]]] = {}
    for record in graphics_records:
        operations = []
        for user_text in record["literal_load_users"]:
            operations.extend(
                discover_palette_operations(rom, int(user_text, 16))
            )
        operations = list(
            {
                (
                    item["graphics_user"],
                    item["callsite"],
                    item["source_address"],
                ): item
                for item in operations
            }.values()
        )
        operations.sort(
            key=lambda item: (
                int(item["graphics_user"], 16),
                int(item["callsite"], 16),
                int(item["source_address"], 16),
            )
        )
        kinds = {item["kind"] for item in operations}
        if len(kinds) > 1:
            raise ValueError(
                f"mixed palette routes in one loader window: {record['gba_address']}"
            )
        kind = next(iter(kinds), "unresolved")
        palette_offsets = list(
            dict.fromkeys(
                int(item["source_address"], 16) - ROM_BASE
                for item in operations
            )
        )
        discovered[record["file_offset"]] = (
            kind,
            palette_offsets,
            operations,
        )
        if kind != "raw_rom":
            continue
        for item in operations:
            source_offset = int(item["source_address"], 16) - ROM_BASE
            by_call = raw_operations.setdefault(source_offset, {})
            callsite = item["callsite"]
            copy = {
                key: value
                for key, value in item.items()
                if key not in {"kind", "source_address", "graphics_user"}
            }
            if callsite not in by_call:
                copy["graphics_users"] = [item["graphics_user"]]
                by_call[callsite] = copy
            elif item["graphics_user"] not in by_call[callsite]["graphics_users"]:
                by_call[callsite]["graphics_users"].append(item["graphics_user"])

    for record in graphics_records:
        offset = record["file_offset"]
        if discovered[offset][0] != "unresolved":
            continue
        start = record["decompressed_bundle_offset"]
        graphics = decompressed_bundle[
            start : start + record["decompressed_size"]
        ]
        runtime = _discover_runtime_oam_binding(
            root, rom, record, graphics, checkpoints
        )
        if runtime is None:
            continue
        palette_offset, evidence = runtime
        discovered[offset] = (
            "runtime_oam_raw_rom",
            [palette_offset],
            evidence,
        )

    kind_counts = {
        kind: sum(value[0] == kind for value in discovered.values())
        for kind in (
            "raw_rom",
            "runtime_oam_raw_rom",
            "lz77_rom",
            "unresolved",
        )
    }
    if kind_counts != {
        "raw_rom": 12,
        "runtime_oam_raw_rom": 2,
        "lz77_rom": 4,
        "unresolved": 2,
    }:
        raise ValueError(f"discovered palette denominator changed: {kind_counts}")

    raw_bundle = bytearray()
    raw_sources = []
    raw_by_offset = {}
    for offset, evidence_by_call in sorted(raw_operations.items()):
        copy_evidence = sorted(
            evidence_by_call.values(), key=lambda item: int(item["callsite"], 16)
        )
        for item in copy_evidence:
            item["graphics_users"].sort(key=lambda value: int(value, 16))
        size = max(item["size"] for item in copy_evidence)
        if size % 32 or not 32 <= size <= 512:
            raise ValueError(f"raw palette size is invalid: {_address(offset)}")
        data = rom[offset : offset + size]
        item = {
            "gba_address": _address(offset),
            "file_offset": offset,
            "size": size,
            "sha256": _sha(data),
            "bundle_offset": len(raw_bundle),
            "copy_evidence": copy_evidence,
        }
        raw_sources.append(item)
        raw_by_offset[offset] = data
        raw_bundle.extend(data)

    files: dict[str, bytes] = {}
    entries = []
    source_palette_preview_count = 0
    index_only_preview_count = 0
    synthetic = _synthetic_palette()
    for record in graphics_records:
        offset = record["file_offset"]
        start = record["decompressed_bundle_offset"]
        graphics = decompressed_bundle[
            start : start + record["decompressed_size"]
        ]
        if _sha(graphics) != record["decompressed_sha256"]:
            raise ValueError(f"graphics payload changed: {_address(offset)}")
        pixels, width, height = render_4bpp_tile_atlas_indices(
            graphics, tiles_per_row=16
        )

        kind, palette_offsets, operation_evidence = discovered[offset]
        if kind == "raw_rom":
            palette_variants = [
                (palette_offset, bank, data[bank * 32 : bank * 32 + 32])
                for palette_offset in palette_offsets
                for data in [raw_by_offset[palette_offset]]
                for bank in range(len(data) // 32)
            ]
        elif kind == "runtime_oam_raw_rom":
            palette_variants = [
                (palette_offset, 0, rom[palette_offset : palette_offset + 32])
                for palette_offset in palette_offsets
            ]
        elif kind == "lz77_rom":
            palette_variants = []
            for palette_offset in palette_offsets:
                palette_record = source_records[palette_offset]
                palette_start = palette_record["decompressed_bundle_offset"]
                data = decompressed_bundle[
                    palette_start
                    : palette_start + palette_record["decompressed_size"]
                ]
                if len(data) != 32:
                    raise ValueError(
                        f"LZ77 palette is not one bank: {_address(palette_offset)}"
                    )
                palette_variants.append((palette_offset, 0, data))
        else:
            kind = "unresolved"
            palette_offsets = []
            palette_variants = [(None, 0, synthetic)]

        previews = []
        for palette_offset, bank, palette in palette_variants:
            address_token = (
                "index-only"
                if palette_offset is None
                else f"{ROM_BASE + palette_offset:08x}-bank-{bank:02d}"
            )
            relative = (
                f"previews/{ROM_BASE + offset:08x}-{address_token}.png"
            )
            png = indexed_png_from_bgr555(
                pixels,
                palette,
                width=width,
                height=height,
            )
            files[relative] = png
            origin = (
                "synthetic_index_only" if kind == "unresolved" else kind
            )
            previews.append(
                {
                    "file": relative,
                    "palette_origin": origin,
                    "palette_address": (
                        None if palette_offset is None else _address(palette_offset)
                    ),
                    "palette_bank": bank,
                    "palette_sha256": _sha(palette),
                    "width": width,
                    "height": height,
                    "png_sha256": _sha(png),
                    "rendering_scope": (
                        "4bpp source-order tile atlas candidate; no tilemap, OAM, "
                        "palette-bank selection or runtime composition"
                    ),
                }
            )
        if kind == "unresolved":
            index_only_preview_count += len(previews)
        else:
            source_palette_preview_count += len(previews)
        entries.append(
            {
                "graphics_address": record["gba_address"],
                "graphics_file_offset": offset,
                "decompressed_size": len(graphics),
                "decompressed_sha256": _sha(graphics),
                "palette_binding": {
                    "kind": kind,
                    "source_addresses": [
                        _address(value) for value in palette_offsets
                    ],
                    "discovery_rule": (
                        (
                            "full payload at static OBJ VRAM destination plus "
                            "active hardware OAM palette bank across every "
                            "tracked checkpoint and unique exact ROM palette"
                        )
                        if kind == "runtime_oam_raw_rom"
                        else (
                            "actual r0 source to PRAM palette operation within "
                            "the graphics literal user's 32-byte loader window"
                        )
                    ),
                    "operation_evidence": operation_evidence,
                },
                "previews": previews,
            }
        )

    implementation = {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_pointer_lz77_graphics.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_pointer_lz77_graphics.py").read_bytes()
        ),
    }
    summary = {
        "graphics_record_count": len(entries),
        "raw_palette_bound_count": kind_counts["raw_rom"],
        "runtime_oam_palette_bound_count": kind_counts[
            "runtime_oam_raw_rom"
        ],
        "lz77_palette_bound_count": kind_counts["lz77_rom"],
        "source_palette_bound_count": (
            kind_counts["raw_rom"]
            + kind_counts["runtime_oam_raw_rom"]
            + kind_counts["lz77_rom"]
        ),
        "unresolved_palette_count": kind_counts["unresolved"],
        "source_palette_preview_count": source_palette_preview_count,
        "index_only_preview_count": index_only_preview_count,
        "preview_file_count": source_palette_preview_count
        + index_only_preview_count,
        "raw_palette_source_count": len(raw_sources),
        "raw_palette_bundle_size": len(raw_bundle),
        "runtime_checkpoint_count": len(checkpoints),
    }
    catalog = {
        "schema": SCHEMA,
        "implementation": implementation,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "source_inventory": {
            "path": SOURCE_ROOT.as_posix(),
            "manifest_sha256": SOURCE_MANIFEST_SHA256,
            "payload_sha256": SOURCE_PAYLOAD_SHA256,
        },
        "summary": summary,
        "selection_rule": SELECTION_RULE,
        "raw_palette_sources": raw_sources,
        "graphics": entries,
        "synthetic_index_palette": {
            "size": len(synthetic),
            "sha256": _sha(synthetic),
            "purpose": "diagnostic index visibility only; not a ROM palette",
        },
        "scope": SCOPE,
    }
    files[CATALOG_NAME] = (
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files[RAW_PALETTE_BUNDLE_NAME] = bytes(raw_bundle)
    return catalog, files


def _promotion(catalog: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    summary = catalog["summary"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            relative: _sha(data) for relative, data in sorted(files.items())
        },
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_pointer_lz77_graphics.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/rom-pointer-lz77-graphics-v1",
            ],
            **catalog["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_pointer_lz77_graphics.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-pointer-lz77-graphics-v1",
            ],
            "verifier_sha256": catalog["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                "graphics_record_count": summary["graphics_record_count"],
                "preview_file_count": summary["preview_file_count"],
            },
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    if output.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = output.expanduser().resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be repository or ancestor")
    if not target.exists():
        return target
    if not target.is_dir() or any(path.is_symlink() for path in target.rglob("*")):
        raise ValueError("refusing to replace foreign output")
    try:
        manifest = json.loads(
            (target / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    actual = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or actual != set(manifest.get("files", {})) | {"manifest.json"}
    ):
        raise ValueError("refusing to replace foreign output")
    for relative, expected in manifest["files"].items():
        if _sha((target / relative).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace_output(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
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
    target = _validate_output(root, output)
    catalog, files = _build(root)
    _replace_output(target, files, _promotion(catalog, files))
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/rom-pointer-lz77-graphics-v1"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    catalog = export_artifact(args.root, output)
    print(json.dumps(catalog["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
