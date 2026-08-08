#!/usr/bin/env python3
"""Independently verify motion/effect parameter natural player-visible evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import tarfile
import tempfile
from typing import Any, Sequence

from PIL import Image

try:
    from tools.render_mode0_checkpoint import render_checkpoint
except ModuleNotFoundError:
    from render_mode0_checkpoint import render_checkpoint


EVIDENCE_SCHEMA = "motion-effect-parameter-pixel-ab-runtime-v1"
BASE_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_BANK_EXTRACTION_SHA256 = "683db11e4186ec145314ad4ae238c34f5b5d80fe66a5520a1cf4d77b5b6b5bf0"
PROFILE_PATH = "sequel/content/motion-effect-parameter-pixel-ab/group-03-record-00-y-offset.json"
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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return value


def byte_differences(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("compared byte lengths differ")
    return [
        index
        for index, pair in enumerate(zip(left, right, strict=True))
        if pair[0] != pair[1]
    ]


def rendered_summary(left: bytes, right: bytes) -> dict[str, Any]:
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
    canonical = json.dumps(changes, separators=(",", ":"), sort_keys=True).encode()
    return {
        "count": len(changes),
        "bbox": [
            min(row["x"] for row in changes),
            min(row["y"] for row in changes),
            max(row["x"] for row in changes),
            max(row["y"] for row in changes),
        ] if changes else None,
        "sha256": sha256_bytes(canonical),
    }


def safe_repo_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} path missing")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} path unsafe")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"{label} path escapes repository")
    return path


def extract_raw(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        for member in members:
            relative = Path(member.name)
            if (
                not member.isfile()
                or relative.is_absolute()
                or ".." in relative.parts
                or member.issym()
                or member.islnk()
            ):
                raise ValueError("raw archive contains unsafe member")
            target = (destination / relative).resolve()
            if destination.resolve() not in target.parents:
                raise ValueError("raw archive member escapes destination")
        archive.extractall(destination, filter="data")


def verify_strict(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    manifest = read_object(artifact / "manifest.json")
    evidence = read_object(artifact / "evidence.json")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != EVIDENCE_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("verified") is not True
        or evidence.get("profile") != PROFILE_PATH
    ):
        raise ValueError("artifact identity mismatch")
    expected_files = {"baseline.png", "candidate.png", "evidence.json", "raw.tar"}
    if set(manifest.get("files", {})) != expected_files:
        raise ValueError("artifact file inventory mismatch")
    for name, expected in manifest["files"].items():
        if sha256_file(artifact / name) != expected:
            raise ValueError(f"artifact file hash mismatch: {name}")
    repository_files = manifest.get("repository_files")
    if not isinstance(repository_files, dict) or not repository_files:
        raise ValueError("repository implementation lock missing")
    for relative, expected in repository_files.items():
        path = safe_repo_file(root, relative, "repository implementation")
        if sha256_file(path) != expected:
            raise ValueError(f"repository implementation hash mismatch: {relative}")

    profile_path = safe_repo_file(root, evidence["profile"], "profile")
    profile = read_object(profile_path)
    if (
        sha256_file(profile_path) != evidence.get("profile_sha256")
        or manifest.get("profile_sha256") != evidence.get("profile_sha256")
        or profile.get("schema") != "motion-effect-parameter-pixel-ab-profile-v1"
        or profile.get("group_id") != 3
        or profile.get("sequence_id") != 3
        or profile.get("record_id") != 0
        or profile.get("field") != "y_offset"
        or profile.get("table_offset") != 0x53EE98
        or profile.get("field_offset") != 4
        or profile.get("before_value") != 0
        or profile.get("after_value") != 32
        or profile.get("consumer_entry") != "0x08080764"
        or profile.get("child_spawn_function") != "0x08080218"
        or profile.get("input_mode") != "zero-input-active-state"
        or profile.get("inputs") != []
    ):
        raise ValueError("profile contract mismatch")
    for key in ("source_bank", "input_state", "input_evidence", "source_phase_profile", "source_phase_manifest"):
        path = safe_repo_file(root, profile.get(key), key)
        if key == "source_bank":
            if profile.get("source_bank_sha256") != SOURCE_BANK_EXTRACTION_SHA256:
                raise ValueError("profile source-bank extraction hash mismatch")
            continue
        if sha256_file(path) != profile.get(f"{key}_sha256"):
            raise ValueError(f"profile dependency hash mismatch: {key}")
    bank = read_object(root / profile["source_bank"])
    if (
        bank.get("table_offset") != 0x53EE98
        or bank.get("entry_count") != 15
        or bank.get("entry_size") != 10
        or bank.get("entries", [{}])[0].get("y_offset") != 0
    ):
        raise ValueError("bank metadata mismatch")

    expected_scope = {
        "natural_gameplay_route": True,
        "player_visible_runtime": True,
        "record_0_y_offset_runtime_verified": True,
        "all_records_runtime_verified": False,
        "all_consumer_routes_runtime_verified": False,
        "physical_gba_verified": False,
    }
    if (
        evidence.get("bank")
        != {
            "path": profile["source_bank"],
            "extraction_sha256": SOURCE_BANK_EXTRACTION_SHA256,
            "current_sha256": sha256_file(root / profile["source_bank"]),
            "historical_slug": "palettes",
            "actual_identity": "motion/effect parameters",
            "table_offset": 0x53EE98,
            "entry_count": 15,
            "entry_size": 10,
        }
        or evidence.get("scope") != expected_scope
        or evidence.get("static_chain")
        != {
            "sequence_id": 3,
            "consumer_entry": "0x08080764",
            "child_spawn_function": "0x08080218",
            "table_address": "0x0853EE98",
        }
        or evidence.get("run_budget")
        != {"planned": 2, "actual": 2, "blind_retries": 0}
    ):
        raise ValueError("evidence scope/static contract mismatch")

    base = (root / "rom/base.gba").read_bytes()
    if sha256_bytes(base) != BASE_SHA256 or base[0x53EE9C:0x53EE9E] != b"\x00\x00":
        raise ValueError("base ROM identity mismatch")
    candidate = bytearray(base)
    candidate[0x53EE9C:0x53EE9E] = b"\x20\x00"
    expected_edit = {
        "rom_offset": 0x53EE9C,
        "rom_address": "0x0853EE9C",
        "record_id": 0,
        "field": "y_offset",
        "before_value": 0,
        "after_value": 32,
        "before_bytes": "0000",
        "after_bytes": "2000",
        "changed_rom_offsets": [0x53EE9C],
    }
    if evidence.get("edit") != expected_edit:
        raise ValueError("evidence edit contract mismatch")
    build_scope = evidence.get("build")
    if (
        not isinstance(build_scope, dict)
        or build_scope.get("probe_free") is not True
        or build_scope.get("baseline_is_base_rom") is not True
        or build_scope.get("changed_rom_offsets") != [0x53EE9C]
    ):
        raise ValueError("evidence build contract mismatch")

    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary) / "raw"
        raw.mkdir()
        extract_raw(artifact / "raw.tar", raw)
        inventory = evidence.get("raw_inventory")
        if not isinstance(inventory, list):
            raise ValueError("raw inventory missing")
        extracted = {
            path.relative_to(raw).as_posix(): path
            for path in raw.rglob("*")
            if path.is_file()
        }
        rows = {row.get("path"): row for row in inventory if isinstance(row, dict)}
        if set(rows) != set(extracted):
            raise ValueError("raw inventory paths mismatch")
        for relative, path in extracted.items():
            if rows[relative] != {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }:
                raise ValueError(f"raw inventory hash mismatch: {relative}")

        build = read_object(raw / "build/build-manifest.json")
        batch = read_object(raw / "batch-audit.json")
        if (
            build.get("schema") != "motion-effect-parameter-pixel-ab-build-v1"
            or build.get("edit") != expected_edit
            or build.get("variants", {}).get("baseline", {}).get("rom_sha256") != BASE_SHA256
            or build.get("variants", {}).get("candidate", {}).get("rom_sha256")
            != sha256_bytes(bytes(candidate))
            or batch.get("schema") != "motion-effect-parameter-pixel-ab-batch-v1"
            or batch.get("run_budget") != evidence["run_budget"]
            or batch.get("build_manifest_sha256") != sha256_file(raw / "build/build-manifest.json")
            or evidence.get("build", {}).get("manifest_sha256")
            != sha256_file(raw / "build/build-manifest.json")
        ):
            raise ValueError("raw build/batch contract mismatch")

        expected_runs = {}
        for variant in VARIANTS:
            run = raw / "runs" / variant
            run_profile = read_object(run / "profile.json")
            audit = read_object(run / "output/audit.json")
            guard = read_object(run / "guard-summary.json")
            phases = audit.get("phases")
            if (
                run_profile.get("variant") != variant
                or run_profile.get("execution_mode") != "natural-motion-parameter-pixel-ab"
                or run_profile.get("natural_gameplay_route") is not True
                or run_profile.get("input_mode") != "zero-input-active-state"
                or run_profile.get("inputs") != []
                or audit.get("outcome") != "three-phase-captured"
                or audit.get("group_id") != 3
                or audit.get("input_mode") != "zero-input-active-state"
                or audit.get("inputs") != []
                or audit.get("automatic_inputs") != []
                or audit.get("recovery_inputs") != []
                or audit.get("pgid_clean") is not True
                or audit.get("runtime_residue", {}).get("pgid_clean") is not True
                or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
                or guard.get("reason") != "completed"
                or guard.get("exit_code") != 0
                or guard.get("degraded") is not False
                or guard.get("completion_trigger") != "success-marker"
                or not isinstance(phases, list)
                or [row.get("name") for row in phases] != list(PHASES)
                or [row.get("address") for row in phases]
                != ["0x08063328", "0x08061126", "0x080612AA"]
                or [row.get("pending") for row in phases] != [0, 1, 0]
                or [row.get("frame") for row in phases] != [67, 67, 68]
                or {row.get("task_slot") for row in phases} != {126}
            ):
                raise ValueError(f"raw {variant} runtime contract mismatch")
            for relative, expected in audit.get("files", {}).items():
                path = run / "output" / relative
                if not path.is_file() or sha256_file(path) != expected:
                    raise ValueError(f"raw {variant} capture hash mismatch: {relative}")
            expected_runs[variant] = {
                "variant": variant,
                "rom_sha256": build["variants"][variant]["rom_sha256"],
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
        if evidence.get("runs") != [expected_runs[name] for name in VARIANTS]:
            raise ValueError("evidence run inventory mismatch")

        memory = {}
        for phase in PHASES:
            differences = {}
            for domain in DOMAINS:
                left = (raw / f"runs/baseline/output/{phase}/capture-{domain}").read_bytes()
                right = (raw / f"runs/candidate/output/{phase}/capture-{domain}").read_bytes()
                offsets = byte_differences(left, right)
                if offsets:
                    differences[domain] = offsets
            if differences != EXPECTED_DIFFS[phase]:
                raise ValueError(f"raw {phase} memory isolation mismatch")
            memory[phase] = differences
        if evidence.get("runtime", {}).get("memory_differences") != memory:
            raise ValueError("evidence memory allowlist mismatch")
        for phase in PHASES:
            task_values = []
            shadow_values = []
            hardware_values = []
            for variant in VARIANTS:
                phase_root = raw / f"runs/{variant}/output/{phase}"
                task = (phase_root / "capture-task-pool.bin").read_bytes()
                shadow = (phase_root / "capture-shadow-oam.bin").read_bytes()
                hardware = (phase_root / "capture-hardware-oam.bin").read_bytes()
                task_values.append(struct.unpack_from("<h", task, 126 * 0x3C + 6)[0])
                shadow_values.append(shadow[0])
                hardware_values.append(hardware[0])
            if task_values != [64, 96] or shadow_values != [80, 112]:
                raise ValueError("raw task/shadow OAM propagation mismatch")
            if hardware_values != ([80, 112] if phase == "ack-post" else [40, 40]):
                raise ValueError("raw hardware OAM transaction mismatch")

        rendered = {
            variant: render_checkpoint(raw / f"runs/{variant}/output/ack-post/capture.ss9")[0]
            for variant in VARIANTS
        }
        summary = rendered_summary(rendered["baseline"], rendered["candidate"])
        runtime = evidence.get("runtime")
        expected_runtime = {
            "memory_differences": memory,
            "task_slot": 126,
            "task_address": "0x03005940",
            "task_field_offset": 6,
            "task_y_values": [64, 96],
            "oam_index": 0,
            "oam_y_values": [80, 112],
            "y_delta": 32,
            "pixel_render_source": "offline-mode0-from-ack-savestate",
            "pixel_change_count": 286,
            "pixel_change_bbox": [54, 88, 72, 107],
            "pixel_changes_sha256": summary["sha256"],
            "baseline_rgb_sha256": sha256_bytes(rendered["baseline"]),
            "candidate_rgb_sha256": sha256_bytes(rendered["candidate"]),
        }
        if summary["count"] != 286 or summary["bbox"] != [54, 88, 72, 107] or runtime != expected_runtime:
            raise ValueError("final Mode 0 runtime contract mismatch")
        for variant in VARIANTS:
            with Image.open(artifact / f"{variant}.png") as image:
                if image.size != (240, 160) or image.convert("RGB").tobytes() != rendered[variant]:
                    raise ValueError(f"rendered PNG mismatch: {variant}")
    return {
        "verified": True,
        "errors": [],
        "natural_gameplay_route": True,
        "record_id": 0,
        "field": "y_offset",
        "pixel_change_count": 286,
    }


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        return verify_strict(root, artifact)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        return {
            "verified": False,
            "errors": [str(error)],
            "natural_gameplay_route": False,
            "record_id": None,
            "field": None,
            "pixel_change_count": 0,
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_evidence(args.root, args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
