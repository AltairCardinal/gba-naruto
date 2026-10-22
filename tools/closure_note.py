#!/usr/bin/env python3
"""Append (or write) repository notes with LF line endings.

The repository uses file SHA-256 as evidence identity, and Windows' default
text mode rewrites ``\\n`` as ``\\r\\n``.  Every note written during the
2026-10-21 closure work goes through this helper so the digest identity is
preserved.

Usage:
    python tools/closure_note.py --out notes/evidence/x.md --file build/body.md
    python tools/closure_note.py --out notes/evidence/x.md --text "one line"
    python tools/closure_note.py --out notes/evidence/x.md --file body.md --append
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.io import write_text  # noqa: E402


def append_note(path: pathlib.Path, body: str) -> pathlib.Path:
    """Append `body` to `path`, keeping LF endings and the existing text."""
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    if existing and not existing.endswith("\n"):
        existing += "\n"
    if body and not body.startswith("\n"):
        body = "\n" + body
    return write_text(path, existing + body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--file", type=pathlib.Path, default=None)
    ap.add_argument("--text", default=None)
    ap.add_argument("--append", action="store_true",
                    help="append to the file instead of replacing it")
    args = ap.parse_args(argv)

    if args.file is not None:
        body = args.file.read_text(encoding="utf-8")
    elif args.text is not None:
        body = args.text
    else:
        body = sys.stdin.read()

    out = args.out if args.out.is_absolute() else REPO / args.out
    if args.append:
        append_note(out, body)
    else:
        write_text(out, body)
    print(f"wrote {out} ({len(body)} chars, append={args.append})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
