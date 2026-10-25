#!/usr/bin/env python3
"""Look for the original's S49 post-battle dialogue bytes in the reverse line.

Stream U3 (wave 10).  The post-battle dialogue the remake has to reproduce was
read from the original's frames, but the **byte codes** the original's font
uses are what the remake's presentation text array stores.  This tool checks
the reverse line's (read-only) story/script artifacts for scenario 49's
post-battle script and prints its raw bytes.

This tool answers one yes/no question:

    *Does the reverse line hold scenario 49's post-battle script bytes, so
     the transcribed text can be re-encoded into the remake's font codes?*

Usage::

    python tools/s49_u3_settlement/u3_postbattle_bytes.py
"""

from __future__ import annotations

import json
import pathlib

REVERSE = pathlib.Path(r"D:\Shell\Github\gba-naruto-reverse")


def main() -> int:
    story = REVERSE / "sequel" / "content" / "story" / "bank.json"
    document = json.loads(story.read_text(encoding="utf-8"))
    entries = document["entries"]
    print(f"story entries: {len(entries)}")
    for entry in entries:
        if entry.get("scenario_id") in (49, 48, 50):
            print("  ", json.dumps(entry, ensure_ascii=False)[:400])

    inventory = (REVERSE / "artifacts" /
                 "rom-chapter-script-inventory-v1" /
                 "chapter-script-inventory.json")
    if inventory.is_file():
        data = json.loads(inventory.read_text(encoding="utf-8"))
        print(f"\ninventory keys: {list(data.keys())[:10]}")
        scripts = data.get("scripts") or data.get("entries") or []
        for script in scripts:
            text = json.dumps(script, ensure_ascii=False)
            if "49" in text[:200]:
                print("  ", text[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
