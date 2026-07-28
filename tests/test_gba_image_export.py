#!/usr/bin/env python3
"""Shared deterministic primitives used by static GBA image exporters."""

from __future__ import annotations

import struct
import unittest
import zlib

from tools.gba_image_export import (
    indexed_png_from_bgr555,
    read_lz77_record,
)


def _chunks(png: bytes) -> dict[bytes, bytes]:
    result: dict[bytes, bytes] = {}
    cursor = 8
    while cursor < len(png):
        length = struct.unpack_from(">I", png, cursor)[0]
        kind = png[cursor + 4 : cursor + 8]
        result[kind] = png[cursor + 8 : cursor + 8 + length]
        cursor += 12 + length
    return result


class GbaImageExportTests(unittest.TestCase):
    def test_reads_exactly_one_literal_lz77_record(self):
        record = b"\x10\x04\x00\x00\x00ABCD"
        rom = b"prefix" + record + b"trailing"
        self.assertEqual(
            record,
            read_lz77_record(rom, 6, expected_size=4),
        )

    def test_lz77_record_rejects_wrong_size_and_invalid_back_reference(self):
        literal = b"\x10\x04\x00\x00\x00ABCD"
        with self.assertRaisesRegex(ValueError, "declares 4 bytes"):
            read_lz77_record(literal, 0, expected_size=5)

        invalid_reference = b"\x10\x03\x00\x00\x80\x00\x00"
        with self.assertRaisesRegex(ValueError, "invalid LZ77 back-reference"):
            read_lz77_record(invalid_reference, 0)

        output_overrun = b"\x10\x02\x00\x00\x40A\x00\x00"
        with self.assertRaisesRegex(ValueError, "exceeds declared size"):
            read_lz77_record(output_overrun, 0)

    def test_indexed_png_preserves_indices_palette_and_transparency(self):
        palette = struct.pack("<HH", 0x0000, 0x001F)
        png = indexed_png_from_bgr555(
            b"\x00\x01",
            palette,
            width=2,
            height=1,
            transparent_index=0,
        )
        chunks = _chunks(png)
        self.assertEqual(
            (2, 1, 8, 3, 0, 0, 0),
            struct.unpack(">IIBBBBB", chunks[b"IHDR"]),
        )
        self.assertEqual(b"\x00\x00\x00\xff\x00\x00", chunks[b"PLTE"])
        self.assertEqual(b"\x00\xff", chunks[b"tRNS"])
        self.assertEqual(b"\x00\x00\x01", zlib.decompress(chunks[b"IDAT"]))

    def test_indexed_png_rejects_pixels_outside_the_palette(self):
        with self.assertRaisesRegex(ValueError, "outside the supplied palette"):
            indexed_png_from_bgr555(
                b"\x02",
                struct.pack("<HH", 0, 0x7FFF),
                width=1,
                height=1,
            )


if __name__ == "__main__":
    unittest.main()
