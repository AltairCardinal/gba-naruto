#!/usr/bin/env python3
"""W20-E2: parse battle_scenario_definition entries out of a generated header.

Usage: python parse_generated_scenario.py <header.h> [battle_id ...]

Prints, for each requested battle id, the slot table: variant, record,
enabled, side, grid, facing, battle_experience.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCENARIO_RE = re.compile(
    r"battle_scenario_definition\{\s*\n"
    r"\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)U,\s*\n"
    r"(.*?)\n    \}",
    re.DOTALL,
)
SLOT_RE = re.compile(
    r"battle_scenario_unit_slot\{\s*"
    r"(true|false),\s*scenario_selector_kind::(\w+),\s*(\d+),\s*"
    r"battle_side::(\w+),\s*grid_point\{\s*(\d+),\s*(\d+)\s*\},\s*"
    r"battle_facing::(\w+),\s*(\d+),"
)


def parse(path: Path) -> dict[int, list[list[tuple]]]:
    text = path.read_text(encoding="utf-8")
    out: dict[int, list[list[tuple]]] = {}
    for match in SCENARIO_RE.finditer(text):
        battle_id = int(match.group(1))
        body = match.group(5)
        variants: list[list[tuple]] = []
        # split by the variant arrays
        chunks = body.split("std::array<battle_scenario_unit_slot, 12>")
        for chunk in chunks[1:]:
            variants.append(
                [
                    (
                        s.group(1) == "true",
                        s.group(4),
                        int(s.group(5)),
                        int(s.group(6)),
                        s.group(7),
                        int(s.group(8)),
                    )
                    for s in SLOT_RE.finditer(chunk)
                ]
            )
        out[battle_id] = variants
    return out


def main() -> int:
    header = Path(sys.argv[1])
    ids = [int(a) for a in sys.argv[2:]] or [14]
    data = parse(header)
    print(f"# parsed {len(data)} scenarios from {header}")
    for battle_id in ids:
        variants = data.get(battle_id)
        if variants is None:
            print(f"battle {battle_id}: NOT FOUND")
            continue
        print(f"battle {battle_id}: {len(variants)} variants")
        for v_index, slots in enumerate(variants):
            print(f"  variant {v_index}: {len(slots)} slots")
            for r_index, slot in enumerate(slots):
                enabled, side, x, y, facing, be = slot
                flag = "ENABLED" if enabled else "disabled"
                print(
                    f"    rec {r_index:2d}: {flag:8s} {side:6s} "
                    f"({x},{y}) {facing:5s} battle_experience={be}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
