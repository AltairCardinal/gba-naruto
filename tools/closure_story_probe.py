#!/usr/bin/env python3
"""Read the story state block while a story scene plays.

The three fields under investigation live in the story flag block
``0x020311D4``:

* ``0x020311E4`` (u16) ``story_progress`` -- written by a story VM opcode
  at ``0x08097BD4``, compared with 360 by the dispatcher at
  ``0x0808F5E0``;
* ``0x020311EC`` (u8)  ``story_branch``  -- read by the dispatcher at
  ``0x0808F5A0`` to pick the "after" root table, then copied to
  ``0x020311ED`` and cleared;
* ``0x020311ED..EF``    ``story_config`` -- the branch id plus two more
  bytes.

Usage:
    python tools/closure_story_probe.py --scene 54 --presses 40
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
    Harness, KEY_BITS, PHASE_NEXT_SCENE, SCENE_BYTE, PHASE_WORD,
)
from tools.mgba_probe.l4_playthrough import parse_scenes  # noqa: E402

STORY_STATE = 0x020311D4
FIELDS = {
    "story_progress@0x020311E4": (0x10, 2),
    "phase@0x020311E6": (0x12, 2),
    "scene_id@0x020311EA": (0x16, 1),
    "story_branch@0x020311EC": (0x18, 1),
    "story_config0@0x020311ED": (0x19, 1),
    "story_config1@0x020311EE": (0x1A, 1),
    "story_config2@0x020311EF": (0x1B, 1),
}


def read_story(harness: Harness) -> dict:
    raw = harness.read(STORY_STATE, 0x20)
    if len(raw) < 0x20:
        return {}
    out = {}
    for name, (offset, size) in FIELDS.items():
        chunk = raw[offset:offset + size]
        out[name] = int.from_bytes(chunk, "little")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--scenes", default="54")
    ap.add_argument("--presses", type=int, default=30)
    ap.add_argument("--plan", default="A")
    ap.add_argument("--settle", type=int, default=60)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    keys = [k.strip() for k in args.plan.split(",") if k.strip()]
    report: dict = {}
    for scene in parse_scenes(args.scenes):
        harness = Harness(args.exe, pathlib.Path(args.rom))
        log = []
        try:
            if not harness.boot_to_state_machine():
                print("could not park on the state machine loop head",
                      file=sys.stderr)
                return 1
            harness.poke(SCENE_BYTE, scene)
            harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
            for index in range(args.presses):
                key = keys[index % len(keys)]
                harness.send(f"frames 8 {KEY_BITS[key]:#05x}")
                harness.send(f"frames {args.settle} 0x000")
                state = read_story(harness)
                log.append({"press": index, "key": key, **state})
                print(f"scene {scene} press {index:3} key={key:<5} " +
                      " ".join(f"{k}={v}" for k, v in state.items()))
        finally:
            harness.close()
        report[str(scene)] = log
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
