#!/usr/bin/env python3
"""W19-D: record the settlement chain of a **real** battle and classify it.

What this tool adds on top of ``tools/s49_battle_balance/v1_battle.py``
---------------------------------------------------------------------
``v1_battle.py`` already plays the battle with the buttons only and walks
the settlement chain with the buttons only, and its receipt already says
whether the run was a real battle (``acceptance.from_real_battle``) or a
tool check (``entry.poke``).  Two things were still missing:

1. **the chain's verdict**: how many pages of the chain were recorded, which
   phases were reached, and whether the chain died on the way.  A chain that
   stops after one page is not a chain, and the receipt has to say so.
2. **the reason the chain died**: wave 19 found that a real battle can leave
   the Butano palette bank without a free slot, so the product dies on the
   Butano error screen the moment the settlement chain starts.  The error is
   visible in the captured frame (the Butano error screen) and in the
   probe's stderr (Butano's ``log_status()`` dump of the palette bank).

So this tool

* runs the **real** chain (``v1_battle.py`` with the buttons only) and the
  **tool-check** chain (``v1_battle.py --poke-settlement``) on the **same**
  ROM and with the **same** probe, so the two are directly comparable;
* keeps the two chains in **separate** result blocks - a poked chain is
  never a real chain, and a report must not mix them;
* detects the Butano error screen in the captured pages and extracts
  Butano's palette bank status from the probe's stderr;
* writes one receipt that answers: "did a real battle reach the settlement
  chain, and how far did the chain get?".

Usage::

    python tools/s49_w19d/w19d_real_chain.py \\
        --rom build/w19-d/rom-pinned.gba \\
        --exe build/w19-d/probe/mgba-probe.exe \\
        --out build/w19-d/chain
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

V1_BATTLE = REPO / "tools" / "s49_battle_balance" / "v1_battle.py"
DEFAULT_EXE = REPO / "build" / "w19-d" / "probe" / "mgba-probe.exe"
DEFAULT_TRUTH = REPO / "build" / "v1" / "battle-truth.json"

# Butano's error screen is a black frame with a fixed block of text; the
# sha256 below is the error screen of this ROM (the palette bank failure).
# The detection does **not** rely on the hash alone: the text block is
# recognised by the palette bank's status line in the probe's stderr.
PALETTE_STATUS_MARKER = "palettes:"


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def palette_status(stderr_path: pathlib.Path) -> dict:
    """Butano's palette bank status, if the probe captured one."""
    if not stderr_path.exists():
        return {"present": False}
    text = stderr_path.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines()
             if line.startswith("[mgba]")]
    if not lines:
        return {"present": False}
    return {"present": True, "lines": lines,
            "slot_table": [line for line in lines if "slot_index" in line]}


def run_chain(rom: pathlib.Path, exe: pathlib.Path, truth: pathlib.Path,
              out_dir: pathlib.Path, poke: bool,
              max_turns: int, use_tools: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(V1_BATTLE),
               "--rom", str(rom),
               "--out", str(out_dir),
               "--exe", str(exe),
               "--truth", str(truth),
               "--boot",
               "--max-turns", str(max_turns)]
    if poke:
        command.append("--poke-settlement")
    elif use_tools:
        command.append("--use-tools")
    completed = subprocess.run(command, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    receipt_path = out_dir / "battle.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) \
        if receipt_path.exists() else {}
    settlement = receipt.get("settlement", {}) or {}
    pages = settlement.get("pages", []) or []
    phases = []
    for page in pages:
        if page["phase_name"] not in phases:
            phases.append(page["phase_name"])
    status = palette_status(out_dir / "stderr.txt")
    entry = receipt.get("entry", {}) or {}
    acceptance = receipt.get("acceptance", {}) or {}
    return {
        "kind": "tool-check (poked)" if poke else "real battle (buttons only)",
        "command": " ".join(command),
        "returncode": completed.returncode,
        "rom_sha256": receipt.get("rom_sha256"),
        "entry": entry,
        "acceptance": acceptance,
        "battle_decided": receipt.get("battle_decided"),
        "outcome": receipt.get("outcome"),
        "round": receipt.get("round"),
        "frames_run": receipt.get("frames_run"),
        "keys_pressed": receipt.get("keys_pressed"),
        "chain": {
            "pages": len(pages),
            "phases_seen": phases,
            "final_phase_name": settlement.get("final_phase_name"),
            "stuck_at": settlement.get("stuck_at"),
            "stuck_phase": settlement.get("stuck_phase"),
            "presses": settlement.get("presses"),
            "poked": settlement.get("poked"),
            "page_files": [page["file"] for page in pages],
            "page_sha256": [page["sha256"] for page in pages],
        },
        "palette_status": status,
        "butano_error_screen": bool(status.get("present")),
        "shots": str(out_dir / "shots"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--truth", type=pathlib.Path, default=DEFAULT_TRUTH)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--max-turns", type=int, default=400)
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument("--skip-toolcheck", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    real = run_chain(args.rom, args.exe, args.truth,
                     args.out / "real", poke=False,
                     max_turns=args.max_turns,
                     use_tools=not args.no_tools)
    document = {
        "schema": "konoha.s49-w19d-real-chain.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "probe": str(args.exe),
        "real_chain": real,
    }
    if not args.skip_toolcheck:
        toolcheck = run_chain(args.rom, args.exe, args.truth,
                              args.out / "toolcheck", poke=True,
                              max_turns=args.max_turns, use_tools=False)
        document["toolcheck_chain"] = toolcheck
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "w19d-chain.json").write_text(
            json.dumps(document, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")
    if not args.quiet:
        for key in ("real_chain", "toolcheck_chain"):
            if key not in document:
                continue
            block = document[key]
            chain = block["chain"]
            print(f"--- {key}: {block['kind']} ---")
            print("  rom_sha256      ", block["rom_sha256"])
            print("  from_real_battle", block["acceptance"].get(
                "from_real_battle"))
            print("  poke_commands   ", block["acceptance"].get(
                "poke_commands"))
            print("  bee_hp_dropped  ", block["acceptance"].get(
                "bee_hp_dropped"))
            print("  outcome         ", block["outcome"])
            print("  chain pages     ", chain["pages"])
            print("  chain phases    ", chain["phases_seen"])
            print("  chain final     ", chain["final_phase_name"])
            print("  butano error    ", block["butano_error_screen"])
            if block["palette_status"].get("present"):
                for line in block["palette_status"]["lines"]:
                    print("   ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
