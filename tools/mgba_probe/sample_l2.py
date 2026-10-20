#!/usr/bin/env python3
"""Collect L2 "native decision point" evidence with the headless mGBA probe.

`notes/runtime-verification-gates-20260710.md` defines L2 as: the breakpoint
actually hits the *consumer* of a ROM field, and the captured registers plus
memory show the field being used.  This tool automates that capture:

  1. set a breakpoint on the consumer address,
  2. continue until it hits,
  3. record PC / LR / the register set,
  4. dump the runtime structure the field feeds into,
  5. dump a window of ROM around the source address.

A spec is a JSON file:

    {
      "rom": "rom/base.gba",
      "savestate": "build/scene-first-battle.ss9",
      "targets": [
        {
          "name": "map-loader",
          "breakpoint": "0x08068FF0",
          "rom_windows": [{"addr": "0x0853D910", "len": 32}],
          "wram_windows": [{"addr": "0x0201BE28", "len": 16}]
        }
      ]
    }

Usage:
    python tools/mgba_probe/sample_l2.py spec.json --out build/l2-evidence.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from navigate import Probe  # noqa: E402

DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

REGISTERS = [f"r{i}" for i in range(13)] + ["sp", "lr", "pc"]


def parse_status(lines: list[str]) -> dict:
    """Parse mGBA's `status` output into a register dict."""
    out: dict[str, int] = {}
    for line in lines:
        for part in line.replace("cpsr:", " ").split():
            if ":" not in part:
                continue
            name, _, value = part.partition(":")
            if name in REGISTERS and value:
                try:
                    out[name] = int(value, 16)
                except ValueError:
                    pass
    return out


def dump_window(probe: Probe, addr: int, length: int) -> str:
    return probe.read_bytes(addr, length).hex()


def run_target(probe: Probe, target: dict) -> dict:
    bp = target["breakpoint"]
    address = int(bp, 16) if isinstance(bp, str) else int(bp)
    result = {"name": target.get("name", hex(address)), "breakpoint": hex(address),
              "hit": False}
    probe.send(f"b {address:#x}")
    cont = probe.send("c")
    result["continue_output"] = cont[:6]
    status = parse_status(probe.send("status"))
    result["registers"] = {k: hex(v) for k, v in status.items()}
    result["hit"] = "pc" in status and status["pc"] == (address & ~1)
    windows = []
    for win in target.get("rom_windows", []):
        addr = int(win["addr"], 16)
        windows.append({
            "where": "rom", "addr": win["addr"], "len": win.get("len", 16),
            "bytes": dump_window(probe, addr, int(win.get("len", 16))),
        })
    for win in target.get("wram_windows", []):
        addr = int(win["addr"], 16)
        windows.append({
            "where": "wram", "addr": win["addr"], "len": win.get("len", 16),
            "bytes": dump_window(probe, addr, int(win.get("len", 16))),
        })
    result["windows"] = windows
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="JSON spec file")
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    rom = REPO / spec.get("rom", "rom/base.gba")
    state = spec.get("savestate")

    exe = pathlib.Path(args.exe)
    if not exe.exists():
        print(f"ERR {exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    argv = [str(exe), str(rom)]
    if state:
        argv.append(str(REPO / state))
    probe = Probe(exe, rom, timeout=spec.get("timeout", 300.0))
    report = {"rom": str(rom), "savestate": state, "targets": []}
    try:
        for target in spec.get("targets", []):
            print(f"--- {target.get('name')} @ {target['breakpoint']}")
            result = run_target(probe, target)
            report["targets"].append(result)
            print(f"    hit={result['hit']} "
                  f"pc={result['registers'].get('pc')} "
                  f"lr={result['registers'].get('lr')}")
    finally:
        probe.close()

    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
