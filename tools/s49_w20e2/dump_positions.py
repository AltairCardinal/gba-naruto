#!/usr/bin/env python3
"""W20-E2: dump the positions bank rows for one group (read-only helper)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"D:\Shell\Github\gba-naruto-butano")
POSITIONS = ROOT / "sequel/content/positions/bank.json"


def main() -> int:
    group = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    pos = json.loads(POSITIONS.read_text(encoding="utf-8"))
    print("top keys:", list(pos.keys()))
    print("entry_count:", pos.get("entry_count"), "len:", len(pos["entries"]))
    rows = [r for r in pos["entries"] if r["group_id"] == group]
    print(f"group {group} rows: {len(rows)}")
    for r in rows:
        raw = r.get("raw_hex", "")
        be = r.get("battle_experience")
        raw_be = None
        if len(raw) >= 28:
            raw_be = int.from_bytes(bytes.fromhex(raw)[0x0C:0x0E], "little")
        print(
            {
                "variant": r.get("variant_id"),
                "record": r.get("record_id"),
                "active": r.get("active"),
                "selector": r.get("selector"),
                "affil": r.get("affiliation"),
                "x": r.get("x"),
                "y": r.get("y"),
                "param": r.get("parameter"),
                "be_field": be,
                "be_raw0x0C": raw_be,
                "rawlen": len(raw),
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
