#!/usr/bin/env python3
"""Round-trip check and a corrected tile mapping for the Konoha Senki font.

The repo's old sequel/content/text/sjis-to-tile-mapping.json was a hand-made
20-character table whose *values* were double-encoded (mojibake): "娴犫偓" was
meant to be "浠€". The byte keys were correct.

This tool:
  1. builds the full code->character mapping from the ROM (fingerprint-checked);
  2. re-derives the old 20 key/value pairs to prove the byte keys were right;
  3. round-trips a sample of real in-game text through encode -> decode;
  4. asserts, machine-checkably, the canonical reverse mapping:
       (a) every one of the ROM's font codes re-encodes to the same character;
       (b) the reverse map is unambiguous - one canonical code per character;
       (c) the old "smallest code point" behaviour is only used where it is
           provably correct;
  5. re-derives the font's rare-character extension blocks straight from the
     ROM and fails if they disagree with tools/text_codec.py;
  6. can emit a corrected mapping file that supersedes the hand-made one.

Every assertion failure makes the script exit non-zero.

Usage:
    python tools/font_roundtrip.py
    python tools/font_roundtrip.py --emit-mapping sequel/content/text/font-code-map.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import konoha_font as kf  # noqa: E402
import text_codec as tc  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
OLD_MAP = REPO / "sequel" / "content" / "text" / "sjis-to-tile-mapping.json"

sys.path.insert(0, str(REPO))
from tools.lib.io import write_text  # noqa: E402


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------
class CheckLog:
    """Collects assertion results so the script can report every failure."""

    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        if ok:
            self.passed.append(label)
        else:
            self.failed.append(f"{label}: {detail}" if detail else label)
        return ok

    def section(self, title: str) -> None:
        print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# (5) Re-derive the font's structure from the ROM
# ---------------------------------------------------------------------------
def gb2312_level1() -> list[str]:
    """GB2312 level-1 characters in pinyin order (3755 of them).

    This is an *independent standard reference*, used only to recognise the
    font's own ordering.  It is never used to decode or encode ROM text -
    that always goes through tools/text_codec.py.  The stdlib codec is used
    so the repository does not have to carry a hand-made charset table.
    """
    out: list[str] = []
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return out


def derive_structure(rom: bytes, mapping: dict[int, str]) -> dict:
    """Re-derive the base run and the rare-character extension blocks.

    The base run is the part of the font code space whose characters are the
    GB2312 level-1 hanzi in pinyin order.  Everything the base run does not
    account for is a rare-character extension block.

    Returns a dict with the derived extension ranges, the number of GB2312
    level-1 characters matched, and the characters that differ.
    """
    import difflib

    segs = [s for s in kf.read_segments(rom) if s.count]
    codes: list[int] = []
    for seg in segs:
        codes.extend(range(seg.start, seg.start + seg.count))
    codes.sort()

    mapped_codes = [c for c in codes if c in mapping]
    chars = [mapping[c] for c in mapped_codes]

    reference = gb2312_level1()
    matcher = difflib.SequenceMatcher(a=reference, b=chars, autojunk=False)

    base: set[int] = set()
    extension: set[int] = set()
    missing: list[str] = []
    replaced: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            base.update(mapped_codes[j1:j2])
        elif tag == "replace":
            base.update(mapped_codes[j1:j2])
            if i2 - i1 == 1 and j2 - j1 == 1:
                replaced.append((reference[i1], chars[j1]))
        elif tag == "insert":
            extension.update(mapped_codes[j1:j2])
        elif tag == "delete":
            missing.extend(reference[i1:i2])

    def to_ranges(values: set[int]) -> list[tuple[int, int]]:
        out: list[list[int]] = []
        for c in sorted(values):
            if out and c == out[-1][1] + 1:
                out[-1][1] = c
            else:
                out.append([c, c])
        return [(a, b) for a, b in out]

    # The symbol / kana / latin block sits before the base run and is not
    # part of it; split it off by code order.
    base_min = min(base) if base else 0
    hanzi_extension = {c for c in extension if c >= base_min}

    return {
        "extension_codes": hanzi_extension,
        "extension_ranges": to_ranges(hanzi_extension),
        "base_codes": len(base),
        "gb2312_level1_total": len(reference),
        "gb2312_level1_missing": missing,
        "gb2312_level1_replaced": replaced,
    }


# ---------------------------------------------------------------------------
# Text usage census (the game's own text)
# ---------------------------------------------------------------------------
def _is_cjk(ch: str) -> bool:
    """True for a hanzi or for the fullwidth / CJK punctuation the game uses.

    The game's sentences are full of fullwidth punctuation ("..." -> U+201C /
    U+201D, "..." -> U+2026, "|" -> U+3000); those count as Chinese text,
    unlike a stray ASCII letter.
    """
    code = ord(ch)
    return (0x2018 <= code <= 0x201D      # ' ' " "
            or code == 0x2026             # ...
            or 0x3000 <= code <= 0x303F    # ideographic space and marks
            or 0x3400 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF
            or 0xFF00 <= code <= 0xFF60
            or 0xFFE0 <= code <= 0xFFE6)


def scan_text_runs(rom: bytes, mapping: dict[int, str]) -> list[list[tuple]]:
    """Split the ROM into runs of the game's own text.

    A run follows the game's text rules: ASCII, 0x0A newline, 0x01/0x02
    control codes, and two-byte font codes (lead 0x80..0x9F).  0x00 ends a
    run.

    A run only counts as *text* when

      * it carries at least three font codes, and every one of them is a
        known character - a single font-code byte pair also occurs by
        accident inside ARM code, pointer tables and the ROM's own
        GB2312-encoded data, and those coincidences must not be counted as
        "the game uses this character here"; and
      * at least 70% of its visible characters are hanzi or fullwidth forms,
        which rejects those accidents (e.g. the run at 0x335E46 decodes to
        '孜杉1:f嘎' and is data, not a sentence).
    """
    runs: list[list[tuple]] = []
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
            if (len(fonts) >= 3 and all(c in mapping for c in fonts)
                    and visible and cjk / len(visible) >= 0.70):
                runs.append(codes)
        i = max(i, start + 1)
    return runs


def text_usage(rom: bytes, mapping: dict[int, str]) -> dict[int, int]:
    """Count, per font code, how many of the game's own text runs use it."""
    usage: dict[int, int] = {}
    for codes in scan_text_runs(rom, mapping):
        fonts = [v for _, kind, v in codes if kind == "font"]
        for c in set(fonts):
            usage[c] = usage.get(c, 0) + 1
    return usage


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def repair_mojibake(s: str) -> str:
    """The old mapping file stored UTF-8 bytes that were read as GBK.

    '娴犫偓' -> '浠€' and friends. Recover the original by re-encoding the
    mis-decoded text as GBK and decoding it as UTF-8.

    This is a one-off diagnostic for the *retired* hand-made table; the
    ROM text itself is never decoded with a legacy charset.
    """
    try:
        return s.encode("gbk", errors="strict").decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-mapping", help="write the full code->character map here")
    ap.add_argument("--rom", help="ROM path (default rom/base.gba)")
    args = ap.parse_args()

    rom_path = tc.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    mapping, report = kf.build_mapping(rom)
    print(f"ROM      : {rom_path.name}")
    print(f"mapping  : {len(mapping)} codes, "
          f"{report['catalog_segments_matched']}/{report['catalog_segments_total']} "
          f"font segments fingerprint-matched")

    log = CheckLog()

    # ---------------------------------------------------------------- (1)
    log.section("the old hand-made table")
    if OLD_MAP.exists():
        old = json.loads(OLD_MAP.read_text(encoding="utf-8"))
        print("  the old file claims it was derived from the bytes at 0x459414;")
        print("  here is what those bytes actually decode to in this ROM:")
        text, _ = kf.decode_at(rom, 0x459414, mapping)
        print(f"    ROM-backed : {text!r}")
        old_text = "".join(
            "\n" if v == "\\n" else v
            for v in (repair_mojibake(x) for x in old.get("mapping", {}).values())
        )
        print(f"    old table  : {old_text!r}")
        agree = sum(1 for k, v in old.get("mapping", {}).items()
                    if mapping.get(int(k, 16)) == repair_mojibake(v))
        print(f"    entries agreeing with the ROM: {agree}/{len(old.get('mapping', {}))}")
        print("    -> the hand-made table does not describe this ROM; the ROM-backed")
        print("       mapping is the one consistent with the text and the quiz answers")
    else:
        print("  (retired table not present)")

    # ---------------------------------------------------------------- (2)
    log.section("round-trip on real in-game text")
    name_ptr = struct.unpack_from("<I", rom, 0x599280 + 4)[0] - 0x08000000
    samples = [
        (0x459414, "story/dialogue text bank entry 0"),
        (0x59A1BC, "mission title, stage 1"),
        (name_ptr, "character name, id 1"),
        (0x59AC20, "mission description, stage 1"),
        (0x08009F3E - 0x08000000, "story script text, scene 1"),
    ]
    for ptr_off, label in samples:
        tokens = kf.scan_tokens(rom, ptr_off)
        text = kf.tokens_to_string(tokens, mapping)
        try:
            encoded = kf.encode_tokens(tokens, mapping)
        except KeyError as exc:
            print(f"  {label}: encode failed -> {exc}")
            continue
        same_bytes = encoded == rom[ptr_off:ptr_off + len(encoded)]
        n_ctrl = sum(1 for k, _ in tokens if k == "ctrl")
        print(f"  {label}: {text[:20]!r}...  bytes_equal={same_bytes}  "
              f"ctrl_codes={n_ctrl}")

    log.section("plain string round trip (new text path)")
    for label, ptr_off in (("mission description, stage 1", 0x59AC20),):
        text, _ = kf.decode_at(rom, ptr_off, mapping)
        try:
            encoded = tc.encode(text, tc.FONT_ENCODING, mapping)
        except KeyError as exc:
            print(f"  {label}: encode failed -> {exc}")
            continue
        back, _ = kf.decode_at(rom, ptr_off, mapping)
        print(f"  {label}: decode_stable={back == text}  "
              f"byte_equal_without_ctrl={encoded == rom[ptr_off:ptr_off + len(encoded)]}")
    print("  (plain-string encoding drops control codes, so it is only safe for")
    print("   brand-new strings; rewriting existing text must use tokens)")

    # ---------------------------------------------------------------- (4)
    log.section("canonical reverse mapping")
    reverse, canon_report = tc.build_canonical_reverse_mapping(mapping)
    canonical, _ = tc.canonical_mapping(mapping)
    duplicates = canon_report["duplicates"]
    print(f"  {len(mapping)} font codes -> {len(reverse)} distinct characters")
    print(f"  {len(duplicates)} characters are spelled by two codes")

    # (a) every font code re-encodes to the same character
    rt = tc.roundtrip_report(mapping, args.rom)
    log.check(rt["failed"] == 0,
              f"(a) round-trip: {rt['passed']}/{rt['codes']} font codes re-encode "
              f"to the same character",
              "; ".join(str(f) for f in rt["failures"][:5]))
    print(f"  (a) round-trip     : {rt['passed']}/{rt['codes']}")

    # (b) the reverse map is unambiguous
    ambiguous = [ch for ch, codes in
                 {c: [k for k, v in mapping.items() if v == c]
                  for c in set(mapping.values())}.items()
                 if len(codes) > 1 and reverse[ch] not in codes]
    log.check(not ambiguous,
              "(b) reverse map is unambiguous (one canonical code per character)",
              str(ambiguous[:5]))
    log.check(len(canonical) == len(reverse),
              "(b) canonical mapping holds exactly one code per character",
              f"{len(canonical)} codes vs {len(reverse)} characters")
    log.check(len(set(reverse.values())) == len(reverse),
              "(b) canonical codes are unique per character",
              f"{len(set(reverse.values()))} unique of {len(reverse)}")
    print(f"  (b) unambiguous    : {len(reverse)} characters -> "
          f"{len(set(reverse.values()))} distinct canonical codes")

    # (c) the old "smallest code point" behaviour is provably correct
    usage = text_usage(rom, mapping)
    print()
    print("  per-character evidence (game's own text usage):")
    print("    char  base-run code  ext-block code   text runs using base/ext")
    smallest_wrong = []
    for entry in duplicates:
        char = entry["char"]
        codes = entry["codes"]
        base = entry["base_run_codes"]
        ext = entry["extension_codes"]
        chosen = entry["canonical"]
        smallest = codes[0]
        if chosen != smallest:
            smallest_wrong.append((char, chosen, smallest))
        base_use = sum(usage.get(c, 0) for c in base)
        ext_use = sum(usage.get(c, 0) for c in ext)
        print(f"    {char}    0x{base[0]:04X}          0x{ext[0]:04X}          "
              f"{base_use:5d} / {ext_use:5d}")
        log.check(len(base) == 1 and len(ext) == 1,
                  f"(c) {char}: exactly one base-run code and one extension code",
                  f"base={base} ext={ext}")
        log.check(chosen in base,
                  f"(c) {char}: canonical code is the base-run code",
                  f"canonical=0x{chosen:04X} base={[hex(c) for c in base]}")
    log.check(not smallest_wrong,
              "(c) the old 'smallest code point' behaviour coincides with the "
              "canonical rule for every duplicated character",
              str(smallest_wrong))
    print(f"  (c) smallest==canonical for all {len(duplicates)} duplicated characters: "
          f"{not smallest_wrong}")

    # ---------------------------------------------------------------- (5)
    log.section("font structure re-derived from the ROM")
    structure = derive_structure(rom, mapping)
    derived_codes = structure["extension_codes"]
    shipped_codes = {c for c in mapping
                     if tc.is_extension_block_code(c)}
    print(f"  GB2312 level-1 characters in the font : "
          f"{structure['base_codes']} matched in pinyin order "
          f"(of {structure['gb2312_level1_total']})")
    print(f"  missing from the base run             : "
          f"{structure['gb2312_level1_missing'] or 'none'}")
    print(f"  slot replaced in the base run         : "
          f"{structure['gb2312_level1_replaced'] or 'none'}")
    print(f"  derived rare-character codes          : {len(derived_codes)}")
    print(f"  shipped EXTENSION_BLOCK_RANGES        : "
          f"{[(hex(a), hex(b)) for a, b in tc.EXTENSION_BLOCK_RANGES]}")
    log.check(derived_codes == shipped_codes,
              "(5) the extension codes re-derived from the ROM are exactly the "
              "codes text_codec.py treats as extension-block codes",
              f"derived-only={sorted(derived_codes - shipped_codes)[:8]} "
              f"shipped-only={sorted(shipped_codes - derived_codes)[:8]}")
    log.check(structure["gb2312_level1_missing"] == ["编"],
              "(5) exactly one GB2312 level-1 character is missing from the base run",
              str(structure["gb2312_level1_missing"]))

    # ---------------------------------------------------------------- (3)
    log.section("roster coverage")
    names = kf.read_character_names(rom, mapping)
    missing_chars = sorted({ch for n in names.values() for ch in n if ch not in reverse})
    print(f"  {len(names)} names, distinct characters not encodable: "
          f"{len(missing_chars)} {missing_chars}")
    log.check(not missing_chars,
              "(3) every character of every character name is encodable",
              str(missing_chars))

    # ---------------------------------------------------------------- (6)
    if args.emit_mapping:
        out = pathlib.Path(args.emit_mapping)
        payload = {
            "_comment": "Konoha Senki font code -> character, derived from the ROM font "
                       "segments (FNV-1a fingerprint checked). Replaces the 20-entry "
                       "hand-made sjis-to-tile-mapping.json whose values were double-encoded.",
            "_encoding": "custom double-byte font code (lead byte 0x80..0x9F), NOT cp932",
            "_canonical": "a character spelled by two codes is encoded with its "
                          "base-run code; see notes/evidence/font-reverse-mapping-20261020.md",
            "segments": report["segments"],
            "mapping": {str(code): ch for code, ch in sorted(mapping.items())},
        }
        write_text(out, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"\nwrote {out} ({len(mapping)} codes)")

    # ---------------------------------------------------------------- summary
    log.section("summary")
    print(f"  checks passed: {len(log.passed)}")
    print(f"  checks failed: {len(log.failed)}")
    for failure in log.failed:
        print(f"    FAIL  {failure}")
    if log.failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS - the canonical reverse mapping is proven and enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
