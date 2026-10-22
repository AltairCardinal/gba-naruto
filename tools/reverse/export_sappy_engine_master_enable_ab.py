#!/usr/bin/env python3
"""Promote the controlled Sappy initializer master-enable runtime A/B."""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_sappy_engine_master_enable_ab import PATCH_OFFSET, build_pair


ARTIFACT_ID = "sappy-engine-master-enable-ab-v1"
BINARY_PATH = Path("/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA")
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
SCRIPT_PATH = Path("tools/mgba_sappy_engine_master_enable_trace.lua")
AUDIO_EVIDENCE_PATH = Path("artifacts/audio/mgba-sound101-full-differential.json")
EXPECTED_FIRST_PCM_SHA256 = "8889eb3cdd3d0ac94711b47ce78b430d8e23a7b31ecc994c56d0c3310c87674a"
RAW_FILES = (
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
)
IMPLEMENTATION_FILES = (
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
)


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


def _interleaved_pcm_sha256(soundmain: dict[str, Any]) -> str:
    right = bytes.fromhex(soundmain["right_hex"])
    left = bytes.fromhex(soundmain["left_hex"])
    if len(right) != 264 or len(left) != 264:
        raise ValueError("Sappy trace FIFO plane size mismatch")
    pcm = bytearray()
    for right_sample, left_sample in zip(right, left, strict=True):
        pcm.extend((right_sample, left_sample))
    return _sha256(bytes(pcm))


def _launch_identity(source: Path, rom_hashes: dict[str, str]) -> dict[str, Any]:
    guards = {}
    for variant in ("baseline", "candidate"):
        guard_path = source / variant / "guard.json"
        guard = _read_json(guard_path)
        command = guard.get("command")
        if not isinstance(command, list) or len(command) != 4:
            raise ValueError(f"Sappy {variant} guard command mismatch")
        guards[variant] = {
            "guard_sha256": _sha256_file(guard_path),
            "staged_rom_sha256": rom_hashes[variant],
            "binary_command_path_sha256": _sha256(command[0].encode()),
            "script_command_path_sha256": _sha256(command[2].encode()),
        }
    result = {
        "schema": "sappy-engine-master-enable-launch-identity-v1",
        "binary": {
            "basename": "mGBA",
            "sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
        },
        "script": {
            "repository_path": SCRIPT_PATH.as_posix(),
            "sha256": _sha256_file(ROOT / SCRIPT_PATH),
        },
        "guards": guards,
    }
    existing = source / "launch-identity.json"
    if existing.is_file() and _read_json(existing) != result:
        raise ValueError("Sappy launch identity mismatch")
    return result


def _collect(root: Path, source: Path) -> dict[str, Any]:
    base = (root / "rom/base.gba").read_bytes()
    baseline_rom, candidate_rom = build_pair(base, sound_id=101)
    roms = {"baseline": baseline_rom, "candidate": candidate_rom}
    rom_hashes = {name: _sha256(payload) for name, payload in roms.items()}
    changed = [
        index
        for index, pair in enumerate(zip(baseline_rom, candidate_rom, strict=True))
        if pair[0] != pair[1]
    ]
    if changed != [PATCH_OFFSET]:
        raise ValueError("Sappy ROM A/B isolation mismatch")
    if not BINARY_PATH.is_file() or _sha256_file(BINARY_PATH) != BINARY_SHA256:
        raise ValueError("Sappy mGBA binary mismatch")
    script_sha256 = _sha256_file(root / SCRIPT_PATH)
    input_sha256 = _sha256_file(source / "input-disclaimer.ss9")
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
    for variant in ("baseline", "candidate"):
        runtime = source / variant
        if any(not (runtime / name).is_file() for name in ("audit.json", "done.json", "frame.png", "output.ss9", "guard.json")):
            raise ValueError(f"Sappy {variant} raw source incomplete")
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
            or command[0] != str(BINARY_PATH)
            or command[1] != "--script"
            or command[2] != str((root / SCRIPT_PATH).resolve())
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
            or _interleaved_pcm_sha256(soundmain) != EXPECTED_FIRST_PCM_SHA256
        ):
            raise ValueError(f"Sappy {variant} runtime chain mismatch")
        audits[variant] = audit
        runs[variant] = {
            "rom_sha256": rom_hashes[variant],
            "audit_sha256": _sha256_file(runtime / "audit.json"),
            "done_sha256": _sha256_file(runtime / "done.json"),
            "state_sha256": _sha256_file(runtime / "output.ss9"),
            "png_sha256": _sha256_file(runtime / "frame.png"),
            "guard_sha256": _sha256_file(runtime / "guard.json"),
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
        raise ValueError("Sappy master-enable effect mismatch")
    return {
        "rom_hashes": rom_hashes,
        "input_sha256": input_sha256,
        "script_sha256": script_sha256,
        "audio_dependency_sha256": _sha256_file(root / AUDIO_EVIDENCE_PATH),
        "runs": runs,
        "launch_identity": _launch_identity(source, rom_hashes),
    }


def _write_raw_tar(source: Path, output: Path, launch_identity: dict[str, Any]) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in RAW_FILES:
            path = source / name
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)
        payload = (json.dumps(launch_identity, indent=2, sort_keys=True) + "\n").encode()
        info = tarfile.TarInfo("launch-identity.json")
        info.size = len(payload)
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 0
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(payload))


def export_artifact(root: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Sappy artifact output must be absent or empty")
    facts = _collect(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "baseline/frame.png", output / "baseline.png")
    shutil.copyfile(source / "candidate/frame.png", output / "candidate.png")
    _write_raw_tar(source, output / "raw.tar", facts["launch_identity"])
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
            "sha256": facts["input_sha256"],
            "restored_for_both_variants": True,
        },
        "emulator": {
            "binary_sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": facts["script_sha256"],
        },
        "runs": facts["runs"],
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
            "sha256": facts["audio_dependency_sha256"],
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
    _write_json(output / "evidence.json", evidence)
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": "sappy-engine-master-enable-ab-artifact-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_status": "accepted",
        "files": {
            name: _sha256_file(output / name)
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
        },
        "implementation": {
            name: _sha256_file(root / name) for name in IMPLEMENTATION_FILES
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_sappy_engine_master_enable_ab.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
                "--binary",
                str(BINARY_PATH),
            ],
            "exit_code": 0,
        },
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_artifact(args.root, args.source, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
