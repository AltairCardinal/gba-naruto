#!/usr/bin/env python3
"""Shared deterministic primitives used by static GBA image exporters."""

from __future__ import annotations

import struct
import unittest
import zlib

from tools.gba_image_export import (
    encode_gba_lz77,
    indexed_png_from_bgr555,
    read_lz77_record,
    render_4bpp_tile_atlas_indices,
    render_4bpp_tile_block_indices,
)


def _decode_lz77_vram_halfwords(record: bytes) -> bytes:
    """Model the committed-halfword behavior of BIOS LZ77UnCompVram."""
    size = int.from_bytes(record[1:4], "little")
    committed = bytearray(size)
    cursor = 4
    dest = 0
    halfword = 0

    def emit(value: int) -> None:
        nonlocal dest, halfword
        if dest & 1:
            halfword |= value << 8
            committed[dest - 1 : dest + 1] = halfword.to_bytes(2, "little")
        else:
            halfword = value
        dest += 1

    while dest < size:
        flags = record[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if dest >= size:
                break
            if flags & (1 << bit):
                token = (record[cursor] << 8) | record[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                source = dest - (token & 0x0FFF) - 1
                for _ in range(length):
                    word_offset = source & ~1
                    word = int.from_bytes(
                        committed[word_offset : word_offset + 2], "little"
                    )
                    emit((word >> (8 * (source & 1))) & 0xFF)
                    source += 1
            else:
                emit(record[cursor])
                cursor += 1
    return bytes(committed)


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
    def test_lz77_encoder_is_safe_for_bios_vram_halfword_writes(self):
        source = b"\x7f" * 64
        encoded = encode_gba_lz77(source)
        self.assertEqual(source, _decode_lz77_vram_halfwords(encoded))

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

    def test_4bpp_atlas_preserves_every_tile_and_pads_the_final_row(self):
        graphics = bytes(
            packed
            for tile in range(3)
            for packed in [tile | ((tile + 1) << 4)] * 32
        )
        pixels, width, height = render_4bpp_tile_atlas_indices(
            graphics,
            tiles_per_row=2,
        )
        self.assertEqual((16, 16), (width, height))
        self.assertEqual(0, pixels[0])
        self.assertEqual(1, pixels[1])
        self.assertEqual(1, pixels[8])
        self.assertEqual(2, pixels[9])
        self.assertEqual(2, pixels[16 * 8])
        self.assertEqual(3, pixels[16 * 8 + 1])
        for row in range(8, 16):
            self.assertEqual(
                {0},
                set(pixels[row * 16 + 8 : (row + 1) * 16]),
            )

    def test_4bpp_tile_block_selects_a_rectangular_tile_range(self):
        graphics = bytes(
            packed
            for tile in range(6)
            for packed in [tile | (tile << 4)] * 32
        )
        pixels, width, height = render_4bpp_tile_block_indices(
            graphics,
            tile_offset=2,
            width_tiles=2,
            height_tiles=2,
        )
        self.assertEqual((16, 16), (width, height))
        self.assertEqual({2}, set(pixels[0:8]))
        self.assertEqual({3}, set(pixels[8:16]))
        self.assertEqual({4}, set(pixels[16 * 8 : 16 * 8 + 8]))
        self.assertEqual({5}, set(pixels[16 * 8 + 8 : 16 * 9]))


if __name__ == "__main__":
    unittest.main()
