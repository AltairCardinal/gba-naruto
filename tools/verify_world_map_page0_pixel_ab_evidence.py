#!/usr/bin/env python3
"""Independently verify the natural world-map page 0 single-pixel A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from tools.verify_menu_portrait_writeback_audit import _encode_lz77


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/world-map-backgrounds-v1/manifest.json")
CATALOG_SHA256 = "b9b879841b7605af80e143a9f2f9bbe2e64754d6390b708033f92cc831bd4dd3"
INPUT_PATH = Path(
    "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-11.ss9"
)
INPUT_SHA256 = "bf821ecdd9945c123576ff7f26717c4d2018f07e623c36cb83dc2bb0fa569555"
GRAPHICS_SOURCE_OFFSET = 0x4414E4
TABLE_POINTER_OFFSET = 0x5A8014
GRAPHICS_ALLOCATION_OFFSET = 0xB71000
GRAPHICS_POINTER = 0x08B71000
GRAPHICS_BYTE_OFFSET = 15588
TARGET_VRAM_OFFSET = 0x7CE4
BEFORE_INDEX = 112
AFTER_INDEX = 137
BASELINE_GRAPHICS_SHA256 = (
    "ed2ef49ec3f755360f2492afaed49936efe70fd92be4333be8cfc9e172338d5e"
)
CANDIDATE_GRAPHICS_SHA256 = (
    "1cc2f755948525ebd13d358fc97910658e4aa8c7ce82393c3ffc7b4be454fd1e"
)
BASELINE_ROM_SHA256 = (
    "58b2a447b125fdf4ae0099a0b41de9c5ea7e32fa5f2bde600f1c2d867198e6c1"
)
CANDIDATE_ROM_SHA256 = (
    "a859355a2a370ee46fab7648224a2f3e31497262a52559e6cfa243b8f40a3a8b"
)
PALETTE_SHA256 = "605542775b27eba571bd59996f69ca7c2858132660f741e08b8b1573676a08af"
TILEMAP_SHA256 = "6713f99e017c9e29c80972f338b577ee9fd5e1873cc8051ace13ab32e3803412"
RAW_FILES = (
    "build-manifest.json",
    "baseline/audit.json",
    "baseline/background.8bpp.bin",
    "baseline/frame80.png",
    "baseline/frame80.ss9",
    "baseline/guard.json",
    "baseline/sentinel.json",
    "baseline/spec.json",
    "candidate/audit.json",
    "candidate/background.8bpp.bin",
    "candidate/frame80.png",
    "candidate/frame80.ss9",
    "candidate/guard.json",
    "candidate/sentinel.json",
    "candidate/spec.json",
)
IMPLEMENTATION_PATHS = (
    "tools/build_world_map_page0_pixel_ab.py",
    "tools/export_world_map_page0_pixel_ab_evidence.py",
    "tools/verify_world_map_page0_pixel_ab_evidence.py",
    "tools/import_world_map_background_relocations.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/build_mod.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
)
EXPECTED_SCOPE = {
    "natural_page0_load": True,
    "production_relocation_route": True,
    "page0_graphics_single_pixel": True,
    "page1_and_page2_runtime_verified": False,
    "labels_cursor_transition_verified": False,
    "physical_gba_verified": False,
}
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
EXPECTED_DIFFERENCES = {
    "EWRAM": [],
    "IWRAM": [],
    "IO": [],
    "PRAM": [],
    "VRAM": [TARGET_VRAM_OFFSET],
    "OAM": [],
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("world-map independent byte domains differ in size")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("world-map independent screenshot geometry mismatch")
        return image.convert("RGB").tobytes()


def _pixel_changes(left: bytes, right: bytes) -> list[dict[str, Any]]:
    changes = []
    for index in range(240 * 160):
        offset = index * 3
        before = list(left[offset : offset + 3])
        after = list(right[offset : offset + 3])
        if before != after:
            changes.append(
                {
                    "x": index % 240,
                    "y": index // 240,
                    "before_rgb": before,
                    "after_rgb": after,
                }
            )
    return changes


def _bgr555_rgb(value: int) -> list[int]:
    return [
        ((value >> shift) & 31) << 3 | ((value >> shift) & 31) >> 2
        for shift in (0, 5, 10)
    ]


def _catalog_contract(root: Path, base: bytes) -> tuple[bytes, bytes, bytes]:
    catalog_path = root / CATALOG_PATH
    if _sha256_file(catalog_path) != CATALOG_SHA256:
        raise ValueError("world-map independent catalog hash mismatch")
    catalog = _json(catalog_path)
    page = next(row for row in catalog["pages"] if row["page_id"] == 0)
    background = page["background"]
    graphics_path = catalog_path.parent / background["graphics_file"]
    palette_path = catalog_path.parent / background["palette_file"]
    tilemap_path = catalog_path.parent / background["tilemap_file"]
    graphics = graphics_path.read_bytes()
    palette = palette_path.read_bytes()
    tilemap = tilemap_path.read_bytes()
    if (
        catalog.get("schema") != "world-map-backgrounds-v1"
        or catalog.get("summary", {}).get("page_count") != 3
        or page.get("raw_hex") != "e4144408d8914408a4134408"
        or background.get("graphics_pointer") != "0x084414E4"
        or background.get("palette_pointer") != "0x084413A4"
        or background.get("tilemap_pointer") != "0x084491D8"
        or background.get("bits_per_pixel") != 8
        or background.get("dimensions_tiles") != [30, 20]
        or background.get("tile_count") != 512
        or background.get("palette_color_count") != 160
        or len(graphics) != 32768
        or _sha256(graphics) != BASELINE_GRAPHICS_SHA256
        or len(palette) != 320
        or _sha256(palette) != PALETTE_SHA256
        or len(tilemap) != 1200
        or _sha256(tilemap) != TILEMAP_SHA256
        or base[TABLE_POINTER_OFFSET : TABLE_POINTER_OFFSET + 36].hex()
        != "e4144408d8914408a4134408bc974408980245087c9644087c084508987845083c074508"
        or _sha256(base[TABLE_POINTER_OFFSET : TABLE_POINTER_OFFSET + 36])
        != catalog["source_tables"]["backgrounds"]["sha256"]
    ):
        raise ValueError("world-map independent catalog contract mismatch")
    target_cell = 9 * 30 + 14
    entries = struct.unpack("<600H", tilemap)
    if (
        entries[target_cell] & 0x3FF != 243
        or sum((entry & 0x3FF) == 243 for entry in entries) != 1
        or 243 * 64 + 4 * 8 + 4 != GRAPHICS_BYTE_OFFSET
        or graphics[GRAPHICS_BYTE_OFFSET] != BEFORE_INDEX
        or _bgr555_rgb(int.from_bytes(palette[224:226], "little"))
        != [189, 165, 107]
        or _bgr555_rgb(int.from_bytes(palette[274:276], "little")) != [66, 33, 0]
    ):
        raise ValueError("world-map independent target pixel mapping mismatch")
    return graphics, palette, tilemap


def _expected_patch_ledger(graphics: bytes) -> list[dict[str, Any]]:
    encoded = _encode_lz77(graphics)
    return [
        {
            "id": "world-map-graphics-00",
            "kind": "allocation",
            "asset_type": "world_map_background_relocation",
            "resource_type": "graphics",
            "offset": GRAPHICS_ALLOCATION_OFFSET,
            "size": len(encoded),
            "before_sha256": _sha256(bytes([0xFF]) * len(encoded)),
            "after_sha256": _sha256(encoded),
            "before_hex": None,
            "after_hex": None,
            "new_pointer": GRAPHICS_POINTER,
            "target_pointer_offsets": [TABLE_POINTER_OFFSET],
            "allocation": {
                "owner": "sequel_image_assets",
                "partition": "sequel-image-assets",
                "region": "world-map-backgrounds",
                "region_owner": "world_map_background_resources",
            },
        },
        {
            "id": "world-map-graphics-00.pointer-5a8014",
            "kind": "redirect",
            "asset_type": "world_map_background_pointer",
            "resource_type": "graphics",
            "offset": TABLE_POINTER_OFFSET,
            "size": 4,
            "before_sha256": _sha256(bytes.fromhex("e4144408")),
            "after_sha256": _sha256(bytes.fromhex("0010b708")),
            "before_hex": "e4144408",
            "after_hex": "0010b708",
            "new_pointer": GRAPHICS_POINTER,
            "target_pointer_offsets": [TABLE_POINTER_OFFSET],
            "allocation": None,
        },
    ]


def _rebuild_rom(base: bytes, graphics: bytes) -> bytes:
    encoded = _encode_lz77(graphics)
    if len(encoded) != 31963:
        raise ValueError("world-map independent encoded size mismatch")
    rom = bytearray(base + bytes([0xFF]) * (0x1000000 - len(base)))
    rom[GRAPHICS_ALLOCATION_OFFSET : GRAPHICS_ALLOCATION_OFFSET + len(encoded)] = encoded
    rom[TABLE_POINTER_OFFSET : TABLE_POINTER_OFFSET + 4] = GRAPHICS_POINTER.to_bytes(
        4, "little"
    )
    return bytes(rom)


def _verify_spec(root: Path, raw: Path, variant: str) -> None:
    spec = _json(raw / variant / "spec.json")
    source_file = Path(spec.get("edits", [{}])[0].get("source_file", ""))
    expected = {
        "schema": "world-map-background-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": "sequel/image-resource-regions.json",
        "region_registry_sha256": _sha256_file(root / "sequel/image-resource-regions.json"),
        "region": "world-map-backgrounds",
        "region_owner": "world_map_background_resources",
        "edits": [
            {
                "id": f"world-map-page0-graphics-pixel-ab-{variant}",
                "resource_type": "graphics",
                "resource_sha256": BASELINE_GRAPHICS_SHA256,
                "source_file": spec["edits"][0]["source_file"],
                "expected": {
                    "decompressed_size": 32768,
                    "physical_offsets": [GRAPHICS_SOURCE_OFFSET],
                    "pointer_offsets": [TABLE_POINTER_OFFSET],
                },
                "target_pointer_offsets": [TABLE_POINTER_OFFSET],
            }
        ],
    }
    if (
        spec != expected
        or source_file.parts[-2:] != (variant, "background.8bpp.bin")
    ):
        raise ValueError(f"world-map independent {variant} authoring spec mismatch")


def _audit_summary(raw: Path, variant: str, build: dict[str, Any]) -> dict[str, Any]:
    audit = _json(raw / variant / "audit.json")
    sentinel = _json(raw / variant / "sentinel.json")
    guard = _json(raw / variant / "guard.json")
    if audit != sentinel:
        raise ValueError("world-map independent audit/sentinel mismatch")
    if (
        audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("inputs")
        != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("capture_frame") != 80
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        or audit.get("staged_rom_sha256") != audit.get("rom_sha256")
        or audit.get("input_state_sha256") != INPUT_SHA256
        or audit.get("output_state_sha256")
        != _sha256_file(raw / variant / "frame80.ss9")
        or audit.get("output_png_sha256")
        != _sha256_file(raw / variant / "frame80.png")
        or audit.get("guard_summary_sha256")
        != _sha256_file(raw / variant / "guard.json")
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
    ):
        raise ValueError(f"world-map independent {variant} runtime provenance mismatch")
    return {
        "run_id": audit["run_id"],
        "rom_sha256": audit["rom_sha256"],
        "state_sha256": audit["output_state_sha256"],
        "png_sha256": audit["output_png_sha256"],
        "binary_sha256": audit["binary_sha256"],
        "build_manifest_sha256": audit["build_manifest_sha256"],
        "replay_script_sha256": audit["replay_script_sha256"],
        "guard_sha256": audit["guard_summary_sha256"],
        "child_pgid": audit["child_pgid"],
        "peak_tree_rss_mib": audit["peak_tree_rss_mib"],
        "pgid_clean": True,
    }


def _verify(root: Path, artifact: Path) -> None:
    root = root.resolve()
    artifact = artifact.resolve()
    raw = artifact / "raw"
    expected_files = {
        Path("manifest.json"),
        Path("runtime-evidence.json"),
        *(Path("raw") / name for name in RAW_FILES),
    }
    actual_files = {
        path.relative_to(artifact)
        for path in artifact.rglob("*")
        if path.is_file()
    }
    if any(path.is_symlink() for path in artifact.rglob("*")):
        raise ValueError("world-map independent artifact must not contain symlinks")
    if actual_files != expected_files:
        raise ValueError("world-map independent artifact file set mismatch")

    manifest = _json(artifact / "manifest.json")
    evidence = _json(artifact / "runtime-evidence.json")
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("world-map independent base ROM mismatch")
    original_graphics, palette, tilemap = _catalog_contract(root, base)

    build = _json(raw / "build-manifest.json")
    expected_edit = {
        "page_id": 0,
        "resource_type": "graphics",
        "table_pointer_offset": TABLE_POINTER_OFFSET,
        "canvas_xy": [116, 76],
        "tile_id": 243,
        "graphics_byte_offset": GRAPHICS_BYTE_OFFSET,
        "before_index": BEFORE_INDEX,
        "after_index": AFTER_INDEX,
    }
    if (
        build.get("schema") != "world-map-page0-pixel-ab-build-v1"
        or build.get("base_rom_sha256") != ROM_SHA256
        or build.get("source_catalog") != CATALOG_PATH.as_posix()
        or build.get("source_catalog_sha256") != CATALOG_SHA256
        or build.get("input_state") != INPUT_PATH.as_posix()
        or build.get("input_state_sha256") != INPUT_SHA256
        or build.get("input")
        != {"key": "A", "down_frame": 5, "up_frame": 13, "capture_frame": 80}
        or build.get("edit") != expected_edit
        or build.get("isolation")
        != {
            "decoded_graphics_offsets": [GRAPHICS_BYTE_OFFSET],
            "same_allocation_address": True,
            "same_redirect_pointer": True,
            "page_1_and_2_descriptors_unchanged": True,
            "rom_changed_offset_count": 1,
            "rom_changed_offsets": [0xB71000 + 14675],
            "changed_span": [0xB71000 + 14675, 0xB71000 + 14676],
        }
        or set(build.get("variants", {})) != {"baseline", "candidate"}
    ):
        raise ValueError("world-map independent build manifest mismatch")

    graphics: dict[str, bytes] = {}
    expected_rom_hashes = {
        "baseline": BASELINE_ROM_SHA256,
        "candidate": CANDIDATE_ROM_SHA256,
    }
    expected_graphics_hashes = {
        "baseline": BASELINE_GRAPHICS_SHA256,
        "candidate": CANDIDATE_GRAPHICS_SHA256,
    }
    for variant in ("baseline", "candidate"):
        _verify_spec(root, raw, variant)
        payload = (raw / variant / "background.8bpp.bin").read_bytes()
        graphics[variant] = payload
        rebuilt = _rebuild_rom(base, payload)
        row = build["variants"][variant]
        if (
            len(payload) != 32768
            or _sha256(payload) != expected_graphics_hashes[variant]
            or row.get("graphics_path") != f"{variant}/background.8bpp.bin"
            or row.get("graphics_sha256") != expected_graphics_hashes[variant]
            or row.get("spec_path") != f"{variant}/spec.json"
            or row.get("rom_path") != f"{variant}/{variant}.gba"
            or row.get("rom_size") != 0x1000000
            or row.get("rom_sha256") != expected_rom_hashes[variant]
            or row.get("patch_ledger") != _expected_patch_ledger(payload)
            or _sha256(rebuilt) != expected_rom_hashes[variant]
            or rebuilt[TABLE_POINTER_OFFSET : TABLE_POINTER_OFFSET + 4]
            != GRAPHICS_POINTER.to_bytes(4, "little")
            or rebuilt[0x5A8020 : 0x5A8038] != base[0x5A8020 : 0x5A8038]
        ):
            raise ValueError(f"world-map independent {variant} ROM rebuild mismatch")
    if (
        graphics["baseline"] != original_graphics
        or _diff(graphics["baseline"], graphics["candidate"])
        != [GRAPHICS_BYTE_OFFSET]
        or graphics["baseline"][GRAPHICS_BYTE_OFFSET] != BEFORE_INDEX
        or graphics["candidate"][GRAPHICS_BYTE_OFFSET] != AFTER_INDEX
    ):
        raise ValueError("world-map independent authored isolation mismatch")

    input_state = load_gba_state(root / INPUT_PATH)
    input_screenblock = input_state.read_memory(0x06000000, 0x800)
    input_has_tilemap = all(
        input_screenblock[row * 64 : row * 64 + 60]
        == tilemap[row * 60 : row * 60 + 60]
        for row in range(20)
    )
    if (
        _sha256_file(root / INPUT_PATH) != INPUT_SHA256
        or input_state.read_u32(0x030011F0) != 0x08031FE7
        or int.from_bytes(input_state.read_memory(0x04000008, 2), "little") != 0x0007
        or int.from_bytes(input_state.read_memory(0x0400000E, 2), "little") != 0x0300
        or input_state.read_memory(0x06004000, 32768) in graphics.values()
        or input_state.read_memory(0x05000000, 320) == palette
        or input_has_tilemap
    ):
        raise ValueError("world-map independent natural pre-load boundary mismatch")

    states = {
        variant: load_gba_state(raw / variant / "frame80.ss9")
        for variant in ("baseline", "candidate")
    }
    differences = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    if differences != EXPECTED_DIFFERENCES:
        raise ValueError("world-map independent runtime memory isolation mismatch")
    overwrite_offsets: dict[str, list[int]] = {}
    screenshot_rgb: dict[str, bytes] = {}
    runs: dict[str, dict[str, Any]] = {}
    for variant in ("baseline", "candidate"):
        state = states[variant]
        runtime_graphics = state.read_memory(0x06004000, 32768)
        overwrite_offsets[variant] = _diff(graphics[variant], runtime_graphics)
        screenblock = state.read_memory(0x06000000, 0x800)
        screenshot_rgb[variant] = _rgb(raw / variant / "frame80.png")
        runs[variant] = _audit_summary(raw, variant, build)
        if (
            int.from_bytes(state.read_memory(0x04000008, 2), "little") != 0x0086
            or int.from_bytes(state.read_memory(0x0400000E, 2), "little") != 0x030C
            or runtime_graphics[GRAPHICS_BYTE_OFFSET]
            != graphics[variant][GRAPHICS_BYTE_OFFSET]
            or state.read_memory(0x05000000, 320) != palette
            or any(
                screenblock[row * 64 : row * 64 + 60]
                != tilemap[row * 60 : row * 60 + 60]
                for row in range(20)
            )
            or render_checkpoint(raw / variant / "frame80.ss9")[0]
            != screenshot_rgb[variant]
        ):
            raise ValueError(f"world-map independent {variant} natural route mismatch")
    common_overwrites = overwrite_offsets["baseline"]
    if (
        common_overwrites != overwrite_offsets["candidate"]
        or len(common_overwrites) != 806
        or GRAPHICS_BYTE_OFFSET in common_overwrites
        or any(
            states["baseline"].read_memory(0x06004000 + offset, 1)
            != states["candidate"].read_memory(0x06004000 + offset, 1)
            for offset in common_overwrites
        )
    ):
        raise ValueError("world-map independent common overwrite mismatch")

    changes = _pixel_changes(screenshot_rgb["baseline"], screenshot_rgb["candidate"])
    expected_changes = [
        {
            "x": 116,
            "y": 76,
            "before_rgb": [189, 165, 107],
            "after_rgb": [66, 33, 0],
        }
    ]
    if changes != expected_changes:
        raise ValueError("world-map independent final pixel mismatch")
    packed_overwrites = b"".join(
        struct.pack("<I", offset) for offset in common_overwrites
    )
    expected_evidence = {
        "schema": "world-map-page0-pixel-ab-runtime-v1",
        "verified": True,
        "input": {
            "path": INPUT_PATH.as_posix(),
            "sha256": INPUT_SHA256,
            "script_cursor": "0x08031FE7",
            "event": {
                "key": "A",
                "down_frame": 5,
                "up_frame": 13,
                "hold_frames": 8,
            },
            "capture_frame": 80,
            "page0_absent_before_input": True,
        },
        "edit": expected_edit,
        "runtime": {
            "memory_differences": differences,
            "changed_vram_address": "0x06007CE4",
            "baseline_vram_byte": BEFORE_INDEX,
            "candidate_vram_byte": AFTER_INDEX,
            "graphics_vram_address": "0x06004000",
            "palette_pram_address": "0x05000000",
            "tilemap_vram_address": "0x06000000",
            "common_overwrite_count": 806,
            "common_overwrite_offsets_sha256": _sha256(packed_overwrites),
            "renderer_exact": True,
            "pixels": {
                "count": 1,
                "bbox": [116, 76, 116, 76],
                "baseline_rgb_sha256": _sha256(screenshot_rgb["baseline"]),
                "candidate_rgb_sha256": _sha256(screenshot_rgb["candidate"]),
                "changes": changes,
            },
        },
        "runs": runs,
        "scope": EXPECTED_SCOPE,
    }
    if evidence != expected_evidence:
        raise ValueError("world-map independent semantic evidence mismatch")

    expected_inventory = {
        path.as_posix(): _sha256_file(artifact / path)
        for path in sorted(expected_files - {Path("manifest.json")})
    }
    expected_manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": "world-map-page0-pixel-ab-runtime-v1",
        "artifact_id": "world-map-page0-pixel-ab-v1",
        "artifact_status": "accepted",
        "base_rom_sha256": ROM_SHA256,
        "parent": {"path": INPUT_PATH.as_posix(), "sha256": INPUT_SHA256},
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256_file(artifact / "runtime-evidence.json"),
        "files": expected_inventory,
        "raw_files": {name: _sha256_file(raw / name) for name in RAW_FILES},
        "implementation_sha256": {
            path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
        },
        "scope": EXPECTED_SCOPE,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_world_map_page0_pixel_ab_evidence.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/world-map-page0-pixel-ab-v1",
            ],
            "exit_code": 0,
            "result": {"errors": [], "verified": True},
        },
    }
    if manifest != expected_manifest:
        raise ValueError("world-map independent promotion manifest mismatch")


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    errors = []
    try:
        _verify(Path(root), Path(artifact))
    except Exception as error:  # fail closed with one stable machine-readable result
        errors.append(str(error))
    return {"verified": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = verify_evidence(args.root, args.artifact)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
