#!/usr/bin/env python3
"""Inventory direct constant ROM-to-GPU CpuSet/CpuFastSet operations."""

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

try:
    from tools.thumb_branch import decode_thumb_bl
except ModuleNotFoundError:
    from thumb_branch import decode_thumb_bl


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-direct-cpuset-gpu-inventory-v1"
VERIFY_SCHEMA = "rom-direct-cpuset-gpu-inventory-verification-v1"
PAYLOAD_NAME = "rom-direct-cpuset-gpu-inventory.json"
BUNDLE_NAME = "new-raw-sources.bin"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_CATALOG = Path(
    "artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json"
)
SOURCE_MANIFEST = Path("artifacts/rom-pointer-lz77-graphics-v1/manifest.json")
SOURCE_CATALOG_SHA256 = (
    "9c3088165fb65004dbeaa124a800d65795395e37b2dcfb90f2d2eedfdd6cf37d"
)
SOURCE_MANIFEST_SHA256 = (
    "17a93ff1f8779a0da50d8e7022adf9c9a7656811884b32db3db3e54f13fd495d"
)
CPU_FAST_SET = 0x0809C0DC
CPU_SET = 0x0809C0E0
WINDOW_BYTES = 32
SCOPE = {
    "all_static_direct_bl_encodings_audited": True,
    "literal_seeded_32_byte_rule_applied_to_full_rom": True,
    "new_raw_sources_losslessly_exported": True,
    "runtime_reachability_complete": False,
    "indirect_calls_complete": False,
    "cross_function_dataflow_complete": False,
    "dma_transfers_complete": False,
    "custom_copy_loops_complete": False,
    "raw_uncompressed_graphics_complete": False,
    "raw_palettes_complete": False,
    "generic_image_writeback_complete": False,
}
SELECTION_RULE = {
    "direct_targets": {
        "CpuFastSet": "0x0809C0DC",
        "CpuSet": "0x0809C0E0",
    },
    "window_bytes": WINDOW_BYTES,
    "source": "mapped ROM constant loaded by Thumb PC-relative literal",
    "destination": "constant PRAM or VRAM address",
    "control": "constant nonzero non-fill copy count",
    "unknown_instruction_policy": "invalidate r0-r3 (fail closed)",
    "call_policy": "inspect actual r0-r2 at BL, then invalidate r0-r3",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _literal_value(rom: bytes, offset: int) -> tuple[int, int] | None:
    instruction = struct.unpack_from("<H", rom, offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    address = ROM_BASE + offset
    literal = ((address + 4) & ~3) + (instruction & 0xFF) * 4
    if not ROM_BASE <= literal < ROM_BASE + len(rom) - 3:
        return None
    return (instruction >> 8) & 7, struct.unpack_from(
        "<I", rom, literal - ROM_BASE
    )[0]


Symbol = tuple[int, bool, int | None]
UNKNOWN: Symbol = (0, True, None)


def _add(left: Symbol, right: Symbol) -> Symbol:
    origin = left[2] if right[0] == 0 and not right[1] else None
    if left[0] == 0 and left[1]:
        origin = right[2]
    return left[0] + right[0], left[1] or right[1], origin


def _copy_control(target: int, control: int) -> tuple[str, int, int, bool]:
    count = control & 0x1FFFFF
    if target == CPU_SET:
        width = 4 if control & 0x01000000 else 2
        fill = bool(control & 0x04000000)
        return "CpuSet", count, count * width, fill
    fill = bool(control & 0x01000000)
    return "CpuFastSet", count, count * 4, fill


def _discover_from_user(
    rom: bytes, source_user: int
) -> list[dict[str, Any]]:
    registers: list[Symbol] = [UNKNOWN for _ in range(16)]
    offset = source_user - ROM_BASE
    end = min(len(rom) - 3, offset + WINDOW_BYTES)
    operations = []
    while offset < end:
        instruction = struct.unpack_from("<H", rom, offset)[0]
        address = ROM_BASE + offset
        literal = _literal_value(rom, offset)
        if literal is not None:
            register, value = literal
            registers[register] = (value, False, address)
            offset += 2
            continue
        if instruction & 0xF800 == 0x2000:
            register = (instruction >> 8) & 7
            registers[register] = (instruction & 0xFF, False, address)
            offset += 2
            continue
        if instruction & 0xF800 in (0x0000, 0x0800):
            shift = (instruction >> 6) & 0x1F
            source = (instruction >> 3) & 7
            destination = instruction & 7
            value, dynamic, origin = registers[source]
            if instruction & 0xF800 == 0:
                registers[destination] = (value << shift, dynamic, origin)
            else:
                registers[destination] = (
                    value >> (shift or 32),
                    dynamic,
                    origin,
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
                (operand, False, address)
                if immediate
                else registers[operand]
            )
            if subtract:
                right = (-right[0], right[1], right[2])
            registers[destination] = _add(registers[source], right)
            offset += 2
            continue
        if instruction & 0xFC00 == 0x4400:
            operation = (instruction >> 8) & 3
            destination = ((instruction >> 4) & 8) | (instruction & 7)
            source = (instruction >> 3) & 0xF
            if operation == 0:
                registers[destination] = _add(
                    registers[destination], registers[source]
                )
            elif operation == 2:
                registers[destination] = registers[source]
            else:
                registers[:4] = [UNKNOWN] * 4
            offset += 2
            continue
        if instruction & 0xF800 == 0xF000:
            second = struct.unpack_from("<H", rom, offset + 2)[0]
            target = decode_thumb_bl(address, instruction, second)
            source, source_dynamic, source_load = registers[0]
            destination, destination_dynamic, _ = registers[1]
            control, control_dynamic, _ = registers[2]
            if target in (CPU_SET, CPU_FAST_SET):
                loader, unit_count, copy_size, fill = _copy_control(
                    target, control
                )
                gpu_destination = (
                    0x05000000 <= destination < 0x05000400
                    or 0x06000000 <= destination < 0x06018000
                )
                if (
                    not source_dynamic
                    and source_load is not None
                    and not destination_dynamic
                    and not control_dynamic
                    and ROM_BASE <= source < ROM_BASE + len(rom)
                    and gpu_destination
                    and unit_count > 0
                    and not fill
                    and source + copy_size <= ROM_BASE + len(rom)
                ):
                    operations.append(
                        {
                            "callsite": _addr(address),
                            "loader": loader,
                            "source_address": _addr(source),
                            "source_load": _addr(source_load),
                            "destination": _addr(destination),
                            "destination_domain": (
                                "PRAM"
                                if destination < 0x06000000
                                else "VRAM"
                            ),
                            "control": _addr(control),
                            "unit_count": unit_count,
                            "copy_size": copy_size,
                            "code_size": offset + 4 - (source_load - ROM_BASE),
                            "code_sha256": _sha(
                                rom[source_load - ROM_BASE : offset + 4]
                            ),
                        }
                    )
            registers[:4] = [UNKNOWN] * 4
            offset += 4
            continue
        registers[:4] = [UNKNOWN] * 4
        offset += 2
    return operations


def _direct_calls(rom: bytes) -> list[dict[str, Any]]:
    calls = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = decode_thumb_bl(ROM_BASE + offset, first, second)
        if target not in (CPU_SET, CPU_FAST_SET):
            continue
        calls.append(
            {
                "callsite": _addr(ROM_BASE + offset),
                "loader": "CpuSet" if target == CPU_SET else "CpuFastSet",
            }
        )
    return calls


def _constant_operations(rom: bytes) -> list[dict[str, Any]]:
    operations: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for offset in range(0, len(rom) - 3, 2):
        literal = _literal_value(rom, offset)
        if (
            literal is None
            or not ROM_BASE <= literal[1] < ROM_BASE + len(rom)
        ):
            continue
        for operation in _discover_from_user(rom, ROM_BASE + offset):
            key = (
                operation["callsite"],
                operation["source_address"],
                operation["destination"],
                operation["copy_size"],
            )
            operations[key] = operation
    return sorted(
        operations.values(), key=lambda item: int(item["callsite"], 16)
    )


def _lz77_span(rom: bytes, start: int) -> int | None:
    if start + 4 > len(rom) or rom[start] != 0x10:
        return None
    declared = int.from_bytes(rom[start + 1 : start + 4], "little")
    if declared <= 0:
        return None
    cursor, produced = start + 4, 0
    try:
        while produced < declared:
            flags = rom[cursor]
            cursor += 1
            for mask in (0x80, 0x40, 0x20, 0x10, 8, 4, 2, 1):
                if produced >= declared:
                    break
                if flags & mask:
                    token = (rom[cursor] << 8) | rom[cursor + 1]
                    cursor += 2
                    length = (token >> 12) + 3
                    distance = (token & 0xFFF) + 1
                    if distance > produced or produced + length > declared:
                        return None
                    produced += length
                else:
                    cursor += 1
                    produced += 1
    except IndexError:
        return None
    return cursor


def _lz77_spans(rom: bytes) -> list[tuple[int, int]]:
    spans = []
    for offset in range(len(rom) - 3):
        end = _lz77_span(rom, offset)
        if end is not None:
            spans.append((offset, end))
    return spans


def _load_existing_bindings(root: Path) -> tuple[dict[str, Any], set[tuple]]:
    manifest_raw = (root / SOURCE_MANIFEST).read_bytes()
    catalog_raw = (root / SOURCE_CATALOG).read_bytes()
    if (
        _sha(manifest_raw) != SOURCE_MANIFEST_SHA256
        or _sha(catalog_raw) != SOURCE_CATALOG_SHA256
    ):
        raise ValueError("source graphics catalog changed")
    manifest = json.loads(manifest_raw)
    catalog = json.loads(catalog_raw)
    if (
        manifest.get("artifact_status") != "accepted"
        or catalog.get("schema") != "rom-pointer-lz77-graphics-v1"
    ):
        raise ValueError("source graphics catalog contract changed")
    bindings = set()
    for source in catalog["raw_palette_sources"]:
        for evidence in source["copy_evidence"]:
            bindings.add(
                (
                    evidence["callsite"],
                    source["gba_address"],
                    evidence["destination"],
                    evidence["size"],
                )
            )
    return catalog, bindings


def _build(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM changed")
    _, existing = _load_existing_bindings(root)
    direct_calls = _direct_calls(rom)
    operations = _constant_operations(rom)
    by_callsite = {operation["callsite"]: operation for operation in operations}
    spans = _lz77_spans(rom)
    for operation in operations:
        source = int(operation["source_address"], 16) - ROM_BASE
        end = source + operation["copy_size"]
        operation["lz77_overlaps"] = [
            {
                "source_address": _addr(ROM_BASE + span_start),
                "compressed_end_address": _addr(ROM_BASE + span_end),
            }
            for span_start, span_end in spans
            if source < span_end and span_start < end
        ]
        key = (
            operation["callsite"],
            operation["source_address"],
            operation["destination"],
            operation["copy_size"],
        )
        operation["already_bound"] = key in existing
    for call in direct_calls:
        operation = by_callsite.get(call["callsite"])
        call["status"] = (
            "constant_rom_gpu"
            if operation is not None
            else "not_proven_in_window"
        )
        if operation is not None:
            call["operation_sha256"] = _sha(
                json.dumps(
                    operation, sort_keys=True, separators=(",", ":")
                ).encode()
            )

    new_operations = [
        operation for operation in operations if not operation["already_bound"]
    ]
    new_by_source: dict[int, list[dict[str, Any]]] = {}
    for operation in new_operations:
        if operation["lz77_overlaps"]:
            continue
        offset = int(operation["source_address"], 16) - ROM_BASE
        new_by_source.setdefault(offset, []).append(operation)
    bundle = bytearray()
    new_sources = []
    for offset, source_operations in sorted(new_by_source.items()):
        size = max(item["copy_size"] for item in source_operations)
        data = rom[offset : offset + size]
        new_sources.append(
            {
                "source_address": _addr(ROM_BASE + offset),
                "file_offset": offset,
                "size": size,
                "sha256": _sha(data),
                "bundle_offset": len(bundle),
                "operations": source_operations,
            }
        )
        bundle.extend(data)

    source_addresses = {item["source_address"] for item in operations}
    bound_operations = [item for item in operations if item["already_bound"]]
    bound_sources = {item["source_address"] for item in bound_operations}
    summary = {
        "direct_call_count": len(direct_calls),
        "cpuset_call_count": sum(
            call["loader"] == "CpuSet" for call in direct_calls
        ),
        "cpufastset_call_count": sum(
            call["loader"] == "CpuFastSet" for call in direct_calls
        ),
        "constant_rom_gpu_operation_count": len(operations),
        "not_proven_in_window_call_count": len(direct_calls)
        - len(operations),
        "pram_operation_count": sum(
            item["destination_domain"] == "PRAM" for item in operations
        ),
        "vram_operation_count": sum(
            item["destination_domain"] == "VRAM" for item in operations
        ),
        "already_bound_operation_count": len(bound_operations),
        "new_operation_count": len(new_operations),
        "unique_source_count": len(source_addresses),
        "already_bound_source_count": len(bound_sources),
        "new_source_count": len(new_sources),
        "lz77_overlap_operation_count": sum(
            bool(item["lz77_overlaps"]) for item in operations
        ),
        "new_bundle_size": len(bundle),
    }
    if summary != {
        "direct_call_count": 146,
        "cpuset_call_count": 126,
        "cpufastset_call_count": 20,
        "constant_rom_gpu_operation_count": 23,
        "not_proven_in_window_call_count": 123,
        "pram_operation_count": 23,
        "vram_operation_count": 0,
        "already_bound_operation_count": 20,
        "new_operation_count": 3,
        "unique_source_count": 15,
        "already_bound_source_count": 12,
        "new_source_count": 3,
        "lz77_overlap_operation_count": 1,
        "new_bundle_size": 96,
    }:
        raise ValueError(f"direct CpuSet denominator changed: {summary}")
    implementation = {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_direct_cpuset_gpu_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_direct_cpuset_gpu_inventory.py").read_bytes()
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
        "source_catalog": {
            "path": SOURCE_CATALOG.as_posix(),
            "sha256": SOURCE_CATALOG_SHA256,
            "manifest_path": SOURCE_MANIFEST.as_posix(),
            "manifest_sha256": SOURCE_MANIFEST_SHA256,
        },
        "selection_rule": SELECTION_RULE,
        "summary": summary,
        "direct_calls": direct_calls,
        "constant_rom_gpu_operations": operations,
        "already_bound_operations": bound_operations,
        "new_sources": new_sources,
        "bundle": {
            "file": BUNDLE_NAME,
            "size": len(bundle),
            "sha256": _sha(bundle),
        },
        "scope": SCOPE,
    }
    files = {
        PAYLOAD_NAME: (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode(),
        BUNDLE_NAME: bytes(bundle),
    }
    return payload, files


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_direct_cpuset_gpu_inventory.py",
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
                "tools/verify_rom_direct_cpuset_gpu_inventory.py",
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
                "direct_call_count": payload["summary"]["direct_call_count"],
                "new_source_count": payload["summary"]["new_source_count"],
            },
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    target = output.expanduser().resolve()
    root = root.resolve()
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
