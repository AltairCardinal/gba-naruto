#!/usr/bin/env python3
"""Independently verify rom-pointer-lz77-graphics-v1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from typing import Any
import zlib


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
STATE_SIZE = 0x61000
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
        raise ValueError("cannot enumerate tracked runtime checkpoints")
    paths = sorted(
        root / raw.decode("utf-8")
        for raw in completed.stdout.split(b"\0")
        if raw
    )
    if not paths or any(not path.is_file() for path in paths):
        raise ValueError("tracked runtime checkpoint set is incomplete")
    return paths


def _load_state(path: Path) -> tuple[bytes, bytes]:
    raw = path.read_bytes()
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("savestate is not a PNG")
    cursor = 8
    state_payloads = []
    saw_iend = False
    while cursor < len(raw):
        if cursor + 12 > len(raw):
            raise ValueError("truncated savestate PNG")
        size = struct.unpack_from(">I", raw, cursor)[0]
        tag = raw[cursor + 4 : cursor + 8]
        start = cursor + 8
        end = start + size
        if end + 4 > len(raw):
            raise ValueError("truncated savestate PNG chunk")
        payload = raw[start:end]
        stored_crc = struct.unpack_from(">I", raw, end)[0]
        if zlib.crc32(tag + payload) & 0xFFFFFFFF != stored_crc:
            raise ValueError("savestate PNG CRC mismatch")
        if tag == b"gbAs":
            state_payloads.append(payload)
        cursor = end + 4
        if tag == b"IEND":
            if payload or cursor != len(raw):
                raise ValueError("invalid savestate PNG IEND")
            saw_iend = True
            break
    if not saw_iend or len(state_payloads) != 1:
        raise ValueError("savestate PNG state payload mismatch")
    decompressor = zlib.decompressobj()
    state = decompressor.decompress(state_payloads[0], STATE_SIZE + 1)
    state += decompressor.flush()
    if (
        len(state) != STATE_SIZE
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise ValueError("invalid compressed savestate payload")
    version = struct.unpack_from("<I", state, 0)[0]
    if not 0x01000000 <= version <= 0x0100000B:
        raise ValueError("unsupported savestate version")
    return raw, state


def _state_memory(state: bytes, address: int, size: int) -> bytes:
    regions = (
        (0x04000000, 0x00400, 0x00400),
        (0x05000000, 0x00400, 0x00800),
        (0x07000000, 0x00400, 0x00C00),
        (0x06000000, 0x18000, 0x01000),
    )
    for base, length, state_offset in regions:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[state_offset + relative : state_offset + relative + size]
    raise ValueError("savestate memory read is outside GPU memory")


def _oam_intersections(
    oam: bytes, resource_tile_start: int, resource_tile_end: int
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


def _runtime_binding(
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
        raw, state = _load_state(checkpoint)
        if not struct.unpack_from(
            "<H", _state_memory(state, 0x04000000, 2)
        )[0] & 0x40:
            continue
        oam = _state_memory(state, 0x07000000, 0x400)
        for destination in destinations:
            if _state_memory(state, destination, len(graphics)) != graphics:
                continue
            tile_start = (destination - OBJ_VRAM_BASE) // 32
            tile_end = tile_start + len(graphics) // 32
            observations = _oam_intersections(oam, tile_start, tile_end)
            if not observations:
                continue
            banks = {item["palette_bank"] for item in observations}
            if len(banks) != 1:
                return None
            bank = next(iter(banks))
            palette_address = OBJ_PALETTE_BASE + bank * 32
            palette = _state_memory(state, palette_address, 32)
            selected.add((bank, palette))
            accepted.append(
                {
                    "kind": "runtime_oam_raw_rom",
                    "checkpoint_path": checkpoint.relative_to(root).as_posix(),
                    "checkpoint_sha256": _sha(raw),
                    "savestate_version_magic": (
                        f"0x{struct.unpack_from('<I', state, 0)[0]:08X}"
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


def _decode_bl(address: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return address + 4 + displacement


def _decode_lz77(rom: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"not LZ77 at {_address(offset)}")
    size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        flags = rom[cursor]
        cursor += 1
        for mask in (0x80, 0x40, 0x20, 0x10, 8, 4, 2, 1):
            if len(output) >= size:
                break
            if flags & mask:
                token = (rom[cursor] << 8) | rom[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0xFFF) + 1
                if distance > len(output) or len(output) + length > size:
                    raise ValueError(f"invalid LZ77 at {_address(offset)}")
                for _ in range(length):
                    output.append(output[-distance])
            else:
                output.append(rom[cursor])
                cursor += 1
    return bytes(output)


def _literal_value(rom: bytes, offset: int) -> tuple[int, int] | None:
    instruction = struct.unpack_from("<H", rom, offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    address = ROM_BASE + offset
    literal = ((address + 4) & ~3) + (instruction & 0xFF) * 4
    if not ROM_BASE <= literal < ROM_BASE + len(rom) - 3:
        return None
    return (instruction >> 8) & 7, struct.unpack_from(
        "<I", rom, literal - ROM_BASE
    )[0]


Value = tuple[int, bool, int | None]
UNKNOWN_VALUE: Value = (0, True, None)


def _sum_values(first: Value, second: Value) -> Value:
    if second[0] == 0 and not second[1]:
        origin = first[2]
    elif first[0] == 0 and first[1]:
        origin = second[2]
    else:
        origin = None
    return first[0] + second[0], first[1] or second[1], origin


def _scan_palette_calls(rom: bytes, graphics_user: int) -> list[dict[str, Any]]:
    registers: list[Value] = [UNKNOWN_VALUE for _ in range(16)]
    cursor = graphics_user - ROM_BASE
    limit = min(len(rom) - 3, cursor + 32)
    found = []
    while cursor < limit:
        halfword = struct.unpack_from("<H", rom, cursor)[0]
        pc = ROM_BASE + cursor
        literal = _literal_value(rom, cursor)
        if literal is not None:
            register, value = literal
            registers[register] = (value, False, pc)
            cursor += 2
            continue
        family = halfword & 0xF800
        if family == 0x2000:
            register = (halfword >> 8) & 7
            registers[register] = (halfword & 0xFF, False, pc)
            cursor += 2
            continue
        if family in (0x0000, 0x0800):
            shift = (halfword >> 6) & 31
            source_register = (halfword >> 3) & 7
            destination_register = halfword & 7
            value, dynamic, origin = registers[source_register]
            if family == 0:
                registers[destination_register] = (
                    value << shift,
                    dynamic,
                    origin,
                )
            else:
                registers[destination_register] = (
                    value >> (shift or 32),
                    dynamic,
                    origin,
                )
            cursor += 2
            continue
        if family == 0x1800:
            use_immediate = bool(halfword & 0x0400)
            subtract = bool(halfword & 0x0200)
            operand = (halfword >> 6) & 7
            source_register = (halfword >> 3) & 7
            destination_register = halfword & 7
            other = (
                (operand, False, pc)
                if use_immediate
                else registers[operand]
            )
            if subtract:
                other = (-other[0], other[1], other[2])
            registers[destination_register] = _sum_values(
                registers[source_register], other
            )
            cursor += 2
            continue
        if halfword & 0xFC00 == 0x4400:
            operation = (halfword >> 8) & 3
            destination_register = ((halfword >> 4) & 8) | (halfword & 7)
            source_register = (halfword >> 3) & 15
            if operation == 0:
                registers[destination_register] = _sum_values(
                    registers[destination_register],
                    registers[source_register],
                )
            elif operation == 2:
                registers[destination_register] = registers[source_register]
            else:
                registers[:4] = [UNKNOWN_VALUE] * 4
            cursor += 2
            continue
        if family == 0xF000:
            second = struct.unpack_from("<H", rom, cursor + 2)[0]
            target = _decode_bl(pc, halfword, second)
            source, source_unknown, source_load = registers[0]
            destination, destination_unknown, _ = registers[1]
            count, count_unknown, _ = registers[2]
            common = (
                not source_unknown
                and source_load is not None
                and ROM_BASE <= source < ROM_BASE + len(rom) - 3
                and not destination_unknown
                and 0x05000000 <= destination < 0x05000400
            )
            if (
                target == LZ77_VRAM
                and common
                and rom[source - ROM_BASE] == 0x10
                and int.from_bytes(
                    rom[source - ROM_BASE + 1 : source - ROM_BASE + 4],
                    "little",
                )
                == 32
            ):
                found.append(
                    {
                        "kind": "lz77_rom",
                        "graphics_user": f"0x{graphics_user:08X}",
                        "source_address": f"0x{source:08X}",
                        "source_load": f"0x{source_load:08X}",
                        "callsite": f"0x{pc:08X}",
                        "loader": "LZ77UnCompVram",
                        "size": 32,
                        "destination": f"0x{destination:08X}",
                        "code_size": cursor + 4 - (source_load - ROM_BASE),
                        "code_sha256": _sha(
                            rom[source_load - ROM_BASE : cursor + 4]
                        ),
                    }
                )
            elif (
                target in (CPU_SET, CPU_FAST_SET)
                and common
                and not count_unknown
                and count > 0
            ):
                found.append(
                    {
                        "kind": "raw_rom",
                        "graphics_user": f"0x{graphics_user:08X}",
                        "source_address": f"0x{source:08X}",
                        "source_load": f"0x{source_load:08X}",
                        "callsite": f"0x{pc:08X}",
                        "loader": (
                            "CpuSet" if target == CPU_SET else "CpuFastSet"
                        ),
                        "unit_count": count,
                        "size": count * (2 if target == CPU_SET else 4),
                        "destination": f"0x{destination:08X}",
                        "code_size": cursor + 4 - (source_load - ROM_BASE),
                        "code_sha256": _sha(
                            rom[source_load - ROM_BASE : cursor + 4]
                        ),
                    }
                )
            registers[:4] = [UNKNOWN_VALUE] * 4
            cursor += 4
            continue
        registers[:4] = [UNKNOWN_VALUE] * 4
        cursor += 2
    return found


def _synthetic_palette() -> bytes:
    output = bytearray()
    for index in range(16):
        component = round(index * 31 / 15)
        output.extend(
            struct.pack("<H", component | component << 5 | component << 10)
        )
    return bytes(output)


def _tile_atlas(graphics: bytes) -> tuple[bytes, int, int]:
    if not graphics or len(graphics) % 32:
        raise ValueError("graphics are not complete 4bpp tiles")
    tile_count = len(graphics) // 32
    columns = min(tile_count, 16)
    rows = (tile_count + 15) // 16
    width, height = columns * 8, rows * 8
    pixels = bytearray(width * height)
    for tile in range(tile_count):
        tile_x, tile_y = tile % 16, tile // 16
        for y in range(8):
            for x in range(8):
                packed = graphics[tile * 32 + y * 4 + x // 2]
                pixels[(tile_y * 8 + y) * width + tile_x * 8 + x] = (
                    packed >> (4 if x & 1 else 0)
                ) & 0xF
    return bytes(pixels), width, height


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png(pixels: bytes, palette_bytes: bytes, width: int, height: int) -> bytes:
    palette = bytearray()
    for offset in range(0, len(palette_bytes), 2):
        value = struct.unpack_from("<H", palette_bytes, offset)[0] & 0x7FFF
        for component in (
            value & 0x1F,
            (value >> 5) & 0x1F,
            (value >> 10) & 0x1F,
        ):
            palette.append((component << 3) | (component >> 2))
    rows = b"".join(
        b"\0" + pixels[y * width : (y + 1) * width]
        for y in range(height)
    )
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)),
            _chunk(b"PLTE", bytes(palette)),
            _chunk(b"IDAT", zlib.compress(rows, level=9)),
            _chunk(b"IEND", b""),
        )
    )


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors = []
    root = root.resolve()
    artifact = artifact.resolve()
    try:
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        catalog = json.loads(
            (artifact / CATALOG_NAME).read_text(encoding="utf-8")
        )
        raw_bundle = (artifact / RAW_PALETTE_BUNDLE_NAME).read_bytes()
        rom = (root / ROM_PATH).read_bytes()
        source_manifest_bytes = (root / SOURCE_ROOT / "manifest.json").read_bytes()
        source_payload_bytes = (
            root / SOURCE_ROOT / "rom-pointer-lz77-inventory.json"
        ).read_bytes()
        source = json.loads(source_payload_bytes)
    except Exception as error:
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "errors": [f"artifact input unreadable: {error}"],
        }

    actual = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    }
    expected_files = manifest.get("files", {})
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or not isinstance(expected_files, dict)
        or actual != set(expected_files) | {"manifest.json"}
        or any(path.is_symlink() for path in artifact.rglob("*"))
    ):
        errors.append("promotion manifest contract mismatch")
    for relative, expected in expected_files.items():
        try:
            if _sha((artifact / relative).read_bytes()) != expected:
                errors.append(f"manifest hash mismatch: {relative}")
        except OSError as error:
            errors.append(f"artifact file unreadable: {relative}: {error}")
    if errors:
        return {"schema": VERIFY_SCHEMA, "verified": False, "errors": errors}

    if _sha(rom) != ROM_SHA256:
        errors.append("ROM identity mismatch")
    if (
        _sha(source_manifest_bytes) != SOURCE_MANIFEST_SHA256
        or _sha(source_payload_bytes) != SOURCE_PAYLOAD_SHA256
    ):
        errors.append("source inventory identity mismatch")
    expected_implementation = {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_pointer_lz77_graphics.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_pointer_lz77_graphics.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_pointer_lz77_graphics.py").read_bytes()
        ),
    }
    if catalog.get("schema") != SCHEMA:
        errors.append("catalog schema mismatch")
    if catalog.get("implementation") != expected_implementation:
        errors.append("implementation identity mismatch")
    if catalog.get("scope") != SCOPE or manifest.get("scope") != SCOPE:
        errors.append("scope mismatch")
    if catalog.get("selection_rule") != SELECTION_RULE:
        errors.append("selection rule mismatch")
    if catalog.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }:
        errors.append("catalog ROM contract mismatch")
    if catalog.get("source_inventory") != {
        "path": SOURCE_ROOT.as_posix(),
        "manifest_sha256": SOURCE_MANIFEST_SHA256,
        "payload_sha256": SOURCE_PAYLOAD_SHA256,
    }:
        errors.append("source inventory contract mismatch")

    source_records = {
        item["file_offset"]: item for item in source["new_records"]
    }
    graphics_records = [
        item
        for item in source["new_records"]
        if item["classification"]["kind"] == "graphics"
    ]
    checkpoints = _tracked_checkpoints(root)
    if len(graphics_records) != 20:
        errors.append("source graphics denominator mismatch")
    partition = {}
    raw_call_groups: dict[int, dict[str, dict[str, Any]]] = {}
    for source_record in graphics_records:
        operations = []
        for user_text in source_record["literal_load_users"]:
            operations.extend(_scan_palette_calls(rom, int(user_text, 16)))
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
            errors.append(
                f"mixed palette routes: {source_record['gba_address']}"
            )
        kind = next(iter(kinds), "unresolved")
        palette_offsets = list(
            dict.fromkeys(
                int(item["source_address"], 16) - ROM_BASE
                for item in operations
            )
        )
        partition[source_record["file_offset"]] = (
            kind,
            palette_offsets,
            operations,
        )
        if kind != "raw_rom":
            continue
        for operation in operations:
            palette_offset = int(operation["source_address"], 16) - ROM_BASE
            calls = raw_call_groups.setdefault(palette_offset, {})
            callsite = operation["callsite"]
            evidence = {
                key: value
                for key, value in operation.items()
                if key not in {"kind", "source_address", "graphics_user"}
            }
            if callsite not in calls:
                evidence["graphics_users"] = [operation["graphics_user"]]
                calls[callsite] = evidence
            elif operation["graphics_user"] not in calls[callsite]["graphics_users"]:
                calls[callsite]["graphics_users"].append(
                    operation["graphics_user"]
                )

    for source_record in graphics_records:
        offset = source_record["file_offset"]
        if partition[offset][0] != "unresolved":
            continue
        runtime = _runtime_binding(
            root,
            rom,
            source_record,
            _decode_lz77(rom, offset),
            checkpoints,
        )
        if runtime is None:
            continue
        palette_offset, evidence = runtime
        partition[offset] = (
            "runtime_oam_raw_rom",
            [palette_offset],
            evidence,
        )

    partition_counts = {
        kind: sum(value[0] == kind for value in partition.values())
        for kind in (
            "raw_rom",
            "runtime_oam_raw_rom",
            "lz77_rom",
            "unresolved",
        )
    }
    if partition_counts != {
        "raw_rom": 12,
        "runtime_oam_raw_rom": 2,
        "lz77_rom": 4,
        "unresolved": 2,
    }:
        errors.append(f"discovered palette denominator mismatch: {partition_counts}")

    expected_raw_bundle = bytearray()
    expected_raw_sources = []
    raw_data: dict[int, bytes] = {}
    for offset, calls in sorted(raw_call_groups.items()):
        evidence = sorted(
            calls.values(), key=lambda item: int(item["callsite"], 16)
        )
        for item in evidence:
            item["graphics_users"].sort(key=lambda value: int(value, 16))
        size = max(item["size"] for item in evidence)
        data = rom[offset : offset + size]
        expected_raw_sources.append(
            {
                "gba_address": _address(offset),
                "file_offset": offset,
                "size": size,
                "sha256": _sha(data),
                "bundle_offset": len(expected_raw_bundle),
                "copy_evidence": evidence,
            }
        )
        expected_raw_bundle.extend(data)
        raw_data[offset] = data
    if raw_bundle != expected_raw_bundle:
        errors.append("raw palette bundle mismatch")
    if catalog.get("raw_palette_sources") != expected_raw_sources:
        errors.append("raw palette source semantics mismatch")

    synthetic = _synthetic_palette()
    expected_entries = []
    source_preview_count = 0
    index_preview_count = 0
    for source_record in graphics_records:
        offset = source_record["file_offset"]
        graphics = _decode_lz77(rom, offset)
        pixels, width, height = _tile_atlas(graphics)
        kind, palette_offsets, operation_evidence = partition[offset]
        if kind == "raw_rom":
            variants = [
                (palette_offset, bank, data[bank * 32 : bank * 32 + 32])
                for palette_offset in palette_offsets
                for data in [raw_data[palette_offset]]
                for bank in range(len(data) // 32)
            ]
        elif kind == "runtime_oam_raw_rom":
            variants = [
                (palette_offset, 0, rom[palette_offset : palette_offset + 32])
                for palette_offset in palette_offsets
            ]
        elif kind == "lz77_rom":
            variants = [
                (palette_offset, 0, _decode_lz77(rom, palette_offset))
                for palette_offset in palette_offsets
            ]
        else:
            kind = "unresolved"
            palette_offsets = []
            variants = [(None, 0, synthetic)]
        previews = []
        for palette_offset, bank, palette in variants:
            address_token = (
                "index-only"
                if palette_offset is None
                else f"{ROM_BASE + palette_offset:08x}-bank-{bank:02d}"
            )
            relative = f"previews/{ROM_BASE + offset:08x}-{address_token}.png"
            png = _png(pixels, palette, width, height)
            if (artifact / relative).read_bytes() != png:
                errors.append(f"preview bytes mismatch: {relative}")
            previews.append(
                {
                    "file": relative,
                    "palette_origin": (
                        "synthetic_index_only" if kind == "unresolved" else kind
                    ),
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
            index_preview_count += len(previews)
        else:
            source_preview_count += len(previews)
        expected_entries.append(
            {
                "graphics_address": source_record["gba_address"],
                "graphics_file_offset": offset,
                "decompressed_size": len(graphics),
                "decompressed_sha256": _sha(graphics),
                "palette_binding": {
                    "kind": kind,
                    "source_addresses": [_address(value) for value in palette_offsets],
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
    if catalog.get("graphics") != expected_entries:
        errors.append("graphics catalog semantics mismatch")

    expected_summary = {
        "graphics_record_count": 20,
        "raw_palette_bound_count": 12,
        "runtime_oam_palette_bound_count": 2,
        "lz77_palette_bound_count": 4,
        "source_palette_bound_count": 18,
        "unresolved_palette_count": 2,
        "source_palette_preview_count": source_preview_count,
        "index_only_preview_count": index_preview_count,
        "preview_file_count": source_preview_count + index_preview_count,
        "raw_palette_source_count": len(expected_raw_sources),
        "raw_palette_bundle_size": len(expected_raw_bundle),
        "runtime_checkpoint_count": len(checkpoints),
    }
    if catalog.get("summary") != expected_summary:
        errors.append("summary mismatch")
    if catalog.get("synthetic_index_palette") != {
        "size": len(synthetic),
        "sha256": _sha(synthetic),
        "purpose": "diagnostic index visibility only; not a ROM palette",
    }:
        errors.append("synthetic palette contract mismatch")
    expected_producer = {
        "command": [
            "python3",
            "tools/export_rom_pointer_lz77_graphics.py",
            "--root",
            ".",
            "--output-dir",
            "artifacts/rom-pointer-lz77-graphics-v1",
        ],
        **expected_implementation,
    }
    if manifest.get("producer") != expected_producer:
        errors.append("producer evidence mismatch")
    expected_verifier = {
        "command": [
            "python3",
            "tools/verify_rom_pointer_lz77_graphics.py",
            "--root",
            ".",
            "--artifact-dir",
            "artifacts/rom-pointer-lz77-graphics-v1",
        ],
        "verifier_sha256": expected_implementation["verifier_sha256"],
        "exit_code": 0,
        "report": {
            "schema": VERIFY_SCHEMA,
            "verified": True,
            "errors": [],
            "graphics_record_count": 20,
            "preview_file_count": source_preview_count + index_preview_count,
        },
    }
    if manifest.get("verifier") != expected_verifier:
        errors.append("verifier evidence mismatch")

    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "graphics_record_count": len(expected_entries),
        "preview_file_count": source_preview_count + index_preview_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-pointer-lz77-graphics-v1"),
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
