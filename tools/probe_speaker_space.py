#!/usr/bin/env python3
"""Read-only probe: verify the ROM tail is unreferenced, list op-0x08 ids,
and locate 0xFF code padding near the readers."""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

ROM_BASE = 0x08000000
TAIL_LO = 0x085DFBEC
TAIL_HI = 0x08600000
READERS = [
    0x0807908C, 0x080811D2, 0x0808123E, 0x08086048, 0x08088814, 0x08088DB2,
    0x08089362, 0x0808D29A, 0x08090152, 0x08095514, 0x08095CF6, 0x08097A12,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()

    print("=== literals pointing into the 0xFF tail [%08X,%08X) ===" % (TAIL_LO, TAIL_HI))
    n = 0
    for off in range(0, len(rom) - 3, 4):
        v = int.from_bytes(rom[off:off + 4], "little")
        if TAIL_LO <= v < TAIL_HI:
            n += 1
            print("   0x%08X at file 0x%06X" % (v, off))
    print("   total: %d" % n)

    print("\n=== 0xFF runs (>=8) inside the code region near each reader ===")
    for r in READERS:
        lo = (r - ROM_BASE) - 0x200
        hi = (r - ROM_BASE) + 0x200
        runs = []
        i = max(0, lo)
        while i < min(len(rom), hi):
            if rom[i] == 0xFF:
                j = i
                while j < min(len(rom), hi) and rom[j] == 0xFF:
                    j += 1
                if j - i >= 8:
                    runs.append((i, j - i))
                i = j
            else:
                i += 1
        print("   reader 0x%08X: %s" % (r, ", ".join("0x%06X+%d" % (o, l) for o, l in runs) or "none"))

    print("\n=== op 0x08 / 0x0E operand ids used in the story scripts ===")
    sys.path.insert(0, str(REPO))
    from tools import decode_story_script as dss
    ids08, ids0e = set(), set()
    scenes = sorted(dss.SCENES) if hasattr(dss, "SCENES") else []
    try:
        table = dss.build_scene_table()  # type: ignore[attr-defined]
    except Exception:
        table = None
    print("   decode_story_script attrs: %s" % [a for a in dir(dss) if not a.startswith("_")][:40])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())