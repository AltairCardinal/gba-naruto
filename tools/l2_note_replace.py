#!/usr/bin/env python3
"""Replace the "# 附录 C" block of the L2 evidence note with a fresh one.

The appendix is generated from `build/l2-runtime.json`, so it has to be
regenerated whenever the run changes; appending a second copy would leave
two versions of the same numbers in one note.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.lib.io import write_text                       # noqa: E402

NOTE = REPO / "notes" / "evidence" / "l2-runtime-evidence-20261021.md"
MARKER = "\n# 附录 C"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--section", type=pathlib.Path, required=True,
                    help="the generated appendix section")
    ap.add_argument("--note", type=pathlib.Path, default=NOTE)
    args = ap.parse_args(argv)

    text = args.note.read_text(encoding="utf-8")
    index = text.find(MARKER)
    if index < 0:
        print("ERR no '# 附录 C' block found in the note", file=sys.stderr)
        return 2
    body = args.section.read_text(encoding="utf-8")
    if not body.startswith("\n"):
        body = "\n" + body
    write_text(args.note, text[:index] + body)
    print(f"replaced the appendix in {args.note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
