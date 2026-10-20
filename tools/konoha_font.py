#!/usr/bin/env python3
"""Konoha Senki text encoding: custom double-byte font codes, not Shift-JIS.

The ROM renders Chinese text from its own baked-in bitmap font. A text byte
pair whose *first* byte is 0x80..0x9F is a **font code** (code = hi*256+lo),
not a Shift-JIS character. Decoding those bytes as cp932 produces mojibake;
that is what earlier versions of notes/dialogue-format.md did.

This module provides the pieces needed to read the game's text properly:

  * font segment table at 0x53D644 (31 slots x 8 bytes: start u16, count u8,
    glyph offset u32) - each glyph is 32 bytes of 4bpp indices;
  * an FNV-1a fingerprint per segment, so a code->character table can only be
    applied to a font whose bytes match the table it was derived from;
  * the text scanner (control bytes 0x01/0x02, single bytes, 0x80..0x9F
    lead bytes) and the decoder that renders codes as characters.

The code->character table is seeded from two independent sources:
  1. the ROM's own character-name table at 0x599280 (21 names, verified
     character by character against the name strings);
  2. third_party/konoha-workshop/editor/text_catalog.js - an inferred
     mapping, applied only to font segments whose fingerprint matches.

Usage:
    python tools/konoha_font.py            # print mapping coverage
"""
from __future__ import annotations

import json
import pathlib
import re
import struct
from typing import Iterable

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = 0x08000000
FONT_SEGMENTS = 0x53D644
FONT_SEGMENT_COUNT = 31
GLYPH_BYTES = 32
NAME_TABLE = 0x599280

# The 21 character names the ROM stores at 0x599280 (index 0 is the "none" slot).
NAMES = [
    "无", "漩涡鸣人", "宇智波佐助", "春野樱", "山中井野", "奈良鹿丸", "秋道丁次",
    "旗木卡卡西", "犬冢牙", "油女志乃", "日向雏田", "日向宁次", "李洛克", "天天",
    "我爱罗", "勘九郎", "手鞠", "萨克", "多斯", "金", "桃地再不斩", "白",
]

CATALOG_PATH = REPO / "third_party" / "konoha-workshop" / "editor" / "text_catalog.js"


def fnv1a(data: bytes) -> str:
    """FNV-1a 32-bit over the segment's glyph bytes, as 8 lowercase hex digits."""
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"


class FontSegment:
    __slots__ = ("index", "start", "count", "offset", "signature")

    def __init__(self, index: int, start: int, count: int, offset: int, signature: str):
        self.index = index
        self.start = start
        self.count = count
        self.offset = offset
        self.signature = signature

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (f"FontSegment(i={self.index} start=0x{self.start:04X} "
                f"count={self.count} off=0x{self.offset:06X} sig={self.signature})")


def read_segments(rom: bytes) -> list[FontSegment]:
    """Parse the font segment table."""
    segs = []
    for i in range(FONT_SEGMENT_COUNT):
        p = FONT_SEGMENTS + i * 8
        start = struct.unpack_from("<H", rom, p)[0]
        count = rom[p + 2]
        offset = struct.unpack_from("<I", rom, p + 4)[0] - BASE
        sig = ""
        if count and 0 <= offset < len(rom) - count * GLYPH_BYTES:
            sig = fnv1a(rom[offset : offset + count * GLYPH_BYTES])
        segs.append(FontSegment(i, start, count, offset, sig))
    return segs


def load_catalog() -> dict:
    """Load the inferred code->character catalog shipped in the vendored package.

    The file is a small JS module wrapping one JSON object; we parse the JSON
    out of it. Returns {} when the file is absent.
    """
    if not CATALOG_PATH.exists():
        return {}
    text = CATALOG_PATH.read_text(encoding="utf-8")
    m = re.search(r"const\s+data\s*=\s*(\{.*\});\s*if\s*\(", text, re.S)
    if not m:
        return {}
    return json.loads(m.group(1))


def seed_from_name_table(rom: bytes) -> dict[int, str]:
    """Map font codes to characters using the ROM's own character-name table.

    Each name entry is a run of font codes; when its length matches the
    expected name length we can assign code -> character with certainty.
    """
    result: dict[int, str] = {}
    for cid in range(1, len(NAMES)):
        ptr = struct.unpack_from("<I", rom, NAME_TABLE + cid * 4)[0] - BASE
        if not (0 <= ptr < len(rom)):
            continue
        codes = [c for c in scan_codes(rom, ptr) if c >= 0x8000]
        chars = list(NAMES[cid])
        if len(codes) != len(chars):
            continue
        for code, ch in zip(codes, chars):
            result[code] = ch
    return result


