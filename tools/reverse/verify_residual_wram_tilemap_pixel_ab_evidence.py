#!/usr/bin/env python3
"""Independently verify the modified-ROM WRAM tilemap pixel A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.inspect_mgba_savestate import load_gba_state


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EMULATOR_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"
SCHEMA = "residual-wram-tilemap-pixel-ab-evidence-v1"
BUILD_SCHEMA = "residual-wram-tilemap-pixel-ab-build-v1"
SOURCE_POINTER = 0x084635D8
RUNTIME_POINTER = 0x08BC15AC
GRAPHICS_POINTER = 0x08463688
GRAPHICS_TILE_BASE = 700
PALETTE_POINTER = 0x084638F4
VRAM_ENTRY_ADDRESS = 0x06000A16
STATE_SHA256 = "dc5a1c1847600bd9719f6e6f4dbfa6237110426f0f942cb74568cdfefd6c0864"
BASELINE_ROM_SHA256 = "bcf83aba98abd840b422a57eecb1144f9c63fcdec9d6aab17a01729539bbe061"
CANDIDATE_ROM_SHA256 = "1e947c35fa0691e588389337e6aa900fa3f78306c0473dce0dbb457cc00eb1dd"
BASELINE_DECODED_SHA256 = "e4184823135e047462d356aa95f690e94b9104b5e8772d58093efba251d3c640"
CANDIDATE_DECODED_SHA256 = "945aec4bdd403d89b3ccbe6034cc34a6c68780e60783088177832c26978bdd30"
INPUTS = [
    {"key": "Down", "down_frame": 18, "up_frame": 20, "hold_frames": 2},
    {"key": "A", "down_frame": 60, "up_frame": 62, "hold_frames": 2},
    {"key": "A", "down_frame": 140, "up_frame": 142, "hold_frames": 2},
]
IMPLEMENTATION_PATHS = (
    "tools/build_residual_wram_tilemap_pixel_ab.py",
    "tools/export_residual_wram_tilemap_pixel_ab_evidence.py",
    "tools/verify_residual_wram_tilemap_pixel_ab_evidence.py",
    "tools/mgba_wram_tilemap_sequence_probe.lua",
    "tools/mgba_checkpoint_replay.lua",
    "tests/test_build_residual_wram_tilemap_pixel_ab.py",
    "tests/test_residual_wram_tilemap_pixel_ab_evidence.py",
)
VARIANT_FILES = {
    "sequence-audit.json",
    "sequence-guard.json",
    "load.ss9",
    "load-post.ss9",
    "staging.bin",
    "output-rows.bin",
    "post-vram-rows.bin",
    "queue-post.ss9",
    "replay-audit.json",
    "replay-guard.json",
    "frame1.ss9",
    "frame1.png",
}
EXPECTED_FILES = {
    "build-manifest.json",
    "runtime-evidence.json",
    *{f"{variant}/{name}" for variant in ("baseline", "candidate") for name in VARIANT_FILES},
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


def _expect(errors: list[str], actual: object, expected: object, message: str) -> None:
    if actual != expected:
        errors.append(message)


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


def _extract_vram_rows(state_path: Path) -> bytes:
    state = load_gba_state(state_path)
    return b"".join(
        state.read_memory(0x06000806 + row * 64, 24) for row in range(12)
    )


def _full_vram(state_path: Path) -> bytes:
    return load_gba_state(state_path).read_memory(0x06000000, 0x18000)


def _decode_tile(graphics: bytes, tile: int, vertical_flip: bool) -> list[int]:
    relative = tile - GRAPHICS_TILE_BASE
    if not 0 <= relative < len(graphics) // 32:
        raise ValueError("tile outside graphics resource")
    raw = graphics[relative * 32 : relative * 32 + 32]
    pixels: list[int] = []
    for value in raw:
        pixels.extend((value & 0x0F, value >> 4))
    rows = [pixels[index : index + 8] for index in range(0, 64, 8)]
    if vertical_flip:
        rows.reverse()
    return [pixel for row in rows for pixel in row]


def _pixel_oracle(rom: bytes) -> tuple[list[list[int]], list[dict[str, int]]]:
    graphics = _decode_lz77(rom, GRAPHICS_POINTER - 0x08000000)
    before = _decode_tile(graphics, 712, True)
    after = _decode_tile(graphics, 711, True)
    coordinates: list[list[int]] = []
    details: list[dict[str, int]] = []
    for index, pair in enumerate(zip(before, after)):
        if pair[0] != pair[1]:
            x, y = 88 + index % 8, 64 + index // 8
            coordinates.append([x, y])
            details.append(
                {
                    "x": x,
                    "y": y,
                    "before_palette_index": pair[0],
                    "after_palette_index": pair[1],
                }
            )
    return coordinates, details


def _rgb555(value: int) -> tuple[int, int, int]:
    components = (value & 31, (value >> 5) & 31, (value >> 10) & 31)
    return tuple((part << 3) | (part >> 2) for part in components)


def _image(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise ValueError("unexpected mGBA frame size")
    return image


def _guard_ok(guard: dict[str, Any], expected_rom: str, expected_script: str) -> bool:
    command = guard.get("command")
    return (
        guard.get("reason") == "completed"
        and guard.get("exit_code") == 0
        and guard.get("degraded") is False
        and guard.get("completion_trigger") == "success-marker"
        and isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        and guard["peak_tree_rss_mib"] <= 1536
        and isinstance(command, list)
        and len(command) >= 4
        and Path(command[-1]).name == expected_rom
        and Path(command[-2]).name == expected_script
    )


def _load_event(audit: dict[str, Any]) -> dict[str, Any]:
    matches = [
        event
        for event in audit.get("events", [])
        if event.get("target") == "choice_phase_b_second_load"
    ]
    return matches[0] if len(matches) == 1 else {}


def _load_post_event(audit: dict[str, Any]) -> dict[str, Any]:
    matches = [
        event
        for event in audit.get("events", [])
        if event.get("target") == "choice_phase_b_second_load_post"
        and event.get("frame") == 150
    ]
    return matches[0] if len(matches) == 1 else {}


def _reconstruct_rom(
    base: bytes,
    ledger: object,
    errors: list[str],
    variant: str,
) -> bytes:
    expected_routes = (
        ("083f2108", 0x083F2108, 0x08BC1400, 0xBC1400, 0x08BD60),
        ("084634b8", 0x084634B8, 0x08BC148C, 0xBC148C, 0x090BDC),
        ("0846356c", 0x0846356C, 0x08BC1540, 0xBC1540, 0x090DDC),
        ("084635d8", 0x084635D8, 0x08BC15AC, 0xBC15AC, 0x090DE8),
    )
    if not isinstance(ledger, list) or len(ledger) != 8:
        errors.append(f"{variant} patch ledger count mismatch")
        return b""
    expected_contracts: dict[str, tuple[str, int, int, int]] = {}
    for suffix, source, target, allocation_offset, pointer_offset in expected_routes:
        expected_contracts[f"residual-wram-derived-tilemap-{suffix}"] = (
            "allocation",
            source,
            target,
            allocation_offset,
        )
        expected_contracts[
            f"residual-wram-derived-tilemap-{suffix}.pointer-{pointer_offset:06x}"
        ] = ("pointer_redirect", source, target, pointer_offset)
    output = bytearray(base + b"\xFF" * (0x1000000 - len(base)))
    spans: list[tuple[int, int]] = []
    for patch in ledger:
        if not isinstance(patch, dict):
            errors.append(f"{variant} patch ledger contains a non-object")
            continue
        patch_id = patch.get("id")
        contract = expected_contracts.get(str(patch_id))
        if contract is None:
            errors.append(f"{variant} patch ledger has unknown id: {patch_id}")
            continue
        kind, source, target, expected_offset = contract
        _expect(errors, patch.get("kind"), kind, f"{variant} patch kind mismatch: {patch_id}")
        _expect(errors, patch.get("source_pointer"), f"0x{source:08X}", f"{variant} patch source mismatch: {patch_id}")
        _expect(errors, patch.get("new_pointer"), f"0x{target:08X}", f"{variant} patch target mismatch: {patch_id}")
        _expect(errors, patch.get("offset"), expected_offset, f"{variant} patch offset mismatch: {patch_id}")
        try:
            before = bytes.fromhex(str(patch.get("before_hex", "")))
            after = bytes.fromhex(str(patch.get("after_hex", "")))
        except ValueError:
            errors.append(f"{variant} patch hex is invalid: {patch_id}")
            continue
        if not before or len(before) != len(after):
            errors.append(f"{variant} patch length mismatch: {patch_id}")
            continue
        offset = patch.get("offset")
        if not isinstance(offset, int) or not 0 <= offset <= len(output) - len(after):
            errors.append(f"{variant} patch is outside ROM: {patch_id}")
            continue
        span = (offset, offset + len(after))
        if any(span[0] < right and left < span[1] for left, right in spans):
            errors.append(f"{variant} patch overlap: {patch_id}")
        spans.append(span)
        _expect(errors, bytes(output[span[0] : span[1]]), before, f"{variant} patch before mismatch: {patch_id}")
        if kind == "pointer_redirect":
            _expect(errors, before, struct.pack("<I", source), f"{variant} pointer before mismatch: {patch_id}")
            _expect(errors, after, struct.pack("<I", target), f"{variant} pointer after mismatch: {patch_id}")
            _expect(errors, patch.get("replacement_sha256"), None, f"{variant} pointer replacement hash mismatch: {patch_id}")
        else:
            _expect(errors, before, b"\xFF" * len(before), f"{variant} allocation before mismatch: {patch_id}")
            try:
                decoded = _decode_lz77(after, 0)
                decoded_hash = hashlib.sha256(decoded).hexdigest()
                _expect(errors, patch.get("replacement_sha256"), decoded_hash, f"{variant} decoded allocation hash mismatch: {patch_id}")
                original = _decode_lz77(base, source - 0x08000000)
                expected = bytearray(original)
                if variant == "candidate" and source == SOURCE_POINTER:
                    expected[208] = 0x0B
                _expect(errors, decoded, bytes(expected), f"{variant} decoded allocation content mismatch: {patch_id}")
            except Exception as error:
                errors.append(f"{variant} allocation decode failed: {patch_id}: {error}")
        output[span[0] : span[1]] = after
    _expect(errors, len(spans), 8, f"{variant} applied patch count mismatch")
    return bytes(output)


def _verify_bg1_state(
    errors: list[str],
    state_path: Path,
    rom: bytes,
    variant: str,
    expected_entry: int,
) -> None:
    state = load_gba_state(state_path)
    expected_io = {
        0x04000000: 0x1F40,
        0x0400000A: 0x0105,
        0x04000014: 0x0000,
        0x04000016: 0x0000,
        0x04000040: 0x0000,
        0x04000042: 0x0000,
        0x04000044: 0x0000,
        0x04000046: 0x0000,
        0x04000048: 0x0000,
        0x0400004A: 0x0000,
        0x04000050: 0x00FF,
        0x04000052: 0x0010,
        0x04000054: 0x0000,
    }
    for address, expected in expected_io.items():
        actual = struct.unpack("<H", state.read_memory(address, 2))[0]
        _expect(errors, actual, expected, f"{variant} BG1/display IO mismatch at 0x{address:08X}")
    dispcnt = struct.unpack("<H", state.read_memory(0x04000000, 2))[0]
    bg1cnt = struct.unpack("<H", state.read_memory(0x0400000A, 2))[0]
    if not dispcnt & (1 << 9) or dispcnt & 0xE000:
        errors.append(f"{variant} BG1 is disabled or a display window is enabled")
    _expect(errors, bg1cnt & 3, 1, f"{variant} BG1 priority mismatch")
    _expect(errors, (bg1cnt >> 2) & 3, 1, f"{variant} BG1 charbase mismatch")
    _expect(errors, (bg1cnt >> 8) & 31, 1, f"{variant} BG1 screenbase mismatch")
    _expect(errors, (bg1cnt >> 14) & 3, 0, f"{variant} BG1 screen size mismatch")
    screen_base = 0x06000000 + ((bg1cnt >> 8) & 31) * 0x800
    char_base = 0x06000000 + ((bg1cnt >> 2) & 3) * 0x4000
    entry_offset = VRAM_ENTRY_ADDRESS - screen_base
    entry_index = entry_offset // 2
    row, column = divmod(entry_index, 32)
    hofs = struct.unpack("<H", state.read_memory(0x04000014, 2))[0] & 0x1FF
    vofs = struct.unpack("<H", state.read_memory(0x04000016, 2))[0] & 0x1FF
    _expect(errors, [column * 8 - hofs, row * 8 - vofs], [88, 64], f"{variant} BG1 screen coordinate mismatch")
    entry = struct.unpack("<H", state.read_memory(VRAM_ENTRY_ADDRESS, 2))[0]
    _expect(errors, entry, expected_entry, f"{variant} BG1 target entry mismatch")
    _expect(errors, entry & 0x03FF, 712 if variant == "baseline" else 711, f"{variant} BG1 tile index mismatch")
    _expect(errors, bool(entry & 0x0400), False, f"{variant} BG1 H-flip mismatch")
    _expect(errors, bool(entry & 0x0800), True, f"{variant} BG1 V-flip mismatch")
    _expect(errors, entry >> 12, 13, f"{variant} BG1 palette bank mismatch")
    graphics = _decode_lz77(rom, GRAPHICS_POINTER - 0x08000000)
    for tile in (711, 712):
        relative = tile - GRAPHICS_TILE_BASE
        expected_tile = graphics[relative * 32 : relative * 32 + 32]
        _expect(errors, state.read_memory(char_base + tile * 32, 32), expected_tile, f"{variant} BG1 tile {tile} VRAM mismatch")
    expected_palette = rom[
        PALETTE_POINTER - 0x08000000 : PALETTE_POINTER - 0x08000000 + 32
    ]
    _expect(errors, state.read_memory(0x050001A0, 32), expected_palette, f"{variant} BG1 palette 13 PRAM mismatch")


def verify(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    summary = {
        "differing_pixel_count": 0,
        "changed_vram_entry_address": "0x06000A16",
    }
    try:
        manifest = _read_json(artifact / "manifest.json")
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        if any(path.is_symlink() for path in artifact.rglob("*")):
            errors.append("artifact contains a symbolic link")
        _expect(errors, actual_files, EXPECTED_FILES, "artifact file set mismatch")
        _expect(errors, manifest.get("schema"), "git-artifact-promotion-v1", "promotion manifest schema mismatch")
        _expect(errors, manifest.get("artifact_schema"), SCHEMA, "artifact schema mismatch")
        _expect(errors, manifest.get("artifact_status"), "accepted", "artifact status mismatch")
        _expect(errors, manifest.get("payload_file"), "runtime-evidence.json", "payload file mismatch")
        _expect(errors, manifest.get("payload_sha256"), _sha256(artifact / "runtime-evidence.json"), "payload hash mismatch")
        expected_verifier = {
            "command": [
                "python3",
                "tools/verify_residual_wram_tilemap_pixel_ab_evidence.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/residual-wram-tilemap-pixel-ab-v1",
            ],
            "exit_code": 0,
        }
        _expect(errors, manifest.get("verifier"), expected_verifier, "promotion verifier evidence mismatch")
        _expect(errors, set(manifest.get("files", {})), EXPECTED_FILES, "manifest file set mismatch")
        for relative, expected in manifest.get("files", {}).items():
            path = artifact / relative
            if not path.is_file() or _sha256(path) != expected:
                errors.append(f"file hash mismatch: {relative}")
        expected_implementation = manifest.get("implementation_sha256", {})
        _expect(
            errors,
            set(expected_implementation),
            set(IMPLEMENTATION_PATHS),
            "implementation file set mismatch",
        )
        for relative in IMPLEMENTATION_PATHS:
            if expected_implementation.get(relative) != _sha256(root / relative):
                errors.append(f"implementation hash mismatch: {relative}")

        parent = manifest.get("parent", {})
        _expect(
            errors,
            parent.get("path"),
            "artifacts/residual-wram-transformed-tilemap-runtime-v1/manifest.json",
            "parent artifact path mismatch",
        )
        parent_path = root / str(parent.get("path", ""))
        _expect(errors, parent.get("manifest_sha256"), _sha256(parent_path), "parent artifact hash mismatch")
        _expect(errors, parent.get("input_state_sha256"), STATE_SHA256, "parent state hash mismatch")
        scope = manifest.get("scope", {})
        expected_scope = {
            "modified_relocated_rom_runtime_load_verified": True,
            "single_source_byte_to_single_transformed_entry_verified": True,
            "post_queue_vram_entry_verified": True,
            "next_frame_mgba_pixel_diff_verified": True,
            "exact_50_pixel_oracle_verified": True,
            "controlled_entry": True,
            "natural_entry": False,
            "full_timing": False,
            "exclusive_writer": False,
        }
        _expect(errors, scope, expected_scope, "artifact scope mismatch")

        rom = (root / "rom/base.gba").read_bytes()
        _expect(errors, hashlib.sha256(rom).hexdigest(), ROM_SHA256, "base ROM hash mismatch")
        build = _read_json(artifact / "build-manifest.json")
        _expect(errors, build.get("schema"), BUILD_SCHEMA, "build manifest schema mismatch")
        _expect(errors, build.get("base_rom_sha256"), ROM_SHA256, "build base ROM mismatch")
        _expect(errors, build.get("runtime_source_pointer"), "0x08BC15AC", "build runtime pointer mismatch")
        expected_edit = {
            "source_pointer": "0x084635D8",
            "row": 8,
            "column": 8,
            "entry_index": 104,
            "before_entry": "0xD80C",
            "after_entry": "0xD80B",
            "effective_before_entry": "0xDAC8",
            "effective_after_entry": "0xDAC7",
            "tile_add": "0x02BC",
            "vram_entry_address": "0x06000A16",
            "decoded_differing_byte_offsets": [208],
        }
        _expect(errors, build.get("edit"), expected_edit, "build edit contract mismatch")
        _expect(errors, build.get("isolation"), {
            "decoded_source_diff_count": 1,
            "same_pointer_redirects": True,
            "same_runtime_source_pointer": True,
        }, "build isolation contract mismatch")
        for variant, expected_rom_hash, expected_decoded_hash in (
            ("baseline", BASELINE_ROM_SHA256, BASELINE_DECODED_SHA256),
            ("candidate", CANDIDATE_ROM_SHA256, CANDIDATE_DECODED_SHA256),
        ):
            record = build.get("roms", {}).get(variant, {})
            expected_record = {
                "path": f"{variant}.gba",
                "sha256": expected_rom_hash,
                "size": 0x1000000,
                "spec": f"{variant}-spec.json",
                "target_decoded_sha256": expected_decoded_hash,
            }
            _expect(errors, record, expected_record, f"{variant} decoded ROM record mismatch")

        ledgers = build.get("patch_ledgers", {})
        _expect(errors, set(ledgers) if isinstance(ledgers, dict) else set(), {"baseline", "candidate"}, "build patch ledger variants mismatch")
        reconstructed_roms: dict[str, bytes] = {}
        for variant, expected_rom_hash, expected_decoded_hash in (
            ("baseline", BASELINE_ROM_SHA256, BASELINE_DECODED_SHA256),
            ("candidate", CANDIDATE_ROM_SHA256, CANDIDATE_DECODED_SHA256),
        ):
            reconstructed = _reconstruct_rom(
                rom,
                ledgers.get(variant) if isinstance(ledgers, dict) else None,
                errors,
                variant,
            )
            reconstructed_roms[variant] = reconstructed
            if reconstructed:
                _expect(errors, hashlib.sha256(reconstructed).hexdigest(), expected_rom_hash, f"{variant} independently reconstructed ROM hash mismatch")
                runtime_payload = _decode_lz77(
                    reconstructed, RUNTIME_POINTER - 0x08000000
                )
                _expect(errors, hashlib.sha256(runtime_payload).hexdigest(), expected_decoded_hash, f"{variant} independently decoded runtime payload mismatch")
        if all(reconstructed_roms.values()):
            left = _decode_lz77(
                reconstructed_roms["baseline"], RUNTIME_POINTER - 0x08000000
            )
            right = _decode_lz77(
                reconstructed_roms["candidate"], RUNTIME_POINTER - 0x08000000
            )
            _expect(errors, _changed_offsets(left, right), [208], "reconstructed runtime payload A/B difference mismatch")

        baseline_staging = (artifact / "baseline/staging.bin").read_bytes()
        candidate_staging = (artifact / "candidate/staging.bin").read_bytes()
        source = _decode_lz77(rom, SOURCE_POINTER - 0x08000000)
        _expect(errors, len(source), 288, "source tilemap decoded size mismatch")
        _expect(errors, baseline_staging, source, "baseline staging does not equal ROM source")
        expected_candidate = bytearray(source)
        expected_candidate[208] = 0x0B
        _expect(errors, candidate_staging, bytes(expected_candidate), "candidate staging edit mismatch")
        _expect(errors, _changed_offsets(baseline_staging, candidate_staging), [208], "staging A/B difference mismatch")

        output_rows: dict[str, bytes] = {}
        for variant, expected_entry in (("baseline", 0xDAC8), ("candidate", 0xDAC7)):
            output_rows[variant] = (artifact / f"{variant}/output-rows.bin").read_bytes()
            post_rows = (artifact / f"{variant}/post-vram-rows.bin").read_bytes()
            _expect(errors, len(output_rows[variant]), 288, f"{variant} output size mismatch")
            _expect(errors, output_rows[variant], post_rows, f"{variant} post-VRAM rows mismatch")
            if len(post_rows) >= 210:
                _expect(errors, struct.unpack_from("<H", post_rows, 208)[0], expected_entry, f"{variant} VRAM entry mismatch")
            state = load_gba_state(artifact / f"{variant}/queue-post.ss9")
            _expect(errors, state.registers[15], 0x080636D0, f"{variant} queue-post PC mismatch")
            _expect(errors, state.read_memory(VRAM_ENTRY_ADDRESS, 2), struct.pack("<H", expected_entry), f"{variant} queue-post state VRAM entry mismatch")
            _expect(errors, _extract_vram_rows(artifact / f"{variant}/queue-post.ss9"), post_rows, f"{variant} queue-post state rows mismatch")
            replay_state = load_gba_state(artifact / f"{variant}/frame1.ss9")
            _expect(errors, replay_state.read_memory(VRAM_ENTRY_ADDRESS, 2), struct.pack("<H", expected_entry), f"{variant} replay state VRAM entry mismatch")
            _expect(errors, _extract_vram_rows(artifact / f"{variant}/frame1.ss9"), post_rows, f"{variant} replay state rows mismatch")
            _verify_bg1_state(
                errors,
                artifact / f"{variant}/frame1.ss9",
                rom,
                variant,
                expected_entry,
            )

            audit = _read_json(artifact / f"{variant}/sequence-audit.json")
            _expect(errors, audit.get("schema"), "mgba-wram-tilemap-sequence-probe-v2", f"{variant} sequence schema mismatch")
            _expect(errors, audit.get("capture_frames"), 180, f"{variant} capture frames mismatch")
            _expect(errors, audit.get("input_state_sha256"), STATE_SHA256, f"{variant} input state mismatch")
            _expect(errors, audit.get("rom_sha256"), BASELINE_ROM_SHA256 if variant == "baseline" else CANDIDATE_ROM_SHA256, f"{variant} sequence ROM mismatch")
            _expect(errors, audit.get("binary_sha256"), EMULATOR_SHA256, f"{variant} emulator mismatch")
            _expect(errors, audit.get("inputs"), INPUTS, f"{variant} sequence inputs mismatch")
            _expect(errors, audit.get("automatic_inputs"), [], f"{variant} automatic inputs present")
            _expect(errors, audit.get("recovery_inputs"), [], f"{variant} recovery inputs present")
            load = _load_event(audit)
            expected_load = {
                "target": "choice_phase_b_second_load",
                "address": "0x08090DC4",
                "frame": 150,
                "cycle": "1198116187",
                "pc": "0x08090DC6",
                "lr": "0x08090DA1",
                "r0": "0x08BC15AC",
                "r1": "0x0200A640",
            }
            for key, value in expected_load.items():
                _expect(errors, load.get(key), value, f"{variant} load event {key} mismatch")
            load_state = load_gba_state(artifact / f"{variant}/load.ss9")
            _expect(errors, load_state.registers[0], RUNTIME_POINTER, f"{variant} load state r0 mismatch")
            _expect(errors, load_state.registers[1], 0x0200A640, f"{variant} load state r1 mismatch")
            _expect(errors, load_state.registers[15], 0x08090DC6, f"{variant} load state PC mismatch")
            post = _load_post_event(audit)
            _expect(errors, post.get("address"), "0x08090DD0", f"{variant} load-post address mismatch")
            if load and post and int(str(post.get("cycle", "0"))) <= int(str(load.get("cycle", "0"))):
                errors.append(f"{variant} load-post cycle is not after load")
            load_post_state = load_gba_state(artifact / f"{variant}/load-post.ss9")
            _expect(errors, load_post_state.registers[15], 0x08090DD2, f"{variant} load-post state PC mismatch")
            _expect(errors, load_post_state.read_memory(0x0200A640, 288), baseline_staging if variant == "baseline" else candidate_staging, f"{variant} load-post state staging mismatch")
            guard = _read_json(artifact / f"{variant}/sequence-guard.json")
            if not _guard_ok(guard, f"{variant}.gba", "mgba_wram_tilemap_sequence_probe.lua"):
                errors.append(f"{variant} sequence guard mismatch")

            queue_hash = _sha256(artifact / f"{variant}/queue-post.ss9")
            replay = _read_json(artifact / f"{variant}/replay-audit.json")
            _expect(errors, replay.get("capture_frame"), 1, f"{variant} replay frame mismatch")
            _expect(errors, replay.get("inputs"), [], f"{variant} replay inputs present")
            _expect(errors, replay.get("success"), True, f"{variant} replay did not succeed")
            _expect(errors, replay.get("status"), "capture-complete", f"{variant} replay status mismatch")
            _expect(errors, replay.get("input_state_sha256"), queue_hash, f"{variant} replay input hash mismatch")
            _expect(errors, replay.get("rom_sha256"), BASELINE_ROM_SHA256 if variant == "baseline" else CANDIDATE_ROM_SHA256, f"{variant} replay ROM mismatch")
            replay_guard = _read_json(artifact / f"{variant}/replay-guard.json")
            if not _guard_ok(replay_guard, f"{variant}.gba", "mgba_checkpoint_replay.lua"):
                errors.append(f"{variant} replay guard mismatch")
            embedded = _image(artifact / f"{variant}/frame1.ss9")
            external = _image(artifact / f"{variant}/frame1.png")
            _expect(errors, embedded.tobytes(), external.tobytes(), f"{variant} external PNG mismatch")

        for state_name, expected_offsets in (
            ("load.ss9", []),
            ("load-post.ss9", []),
            ("queue-post.ss9", [0x0A16]),
            ("frame1.ss9", [0x0A16]),
        ):
            actual_offsets = _changed_offsets(
                _full_vram(artifact / "baseline" / state_name),
                _full_vram(artifact / "candidate" / state_name),
            )
            _expect(
                errors,
                actual_offsets,
                expected_offsets,
                f"full VRAM A/B difference mismatch: {state_name}",
            )
        _expect(errors, _changed_offsets(output_rows["baseline"], output_rows["candidate"]), [208], "transformed output A/B difference mismatch")

        expected_coordinates, expected_details = _pixel_oracle(rom)
        _expect(errors, len(expected_coordinates), 50, "independent source pixel oracle count mismatch")
        oracle = build.get("pixel_oracle", {})
        expected_oracle = {
            "graphics_pointer": "0x08463688",
            "graphics_tile_base": 700,
            "before_tile_index": 712,
            "after_tile_index": 711,
            "palette_pointer": "0x084638F4",
            "palette_bank": 13,
            "vertical_flip": True,
            "screen_bbox": [88, 64, 95, 71],
            "source_tile_differing_pixel_count": 50,
            "expected_screen_pixels": expected_details,
        }
        _expect(errors, oracle, expected_oracle, "build pixel oracle mismatch")
        baseline_image = _image(artifact / "baseline/frame1.png")
        candidate_image = _image(artifact / "candidate/frame1.png")
        actual_coordinates = [
            [x, y]
            for y in range(160)
            for x in range(240)
            if baseline_image.getpixel((x, y)) != candidate_image.getpixel((x, y))
        ]
        _expect(errors, actual_coordinates, expected_coordinates, "mGBA pixel difference does not match independent oracle")
        palette_value = struct.unpack_from("<H", rom, PALETTE_POINTER - 0x08000000 + 2)[0]
        expected_baseline_rgb = _rgb555(palette_value)
        _expect(errors, expected_baseline_rgb, (8, 8, 255), "source palette RGB mismatch")
        for coordinate in expected_coordinates:
            point = tuple(coordinate)
            _expect(errors, baseline_image.getpixel(point), expected_baseline_rgb, f"baseline pixel color mismatch at {point}")
            _expect(errors, candidate_image.getpixel(point), (231, 247, 214), f"candidate pixel color mismatch at {point}")
        summary["differing_pixel_count"] = len(actual_coordinates)

        evidence = _read_json(artifact / "runtime-evidence.json")
        _expect(errors, evidence.get("schema"), SCHEMA, "runtime evidence schema mismatch")
        _expect(errors, evidence.get("source_pointer"), "0x084635D8", "runtime evidence source mismatch")
        _expect(errors, evidence.get("runtime_source_pointer"), "0x08BC15AC", "runtime evidence pointer mismatch")
        _expect(errors, evidence.get("input_state_sha256"), STATE_SHA256, "runtime evidence state mismatch")
        _expect(errors, evidence.get("edit"), expected_edit, "runtime evidence edit mismatch")
        expected_pixel_result = {
            "frame_after_queue_post": 1,
            "differing_pixel_count": 50,
            "screen_bbox": [88, 64, 95, 71],
            "differing_pixels": expected_coordinates,
            "baseline_rgb": [8, 8, 255],
            "candidate_rgb": [231, 247, 214],
        }
        _expect(errors, evidence.get("pixel_result"), expected_pixel_result, "runtime evidence pixel result mismatch")
        expected_chain = {
            "load_frame": 150,
            "load_cycle": "1198116187",
            "staging_differing_byte_offsets": [208],
            "output_differing_byte_offsets": [208],
            "post_vram_differing_byte_offsets": [208],
            "baseline_vram_entry": "0xDAC8",
            "candidate_vram_entry": "0xDAC7",
        }
        _expect(errors, evidence.get("runtime_chain"), expected_chain, "runtime evidence chain mismatch")
    except Exception as error:  # Convert malformed evidence into a verifier failure.
        errors.append(f"verification exception: {error}")
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
