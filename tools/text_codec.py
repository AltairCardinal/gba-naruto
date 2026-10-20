#!/usr/bin/env python3
"""Text codec for the Konoha Senki ROM.

The ROM does **not** store text as cp932/Shift-JIS.  Its text engine reads a
custom double-byte *font code*: a lead byte in 0x80..0x9F followed by a trail
byte, with `code = lead * 256 + trail` indexing a glyph baked into the ROM's
own bitmap font.  See `notes/font-encoding.md` for the full derivation.

This module is the single place the rest of the toolchain is allowed to encode
or decode ROM text, so that no writer can silently fall back to cp932 and
write bytes the game cannot render.

Encodings
---------
``"font"``
    The game's own font codes.  This is the only encoding that produces text a
    player can read.  Requires a ROM (for the fingerprint-checked code->glyph
    table); the ROM's font segments are FNV-1a checked, so a ROM with a
    different font yields fewer characters instead of wrong ones.

``"cp932"`` / ``"shift_jis"`` / ...
    Legacy.  Kept so old patches still build, but flagged: bytes produced this
    way are Shift-JIS, and the game will render them as whatever font codes
    they happen to collide with.  Never use it for new content.

Canonical reverse mapping
-------------------------
Eight characters are spelled by **two** font codes each.  The encoder must
pick one of them, and it must pick the *same* one every time, otherwise
``encode()`` is not reproducible.  The rule used here is derived from the ROM
itself (full derivation and evidence in
``notes/evidence/font-reverse-mapping-20261020.md``):

    The font code space is not one ordered block.  On this ROM it splits into

      0x8140..0x889E  symbol / kana / latin block
      0x889F..0x9CC3  BASE RUN - the GB2312 level-1 hanzi in pinyin order
                      (3754 of GB2312's 3755 level-1 characters are here,
                      in order; only U+7F16 is missing)
      0x9873..0x989E  rare-character extension block A (39 characters)
      0x9CC4..0x9D3E  rare-character extension block B (50 characters)

    The two extension blocks are the font packer's additions for characters
    GB2312 level 1 does not carry.  Eight of the characters they add are
    *already* in the base run, so those eight have two codes.

    CANONICAL RULE: a character is encoded with its **base-run** code, i.e.
    the code in the GB2312-ordered run.  The extension-block spelling is a
    redundant re-spelling of a character the base run already carries at its
    standard slot, and the game's own text overwhelmingly uses the base-run
    spelling (see the evidence note for the per-character counts).

The rule is mechanical: ``EXTENSION_BLOCK_RANGES`` names the two extension
blocks, ``build_canonical_reverse_mapping()`` applies it, and
``tools/font_roundtrip.py`` re-derives the same structure straight from the
ROM and fails the build if the two disagree.

Usage
-----
    from text_codec import encode, decode, load_mapping

    mapping, report = load_mapping()
    raw = encode("漩涡鸣人", "font", mapping)
    print(decode(raw, mapping))
"""
from __future__ import annotations

import pathlib
import sys
import warnings

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

import konoha_font as kf  # noqa: E402

FONT_ENCODING = "font"
LEGACY_ENCODINGS = frozenset({
    "cp932", "shift_jis", "shift-jis", "sjis", "gbk", "gb2312", "big5",
})
DEFAULT_ROM = REPO / "rom" / "base.gba"

# ---------------------------------------------------------------------------
# Rare-character extension blocks of the font code space.
#
# Measured on rom/base.gba (see notes/evidence/font-reverse-mapping-20261020.md
# for the full derivation and the per-character evidence):
#
#   0x8140..0x889E   symbol / kana / latin block
#   0x889F..0x9CC3   BASE RUN: GB2312 level-1 hanzi in pinyin order
#                    (3754 of GB2312's 3755 level-1 characters, in order)
#   0x9873..0x989E   extension block A (39 characters)
#   0x9CC4..0x9D3E   extension block B (50 characters + 73 filler slots)
#
# The extension blocks are the font packer's additions for characters GB2312
# level 1 does not carry.  Eight of the characters they add are already in the
# base run, so those eight characters have two codes.  The base-run spelling
# is canonical - see the module docstring.
# ---------------------------------------------------------------------------
EXTENSION_BLOCK_RANGES: tuple[tuple[int, int], ...] = (
    (0x9873, 0x989E),
    (0x9CC4, 0x9D3E),
)

