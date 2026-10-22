#!/usr/bin/env python3
"""Validate and promote the natural map-events E4 primary-handler pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
from typing import Any, Sequence

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint


EVIDENCE_SCHEMA = "map-events-e4-handler-pixel-ab-evidence-v1"
MANIFEST_SCHEMA = "map-events-e4-handler-pixel-ab-artifact-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
BINARY_PATH = Path("/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA")
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
CHECKPOINT = "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready.ss9"
CHECKPOINT_SHA256 = "34eb56d34d876a275546a2b6875804aa5e24c97600a9d299c0c6ba0ae165b501"
EXPECTED_RAW_FILES = (
    "build/build-manifest.json",
    "runs/baseline/guard-summary.json",
    "runs/baseline/output/audit.json",
    "runs/baseline/output/final.png",
    "runs/baseline/output/final.ss9",
    "runs/candidate/guard-summary.json",
    "runs/candidate/output/audit.json",
    "runs/candidate/output/final.png",
    "runs/candidate/output/final.ss9",
)
IMPLEMENTATION_FILES = (
    "sequel/content/map-events/bank.json",
    "sequel/content/map-events/entry-e4-primary-pixel-ab.json",
    "notes/battlefield-object-effect-chain-bindings-20260802.json",
    "artifacts/battle-effect-frame-phase-group3-natural-v1/manifest.json",
    "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready-evidence.json",
    "tools/build_map_events_e4_handler_pixel_ab.py",
    "tools/export_map_events_e4_handler_pixel_ab.py",
    "tools/verify_map_events_e4_handler_pixel_ab.py",
    "tools/mgba_map_events_e4_trace.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
    "tests/test_build_map_events_e4_handler_pixel_ab.py",
    "tests/test_mgba_map_events_e4_trace_script.py",
    "tests/test_map_events_e4_handler_pixel_ab_artifact.py",
    "tests/test_render_mode0_checkpoint.py",
)
EXPECTED_MEMORY = {
    "IO": {
        "count": 1,
        "indices_sha256": "f3c95d13a34c34b7e2a69c1947983a4fd88f2bc10b2e4d2d992a3fb66b55eca3",
        "baseline_sha256": "60bfbb7456f14ca72548b72d1d3fe66dcaba1b106bc848bee4d61c93ddb01aff",
        "candidate_sha256": "d0e359fabe3e2c85fd85df12c11e555768ca3bf832eaec6fd4726380ff458912",
    },
    "PRAM": {
        "count": 62,
        "indices_sha256": "d0374daf5af8f552ed1562bb4da0c315339e2aaaac67d022d9a18ab140793275",
        "baseline_sha256": "e392b651b31ed2fc2f25da270ca51d7657b7770a04dab1468087cbfcf91cbb4e",
        "candidate_sha256": "8a5d91444000ba9da4559b1d9274bd7f31bbbfe90a624e263093256ea348b9f1",
    },
    "VRAM": {
        "count": 6841,
        "indices_sha256": "530e2a560fff59104f05996c20556d6f43d7a2774e4160fb235449cb09c5c1e2",
        "baseline_sha256": "9b301d47ae43ffbc17df2d8bcbd17d8be6b8886e20eede78cfe6a473e8f97e10",
        "candidate_sha256": "83052913843f00ec5c12ec7446c13c4b12285275a91162df3d546f45aa811a34",
    },
    "OAM": {
        "count": 11,
        "indices_sha256": "fc6a44db36e54ee4caec5442e4fa86a396d814ea701564b65d1c1f96725c7c0d",
        "baseline_sha256": "d0c2a41dc2b240bd31f8fc167e10a8a6b36f4937682f8210841ecb968b38424e",
        "candidate_sha256": "73680856565cd58877337330c5d4e63dbd566852dcf9f2999a2f747a9ef09623",
    },
    "IWRAM": {
        "count": 417,
        "indices_sha256": "ae99e437a2b8b9a372b35adda9a8bb5352f01f7cdf129dea814de7c55f927e09",
        "baseline_sha256": "a0c2045589544fba95de4681b65538e1469081725e770cf15d9b85896d966642",
        "candidate_sha256": "758b420e982da0f7f6984837d35f4c5d93147343be85f344787bc950f23106ee",
    },
    "EWRAM": {
        "count": 13,
        "indices_sha256": "b955fa2bee7dd17beb0af90861296f8fb0b4c4ed7019c32d4eb2c2436a323ca8",
        "baseline_sha256": "1a7a80b673bc24d0d418e7ac892bc1eb2eb7031c5b88e9739913e136709c5236",
        "candidate_sha256": "c34d3f60bbe573a0f38ac9d6d5a135fdd51da123faf8eda12b0321ccae020255",
    },
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_guard(root: Path, guard: dict[str, Any], variant: str) -> None:
    command = guard.get("command")
    expected_script = str((root / "tools/mgba_map_events_e4_trace.lua").resolve(strict=True))
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("degraded") is not False
        or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        or guard["peak_tree_rss_mib"] > 768
        or not isinstance(command, list)
        or len(command) != 4
        or command[0] != str(BINARY_PATH)
        or command[1] != "--script"
        or command[2] != expected_script
        or Path(command[3]).name != f"{variant}.gba"
        or root not in Path(command[3]).resolve().parents
    ):
        raise ValueError(f"map-events {variant} guard mismatch")


def _reconstruct_variants(root: Path, build: dict[str, Any]) -> dict[str, bytes]:
    base = (root / "rom/base.gba").read_bytes()
    patch_offset = 0x53EDB8
    before = bytes.fromhex("09f20708")
    after = bytes.fromhex("49c10908")
    if (
        len(base) != 0x600000
        or sha256_bytes(base) != build.get("source_rom_sha256")
        or base[patch_offset : patch_offset + 4] != before
        or base[0x09C148 : 0x09C14A] != bytes.fromhex("7047")
    ):
        raise ValueError("map-events ROM reconstruction mismatch")
    candidate_buffer = bytearray(base)
    candidate_buffer[patch_offset : patch_offset + 4] = after
    candidate = bytes(candidate_buffer)
    changed = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    expected_edit = {
        "rom_offset": patch_offset,
        "rom_address": "0x0853EDB8",
        "field": "primary_handler_ptr",
        "before_pointer": "0x0807F209",
        "after_pointer": "0x0809C149",
        "after_target_instruction": "bx lr",
        "before_bytes": before.hex(),
        "after_bytes": after.hex(),
        "changed_rom_offsets": changed,
    }
    reconstructed = {"baseline": base, "candidate": candidate}
    variants = build.get("variants")
    if build.get("edit") != expected_edit or not isinstance(variants, dict) or set(variants) != set(reconstructed):
        raise ValueError("map-events ROM reconstruction mismatch")
    for variant, payload in reconstructed.items():
        expected = {
            "rom_path": f"{variant}/{variant}.gba",
            "rom_sha256": sha256_bytes(payload),
            "rom_size": len(payload),
        }
        if variants.get(variant) != expected:
            raise ValueError("map-events ROM reconstruction mismatch")
    return reconstructed


def _event_map(audit: dict[str, Any], variant: str) -> dict[str, dict[str, Any]]:
    events = audit.get("events")
    if not isinstance(events, list):
        raise ValueError(f"map-events {variant} events missing")
    result = {event.get("name"): event for event in events if isinstance(event, dict)}
    expected = {"e4-table-address", "e4-handler-loaded", "e4-trampoline"}
    if variant == "baseline":
        expected |= {"native-group3-handler", "group3-renderer"}
    if set(result) != expected:
        raise ValueError(f"map-events {variant} runtime chain mismatch")
    return result


def _pixel_facts(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    with Image.open(baseline_path) as image:
        baseline = image.convert("RGB")
    with Image.open(candidate_path) as image:
        candidate = image.convert("RGB")
    if baseline.size != (240, 160) or candidate.size != baseline.size:
        raise ValueError("map-events runtime PNG dimensions mismatch")
    left = baseline.tobytes()
    right = candidate.tobytes()
    changed = sum(
        left[offset : offset + 3] != right[offset : offset + 3]
        for offset in range(0, len(left), 3)
    )
    bbox = ImageChops.difference(baseline, candidate).getbbox()
    facts = {
        "width": 240,
        "height": 160,
        "baseline_rgb_sha256": sha256_bytes(left),
        "candidate_rgb_sha256": sha256_bytes(right),
        "changed_pixel_count": changed,
        "bbox_inclusive": None if bbox is None else [bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1],
    }
    if facts != {
        "width": 240,
        "height": 160,
        "baseline_rgb_sha256": "12c28206d046864088b43898075275ce8aec11db414172f6b2f47fa0a69dff41",
        "candidate_rgb_sha256": "3ac44a642a77c63c09f3048aff7069845f7c48772eaf07d46581637989f03c4a",
        "changed_pixel_count": 37436,
        "bbox_inclusive": [0, 0, 239, 159],
    }:
        raise ValueError("map-events pixel difference mismatch")
    return facts


def _memory_facts(states: dict[str, Any]) -> dict[str, Any]:
    regions = (
        ("IO", 0x04000000, 0x400),
        ("PRAM", 0x05000000, 0x400),
        ("VRAM", 0x06000000, 0x18000),
        ("OAM", 0x07000000, 0x400),
        ("IWRAM", 0x03000000, 0x8000),
        ("EWRAM", 0x02000000, 0x40000),
    )
    result: dict[str, Any] = {}
    for name, address, size in regions:
        left = states["baseline"].read_memory(address, size)
        right = states["candidate"].read_memory(address, size)
        indices = [
            index for index, pair in enumerate(zip(left, right, strict=True)) if pair[0] != pair[1]
        ]
        result[name] = {
            "count": len(indices),
            "indices_sha256": sha256_bytes(json.dumps(indices, separators=(",", ":")).encode()),
            "baseline_sha256": sha256_bytes(left),
            "candidate_sha256": sha256_bytes(right),
        }
    if result != EXPECTED_MEMORY:
        raise ValueError("map-events runtime memory attribution mismatch")
    return result


def _validate_source(root: Path, source: Path) -> dict[str, Any]:
    for name in EXPECTED_RAW_FILES:
        if not (source / name).is_file():
            raise ValueError(f"map-events raw source missing {name}")
    build = read_object(source / "build/build-manifest.json", "map-events build manifest")
    source_contract = {
        "profile": "sequel/content/map-events/entry-e4-primary-pixel-ab.json",
        "source_rom": "rom/base.gba",
        "source_bank": "sequel/content/map-events/bank.json",
        "source_chain_manifest": "notes/battlefield-object-effect-chain-bindings-20260802.json",
        "source_phase_artifact": "artifacts/battle-effect-frame-phase-group3-natural-v1",
        "input_state": CHECKPOINT,
        "input_evidence": "artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready-evidence.json",
    }
    digest_contract = (
        ("profile", "profile_sha256"),
        ("source_rom", "source_rom_sha256"),
        ("source_bank", "source_bank_sha256"),
        ("source_chain_manifest", "source_chain_manifest_sha256"),
        ("input_state", "input_state_sha256"),
        ("input_evidence", "input_evidence_sha256"),
    )
    if any(build.get(key) != value for key, value in source_contract.items()) or any(
        build.get(digest_key) != sha256_file(root / build[path_key])
        for path_key, digest_key in digest_contract
    ) or build.get("source_phase_manifest_sha256") != sha256_file(
        root / build["source_phase_artifact"] / "manifest.json"
    ):
        raise ValueError("map-events source contract mismatch")
    if (
        build.get("schema") != "map-events-e4-handler-pixel-ab-build-v1"
        or build.get("entry_id") != 0xE4
        or build.get("field") != "primary_handler_ptr"
        or build.get("natural_gameplay_route") is not True
        or build.get("input_mode") != "zero-input-natural-expiry"
        or build.get("inputs") != []
        or build.get("input_state_sha256") != CHECKPOINT_SHA256
        or build.get("capture_post_dispatch_frames") != 3
    ):
        raise ValueError("map-events build contract mismatch")
    reconstructed = _reconstruct_variants(root, build)
    script_digest = sha256_file(root / "tools/mgba_map_events_e4_trace.lua")
    if not BINARY_PATH.is_file() or sha256_file(BINARY_PATH) != BINARY_SHA256:
        raise ValueError("map-events runtime tool hash mismatch")

    handlers = {"baseline": "0x0807F209", "candidate": "0x0809C149"}
    states: dict[str, Any] = {}
    runs: dict[str, Any] = {}
    event_summaries: dict[str, Any] = {}
    for variant in ("baseline", "candidate"):
        audit_path = source / f"runs/{variant}/output/audit.json"
        guard_path = source / f"runs/{variant}/guard-summary.json"
        state_path = source / f"runs/{variant}/output/final.ss9"
        png_path = source / f"runs/{variant}/output/final.png"
        audit = read_object(audit_path, f"map-events {variant} audit")
        guard = read_object(guard_path, f"map-events {variant} guard")
        _validate_guard(root, guard, variant)
        if audit.get("script_sha256") != script_digest or audit.get("binary_sha256") != BINARY_SHA256:
            raise ValueError("map-events runtime tool hash mismatch")
        events = _event_map(audit, variant)
        handler = handlers[variant]
        expected_native = variant == "baseline"
        common_ok = (
            audit.get("schema") == "map-events-e4-runtime-trace-v1"
            and audit.get("outcome") == "post-dispatch-window-complete"
            and audit.get("frame") == 69
            and audit.get("post_dispatch_frames") == 3
            and audit.get("input_mode") == "zero-input-natural-expiry"
            and audit.get("inputs") == []
            and audit.get("automatic_inputs") == []
            and audit.get("recovery_inputs") == []
            and audit.get("input_state_sha256") == CHECKPOINT_SHA256
            and audit.get("rom_sha256") == sha256_bytes(reconstructed[variant])
            and audit.get("expected_handler") == handler
            and audit.get("expect_group3") is expected_native
            and audit.get("expiry_seen") is False
            and audit.get("table_address_seen") is True
            and audit.get("table_handler_seen") is True
            and audit.get("dispatch_seen") is True
            and audit.get("native_handler_seen") is expected_native
            and audit.get("group3_seen") is expected_native
            and events["e4-table-address"].get("address") == "0x0807FD36"
            and events["e4-table-address"].get("frame") == 66
            and events["e4-table-address"].get("r0") == "0x0853EDB8"
            and events["e4-table-address"].get("table_entry_address") == "0x0853EDB8"
            and events["e4-table-address"].get("table_handler") == handler
            and events["e4-handler-loaded"].get("address") == "0x0807FD38"
            and events["e4-handler-loaded"].get("r0") == "0x0853EDB8"
            and events["e4-handler-loaded"].get("r1") == handler
            and events["e4-trampoline"].get("address") == "0x0809C114"
            and events["e4-trampoline"].get("r1") == handler
            and events["e4-trampoline"].get("lr") == "0x0807FD3F"
        )
        if expected_native:
            common_ok = common_ok and (
                events["native-group3-handler"].get("address") == "0x0807F208"
                and events["native-group3-handler"].get("frame") == 66
                and events["native-group3-handler"].get("lr") == "0x0807FD3F"
                and events["group3-renderer"].get("address") == "0x08063328"
                and events["group3-renderer"].get("frame") == 67
                and events["group3-renderer"].get("task_slot") == 126
                and events["group3-renderer"].get("task_address") == "0x03005940"
            )
        if not common_ok:
            raise ValueError(f"map-events {variant} runtime chain mismatch")
        state = load_gba_state(state_path)
        rendered = render_checkpoint(state_path)[0]
        with Image.open(png_path) as screenshot:
            screenshot_rgb = screenshot.convert("RGB").tobytes()
            screenshot_size = screenshot.size
        if screenshot_size != (240, 160) or screenshot_rgb != rendered:
            raise ValueError(f"map-events {variant} savestate screenshot mismatch")
        states[variant] = state
        runs[variant] = {
            "rom_sha256": audit["rom_sha256"],
            "audit_sha256": sha256_file(audit_path),
            "guard_sha256": sha256_file(guard_path),
            "state_sha256": sha256_file(state_path),
            "png_sha256": sha256_file(png_path),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            "pgid_clean": True,
        }
        event_summaries[variant] = {
            name: {key: event[key] for key in ("address", "frame", "r0", "r1", "lr", "table_entry_address", "table_handler", "task_slot", "task_address")}
            for name, event in events.items()
        }
    pixels = _pixel_facts(
        source / "runs/baseline/output/final.png",
        source / "runs/candidate/output/final.png",
    )
    return {
        "build": build,
        "runs": runs,
        "events": event_summaries,
        "memory": _memory_facts(states),
        "pixels": pixels,
    }


def _build_evidence(facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_SCHEMA,
        "verified": True,
        "entry_id": 0xE4,
        "field": "primary_handler_ptr",
        "checkpoint": {"path": CHECKPOINT, "sha256": CHECKPOINT_SHA256},
        "route": {
            "natural_checkpoint": True,
            "zero_input": True,
            "current_run_rehit_expiry_builder": False,
            "table_entry_address": "0x0853EDB8",
            "dispatch_address": "0x0807FD36",
            "trampoline": "0x0809C114",
            "baseline_handler": "0x0807F209",
            "candidate_handler": "0x0809C149",
            "candidate_handler_instruction": "bx lr",
            "post_dispatch_frames": 3,
            "boundary": facts["build"]["boundary"],
        },
        "build": {"manifest_sha256": None, "edit": facts["build"]["edit"]},
        "emulator": {"source_commit": BINARY_COMMIT, "binary_sha256": BINARY_SHA256},
        "runs": facts["runs"],
        "events": facts["events"],
        "memory": facts["memory"],
        "pixels": facts["pixels"],
        "proved": "Natural zero-input recovery reaches E4 primary_handler_ptr through 0x0807FD36 and 0x0809C114; the baseline enters 0x0807F208 and renders group 3, while the isolated bx-lr candidate does neither and changes 37,436 final pixels.",
        "not_proved": "This run resumes after the C3-to-E4 event was queued and does not re-hit 0x08081D74; source checkpoint and static-chain artifacts bind that upstream route. It does not prove secondary handlers, all 256 entries, full animation semantics, or physical-GBA output.",
    }


def _write_raw_tar(source: Path, output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in EXPECTED_RAW_FILES:
            path = source / name
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)


def export_artifact(root: Path, source: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("map-events artifact output must be absent or empty")
    facts = _validate_source(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "runs/baseline/output/final.png", output / "baseline.png")
    shutil.copyfile(source / "runs/candidate/output/final.png", output / "candidate.png")
    _write_raw_tar(source, output / "raw.tar")
    evidence = _build_evidence(facts)
    evidence["build"]["manifest_sha256"] = sha256_file(source / "build/build-manifest.json")
    write_json(output / "evidence.json", evidence)
    files = {
        name: sha256_file(output / name)
        for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar")
    }
    manifest = {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": MANIFEST_SCHEMA,
        "artifact_id": "map-events-e4-handler-pixel-ab-v1",
        "artifact_status": "accepted",
        "files": files,
        "implementation": {name: sha256_file(root / name) for name in IMPLEMENTATION_FILES},
        "verifier": {
            "command": [
                "python3",
                "tools/verify_map_events_e4_handler_pixel_ab.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/map-events-e4-handler-pixel-ab-v1",
            ],
            "exit_code": 0,
        },
        "scope": {"proved": evidence["proved"], "not_proved": evidence["not_proved"]},
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(export_artifact(ROOT, args.source, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
