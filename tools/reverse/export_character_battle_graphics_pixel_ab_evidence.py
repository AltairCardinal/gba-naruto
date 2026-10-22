#!/usr/bin/env python3
"""Export the natural character-battle graphics modified-ROM pixel A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "character-battle-graphics-pixel-ab-v1"
ARTIFACT_ID = "character-battle-graphics-pixel-ab-v1"
BUILD_SCHEMA = "character-battle-graphics-pixel-ab-build-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
VARIANTS = ("baseline", "candidate")
EVENT = {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
BUNDLE_OFFSET = 0x600000
BUNDLE_SIZE = 0x4B60
MGBA_SHA256 = "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
REPLAY_SHA256 = "28965f8610bdb9e6669ac4c4b787c7e6d1e16cc1e259d6446150f306a382703d"
VARIANT_FILES = (
    "frame80.ss9",
    "frame80.png",
    "audit.json",
    "sentinel.json",
    "guard.json",
)
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "VRAM": (0x06000000, 0x18000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "OAM": (0x07000000, 0x400),
}
IMPLEMENTATION_PATHS = (
    "tools/build_character_battle_graphics_pixel_ab.py",
    "tools/export_character_battle_graphics_pixel_ab_evidence.py",
    "tools/verify_character_battle_graphics_pixel_ab_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_character_battle_graphics_pixel_ab.py",
    "tests/test_character_battle_graphics_pixel_ab_evidence.py",
)


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


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("character graphics A/B domains have different lengths")
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def _pixel_changes(left_path: Path, right_path: Path) -> list[list[Any]]:
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != (240, 160) or right.size != left.size:
        raise ValueError("character graphics A/B screenshots are not 240x160 RGB")
    return [
        [x, y, list(left.getpixel((x, y))), list(right.getpixel((x, y)))]
        for y in range(160)
        for x in range(240)
        if left.getpixel((x, y)) != right.getpixel((x, y))
    ]


def _rgb555(value: int) -> list[int]:
    return [
        ((value >> shift) & 31) << 3 | ((value >> shift) & 31) >> 2
        for shift in (0, 5, 10)
    ]


def _text_bg_sample(state: Any, bg: int, x: int, y: int) -> dict[str, Any]:
    io = state.read_memory(0x04000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    pram = state.read_memory(0x05000000, 0x400)
    control = struct.unpack_from("<H", io, 8 + bg * 2)[0]
    scroll_x = struct.unpack_from("<H", io, 0x10 + bg * 4)[0] & 0x1FF
    scroll_y = struct.unpack_from("<H", io, 0x12 + bg * 4)[0] & 0x1FF
    size = (control >> 14) & 3
    width = 512 if size in (1, 3) else 256
    height = 512 if size in (2, 3) else 256
    world_x = (x + scroll_x) % width
    world_y = (y + scroll_y) % height
    blocks_x = width // 256
    screen_base = ((control >> 8) & 31) * 0x800
    screen_base += ((world_y // 256) * blocks_x + world_x // 256) * 0x800
    entry = struct.unpack_from(
        "<H",
        vram,
        screen_base
        + (((world_y & 255) // 8) * 32 + (world_x & 255) // 8) * 2,
    )[0]
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
        "rgb": _rgb555(color),
    }


def _obj_oracle(state: Any) -> dict[str, Any]:
    io = state.read_memory(0x04000000, 0x400)
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    attr0, attr1, attr2 = struct.unpack(
        "<3H", state.read_memory(0x07000000, 6)
    )
    local_x, local_y = 13, 17
    tile = (attr2 & 0x03FF) + (local_y // 8) * 4 + local_x // 8
    address = 0x06010000 + tile * 32 + (local_y & 7) * 4 + (local_x & 7) // 2
    packed = state.read_memory(address, 1)[0]
    palette_index = (packed >> 4) & 15
    palette_bank = (attr2 >> 12) & 15
    color = struct.unpack(
        "<H",
        state.read_memory(
            0x05000200 + (palette_bank * 16 + palette_index) * 2,
            2,
        ),
    )[0]
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
        "rgb": _rgb555(color),
        "backgrounds": {
            f"BG{bg}": _text_bg_sample(state, bg, 117, 25)
            for bg in range(4)
            if dispcnt & (1 << (8 + bg))
        },
    }


def _validate_build(build: dict[str, Any]) -> None:
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("base_rom_sha256") != ROM_SHA256
        or build.get("resource", {}).get("resource_id") != 0
        or build.get("resource", {}).get("source_frame_id") != 3
        or build.get("resource", {}).get("source_component_index") != 0
        or build.get("edit")
        != {
            "graphics_byte_offset": 0xD26,
            "before_hex": "12",
            "after_hex": "42",
            "source_pixel": [13, 17],
            "expected_screen_pixel": [117, 25],
            "before_palette_index": 1,
            "after_palette_index": 4,
        }
        or build.get("isolation", {}).get("rom_difference_offsets") != [0x600D46]
        or build.get("isolation", {}).get("shared_patch_topology") is not True
        or build.get("isolation", {}).get("single_graphics_byte_difference") is not True
        or set(build.get("variants", {})) != set(VARIANTS)
    ):
        raise ValueError("character graphics pixel A/B build contract mismatch")


def export(root: Path, run_dir: Path, output: Path) -> dict[str, Any]:
    """Copy the minimal raw evidence, bind it, and run the independent verifier."""

    root = Path(root).resolve()
    run_dir = Path(run_dir).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("character graphics pixel A/B output already exists")
    if _sha256(root / "rom/base.gba") != ROM_SHA256:
        raise ValueError("character graphics pixel A/B base ROM identity mismatch")
    if _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
        raise ValueError("character graphics pixel A/B input checkpoint mismatch")

    build_path = run_dir / "build/build-manifest.json"
    build = _read_json(build_path)
    _validate_build(build)
    output.mkdir(parents=True)
    shutil.copy2(build_path, output / "build-manifest.json")

    states = {}
    audits = {}
    guards = {}
    run_ids = []
    for variant in VARIANTS:
        source = run_dir / "runtime" / variant
        target = output / variant
        target.mkdir()
        staged = source / "staged.gba"
        if staged.stat().st_size != 0x1000000:
            raise ValueError(f"{variant} staged ROM size mismatch")
        if _sha256(staged) != build["variants"][variant]["rom_sha256"]:
            raise ValueError(f"{variant} staged ROM hash mismatch")
        with staged.open("rb") as rom:
            rom.seek(BUNDLE_OFFSET)
            bundle = rom.read(BUNDLE_SIZE)
        (target / "bundle.bin").write_bytes(bundle)
        for name in VARIANT_FILES:
            path = source / name
            if not path.is_file():
                raise ValueError(f"missing character graphics runtime file: {path}")
            shutil.copy2(path, target / name)

        audit = _read_json(target / "audit.json")
        sentinel = _read_json(target / "sentinel.json")
        guard = _read_json(target / "guard.json")
        if audit != sentinel:
            raise ValueError(f"{variant} audit and sentinel differ")
        if (
            audit.get("frame") != 80
            or audit.get("inputs") != [EVENT]
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("input_state_sha256") != INPUT_STATE_SHA256
            or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        ):
            raise ValueError(f"{variant} replay audit mismatch")
        if (
            guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
            or guard.get("protection_backend") != "posix-process-group"
            or guard.get("completion_trigger") != "success-marker"
        ):
            raise ValueError(f"{variant} resource guard mismatch")
        if (
            png_screen_fingerprint(target / "frame80.ss9")
            != png_screen_fingerprint(target / "frame80.png")
        ):
            raise ValueError(f"{variant} screenshot is not bound to the savestate")
        states[variant] = load_gba_state(target / "frame80.ss9")
        audits[variant] = audit
        guards[variant] = guard
        run_ids.append(audit.get("run_id"))

    if len(set(run_ids)) != 2 or any(not isinstance(value, str) for value in run_ids):
        raise ValueError("character graphics runtime runs are not independent")
    for variant in VARIANTS:
        command = guards[variant].get("command", [])
        if (
            not isinstance(command, list)
            or len(command) != 4
            or not Path(command[0]).is_file()
            or _sha256(Path(command[0])) != MGBA_SHA256
            or command[1] != "--script"
            or _sha256(Path(command[2])) != REPLAY_SHA256
            or not str(command[3]).endswith(f"/{variant}/staged.gba")
        ):
            raise ValueError(f"{variant} runtime tool provenance mismatch")

    memory_differences = {}
    for label, (address, size) in DOMAINS.items():
        changed = _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        if changed:
            memory_differences[label] = changed
    if memory_differences != {"VRAM": [0x10126]}:
        raise ValueError("character graphics runtime domain isolation mismatch")
    pixels = _pixel_changes(
        output / "baseline/frame80.png",
        output / "candidate/frame80.png",
    )
    if pixels != [[117, 25, [33, 33, 33], [255, 0, 0]]]:
        raise ValueError("character graphics final pixel contract mismatch")
    obj_oracles = {
        variant: _obj_oracle(state) for variant, state in states.items()
    }
    if (
        obj_oracles["baseline"]["source_address"] != "0x06010126"
        or obj_oracles["baseline"]["palette_index"] != 1
        or obj_oracles["baseline"]["rgb"] != [33, 33, 33]
        or obj_oracles["candidate"]["palette_index"] != 4
        or obj_oracles["candidate"]["rgb"] != [255, 0, 0]
        or any(
            oracle["dispcnt"] != 0x1940
            or oracle["obj_1d_mapping"] is not True
            or oracle["obj_enabled"] is not True
            or oracle["windows_enabled"] is not False
            or oracle["backgrounds"].get("BG3", {}).get("palette_index") != 0
            for oracle in obj_oracles.values()
        )
    ):
        raise ValueError("character graphics OBJ composition oracle mismatch")

    evidence = {
        "schema": SCHEMA,
        "input": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "event": EVENT,
            "loader_state": "pre-map-load-zero-runtime",
        },
        "source": {
            "resource_id": 0,
            "character_id": 1,
            "visual_slot": 0,
            "frame_id": 3,
            "component_index": 0,
            "graphics_byte_offset": 0xD26,
            "source_pixel": [13, 17],
            "palette_index_change": [1, 4],
        },
        "runtime": {
            "battle_id": 41,
            "resource_id": 0,
            "frame_id": 3,
            "capture_frame": 80,
            "oam0_hex": "088068c00008e300",
            "memory_differences": memory_differences,
            "pixel_changes": pixels,
            "obj_oracles": obj_oracles,
        },
        "provenance": {
            "mgba_sha256": MGBA_SHA256,
            "replay_script_sha256": REPLAY_SHA256,
        },
        "runs": {
            variant: {
                "run_id": audits[variant]["run_id"],
                "rom_sha256": audits[variant]["rom_sha256"],
                "peak_tree_rss_mib": guards[variant]["peak_tree_rss_mib"],
                "guard_reason": guards[variant]["reason"],
            }
            for variant in VARIANTS
        },
    }
    _write_json(output / "runtime-evidence.json", evidence)

    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "artifact_status": "accepted",
        "parent": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
        },
        "scope": {
            "natural_entry": True,
            "character_resource_0_frame_3_graphics_pixel_ab": True,
            "relocated_bundle_runtime_verified": True,
            "all_250_resources_runtime_verified": False,
            "all_character_slots_runtime_verified": False,
            "camera_blend_transform_verified": False,
            "physical_gba_verified": False,
        },
        "implementation_sha256": {
            path: _sha256(root / path) for path in IMPLEMENTATION_PATHS
        },
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256(output / "runtime-evidence.json"),
        "files": {},
        "verifier": {
            "command": [
                "python3",
                "tools/verify_character_battle_graphics_pixel_ab_evidence.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
            "result": {
                "verified": True,
                "errors": [],
                "resource_id": 0,
                "frame_id": 3,
                "memory_differences": {"VRAM": [0x10126]},
                "pixel_changes": [
                    [117, 25, [33, 33, 33], [255, 0, 0]]
                ],
            },
        },
    }
    manifest["files"] = {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    _write_json(output / "manifest.json", manifest)

    try:
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify
    except ModuleNotFoundError:
        from verify_character_battle_graphics_pixel_ab_evidence import verify
    report = verify(root, output)
    manifest["verifier"]["result"] = report
    manifest["verifier"]["exit_code"] = 0 if report["verified"] else 1
    _write_json(output / "manifest.json", manifest)
    if not report["verified"]:
        raise ValueError(f"character graphics independent verifier failed: {report['errors']}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.root, args.run_dir, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
