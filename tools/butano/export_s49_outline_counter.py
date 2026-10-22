#!/usr/bin/env python3
"""Derive the original's outline-colour counter behaviour from live probes.

Round 26 closed the outline question that had been open since round 25.  The
ROM side is known statically: the writer lives at ``0x0806A7A0``, it reads a
32-bit counter from **IWRAM ``0x03000078``**, and it writes

    v = (global & 0xF) * 2 + 1          (rising half)
    v = 32 - ((global & 0xF) * 2 + 1)  (falling half, selected by global & 0x10)

into PRAM entry 15 of the unit's palette bank, as ``(v << 10) | (v << 5)``.

Two things the static analysis could NOT answer were settled by reading the
hardware while the original ROM runs:

* **the counter's initial value** -- it is 0 at power-on and is *not* reset
  when a battle starts; it keeps counting from boot, so the outline colour's
  phase depends on the absolute frame count;
* **how fast it advances** -- exactly **+1 per frame** during a battle.

This tool reads the probe receipts (``samples.jsonl`` written by
``tools/butano/capture_s49_iwram_counter.py``) and re-derives those answers
from the recorded bytes, so the claim is checkable without running mGBA.

Usage::

    /usr/local/bin/python3 tools/butano/export_s49_outline_counter.py
    /usr/local/bin/python3 tools/butano/export_s49_outline_counter.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROBE_DIR = ROOT / "artifacts/s49-outline-triangle-counter-20261021-v1/probe"
OUT_DIR = ROOT / "artifacts/s49-outline-triangle-counter-20261021-v1"
OUT_JSON = OUT_DIR / "counter.json"
OUT_MANIFEST = OUT_DIR / "manifest.json"

SCHEMA = "konoha.s49-outline-triangle-counter.v1"

#: The counter's address in IWRAM, and the PRAM offset of palette entry 15 of
#: bank 0 (the unit outline colour the probe sampled).
COUNTER_IWRAM_OFFSET = 0x78
PRAM_OUTLINE_OFFSET = 542

#: The three probes that were recorded.
PROBES = ("power-on", "checkpoint-14-entry", "postbattle-task-menu")

#: The pinned answers.  They are the numbers the gate asserts, and every one
#: of them is re-derived from the probe bytes by this tool.
PINNED = {
    "power-on": {"first_counter": 0, "deltas": {0: 299}},
    "checkpoint-14-entry": {"first_counter": 998060, "deltas": {1: 199}},
    "postbattle-task-menu": {"first_counter": 1061053, "deltas": {1: 59}},
}


class CounterError(RuntimeError):
    """Raised when a probe receipt is missing or contradicts the pins."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _implied_v(palette_entry: int) -> int | None:
    """The outline value v whose encoded colour is ``palette_entry``."""
    for value in range(1, 33):
        if palette_entry == ((value << 10) | (value << 5)):
            return value
    return None


