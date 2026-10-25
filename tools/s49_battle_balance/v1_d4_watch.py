#!/usr/bin/env python3
"""U4 (wave 17): watch the remake ROM and re-test defect D4 when it moves.

Defect D4 is the product defect wave 16's V1 found: as soon as the player
confirms an attack whose range holds a living enemy, the remake's battle
scene stops advancing (the ninja tool freezes the ROM outright, the plain
attacks kill the input).  The fix belongs to the remake line (stream U1), so
this watcher does the only thing the driving side can do: **wait for the ROM
to change and re-run the freeze diagnostic on the new ROM**.

The watcher

* polls the ROM's sha256,
* waits until the ROM is **stable** (the same sha twice in a row) before it
  touches it, so a half written ROM is never tested,
* copies the ROM into ``build/v1-u4/`` and pins it,
* runs ``v1_diag_freeze.py`` on the pinned copy and writes a report,
* keeps watching.

It never writes to the remake tree and never pokes the ROM.

Usage::

    python tools/s49_battle_balance/v1_d4_watch.py \\
        --rom D:\\Shell\\Github\\gba-naruto-butano\\butano-sequel\\butano-sequel.gba \\
        --out build/v1-u4/watch --minutes 120
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "v1-u4" / "watch")
    parser.add_argument("--exe", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe-u4" /
                        "mgba-probe.exe")
    parser.add_argument("--minutes", type=float, default=120.0)
    parser.add_argument("--poll", type=float, default=45.0)
    parser.add_argument("--cells", type=str, default="9,6;8,6;11,6")
    parser.add_argument("--index", type=int, default=3)
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / "watch.json"
    seen: list[str] = []
    last_sha = None
    stable_sha = None
    deadline = time.time() + args.minutes * 60.0
    while time.time() < deadline:
        try:
            sha = sha256_file(args.rom)
        except OSError as error:
            print(f"watch: {args.rom} unreadable ({error})", flush=True)
            time.sleep(args.poll)
            continue
        if sha != last_sha:
            print(f"watch: rom sha {sha}", flush=True)
            last_sha = sha
            stable_sha = None
        elif stable_sha != sha:
            # The ROM has not moved for one poll: it is safe to test it.
            stable_sha = sha
            print(f"watch: rom {sha[:16]} is stable -> testing D4", flush=True)
            pinned = args.out / f"rom-{sha[:16]}.gba"
            shutil.copyfile(args.rom, pinned)
            report = args.out / f"d4-{sha[:16]}"
            command = [
                sys.executable, str(HERE / "v1_diag_freeze.py"),
                "--rom", str(pinned), "--exe", str(args.exe),
                "--out", str(report), "--index", str(args.index),
                "--cells", args.cells,
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            print(completed.stdout, flush=True)
            if completed.stderr:
                print(completed.stderr, flush=True)
            results = []
            freeze_report = report / "freeze-report.json"
            if freeze_report.is_file():
                results = json.loads(freeze_report.read_text(
                    encoding="utf-8")).get("results", [])
            frozen = [item for item in results
                      if not item.get("after", {}).get("advanced", True)]
            verdict = {
                "rom_sha256": sha,
                "tested_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "results": results,
                "frozen_cells": len(frozen),
                "d4_present": bool(frozen),
                "returncode": completed.returncode,
            }
            report_path.write_text(
                json.dumps(verdict, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n")
            seen.append(sha)
            print(f"watch: D4 present = {verdict['d4_present']} "
                  f"(frozen {len(frozen)}/{len(results)})", flush=True)
        time.sleep(args.poll)
    print("watch: time is up", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
