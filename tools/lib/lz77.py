"""GBA LZ77 (type 0x10) codec.

The decompressor already exists in `tools/extract_tileset.py`; this module adds
the *compressor*, which the repo never had.  That is what makes the
"synthetic fixture" technique possible for LZ-compressed resources: write a
block we know the contents of, compress it, point the game at it, and read it
back.

Only the "literal" encoding is produced: every group of 8 bytes is stored
uncompressed behind a flags byte of 0x00.  That is valid GBA LZ77, it is what
the native decompressor accepts, and it keeps the encoder trivially
verifiable.  A real back-reference compressor is not needed to prove a format.
"""
from __future__ import annotations


def decompress(data: bytes, offset: int) -> bytes:
    """Decompress the GBA LZ77 stream that starts at `offset`."""
    if data[offset] != 0x10:
        raise ValueError(
            f"not LZ77 data at 0x{offset:06X}: header byte = 0x{data[offset]:02X}"
        )
    decomp_size = int.from_bytes(data[offset + 1: offset + 4], "little")
    out = bytearray()
    pos = offset + 4

    while len(out) < decomp_size:
        flags = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) >= decomp_size:
                break
            if flags & (1 << bit):
                b0 = data[pos]
                b1 = data[pos + 1]
                pos += 2
                disp_len = ((b0 >> 4) & 0xF) + 3
                disp = ((b0 & 0xF) << 8) | b1
                copy_from = len(out) - disp - 1
                for _ in range(disp_len):
                    out.append(out[copy_from])
                    copy_from += 1
            else:
                out.append(data[pos])
                pos += 1

    return bytes(out[:decomp_size])


def compress_literal(data: bytes) -> bytes:
    """Encode `data` as a GBA LZ77 block with no back-references.

    The result is a complete LZ77 stream: 0x10 header, 24-bit decompressed
    size, then one flags byte per 8 literals.
    """
    if len(data) >= 0x1000000:
        raise ValueError("LZ77 payload too large for a 24-bit size field")
    out = bytearray(b"\x10")
    out += len(data).to_bytes(3, "little")
    for i in range(0, len(data), 8):
        out.append(0x00)              # all eight are literals
        out += data[i:i + 8]
    return bytes(out)
