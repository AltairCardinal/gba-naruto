#!/usr/bin/env python3
"""Independently verify the persisted original-ROM affine OBJ runtime capture."""

from __future__ import annotations

import argparse
import hashlib
import json
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
RAW_HASHES = {
    "state-0154-io.bin": "2bf6e9817e75b2508e5628e10260d8f9a96dcc8ae652e76e33f4dbe1eec5d8a0",
    "state-0154-oam.bin": "8836ef98597dd670c76069c500fa8020e4af973041b58cdc73e06f34d4aeb294",
    "state-0154-pram.bin": "b7a396594ceb245563c14a1237e186e42db7e0204a663d5ba3e2f98b779e3ce3",
    "state-0154-vram.bin": "4057913232ccf218b707b935f3b034e6c2f66e309b66df91308db8121c91797a",
    "state-0154.png": "54713f2dfc43195aad93adc57344a0e325f543c985d6d07f4639ddfda24602d5",
    "state-0154.ss9": "60028c26e1a529c9542b1e9644dcd35d341cfcfe593cde1b3359c1e2817e3c93",
}
SEQUENCE_FRAMES = tuple(range(152, 180))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raster(
    source: bytes,
    width: int,
    height: int,
    matrix: tuple[int, int, int, int],
) -> bytes:
    pa, pb, pc, pd = matrix
    result = bytearray(width * height)
    for output_y in range(height):
        ry = output_y - height // 2
        for output_x in range(width):
            rx = output_x - width // 2
            source_x = (pa * rx + pb * ry + width * 128) >> 8
            source_y = (pc * rx + pd * ry + height * 128) >> 8
            if 0 <= source_x < width and 0 <= source_y < height:
                result[output_y * width + output_x] = source[
                    source_y * width + source_x
                ]
    return bytes(result)


def _expect(
    condition: bool,
    message: str,
    errors: list[str],
) -> None:
    if not condition:
        errors.append(message)