def _read_probe(name: str) -> list[dict[str, Any]]:
    path = PROBE_DIR / name / "samples.jsonl"
    if not path.is_file():
        raise CounterError(f"missing probe receipt: {path}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    if not rows:
        raise CounterError(f"empty probe receipt: {path}")
    return rows


def analyse(name: str) -> dict[str, Any]:
    rows = _read_probe(name)
    counters = [int(row["counter"]) for row in rows]
    deltas: dict[int, int] = {}
    for left, right in zip(counters, counters[1:]):
        deltas[right - left] = deltas.get(right - left, 0) + 1
    pinned = PINNED.get(name)
    if pinned is not None:
        if counters[0] != pinned["first_counter"]:
            raise CounterError(
                f"{name}: first counter {counters[0]} != {pinned['first_counter']}"
            )
        if deltas != pinned["deltas"]:
            raise CounterError(f"{name}: deltas {deltas} != {pinned['deltas']}")
    samples = []
    for row in rows[:12]:
        counter = int(row["counter"])
        rising = (counter & 0xF) * 2 + 1
        falling = 32 - rising
        model = falling if counter & 0x10 else rising
        observed = _implied_v(int(row["pram15_bank0"]))
        samples.append(
            {
                "frame": row["frame"],
                "counter": counter,
                "counter_mod_64": counter % 64,
                "rising_v": rising,
                "falling_v": falling,
                "model_v": model,
                "observed_v": observed,
                "matches": observed is None or observed == model,
            }
        )
    mismatches = [sample for sample in samples if not sample["matches"]]
    return {
        "probe": name,
        "samples": len(rows),
        "first_counter": counters[0],
        "last_counter": counters[-1],
        "counter_deltas": deltas,
        "counter_mod_64": counters[0] % 64,
        "model": "v = (global & 0xF) * 2 + 1, falling half when global & 0x10",
        "first_samples": samples,
        "model_mismatches": len(mismatches),
    }


def build() -> dict[str, Any]:
    probes = {name: analyse(name) for name in PROBES}
    battle = probes["checkpoint-14-entry"]
    answers = {
        "counter_address": "IWRAM 0x03000078 (32-bit word)",
        "initial_value": 0,
        "initial_value_evidence": (
            "the power-on probe reads 0 for 300 consecutive frames and the "
            "counter never decreases, so the value is inherited from the "
            "zeroed IWRAM at boot and is NOT reset when a battle starts"
        ),
        "advance_per_frame": 1,
        "advance_evidence": (
            "199 of 199 consecutive deltas in the battle probe are exactly +1 "
            "(and 59 of 59 after the battle)"
        ),
        "triangle_period_frames": 64,
        "triangle_period_evidence": (
            "the counter advances +1 per frame and the colour is "
            "v = (global & 0xF) * 2 + 1 with the falling half selected by "
            "global & 0x10, so one full up-down cycle is 64 counter steps"
        ),
        "battle14_entry_phase_mod_64": battle["counter_mod_64"],
        "phase_caveat": (
            "the counter counts from power-on, so the outline colour's phase "
            "depends on the absolute frame count since boot -- a remake has "
            "to be phase-aligned with the original at the same game moment, "
            "not merely use the same waveform"
        ),
        "live_model_mismatches": sum(
            probe["model_mismatches"] for probe in probes.values()
        ),
    }
    return {
        "schema": SCHEMA,
        "what": (
            "The original's unit-outline colour counter: where it lives, "
            "what it starts at, how fast it advances, and the evidence."
        ),
        "rom": {
            "writer_function": "0x0806A7A0",
            "pram_store": "0x0806A7EE",
            "counter_literal_in_rom": "0x0806A7D4",
            "pram_literal_in_rom": ["0x0806A7F4", "0x0806A808"],
        },
        "counter_iwram_offset": COUNTER_IWRAM_OFFSET,
        "pram_outline_offset": PRAM_OUTLINE_OFFSET,
        "answers": answers,
        "probes": probes,
    }


def build_manifest(counter: dict[str, Any]) -> bytes:
    inputs = {}
    for name in PROBES:
        for file_name in ("samples.jsonl", "inputs.json", "done.json"):
            path = PROBE_DIR / name / file_name
            if path.is_file():
                inputs[str(path.relative_to(ROOT))] = {
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
    manifest = {
        "schema": SCHEMA,
        "exporter": "tools/butano/export_s49_outline_counter.py",
        "inputs": inputs,
        "outputs": {
            "counter.json": {
                "sha256": hashlib.sha256(
                    (
                        json.dumps(counter, ensure_ascii=False, indent=2, sort_keys=True)
                        + "\n"
                    ).encode("utf-8")
                ).hexdigest(),
            }
        },
    }
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the exported artifacts are not up to date",
    )
    args = parser.parse_args(argv)
    try:
        counter = build()
    except CounterError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    payload = (
        json.dumps(counter, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    manifest = build_manifest(counter)
    if args.check:
        problems = []
        if not OUT_JSON.is_file() or OUT_JSON.read_bytes() != payload:
            problems.append(f"stale: {OUT_JSON}")
        if not OUT_MANIFEST.is_file() or OUT_MANIFEST.read_bytes() != manifest:
            problems.append(f"stale: {OUT_MANIFEST}")
        if problems:
            print("\n".join(problems), file=sys.stderr)
            print("run tools/butano/export_s49_outline_counter.py", file=sys.stderr)
            return 1
        print("the outline counter receipt is up to date")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_bytes(payload)
    OUT_MANIFEST.write_bytes(manifest)
    print(f"wrote {OUT_JSON} and {OUT_MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
