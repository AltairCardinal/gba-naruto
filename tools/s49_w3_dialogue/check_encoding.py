"""W3: check that the files this stream touched are LF and have no BOM."""
from __future__ import annotations

import pathlib
import sys

FILES = [
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_range_ui_style.h",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_map_content.h",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\grid_pathfinder.h",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_presentation_content.h",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_range_ui_overlay_rules.cpp",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_transition_overlay_budget.cpp",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\measure_full_mask.py",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\visible_area.py",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\render_mask_sheet.py",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\entry_levels.py",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\shard_plan.py",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\overlay_obj_cost.py",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\diff_shipped_mask_table.py",
    r"D:\Github\gba-naruto\tools\s49_w3_dialogue\emit_tables.py",
    r"D:\Github\gba-naruto\build\w3-run-new-tests.sh",
    r"D:\Github\gba-naruto\notes\s49-fidelity\W3-overlay-dialogue.md",
]


def main() -> int:
    bad = 0
    for name in FILES:
        path = pathlib.Path(name)
        if not path.exists():
            print(f"MISSING {name}")
            bad += 1
            continue
        data = path.read_bytes()
        bom = data[:3] == b"\xef\xbb\xbf"
        crlf = data.count(b"\r\n")
        lf = data.count(b"\n") - crlf
        status = "ok"
        if bom:
            status = "BOM"
            bad += 1
        elif crlf:
            status = "CRLF"
            bad += 1
        print(f"{status:5s} bom={int(bom)} crlf={crlf:4d} lf={lf:5d} "
              f"{path.name}")
    print(f"problem files: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
