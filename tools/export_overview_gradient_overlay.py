#!/usr/bin/env python3
"""Export and bind the generated BG0 gradient used by the overview controller."""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.thumb_branch import decode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from inspect_mgba_savestate import load_gba_state
    from thumb_branch import decode_thumb_bl


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "overview-gradient-overlay-v1"
VERIFY_SCHEMA = "overview-gradient-overlay-verification-v1"
PAYLOAD_NAME = "overview-gradient-overlay.json"
ROM_RELATIVE = Path("rom/base.gba")
CHECKPOINT_RELATIVE = Path(
    "artifacts/runtime-checkpoints/alternate-character-overview.ss9"
)
PARENT_PAYLOAD_RELATIVE = Path(
    "artifacts/initializer-resource-pack-v1/initializer-resource-pack.json"
)
PARENT_MANIFEST_RELATIVE = Path(
    "artifacts/initializer-resource-pack-v1/manifest.json"
)
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CHECKPOINT_SHA256 = (
    "209bf3c7321fedc93a6c957fb2c7b46f0d48aa56ea5c4bb3858fce93d0a336f6"
)
PARENT_PAYLOAD_SHA256 = (
    "c096e70c033f804548446272c47d43bfefa72eed173841e152c630c5436efba8"
)
PARENT_MANIFEST_SHA256 = (
    "8fc7c3ea449b480c5065a97e70d0f6c5c0fa30a0dc3f942931f6be86264337a4"
)
GENERATOR_RANGE = (0x08D934, 0x08DA80)
GENERATOR_SHA256 = (
    "d5c6e7269c416817aae299d3d987c27abda6c1bde1a1edea0932329ce7179e96"
)
CALLER_RANGE = (0x08DA90, 0x08DBB0)
CALLER_SHA256 = "511f6e58cf79fefdc5a20c37aa968bce976f23eb79bcc80bcd9f3d96810976ef"
CONTROLLER_RANGE = (0x08DCE0, 0x08E08E)
CONTROLLER_SHA256 = (
    "d83823d4dbf8f136c5c119ac1ee2ab8a36955aba30afe80176f0a6dacf290585"
)

WORK_TILES = 0x02002AB0
WORK_PALETTE = 0x02002C10
WORK_TILEMAP = 0x02002C30
VRAM_TILES = 0x06002000
PRAM_PALETTE = 0x050001A0
VRAM_TILEMAP = 0x06000000
TILE_BASE = 0x0100
PALETTE_BANK = 13
TILE_BYTES = 0x160
PALETTE_BYTES = 0x20
MAP_WIDTH = 30
MAP_HEIGHT = 20
MAP_BYTES = MAP_WIDTH * MAP_HEIGHT * 2

