"""Sweep the level object's type and watch the map renderer's readers.

`fn 0x08080F18` walks the level object list (`0x02026604`, 32 records of
16 bytes) and, for every record whose type byte is 1, 2, 3 or 4, builds a
sprite from the template table `0x0859924C` and the sprite attribute table
`0x08599274`.

The level the chapter route enters has exactly **one** object (type 3).
This tool rewrites that object's type byte (right before the walk, so the
level data DMA cannot overwrite it) and watches the readers of the
structures that are still open -- above all the map renderer's text
renderer (`fn 0x0807F064`, the `fonts` reader) and the sprite frame
descriptor readers (`fn 0x08080670` / `0x08080764` / `0x08080814`).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(r"D:\Github\gba-naruto")
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_WORD,
)

OBJ_LIST = 0x02026604
OBJ_STRIDE = 16
OBJ_COUNT = 32

# decision point -> (structure, register, expected value)
READERS: dict[int, tuple[str, str, int]] = {
    0x0807F0FC: ("fonts", "r1", 0x0853E596),
    0x080806BA: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0808077E: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0808082E: ("sprite-frame-descriptors", "r1", 0x0853EE98),
    0x0807B220: ("resource-pointers", "r0", 0x08596F0C),
    0x0806D91A: ("items", "r1", 0x08545BE4),
    0x08081350: ("mechanism-effects", "r1", 0x0808136C),
    0x0807EEA8: ("font-metrics", "r1", 0x0853E328),
}
SENTINELS = {
    0x08080EF0: "SENTINEL level data DMA",
    0x08080FA0: "SENTINEL object list reset",
    0x08080F18: "SENTINEL object list walker",
    0x08080B08: "SENTINEL object descriptor reader fn",
    0x0807FE2C: "SENTINEL object-type dispatch fn",
    0x0807EE50: "SENTINEL glyph metrics reader fn",
}


def dump_objects(harness):
    raw = harness.read(OBJ_LIST, OBJ_COUNT * OBJ_STRIDE)
    out = []
    for i in range(OBJ_COUNT):
        rec = raw[i * OBJ_STRIDE:(i + 1) * OBJ_STRIDE]
        if any(rec):
            out.append({"index": i, "type": rec[0], "sub": rec[1],
                        "bytes": " ".join(f"{b:02X}" for b in rec)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--state", default="build/l2-states/chapter.ss9")
    ap.add_argument("--types", default="1-4")
    ap.add_argument("--presses", type=int, default=40)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    types = []
    for part in args.types.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            types.extend(range(int(lo), int(hi) + 1))
        else:
            types.append(int(part))

    harness = Harness(REPO / "build" / "mgba-probe" / "mgba-probe.exe",
                      pathlib.Path(args.rom))
    results: dict[str, dict] = {}
    try:
        for otype in types:
            harness.send(f"load {args.state}")
            harness.disarm_all()
            for addr in {**READERS, **SENTINELS}:
                harness.arm(addr)
            # re-run the level setup so the object list is rebuilt
            harness.poke16(PHASE_WORD, 0x0100)
            harness.send("next")
            seen: list[str] = []
            patched = False
            for _ in range(args.presses):
                out = harness.send(f"cont 600")
                hit = hit_of(out)
                if hit is None:
                    out = (harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
                           + harness.send("frames 120 0x000"))
                    hit = hit_of(out)
                if hit is None:
                    break
                if hit == 0x08080F18 and not patched:
                    # the DMA has already run, so the patch survives
                    base = OBJ_LIST + 1 * OBJ_STRIDE
                    harness.poke(base, otype & 0xFF)
                    patched = True
                    print(f"    [patched object 1 type -> {otype}]")
                label = None
                for addr, (struct, _reg, _exp) in READERS.items():
                    if hit == addr:
                        label = struct
                        break
                if label is None:
                    for addr, name in SENTINELS.items():
                        if hit == addr:
                            label = name
                            break
                if label and label not in seen:
                    seen.append(label)
                harness.send("next")
                harness.rearm()
            results[str(otype)] = {"seen": seen,
                                   "objects": dump_objects(harness)}
            print(f"  type {otype:3d}: {seen if seen else '(nothing)'}")
    finally:
        harness.close()

    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