_MAPPING_CACHE: dict[str, tuple[dict[int, str], dict]] = {}
_CANONICAL_CACHE: dict[int, tuple[dict[int, str], dict[int, str], dict]] = {}


def resolve_rom(rom_path: pathlib.Path | str | None = None) -> pathlib.Path:
    """Locate the ROM used for the font table.

    Order: explicit argument -> ``$KONOHA_ROM`` -> ``rom/base.gba`` -> the
    first ``*.gba`` in the repo root.
    """
    if rom_path is not None:
        path = pathlib.Path(rom_path)
        if not path.exists():
            raise FileNotFoundError(f"ROM not found: {path}")
        return path

    import os

    env = os.environ.get("KONOHA_ROM")
    if env:
        path = pathlib.Path(env)
        if path.exists():
            return path

    if DEFAULT_ROM.exists():
        return DEFAULT_ROM

    for cand in sorted(REPO.glob("*.gba")):
        return cand
    raise FileNotFoundError(
        f"no ROM found; put the base ROM at {DEFAULT_ROM} or set KONOHA_ROM"
    )


def load_mapping(rom_path: pathlib.Path | str | None = None) -> tuple[dict[int, str], dict]:
    """Return (code -> character mapping, report) for the ROM's font.

    The mapping is built from the ROM's own font segments and is only applied
    to segments whose FNV-1a fingerprint matches the catalog the table was
    derived from, so a mismatched ROM cannot produce wrong characters.
    """
    path = resolve_rom(rom_path)
    key = str(path.resolve())
    cached = _MAPPING_CACHE.get(key)
    if cached is None:
        rom = path.read_bytes()
        mapping, report = kf.build_mapping(rom)
        report["rom"] = str(path)
        cached = (mapping, report)
        _MAPPING_CACHE[key] = cached
    return cached


def is_legacy(encoding: str) -> bool:
    return encoding.lower() in LEGACY_ENCODINGS


def is_extension_block_code(code: int) -> bool:
    """True when `code` lives in one of the font's rare-character blocks."""
    return any(lo <= code <= hi for lo, hi in EXTENSION_BLOCK_RANGES)


def build_canonical_reverse_mapping(
    mapping: dict[int, str],
) -> tuple[dict[str, int], dict]:
    """Build the canonical character -> code map, plus an evidence report.

    The rule (see the module docstring and
    `notes/evidence/font-reverse-mapping-20261020.md`):

        A character is encoded with its **base-run** code - the code in the
        GB2312-ordered run of the font code space.  The rare-character
        extension blocks only exist to supply characters the base run lacks;
        where one of them re-spells a character the base run already carries,
        that second spelling is redundant and is not the canonical one.

    The result is a *total* function on the characters of `mapping`: every
    character gets exactly one code, so `encode()` is deterministic.

    The report carries, per duplicated character, the candidate codes, which
    of them are base-run / extension-block, and the chosen one.
    """
    candidates: dict[str, list[int]] = {}
    for code in sorted(mapping):
        candidates.setdefault(mapping[code], []).append(code)

    reverse: dict[str, int] = {}
    duplicates: list[dict] = []
    for char, codes in candidates.items():
        base = [c for c in codes if not is_extension_block_code(c)]
        extension = [c for c in codes if is_extension_block_code(c)]
        if base:
            chosen = base[0]
        elif extension:
            chosen = extension[0]
        else:  # pragma: no cover - every code is in one of the two classes
            chosen = codes[0]
        reverse[char] = chosen
        if len(codes) > 1:
            duplicates.append({
                "char": char,
                "codes": codes,
                "base_run_codes": base,
                "extension_codes": extension,
                "canonical": chosen,
                "canonical_is_base_run": chosen in base,
            })

    report = {
        "characters": len(reverse),
        "duplicate_characters": len(duplicates),
        "duplicates": duplicates,
        "extension_block_ranges": [
            [lo, hi] for lo, hi in EXTENSION_BLOCK_RANGES
        ],
    }
    return reverse, report


