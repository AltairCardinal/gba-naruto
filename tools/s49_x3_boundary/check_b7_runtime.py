#!/usr/bin/env python3
"""X3 / B7 runtime criterion: the battle result save writes 0 bytes.

The unit test (``game/tests/test_battle_campaign_sram_trigger.cpp``) proves
the rule on the host.  This script proves it **on the ROM**:

* it records the same walk on two builds -- the shipped build and a probe
  build whose ``main.cpp`` calls ``save_battle_campaign_to_sram`` with the
  ``battle_result`` trigger at boot (the shipped build only reaches that call
  after a won battle, which the current tooling cannot drive),
* it reads the cartridge SRAM at the end of both walks,
* and it compares the two images byte for byte.

If the battle result path wrote anything, the two images would differ.  The
probe build also asserts ``saved.success() && saved.suppressed`` at runtime,
so an unsuppressed write would stop the ROM with Butano's fatal error
screen.

Usage::

    python tools/s49_x3_boundary/check_b7_runtime.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import walkrec  # noqa: E402

WORK = walkrec.WORK
RECEIPTS = WORK / "receipts"

PROBE_ROM = WORK / "roms" / "rom-probe-b7.gba"
SHIPPED_ROM = WORK / "roms" / "rom-A2-with-b5.gba"

#: The canonical S49 walk (the one the fidelity bench uses).
CANONICAL_KEYS = ["Down", "Down"] + ["A"] * 32

SRAM_BASE = 0x0E000000
SRAM_SIZE = 32768


def dump_sram(rom: pathlib.Path, state: pathlib.Path, out: pathlib.Path) -> str:
    """Read the cartridge SRAM of one savestate and return its sha256."""

    out.parent.mkdir(parents=True, exist_ok=True)
    prefix = out.with_suffix("")
    command = [
        sys.executable,
        str(walkrec.REPO / "tools" / "mgba_probe" / "probe_client.py"),
        "--rom", str(rom),
        "--exe", str(walkrec.PRIVATE_PROBE),
        "--timeout", "600",
        "--cmd", "load %s" % state,
        "--cmd", "framedump 1 0x%08X %d 0x000 %s"
                 % (SRAM_BASE, SRAM_SIZE, prefix.as_posix()),
        "--out", str(out.with_suffix(".json")),
    ]
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "sram dump failed: %s" % (completed.stderr or completed.stdout)[-800:]
        )
    binary = prefix.with_name(prefix.name + "-0000.bin")
    if not binary.is_file():
        candidates = sorted(out.parent.glob(prefix.name + "*.bin"))
        if not candidates:
            raise RuntimeError("no sram image for %s" % state)
        binary = candidates[0]
    return hashlib.sha256(binary.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args(argv)

    for rom in (PROBE_ROM, SHIPPED_ROM):
        if not rom.is_file():
            print("ERR missing ROM: %s" % rom, file=sys.stderr)
            return 2

    walks = {}
    for label, rom in (("probe", PROBE_ROM), ("shipped", SHIPPED_ROM)):
        walks[label] = WORK / ("b7-%s" % label)
        if not args.no_record:
            walkrec.record_walk(rom, CANONICAL_KEYS, walks[label])

    receipt = {
        "schema_version": 1,
        "identity": "x3_b7_runtime_zero_byte_write",
        "walks": {},
    }
    hashes = {}
    for label, rom in (("probe", PROBE_ROM), ("shipped", SHIPPED_ROM)):
        walk = walks[label]
        frames = walkrec.frames_of(walk)
        states = sorted(walk.glob("step-*.ss9"))
        crash = walkrec.crash_step(walk)
        digest = ""
        if states:
            digest = dump_sram(
                rom, states[-1], WORK / "sram" / ("b7-%s.bin" % label)
            )
        hashes[label] = digest
        receipt["walks"][label] = {
            "rom": str(rom),
            "rom_sha256": walkrec.sha256_file(rom),
            "frames": len(frames),
            "last_state": states[-1].name if states else None,
            "sram_sha256": digest,
            "crash": crash,
        }

    identical = (
        hashes["probe"] != "" and hashes["probe"] == hashes["shipped"]
    )
    no_crash = all(
        receipt["walks"][label]["crash"] is None for label in ("probe", "shipped")
    )
    receipt["criteria"] = {
        "probe-build-did-not-crash": {
            "status": "PASS" if no_crash else "FAIL",
            "detail": "the probe build ran the battle result save at boot",
        },
        "battle-result-write-is-zero-bytes": {
            "status": "PASS" if identical else "FAIL",
            "detail": "probe sram %s vs shipped sram %s"
                      % (hashes["probe"][:16], hashes["shipped"][:16]),
        },
    }
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    out = RECEIPTS / "b7_runtime.json"
    out.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for label in ("probe", "shipped"):
        row = receipt["walks"][label]
        print("%-8s frames=%d sram=%s crash=%s"
              % (label, row["frames"], row["sram_sha256"][:16],
                 row["crash"]))
    for name, criterion in receipt["criteria"].items():
        print("%-42s %s  %s"
              % (name, criterion["status"], criterion["detail"]))
    print("receipt: %s" % out)
    return 0 if (identical and no_crash) else 1


if __name__ == "__main__":
    raise SystemExit(main())
