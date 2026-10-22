#!/usr/bin/env python3
"""Promote natural motion/effect parameter A/B captures into a compact artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import tarfile
from typing import Any, Sequence

from PIL import Image

try:
    from tools.render_mode0_checkpoint import render_checkpoint
except ModuleNotFoundError:
    from render_mode0_checkpoint import render_checkpoint


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_SCHEMA = "motion-effect-parameter-pixel-ab-runtime-v1"
BUILD_SCHEMA = "motion-effect-parameter-pixel-ab-build-v1"
VARIANTS = ("baseline", "candidate")
PHASES = ("renderer-post", "submit-post", "ack-post")
DOMAINS = (
    "task-pool.bin",
    "active-count.bin",
    "active-pointers.bin",
    "runtime-offsets.bin",
    "shadow-oam.bin",
    "hardware-oam.bin",
    "submission.bin",
    "vram.bin",
    "pram.bin",
    "io.bin",
)
EXPECTED_DIFFS = {
    "renderer-post": {"task-pool.bin": [0x1D8E], "shadow-oam.bin": [0]},
    "submit-post": {"task-pool.bin": [0x1D8E], "shadow-oam.bin": [0]},
    "ack-post": {
        "task-pool.bin": [0x1D8E],
        "shadow-oam.bin": [0],
        "hardware-oam.bin": [0],
    },
}
IMPLEMENTATION_PATHS = (
    "sequel/content/palettes/bank.json",
    "sequel/content/motion-effect-parameter-pixel-ab/group-03-record-00-y-offset.json",
    "tools/build_motion_effect_parameter_pixel_ab.py",
    "tools/run_motion_effect_parameter_pixel_ab.py",
    "tools/export_motion_effect_parameter_pixel_ab.py",
    "tools/verify_motion_effect_parameter_pixel_ab.py",
    "tools/render_mode0_checkpoint.py",
    "tools/inspect_mgba_savestate.py",
    "tools/mgba_battle_effect_phase_capture.lua",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tests/test_build_motion_effect_parameter_pixel_ab.py",
    "tests/test_run_motion_effect_parameter_pixel_ab.py",
    "tests/test_export_motion_effect_parameter_pixel_ab.py",
    "tests/test_verify_motion_effect_parameter_pixel_ab.py",
    "tests/test_overlapping_visual_table_identity.py",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"motion parameter JSON must be an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def byte_differences(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("motion parameter compared byte lengths differ")
    return [
        index
        for index, pair in enumerate(zip(left, right, strict=True))
        if pair[0] != pair[1]
    ]


def pixel_summary(left: bytes, right: bytes) -> dict[str, Any]:
    if len(left) != 240 * 160 * 3 or len(right) != len(left):
        raise ValueError("motion parameter rendered frame size mismatch")
    changes = []
    for index in range(240 * 160):
        offset = index * 3
        before = left[offset : offset + 3]
        after = right[offset : offset + 3]
        if before != after:
            changes.append(
                {
                    "x": index % 240,
                    "y": index // 240,
                    "before_rgb": list(before),
                    "after_rgb": list(after),
                }
            )
    if not changes:
        raise ValueError("motion parameter produced no final Mode 0 pixel change")
    canonical = json.dumps(changes, separators=(",", ":"), sort_keys=True).encode()
    return {
        "count": len(changes),
        "bbox": [
            min(row["x"] for row in changes),
            min(row["y"] for row in changes),
            max(row["x"] for row in changes),
            max(row["y"] for row in changes),
        ],
        "changes_sha256": sha256_bytes(canonical),
    }


def raw_paths(source: Path) -> list[Path]:
    selected = [source / "batch-audit.json", source / "build/build-manifest.json"]
    for variant in VARIANTS:
        selected.extend(
            [
                source / f"runs/{variant}/profile.json",
                source / f"runs/{variant}/guard-summary.json",
                source / f"runs/{variant}/guard-summary.json.done.json",
            ]
        )
        selected.extend(
            path
            for path in (source / f"runs/{variant}/output").rglob("*")
            if path.is_file()
        )
    selected = sorted(set(selected), key=lambda path: path.relative_to(source).as_posix())
    if any(not path.is_file() or path.is_symlink() for path in selected):
        raise ValueError("motion parameter raw source is incomplete or unsafe")
    return selected


def write_tar(source: Path, paths: list[Path], output: Path) -> list[dict[str, Any]]:
    inventory = []
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for path in paths:
            name = path.relative_to(source).as_posix()
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
            inventory.append({"path": name, "size": len(data), "sha256": sha256_bytes(data)})
    return inventory


def validate_phase_run(source: Path, variant: str, build: dict[str, Any]) -> dict[str, Any]:
    run = source / "runs" / variant
    profile = read_object(run / "profile.json")
    audit = read_object(run / "output/audit.json")
    guard = read_object(run / "guard-summary.json")
    row = build["variants"][variant]
    if (
        profile.get("variant") != variant
        or profile.get("group_id") != 3
        or profile.get("sequence_id") != 3
        or profile.get("execution_mode") != "natural-motion-parameter-pixel-ab"
        or profile.get("natural_gameplay_route") is not True
        or profile.get("input_mode") != "zero-input-active-state"
        or profile.get("inputs") != []
        or profile.get("source_rom_sha256") != row["rom_sha256"]
        or audit.get("outcome") != "three-phase-captured"
        or audit.get("group_id") != 3
        or audit.get("input_mode") != "zero-input-active-state"
        or audit.get("inputs") != []
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("rom_sha256") != row["rom_sha256"]
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
    ):
        raise ValueError(f"motion parameter {variant} runtime provenance mismatch")
    phases = audit.get("phases")
    if (
        not isinstance(phases, list)
        or [row.get("name") for row in phases] != list(PHASES)
        or [row.get("address") for row in phases]
        != ["0x08063328", "0x08061126", "0x080612AA"]
        or [row.get("pending") for row in phases] != [0, 1, 0]
        or {row.get("task_slot") for row in phases} != {126}
        or {row.get("task_address") for row in phases} != {"0x03005940"}
        or [row.get("frame") for row in phases] != [67, 67, 68]
    ):
        raise ValueError(f"motion parameter {variant} phase transaction mismatch")
    for relative, expected in audit.get("files", {}).items():
        path = run / "output" / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"motion parameter {variant} raw hash mismatch: {relative}")
    return {
        "variant": variant,
        "rom_sha256": row["rom_sha256"],
        "profile_sha256": sha256_file(run / "profile.json"),
        "audit_sha256": sha256_file(run / "output/audit.json"),
        "guard_summary_sha256": sha256_file(run / "guard-summary.json"),
        "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        "pgid_clean": True,
        "phase_transaction": {
            "frames": [67, 67, 68],
            "pending": [0, 1, 0],
            "task_slot": 126,
            "task_address": "0x03005940",
            "cycles": [row["cycle"] for row in phases],
        },
    }


def export_evidence(root: Path, profile_path: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("motion parameter artifact output must be absent or empty")
    profile = read_object(profile_path)
    batch = read_object(source / "batch-audit.json")
    build = read_object(source / "build/build-manifest.json")
    if (
        profile.get("schema") != "motion-effect-parameter-pixel-ab-profile-v1"
        or profile.get("group_id") != 3
        or profile.get("sequence_id") != 3
        or profile.get("record_id") != 0
        or profile.get("field") != "y_offset"
        or profile.get("consumer_entry") != "0x08080764"
        or profile.get("child_spawn_function") != "0x08080218"
        or batch.get("schema") != "motion-effect-parameter-pixel-ab-batch-v1"
        or batch.get("run_budget") != {"planned": 2, "actual": 2, "blind_retries": 0}
        or build.get("schema") != BUILD_SCHEMA
        or build.get("profile_sha256") != sha256_file(profile_path)
        or build.get("edit", {}).get("changed_rom_offsets") != [0x53EE9C]
        or batch.get("build_manifest_sha256") != sha256_file(source / "build/build-manifest.json")
    ):
        raise ValueError("motion parameter profile/build/batch contract mismatch")

    base = (root / "rom/base.gba").read_bytes()
    candidate = bytearray(base)
    candidate[0x53EE9C:0x53EE9E] = b"\x20\x00"
    if (
        sha256_bytes(base) != build["variants"]["baseline"]["rom_sha256"]
        or sha256_bytes(bytes(candidate)) != build["variants"]["candidate"]["rom_sha256"]
        or byte_differences(base, bytes(candidate)) != [0x53EE9C]
    ):
        raise ValueError("motion parameter probe-free ROM reconstruction mismatch")

    runs = [validate_phase_run(source, variant, build) for variant in VARIANTS]
    memory: dict[str, dict[str, list[int]]] = {}
    for phase in PHASES:
        differences = {}
        for domain in DOMAINS:
            left = (source / f"runs/baseline/output/{phase}/capture-{domain}").read_bytes()
            right = (source / f"runs/candidate/output/{phase}/capture-{domain}").read_bytes()
            offsets = byte_differences(left, right)
            if offsets:
                differences[domain] = offsets
        if differences != EXPECTED_DIFFS[phase]:
            raise ValueError(f"motion parameter {phase} memory isolation mismatch")
        memory[phase] = differences

    for phase in PHASES:
        task_values = []
        shadow_values = []
        hardware_values = []
        for variant in VARIANTS:
            phase_root = source / f"runs/{variant}/output/{phase}"
            task = (phase_root / "capture-task-pool.bin").read_bytes()
            shadow = (phase_root / "capture-shadow-oam.bin").read_bytes()
            hardware = (phase_root / "capture-hardware-oam.bin").read_bytes()
            task_values.append(struct.unpack_from("<h", task, 126 * 0x3C + 6)[0])
            shadow_values.append(shadow[0])
            hardware_values.append(hardware[0])
        if task_values != [64, 96] or shadow_values != [80, 112]:
            raise ValueError("motion parameter task/OAM y propagation mismatch")
        expected_hardware = [80, 112] if phase == "ack-post" else [40, 40]
        if hardware_values != expected_hardware:
            raise ValueError("motion parameter OAM transaction mismatch")

    rendered = {
        variant: render_checkpoint(
            source / f"runs/{variant}/output/ack-post/capture.ss9"
        )[0]
        for variant in VARIANTS
    }
    pixels = pixel_summary(rendered["baseline"], rendered["candidate"])
    if pixels["count"] != 286 or pixels["bbox"] != [54, 88, 72, 107]:
        raise ValueError("motion parameter final Mode 0 pixel contract mismatch")

    output.mkdir(parents=True, exist_ok=True)
    for variant in VARIANTS:
        Image.frombytes("RGB", (240, 160), rendered[variant]).save(
            output / f"{variant}.png", optimize=False
        )
    inventory = write_tar(source, raw_paths(source), output / "raw.tar")
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "verified": True,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": sha256_file(profile_path),
        "bank": {
            "path": profile["source_bank"],
            "extraction_sha256": profile["source_bank_sha256"],
            "current_sha256": sha256_file(root / profile["source_bank"]),
            "historical_slug": "palettes",
            "actual_identity": "motion/effect parameters",
            "table_offset": profile["table_offset"],
            "entry_count": 15,
            "entry_size": 10,
        },
        "scope": {
            "natural_gameplay_route": True,
            "player_visible_runtime": True,
            "record_0_y_offset_runtime_verified": True,
            "all_records_runtime_verified": False,
            "all_consumer_routes_runtime_verified": False,
            "physical_gba_verified": False,
        },
        "static_chain": {
            "sequence_id": 3,
            "consumer_entry": profile["consumer_entry"],
            "child_spawn_function": profile["child_spawn_function"],
            "table_address": "0x0853EE98",
        },
        "input": {
            "mode": "zero-input-active-state",
            "inputs": [],
            "path": profile["input_state"],
            "sha256": profile["input_state_sha256"],
            "evidence": profile["input_evidence"],
            "evidence_sha256": profile["input_evidence_sha256"],
        },
        "edit": build["edit"],
        "build": {
            "manifest_sha256": sha256_file(source / "build/build-manifest.json"),
            "probe_free": True,
            "baseline_is_base_rom": True,
            "changed_rom_offsets": [0x53EE9C],
        },
        "run_budget": batch["run_budget"],
        "runs": runs,
        "runtime": {
            "memory_differences": memory,
            "task_slot": 126,
            "task_address": "0x03005940",
            "task_field_offset": 6,
            "task_y_values": [64, 96],
            "oam_index": 0,
            "oam_y_values": [80, 112],
            "y_delta": 32,
            "pixel_render_source": "offline-mode0-from-ack-savestate",
            "pixel_change_count": pixels["count"],
            "pixel_change_bbox": pixels["bbox"],
            "pixel_changes_sha256": pixels["changes_sha256"],
            "baseline_rgb_sha256": sha256_bytes(rendered["baseline"]),
            "candidate_rgb_sha256": sha256_bytes(rendered["candidate"]),
        },
        "raw_inventory": inventory,
        "boundary": profile["boundary"],
    }
    write_json(output / "evidence.json", evidence)
    artifact_relative = "artifacts/motion-effect-parameter-pixel-ab-v1"
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": EVIDENCE_SCHEMA,
        "artifact_status": "accepted",
        "files": {
            name: sha256_file(output / name)
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
        },
        "repository_files": {
            path: sha256_file(root / path) for path in IMPLEMENTATION_PATHS
        },
        "profile": evidence["profile"],
        "profile_sha256": evidence["profile_sha256"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_motion_effect_parameter_pixel_ab.py",
                "--root",
                ".",
                "--artifact",
                artifact_relative,
            ],
            "exit_code": 0,
        },
        "boundary": profile["boundary"],
    }
    write_json(output / "manifest.json", manifest)
    return evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = export_evidence(args.root, args.profile, args.source, args.output)
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
