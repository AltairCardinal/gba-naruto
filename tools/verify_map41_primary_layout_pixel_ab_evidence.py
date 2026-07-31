#!/usr/bin/env python3
"""Independently verify the natural map-41 primary-layout pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
BASELINE_ROM_SHA256 = "938d99d2a83729b3c582ebc6be7e710f86f605195581e48695eb56779f277a64"
CANDIDATE_ROM_SHA256 = "9c164ea8aaaae99c13490743fd7673c57401adcb199c9799505fb30e10bc61a6"
BASELINE_DECODED_SHA256 = "950f9555a8b12c73b3c3fdabb50209917b849972ff1ee6c3e5b80ead5d472f6f"
CANDIDATE_DECODED_SHA256 = "cb79b40f285dfcb2bd33e4f5227cef4f347a0bbc48e451826e2f91b6dc798396"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
EMULATOR_SHA256 = "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
BUILD_MANIFEST_SHA256 = "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d"
REPLAY_SCRIPT_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
PATCH_SHA256 = "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6"
SCHEMA = "map41-primary-layout-pixel-ab-evidence-v1"
BUILD_SCHEMA = "map41-primary-layout-pixel-ab-build-v1"
ARTIFACT_ID = "map41-primary-layout-pixel-ab-v1"
RUNTIME_POINTER = 0x08980000
TARGET_HEADER_POINTER_OFFSET = 0x53DE3C
ALL_HEADER_POINTER_OFFSETS = [
    0x53DDFC,
    0x53DE1C,
    0x53DE3C,
    0x53DE5C,
    0x53DE7C,
    0x53DE9C,
    0x53DEBC,
]
PRESERVED_MAP_IDS = [39, 40, 42, 43, 44, 45]
RUNTIME_LAYOUT_BASE = 0x0201BE2C
RUNTIME_WORD = 0x0201BF08
BEFORE_WORD = 0x00350022
AFTER_WORD = 0x00220035
VRAM_ENTRY_ADDRESSES = [
    0x06000308,
    0x0600030A,
    0x0600030C,
    0x0600030E,
    0x06000348,
    0x0600034A,
    0x0600034C,
    0x0600034E,
]
IMPLEMENTATION_PATHS = (
    "tools/build_map41_primary_layout_pixel_ab.py",
    "tools/export_map41_primary_layout_pixel_ab_evidence.py",
    "tools/verify_map41_primary_layout_pixel_ab_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_map41_primary_layout_pixel_ab.py",
    "tests/test_map41_primary_layout_pixel_ab_evidence.py",
)
VARIANT_FILES = {
    "frame80.ss9",
    "frame80.png",
    "audit.json",
    "sentinel.json",
    "guard.json",
}
EXPECTED_FILES = {
    "build-manifest.json",
    "runtime-evidence.json",
    *{
        f"{variant}/{name}"
        for variant in ("baseline", "candidate")
        for name in VARIANT_FILES
    },
}
EXPECTED_INPUT = {
    "key": "A",
    "down_frame": 5,
    "up_frame": 13,
    "hold_frames": 8,
}


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
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
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
                output.append(data[cursor])
                cursor += 1
    return bytes(output)


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        return [-1]
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _reconstruct_rom(base: bytes, ledger: object) -> bytes:
    if not isinstance(ledger, list) or len(ledger) != 2:
        raise ValueError("patch ledger must contain allocation and pointer redirect")
    output = bytearray(base + b"\xFF" * (0x1000000 - len(base)))
    kinds = []
    for entry in ledger:
        if not isinstance(entry, dict):
            raise ValueError("patch ledger entry must be an object")
        kinds.append(entry.get("kind"))
        offset = entry.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError("patch ledger offset is invalid")
        before = bytes.fromhex(str(entry.get("before_hex")))
        after = bytes.fromhex(str(entry.get("after_hex")))
        if output[offset : offset + len(before)] != before:
            raise ValueError("patch ledger before bytes mismatch")
        output[offset : offset + len(after)] = after
    if kinds != ["allocation", "pointer_redirect"]:
        raise ValueError("patch ledger kinds mismatch")
    return bytes(output)


def _rgb555(value: int) -> tuple[int, int, int]:
    result = []
    for shift in (0, 5, 10):
        part = (value >> shift) & 31
        result.append((part << 3) | (part >> 2))
    return tuple(result)


def _tile_pixels(
    graphics: bytes,
    palette: bytes,
    entry: int,
) -> list[list[tuple[int, int, int]]]:
    tile = entry & 0x03FF
    raw = graphics[tile * 32 : tile * 32 + 32]
    if len(raw) != 32:
        raise ValueError("map tile index exceeds graphics")
    indices: list[int] = []
    for value in raw:
        indices.extend((value & 0x0F, value >> 4))
    rows = [indices[index : index + 8] for index in range(0, 64, 8)]
    if entry & 0x0800:
        rows.reverse()
    if entry & 0x0400:
        rows = [list(reversed(row)) for row in rows]
    bank = (entry >> 12) & 0x0F
    return [
        [
            _rgb555(struct.unpack_from("<H", palette, (bank * 16 + index) * 2)[0])
            for index in row
        ]
        for row in rows
    ]


def _render_cell(
    rom: bytes,
    word: int,
    *,
    scroll_x: int,
    scroll_y: int,
) -> dict[tuple[int, int], tuple[int, int, int]]:
    graphics = _decode_lz77(rom, 0x11B4E0)
    palette = _decode_lz77(rom, 0x11DC1C)
    metatiles = _decode_lz77(rom, 0x11DEB4)
    metatile_ids = (word & 0xFFFF, word >> 16)
    cell = [[(0, 0, 0) for _ in range(32)] for _ in range(16)]
    for metatile_x, metatile_id in enumerate(metatile_ids):
        entries = struct.unpack_from("<4H", metatiles, metatile_id * 8)
        for tile_y in range(2):
            for tile_x in range(2):
                pixels = _tile_pixels(
                    graphics,
                    palette,
                    entries[tile_y * 2 + tile_x],
                )
                for y in range(8):
                    for x in range(8):
                        cell[tile_y * 8 + y][metatile_x * 16 + tile_x * 8 + x] = (
                            pixels[y][x]
                        )
    screen_x = 1 * 32 - scroll_x
    screen_y = 6 * 16 - scroll_y
    return {
        (screen_x + x, screen_y + y): cell[y][x]
        for y in range(16)
        for x in range(32)
        if 0 <= screen_x + x < 240 and 0 <= screen_y + y < 160
    }


def _image(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise ValueError("mGBA screenshot is not 240x160")
    return image


def _audit_ok(
    artifact: Path,
    variant: str,
    expected_rom_sha256: str,
) -> tuple[bool, str]:
    audit = _read_json(artifact / variant / "audit.json")
    sentinel = _read_json(artifact / variant / "sentinel.json")
    guard = _read_json(artifact / variant / "guard.json")
    if audit != sentinel:
        return False, f"{variant} audit and sentinel differ"
    expected = {
        "inputs": [EXPECTED_INPUT],
        "automatic_inputs": [],
        "recovery_inputs": [],
        "capture_frame": 80,
        "frame": 80,
        "evidence_mode": "single-input",
        "zero_input_verified": False,
        "rom_sha256": expected_rom_sha256,
        "input_state_sha256": INPUT_STATE_SHA256,
        "binary_sha256": EMULATOR_SHA256,
        "build_manifest_sha256": BUILD_MANIFEST_SHA256,
        "replay_script_sha256": REPLAY_SCRIPT_SHA256,
        "patch_sha256": PATCH_SHA256,
        "staged_rom_sha256": expected_rom_sha256,
        "pgid_clean": True,
        "success": True,
        "status": "capture-complete",
    }
    for name, value in expected.items():
        if audit.get(name) != value:
            return False, f"{variant} audit {name} mismatch"
    if audit.get("output_state_sha256") != _sha256(
        artifact / variant / "frame80.ss9"
    ) or audit.get("output_png_sha256") != _sha256(
        artifact / variant / "frame80.png"
    ):
        return False, f"{variant} audit output hash mismatch"
    residue = audit.get("runtime_residue")
    if not isinstance(residue, dict) or not (
        residue.get("pgid_clean") is True
        and residue.get("mgba_listener_clean") is True
    ):
        return False, f"{variant} audit runtime residue mismatch"
    command = guard.get("command")
    if not (
        guard.get("reason") == "completed"
        and guard.get("exit_code") == 0
        and guard.get("degraded") is False
        and guard.get("protection_backend") == "posix-process-group"
        and guard.get("completion_trigger") == "success-marker"
        and isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        and guard["peak_tree_rss_mib"] <= 1536
        and isinstance(guard.get("child_pid"), int)
        and guard["child_pid"] > 0
        and isinstance(command, list)
        and len(command) >= 4
        and Path(command[-2]).name == "mgba_single_input_replay.lua"
        and Path(command[-1]).name == "staged.gba"
        and audit.get("guard_summary_sha256")
        == _sha256(artifact / variant / "guard.json")
        and audit.get("child_pgid") == guard.get("child_pid")
        and audit.get("peak_tree_rss_mib") == guard.get("peak_tree_rss_mib")
        and Path(str(audit.get("staged_rom"))).name == "staged.gba"
    ):
        return False, f"{variant} guard mismatch"
    return True, ""


def verify(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    summary: dict[str, Any] = {}
    try:
        manifest = _read_json(artifact / "manifest.json")
        evidence = _read_json(artifact / "runtime-evidence.json")
        build = _read_json(artifact / "build-manifest.json")
        if set(manifest) != {
            "schema",
            "artifact_schema",
            "artifact_id",
            "artifact_status",
            "parent",
            "scope",
            "implementation_sha256",
            "files",
            "payload_file",
            "payload_sha256",
            "verifier",
        }:
            errors.append("artifact promotion field denominator mismatch")
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_id") != ARTIFACT_ID
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("payload_file") != "runtime-evidence.json"
            or manifest.get("payload_sha256")
            != _sha256(artifact / "runtime-evidence.json")
        ):
            errors.append("artifact promotion manifest mismatch")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != EXPECTED_FILES:
            errors.append("artifact file denominator mismatch")
        else:
            for relative, expected_hash in files.items():
                path = artifact / relative
                if path.is_symlink() or not path.is_file() or _sha256(path) != expected_hash:
                    errors.append(f"artifact file hash mismatch: {relative}")
        implementation = manifest.get("implementation_sha256")
        if not isinstance(implementation, dict) or set(implementation) != set(
            IMPLEMENTATION_PATHS
        ):
            errors.append("implementation denominator mismatch")
        else:
            for relative in IMPLEMENTATION_PATHS:
                if implementation.get(relative) != _sha256(root / relative):
                    errors.append(f"implementation hash mismatch: {relative}")
        parent = manifest.get("parent")
        if parent != {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "loader_state": "pre-map-load",
        }:
            errors.append("artifact parent checkpoint mismatch")
        if manifest.get("scope") != {
            "natural_entry": True,
            "preloader_zero_to_runtime_resource_verified": True,
            "map41_alias_split_verified": True,
            "exact_ewram_vram_pixel_diff_verified": True,
            "exact_loader_pc_runtime_trace": False,
            "full_camera_timing": False,
            "physical_gba_verified": False,
        }:
            errors.append("artifact scope mismatch")
        if manifest.get("verifier") != {
            "command": [
                "python3",
                "tools/verify_map41_primary_layout_pixel_ab_evidence.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        }:
            errors.append("artifact verifier command mismatch")

        if (
            build.get("schema") != BUILD_SCHEMA
            or build.get("base_rom_sha256") != ROM_SHA256
        ):
            errors.append("build manifest schema mismatch")
        if set(build) != {
            "schema",
            "base_rom_sha256",
            "runtime_source_pointer",
            "edit",
            "alias_split",
            "roms",
            "patch_ledgers",
            "isolation",
        }:
            errors.append("build manifest field denominator mismatch")
        expected_edit = {
            "map_id": 41,
            "resource_type": "primary_layout",
            "resource_sha256": BASELINE_DECODED_SHA256,
            "map41_source_pointer": "0x0811DCC0",
            "target_header_pointer_offset": "0x0053DE3C",
            "coarse_x": 1,
            "coarse_y": 6,
            "decoded_byte_offset": 0xDC,
            "before_word": "0x00350022",
            "after_word": "0x00220035",
            "decoded_differing_byte_offsets": [0xDC, 0xDE],
            "expected_runtime_ewram_word_address": "0x0201BF08",
        }
        if build.get("edit") != expected_edit:
            errors.append("build edit contract mismatch")
        expected_alias = {
            "all_header_pointer_offsets": ALL_HEADER_POINTER_OFFSETS,
            "redirected_header_pointer_offsets": [TARGET_HEADER_POINTER_OFFSET],
            "preserved_header_pointer_offsets": [
                offset
                for offset in ALL_HEADER_POINTER_OFFSETS
                if offset != TARGET_HEADER_POINTER_OFFSET
            ],
            "preserved_map_ids": PRESERVED_MAP_IDS,
        }
        if build.get("alias_split") != expected_alias:
            errors.append("build alias split mismatch")
        if build.get("runtime_source_pointer") != "0x08980000":
            errors.append("build runtime pointer mismatch")
        if build.get("isolation") != {
            "same_runtime_source_pointer": True,
            "same_pointer_redirect": True,
            "only_map41_header_redirected": True,
            "decoded_source_diff_count": 2,
        }:
            errors.append("build isolation contract mismatch")

        base_path = root / "rom/base.gba"
        base = base_path.read_bytes()
        if len(base) != 0x600000 or _sha256(base_path) != ROM_SHA256:
            errors.append("base ROM identity mismatch")
        roms: dict[str, bytes] = {}
        decoded: dict[str, bytes] = {}
        expected_rom_hashes = {
            "baseline": BASELINE_ROM_SHA256,
            "candidate": CANDIDATE_ROM_SHA256,
        }
        expected_decoded_hashes = {
            "baseline": BASELINE_DECODED_SHA256,
            "candidate": CANDIDATE_DECODED_SHA256,
        }
        for variant in ("baseline", "candidate"):
            expected_rom_metadata = {
                "path": f"{variant}.gba",
                "sha256": expected_rom_hashes[variant],
                "size": 0x1000000,
                "decoded_sha256": expected_decoded_hashes[variant],
                "spec": f"{variant}-spec.json",
            }
            if build.get("roms", {}).get(variant) != expected_rom_metadata:
                errors.append(f"{variant} build ROM metadata mismatch")
            ledger = build.get("patch_ledgers", {}).get(variant)
            expected_common = {
                "resource_type": "primary_layout",
                "source_sha256": BASELINE_DECODED_SHA256,
                "replacement_sha256": expected_decoded_hashes[variant],
                "new_pointer": "0x08980000",
                "target_header_pointer_offsets": [TARGET_HEADER_POINTER_OFFSET],
            }
            ledger_ok = isinstance(ledger, list) and len(ledger) == 2
            if ledger_ok:
                expected_entries = (
                    {
                        "id": "map41-primary-layout-pixel-ab-allocation",
                        "kind": "allocation",
                        "offset": 0x980000,
                        **expected_common,
                    },
                    {
                        "id": "map41-primary-layout-pixel-ab-pointer-53de3c",
                        "kind": "pointer_redirect",
                        "offset": TARGET_HEADER_POINTER_OFFSET,
                        **expected_common,
                    },
                )
                for index, expected_entry in enumerate(expected_entries):
                    entry = ledger[index]
                    if not isinstance(entry, dict) or set(entry) != {
                        *expected_entry,
                        "before_hex",
                        "after_hex",
                    } or any(
                        entry.get(name) != value
                        for name, value in expected_entry.items()
                    ):
                        ledger_ok = False
                        break
                if ledger_ok and (
                    ledger[1].get("before_hex") != "c0dc1108"
                    or ledger[1].get("after_hex") != "00009808"
                ):
                    ledger_ok = False
            if not ledger_ok:
                errors.append(f"{variant} patch ledger provenance mismatch")
            rom = _reconstruct_rom(base, ledger)
            roms[variant] = rom
            if hashlib.sha256(rom).hexdigest() != expected_rom_hashes[variant]:
                errors.append(f"{variant} reconstructed ROM hash mismatch")
            if struct.unpack_from("<I", rom, TARGET_HEADER_POINTER_OFFSET)[0] != RUNTIME_POINTER:
                errors.append(f"{variant} map41 pointer redirect mismatch")
            for offset in expected_alias["preserved_header_pointer_offsets"]:
                if rom[offset : offset + 4] != base[offset : offset + 4]:
                    errors.append(f"{variant} preserved alias pointer changed")
            raw = _decode_lz77(rom, RUNTIME_POINTER - 0x08000000)
            decoded[variant] = raw
            if (
                len(raw) != 792
                or hashlib.sha256(raw).hexdigest() != expected_decoded_hashes[variant]
            ):
                errors.append(f"{variant} decoded resource mismatch")
        if _changed_offsets(decoded["baseline"], decoded["candidate"]) != [0xDC, 0xDE]:
            errors.append("decoded resource isolation mismatch")
        if struct.unpack_from("<I", decoded["baseline"], 0xDC)[0] != BEFORE_WORD or struct.unpack_from(
            "<I", decoded["candidate"], 0xDC
        )[0] != AFTER_WORD:
            errors.append("decoded resource edit word mismatch")

        input_path = root / INPUT_STATE
        if _sha256(input_path) != INPUT_STATE_SHA256:
            errors.append("input checkpoint hash mismatch")
        initial = load_gba_state(input_path)
        if (
            initial.read_memory(0x02026804, 8) != bytes(8)
            or initial.read_memory(0x0201BE28, 4) != bytes(4)
            or initial.read_memory(RUNTIME_WORD, 4) != bytes(4)
        ):
            errors.append("input checkpoint is not pre-map-load")

        states = {
            variant: load_gba_state(artifact / variant / "frame80.ss9")
            for variant in ("baseline", "candidate")
        }
        for variant, expected_word in (
            ("baseline", BEFORE_WORD),
            ("candidate", AFTER_WORD),
        ):
            ok, message = _audit_ok(
                artifact,
                variant,
                expected_rom_hashes[variant],
            )
            if not ok:
                errors.append(message)
            state = states[variant]
            if state.read_memory(0x02026805, 1) != bytes([41]) or state.read_memory(
                0x0201BE28, 4
            ) != bytes([36, 44, 9, 22]):
                errors.append(f"{variant} natural battle/map arrival mismatch")
            if state.read_memory(RUNTIME_LAYOUT_BASE, 792) != decoded[variant]:
                errors.append(f"{variant} runtime layout does not equal relocated resource")
            if struct.unpack("<I", state.read_memory(RUNTIME_WORD, 4))[0] != expected_word:
                errors.append(f"{variant} runtime layout word mismatch")

        domain_specs = {
            "IO": (0x04000000, 0x400, []),
            "PRAM": (0x05000000, 0x400, []),
            "OAM": (0x07000000, 0x400, []),
            "EWRAM": (
                0x02000000,
                0x40000,
                [RUNTIME_WORD - 0x02000000, RUNTIME_WORD - 0x02000000 + 2],
            ),
            "VRAM": (
                0x06000000,
                0x18000,
                [address - 0x06000000 for address in VRAM_ENTRY_ADDRESSES],
            ),
        }
        domain_diffs: dict[str, list[int]] = {}
        for name, (address, size, expected) in domain_specs.items():
            offsets = _changed_offsets(
                states["baseline"].read_memory(address, size),
                states["candidate"].read_memory(address, size),
            )
            domain_diffs[name] = offsets
            if offsets != expected:
                errors.append(f"full {name} difference mismatch")

        io = states["baseline"]
        display = {
            "dispcnt": struct.unpack("<H", io.read_memory(0x04000000, 2))[0],
            "bg0cnt": struct.unpack("<H", io.read_memory(0x04000008, 2))[0],
            "bg0hofs": struct.unpack("<H", io.read_memory(0x04000010, 2))[0],
            "bg0vofs": struct.unpack("<H", io.read_memory(0x04000012, 2))[0],
        }
        if display != {
            "dispcnt": 0x1940,
            "bg0cnt": 0x0007,
            "bg0hofs": 24,
            "bg0vofs": 104,
        }:
            errors.append("BG0 runtime register mismatch")
        expected_entries: dict[str, list[int]] = {}
        for variant in ("baseline", "candidate"):
            word = struct.unpack_from("<I", decoded[variant], 0xDC)[0]
            metatiles = _decode_lz77(roms[variant], 0x11DEB4)
            ids = (word & 0xFFFF, word >> 16)
            entries: list[int] = []
            for row in range(2):
                for metatile_id in ids:
                    entries.extend(
                        struct.unpack_from("<2H", metatiles, metatile_id * 8 + row * 4)
                    )
            expected_entries[variant] = entries
            actual_entries = [
                struct.unpack("<H", states[variant].read_memory(address, 2))[0]
                for address in VRAM_ENTRY_ADDRESSES
            ]
            if actual_entries != entries:
                errors.append(f"{variant} metatile-to-VRAM expansion mismatch")

        images = {
            variant: _image(artifact / variant / "frame80.png")
            for variant in ("baseline", "candidate")
        }
        for variant in ("baseline", "candidate"):
            embedded = png_screen_fingerprint(artifact / variant / "frame80.ss9")
            external = png_screen_fingerprint(artifact / variant / "frame80.png")
            if (
                embedded["width"] != 240
                or embedded["height"] != 160
                or external["width"] != 240
                or external["height"] != 160
                or embedded["rgb_pixels_sha256"]
                != external["rgb_pixels_sha256"]
            ):
                errors.append(
                    f"{variant} embedded screenshot does not match external PNG"
                )
        expected_pixels = {
            variant: _render_cell(
                roms[variant],
                struct.unpack_from("<I", decoded[variant], 0xDC)[0],
                scroll_x=display["bg0hofs"],
                scroll_y=display["bg0vofs"],
            )
            for variant in ("baseline", "candidate")
        }
        for variant in ("baseline", "candidate"):
            if any(
                images[variant].getpixel(coordinate) != rgb
                for coordinate, rgb in expected_pixels[variant].items()
            ):
                errors.append(f"{variant} visible edited cell pixels mismatch")
        differing_pixels = [
            [x, y]
            for y in range(160)
            for x in range(240)
            if images["baseline"].getpixel((x, y))
            != images["candidate"].getpixel((x, y))
        ]
        expected_differing_pixels = [
            [x, y]
            for x, y in sorted(expected_pixels["baseline"], key=lambda pair: (pair[1], pair[0]))
            if expected_pixels["baseline"][(x, y)]
            != expected_pixels["candidate"][(x, y)]
        ]
        if differing_pixels != expected_differing_pixels:
            errors.append("final screenshot difference does not match cell pixel oracle")
        bbox = [
            min(row[0] for row in differing_pixels),
            min(row[1] for row in differing_pixels),
            max(row[0] for row in differing_pixels),
            max(row[1] for row in differing_pixels),
        ]
        if len(differing_pixels) != 204 or bbox != [8, 0, 39, 7]:
            errors.append("final screenshot difference count or bbox mismatch")

        if set(evidence) != {
            "schema",
            "input",
            "edit",
            "runtime",
            "pixel_result",
            "resource_guard",
        }:
            errors.append("runtime evidence field denominator mismatch")
        if evidence.get("schema") != SCHEMA:
            errors.append("runtime evidence schema mismatch")
        if evidence.get("edit") != expected_edit:
            errors.append("runtime evidence edit mismatch")
        if evidence.get("input") != {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "pre_map_dimensions_hex": "00000000",
            "pre_runtime_word_hex": "00000000",
            "event": EXPECTED_INPUT,
        }:
            errors.append("runtime evidence input mismatch")
        if evidence.get("pixel_result") != {
            "differing_pixel_count": len(differing_pixels),
            "screen_bbox": bbox,
            "differing_pixels": differing_pixels,
        }:
            errors.append("runtime evidence pixel result mismatch")
        if evidence.get("runtime") != {
            "battle_id": 41,
            "map_dimensions_hex": "242c0916",
            "runtime_layout_base": "0x0201BE2C",
            "runtime_word_address": "0x0201BF08",
            "baseline_word": "0x00350022",
            "candidate_word": "0x00220035",
            "ewram_differing_addresses": ["0x0201BF08", "0x0201BF0A"],
            "vram_differing_addresses": [
                f"0x{address:08X}" for address in VRAM_ENTRY_ADDRESSES
            ],
            "display": display,
            "vram_entries": expected_entries,
        }:
            errors.append("runtime evidence memory result mismatch")
        resource_guard = evidence.get("resource_guard")
        if not isinstance(resource_guard, dict):
            errors.append("runtime evidence resource guard mismatch")
        else:
            for variant in ("baseline", "candidate"):
                guard = _read_json(artifact / variant / "guard.json")
                if resource_guard.get(variant) != {
                    "peak_tree_rss_mib": guard.get("peak_tree_rss_mib"),
                    "reason": "completed",
                    "degraded": False,
                }:
                    errors.append(f"{variant} runtime evidence resource guard mismatch")

        summary = {
            "runtime_layout_word": "0x0201BF08",
            "vram_differing_byte_count": len(domain_diffs["VRAM"]),
            "differing_pixel_count": len(differing_pixels),
            "screen_bbox": bbox,
            "natural_entry": True,
        }
    except Exception as error:  # report malformed/tampered artifacts as verification failures
        errors.append(f"verification exception: {error}")
    return {
        "schema": "map41-primary-layout-pixel-ab-verification-v1",
        "verified": not errors,
        "errors": errors,
        "summary": summary,
    }


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
