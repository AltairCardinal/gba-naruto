#!/usr/bin/env python3
"""Independently verify the natural map-41 visual-resource A/B matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from tools.inspect_mgba_savestate import (
        load_gba_state,
        png_screen_fingerprint,
    )
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.inspect_mgba_savestate import (
        load_gba_state,
        png_screen_fingerprint,
    )


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
EMULATOR_SHA256 = "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
EMULATOR_MANIFEST_SHA256 = "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d"
REPLAY_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
PATCH_SHA256 = "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6"
SCHEMA = "map41-visual-resource-matrix-evidence-v1"
BUILD_SCHEMA = "map41-visual-resource-matrix-build-v1"
ARTIFACT_ID = "map41-visual-resource-matrix-v1"
VARIANTS = ("baseline", "tile_graphics", "bg_palette", "metatile_definitions")
CANDIDATES = VARIANTS[1:]
EVENT = {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
VARIANT_ROM_SHA256 = {
    "baseline": "831e99f4a4f3672be81b4842ea12fb0aa5b9166e4684f9f73d299d52d90fbe05",
    "tile_graphics": "b175298fd3e585f6e89e3b2c68db66ef879b993b9b0b603e0186606fd3c49c7d",
    "bg_palette": "ea2d1e17e98f89e7b0db8658386d18474b480ccffde9b79fe96c9b8d6cbf76f1",
    "metatile_definitions": "19fa69f0ee2640c6988780e40d2cea98d075ced4b33b6ec4d4b5080c47a3d985",
}
RESOURCE_ORDER = ("bg_palette", "tile_graphics", "metatile_definitions")
RESOURCES: dict[str, dict[str, Any]] = {
    "tile_graphics": {
        "source_sha256": "f7d4ac8b041bfcd7d5f1a2103e3402185fd57a35651a0f1d75e47e48d47a44c2",
        "source_pointer": 0x0811B4E0,
        "source_size": 12288,
        "physical_offsets": [
            0x115760, 0x118620, 0x11B4E0, 0x11E3A0,
            0x121260, 0x124120, 0x126FE0,
        ],
        "header_offsets": [
            0x53DDF4, 0x53DE14, 0x53DE34, 0x53DE54,
            0x53DE74, 0x53DE94, 0x53DEB4,
        ],
        "target_header": 0x53DE34,
        "edit_offset": 0x2A20,
        "before": 0x34,
        "after": 0x35,
        "allocation_offset": 0x9800A4,
        "new_pointer": 0x089800A4,
    },
    "bg_palette": {
        "source_sha256": "3c86d041724735cc717fedffe8cca91ac9d717b7878c2296672e295eb12923e4",
        "source_pointer": 0x0811DC1C,
        "source_size": 384,
        "physical_offsets": [
            0x0C166C, 0x0C416C, 0x0C5F24, 0x0C8454,
            0x0EA0F4, 0x0EF448, 0x0F584C, 0x117E9C,
            0x11AD5C, 0x11DC1C, 0x120ADC, 0x12399C,
            0x12685C, 0x12971C,
        ],
        "header_offsets": [
            0x53D938, 0x53D958, 0x53D978, 0x53D998, 0x53DAD8,
            0x53DB18, 0x53DB58, 0x53DD38, 0x53DDF8, 0x53DE18,
            0x53DE38, 0x53DE58, 0x53DE78, 0x53DE98, 0x53DEB8,
        ],
        "target_header": 0x53DE38,
        "edit_offset": 0x4A,
        "before": 0x0D,
        "after": 0x0C,
        "allocation_offset": 0x980000,
        "new_pointer": 0x08980000,
    },
    "metatile_definitions": {
        "source_sha256": "f557bf169836e7b1abdf2e6fac94887f0f50b9293a9976eb8e7c93d64e3bb3db",
        "source_pointer": 0x0811DEB4,
        "source_size": 1376,
        "physical_offsets": [
            0x118134, 0x11AFF4, 0x11DEB4, 0x120D74,
            0x123C34, 0x126AF4, 0x1299B4,
        ],
        "header_offsets": [
            0x53DE04, 0x53DE24, 0x53DE44, 0x53DE64,
            0x53DE84, 0x53DEA4, 0x53DEC4,
        ],
        "target_header": 0x53DE44,
        "edit_offset": 0x230,
        "before": 0x19,
        "after": 0x1A,
        "allocation_offset": 0x9827D8,
        "new_pointer": 0x089827D8,
    },
}
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "VRAM": (0x06000000, 0x18000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "OAM": (0x07000000, 0x400),
}
EXPECTED_DOMAIN_DIFFS = {
    "tile_graphics": {"VRAM": [0x6A20]},
    "bg_palette": {"PRAM": [0x4A]},
    "metatile_definitions": {"EWRAM": [0x1E05C], "VRAM": [0x418]},
}
EXPECTED_PIXELS = {
    "tile_graphics": (1, [160, 32, 160, 32]),
    "bg_palette": (119, [0, 104, 238, 116]),
    "metatile_definitions": (56, [72, 24, 79, 31]),
}
IMPLEMENTATION_PATHS = (
    "tools/build_map41_visual_resource_matrix.py",
    "tools/export_map41_visual_resource_matrix_evidence.py",
    "tools/verify_map41_visual_resource_matrix_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_map41_visual_resource_matrix.py",
    "tests/test_map41_visual_resource_matrix_evidence.py",
)
VARIANT_FILES = {
    "frame80.ss9", "frame80.png", "audit.json", "sentinel.json", "guard.json"
}
EXPECTED_FILES = {
    "build-manifest.json", "runtime-evidence.json",
    *{f"{variant}/{name}" for variant in VARIANTS for name in VARIANT_FILES},
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _decode_lz77(data: bytes, offset: int) -> bytes:
    if not 0 <= offset <= len(data) - 4 or data[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(data):
            raise ValueError("truncated LZ77 flags")
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(data):
                    raise ValueError("truncated LZ77 token")
                token = (data[cursor] << 8) | data[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                for _ in range(length):
                    if len(output) >= size:
                        break
                    output.append(output[-distance])
            else:
                if cursor >= len(data):
                    raise ValueError("truncated LZ77 literal")
                output.append(data[cursor])
                cursor += 1
    return bytes(output)


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        return [-1]
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def _rgb555(value: int) -> tuple[int, int, int]:
    return tuple(
        (((value >> shift) & 31) << 3) | (((value >> shift) & 31) >> 2)
        for shift in (0, 5, 10)
    )


def _render_bg0(state: Any) -> dict[tuple[int, int], tuple[int, int, int]]:
    io = state.read_memory(0x04000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    pram = state.read_memory(0x05000000, 0x400)
    bg0cnt = struct.unpack_from("<H", io, 8)[0]
    scroll_x = struct.unpack_from("<H", io, 0x10)[0] & 0x1FF
    scroll_y = struct.unpack_from("<H", io, 0x12)[0] & 0x1FF
    char_base = ((bg0cnt >> 2) & 3) * 0x4000
    screen_base = ((bg0cnt >> 8) & 31) * 0x800
    output = {}
    for y in range(160):
        world_y = (y + scroll_y) & 0xFF
        for x in range(240):
            world_x = (x + scroll_x) & 0xFF
            entry_offset = screen_base + (
                (world_y // 8) * 32 + world_x // 8
            ) * 2
            entry = struct.unpack_from("<H", vram, entry_offset)[0]
            pixel_x = world_x & 7
            pixel_y = world_y & 7
            if entry & 0x0400:
                pixel_x = 7 - pixel_x
            if entry & 0x0800:
                pixel_y = 7 - pixel_y
            byte = vram[
                char_base + (entry & 0x03FF) * 32
                + pixel_y * 4 + pixel_x // 2
            ]
            index = (byte >> (4 * (pixel_x & 1))) & 15
            bank = (entry >> 12) & 15
            value = struct.unpack_from("<H", pram, (bank * 16 + index) * 2)[0]
            output[(x, y)] = _rgb555(value)
    return output


def _image(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise ValueError("mGBA screenshot is not 240x160")
    return image


def _expected_resource_metadata(resource_type: str) -> dict[str, Any]:
    resource = RESOURCES[resource_type]
    return {
        "source_sha256": resource["source_sha256"],
        "source_pointer": f"0x{resource['source_pointer']:08X}",
        "source_size": resource["source_size"],
        "physical_offsets": resource["physical_offsets"],
        "all_header_pointer_offsets": resource["header_offsets"],
        "target_header_pointer_offset": resource["target_header"],
        "preserved_header_pointer_offsets": [
            offset for offset in resource["header_offsets"]
            if offset != resource["target_header"]
        ],
    }


def _verify_alias_denominator(base: bytes) -> list[str]:
    errors: list[str] = []
    for resource_type, resource in RESOURCES.items():
        decoded = []
        for offset in resource["physical_offsets"]:
            try:
                value = _decode_lz77(base, offset)
            except ValueError as error:
                errors.append(f"alias denominator {resource_type}: {error}")
                continue
            decoded.append(value)
            if (
                len(value) != resource["source_size"]
                or _sha256_bytes(value) != resource["source_sha256"]
            ):
                errors.append(f"alias denominator {resource_type} content mismatch")
        physical = set(resource["physical_offsets"])
        expected_by_physical = {offset: set() for offset in physical}
        for header in resource["header_offsets"]:
            pointer = struct.unpack_from("<I", base, header)[0]
            offset = pointer - ROM_BASE
            if offset not in physical:
                errors.append(f"alias denominator {resource_type} header target mismatch")
            else:
                expected_by_physical[offset].add(header)
        actual_by_physical = {offset: set() for offset in physical}
        pointer_to_offset = {ROM_BASE + offset: offset for offset in physical}
        for pointer_offset in range(0, len(base) - 3, 4):
            pointer = struct.unpack_from("<I", base, pointer_offset)[0]
            if pointer in pointer_to_offset:
                actual_by_physical[pointer_to_offset[pointer]].add(pointer_offset)
        if actual_by_physical != expected_by_physical:
            errors.append(f"alias denominator {resource_type} pointer users mismatch")
        target_pointer = struct.unpack_from("<I", base, resource["target_header"])[0]
        if target_pointer != resource["source_pointer"]:
            errors.append(f"alias denominator {resource_type} target source mismatch")
    return errors


def _reconstruct_variant(
    base: bytes,
    variant: str,
    metadata: dict[str, Any],
) -> tuple[bytes, dict[str, bytes], list[tuple[Any, ...]]]:
    ledger = metadata.get("patch_ledger")
    if not isinstance(ledger, list) or len(ledger) != 6:
        raise ValueError("patch topology ledger denominator mismatch")
    output = bytearray(base + b"\xFF" * (0x1000000 - len(base)))
    decoded: dict[str, bytes] = {}
    topology = []
    for index, entry in enumerate(ledger):
        if not isinstance(entry, dict):
            raise ValueError("patch topology entry is not an object")
        resource_type = RESOURCE_ORDER[index // 2]
        resource = RESOURCES[resource_type]
        expected_kind = "allocation" if index % 2 == 0 else "pointer_redirect"
        expected_offset = (
            resource["allocation_offset"]
            if expected_kind == "allocation"
            else resource["target_header"]
        )
        if (
            entry.get("kind") != expected_kind
            or entry.get("offset") != expected_offset
            or entry.get("resource_type") != resource_type
            or entry.get("new_pointer") != f"0x{resource['new_pointer']:08X}"
            or entry.get("all_header_pointer_offsets") != resource["header_offsets"]
            or entry.get("target_header_pointer_offsets") != [resource["target_header"]]
            or entry.get("source_sha256") != resource["source_sha256"]
            or entry.get("source_size") != resource["source_size"]
        ):
            raise ValueError(f"patch topology {variant} {resource_type} mismatch")
        try:
            before = bytes.fromhex(entry["before_hex"])
            after = bytes.fromhex(entry["after_hex"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("patch topology contains invalid hex") from error
        if expected_kind == "pointer_redirect":
            if len(before) != 4 or after != struct.pack("<I", resource["new_pointer"]):
                raise ValueError("patch topology pointer bytes mismatch")
        if output[expected_offset : expected_offset + len(before)] != before:
            raise ValueError("patch topology before bytes mismatch")
        output[expected_offset : expected_offset + len(after)] = after
        topology.append(
            (
                expected_kind,
                expected_offset,
                resource_type,
                tuple(entry["target_header_pointer_offsets"]),
                entry["new_pointer"],
                len(after),
            )
        )
        if expected_kind == "allocation":
            value = _decode_lz77(bytes(output), expected_offset)
            source = _decode_lz77(base, resource["source_pointer"] - ROM_BASE)
            expected = bytearray(source)
            if variant == resource_type:
                expected[resource["edit_offset"]] = resource["after"]
            if value != bytes(expected):
                raise ValueError(f"patch topology {variant} decoded content mismatch")
            if (
                entry.get("replacement_sha256") != _sha256_bytes(value)
                or entry.get("replacement_size") != len(value)
            ):
                raise ValueError("patch topology replacement provenance mismatch")
            decoded[resource_type] = value
    result = bytes(output)
    if (
        len(result) != 0x1000000
        or _sha256_bytes(result) != VARIANT_ROM_SHA256[variant]
        or metadata.get("rom_sha256") != VARIANT_ROM_SHA256[variant]
        or metadata.get("rom_size") != 0x1000000
    ):
        raise ValueError(f"patch topology {variant} reconstructed ROM mismatch")
    for resource_type, resource in RESOURCES.items():
        if struct.unpack_from("<I", result, resource["target_header"])[0] != resource["new_pointer"]:
            raise ValueError("patch topology target pointer mismatch")
        for offset in resource["header_offsets"]:
            if offset != resource["target_header"] and result[offset : offset + 4] != base[offset : offset + 4]:
                raise ValueError("patch topology changed a preserved alias")
    return result, decoded, topology


def _audit_errors(
    artifact: Path,
    variant: str,
    expected_rom_sha256: str,
) -> list[str]:
    errors: list[str] = []
    audit = _read_json(artifact / variant / "audit.json")
    sentinel = _read_json(artifact / variant / "sentinel.json")
    guard = _read_json(artifact / variant / "guard.json")
    if audit != sentinel:
        errors.append(f"{variant} audit and sentinel differ")
    expected = {
        "inputs": [EVENT],
        "automatic_inputs": [],
        "recovery_inputs": [],
        "evidence_mode": "single-input",
        "zero_input_verified": False,
        "frame": 80,
        "capture_frame": 80,
        "success": True,
        "status": "capture-complete",
        "rom_sha256": expected_rom_sha256,
        "staged_rom_sha256": expected_rom_sha256,
        "input_state_sha256": INPUT_STATE_SHA256,
        "binary_sha256": EMULATOR_SHA256,
        "build_manifest_sha256": EMULATOR_MANIFEST_SHA256,
        "replay_script_sha256": REPLAY_SHA256,
        "patch_sha256": PATCH_SHA256,
        "pgid_clean": True,
    }
    for key, value in expected.items():
        if audit.get(key) != value:
            errors.append(f"{variant} audit {key} mismatch")
    if audit.get("output_state_sha256") != _sha256(artifact / variant / "frame80.ss9"):
        errors.append(f"{variant} audit state hash mismatch")
    if audit.get("output_png_sha256") != _sha256(artifact / variant / "frame80.png"):
        errors.append(f"{variant} audit PNG hash mismatch")
    if audit.get("guard_summary_sha256") != _sha256(artifact / variant / "guard.json"):
        errors.append(f"{variant} audit guard hash mismatch")
    residue = audit.get("runtime_residue")
    if (
        not isinstance(residue, dict)
        or residue.get("pgid_clean") is not True
        or residue.get("mgba_listener_clean") is not True
        or residue.get("pgid_matching_rows") != []
        or residue.get("mgba_listener_rows") != []
    ):
        errors.append(f"{variant} audit runtime residue mismatch")
    expected_guard = {
        "reason": "completed",
        "exit_code": 0,
        "protection_backend": "posix-process-group",
        "degraded": False,
        "completion_trigger": "success-marker",
    }
    for key, value in expected_guard.items():
        if guard.get(key) != value:
            errors.append(f"{variant} guard {key} mismatch")
    if (
        isinstance(guard.get("peak_tree_rss_mib"), bool)
        or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        or not 0 < guard["peak_tree_rss_mib"] <= 1536
    ):
        errors.append(f"{variant} guard RSS mismatch")
    return errors


def verify(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    summary: dict[str, Any] = {"candidates": {}}
    try:
        manifest = _read_json(artifact / "manifest.json")
        build = _read_json(artifact / "build-manifest.json")
        evidence = _read_json(artifact / "runtime-evidence.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {"verified": False, "errors": [str(error)], "summary": summary}

    actual_files = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_files != EXPECTED_FILES:
        errors.append("artifact file denominator mismatch")
    if manifest.get("files") != {
        relative: _sha256(artifact / relative) for relative in sorted(actual_files)
    }:
        errors.append("artifact file hashes mismatch")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_id") != ARTIFACT_ID
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("payload_file") != "runtime-evidence.json"
        or manifest.get("payload_sha256") != _sha256(artifact / "runtime-evidence.json")
    ):
        errors.append("artifact manifest contract mismatch")
    expected_implementation = {
        path: _sha256(root / path) for path in IMPLEMENTATION_PATHS
    }
    if manifest.get("implementation_sha256") != expected_implementation:
        errors.append("artifact implementation hashes mismatch")
    if manifest.get("parent") != {
        "path": INPUT_STATE.as_posix(),
        "sha256": INPUT_STATE_SHA256,
        "loader_state": "pre-map-load-zero-runtime",
    }:
        errors.append("artifact parent contract mismatch")
    expected_scope = {
        "natural_entry": True,
        "map41_tile_graphics_pixel_ab": True,
        "map41_bg_palette_pixel_ab": True,
        "map41_metatile_definitions_pixel_ab": True,
        "shared_patch_topology": True,
        "preserved_aliases": True,
        "all_maps_all_resources": False,
        "collision_gameplay": False,
        "physical_gba_verified": False,
    }
    if manifest.get("scope") != expected_scope:
        errors.append("artifact scope mismatch")

    if _sha256(root / "rom/base.gba") != ROM_SHA256:
        errors.append("base ROM identity mismatch")
        base = b""
    else:
        base = (root / "rom/base.gba").read_bytes()
        errors.extend(_verify_alias_denominator(base))
    if _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
        errors.append("input checkpoint identity mismatch")

    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("base_rom_sha256") != ROM_SHA256
        or build.get("map_id") != 41
        or set(build.get("variants", {})) != set(VARIANTS)
        or build.get("isolation")
        != {
            "shared_patch_topology": True,
            "only_map41_headers_redirected": True,
            "independent_runtime_required": True,
        }
    ):
        errors.append("build contract mismatch")
    expected_resources = {
        resource_type: _expected_resource_metadata(resource_type)
        for resource_type in ("tile_graphics", "bg_palette", "metatile_definitions")
    }
    if build.get("resources") != expected_resources:
        errors.append("alias denominator build metadata mismatch")
    expected_edits = {
        resource_type: {
            "source_pointer": f"0x{resource['source_pointer']:08X}",
            "target_header_pointer_offset": f"0x{resource['target_header']:08X}",
            "decoded_byte_offsets": [resource["edit_offset"]],
            "before_hex": bytes([resource["before"]]).hex(),
            "after_hex": bytes([resource["after"]]).hex(),
        }
        for resource_type, resource in RESOURCES.items()
    }
    if build.get("edits") != expected_edits:
        errors.append("build edit contract mismatch")

    reconstructed: dict[str, bytes] = {}
    decoded: dict[str, dict[str, bytes]] = {}
    topologies = []
    if base:
        for variant in VARIANTS:
            try:
                rom, resources, topology = _reconstruct_variant(
                    base, variant, build.get("variants", {}).get(variant, {})
                )
                reconstructed[variant] = rom
                decoded[variant] = resources
                topologies.append(topology)
            except (KeyError, TypeError, ValueError) as error:
                errors.append(str(error))
        if topologies and any(topology != topologies[0] for topology in topologies[1:]):
            errors.append("patch topology is not shared across variants")

    audits = []
    for variant in VARIANTS:
        try:
            errors.extend(_audit_errors(artifact, variant, VARIANT_ROM_SHA256[variant]))
            audits.append(_read_json(artifact / variant / "audit.json"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{variant} audit read failed: {error}")
    if len({audit.get("run_id") for audit in audits}) != len(VARIANTS):
        errors.append("audit run IDs are not independent")
    if len({audit.get("child_pgid") for audit in audits}) != len(VARIANTS):
        errors.append("audit child process groups are not independent")

    try:
        initial = load_gba_state(root / INPUT_STATE)
        if (
            initial.read_memory(0x02026804, 8) != bytes(8)
            or initial.read_memory(0x0201BE28, 4) != bytes(4)
            or initial.read_memory(0x0201DE2C, 1376) != bytes(1376)
        ):
            errors.append("parent pre-loader zero runtime mismatch")
        states = {
            variant: load_gba_state(artifact / variant / "frame80.ss9")
            for variant in VARIANTS
        }
        images = {
            variant: _image(artifact / variant / "frame80.png")
            for variant in VARIANTS
        }
    except (OSError, ValueError) as error:
        errors.append(f"runtime state load failed: {error}")
        states = {}
        images = {}

    if states:
        displays = []
        for variant in VARIANTS:
            state = states[variant]
            if (
                state.read_memory(0x02026805, 1) != bytes([41])
                or state.read_memory(0x0201BE28, 4) != bytes([36, 44, 9, 22])
            ):
                errors.append(f"{variant} natural map41 arrival mismatch")
            display = (
                struct.unpack("<H", state.read_memory(0x04000000, 2))[0],
                struct.unpack("<H", state.read_memory(0x04000008, 2))[0],
                struct.unpack("<H", state.read_memory(0x04000010, 2))[0],
                struct.unpack("<H", state.read_memory(0x04000012, 2))[0],
            )
            displays.append(display)
            if display != (0x1940, 0x0007, 24, 104):
                errors.append(f"{variant} display contract mismatch")
            try:
                if png_screen_fingerprint(artifact / variant / "frame80.ss9") != png_screen_fingerprint(artifact / variant / "frame80.png"):
                    errors.append(f"{variant} embedded screenshot binding mismatch")
            except ValueError as error:
                errors.append(f"{variant} embedded screenshot invalid: {error}")
        if any(display != displays[0] for display in displays[1:]):
            errors.append("candidate display states differ")

        complete_reconstruction = (
            set(decoded) == set(VARIANTS)
            and set(reconstructed) == set(VARIANTS)
            and all(set(decoded[variant]) == set(RESOURCES) for variant in VARIANTS)
        )
        if complete_reconstruction:
            checks = (
                ("tile_graphics", 0x06006A20, 0x2A20),
                ("bg_palette", 0x0500004A, 0x4A),
                ("metatile_definitions", 0x0201E05C, 0x230),
            )
            for resource_type, runtime_address, decoded_offset in checks:
                for variant in VARIANTS:
                    expected = decoded[variant][resource_type][decoded_offset]
                    if states[variant].read_memory(runtime_address, 1) != bytes([expected]):
                        errors.append(f"{variant} runtime resource {resource_type} byte mismatch")
            for variant in VARIANTS:
                if states[variant].read_memory(0x0201DE2C, 1376) != decoded[variant]["metatile_definitions"]:
                    errors.append(f"{variant} runtime resource metatile payload mismatch")
                palette = states[variant].read_memory(0x05000000, 384)
                if palette[:2] != bytes(2) or palette[2:] != decoded[variant]["bg_palette"][2:]:
                    errors.append(f"{variant} runtime resource palette payload mismatch")
            if states["baseline"].read_memory(0x06000418, 2) != bytes.fromhex("1931"):
                errors.append("baseline runtime resource metatile VRAM entry mismatch")
            if states["metatile_definitions"].read_memory(0x06000418, 2) != bytes.fromhex("1a31"):
                errors.append("metatile_definitions runtime resource VRAM entry mismatch")

            overwrite_signatures = []
            for variant in VARIANTS:
                graphics = decoded[variant]["tile_graphics"]
                runtime_graphics = states[variant].read_memory(0x06004000, len(graphics))
                overwritten = _changed_offsets(graphics, runtime_graphics)
                overwrite_signatures.append(
                    [
                        (offset, graphics[offset], runtime_graphics[offset])
                        for offset in overwritten
                    ]
                )
            if (
                len(overwrite_signatures[0]) != 1080
                or any(
                    signature != overwrite_signatures[0]
                    for signature in overwrite_signatures[1:]
                )
            ):
                errors.append("runtime resource tile common overwrite mask mismatch")

            for variant in VARIANTS:
                pointer = struct.unpack_from("<I", reconstructed[variant], 0x53DE3C)[0]
                layout = _decode_lz77(reconstructed[variant], pointer - ROM_BASE)
                if (
                    len(layout) != 792
                    or states[variant].read_memory(0x0201BE2C, len(layout)) != layout
                ):
                    errors.append(f"{variant} runtime resource primary layout mismatch")

        baseline_bg = _render_bg0(states["baseline"])
        for candidate in CANDIDATES:
            domain_diffs = {}
            for label, (address, size) in DOMAINS.items():
                difference = _changed_offsets(
                    states["baseline"].read_memory(address, size),
                    states[candidate].read_memory(address, size),
                )
                if difference:
                    domain_diffs[label] = difference
            if domain_diffs != EXPECTED_DOMAIN_DIFFS[candidate]:
                errors.append(f"{candidate} runtime resource domain isolation mismatch")
            candidate_bg = _render_bg0(states[candidate])
            expected_pixels = [
                [x, y]
                for y in range(160)
                for x in range(240)
                if baseline_bg[(x, y)] != candidate_bg[(x, y)]
                and images["baseline"].getpixel((x, y)) == baseline_bg[(x, y)]
            ]
            actual_pixels = [
                [x, y]
                for y in range(160)
                for x in range(240)
                if images["baseline"].getpixel((x, y))
                != images[candidate].getpixel((x, y))
            ]
            if expected_pixels != actual_pixels:
                errors.append(f"{candidate} BG0 final pixel oracle mismatch")
            if any(
                images[candidate].getpixel(tuple(row)) != candidate_bg[tuple(row)]
                for row in actual_pixels
            ):
                errors.append(f"{candidate} final pixels do not equal candidate BG0")
            bbox = [
                min(row[0] for row in actual_pixels),
                min(row[1] for row in actual_pixels),
                max(row[0] for row in actual_pixels),
                max(row[1] for row in actual_pixels),
            ] if actual_pixels else []
            if (len(actual_pixels), bbox) != EXPECTED_PIXELS[candidate]:
                errors.append(f"{candidate} final pixel denominator mismatch")
            pixel_changes = [
                [
                    x,
                    y,
                    list(images["baseline"].getpixel((x, y))),
                    list(images[candidate].getpixel((x, y))),
                ]
                for x, y in actual_pixels
            ]
            summary["candidates"][candidate] = {
                "memory_differences": domain_diffs,
                "pixel_count": len(actual_pixels),
                "screen_bbox": bbox,
            }
            recorded = evidence.get("runtime", {}).get("candidates", {}).get(candidate, {})
            if (
                recorded.get("memory_differences") != domain_diffs
                or recorded.get("pixel_count") != len(actual_pixels)
                or recorded.get("screen_bbox") != bbox
                or recorded.get("differing_pixels") != actual_pixels
                or recorded.get("pixel_changes") != pixel_changes
            ):
                errors.append(f"{candidate} evidence memory result mismatch")

        expected_display = {
            "dispcnt": 0x1940, "bg0cnt": 0x0007,
            "bg0hofs": 24, "bg0vofs": 104,
        }
        if (
            evidence.get("schema") != SCHEMA
            or evidence.get("input")
            != {
                "path": INPUT_STATE.as_posix(),
                "sha256": INPUT_STATE_SHA256,
                "loader_state": "pre-map-load-zero-runtime",
                "event": EVENT,
            }
            or evidence.get("runtime", {}).get("battle_id") != 41
            or evidence.get("runtime", {}).get("map_dimensions_hex") != "242c0916"
            or evidence.get("runtime", {}).get("display") != expected_display
        ):
            errors.append("runtime evidence contract mismatch")
        for variant in VARIANTS:
            guard = _read_json(artifact / variant / "guard.json")
            recorded_guard = evidence.get("resource_guard", {}).get(variant)
            expected_guard = {
                "peak_tree_rss_mib": guard.get("peak_tree_rss_mib"),
                "reason": "completed", "exit_code": 0, "degraded": False,
            }
            if recorded_guard != expected_guard:
                errors.append(f"{variant} evidence guard mismatch")

    return {"verified": not errors, "errors": errors, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.root, args.artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
