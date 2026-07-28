#!/usr/bin/env python3
"""Export the complete ROM-backed menu/story portrait matrix as indexed PNG."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import (
    gba_address,
    gba_pointer,
    indexed_png_from_bgr555,
    read_lz77_record,
    sha256,
)


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x5A4DEC
TABLE_ENTRY_COUNT = 63
TABLE_ENTRY_SIZE = 0x28
VARIANTS_PER_ENTRY = 5
SPECIAL_PAIR_OFFSET = TABLE_OFFSET - 8
PORTRAIT_WIDTH = 80
PORTRAIT_HEIGHT = 80
PORTRAIT_BYTES = PORTRAIT_WIDTH * PORTRAIT_HEIGHT
PORTRAIT_COLORS = 64

# The original 8bpp OBJ task loads six hardware-supported shapes.  The
# decompressed stream follows component order rather than a flat 10x10 tile
# atlas, so these rectangles are required to reconstruct the 80x80 canvas.
PORTRAIT_COMPONENTS = (
    (64, 64, 16, 16, 0, 256),
    (64, 32, 16, 32, 256, 512),
    (64, 0, 16, 32, 768, 512),
    (32, 64, 32, 16, 1280, 512),
    (0, 64, 32, 16, 1792, 512),
    (0, 0, 64, 64, 2304, 4096),
)


def render_portrait_indices(graphics: bytes) -> bytes:
    """Convert the original six-component 8bpp OBJ stream to an 80x80 canvas."""
    if len(graphics) != PORTRAIT_BYTES:
        raise ValueError(
            f"expected {PORTRAIT_BYTES} portrait bytes, got {len(graphics)}"
        )

    output = bytearray(PORTRAIT_BYTES)
    covered = bytearray(PORTRAIT_BYTES)
    for x, y, width, height, source_offset, source_size in PORTRAIT_COMPONENTS:
        if width * height != source_size:
            raise ValueError("portrait component size does not match its shape")
        if source_offset < 0 or source_offset + source_size > len(graphics):
            raise ValueError("portrait component exceeds the graphics stream")
        tiles_wide = width // 8
        for local_y in range(height):
            tile_y, pixel_y = divmod(local_y, 8)
            for local_x in range(width):
                tile_x, pixel_x = divmod(local_x, 8)
                tile_index = tile_y * tiles_wide + tile_x
                source = (
                    source_offset
                    + tile_index * 64
                    + pixel_y * 8
                    + pixel_x
                )
                destination = (
                    (y + local_y) * PORTRAIT_WIDTH + x + local_x
                )
                if covered[destination]:
                    raise ValueError("portrait components overlap")
                output[destination] = graphics[source]
                covered[destination] = 1
    if not all(covered):
        raise ValueError("portrait components do not cover the canvas")
    return bytes(output)


def _load_sources(
    rom: bytes,
    matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    if (
        matrix.get("table_offset") != TABLE_OFFSET
        or matrix.get("entry_count") != TABLE_ENTRY_COUNT
        or matrix.get("entry_size") != TABLE_ENTRY_SIZE
        or len(matrix.get("entries", [])) != TABLE_ENTRY_COUNT
        or matrix.get("verification") != "runtime_verified"
    ):
        raise ValueError("unexpected visual variant matrix")

    sources: list[dict[str, Any]] = []
    for record_id, entry in enumerate(matrix["entries"]):
        if entry.get("_index") != record_id:
            raise ValueError(f"portrait matrix row {record_id} has wrong index")
        row_offset = TABLE_OFFSET + record_id * TABLE_ENTRY_SIZE
        rom_values = struct.unpack_from("<10I", rom, row_offset)
        for variant in range(VARIANTS_PER_ENTRY):
            gfx_pointer = entry.get(f"gfx_ptr_{variant}")
            palette_pointer = entry.get(f"palette_ptr_{variant}")
            expected = rom_values[variant * 2 : variant * 2 + 2]
            if (gfx_pointer, palette_pointer) != expected:
                raise ValueError(
                    "portrait bank diverges from ROM at "
                    f"record {record_id}, variant {variant}"
                )
            if record_id == 0:
                if gfx_pointer or palette_pointer:
                    raise ValueError("portrait record 0 must remain all zero")
                continue
            if not gfx_pointer or not palette_pointer:
                raise ValueError(
                    f"portrait {record_id}/{variant} has a partial zero pair"
                )
            pair_offset = row_offset + variant * 8
            sources.append(
                {
                    "portrait_id": record_id,
                    "variant": variant,
                    "kind": "matrix",
                    "pair_file_offset": pair_offset,
                    "gfx_pointer_int": gfx_pointer,
                    "palette_pointer_int": palette_pointer,
                    "png": (
                        f"portrait_{record_id:02d}_variant_{variant}.png"
                    ),
                }
            )

    special = matrix.get("special_variant_5", {})
    special_gfx, special_palette = struct.unpack_from(
        "<II", rom, SPECIAL_PAIR_OFFSET
    )
    if special != {
        "gfx_ptr": special_gfx,
        "palette_ptr": special_palette,
    }:
        raise ValueError("special portrait variant diverges from ROM")
    sources.append(
        {
            "portrait_id": None,
            "variant": 5,
            "kind": "global_special",
            "pair_file_offset": SPECIAL_PAIR_OFFSET,
            "gfx_pointer_int": special_gfx,
            "palette_pointer_int": special_palette,
            "png": "special_variant_5.png",
        }
    )
    return sources


def export_menu_portraits(root: Path, output_dir: Path) -> dict[str, Any]:
    """Export all logical portrait variants and return their audit manifest."""
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    rom_path = root / "rom/base.gba"
    matrix_path = root / "sequel/content/menu-ui/bank.json"
    rom = rom_path.read_bytes()
    rom_sha256 = sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_sha256}"
        )
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    sources = _load_sources(rom, matrix)
    matrix_count = sum(row["kind"] == "matrix" for row in sources)
    if matrix_count != 310 or len(sources) != 311:
        raise ValueError(
            f"unexpected portrait coverage: {matrix_count} matrix, "
            f"{len(sources)} total"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    cached: dict[tuple[int, int], dict[str, Any]] = {}
    portraits: list[dict[str, Any]] = []
    unique_graphics: set[int] = set()
    for source in sources:
        gfx_pointer = source["gfx_pointer_int"]
        palette_pointer = source["palette_pointer_int"]
        public_source = {
            key: value
            for key, value in source.items()
            if key not in {"gfx_pointer_int", "palette_pointer_int"}
        }
        gfx_offset = gfx_pointer - ROM_BASE
        palette_offset = palette_pointer - ROM_BASE
        if not 0 <= gfx_offset < len(rom):
            raise ValueError(
                "portrait graphics pointer is outside ROM: "
                f"{gba_pointer(gfx_pointer)}"
            )
        if not 0 <= palette_offset <= len(rom) - PORTRAIT_COLORS * 2:
            raise ValueError(
                "portrait palette pointer is outside ROM: "
                f"{gba_pointer(palette_pointer)}"
            )

        resource_key = (gfx_pointer, palette_pointer)
        resource = cached.get(resource_key)
        if resource is None:
            compressed = read_lz77_record(
                rom,
                gfx_offset,
                expected_size=PORTRAIT_BYTES,
            )
            decompressed = lz77_decompress(rom, gfx_offset)
            if len(decompressed) != PORTRAIT_BYTES:
                raise ValueError(
                    "unexpected portrait graphics size at "
                    f"{gba_pointer(gfx_pointer)}: {len(decompressed)}"
                )
            palette = rom[
                palette_offset : palette_offset + PORTRAIT_COLORS * 2
            ]
            pixels = render_portrait_indices(decompressed)
            png = indexed_png_from_bgr555(
                pixels,
                palette,
                width=PORTRAIT_WIDTH,
                height=PORTRAIT_HEIGHT,
                transparent_index=0,
            )
            resource = {
                "resource_id": len(cached),
                "gfx_pointer": gba_pointer(gfx_pointer),
                "palette_pointer": gba_pointer(palette_pointer),
                "gfx_file_offset": gfx_offset,
                "palette_file_offset": palette_offset,
                "compressed_size": len(compressed),
                "compressed_sha256": sha256(compressed),
                "decompressed_size": len(decompressed),
                "decompressed_sha256": sha256(decompressed),
                "palette_size": len(palette),
                "palette_sha256": sha256(palette),
                "pixel_count": len(pixels),
                "maximum_palette_index": max(pixels),
                "png_sha256": sha256(png),
                "png_bytes": png,
                "reuse_count": 0,
            }
            cached[resource_key] = resource
            unique_graphics.add(gfx_pointer)
        resource["reuse_count"] += 1

        png_path = output_dir / source["png"]
        png_path.write_bytes(resource["png_bytes"])
        portraits.append(
            {
                **public_source,
                "pair_gba_address": gba_address(
                    source["pair_file_offset"]
                ),
                **{
                    key: value
                    for key, value in resource.items()
                    if key not in {"png_bytes", "reuse_count"}
                },
            }
        )

    unique_resources = [
        {
            key: value
            for key, value in resource.items()
            if key != "png_bytes"
        }
        for resource in cached.values()
    ]
    table_bytes = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    manifest = {
        "schema": "menu-portrait-export-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "source_bank": "sequel/content/menu-ui/bank.json",
        "source_table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": gba_address(TABLE_OFFSET),
            "entry_count": TABLE_ENTRY_COUNT,
            "entry_size": TABLE_ENTRY_SIZE,
            "variants_per_entry": VARIANTS_PER_ENTRY,
            "sha256": sha256(table_bytes),
            "verification": matrix["verification"],
        },
        "canvas": {
            "width": PORTRAIT_WIDTH,
            "height": PORTRAIT_HEIGHT,
            "pixel_format": "8bpp indexed",
            "palette_format": "64-color GBA BGR555",
            "transparent_palette_index": 0,
            "source_layout": "six-component 1D OBJ tile order",
        },
        "matrix_portrait_count": matrix_count,
        "special_portrait_count": len(sources) - matrix_count,
        "portrait_count": len(sources),
        "unique_resource_count": len(cached),
        "unique_graphics_count": len(unique_graphics),
        "unique_resources": unique_resources,
        "portraits": portraits,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/menu-portraits-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_menu_portraits(args.root, args.output_dir)
    print(
        f"Exported {manifest['portrait_count']} portraits "
        f"({manifest['unique_resource_count']} unique resources) "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
