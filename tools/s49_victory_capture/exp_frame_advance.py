#!/usr/bin/env python3
"""Experiment: does a *sequence* of probe commands advance the frame?

Experiment W3-E1 showed that a single ``dump`` between two ``rawshot``
calls does not advance the frame.  The driver's observation does ~20 reads
per frame, and the driver saw the screen change between two observations
that were separated only by reads.  This experiment measures the frame count
that the driver actually uses.

Usage::

    python tools/s49_victory_capture/exp_frame_advance.py \
        --out build/s49-victory-capture/exp-frame-advance
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import probe as probe_module  # noqa: E402

DEFAULT_EXE = pathlib.Path(__file__).resolve().parents[2] / "build" / "mgba-probe-w3" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")

ADDR_POOL = 0x020240C0
POOL_STRIDE = 0x1D4


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path,
                        default=pathlib.Path("build/s49-victory-capture/exp-frame-advance"))
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    args = parser.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    scratch = out / "scratch.raw"

    def rawshot(label: str) -> str:
        probe.run(f"rawshot {out / (label + '.raw')}")
        return sha256(out / (label + ".raw"))

    def observe_reads() -> None:
        """The reads the driver's observation does (20 small dumps)."""
        probe.dump(0x02026A8C, 1)
        probe.dump(0x0200A8BA, 1)
        probe.dump(0x02026A78, 3)
        for slot in range(1, 10):
            base = ADDR_POOL + slot * POOL_STRIDE
            probe.dump(base + 0x0C, 1)
            probe.dump(base + 0xC0, 13)

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        probe.frames(1, 0)
        a = rawshot("a")
        b = rawshot("b")
        observe_reads()
        c = rawshot("c")
        observe_reads()
        observe_reads()
        d = rawshot("d")
        probe.frames(1, 0)
        e = rawshot("e")

    result = {
        "a": a, "b": b, "c": c, "d": d, "e": e,
        "rawshot_advances": a != b,
        "one_read_round_advances": b != c,
        "two_read_rounds_advance": c != d,
        "frames_advance": d != e,
    }
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
