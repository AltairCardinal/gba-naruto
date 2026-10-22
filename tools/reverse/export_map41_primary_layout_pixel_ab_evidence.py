#!/usr/bin/env python3
"""Promote the natural map-41 primary-layout modified-ROM pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.inspect_mgba_savestate import load_gba_state


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "map41-primary-layout-pixel-ab-evidence-v1"
ARTIFACT_ID = "map41-primary-layout-pixel-ab-v1"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
RUNTIME_WORD = 0x0201BF08
VRAM_ENTRY_ADDRESSES = [
    0x06000308,
    0x0600030A,
    0x0600030C,
    0x0600030E,
    0x06000348,
    0x0600034A,
    0x0600034C,
    0x0600034E,
]
IMPLEMENTATION_PATHS = (
    "tools/build_map41_primary_layout_pixel_ab.py",
    "tools/export_map41_primary_layout_pixel_ab_evidence.py",
    "tools/verify_map41_primary_layout_pixel_ab_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_map41_primary_layout_pixel_ab.py",
    "tests/test_map41_primary_layout_pixel_ab_evidence.py",
)
VARIANT_FILES = (
    "frame80.ss9",
    "frame80.png",
    "audit.json",
    "sentinel.json",
    "guard.json",
)
EVENT = {
    "key": "A",
    "down_frame": 5,
    "up_frame": 13,
    "hold_frames": 8,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("A/B memory domains have different lengths")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def _changed_pixels(left_path: Path, right_path: Path) -> list[list[int]]:
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != (240, 160) or right.size != left.size:
        raise ValueError("A/B screenshots are not 240x160 RGB frames")
    return [
        [x, y]
        for y in range(160)
        for x in range(240)
        if left.getpixel((x, y)) != right.getpixel((x, y))
    ]


def export(root: Path, run_dir: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    run_dir = Path(run_dir).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("map41 pixel A/B artifact output already exists")
    build_path = run_dir / "build/build-manifest.json"
    build = _read_json(build_path)
    if (
        build.get("schema") != "map41-primary-layout-pixel-ab-build-v1"
        or build.get("runtime_source_pointer") != "0x08980000"
        or build.get("edit", {}).get("map_id") != 41
    ):
        raise ValueError("map41 pixel A/B build manifest contract mismatch")

    output.mkdir(parents=True)
    shutil.copy2(build_path, output / "build-manifest.json")
    for variant in ("baseline", "candidate"):
        target = output / variant
        target.mkdir()
        for name in VARIANT_FILES:
            source = run_dir / variant / name
            if not source.is_file():
                raise ValueError(f"missing map41 pixel A/B run file: {source}")
            shutil.copy2(source, target / name)

    if _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
        raise ValueError("map41 pixel A/B input checkpoint hash mismatch")
    initial = load_gba_state(root / INPUT_STATE)
    if (
        initial.read_memory(0x02026804, 8) != bytes(8)
        or initial.read_memory(0x0201BE28, 4) != bytes(4)
        or initial.read_memory(RUNTIME_WORD, 4) != bytes(4)
    ):
        raise ValueError("map41 pixel A/B input is not before the map loader")

    states = {
        variant: load_gba_state(output / variant / "frame80.ss9")
        for variant in ("baseline", "candidate")
    }
    for variant in ("baseline", "candidate"):
        audit = _read_json(output / variant / "audit.json")
        sentinel = _read_json(output / variant / "sentinel.json")
        if audit != sentinel or audit.get("inputs") != [EVENT]:
            raise ValueError(f"{variant} finalized input audit mismatch")
        if (
            states[variant].read_memory(0x02026805, 1) != bytes([41])
            or states[variant].read_memory(0x0201BE28, 4)
            != bytes([36, 44, 9, 22])
        ):
            raise ValueError(f"{variant} did not reach natural battle 41 map")
    baseline_word = struct.unpack(
        "<I", states["baseline"].read_memory(RUNTIME_WORD, 4)
    )[0]
    candidate_word = struct.unpack(
        "<I", states["candidate"].read_memory(RUNTIME_WORD, 4)
    )[0]
    if (baseline_word, candidate_word) != (0x00350022, 0x00220035):
        raise ValueError("map41 pixel A/B runtime layout word mismatch")

    ewram_diff = _changed_offsets(
        states["baseline"].read_memory(0x02000000, 0x40000),
        states["candidate"].read_memory(0x02000000, 0x40000),
    )
    vram_diff = _changed_offsets(
        states["baseline"].read_memory(0x06000000, 0x18000),
        states["candidate"].read_memory(0x06000000, 0x18000),
    )
    if ewram_diff != [0x1BF08, 0x1BF0A] or vram_diff != [
        address - 0x06000000 for address in VRAM_ENTRY_ADDRESSES
    ]:
        raise ValueError("map41 pixel A/B runtime memory isolation mismatch")
    for address, size, label in (
        (0x04000000, 0x400, "IO"),
        (0x05000000, 0x400, "PRAM"),
        (0x07000000, 0x400, "OAM"),
    ):
        if states["baseline"].read_memory(address, size) != states[
            "candidate"
        ].read_memory(address, size):
            raise ValueError(f"map41 pixel A/B full {label} differs")

    display = {
        "dispcnt": struct.unpack(
            "<H", states["baseline"].read_memory(0x04000000, 2)
        )[0],
        "bg0cnt": struct.unpack(
            "<H", states["baseline"].read_memory(0x04000008, 2)
        )[0],
        "bg0hofs": struct.unpack(
            "<H", states["baseline"].read_memory(0x04000010, 2)
        )[0],
        "bg0vofs": struct.unpack(
            "<H", states["baseline"].read_memory(0x04000012, 2)
        )[0],
    }
    vram_entries = {
        variant: [
            struct.unpack("<H", states[variant].read_memory(address, 2))[0]
            for address in VRAM_ENTRY_ADDRESSES
        ]
        for variant in ("baseline", "candidate")
    }
    pixels = _changed_pixels(
        output / "baseline/frame80.png",
        output / "candidate/frame80.png",
    )
    bbox = [
        min(row[0] for row in pixels),
        min(row[1] for row in pixels),
        max(row[0] for row in pixels),
        max(row[1] for row in pixels),
    ]
    if len(pixels) != 204 or bbox != [8, 0, 39, 7]:
        raise ValueError("map41 pixel A/B screenshot difference mismatch")

    evidence = {
        "schema": SCHEMA,
        "input": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "pre_map_dimensions_hex": "00000000",
            "pre_runtime_word_hex": "00000000",
            "event": EVENT,
        },
        "edit": build["edit"],
        "runtime": {
            "battle_id": 41,
            "map_dimensions_hex": "242c0916",
            "runtime_layout_base": "0x0201BE2C",
            "runtime_word_address": "0x0201BF08",
            "baseline_word": "0x00350022",
            "candidate_word": "0x00220035",
            "ewram_differing_addresses": ["0x0201BF08", "0x0201BF0A"],
            "vram_differing_addresses": [
                f"0x{address:08X}" for address in VRAM_ENTRY_ADDRESSES
            ],
            "display": display,
            "vram_entries": vram_entries,
        },
        "pixel_result": {
            "differing_pixel_count": len(pixels),
            "screen_bbox": bbox,
            "differing_pixels": pixels,
        },
        "resource_guard": {
            variant: {
                "peak_tree_rss_mib": _read_json(
                    output / variant / "guard.json"
                )["peak_tree_rss_mib"],
                "reason": "completed",
                "degraded": False,
            }
            for variant in ("baseline", "candidate")
        },
    }
    _write_json(output / "runtime-evidence.json", evidence)

    verifier_command = [
        "python3",
        "tools/verify_map41_primary_layout_pixel_ab_evidence.py",
        "--root",
        ".",
        "--artifact",
        f"artifacts/{ARTIFACT_ID}",
    ]
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "artifact_status": "accepted",
        "parent": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "loader_state": "pre-map-load",
        },
        "scope": {
            "natural_entry": True,
            "preloader_zero_to_runtime_resource_verified": True,
            "map41_alias_split_verified": True,
            "exact_ewram_vram_pixel_diff_verified": True,
            "exact_loader_pc_runtime_trace": False,
            "full_camera_timing": False,
            "physical_gba_verified": False,
        },
        "implementation_sha256": {
            path: _sha256(root / path) for path in IMPLEMENTATION_PATHS
        },
        "files": {},
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256(output / "runtime-evidence.json"),
        "verifier": {"command": verifier_command, "exit_code": 0},
    }
    manifest["files"] = {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.root, args.run_dir, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
