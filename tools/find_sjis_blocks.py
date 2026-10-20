#!/usr/bin/env python3
"""Find the ROM's own text blocks and decode them with the game's font codes.

History
-------
This tool used to scan for "Shift-JIS-like" blocks and decode them with
``shift_jis``.  That was wrong: the ROM does not store Shift-JIS.  It stores a
custom double-byte *font code* (lead byte 0x80..0x9F) that indexes the ROM's
own baked-in bitmap font.  The "sjis" in the file name is historical; the
scanner now looks for font codes and the decoder goes through
``tools/text_codec.py``.

Scanning for Shift-JIS lead bytes was also useless on this ROM: the byte
range 0x81..0x9F is *inside* the font-code range, so every font-code block
also looked like a Shift-JIS block, and the ROM additionally carries a
GB2312-encoded data region that a Shift-JIS scanner mis-reads as well.

What it does now
----------------
Scan the ROM with the game's own text rules (see notes/font-encoding.md):

    0x00      string terminator
    0x0A      newline
    0x01/0x02 control codes (2 and 3 bytes)
    0x20..0x7E  ASCII
    0x80..0x9F  two-byte font code

A run is only reported when it carries at least `--min-codes` font codes and
is dominated by hanzi, so ARM code, pointer tables and the ROM's
GB2312-encoded data are not mistaken for sentences.

Usage:
    python tools/find_sjis_blocks.py
    python tools/find_sjis_blocks.py rom/base.gba --min-codes 4
    python tools/find_sjis_blocks.py --output build/font-blocks.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import text_codec as tc  # noqa: E402
from tools.lib.io import write_text  # noqa: E402


def _is_cjk(ch: str) -> bool:
    """True for a hanzi or for the fullwidth / CJK punctuation the game uses."""
    code = ord(ch)
    return (0x2018 <= code <= 0x201D
            or code == 0x2026
            or 0x3000 <= code <= 0x303F
            or 0x3400 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF
            or 0xFF00 <= code <= 0xFF60
            or 0xFFE0 <= code <= 0xFFE6)


def scan_text_blocks(
    rom: bytes,
    mapping: dict[int, str],
    min_codes: int = 3,
    min_cjk_ratio: float = 0.70,
) -> list[dict]:
    """Return the ROM's text blocks, decoded with the game's font codes."""
    blocks: list[dict] = []
    n = len(rom)
    i = 0
    while i < n:
        start = i
        codes: list[tuple] = []
        while i < n:
            b = rom[i]
            if b == 0x00:
                break
            if 0x20 <= b <= 0x7E:
                codes.append((i, "ascii", b))
                i += 1
                continue
            if b == 0x0A:
                codes.append((i, "nl", b))
                i += 1
                continue
            if b == 0x01:
                if i + 1 >= n:
                    break
                codes.append((i, "ctrl", rom[i:i + 2]))
                i += 2
                continue
            if b == 0x02:
                if i + 2 >= n:
                    break
                codes.append((i, "ctrl", rom[i:i + 3]))
                i += 3
                continue
            if 0x80 <= b <= 0x9F and i + 1 < n and 0x40 <= rom[i + 1] <= 0xFC:
                codes.append((i, "font", b * 256 + rom[i + 1]))
                i += 2
                continue
            break
        if len(codes) >= 6:
            fonts = [v for _, kind, v in codes if kind == "font"]
            visible = [mapping.get(v, chr(v)) for _, kind, v in codes
                       if kind in ("font", "ascii")]
            cjk = sum(1 for ch in visible if _is_cjk(ch))
            if (len(fonts) >= min_codes and all(c in mapping for c in fonts)
                    and visible and cjk / len(visible) >= min_cjk_ratio):
                data = rom[start:i]
                text = tc.decode(data, mapping)
                blocks.append({
                    "offset": start,
                    "length": len(data),
                    "char_count": len(visible),
                    "code_count": len(fonts),
                    "control_codes": sum(1 for _, k, _ in codes if k == "ctrl"),
                    "text": text,
                })
        i = max(i, start + 1)
    return blocks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find the ROM's text blocks and decode them with font codes.")
    parser.add_argument("rom", nargs="?", type=pathlib.Path, default=None,
                        help="Path to the ROM file (default: rom/base.gba)")
    parser.add_argument("--min-codes", type=int, default=3,
                        help="Minimum number of font codes in a block")
    parser.add_argument("--output", type=pathlib.Path, default=None,
                        help="Optional JSON output path")
    return parser.parse_args()


def summarize(blocks: list[dict], limit: int = 20) -> str:
    lines = [f"Text blocks found: {len(blocks)}", "Sample blocks:"]
    for block in blocks[:limit]:
        sample = block["text"].replace("\n", "\\n")
        lines.append(
            f"  - 0x{block['offset']:06X} len {block['length']} "
            f"chars {block['char_count']} codes {block['code_count']}: {sample!r}"
        )
    if len(blocks) > limit:
        lines.append(f"  ... and {len(blocks) - limit} more")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    rom_path = tc.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    mapping, report = tc.load_mapping(rom_path)

    blocks = scan_text_blocks(rom, mapping, args.min_codes)
    if args.output is not None:
        write_text(args.output,
                   json.dumps(blocks, indent=2, ensure_ascii=False) + "\n")
    print(f"ROM      : {rom_path}")
    print(f"mapping  : {len(mapping)} font codes, "
          f"{report['catalog_segments_matched']}/"
          f"{report['catalog_segments_total']} segments fingerprint-matched")
    print(summarize(blocks))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
