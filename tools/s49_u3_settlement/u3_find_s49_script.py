#!/usr/bin/env python3
"""Locate the original's S49 post-battle script in the reverse inventory.

Stream U3 (wave 10).  The post-battle dialogue text has to be authored in the
original's **own** byte codes (the remake's ``battle_presentation_text``
holds raw codes and ``battle_presentation_glyph_codes`` is the original's
dialogue font).  The reverse line's chapter-script inventory is where those
codes come from, so this tool locates scenario 49's scripts and prints their
text bytes.

This tool answers one yes/no question:

    *Does the reverse line's chapter-script inventory carry scenario 49's
     post-battle script (and its encoded text)?*

Usage::

    python tools/s49_u3_settlement/u3_find_s49_script.py
"""

from __future__ import annotations

import json
import pathlib

INVENTORY = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-reverse\artifacts"
    r"\rom-chapter-script-inventory-v1\chapter-script-inventory.json")
BYTES = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-reverse\artifacts"
    r"\rom-chapter-script-inventory-v1\chapter-script-bytes.bin")


def main() -> int:
    document = json.loads(INVENTORY.read_text(encoding="utf-8"))
    print("top keys:", list(document.keys()))

    ranges = document.get("ranges") or []
    print(f"ranges: {len(ranges)}")
    for entry in ranges[:4]:
        print("  ", json.dumps(entry, ensure_ascii=False)[:400])

    pointer_tables = document.get("pointer_tables") or []
    print(f"\npointer tables: {len(pointer_tables)}")
    for table in pointer_tables:
        print("  ", json.dumps(table, ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
