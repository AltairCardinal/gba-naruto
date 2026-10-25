#!/usr/bin/env python3
"""W5 -- run the title-card watch on both sides and locate the transition.

The lua script ``w5_titlecard_watch.lua`` loads a captured savestate, presses
nothing and screenshots every N frames.  This driver runs it for the original
and for the remake, then prices every consecutive pair of screenshots so the
frame at which the title card gives way to the battle transition can be read
off a number instead of an eye.

Usage
-----
    python tools/s49_w5/w5_titlecard_watch.py \
        --original-rom D:/Shell/GBA-naruto-butano/rom/base.gba \
        --remake-rom   build/s49-package-u3-final/work/pinned-rom/measured.gba \
        --original-capture build/s49-package-u3-final/work/s49-report/capture-original \
        --remake-capture   build/s49-package-u3-final/work/s49-report/capture-remake \
        --exe build/s49-wave18/w5/probe/mgba-probe.exe \
        --out build/s49-wave18/w5
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
LUA = HERE / "w5_titlecard_watch.lua"
CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"

FIELD_AREA = (0, 0, 240, 128)


def run_side(name: str, rom: str, state: str, outdir: pathlib.Path, exe: str,
             frames: int, every: int, press: str) -> pathlib.Path:
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "W5_STATE": str(state),
        "W5_OUTDIR": str(outdir).replace("\\", "/"),
        "W5_FRAMES": str(frames),
        "W5_EVERY": str(every),
        "W5_PRESS": press,
    })
    command = [
        sys.executable, str(CLIENT), "--rom", rom, "--exe", exe,
        "--cmd", f"script {LUA}",
        "--cmd", f"frames {frames + 10} 0x000",
        "--timeout", "300",
    ]
    print(f"--- {name}: {state}")
    result = subprocess.run(command, env=env, cwd=str(REPO), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    print(result.stdout[-2000:])
    if result.returncode != 0:
        print("STDERR:", result.stderr[-2000:])
    return outdir


def price(outdir: pathlib.Path) -> list[dict]:
    shots = sorted(outdir.glob("f*.png"))
    rows = []
    previous = None
    previous_name = None
    for shot in shots:
        image = load_rgb(shot)
        if previous is not None:
            count, _ = diff_mask(previous, image, FIELD_AREA)
            rows.append({"from": previous_name, "to": shot.name, "field_px": count})
        previous = image
        previous_name = shot.name
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-rom", required=True)
    parser.add_argument("--remake-rom", required=True)
    parser.add_argument("--original-capture", required=True)
    parser.add_argument("--remake-capture", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--every", type=int, default=10)
    parser.add_argument("--press", default="none")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sides = {
        "original": (
            args.original_rom,
            pathlib.Path(args.original_capture) / "step-09-A.ss9",
            out / "watch-original",
        ),
        "remake": (
            args.remake_rom,
            pathlib.Path(args.remake_capture) / "step-13-A.ss9",
            out / "watch-remake",
        ),
    }

    report = {}
    for name, (rom, state, outdir) in sides.items():
        if not state.exists():
            print("MISSING", state)
            continue
        run_side(name, rom, str(state), outdir, args.exe, args.frames,
                 args.every, args.press)
        rows = price(outdir)
        print(f"\n=== {name}: consecutive screenshot residuals (field 240x128) ===")
        for row in rows:
            print("  {:>10} -> {:<10} {:>7}".format(
                row["from"], row["to"], row["field_px"]))
        report[name] = {"state": str(state), "outdir": str(outdir), "rows": rows}

    path = out / "titlecard-watch.json"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
    print("\nwrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
