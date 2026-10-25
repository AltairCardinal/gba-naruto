#!/usr/bin/env python3
"""W20-E2: compare two generated scenario headers slot by slot.

Usage::

    python tools/s49_w20e2/compare_headers.py <old.h> <new.h>

Reports, per (battle_id, variant, record), the ``battle_experience`` value in
each header, and summarises the differences.  Also prints the battle 14 table
for both sides (the S49 mission).
"""

from __future__ import annotations

import pathlib
import re
import sys

SCENARIO_HEAD = re.compile(
    r"battle_scenario_definition\{\s*\n\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)U,"
)
INNER_ARRAY = "std::array<battle_scenario_unit_slot, 12>{{"
SLOT_RE = re.compile(
    r"battle_scenario_unit_slot\{\s*"
    r"(true|false),\s*scenario_selector_kind::(\w+),\s*(\d+),\s*"
    r"battle_side::(\w+),\s*grid_point\{\s*(\d+),\s*(\d+)\s*\},\s*"
    r"battle_facing::(\w+),\s*(\d+),"
)


def load_slots(path: pathlib.Path) -> dict[tuple[int, int, int], int]:
    text = path.read_text(encoding="utf-8")
    out: dict[tuple[int, int, int], int] = {}
    for head in SCENARIO_HEAD.finditer(text):
        battle_id = int(head.group(1))
        region = text[head.end():]
        starts = []
        cursor = 0
        for _ in range(3):
            index = region.find(INNER_ARRAY, cursor)
            if index < 0:
                break
            starts.append(index)
            cursor = index + len(INNER_ARRAY)
        for variant_index, start in enumerate(starts):
            end = (
                starts[variant_index + 1]
                if variant_index + 1 < len(starts)
                else region.find("\n        }}", start)
            )
            for record_index, slot in enumerate(SLOT_RE.finditer(region[start:end])):
                out[(battle_id, variant_index, record_index)] = int(slot.group(8))
    return out


def main() -> int:
    old_path = pathlib.Path(sys.argv[1])
    new_path = pathlib.Path(sys.argv[2])
    old = load_slots(old_path)
    new = load_slots(new_path)
    print(f"old: {old_path}\n     slots={len(old)}")
    print(f"new: {new_path}\n     slots={len(new)}")
    print()
    keys = sorted(set(old) | set(new))
    diffs = [(k, old.get(k), new.get(k)) for k in keys if old.get(k) != new.get(k)]
    print(f"differing slots: {len(diffs)} / {len(keys)}")
    for key, old_value, new_value in diffs[:60]:
        print(f"  battle {key[0]:2d} v{key[1]} rec{key[2]:2d}: "
              f"{old_value} -> {new_value}")
    if len(diffs) > 60:
        print(f"  ... and {len(diffs) - 60} more")

    print()
    print("=== battle 14, variant 0 ===")
    for record in range(12):
        key = (14, 0, record)
        print(f"  rec{record:2d}: old={old.get(key)} new={new.get(key)}")
    print("=== battle 14, variant 2 ===")
    for record in range(12):
        key = (14, 2, record)
        print(f"  rec{record:2d}: old={old.get(key)} new={new.get(key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
