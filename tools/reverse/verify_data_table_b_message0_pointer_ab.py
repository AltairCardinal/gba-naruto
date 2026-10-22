#!/usr/bin/env python3
"""Verify the natural action-7 data-table-b message pointer pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_battle_message_runtime_probe import (
    HOOK,
    MAGIC,
    MESSAGE_COUNT,
    MESSAGE_TABLE,
    MESSAGE_TABLE_BUS,
    SCRATCH,
    build_probe,
)
from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint


ARTIFACT_ID = "data-table-b-message0-pointer-pixel-ab-v1"
ARTIFACT_SCHEMA = "data-table-b-message0-pointer-pixel-ab-artifact-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
BINARY_PATH = Path("/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA")
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
SCRIPT_PATH = Path("tools/mgba_input_sequence_replay.lua")
INPUT_PATH = Path(
    "artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9"
)
INPUT_SHA256 = "2b800fe1609923966c7e3898cc8bc81c67e106e3f04a93afed919ed950e5ae71"
MESSAGE_ID = 0
DONOR_ID = 1
CAPTURE_FRAME = 300
SOURCE_DIRS = {"baseline": "action7", "candidate": "action7-candidate"}
ROM_NAMES = {"baseline": "probe.gba", "candidate": "candidate.gba"}
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
    "tools/build_battle_message_runtime_probe.py",
    "tools/export_data_table_b_message0_pointer_ab.py",
    "tools/verify_data_table_b_message0_pointer_ab.py",
    "tools/inspect_mgba_savestate.py",
    "tools/mgba_input_sequence_replay.lua",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/run_guarded.py",
    "tests/test_build_battle_message_runtime_probe.py",
    "tests/test_data_table_b_message0_pointer_ab_artifact.py",
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verifier_command() -> list[str]:
    return [
        "python3",
        "tools/verify_data_table_b_message0_pointer_ab.py",
        f"artifacts/{ARTIFACT_ID}",
        "--binary",
        str(BINARY_PATH),
    ]


def extract_raw(archive_path: Path, output: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(members) != len(RAW_FILES) or len(set(names)) != len(names):
            raise ValueError("data-table-b raw archive contains duplicate members")
        if set(names) != RAW_FILES:
            raise ValueError("data-table-b raw file set mismatch")
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
                raise ValueError("data-table-b raw archive member mismatch")
        archive.extractall(output, filter="data")


def validate_state_png_pair(state_path: Path, png_path: Path, label: str) -> str:
    state_rgb = png_screen_fingerprint(state_path)["rgb_pixels_sha256"]
    png_rgb = png_screen_fingerprint(png_path)["rgb_pixels_sha256"]
    if state_rgb != png_rgb:
        raise ValueError(f"data-table-b {label} embedded screen does not match PNG")
    return str(png_rgb)


def _rgb_bytes(path: Path) -> bytes:
    with Image.open(path) as image:
        if image.size != (240, 160):
            raise ValueError("data-table-b PNG dimensions mismatch")
        return image.convert("RGB").tobytes()


def _different_pixels(first: Path, second: Path) -> int:
    before = _rgb_bytes(first)
    after = _rgb_bytes(second)
    return sum(
        before[offset : offset + 3] != after[offset : offset + 3]
        for offset in range(0, len(before), 3)
    )


def _scratch(path: Path) -> dict[str, Any]:
    state = load_gba_state(path)
    raw = state.read_memory(SCRATCH, 36)
    words = [int.from_bytes(raw[offset : offset + 4], "little") for offset in range(0, 36, 4)]
    return {
        "magic": words[0],
        "hit_count": words[1],
        "message_id": words[2],
        "entry_address": words[3],
        "selected_pointer": words[4],
        "target_prefix_hex": raw[20:36].hex(),
    }


def _variant_dir(source: Path, variant: str) -> Path:
    canonical = source / variant
    return canonical if canonical.is_dir() else source / SOURCE_DIRS[variant]


def _input_file(root: Path, source: Path) -> Path:
    local = source / "input.ss9"
    return local if local.is_file() else root / INPUT_PATH


def collect_evidence(
    root: Path, source: Path, *, binary: Path = BINARY_PATH
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not binary.is_file() or sha256_file(binary) != BINARY_SHA256:
        raise ValueError("data-table-b mGBA binary mismatch")
    if binary.resolve() != BINARY_PATH.resolve():
        raise ValueError("data-table-b mGBA binary path mismatch")
    if sha256_file(root / INPUT_PATH) != INPUT_SHA256:
        raise ValueError("data-table-b tracked checkpoint mismatch")
    if sha256_file(_input_file(root, source)) != INPUT_SHA256:
        raise ValueError("data-table-b raw checkpoint mismatch")

    base = (root / "rom/base.gba").read_bytes()
    roms = {
        "baseline": build_probe(base),
        "candidate": build_probe(base, message_id=MESSAGE_ID, replacement_id=DONOR_ID),
    }
    rom_hashes = {name: sha256(payload) for name, payload in roms.items()}
    changed = [
        index
        for index, pair in enumerate(zip(roms["baseline"], roms["candidate"], strict=True))
        if pair[0] != pair[1]
    ]
    if changed != [MESSAGE_TABLE]:
        raise ValueError("data-table-b ROM A/B isolation mismatch")
    baseline_pointer = int.from_bytes(base[MESSAGE_TABLE : MESSAGE_TABLE + 4], "little")
    candidate_pointer = int.from_bytes(
        base[MESSAGE_TABLE + 4 : MESSAGE_TABLE + 8], "little"
    )
    expected_pointers = {
        "baseline": baseline_pointer,
        "candidate": candidate_pointer,
    }
    script_hash = sha256_file(root / SCRIPT_PATH)
    runs: dict[str, Any] = {}
    guards: dict[str, Any] = {}
    for variant in ("baseline", "candidate"):
        runtime = _variant_dir(source, variant)
        for name in (
            "audit.json",
            "done.json",
            "sentinel.json",
            "output.png",
            "output.ss9",
            "guard.json",
        ):
            if not (runtime / name).is_file():
                raise ValueError(f"data-table-b {variant} raw source incomplete")
        audit = read_json(runtime / "audit.json")
        sentinel = read_json(runtime / "sentinel.json")
        done = read_json(runtime / "done.json")
        guard = read_json(runtime / "guard.json")
        command = guard.get("command")
        original_dir = SOURCE_DIRS[variant]
        if (
            audit != sentinel
            or audit.get("status") != "capture-complete"
            or audit.get("success") is not True
            or audit.get("capture_frame") != CAPTURE_FRAME
            or audit.get("inputs")
            != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
            or audit.get("rom_sha256") != rom_hashes[variant]
            or audit.get("input_state_sha256") != INPUT_SHA256
            or audit.get("input_state") != str((root / INPUT_PATH).resolve())
            or not str(audit.get("output_state", "")).endswith(
                f"/{original_dir}/output.ss9"
            )
            or not str(audit.get("output_png", "")).endswith(
                f"/{original_dir}/output.png"
            )
            or not str(audit.get("audit", "")).endswith(
                f"/{original_dir}/audit.json"
            )
            or not str(audit.get("sentinel", "")).endswith(
                f"/{original_dir}/sentinel.json"
            )
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
            or not command[3].endswith(f"/input/{ROM_NAMES[variant]}")
        ):
            raise ValueError(f"data-table-b {variant} provenance mismatch")
        scratch = _scratch(runtime / "output.ss9")
        pointer = expected_pointers[variant]
        pointer_offset = pointer - 0x08000000
        expected_prefix = base[pointer_offset : pointer_offset + 16].hex()
        expected_scratch = {
            "magic": MAGIC,
            "hit_count": 1,
            "message_id": MESSAGE_ID,
            "entry_address": MESSAGE_TABLE_BUS,
            "selected_pointer": pointer,
            "target_prefix_hex": expected_prefix,
        }
        if scratch != expected_scratch:
            raise ValueError(f"data-table-b {variant} selector scratch mismatch")
        rgb_hash = validate_state_png_pair(
            runtime / "output.ss9", runtime / "output.png", variant
        )
        runs[variant] = {
            "rom_sha256": rom_hashes[variant],
            "audit_sha256": sha256_file(runtime / "audit.json"),
            "done_sha256": sha256_file(runtime / "done.json"),
            "sentinel_sha256": sha256_file(runtime / "sentinel.json"),
            "state_sha256": sha256_file(runtime / "output.ss9"),
            "png_sha256": sha256_file(runtime / "output.png"),
            "rgb_sha256": rgb_hash,
            "guard_sha256": sha256_file(runtime / "guard.json"),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            "scratch": scratch,
        }
        guards[variant] = {
            "guard_sha256": runs[variant]["guard_sha256"],
            "rom_sha256": rom_hashes[variant],
            "binary_command_path_sha256": sha256(command[0].encode()),
            "script_command_path_sha256": sha256(command[2].encode()),
        }

    baseline_png = _variant_dir(source, "baseline") / "output.png"
    candidate_png = _variant_dir(source, "candidate") / "output.png"
    different_pixel_count = _different_pixels(baseline_png, candidate_png)
    if different_pixel_count != 928:
        raise ValueError("data-table-b final pixel difference mismatch")
    launch = {
        "schema": "data-table-b-message0-pointer-launch-identity-v1",
        "binary": {
            "basename": "mGBA",
            "sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
        },
        "script": {"repository_path": SCRIPT_PATH.as_posix(), "sha256": script_hash},
        "guards": guards,
    }
    existing_launch = source / "launch-identity.json"
    if existing_launch.is_file() and read_json(existing_launch) != launch:
        raise ValueError("data-table-b launch identity mismatch")
    evidence = {
        "schema": "data-table-b-message0-pointer-pixel-ab-evidence-v1",
        "verified": True,
        "bank": {
            "rom_offset": MESSAGE_TABLE,
            "record_count": MESSAGE_COUNT,
            "record_size": 4,
            "end_offset_exclusive": MESSAGE_TABLE + MESSAGE_COUNT * 4,
        },
        "natural_route": {
            "checkpoint": INPUT_PATH.as_posix(),
            "checkpoint_sha256": INPUT_SHA256,
            "action": "confirmed natural action 7 (shadow clone)",
            "input": {"key": "A", "down_frame": 5, "up_frame": 13},
            "selector_hook": f"0x{HOOK:08X}",
            "renderer": "0x08098290",
        },
        "edit": {
            "message_id": MESSAGE_ID,
            "field": "text_ptr",
            "rom_offset": MESSAGE_TABLE,
            "baseline_pointer": f"0x{baseline_pointer:08X}",
            "candidate_donor_id": DONOR_ID,
            "candidate_pointer": f"0x{candidate_pointer:08X}",
            "changed_rom_offsets": changed,
        },
        "runtime_effect": {
            "selector_hit_count_each": 1,
            "selected_entry_address": f"0x{MESSAGE_TABLE_BUS:08X}",
            "baseline_rgb_sha256": runs["baseline"]["rgb_sha256"],
            "candidate_rgb_sha256": runs["candidate"]["rgb_sha256"],
            "different_pixel_count": different_pixel_count,
            "visible_message_changed": True,
        },
        "emulator": {
            "binary_sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": script_hash,
        },
        "runs": runs,
        "scope": {
            "natural_action7_consumer_verified": True,
            "message0_pointer_causal_visible_difference_verified": True,
            "all_79_messages_naturally_exercised": False,
            "natural_language_decoding_claimed": False,
            "external_cryptographic_attestation_claimed": False,
            "physical_gba_verified": False,
        },
    }
    return evidence, launch


def verify_artifact(
    root: Path, artifact: Path, *, binary: Path = BINARY_PATH
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    manifest = read_json(artifact / "manifest.json")
    if manifest.get("artifact_id") != ARTIFACT_ID:
        raise ValueError("data-table-b manifest artifact ID mismatch")
    if manifest.get("artifact_schema") != ARTIFACT_SCHEMA:
        raise ValueError("data-table-b manifest artifact schema mismatch")
    if manifest.get("schema") != PROMOTION_SCHEMA:
        raise ValueError("data-table-b manifest promotion schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("data-table-b manifest status mismatch")
    expected_files = {"baseline.png", "candidate.png", "evidence.json", "raw.tar"}
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != expected_files:
        raise ValueError("data-table-b manifest file set mismatch")
    for name, expected in files.items():
        if sha256_file(artifact / name) != expected:
            raise ValueError(f"data-table-b manifest hash mismatch: {name}")
    implementation = manifest.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != IMPLEMENTATION_FILES:
        raise ValueError("data-table-b implementation file set mismatch")
    for name, expected in implementation.items():
        if sha256_file(root / name) != expected:
            raise ValueError(f"data-table-b implementation hash mismatch: {name}")
    if manifest.get("verifier") != {"command": verifier_command(), "exit_code": 0}:
        raise ValueError("data-table-b verifier evidence mismatch")

    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "raw"
        raw.mkdir()
        extract_raw(artifact / "raw.tar", raw)
        expected_evidence, _ = collect_evidence(root, raw, binary=Path(binary))
        if (artifact / "baseline.png").read_bytes() != (
            raw / "baseline/output.png"
        ).read_bytes():
            raise ValueError("data-table-b baseline PNG mismatch")
        if (artifact / "candidate.png").read_bytes() != (
            raw / "candidate/output.png"
        ).read_bytes():
            raise ValueError("data-table-b candidate PNG mismatch")
    if read_json(artifact / "evidence.json") != expected_evidence:
        raise ValueError("data-table-b evidence mismatch")
    return {
        "verified": True,
        "message_id": MESSAGE_ID,
        "different_pixel_count": expected_evidence["runtime_effect"][
            "different_pixel_count"
        ],
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
