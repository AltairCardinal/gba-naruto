#!/usr/bin/env python3
"""Independently verify relocated character graphics natural pixel A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


SCHEMA = "character-battle-graphics-pixel-ab-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG = Path("artifacts/character-battle-visuals-v1/manifest.json")
CATALOG_SHA256 = "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
BUILD_SCHEMA = "character-battle-graphics-pixel-ab-build-v1"
BUILD_MANIFEST_SHA256 = "4dd708286e41dd6a7f4cafc4aa3fcbc9895381c9b5ff4889f930f032abccac0d"
RESOURCE_ID = 0
FRAME_ID = 3
COMPONENT_ID = 0
SOURCE_TILE_OFFSET = 96
GRAPHICS_BYTE_OFFSET = 0xD26
BUNDLE_OFFSET = 0x600000
BUNDLE_SIZE = 0x4B60
GRAPHICS_LOCAL = 0x20
COMPONENT_LOCAL = 0x4820
FRAME_TABLE_LOCAL = 0x4A00
TIMELINE_LOCAL = 0x4A50
ANIMATION_TABLE_LOCAL = 0x4B30
DESCRIPTOR_OFFSET = 0x596D5C
NEW_POINTERS = {
    "palette": 0x08600000,
    "graphics": 0x08600020,
    "component_region": 0x08604820,
    "frame_pointer_table": 0x08604A00,
    "timeline_region": 0x08604A50,
    "animation_pointer_table": 0x08604B30,
}
VARIANTS = ("baseline", "candidate")
FILES = {
    "build-manifest.json",
    "runtime-evidence.json",
    *{
        f"{variant}/{name}"
        for variant in VARIANTS
        for name in (
            "bundle.bin", "frame80.ss9", "frame80.png", "audit.json",
            "sentinel.json", "guard.json",
        )
    },
}
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "VRAM": (0x06000000, 0x18000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "OAM": (0x07000000, 0x400),
}
RAW_FILE_SHA256 = {
    "baseline/frame80.ss9": "99846a652a25c4716ddcfcb616d17bf0c66d2bc26813717b532546204ccd6ac2",
    "baseline/frame80.png": "8977b9c1215df7577cb013d26f300806a650c2174edc96799cbdbc1dd49f6464",
    "baseline/audit.json": "b73b0acecf4c05b8a461f004ff96a99f7648df55aa57513b615f8278598c9191",
    "baseline/sentinel.json": "b73b0acecf4c05b8a461f004ff96a99f7648df55aa57513b615f8278598c9191",
    "baseline/guard.json": "9223495585e1507b9403732ab765ef0f7096d526d644c739ab5875610c553f6f",
    "baseline/bundle.bin": "10b78ae7a78d886531b49b3d4810008f191bea11eadc62f364ad873bd79d636d",
    "candidate/frame80.ss9": "20ecfa1ff5c444f7b9483f3efd5c8d20bf6d386bfe7c304c1e52f98c5ea29f33",
    "candidate/frame80.png": "ff00d40c06e4daee1ce204ba4c302d28712b48e636d78ffbd22a564cff6f5f7f",
    "candidate/audit.json": "ce6a0cd2ab5640f74527c8ccef11c6bfbb1e3775d83a8514e2a2408557a9ff8b",
    "candidate/sentinel.json": "ce6a0cd2ab5640f74527c8ccef11c6bfbb1e3775d83a8514e2a2408557a9ff8b",
    "candidate/guard.json": "f43ccdd0ecfe9c48c8834a33037570ac41e653432153003e7b996933f447b0d0",
    "candidate/bundle.bin": "4a1523058a958909842e4cd5925795d8b2ba7cf9fdfd037ddee9bc759720c7c2",
}
DOMAIN_SHA256 = {
    "baseline": {
        "EWRAM": "95ad6f8b448992d29ded38b85af5fe3306a5c1d1742eb6888ffd32b13b4a13cb",
        "VRAM": "7332e03f2f77d0de2999fc8e8862902b98fc3eb4128fcb210fdb6ffcf425cf3c",
        "IO": "231e1f87c0681f73223e68769d361ccf64a2028409e3c056a6931da2448adb30",
        "PRAM": "78c2600dad88cbb2e58e36e9e5d9577b0003e7219c432a54b981dfcee1a3c293",
        "OAM": "dbe5b301548d3902ac2186f53af6e3fa2d5d7a267b6276c4fb24fd3bd0feb81b",
    },
    "candidate": {
        "EWRAM": "95ad6f8b448992d29ded38b85af5fe3306a5c1d1742eb6888ffd32b13b4a13cb",
        "VRAM": "437664a56f0e3c3f581fa4ee6d6c57dd8b04f5355e0e1d7a9c0f3b2156a1d280",
        "IO": "231e1f87c0681f73223e68769d361ccf64a2028409e3c056a6931da2448adb30",
        "PRAM": "78c2600dad88cbb2e58e36e9e5d9577b0003e7219c432a54b981dfcee1a3c293",
        "OAM": "dbe5b301548d3902ac2186f53af6e3fa2d5d7a267b6276c4fb24fd3bd0feb81b",
    },
}
ROM_HASHES = {
    "baseline": "2f738f390239caed48d12af99bd8d324df6c5465610c64fda8278c7f945e5db8",
    "candidate": "6956b3fc3b08f9b5fc7fa730fc9ff3ea321b8d98c177b6182efe155d0c500143",
}
RUN_IDS = {
    "baseline": "character-battle-graphics-pixel-ab-baseline-20260801-r1",
    "candidate": "character-battle-graphics-pixel-ab-candidate-20260801-r1",
}
MGBA_SHA256 = "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
REPLAY_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
IMPLEMENTATION_PATHS = {
    "tools/build_character_battle_graphics_pixel_ab.py",
    "tools/" + "export_" + "character_battle_graphics_pixel_ab_evidence.py",
    "tools/verify_character_battle_graphics_pixel_ab_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_character_battle_graphics_pixel_ab.py",
    "tests/test_character_battle_graphics_pixel_ab_evidence.py",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        return [-1]
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _pointer(value: str) -> int:
    return int(value, 16)


def _bgr555(value: int) -> list[int]:
    return [
        ((value >> shift) & 31) << 3 | ((value >> shift) & 31) >> 2
        for shift in (0, 5, 10)
    ]


def _text_bg_sample(state: Any, bg: int, x: int, y: int) -> dict[str, int | list[int]]:
    io = state.read_memory(0x04000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    pram = state.read_memory(0x05000000, 0x400)
    control = struct.unpack_from("<H", io, 8 + bg * 2)[0]
    scroll_x = struct.unpack_from("<H", io, 0x10 + bg * 4)[0] & 0x1FF
    scroll_y = struct.unpack_from("<H", io, 0x12 + bg * 4)[0] & 0x1FF
    size = (control >> 14) & 3
    width = 512 if size in (1, 3) else 256
    world_x = (x + scroll_x) % width
    world_y = (y + scroll_y) % (512 if size in (2, 3) else 256)
    blocks_x = width // 256
    screen_base = ((control >> 8) & 31) * 0x800
    screen_base += ((world_y // 256) * blocks_x + world_x // 256) * 0x800
    entry_offset = screen_base + (
        ((world_y & 255) // 8) * 32 + (world_x & 255) // 8
    ) * 2
    entry = struct.unpack_from("<H", vram, entry_offset)[0]
    pixel_x = world_x & 7
    pixel_y = world_y & 7
    if entry & 0x0400:
        pixel_x = 7 - pixel_x
    if entry & 0x0800:
        pixel_y = 7 - pixel_y
    char_base = ((control >> 2) & 3) * 0x4000
    if control & 0x0080:
        palette_index = vram[
            char_base + (entry & 0x03FF) * 64 + pixel_y * 8 + pixel_x
        ]
        palette_offset = palette_index * 2
    else:
        packed = vram[
            char_base + (entry & 0x03FF) * 32 + pixel_y * 4 + pixel_x // 2
        ]
        palette_index = (packed >> (4 * (pixel_x & 1))) & 15
        palette_offset = (((entry >> 12) & 15) * 16 + palette_index) * 2
    color = struct.unpack_from("<H", pram, palette_offset)[0]
    return {
        "control": control,
        "priority": control & 3,
        "entry": entry,
        "palette_index": palette_index,
        "rgb": _bgr555(color),
    }


def _target_obj_oracle(state: Any) -> dict[str, Any]:
    io = state.read_memory(0x04000000, 0x400)
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    attr0, attr1, attr2 = struct.unpack(
        "<3H", state.read_memory(0x07000000, 6)
    )
    local_x, local_y = 13, 17
    width_tiles = 4
    tile = (attr2 & 0x03FF) + (local_y // 8) * width_tiles + local_x // 8
    address = 0x06010000 + tile * 32 + (local_y & 7) * 4 + (local_x & 7) // 2
    packed = state.read_memory(address, 1)[0]
    palette_index = (packed >> (4 * (local_x & 1))) & 15
    palette_bank = (attr2 >> 12) & 15
    color = struct.unpack(
        "<H",
        state.read_memory(
            0x05000200 + (palette_bank * 16 + palette_index) * 2,
            2,
        ),
    )[0]
    backgrounds = {
        f"BG{bg}": _text_bg_sample(state, bg, 117, 25)
        for bg in range(4)
        if dispcnt & (1 << (8 + bg))
    }
    return {
        "dispcnt": dispcnt,
        "display_mode": dispcnt & 7,
        "obj_1d_mapping": bool(dispcnt & 0x0040),
        "obj_enabled": bool(dispcnt & 0x1000),
        "windows_enabled": bool(dispcnt & 0xE000),
        "mosaic": struct.unpack_from("<H", io, 0x4C)[0],
        "bldcnt": struct.unpack_from("<H", io, 0x50)[0],
        "bldalpha": struct.unpack_from("<H", io, 0x52)[0],
        "bldy": struct.unpack_from("<H", io, 0x54)[0],
        "attr0": attr0,
        "attr1": attr1,
        "attr2": attr2,
        "screen": [117, 25],
        "local": [local_x, local_y],
        "source_address": f"0x{address:08X}",
        "packed_byte": packed,
        "palette_index": palette_index,
        "rgb": _bgr555(color),
        "backgrounds": backgrounds,
    }


def _validate_bundle(
    root: Path,
    bundle: bytes,
    source: dict[str, Any],
    variant: str,
) -> list[str]:
    errors: list[str] = []
    base = (root / "rom/base.gba").read_bytes()

    def source_bytes(key: str) -> bytes:
        row = source[key]
        offset = _pointer(row["gba_pointer"]) - 0x08000000
        return base[offset : offset + row["size"]]

    if len(bundle) != BUNDLE_SIZE:
        return [f"{variant} bundle size mismatch"]
    palette = source_bytes("palette")
    graphics = source_bytes("graphics")
    components = source_bytes("component_region")
    timelines = source_bytes("timeline_region")
    if bundle[:GRAPHICS_LOCAL] != palette:
        errors.append(f"{variant} bundle palette mismatch")
    expected_graphics = bytearray(graphics)
    if variant == "candidate":
        expected_graphics[GRAPHICS_BYTE_OFFSET] = 0x42
    if bundle[GRAPHICS_LOCAL:COMPONENT_LOCAL] != expected_graphics:
        errors.append(f"{variant} bundle graphics mismatch")
    if bundle[COMPONENT_LOCAL:FRAME_TABLE_LOCAL] != components:
        errors.append(f"{variant} bundle component region mismatch")
    if bundle[TIMELINE_LOCAL:ANIMATION_TABLE_LOCAL] != timelines:
        errors.append(f"{variant} bundle timeline region mismatch")

    old_component = _pointer(source["component_region"]["gba_pointer"])
    frame_table = source_bytes("frame_pointer_table")
    expected_frame_table = b"".join(
        struct.pack(
            "<I",
            NEW_POINTERS["component_region"]
            + struct.unpack_from("<I", frame_table, offset)[0]
            - old_component,
        )
        for offset in range(0, len(frame_table), 4)
    )
    if bundle[FRAME_TABLE_LOCAL:TIMELINE_LOCAL] != expected_frame_table:
        errors.append(f"{variant} bundle frame pointers mismatch")

    old_timeline = _pointer(source["timeline_region"]["gba_pointer"])
    animation_table = source_bytes("animation_pointer_table")
    expected_animation_table = b"".join(
        struct.pack(
            "<I",
            NEW_POINTERS["timeline_region"]
            + struct.unpack_from("<I", animation_table, offset)[0]
            - old_timeline,
        )
        for offset in range(0, len(animation_table), 4)
    )
    if bundle[ANIMATION_TABLE_LOCAL:] != expected_animation_table:
        errors.append(f"{variant} bundle animation pointers mismatch")
    return errors


def _reconstruct_rom(base: bytes, bundle: bytes) -> bytes:
    rom = bytearray(base + bytes([0xFF]) * (0x1000000 - len(base)))
    rom[BUNDLE_OFFSET : BUNDLE_OFFSET + len(bundle)] = bundle
    rom[DESCRIPTOR_OFFSET : DESCRIPTOR_OFFSET + 16] = struct.pack(
        "<4I",
        NEW_POINTERS["frame_pointer_table"],
        NEW_POINTERS["animation_pointer_table"],
        NEW_POINTERS["graphics"],
        NEW_POINTERS["palette"],
    )
    return bytes(rom)


def verify(root: Path | str, artifact: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    memory_differences: dict[str, list[int]] = {}
    pixel_changes: list[list[Any]] = []
    try:
        if artifact.is_symlink():
            raise ValueError("artifact directory is a symlink")
        manifest = _json(artifact / "manifest.json")
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        if actual_files != FILES or set(manifest.get("files", {})) != FILES:
            errors.append("artifact file inventory mismatch")
        for relative in sorted(actual_files & set(manifest.get("files", {}))):
            path = artifact / relative
            if path.is_symlink() or _sha256(path) != manifest["files"][relative]:
                errors.append(f"artifact file hash mismatch: {relative}")
        for relative, expected_hash in RAW_FILE_SHA256.items():
            if relative in actual_files and _sha256(artifact / relative) != expected_hash:
                errors.append(f"raw runtime provenance mismatch: {relative}")
        expected_scope = {
            "natural_entry": True,
            "character_resource_0_frame_3_graphics_pixel_ab": True,
            "relocated_bundle_runtime_verified": True,
            "all_250_resources_runtime_verified": False,
            "all_character_slots_runtime_verified": False,
            "camera_blend_transform_verified": False,
            "physical_gba_verified": False,
        }
        expected_verifier_command = [
            "python3",
            "tools/verify_character_battle_graphics_pixel_ab_evidence.py",
            "--root",
            ".",
            "--artifact",
            f"artifacts/{SCHEMA}",
        ]
        expected_stored_result = {
            "verified": True,
            "errors": [],
            "resource_id": RESOURCE_ID,
            "frame_id": FRAME_ID,
            "memory_differences": {"VRAM": [0x10126]},
            "pixel_changes": [[117, 25, [33, 33, 33], [255, 0, 0]]],
        }
        implementation = manifest.get("implementation_sha256", {})
        implementation_valid = (
            isinstance(implementation, dict)
            and set(implementation) == IMPLEMENTATION_PATHS
            and all(
                _sha256(root / relative) == expected_hash
                for relative, expected_hash in implementation.items()
            )
        )
        if (
            manifest.get("schema") != PROMOTION_SCHEMA
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_id") != SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("parent")
            != {"path": INPUT_STATE.as_posix(), "sha256": INPUT_STATE_SHA256}
            or manifest.get("scope") != expected_scope
            or manifest.get("payload_file") != "runtime-evidence.json"
            or manifest.get("payload_sha256")
            != _sha256(artifact / "runtime-evidence.json")
            or not implementation_valid
            or manifest.get("verifier", {}).get("exit_code") != 0
            or manifest.get("verifier", {}).get("command")
            != expected_verifier_command
            or manifest.get("verifier", {}).get("result")
            != expected_stored_result
        ):
            errors.append("promotion manifest contract mismatch")

        base = (root / "rom/base.gba").read_bytes()
        if len(base) != 0x600000 or _sha256_bytes(base) != ROM_SHA256:
            errors.append("base ROM identity mismatch")
        input_state = root / INPUT_STATE
        if not input_state.is_file() or _sha256(input_state) != INPUT_STATE_SHA256:
            errors.append("input checkpoint identity mismatch")
        if _sha256(root / CATALOG) != CATALOG_SHA256:
            errors.append("character visual catalog identity mismatch")
        catalog = _json(root / CATALOG)
        source = catalog["resources"][RESOURCE_ID]
        if (
            source.get("resource_id") != RESOURCE_ID
            or source.get("slot_rows") != [0]
            or source["descriptor"].get("graphics") != "0x0813E090"
            or source["frames"][FRAME_ID]["components"][COMPONENT_ID].get("tile_offset")
            != SOURCE_TILE_OFFSET
        ):
            errors.append("source resource contract mismatch")

        build = _json(artifact / "build-manifest.json")
        expected_edit = {
            "graphics_byte_offset": GRAPHICS_BYTE_OFFSET,
            "before_hex": "12", "after_hex": "42",
            "source_pixel": [13, 17], "expected_screen_pixel": [117, 25],
            "before_palette_index": 1, "after_palette_index": 4,
        }
        if (
            _sha256(artifact / "build-manifest.json") != BUILD_MANIFEST_SHA256
            or set(build.get("variants", {})) != set(VARIANTS)
            or build.get("schema") != BUILD_SCHEMA
            or build.get("base_rom_sha256") != ROM_SHA256
            or build.get("edit") != expected_edit
            or build.get("resource")
            != {
                "resource_id": 0,
                "slot_rows": [0],
                "source_graphics": "0x0813E090",
                "source_graphics_sha256": "00604b6d454b23f73413ec7d65cebead033c7a6177f3e8da9861fb32f44db3ec",
                "source_frame_id": 3,
                "source_component_index": 0,
                "source_tile_offset": 96,
            }
            or build.get("runtime_contract", {}).get("capture_frame") != 80
            or build.get("runtime_contract", {}).get("input")
            != {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
            or build.get("runtime_contract", {}).get("input_checkpoint")
            != INPUT_STATE.as_posix()
            or build.get("isolation", {}).get("rom_difference_offsets") != [0x600D46]
            or build.get("isolation", {}).get("independent_runtime_required") is not True
            or not build.get("isolation", {}).get("shared_patch_topology")
            or not build.get("isolation", {}).get("single_graphics_byte_difference")
        ):
            errors.append("build manifest contract mismatch")

        bundles = {variant: (artifact / variant / "bundle.bin").read_bytes() for variant in VARIANTS}
        for variant in VARIANTS:
            errors.extend(_validate_bundle(root, bundles[variant], source, variant))
            rom = _reconstruct_rom(base, bundles[variant])
            if _sha256_bytes(rom) != build["variants"][variant]["rom_sha256"]:
                errors.append(f"{variant} reconstructed ROM hash mismatch")
        if _diff(bundles["baseline"], bundles["candidate"]) != [0xD46]:
            errors.append("candidate bundle single-byte isolation mismatch")

        states = {
            variant: load_gba_state(artifact / variant / "frame80.ss9")
            for variant in VARIANTS
        }
        for variant, state in states.items():
            for label, (address, size) in DOMAINS.items():
                actual_hash = _sha256_bytes(state.read_memory(address, size))
                if actual_hash != DOMAIN_SHA256[variant][label]:
                    errors.append(f"{variant} {label} state identity mismatch")
        for label, (address, size) in DOMAINS.items():
            changed = _diff(
                states["baseline"].read_memory(address, size),
                states["candidate"].read_memory(address, size),
            )
            if changed:
                memory_differences[label] = changed
        if memory_differences != {"VRAM": [0x10126]}:
            errors.append("runtime memory domain isolation mismatch")
        if (
            states["baseline"].read_memory(0x06010126, 1) != b"\x12"
            or states["candidate"].read_memory(0x06010126, 1) != b"\x42"
        ):
            errors.append("runtime OBJ graphics byte mismatch")
        expected_oam = bytes.fromhex("088068c00008e300")
        if any(state.read_memory(0x07000000, 8) != expected_oam for state in states.values()):
            errors.append("runtime OAM identity mismatch")
        if any(
            state.read_memory(0x0201BE28, 4) != bytes.fromhex("242c0916")
            or state.read_memory(0x02026804, 2) != bytes([0, 41])
            for state in states.values()
        ):
            errors.append("runtime battle arrival mismatch")

        obj_oracles = {
            variant: _target_obj_oracle(state) for variant, state in states.items()
        }
        for variant, oracle in obj_oracles.items():
            if (
                oracle["dispcnt"] != 0x1940
                or oracle["display_mode"] != 0
                or oracle["obj_1d_mapping"] is not True
                or oracle["obj_enabled"] is not True
                or oracle["windows_enabled"] is not False
                or oracle["mosaic"] != 0
                or oracle["bldcnt"] != 0x1744
                or oracle["bldalpha"] != 0x0A0A
                or oracle["bldy"] != 0x0010
                or oracle["attr0"] != 0x8008
                or oracle["attr1"] != 0xC068
                or oracle["attr2"] != 0x0800
                or oracle["source_address"] != "0x06010126"
                or oracle["backgrounds"].get("BG0", {}).get("priority") != 3
                or oracle["backgrounds"].get("BG3", {}).get("priority") != 0
                or oracle["backgrounds"].get("BG3", {}).get("palette_index") != 0
            ):
                errors.append(f"{variant} display/OBJ composition contract mismatch")
        if (
            obj_oracles["baseline"]["packed_byte"] != 0x12
            or obj_oracles["baseline"]["palette_index"] != 1
            or obj_oracles["baseline"]["rgb"] != [33, 33, 33]
            or obj_oracles["candidate"]["packed_byte"] != 0x42
            or obj_oracles["candidate"]["palette_index"] != 4
            or obj_oracles["candidate"]["rgb"] != [255, 0, 0]
        ):
            errors.append("runtime OBJ source pixel oracle mismatch")

        images = {
            variant: Image.open(artifact / variant / "frame80.png").convert("RGB")
            for variant in VARIANTS
        }
        for variant in VARIANTS:
            if images[variant].size != (240, 160):
                errors.append(f"{variant} screenshot dimensions mismatch")
            if png_screen_fingerprint(artifact / variant / "frame80.ss9") != png_screen_fingerprint(artifact / variant / "frame80.png"):
                errors.append(f"{variant} embedded screenshot binding mismatch")
        pixel_changes = [
            [x, y, list(images["baseline"].getpixel((x, y))), list(images["candidate"].getpixel((x, y)))]
            for y in range(160)
            for x in range(240)
            if images["baseline"].getpixel((x, y)) != images["candidate"].getpixel((x, y))
        ]
        if pixel_changes != [[117, 25, [33, 33, 33], [255, 0, 0]]]:
            errors.append("final pixel oracle mismatch")
        if any(
            list(images[variant].getpixel((117, 25))) != obj_oracles[variant]["rgb"]
            for variant in VARIANTS
        ):
            errors.append("final screenshot does not match the visible OBJ oracle")
        palette = states["baseline"].read_memory(0x05000200, 32)
        before_color = struct.unpack_from("<H", palette, 2)[0]
        after_color = struct.unpack_from("<H", palette, 8)[0]
        if _bgr555(before_color) != [33, 33, 33] or _bgr555(after_color) != [255, 0, 0]:
            errors.append("runtime palette color oracle mismatch")

        evidence = _json(artifact / "runtime-evidence.json")
        if (
            evidence.get("schema") != SCHEMA
            or evidence.get("runtime", {}).get("memory_differences") != memory_differences
            or evidence.get("runtime", {}).get("pixel_changes") != pixel_changes
            or evidence.get("runtime", {}).get("resource_id") != RESOURCE_ID
            or evidence.get("runtime", {}).get("frame_id") != FRAME_ID
            or evidence.get("runtime", {}).get("obj_oracles") != obj_oracles
            or evidence.get("input", {}).get("path") != INPUT_STATE.as_posix()
            or evidence.get("input", {}).get("sha256") != INPUT_STATE_SHA256
            or evidence.get("provenance")
            != {"mgba_sha256": MGBA_SHA256, "replay_script_sha256": REPLAY_SHA256}
        ):
            errors.append("runtime evidence pixel/resource contract mismatch")
        run_ids = []
        for variant in VARIANTS:
            audit = _json(artifact / variant / "audit.json")
            sentinel = _json(artifact / variant / "sentinel.json")
            guard = _json(artifact / variant / "guard.json")
            if audit != sentinel:
                errors.append(f"{variant} audit/sentinel mismatch")
            run_ids.append(audit.get("run_id"))
            if (
                audit.get("run_id") != RUN_IDS[variant]
                or audit.get("frame") != 80
                or audit.get("capture_frame") != 80
                or audit.get("inputs") != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
                or audit.get("evidence_mode") != "single-input"
                or audit.get("success") is not True
                or audit.get("status") != "capture-complete"
                or audit.get("automatic_inputs") != []
                or audit.get("recovery_inputs") != []
                or audit.get("input_state_sha256") != INPUT_STATE_SHA256
                or audit.get("rom_sha256") != ROM_HASHES[variant]
                or not str(audit.get("output_state", "")).endswith(f"/{variant}/frame80.ss9")
                or not str(audit.get("output_png", "")).endswith(f"/{variant}/frame80.png")
            ):
                errors.append(f"{variant} replay audit mismatch")
            command = guard.get("command", [])
            if (
                guard.get("reason") != "completed"
                or guard.get("exit_code") != 0
                or guard.get("degraded") is not False
                or guard.get("protection_backend") != "posix-process-group"
                or guard.get("completion_trigger") != "success-marker"
                or not isinstance(guard.get("child_pid"), int)
                or guard.get("child_pid") <= 1
                or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
                or not 0 < guard.get("peak_tree_rss_mib") < 1024
                or not isinstance(command, list)
                or len(command) != 4
                or not str(command[0]).endswith("/mGBA")
                or command[1] != "--script"
                or not str(command[2]).endswith("/tools/mgba_single_input_replay.lua")
                or not str(command[3]).endswith(f"/{variant}/staged.gba")
            ):
                errors.append(f"{variant} resource guard mismatch")
        if len(set(run_ids)) != 2 or any(not isinstance(value, str) for value in run_ids):
            errors.append("runtime runs are not independent")
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error, json.JSONDecodeError) as error:
        errors.append(f"verification exception: {error}")
    return {
        "verified": not errors,
        "errors": errors,
        "resource_id": RESOURCE_ID,
        "frame_id": FRAME_ID,
        "memory_differences": memory_differences,
        "pixel_changes": pixel_changes,
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
