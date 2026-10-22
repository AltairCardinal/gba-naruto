#!/usr/bin/env python3
"""Independently verify the direct DMA-register literal-user inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


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
EXPECTED_SCOPE = {
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
EXPECTED_SELECTION_RULE = {
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


def _literal(
    rom: bytes, offset: int
) -> tuple[int, int, int] | None:
    instruction = struct.unpack_from("<H", rom, offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    instruction_address = ROM_BASE + offset
    literal_address = (
        ((instruction_address + 4) & ~3) + (instruction & 0xFF) * 4
    )
    literal_offset = literal_address - ROM_BASE
    if literal_offset < 0 or literal_offset + 4 > len(rom):
        return None
    return (
        (instruction >> 8) & 7,
        literal_address,
        struct.unpack_from("<I", rom, literal_offset)[0],
    )


def _channel(address: int) -> tuple[int, int]:
    index = (address - DMA_BASE) // DMA_STRIDE
    return index, DMA_BASE + index * DMA_STRIDE


def _plus(left: Symbol, right: Symbol) -> Symbol:
    return left[0] + right[0], left[1] or right[1]


def _gpu_domain(address: int) -> str | None:
    if 0x05000000 <= address < 0x05000400:
        return "PRAM"
    if 0x06000000 <= address < 0x06018000:
        return "VRAM"
    if 0x07000000 <= address < 0x07000400:
        return "OAM"
    return None


def _transfer_size(control: int) -> int | None:
    count = control & 0xFFFF
    if not control & 0x80000000 or count == 0:
        return None
    return count * (4 if control & 0x04000000 else 2)


def _scan(
    rom: bytes, start: int
) -> tuple[list[dict[str, Any]], list[str]]:
    registers: list[Symbol] = [UNKNOWN] * 8
    slots: dict[int, dict[int, Symbol]] = {
        index: {} for index in range(4)
    }
    transfers: list[dict[str, Any]] = []
    offset = start
    end = min(len(rom) - 1, start + WINDOW_BYTES)
    while offset + 2 <= end:
        instruction = struct.unpack_from("<H", rom, offset)[0]
        address = ROM_BASE + offset
        literal = _literal(rom, offset)
        if literal is not None:
            registers[literal[0]] = (literal[2], False)
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
            registers[destination] = (
                value << shift
                if instruction & 0xF800 == 0
                else value >> (shift or 32),
                dynamic,
            )
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
            registers[destination] = _plus(registers[source], right)
            offset += 2
            continue
        if instruction & 0xFC00 == 0x4400:
            operation = (instruction >> 8) & 3
            destination = ((instruction >> 4) & 8) | (instruction & 7)
            source = (instruction >> 3) & 0xF
            if destination < 8 and source < 8 and operation == 0:
                registers[destination] = _plus(
                    registers[destination], registers[source]
                )
            elif destination < 8 and source < 8 and operation == 2:
                registers[destination] = registers[source]
            else:
                registers = [UNKNOWN] * 8
                slots = {index: {} for index in range(4)}
            offset += 2
            continue
        if instruction & 0xF800 == 0x6000:
            immediate = ((instruction >> 6) & 0x1F) * 4
            base_register = (instruction >> 3) & 7
            value_register = instruction & 7
            base, base_dynamic = registers[base_register]
            target = base + immediate
            if not base_dynamic and DMA_BASE <= target < DMA_END:
                index, channel_base = _channel(target)
                relative = target - channel_base
                if relative in (0, 4, 8):
                    slots[index][relative] = registers[value_register]
                    if relative == 8:
                        snapshot = slots[index]
                        source = snapshot.get(0, UNKNOWN)
                        destination = snapshot.get(4, UNKNOWN)
                        control = snapshot.get(8, UNKNOWN)
                        transfers.append(
                            {
                                "control_write": _addr(address),
                                "dma_channel": f"DMA{index}",
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
                        slots[index] = {}
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
                index, channel_base = _channel(target)
                relative = target - channel_base
                if relative in (0, 2, 4, 6):
                    slots[index].pop(relative & ~3, None)
                elif relative == 8:
                    slots[index][8] = (
                        value[0] & 0xFFFF,
                        value[1],
                    )
                elif relative == 10:
                    snapshot = slots[index]
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
                            "dma_channel": f"DMA{index}",
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
                    slots[index] = {}
            offset += 2
            continue
        if instruction & 0xF800 == 0xF000 and offset + 4 <= end:
            registers[:4] = [UNKNOWN] * 4
            slots = {index: {} for index in range(4)}
            offset += 4
            continue
        registers = [UNKNOWN] * 8
        slots = {index: {} for index in range(4)}
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
        if control is None or _transfer_size(int(control, 16)) is None:
            reasons.add("control_not_proven")
    return transfers, sorted(reasons)


def _rebuild_users(rom: bytes) -> list[dict[str, Any]]:
    output = []
    for offset in range(0, len(rom) - 3, 2):
        literal = _literal(rom, offset)
        if literal is None or not DMA_BASE <= literal[2] < DMA_END:
            continue
        register, literal_address, value = literal
        channel, channel_base = _channel(value)
        transfers, reasons = _scan(rom, offset)
        accepted = []
        for transfer in transfers:
            if any(
                transfer[key] is None
                for key in ("source", "destination", "control")
            ):
                continue
            source = int(transfer["source"], 16)
            destination = int(transfer["destination"], 16)
            control = int(transfer["control"], 16)
            size = _transfer_size(control)
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
        output.append(
            {
                "instruction_address": _addr(ROM_BASE + offset),
                "instruction_halfword": f"0x{struct.unpack_from('<H', rom, offset)[0]:04X}",
                "destination_register": register,
                "literal_address": _addr(literal_address),
                "literal_value": _addr(value),
                "dma_channel": f"DMA{channel}",
                "register_offset": value - channel_base,
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
    return output


def _load_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"{label}: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label}: not an object")
        return {}
    return value


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact_dir = artifact_dir.resolve()
    errors: list[str] = []
    if (
        artifact_dir == root
        or artifact_dir in root.parents
        or artifact_dir.is_symlink()
    ):
        errors.append("artifact directory is unsafe")
    manifest = _load_json(
        artifact_dir / "manifest.json", errors, "manifest"
    )
    payload = _load_json(
        artifact_dir / PAYLOAD_NAME, errors, PAYLOAD_NAME
    )
    actual_files = {
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file()
    } if artifact_dir.is_dir() else set()
    expected_files = set(manifest.get("files", {})) | {"manifest.json"}
    if actual_files != expected_files:
        errors.append("artifact file set mismatch")
    for name, expected in manifest.get("files", {}).items():
        path = artifact_dir / name
        if not path.is_file() or _sha(path.read_bytes()) != expected:
            errors.append(f"{name}: manifest hash mismatch")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
    ):
        errors.append("manifest contract mismatch")
    if manifest.get("scope") != EXPECTED_SCOPE:
        errors.append("manifest scope mismatch")

    try:
        rom = (root / ROM_PATH).read_bytes()
    except OSError as error:
        errors.append(f"ROM: {error}")
        rom = b""
    if _sha(rom) != ROM_SHA256:
        errors.append("ROM hash mismatch")
    rebuilt = _rebuild_users(rom) if rom else []
    accepted = [
        transfer
        for user in rebuilt
        for transfer in user["accepted_transfers"]
    ]
    expected_summary = {
        "dma_register_literal_user_count": len(rebuilt),
        **{
            f"dma{channel}_literal_user_count": sum(
                row["dma_channel"] == f"DMA{channel}" for row in rebuilt
            )
            for channel in range(4)
        },
        "constant_rom_gpu_transfer_count": len(accepted),
        "not_proven_in_window_count": sum(
            row["status"] == "not_proven_in_window" for row in rebuilt
        ),
        "new_source_count": len(
            {transfer["source"] for transfer in accepted}
        ),
    }
    expected_reasons = {
        reason: sum(reason in row["rejection_reasons"] for row in rebuilt)
        for reason in (
            "source_not_rom",
            "destination_not_gpu",
            "no_complete_transfer",
            "control_not_proven",
        )
    }
    if payload.get("schema") != SCHEMA:
        errors.append("payload schema mismatch")
    if payload.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }:
        errors.append("payload ROM contract mismatch")
    if payload.get("selection_rule") != EXPECTED_SELECTION_RULE:
        errors.append("selection rule mismatch")
    if payload.get("scope") != EXPECTED_SCOPE:
        errors.append("payload scope mismatch")
    if payload.get("summary") != expected_summary:
        errors.append("summary mismatch")
    if payload.get("rejection_reason_counts") != expected_reasons:
        errors.append("rejection reason counts mismatch")
    if payload.get("literal_users") != rebuilt:
        errors.append("literal user reconstruction mismatch")
    if payload.get("constant_rom_gpu_transfers") != accepted:
        errors.append("accepted transfer reconstruction mismatch")

    implementation = payload.get("implementation", {})
    expected_implementation = {
        "exporter_sha256": _sha(
            (
                root / "tools/export_rom_direct_dma_gpu_inventory.py"
            ).read_bytes()
        ),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha(
            (
                root / "tests/test_export_rom_direct_dma_gpu_inventory.py"
            ).read_bytes()
        ),
    }
    if implementation != expected_implementation:
        errors.append("implementation hash mismatch")
    producer = manifest.get("producer", {})
    if any(
        producer.get(name) != value
        for name, value in expected_implementation.items()
    ):
        errors.append("manifest producer hash mismatch")
    verifier = manifest.get("verifier", {})
    if (
        verifier.get("verifier_sha256")
        != expected_implementation["verifier_sha256"]
        or verifier.get("exit_code") != 0
        or verifier.get("report")
        != {
            "schema": VERIFY_SCHEMA,
            "verified": True,
            "errors": [],
            "dma_register_literal_user_count": expected_summary[
                "dma_register_literal_user_count"
            ],
            "constant_rom_gpu_transfer_count": expected_summary[
                "constant_rom_gpu_transfer_count"
            ],
        }
    ):
        errors.append("manifest verifier contract mismatch")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "dma_register_literal_user_count": len(rebuilt),
        "constant_rom_gpu_transfer_count": len(accepted),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    artifact_dir = args.artifact_dir
    if not artifact_dir.is_absolute():
        artifact_dir = args.root / artifact_dir
    report = verify_artifact(args.root, artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
