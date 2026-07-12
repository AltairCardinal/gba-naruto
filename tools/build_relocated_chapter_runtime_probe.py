#!/usr/bin/env python3
"""Layer production chapter relocation onto the generic alternate trace probe."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

try:
    from tools.build_alternate_chapter_runtime_probe import build_probe
    from tools.import_chapter_scripts import resolve_chapter_script_patches
except ModuleNotFoundError:
    from build_alternate_chapter_runtime_probe import build_probe
    from import_chapter_scripts import resolve_chapter_script_patches


def build_relocated_probe(base: bytes, spec_path: Path) -> bytes:
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
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output_rom", type=Path)
    args = parser.parse_args()
    output = build_relocated_probe(args.base_rom.read_bytes(), args.spec)
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
