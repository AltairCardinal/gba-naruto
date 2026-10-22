#!/usr/bin/env python3
"""Measure the m4a engine's own pitch value at run time (item H).

The engine computes a DirectSound note's pitch in ``0x0809A998``
(``GetPitch``) and stores it into the voice structure at
``0x0809A658`` (``str r0, [r4, #0x20]``).  This tool parks the game in a
real battle (the three-write route proved in
``notes/evidence/l4-battle-matrix-20261021.md``), breaks on that store and
records:

* ``r0``   -- the pitch register the engine actually used,
* ``r4``   -- the voice structure (key at +8, rate at +4, wave at +0x24),
* ``r5``   -- the channel structure (bend offset at +8, fraction at +9).

The recorded triple (key, bend offset, fraction) is what a renderer has to
reproduce, and the recorded ``r0`` is the number a renderer has to hit.

Usage:
    python tools/closure_pitch_probe.py --battle 9:0 --hits 6 \
        --json build/closure-pitch.json
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
    Harness, hit_of, KEY_BITS, PHASE_BATTLE, PHASE_NEXT_SCENE,
    SCENE_BYTE, SUBCFG_BYTE, PHASE_WORD, MAPID_BYTE,
)

# native addresses
PITCH_STORE_DS = 0x0809A658      # str r0, [r4, #0x20]  (DirectSound path)
PITCH_STORE_NOTE = 0x0809A8E0    # str r0, [r4, #0x20]  (note-on path)
PITCH_STORE_PSG = 0x0809A642     # str r0, [r4, #0x20]  (PSG path)
BEND_CMD = 0x0809A368            # the BEND command handler
BENDR_CMD = 0x0809A37C           # the BENDR command handler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--battle", default="9:0")
    ap.add_argument("--scene", type=int, default=None,
                    help="dispatch a story scene instead of a battle")
    ap.add_argument("--breaks", action="append", default=[],
                    help="extra breakpoint address (repeatable)")
    ap.add_argument("--hits", type=int, default=6)
    ap.add_argument("--poke-bend", default=None,
                    help="after the first note-on hit, write this BEND value "
                         "(0..255) into the channel's +0x0E slot, set the bend "
                         "range in +0x0F and raise the pitch-dirty bit, so the "
                         "engine itself recomputes the bend")
    ap.add_argument("--poke-range", type=int, default=2)
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    group, _, sub = args.battle.partition(":")
    harness = Harness(args.exe, pathlib.Path(args.rom))
    record: dict = {"battle": args.battle, "hits": []}
    try:
        if not harness.boot_to_state_machine():
            record["error"] = "could not park on the state machine loop head"
            print(json.dumps(record, indent=2))
            return 1
        if args.scene is not None:
            harness.poke(SCENE_BYTE, args.scene)
            harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
            record["scene"] = args.scene
        else:
            harness.poke(SCENE_BYTE, int(group))
            harness.poke(SUBCFG_BYTE, int(sub))
            harness.poke16(PHASE_WORD, PHASE_BATTLE)

        # --- let the battle intro play out (no breakpoints: fast path) ---
        mask = KEY_BITS["A"]
        for _ in range(30):
            harness.send(f"frames 8 {mask:#05x}")
            harness.send("frames 120 0x000")
            if args.scene is None:
                raw = harness.read(MAPID_BYTE, 1)
                if raw and raw[0] == int(group):
                    break
        harness.send(f"frames 8 {mask:#05x}")
        harness.send("frames 120 0x000")

        # --- now break on the engine's own pitch store ---
        breaks = [PITCH_STORE_DS, PITCH_STORE_NOTE, PITCH_STORE_PSG,
                  0x0809B486, 0x0809A368, 0x0809A8F0]
        breaks += [int(b, 0) for b in args.breaks]
        for addr in breaks:
            harness.arm(addr)

        hit = None
        for _ in range(args.hits + 4):
            out = harness.send(f"frames {args.frames} {mask:#05x}")
            hit = hit_of(out)
            if hit is None:
                out = harness.send(f"frames 8 {mask:#05x}") + harness.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                break
            regs = harness.probe.registers()
            voice = regs.get("r4", 0)
            channel = regs.get("r5", 0)
            entry = {
                "address": f"0x{hit:08X}",
                "pitch": f"0x{regs.get('r0', 0):08X}",
                "voice": f"0x{voice:08X}",
                "channel": f"0x{channel:08X}",
                "r1": f"0x{regs.get('r1', 0):08X}",
                "r2": f"0x{regs.get('r2', 0):08X}",
                "r3": f"0x{regs.get('r3', 0):08X}",
            }
            if voice:
                raw = harness.read(voice, 0x28)
                entry["voice_bytes"] = raw.hex()
                entry["key"] = raw[8] if len(raw) > 8 else None
                entry["rate"] = int.from_bytes(raw[4:8], "little") if len(raw) >= 8 else None
                entry["wave"] = f"0x{int.from_bytes(raw[0x24:0x28], 'little'):08X}" \
                    if len(raw) >= 0x28 else None
            if channel:
                raw = harness.read(channel, 0x20)
                entry["channel_bytes"] = raw.hex()
                entry["bend_offset"] = raw[8] if len(raw) > 8 else None
                entry["fraction"] = raw[9] if len(raw) > 9 else None
                entry["bend_cmd"] = (raw[0x0E] - 256) & 0xFF if len(raw) > 0x0E else None
                entry["bend_range"] = raw[0x0F] if len(raw) > 0x0F else None
                entry["key_shift"] = (raw[0x0A] - 256) & 0xFF if len(raw) > 0x0A else None
                entry["tune"] = (raw[0x0C] - 256) & 0xFF if len(raw) > 0x0C else None
                entry["ch0b"] = raw[0x0B] if len(raw) > 0x0B else None
                entry["ch0d"] = raw[0x0D] if len(raw) > 0x0D else None
                entry["mod_offset"] = (raw[0x16] - 256) & 0xFF if len(raw) > 0x16 else None
                entry["modt"] = raw[0x18] if len(raw) > 0x18 else None
            record["hits"].append(entry)
            print(f"hit 0x{hit:08X} pitch={entry['pitch']} key={entry.get('key')} "
                  f"off={entry.get('bend_offset')} frac={entry.get('fraction')}")
            if (args.poke_bend is not None and not record.get("poked")
                    and hit == 0x0809A8F0 and channel):
                # Drive the engine's own bend path.
                #
                # The BEND command (0xC0) writes `value - 0x40` into
                # channel+0x0E and the BENDR command (0xC1) writes the range
                # into channel+0x0F (0x0809A368 / 0x0809A37C).  The engine
                # turns those into the semitone offset (channel+0x08) and the
                # fraction (channel+0x09) in 0x0809B450..0x0809B486, and it
                # only does that while channel[0] bit 2 is set.  The note
                # handler clears bits 0..3 at 0x0809A8EC, so the poke has to
                # happen after that -- 0x0809A8F0 is the note handler's
                # epilogue and is reached right after the clear.
                value = int(args.poke_bend, 0)
                harness.poke(channel + 0x0E, (value - 0x40) & 0xFF)
                harness.poke(channel + 0x0F, args.poke_range)
                status = harness.read(channel, 1)
                harness.poke(channel, (status[0] | 0x04) & 0xFF)
                record["poked"] = {
                    "channel": f"0x{channel:08X}",
                    "bend_value": value,
                    "bend_stored": (value - 0x40) & 0xFF,
                    "bend_range": args.poke_range,
                }
                print("   poked: " + json.dumps(record["poked"]))
            harness.send("next")
            harness.rearm()
    finally:
        harness.close()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
