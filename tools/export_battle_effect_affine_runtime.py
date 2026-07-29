#!/usr/bin/env python3
"""Persist and decode a runtime affine OBJ capture from the original ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.gba_image_export import (
    indexed_png_from_bgr555,
    render_4bpp_tile_block_indices,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STATIC_MANIFEST = "artifacts/battle-effect-sprite-animations-v1/manifest.json"
RESOURCE_ROOT = "artifacts/battle-effect-resource-pairs-v1"
RAW_NAMES = (
    "state-0154-io.bin",
    "state-0154-oam.bin",
    "state-0154-pram.bin",
    "state-0154-vram.bin",
    "state-0154.png",
    "state-0154.ss9",
)
SEQUENCE_FRAMES = tuple(range(152, 180))
EXPECTED_HASHES = {
    "state-0154-io.bin": "2bf6e9817e75b2508e5628e10260d8f9a96dcc8ae652e76e33f4dbe1eec5d8a0",
    "state-0154-oam.bin": "8836ef98597dd670c76069c500fa8020e4af973041b58cdc73e06f34d4aeb294",
    "state-0154-pram.bin": "b7a396594ceb245563c14a1237e186e42db7e0204a663d5ba3e2f98b779e3ce3",
    "state-0154-vram.bin": "4057913232ccf218b707b935f3b034e6c2f66e309b66df91308db8121c91797a",
    "state-0154.png": "54713f2dfc43195aad93adc57344a0e325f543c985d6d07f4639ddfda24602d5",
    "state-0154.ss9": "60028c26e1a529c9542b1e9644dcd35d341cfcfe593cde1b3359c1e2817e3c93",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raster(
    source: bytes,
    width: int,
    height: int,
    matrix: tuple[int, int, int, int],
) -> bytes:
    pa, pb, pc, pd = matrix
    output = bytearray(width * height)
    for y in range(height):
        relative_y = y - height // 2
        for x in range(width):
            relative_x = x - width // 2
            source_x = (
                pa * relative_x + pb * relative_y + (width << 7)
            ) >> 8
            source_y = (
                pc * relative_x + pd * relative_y + (height << 7)
            ) >> 8
            if 0 <= source_x < width and 0 <= source_y < height:
                output[y * width + x] = source[source_y * width + source_x]
    return bytes(output)


def _manifest(
    root: Path,
    raw_dir: Path,
) -> tuple[dict[str, Any], bytes]:
    raw = {name: (raw_dir / name).read_bytes() for name in RAW_NAMES}
    hashes = {name: _sha256(payload) for name, payload in raw.items()}
    if hashes != EXPECTED_HASHES:
        raise ValueError("runtime affine capture hashes do not match")
    if _sha256((root / "rom/base.gba").read_bytes()) != ROM_SHA256:
        raise ValueError("ROM SHA-256 mismatch")

    io = raw["state-0154-io.bin"]
    oam = raw["state-0154-oam.bin"]
    pram = raw["state-0154-pram.bin"]
    vram = raw["state-0154-vram.bin"]
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    if dispcnt != 0x1B40:
        raise ValueError("unexpected DISPCNT")
    object_index = 2
    attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, object_index * 8)
    if (attr0, attr1, attr2) != (0x0550, 0x80A0, 0x79D8):
        raise ValueError("unexpected affine OAM object")
    matrix_index = (attr1 >> 9) & 0x1F
    matrix = tuple(
        struct.unpack_from("<h", oam, matrix_index * 32 + offset)[0]
        for offset in (6, 14, 22, 30)
    )
    if matrix != (240, 0, 0, 240):
        raise ValueError("unexpected affine matrix")

    sequence_hashes = {}
    matrix_counts: dict[tuple[int, int, int, int], int] = {}
    affine_component_instances = 0
    for frame_number in SEQUENCE_FRAMES:
        name = f"gpu-frame-{frame_number:04d}-oam.bin"
        frame_oam = (raw_dir / "sequence-oam" / name).read_bytes()
        if len(frame_oam) != 0x400:
            raise ValueError(f"{name} is not a complete OAM dump")
        sequence_hashes[name] = _sha256(frame_oam)
        for object_offset in range(0, 0x400, 8):
            item0, item1, item2 = struct.unpack_from(
                "<HHH", frame_oam, object_offset
            )
            if not item0 & 0x0100:
                continue
            item_tile = item2 & 0x3FF
            if not 472 <= item_tile < 472 + 304:
                continue
            if (item2 >> 12) & 0xF != 7:
                continue
            item_matrix_index = (item1 >> 9) & 0x1F
            item_matrix = tuple(
                struct.unpack_from(
                    "<h",
                    frame_oam,
                    item_matrix_index * 32 + parameter_offset,
                )[0]
                for parameter_offset in (6, 14, 22, 30)
            )
            matrix_counts[item_matrix] = matrix_counts.get(item_matrix, 0) + 1
            affine_component_instances += 1
    if matrix_counts != {(240, 0, 0, 240): 44}:
        raise ValueError("unexpected affine sequence matrix coverage")

    tile_index = attr2 & 0x3FF
    tile_bytes = vram[
        0x10000 + tile_index * 32 : 0x10000 + (tile_index + 16) * 32
    ]
    graphics_path = (
        root / RESOURCE_ROOT / "group-02-graphics-4bpp.bin"
    )
    rom_tiles = graphics_path.read_bytes()[:512]
    palette = pram[0x200 + 7 * 32 : 0x200 + 8 * 32]
    rom_palette = (
        root / RESOURCE_ROOT / "group-02-palette-bgr555.bin"
    ).read_bytes()
    source, width, height = render_4bpp_tile_block_indices(
        tile_bytes,
        tile_offset=0,
        width_tiles=4,
        height_tiles=4,
    )
    runtime_pixels = _raster(source, width, height, matrix)
    png = indexed_png_from_bgr555(
        runtime_pixels,
        palette,
        width=width,
        height=height,
        transparent_index=0,
    )

    static = json.loads(
        (root / STATIC_MANIFEST).read_text(encoding="utf-8")
    )
    group = next(item for item in static["groups"] if item["group_id"] == 2)
    frame = next(item for item in group["frames"] if item["frame_id"] == 1)
    reference = next(
        item
        for item in frame["components"][0]["affine_reference_previews"]
        if item["variant"] == "normal"
    )
    runtime_pixel_sha256 = _sha256(runtime_pixels)
    if runtime_pixel_sha256 != reference["pixel_sha256"]:
        raise ValueError("runtime pixels do not match source-model preview")

    artifact_files = sorted(
        ["manifest.json", "runtime-object-02.png"]
        + [f"raw/{name}" for name in RAW_NAMES]
        + [
            f"raw/sequence-oam/gpu-frame-{frame:04d}-oam.bin"
            for frame in SEQUENCE_FRAMES
        ]
    )
    manifest = {
        "schema": "battle-effect-affine-runtime-v1",
        "rom_sha256": ROM_SHA256,
        "capture": {
            "original_frame": 154,
            "historical_source": (
                "build/battle-presentation-original-probes-20260727-15/"
                "tool49-component-trace"
            ),
            "savestate": "raw/state-0154.ss9",
            "savestate_sha256": hashes["state-0154.ss9"],
            "screenshot": "raw/state-0154.png",
            "screenshot_sha256": hashes["state-0154.png"],
            "gpu_hashes": {
                name: hashes[name]
                for name in RAW_NAMES
                if name.endswith(".bin")
            },
            "sequence_oam_hashes": sequence_hashes,
        },
        "display": {
            "dispcnt": "0x1B40",
            "obj_mapping": "1d",
            "screen_dimensions": {"width": 240, "height": 160},
        },
        "object": {
            "index": object_index,
            "attr0": "0x0550",
            "attr1": "0x80A0",
            "attr2": "0x79D8",
            "position": {"x": 160, "y": 80},
            "dimensions": {"width": 32, "height": 32},
            "affine": True,
            "double_size": False,
            "matrix_index": matrix_index,
            "matrix": {
                "PA": matrix[0],
                "PB": matrix[1],
                "PC": matrix[2],
                "PD": matrix[3],
            },
            "tile_index": tile_index,
            "priority": (attr2 >> 10) & 3,
            "palette_bank": (attr2 >> 12) & 0xF,
            "object_mode": "semi_transparent",
        },
        "resource_binding": {
            "group_id": 2,
            "frame_id": 1,
            "component_index": 0,
            "vram_tile_sha256": _sha256(tile_bytes),
            "rom_tile_sha256": _sha256(rom_tiles),
            "vram_tiles_match_rom": tile_bytes == rom_tiles,
            "pram_palette_sha256": _sha256(palette),
            "rom_palette_sha256": _sha256(rom_palette),
            "pram_palette_matches_rom": palette == rom_palette,
            "runtime_pixel_sha256": runtime_pixel_sha256,
            "source_model_pixel_sha256": reference["pixel_sha256"],
            "runtime_pixels_match_source_model": (
                runtime_pixel_sha256 == reference["pixel_sha256"]
            ),
            "runtime_object_png": "runtime-object-02.png",
            "runtime_object_png_sha256": _sha256(png),
        },
        "sequence_coverage": {
            "frame_start": SEQUENCE_FRAMES[0],
            "frame_end": SEQUENCE_FRAMES[-1],
            "frame_count": len(SEQUENCE_FRAMES),
            "affine_component_instances": affine_component_instances,
            "matrix_counts": [
                {
                    "matrix": {
                        "PA": item_matrix[0],
                        "PB": item_matrix[1],
                        "PC": item_matrix[2],
                        "PD": item_matrix[3],
                    },
                    "component_instances": count,
                }
                for item_matrix, count in sorted(matrix_counts.items())
            ],
        },
        "scope": {
            "normal_runtime_oam_golden_complete": True,
            "mirror_runtime_oam_golden_complete": False,
            "physical_gba_capture_complete": False,
            "full_screen_composition_complete": False,
        },
        "artifact_file_count": len(artifact_files),
        "artifact_files": artifact_files,
    }
    return manifest, png


def export_battle_effect_affine_runtime(
    root: Path | str,
    raw_dir: Path | str,
    output_dir: Path | str | None,
) -> dict[str, Any]:
    root = Path(root)
    raw_dir = Path(raw_dir)
    manifest, png = _manifest(root, raw_dir)
    if output_dir is not None:
        output_dir = Path(output_dir)
        target_raw = output_dir / "raw"
        target_raw.mkdir(parents=True, exist_ok=True)
        for name in RAW_NAMES:
            source = raw_dir / name
            target = target_raw / name
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
        target_sequence = target_raw / "sequence-oam"
        target_sequence.mkdir(parents=True, exist_ok=True)
        for frame in SEQUENCE_FRAMES:
            name = f"gpu-frame-{frame:04d}-oam.bin"
            source = raw_dir / "sequence-oam" / name
            target = target_sequence / name
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
        (output_dir / "runtime-object-02.png").write_bytes(png)
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = export_battle_effect_affine_runtime(
        args.root, args.raw_dir, args.output_dir
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
