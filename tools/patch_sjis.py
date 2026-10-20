#!/usr/bin/env python3
"""Patch a ROM at a given offset with game text.

The ROM stores a custom double-byte font code, not Shift-JIS (see
notes/font-encoding.md), so the default encoding here is ``font``: the text is
written with the ROM's own glyph codes and renders exactly as authored.

``--encoding shift_jis`` is still accepted for legacy callers, but it writes
bytes the game cannot render as the authored characters.

Usage:
    python tools/patch_sjis.py in.gba out.gba 0x459414 "漩涡鸣人"
    python tools/patch_sjis.py in.gba out.gba 0x459414 "漩涡鸣人" --encoding font
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.lib import parse_int
from tools import text_codec


def render_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch a ROM at a given offset with game text."
    )
    parser.add_argument("input_rom", type=Path, help="Input ROM path")
    parser.add_argument("output_rom", type=Path, help="Output ROM path")
    parser.add_argument("offset", help="Target ROM offset")
    parser.add_argument("text", help="Replacement text")
    parser.add_argument(
        "--encoding",
        default=text_codec.FONT_ENCODING,
        help="Text encoding: 'font' (default, the ROM's own glyph codes) or a "
             "legacy codec name such as shift_jis",
    )
    parser.add_argument(
        "--rom",
        default=None,
        help="ROM used for the font code table (default rom/base.gba)",
    )
    parser.add_argument(
        "--expected-len",
        type=parse_int,
        default=None,
        help="Require the encoded replacement to match this byte length",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    offset = parse_int(args.offset)

    mapping = None
    if args.encoding == text_codec.FONT_ENCODING:
        mapping, _ = text_codec.load_mapping(args.rom)
    replacement = text_codec.encode(args.text, args.encoding, mapping)

    if args.expected_len is not None and len(replacement) != args.expected_len:
        raise SystemExit(
            f"replacement length {len(replacement)} does not match expected {args.expected_len}"
        )

    buf = bytearray(args.input_rom.read_bytes())
    if offset + len(replacement) > len(buf):
        raise SystemExit(f"offset 0x{offset:06X} + replacement ({len(replacement)} bytes) exceeds ROM size ({len(buf)} bytes)")
    original = bytes(buf[offset : offset + len(replacement)])
    buf[offset : offset + len(replacement)] = replacement

    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(buf)

    print(f"Patched: {args.input_rom} -> {args.output_rom}")
    print(f"Offset: 0x{offset:06X}")
    print(f"Original bytes:   {render_bytes(original)}")
    print(f"Replacement bytes:{render_bytes(replacement)}")
    if mapping is not None:
        print(f"Original text:    {text_codec.decode(original, mapping)!r}")
    print(f"Replacement text: {args.text!r}")
    print(f"Rendering as:     {text_codec.decode(replacement, mapping)!r}"
          if mapping is not None else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
