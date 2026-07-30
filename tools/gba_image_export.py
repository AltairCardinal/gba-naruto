#!/usr/bin/env python3
"""Shared lossless primitives for deterministic GBA image exports."""

from __future__ import annotations

import hashlib
import struct
import zlib
from collections import deque

from tools.extract_tileset import bgr555_to_rgb


ROM_BASE = 0x08000000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gba_address(file_offset: int) -> str:
    if file_offset < 0:
        raise ValueError("GBA file offset must be non-negative")
    return f"0x{ROM_BASE + file_offset:08X}"


def gba_pointer(value: int) -> str:
    return f"0x{value:08X}"


def read_lz77_record(
    rom: bytes,
    offset: int,
    *,
    expected_size: int | None = None,
) -> bytes:
    """Return exactly one validated GBA type-0x10 compressed record."""
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"resource is not LZ77 at 0x{offset:06X}")
    declared_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    if expected_size is not None and declared_size != expected_size:
        raise ValueError(
            f"LZ77 resource at 0x{offset:06X} declares "
            f"{declared_size} bytes, expected {expected_size}"
        )

    produced = 0
    cursor = offset + 4
    while produced < declared_size:
        if cursor >= len(rom):
            raise ValueError(f"truncated LZ77 flags at 0x{cursor:06X}")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if produced >= declared_size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError(
                        f"truncated LZ77 back-reference at 0x{cursor:06X}"
                    )
                length = (rom[cursor] >> 4) + 3
                displacement = (
                    ((rom[cursor] & 0x0F) << 8) | rom[cursor + 1]
                )
                if displacement >= produced:
                    raise ValueError(
                        "invalid LZ77 back-reference "
                        f"at 0x{cursor:06X}: distance {displacement + 1}, "
                        f"produced {produced}"
                    )
                if produced + length > declared_size:
                    raise ValueError(
                        "LZ77 back-reference exceeds declared size "
                        f"at 0x{cursor:06X}: {produced} + {length} > "
                        f"{declared_size}"
                    )
                produced += length
                cursor += 2
            else:
                if cursor >= len(rom):
                    raise ValueError(
                        f"truncated LZ77 literal at 0x{cursor:06X}"
                    )
                produced += 1
                cursor += 1
    return rom[offset:cursor]


def encode_gba_lz77(data: bytes) -> bytes:
    """Deterministically encode BIOS-compatible type-0x10 GBA LZ77."""
    if not data or len(data) >= 1 << 24:
        raise ValueError("GBA LZ77 input length must be 1..0xFFFFFF")
    output = bytearray(
        (0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, len(data) >> 16)
    )
    positions: dict[bytes, deque[int]] = {}
    cursor = 0
    while cursor < len(data):
        flags_offset = len(output)
        output.append(0)
        flags = 0
        for token_index in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                key = data[cursor : cursor + 3]
                candidates = positions.get(key, ())
                for previous in reversed(candidates):
                    distance = cursor - previous
                    if distance > 0x1000:
                        break
                    length = 3
                    while (
                        length < 18
                        and cursor + length < len(data)
                        and data[previous + length] == data[cursor + length]
                    ):
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                    if length == 18:
                        break
            if best_length >= 3:
                flags |= 1 << (7 - token_index)
                encoded = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((encoded >> 8, encoded & 0xFF))
                advance = best_length
            else:
                output.append(data[cursor])
                advance = 1

            for position in range(cursor, cursor + advance):
                if position + 3 > len(data):
                    continue
                key = data[position : position + 3]
                bucket = positions.setdefault(key, deque())
                bucket.append(position)
                while bucket and position - bucket[0] > 0x1000:
                    bucket.popleft()
            cursor += advance
        output[flags_offset] = flags
    return bytes(output)