def scan_codes(rom: bytes, pos: int, limit: int = 8192) -> list[int]:
    """Scan a text run, returning the font/single-byte codes it contains.

    Control bytes 0x01 and 0x02 are skipped (2 and 3 bytes total).
    0x00 terminates. A lead byte in 0x80..0x9F starts a two-byte code.
    """
    codes: list[int] = []
    for _ in range(limit):
        if pos >= len(rom):
            break
        a = rom[pos]
        if a == 0:
            break
        if a == 1:
            pos += 2
            continue
        if a == 2:
            pos += 3
            continue
        if 0x80 <= a <= 0x9F:
            if pos + 1 >= len(rom) or rom[pos + 1] == 0:
                break
            codes.append(a * 256 + rom[pos + 1])
            pos += 2
            continue
        codes.append(a)
        pos += 1
    return codes


def build_mapping(rom: bytes) -> tuple[dict[int, str], dict]:
    """Build the verified code->character mapping.

    Returns (mapping, report). The catalog part is only applied to font
    segments whose FNV-1a fingerprint matches the catalog entry, so a ROM
    with a different font simply gets fewer characters instead of wrong ones.
    """
    segs = read_segments(rom)
    catalog = load_catalog()
    report = {
        "segments": [
            {"index": s.index, "start": s.start, "count": s.count,
             "offset": s.offset, "signature": s.signature}
            for s in segs
        ],
        "catalog_loaded": bool(catalog),
        "catalog_segments_matched": 0,
        "catalog_segments_total": 0,
        "seed_codes": 0,
    }

    mapping: dict[int, str] = {}
    seed = seed_from_name_table(rom)
    mapping.update(seed)
    report["seed_codes"] = len(seed)

    known = {s["start"]: s for s in catalog.get("segments", [])}
    catalog_map = {int(k): v for k, v in catalog.get("mapping", {}).items()}
    for seg in segs:
        if not seg.count:
            continue
        entry = known.get(seg.start)
        if not entry or entry.get("count") != seg.count:
            continue
        report["catalog_segments_total"] += 1
        if entry.get("signature") != seg.signature:
            continue  # font bytes differ - do not trust the catalog here
        report["catalog_segments_matched"] += 1
        for code in range(seg.start, seg.start + seg.count):
            ch = catalog_map.get(code)
            if ch:
                mapping[code] = ch
    return mapping, report


def decode_codes(codes: Iterable[int], mapping: dict[int, str]) -> str:
    """Render codes as text. Unknown codes become a visible {字XXXX} marker."""
    out = []
    for code in codes:
        if code == 10:
            out.append("\n")
        elif code == 3:
            out.append("{c03}")
        elif 32 <= code < 127:
            out.append(chr(code))
        elif code == 0x8140:
            out.append("　")
        else:
            out.append(mapping.get(code) or f"{{字{code:04X}}}")
    return "".join(out)


def decode_at(rom: bytes, pos: int, mapping: dict[int, str]) -> tuple[str, int]:
    """Decode a text run at `pos`; returns (text, offset of the next byte)."""
    codes: list[int] = []
    p = pos
    for _ in range(8192):
        if p >= len(rom):
            break
        a = rom[p]
        if a == 0:
            p += 1
            break
        if a == 1:
            p += 2
            continue
        if a == 2:
            p += 3
            continue
        if 0x80 <= a <= 0x9F:
            if p + 1 >= len(rom) or rom[p + 1] == 0:
                break
            codes.append(a * 256 + rom[p + 1])
            p += 2
            continue
        codes.append(a)
        p += 1
    return decode_codes(codes, mapping), p


def read_character_names(rom: bytes, mapping: dict[int, str], limit: int = 62) -> dict[int, str]:
    """Decode the ROM's character-name table at 0x599280 with the font mapping.

    Entry i is a pointer to the name of character i. The table is the same one
    the game uses for the "pick up" windows, so decoding it is a direct test
    of the mapping.
    """
    names: dict[int, str] = {}
    for cid in range(1, limit + 1):
        ptr = struct.unpack_from("<I", rom, NAME_TABLE + cid * 4)[0] - BASE
        if not (0 <= ptr < len(rom)):
            break
        text, _ = decode_at(rom, ptr, mapping)
        text = text.replace("\n", "").strip()
        if not text:
            break
        names[cid] = text
    return names


def catalog_mapping_only() -> dict[int, str]:
    """Code->character table straight from the catalog, without a ROM check.

    Used for the *write* path: encoding text needs char->code, and the
    catalog is enough for that. The ROM-backed build_mapping() should be
    preferred whenever a ROM is available, because it additionally verifies
    the font fingerprint.
    """
    catalog = load_catalog()
    return {int(k): v for k, v in catalog.get("mapping", {}).items()}


