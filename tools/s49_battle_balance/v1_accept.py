#!/usr/bin/env python3
"""U4 (wave 17): the acceptance run of the real victory.

One command produces every piece of evidence the stream has to deliver:

1. **two independent real battle runs** of the same ROM (``v1_battle.py``),
2. the **per-screen comparison** of the settlement chain against the
   original's truth (``v1_compare.py``),
3. the **byte identity** of the two runs (``v1_repeat.py``).

The runs are **real**: the driver plays the battle with the buttons only and
the receipt's ``acceptance`` block says whether the outcome came from the
product's own decision, whether a bee's hit points went down and whether the
escort survived.  The receipt also carries the number of ``poke`` commands
the driver sent to the probe, so a poked victory can never pass for a real
one.

Usage::

    python tools/s49_battle_balance/v1_accept.py \\
        --rom build/v1-u4/rom-pinned.gba \\
        --exe build/mgba-probe-u4/mgba-probe.exe \\
        --out build/v1-u4/accept --use-tools
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]


def run(command: list[str]) -> subprocess.CompletedProcess:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe-u4" /
                        "mgba-probe.exe")
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "v1-u4" / "accept")
    parser.add_argument("--truth", type=pathlib.Path,
                        default=REPO / "build" / "v1" / "battle-truth.json")
    parser.add_argument("--settlement-truth", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "w4" /
                        "settlement-truth")
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--use-tools", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    battle = [sys.executable, str(HERE / "v1_battle.py"),
              "--rom", str(args.rom), "--exe", str(args.exe),
              "--truth", str(args.truth), "--boot",
              "--max-turns", str(args.max_turns)]
    if args.use_tools:
        battle.append("--use-tools")
    if args.quiet:
        battle.append("--quiet")

    runs = []
    for name in ("run-a", "run-b"):
        target = args.out / name
        completed = run(battle + ["--out", str(target)])
        receipt_path = target / "battle.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) \
            if receipt_path.is_file() else {}
        runs.append({"name": name, "returncode": completed.returncode,
                     "receipt": receipt})
        print(f"  {name}: outcome={receipt.get('outcome')} "
              f"acceptance={json.dumps(receipt.get('acceptance', {}))}",
              flush=True)

    compare = run([sys.executable, str(HERE / "v1_compare.py"),
                   "--truth", str(args.settlement_truth),
                   "--remake", str(args.out / "run-a" / "shots"),
                   "--out", str(args.out / "compare-real.json")])
    repeat = run([sys.executable, str(HERE / "v1_repeat.py"),
                  "--a", str(args.out / "run-a"),
                  "--b", str(args.out / "run-b"),
                  "--out", str(args.out / "repeat.json")])

    screens = []
    compare_path = args.out / "compare-real.json"
    if compare_path.is_file():
        screens = json.loads(compare_path.read_text(
            encoding="utf-8")).get("screens", [])
    repeat_document = {}
    repeat_path = args.out / "repeat.json"
    if repeat_path.is_file():
        repeat_document = json.loads(repeat_path.read_text(encoding="utf-8"))

    acceptance = runs[0]["receipt"].get("acceptance", {})
    verdict = {
        "schema": "konoha.s49-u4-acceptance.v1",
        "rom": str(args.rom),
        "rom_sha256": runs[0]["receipt"].get("rom_sha256"),
        "entry": runs[0]["receipt"].get("entry"),
        "outcome": runs[0]["receipt"].get("outcome"),
        "acceptance": acceptance,
        "real_victory": bool(acceptance.get("from_real_battle")),
        "bee_hp_dropped": bool(acceptance.get("bee_hp_dropped")),
        "escort_alive": bool(acceptance.get("escort_alive")),
        "poke_commands": acceptance.get("poke_commands"),
        "two_runs_identical": bool(repeat_document.get("identical")),
        "repeat": repeat_document,
        "screens": screens,
        "compare_returncode": compare.returncode,
        "repeat_returncode": repeat.returncode,
    }
    verdict["passed"] = bool(verdict["real_victory"] and
                             verdict["bee_hp_dropped"] and
                             verdict["escort_alive"] and
                             verdict["two_runs_identical"])
    (args.out / "acceptance.json").write_text(
        json.dumps(verdict, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in verdict.items()
                      if key not in ("screens", "repeat")},
                     indent=1, ensure_ascii=False))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