def render_4bpp_tile_atlas_indices(
    graphics: bytes,
    *,
    tiles_per_row: int = 32,
) -> tuple[bytes, int, int]:
    """Lay out every 4bpp tile in source order on an indexed canvas."""
    if not graphics or len(graphics) % 32:
        raise ValueError("4bpp atlas graphics must contain complete tiles")
    if tiles_per_row <= 0:
        raise ValueError("4bpp atlas tiles-per-row must be positive")

    tile_count = len(graphics) // 32
    columns = min(tile_count, tiles_per_row)
    rows = (tile_count + tiles_per_row - 1) // tiles_per_row
    width = columns * 8
    height = rows * 8
    pixels = bytearray(width * height)
    for tile_index in range(tile_count):
        tile_x = tile_index % tiles_per_row
        tile_y = tile_index // tiles_per_row
        for local_y in range(8):
            for local_x in range(8):
                packed = graphics[
                    tile_index * 32 + local_y * 4 + local_x // 2
                ]
                pixels[
                    (tile_y * 8 + local_y) * width
                    + tile_x * 8
                    + local_x
                ] = (packed >> (4 if local_x & 1 else 0)) & 0x0F
    return bytes(pixels), width, height


def render_4bpp_tile_block_indices(
    graphics: bytes,
    *,
    tile_offset: int,
    width_tiles: int,
    height_tiles: int,
) -> tuple[bytes, int, int]:
    """Render a row-major rectangular block from a 4bpp tile sequence."""
    if tile_offset < 0:
        raise ValueError("4bpp tile-block offset must be non-negative")
    if width_tiles <= 0 or height_tiles <= 0:
        raise ValueError("4bpp tile-block dimensions must be positive")
    tile_count = width_tiles * height_tiles
    start = tile_offset * 32
    end = start + tile_count * 32
    if end > len(graphics):
        raise ValueError("4bpp tile block exceeds the graphics payload")
    pixels, width, height = render_4bpp_tile_atlas_indices(
        graphics[start:end],
        tiles_per_row=width_tiles,
    )
    if height != height_tiles * 8:
        raise ValueError("4bpp tile block did not fill its declared height")
    return pixels, width, height


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", checksum)
    )


def indexed_png_from_bgr555(
    pixels: bytes,
    palette_bytes: bytes,
    *,
    width: int,
    height: int,
    transparent_index: int | None = None,
) -> bytes:
    """Encode deterministic indexed PNG while preserving GBA palette indices."""
    if len(pixels) != width * height:
        raise ValueError("indexed PNG pixel count does not match its canvas")
    if not palette_bytes or len(palette_bytes) % 2:
        raise ValueError("GBA palette must contain complete BGR555 colors")
    color_count = len(palette_bytes) // 2
    if color_count > 256:
        raise ValueError("indexed PNG palette exceeds 256 colors")
    if pixels and max(pixels) >= color_count:
        raise ValueError(
            "image references a palette index outside the supplied palette"
        )
    if transparent_index is not None and not (
        0 <= transparent_index < color_count
    ):
        raise ValueError("transparent palette index is outside the palette")

    palette = bytearray()
    for offset in range(0, len(palette_bytes), 2):
        color = struct.unpack_from("<H", palette_bytes, offset)[0]
        palette.extend(bgr555_to_rgb(color))
    rows = b"".join(
        b"\0" + pixels[y * width : (y + 1) * width]
        for y in range(height)
    )
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    chunks = [
        b"\x89PNG\r\n\x1a\n",
        _png_chunk(b"IHDR", ihdr),
        _png_chunk(b"PLTE", bytes(palette)),
    ]
    if transparent_index is not None:
        alpha = bytearray([255] * color_count)
        alpha[transparent_index] = 0
        chunks.append(_png_chunk(b"tRNS", bytes(alpha)))
    chunks.extend(
        (
            _png_chunk(b"IDAT", zlib.compress(rows, level=9)),
            _png_chunk(b"IEND", b""),
        )
    )
    return b"".join(chunks)
