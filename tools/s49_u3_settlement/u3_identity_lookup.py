#!/usr/bin/env python3
"""Look up the remake's identity display names for the settlement speakers.

Stream U3 (wave 10).  S1's post-battle dialogue names its speakers by
``character_id``; this tool checks the ids against the remake's own identity
table so the header's ids are the ones the runtime can render.

This tool answers one yes/no question:

    *Do the speaker character_ids used by the post-battle dialogue match the
     remake's identity records?*

Usage::

    python tools/s49_u3_settlement/u3_identity_lookup.py
"""

from __future__ import annotations

import pathlib
import re

IDENTITY = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
    r"\konoha\generated_battle_identity_content.h")

WANTED = (1, 2, 3, 4, 30)


def main() -> int:
    text = IDENTITY.read_text(encoding="utf-8")
    rows = re.findall(r'battle_identity_record\{ "([^"]*)", (\w+) \}', text)
    print(f"identity records: {len(rows)}")
    for character_id in WANTED:
        if character_id < len(rows):
            name, active = rows[character_id]
            print(f"  id={character_id:>3} name={name!r} active={active}")
        else:
            print(f"  id={character_id:>3} out of range")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
