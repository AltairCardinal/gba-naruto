"""Record the semantic walk on both sides.

    python tools/s49_pairing/record.py --side original \
        --out build/s49-pairing/walk/dense-original
    python tools/s49_pairing/record.py --side remake \
        --out build/s49-pairing/walk/dense-remake

The recording writes, for every captured frame, the PNG **and** the savestate
that produced it, so the content anchor can be read back without re-running
the walk.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_pairing import walkspec  # noqa: E402

LUA = REPO / "tools" / "s49_pairing" / "lua" / "record_walk.lua"
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"
PROBE_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def record(spec: walkspec.WalkSpec, out_dir: pathlib.Path,
           stride: int = walkspec.CAPTURE_STRIDE,
           exe: pathlib.Path = PROBE_EXE) -> dict:
    """Record one side of the walk; returns the receipt."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    done_marker = out_dir / "done.json"

    env = dict(os.environ)
    env.update({
        "X2_OUTPUT_DIR": str(out_dir),
        "X2_DONE_MARKER": str(done_marker),
        "X2_KEY_SEQUENCE": ",".join(spec.sequence()),
        "X2_ZERO_INPUT_FRAMES": str(spec.zero_input_frames),
        "X2_SETTLE_FRAMES": str(spec.settle_frames),
        "X2_HOLD_FRAMES": str(spec.hold_frames),
        "X2_CAPTURE_STRIDE": str(stride),
        "X2_CAPTURE_BASE": "1",
    })
    if spec.input_state:
        env["X2_INPUT_STATE"] = spec.input_state
    else:
        env.pop("X2_INPUT_STATE", None)

    attempts = []
    for attempt, budget in enumerate((spec.frames_budget,
                                      spec.frames_budget * 3), start=1):
        if done_marker.exists():
            done_marker.unlink()
        for stale in out_dir.glob("step-*.png"):
            stale.unlink()
        for stale in out_dir.glob("step-*.ss9"):
            stale.unlink()
        command = [sys.executable, str(PROBE_CLIENT), "--rom", spec.rom,
                   "--exe", str(exe),
                   "--cmd", f"script {LUA}",
                   "--cmd", f"frames {budget} 0x000",
                   "--out", str(out_dir / "probe.json")]
        proc = subprocess.run(command, env=env, cwd=str(REPO),
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        attempts.append({"attempt": attempt, "frames_budget": budget,
                         "exit_code": proc.returncode,
                         "stderr_tail": (proc.stderr or "").splitlines()[-6:]})
        if proc.returncode == 0 and done_marker.exists():
            break
    else:
        raise SystemExit(f"ERR the {spec.side} walk did not complete")

    frames = sorted(out_dir.glob("step-*.png"))
    states = sorted(out_dir.glob("step-*.ss9"))
    receipt = {
        "side": spec.side,
        "rom": spec.rom,
        "input_state": spec.input_state,
        "zero_input_frames": spec.zero_input_frames,
        "hold_frames": spec.hold_frames,
        "settle_frames": spec.settle_frames,
        "capture_stride": stride,
        "prefix": list(spec.prefix),
        "beats": spec.beats,
        "frames": len(frames),
        "states": len(states),
        "output_dir": str(out_dir),
        "attempts": attempts,
    }
    write_text(out_dir / "receipt.json",
               json.dumps(receipt, ensure_ascii=False, indent=1) + "\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side", choices=("original", "remake", "both"),
                    default="both")
    ap.add_argument("--out", type=pathlib.Path, default=None,
                    help="output root (default build/s49-pairing/walk)")
    ap.add_argument("--stride", type=int, default=walkspec.CAPTURE_STRIDE)
    ap.add_argument("--beats", type=int, default=walkspec.BEATS)
    ap.add_argument("--exe", type=pathlib.Path, default=PROBE_EXE)
    args = ap.parse_args(argv)

    root = args.out or (REPO / "build" / "s49-pairing" / "walk")
    for side, spec in walkspec.specs(args.beats).items():
        if args.side not in (side, "both"):
            continue
        print(f"recording the {side} walk ({spec.beats} beats, "
              f"stride {args.stride})...")
        receipt = record(spec, root / f"dense-{side}", stride=args.stride,
                         exe=args.exe)
        print(f"  {receipt['frames']} frames, {receipt['states']} savestates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
