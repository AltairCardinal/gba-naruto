#!/usr/bin/env python3
"""Census of the structures whose readers live inside a subsystem.

Seven structures are still open because their reader is *not* the phase
dispatch of the story state machine:

    fonts                  0x0853E596   fn 0x0807F064   (level text label renderer)
    sprite-frame-descriptors 0x0853EE98 fn 0x08080670  (sprite frame table)
    items / skills         0x08545BE4   fn 0x0806D910   (item & skill record)
    ninjutsu-names         0x08599634   fn 0x0806F210   (ninjutsu name table)
    resource-pointers      0x08596F0C   fn 0x0807AE04   (resource pointer table)
    mechanism-effects      0x0808136C   fn 0x080812DC   (13-entry jump table)

All of them are read by the **level / map object system**, so this tool
loads every valid map through the game's own story dispatcher
(``state[0x16] = map_id``, ``state[0x12] = 0x0030``) and watches the
readers while the map is built and rendered.

Every hit is attributed by the program counter (``r15``), because the
probe's frame loop can stop on a *different* breakpoint than the one that
was armed last.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_WORD, SCENE_BYTE,
    MAP_LOAD_CALL, NEXT_SCENE, valid_map_ids,
)

# ---------------------------------------------------------------------------
# decision point -> (label, register, expected value)
#
# The decision point is the instruction that *loads* the table base, so the
# table address is visible in a register at that moment.  The value check
# makes a hit self-proving: a hit at the wrong place (or with a different
# table) is rejected instead of being counted.
READERS: dict[int, tuple[str, str, int]] = {
    0x0807F0FC: ("fonts", "r1", 0x0853E596),
    0x080806BA: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0808077E: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0808082E: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0806D91A: ("items", "r1", 0x08545BE4),
    0x0808FC28: ("items", "r1", 0x08545BE4),
    0x0808FF78: ("items", "r1", 0x08545BE4),
    0x08095394: ("items", "r1", 0x08545BE4),
    0x0806F504: ("ninjutsu-names", "r2", 0x08599634),
    0x08090286: ("ninjutsu-names", "r1", 0x08599634),
    0x08090350: ("ninjutsu-names", "r1", 0x08599634),
    0x0809734C: ("ninjutsu-names", "r1", 0x08599634),
    0x080973E6: ("ninjutsu-names", "r1", 0x08599634),
    0x0807B220: ("resource-pointers", "r0", 0x08596F0C),
    0x08081350: ("mechanism-effects", "r1", 0x0808136C),
}

# Sentinels that prove the route really ran.
SENTINEL_MAP_LOAD = MAP_LOAD_CALL
SENTINEL_OBJ_WALK = 0x08080F18     # level object list walker
SENTINEL_OBJ_CLEAR = 0x08080FA0    # level object list reset
SENTINEL_OBJ_TYPE = 0x0807FE2C     # the map renderer's object-type dispatch
SENTINEL_GLYPH = 0x0807EE50        # the map renderer's glyph metrics reader
SENTINEL_SPRITE = 0x08080B08       # the level object's descriptor reader


def pc_of(regs: dict) -> int:
    """The program counter of a register dump (mGBA prints r15, not `pc`)."""
    for key in ("r15", "pc"):
        if key in regs:
            return regs[key] & 0xFFFFFFFF
    return 0


def owner(addr: int) -> str:
    for base, (label, _reg, _val) in READERS.items():
        if abs(addr - base) <= 4:
            return label
    if abs(addr - SENTINEL_OBJ_WALK) <= 4:
        return "sentinel:object-walker"
    if abs(addr - SENTINEL_OBJ_CLEAR) <= 4:
        return "sentinel:object-clear"
    if abs(addr - SENTINEL_MAP_LOAD) <= 4:
        return "sentinel:map-load"
    if abs(addr - SENTINEL_OBJ_TYPE) <= 4:
        return "sentinel:object-type-dispatch"
    if abs(addr - SENTINEL_GLYPH) <= 4:
        return "sentinel:glyph-metrics-reader"
    if abs(addr - SENTINEL_SPRITE) <= 4:
        return "sentinel:object-descriptor-reader"
    return "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--maps", default="")
    ap.add_argument("--cont", type=int, default=900,
                    help="frames to continue between two hits")
    ap.add_argument("--rounds", type=int, default=8,
                    help="how many times to resume after a hit")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    rom_bytes = (REPO / args.rom).read_bytes()
    map_ids = valid_map_ids(rom_bytes)
    if args.maps:
        wanted = []
        for part in args.maps.split(","):
            if "-" in part:
                lo, hi = part.split("-", 1)
                wanted.extend(range(int(lo), int(hi) + 1))
            else:
                wanted.append(int(part))
        map_ids = [m for m in map_ids if m in wanted]

    results: dict[str, dict] = {}
    hits_by_structure: dict[str, int] = {}

    for map_id in map_ids:
        harness = Harness(REPO / "build" / "mgba-probe" / "mgba-probe.exe",
                          pathlib.Path(args.rom))
        record: dict = {"map_id": map_id, "map_loaded": False,
                        "hits": [], "notes": []}
        try:
            if not harness.boot_to_state_machine():
                record["notes"].append("state machine not reached")
                results[str(map_id)] = record
                continue

            # --- load the map through the game's own dispatcher -----------
            harness.arm(SENTINEL_MAP_LOAD)
            harness.poke(SCENE_BYTE, map_id)
            harness.poke16(PHASE_WORD, 0x0030)
            loaded = False
            for _ in range(20):
                out = harness.send(f"cont {args.cont}")
                hit = hit_of(out)
                if hit is None:
                    out = (harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
                           + harness.send("frames 120 0x000"))
                    hit = hit_of(out)
                if hit is None:
                    record["notes"].append("dispatcher never reached")
                    break
                if hit == SENTINEL_MAP_LOAD:
                    loaded = True
                    break
                harness.send("next")
                harness.rearm()
            record["map_loaded"] = loaded
            harness.disarm_all()

            if not loaded:
                results[str(map_id)] = record
                print(f"  map {map_id:3d}: (not loaded)")
                continue

            # --- watch the readers while the map is built and drawn ------
            for addr in READERS:
                harness.arm(addr)
            harness.arm(SENTINEL_OBJ_WALK)
            harness.arm(SENTINEL_OBJ_CLEAR)
            harness.arm(SENTINEL_OBJ_TYPE)
            harness.arm(SENTINEL_GLYPH)
            harness.arm(SENTINEL_SPRITE)

            for _ in range(args.rounds):
                out = harness.send(f"cont {args.cont}")
                hit = hit_of(out)
                if hit is None:
                    out = (harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
                           + harness.send("frames 120 0x000"))
                    hit = hit_of(out)
                if hit is None:
                    break
                # capture the registers *immediately* -- the next command
                # would move the program counter to another stop point
                regs = harness.probe.registers()
                pc = pc_of(regs)
                # mGBA reports the *armed* address in "Hit breakpoint N at
                # 0xADDR" while `status` prints r15 = armed + 2, so the hit
                # address is the reliable attribution key.
                label = owner(hit)
                entry = {"pc": f"0x{pc:08X}", "hit": f"0x{hit:08X}",
                         "owner": label}
                if label in {v[0] for v in READERS.values()}:
                    reg, expect = next((r, e) for _b, (_l, r, e)
                                        in READERS.items()
                                        if _l == label and abs(hit - _b) <= 4)
                    value = regs.get(reg, 0)
                    entry["reg"] = reg
                    entry["value"] = f"0x{value:08X}"
                    entry["expected"] = f"0x{expect:08X}"
                    entry["match"] = (value == expect)
                    if entry["match"]:
                        hits_by_structure[label] = hits_by_structure.get(label, 0) + 1
                record["hits"].append(entry)
                harness.send("next")
                harness.rearm()
            results[str(map_id)] = record
            labels = sorted({h["owner"] for h in record["hits"]
                             if h["owner"] != "?"})
            print(f"  map {map_id:3d}: {labels if labels else '(no reader hit)'}")
        finally:
            harness.close()

    summary = {
        "maps": len(map_ids),
        "hits_by_structure": hits_by_structure,
        "structures": sorted(hits_by_structure),
    }
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, {"summary": summary, "maps": results})
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
