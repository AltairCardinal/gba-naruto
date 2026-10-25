"""W3: emit the C++ tables of the entry transition from the measurements.

The probe reads the measured level table and the measured shard plan and
writes the two C++ tables the product header needs:

  battle_transition_level_area        the visible window's area per level
  battle_transition_level_cost         the OBJ tiles and sprites per level

The tables are never hand typed: this script writes them.
"""
from __future__ import annotations

import argparse
import json
import pathlib

# Z2's star model covers 25 levels; the original keeps growing afterwards.
STAR_LEVELS = 25
EXTRA_LEVELS = 12
TOTAL_LEVELS = STAR_LEVELS + EXTRA_LEVELS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    levels = json.loads(
        pathlib.Path(args.levels).read_text(encoding="utf-8"))["levels"]
    plan = json.loads(
        pathlib.Path(args.plan).read_text(encoding="utf-8"))

    # The transition starts at the first level whose area is Z2's first area
    # (7925): that is the first level of the black field.
    start = next(index for index, level in enumerate(levels)
                 if level["area"] == 7925)
    window = levels[start:start + TOTAL_LEVELS]
    assert len(window) == TOTAL_LEVELS, len(window)

    costs = {entry["level"]: entry for entry in plan}
    rows = []
    for index, level in enumerate(window):
        shard = costs[level["level"]]["shards"]["16"]
        rows.append((level["area"], shard["obj_tiles"], shard["sprites"]))

    lines = []
    lines.append("inline constexpr std::array<int, "
                 f"{TOTAL_LEVELS}> battle_transition_level_area = {{")
    for offset in range(0, TOTAL_LEVELS, 8):
        chunk = ", ".join(f"{rows[i][0]:6d}" for i in
                          range(offset, min(offset + 8, TOTAL_LEVELS)))
        lines.append(f"    {chunk},")
    lines.append("}};")
    lines.append("")
    lines.append("struct battle_transition_level_cost")
    lines.append("{")
    lines.append("    std::uint16_t obj_tiles = 0;")
    lines.append("    std::uint16_t sprites = 0;")
    lines.append("")
    lines.append("    constexpr bool operator==(")
    lines.append("            const battle_transition_level_cost&) const = default;")
    lines.append("};")
    lines.append("")
    lines.append("inline constexpr std::array<battle_transition_level_cost, "
                 f"{TOTAL_LEVELS}> battle_transition_level_cost = {{")
    for offset in range(0, TOTAL_LEVELS, 6):
        chunk = []
        for i in range(offset, min(offset + 6, TOTAL_LEVELS)):
            chunk.append("{{ {:4d}, {:3d} }}".format(rows[i][1], rows[i][2]))
        lines.append("    " + ", ".join(chunk) + ",")
    lines.append("}};")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
