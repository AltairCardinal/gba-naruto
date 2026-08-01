#!/usr/bin/env python3
"""Promote profile-driven battle-effect single-pixel runtime A/B evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_battle_effect_pixel_ab import (
    BUILD_SCHEMA,
    PROFILE_SCHEMA,
    _runtime_oam_instances,
    _validate_profile,
    build_pair,
)
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


SCHEMA = "battle-effect-pixel-ab-runtime-v1"
MGBA_BINARY_SHA256 = (
    "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
)
MGBA_BUILD_MANIFEST_SHA256 = (
    "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d"
)
CURRENT_MGBA_BINARY_SHA256 = (
    "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8"
)
CURRENT_TOOLCHAIN_PROFILE_SHA256 = (
    "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287"
)
CURRENT_MGBA_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"
VARIANTS = ("baseline", "candidate")
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
LEGACY_IMPLEMENTATION_PATHS = (
    "tools/build_battle_effect_pixel_ab.py",
    "tools/export_battle_effect_pixel_ab_evidence.py",
    "tools/verify_battle_effect_pixel_ab_evidence.py",
    "tools/import_battle_effect_resource_relocations.py",
    "tools/import_battle_effect_resources.py",
    "tools/build_mod.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tools/run_macos_mgba_input_sequence.py",
    "tools/mgba_input_sequence_replay.lua",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
)
INTERMEDIATE_IMPLEMENTATION_PATHS = LEGACY_IMPLEMENTATION_PATHS + (
    "tools/run_macos_mgba_single_input_current.py",
)
IMPLEMENTATION_PATHS = INTERMEDIATE_IMPLEMENTATION_PATHS + (
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/run_macos_mgba_replay.py",
    "tools/macos_mgba_runtime_residue.py",
    "tools/verify_battle_effect_group15_natural_runtime.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _runtime_toolchain_contract(
    root: Path, profile: dict[str, Any]
) -> dict[str, Any]:
    configured = profile.get("runtime_toolchain")
    if configured is None:
        return {
            "kind": "legacy-build-manifest",
            "binary_sha256": MGBA_BINARY_SHA256,
            "build_manifest_sha256": MGBA_BUILD_MANIFEST_SHA256,
        }
    expected = {
        "kind": "current-desktop-runtime-profile",
        "path": "artifacts/rom-expansion-profile-v1/profile.json",
        "sha256": CURRENT_TOOLCHAIN_PROFILE_SHA256,
        "binary_sha256": CURRENT_MGBA_BINARY_SHA256,
        "source_commit": CURRENT_MGBA_SOURCE_COMMIT,
    }
    if configured != expected:
        raise ValueError("battle-effect pixel current runtime toolchain contract mismatch")
    path = (root / expected["path"]).resolve(strict=True)
    if (
        root.resolve(strict=True) not in path.parents
        or _sha256_file(path) != expected["sha256"]
    ):
        raise ValueError("battle-effect pixel current runtime profile hash mismatch")
    payload = _json(path)
    hardware = payload.get("hardware_evidence", {})
    runtime = payload.get("runtime_probe", {})
    if (
        payload.get("schema") != "rom-expansion-profile-v1"
        or hardware.get("mgba_binary_sha256") != expected["binary_sha256"]
        or hardware.get("mgba_source_commit") != expected["source_commit"]
        or runtime.get("guard_reason") != "completed"
        or runtime.get("guard_completion_trigger") != "success-marker"
        or runtime.get("guard_exit_code") != 0
        or runtime.get("guard_degraded") is not False
        or runtime.get("new_mgba_crash_report") is not False
        or runtime.get("owned_process_residue") is not False
    ):
        raise ValueError("battle-effect pixel current runtime profile contract mismatch")
    return dict(expected)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"battle-effect pixel evidence JSON must be an object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("battle-effect pixel evidence byte lengths differ")
    return [
        index
        for index, (before, after) in enumerate(zip(left, right))
        if before != after
    ]


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("battle-effect pixel screenshot geometry mismatch")
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


def _expected_pixels(profile: dict[str, Any]) -> list[dict[str, Any]]:
    coordinates = profile.get("screen_pixels", [profile.get("screen_xy")])
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("battle-effect pixel expected screen pixels are invalid")
    return [
        {
            "x": coordinate[0],
            "y": coordinate[1],
            "before_rgb": profile["before_rgb"],
            "after_rgb": profile["after_rgb"],
        }
        for coordinate in coordinates
    ]


def _runtime_component_obj_tile_base(
    profile: dict[str, Any], component_tile_index: int
) -> int:
    runtime_oam = profile.get("runtime_oam")
    if not isinstance(runtime_oam, dict):
        raise ValueError("battle-effect pixel runtime component tile mapping mismatch")
    try:
        address = int(runtime_oam.get("obj_vram_address"), 16)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "battle-effect pixel runtime component tile mapping mismatch"
        ) from error
    if (
        not isinstance(component_tile_index, int)
        or isinstance(component_tile_index, bool)
    ):
        raise ValueError("battle-effect pixel runtime component tile mapping mismatch")
    delta = address - 0x06010000
    expected = delta // 32 + component_tile_index
    if (
        delta < 0
        or delta % 32
        or not 0 <= expected < 1024
        or runtime_oam.get("obj_tile_base") != expected
    ):
        raise ValueError("battle-effect pixel runtime component tile mapping mismatch")
    return expected


def _preload_evidence(
    obj_vram: bytes,
    baseline: bytes,
    candidate: bytes,
    target_offset: int,
) -> dict[str, Any]:
    locations: list[str] = []
    cursor = 0
    while True:
        found = obj_vram.find(baseline, cursor)
        if found < 0:
            break
        locations.append(f"0x{0x06010000 + found:08X}")
        cursor = found + 1
    candidate_absent = obj_vram.find(candidate) < 0
    target_candidate_absent = (
        0 <= target_offset <= len(obj_vram) - len(candidate)
        and obj_vram[target_offset : target_offset + len(candidate)] != candidate
    )
    if not candidate_absent or not target_candidate_absent:
        raise ValueError("battle-effect pixel candidate exists before natural input")
    return {
        "candidate_resource_absent_before_input": True,
        "target_candidate_absent_before_input": True,
        "stale_baseline_locations": locations,
    }


def _valid_implementation_hashes(
    value: object, expected_paths: tuple[str, ...]
) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(expected_paths)
        and all(
            isinstance(digest, str)
            and len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest)
            for digest in value.values()
        )
    )


def _generation_implementation_hashes(
    raw: Path,
    raw_hashes: dict[str, str],
    current: dict[str, str],
) -> dict[str, str]:
    source_manifest = raw.parent / "manifest.json"
    if not source_manifest.is_file():
        return current
    manifest = _json(source_manifest)
    if manifest.get("raw_files") != raw_hashes:
        return current
    historical = manifest.get(
        "generated_with_implementation_sha256",
        manifest.get("implementation_sha256"),
    )
    if not any(
        _valid_implementation_hashes(historical, paths)
        for paths in (
            LEGACY_IMPLEMENTATION_PATHS,
            INTERMEDIATE_IMPLEMENTATION_PATHS,
            IMPLEMENTATION_PATHS,
        )
    ):
        raise ValueError("battle-effect pixel generation provenance is invalid")
    return dict(historical)


def _build_manifest_profile_metadata_matches(
    build: dict[str, Any], profile: dict[str, Any], profile_sha256: str
) -> bool:
    if (
        build.get("profile_sha256") == profile_sha256
        and build.get("runtime_oam") == profile.get("runtime_oam")
    ):
        return True
    runtime_oam = profile.get("runtime_oam")
    historical_sha = build.get("profile_sha256")
    return (
        isinstance(runtime_oam, dict)
        and "instances" in runtime_oam
        and isinstance(historical_sha, str)
        and len(historical_sha) == 64
        and all(character in "0123456789abcdef" for character in historical_sha)
        and build.get("runtime_oam")
        == {key: value for key, value in runtime_oam.items() if key != "instances"}
    )


def _build_manifest_reproducible_with_profile_extension(
    historical: dict[str, Any], current: dict[str, Any], profile: dict[str, Any]
) -> bool:
    if historical == current:
        return True
    if not _build_manifest_profile_metadata_matches(
        historical, profile, current.get("profile_sha256")
    ):
        return False
    keys = set(historical) | set(current)
    return all(
        historical.get(key) == current.get(key)
        for key in keys
        if key not in {"profile_sha256", "runtime_oam"}
    )


def _selector_scope(selector: object) -> dict[str, bool]:
    if not isinstance(selector, dict) or selector.get("kind") not in {
        "ninja_tool",
        "active_action",
    }:
        raise ValueError("battle-effect pixel selector scope mismatch")
    return {
        f"natural_{selector['kind']}_route": True,
        "production_relocation_route": True,
        "single_group_single_frame_single_pixel": True,
        "all_18_effect_groups_runtime_verified": False,
        "all_group_frames_runtime_verified": False,
        "full_affine_blend_timing_audio_equivalence": False,
        "physical_gba_verified": False,
    }


def _raw_files(profile: dict[str, Any]) -> tuple[str, ...]:
    frame = profile["runtime_input"]["capture_frame"]
    group = profile["group_id"]
    files = ["build-manifest.json"]
    for variant in VARIANTS:
        files.extend(
            (
                f"{variant}/audit.json",
                f"{variant}/frame{frame}.png",
                f"{variant}/frame{frame}.ss9",
                f"{variant}/group-{group:02d}-graphics-4bpp.bin",
                f"{variant}/guard.json",
                f"{variant}/sentinel.json",
                f"{variant}/spec.json",
            )
        )
    return tuple(files)


def collect_experiment_raw(
    build_root: Path,
    runtime_root: Path,
    raw: Path,
    profile: dict[str, Any],
) -> None:
    """Copy the bounded build/runtime files needed for durable verification."""

    build_root = Path(build_root).resolve(strict=True)
    runtime_root = Path(runtime_root).resolve(strict=True)
    raw = Path(raw).resolve()
    if raw.exists():
        raise ValueError("battle-effect pixel canonical raw output already exists")
    frame = profile["runtime_input"]["capture_frame"]
    group = profile["group_id"]
    mapping = {"build-manifest.json": build_root / "build-manifest.json"}
    for variant in VARIANTS:
        mapping.update(
            {
                f"{variant}/audit.json": runtime_root / variant / "audit.json",
                f"{variant}/frame{frame}.png": runtime_root
                / variant
                / f"frame{frame}.png",
                f"{variant}/frame{frame}.ss9": runtime_root
                / variant
                / f"frame{frame}.ss9",
                f"{variant}/group-{group:02d}-graphics-4bpp.bin": build_root
                / variant
                / f"group-{group:02d}-graphics-4bpp.bin",
                f"{variant}/guard.json": runtime_root / variant / "guard.json",
                f"{variant}/sentinel.json": runtime_root / variant / "sentinel.json",
                f"{variant}/spec.json": build_root / variant / "spec.json",
            }
        )
    if set(mapping) != set(_raw_files(profile)) or any(
        not path.is_file() for path in mapping.values()
    ):
        raise ValueError("battle-effect pixel experiment evidence is incomplete")
    for name, source in mapping.items():
        destination = raw / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _canonicalize(raw: Path, profile: dict[str, Any]) -> None:
    frame = profile["runtime_input"]["capture_frame"]
    group = profile["group_id"]
    for variant in VARIANTS:
        guard_path = raw / variant / "guard.json"
        guard = _json(guard_path)
        guard["command"] = [
            "mGBA",
            "--script",
            "tools/mgba_single_input_replay.lua",
            f"runtime-only/{variant}/staged.gba",
        ]
        guard["cwd"] = "."
        _write_json(guard_path, guard)

        audit_path = raw / variant / "audit.json"
        audit = _json(audit_path)
        audit.update(
            {
                "audit": f"raw/{variant}/audit.json",
                "input_state": profile["input_state"],
                "output_png": f"raw/{variant}/frame{frame}.png",
                "output_state": f"raw/{variant}/frame{frame}.ss9",
                "replay_script": "tools/mgba_single_input_replay.lua",
                "sentinel": f"raw/{variant}/sentinel.json",
                "staged_rom": f"runtime-only/{variant}/staged.gba",
                "guard_summary_sha256": _sha256_file(guard_path),
            }
        )
        configured_toolchain = profile.get("runtime_toolchain")
        if configured_toolchain is None:
            audit["build_manifest"] = "toolchain/mgba-build-manifest.json"
        else:
            audit.pop("build_manifest", None)
            audit.pop("build_manifest_sha256", None)
            audit["toolchain"] = {
                "kind": configured_toolchain["kind"],
                "path": "toolchain/mgba-runtime-profile.json",
                "sha256": configured_toolchain["sha256"],
                "source_commit": configured_toolchain["source_commit"],
                "patch_sha256": None,
            }
        _write_json(audit_path, audit)
        _write_json(raw / variant / "sentinel.json", audit)

        spec_path = raw / variant / "spec.json"
        spec = _json(spec_path)
        edits = spec.get("edits")
        if not isinstance(edits, list) or len(edits) != 1:
            raise ValueError("battle-effect pixel promoted spec mismatch")
        edits[0]["source_file"] = (
            f"raw/{variant}/group-{group:02d}-graphics-4bpp.bin"
        )
        _write_json(spec_path, spec)


def _validate_audit(
    root: Path,
    raw: Path,
    variant: str,
    build: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    toolchain = _runtime_toolchain_contract(root, profile)
    current = toolchain["kind"] == "current-desktop-runtime-profile"
    expected_runtime_toolchain = {
        "kind": "current-desktop-runtime-profile",
        "path": "toolchain/mgba-runtime-profile.json",
        "sha256": CURRENT_TOOLCHAIN_PROFILE_SHA256,
        "source_commit": CURRENT_MGBA_SOURCE_COMMIT,
        "patch_sha256": None,
    }
    frame = profile["runtime_input"]["capture_frame"]
    runtime_input = profile["runtime_input"]
    event = {
        "key": runtime_input["key"],
        "down_frame": runtime_input["down_frame"],
        "up_frame": runtime_input["up_frame"],
        "hold_frames": runtime_input["up_frame"] - runtime_input["down_frame"],
    }
    audit = _json(raw / variant / "audit.json")
    sentinel = _json(raw / variant / "sentinel.json")
    guard_path = raw / variant / "guard.json"
    guard = _json(guard_path)
    state_path = raw / variant / f"frame{frame}.ss9"
    png_path = raw / variant / f"frame{frame}.png"
    if (
        audit != sentinel
        or audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        or audit.get("staged_rom_sha256") != audit.get("rom_sha256")
        or audit.get("input_state_sha256") != profile["input_state_sha256"]
        or audit.get("inputs") != [event]
        or audit.get("capture_frame") != frame
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("binary_sha256") != toolchain["binary_sha256"]
        or (
            current
            and (
                "build_manifest_sha256" in audit
                or "build_manifest" in audit
                or audit.get("toolchain") != expected_runtime_toolchain
            )
        )
        or (
            not current
            and (
                audit.get("build_manifest_sha256")
                != MGBA_BUILD_MANIFEST_SHA256
                or audit.get("build_manifest")
                != "toolchain/mgba-build-manifest.json"
            )
        )
        or audit.get("replay_script_sha256")
        != _sha256_file(root / "tools/mgba_single_input_replay.lua")
        or audit.get("output_state_sha256") != _sha256_file(state_path)
        or audit.get("output_png_sha256") != _sha256_file(png_path)
        or audit.get("guard_summary_sha256") != _sha256_file(guard_path)
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
    ):
        raise ValueError(f"battle-effect pixel {variant} runtime provenance mismatch")
    result = {
        "run_id": audit["run_id"],
        "rom_sha256": audit["rom_sha256"],
        "state_sha256": audit["output_state_sha256"],
        "png_sha256": audit["output_png_sha256"],
        "binary_sha256": audit["binary_sha256"],
        "replay_script_sha256": audit["replay_script_sha256"],
        "guard_sha256": audit["guard_summary_sha256"],
        "child_pgid": audit["child_pgid"],
        "peak_tree_rss_mib": audit["peak_tree_rss_mib"],
        "pgid_clean": True,
    }
    if current:
        result["toolchain"] = dict(audit["toolchain"])
    else:
        result["build_manifest_sha256"] = audit["build_manifest_sha256"]
    return result


def export_evidence(
    root: Path,
    profile_path: Path,
    raw_root: Path,
    output: Path,
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    raw_root = Path(raw_root).resolve(strict=True)
    output = Path(output).resolve()
    profile, contract = _validate_profile(root, profile_path)
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("battle-effect pixel evidence profile mismatch")
    _runtime_toolchain_contract(root, profile)
    _runtime_component_obj_tile_base(
        profile, contract["component"]["tile_index"]
    )
    actual_raw = {
        path.relative_to(raw_root) for path in raw_root.rglob("*") if path.is_file()
    }
    if actual_raw != {Path(name) for name in _raw_files(profile)}:
        raise ValueError("battle-effect pixel raw evidence file set mismatch")
    source_raw_hashes = {
        name: _sha256_file(raw_root / name) for name in _raw_files(profile)
    }
    if output.exists() and any(output.iterdir()):
        raise ValueError("battle-effect pixel evidence output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    promoted_raw = output / "raw"
    shutil.copytree(raw_root, promoted_raw)
    _canonicalize(promoted_raw, profile)
    raw = promoted_raw

    build = _json(raw / "build-manifest.json")
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("profile_id") != profile["profile_id"]
        or not _build_manifest_profile_metadata_matches(
            build, profile, _sha256_file(profile_path)
        )
        or build.get("input_state") != profile["input_state"]
        or build.get("input_state_sha256") != profile["input_state_sha256"]
        or build.get("input_evidence") != profile["input_evidence"]
        or build.get("input_evidence_sha256")
        != profile["input_evidence_sha256"]
        or build.get("same_patch_topology") is not True
        or build.get("same_encoded_size") is not True
    ):
        raise ValueError("battle-effect pixel build manifest contract mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        current_build = build_pair(root, profile_path, Path(temporary) / "build")
        if not _build_manifest_reproducible_with_profile_extension(
            build, current_build, profile
        ):
            raise ValueError("battle-effect pixel build manifest is not reproducible")

    group = profile["group_id"]
    graphics = {
        variant: (
            raw / variant / f"group-{group:02d}-graphics-4bpp.bin"
        ).read_bytes()
        for variant in VARIANTS
    }
    offset = profile["graphics_byte_offset"]
    if (
        _diff(graphics["baseline"], graphics["candidate"]) != [offset]
        or graphics["baseline"][offset] != profile["before_byte"]
        or graphics["candidate"][offset] != profile["after_byte"]
        or graphics["baseline"] != contract["source_path"].read_bytes()
    ):
        raise ValueError("battle-effect pixel authored graphics isolation mismatch")

    runs = {
        variant: _validate_audit(root, raw, variant, build, profile)
        for variant in VARIANTS
    }
    frame = profile["runtime_input"]["capture_frame"]
    states = {
        variant: load_gba_state(raw / variant / f"frame{frame}.ss9")
        for variant in VARIANTS
    }
    memory_differences = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    changed_vram_offset = int(profile["runtime_oam"]["obj_vram_address"], 16) - 0x06000000 + offset
    expected_differences = {name: [] for name in DOMAINS}
    expected_differences["VRAM"] = [changed_vram_offset]
    if memory_differences != expected_differences:
        raise ValueError("battle-effect pixel runtime memory isolation mismatch")

    resource = contract["resource"]
    palette_path = root / "artifacts/battle-effect-resource-pairs-v1" / resource["palette"]["output_bin"]
    palette = palette_path.read_bytes()
    vram_address = int(profile["runtime_oam"]["obj_vram_address"], 16)
    palette_address = 0x05000200 + profile["runtime_oam"]["palette_bank"] * 32
    oam_instances = _runtime_oam_instances(
        profile,
        profile["component_pixel_xy"][0],
        profile["component_pixel_xy"][1],
        component_width=contract["component"]["width"],
        component_height=contract["component"]["height"],
    )
    for variant in VARIANTS:
        rendered, _ = render_checkpoint(raw / variant / f"frame{frame}.ss9")
        if (
            states[variant].read_memory(vram_address, len(graphics[variant]))
            != graphics[variant]
            or states[variant].read_memory(palette_address, len(palette)) != palette
            or rendered != _rgb(raw / variant / f"frame{frame}.png")
        ):
            raise ValueError(f"battle-effect pixel {variant} natural route mismatch")
        for instance in oam_instances:
            address = 0x07000000 + instance["oam_index"] * 8
            expected = b"".join(
                int(value, 16).to_bytes(2, "little")
                for value in instance["attributes"]
            )
            if states[variant].read_memory(address, 6) != expected:
                raise ValueError(
                    f"battle-effect pixel {variant} OAM instance mismatch"
                )

    input_state = load_gba_state(root / profile["input_state"])
    input_obj_vram = input_state.read_memory(0x06010000, 0x8000)
    target_offset = int(profile["runtime_oam"]["obj_vram_address"], 16) - 0x06010000
    preload = _preload_evidence(
        input_obj_vram,
        graphics["baseline"],
        graphics["candidate"],
        target_offset,
    )
    input_presence = (
        {"resource_absent_before_input": True}
        if not preload["stale_baseline_locations"]
        else preload
    )

    baseline_rgb = _rgb(raw / "baseline" / f"frame{frame}.png")
    candidate_rgb = _rgb(raw / "candidate" / f"frame{frame}.png")
    changes = _pixel_changes(baseline_rgb, candidate_rgb)
    expected_pixels = _expected_pixels(profile)
    if changes != expected_pixels:
        raise ValueError("battle-effect pixel final pixel isolation mismatch")

    evidence = {
        "schema": SCHEMA,
        "verified": True,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256_file(profile_path),
        "input": {
            "path": profile["input_state"],
            "sha256": profile["input_state_sha256"],
            "event": {
                "key": profile["runtime_input"]["key"],
                "down_frame": profile["runtime_input"]["down_frame"],
                "up_frame": profile["runtime_input"]["up_frame"],
                "hold_frames": profile["runtime_input"]["up_frame"]
                - profile["runtime_input"]["down_frame"],
            },
            "capture_frame": frame,
            **input_presence,
        },
        "binding": build["binding"],
        "edit": build["edit"],
        "runtime": {
            "memory_differences": memory_differences,
            "graphics_vram_address": profile["runtime_oam"]["obj_vram_address"],
            "changed_vram_address": f"0x{0x06000000 + changed_vram_offset:08X}",
            "baseline_vram_byte": profile["before_byte"],
            "candidate_vram_byte": profile["after_byte"],
            "oam_entry": profile["runtime_oam"]["oam_index"],
            "oam_attributes": profile["runtime_oam"]["attributes"],
            "palette_bank": profile["runtime_oam"]["palette_bank"],
            **(
                {"oam_instances": oam_instances}
                if "instances" in profile["runtime_oam"]
                else {}
            ),
            "renderer_exact": True,
            "pixels": {
                "count": len(changes),
                "bbox": [
                    min(pixel["x"] for pixel in changes),
                    min(pixel["y"] for pixel in changes),
                    max(pixel["x"] for pixel in changes),
                    max(pixel["y"] for pixel in changes),
                ],
                "baseline_rgb_sha256": _sha256(baseline_rgb),
                "candidate_rgb_sha256": _sha256(candidate_rgb),
                "changes": changes,
            },
        },
        "runs": runs,
        "scope": _selector_scope(profile["selector"]),
    }
    _write_json(output / "runtime-evidence.json", evidence)

    files = {
        path.relative_to(output).as_posix(): _sha256_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    implementation_hashes = {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }
    raw_hashes = {
        name: _sha256_file(raw / name) for name in _raw_files(profile)
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": f"battle-effect-group{profile['group_id']}-pixel-ab-v1",
        "artifact_status": "accepted",
        "base_rom_sha256": build["base_rom_sha256"],
        "parent": {
            "path": profile["input_state"],
            "sha256": profile["input_state_sha256"],
        },
        "source_catalog": profile["catalogs"]["resource_pairs"],
        "source_catalog_sha256": profile["catalogs"][
            "resource_pairs_sha256"
        ],
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256_file(profile_path),
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256_file(output / "runtime-evidence.json"),
        "files": files,
        "raw_files": raw_hashes,
        "generated_with_implementation_sha256": _generation_implementation_hashes(
            raw_root, source_raw_hashes, implementation_hashes
        ),
        "verified_with_implementation_sha256": implementation_hashes,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_battle_effect_pixel_ab_evidence.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/battle-effect-group{profile['group_id']}-pixel-ab-v1",
            ],
            "exit_code": 0,
            "result": {"errors": [], "verified": True},
        },
        "scope": evidence["scope"],
    }
    _write_json(output / "manifest.json", manifest)
    return evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve(strict=True)
    profile_path = args.profile.resolve(strict=True)
    profile, _ = _validate_profile(root, profile_path)
    if (args.build_root is None) != (args.runtime_root is None):
        raise ValueError("--build-root and --runtime-root must be supplied together")
    if args.build_root is not None:
        collect_experiment_raw(
            args.build_root,
            args.runtime_root,
            args.raw_root,
            profile,
        )
    evidence = export_evidence(root, profile_path, args.raw_root, args.output)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
