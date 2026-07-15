#!/usr/bin/env python3
"""Fail-closed acceptance for the scenario 41 prebattle-menu checkpoint."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

try:
    from tools.inspect_mgba_savestate import inspect_savestate, png_screen_fingerprint
    from tools.run_macos_mgba_replay import (
        ReplayError,
        validate_build_manifest,
        validate_guard_summary,
    )
    from tools.thumb_branch import decode_thumb_bl
except ModuleNotFoundError:
    from inspect_mgba_savestate import inspect_savestate, png_screen_fingerprint
    from run_macos_mgba_replay import (
        ReplayError,
        validate_build_manifest,
        validate_guard_summary,
    )
    from thumb_branch import decode_thumb_bl


SOURCE_COMMIT = "26b7884bc25a5933960f3cdcd98bac1ae14d42e2"
BACKPORT_COMMIT = "7cacae126207de5499857439b9c7919bf8e882c2"
EXPECTED_UNWIND = (
    (0x03001220, 0x080885C1, 0x08067158),
    (0x03001240, 0x08088F9F, 0x080884DC),
    (0x03001278, 0x0808F92D, 0x08088F10),
)
CONTROLLER_RETURN = 0x0808F957
CONTROLLER_TARGET = 0x080732B4
STEP2_MANIFEST_PATH = Path(
    "/Users/altair/.cache/codex-tools/mgba/"
    "0.10.5-script-backport-manifest-fix1-20260715.json"
)
STEP2_BINARY_PATH = Path(
    "/Users/altair/.cache/codex-tools/mgba/"
    "0.10.5-script-backport-build-fix1-20260715/qt/"
    "mGBA.app/Contents/MacOS/mGBA"
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_TRACKED_PATCH_PATH = (
    PROJECT_ROOT / "tools/patches/mgba-0.10.5-qt-script-cli.patch"
)
STEP2_SHA256 = {
    "audit": "e2263354cf9f9a0a5b2e532e5b754b246697f9a73c607284ad686a174ab32eae",
    "sentinel": "e2263354cf9f9a0a5b2e532e5b754b246697f9a73c607284ad686a174ab32eae",
    "guard_summary": "17a8c5abfe3e12f829e85119a5ebd3d9f576df6f3e51d5a0adee67651a1a4c2c",
    "input_state": "b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078",
    "output_state": "53ab750fe1c91d8ee2d47dee212aafcd3c3625059d349b2b3a2aa2eb59d23b65",
    "output_png": "6a4a715a35072b0a5d68b8a33de4076598fc67fb435e816516a9b211bb76e5f0",
    "replay_script": "d1d1dbcce947f6a9149963cc947ef76944e5ac9065cb9906e12bd1a2dda173af",
    "build_manifest": "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d",
    "binary": "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408",
    "patch": "e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6",
    "base_rom": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
    "staged_rom": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
}


def step2_paths(root: Path) -> dict[str, Path]:
    replay_dir = root / "build/macos-prebattle-frame80-step2-20260715"
    return {
        "audit": replay_dir / "audit.json",
        "sentinel": replay_dir / "sentinel.json",
        "guard_summary": replay_dir / "guard-summary.json",
        "base_rom": root / "rom/base.gba",
        "input_state": root
        / "artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9",
        "output_state": replay_dir / "frame80.ss9",
        "output_png": replay_dir / "frame80.png",
        "staged_rom": replay_dir / "staged-base.gba",
        "replay_script": root / "tools/mgba_checkpoint_replay.lua",
        "build_manifest": STEP2_MANIFEST_PATH,
        "binary": STEP2_BINARY_PATH,
        "tracked_patch": PROJECT_TRACKED_PATCH_PATH,
    }


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_path(actual: Path | str, expected: Path, label: str) -> None:
    if Path(actual).resolve() != expected.resolve():
        raise ValueError(f"{label} path mismatch")


def _authenticated_file(
    path_value: object, expected_hash: object, label: str
) -> dict[str, str]:
    _require(
        isinstance(path_value, (str, Path)) and bool(str(path_value)),
        f"{label} path missing",
    )
    _require(isinstance(expected_hash, str), f"{label} hash missing")
    path = Path(path_value)
    _require(path.is_file(), f"{label} file missing: {path}")
    actual_hash = sha256_file(path)
    _require(actual_hash == expected_hash, f"{label} hash mismatch")
    return {"path": str(path), "sha256": actual_hash}


def _decode_manifest_patch(manifest: dict[str, object]) -> bytes:
    try:
        command = manifest["guard"]["summaries"]["prepare"]["command"]
        encoded = command[-1]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("manifest has no reproducible backport patch payload") from error
    _require(isinstance(encoded, str), "manifest patch payload is not text")
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("manifest patch payload is not valid base64") from error


def validate_strict_replay(
    audit_path: Path | str,
    rom_path: Path | str,
    guard_summary_path: Path | str,
    *,
    caller_paths: Mapping[str, Path] | None = None,
    caller_hashes: Mapping[str, str] | None = None,
    canonical_tracked_patch_path: Path | str = PROJECT_TRACKED_PATCH_PATH,
) -> dict[str, object]:
    audit_path = Path(audit_path)
    rom_path = Path(rom_path)
    guard_summary_path = Path(guard_summary_path)
    audit = _load_json(audit_path)
    guard = _load_json(guard_summary_path)

    if caller_paths is not None:
        _require_path(audit_path, caller_paths["audit"], "audit")
        _require_path(rom_path, caller_paths["base_rom"], "base ROM")
        _require_path(
            guard_summary_path, caller_paths["guard_summary"], "guard summary"
        )

    _require(audit.get("success") is True, "strict replay did not succeed")
    _require(audit.get("status") == "capture-complete", "strict replay is incomplete")
    _require(
        audit.get("evidence_mode") == "zero-input",
        "replay is not zero-input evidence",
    )
    _require(audit.get("zero_input_verified") is True, "zero-input verification is false")
    _require(audit.get("inputs") == [], "zero-input replay contains inputs")
    _require(audit.get("pre_scripts") == [], "zero-input replay contains pre-scripts")
    _require(
        audit.get("capture_frame") == 80 and audit.get("frame") == 80,
        "strict replay is not a frame-80 capture",
    )
    _require(audit.get("pgid_clean") is True, "replay did not report a clean PGID")
    _require_path(audit.get("audit", ""), audit_path, "audit payload")

    sentinel_value = audit.get("sentinel")
    _require(
        isinstance(sentinel_value, str) and bool(sentinel_value),
        "strict replay sentinel path missing",
    )
    sentinel_path = Path(sentinel_value)
    if caller_paths is not None:
        _require_path(sentinel_path, caller_paths["sentinel"], "sentinel")

    files = {
        "input_state": _authenticated_file(
            audit.get("input_state"), audit.get("input_state_sha256"), "input state"
        ),
        "output_state": _authenticated_file(
            audit.get("output_state"), audit.get("output_state_sha256"), "output state"
        ),
        "output_png": _authenticated_file(
            audit.get("output_png"), audit.get("output_png_sha256"), "output PNG"
        ),
        "staged_rom": _authenticated_file(
            audit.get("staged_rom"), audit.get("staged_rom_sha256"), "staged ROM"
        ),
        "replay_script": _authenticated_file(
            audit.get("replay_script"), audit.get("replay_script_sha256"), "replay script"
        ),
        "build_manifest": _authenticated_file(
            audit.get("build_manifest"),
            audit.get("build_manifest_sha256"),
            "build manifest",
        ),
    }
    if caller_paths is not None:
        _require(
            caller_hashes is not None and "patch" in caller_hashes,
            "caller-known tracked patch hash missing",
        )
        _require_path(
            caller_paths["tracked_patch"],
            Path(canonical_tracked_patch_path),
            "tracked patch",
        )
        tracked_patch = _authenticated_file(
            caller_paths["tracked_patch"],
            caller_hashes["patch"],
            "tracked patch",
        )
        tracked_patch_path = Path(tracked_patch["path"]).resolve()
        try:
            repo_relative_patch = str(tracked_patch_path.relative_to(PROJECT_ROOT))
        except ValueError:
            repo_relative_patch = tracked_patch_path.name
        files["tracked_patch"] = {
            **tracked_patch,
            "repo_relative_path": repo_relative_patch,
        }
    if caller_paths is not None:
        for label in (
            "input_state",
            "output_state",
            "output_png",
            "staged_rom",
            "replay_script",
            "build_manifest",
        ):
            _require_path(files[label]["path"], caller_paths[label], label)
    _require(rom_path.is_file(), f"base ROM file missing: {rom_path}")
    rom_hash = sha256_file(rom_path)
    _require(rom_hash == audit.get("rom_sha256"), "base ROM hash mismatch")
    _require(files["staged_rom"]["sha256"] == rom_hash, "staged ROM differs from base ROM")
    files["base_rom"] = {"path": str(rom_path), "sha256": rom_hash}

    manifest_path = Path(files["build_manifest"]["path"])
    manifest = _load_json(manifest_path)
    _require(
        manifest.get("version") == "0.10.5",
        "emulator manifest is not mGBA 0.10.5",
    )
    _require(manifest.get("source_commit") == SOURCE_COMMIT, "mGBA source commit mismatch")
    _require(
        manifest.get("backport_commit") == BACKPORT_COMMIT,
        "mGBA backport commit mismatch",
    )
    _require(manifest.get("architecture") == "x86_64", "mGBA architecture is not x86_64")

    command = guard.get("command")
    _require(isinstance(command, list) and len(command) == 4, "guard command is incomplete")
    binary = _authenticated_file(command[0], audit.get("binary_sha256"), "emulator binary")
    if caller_paths is not None:
        _require_path(binary["path"], caller_paths["binary"], "emulator binary")
        try:
            manifest_binary = manifest["guard"]["summaries"]["sentinel"]["command"][3]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(
                "manifest has no authenticated sentinel binary path"
            ) from error
        _require_path(
            manifest_binary,
            caller_paths["binary"],
            "manifest authenticated binary",
        )
    try:
        validate_build_manifest(manifest_path, Path(binary["path"]), binary["sha256"])
    except ReplayError as error:
        raise ValueError(f"build manifest validation failed: {error}") from error
    _require(
        binary["sha256"] == manifest.get("binary_sha256"),
        "manifest binary hash mismatch",
    )
    _require(command[1] == "--script", "guard command did not use --script")
    _require(command[2] == files["replay_script"]["path"], "guard script path mismatch")
    _require(command[3] == files["staged_rom"]["path"], "guard staged ROM path mismatch")

    patch = _decode_manifest_patch(manifest)
    patch_hash = hashlib.sha256(patch).hexdigest()
    _require(patch_hash == audit.get("patch_sha256"), "audit patch hash mismatch")
    _require(patch_hash == manifest.get("patch_sha256"), "manifest patch hash mismatch")
    if caller_paths is not None:
        _require(
            Path(files["tracked_patch"]["path"]).read_bytes() == patch,
            "tracked patch bytes differ from manifest embedded patch payload",
        )

    guard_hash = sha256_file(guard_summary_path)
    _require(guard_hash == audit.get("guard_summary_sha256"), "guard summary hash mismatch")
    try:
        validate_guard_summary(guard, command, 0)
    except ReplayError as error:
        raise ValueError(f"guard validation failed: {error}") from error
    peak = guard.get("peak_tree_rss_mib")
    _require(
        isinstance(peak, (int, float))
        and not isinstance(peak, bool)
        and math.isfinite(peak)
        and peak > 0,
        "guard peak RSS must be finite and positive",
    )
    _require(
        guard.get("child_pid") == audit.get("child_pgid"),
        "guard child/PGID mismatch",
    )
    _require(audit.get("peak_tree_rss_mib") == peak, "audit/guard peak RSS mismatch")

    sentinel = _load_json(sentinel_path)
    _require(sentinel == audit, "sentinel content differs from final audit")
    sentinel_record = {
        "path": str(sentinel_path),
        "sha256": sha256_file(sentinel_path),
    }

    actual_hashes = {
        "audit": sha256_file(audit_path),
        "sentinel": sentinel_record["sha256"],
        "guard_summary": guard_hash,
        "base_rom": rom_hash,
        "input_state": files["input_state"]["sha256"],
        "output_state": files["output_state"]["sha256"],
        "output_png": files["output_png"]["sha256"],
        "staged_rom": files["staged_rom"]["sha256"],
        "replay_script": files["replay_script"]["sha256"],
        "build_manifest": files["build_manifest"]["sha256"],
        "binary": binary["sha256"],
        "patch": patch_hash,
    }
    if caller_hashes is not None:
        for label, expected_hash in caller_hashes.items():
            _require(
                actual_hashes.get(label) == expected_hash,
                f"caller-known {label} hash mismatch",
            )

    return {
        "run_id": audit.get("run_id"),
        "audit": {"path": str(audit_path), "sha256": sha256_file(audit_path)},
        "sentinel": sentinel_record,
        "zero_input_verified": True,
        "evidence_mode": "zero-input",
        "inputs": [],
        "pre_scripts": [],
        "capture_frame": 80,
        "caller_known_sha256": dict(caller_hashes or actual_hashes),
        "files": files,
        "emulator": {
            **binary,
            "version": manifest["version"],
            "architecture": manifest["architecture"],
            "source_commit": manifest["source_commit"],
            "backport_commit": manifest["backport_commit"],
            "patch_sha256": patch_hash,
        },
        "guard": {
            "path": str(guard_summary_path),
            "sha256": guard_hash,
            "reason": guard["reason"],
            "exit_code": guard["exit_code"],
            "degraded": guard["degraded"],
            "child_pgid": audit["child_pgid"],
            "peak_tree_rss_mib": guard.get("peak_tree_rss_mib"),
            "protection_backend": guard.get("protection_backend"),
        },
    }


def validate_runtime_residue(
    pgid: int, ps_output: str, lsof_output: str, *, lsof_exit_code: int
) -> dict[str, object]:
    matching_rows = []
    for line in ps_output.splitlines():
        columns = line.split(maxsplit=2)
        if len(columns) >= 2:
            try:
                row_pgid = int(columns[1])
            except ValueError:
                continue
            if row_pgid == pgid:
                matching_rows.append(line.strip())
    _require(not matching_rows, f"PGID {pgid} still has residual processes")
    _require(lsof_exit_code in (0, 1), f"lsof failed with exit code {lsof_exit_code}")
    listeners = [line for line in lsof_output.splitlines() if line.strip()]
    _require(not listeners and lsof_exit_code == 1, "mGBA listener residue detected")
    return {
        "checked_pgid": pgid,
        "pgid_clean": True,
        "pgid_matching_rows": [],
        "mgba_listener_clean": True,
        "mgba_listener_rows": [],
        "ps_command": ["ps", "-axo", "pid=,pgid=,comm="],
        "lsof_command": [
            "lsof",
            "-nP",
            "-iTCP",
            "-sTCP:LISTEN",
            "-a",
            "-c",
            "mGBA",
            "-Fpcn",
        ],
        "lsof_exit_code": lsof_exit_code,
    }


def probe_runtime_residue(pgid: int) -> dict[str, object]:
    ps_result = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,comm="], capture_output=True, text=True, check=True
    )
    lsof_result = subprocess.run(
        ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-a", "-c", "mGBA", "-Fpcn"],
        capture_output=True,
        text=True,
        check=False,
    )
    residue = validate_runtime_residue(
        pgid,
        ps_result.stdout,
        lsof_result.stdout or lsof_result.stderr,
        lsof_exit_code=lsof_result.returncode,
    )
    residue["checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return residue


def _validated_controller_boundary(rom_path: Path) -> dict[str, str]:
    rom = rom_path.read_bytes()
    callsite = CONTROLLER_RETURN - 5
    offset = callsite - 0x08000000
    _require(0 <= offset <= len(rom) - 4, "controller callsite is outside ROM")
    first, second = struct.unpack_from("<HH", rom, offset)
    target = decode_thumb_bl(callsite, first, second)
    _require(target == CONTROLLER_TARGET, "controller boundary BL target mismatch")
    return {
        "raw_return_word": f"0x{CONTROLLER_RETURN:08X}",
        "callsite": f"0x{callsite:08X}",
        "decoded_target": f"0x{target:08X}",
    }


def validate_prebattle_state(
    report: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        task = report["tasks"][1]
        unwind = report["active_unwind"]
        raw_return_words = unwind["raw_return_words"]
        battle_control = report["memory_bytes"]["0x0202680C"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("prebattle savestate report is incomplete") from error
    expected_words = [f"0x{raw:08X}" for _, raw, _ in EXPECTED_UNWIND]
    _require(task.get("sp") == "0x030011D8", "task 2 SP mismatch")
    _require(task.get("resume_pc") == "0x08067D02", "task 2 resume PC mismatch")
    _require(raw_return_words == expected_words, "active unwind mismatch")
    _require(
        f"0x{CONTROLLER_RETURN:08X}" not in raw_return_words,
        "controller return is present in prebattle unwind",
    )
    _require(battle_control == 0, "battle-control byte is not zero")
    return task, unwind


def build_prebattle_evidence(root: Path | str) -> dict[str, object]:
    root = Path(root).resolve()
    paths = step2_paths(root)
    candidate = paths["input_state"]
    output_state = paths["output_state"]
    output_png = paths["output_png"]
    audit_path = paths["audit"]
    guard_path = paths["guard_summary"]
    rom_path = paths["base_rom"]

    strict = validate_strict_replay(
        audit_path,
        rom_path,
        guard_path,
        caller_paths=paths,
        caller_hashes=STEP2_SHA256,
    )
    _require(
        Path(strict["files"]["input_state"]["path"]).resolve() == candidate,
        "audit input is not the tracked candidate",
    )
    _require(
        Path(strict["files"]["output_state"]["path"]).resolve() == output_state,
        "audit output state path mismatch",
    )
    _require(
        Path(strict["files"]["output_png"]["path"]).resolve() == output_png,
        "audit output PNG path mismatch",
    )

    candidate_screen = png_screen_fingerprint(candidate)
    replay_screen = png_screen_fingerprint(output_png)
    _require(candidate_screen == replay_screen, "frame-80 screen differs from candidate screen")
    _require(
        (candidate_screen["width"], candidate_screen["height"]) == (240, 160),
        "prebattle screen dimensions are not 240x160",
    )

    report = inspect_savestate(
        output_state,
        rom_path=rom_path,
        task_slot=2,
        unwind_frames=[(address, target) for address, _, target in EXPECTED_UNWIND],
        memory_bytes=[0x0202680C],
    )
    task, unwind = validate_prebattle_state(report)
    controller = _validated_controller_boundary(rom_path)
    residue = probe_runtime_residue(strict["guard"]["child_pgid"])

    return {
        "schema_version": 1,
        "verdict": "accepted",
        "checkpoint": {
            "name": "scenario-41-prebattle-menu",
            "path": str(candidate.relative_to(root)),
            "sha256": strict["files"]["input_state"]["sha256"],
            "screen": "scenario-41-prebattle-menu",
            "stable_zero_input": True,
        },
        "screen_identity": {
            "method": "strict PNG decode to normalized RGB8 pixel SHA-256",
            "candidate": candidate_screen,
            "frame80": replay_screen,
            "identical": True,
        },
        "savestate": {
            "output": strict["files"]["output_state"],
            "task_2": task,
            "active_unwind": unwind,
            "controller_negative_boundary": controller,
            "controller_return_absent": True,
            "memory_bytes": report["memory_bytes"],
        },
        "strict_replay": strict,
        "runtime_residue": residue,
        "scope": {
            "proves": ["stable zero-input scenario 41 prebattle menu"],
            "does_not_prove": [
                "battle controller entry",
                "player control",
                "MOVEDONE",
                "victory",
                "postbattle",
            ],
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/runtime-checkpoints/scenario-41-prebattle-menu-evidence.json"),
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    evidence = build_prebattle_evidence(args.root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"accepted evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
