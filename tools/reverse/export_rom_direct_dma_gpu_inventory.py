#!/usr/bin/env python3
"""Inventory direct DMA-register literal users for fixed ROM-to-GPU copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-direct-dma-gpu-inventory-v1"
VERIFY_SCHEMA = "rom-direct-dma-gpu-inventory-verification-v1"
PAYLOAD_NAME = "rom-direct-dma-gpu-inventory.json"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
DMA_BASE = 0x040000B0
DMA_END = 0x040000E0
DMA_STRIDE = 12
WINDOW_BYTES = 96
SCOPE = {
    "all_thumb_shaped_dma_register_literal_users_audited": True,
    "literal_seeded_96_byte_rule_applied_to_full_rom": True,
    "runtime_reachability_complete": False,
    "non_literal_dma_base_derivations_complete": False,
    "cross_function_dataflow_complete": False,
    "indirect_dma_wrappers_complete": False,
    "custom_copy_loops_complete": False,
    "two_stage_copies_complete": False,
    "raw_uncompressed_graphics_complete": False,
    "generic_image_writeback_complete": False,
}
SELECTION_RULE = {
    "denominator": (
        "every halfword-aligned Thumb-shaped PC-relative literal load whose "
        "32-bit value lies in 0x040000B0..0x040000DF"
    ),
    "window_bytes": WINDOW_BYTES,
    "accepted_transfer": (
        "one channel has statically fixed source, destination and control at "
        "the control write; source is mapped ROM; destination is PRAM, VRAM "
        "or OAM; enable and nonzero count are proven"
    ),
    "unknown_instruction_policy": "invalidate r0-r7 and pending channel values",
    "thumb_shaped_encoding_is_runtime_reachable_code": False,
}


Symbol = tuple[int, bool]
UNKNOWN: Symbol = (0, True)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _literal_value(
    rom: bytes, offset: int
) -> tuple[int, int, int] | None:
    instruction = struct.unpack_from("<H", rom, offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    address = ROM_BASE + offset
    literal_address = ((address + 4) & ~3) + (instruction & 0xFF) * 4
    literal_offset = literal_address - ROM_BASE
    if literal_offset < 0 or literal_offset + 4 > len(rom):
        return None
    return (
        (instruction >> 8) & 7,
        literal_address,
        struct.unpack_from("<I", rom, literal_offset)[0],
    )


def _channel(address: int) -> tuple[int, int]:
    channel = (address - DMA_BASE) // DMA_STRIDE
    return channel, DMA_BASE + channel * DMA_STRIDE


def _add(left: Symbol, right: Symbol) -> Symbol:
    return left[0] + right[0], left[1] or right[1]


def _gpu_domain(address: int) -> str | None:
    if 0x05000000 <= address < 0x05000400:
        return "PRAM"
    if 0x06000000 <= address < 0x06018000:
        return "VRAM"
    if 0x07000000 <= address < 0x07000400:
        return "OAM"
    return None


def _control_size(control: int) -> int | None:
    count = control & 0xFFFF
    if not control & 0x80000000 or count == 0:
        return None
    width = 4 if control & 0x04000000 else 2
    return count * width


def _scan_user(
    rom: bytes, instruction_offset: int
) -> tuple[list[dict[str, Any]], list[str]]:
    registers: list[Symbol] = [UNKNOWN] * 8
    channel_values: dict[int, dict[int, Symbol]] = {
        index: {} for index in range(4)
    }
    transfers: list[dict[str, Any]] = []
    offset = instruction_offset
    end = min(len(rom) - 1, instruction_offset + WINDOW_BYTES)
    while offset + 2 <= end:
        instruction = struct.unpack_from("<H", rom, offset)[0]
        address = ROM_BASE + offset
        literal = _literal_value(rom, offset)
        if literal is not None:
            register, _, value = literal
            registers[register] = (value, False)
            offset += 2
            continue
        if instruction & 0xF800 == 0x2000:
            registers[(instruction >> 8) & 7] = (
                instruction & 0xFF,
                False,
            )
            offset += 2
            continue
        if instruction & 0xF800 in (0x0000, 0x0800):
            shift = (instruction >> 6) & 0x1F
            source = (instruction >> 3) & 7
            destination = instruction & 7
            value, dynamic = registers[source]
            if instruction & 0xF800 == 0:
                registers[destination] = (value << shift, dynamic)
            else:
                registers[destination] = (value >> (shift or 32), dynamic)
            offset += 2
            continue
        if instruction & 0xF800 == 0x1800:
            immediate = bool(instruction & 0x0400)
            subtract = bool(instruction & 0x0200)
            operand = (instruction >> 6) & 7
            source = (instruction >> 3) & 7
            destination = instruction & 7
            right = (
                (operand, False) if immediate else registers[operand]
            )
            if subtract:
                right = (-right[0], right[1])
            registers[destination] = _add(registers[source], right)
            offset += 2
            continue
        if instruction & 0xFC00 == 0x4400:
            operation = (instruction >> 8) & 3
            destination = ((instruction >> 4) & 8) | (instruction & 7)
            source = (instruction >> 3) & 0xF
            if destination < 8 and source < 8 and operation == 0:
                registers[destination] = _add(
                    registers[destination], registers[source]
                )
            elif destination < 8 and source < 8 and operation == 2:
                registers[destination] = registers[source]
            else:
                registers = [UNKNOWN] * 8
                channel_values = {index: {} for index in range(4)}
            offset += 2
            continue
        if instruction & 0xF800 == 0x6000:
            immediate = ((instruction >> 6) & 0x1F) * 4
            base_register = (instruction >> 3) & 7
            value_register = instruction & 7
            base, base_dynamic = registers[base_register]
            value = registers[value_register]
            target = base + immediate
            if not base_dynamic and DMA_BASE <= target < DMA_END:
                channel, channel_base = _channel(target)
                relative = target - channel_base
                if relative in (0, 4, 8):
                    channel_values[channel][relative] = value
                    if relative == 8:
                        snapshot = channel_values[channel]
                        source = snapshot.get(0, UNKNOWN)
                        destination = snapshot.get(4, UNKNOWN)
                        control = snapshot.get(8, UNKNOWN)
                        transfers.append(
                            {
                                "control_write": _addr(address),
                                "dma_channel": f"DMA{channel}",
                                "source": (
                                    None
                                    if source[1]
                                    else _addr(source[0])
                                ),
                                "destination": (
                                    None
                                    if destination[1]
                                    else _addr(destination[0])
                                ),
                                "control": (
                                    None
                                    if control[1]
                                    else _addr(control[0])
                                ),
                            }
                        )
                        channel_values[channel] = {}
            offset += 2
            continue
        if instruction & 0xF800 == 0x8000:
            immediate = ((instruction >> 6) & 0x1F) * 2
            base_register = (instruction >> 3) & 7
            value_register = instruction & 7
            base, base_dynamic = registers[base_register]
            value = registers[value_register]
            target = base + immediate
            if (
                not base_dynamic
                and DMA_BASE <= target
                and target + 2 <= DMA_END
            ):
                channel, channel_base = _channel(target)
                relative = target - channel_base
                if relative in (0, 2, 4, 6):
                    channel_values[channel].pop(relative & ~3, None)
                elif relative == 8:
                    channel_values[channel][8] = (
                        value[0] & 0xFFFF,
                        value[1],
                    )
                elif relative == 10:
                    snapshot = channel_values[channel]
                    source = snapshot.get(0, UNKNOWN)
                    destination = snapshot.get(4, UNKNOWN)
                    count = snapshot.get(8, UNKNOWN)
                    control = (
                        ((value[0] & 0xFFFF) << 16)
                        | (count[0] & 0xFFFF),
                        value[1] or count[1],
                    )
                    transfers.append(
                        {
                            "control_write": _addr(address),
                            "dma_channel": f"DMA{channel}",
                            "source": (
                                None if source[1] else _addr(source[0])
                            ),
                            "destination": (
                                None
                                if destination[1]
                                else _addr(destination[0])
                            ),
                            "control": (
                                None
                                if control[1]
                                else _addr(control[0])
                            ),
                        }
                    )
                    channel_values[channel] = {}
            offset += 2
            continue
        if instruction & 0xF800 == 0xF000 and offset + 4 <= end:
            registers[:4] = [UNKNOWN] * 4
            channel_values = {index: {} for index in range(4)}
            offset += 4
            continue

        registers = [UNKNOWN] * 8
        channel_values = {index: {} for index in range(4)}
        offset += 2

    reasons: set[str] = set()
    if not transfers:
        reasons.update(("no_complete_transfer", "control_not_proven"))
    for transfer in transfers:
        source = transfer["source"]
        destination = transfer["destination"]
        control = transfer["control"]
        if source is None or not (
            ROM_BASE <= int(source, 16) < ROM_BASE + len(rom)
        ):
            reasons.add("source_not_rom")
        if destination is None or _gpu_domain(int(destination, 16)) is None:
            reasons.add("destination_not_gpu")
        if control is None or _control_size(int(control, 16)) is None:
            reasons.add("control_not_proven")
    return transfers, sorted(reasons)


def _literal_users(rom: bytes) -> list[dict[str, Any]]:
    users = []
    for offset in range(0, len(rom) - 3, 2):
        literal = _literal_value(rom, offset)
        if literal is None or not DMA_BASE <= literal[2] < DMA_END:
            continue
        register, literal_address, value = literal
        channel, _ = _channel(value)
        transfers, reasons = _scan_user(rom, offset)
        accepted = []
        for transfer in transfers:
            if (
                transfer["source"] is None
                or transfer["destination"] is None
                or transfer["control"] is None
            ):
                continue
            source = int(transfer["source"], 16)
            destination = int(transfer["destination"], 16)
            control = int(transfer["control"], 16)
            size = _control_size(control)
            domain = _gpu_domain(destination)
            if (
                ROM_BASE <= source < ROM_BASE + len(rom)
                and domain is not None
                and size is not None
                and source + size <= ROM_BASE + len(rom)
            ):
                accepted.append(
                    {
                        **transfer,
                        "copy_size": size,
                        "destination_domain": domain,
                    }
                )
        users.append(
            {
                "instruction_address": _addr(ROM_BASE + offset),
                "instruction_halfword": f"0x{struct.unpack_from('<H', rom, offset)[0]:04X}",
                "destination_register": register,
                "literal_address": _addr(literal_address),
                "literal_value": _addr(value),
                "dma_channel": f"DMA{channel}",
                "register_offset": value - (DMA_BASE + channel * DMA_STRIDE),
                "window_size": min(WINDOW_BYTES, len(rom) - offset),
                "window_sha256": _sha(
                    rom[offset : min(len(rom), offset + WINDOW_BYTES)]
                ),
                "observed_control_writes": transfers,
                "rejection_reasons": reasons,
                "status": (
                    "constant_rom_gpu"
                    if accepted
                    else "not_proven_in_window"
                ),
                "accepted_transfers": accepted,
            }
        )
    return users


def _build(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM changed")
    users = _literal_users(rom)
    accepted = [
        transfer
        for user in users
        for transfer in user["accepted_transfers"]
    ]
    reason_counts = {
        reason: sum(
            reason in user["rejection_reasons"] for user in users
        )
        for reason in (
            "source_not_rom",
            "destination_not_gpu",
            "no_complete_transfer",
            "control_not_proven",
        )
    }
    summary = {
        "dma_register_literal_user_count": len(users),
        **{
            f"dma{channel}_literal_user_count": sum(
                user["dma_channel"] == f"DMA{channel}" for user in users
            )
            for channel in range(4)
        },
        "constant_rom_gpu_transfer_count": len(accepted),
        "not_proven_in_window_count": sum(
            user["status"] == "not_proven_in_window" for user in users
        ),
        "new_source_count": len(
            {transfer["source"] for transfer in accepted}
        ),
    }
    expected = {
        "dma_register_literal_user_count": 21,
        "dma0_literal_user_count": 2,
        "dma1_literal_user_count": 7,
        "dma2_literal_user_count": 2,
        "dma3_literal_user_count": 10,
        "constant_rom_gpu_transfer_count": 0,
        "not_proven_in_window_count": 21,
        "new_source_count": 0,
    }
    if summary != expected:
        raise ValueError(f"direct DMA denominator changed: {summary}")
    implementation = {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_direct_dma_gpu_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_direct_dma_gpu_inventory.py").read_bytes()
        ),
    }
    payload = {
        "schema": SCHEMA,
        "implementation": implementation,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "selection_rule": SELECTION_RULE,
        "summary": summary,
        "rejection_reason_counts": reason_counts,
        "literal_users": users,
        "constant_rom_gpu_transfers": accepted,
        "scope": SCOPE,
    }
    files = {
        PAYLOAD_NAME: (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode()
    }
    return payload, files


def _manifest(
    payload: dict[str, Any], files: dict[str, bytes]
) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_direct_dma_gpu_inventory.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_direct_dma_gpu_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                "dma_register_literal_user_count": payload["summary"][
                    "dma_register_literal_user_count"
                ],
                "constant_rom_gpu_transfer_count": payload["summary"][
                    "constant_rom_gpu_transfer_count"
                ],
            },
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    target = output.expanduser().resolve()
    if output.is_symlink() or target == root or target in root.parents:
        raise ValueError("output directory is unsafe")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("refusing to replace foreign output")
    try:
        manifest = json.loads(
            (target / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    actual = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    if (
        any(path.is_symlink() for path in target.rglob("*"))
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or actual != set(manifest.get("files", {})) | {"manifest.json"}
    ):
        raise ValueError("refusing to replace foreign output")
    for name, expected in manifest["files"].items():
        if _sha((target / name).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup = None
    try:
        for name, data in files.items():
            (temporary / name).write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists():
            if not output.exists():
                backup.rename(output)
            else:
                shutil.rmtree(backup)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    target = _validate_output(root, output)
    payload, files = _build(root)
    _replace(target, files, _manifest(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
