#!/usr/bin/env python3
"""Read-only probe: raw bytes of the story-VM text ops (0x01 / 0x20), to see
whether a script can position its own text at the name-plate position (row 0).
Control code 0x02 in the text stream = "set cursor to (x, y)".
"""
from __future__ import annotations

import collections
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tools import decode_story_script as dss  # noqa: E402
import konoha_font as kf  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()
    mapping, _ = kf.build_mapping(rom)
    c20 = collections.Counter()
    c01 = collections.Counter()
    ex20, ex01 = [], []
    for scene in range(1, dss.STORY_SCENES + 1):
        roots = dss.scene_roots(rom, scene)
        nodes, _ = dss.walk(rom, list(roots.values()), mapping)
        for off, node in sorted(nodes.items()):
            if node.op == 0x20:
                b1 = rom[off + 1]
                c20[b1] += 1
                if len(ex20) < 10:
                    ex20.append((off, rom[off:off + 12].hex(" ")))
            elif node.op == 0x01:
                b1 = rom[off + 1]
                c01[b1] += 1
                if len(ex01) < 10:
                    ex01.append((off, rom[off:off + 12].hex(" ")))
    print("op 0x20 (dialogue-with-speaker) byte+1 histogram:")
    for k, v in sorted(c20.items()):
        print("    0x%02X x%d" % (k, v))
    print("op 0x01 (plain text) byte+1 histogram:")
    for k, v in sorted(c01.items()):
        print("    0x%02X x%d" % (k, v))
    print("\nop 0x20 examples (offset, bytes):")
    for o, h in ex20:
        print("   0x%08X  %s" % (o, h))
    print("\nop 0x01 examples (offset, bytes):")
    for o, h in ex01:
        print("   0x%08X  %s" % (o, h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())