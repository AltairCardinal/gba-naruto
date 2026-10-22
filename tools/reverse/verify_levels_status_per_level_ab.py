#!/usr/bin/env python3
"""Independently verify the controlled status-caller levels runtime A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_levels_runtime_probe import (
    EXPECTED_PER_LEVEL_A,
    HOOK,
    LEVELS_TABLE,
    SCRATCH,
    TARGET_LEVEL,
    TARGET_RECORD_ID,
    TARGET_TYPE,
    build_probe,
)
from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ARTIFACT_ID = "levels-status-per-level-ab-v1"
ARTIFACT_SCHEMA = "levels-status-per-level-ab-artifact-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
BINARY_PATH = Path("/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA")
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
SCRIPT_PATH = Path("tools/mgba_input_sequence_replay.lua")
INPUT_PATH = Path("artifacts/runtime-checkpoints/scenario-41-action-menu-0.ss9")
INPUT_SHA256 = "863737740529a3fbd74931acdbc6eca822e4d01c09772e11a5800ab0097537ab"
PATCH_OFFSET = LEVELS_TABLE + TARGET_RECORD_ID * 12 + 6
RAW_FILES = {
    "input.ss9",
    "baseline/audit.json",
    "baseline/done.json",
    "baseline/sentinel.json",
    "baseline/output.png",
    "baseline/output.ss9",
    "baseline/guard.json",
    "candidate/audit.json",
    "candidate/done.json",
    "candidate/sentinel.json",
    "candidate/output.png",
    "candidate/output.ss9",
    "candidate/guard.json",
    "launch-identity.json",
}
IMPLEMENTATION_FILES = {
    "tools/build_levels_runtime_probe.py",
    "tools/export_levels_status_per_level_ab.py",
    "tools/verify_levels_status_per_level_ab.py",
    "tools/inspect_mgba_savestate.py",
    "tools/mgba_input_sequence_replay.lua",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/run_guarded.py",
    "tests/test_build_levels_runtime_probe.py",
    "tests/test_levels_status_per_level_ab_artifact.py",
}


def _verifier_command() -> list[str]:
    return [
        "python3",
        "tools/verify_levels_status_per_level_ab.py",
        f"artifacts/{ARTIFACT_ID}",
        "--binary",
        str(BINARY_PATH),
    ]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def extract_raw(archive_path: Path, output: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(members) != len(RAW_FILES) or len(set(names)) != len(names):
            raise ValueError("levels raw archive contains duplicate members")
        if {member.name for member in members} != RAW_FILES:
            raise ValueError("levels raw file set mismatch")
        for member in members:
            target = Path(member.name)
            if (
                not member.isfile()
                or target.is_absolute()
                or ".." in target.parts
                or member.uid != 0
                or member.gid != 0
                or member.mtime != 0
                or member.mode != 0o644
            ):
                raise ValueError("levels raw archive member mismatch")
        archive.extractall(output, filter="data")


def validate_state_png_pair(state_path: Path, png_path: Path, label: str) -> str:
    state_rgb = png_screen_fingerprint(state_path)["rgb_pixels_sha256"]
    png_rgb = png_screen_fingerprint(png_path)["rgb_pixels_sha256"]
    if state_rgb != png_rgb:
        raise ValueError(f"levels {label} embedded screen does not match PNG")
    return str(png_rgb)


def _scratch(path: Path) -> dict[str, int]:
    state = load_gba_state(path)
    words = [
        int.from_bytes(state.read_memory(SCRATCH + offset, 4), "little")
        for offset in range(0, 40, 4)
    ]
    keys = (
        "magic",
        "hit_count",
        "template",
        "target_type",
        "output_pointer",
        "return_value",
        "output_a",
        "output_b",
        "packed_record_level",
        "reserved",
    )
    return dict(zip(keys, words, strict=True))


def _collect(root: Path, raw: Path, binary: Path) -> dict[str, Any]:
    if not binary.is_file() or _sha256_file(binary) != BINARY_SHA256:
        raise ValueError("levels mGBA binary mismatch")
    if binary.resolve() != BINARY_PATH.resolve():
        raise ValueError("levels mGBA binary path mismatch")
    if _sha256_file(raw / "input.ss9") != INPUT_SHA256:
        raise ValueError("levels raw input checkpoint mismatch")
    if _sha256_file(root / INPUT_PATH) != INPUT_SHA256:
        raise ValueError("levels tracked input checkpoint mismatch")

    base = (root / "rom/base.gba").read_bytes()
    roms = {
        "baseline": build_probe(base),
        "candidate": build_probe(base, per_level_a=0),
    }
    rom_hashes = {name: _sha256(payload) for name, payload in roms.items()}
    differences = [
        index
        for index, pair in enumerate(zip(roms["baseline"], roms["candidate"], strict=True))
        if pair[0] != pair[1]
    ]
    if differences != [PATCH_OFFSET]:
        raise ValueError("levels rebuilt ROM isolation mismatch")

    runs: dict[str, Any] = {}
    guards: dict[str, Any] = {}
    results: dict[str, int] = {}
    script_hash = _sha256_file(root / SCRIPT_PATH)
    common = {
        "magic": 0x5250564C,
        "hit_count": 1,
        "template": 0x02024294,
        "target_type": TARGET_TYPE,
        "output_pointer": 0x0300120C,
        "return_value": 0,
        "output_b": 0,
        "packed_record_level": TARGET_RECORD_ID | (TARGET_LEVEL << 8),
        "reserved": 0,
    }
    for variant, expected_result in (("baseline", 18), ("candidate", 2)):
        runtime = raw / variant
        audit = _read_json(runtime / "audit.json")
        sentinel = _read_json(runtime / "sentinel.json")
        done = _read_json(runtime / "done.json")
        guard = _read_json(runtime / "guard.json")
        command = guard.get("command")
        if (
            audit != sentinel
            or audit.get("status") != "capture-complete"
            or audit.get("success") is not True
            or audit.get("capture_frame") != 120
            or audit.get("inputs") != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
            or audit.get("rom_sha256") != rom_hashes[variant]
            or audit.get("input_state_sha256") != INPUT_SHA256
            or audit.get("input_state") != str((root / INPUT_PATH).resolve())
            or not str(audit.get("output_state", "")).endswith(f"/{variant}/output.ss9")
            or not str(audit.get("output_png", "")).endswith(f"/{variant}/output.png")
            or not str(audit.get("audit", "")).endswith(f"/{variant}/audit.json")
            or not str(audit.get("sentinel", "")).endswith(f"/{variant}/sentinel.json")
            or done.get("status") != "capture-complete"
            or guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("completion_trigger") != "success-marker"
            or guard.get("protection_backend") != "posix-process-group"
            or guard.get("degraded") is not False
            or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
            or guard["peak_tree_rss_mib"] > 512
            or not isinstance(command, list)
            or len(command) != 4
            or command[0] != str(BINARY_PATH)
            or command[1] != "--script"
            or command[2] != str((root / SCRIPT_PATH).resolve())
            or not command[3].endswith(f"/input/{variant}.gba")
        ):
            raise ValueError(f"levels {variant} provenance mismatch")
        scratch = _scratch(runtime / "output.ss9")
        for key, expected in common.items():
            if scratch.get(key) != expected:
                raise ValueError(f"levels {variant} scratch {key} mismatch")
        if scratch["output_a"] != expected_result:
            raise ValueError(f"levels {variant} query result mismatch")
        state = load_gba_state(runtime / "output.ss9")
        if state.read_memory(0x020242E4, 4) != b"\x01\xff\x00\x00":
            raise ValueError(f"levels {variant} live slot restoration mismatch")
        results[variant] = expected_result
        rgb_sha256 = validate_state_png_pair(
            runtime / "output.ss9", runtime / "output.png", variant
        )
        guard_hash = _sha256_file(runtime / "guard.json")
        runs[variant] = {
            "rom_sha256": rom_hashes[variant],
            "audit_sha256": _sha256_file(runtime / "audit.json"),
            "done_sha256": _sha256_file(runtime / "done.json"),
            "sentinel_sha256": _sha256_file(runtime / "sentinel.json"),
            "state_sha256": _sha256_file(runtime / "output.ss9"),
            "png_sha256": _sha256_file(runtime / "output.png"),
            "rgb_sha256": rgb_sha256,
            "guard_sha256": guard_hash,
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        }
        guards[variant] = {
            "guard_sha256": guard_hash,
            "rom_sha256": rom_hashes[variant],
            "binary_command_path_sha256": _sha256(command[0].encode()),
            "script_command_path_sha256": _sha256(command[2].encode()),
        }
    if runs["baseline"]["rgb_sha256"] != runs["candidate"]["rgb_sha256"]:
        raise ValueError("levels final screen mismatch")
    launch = {
        "schema": "levels-status-per-level-launch-identity-v1",
        "binary": {"basename": "mGBA", "sha256": BINARY_SHA256, "source_commit": BINARY_COMMIT},
        "script": {"repository_path": SCRIPT_PATH.as_posix(), "sha256": script_hash},
        "guards": guards,
    }
    if _read_json(raw / "launch-identity.json") != launch:
        raise ValueError("levels launch identity mismatch")
    evidence = {
        "schema": "levels-status-per-level-ab-evidence-v1",
        "verified": True,
        "bank": {
            "rom_offset": LEVELS_TABLE,
            "record_count": 45,
            "record_size": 12,
            "end_offset_exclusive": LEVELS_TABLE + 45 * 12,
        },
        "controlled_materialization": {
            "natural_call_site": f"0x{HOOK:08X}",
            "query": "0x0806DDA4",
            "record_id": TARGET_RECORD_ID,
            "requested_type": TARGET_TYPE,
            "level": TARGET_LEVEL,
            "temporary_live_slot": "0x020242E4",
            "slot_restored_after_query": True,
        },
        "edit": {
            "record_id": TARGET_RECORD_ID,
            "field": "per_level_a",
            "rom_offset": PATCH_OFFSET,
            "baseline": EXPECTED_PER_LEVEL_A,
            "candidate": 0,
            "changed_rom_offsets": [PATCH_OFFSET],
        },
        "runtime_effect": {
            "formula": "base_a + per_level_a * (level - 1)",
            "base_a": 2,
            "baseline_output_a": results["baseline"],
            "candidate_output_a": results["candidate"],
            "output_b": 0,
            "query_hit_count_each": 1,
            "final_screen_equal": True,
        },
        "input_checkpoint": {"path": INPUT_PATH.as_posix(), "sha256": INPUT_SHA256},
        "emulator": {
            "binary_sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": script_hash,
        },
        "runs": runs,
        "scope": {
            "real_natural_type_call_site_verified": True,
            "controlled_record_materialization_verified": True,
            "per_level_a_runtime_formula_verified": True,
            "natural_unlock_or_training_ui_claimed": False,
            "visible_pixel_difference_claimed": False,
            "external_cryptographic_attestation_claimed": False,
            "physical_gba_verified": False,
        },
    }
    return evidence


def verify_artifact(
    root: Path, artifact: Path, *, binary: Path = BINARY_PATH
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    manifest = _read_json(artifact / "manifest.json")
    if manifest.get("artifact_id") != ARTIFACT_ID:
        raise ValueError("levels manifest artifact ID mismatch")
    if manifest.get("artifact_schema") != ARTIFACT_SCHEMA:
        raise ValueError("levels manifest artifact schema mismatch")
    if manifest.get("schema") != PROMOTION_SCHEMA:
        raise ValueError("levels manifest promotion schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("levels manifest status mismatch")
    expected_files = {"baseline.png", "candidate.png", "evidence.json", "raw.tar"}
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != expected_files:
        raise ValueError("levels manifest file set mismatch")
    for name, expected in files.items():
        if _sha256_file(artifact / name) != expected:
            raise ValueError(f"levels manifest hash mismatch: {name}")
    implementation = manifest.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != IMPLEMENTATION_FILES:
        raise ValueError("levels implementation file set mismatch")
    for name, expected in implementation.items():
        if _sha256_file(root / name) != expected:
            raise ValueError(f"levels implementation hash mismatch: {name}")
    if manifest.get("verifier") != {
        "command": _verifier_command(),
        "exit_code": 0,
    }:
        raise ValueError("levels verifier evidence mismatch")

    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "raw"
        raw.mkdir()
        extract_raw(artifact / "raw.tar", raw)
        expected_evidence = _collect(root, raw, Path(binary))
        if (artifact / "baseline.png").read_bytes() != (raw / "baseline/output.png").read_bytes():
            raise ValueError("levels baseline PNG mismatch")
        if (artifact / "candidate.png").read_bytes() != (raw / "candidate/output.png").read_bytes():
            raise ValueError("levels candidate PNG mismatch")
    if _read_json(artifact / "evidence.json") != expected_evidence:
        raise ValueError("levels evidence mismatch")
    return {
        "verified": True,
        "baseline_output_a": expected_evidence["runtime_effect"]["baseline_output_a"],
        "candidate_output_a": expected_evidence["runtime_effect"]["candidate_output_a"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--binary", type=Path, default=BINARY_PATH)
    args = parser.parse_args()
    print(json.dumps(verify_artifact(ROOT, args.artifact, binary=args.binary), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
