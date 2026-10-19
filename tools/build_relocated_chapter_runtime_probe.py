#!/usr/bin/env python3
"""Layer production chapter relocation onto the generic alternate trace probe."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

try:
    from tools.build_alternate_chapter_runtime_probe import build_probe
    from tools.import_chapter_scripts import resolve_chapter_script_patches
except ModuleNotFoundError:
    from build_alternate_chapter_runtime_probe import build_probe
    from import_chapter_scripts import resolve_chapter_script_patches


PORTRAIT_MATRIX = 0x5A4DEC
PORTRAIT_RECORD_SIZE = 40
PORTRAIT_PAIR_SIZE = 8


def build_relocated_probe(
    base: bytes,
    spec_path: Path,
    *,
    portrait_pair_ab: dict[str, Any] | None = None,
) -> bytes:
    """Apply an already-validated production plan to the traced base ROM."""
    plan = resolve_chapter_script_patches(spec_path, rom=base)
    rom = bytearray(build_probe(base))
    for patch in plan:
        if patch["type"] == "bytes":
            offset = int(patch["offset"])
            before = bytes.fromhex(patch["before_hex"])
            after = bytes.fromhex(patch["after_hex"])
        elif patch["type"] == "pointer_redirect":
            offset = int(patch["pointer_table_offset"])
            before = bytes.fromhex(patch["expected_pointer_hex"])
            after = bytes.fromhex(patch["new_pointer_hex"])
        else:
            raise ValueError(f"unsupported relocation sub-patch {patch['type']!r}")
        actual = bytes(rom[offset:offset + len(before)])
        if actual != before:
            raise ValueError(
                f"relocation probe patch {patch['id']} mismatch at 0x{offset:X}: "
                f"expected {before.hex()}, got {actual.hex()}"
            )
        rom[offset:offset + len(after)] = after
    if portrait_pair_ab is not None:
        target_id = int(portrait_pair_ab["target_id"])
        source_id = int(portrait_pair_ab["source_id"])
        variant = int(portrait_pair_ab["variant"])
        if not 0 <= target_id < 63 or not 0 <= source_id < 63:
            raise ValueError("portrait A/B record ID must be in 0..62")
        if not 0 <= variant < 5:
            raise ValueError("portrait A/B variant must be in 0..4")
        target = PORTRAIT_MATRIX + target_id * PORTRAIT_RECORD_SIZE + variant * 8
        source = PORTRAIT_MATRIX + source_id * PORTRAIT_RECORD_SIZE + variant * 8
        pair = base[source:source + PORTRAIT_PAIR_SIZE]
        if pair == b"\x00" * PORTRAIT_PAIR_SIZE:
            raise ValueError("portrait A/B source pair is null")
        rom[target:target + PORTRAIT_PAIR_SIZE] = pair
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--portrait-target-id", type=int)
    parser.add_argument("--portrait-source-id", type=int)
    parser.add_argument("--portrait-variant", type=int, default=0)
    args = parser.parse_args()
    portrait_pair_ab = None
    if args.portrait_target_id is not None or args.portrait_source_id is not None:
        if args.portrait_target_id is None or args.portrait_source_id is None:
            parser.error("portrait target and source IDs must be provided together")
        portrait_pair_ab = {
            "target_id": args.portrait_target_id,
            "source_id": args.portrait_source_id,
            "variant": args.portrait_variant,
        }
    output = build_relocated_probe(
        args.base_rom.read_bytes(), args.spec, portrait_pair_ab=portrait_pair_ab
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
