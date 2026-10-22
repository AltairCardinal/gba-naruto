#!/usr/bin/env python3
"""Export the natural map-41 visual-resource runtime A/B matrix."""

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
    from tools.inspect_mgba_savestate import (
        load_gba_state,
        png_screen_fingerprint,
    )
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.inspect_mgba_savestate import (
        load_gba_state,
        png_screen_fingerprint,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "map41-visual-resource-matrix-evidence-v1"
ARTIFACT_ID = "map41-visual-resource-matrix-v1"
INPUT_STATE = Path("artifacts/runtime-checkpoints/scenario-41-start-row.ss9")
INPUT_STATE_SHA256 = "e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81"
VARIANTS = ("baseline", "tile_graphics", "bg_palette", "metatile_definitions")
CANDIDATES = VARIANTS[1:]
EVENT = {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "VRAM": (0x06000000, 0x18000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "OAM": (0x07000000, 0x400),
}
EXPECTED_DOMAIN_DIFFS = {
    "tile_graphics": {"VRAM": [0x6A20]},
    "bg_palette": {"PRAM": [0x4A]},
    "metatile_definitions": {"EWRAM": [0x1E05C], "VRAM": [0x418]},
}
EXPECTED_PIXELS = {
    "tile_graphics": (1, [160, 32, 160, 32]),
    "bg_palette": (119, [0, 104, 238, 116]),
    "metatile_definitions": (56, [72, 24, 79, 31]),
}
IMPLEMENTATION_PATHS = (
    "tools/build_map41_visual_resource_matrix.py",
    "tools/export_map41_visual_resource_matrix_evidence.py",
    "tools/verify_map41_visual_resource_matrix_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_map41_visual_resource_matrix.py",
    "tests/test_map41_visual_resource_matrix_evidence.py",
)
VARIANT_FILES = (
    "frame80.ss9",
    "frame80.png",
    "audit.json",
    "sentinel.json",
    "guard.json",
)


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
        raise ValueError("runtime domains have different lengths")
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def _rgb555(value: int) -> tuple[int, int, int]:
    return tuple(
        (((value >> shift) & 31) << 3) | (((value >> shift) & 31) >> 2)
        for shift in (0, 5, 10)
    )


def _render_bg0(state: Any) -> dict[tuple[int, int], tuple[int, int, int]]:
    io = state.read_memory(0x04000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    pram = state.read_memory(0x05000000, 0x400)
    bg0cnt = struct.unpack_from("<H", io, 8)[0]
    scroll_x = struct.unpack_from("<H", io, 0x10)[0] & 0x1FF
    scroll_y = struct.unpack_from("<H", io, 0x12)[0] & 0x1FF
    char_base = ((bg0cnt >> 2) & 3) * 0x4000
    screen_base = ((bg0cnt >> 8) & 31) * 0x800
    output: dict[tuple[int, int], tuple[int, int, int]] = {}
    for y in range(160):
        world_y = (y + scroll_y) & 0xFF
        for x in range(240):
            world_x = (x + scroll_x) & 0xFF
            entry_offset = screen_base + (
                (world_y // 8) * 32 + world_x // 8
            ) * 2
            entry = struct.unpack_from("<H", vram, entry_offset)[0]
            pixel_x = world_x & 7
            pixel_y = world_y & 7
            if entry & 0x0400:
                pixel_x = 7 - pixel_x
            if entry & 0x0800:
                pixel_y = 7 - pixel_y
            byte = vram[
                char_base
                + (entry & 0x03FF) * 32
                + pixel_y * 4
                + pixel_x // 2
            ]
            index = (byte >> (4 * (pixel_x & 1))) & 15
            bank = (entry >> 12) & 15
            color = struct.unpack_from("<H", pram, (bank * 16 + index) * 2)[0]
            output[(x, y)] = _rgb555(color)
    return output


def _image(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise ValueError("mGBA screenshot is not 240x160 RGB")
    return image


def export(root: Path, run_dir: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    run_dir = Path(run_dir).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("map41 visual matrix output already exists")
    build_path = run_dir / "build/build-manifest.json"
    build = _read_json(build_path)
    if (
        build.get("schema") != "map41-visual-resource-matrix-build-v1"
        or set(build.get("variants", {})) != set(VARIANTS)
        or build.get("isolation")
        != {
            "shared_patch_topology": True,
            "only_map41_headers_redirected": True,
            "independent_runtime_required": True,
        }
    ):
        raise ValueError("map41 visual matrix build contract mismatch")
    if _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
        raise ValueError("map41 visual matrix input checkpoint hash mismatch")

    output.mkdir(parents=True)
    shutil.copy2(build_path, output / "build-manifest.json")
    for variant in VARIANTS:
        target = output / variant
        target.mkdir()
        for name in VARIANT_FILES:
            source = run_dir / variant / name
            if not source.is_file():
                raise ValueError(f"missing map41 visual matrix run file: {source}")
            shutil.copy2(source, target / name)

    initial = load_gba_state(root / INPUT_STATE)
    if (
        initial.read_memory(0x02026804, 8) != bytes(8)
        or initial.read_memory(0x0201BE28, 4) != bytes(4)
        or initial.read_memory(0x0201DE2C, 1376) != bytes(1376)
    ):
        raise ValueError("map41 visual matrix parent is not pre-loader zero state")

    states = {
        variant: load_gba_state(output / variant / "frame80.ss9")
        for variant in VARIANTS
    }
    images = {
        variant: _image(output / variant / "frame80.png")
        for variant in VARIANTS
    }
    baseline_bg = _render_bg0(states["baseline"])
    candidates: dict[str, Any] = {}
    guards: dict[str, Any] = {}
    for variant in VARIANTS:
        audit = _read_json(output / variant / "audit.json")
        sentinel = _read_json(output / variant / "sentinel.json")
        guard = _read_json(output / variant / "guard.json")
        if audit != sentinel or audit.get("inputs") != [EVENT]:
            raise ValueError(f"{variant} input audit mismatch")
        if (
            states[variant].read_memory(0x02026805, 1) != bytes([41])
            or states[variant].read_memory(0x0201BE28, 4)
            != bytes([36, 44, 9, 22])
        ):
            raise ValueError(f"{variant} did not reach battle 41 map")
        if (
            png_screen_fingerprint(output / variant / "frame80.ss9")
            != png_screen_fingerprint(output / variant / "frame80.png")
        ):
            raise ValueError(f"{variant} external PNG is not the embedded screenshot")
        if (
            guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
            or guard.get("completion_trigger") != "success-marker"
        ):
            raise ValueError(f"{variant} resource guard mismatch")
        guards[variant] = {
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            "reason": guard["reason"],
            "exit_code": guard["exit_code"],
            "degraded": guard["degraded"],
        }

    for candidate in CANDIDATES:
        domain_diffs = {}
        for label, (address, size) in DOMAINS.items():
            changed = _changed_offsets(
                states["baseline"].read_memory(address, size),
                states[candidate].read_memory(address, size),
            )
            if changed:
                domain_diffs[label] = changed
        if domain_diffs != EXPECTED_DOMAIN_DIFFS[candidate]:
            raise ValueError(f"{candidate} runtime memory isolation mismatch")

        candidate_bg = _render_bg0(states[candidate])
        expected_pixels = [
            [x, y]
            for y in range(160)
            for x in range(240)
            if baseline_bg[(x, y)] != candidate_bg[(x, y)]
            and images["baseline"].getpixel((x, y)) == baseline_bg[(x, y)]
        ]
        actual_pixels = [
            [x, y]
            for y in range(160)
            for x in range(240)
            if images["baseline"].getpixel((x, y))
            != images[candidate].getpixel((x, y))
        ]
        if expected_pixels != actual_pixels:
            raise ValueError(f"{candidate} final pixels do not follow BG0 oracle")
        bbox = [
            min(row[0] for row in actual_pixels),
            min(row[1] for row in actual_pixels),
            max(row[0] for row in actual_pixels),
            max(row[1] for row in actual_pixels),
        ]
        if (len(actual_pixels), bbox) != EXPECTED_PIXELS[candidate]:
            raise ValueError(f"{candidate} pixel denominator mismatch")
        pixel_changes = [
            [
                x,
                y,
                list(images["baseline"].getpixel((x, y))),
                list(images[candidate].getpixel((x, y))),
            ]
            for x, y in actual_pixels
        ]
        candidates[candidate] = {
            "memory_differences": domain_diffs,
            "pixel_count": len(actual_pixels),
            "screen_bbox": bbox,
            "differing_pixels": actual_pixels,
            "pixel_changes": pixel_changes,
        }

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
    evidence = {
        "schema": SCHEMA,
        "input": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "loader_state": "pre-map-load-zero-runtime",
            "event": EVENT,
        },
        "runtime": {
            "battle_id": 41,
            "map_dimensions_hex": "242c0916",
            "display": display,
            "candidates": candidates,
        },
        "resource_guard": guards,
    }
    _write_json(output / "runtime-evidence.json", evidence)

    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "artifact_status": "accepted",
        "parent": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "loader_state": "pre-map-load-zero-runtime",
        },
        "scope": {
            "natural_entry": True,
            "map41_tile_graphics_pixel_ab": True,
            "map41_bg_palette_pixel_ab": True,
            "map41_metatile_definitions_pixel_ab": True,
            "shared_patch_topology": True,
            "preserved_aliases": True,
            "all_maps_all_resources": False,
            "collision_gameplay": False,
            "physical_gba_verified": False,
        },
        "implementation_sha256": {
            path: _sha256(root / path) for path in IMPLEMENTATION_PATHS
        },
        "files": {},
        "payload_file": "runtime-evidence.json",
        "payload_sha256": _sha256(output / "runtime-evidence.json"),
        "verifier": {
            "command": [
                "python3",
                "tools/verify_map41_visual_resource_matrix_evidence.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
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
