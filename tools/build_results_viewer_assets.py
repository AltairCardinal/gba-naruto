#!/usr/bin/env python3
"""Build the verified image/data assets consumed by the results viewer page.

Two sources are used, both already proven elsewhere in the repo:

1. ``build/vfx/menu-portraits-v1/manifest.json``
   Produced by ``tools/export_menu_portraits.py`` from the consumer-verified
   matrix at ROM ``0x5A4DEC`` (63 records x 40 bytes x 5 variants).  The
   superseded ``0x5A4E14`` 155x16 reading produced duplicated and misaligned
   64x64 crops and must not be reused.

2. ``build/tiles-palette/manifest.json`` + ``build/tiles/manifest.json``
   Produced by ``tools/extract_tileset.py`` from the 47-row map header table at
   ROM ``0x53D910``.

Outputs:

* ``build/vfx/menu-portraits-v1/gallery_unique.png``  - poster of the unique
  portrait resources (no duplicated cells).
* ``build/viewer-data/map-rows.json``                  - corrected per-map rows
  used by the viewer's map/tileset and scenario sections.

Usage:
    python3 tools/build_results_viewer_assets.py [--root .]
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image

ROM_BASE = 0x08000000
PORTRAIT_TABLE_OFFSET = 0x5A4DEC
PORTRAIT_CANVAS = 80
MAP_TABLE_FILE = 0x53D910
MAP_TABLE_ENTRY_SIZE = 32

GALLERY_COLUMNS = 10
GALLERY_BACKGROUND = (24, 28, 38, 255)


def build_portrait_gallery(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    """Compose one poster cell per unique (gfx, palette) resource."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_png_by_resource: dict[int, str] = {}
    for portrait in manifest["portraits"]:
        first_png_by_resource.setdefault(portrait["resource_id"], portrait["png"])

    resources = manifest["unique_resources"]
    if not resources:
        raise ValueError("portrait manifest has no unique resources")

    rows = (len(resources) + GALLERY_COLUMNS - 1) // GALLERY_COLUMNS
    width = GALLERY_COLUMNS * PORTRAIT_CANVAS
    height = rows * PORTRAIT_CANVAS
    sheet = Image.new("RGBA", (width, height), GALLERY_BACKGROUND)

    entries: list[dict[str, Any]] = []
    for index, resource in enumerate(resources):
        png_name = first_png_by_resource[resource["resource_id"]]
        with Image.open(manifest_path.parent / png_name) as cell:
            cell = cell.convert("RGBA")
            if cell.size != (PORTRAIT_CANVAS, PORTRAIT_CANVAS):
                raise ValueError(
                    f"unexpected portrait size {cell.size} for {png_name}"
                )
            sheet.paste(cell, (index % GALLERY_COLUMNS * PORTRAIT_CANVAS,
                                index // GALLERY_COLUMNS * PORTRAIT_CANVAS), cell)
        entries.append(
            {
                "index": index,
                "resource_id": resource["resource_id"],
                "png": png_name,
                "gfx_pointer": resource["gfx_pointer"],
                "palette_pointer": resource["palette_pointer"],
                "decompressed_sha256": resource["decompressed_sha256"],
                "png_sha256": resource["png_sha256"],
                "reuse_count": resource["reuse_count"],
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return {
        "png": str(output_path),
        "width": width,
        "height": height,
        "columns": GALLERY_COLUMNS,
        "unique_resource_count": len(resources),
        "unique_graphics_count": manifest["unique_graphics_count"],
        "logical_variant_count": manifest["portrait_count"],
        "table_offset": manifest["source_table"]["file_offset"],
        "table_sha256": manifest["source_table"]["sha256"],
        "resources": entries,
    }


def build_map_rows(root: Path, palette_manifest: Path) -> dict[str, Any]:
    """Rebuild every map header row straight from the ROM table."""
    rom = (root / "rom/base.gba").read_bytes()
    palette_results = {
        entry["map_id"]: entry
        for entry in json.loads(
            palette_manifest.read_text(encoding="utf-8")
        )["results"]
    }

    rows: list[dict[str, Any]] = []
    for map_id in range(47):
        base = MAP_TABLE_FILE + map_id * MAP_TABLE_ENTRY_SIZE
        fields = struct.unpack_from("<8I", rom, base)

        def file_offset(value: int) -> int | None:
            if ROM_BASE <= value < ROM_BASE + len(rom):
                return value - ROM_BASE
            return None

        rendered = palette_results.get(map_id, {})
        width_tiles = fields[0] & 0xFFFF
        height_tiles = (fields[0] >> 16) & 0xFFFF
        rows.append(
            {
                "map_id": map_id,
                "file_offset": base,
                "packed_dims": f"0x{fields[0]:08X}",
                "width_tiles": width_tiles,
                "height_tiles": height_tiles,
                "cell_count": width_tiles * height_tiles,
                "tile_gfx_offset": file_offset(fields[1]),
                "tile_gfx_offset_hex": (
                    f"0x{file_offset(fields[1]):06X}"
                    if file_offset(fields[1]) is not None else None
                ),
                # Field +8 is the compressed BG palette block consumed by the
                # loader (verified destination 0x05000000).
                "bg_palette_offset": file_offset(fields[2]),
                "bg_palette_offset_hex": (
                    f"0x{file_offset(fields[2]):06X}"
                    if file_offset(fields[2]) is not None else None
                ),
                "layout_a_offset": file_offset(fields[3]),
                "layout_a_offset_hex": (
                    f"0x{file_offset(fields[3]):06X}"
                    if file_offset(fields[3]) is not None else None
                ),
                "layout_b_offset": file_offset(fields[4]),
                "layout_b_offset_hex": (
                    f"0x{file_offset(fields[4]):06X}"
                    if file_offset(fields[4]) is not None else None
                ),
                # Field +20 holds metatile/attribute data, not displayable
                # colours.  The historical "palette_ptr" alias mislabelled it.
                "metatile_attr_offset": file_offset(fields[5]),
                "metatile_attr_offset_hex": (
                    f"0x{file_offset(fields[5]):06X}"
                    if file_offset(fields[5]) is not None else None
                ),
                "extra_offset": file_offset(fields[6]),
                "flags": f"0x{fields[7]:08X}",
                "tileset_tile_count": rendered.get("num_tiles"),
                "tileset_png": rendered.get("png"),
                "tileset_palette_source": rendered.get("palette_source"),
            }
        )
    return {
        "schema": "results-viewer-map-rows-v1",
        "rom_sha256": json.loads(
            (root / "build/tiles/manifest.json").read_text(encoding="utf-8")
        ).get("rom_sha1", ""),
        "table_file_offset": MAP_TABLE_FILE,
        "table_entry_size": MAP_TABLE_ENTRY_SIZE,
        "row_count": len(rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()

    portrait_manifest = root / "build/vfx/menu-portraits-v1/manifest.json"
    gallery_path = portrait_manifest.parent / "gallery_unique.png"
    gallery = build_portrait_gallery(portrait_manifest, gallery_path)

    map_rows = build_map_rows(root, root / "build/tiles-palette/manifest.json")
    map_rows_path = root / "build/viewer-data/map-rows.json"
    map_rows_path.parent.mkdir(parents=True, exist_ok=True)
    map_rows_path.write_text(
        json.dumps(map_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"portrait gallery: {gallery['png']} "
        f"({gallery['width']}x{gallery['height']}, "
        f"{gallery['unique_resource_count']} unique of "
        f"{gallery['logical_variant_count']} variants)"
    )
    print(
        f"map rows: {map_rows_path} ({map_rows['row_count']} rows "
        f"from 0x{map_rows['table_file_offset']:06X})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
