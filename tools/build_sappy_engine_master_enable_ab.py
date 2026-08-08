#!/usr/bin/env python3
"""Build controlled audio ROMs differing only in SOUNDCNT_X master enable."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

try:
    from tools.build_controlled_audio_runtime_probe import build_probe
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from build_controlled_audio_runtime_probe import build_probe


PATCH_OFFSET = 0x09AE76
BASELINE_IMMEDIATE = 0x8F
CANDIDATE_IMMEDIATE = 0x0F
MOVS_R0_OPCODE_HIGH = 0x20


def build_pair(base: bytes, *, sound_id: int = 101) -> tuple[bytes, bytes]:
    baseline = build_probe(base, sound_id=sound_id)
    expected = bytes((BASELINE_IMMEDIATE, MOVS_R0_OPCODE_HIGH))
    if baseline[PATCH_OFFSET:PATCH_OFFSET + 2] != expected:
        raise ValueError("audio initializer master-enable instruction does not match")
    candidate = bytearray(baseline)
    candidate[PATCH_OFFSET] = CANDIDATE_IMMEDIATE
    changed = [
        index
        for index, (left, right) in enumerate(zip(baseline, candidate))
        if left != right
    ]
    if changed != [PATCH_OFFSET]:
        raise AssertionError(f"unexpected A/B differences: {changed}")
    return baseline, bytes(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("baseline_rom", type=Path)
    parser.add_argument("candidate_rom", type=Path)
    parser.add_argument("--sound-id", type=lambda value: int(value, 0), default=101)
    args = parser.parse_args()
    baseline, candidate = build_pair(
        args.base_rom.read_bytes(), sound_id=args.sound_id
    )
    for path, payload in (
        (args.baseline_rom, baseline),
        (args.candidate_rom, candidate),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        print(f"wrote {path}: sha256={hashlib.sha256(payload).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
