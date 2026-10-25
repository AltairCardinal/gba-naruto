#!/usr/bin/env python3
"""Inspect the remake's presentation cases and their script text.

Stream U3 (wave 10).  The remake's generated presentation content holds the
battle scripts.  S1 needs to know whether a **post-battle** script for
scenario 49 already exists there, and if not, what the script table's shape
is so the new script can be authored in the same form.

This tool answers one yes/no question:

    *Does the remake's generated presentation content carry a post-battle
     script for scenario 49, and what is the table's shape?*

Usage::

    python tools/s49_u3_settlement/u3_remake_scripts.py
"""

from __future__ import annotations

import pathlib
import re

HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
    r"\konoha\generated_battle_presentation_content.h")


def section(text: str, name: str) -> str:
    start = text.find(f" {name} = {{")
    if start < 0:
        return ""
    end = text.find("}};", start)
    return text[start:end]


def main() -> int:
    text = HEADER.read_text(encoding="utf-8")

    definitions = section(text, "battle_presentation_definitions")
    print(f"definitions block: {len(definitions)} chars")
    rows = re.findall(r"\{[^{}]*\}", definitions)
    print(f"definition rows: {len(rows)}")
    for row in rows[:4]:
        print("  ", " ".join(row.split())[:300])

    print("\n-- searching for scenario 49 / postbattle mentions --")
    for keyword in ("postbattle", "post_battle", "task_menu", "world_map"):
        hits = text.count(keyword)
        print(f"  {keyword}: {hits}")

    commands = section(text, "battle_presentation_commands")
    print(f"\ncommands block: {len(commands)} chars")
    for keyword in ("0x0361F6", "0x0361D9", "0x08061"):
        print(f"  {keyword}: {commands.count(keyword)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
