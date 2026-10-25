#!/usr/bin/env python3
"""Capture the original game's own state at the four overlay moments.

The original game's BG2 overlay content (the "ground truth" exported by the
Butano line) is reproducible on this machine: replaying the recorded A-walk
from ``scenario-49-battle-14-entry.ss9`` reproduces all four moments
byte-for-byte in BG2's tilemap.  This script

1. replays that walk with the probe, and saves a savestate at the exact frame
   where each moment's tilemap is byte-identical to the exported ground
   truth, and
2. from each saved state, dumps EWRAM / VRAM / I/O so the overlay can be
   correlated with the original's own game state.

Moments are located **by content** (sha256 of the 2048 byte BG2 tilemap),
never by frame number: the local simulator's animation phase differs from
the machine the receipts were captured on.

Usage::

    python tools/s49_rule_probe/capture_original.py --out build/s49-rule/capture
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"

GT_DIR = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
)
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9"
)
DEFAULT_EXE = REPO / "build" / "mgba-probe-f" / "mgba-probe.exe"

MOMENTS = ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1", "banner-frame-v1")

# The recorded walk: 90 idle frames, then 24 rounds of "A held for 4 frames,
# then 90 idle frames".  Mirrors tools/butano/mgba_original_s49_ui_boundaries.lua
# with ZERO_INPUT_FRAMES=90, HOLD_FRAMES=4, SETTLE_FRAMES=90.
IDLE_FRAMES = 90
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
ROUNDS = 24
KEY_A = 0x001

BG2_TILEMAP_ADDR = 0x06001000
BG2_TILEMAP_LEN = 2048
VRAM_ADDR = 0x06000000
VRAM_LEN = 0x18000
EWRAM_ADDR = 0x02000000
EWRAM_LEN = 0x40000
IO_ADDR = 0x04000000
IO_LEN = 0x400


def moment_tilemap(name: str) -> bytes:
    data = json.loads(
        (GT_DIR / f"{name}.bg2-tilemap.json").read_text(encoding="utf-8"))
    cells = data["cells"]
    if len(cells) != 1024:
        raise RuntimeError(f"{name}: expected 1024 cells, got {len(cells)}")
    return b"".join(int(c["raw_hex"], 16).to_bytes(2, "little") for c in cells)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def segments() -> list[tuple[int, int]]:
    """The (mask, frames) segments of the recorded walk."""
    out: list[tuple[int, int]] = [(0x000, IDLE_FRAMES)]
    for _ in range(ROUNDS):
        out.append((KEY_A, HOLD_FRAMES))
        out.append((0x000, SETTLE_FRAMES))
    return out


def build_commands(saves: dict[int, str]) -> list[str]:
    """Probe commands that stop at each requested global frame and save."""
    commands: list[str] = []
    frame = 0
    pending = dict(saves)
    for mask, count in segments():
        while count > 0:
            # find the next save point inside this segment
            target = None
            for candidate in sorted(pending):
                if frame < candidate <= frame + count:
                    target = candidate
                    break
            take = (target - frame) if target is not None else count
            commands.append(f"frames {take} 0x{mask:03X}")
            frame += take
            count -= take
            if target is not None:
                commands.append(f"save {pending[target]}")
                del pending[target]
    if pending:
        raise RuntimeError(f"save points beyond the walk: {pending}")
    return commands


def run_probe(exe: pathlib.Path, rom: pathlib.Path, commands: list[str],
              out: pathlib.Path, timeout: float = 900.0) -> dict:
    argv = [sys.executable, str(PROBE_CLIENT), "--exe", str(exe), "--rom", str(rom)]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", str(out)]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"probe failed: {proc.stderr[:2000]}")
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    ap.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    ap.add_argument("--out", type=pathlib.Path,
                    default=REPO / "build" / "s49-rule" / "capture")
    ap.add_argument("--skip-walk", action="store_true",
                    help="reuse the frame->moment map in --frames-json")
    ap.add_argument("--frames-json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. find the global frame of each moment by content --------------
    if args.frames_json and args.frames_json.is_file():
        mapping = json.loads(args.frames_json.read_text(encoding="utf-8"))
        moment_frame = {k: int(v) for k, v in mapping.items()}
    else:
        walk_dir = out_dir / "walk"
        walk_dir.mkdir(parents=True, exist_ok=True)
        commands = [
            f"load {args.state}",
            f"framedump {IDLE_FRAMES} 0x{BG2_TILEMAP_ADDR:08X} {BG2_TILEMAP_LEN} "
            f"0x000 {walk_dir / 'pre'}",
            f"keyseq {HOLD_FRAMES} {SETTLE_FRAMES} {ROUNDS} "
            f"0x{BG2_TILEMAP_ADDR:08X} {BG2_TILEMAP_LEN} 0x{KEY_A:03X} "
            f"{walk_dir / 'a'}",
        ]
        print("running the recorded A-walk, dumping BG2's tilemap every frame ...")
        document = run_probe(args.exe, args.rom, commands, out_dir / "walk-vram.json")
        for step in document["steps"]:
            if step["status"] != "ok":
                raise RuntimeError(f"probe step failed: {step}")

        targets = {name: sha256(moment_tilemap(name)) for name in MOMENTS}
        by_hash: dict[str, list[int]] = {}
        for path in sorted(walk_dir.glob("*.bin")):
            index = int(path.stem.rsplit("-", 1)[1])
            by_hash.setdefault(sha256(path.read_bytes()), []).append(index)
        # global frame = IDLE_FRAMES + (a-index + 1)
        moment_frame = {}
        for name, digest in targets.items():
            hits = by_hash.get(digest)
            if not hits:
                raise RuntimeError(f"{name}: no frame reproduces its tilemap")
            a_index = hits[0]
            moment_frame[name] = IDLE_FRAMES + a_index + 1
            print(f"  {name}: {len(hits)} frame(s), first a-{a_index:04d} "
                  f"= global frame {moment_frame[name]}")
        (out_dir / "moment-frames.json").write_text(
            json.dumps(moment_frame, indent=1) + "\n", encoding="utf-8", newline="\n")

    # ---- 2. replay to each moment and save a savestate -------------------
    saves = {frame: str(out_dir / f"{name}.ss9")
             for name, frame in moment_frame.items()}
    commands = [f"load {args.state}"] + build_commands(saves)
    print("replaying to each moment and saving savestates ...")
    document = run_probe(args.exe, args.rom, commands, out_dir / "states.json")
    for step in document["steps"]:
        if step["status"] != "ok":
            raise RuntimeError(f"probe step failed: {step['command']}: {step['output']}")

    # ---- 3. from each saved state, dump the state regions ----------------
    for name in MOMENTS:
        state_path = out_dir / f"{name}.ss9"
        if not state_path.is_file():
            print(f"  !! {name}: no savestate")
            continue
        commands = [
            f"load {state_path}",
            f"framedump 1 0x{EWRAM_ADDR:08X} {EWRAM_LEN} 0x000 {out_dir / (name + '.ewram')}",
            f"framedump 1 0x{VRAM_ADDR:08X} {VRAM_LEN} 0x000 {out_dir / (name + '.vram')}",
            f"framedump 1 0x{IO_ADDR:08X} {IO_LEN} 0x000 {out_dir / (name + '.io')}",
        ]
        document = run_probe(args.exe, args.rom, commands, out_dir / f"{name}-dump.json")
        bad = [s for s in document["steps"] if s["status"] != "ok"]
        if bad:
            raise RuntimeError(f"{name}: dump step failed: {bad[0]['output']}")
        print(f"  {name}: state dumped")

    print("done ->", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
