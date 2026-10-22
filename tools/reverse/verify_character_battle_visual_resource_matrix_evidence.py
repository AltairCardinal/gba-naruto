#!/usr/bin/env python3
"""Independently verify character palette/component/timeline natural pixel A/B."""

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
    from inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "character-battle-visual-resource-matrix-v1"
BUILD_SCHEMA = "character-battle-visual-resource-matrix-build-v1"
ARTIFACT_ID = SCHEMA
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
MGBA_SHA256 = "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
MGBA_BUILD_MANIFEST_SHA256 = "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d"
REPLAY_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
VARIANTS = ("baseline", "palette", "component", "timeline")
EVENT = {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
BUNDLE_OFFSET = 0x600000
BUNDLE_SIZE = 0x4B60
DESCRIPTOR_OFFSET = 0x596D5C
DESCRIPTOR = struct.pack("<4I", 0x08604A00, 0x08604B30, 0x08600020, 0x08600000)
TASK_ADDRESS = 0x0300597C
TASK_SHA256 = "2a3c4996119c428278a3270c6932d284443d8766ce7ce4bd8f6de166d0a3a47b"
EXPECTED_BUNDLE_SHA256 = {
    "baseline": "10b78ae7a78d886531b49b3d4810008f191bea11eadc62f364ad873bd79d636d",
    "palette": "9c40959228c19ea0bc32a2846b1986e05e944d76c34e7c23c4a576833e2b44bc",
    "component": "7c6c6331f8a41b5131d1201cdaf68b330bf625c0c8ad086640faf90426185a26",
    "timeline": "1ec398095b78fa0d3d7a8e953bc93db71555b1e0e67004a49c7d186f60634603",
}
EXPECTED_ROM_SHA256 = {
    "baseline": "2f738f390239caed48d12af99bd8d324df6c5465610c64fda8278c7f945e5db8",
    "palette": "7812e244b7dfe305c631695ac6dc5de774fbbff9bf6c8859a9364a2846483b61",
    "component": "3b8d46cf3e4a555a2928a019736d633624f0909a10c1cbe22510cce9c199e84b",
    "timeline": "f94dc6b6c44c964e0097787b4f5e70ea40ee0278479999faec20fd0059e203e8",
}
EXPECTED_SCREEN_SHA256 = {
    "baseline": "2a4d6f154b266fffc24bf683c2b90645443c0dabd08d588f1ed5c03ecc13c6a8",
    "palette": "fb87b6f625b6c54cc3995a6aade7762b874b3c7ad8c87336498d0b66b8049385",
    "component": "f7d69a56791304bfe6ebf6e85b80ac7d8c44ecdb7bdc1a55d964e56523b28a04",
    "timeline": "71a864632cb01c1cb3f75eb8d7057860a743469aec8de23f029fae0c8be57265",
}
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "VRAM": (0x06000000, 0x18000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "OAM": (0x07000000, 0x400),
}
EXPECTED_DOMAIN_SHA256 = {
    "baseline": {
        "EWRAM": "95ad6f8b448992d29ded38b85af5fe3306a5c1d1742eb6888ffd32b13b4a13cb",
        "VRAM": "7332e03f2f77d0de2999fc8e8862902b98fc3eb4128fcb210fdb6ffcf425cf3c",
        "IO": "231e1f87c0681f73223e68769d361ccf64a2028409e3c056a6931da2448adb30",
        "PRAM": "78c2600dad88cbb2e58e36e9e5d9577b0003e7219c432a54b981dfcee1a3c293",
        "OAM": "dbe5b301548d3902ac2186f53af6e3fa2d5d7a267b6276c4fb24fd3bd0feb81b",
    },
    "palette": {
        "EWRAM": "95ad6f8b448992d29ded38b85af5fe3306a5c1d1742eb6888ffd32b13b4a13cb",
        "VRAM": "7332e03f2f77d0de2999fc8e8862902b98fc3eb4128fcb210fdb6ffcf425cf3c",
        "IO": "231e1f87c0681f73223e68769d361ccf64a2028409e3c056a6931da2448adb30",
        "PRAM": "ff4c896bfe65bbec9afc9816675440d7693c605e378bfd7a05b89f6ee34cb03d",
        "OAM": "dbe5b301548d3902ac2186f53af6e3fa2d5d7a267b6276c4fb24fd3bd0feb81b",
    },
    "component": {
        "EWRAM": "95ad6f8b448992d29ded38b85af5fe3306a5c1d1742eb6888ffd32b13b4a13cb",
        "VRAM": "7332e03f2f77d0de2999fc8e8862902b98fc3eb4128fcb210fdb6ffcf425cf3c",
        "IO": "231e1f87c0681f73223e68769d361ccf64a2028409e3c056a6931da2448adb30",
        "PRAM": "78c2600dad88cbb2e58e36e9e5d9577b0003e7219c432a54b981dfcee1a3c293",
        "OAM": "cb943219e339d67f1f6ca1e5d498c8968f8f0ac216996c1d30369dcfcb1e7793",
    },
    "timeline": {
        "EWRAM": "95ad6f8b448992d29ded38b85af5fe3306a5c1d1742eb6888ffd32b13b4a13cb",
        "VRAM": "4f2da3cca707cc0ef00952e7b8c752443341a138f3d677b5cd7fece5a109bbd7",
        "IO": "231e1f87c0681f73223e68769d361ccf64a2028409e3c056a6931da2448adb30",
        "PRAM": "78c2600dad88cbb2e58e36e9e5d9577b0003e7219c432a54b981dfcee1a3c293",
        "OAM": "dbe5b301548d3902ac2186f53af6e3fa2d5d7a267b6276c4fb24fd3bd0feb81b",
    },
}
EXPECTED_PIXEL = {
    "palette": {"count": 268, "bbox": [109, 25, 131, 68], "sha256": "456a9d5a591de568a6771c16d2358f878e5b7b5e03acbfe5f93c893f17ddf67e"},
    "component": {"count": 634, "bbox": [108, 17, 134, 68], "sha256": "861e718d74fe212614cd35dae974733b46bcc7b6b199605e34b9c07ce11edf5f"},
    "timeline": {"count": 616, "bbox": [107, 17, 133, 65], "sha256": "beee67b769f57eb9f6265c80c5ddcc9baae47cb1f1b7db8d68b6bc22a7b76fd0"},
}
EXPECTED_PROVENANCE_SHA256 = {
    "baseline": {
        "audit.json": "d31723168d68686f178924574ff7376caa65a8430ad3b897b9cfb36e2b046288",
        "sentinel.json": "d31723168d68686f178924574ff7376caa65a8430ad3b897b9cfb36e2b046288",
        "guard.json": "a08b09e635ac9f7d71fddad1865790699acdc7884d5970ffca78413d0d17f6e0",
        "outer-guard.json": "f02df4d37c0071c21673f1bb439e21d5dc62bc015855f4ffb3bfa5f0dcfb635b",
    },
    "palette": {
        "audit.json": "42ae4d80dd956097c2b1135d8308bc455226de9d630905c26ddb6263f32074c5",
        "sentinel.json": "42ae4d80dd956097c2b1135d8308bc455226de9d630905c26ddb6263f32074c5",
        "guard.json": "788dd4d814a463e506c89941549b1ca67376733d66d2560614d87d562fee3d31",
        "outer-guard.json": "777948c750b4055b2c92f413f2ff8bfcf1845ee4982ff934901a83fc3587affa",
    },
    "component": {
        "audit.json": "d8b0db5fa733f5778d701d14b84f6d014d805c53918b0640bf9cbdaa00bbf996",
        "sentinel.json": "d8b0db5fa733f5778d701d14b84f6d014d805c53918b0640bf9cbdaa00bbf996",
        "guard.json": "d2b7331951ac5016bd8e05f07cc7370cc0b2e7740a167e8d610dd0115ef88716",
        "outer-guard.json": "869ae74699653ae70acff1ac92566999c855938ba4e7bcc4f146b1479b5c6753",
    },
    "timeline": {
        "audit.json": "1e81978df24fa7f34fd73247a66366002f5d57c716c952e2ffd98f52b7cffd69",
        "sentinel.json": "1e81978df24fa7f34fd73247a66366002f5d57c716c952e2ffd98f52b7cffd69",
        "guard.json": "b8dbceb9d0031e950661e9407c45b949acdc7c3d34900a9cd548ba064a5af5bb",
        "outer-guard.json": "3a9ccfce706d10de8940efdf74eb51f9b5f67ab8e6b402ef65922de6b08d58f9",
    },
}
EXPECTED_RUN_IDS = {
    "baseline": "1ca19cd45e6893e313c925461e078670",
    "palette": "6a7cbf5e18d680009d508d04d0362342",
    "component": "654392940a7c2432364af512b698e407",
    "timeline": "be76febd040635bb3216af1a323356c9",
}
IMPLEMENTATION_PATHS = (
    "tools/build_character_battle_visual_resource_matrix.py",
    "tools/export_character_battle_visual_resource_matrix_evidence.py",
    "tools/verify_character_battle_visual_resource_matrix_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_character_battle_visual_resource_matrix.py",
    "tests/test_character_battle_visual_resource_matrix_evidence.py",
)
VARIANT_FILES = (
    "bundle.bin",
    "frame80.ss9",
    "frame80.png",
    "audit.json",
    "sentinel.json",
    "guard.json",
    "outer-guard.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("runtime domains have different lengths")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _pixel_changes(left_path: Path, right_path: Path) -> list[list[Any]]:
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != (240, 160) or right.size != left.size:
        raise ValueError("runtime screenshots are not 240x160 RGB")
    return [
        [x, y, list(left.getpixel((x, y))), list(right.getpixel((x, y)))]
        for y in range(160)
        for x in range(240)
        if left.getpixel((x, y)) != right.getpixel((x, y))
    ]


def _pixel_summary(changes: list[list[Any]]) -> dict[str, Any]:
    return {
        "count": len(changes),
        "bbox": [
            min(row[0] for row in changes),
            min(row[1] for row in changes),
            max(row[0] for row in changes),
            max(row[1] for row in changes),
        ],
        "sha256": _digest(json.dumps(changes, separators=(",", ":")).encode()),
    }


def _expected_files() -> set[str]:
    return {"build-manifest.json", "runtime-evidence.json"} | {
        f"{variant}/{name}" for variant in VARIANTS for name in VARIANT_FILES
    }


def _scope() -> dict[str, bool]:
    return {
        "natural_entry": True,
        "resource_0_relocated_bundle_route_verified": True,
        "resource_0_palette_pixel_ab": True,
        "resource_0_component_geometry_pixel_ab": True,
        "resource_0_timeline_frame_selection_pixel_ab": True,
        "all_250_resources_runtime_verified": False,
        "all_character_slots_runtime_verified": False,
        "full_animation_timing_verified": False,
        "camera_blend_transform_verified": False,
        "physical_gba_verified": False,
    }


def _result(
    errors: list[str],
    memory_differences: dict[str, dict[str, list[int]]],
    pixel_counts: dict[str, int],
    selected_frames: dict[str, int],
) -> dict[str, Any]:
    return {
        "verified": not errors,
        "errors": errors,
        "memory_differences": memory_differences,
        "pixel_change_counts": pixel_counts,
        "selected_frame_ids": selected_frames,
    }


def _validate_build(build: dict[str, Any], bundles: dict[str, bytes], base: bytes) -> list[str]:
    errors: list[str] = []
    expected_edits = {
        "palette": {"bundle_local_offset": 2, "before_hex": "84", "after_hex": "85", "palette_index": 1},
        "component": {"bundle_local_offset": 0x486C, "before_hex": "f0", "after_hex": "f1", "frame_id": 3, "component_index": 0, "field": "x", "before": -16, "after": -15},
        "timeline": {"bundle_local_offset": 0x4A64, "before_hex": "03", "after_hex": "04", "animation_id": 1, "keyframe_index": 0, "field": "frame_id", "before": 3, "after": 4},
    }
    expected_resource = {"resource_id": 0, "character_id": 1, "visual_slot": 0, "slot_rows": [0], "frame_id": 3, "component_index": 0, "animation_id": 1, "keyframe_index": 0}
    expected_runtime = {
        "input_checkpoint": INPUT_STATE.as_posix(),
        "input": EVENT,
        "capture_frame": 80,
        "baseline_active_task": {"task_address": "0x0300597C", "animation_id": 1, "keyframe_index": 0, "frame_id": 3},
    }
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("base_rom_sha256") != BASE_ROM_SHA256
        or build.get("resource") != expected_resource
        or build.get("edits") != expected_edits
        or build.get("runtime_contract") != expected_runtime
        or build.get("isolation") != {
            "shared_patch_topology": True,
            "single_byte_candidates": True,
            "rom_difference_offsets": {"palette": [0x600002], "component": [0x60486C], "timeline": [0x604A64]},
            "independent_runtime_required": True,
        }
        or set(build.get("variants", {})) != set(VARIANTS)
    ):
        errors.append("build manifest contract mismatch")
        return errors

    common_pointers = {
        "animation_pointer_table": "0x08604B30",
        "component_region": "0x08604820",
        "frame_pointer_table": "0x08604A00",
        "graphics": "0x08600020",
        "palette": "0x08600000",
        "timeline_region": "0x08604A50",
    }
    expanded = base + bytes([0xFF]) * (0x1000000 - len(base))
    for variant in VARIANTS:
        row = build["variants"].get(variant, {})
        ledger = row.get("patch_ledger", [])
        expected_palette_sha = "8fab9afb53a8e291874b960327f54aa9655e1f3da59384ef0ab42b0bed3471ef" if variant == "palette" else "5ed6559b7dbaee0832ff46c3961fd0e60ed89c6c9db5dd945d1135aa2dc52916"
        if (
            row.get("rom_path") != f"{variant}/{variant}.gba"
            or row.get("spec_path") != f"{variant}/spec.json"
            or row.get("rom_size") != 0x1000000
            or row.get("rom_sha256") != EXPECTED_ROM_SHA256[variant]
            or row.get("graphics_sha256") != "00604b6d454b23f73413ec7d65cebead033c7a6177f3e8da9861fb32f44db3ec"
            or row.get("palette_sha256") != expected_palette_sha
            or len(ledger) != 2
        ):
            errors.append(f"build manifest {variant} variant mismatch")
            continue
        allocation, descriptor = ledger
        if (
            allocation.get("id") != f"resource-000-visual-matrix-{variant}.bundle"
            or allocation.get("kind") != "allocation"
            or allocation.get("offset") != BUNDLE_OFFSET
            or allocation.get("size") != BUNDLE_SIZE
            or allocation.get("resource_id") != 0
            or allocation.get("slot_row") is not None
            or allocation.get("allocation") != {"owner": "character_battle_visuals", "partition": "character-battle-visual-bundles"}
            or allocation.get("new_pointers") != common_pointers
            or allocation.get("after_sha256") != EXPECTED_BUNDLE_SHA256[variant]
            or descriptor.get("id") != f"resource-000-visual-matrix-{variant}.descriptor-row-0"
            or descriptor.get("kind") != "descriptor"
            or descriptor.get("offset") != DESCRIPTOR_OFFSET
            or descriptor.get("size") != 16
            or descriptor.get("resource_id") != 0
            or descriptor.get("slot_row") != 0
            or descriptor.get("allocation") is not None
            or descriptor.get("new_pointers") != common_pointers
        ):
            errors.append(f"build manifest {variant} patch ledger mismatch")
        rom = bytearray(expanded)
        rom[BUNDLE_OFFSET : BUNDLE_OFFSET + BUNDLE_SIZE] = bundles[variant]
        rom[DESCRIPTOR_OFFSET : DESCRIPTOR_OFFSET + 16] = DESCRIPTOR
        if _digest(bytes(rom)) != EXPECTED_ROM_SHA256[variant]:
            errors.append(f"{variant} bundle cannot reconstruct the declared ROM")
    return errors


def _validate_bundle_contract(bundles: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    baseline = bundles["baseline"]
    expected = {"palette": (2, 0x84, 0x85), "component": (0x486C, 0xF0, 0xF1), "timeline": (0x4A64, 0x03, 0x04)}
    for variant, payload in bundles.items():
        if len(payload) != BUNDLE_SIZE or _digest(payload) != EXPECTED_BUNDLE_SHA256[variant]:
            errors.append(f"{variant} bundle identity mismatch")
    for variant, (offset, before, after) in expected.items():
        differences = _diff(baseline, bundles[variant])
        if differences != [offset] or baseline[offset] != before or bundles[variant][offset] != after:
            errors.append(f"{variant} bundle single-factor mismatch")
    return errors


def _validate_provenance(artifact: Path, build: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    rows: dict[str, dict[str, Any]] = {}
    run_ids: list[str] = []
    child_pids: list[int] = []
    outer_child_pids: list[int] = []
    for variant in VARIANTS:
        if any(
            _sha256(artifact / variant / name)
            != EXPECTED_PROVENANCE_SHA256[variant][name]
            for name in EXPECTED_PROVENANCE_SHA256[variant]
        ):
            errors.append(f"{variant} runtime provenance raw identity mismatch")
        audit = _read_json(artifact / variant / "audit.json")
        sentinel = _read_json(artifact / variant / "sentinel.json")
        guard = _read_json(artifact / variant / "guard.json")
        outer = _read_json(artifact / variant / "outer-guard.json")
        if audit != sentinel:
            errors.append(f"{variant} runtime provenance audit/sentinel mismatch")
        expected_rom = EXPECTED_ROM_SHA256[variant]
        if (
            audit.get("frame") != 80
            or audit.get("capture_frame") != 80
            or audit.get("inputs") != [EVENT]
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("input_state_sha256") != INPUT_STATE_SHA256
            or audit.get("rom_sha256") != expected_rom
            or audit.get("staged_rom_sha256") != expected_rom
            or audit.get("binary_sha256") != MGBA_SHA256
            or audit.get("build_manifest_sha256") != MGBA_BUILD_MANIFEST_SHA256
            or audit.get("replay_script_sha256") != REPLAY_SHA256
            or audit.get("guard_summary_sha256") != _sha256(artifact / variant / "guard.json")
            or audit.get("status") != "capture-complete"
            or audit.get("success") is not True
            or audit.get("evidence_mode") != "single-input"
            or audit.get("zero_input_verified") is not False
            or audit.get("patch_sha256") != "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6"
            or audit.get("output_state_sha256") != _sha256(artifact / variant / "frame80.ss9")
            or audit.get("output_png_sha256") != _sha256(artifact / variant / "frame80.png")
            or audit.get("pgid_clean") is not True
            or audit.get("runtime_residue", {}).get("pgid_clean") is not True
            or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
            or audit.get("runtime_residue", {}).get("pgid_matching_rows") != []
            or audit.get("runtime_residue", {}).get("mgba_listener_rows") != []
        ):
            errors.append(f"{variant} runtime provenance audit mismatch")
        command = guard.get("command", [])
        child_pid = guard.get("child_pid")
        if (
            guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
            or guard.get("protection_backend") != "posix-process-group"
            or guard.get("completion_trigger") != "success-marker"
            or not isinstance(command, list)
            or len(command) != 4
            or command[1] != "--script"
            or not str(command[3]).endswith(f"/{variant}/staged.gba")
            or not Path(command[0]).is_file()
            or _sha256(Path(command[0])) != MGBA_SHA256
            or not Path(command[2]).is_file()
            or _sha256(Path(command[2])) != REPLAY_SHA256
            or not isinstance(child_pid, int)
            or child_pid <= 1
            or audit.get("child_pgid") != child_pid
            or audit.get("peak_tree_rss_mib") != guard.get("peak_tree_rss_mib")
        ):
            errors.append(f"{variant} runtime provenance guard mismatch")
        outer_command = outer.get("command", [])
        outer_options = {}
        if isinstance(outer_command, list) and len(outer_command) >= 2 and len(outer_command[2:]) % 2 == 0:
            keys = outer_command[2::2]
            values = outer_command[3::2]
            if all(isinstance(key, str) and key.startswith("--") for key in keys) and len(set(keys)) == len(keys):
                outer_options = dict(zip(keys, values))
        expected_outer_options = {
            "--binary": guard.get("command", [None])[0] if isinstance(guard.get("command"), list) and guard.get("command") else None,
            "--build-manifest": audit.get("build_manifest"),
            "--expected-build-manifest-sha256": MGBA_BUILD_MANIFEST_SHA256,
            "--expected-binary-sha256": MGBA_SHA256,
            "--rom": f"build/experiments/active/character-battle-visual-resource-matrix/character-battle-visual-resource-matrix-20260801-r1/build/{variant}/{variant}.gba",
            "--state": INPUT_STATE.as_posix(),
            "--expected-rom-sha256": expected_rom,
            "--expected-state-sha256": INPUT_STATE_SHA256,
            "--key": "A",
            "--down-frame": "5",
            "--up-frame": "13",
            "--capture-frame": "80",
            "--staged-rom": f"build/experiments/active/character-battle-visual-resource-matrix/character-battle-visual-resource-matrix-20260801-r1/runtime/{variant}/staged.gba",
            "--output-state": f"build/experiments/active/character-battle-visual-resource-matrix/character-battle-visual-resource-matrix-20260801-r1/runtime/{variant}/frame80.ss9",
            "--output-png": f"build/experiments/active/character-battle-visual-resource-matrix/character-battle-visual-resource-matrix-20260801-r1/runtime/{variant}/frame80.png",
            "--audit": f"build/experiments/active/character-battle-visual-resource-matrix/character-battle-visual-resource-matrix-20260801-r1/runtime/{variant}/audit.json",
            "--sentinel": f"build/experiments/active/character-battle-visual-resource-matrix/character-battle-visual-resource-matrix-20260801-r1/runtime/{variant}/sentinel.json",
            "--guard-summary": f"build/experiments/active/character-battle-visual-resource-matrix/character-battle-visual-resource-matrix-20260801-r1/runtime/{variant}/guard.json",
            "--wall-timeout-s": "120",
            "--idle-timeout-s": "30",
        }
        outer_child_pid = outer.get("child_pid")
        if (
            outer.get("reason") != "completed"
            or outer.get("exit_code") != 0
            or outer.get("degraded") is not False
            or outer.get("protection_backend") != "posix-process-group"
            or not isinstance(outer_command, list)
            or outer_command[:2] != ["python3", "tools/run_macos_mgba_single_input.py"]
            or outer_options != expected_outer_options
            or not isinstance(outer_child_pid, int)
            or outer_child_pid <= 1
        ):
            errors.append(f"{variant} runtime provenance outer guard mismatch")
        run_id = audit.get("run_id")
        if run_id != EXPECTED_RUN_IDS[variant]:
            errors.append(f"{variant} runtime provenance run ID mismatch")
        if isinstance(run_id, str):
            run_ids.append(run_id)
        if isinstance(child_pid, int):
            child_pids.append(child_pid)
        if isinstance(outer_child_pid, int):
            outer_child_pids.append(outer_child_pid)
        rows[variant] = {"audit": audit, "guard": guard, "outer_guard": outer}
    if len(set(run_ids)) != len(VARIANTS):
        errors.append("runtime provenance runs are not independent")
    if len(set(child_pids)) != len(VARIANTS) or len(set(outer_child_pids)) != len(VARIANTS):
        errors.append("runtime provenance child process identities are not independent")
    return errors, rows


def verify(root: Path, artifact: Path) -> dict[str, Any]:
    """Return a deterministic verification report without trusting the exporter."""

    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    errors: list[str] = []
    memory_differences: dict[str, dict[str, list[int]]] = {}
    pixel_counts: dict[str, int] = {}
    selected_frames: dict[str, int] = {}
    try:
        if not (root / INPUT_STATE).is_file() or _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
            errors.append("input checkpoint identity mismatch")
        base_path = root / "rom/base.gba"
        if not base_path.is_file() or _sha256(base_path) != BASE_ROM_SHA256:
            errors.append("base ROM identity mismatch")
            base = b""
        else:
            base = base_path.read_bytes()

        manifest = _read_json(artifact / "manifest.json")
        actual_paths = set()
        for path in artifact.rglob("*"):
            if path.is_symlink():
                errors.append("artifact contains a symbolic link")
            elif path.is_file() and path.name != "manifest.json":
                actual_paths.add(path.relative_to(artifact).as_posix())
        expected_paths = _expected_files()
        if actual_paths != expected_paths or set(manifest.get("files", {})) != expected_paths:
            errors.append("promotion manifest file inventory mismatch")
        for relative in sorted(actual_paths & set(manifest.get("files", {}))):
            if _sha256(artifact / relative) != manifest["files"][relative]:
                errors.append(f"file hash mismatch: {relative}")

        bundles = {variant: (artifact / variant / "bundle.bin").read_bytes() for variant in VARIANTS}
        errors.extend(_validate_bundle_contract(bundles))
        build = _read_json(artifact / "build-manifest.json")
        errors.extend(_validate_build(build, bundles, base))
        provenance_errors, provenance = _validate_provenance(artifact, build)
        errors.extend(provenance_errors)

        states = {variant: load_gba_state(artifact / variant / "frame80.ss9") for variant in VARIANTS}
        for variant, state in states.items():
            if state.read_memory(0x0201BE28, 4) != bytes.fromhex("242c0916"):
                errors.append(f"{variant} runtime did not reach battle 41")
            embedded = png_screen_fingerprint(artifact / variant / "frame80.ss9")
            external = png_screen_fingerprint(artifact / variant / "frame80.png")
            if embedded != external or external.get("rgb_pixels_sha256") != EXPECTED_SCREEN_SHA256[variant]:
                errors.append(f"{variant} screenshot/state mismatch")
            for label, (address, size) in DOMAINS.items():
                if _digest(state.read_memory(address, size)) != EXPECTED_DOMAIN_SHA256[variant][label]:
                    errors.append(f"{variant} runtime domain identity mismatch: {label}")

        baseline = states["baseline"]
        for variant in VARIANTS[1:]:
            changed = {}
            for label, (address, size) in DOMAINS.items():
                offsets = _diff(baseline.read_memory(address, size), states[variant].read_memory(address, size))
                if offsets:
                    changed[label] = offsets
            memory_differences[variant] = changed
        if memory_differences.get("palette") != {"PRAM": [0x202]}:
            errors.append("palette runtime domain isolation mismatch")
        if memory_differences.get("component") != {"OAM": [2]}:
            errors.append("component runtime domain isolation mismatch")
        timeline_offsets = memory_differences.get("timeline", {}).get("VRAM", [])
        if set(memory_differences.get("timeline", {})) != {"VRAM"} or len(timeline_offsets) != 394:
            errors.append("timeline runtime domain isolation mismatch")

        for variant, state in states.items():
            task = state.read_memory(TASK_ADDRESS, 0x3C)
            animation_id, keyframe_index, hold_timer = struct.unpack_from("<HHH", task, 0x14)
            expected_frame = 4 if variant == "timeline" else 3
            frame_table_pointer, animation_table_pointer, graphics_pointer = struct.unpack_from("<III", task, 0x1C)
            animation_entry_local = animation_table_pointer - 0x08600000 + animation_id * 4
            try:
                timeline_pointer = struct.unpack_from("<I", bundles[variant], animation_entry_local)[0]
                keyframe_local = timeline_pointer - 0x08600000 + keyframe_index * 4
                frame_id, hold_frames = struct.unpack_from("<HH", bundles[variant], keyframe_local)
            except struct.error:
                timeline_pointer = 0
                frame_id = -1
                hold_frames = -1
            selected_frames[variant] = frame_id
            if (
                _digest(task) != TASK_SHA256
                or animation_id != 1
                or keyframe_index != 0
                or hold_timer != 0
                or (frame_table_pointer, animation_table_pointer, graphics_pointer)
                != (0x08604A00, 0x08604B30, 0x08600020)
            ):
                errors.append(f"{variant} task identity contract mismatch")
            if timeline_pointer != 0x08604A64 or frame_id != expected_frame or hold_frames != 8:
                errors.append(f"{variant} animation selection contract mismatch")
            frame_pointer = struct.unpack_from(
                "<I", bundles[variant], frame_table_pointer - 0x08600000 + frame_id * 4
            )[0]
            frame_local = frame_pointer - 0x08600000
            tile_offset = struct.unpack_from("<H", bundles[variant], frame_local)[0]
            component_x = struct.unpack_from("<h", bundles[variant], frame_local + 4)[0]
            expected_tile = 128 if variant == "timeline" else 96
            expected_x = -15 if variant == "component" else -16
            source = bundles[variant][0x20 + tile_offset * 32 : 0x20 + (tile_offset + 32) * 32]
            dynamic = state.read_memory(0x06010000, 1024)
            if tile_offset != expected_tile or component_x != expected_x or len(source) != 1024 or source != dynamic:
                errors.append(f"{variant} runtime dynamic OBJ source mismatch")

        expected_oam = {"baseline": "088068c00008e300", "palette": "088068c00008e300", "component": "088069c00008e300", "timeline": "088068c00008e300"}
        for variant, state in states.items():
            if state.read_memory(0x07000000, 8).hex() != expected_oam[variant]:
                errors.append(f"{variant} runtime OAM contract mismatch")
        if states["palette"].read_memory(0x05000202, 2) != bytes.fromhex("8510"):
            errors.append("palette runtime palette value mismatch")
        if states["baseline"].read_memory(0x05000202, 2) != bytes.fromhex("8410"):
            errors.append("baseline runtime palette value mismatch")

        pixel_summaries: dict[str, dict[str, Any]] = {}
        for variant in VARIANTS[1:]:
            changes = _pixel_changes(artifact / "baseline/frame80.png", artifact / variant / "frame80.png")
            summary = _pixel_summary(changes)
            pixel_summaries[variant] = summary
            pixel_counts[variant] = summary["count"]
            if summary != EXPECTED_PIXEL[variant]:
                errors.append(f"{variant} final pixel contract mismatch")
        palette_changes = _pixel_changes(artifact / "baseline/frame80.png", artifact / "palette/frame80.png")
        if any(row[2:] != [[33, 33, 33], [41, 33, 33]] for row in palette_changes):
            errors.append("palette final pixel color mismatch")

        evidence = _read_json(artifact / "runtime-evidence.json")
        expected_evidence = {
            "schema": SCHEMA,
            "input": {"path": INPUT_STATE.as_posix(), "sha256": INPUT_STATE_SHA256, "event": EVENT, "loader_state": "pre-map-load-zero-runtime"},
            "source": {"resource_id": 0, "character_id": 1, "visual_slot": 0, "animation_id": 1, "keyframe_index": 0, "baseline_frame_id": 3, "timeline_frame_id": 4},
            "runtime": {
                variant: {
                    "memory_differences": memory_differences[variant],
                    "pixel_change_count": pixel_counts[variant],
                    "pixel_bbox": pixel_summaries[variant]["bbox"],
                    "pixel_changes_sha256": pixel_summaries[variant]["sha256"],
                    "selected_frame_id": selected_frames[variant],
                }
                for variant in VARIANTS[1:]
            },
            "domain_sha256": EXPECTED_DOMAIN_SHA256,
            "provenance": {"mgba_sha256": MGBA_SHA256, "mgba_build_manifest_sha256": MGBA_BUILD_MANIFEST_SHA256, "replay_script_sha256": REPLAY_SHA256},
            "runs": {
                variant: {
                    "run_id": provenance[variant]["audit"].get("run_id"),
                    "rom_sha256": EXPECTED_ROM_SHA256[variant],
                    "peak_tree_rss_mib": provenance[variant]["guard"].get("peak_tree_rss_mib"),
                    "outer_peak_tree_rss_mib": provenance[variant]["outer_guard"].get("peak_tree_rss_mib"),
                    "guard_reason": "completed",
                }
                for variant in VARIANTS
            },
        }
        if evidence != expected_evidence:
            errors.append("runtime evidence pixel/provenance contract mismatch")
        if manifest.get("payload_file") != "runtime-evidence.json" or manifest.get("payload_sha256") != _sha256(artifact / "runtime-evidence.json"):
            errors.append("promotion manifest payload mismatch")

        clean_result = _result([], memory_differences, pixel_counts, selected_frames)
        expected_command = ["python3", "tools/verify_character_battle_visual_resource_matrix_evidence.py", "--root", ".", "--artifact", f"artifacts/{ARTIFACT_ID}"]
        expected_implementation = {path: _sha256(root / path) for path in IMPLEMENTATION_PATHS if (root / path).is_file()}
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_id") != ARTIFACT_ID
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("parent") != {"path": INPUT_STATE.as_posix(), "sha256": INPUT_STATE_SHA256}
            or manifest.get("scope") != _scope()
            or manifest.get("implementation_sha256") != expected_implementation
            or manifest.get("verifier") != {"command": expected_command, "exit_code": 0, "result": clean_result}
        ):
            errors.append("promotion manifest contract mismatch")
    except Exception as error:  # keep verifier failures machine-readable
        errors.append(f"verification exception: {error}")
    return _result(errors, memory_differences, pixel_counts, selected_frames)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.root, args.artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