def verify_battle_effect_affine_runtime(
    root: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    artifact_dir = Path(artifact_dir)
    errors: list[str] = []
    try:
        manifest = json.loads(
            (artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        return {
            "errors": [f"manifest: {error}"],
            "verified_object_count": 0,
            "verified_runtime_frame": None,
        }

    raw: dict[str, bytes] = {}
    for name, digest in RAW_HASHES.items():
        try:
            payload = (artifact_dir / "raw" / name).read_bytes()
        except OSError as error:
            errors.append(f"raw/{name}: {error}")
            continue
        raw[name] = payload
        _expect(_sha256(payload) == digest, f"raw/{name}: hash mismatch", errors)
    if len(raw) != len(RAW_HASHES):
        return {
            "errors": errors,
            "verified_object_count": 0,
            "verified_runtime_frame": None,
        }

    _expect(
        _sha256((root / "rom/base.gba").read_bytes()) == ROM_SHA256,
        "ROM hash mismatch",
        errors,
    )
    io = raw["state-0154-io.bin"]
    oam = raw["state-0154-oam.bin"]
    pram = raw["state-0154-pram.bin"]
    vram = raw["state-0154-vram.bin"]
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, 16)
    matrix_index = (attr1 >> 9) & 0x1F
    matrix = tuple(
        struct.unpack_from("<h", oam, matrix_index * 32 + offset)[0]
        for offset in (6, 14, 22, 30)
    )
    _expect(dispcnt == 0x1B40, "DISPCNT mismatch", errors)
    _expect(
        (attr0, attr1, attr2) == (0x0550, 0x80A0, 0x79D8),
        "object attributes mismatch",
        errors,
    )
    _expect(matrix == (240, 0, 0, 240), "affine matrix mismatch", errors)

    sequence_hashes = {}
    matrix_counts: dict[tuple[int, int, int, int], int] = {}
    affine_instances = 0
    for frame_number in SEQUENCE_FRAMES:
        name = f"gpu-frame-{frame_number:04d}-oam.bin"
        try:
            frame_oam = (
                artifact_dir / "raw" / "sequence-oam" / name
            ).read_bytes()
        except OSError as error:
            errors.append(f"raw/sequence-oam/{name}: {error}")
            continue
        sequence_hashes[name] = _sha256(frame_oam)
        _expect(
            len(frame_oam) == 0x400,
            f"raw/sequence-oam/{name}: size mismatch",
            errors,
        )
        if len(frame_oam) != 0x400:
            continue
        for object_offset in range(0, 0x400, 8):
            item0, item1, item2 = struct.unpack_from(
                "<HHH", frame_oam, object_offset
            )
            if not item0 & 0x0100:
                continue
            if not 472 <= (item2 & 0x3FF) < 776:
                continue
            if ((item2 >> 12) & 0xF) != 7:
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
            affine_instances += 1
    _expect(
        matrix_counts == {(240, 0, 0, 240): 44},
        "sequence affine matrix coverage mismatch",
        errors,
    )
    _expect(
        manifest.get("capture", {}).get("sequence_oam_hashes")
        == sequence_hashes,
        "sequence OAM hashes mismatch",
        errors,
    )

    tile_index = attr2 & 0x3FF
    runtime_tiles = vram[
        0x10000 + tile_index * 32 : 0x10000 + (tile_index + 16) * 32
    ]
    source_tiles = (
        root
        / "artifacts/battle-effect-resource-pairs-v1/"
        "group-02-graphics-4bpp.bin"
    ).read_bytes()[:512]
    runtime_palette = pram[0x2E0:0x300]
    source_palette = (
        root
        / "artifacts/battle-effect-resource-pairs-v1/"
        "group-02-palette-bgr555.bin"
    ).read_bytes()
    _expect(runtime_tiles == source_tiles, "VRAM tiles differ from ROM", errors)
    _expect(
        runtime_palette == source_palette,
        "PRAM palette differs from ROM",
        errors,
    )
    source, width, height = render_4bpp_tile_block_indices(
        runtime_tiles,
        tile_offset=0,
        width_tiles=4,
        height_tiles=4,
    )
    pixels = _raster(source, width, height, matrix)
    pixel_hash = _sha256(pixels)
    _expect(
        pixel_hash
        == "0fc78c8d612c9307624420bb276dd35c3dc4396761bddfd0703cd4a62fe375f1",
        "runtime pixel hash mismatch",
        errors,
    )
    png = indexed_png_from_bgr555(
        pixels,
        runtime_palette,
        width=width,
        height=height,
        transparent_index=0,
    )
    try:
        stored_png = (artifact_dir / "runtime-object-02.png").read_bytes()
        _expect(stored_png == png, "runtime object PNG mismatch", errors)
    except OSError as error:
        errors.append(f"runtime-object-02.png: {error}")

    expected_object = {
        "index": 2,
        "attr0": "0x0550",
        "attr1": "0x80A0",
        "attr2": "0x79D8",
        "position": {"x": 160, "y": 80},
        "dimensions": {"width": 32, "height": 32},
        "affine": True,
        "double_size": False,
        "matrix_index": 0,
        "matrix": {"PA": 240, "PB": 0, "PC": 0, "PD": 240},
        "tile_index": 472,
        "priority": 2,
        "palette_bank": 7,
        "object_mode": "semi_transparent",
    }
    _expect(
        manifest.get("schema") == "battle-effect-affine-runtime-v1",
        "schema mismatch",
        errors,
    )
    _expect(
        manifest.get("rom_sha256") == ROM_SHA256,
        "manifest ROM hash mismatch",
        errors,
    )
    _expect(
        manifest.get("capture")
        == {
            "original_frame": 154,
            "historical_source": (
                "build/battle-presentation-original-probes-20260727-15/"
                "tool49-component-trace"
            ),
            "savestate": "raw/state-0154.ss9",
            "savestate_sha256": RAW_HASHES["state-0154.ss9"],
            "screenshot": "raw/state-0154.png",
            "screenshot_sha256": RAW_HASHES["state-0154.png"],
            "gpu_hashes": {
                name: digest
                for name, digest in RAW_HASHES.items()
                if name.endswith(".bin")
            },
            "sequence_oam_hashes": sequence_hashes,
        },
        "capture manifest mismatch",
        errors,
    )
    _expect(
        manifest.get("display")
        == {
            "dispcnt": "0x1B40",
            "obj_mapping": "1d",
            "screen_dimensions": {"width": 240, "height": 160},
        },
        "display manifest mismatch",
        errors,
    )
    _expect(
        manifest.get("object") == expected_object,
        "object manifest mismatch",
        errors,
    )
    binding = manifest.get("resource_binding", {})
    _expect(
        binding
        == {
            "group_id": 2,
            "frame_id": 1,
            "component_index": 0,
            "vram_tile_sha256": _sha256(runtime_tiles),
            "rom_tile_sha256": _sha256(source_tiles),
            "vram_tiles_match_rom": True,
            "pram_palette_sha256": _sha256(runtime_palette),
            "rom_palette_sha256": _sha256(source_palette),
            "pram_palette_matches_rom": True,
            "runtime_pixel_sha256": pixel_hash,
            "source_model_pixel_sha256": (
                "0fc78c8d612c9307624420bb276dd35c3dc4396761bddfd0703cd4a62fe375f1"
            ),
            "runtime_pixels_match_source_model": True,
            "runtime_object_png": "runtime-object-02.png",
            "runtime_object_png_sha256": _sha256(png),
        },
        "resource binding mismatch",
        errors,
    )
    _expect(
        manifest.get("scope")
        == {
            "normal_runtime_oam_golden_complete": True,
            "mirror_runtime_oam_golden_complete": False,
            "physical_gba_capture_complete": False,
            "full_screen_composition_complete": False,
        },
        "scope mismatch",
        errors,
    )
    _expect(
        manifest.get("sequence_coverage")
        == {
            "frame_start": 152,
            "frame_end": 179,
            "frame_count": 28,
            "affine_component_instances": affine_instances,
            "matrix_counts": [
                {
                    "matrix": {
                        "PA": 240,
                        "PB": 0,
                        "PC": 0,
                        "PD": 240,
                    },
                    "component_instances": 44,
                }
            ],
        },
        "sequence coverage mismatch",
        errors,
    )
    expected_files = sorted(
        ["manifest.json", "runtime-object-02.png"]
        + [f"raw/{name}" for name in RAW_HASHES]
        + [
            f"raw/sequence-oam/gpu-frame-{frame:04d}-oam.bin"
            for frame in SEQUENCE_FRAMES
        ]
    )
    _expect(
        manifest.get("artifact_files") == expected_files,
        "artifact file list mismatch",
        errors,
    )
    _expect(
        manifest.get("artifact_file_count") == len(expected_files),
        "artifact file count mismatch",
        errors,
    )
    return {
        "errors": errors,
        "verified_object_count": 1 if not errors else 0,
        "verified_runtime_frame": 154 if not errors else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    result = verify_battle_effect_affine_runtime(
        args.root, args.artifact_dir
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
