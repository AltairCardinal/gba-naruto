#!/usr/bin/env python3
"""Scan C/C++ source files for string literals that are not valid UTF-8.

The remake's dialogue texts are stored as UTF-8 string literals inside the
`konoha` headers.  Butano's text generator decodes them with
`bn::utf8_character`, which aborts the ROM with
"ERROR in bn_utf8_character.h / Invalid UTF-8 character" when a literal is
not well formed UTF-8 (a truncated multi byte sequence, a stray continuation
byte, or a surrogate).

The scanner prints, for every offending literal, the file, the line number,
the byte offset inside the literal and the offending bytes, so the fix can be
made on the exact byte instead of by guessing.

Usage:
    python tools/s49_battle_balance/w1_utf8_scan.py <file> [<file> ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_LITERAL = re.compile(rb'"((?:[^"\\]|\\.)*)"')


def scan(path: Path) -> list[tuple[int, int, bytes, bytes]]:
    """Return (line, column, literal_bytes, offending_bytes) tuples."""
    data = path.read_bytes()
    problems: list[tuple[int, int, bytes, bytes]] = []
    for match in _LITERAL.finditer(data):
        raw = match.group(1)
        # Undo the C escapes that can hide a broken byte.
        decoded = raw.replace(b"\\n", b"\n").replace(b"\\t", b"\t")
        try:
            decoded.decode("utf-8")
        except UnicodeDecodeError as error:
            line = data.count(b"\n", 0, match.start(1)) + 1
            column = match.start(1) - (data.rfind(b"\n", 0, match.start(1)) + 1) + 1
            bad = decoded[error.start:error.end]
            problems.append((line, column, raw, bad))
    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    total = 0
    for name in argv[1:]:
        path = Path(name)
        if not path.is_file():
            print(f"{path}: not a file")
            total += 1
            continue
        raw = path.read_bytes()
        if raw[:3] == b"\xef\xbb\xbf":
            print(f"{path}: has a UTF-8 BOM")
            total += 1
        problems = scan(path)
        if not problems:
            print(f"{path}: all string literals are valid UTF-8")
            continue
        for line, column, literal, bad in problems:
            print(
                f"{path}:{line}:{column}: invalid UTF-8 {bad.hex(' ')} "
                f"in literal {literal!r}"
            )
        total += len(problems)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
