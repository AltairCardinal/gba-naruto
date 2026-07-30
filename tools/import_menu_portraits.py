#!/usr/bin/env python3
"""Build guarded in-place ROM patches from indexed menu/story portrait PNGs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77
from tools.export_menu_portraits import (
    PORTRAIT_BYTES,
    PORTRAIT_COLORS,
    PORTRAIT_COMPONENTS,
    PORTRAIT_HEIGHT,
    PORTRAIT_WIDTH,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/menu-portraits-v1/manifest.json")
CATALOG_SHA256 = "cd54c20d774a2aa69c7a41db396ca344157320882602b03a00ccd83851a791b3"
SPEC_SCHEMA = "menu-portrait-import-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def portrait_canvas_to_stream(pixels: bytes) -> bytes:
    """Invert the six-component portrait layout back to 1D OBJ tile order."""
    if len(pixels) != PORTRAIT_BYTES:
        raise ValueError(
            f"expected {PORTRAIT_BYTES} portrait pixels, got {len(pixels)}"
        )
    output = bytearray(PORTRAIT_BYTES)
    covered = bytearray(PORTRAIT_BYTES)
    for x, y, width, height, target_offset, target_size in PORTRAIT_COMPONENTS:
        if width * height != target_size:
            raise ValueError("portrait component size does not match its shape")
        tiles_wide = width // 8
        for local_y in range(height):
            tile_y, pixel_y = divmod(local_y, 8)
            for local_x in range(width):
                tile_x, pixel_x = divmod(local_x, 8)
                tile_index = tile_y * tiles_wide + tile_x
                source = (y + local_y) * PORTRAIT_WIDTH + x + local_x
                target = (
                    target_offset
                    + tile_index * 64
                    + pixel_y * 8
                    + pixel_x
                )
                if covered[target]:
                    raise ValueError("portrait components overlap in OBJ stream")
                output[target] = pixels[source]
                covered[target] = 1
    if not all(covered):
        raise ValueError("portrait components do not cover the OBJ stream")
    return bytes(output)


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _palette_transparency(image: Image.Image) -> None:
    transparency = image.info.get("transparency")
    if isinstance(transparency, int):
        if transparency != 0:
            raise ValueError("portrait PNG must use transparent palette index 0")
        return
    if isinstance(transparency, bytes):
        if not transparency or transparency[0] != 0:
            raise ValueError("portrait PNG must use transparent palette index 0")
        if any(value != 255 for value in transparency[1:PORTRAIT_COLORS]):
            raise ValueError("only portrait palette index 0 may be transparent")
        return
    raise ValueError("portrait PNG must declare transparent palette index 0")


def _rgb_to_bgr555(red: int, green: int, blue: int) -> int:
    red5 = (red * 31 + 127) // 255
    green5 = (green * 31 + 127) // 255
    blue5 = (blue * 31 + 127) // 255
    return red5 | (green5 << 5) | (blue5 << 10)


def _load_png(path: Path) -> tuple[bytes, bytes]:
    with Image.open(path) as image:
        image.load()
        if image.mode != "P":
            raise ValueError(f"portrait PNG must be indexed mode P: {path}")
        if image.size != (PORTRAIT_WIDTH, PORTRAIT_HEIGHT):
            raise ValueError(
                "portrait PNG must be exactly "
                f"{PORTRAIT_WIDTH}x{PORTRAIT_HEIGHT}: {path}"
            )
        _palette_transparency(image)
        pixels = image.tobytes()
        if pixels and max(pixels) >= PORTRAIT_COLORS:
            raise ValueError(
                f"portrait PNG uses palette index >= {PORTRAIT_COLORS}: {path}"
            )
        palette = image.getpalette()
        if palette is None or len(palette) < PORTRAIT_COLORS * 3:
            raise ValueError(f"portrait PNG palette is truncated: {path}")
        encoded_palette = bytearray()
        for index in range(PORTRAIT_COLORS):
            offset = index * 3
            value = _rgb_to_bgr555(*palette[offset : offset + 3])
            encoded_palette.extend(value.to_bytes(2, "little"))
    return portrait_canvas_to_stream(pixels), bytes(encoded_palette)


def _preserve_palette_reserved_bits(
    encoded_palette: bytes,
    original_palette: bytes,
) -> bytes:
    if len(encoded_palette) != len(original_palette):
        raise ValueError("portrait palette length mismatch")
    output = bytearray()
    for offset in range(0, len(encoded_palette), 2):
        edited = int.from_bytes(encoded_palette[offset : offset + 2], "little")
        original = int.from_bytes(
            original_palette[offset : offset + 2],
            "little",
        )
        output.extend(((edited & 0x7FFF) | (original & 0x8000)).to_bytes(2, "little"))
    return bytes(output)


def _validate_catalog(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("source_catalog") != CATALOG_PATH.as_posix():
        raise ValueError("menu portrait source catalog path mismatch")
    path = root / CATALOG_PATH
    data = path.read_bytes()
    if _sha256(data) != CATALOG_SHA256:
        raise ValueError("menu portrait source catalog SHA-256 mismatch")
    catalog = json.loads(data)
    if (
        catalog.get("schema") != "menu-portrait-export-v1"
        or catalog.get("rom", {}).get("sha256") != ROM_SHA256
        or catalog.get("unique_resource_count") != 74
        or len(catalog.get("unique_resources", [])) != 74
        or catalog.get("portrait_count") != 311
    ):
        raise ValueError("menu portrait source catalog denominator mismatch")
    return catalog


def _expected_provenance(
    edit: dict[str, Any],
    resource: dict[str, Any],
) -> None:
    expected = edit.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("portrait edit requires expected provenance")
    for field in ("gfx_pointer", "palette_pointer"):
        if expected.get(field) != resource[field]:
            raise ValueError(f"{field} provenance mismatch")
    if expected.get("compressed_sha256") != resource["compressed_sha256"]:
        raise ValueError("compressed provenance mismatch")
    if expected.get("palette_sha256") != resource["palette_sha256"]:
        raise ValueError("palette provenance mismatch")


def resolve_menu_portrait_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
) -> list[dict[str, Any]]:
    """Resolve a portrait authoring spec to guarded fixed-length byte patches."""
    root = Path(root).resolve()
    spec_path = Path(spec_path)
    if not spec_path.is_absolute():
        spec_path = root / spec_path
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("menu portrait import schema mismatch")
    catalog = _validate_catalog(root, spec)
    if rom is None:
        rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")

    resources = {
        row["resource_id"]: row for row in catalog["unique_resources"]
    }
    aliases: dict[int, list[dict[str, Any]]] = {
        resource_id: [] for resource_id in resources
    }
    for portrait in catalog["portraits"]:
        aliases[portrait["resource_id"]].append(
            {
                key: portrait.get(key)
                for key in ("portrait_id", "variant", "kind", "png")
            }
        )

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("menu portrait import edits must be a list")
    seen_resources: set[int] = set()
    seen_ids: set[str] = set()
    patches: list[dict[str, Any]] = []
    for edit in edits:
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id:
            raise ValueError("portrait edit requires a non-empty id")
        if edit_id in seen_ids:
            raise ValueError(f"duplicate portrait edit id: {edit_id}")
        seen_ids.add(edit_id)
        resource_id = edit.get("resource_id")
        if resource_id not in resources:
            raise ValueError(f"unknown portrait resource: {resource_id}")
        if resource_id in seen_resources:
            raise ValueError(f"duplicate resource edit: {resource_id}")
        seen_resources.add(resource_id)
        resource = resources[resource_id]
        _expected_provenance(edit, resource)

        graphics_offset = int(resource["gfx_file_offset"])
        palette_offset = int(resource["palette_file_offset"])
        slot_size = int(resource["compressed_size"])
        original_compressed = rom[graphics_offset : graphics_offset + slot_size]
        original_palette = rom[
            palette_offset : palette_offset + PORTRAIT_COLORS * 2
        ]
        if _sha256(original_compressed) != resource["compressed_sha256"]:
            raise ValueError("base ROM compressed portrait provenance mismatch")
        if _sha256(original_palette) != resource["palette_sha256"]:
            raise ValueError("base ROM portrait palette provenance mismatch")

        png_path = _resolve_path(root, edit["png"])
        graphics, palette = _load_png(png_path)
        palette = _preserve_palette_reserved_bits(palette, original_palette)
        original_graphics = lz77_decompress(rom, graphics_offset)
        affected = aliases[resource_id]

        if graphics != original_graphics:
            compressed = encode_gba_lz77(graphics)
            if len(compressed) > slot_size:
                raise ValueError(
                    f"portrait resource {resource_id} compressed data does not fit "
                    f"its {slot_size}-byte slot: needs {len(compressed)}"
                )
            after = compressed + original_compressed[len(compressed) :]
            if len(after) != slot_size:
                raise AssertionError("portrait graphics patch changed slot length")
            patches.append(
                {
                    "id": f"{edit_id}.graphics",
                    "type": "bytes",
                    "asset_type": "menu_portrait_graphics",
                    "resource_id": resource_id,
                    "offset": graphics_offset,
                    "before_hex": original_compressed.hex(),
                    "after_hex": after.hex(),
                    "encoded_size": len(compressed),
                    "slot_size": slot_size,
                    "padding_bytes": slot_size - len(compressed),
                    "affected_portraits": affected,
                    "source_png": str(png_path),
                }
            )
        if palette != original_palette:
            patches.append(
                {
                    "id": f"{edit_id}.palette",
                    "type": "bytes",
                    "asset_type": "menu_portrait_palette",
                    "resource_id": resource_id,
                    "offset": palette_offset,
                    "before_hex": original_palette.hex(),
                    "after_hex": palette.hex(),
                    "slot_size": len(original_palette),
                    "affected_portraits": affected,
                    "source_png": str(png_path),
                }
            )
    return patches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_menu_portrait_patches(args.root, args.spec)
    rendered = json.dumps(patches, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
