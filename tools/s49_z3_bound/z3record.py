"""Record the dense semantic walk of the **current** ROM (pinned, line-safe).

    python tools/s49_z3_bound/z3record.py --side remake \
        --out build/s49-z3-bound/walk

Why this exists instead of ``tools/s49_pairing/record.py``
---------------------------------------------------------
The pairing stream's recorder drives the probe with
``tools/mgba_probe/probe_client.py``, whose ``read_line`` spawns **one reader
thread per line** and joins it.  A long ``frames`` command followed by more
commands can lose the sentinel and stall the whole run.  The wave-11 client
``tools/s49_battle_balance/w1_probe.py`` uses **one** background reader thread
that pushes every line into a queue, so nothing is lost and nothing is read
out of order.  This recorder uses that client (read-only import).

It also **pins the ROM**: the remake ROM is rebuilt by parallel streams, so
the recording runs against a byte copy whose sha256 is written into the
receipt.  A measurement that cannot name its ROM is not a measurement.

Everything else -- the walk script, the beat script, the frame layout -- is
reused **read-only** from ``tools/s49_pairing``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

from s49_battle_balance import w1_probe  # noqa: E402
from s49_pairing import walkspec  # noqa: E402

LUA = REPO / "tools" / "s49_pairing" / "lua" / "record_walk.lua"
DEFAULT_EXE = REPO / "build" / "mgba-probe-z3" / "mgba-probe.exe"

# The probe's own timeout for one command.  A 4000 frame run of the remake ROM
# plus 783 savestate writes is minutes, not seconds.
PROBE_TIMEOUT = 3600.0


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def frames_digest(directory: pathlib.Path) -> str:
    """The sha256 of every captured PNG, in name order (a run's fingerprint)."""
    digest = hashlib.sha256()
    for path in sorted(directory.glob("step-*.png")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def pin_rom(source: pathlib.Path, pinned: pathlib.Path) -> dict:
    """Copy the ROM to a pinned byte copy and record both digests."""
    pinned.parent.mkdir(parents=True, exist_ok=True)
    source_sha = sha256_file(source)
    if not pinned.exists() or sha256_file(pinned) != source_sha:
        shutil.copyfile(source, pinned)
    pinned_sha = sha256_file(pinned)
    if pinned_sha != source_sha:
        raise SystemExit(f"ERR the pinned ROM differs from {source}")
    return {"source": str(source), "source_sha256": source_sha,
            "pinned": str(pinned), "pinned_sha256": pinned_sha}


def record(spec: walkspec.WalkSpec, out_dir: pathlib.Path,
           rom_path: pathlib.Path, exe: pathlib.Path,
           stride: int = walkspec.CAPTURE_STRIDE) -> dict:
    """Record one side of the walk; returns the receipt."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    done_marker = out_dir / "done.json"

    # The walk script reads its parameters with ``os.getenv`` **inside the
    # probe process**, so they have to be exported into this process's
    # environment (the probe inherits it) -- not merely into a dict that is
    # handed to a client.
    env = {
        "X2_OUTPUT_DIR": str(out_dir),
        "X2_DONE_MARKER": str(done_marker),
        "X2_KEY_SEQUENCE": ",".join(spec.sequence()),
        "X2_ZERO_INPUT_FRAMES": str(spec.zero_input_frames),
        "X2_SETTLE_FRAMES": str(spec.settle_frames),
        "X2_HOLD_FRAMES": str(spec.hold_frames),
        "X2_CAPTURE_STRIDE": str(stride),
        "X2_CAPTURE_BASE": "1",
    }
    os.environ.update(env)
    if spec.input_state:
        os.environ["X2_INPUT_STATE"] = spec.input_state
    else:
        os.environ.pop("X2_INPUT_STATE", None)

    started = time.time()
    probe = w1_probe.Probe(rom=rom_path, exe=exe, timeout=PROBE_TIMEOUT)
    probe.start()
    try:
        probe.run(f"script {LUA}")
        probe.run(f"frames {spec.frames_budget} 0x000")
    finally:
        probe.close()
    elapsed = time.time() - started

    if not done_marker.exists():
        raise SystemExit(f"ERR the {spec.side} walk did not complete")
    frames = sorted(out_dir.glob("step-*.png"))
    states = sorted(out_dir.glob("step-*.ss9"))
    receipt = {
        "side": spec.side,
        "rom": str(rom_path),
        "rom_sha256": sha256_file(rom_path),
        "probe_exe": str(exe),
        "probe_exe_sha256": sha256_file(exe) if exe.exists() else None,
        "input_state": spec.input_state,
        "zero_input_frames": spec.zero_input_frames,
        "hold_frames": spec.hold_frames,
        "settle_frames": spec.settle_frames,
        "capture_stride": stride,
        "prefix": list(spec.prefix),
        "beats": spec.beats,
        "frames": len(frames),
        "states": len(states),
        "frames_sha256": frames_digest(out_dir),
        "output_dir": str(out_dir),
        "elapsed_seconds": round(elapsed, 1),
    }
    write_text(out_dir / "receipt.json",
               json.dumps(receipt, ensure_ascii=False, indent=1) + "\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--side", choices=("original", "remake", "both"),
                        default="both")
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-z3-bound" / "walk")
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--remake-rom", type=pathlib.Path,
                        default=pathlib.Path(walkspec.REMAKE_ROM))
    parser.add_argument("--original-rom", type=pathlib.Path,
                        default=pathlib.Path(walkspec.ORIGINAL_ROM))
    parser.add_argument("--stride", type=int, default=walkspec.CAPTURE_STRIDE)
    parser.add_argument("--beats", type=int, default=walkspec.BEATS)
    args = parser.parse_args(argv)

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: "
              "$env:KONOHA_PROBE_OUT='build/mgba-probe-z3'; "
              "python tools/mgba_probe/build.py")
        return 2

    pinned_dir = args.out / "pinned"
    args.out.mkdir(parents=True, exist_ok=True)
    pinned = {
        "remake": pin_rom(args.remake_rom, pinned_dir / "remake.gba"),
        "original": pin_rom(args.original_rom, pinned_dir / "original.gba"),
    }

    specs = walkspec.specs(args.beats)
    for side in ("original", "remake"):
        if args.side not in (side, "both"):
            continue
        spec = specs[side]
        rom_path = pathlib.Path(pinned[side]["pinned"])
        print(f"recording the {side} walk on ROM {pinned[side]['pinned_sha256'][:16]}… "
              f"({spec.beats} beats, stride {args.stride})...")
        receipt = record(spec, args.out / f"dense-{side}", rom_path, args.exe,
                         stride=args.stride)
        print(f"  {receipt['frames']} frames, {receipt['states']} savestates, "
              f"{receipt['elapsed_seconds']}s, "
              f"frames_sha256 {receipt['frames_sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