def build_reverse_mapping(mapping: dict[int, str]) -> dict[str, int]:
    """char -> code. The first (lowest) code wins when a character repeats."""
    rev: dict[str, int] = {}
    for code in sorted(mapping):
        rev.setdefault(mapping[code], code)
    return rev


def encode_text(text: str, mapping: dict[int, str]) -> bytes:
    """Encode a string into the game's font codes.

    Characters that the ROM's font cannot draw raise KeyError - there is no
    safe way to substitute them, because a wrong code shows a wrong glyph.
    """
    rev = build_reverse_mapping(mapping)
    out = bytearray()
    for ch in text:
        if ch == "\n":
            out.append(0x0A)
            continue
        if ch == "　":
            out += b"\x81\x40"
            continue
        if 32 <= ord(ch) < 127:
            out.append(ord(ch))
            continue
        code = rev.get(ch)
        if code is None:
            raise KeyError(f"character {ch!r} (U+{ord(ch):04X}) is not in the ROM font")
        out.append((code >> 8) & 0xFF)
        out.append(code & 0xFF)
    return bytes(out)


def scan_tokens(rom: bytes, pos: int, limit: int = 8192) -> list[tuple]:
    """Scan a text run into a token stream that preserves control codes.

    Each token is one of:
        ("text", code)   a font code (2 bytes in the ROM) or an ASCII byte
        ("ctrl", bytes)  a control code, exactly as it appears in the ROM

    Control codes carry layout meaning (line breaks, page breaks) and must
    survive a rewrite unchanged, so anything that writes text back has to
    work on tokens rather than on the decoded string.
    """
    tokens: list[tuple] = []
    p = pos
    for _ in range(limit):
        if p >= len(rom):
            break
        a = rom[p]
        if a == 0:
            break
        if a == 1:
            tokens.append(("ctrl", bytes(rom[p:p + 2])))
            p += 2
            continue
        if a == 2:
            tokens.append(("ctrl", bytes(rom[p:p + 3])))
            p += 3
            continue
        if 0x80 <= a <= 0x9F:
            if p + 1 >= len(rom) or rom[p + 1] == 0:
                break
            tokens.append(("text", a * 256 + rom[p + 1]))
            p += 2
            continue
        tokens.append(("text", a))
        p += 1
    return tokens


def encode_tokens(tokens: list[tuple], mapping: dict[int, str]) -> bytes:
    """Encode a token stream back into ROM bytes."""
    rev = build_reverse_mapping(mapping)
    out = bytearray()
    for kind, value in tokens:
        if kind == "ctrl":
            out += value
            continue
        code = value
        if code == 10:
            out.append(0x0A)
        elif 32 <= code < 127:
            out.append(code)
        elif code == 0x8140:
            out += b"\x81\x40"
        else:
            out.append((code >> 8) & 0xFF)
            out.append(code & 0xFF)
    return bytes(out)


def tokens_to_string(tokens: list[tuple], mapping: dict[int, str]) -> str:
    """Render a token stream as text, dropping control codes."""
    out = []
    for kind, value in tokens:
        if kind == "ctrl":
            continue
        if value == 10:
            out.append("\n")
        elif 32 <= value < 127:
            out.append(chr(value))
        elif value == 0x8140:
            out.append("　")
        else:
            out.append(mapping.get(value) or f"{{字{value:04X}}}")
    return "".join(out)


def main() -> None:
    import sys

    rom_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if rom_path is None:
        for cand in REPO.glob("*.gba"):
            rom_path = cand
            break
    rom = rom_path.read_bytes()
    mapping, report = build_mapping(rom)
    segs = report["segments"]

    print(f"ROM        : {rom_path.name}")
    print(f"font segs  : {sum(1 for s in segs if s['count'])} non-empty of {len(segs)}")
    print(f"seed codes : {report['seed_codes']} (from the ROM name table)")
    print(f"catalog    : matched {report['catalog_segments_matched']}"
          f"/{report['catalog_segments_total']} segments")
    print(f"mapping    : {len(mapping)} codes total")
    unknown = sum(1 for v in mapping.values() if v.startswith("{字"))
    print(f"unresolved : {unknown}")
    print()
    print("segments:")
    for s in segs:
        if s["count"]:
            hit = "MATCH" if any(
                e["start"] == s["start"] and e["count"] == s["count"]
                and e["signature"] == s["signature"]
                for e in load_catalog().get("segments", [])
            ) else "-----"
            print(f"  seg{s['index']:2d} start=0x{s['start']:04X} count={s['count']:4d} "
                  f"sig={s['signature']} {hit}")


if __name__ == "__main__":
    main()
