#!/usr/bin/env python3
"""Derive viewer-ready copies of the battle-map canvases with a uniform background.

The canonical canvases under ``artifacts/map-canvases-v1/canvases/`` are
indexed-colour PNGs.  Palette entry 0 of such a PNG is the GBA backdrop colour
of the map it belongs to, and index 0 is exactly the "no tile placed here"
pixel:

  * ``tools/export_map_canvases.py`` maps GBA colour 0 to PNG index 0
    (``0 if color == 0 else palette_bank * 16 + color``), and
  * tile index 0 is a fully transparent 8x8 tile in all 47 maps -- every one
    of its 64 pixels is colour 0 -- so only empty blocks can emit index 0.

Left alone, every map therefore paints its empty blocks in its own backdrop
colour: map 0 light blue, maps 1-5 dark blue, map 6 green, maps 7+ black.  The
viewer showed that directly, so "no tile" looked like a different colour in
every single map, which reads as a rendering bug rather than as empty space.

This writes display copies under ``build/map-canvases-web/``.  A copy is
byte-identical to the canonical PNG except for an added ``tRNS`` chunk that
declares palette index 0 transparent: the indexed pixels and the palette are
untouched, so a copy proves nothing the canonical file does not already prove.
The empty blocks become transparent and the page paints one uniform backdrop
behind them.

The canonical artifacts are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from PIL import Image

FAMILY = "map-canvases-v1"
SOURCE_DIR = Path("artifacts") / FAMILY / "canvases"
OUTPUT_DIR = Path("build/map-canvases-web")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TRANSPARENT_INDEX = 0
RULE = (
    "palette index 0 (GBA colour 0, the fully transparent tile 0) is declared "
    "transparent through an added tRNS chunk; every other index keeps the "
    "canonical palette entry and every indexed pixel is unchanged"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """Split a PNG into (type, payload) pairs, verifying the framing."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")
    out: list[tuple[bytes, bytes]] = []
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("truncated PNG chunk header")
        (length,) = struct.unpack_from(">I", data, pos)
        ctype = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if len(payload) != length or pos + 12 + length > len(data):
            raise ValueError("truncated PNG chunk body")
        out.append((ctype, payload))
        pos += 12 + length
    return out


def _chunk(ctype: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(ctype + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + ctype + payload + struct.pack(">I", crc)


def _header(chunks: list[tuple[bytes, bytes]]) -> tuple[int, int, int, int, int]:
    """Return (width, height, bit_depth, colour_type, palette_entries)."""
    ihdr = next((p for t, p in chunks if t == b"IHDR"), None)
    if ihdr is None or len(ihdr) != 13:
        raise ValueError("PNG has no usable IHDR")
    width, height, depth, colour = struct.unpack_from(">IIBB", ihdr, 0)
    palette = next((p for t, p in chunks if t == b"PLTE"), None)
    if palette is None:
        raise ValueError("PNG has no palette")
    if colour != 3:
        raise ValueError(f"expected a palette PNG (colour type 3), got {colour}")
    if depth != 8:
        raise ValueError(f"expected 8-bit palette PNG, got {depth}")
    return width, height, depth, colour, len(palette) // 3


def add_transparency(data: bytes) -> bytes:
    """Return the same PNG with palette index 0 declared transparent."""
    chunks = _chunks(data)
    types = [ctype for ctype, _ in chunks]
    if b"tRNS" in types:
        raise ValueError("PNG already carries a tRNS chunk")
    if b"PLTE" not in types or b"IDAT" not in types:
        raise ValueError("PNG is not a palette image with pixel data")
    _header(chunks)
    out = bytearray(PNG_SIGNATURE)
    for ctype, payload in chunks:
        out += _chunk(ctype, payload)
        if ctype == b"PLTE":
            # tRNS for a palette PNG is a run of alpha values starting at
            # index 0; one byte makes index 0 transparent and leaves the rest
            # of the palette opaque.
            out += _chunk(b"tRNS", bytes([0]))
    return bytes(out)


def _pixel_stats(path: Path) -> tuple[int, int, int]:
    """Return (width, height, index-0 pixel count) of an indexed PNG."""
    with Image.open(path) as image:
        if image.mode != "P":
            raise ValueError(f"{path.name}: expected a palette PNG, got {image.mode}")
        width, height = image.size
        indices = image.tobytes()
        if len(indices) != width * height:
            raise ValueError(f"{path.name}: unexpected raw size {len(indices)}")
        return width, height, indices.count(TRANSPARENT_INDEX)


def _transparent_tile0_maps(root: Path, manifest: dict) -> list[int]:
    """Map ids whose tile 0 is a fully transparent 8x8 tile.

    This is the evidence behind the rule: only an empty block can ever be
    drawn with tile 0, so index 0 means "no tile here" and nothing else.
    """
    verified: list[int] = []
    for entry in manifest.get("entries", []):
        resources = entry.get("resources") or {}
        graphics = resources.get("tile_graphics")
        if not graphics:
            continue
        blob = root / graphics["output_bin"]
        data = blob.read_bytes()
        if len(data) < 32:
            raise ValueError(f"map {entry['map_id']}: tile graphics too short")
        colours: list[int] = []
        for byte in data[:32]:
            colours.append(byte & 0x0F)
            colours.append(byte >> 4)
        if set(colours) != {0} or len(colours) != 64:
            raise ValueError(
                f"map {entry['map_id']}: tile 0 is not fully transparent"
            )
        verified.append(entry["map_id"])
    return verified


def build(root: Path, output_dir: Path) -> dict:
    source_dir = root / SOURCE_DIR
    manifest_path = root / "artifacts" / FAMILY / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canvases = sorted(source_dir.glob("map-*.png"))
    if not canvases:
        raise FileNotFoundError(f"no canvases under {source_dir}")

    verified = _transparent_tile0_maps(root / "artifacts" / FAMILY, manifest)
    if len(verified) != manifest.get("map_count"):
        raise ValueError(
            f"only {len(verified)} of {manifest.get('map_count')} maps carry a "
            "fully transparent tile 0"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for source in canvases:
        raw = source.read_bytes()
        derived = add_transparency(raw)
        target = output_dir / source.name
        target.write_bytes(derived)
        width, height, empty_pixels = _pixel_stats(source)
        files.append({
            "name": source.name,
            "source_path": (SOURCE_DIR / source.name).as_posix(),
            "output_path": (output_dir / source.name).as_posix(),
            "source_sha256": _sha256(raw),
            "output_sha256": _sha256(derived),
            "width": width,
            "height": height,
            "empty_pixels": empty_pixels,
            "empty_ratio": round(empty_pixels / (width * height), 6),
            "bytes_added": len(derived) - len(raw),
        })

    report = {
        "schema": "viewer-map-canvases-v1",
        "source_family": f"artifacts/{FAMILY}",
        "source_manifest_sha256": _sha256(manifest_path.read_bytes()),
        "rule": RULE,
        "transparent_index": TRANSPARENT_INDEX,
        "output_dir": output_dir.as_posix(),
        "canvas_count": len(files),
        "map_count": manifest.get("map_count"),
        "maps_with_transparent_tile0": verified,
        "empty_canvas_count": sum(1 for f in files if f["empty_pixels"] > 0),
        "files": files,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    try:
        report = build(root, output_dir)
    except (FileNotFoundError, ValueError) as error:
        print(f"map canvas derivation refused: {error}")
        return 2
    print(
        f"map canvases={report['canvas_count']} "
        f"empty={report['empty_canvas_count']} "
        f"-> {report['output_dir']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