def canonical_mapping(
    mapping: dict[int, str],
) -> tuple[dict[int, str], dict]:
    """Return (mapping restricted to canonical codes, report).

    The returned code -> character table contains exactly one code per
    character, so `konoha_font.build_reverse_mapping()` applied to it yields
    the canonical reverse map.  Passing it to `konoha_font.encode_text()`
    therefore makes the encoder emit the canonical code for every character.

    The result is cached per mapping object, because `encode()` is called
    once per string and re-deriving the map every time is wasteful.  The
    cache keeps a strong reference to the mapping so its `id()` cannot be
    reused by a different object.
    """
    key = id(mapping)
    cached = _CANONICAL_CACHE.get(key)
    if cached is not None and cached[0] is mapping:
        return cached[1], cached[2]
    reverse, report = build_canonical_reverse_mapping(mapping)
    keep = set(reverse.values())
    canonical = {code: ch for code, ch in mapping.items() if code in keep}
    report["canonical_codes"] = len(canonical)
    _CANONICAL_CACHE[key] = (mapping, canonical, report)
    return canonical, report


def encode(
    text: str,
    encoding: str = FONT_ENCODING,
    mapping: dict[int, str] | None = None,
    rom_path: pathlib.Path | str | None = None,
) -> bytes:
    """Encode `text` into ROM text bytes.

    With ``encoding="font"`` the text is written with the game's own font
    codes.  Characters the ROM's font cannot draw raise ``KeyError`` - there
    is no safe substitute, because a wrong code shows a wrong glyph.

    Characters that the font spells with two codes are encoded with the
    canonical (base-run) code - see `build_canonical_reverse_mapping()`.
    """
    enc = (encoding or FONT_ENCODING).lower()

    if enc == FONT_ENCODING:
        if mapping is None:
            mapping, _ = load_mapping(rom_path)
        canon, _ = canonical_mapping(mapping)
        return kf.encode_text(text, canon)

    if is_legacy(enc):
        warnings.warn(
            f"encoding {encoding!r} is legacy: it writes Shift-JIS bytes, which "
            f"the game renders as font codes. Use encoding={FONT_ENCODING!r} for "
            f"any text a player will read.",
            DeprecationWarning,
            stacklevel=2,
        )
        return text.encode(enc)

    raise LookupError(
        f"unknown encoding {encoding!r}; use {FONT_ENCODING!r} "
        f"or one of {sorted(LEGACY_ENCODINGS)}"
    )


def decode(
    data: bytes,
    mapping: dict[int, str] | None = None,
    rom_path: pathlib.Path | str | None = None,
) -> str:
    """Decode ROM text bytes back into readable text.

    This is the check that the old pipeline never ran: it answers "what will
    the player actually see at this address?".
    """
    if mapping is None:
        mapping, _ = load_mapping(rom_path)
    return kf.decode_codes(kf.scan_codes(data, 0), mapping)


def encode_tokens(
    tokens: list[tuple],
    mapping: dict[int, str] | None = None,
    rom_path: pathlib.Path | str | None = None,
) -> bytes:
    """Re-encode a token stream (control codes preserved) into ROM bytes.

    Use this when *rewriting* existing text: control bytes 0x01/0x02 carry
    layout meaning and must survive unchanged.
    """
    if mapping is None:
        mapping, _ = load_mapping(rom_path)
    return kf.encode_tokens(tokens, mapping)


def decode_tokens(
    rom: bytes,
    offset: int,
    mapping: dict[int, str] | None = None,
    rom_path: pathlib.Path | str | None = None,
) -> tuple[str, int]:
    """Decode the text run at `offset`; returns (text, next offset)."""
    if mapping is None:
        mapping, _ = load_mapping(rom_path)
    return kf.decode_at(rom, offset, mapping)