SCOPE = {
    "generator_algorithm_code_verified": True,
    "generated_tiles_palette_tilemap_losslessly_exported": True,
    "overview_checkpoint_work_buffers_exact": True,
    "overview_checkpoint_hardware_destinations_exact": True,
    "overview_checkpoint_writer_identity_complete": True,
    "whole_overview_screen_source_identity_complete": False,
    "all_callers_runtime_bound": False,
    "all_game_visual_states_complete": False,
    "generic_image_writeback_complete": False,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _code_record(rom: bytes, start: int, end: int, expected: str) -> dict[str, Any]:
    code = rom[start:end]
    actual = _sha256(code)
    if actual != expected:
        raise ValueError(
            f"ROM code hash changed at 0x{0x08000000 + start:08X}: {actual}"
        )
    return {
        "gba_start": _address(0x08000000 + start),
        "gba_end_exclusive": _address(0x08000000 + end),
        "size": len(code),
        "sha256": actual,
    }


def _require_bl(rom: bytes, address: int, target: int) -> None:
    offset = address - 0x08000000
    first, second = struct.unpack_from("<HH", rom, offset)
    if decode_thumb_bl(address, first, second) != target:
        raise ValueError(
            f"Thumb BL at {_address(address)} no longer targets {_address(target)}"
        )


def generate_tiles() -> bytes:
    """Reproduce 0x0808D934's blank tile plus 80 generated scanlines."""

    tiles = bytearray(TILE_BYTES)
    for y in range(80):
        pixel_index = (y * 15) // 80 + 1
        packed = pixel_index | (pixel_index << 4)
        tile_index = 1 + y // 8
        row = y % 8
        start = tile_index * 32 + row * 4
        tiles[start : start + 4] = bytes((packed,)) * 4
    return bytes(tiles)


def generate_palette() -> bytes:
    colors = []
    for index in range(16):
        component = 0 if index == 0 else 20 - index
        colors.append(component | (component << 5) | (component << 10))
    return struct.pack("<16H", *colors)


def generate_tilemap() -> bytes:
    entries = []
    for row in range(MAP_HEIGHT):
        value = TILE_BASE
        if 4 <= row <= 13:
            value = (PALETTE_BANK << 12) | TILE_BASE | (row - 3)
        entries.extend((value,) * MAP_WIDTH)
    return struct.pack(f"<{len(entries)}H", *entries)


def _rgb555(value: int) -> tuple[int, int, int]:
    channels = ((value >> shift) & 0x1F for shift in (0, 5, 10))
    return tuple((channel << 3) | (channel >> 2) for channel in channels)  # type: ignore[return-value]


def _preview(tiles: bytes, palette: bytes, tilemap: bytes) -> bytes:
    entries = struct.unpack("<600H", tilemap)
    pixels = bytearray(240 * 160)
    for tile_y in range(20):
        for tile_x in range(30):
            entry = entries[tile_y * 30 + tile_x]
            source_tile = (entry & 0x03FF) - TILE_BASE
            if not 0 <= source_tile < 11:
                raise ValueError("generated tilemap references outside generated tiles")
            tile = tiles[source_tile * 32 : source_tile * 32 + 32]
            for py in range(8):
                for px in range(8):
                    packed = tile[py * 4 + px // 2]
                    index = (packed >> (4 * (px & 1))) & 0x0F
                    pixels[(tile_y * 8 + py) * 240 + tile_x * 8 + px] = index

    image = Image.frombytes("P", (240, 160), bytes(pixels))
    colors = struct.unpack("<16H", palette)
    rgb = [component for color in colors for component in _rgb555(color)]
    image.putpalette(rgb + [0] * (768 - len(rgb)))
    image.info["transparency"] = 0
    encoded = BytesIO()
    image.save(encoded, format="PNG", compress_level=9, optimize=False)
    return encoded.getvalue()


def _visible_map(state: Any) -> bytes:
    return b"".join(
        state.read_memory(VRAM_TILEMAP + row * 64, MAP_WIDTH * 2)
        for row in range(MAP_HEIGHT)
    )


def _parent_unmatched_resolution(root: Path, tiles: bytes) -> dict[str, Any]:
    payload_path = root / PARENT_PAYLOAD_RELATIVE
    manifest_path = root / PARENT_MANIFEST_RELATIVE
    payload_bytes = payload_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    if _sha256(payload_bytes) != PARENT_PAYLOAD_SHA256:
        raise ValueError("initializer parent payload SHA-256 changed")
    if _sha256(manifest_bytes) != PARENT_MANIFEST_SHA256:
        raise ValueError("initializer parent manifest SHA-256 changed")
    parent = json.loads(payload_bytes)
    summary = parent["runtime_binding"]["summary"]
    layer = next(
        item
        for item in parent["runtime_binding"]["layers"]
        if item["checkpoint"] == "alternate-character-overview.ss9"
        and item["bg_index"] == 0
    )

    tile_hashes = {
        TILE_BASE + index: _sha256(tiles[index * 32 : (index + 1) * 32])
        for index in range(1, 11)
    }
    resolved = [
        item
        for item in layer["unmatched_nonfont_contents"]
        if item["runtime_tile_sha256"] in set(tile_hashes.values())
    ]
    resolved_ids = sorted(item["runtime_tile_id"] for item in resolved)
    resolved_hashes = {item["runtime_tile_sha256"] for item in resolved}
    resolved_cells = sum(item["cell_count"] for item in resolved)
    layer_hashes = {
        item["runtime_tile_sha256"]
        for item in layer["unmatched_nonfont_contents"]
    }
    all_unmatched = [
        content
        for parent_layer in parent["runtime_binding"]["layers"]
        for content in parent_layer.get("unmatched_nonfont_contents", [])
    ]
    global_hashes = {item["runtime_tile_sha256"] for item in all_unmatched}
    if (
        summary["unmatched_nonfont_cell_count"],
        summary["unmatched_nonfont_distinct_hash_count"],
        layer["unmatched_nonfont_cell_count"],
        len(layer_hashes),
        resolved_cells,
        len(resolved_hashes),
        resolved_ids,
    ) != (898, 39, 717, 17, 300, 10, list(range(257, 267))):
        raise ValueError("initializer parent unmatched denominator changed")
    if any(
        tile_hashes[item["runtime_tile_id"]] != item["runtime_tile_sha256"]
        for item in resolved
    ):
        raise ValueError("generated gradient hash does not match parent unknown tile")

    return {
        "parent": {
            "artifact": PARENT_PAYLOAD_RELATIVE.as_posix(),
            "artifact_sha256": PARENT_PAYLOAD_SHA256,
            "manifest": PARENT_MANIFEST_RELATIVE.as_posix(),
            "manifest_sha256": PARENT_MANIFEST_SHA256,
        },
        "target_layer": {
            "parent_layer_key": layer["parent_layer_key"],
            "parent_layer_sha256": layer["parent_layer_sha256"],
            "checkpoint": layer["checkpoint"],
            "bg_index": layer["bg_index"],
        },
        "baseline": {
            "global_unmatched_cell_count": 898,
            "global_unmatched_distinct_hash_count": len(global_hashes),
            "target_layer_unmatched_cell_count": 717,
            "target_layer_unmatched_distinct_hash_count": len(layer_hashes),
        },
        "resolved": {
            "classification": "generated_overview_gradient_content",
            "cell_count": resolved_cells,
            "distinct_hash_count": len(resolved_hashes),
            "runtime_tile_ids": resolved_ids,
            "runtime_tile_sha256": [
                tile_hashes[tile_id] for tile_id in resolved_ids
            ],
            "parent_records": resolved,
        },
        "remaining": {
            "global_unmatched_cell_count": 898 - resolved_cells,
            "global_unmatched_distinct_hash_count": len(
                global_hashes - resolved_hashes
            ),
            "target_layer_unmatched_cell_count": 717 - resolved_cells,
            "target_layer_unmatched_distinct_hash_count": len(
                layer_hashes - resolved_hashes
            ),
        },
        "scope": (
            "This subtracts only exact generated tile-content matches from the "
            "hash-bound initializer unknown denominator; it does not reclassify "
            "the remaining target layer or any untracked visual state."
        ),
    }


def _build_payload(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom_path = root / ROM_RELATIVE
    checkpoint_path = root / CHECKPOINT_RELATIVE
    rom = rom_path.read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    checkpoint_bytes = checkpoint_path.read_bytes()
    if _sha256(checkpoint_bytes) != CHECKPOINT_SHA256:
        raise ValueError("overview checkpoint SHA-256 changed")

    generator_code = _code_record(rom, *GENERATOR_RANGE, GENERATOR_SHA256)
    caller_code = _code_record(rom, *CALLER_RANGE, CALLER_SHA256)
    controller_code = _code_record(rom, *CONTROLLER_RANGE, CONTROLLER_SHA256)
    _require_bl(rom, 0x0808DAB8, 0x0808D934)
    _require_bl(rom, 0x0808DCFC, 0x0808DA90)

    tiles = generate_tiles()
    palette = generate_palette()
    tilemap = generate_tilemap()
    preview = _preview(tiles, palette, tilemap)
    state = load_gba_state(checkpoint_path)
    task_raw = state.read_memory(0x03000A88 + 0x4C, 0x4C)
    task_lr = struct.unpack_from("<I", task_raw, 8)[0]
    task_sp = struct.unpack_from("<I", task_raw, 4)[0]
    runtime_domains = {
        "work_tiles": state.read_memory(WORK_TILES, TILE_BYTES),
        "work_palette": state.read_memory(WORK_PALETTE, PALETTE_BYTES),
        "work_tilemap": state.read_memory(WORK_TILEMAP, MAP_BYTES),
        "vram_tiles": state.read_memory(VRAM_TILES, TILE_BYTES),
        "pram_palette": state.read_memory(PRAM_PALETTE, PALETTE_BYTES),
        "vram_tilemap_visible_30x20": _visible_map(state),
    }
    generated_domains = {
        "work_tiles": tiles,
        "work_palette": palette,
        "work_tilemap": tilemap,
        "vram_tiles": tiles,
        "pram_palette": palette,
        "vram_tilemap_visible_30x20": tilemap,
    }
    exact_matches = {
        key: runtime_domains[key] == generated_domains[key]
        for key in runtime_domains
    }
    if not all(exact_matches.values()):
        failed = [key for key, value in exact_matches.items() if not value]
        raise ValueError(f"checkpoint differs from generated domains: {failed}")
    if task_raw[0] != 2 or task_sp != 0x030011D4 or task_lr != 0x0808DF1B:
        raise ValueError("checkpoint active task no longer resumes in overview controller")
    bg0cnt = struct.unpack("<H", state.read_memory(0x04000008, 2))[0]
    if bg0cnt != 0x0002:
        raise ValueError(f"checkpoint BG0CNT changed to 0x{bg0cnt:04X}")

    files = {
        "generated-tiles.4bpp.bin": tiles,
        "generated-palette.bgr555.bin": palette,
        "generated-tilemap-30x20.bin": tilemap,
        "overview-gradient-overlay.png": preview,
    }
    verifier_path = root / "tools/verify_overview_gradient_overlay.py"
    test_path = root / "tests/test_export_overview_gradient_overlay.py"
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha256(Path(__file__).read_bytes()),
            "verifier_sha256": _sha256(verifier_path.read_bytes()),
            "test_sha256": _sha256(test_path.read_bytes()),
        },
        "rom": {"file": ROM_RELATIVE.as_posix(), "sha256": ROM_SHA256},
        "generator": {
            "code": generator_code,
            "formulas": {
                "pixel_index": "floor(y * 15 / 80) + 1",
                "tile_scanline": (
                    "pixel_index repeated across all 8 pixels of scanline y"
                ),
                "palette_component": "0 if index == 0 else 20 - index",
                "palette_bgr555": (
                    "component | component << 5 | component << 10"
                ),
            },
            "destinations": {
                "work_tiles": _address(WORK_TILES),
                "work_palette": _address(WORK_PALETTE),
                "work_tilemap": _address(WORK_TILEMAP),
                "vram_tiles": _address(VRAM_TILES),
                "pram_palette": _address(PRAM_PALETTE),
                "vram_tilemap": _address(VRAM_TILEMAP),
            },
            "copy_routes": [
                {
                    "call": "0x0808D9C6",
                    "source": _address(WORK_TILES),
                    "destination": _address(VRAM_TILES),
                    "size": TILE_BYTES,
                },
                {
                    "call": "0x0808DA0E",
                    "source": _address(WORK_PALETTE),
                    "destination": _address(PRAM_PALETTE),
                    "size": PALETTE_BYTES,
                },
                {
                    "call": "0x0808DA6E",
                    "source": _address(WORK_TILEMAP),
                    "destination": _address(VRAM_TILEMAP),
                    "dimensions": [MAP_WIDTH, MAP_HEIGHT],
                    "destination_stride_cells": 32,
                },
            ],
        },
        "caller": {
            "code": caller_code,
            "gba_address": "0x0808DA90",
            "generator_call": "0x0808DAB8",
            "generator_parameters": {
                "work_buffer": _address(WORK_TILES),
                "charblock": 0,
                "tile_base": TILE_BASE,
                "palette_bank": PALETTE_BANK,
            },
            "bg0cnt_write": "0x0808DABC",
            "bg0cnt_value": "0x0002",
        },
        "controller": {
            "code": controller_code,
            "gba_address": "0x0808DCE0",
            "caller_call": "0x0808DCFC",
            "resume_after_yield": "0x0808DF1A",
        },
        "generated": {
            "tiles": {
                "file": "generated-tiles.4bpp.bin",
                "size": len(tiles),
                "sha256": _sha256(tiles),
                "tile_count": len(tiles) // 32,
                "tile_base": TILE_BASE,
            },
            "palette": {
                "file": "generated-palette.bgr555.bin",
                "size": len(palette),
                "sha256": _sha256(palette),
                "color_count": len(palette) // 2,
                "palette_bank": PALETTE_BANK,
            },
            "tilemap": {
                "file": "generated-tilemap-30x20.bin",
                "size": len(tilemap),
                "sha256": _sha256(tilemap),
                "dimensions": [MAP_WIDTH, MAP_HEIGHT],
                "layout": {
                    "blank_tile": TILE_BASE,
                    "gradient_rows": [
                        {"row": row, "tile": 0xD101 + row - 4}
                        for row in range(4, 14)
                    ],
                    "palette_bank": PALETTE_BANK,
                },
            },
            "preview": {
                "file": "overview-gradient-overlay.png",
                "sha256": _sha256(preview),
                "dimensions": [240, 160],
                "semantics": "generated BG0 overlay before other BG/OBJ composition",
            },
        },
        "runtime_binding": {
            "checkpoint": CHECKPOINT_RELATIVE.as_posix(),
            "checkpoint_sha256": CHECKPOINT_SHA256,
            "active_task": {
                "slot": 2,
                "type": task_raw[0],
                "sp": _address(task_sp),
                "lr": _address(task_lr),
                "resume_pc": _address(task_lr - 1),
                "controller_range": [
                    controller_code["gba_start"],
                    controller_code["gba_end_exclusive"],
                ],
            },
            "bg0cnt": f"0x{bg0cnt:04X}",
            "exact_matches": exact_matches,
            "runtime_sha256": {
                key: _sha256(value) for key, value in runtime_domains.items()
            },
            "tilemap_exact_cell_count": MAP_WIDTH * MAP_HEIGHT,
            "tilemap_cell_count": MAP_WIDTH * MAP_HEIGHT,
            "identity_status": "checkpoint_writer_proven",
            "evidence_contract": (
                "hash-bound generator and caller code, active overview controller "
                "task, and exact generated EWRAM/VRAM/PRAM domains jointly bind "
                "this checkpoint; no claim is made for unobserved callers"
            ),
        },
        "parent_unmatched_resolution": _parent_unmatched_resolution(root, tiles),
        "scope": SCOPE,
    }
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files[PAYLOAD_NAME] = payload_bytes
    return payload, files


def _promotion(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            relative: _sha256(data) for relative, data in sorted(files.items())
        },
        "source": {
            "rom_sha256": ROM_SHA256,
            "checkpoint_sha256": CHECKPOINT_SHA256,
            "generator_gba_address": "0x0808D934",
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_overview_gradient_overlay.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/overview-gradient-overlay-v1",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_overview_gradient_overlay.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/overview-gradient-overlay-v1",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "tilemap_exact_cell_count": 600,
                "errors": [],
            },
        },
    }


def validate_output_target(root: Path, output: Path) -> Path:
    root = root.resolve()
    requested = output.expanduser()
    if requested.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = requested.resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be the repository or its ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("existing output target is not a directory")
        try:
            existing = json.loads(
                (target / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            raise ValueError("refusing to replace output not owned by this artifact") from error
        if existing.get("artifact_schema") != SCHEMA:
            raise ValueError("refusing to replace output not owned by this artifact")
    return target


def _replace_output(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup: Path | None = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and output.exists():
            shutil.rmtree(backup)


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    payload, files = _build_payload(root)
    output = validate_output_target(root, Path(output_dir))
    _replace_output(output, files, _promotion(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/overview-gradient-overlay-v1"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(
        json.dumps(
            payload["runtime_binding"], ensure_ascii=False, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
