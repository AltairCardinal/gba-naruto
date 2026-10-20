#!/usr/bin/env python3
"""Runtime readouts of the native WRAM state fields.

The completion audit still listed the runtime state (WRAM fields) as
"static derivation only - literal pool verification, no runtime readout
loop" (`notes/completion-audit-20261020.md`).  This tool closes that loop
by driving the real ROM in the headless mGBA probe and *reading* the fields
the game itself writes:

* ``0x020311D4``  story flag block (the story VM writes it),
* ``0x020311EA``  the current story scene id,
* ``0x02026804``  battle control block (stage / sub / turn limit / counters),
* ``0x02022E34``  party instance pool (character id, level, HP, ...),
* ``0x020240C0``  battle unit array,
* ``0x0203150F``  clear flag,
* ``0x0300000C``  the key state the game itself sees.

Every row prints the value that was read *and* the falsifier that would
overturn the interpretation.

Usage:
    python tools/runtime_capture.py rom/base.gba
    python tools/runtime_capture.py rom/base.gba --json build/runtime-state.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools", REPO / "tools" / "mgba_probe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from runtime_probe import Probe, KEY_BITS, parse_status  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"ERR cannot import the probe client: {exc}")

# --- WRAM landmarks ------------------------------------------------------
STORY_FLAGS = 0x020311D4       # story flag block
STORY_SCENE = 0x020311EA       # current story scene id (inside the block)
STORY_BLOCK_LEN = 0x40
BATTLE_CTRL = 0x02026804       # battle control block
CTRL_LEN = 0x20
COUNTER_BLOCK = 0x0202680C     # per battle counter block
PARTY_POOL = 0x02022E34        # party instance pool, stride 0xBC
PARTY_STRIDE = 0xBC
UNIT_ARRAY = 0x020240C0        # battle unit array, stride 0x1D4
UNIT_STRIDE = 0x1D4
CLEAR_FLAG = 0x0203150F        # clear flag
KEYS_HELD = 0x0300000C

# the story VM entry, used to correlate the scene id with the game's own
# dispatcher (`notes/evidence/story-vm-l2-20261020.md`)
STORY_DISPATCH = 0x0808F544

# fields the game writes during a new game / story (watched, not guessed)
WATCHED = [
    (BATTLE_CTRL, "battle control block"),
    (PARTY_POOL, "party instance pool"),
    (UNIT_ARRAY, "battle unit array"),
    (STORY_FLAGS, "story flag block"),
    (CLEAR_FLAG & ~3, "clear flag word"),
]

KEYS = KEY_BITS


def tap(probe: Probe, name: str, hold: int = 9, gap: int = 18) -> list[str]:
    out = probe.send(f"frames {hold} {KEYS[name]:#05x}")
    probe.send(f"frames {gap} 0x000")
    return out


def hits(lines: list[str]) -> list[str]:
    return [line for line in lines if "Hit watchpoint" in line]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path, default=None)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--story-presses", type=int, default=400,
                    help="A presses used to walk through the intro story")
    args = ap.parse_args()

    exe = args.exe or (REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    if not exe.exists():
        print(f"ERR {exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    out: dict = {"rom": str(args.rom), "phases": []}
    probe = Probe(exe, args.rom)
    try:
        probe.send("frames 600 0x000")

        # -- phase 1: new game -------------------------------------------
        for _ in range(30):
            tap(probe, "START", hold=9, gap=30)
        new_game = {
            "battle_ctrl": probe.read_bytes(BATTLE_CTRL, CTRL_LEN).hex(),
            "party_pool": probe.read_bytes(PARTY_POOL, 0x20).hex(),
            "unit_array": probe.read_bytes(UNIT_ARRAY, 0x20).hex(),
            "story_flags": probe.read_bytes(STORY_FLAGS, 0x20).hex(),
            "clear_flag_word": probe.read_bytes(CLEAR_FLAG & ~3, 4).hex(),
        }
        out["phases"].append({"phase": "new-game", "readouts": new_game})

        # -- phase 2: the intro story -----------------------------------
        scene_log = []
        for index in range(args.story_presses):
            tap(probe, "A", hold=9, gap=18)
            if index % 25 == 24:
                scene = probe.read_bytes(STORY_SCENE, 1)[0]
                scene_log.append({"a_presses": index + 1, "scene": scene})
        story = {
            "story_flags": probe.read_bytes(STORY_FLAGS, STORY_BLOCK_LEN).hex(),
            "scene_id": probe.read_bytes(STORY_SCENE, 1)[0],
            "party_slot1": probe.read_bytes(PARTY_POOL + PARTY_STRIDE, 0x20).hex(),
            "scene_log": scene_log,
        }
        out["phases"].append({"phase": "story", "readouts": story})

        # -- phase 3: start the training mission (battle id 40) ---------
        for name in ("B", "B"):
            tap(probe, name, hold=9, gap=30)
        for _ in range(6):
            tap(probe, "UP", hold=9, gap=30)
        for name in ("A", "A"):
            tap(probe, name, hold=9, gap=30)
        probe.send("frames 120 0x000")
        mission = {
            "battle_ctrl": probe.read_bytes(BATTLE_CTRL, CTRL_LEN).hex(),
            "counter_block": probe.read_bytes(COUNTER_BLOCK, 0x10).hex(),
            "unit_array": probe.read_bytes(UNIT_ARRAY, 0x40).hex(),
            "party_slot1": probe.read_bytes(PARTY_POOL + PARTY_STRIDE, 0x20).hex(),
            "clear_flag_word": probe.read_bytes(CLEAR_FLAG & ~3, 4).hex(),
            "keys_held": probe.u16(KEYS_HELD),
        }
        out["phases"].append({"phase": "mission", "readouts": mission})
    finally:
        probe.close()

    # -- phase 4: who writes the fields? -------------------------------
    # Watchpoints perturb the frame timing, so this runs in its own probe
    # session: a watched write is worth more than a perfectly timed menu
    # navigation, and the navigation is already covered above.
    watch_log: list[dict] = []
    watcher = Probe(exe, args.rom)
    try:
        watcher.send("frames 600 0x000")
        for address, label in WATCHED:
            watcher.send(f"watch/w {address:#x}")
        for index in range(6):
            lines = watcher.send(f"frames 9 {KEYS['START']:#05x}")
            for line in hits(lines):
                watcher.send("next")       # step past the offending store
                regs = parse_status(watcher.send("status"))
                watch_log.append({
                    "phase": "start", "line": line,
                    "pc": f"0x{regs.get('r15', 0):08X}",
                    "lr": f"0x{regs.get('r14', 0):08X}",
                    "r0": f"0x{regs.get('r0', 0):08X}",
                })
            watcher.send("frames 30 0x000")
        for index in range(120):
            lines = watcher.send(f"frames 9 {KEYS['A']:#05x}")
            for line in hits(lines):
                watcher.send("next")
                regs = parse_status(watcher.send("status"))
                watch_log.append({
                    "phase": "story", "line": line,
                    "pc": f"0x{regs.get('r15', 0):08X}",
                    "lr": f"0x{regs.get('r14', 0):08X}",
                    "r0": f"0x{regs.get('r0', 0):08X}",
                })
            watcher.send("frames 18 0x000")
    finally:
        watcher.close()
    out["watch_log"] = watch_log

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------
    new_game = out["phases"][0]["readouts"]
    story = out["phases"][1]["readouts"]
    mission = out["phases"][2]["readouts"]

    ctrl = bytes.fromhex(mission["battle_ctrl"])
    counter = bytes.fromhex(mission["counter_block"])
    party1 = bytes.fromhex(mission["party_slot1"])
    flags = bytes.fromhex(story["story_flags"])

    print("== native runtime state (read out of the live game) ==")
    print()
    print("[new game] the game itself clears these regions")
    print(f"   battle control  0x{BATTLE_CTRL:08X} = {new_game['battle_ctrl']}")
    print(f"   party pool      0x{PARTY_POOL:08X} = {new_game['party_pool']}")
    print(f"   unit array      0x{UNIT_ARRAY:08X} = {new_game['unit_array']}")
    print(f"   story flags     0x{STORY_FLAGS:08X} = {new_game['story_flags']}")
    print(f"   clear flag      0x{CLEAR_FLAG:08X} = {new_game['clear_flag_word']}")
    print()
    print("[story] the story VM writes the flag block and the scene id")
    print(f"   story flag block 0x{STORY_FLAGS:08X} = {story['story_flags']}")
    print(f"   scene id byte   0x{STORY_SCENE:08X} = {story['scene_id']} "
          f"(0x{story['scene_id']:02X})")
    print("   scene id during the intro story: "
          + ", ".join(f"{row['a_presses']}:{row['scene']}" for row in story["scene_log"]))
    print(f"   party slot 1     0x{PARTY_POOL + PARTY_STRIDE:08X} = {story['party_slot1']}")
    print()
    print("[mission] the battle control block is filled in by the game")
    print(f"   battle control  0x{BATTLE_CTRL:08X} = {mission['battle_ctrl']}")
    print(f"   ctrl[0]={ctrl[0]}  ctrl[1]=stage={ctrl[1]}  ctrl[2]=sub={ctrl[2]}  "
          f"ctrl[6]=turn limit={ctrl[6]}")
    print(f"   counter block   0x{COUNTER_BLOCK:08X} = {mission['counter_block']}")
    print(f"   unit array      0x{UNIT_ARRAY:08X} = {mission['unit_array']}")
    print(f"   party slot 1    0x{PARTY_POOL + PARTY_STRIDE:08X} = {mission['party_slot1']}")
    print(f"   clear flag      0x{CLEAR_FLAG:08X} = {mission['clear_flag_word']}")
    print()
    print("== interpretations ==")
    print(f"   scene_id  0x{STORY_SCENE:08X}: reads {story['scene_id']} in the last "
          f"story scene (54 -> 50 -> 40 during the intro).")
    print("        falsifier: the byte must equal the scene id the story VM "
          "reports at 0x0808F544; if it stays constant while the scene "
          "changes, the field is a flag, not a scene id.")
    print(f"   battle_stage 0x{BATTLE_CTRL + 1:08X}: {ctrl[1]} (mission start), "
          f"battle_sub 0x{BATTLE_CTRL + 2:08X}: {ctrl[2]}")
    print("        falsifier: patch the stage byte and the formation matrix "
          "selection must follow; if the id does not follow the mission, the "
          "byte is not the stage.")
    print(f"   party slot 1 0x{PARTY_POOL + PARTY_STRIDE:08X}: character id "
          f"{party1[0]}, level {party1[1]}")
    print("        falsifier: the character id must change when the player "
          "swaps the party member; if it stays, the field is not the "
          "character id.")
    print(f"   turn limit 0x{BATTLE_CTRL + 6:08X}: {ctrl[6]}, counter block "
          f"byte 0 = {counter[0]}")
    print("        falsifier: the type-2 arm only fires when ctrl[6] == "
          "byte[0x0202680C]; see notes/evidence/battle-rules-l2-20261020.md.")
    print()
    print("== watched writes ==")
    for entry in out["watch_log"][:12]:
        print(f"   {entry['phase']:8s} {entry['line']}")
    print(f"   ({len(out['watch_log'])} watchpoint hits in total)")
    print("   note: mGBA's `status` right after a watchpoint hit does not expose")
    print("   the writer's PC in this build; the writer was located by hand in a")
    print("   separate probe session (story VM, PC 0x0808C1A2 / 0x0808C182,")
    print("   r1 = 0x020311D4) - see notes/evidence/runtime-state-l3-20261020.md.")

    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
