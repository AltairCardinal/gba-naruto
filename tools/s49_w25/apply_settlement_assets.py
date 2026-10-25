#!/usr/bin/env python3
"""Copy wave-24 / G3's settlement assets from its lane back into the shared tree.

G3 proved the settlement screen is a pure asset-layer defect (no C++ change):
    battle_result_font.bmp            - the 合計 row glyph cells lost their two-tone split
    battle_ui_result_total_palette.bmp - the palette table had no light-red (231,99,66) entry
    battle_ui_result_plate.bmp         - the plate was missing the patterned top border and a 3px right frame line

Result: 514 px -> 0 px on the settlement screen, 8 screens byte-identical.

The shared tree is the acceptance tree, so this copy is a parent action (the lane
copies are never authoritative).  The script verifies the sha256 of every file
against the receipts G3 recorded, refuses to write on a mismatch, and never
touches the shared tree's working state beyond the three listed files.

Usage:
    python tools/s49_w25/apply_settlement_assets.py            # dry run
    python tools/s49_w25/apply_settlement_assets.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARED = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
LANE = REPO / "build" / "w24-g3" / "butano-sequel"

# relative path -> expected sha256 prefix (from notes/s49-fidelity/W24-G3-settlement-frame.md)
ASSETS = {
    "graphics/battle_result_font.bmp": "68f7273072f901e4",
    "graphics/battle_ui_result_total_palette.bmp": "3321c0509b2ba6db",
    "graphics/battle_ui_result_plate.bmp": "1966940217d15893",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    failures = 0
    for rel, want in ASSETS.items():
        src = LANE / rel
        dst = SHARED / rel
        if not src.exists():
            print(f"MISSING in lane: {src}")
            failures += 1
            continue
        got = sha256(src)
        ok = got.startswith(want)
        shared_sha = sha256(dst) if dst.exists() else "<absent>"
        print(f"{rel}")
        print(f"    lane   {got[:32]}")
        print(f"    shared {shared_sha[:32]}")
        if not ok:
            print(f"    SHA MISMATCH (expected {want}) - refusing")
            failures += 1
            continue
        if shared_sha == got:
            print("    already identical - nothing to do")
            continue
        if args.apply:
            shutil.copy2(src, dst)
            print(f"    -> COPIED into the shared tree")
        else:
            print("    -> would copy (dry run)")
    if failures:
        print(f"\n{failures} problem(s); shared tree left alone")
        return 2
    print("\nok" if args.apply else "\ndry run ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
