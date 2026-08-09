#!/usr/bin/env python3
"""Promote the controlled status-caller levels per-level runtime A/B."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_levels_runtime_probe import (
    ACTIVATION_OFFSET,
    EXPECTED_PER_LEVEL_A,
    HOOK,
    LEVELS_TABLE,
    SCRATCH,
    STUB_OFFSET,
    STUB_SIZE,
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
RAW_FILES = (
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
)
IMPLEMENTATION_FILES = (
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
)


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


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _scratch(path: Path) -> dict[str, int]:
    state = load_gba_state(path)
    words = [
        int.from_bytes(state.read_memory(SCRATCH + offset, 4), "little")
        for offset in range(0, 40, 4)
    ]
    return {
        "magic": words[0],
        "hit_count": words[1],
        "template": words[2],
        "target_type": words[3],
        "output_pointer": words[4],
        "return_value": words[5],
        "output_a": words[6],
        "output_b": words[7],
        "packed_record_level": words[8],
        "reserved": words[9],
    }


def _validated_state_png_rgb(state_path: Path, png_path: Path, label: str) -> str:
    state_rgb = png_screen_fingerprint(state_path)["rgb_pixels_sha256"]
    png_rgb = png_screen_fingerprint(png_path)["rgb_pixels_sha256"]
    if state_rgb != png_rgb:
        raise ValueError(f"levels {label} embedded screen does not match PNG")
    return str(png_rgb)


def _source_file(root: Path, source: Path, name: str) -> Path:
    if name == "input.ss9":
        local = source / name
        return local if local.is_file() else root / INPUT_PATH
    return source / name


def _collect(root: Path, source: Path) -> dict[str, Any]:
    base = (root / "rom/base.gba").read_bytes()
    baseline_rom = build_probe(base)
    candidate_rom = build_probe(base, per_level_a=0)
    roms = {"baseline": baseline_rom, "candidate": candidate_rom}
    rom_hashes = {name: _sha256(payload) for name, payload in roms.items()}
    changed = [
        index
        for index, pair in enumerate(zip(baseline_rom, candidate_rom, strict=True))
        if pair[0] != pair[1]
    ]
    if changed != [PATCH_OFFSET]:
        raise ValueError("levels ROM A/B isolation mismatch")
    if not BINARY_PATH.is_file() or _sha256_file(BINARY_PATH) != BINARY_SHA256:
        raise ValueError("levels mGBA binary mismatch")
    if _sha256_file(_source_file(root, source, "input.ss9")) != INPUT_SHA256:
        raise ValueError("levels input checkpoint mismatch")

    runs: dict[str, Any] = {}
    scratch: dict[str, dict[str, int]] = {}
    guards: dict[str, Any] = {}
    script_hash = _sha256_file(root / SCRIPT_PATH)
    for variant in ("baseline", "candidate"):
        runtime = source / variant
        for name in ("audit.json", "done.json", "sentinel.json", "output.png", "output.ss9", "guard.json"):
            if not (runtime / name).is_file():
                raise ValueError(f"levels {variant} raw source incomplete")
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
        scratch[variant] = _scratch(runtime / "output.ss9")
        rgb_sha256 = _validated_state_png_rgb(
            runtime / "output.ss9", runtime / "output.png", variant
        )
        runs[variant] = {
            "rom_sha256": rom_hashes[variant],
            "audit_sha256": _sha256_file(runtime / "audit.json"),
            "done_sha256": _sha256_file(runtime / "done.json"),
            "sentinel_sha256": _sha256_file(runtime / "sentinel.json"),
            "state_sha256": _sha256_file(runtime / "output.ss9"),
            "png_sha256": _sha256_file(runtime / "output.png"),
            "rgb_sha256": rgb_sha256,
            "guard_sha256": _sha256_file(runtime / "guard.json"),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        }
        guards[variant] = {
            "guard_sha256": runs[variant]["guard_sha256"],
            "rom_sha256": rom_hashes[variant],
            "binary_command_path_sha256": _sha256(command[0].encode()),
            "script_command_path_sha256": _sha256(command[2].encode()),
        }

    expected_common = {
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
    for variant, value in (("baseline", 18), ("candidate", 2)):
        actual = dict(scratch[variant])
        for key, expected in expected_common.items():
            if actual.get(key) != expected:
                raise ValueError(f"levels {variant} scratch {key} mismatch")
        if actual["output_a"] != value:
            raise ValueError(f"levels {variant} query result mismatch")
        state = load_gba_state(source / variant / "output.ss9")
        if state.read_memory(0x02024294 + 0x50, 4) != b"\x01\xff\x00\x00":
            raise ValueError(f"levels {variant} live slot was not restored")
    if runs["baseline"]["rgb_sha256"] != runs["candidate"]["rgb_sha256"]:
        raise ValueError("levels checkpoint screen unexpectedly differs")
    launch = {
        "schema": "levels-status-per-level-launch-identity-v1",
        "binary": {"basename": "mGBA", "sha256": BINARY_SHA256, "source_commit": BINARY_COMMIT},
        "script": {"repository_path": SCRIPT_PATH.as_posix(), "sha256": script_hash},
        "guards": guards,
    }
    existing = source / "launch-identity.json"
    if existing.is_file() and _read_json(existing) != launch:
        raise ValueError("levels launch identity mismatch")
    return {
        "rom_hashes": rom_hashes,
        "runs": runs,
        "scratch": scratch,
        "script_sha256": script_hash,
        "launch_identity": launch,
    }


def _write_raw_tar(root: Path, source: Path, output: Path, launch: dict[str, Any]) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in RAW_FILES:
            path = _source_file(root, source, name)
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)
        payload = (json.dumps(launch, indent=2, sort_keys=True) + "\n").encode()
        info = tarfile.TarInfo("launch-identity.json")
        info.size = len(payload)
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 0
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(payload))


def _evidence(facts: dict[str, Any]) -> dict[str, Any]:
    return {
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
            "baseline_output_a": 18,
            "candidate_output_a": 2,
            "output_b": 0,
            "query_hit_count_each": 1,
            "final_screen_equal": True,
        },
        "input_checkpoint": {"path": INPUT_PATH.as_posix(), "sha256": INPUT_SHA256},
        "emulator": {
            "binary_sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": facts["script_sha256"],
        },
        "runs": facts["runs"],
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


def export_artifact(root: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("levels artifact output must be absent or empty")
    facts = _collect(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "baseline/output.png", output / "baseline.png")
    shutil.copyfile(source / "candidate/output.png", output / "candidate.png")
    _write_raw_tar(root, source, output / "raw.tar", facts["launch_identity"])
    evidence = _evidence(facts)
    _write_json(output / "evidence.json", evidence)
    files = {
        name: _sha256_file(output / name)
        for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
    }
    manifest = {
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_status": "accepted",
        "files": files,
        "implementation": {
            name: _sha256_file(root / name) for name in IMPLEMENTATION_FILES
        },
        "schema": PROMOTION_SCHEMA,
        "verifier": {
            "command": _verifier_command(),
            "exit_code": 0,
        },
    }
    _write_json(output / "manifest.json", manifest)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    evidence = export_artifact(ROOT, args.source, args.output)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
