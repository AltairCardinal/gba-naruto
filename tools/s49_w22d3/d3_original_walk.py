#!/usr/bin/env python3
"""W22-D3: walk the **original** ROM past the point where the remake's
"CANNOT SELECT" banner appears, to see whether the original needs a direction
key before its A button accepts a target.

The original game publishes no telemetry, so this tool records only what can
be seen: a screenshot and its sha256 after every key press.  The phase is then
read off the picture by eye (the screenshots are in the receipt's directory).

The cadence is the one the recorded original walk used
(``tools/s49_rule_probe/capture_original.py``): 90 idle frames, then "A held
for 4 frames, then 90 idle frames" per round.

Usage::

    python tools/s49_w22d3/d3_original_walk.py \\
        --rom   D:/Shell/Github/gba-naruto-butano/rom/base.gba \\
        --exe   build/mgba-probe-w22d3/mgba-probe.exe \\
        --state build/s49-package-w20/work/s49-report/capture-original/step-24-A.ss9 \\
        --out   build/w22-d3/original-walk \\
        --keys  A,A,A,A,A,A,A,A,A,A
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

import w1_probe as probe_module  # noqa: E402

KEYS = probe_module.KEYS

HOLD_FRAMES = 4
SETTLE_FRAMES = 90


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, required=True)
    parser.add_argument("--state", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--keys", default="A,A,A,A,A,A,A,A,A,A")
    parser.add_argument("--idle", type=int, default=0,
                        help="after the key sequence, take this many "
                             "screenshots with NO key pressed")
    parser.add_argument("--hold", type=int, default=HOLD_FRAMES)
    parser.add_argument("--settle", type=int, default=SETTLE_FRAMES)
    parser.add_argument("--label", default="original")
    args = parser.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    keys = [part.strip() for part in args.keys.split(",") if part.strip()]

    probe = probe_module.Probe(args.rom, exe=args.exe)
    steps: list[dict[str, object]] = []
    frames = 0
    try:
        probe.start()
        probe.load(args.state)
        probe.run(f"frames {args.settle} 0x00000000")
        frames += args.settle
        shot = out / "00-baseline.png"
        probe.run(f"shot {shot}")
        steps.append({"index": 0, "key": None, "shot": str(shot),
                      "sha256": sha256_file(shot), "frames": frames})
        print(f"[0] baseline sha={steps[-1]['sha256'][:12]}")

        for index, key in enumerate(keys, start=1):
            if key not in KEYS:
                raise KeyError(key)
            probe.run(f"frames {args.hold} 0x{KEYS[key]:08X}")
            probe.run(f"frames {args.settle} 0x00000000")
            frames += args.hold + args.settle
            shot = out / f"{index:02d}-{key}.png"
            probe.run(f"shot {shot}")
            digest = sha256_file(shot)
            state = out / f"{index:02d}-{key}.ss9"
            probe.run(f"save {state}")
            steps.append({"index": index, "key": key, "shot": str(shot),
                          "sha256": digest, "frames": frames,
                          "state": str(state),
                          "state_sha256": sha256_file(state)})
            print(f"[{index}] {key:6s} sha={digest[:12]} state={state.name}")

        for offset in range(args.idle):
            probe.run(f"frames {args.settle} 0x00000000")
            frames += args.settle
            shot = out / f"idle-{offset + 1:02d}.png"
            probe.run(f"shot {shot}")
            digest = sha256_file(shot)
            steps.append({"index": f"idle-{offset + 1}", "key": None,
                          "shot": str(shot), "sha256": digest,
                          "frames": frames})
            print(f"[idle {offset + 1}] sha={digest[:12]}")
    finally:
        probe.close()

    document = {
        "schema": "konoha.s49-d3-original-walk.v1",
        "generated_by": "tools/s49_w22d3/d3_original_walk.py",
        "label": args.label,
        "rom": {"path": str(args.rom), "sha256": sha256_file(args.rom)},
        "exe": {"path": str(args.exe), "sha256": sha256_file(args.exe)},
        "state": {"path": str(args.state),
                  "sha256": sha256_file(args.state)},
        "key_sequence": keys,
        "hold_frames": args.hold,
        "settle_frames": args.settle,
        "frames_run": frames,
        "steps": steps,
    }
    receipt = out / "receipt.json"
    receipt.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    print(f"wrote {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
