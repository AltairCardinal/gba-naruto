#!/usr/bin/env python3
"""Convert the probe's raw framebuffer dump into a PNG.

The host writes the 240x160 framebuffer as raw 16-bit BGR555 pixels with a
small header (width, height, bits, reserved).  This converts that to PNG so
the screen can actually be looked at - navigating a game blind is guesswork.

Usage:
    python tools/mgba_probe/shot.py build/raw.bin build/shot.png
"""
from __future__ import annotations

import pathlib
import struct
import sys


def read_raw(path: pathlib.Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"{path} is too short to be a framebuffer dump")
    width, height, bits, _ = struct.unpack_from("<4I", data, 0)
    if bits != 16:
        raise ValueError(f"unsupported pixel format: {bits} bits")
    pixels = data[16:]
    expected = width * height * 2
    if len(pixels) < expected:
        raise ValueError(f"expected {expected} pixel bytes, got {len(pixels)}")
    return width, height, pixels[:expected]


def to_png(width: int, height: int, pixels: bytes, out: pathlib.Path) -> pathlib.Path:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("ERR Pillow is required for PNG output") from exc

    image = Image.new("RGB", (width, height))
    data = pixels
    image.putdata([
        (
            (data[i * 2] & 0x1F) * 255 // 31,
            ((data[i * 2] | (data[i * 2 + 1] << 8)) >> 5 & 0x1F) * 255 // 31,
            ((data[i * 2] | (data[i * 2 + 1] << 8)) >> 10 & 0x1F) * 255 // 31,
        )
        for i in range(width * height)
    ])
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return out


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2])
    width, height, pixels = read_raw(src)
    to_png(width, height, pixels, dst)
    print(f"wrote {dst} ({width}x{height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
