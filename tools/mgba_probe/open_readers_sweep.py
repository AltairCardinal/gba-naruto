"""Sweep the story route for every still-open structure's reader.

Several structures are only read by the map/battle renderer, which the
story route never reaches; the story VM, however, runs a lot of code.
This tool runs a list of scenes with *all* the open reader decision
points armed at once and reports which of them fire.

Usage:
    python tools/mgba_probe/open_readers_sweep.py rom/base.gba \\
        --scenes 43,46,30,50,51,60,23 --presses 220
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
)

ANSWER_ADDR = 0x0200A880

# decision point -> (structure, register, expected value)
READERS: dict[int, tuple[str, str, int]] = {
    # fonts -- the level text label renderer
    0x0807F0FC: ("fonts", "r1", 0x0853E596),
    # sprite frame descriptors
    0x080806BA: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0808077E: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0808082E: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    # items / skills -- one 16 byte record per id
    0x0806D91A: ("items", "r1", 0x08545BE4),
    0x08078EF8: ("items", "r1", 0x08545BE4),
    0x0808FC28: ("items", "r1", 0x08545BE4),
    0x0808FF78: ("items", "r1", 0x08545BE4),
    0x08095394: ("items", "r1", 0x08545BE4),
    # ninjutsu names -- 12 readers
    0x0809734C: ("ninjutsu-names", "r1", 0x08599634),
    0x080973E6: ("ninjutsu-names", "r1", 0x08599634),
    0x0806F504: ("ninjutsu-names", "r2", 0x08599634),
    0x080796E4: ("ninjutsu-names", "r1", 0x08599634),
    0x08079704: ("ninjutsu-names", "r1", 0x08599634),
    0x08081642: ("ninjutsu-names", "r1", 0x08599634),
    0x080816FE: ("ninjutsu-names", "r1", 0x08599634),
    0x0808E9F8: ("ninjutsu-names", "r1", 0x08599634),
    0x08090286: ("ninjutsu-names", "r1", 0x08599634),
    0x08090350: ("ninjutsu-names", "r1", 0x08599634),
    # resource pointers
    0x0807B220: ("resource-pointers", "r0", 0x08596F0C),
    # mechanism effects -- a 13 entry jump table
    0x08081350: ("mechanism-effects", "r1", 0x0808136C),
    # story-e -- the sound id 14 jingle
    0x080894FC: ("story-e", "r0", 0x0E),
    # cutscene scripts
    0x08072F0E: ("cutscene-scripts", "r4", 0x0853DF70),
}
# extra sites that only trace how far the script got
TRACE_SITES = {
    0x080978DC: "VM op 0x01 dialogue",
    0x08097992: "VM op 0x05 menu-text",
    0x080979D6: "VM op 0x06 branch2",
    0x08097C9C: "VM op 0x1B music",
    0x08097CC4: "VM op 0x1D ninjutsu name",
    0x08097C2C: "VM op 0x16 after-root switch",
    0x080960BE: "story choice menu",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--scenes", default="43")
    ap.add_argument("--state", default="build/l2-states/sweep.ss9")
    ap.add_argument("--presses", type=int, default=220)
    ap.add_argument("--force-row", type=int, default=None)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    scenes = [int(s) for s in args.scenes.split(",") if s.strip()]
    harness = Harness(REPO / "build" / "mgba-probe" / "mgba-probe.exe",
                      pathlib.Path(args.rom))
    records: list[dict] = []
    try:
        for scene in scenes:
            harness.send(f"load {args.state}")
            harness.disarm_all()
            armed = dict(READERS)
            if args.trace:
                armed.update(TRACE_SITES)
            for addr in armed:
                harness.arm(addr)
            harness.poke(SCENE_BYTE, scene)
            harness.poke16(PHASE_WORD, 0x0030)
            harness.send("next")
            for _ in range(args.presses):
                out = harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
                hit = hit_of(out)
                regs = harness.probe.registers() if hit is not None else {}
                pc = regs.get("r15", 0) & 0xFFFFFFFF
                out2 = harness.send("frames 120 0x000")
                hit2 = hit_of(out2)
                regs2 = harness.probe.registers() if hit2 is not None else {}
                pc2 = regs2.get("r15", 0) & 0xFFFFFFFF
                for h, p, r in ((hit, pc, regs), (hit2, pc2, regs2)):
                    if h is None:
                        continue
                    if h == 0x080960BE and args.force_row is not None:
                        harness.poke(ANSWER_ADDR, args.force_row & 0xFF)
                    struct = READERS.get(h, (None, None, None))[0]
                    reg = READERS.get(h, (None, None, None))[1]
                    expect = READERS.get(h, (None, None, None))[2]
                    value = r.get(reg, 0) if reg else None
                    rec = {"scene": scene, "hit": f"0x{h:08X}",
                           "pc": f"0x{p:08X}",
                           "structure": struct or "",
                           "label": {**{k: v[0] for k, v in READERS.items()},
                                     **TRACE_SITES}.get(h, "?"),
                           "r0": f"0x{r.get('r0', 0):08X}",
                           "r4": f"0x{r.get('r4', 0):08X}",
                           "r6": f"0x{r.get('r6', 0):08X}"}
                    if value is not None:
                        rec["value"] = f"0x{value:08X}"
                        rec["expected"] = f"0x{expect:08X}"
                        rec["match"] = (value == expect)
                    records.append(rec)
                    harness.send("next")
                    harness.rearm()
    finally:
        harness.close()

    matched = [r for r in records if r.get("match")]
    for rec in records:
        if rec["structure"]:
            print(json.dumps(rec, ensure_ascii=False))
    print(f"\nreader hits with a matching register: "
          f"{[(r['scene'], r['label']) for r in matched]}")
    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, {"records": records})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
