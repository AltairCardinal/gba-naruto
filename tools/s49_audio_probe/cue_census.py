#!/usr/bin/env python3
"""Census of the MP2K cues that are live in each recorded savestate.

For every savestate the tool loads it into the headless mGBA probe, advances a
single frame and reads the four MP2K player blocks.  Each player's song
descriptor pointer is mapped back to a MP2K sound ID through the ROM
dispatcher table, so the result answers "which cue is the original playing at
this moment".

Usage:
    python tools/s49_audio_probe/cue_census.py \
        --state-glob "D:/Shell/Github/gba-naruto-butano/artifacts/runtime-checkpoints/scenario-4*.ss9" \
        --out build/s49-audio/cue_census.json
"""
from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mp2k_layout as L  # noqa: E402
from probe_driver import Probe, sha256_file, write_json  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_ROM = REPO / "rom" / "base.gba"
DEFAULT_CHECKPOINTS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints")


def parse_dump_hex(lines: list[str], length: int) -> bytes:
    """Parse the probe's `dump` output back into bytes."""
    data = bytearray()
    for line in lines:
        if line.startswith("DUMP ") or line == "ENDDUMP":
            continue
        text = line.replace(" ", "")
        for index in range(0, len(text) - 1, 2):
            data.append(int(text[index:index + 2], 16))
    return bytes(data[:length])


def census(rom: pathlib.Path, states: list[pathlib.Path]) -> list[dict]:
    table = L.build_sound_table(L.load_rom(rom))
    descriptor_index = L.build_descriptor_index(table)
    results = []
    with Probe(rom) as probe:
        for state in states:
            probe.run(f"load {state}")
            probe.run("frames 1 0x000")
            output = probe.run(f"dump 0x{L.CAPTURE_BASE:08X} {L.CAPTURE_LENGTH}")
            window = parse_dump_hex(output, L.CAPTURE_LENGTH)
            players = []
            for slot in sorted(L.PLAYER_STATE):
                decoded = L.decode_player_state(window, slot, descriptor_index)
                players.append({
                    "slot": decoded["slot"],
                    "sound_id": decoded["sound_id"],
                    "descriptor": f"0x{decoded['descriptor']:08X}",
                    "track_status": decoded["track_status"],
                    "tracks_running": decoded["tracks_running"],
                })
            results.append({
                "state": state.name,
                "state_path": str(state),
                "state_sha256": sha256_file(state),
                "slots": players,
                "live_cues": sorted({
                    p["sound_id"] for p in players
                    if p["sound_id"] is not None and p["tracks_running"] > 0}),
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--checkpoints", default=str(DEFAULT_CHECKPOINTS))
    parser.add_argument("--include", default="scenario-41-,scenario-49-",
                        help="comma separated name prefixes to include")
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio"
                                             / "cue_census.json"))
    args = parser.parse_args()

    rom = pathlib.Path(args.rom)
    root = pathlib.Path(args.checkpoints)
    prefixes = [item for item in args.include.split(",") if item]
    states = sorted(
        path for path in root.glob("*.ss9")
        if any(path.name.startswith(prefix) for prefix in prefixes))
    if not states:
        raise SystemExit(f"ERR no checkpoints matched under {root}")
    print(f"censusing {len(states)} checkpoints ...")
    rows = census(rom, states)
    for row in rows:
        live = ",".join(str(cue) for cue in row["live_cues"]) or "-"
        print(f"  {row['state']:<52} live cues: {live}")
    write_json(pathlib.Path(args.out), {
        "rom_sha256": sha256_file(rom),
        "checkpoint_count": len(rows),
        "checkpoints": rows,
    })
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
