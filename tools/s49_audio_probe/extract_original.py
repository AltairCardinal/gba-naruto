#!/usr/bin/env python3
"""Stream J / original side: export the MP2K audio-event sequence of the
S49 "Konoha Maru vs Bee" battle (scenario-49 battle-14).

Method
------
The original ROM is driven by the headless mGBA probe from the recorded
battle-14 entry savestate, with the recorded walk (24 x A, hold 4 frames,
90-frame settle).  Two independent instruments are captured, frame by frame:

  A) MP2K runtime state -- IWRAM 0x03005E58 .. 0x030077CF (0x1978 bytes):
     the four track arrays, SoundInfo, the DirectSound / CGB channel pools and
     the four MP2K player blocks.  `player+0x00` is the song descriptor
     pointer, which the ROM dispatcher table maps back to a sound ID.

  B) PSG / DMA I/O block -- 0x04000060 .. 0x040000DF (0x80 bytes): the four
     PSG channels, SOUNDCNT_L/H/X, SOUNDBIAS, the two FIFO ports and the three
     DMA channels.  This is the "is anything audible right now" instrument.

Reading the I/O block can perturb a simulation, so the MP2K capture (A) and
the I/O capture (B) are two separate probe runs, and a third run (C) re-captures
the MP2K window *after* an I/O-window run of the first half of the walk.  If
A and C agree byte for byte on the shared frames, the I/O read did not perturb
the emulation and the two timelines can be merged.

Usage
-----
    python tools/s49_audio_probe/extract_original.py --out build/s49-audio
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mp2k_layout as L  # noqa: E402
from probe_driver import (  # noqa: E402
    KEY_A, Probe, framedump_command, keyseq_command, read_dump_series,
    sha256_file, write_json,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

DEFAULT_ROM = REPO / "rom" / "base.gba"
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")

# Recorded walk (artifacts/s49-fidelity-20261019-v1/walk-original-a24).
WALK_ROUNDS = 24
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
ZERO_INPUT_FRAMES = 90
TAIL_FRAMES = 300


def capture_original(out_dir: pathlib.Path, rom: pathlib.Path,
                     state: pathlib.Path, *, repeat: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    mp2k_dir = out_dir / "orig-mp2k"
    psg_dir = out_dir / "orig-psg"
    mp2k_dir.mkdir(parents=True, exist_ok=True)
    psg_dir.mkdir(parents=True, exist_ok=True)

    walk_frames = WALK_ROUNDS * (HOLD_FRAMES + SETTLE_FRAMES)
    half = WALK_ROUNDS // 2

    # ── session A: MP2K window over the whole walk + tail ──────────────────
    with Probe(rom, cwd=mp2k_dir) as probe:
        probe.run(f"load {state}")
        probe.run(f"frames {ZERO_INPUT_FRAMES} 0x000")
        probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, WALK_ROUNDS,
                                  L.CAPTURE_BASE, L.CAPTURE_LENGTH,
                                  KEY_A, "m"))
        probe.run(framedump_command(TAIL_FRAMES, L.CAPTURE_BASE,
                                    L.CAPTURE_LENGTH, 0x000, "t"))
    mp2k = read_dump_series(mp2k_dir, "m") + read_dump_series(mp2k_dir, "t")

    # ── session A2: same again (determinism control) ───────────────────────
    mp2k_repeat: list[bytes] = []
    if repeat:
        rep_dir = out_dir / "orig-mp2k-repeat"
        rep_dir.mkdir(parents=True, exist_ok=True)
        with Probe(rom, cwd=rep_dir) as probe:
            probe.run(f"load {state}")
            probe.run(f"frames {ZERO_INPUT_FRAMES} 0x000")
            probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, WALK_ROUNDS,
                                      L.CAPTURE_BASE, L.CAPTURE_LENGTH,
                                      KEY_A, "m"))
            probe.run(framedump_command(TAIL_FRAMES, L.CAPTURE_BASE,
                                        L.CAPTURE_LENGTH, 0x000, "t"))
        mp2k_repeat = (read_dump_series(rep_dir, "m")
                       + read_dump_series(rep_dir, "t"))

    # ── session B: PSG / DMA I/O window over the whole walk + tail ──────────
    with Probe(rom, cwd=psg_dir) as probe:
        probe.run(f"load {state}")
        probe.run(f"frames {ZERO_INPUT_FRAMES} 0x000")
        probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, WALK_ROUNDS,
                                  L.PSG_BASE, L.PSG_LENGTH, KEY_A, "p"))
        probe.run(framedump_command(TAIL_FRAMES, L.PSG_BASE, L.PSG_LENGTH,
                                    0x000, "q"))
    psg = read_dump_series(psg_dir, "p") + read_dump_series(psg_dir, "q")

    # ── session C: I/O window first half, MP2K window second half ───────────
    ctrl_dir = out_dir / "orig-perturb"
    ctrl_dir.mkdir(parents=True, exist_ok=True)
    with Probe(rom, cwd=ctrl_dir) as probe:
        probe.run(f"load {state}")
        probe.run(f"frames {ZERO_INPUT_FRAMES} 0x000")
        probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, half,
                                  L.PSG_BASE, L.PSG_LENGTH, KEY_A, "p"))
        probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, WALK_ROUNDS - half,
                                  L.CAPTURE_BASE, L.CAPTURE_LENGTH,
                                  KEY_A, "m"))
    control_second_half = read_dump_series(ctrl_dir, "m")

    return {
        "mp2k": mp2k,
        "mp2k_repeat": mp2k_repeat,
        "psg": psg,
        "control_second_half": control_second_half,
        "walk_frames": walk_frames,
        "half_frames": half * (HOLD_FRAMES + SETTLE_FRAMES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio"),
                        help="output directory")
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--no-repeat", action="store_true",
                        help="skip the determinism control run")
    parser.add_argument("--decode-only", action="store_true",
                        help="re-decode the dumps already present in --out "
                             "without re-running the emulator")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    rom = pathlib.Path(args.rom)
    state = pathlib.Path(args.state)
    if not rom.is_file():
        raise SystemExit(f"ERR ROM missing: {rom}")
    if not state.is_file():
        raise SystemExit(f"ERR savestate missing: {state}")

    if args.decode_only:
        mp2k_dir = out_dir / "orig-mp2k"
        psg_dir = out_dir / "orig-psg"
        data = {
            "mp2k": read_dump_series(mp2k_dir, "m") + read_dump_series(mp2k_dir, "t"),
            "mp2k_repeat": [],
            "psg": read_dump_series(psg_dir, "p") + read_dump_series(psg_dir, "q"),
            "control_second_half": [],
            "walk_frames": WALK_ROUNDS * (HOLD_FRAMES + SETTLE_FRAMES),
            "half_frames": (WALK_ROUNDS // 2) * (HOLD_FRAMES + SETTLE_FRAMES),
        }
        print(f"decoding existing capture ... mp2k frames: {len(data['mp2k'])}")
    else:
        print(f"capturing original ... rom={rom.name} state={state.name}")
        data = capture_original(out_dir, rom, state, repeat=not args.no_repeat)
        print(f"  mp2k frames : {len(data['mp2k'])}")
        print(f"  psg  frames : {len(data['psg'])}")

    # ── determinism control ─────────────────────────────────────────────────
    determinism = None
    if data["mp2k_repeat"]:
        determinism = data["mp2k"] == data["mp2k_repeat"]
        print(f"  determinism (run twice byte-identical): {determinism}")

    # ── I/O perturbation control ────────────────────────────────────────────
    perturbation = None
    if data["control_second_half"]:
        half = data["half_frames"]
        shared = data["mp2k"][half:half + len(data["control_second_half"])]
        perturbation = shared == data["control_second_half"]
        print(f"  I/O read does not perturb the MP2K timeline: {perturbation}")

    # A decode-only run must produce the same document as a capture run, so
    # carry the control results of the previous capture over instead of
    # blanking them.
    previous_controls = {}
    previous_path = out_dir / "original_events.json"
    if previous_path.is_file():
        try:
            previous_controls = json.loads(
                previous_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous_controls = {}
    if determinism is None:
        determinism = previous_controls.get("determinism_byte_identical")
    if perturbation is None:
        perturbation = previous_controls.get("io_read_does_not_perturb")

    # ── decode ──────────────────────────────────────────────────────────────
    rom_bytes = L.load_rom(rom)
    table = L.build_sound_table(rom_bytes)
    descriptor_index = L.build_descriptor_index(table)
    frames = [L.decode_frame(buf, descriptor_index) for buf in data["mp2k"]]

    events = derive_events(frames, data["walk_frames"])

    write_json(out_dir / "original_frames.json", {
        "frame_count": len(frames),
        "walk_frames": data["walk_frames"],
        "frames": frames,
    })
    write_json(out_dir / "original_events.json", {
        "side": "original",
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "state": str(state),
        "state_sha256": sha256_file(state),
        "walk": {
            "rounds": WALK_ROUNDS, "hold_frames": HOLD_FRAMES,
            "settle_frames": SETTLE_FRAMES,
            "zero_input_frames": ZERO_INPUT_FRAMES,
            "tail_frames": TAIL_FRAMES,
            "key": "A",
        },
        "determinism_byte_identical": determinism,
        "io_read_does_not_perturb": perturbation,
        "event_count": len(events),
        "events": events,
    })
    print(f"  events: {len(events)} -> {out_dir / 'original_events.json'}")
    return 0


def derive_events(frames: list[dict], walk_frames: int) -> list[dict]:
    """Turn the per-frame MP2K player state into a cue event list.

    A cue event is a *dispatch*: the game handed a sound ID to an MP2K player
    slot.  MP2K keeps the song descriptor in the player block even after the
    song ends, so the descriptor alone cannot say "a cue is playing".

    Two fingerprints are used, both verified on this ROM:

      cue_start  -- the slot's song descriptor changed to a different known
                    descriptor, OR the descriptor is unchanged but one of the
                    slot's tracks carries status 0xC0 (MP2K's MPlayStart sets
                    track.status = 0xC0 on the frame it dispatches a track,
                    and 0x80 on every later frame).  The second case is a
                    re-dispatch of the *same* cue, which the descriptor cannot
                    show.
      cue_stop   -- the slot's descriptor is unchanged and no track of that
                    slot is running any more (status & 0x80 == 0).
    """
    events: list[dict] = []
    previous: dict[int, dict] = {}
    for index, frame in enumerate(frames):
        frame_no = index + 1
        phase = "walk" if frame_no <= walk_frames else "tail"
        for player in frame["players"]:
            slot = player["slot"]
            sound_id = player["sound_id"]
            descriptor = player["descriptor"]
            before = previous.get(slot)
            current = {
                "descriptor": descriptor,
                "sound_id": sound_id,
                "dispatched": player["dispatched_this_frame"],
                "running": player["tracks_running"],
            }
            previous[slot] = current
            if before is None:
                continue
            if before["descriptor"] != descriptor:
                events.append({
                    "frame": frame_no,
                    "phase": phase,
                    "slot": slot,
                    "kind": "cue_start",
                    "sound_id": sound_id,
                    "descriptor": f"0x{descriptor:08X}",
                    "previous_sound_id": before["sound_id"],
                    "trigger": "descriptor_change",
                })
            elif current["dispatched"]:
                events.append({
                    "frame": frame_no,
                    "phase": phase,
                    "slot": slot,
                    "kind": "cue_start",
                    "sound_id": sound_id,
                    "descriptor": f"0x{descriptor:08X}",
                    "previous_sound_id": before["sound_id"],
                    "trigger": "status_0xC0",
                })
            elif before["running"] > 0 and current["running"] == 0:
                events.append({
                    "frame": frame_no,
                    "phase": phase,
                    "slot": slot,
                    "kind": "cue_stop",
                    "sound_id": sound_id,
                    "descriptor": f"0x{descriptor:08X}",
                    "previous_sound_id": before["sound_id"],
                })
    return events


if __name__ == "__main__":
    raise SystemExit(main())
