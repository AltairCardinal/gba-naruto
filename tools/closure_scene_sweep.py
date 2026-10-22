#!/usr/bin/env python3
"""Sweep the story scenes and record what the native loaders do in each.

One boot per scene (the same rule the L4 playthrough uses: a per-scene boot
keeps the evidence independent of what the scene does next).  For every
scene the tool

* dispatches it with the three-write route (scene byte + phase 0x0030),
* watches a list of native addresses (the background loader, the level
  block loader, the portrait loader, ...),
* records, at every hit, the registers, the **stack** (so the caller of the
  hit can be identified) and the **IO registers** (DISPCNT, BG0CNT..BG3CNT).

Usage:
    python tools/closure_scene_sweep.py --scenes 1-55 \
        --break 0x08072F0C --break 0x08088348 --json build/closure-sweep.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_NEXT_SCENE, SCENE_BYTE, PHASE_WORD,
)
from tools.mgba_probe.l4_playthrough import parse_scenes  # noqa: E402

IO_BASE = 0x04000000
IO_LEN = 0x100
STORY_STATE = 0x020311D4      # the story flag block
STORY_LEN = 0x30


def read_story(harness: Harness) -> dict:
    """The story state block, with the three field names resolved."""
    raw = harness.read(STORY_STATE, STORY_LEN)
    if len(raw) < 0x20:
        return {}
    return {
        "story_progress@0x020311E4": int.from_bytes(raw[0x10:0x12], "little"),
        "story_branch@0x020311EC": raw[0x18],
        "story_config0@0x020311ED": raw[0x19],
        "story_config1@0x020311EE": raw[0x1A],
        "story_config2@0x020311EF": raw[0x1B],
        "scene_id@0x020311EA": raw[0x16],
        "phase@0x020311E6": int.from_bytes(raw[0x12:0x14], "little"),
    }


def read_io(harness: Harness) -> dict:
    """DISPCNT + the four BG control registers."""
    raw = harness.read(IO_BASE, IO_LEN)
    if len(raw) < 0x10:
        return {}
    out = {
        "DISPCNT": f"0x{int.from_bytes(raw[0:2], 'little'):04X}",
    }
    for index in range(4):
        offset = 0x08 + index * 2
        value = int.from_bytes(raw[offset:offset + 2], "little")
        out[f"BG{index}CNT"] = f"0x{value:04X}"
    return out


def run_scene(harness: Harness, scene: int, breaks: list[int], frames: int,
              hits: int, press: str) -> list[dict]:
    """Dispatch one scene and collect the breakpoint hits."""
    if not harness.boot_to_state_machine():
        return [{"error": "could not park on the state machine loop head"}]
    harness.poke(SCENE_BYTE, scene)
    harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
    for address in breaks:
        harness.arm(address)
    mask = KEY_BITS.get(press, 0)
    out: list[dict] = []
    budget = frames
    while budget > 0 and len(out) < hits:
        chunk = min(240, budget)
        budget -= chunk
        lines = harness.send(f"frames {chunk} {mask:#05x}")
        hit = hit_of(lines)
        if hit is None:
            harness.send("frames 8 0x000")
            continue
        regs = harness.probe.registers()
        entry = {
            "address": f"0x{hit:08X}",
            "registers": {k: f"0x{v:08X}" for k, v in sorted(regs.items())},
        }
        sp = regs.get("sp", 0)
        if sp:
            stack = harness.read(sp, 0x10)
            entry["stack"] = [f"0x{int.from_bytes(stack[i:i + 4], 'little'):08X}"
                              for i in range(0, len(stack), 4)]
        entry["io"] = read_io(harness)
        entry["story"] = read_story(harness)
        out.append(entry)
        harness.send("next")
        harness.rearm()
    harness.disarm_all()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--scenes", default="1-55")
    ap.add_argument("--breaks", default="", help="comma separated addresses")
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--hits", type=int, default=8)
    ap.add_argument("--press", default="A")
    ap.add_argument("--json", type=pathlib.Path,
                    default=REPO / "build" / "closure-scene-sweep.json")
    args = ap.parse_args(argv)

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    breaks = [int(item, 0) for item in args.breaks.split(",") if item.strip()]
    scenes = parse_scenes(args.scenes)
    report: dict = {"scenes": {}}
    for scene in scenes:
        harness = Harness(args.exe, pathlib.Path(args.rom))
        try:
            hits = run_scene(harness, scene, breaks, args.frames, args.hits,
                             args.press)
        finally:
            harness.close()
        report["scenes"][str(scene)] = hits
        summary = ", ".join(
            f"{h['address']}" for h in hits if "address" in h)
        print(f"scene {scene:3}: {len(hits)} hit(s)  {summary}")
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
