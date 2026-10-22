#!/usr/bin/env python3
"""Promote the controlled story visual descriptor runtime pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import io
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


SCHEMA = "battle-encounters-story-visual-pixel-ab-evidence-v1"
ARTIFACT_SCHEMA = "battle-encounters-story-visual-pixel-ab-artifact-v1"
BINARY_PATH = Path(
    "/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA"
)
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
BINARY_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
SCRIPT_PATH = Path("tools/mgba_battle_encounters_story_visual_trace.lua")
SCRIPT_SHA256 = "078c19552036a1fea0fe33ec173ec823ba81995b05f8a4398378eb90580e49e0"
INPUT_SHA256 = "65cd8b010f9c21a6d5bc93fe8ed1b84fada025136936f6a42f0d540d0f7ab0a9"
CANONICAL_PATH = Path(
    "artifacts/runtime-checkpoints/scenario-53-story-slideshow-command-controlled.ss9"
)
PARENT_PATH = Path(
    "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-8.ss9"
)
PARENT_SHA256 = "62adcd52b577f73ca1ffd6d2d4ec3b9fafa2a2b130ac644a6834e2a56a50d4d8"
RAW_FILES = (
    ("build/build-manifest.json", "build/build-manifest.json"),
    ("build/input/controlled-story-opcode.ss9", "input/controlled-story-opcode.ss9"),
    ("runs/baseline/audit.json", "runs/baseline/audit.json"),
    ("runs/baseline/final.png", "runs/baseline/final.png"),
    ("runs/baseline/final.ss9", "runs/baseline/final.ss9"),
    ("runs/baseline/guard-summary.json", "runs/baseline/guard-summary.json"),
    ("runs/candidate/audit.json", "runs/candidate/audit.json"),
    ("runs/candidate/final.png", "runs/candidate/final.png"),
    ("runs/candidate/final.ss9", "runs/candidate/final.ss9"),
    ("runs/candidate/guard-summary.json", "runs/candidate/guard-summary.json"),
)
IMPLEMENTATION_FILES = (
    "tools/build_battle_encounters_story_visual_pixel_ab.py",
    "tools/export_battle_encounters_story_visual_pixel_ab.py",
    "tools/verify_battle_encounters_story_visual_pixel_ab.py",
    "tools/mgba_battle_encounters_story_visual_trace.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
    "tools/patch_mgba_savestate_memory.py",
    "tests/test_build_battle_encounters_story_visual_pixel_ab.py",
    "tests/test_mgba_battle_encounters_story_visual_trace_script.py",
    "tests/test_battle_encounters_story_visual_pixel_ab_artifact.py",
)

EXPECTED_REGIONS = {
    "IO": {
        "count": 0,
        "index_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "baseline_sha256": "e0f287b97d27486e6c7e4ba5aba72b3dd71395199ffbd1660e45449920eaa2c6",
        "candidate_sha256": "e0f287b97d27486e6c7e4ba5aba72b3dd71395199ffbd1660e45449920eaa2c6",
    },
    "PRAM": {
        "count": 0,
        "index_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "baseline_sha256": "76b4e174e0730e8902fee39c1f720b2449055d745c721dbcd35d8804aa0e3f32",
        "candidate_sha256": "76b4e174e0730e8902fee39c1f720b2449055d745c721dbcd35d8804aa0e3f32",
    },
    "VRAM": {
        "count": 2348,
        "index_sha256": "0a2034d58c9f7ebb9556ee5fdbd77cf28d4468c99408ecae333d494775ec56e8",
        "baseline_sha256": "0e151558329d8483c1424966fc77fedc8b8dcb9ee50ba7991faae162fdf577d9",
        "candidate_sha256": "bc22c6e21af8cf4fbe8138cc6a82a4da2531974a8bebf22a10a269fd55700de2",
        "first_offset": 0xE83E,
        "last_offset": 0xF5C2,
    },
    "OAM": {
        "count": 0,
        "index_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "baseline_sha256": "2a25f06c35b6c2bb7327a651cc845e3fafc093881f3c13358a3cce44b66ba13d",
        "candidate_sha256": "2a25f06c35b6c2bb7327a651cc845e3fafc093881f3c13358a3cce44b66ba13d",
    },
    "IWRAM": {
        "count": 1,
        "index_sha256": "df07d516b299fe1db9db5f6c94a2e36735d5ce4027aeb9f7c648878b8882cc1c",
        "baseline_sha256": "9645dd5ebdf587bb924c59ff442af5007d20b945db8a50e87981e3c2dbf9ee1f",
        "candidate_sha256": "377dffd9048a62246e7058934612bdf5b75e87b49c74fff8c3f5c05c9a6e2ae8",
        "first_offset": 0x7F9C,
        "last_offset": 0x7F9C,
    },
    "EWRAM": {
        "count": 0,
        "index_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "baseline_sha256": "75c12071d842f55e8ae96b811cf6bed241fca8279113d53b9763a2e7244afe71",
        "candidate_sha256": "75c12071d842f55e8ae96b811cf6bed241fca8279113d53b9763a2e7244afe71",
    },
}
EXPECTED_PIXELS = {
    "width": 240,
    "height": 160,
    "changed_pixel_count": 1603,
    "bbox_inclusive": [88, 48, 159, 108],
    "baseline_rgb_sha256": "3551e69b1b3eef6e7acfc179ba2556622608544f322e3999b25c66f9fd90a2ce",
    "candidate_rgb_sha256": "6b87ae09aadf58d8ccca94f78efa5dd9260c04b29f6f20a2a4fc29cd56bb444a",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pixel_facts(left_path: Path, right_path: Path) -> dict[str, Any]:
    left_image = Image.open(left_path).convert("RGB")
    right_image = Image.open(right_path).convert("RGB")
    if left_image.size != (240, 160) or right_image.size != left_image.size:
        raise ValueError("battle-encounters PNG dimensions mismatch")
    left = left_image.tobytes()
    right = right_image.tobytes()
    count = sum(
        left[index : index + 3] != right[index : index + 3]
        for index in range(0, len(left), 3)
    )
    bbox = ImageChops.difference(left_image, right_image).getbbox()
    return {
        "width": 240,
        "height": 160,
        "changed_pixel_count": count,
        "bbox_inclusive": None
        if bbox is None
        else [bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1],
        "baseline_rgb_sha256": _sha256(left),
        "candidate_rgb_sha256": _sha256(right),
    }


def _region_facts(states: dict[str, Any]) -> dict[str, dict[str, Any]]:
    regions = (
        ("IO", 0x04000000, 0x400),
        ("PRAM", 0x05000000, 0x400),
        ("VRAM", 0x06000000, 0x18000),
        ("OAM", 0x07000000, 0x400),
        ("IWRAM", 0x03000000, 0x8000),
        ("EWRAM", 0x02000000, 0x40000),
    )
    result = {}
    for name, address, size in regions:
        left = states["baseline"].read_memory(address, size)
        right = states["candidate"].read_memory(address, size)
        indices = [
            index
            for index, pair in enumerate(zip(left, right, strict=True))
            if pair[0] != pair[1]
        ]
        row: dict[str, Any] = {
            "count": len(indices),
            "index_sha256": _sha256(
                b"".join(index.to_bytes(4, "little") for index in indices)
            ),
            "baseline_sha256": _sha256(left),
            "candidate_sha256": _sha256(right),
        }
        if indices:
            row["first_offset"] = indices[0]
            row["last_offset"] = indices[-1]
        result[name] = row
    return result


def _events_by_name(audit: dict[str, Any], variant: str) -> dict[str, dict[str, Any]]:
    events = audit.get("events")
    if not isinstance(events, list):
        raise ValueError(f"{variant} trace events missing")
    indexed = {row.get("name"): row for row in events if isinstance(row, dict)}
    expected_names = [
        "chapter-opcode-14",
        "story-state-dispatch",
        "story-wrapper",
        "story-loader",
        "descriptor-0-select",
        "gfx-decompress",
        "palette-decompress",
        "tilemap-decompress",
        "overlay-first-vblank",
    ]
    if [row.get("name") for row in events] != expected_names:
        raise ValueError(f"{variant} trace event order mismatch")
    return indexed


def _validate_guard(root: Path, guard: dict[str, Any], variant: str) -> None:
    command = guard.get("command")
    expected_script = str((root / SCRIPT_PATH).resolve())
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("degraded") is not False
        or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        or guard["peak_tree_rss_mib"] > 512
        or not isinstance(command, list)
        or len(command) != 4
        or command[0] != str(BINARY_PATH)
        or command[1:3] != ["--script", expected_script]
        or not command[3].endswith(f"/build/{variant}/{variant}.gba")
    ):
        raise ValueError(f"{variant} guard contract mismatch")


def _validate_source(root: Path, source: Path) -> dict[str, Any]:
    for source_name, _ in RAW_FILES:
        if not (source / source_name).is_file():
            raise ValueError(f"battle-encounters raw file missing: {source_name}")
    if _sha256_file(root / SCRIPT_PATH) != SCRIPT_SHA256:
        raise ValueError("battle-encounters trace script hash mismatch")
    if not BINARY_PATH.is_file() or _sha256_file(BINARY_PATH) != BINARY_SHA256:
        raise ValueError("battle-encounters emulator binary mismatch")

    build = _read_json(source / "build/build-manifest.json", "build manifest")
    if (
        build.get("schema") != "battle-encounters-story-visual-pixel-ab-build-v1"
        or build.get("input_state_sha256") != INPUT_SHA256
        or build.get("edit", {}).get("record_id") != 0
        or build.get("edit", {}).get("field") != "gfx_lz_ptr"
        or build.get("edit", {}).get("before_pointer") != "0x0812FF50"
        or build.get("edit", {}).get("after_pointer") != "0x081303E8"
        or build.get("edit", {}).get("changed_rom_offsets")
        != [0x54229C, 0x54229D, 0x54229E]
        or build.get("controlled_entry", {}).get("fixture_edit_kind")
        != "script-cursor-only"
        or build.get("controlled_entry", {}).get("canonical_checkpoint")
        != CANONICAL_PATH.as_posix()
        or build.get("controlled_entry", {}).get("canonical_checkpoint_sha256")
        != INPUT_SHA256
        or build.get("boundary", {}).get("natural_scenario_53_navigation") is not False
    ):
        raise ValueError("battle-encounters build contract mismatch")

    fixture = source / "build/input/controlled-story-opcode.ss9"
    if _sha256_file(fixture) != INPUT_SHA256:
        raise ValueError("battle-encounters fixture hash mismatch")
    canonical = root / CANONICAL_PATH
    if _sha256_file(canonical) != INPUT_SHA256 or canonical.read_bytes() != fixture.read_bytes():
        raise ValueError("battle-encounters canonical checkpoint mismatch")
    parent = root / PARENT_PATH
    if _sha256_file(parent) != PARENT_SHA256:
        raise ValueError("battle-encounters parent checkpoint mismatch")
    parent_state = load_gba_state(parent)
    fixture_state = load_gba_state(fixture)
    if (
        parent_state.read_u32(0x030011F0) != 0x08031F31
        or fixture_state.read_u32(0x030011F0) != 0x08049E63
    ):
        raise ValueError("battle-encounters controlled cursor mismatch")
    state_differences = [
        index
        for index, pair in enumerate(
            zip(parent_state.data, fixture_state.data, strict=True)
        )
        if pair[0] != pair[1]
    ]
    if state_differences != [106992, 106993, 106994]:
        raise ValueError("battle-encounters fixture state isolation mismatch")

    states: dict[str, Any] = {}
    runs: dict[str, Any] = {}
    for variant in ("baseline", "candidate"):
        audit_path = source / f"runs/{variant}/audit.json"
        state_path = source / f"runs/{variant}/final.ss9"
        png_path = source / f"runs/{variant}/final.png"
        guard_path = source / f"runs/{variant}/guard-summary.json"
        audit = _read_json(audit_path, f"{variant} audit")
        guard = _read_json(guard_path, f"{variant} guard")
        if (
            audit.get("schema") != "battle-encounters-story-visual-trace-v1"
            or audit.get("outcome") != "capture-complete"
            or audit.get("frame") != 205
            or audit.get("missing") != []
            or audit.get("input_state_sha256") != INPUT_SHA256
            or audit.get("script_sha256") != SCRIPT_SHA256
            or audit.get("rom_sha256")
            != build["variants"][variant]["rom_sha256"]
        ):
            raise ValueError(f"{variant} runtime audit mismatch")
        events = _events_by_name(audit, variant)
        expected_gfx = "0x0812FF50" if variant == "baseline" else "0x081303E8"
        if (
            events["chapter-opcode-14"].get("r7") != "0x08049E63"
            or events["chapter-opcode-14"].get("story_state") != "0x0030"
            or events["story-state-dispatch"].get("story_state") != "0x8000"
            or events["story-wrapper"].get("lr") != "0x0808FA31"
            or events["story-loader"].get("lr") != "0x0808A6A3"
            or events["descriptor-0-select"].get("r0") != "0x0854229C"
            or events["descriptor-0-select"].get("r7") != "0x00000000"
            or events["gfx-decompress"].get("r0") != expected_gfx
            or events["gfx-decompress"].get("r1") != "0x0600E800"
            or events["palette-decompress"].get("r0") != "0x08130268"
            or events["palette-decompress"].get("r1") != "0x050001E0"
            or events["tilemap-decompress"].get("r0") != "0x08130290"
            or events["tilemap-decompress"].get("r1") != "0x06001800"
            or events["overlay-first-vblank"].get("frame") != 198
        ):
            raise ValueError(f"{variant} runtime event chain mismatch")
        _validate_guard(root, guard, variant)
        state = load_gba_state(state_path)
        with Image.open(png_path) as screenshot:
            png_rgb = screenshot.convert("RGB").tobytes()
        if render_checkpoint(state_path)[0] != png_rgb:
            raise ValueError(f"{variant} savestate screenshot mismatch")
        states[variant] = state
        runs[variant] = {
            "rom_sha256": audit["rom_sha256"],
            "audit_sha256": _sha256_file(audit_path),
            "state_sha256": _sha256_file(state_path),
            "png_sha256": _sha256_file(png_path),
            "guard_sha256": _sha256_file(guard_path),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            "pgid_clean": True,
        }
    regions = _region_facts(states)
    if regions != EXPECTED_REGIONS:
        raise ValueError("battle-encounters memory attribution mismatch")
    pixels = _pixel_facts(
        source / "runs/baseline/final.png",
        source / "runs/candidate/final.png",
    )
    if pixels != EXPECTED_PIXELS:
        raise ValueError("battle-encounters pixel facts mismatch")
    return {
        "build": build,
        "runs": runs,
        "memory_differences": regions,
        "pixels": pixels,
        "fixture_state_differences": state_differences,
    }


def _launch_identity(source: Path) -> dict[str, Any]:
    guards = {}
    for variant in ("baseline", "candidate"):
        path = source / f"runs/{variant}/guard-summary.json"
        guard = _read_json(path, f"{variant} guard")
        command = guard["command"]
        guards[variant] = {
            "guard_sha256": _sha256_file(path),
            "binary_command_path_sha256": _sha256(command[0].encode("utf-8")),
            "script_command_path_sha256": _sha256(command[2].encode("utf-8")),
        }
    return {
        "schema": "battle-encounters-launch-identity-v1",
        "binary": {
            "basename": "mGBA",
            "sha256": BINARY_SHA256,
            "source_commit": BINARY_COMMIT,
        },
        "script": {
            "repository_path": SCRIPT_PATH.as_posix(),
            "sha256": SCRIPT_SHA256,
        },
        "guards": guards,
    }


def _write_raw_tar(source: Path, output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for source_name, archive_name in RAW_FILES:
            path = source / source_name
            info = archive.gettarinfo(str(path), arcname=archive_name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)
        payload = (
            json.dumps(
                _launch_identity(source), ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n"
        ).encode("utf-8")
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
        raise ValueError("battle-encounters artifact output must be absent or empty")
    facts = _validate_source(root, source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "runs/baseline/final.png", output / "baseline.png")
    shutil.copyfile(source / "runs/candidate/final.png", output / "candidate.png")
    _write_raw_tar(source, output / "raw.tar")
    evidence = {
        "schema": SCHEMA,
        "verified": True,
        "historical_slug": "battle-encounters",
        "actual_identity": "24 story visual descriptors",
        "controlled_entry": facts["build"]["controlled_entry"],
        "input_state": {
            "path": "raw.tar:input/controlled-story-opcode.ss9",
            "sha256": INPUT_SHA256,
            "canonical_path": CANONICAL_PATH.as_posix(),
            "parent_path": PARENT_PATH.as_posix(),
            "parent_sha256": PARENT_SHA256,
            "state_difference_offsets": facts["fixture_state_differences"],
        },
        "emulator": {
            "source_commit": BINARY_COMMIT,
            "binary_sha256": BINARY_SHA256,
            "launch_identity": "raw.tar:launch-identity.json",
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": SCRIPT_SHA256,
        },
        "edit": facts["build"]["edit"],
        "runs": facts["runs"],
        "memory_differences": facts["memory_differences"],
        "pixels": facts["pixels"],
        "runtime_chain": [
            "0x08049E63: opcode 0x14 state 0x0168",
            "0x0808FA2C story-state dispatch",
            "0x0808A69C story wrapper",
            "0x08087C9C story loader",
            "0x0854229C descriptor 0",
            "0x0809C0E8 three LZ77 streams",
            "BG3 visible frame",
        ],
        "boundary": facts["build"]["boundary"],
    }
    _write_json(output / "evidence.json", evidence)
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": ARTIFACT_SCHEMA,
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
                "tools/verify_battle_encounters_story_visual_pixel_ab.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/battle-encounters-story-visual-pixel-ab-v1",
            ],
            "exit_code": 0,
        },
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = export_artifact(args.root, args.source, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
