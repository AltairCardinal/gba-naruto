#!/usr/bin/env python3
"""Replay a key route from a savestate and record what the game did.

This is the workhorse of stream K.  It reproduces the timing contract of the
remake line's ``mgba_original_s49_ui_boundaries.lua``:

* a key is *held* for ``--hold`` frames and then released for ``--release``
  frames (the game needs the release edge -- holding a button down does
  nothing),
* then the segment's settle time passes before the screenshot is taken and the
  next key is pressed.

Two input modes:

* ``--keys "A,Down*3,B"`` -- one segment, one settle time.
* ``--route route.json``  -- a list of segments, each with its own settle time
  (the battle mixes 90-frame menu settles with 900-frame animation settles).

Per key it records a PNG screenshot, the live battle roster (HP, acting unit,
positions) and a hash of the raw battle-state memory block.

Usage::

    python tools/s49_victory_capture/shoot.py \
        --state artifacts/.../scenario-49-battle-14-entry.ss9 \
        --out build/s49-victory-capture/run \
        --route tools/s49_victory_capture/routes/round1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

_BUILD = pathlib.Path(__file__).resolve().parents[2] / "build"
# A private copy of the probe avoids the LNK1104 clash with the other streams.
DEFAULT_EXE = (_BUILD / "mgba-probe-k" / "mgba-probe.exe")
if not DEFAULT_EXE.exists():
    DEFAULT_EXE = _BUILD / "mgba-probe" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")

# One blob that holds the unit pool (16 slots x 0x1D4) and the HP array
# (9 x 0x1D4 at +0x1E0) in a single bus read.
STATE_BASE = s49_state.POOL_ADDRESS
STATE_LENGTH = 0x3000


def parse_keys(spec: str) -> list[str]:
    """Parse ``A,Down*3,B`` into ``["A", "Down", "Down", "Down", "B"]``."""
    keys: list[str] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "*" in token:
            name, _, count = token.partition("*")
            keys.extend([name.strip()] * int(count))
        else:
            keys.append(token)
    return keys


def load_route(path: pathlib.Path) -> tuple[list[dict], dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    segments = document.get("segments")
    if not segments:
        raise SystemExit(f"route {path} has no segments")
    for segment in segments:
        segment.setdefault("settle", 90)
        keys = segment.get("keys", [])
        if isinstance(keys, str):
            segment["keys"] = parse_keys(keys)
    return segments, document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", help="starting savestate")
    parser.add_argument("--route", help="route JSON with segments")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--keys", help="key sequence, e.g. 'A,Down*3'")
    parser.add_argument("--settle", type=int, default=90,
                        help="frames to wait after each key before capturing")
    parser.add_argument("--zero", type=int, default=0,
                        help="frames of zero input before the first key")
    parser.add_argument("--hold", type=int, default=4,
                        help="frames a key is held down")
    parser.add_argument("--release", type=int, default=1,
                        help="frames after the release edge")
    parser.add_argument("--start-index", type=int, default=0,
                        help="index of the first captured step")
    parser.add_argument("--label", default="step")
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--no-shot", action="store_true")
    parser.add_argument("--no-state", action="store_true")
    parser.add_argument("--settle-only", action="store_true",
                        help="do not press any key, just settle and capture")
    args = parser.parse_args(argv)

    if args.route:
        segments, document = load_route(pathlib.Path(args.route))
        start_state = args.state or document.get("start_state")
    else:
        segments = [{"label": args.label, "keys": parse_keys(args.keys or ""),
                     "settle": args.settle}]
        start_state = args.state
    if not start_state:
        raise SystemExit("--state is required (or the route must carry start_state)")
    start_state = pathlib.Path(start_state)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    steps: list[dict] = []
    frame_index = args.start_index
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(start_state)

        def capture(name: str, index: int, key: str | None,
                    segment: str) -> dict:
            row: dict = {"index": index, "key": key, "name": name,
                         "segment": segment}
            memory = probe.dump(STATE_BASE, STATE_LENGTH)
            row["roster"] = s49_state.summarize_memory(memory, STATE_BASE)
            row["battle_state_sha256"] = hashlib.sha256(memory).hexdigest()
            if not args.no_shot:
                png = out_dir / f"{name}.png"
                probe.shot(png)
                row["png"] = str(png)
                row["png_sha256"] = s49_state.file_sha256(png)
            if not args.no_state:
                ss9 = out_dir / f"{name}.ss9"
                probe.save(ss9)
                row["state"] = str(ss9)
                row["state_file_sha256"] = s49_state.file_sha256(ss9)
            return row

        if args.zero:
            probe.frames(args.zero, 0)
            steps.append(capture(f"{args.label}-base", -1, None, "zero"))
        for segment in segments:
            label = segment.get("label", "seg")
            settle = int(segment.get("settle", args.settle))
            if segment.get("zero"):
                probe.frames(int(segment["zero"]), 0)
                steps.append(capture(f"{label}-base", -1, None, label))
            for key in segment.get("keys", []):
                mask = probe_module.key_mask([key])
                probe.frames(args.hold, mask)
                probe.frames(args.release, 0)
                probe.frames(settle, 0)
                steps.append(capture(
                    f"{label}-{frame_index:04d}-{key}", frame_index, key, label))
                frame_index += 1

    receipt = {
        "schema": "konoha.s49-victory-capture.steps.v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "rom": str(args.rom),
        "start_state": str(start_state),
        "start_state_sha256": s49_state.file_sha256(start_state),
        "hold_frames": args.hold,
        "release_frames": args.release,
        "segments": [{"label": s.get("label"), "settle": s.get("settle"),
                      "keys": s.get("keys")} for s in segments],
        "steps": steps,
    }
    (out_dir / "steps.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    last = steps[-1]["roster"] if steps else {}
    print(json.dumps({
        "steps": len(steps),
        "acting": last.get("acting"),
        "hp": last.get("hp"),
        "bees_alive": last.get("bees_alive"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
