#!/usr/bin/env python3
"""W20-E2: dump the raw text of one battle_scenario_definition from the header."""

from __future__ import annotations

import pathlib
import sys

HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\generated_battle_scenario_content.h"
)


def main() -> int:
    battle_id = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    text = HEADER.read_text(encoding="utf-8")
    needle = f"battle_scenario_definition{{\n    {battle_id}, "
    start = text.find(needle)
    if start < 0:
        print("not found")
        return 1
    end = text.find("\n    }", start)
    body = text[start:end + len("\n    }")]
    # strip the long runtime_config blobs so the slot list is readable
    lines = []
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("battle_scenario_unit_slot{") or stripped.startswith(
            "battle_scenario_definition{"
        ):
            lines.append(stripped[:260])
        else:
            lines.append(stripped)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
