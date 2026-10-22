#!/usr/bin/env python3
"""Independently verify the ROM expansion profile and runtime evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

try:
    from tools.inspect_mgba_savestate import (
        load_gba_state,
        png_screen_fingerprint,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value: object) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _branch_target(instruction: int, address: int) -> int:
    if instruction & 0xFF000000 != 0xEA000000:
        raise ValueError(f"entry 0x{instruction:08X} is not ARM B")
    displacement = instruction & 0xFFFFFF
    if displacement & 0x800000:
        displacement -= 0x1000000
    return address + 8 + displacement * 4


def _arm_branch(address: int, target: int) -> bytes:
    displacement = (target - address - 8) // 4
    return struct.pack("<I", 0xEA000000 | (displacement & 0xFFFFFF))


def verify_profile(root: Path, manifest_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    promotion = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = manifest_path.parent
    payload_name = "profile.json"
    payload_path = artifact / payload_name
    manifest = json.loads(payload_path.read_text(encoding="utf-8"))
    payload_digest = _sha256(payload_path)
    actual_files = {
        path.relative_to(artifact).as_posix(): _sha256(path)
        for path in artifact.rglob("*")
        if path.is_file() and path != manifest_path
    }
    expected_command = [
        "python3",
        "tools/verify_rom_expansion_profile.py",
        "--root",
        ".",
        "--manifest",
        "artifacts/rom-expansion-profile-v1/manifest.json",
    ]
    if promotion.get("schema") != "git-artifact-promotion-v1":
        errors.append("promotion manifest schema mismatch")
    if (
        promotion.get("artifact_id") != "rom-expansion-profile-v1"
        or promotion.get("artifact_schema") != "rom-expansion-profile-v1"
        or promotion.get("artifact_status") != "accepted"
    ):
        errors.append("promotion identity/status mismatch")
    if (
        promotion.get("payload_file") != payload_name
        or promotion.get("payload_sha256") != payload_digest
    ):
        errors.append("promotion payload mismatch")
    if promotion.get("files") != actual_files:
        errors.append("promotion file inventory mismatch")
    if promotion.get("verifier") != {
        "command": expected_command,
        "exit_code": 0,
    }:
        errors.append("promotion verifier evidence mismatch")
    if (
        promotion.get("scope", {}).get("boundary")
        != manifest.get("boundary")
    ):
        errors.append("promotion scope mismatch")
    if manifest.get("schema") != "rom-expansion-profile-v1":
        errors.append("profile schema mismatch")

    for relative, expected in manifest.get("files", {}).items():
        path = root / relative
        if not path.is_file():
            errors.append(f"tracked evidence file is missing: {relative}")
            continue
        actual = _sha256(path)
        if actual != expected:
            errors.append(
                f"tracked evidence hash mismatch for {relative}: "
                f"expected {expected} got {actual}"
            )

    base_spec = manifest["base_rom"]
    base_path = root / base_spec["path"]
    base = base_path.read_bytes()
    if len(base) != int(base_spec["size"]):
        errors.append("base ROM size mismatch")
    if hashlib.sha1(base).hexdigest() != base_spec["sha1"]:
        errors.append("base ROM SHA-1 mismatch")
    if hashlib.sha256(base).hexdigest() != base_spec["sha256"]:
        errors.append("base ROM SHA-256 mismatch")

    layout_path = root / "sequel/rom-layout.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    target_size = _int(layout["target_rom_size"])
    max_size = _int(layout["cartridge_profile"]["max_rom_size"])
    fill_byte = _int(layout["fill_byte"])
    if target_size != int(manifest["target_rom"]["size"]):
        errors.append("target ROM size claim mismatch")
    if target_size > max_size or target_size & (target_size - 1):
        errors.append("target ROM size violates cartridge profile")
    if _int(layout["cartridge_profile"]["rom_base"]) != 0x08000000:
        errors.append("cartridge ROM base mismatch")
    if layout["cartridge_profile"]["id"] != manifest["target_rom"]["cartridge_profile"]:
        errors.append("cartridge profile identity mismatch")
    if layout["base_rom"]["sha1"] != base_spec["sha1"]:
        errors.append("layout base SHA-1 mismatch")
    if _int(layout["base_rom"]["size"]) != len(base):
        errors.append("layout base size mismatch")

    partitions = []
    ids: set[str] = set()
    for row in layout["partitions"]:
        partition_id = row["id"]
        start = _int(row["start"])
        end = _int(row["end"])
        alignment = _int(row["alignment"])
        origin = row["origin"]
        if partition_id in ids:
            errors.append(f"duplicate partition {partition_id}")
        ids.add(partition_id)
        if not 0 <= start < end <= target_size:
            errors.append(f"partition {partition_id} is outside target ROM")
        if alignment <= 0 or alignment & (alignment - 1):
            errors.append(f"partition {partition_id} alignment is invalid")
        if start % alignment or end % alignment:
            errors.append(f"partition {partition_id} is unaligned")
        if origin == "base_ff":
            if end > len(base) or base[start:end] != bytes([fill_byte]) * (end - start):
                errors.append(f"base_ff partition {partition_id} is not base FF")
        elif origin == "expanded_ff":
            if start < len(base):
                errors.append(f"expanded partition {partition_id} overlaps base")
        else:
            errors.append(f"partition {partition_id} has unknown origin")
        partitions.append((start, end, partition_id, row["owner"]))
    partitions.sort()
    for left, right in zip(partitions, partitions[1:]):
        if left[1] > right[0]:
            errors.append(f"partition overlap: {left[2]} / {right[2]}")

    build_manifest_path = artifact / "build-manifest.json"
    build_manifest = json.loads(build_manifest_path.read_text(encoding="utf-8"))
    expected_build_values = {
        "schema": "rom-expansion-cpu-read-probe-v1",
        "base_sha1": base_spec["sha1"],
        "base_sha256": base_spec["sha256"],
        "base_size": len(base),
        "layout_sha256": _sha256(layout_path),
        "cartridge_profile": layout["cartridge_profile"]["id"],
        "target_rom_size": target_size,
        "partition": "character-battle-visual-bundles",
        "owner": "character_battle_visuals",
        "original_entry_instruction": "0xEA00002E",
        "original_entry_target": "0x080000C0",
        "stub_address": "0x08600000",
        "marker_address": "0x08600100",
        "marker_hex": "4D475842",
        "scratch_address": "0x0203FFF0",
    }
    for key, expected in expected_build_values.items():
        if build_manifest.get(key) != expected:
            errors.append(
                f"build manifest {key} mismatch: "
                f"expected {expected!r} got {build_manifest.get(key)!r}"
            )

    original_instruction = struct.unpack_from("<I", base, 0)[0]
    original_target = _branch_target(original_instruction, 0x08000000)
    stub_offset = 0x600000
    marker_offset = 0x600100
    stub = struct.pack(
        "<9I",
        0xE59F0010,
        0xE5901000,
        0xE59F200C,
        0xE5821000,
        0xE59F3008,
        0xE12FFF13,
        0x08600100,
        0x0203FFF0,
        original_target,
    )
    rebuilt = bytearray(base + bytes([fill_byte]) * (target_size - len(base)))
    rebuilt[:4] = _arm_branch(0x08000000, 0x08600000)
    rebuilt[stub_offset : stub_offset + len(stub)] = stub
    rebuilt[marker_offset : marker_offset + 4] = bytes.fromhex("4D475842")
    rebuilt_sha256 = hashlib.sha256(rebuilt).hexdigest()
    if rebuilt_sha256 != build_manifest.get("output_sha256"):
        errors.append("independently rebuilt probe ROM SHA-256 mismatch")

    runtime_path = artifact / "runtime-evidence.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    expected_runtime = {
        "schema": "rom-expansion-runtime-evidence-v1",
        "success": True,
        "capture_frame": 60,
        "rom_sha256": rebuilt_sha256,
        "marker_address": "0x08600100",
        "scratch_address": "0x0203FFF0",
        "expected_marker": "0x4258474D",
        "rom_marker": "0x4258474D",
        "first_frame_scratch": "0x4258474D",
        "final_scratch": "0x4258474D",
        "pc": "0x085CCC88",
    }
    for key, expected in expected_runtime.items():
        if runtime.get(key) != expected:
            errors.append(
                f"runtime evidence {key} mismatch: "
                f"expected {expected!r} got {runtime.get(key)!r}"
            )
    if (
        manifest["runtime_probe"].get("first_frame_scratch")
        != runtime.get("first_frame_scratch")
    ):
        errors.append("profile first_frame_scratch claim mismatches runtime evidence")

    guard = json.loads(
        (
            artifact / "guard-summary.json"
        ).read_text(encoding="utf-8")
    )
    expected_guard = {
        "reason": "completed",
        "exit_code": 0,
        "degraded": False,
        "completion_trigger": "success-marker",
    }
    for key, expected in expected_guard.items():
        if guard.get(key) != expected:
            errors.append(
                f"guard {key} mismatch: expected {expected!r} "
                f"got {guard.get(key)!r}"
            )
    if float(guard.get("peak_tree_rss_mib", float("inf"))) != float(
        manifest["runtime_probe"]["peak_tree_rss_mib"]
    ):
        errors.append("guard peak RSS claim mismatch")

    state_path = root / runtime["state"]
    try:
        state = load_gba_state(state_path)
        savestate_scratch = state.read_u32(0x0203FFF0)
        if savestate_scratch != 0x4258474D:
            errors.append(
                f"savestate EWRAM scratch mismatch: 0x{savestate_scratch:08X}"
            )
        if state.registers[15] != int(runtime["pc"], 0):
            errors.append("savestate PC mismatches runtime evidence")
    except (OSError, ValueError, struct.error) as error:
        savestate_scratch = -1
        errors.append(f"savestate verification failed: {error}")

    try:
        screenshot = png_screen_fingerprint(root / runtime["screenshot"])
        if screenshot["width"] != 240 or screenshot["height"] != 160:
            errors.append("runtime screenshot dimensions mismatch")
    except (OSError, ValueError, struct.error) as error:
        screenshot = {}
        errors.append(f"screenshot verification failed: {error}")

    restore_path = artifact / "restore-evidence.json"
    restore = json.loads(restore_path.read_text(encoding="utf-8"))
    expected_restore = {
        "schema": "rom-expansion-snapshot-restore-v1",
        "success": True,
        "rom_sha256": rebuilt_sha256,
        "input_state": runtime["state"],
        "restored_frame": 60,
        "capture_delta": 30,
        "rom_marker": "0x4258474D",
        "scratch_marker": "0x4258474D",
        "pc": "0x085CCC80",
    }
    for key, expected in expected_restore.items():
        if restore.get(key) != expected:
            errors.append(
                f"snapshot restore {key} mismatch: "
                f"expected {expected!r} got {restore.get(key)!r}"
            )
    restore_claim = manifest["runtime_probe"].get("snapshot_restore", {})
    for key in (
        "run_id",
        "input_state",
        "restored_frame",
        "capture_delta",
        "rom_marker",
        "scratch_marker",
        "pc",
    ):
        if restore_claim.get(key) != restore.get(key):
            errors.append(f"profile snapshot restore {key} claim mismatch")

    restore_guard = json.loads(
        (
            artifact / "restore-guard-summary.json"
        ).read_text(encoding="utf-8")
    )
    expected_restore_guard = {
        "reason": "completed",
        "exit_code": 0,
        "degraded": False,
        "completion_trigger": "success-marker",
    }
    for key, expected in expected_restore_guard.items():
        if restore_guard.get(key) != expected:
            errors.append(
                f"snapshot restore guard {key} mismatch: "
                f"expected {expected!r} got {restore_guard.get(key)!r}"
            )
    restore_guard_claims = {
        "guard_reason": "reason",
        "guard_exit_code": "exit_code",
        "guard_degraded": "degraded",
        "guard_completion_trigger": "completion_trigger",
        "peak_tree_rss_mib": "peak_tree_rss_mib",
    }
    for claim_key, guard_key in restore_guard_claims.items():
        if restore_claim.get(claim_key) != restore_guard.get(guard_key):
            errors.append(f"profile snapshot restore {claim_key} claim mismatch")

    snapshot_restore_scratch = int(
        restore.get("scratch_marker", "0"),
        0,
    )
    snapshot_restore_pc = str(restore.get("pc", ""))
    try:
        restore_screenshot = png_screen_fingerprint(
            root / restore["screenshot"]
        )
        if (
            restore_screenshot["width"] != 240
            or restore_screenshot["height"] != 160
        ):
            errors.append("snapshot restore screenshot dimensions mismatch")
        if (
            screenshot
            and restore_screenshot.get("rgb_pixels_sha256")
            != screenshot.get("rgb_pixels_sha256")
        ):
            errors.append("snapshot restore screenshot changed after zero input")
    except (OSError, ValueError, struct.error) as error:
        restore_screenshot = {}
        errors.append(f"snapshot restore screenshot verification failed: {error}")

    return {
        "schema": "rom-expansion-profile-verification-v1",
        "errors": errors,
        "target_rom_size": target_size,
        "partition_count": len(partitions),
        "rebuilt_probe_sha256": rebuilt_sha256,
        "savestate_scratch": savestate_scratch,
        "screenshot": screenshot,
        "snapshot_restore_pc": snapshot_restore_pc,
        "snapshot_restore_scratch": snapshot_restore_scratch,
        "snapshot_restore_screenshot": restore_screenshot,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independently verify the tracked ROM expansion profile."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/rom-expansion-profile-v1/manifest.json"),
    )
    args = parser.parse_args()
    manifest = (
        args.manifest
        if args.manifest.is_absolute()
        else args.root / args.manifest
    )
    result = verify_profile(args.root, manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
