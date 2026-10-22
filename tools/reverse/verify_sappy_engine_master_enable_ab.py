#!/usr/bin/env python3
"""Independently verify the Sappy initializer master-enable runtime A/B."""
from __future__ import annotations

import argparse
import copy
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

from tools.build_sappy_engine_master_enable_ab import PATCH_OFFSET, build_pair
from tools.inspect_mgba_savestate import load_gba_state


ARTIFACT_ID = "sappy-engine-master-enable-ab-v1"
BINARY_PATH = Path("/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA")
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
SCRIPT_PATH = Path("tools/mgba_sappy_engine_master_enable_trace.lua")
AUDIO_EVIDENCE_PATH = Path("artifacts/audio/mgba-sound101-full-differential.json")
EXPECTED_FIRST_PCM_SHA256 = "8889eb3cdd3d0ac94711b47ce78b430d8e23a7b31ecc994c56d0c3310c87674a"
RAW_FILES = {
    "input-disclaimer.ss9",
    "baseline/audit.json",
    "baseline/done.json",
    "baseline/frame.png",
    "baseline/output.ss9",
    "baseline/guard.json",
    "candidate/audit.json",
    "candidate/done.json",
    "candidate/frame.png",
    "candidate/output.ss9",
    "candidate/guard.json",
    "launch-identity.json",
}
IMPLEMENTATION_FILES = {
    "tools/build_controlled_audio_runtime_probe.py",
    "tools/build_sappy_engine_master_enable_ab.py",
    "tools/export_sappy_engine_master_enable_ab.py",
    "tools/verify_sappy_engine_master_enable_ab.py",
    "tools/inspect_mgba_savestate.py",
    "tools/mgba_sappy_engine_master_enable_trace.lua",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/run_guarded.py",
    "tests/test_build_sappy_engine_master_enable_ab.py",
    "tests/test_mgba_sappy_engine_master_enable_trace_script.py",
    "tests/test_sappy_engine_master_enable_ab_artifact.py",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _extract_raw(archive_path: Path, output: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        if {member.name for member in members} != RAW_FILES:
            raise ValueError("Sappy raw file set mismatch")
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
                raise ValueError("Sappy raw archive member mismatch")
        archive.extractall(output, filter="data")


def _pcm_hash(soundmain: dict[str, Any]) -> str:
    right = bytes.fromhex(soundmain["right_hex"])
    left = bytes.fromhex(soundmain["left_hex"])
    if len(right) != 264 or len(left) != 264:
        raise ValueError("Sappy FIFO size mismatch")
    pcm = bytearray()
    for right_sample, left_sample in zip(right, left, strict=True):
        pcm.extend((right_sample, left_sample))
    return _sha256(bytes(pcm))


def _collect(root: Path, raw: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_rom, candidate_rom = build_pair(
        (root / "rom/base.gba").read_bytes(), sound_id=101
    )
    roms = {"baseline": baseline_rom, "candidate": candidate_rom}
    rom_hashes = {name: _sha256(payload) for name, payload in roms.items()}
    if [
        index
        for index, pair in enumerate(zip(baseline_rom, candidate_rom, strict=True))
        if pair[0] != pair[1]
    ] != [PATCH_OFFSET]:
        raise ValueError("Sappy rebuilt ROM isolation mismatch")
    script_sha256 = _sha256_file(root / SCRIPT_PATH)
    input_sha256 = _sha256_file(raw / "input-disclaimer.ss9")
    input_state = load_gba_state(raw / "input-disclaimer.ss9")
    if (
        input_state.read_memory(0x04000084, 2) != b"\x00\x00"
        or input_state.read_memory(0x03006570, 4) != b"\x00\x00\x00\x00"
    ):
        raise ValueError("Sappy input checkpoint is not pre-initialization")

    audio_dependency = _read_json(root / AUDIO_EVIDENCE_PATH)
    if (
        audio_dependency.get("all_chunks_match") is not True
        or audio_dependency.get("matched_chunk_count") != 79
        or audio_dependency.get("comparisons", [{}])[0].get("expected_pcm_sha256")
        != EXPECTED_FIRST_PCM_SHA256
    ):
        raise ValueError("Sappy downstream audio evidence mismatch")

    audits: dict[str, dict[str, Any]] = {}
    runs = {}
    expected_guards = {}
    for variant in ("baseline", "candidate"):
        runtime = raw / variant
        audit = _read_json(runtime / "audit.json")
        done = _read_json(runtime / "done.json")
        guard = _read_json(runtime / "guard.json")
        command = guard.get("command")
        if (
            audit.get("schema") != "sappy-engine-master-enable-trace-v1"
            or audit.get("variant") != variant
            or audit.get("outcome") != "capture-complete"
            or audit.get("missing") != []
            or audit.get("frame") != 53
            or audit.get("sound_id") != 101
            or audit.get("inputs") != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
            or audit.get("rom_sha256") != rom_hashes[variant]
            or audit.get("script_sha256") != script_sha256
            or audit.get("input_state_sha256") != input_sha256
            or done.get("outcome") != "capture-complete"
            or done.get("missing_count") != 0
            or guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("completion_trigger") != "success-marker"
            or guard.get("protection_backend") != "posix-process-group"
            or guard.get("degraded") is not False
            or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
            or guard["peak_tree_rss_mib"] > 512
            or not isinstance(command, list)
            or len(command) != 4
            or Path(command[0]).name != "mGBA"
            or command[1] != "--script"
            or Path(command[2]).name != SCRIPT_PATH.name
            or not command[3].endswith(f"/{variant}/staged.gba")
        ):
            raise ValueError(f"Sappy {variant} provenance mismatch")
        entry = audit.get("initializer_entry", {})
        exit_event = audit.get("initializer_exit", {})
        dispatch = audit.get("dispatch", {})
        soundmain = audit.get("soundmain", {})
        if (
            (entry.get("pc"), entry.get("lr"), entry.get("r0"))
            != ("0x0809AE3E", "0x0809AA55", "0x03006570")
            or exit_event.get("pc") != "0x0809AEF4"
            or (dispatch.get("pc"), dispatch.get("lr"), dispatch.get("r0"))
            != ("0x0809AAC2", "0x0809E80D", "0x00000065")
            or soundmain.get("pc") != "0x0809AABC"
            or soundmain.get("sound_info_magic") != "0x68736D53"
            or soundmain.get("counter") != "0x00"
            or _pcm_hash(soundmain) != EXPECTED_FIRST_PCM_SHA256
        ):
            raise ValueError(f"Sappy {variant} runtime chain mismatch")
        state = load_gba_state(runtime / "output.ss9")
        if (
            state.read_memory(0x04000084, 2) != b"\x8b\x00"
            or state.read_memory(0x03006570, 4) != b"Smsh"
        ):
            raise ValueError(f"Sappy {variant} output checkpoint mismatch")
        audits[variant] = audit
        guard_sha256 = _sha256_file(runtime / "guard.json")
        expected_guards[variant] = {
            "guard_sha256": guard_sha256,
            "staged_rom_sha256": rom_hashes[variant],
            "binary_command_path_sha256": _sha256(command[0].encode()),
            "script_command_path_sha256": _sha256(command[2].encode()),
        }
        runs[variant] = {
            "rom_sha256": rom_hashes[variant],
            "audit_sha256": _sha256_file(runtime / "audit.json"),
            "done_sha256": _sha256_file(runtime / "done.json"),
            "state_sha256": _sha256_file(runtime / "output.ss9"),
            "png_sha256": _sha256_file(runtime / "frame.png"),
            "guard_sha256": guard_sha256,
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        }

    comparable = copy.deepcopy(audits["candidate"])
    comparable["variant"] = "baseline"
    comparable["run_id"] = audits["baseline"]["run_id"]
    comparable["rom_sha256"] = audits["baseline"]["rom_sha256"]
    comparable["initializer_exit"]["io"]["soundcnt_x"] = "0x0080"
    if comparable != audits["baseline"]:
        raise ValueError("Sappy runtime A/B changed outside the target gate")
    if (
        audits["candidate"]["initializer_exit"]["io"]["soundcnt_x"] != "0x0000"
        or audits["baseline"]["soundmain"]["io"]["soundcnt_x"] != "0x008B"
        or audits["candidate"]["soundmain"]["io"]["soundcnt_x"] != "0x008B"
    ):
        raise ValueError("Sappy runtime gate effect mismatch")
    launch = {
        "schema": "sappy-engine-master-enable-launch-identity-v1",
        "binary": {
            "basename": "mGBA",
            "sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
        },
        "script": {
            "repository_path": SCRIPT_PATH.as_posix(),
            "sha256": script_sha256,
        },
        "guards": expected_guards,
    }
    if _read_json(raw / "launch-identity.json") != launch:
        raise ValueError("Sappy launch identity mismatch")
    evidence = {
        "schema": "sappy-engine-master-enable-ab-evidence-v1",
        "verified": True,
        "actual_identity": "0x0809AE3C..0x0809AEF3 FIFO/DMA audio initializer code",
        "function": {
            "rom_offset": PATCH_OFFSET - 0x3A,
            "entry_address": "0x0809AE3C",
            "return_address": "0x0809AEF2",
            "size": 184,
        },
        "edit": {
            "rom_offset": PATCH_OFFSET,
            "instruction_address": "0x0809AE76",
            "before_halfword": "0x208F",
            "after_halfword": "0x200F",
            "changed_rom_offsets": [PATCH_OFFSET],
        },
        "input_checkpoint": {
            "archive_path": "input-disclaimer.ss9",
            "sha256": input_sha256,
            "restored_for_both_variants": True,
        },
        "emulator": {
            "binary_sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": script_sha256,
        },
        "runs": runs,
        "runtime_effect": {
            "baseline_exit_soundcnt_x": "0x0080",
            "candidate_exit_soundcnt_x": "0x0000",
            "baseline_first_soundmain_soundcnt_x": "0x008B",
            "candidate_first_soundmain_soundcnt_x": "0x008B",
            "control_flow_and_fifo_equal": True,
            "first_fifo_pcm_sha256": EXPECTED_FIRST_PCM_SHA256,
        },
        "downstream_audio_evidence": {
            "path": AUDIO_EVIDENCE_PATH.as_posix(),
            "sha256": _sha256_file(root / AUDIO_EVIDENCE_PATH),
            "matched_chunks": 79,
        },
        "scope": {
            "initializer_runtime_identity_verified": True,
            "master_enable_instruction_effect_verified": True,
            "persistent_mute_claimed": False,
            "audible_wav_difference_claimed": False,
            "physical_gba_verified": False,
        },
    }
    return evidence, launch


def _verify(root: Path, artifact: Path, binary: Path | None) -> None:
    root = root.resolve(strict=True)
    artifact = artifact.resolve(strict=True)
    expected_files = {"baseline.png", "candidate.png", "evidence.json", "manifest.json", "raw.tar"}
    if {path.name for path in artifact.iterdir() if path.is_file()} != expected_files:
        raise ValueError("Sappy artifact file set mismatch")
    manifest = _read_json(artifact / "manifest.json")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != "sappy-engine-master-enable-ab-artifact-v1"
        or manifest.get("artifact_id") != ARTIFACT_ID
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("verifier") != {
            "command": ["python3", "tools/verify_sappy_engine_master_enable_ab.py", "--root", ".", "--artifact", f"artifacts/{ARTIFACT_ID}", "--binary", str(BINARY_PATH)],
            "exit_code": 0,
        }
    ):
        raise ValueError("Sappy artifact manifest contract mismatch")
    for name in expected_files - {"manifest.json"}:
        if manifest.get("files", {}).get(name) != _sha256_file(artifact / name):
            raise ValueError(f"Sappy artifact hash mismatch: {name}")
    implementation = manifest.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != IMPLEMENTATION_FILES:
        raise ValueError("Sappy implementation file set mismatch")
    for name, digest in implementation.items():
        if _sha256_file(root / name) != digest:
            raise ValueError(f"Sappy implementation hash mismatch: {name}")
    selected_binary = BINARY_PATH if binary is None else Path(binary)
    if _sha256_file(selected_binary.resolve(strict=True)) != BINARY_SHA256:
        raise ValueError("Sappy supplied mGBA binary mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary) / "raw"
        raw.mkdir()
        _extract_raw(artifact / "raw.tar", raw)
        expected_evidence, _ = _collect(root, raw)
        if _read_json(artifact / "evidence.json") != expected_evidence:
            raise ValueError("Sappy signed evidence mismatch")
        if (
            _sha256_file(artifact / "baseline.png") != _sha256_file(raw / "baseline/frame.png")
            or _sha256_file(artifact / "candidate.png") != _sha256_file(raw / "candidate/frame.png")
        ):
            raise ValueError("Sappy promoted PNG mismatch")


def verify_artifact(root: Path, artifact: Path, binary: Path | None = None) -> dict[str, Any]:
    try:
        _verify(Path(root), Path(artifact), binary)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError) as error:
        return {"errors": [str(error)], "verified": False}
    return {"errors": [], "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--binary", type=Path, default=BINARY_PATH)
    args = parser.parse_args()
    result = verify_artifact(args.root, args.artifact, args.binary)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