def decode_bounded(
    rom: bytes,
    offset: int,
    max_bytes: int,
    mapping: dict[int, str] | None = None,
    rom_path: pathlib.Path | str | None = None,
) -> tuple[str, int]:
    """Decode the text at `offset`, stopping at the slot's byte budget.

    A text run in the ROM can be longer than the slot a bank entry claims
    (the title-screen menu list at 0x00076D is one long run; the proof-of-write
    entry only owns its first four bytes).  This helper returns only the
    characters that fit in `max_bytes`, plus the number of control codes it
    saw.
    """
    if mapping is None:
        mapping, _ = load_mapping(rom_path)
    tokens = kf.scan_tokens(rom, offset)
    kept: list[tuple] = []
    used = 0
    n_ctrl = 0
    for kind, value in tokens:
        if kind == "ctrl":
            size = len(value)
        else:
            size = 2 if 0x8000 <= value <= 0x9FFF else 1
        if used + size > max_bytes:
            break
        kept.append((kind, value))
        used += size
        if kind == "ctrl":
            n_ctrl += 1
    return kf.tokens_to_string(kept, mapping), n_ctrl


def coverage(mapping: dict[int, str] | None = None) -> dict:
    """Report how many characters the ROM font can draw."""
    if mapping is None:
        mapping, _ = load_mapping()
    reverse, report = build_canonical_reverse_mapping(mapping)
    return {
        "codes": len(mapping),
        "distinct_characters": len(reverse),
        "duplicate_characters": report["duplicate_characters"],
    }


def roundtrip_report(
    mapping: dict[int, str] | None = None,
    rom_path: pathlib.Path | str | None = None,
) -> dict:
    """Check that every font code re-encodes to the same character.

    For each of the ROM's font codes the character it spells is encoded
    again and decoded back.  The check is character-level, so it holds for
    the non-canonical spelling of a duplicated character as well: both
    spellings render the same character.

    Returns a report with ``codes``, ``passed`` and ``failures``.
    """
    if mapping is None:
        mapping, _ = load_mapping(rom_path)
    canon, _ = canonical_mapping(mapping)
    passed = 0
    failures: list[dict] = []
    for code in sorted(mapping):
        char = mapping[code]
        try:
            raw = kf.encode_text(char, canon)
        except KeyError as exc:  # pragma: no cover - defensive
            failures.append({"code": code, "char": char, "error": str(exc)})
            continue
        back = kf.decode_codes(kf.scan_codes(raw, 0), mapping)
        if back == char:
            passed += 1
        else:
            failures.append({
                "code": code, "char": char, "encoded": raw.hex(),
                "decoded": back,
            })
    return {
        "codes": len(mapping),
        "passed": passed,
        "failed": len(failures),
        "failures": failures,
    }


def main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Inspect the ROM text codec.")
    ap.add_argument("--rom", help="ROM path (default rom/base.gba)")
    ap.add_argument("--encode", help="text to encode with the font codes")
    ap.add_argument("--decode-hex", help="hex bytes to decode back to text")
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="run the round-trip self test and exit non-zero on failure",
    )
    args = ap.parse_args()

    mapping, report = load_mapping(args.rom)
    print(f"ROM      : {report['rom']}")
    print(f"mapping  : {len(mapping)} font codes")
    print(f"catalog  : {report['catalog_segments_matched']}"
          f"/{report['catalog_segments_total']} segments fingerprint-matched")

    cov = coverage(mapping)
    print(f"characters: {cov['distinct_characters']} distinct "
          f"({cov['duplicate_characters']} spelled by two codes)")

    rt = roundtrip_report(mapping, args.rom)
    print(f"round-trip: {rt['passed']}/{rt['codes']} font codes re-encode "
          f"to the same character")

    if args.encode:
        raw = encode(args.encode, FONT_ENCODING, mapping)
        print(f"\nencode   : {args.encode!r}")
        print(f"bytes    : {raw.hex()}")
        print(f"decoded  : {decode(raw, mapping)!r}")

    if args.decode_hex:
        raw = bytes.fromhex(args.decode_hex)
        print(f"\ndecode   : {args.decode_hex}")
        print(f"text     : {decode(raw, mapping)!r}")

    if not args.encode and not args.decode_hex and not args.self_test:
        print(json.dumps(cov, ensure_ascii=False))

    if args.self_test and rt["failed"]:
        print(f"\nFAIL: {rt['failed']} code(s) do not round-trip", file=sys.stderr)
        for f in rt["failures"][:20]:
            print(f"  {f}", file=sys.stderr)
        return 1
    if args.self_test:
        print("\nSELF-TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
