"""Run the whole X2 flow with one command.

    python tools/s49_pairing/run_all.py

The steps, each with its own success criterion:

1. **record** the dense walk of both sides (frame **and** savestate per
   sample).  Skipped when the recording is already complete.
2. **bench view** -- the dense walk in the shape the judgment bench reads.
3. **baseline** -- the bench on the *pinned* coarse walk (the ratchet baseline).
4. **dense** -- the bench on the dense walk, ratcheted against the baseline.
5. **reproduce** -- the bench a second time, compared byte for byte.
6. **pairing** -- the pairing table and the reachability bound.

Every step exits non zero when it fails; nothing is skipped silently.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_pairing import walkspec  # noqa: E402

BENCH = REPO / "tools" / "s49_fidelity_report.py"


def run(label: str, command: list[str]) -> None:
    print(f"\n=== {label}\n$ {' '.join(command)}")
    result = subprocess.run(command, cwd=str(REPO))
    if result.returncode != 0:
        raise SystemExit(f"ERR the step '{label}' failed with exit "
                         f"{result.returncode}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=pathlib.Path,
                    default=REPO / "build" / "s49-pairing" / "x2")
    ap.add_argument("--walk", type=pathlib.Path,
                    default=REPO / "build" / "s49-pairing" / "walk4")
    ap.add_argument("--stride", type=int, default=walkspec.CAPTURE_STRIDE)
    ap.add_argument("--beats", type=int, default=walkspec.BEATS)
    ap.add_argument("--skip-record", action="store_true")
    args = ap.parse_args(argv)

    root = args.root
    base_dir = root / "base"
    dense_dir = root / "dense"
    pairing_dir = root / "pairing"

    if not args.skip_record:
        run("record the dense walk", [
            sys.executable, str(REPO / "tools" / "s49_pairing" / "record.py"),
            "--side", "both", "--out", str(args.walk), "--stride",
            str(args.stride), "--beats", str(args.beats)])

    run("build the bench view", [
        sys.executable, str(REPO / "tools" / "s49_pairing" / "bench_view.py"),
        "--walk", str(args.walk), "--work-dir", str(dense_dir),
        "--beats", str(args.beats)])

    run("the baseline bench (the ratchet baseline)", [
        sys.executable, str(BENCH), "--out", str(base_dir / "report.json"),
        "--work-dir", str(base_dir)])

    run("the dense bench (ratcheted against the baseline)", [
        sys.executable, str(BENCH), "--out", str(dense_dir / "report.json"),
        "--work-dir", str(dense_dir), "--skip-capture",
        "--ratchet", str(base_dir / "report.json")])

    run("the dense bench again (byte identical?)", [
        sys.executable, str(BENCH), "--out", str(dense_dir / "report-2.json"),
        "--work-dir", str(dense_dir), "--skip-capture",
        "--ratchet", str(base_dir / "report.json"),
        "--compare", str(dense_dir / "report.json")])

    run("the pairing table and the reachability bound", [
        sys.executable, str(REPO / "tools" / "s49_pairing" / "pairing_report.py"),
        "--walk", str(args.walk), "--bench-report",
        str(dense_dir / "report.json"), "--out", str(pairing_dir),
        "--beats", str(args.beats)])

    print("\nall steps passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
