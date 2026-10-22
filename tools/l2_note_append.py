#!/usr/bin/env python3
"""Append a section to the L2 evidence note, with LF line endings.

The note is written through `tools/lib/io.write_text` (LF, no BOM) so the
repository's SHA-256 evidence identity is not broken by Windows' default
CRLF text mode.

Usage:
    python tools/l2_note_append.py --file build/l2-batch2-runtime.md
    python tools/l2_note_append.py --text "one line"
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from l2_batch2 import NOTE, append_note                     # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", type=pathlib.Path, default=None,
                    help="a UTF-8 file whose content is appended")
    ap.add_argument("--text", default=None, help="text to append")
    ap.add_argument("--note", type=pathlib.Path, default=NOTE)
    args = ap.parse_args(argv)

    if args.file is not None:
        body = args.file.read_text(encoding="utf-8")
    elif args.text is not None:
        body = args.text
    else:
        body = sys.stdin.read()
    if body and not body.startswith("\n"):
        body = "\n" + body
    path = append_note(body, args.note)
    print(f"appended {len(body)} chars to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
