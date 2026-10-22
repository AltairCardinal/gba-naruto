#!/usr/bin/env python3
"""Build a one-shot ARM probe that executes and reads from expanded ROM.

The probe replaces only the reset entry branch.  Its expanded-ROM stub reads a
marker from the same declared allocation partition, stores it near the end of
EWRAM, and branches to the original entry target so the game continues booting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from patch_safety import PatchSafetyGate
from rom_layout import RomLayout


DEFAULT_PARTITION = "character-battle-visual-bundles"
DEFAULT_OWNER = "character_battle_visuals"
DEFAULT_SCRATCH_ADDRESS = 0x0203FFF0
MARKER_BYTES = bytes.fromhex("4D475842")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_arm_branch(instruction: int, address: int) -> int:
    if instruction & 0xFF000000 != 0xEA000000:
        raise ValueError(
            f"base ROM entry is not an unconditional ARM branch: "
            f"0x{instruction:08X}"
        )
    displacement = instruction & 0x00FFFFFF
    if displacement & 0x00800000:
        displacement -= 0x01000000
    return address + 8 + displacement * 4


def _encode_arm_branch(address: int, target: int) -> int:
    delta = target - (address + 8)
    if delta % 4:
        raise ValueError("ARM branch target is not word aligned")
    displacement = delta // 4
    if not -(1 << 23) <= displacement < (1 << 23):
        raise ValueError("ARM branch target is outside the signed 24-bit range")
    return 0xEA000000 | (displacement & 0x00FFFFFF)


def _stub(
    *,
    marker_address: int,
    scratch_address: int,
    original_entry_target: int,
) -> bytes:
    words = (
        0xE59F0010,  # ldr r0, [pc, #16] -> marker pointer literal
        0xE5901000,  # ldr r1, [r0]
        0xE59F200C,  # ldr r2, [pc, #12] -> EWRAM scratch literal
        0xE5821000,  # str r1, [r2]
        0xE59F3008,  # ldr r3, [pc, #8] -> original target literal
        0xE12FFF13,  # bx r3
        marker_address,
        scratch_address,
        original_entry_target,
    )
    return struct.pack("<9I", *words)


def build_probe(
    base_rom_path: Path,
    layout_path: Path,
    output_rom_path: Path,
    manifest_path: Path,
    *,
    partition_id: str = DEFAULT_PARTITION,
    owner: str = DEFAULT_OWNER,
    scratch_address: int = DEFAULT_SCRATCH_ADDRESS,
) -> dict[str, object]:
    base = base_rom_path.read_bytes()
    layout_bytes = layout_path.read_bytes()
    layout = RomLayout.from_dict(json.loads(layout_bytes), base)
    stub_offset = next(
        (
            partition.start
            for partition in layout.partitions
            if partition.id == partition_id
        ),
        None,
    )
    if stub_offset is None:
        raise ValueError(f"probe partition {partition_id!r} is absent")
    marker_offset = stub_offset + 0x100
    layout.allocation_partition(
        partition_id,
        owner,
        stub_offset,
        marker_offset + len(MARKER_BYTES),
    )

    entry_address = layout.rom_base
    original_instruction = struct.unpack_from("<I", base, 0)[0]
    original_entry_target = _decode_arm_branch(original_instruction, entry_address)
    stub_address = layout.rom_base + stub_offset
    marker_address = layout.rom_base + marker_offset
    entry_patch = struct.pack(
        "<I",
        _encode_arm_branch(entry_address, stub_address),
    )
    stub = _stub(
        marker_address=marker_address,
        scratch_address=scratch_address,
        original_entry_target=original_entry_target,
    )

    data = bytearray(layout.expanded_base())
    gate = PatchSafetyGate(base, layout=layout)
    patches = (
        (
            {
                "id": "rom-expansion-probe-entry",
                "type": "bytes",
                "offset": 0,
                "before_hex": base[:4].hex(),
                "after_hex": entry_patch.hex(),
            },
            "game_effective",
        ),
        (
            {
                "id": "rom-expansion-probe-stub",
                "type": "bytes",
                "offset": stub_offset,
                "before_hex": (
                    bytes([layout.fill_byte]) * len(stub)
                ).hex(),
                "after_hex": stub.hex(),
                "allocation": {
                    "partition": partition_id,
                    "owner": owner,
                },
            },
            "allocation",
        ),
        (
            {
                "id": "rom-expansion-probe-marker",
                "type": "bytes",
                "offset": marker_offset,
                "before_hex": (
                    bytes([layout.fill_byte]) * len(MARKER_BYTES)
                ).hex(),
                "after_hex": MARKER_BYTES.hex(),
                "allocation": {
                    "partition": partition_id,
                    "owner": owner,
                },
            },
            "allocation",
        ),
    )
    applied: list[dict[str, object]] = []
    for patch, patch_class in patches:
        gate_result = gate.register(patch, patch_class=patch_class)
        after = bytes.fromhex(patch["after_hex"])
        offset = int(patch["offset"])
        data[offset : offset + len(after)] = after
        applied.append(
            {
                "id": patch["id"],
                "patch_class": patch_class,
                "offset": offset,
                "length": len(after),
                "before_sha256": _sha256(bytes.fromhex(patch["before_hex"])),
                "after_sha256": _sha256(after),
                **gate_result,
            }
        )

    output = bytes(data)
    output_rom_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_rom_path.write_bytes(output)
    manifest: dict[str, object] = {
        "schema": "rom-expansion-cpu-read-probe-v1",
        "base_rom": str(base_rom_path),
        "base_sha1": hashlib.sha1(base).hexdigest(),
        "base_sha256": _sha256(base),
        "base_size": len(base),
        "layout": str(layout_path),
        "layout_sha256": _sha256(layout_bytes),
        "cartridge_profile": layout.cartridge_profile,
        "target_rom_size": layout.target_rom_size,
        "partition": partition_id,
        "owner": owner,
        "original_entry_instruction": f"0x{original_instruction:08X}",
        "original_entry_target": f"0x{original_entry_target:08X}",
        "stub_address": f"0x{stub_address:08X}",
        "marker_address": f"0x{marker_address:08X}",
        "marker_hex": MARKER_BYTES.hex().upper(),
        "scratch_address": f"0x{scratch_address:08X}",
        "output_rom": str(output_rom_path),
        "output_sha256": _sha256(output),
        "applied_patches": applied,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a CPU execution/read probe in declared expanded ROM."
    )
    parser.add_argument("--base-rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("sequel/rom-layout.json"),
    )
    parser.add_argument("--output-rom", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_probe(
        args.base_rom,
        args.layout,
        args.output_rom,
        args.manifest,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
