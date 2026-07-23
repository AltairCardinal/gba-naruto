#!/usr/bin/env python3
"""Verify Maxmod Direct Sound hardware state in scenario 41 mGBA states."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.inspect_mgba_savestate import GbaState, load_gba_state


def _u16(state: GbaState, address: int) -> int:
    return int.from_bytes(state.read_memory(address, 2), "little")


def verify_audio_state(state: GbaState) -> dict[str, int | bool]:
    sound_control = _u16(state, 0x04000082)
    sound_master = _u16(state, 0x04000084)
    dma1_control = _u16(state, 0x040000C6)
    dma2_control = _u16(state, 0x040000D2)
    timer0_reload = _u16(state, 0x04000100)
    timer0_control = _u16(state, 0x04000102)
    active = (
        bool(sound_master & 0x80)
        and bool(dma1_control & 0x8000)
        and bool(dma2_control & 0x8000)
        and bool(timer0_control & 0x80)
    )
    return {
        "active": active,
        "sound_control": sound_control,
        "sound_master": sound_master,
        "dma1_control": dma1_control,
        "dma2_control": dma2_control,
        "timer0_reload": timer0_reload,
        "timer0_control": timer0_control,
    }


def verify_bundle(bundle_dir: Path) -> dict:
    states = sorted(bundle_dir.glob("audio-state-*.ss9"))
    if not states:
        raise ValueError(f"no audio-state savestates in {bundle_dir}")
    samples = []
    for path in states:
        report = verify_audio_state(load_gba_state(path))
        report["state"] = path.name
        samples.append(report)
    return {
        "status": "active" if all(sample["active"] for sample in samples) else "inactive",
        "sample_count": len(samples),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_bundle(args.bundle_dir)
    output = args.output or args.bundle_dir / "audio-hardware-audit.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "active" else 1


if __name__ == "__main__":
    raise SystemExit(main())
