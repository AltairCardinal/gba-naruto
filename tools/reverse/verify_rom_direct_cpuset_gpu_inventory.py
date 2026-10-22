#!/usr/bin/env python3
"""Verify direct CpuSet GPU claims from callsites back to their inputs.

The exporter discovers calls by starting at ROM literals and executing forward.
This verifier deliberately starts from every direct CpuSet/CpuFastSet BL and
matches the immediately preceding argument-definition slice backwards.  The two
directions do not share a symbolic executor or candidate-generation path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Iterator


SCHEMA = "rom-direct-cpuset-gpu-inventory-v1"
VERIFY_SCHEMA = "rom-direct-cpuset-gpu-inventory-verification-v1"
PAYLOAD_NAME = "rom-direct-cpuset-gpu-inventory.json"
BUNDLE_NAME = "new-raw-sources.bin"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
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
EXPECTED_SUMMARY = {
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
}
EXPECTED_NEW_SOURCES = {
    0x3F1E60: ("0x0808BC06", "0x05000120"),
    0x3F1F08: ("0x0808BC26", "0x05000140"),
    0x406010: ("0x0808C260", "0x05000200"),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _decode_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _literal_value(rom: bytes, offset: int, register: int) -> int | None:
    instruction = struct.unpack_from("<H", rom, offset)[0]
    if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != register:
        return None
    literal = ((ROM_BASE + offset + 4) & ~3) + (instruction & 0xFF) * 4
    literal_offset = literal - ROM_BASE
    if not 0 <= literal_offset <= len(rom) - 4:
        return None
    return struct.unpack_from("<I", rom, literal_offset)[0]


def _movs_immediate(instruction: int, register: int) -> int | None:
    if instruction & 0xF800 != 0x2000 or (instruction >> 8) & 7 != register:
        return None
    return instruction & 0xFF


def _is_lsl_immediate(
    instruction: int, destination: int, source: int, shift: int
) -> bool:
    return (
        instruction & 0xF800 == 0
        and instruction & 7 == destination
        and (instruction >> 3) & 7 == source
        and (instruction >> 6) & 0x1F == shift
    )


def _is_add_register(
    instruction: int, destination: int, left: int, right: int
) -> bool:
    return (
        instruction & 0xFE00 == 0x1800
        and instruction & 7 == destination
        and (instruction >> 3) & 7 == left
        and (instruction >> 6) & 7 == right
    )


def _decode_control(target: int, control: int) -> tuple[str, int, int, bool]:
    count = control & 0x1FFFFF
    if target == CPU_SET:
        width = 4 if control & 0x01000000 else 2
        return "CpuSet", count, count * width, bool(control & 0x04000000)
    return "CpuFastSet", count, count * 4, bool(control & 0x01000000)


def _iter_direct_cpuset_calls(rom: bytes) -> Iterator[dict[str, Any]]:
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_bl(ROM_BASE + offset, first, second)
        if target not in (CPU_SET, CPU_FAST_SET):
            continue
        yield {
            "offset": offset,
            "callsite": _addr(ROM_BASE + offset),
            "loader": "CpuSet" if target == CPU_SET else "CpuFastSet",
            "target": target,
        }


def _resolve_call_inputs_backward(
    rom: bytes, call: dict[str, Any]
) -> dict[str, Any] | None:
    """Resolve the two observed local definition shapes immediately before BL."""

    call_offset = call["offset"]
    target = call["target"]
    if call_offset < 12:
        return None

    short_start = call_offset - 6
    source = _literal_value(rom, short_start, 0)
    destination = _literal_value(rom, call_offset - 4, 1)
    control = _movs_immediate(
        struct.unpack_from("<H", rom, call_offset - 2)[0], 2
    )
    source_load = short_start

    if source is None or destination is None or control is None:
        long_start = call_offset - 12
        source = _literal_value(rom, long_start, 0)
        seed = _movs_immediate(
            struct.unpack_from("<H", rom, call_offset - 10)[0], 2
        )
        shift_instruction = struct.unpack_from("<H", rom, call_offset - 8)[0]
        destination_base = _literal_value(rom, call_offset - 6, 2)
        add_instruction = struct.unpack_from("<H", rom, call_offset - 4)[0]
        control = _movs_immediate(
            struct.unpack_from("<H", rom, call_offset - 2)[0], 2
        )
        if (
            source is None
            or seed is None
            or destination_base is None
            or control is None
            or not _is_lsl_immediate(shift_instruction, 1, 2, 5)
            or not _is_add_register(add_instruction, 1, 1, 2)
        ):
            return None
        destination = destination_base + (seed << 5)
        source_load = long_start

    loader, unit_count, copy_size, fill = _decode_control(target, control)
    gpu_destination = (
        0x05000000 <= destination < 0x05000400
        or 0x06000000 <= destination < 0x06018000
    )
    if (
        not ROM_BASE <= source < ROM_BASE + len(rom)
        or not gpu_destination
        or unit_count <= 0
        or fill
        or source + copy_size > ROM_BASE + len(rom)
    ):
        return None
    raw_code = rom[source_load : call_offset + 4]
    return {
        "callsite": call["callsite"],
        "loader": loader,
        "source_address": _addr(source),
        "source_load": _addr(ROM_BASE + source_load),
        "destination": _addr(destination),
        "destination_domain": "PRAM" if destination < 0x06000000 else "VRAM",
        "control": _addr(control),
        "unit_count": unit_count,
        "copy_size": copy_size,
        "code_size": len(raw_code),
        "code_sha256": _sha(raw_code),
    }


def _lz77_end(rom: bytes, start: int) -> int | None:
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


def _operation_overlap(rom: bytes, operation: dict[str, Any]) -> list[dict[str, str]]:
    if operation["callsite"] != "0x0808BFF4":
        return []
    start = 0x4060A8
    end = _lz77_end(rom, start)
    if (
        end != 0x406550
        or _sha(rom[start:end])
        != "e020e465e3f6718edde08d0208b0b68dccf278c496563ed498eb918d8658edf1"
    ):
        raise ValueError("known CpuSet/LZ77 overlap changed")
    source_start = int(operation["source_address"], 16) - ROM_BASE
    source_end = source_start + operation["copy_size"]
    if not source_start < end or not start < source_end:
        raise ValueError("known CpuSet/LZ77 overlap no longer intersects")
    return [
        {
            "source_address": _addr(ROM_BASE + start),
            "compressed_end_address": _addr(ROM_BASE + end),
        }
    ]


def _load_bindings(root: Path) -> set[tuple[str, str, str, int]]:
    catalog_raw = (root / SOURCE_CATALOG).read_bytes()
    manifest_raw = (root / SOURCE_MANIFEST).read_bytes()
    if _sha(catalog_raw) != SOURCE_CATALOG_SHA256:
        raise ValueError("source catalog hash mismatch")
    if _sha(manifest_raw) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source manifest hash mismatch")
    catalog = json.loads(catalog_raw)
    manifest = json.loads(manifest_raw)
    if catalog.get("schema") != "rom-pointer-lz77-graphics-v1":
        raise ValueError("source catalog schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("source artifact is not accepted")
    bindings = set()
    sources = catalog.get("raw_palette_sources")
    if not isinstance(sources, list) or len(sources) != 12:
        raise ValueError("source catalog raw-palette denominator changed")
    for source in sources:
        for evidence in source["copy_evidence"]:
            bindings.add(
                (
                    evidence["callsite"],
                    source["gba_address"],
                    evidence["destination"],
                    evidence["size"],
                )
            )
    return bindings


def _resolve_operations(
    root: Path, rom: bytes
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    calls = list(_iter_direct_cpuset_calls(rom))
    if len(calls) != 146:
        raise ValueError(f"direct CpuSet call denominator changed: {len(calls)}")
    bindings = _load_bindings(root)
    operations: list[dict[str, Any]] = []
    for call in calls:
        operation = _resolve_call_inputs_backward(rom, call)
        if operation is None:
            continue
        operation["lz77_overlaps"] = _operation_overlap(rom, operation)
        operation["already_bound"] = (
            operation["callsite"],
            operation["source_address"],
            operation["destination"],
            operation["copy_size"],
        ) in bindings
        operations.append(operation)
    if len(operations) != 23:
        raise ValueError(f"constant operation denominator changed: {len(operations)}")
    return calls, operations


def _verify_call_partition(
    claimed: object,
    calls: list[dict[str, Any]],
    operations: list[dict[str, Any]],
) -> None:
    if not isinstance(claimed, list) or len(claimed) != len(calls):
        raise ValueError("direct call partition denominator changed")
    by_callsite = {item["callsite"]: item for item in operations}
    for actual, call in zip(claimed, calls, strict=True):
        expected = {
            "callsite": call["callsite"],
            "loader": call["loader"],
            "status": (
                "constant_rom_gpu"
                if call["callsite"] in by_callsite
                else "not_proven_in_window"
            ),
        }
        operation = by_callsite.get(call["callsite"])
        if operation is not None:
            expected["operation_sha256"] = _sha(
                json.dumps(
                    operation, sort_keys=True, separators=(",", ":")
                ).encode()
            )
        if actual != expected:
            raise ValueError(f"direct call claim changed at {call['callsite']}")


def _verify_new_sources(
    claimed: object,
    bundle: bytes,
    rom: bytes,
    operations: list[dict[str, Any]],
) -> None:
    if not isinstance(claimed, list) or len(claimed) != 3 or len(bundle) != 96:
        raise ValueError("new source denominator changed")
    new_operations = [item for item in operations if not item["already_bound"]]
    if len(new_operations) != 3 or any(item["lz77_overlaps"] for item in new_operations):
        raise ValueError("new operation partition changed")
    by_source = {
        int(item["source_address"], 16) - ROM_BASE: item
        for item in new_operations
    }
    if {
        offset: (item["callsite"], item["destination"])
        for offset, item in by_source.items()
    } != EXPECTED_NEW_SOURCES:
        raise ValueError("new source witness set changed")
    cursor = 0
    for source, operation in sorted(by_source.items()):
        raw = rom[source : source + 32]
        expected = {
            "source_address": _addr(ROM_BASE + source),
            "file_offset": source,
            "size": 32,
            "sha256": _sha(raw),
            "bundle_offset": cursor,
            "operations": [operation],
        }
        item = claimed[cursor // 32]
        if item != expected or bundle[cursor : cursor + 32] != raw:
            raise ValueError(f"new raw source differs from ROM at 0x{source:06X}")
        cursor += 32


def _expected_implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_direct_cpuset_gpu_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_direct_cpuset_gpu_inventory.py").read_bytes()
        ),
    }


def _summary(
    calls: list[dict[str, Any]], operations: list[dict[str, Any]]
) -> dict[str, int]:
    bound = [item for item in operations if item["already_bound"]]
    source_addresses = {item["source_address"] for item in operations}
    bound_sources = {item["source_address"] for item in bound}
    result = {
        "direct_call_count": len(calls),
        "cpuset_call_count": sum(item["loader"] == "CpuSet" for item in calls),
        "cpufastset_call_count": sum(
            item["loader"] == "CpuFastSet" for item in calls
        ),
        "constant_rom_gpu_operation_count": len(operations),
        "not_proven_in_window_call_count": len(calls) - len(operations),
        "pram_operation_count": sum(
            item["destination_domain"] == "PRAM" for item in operations
        ),
        "vram_operation_count": sum(
            item["destination_domain"] == "VRAM" for item in operations
        ),
        "already_bound_operation_count": len(bound),
        "new_operation_count": len(operations) - len(bound),
        "unique_source_count": len(source_addresses),
        "already_bound_source_count": len(bound_sources),
        "new_source_count": 3,
        "lz77_overlap_operation_count": sum(
            bool(item["lz77_overlaps"]) for item in operations
        ),
        "new_bundle_size": 96,
    }
    if result != EXPECTED_SUMMARY:
        raise ValueError(f"independent denominator changed: {result}")
    return result


def _verify_payload_metadata(
    root: Path,
    payload: object,
    payload_raw: bytes,
    bundle: bytes,
    summary: dict[str, int],
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")
    if payload_raw != (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode():
        raise ValueError("payload JSON is not canonical")
    if payload.get("schema") != SCHEMA:
        raise ValueError("payload schema changed")
    if payload.get("implementation") != _expected_implementation(root):
        raise ValueError("payload implementation binding changed")
    if payload.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "size": 6_291_456,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("payload ROM identity changed")
    if payload.get("source_catalog") != {
        "path": SOURCE_CATALOG.as_posix(),
        "sha256": SOURCE_CATALOG_SHA256,
        "manifest_path": SOURCE_MANIFEST.as_posix(),
        "manifest_sha256": SOURCE_MANIFEST_SHA256,
    }:
        raise ValueError("payload source-catalog binding changed")
    if payload.get("selection_rule") != SELECTION_RULE or payload.get("scope") != SCOPE:
        raise ValueError("payload selection rule or scope changed")
    if payload.get("summary") != summary:
        raise ValueError("payload summary changed")
    if payload.get("bundle") != {
        "file": BUNDLE_NAME,
        "size": len(bundle),
        "sha256": _sha(bundle),
    }:
        raise ValueError("payload bundle metadata changed")


def _verify_manifest(
    root: Path,
    manifest: object,
    payload_raw: bytes,
    bundle: bytes,
) -> None:
    implementation = _expected_implementation(root)
    expected = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {BUNDLE_NAME: _sha(bundle), PAYLOAD_NAME: _sha(payload_raw)},
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
            **implementation,
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
            "verifier_sha256": implementation["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                "direct_call_count": 146,
                "new_source_count": 3,
            },
        },
    }
    if manifest != expected:
        raise ValueError("promotion manifest bindings changed")


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    direct_call_count = 0
    new_source_count = 0
    try:
        if not artifact.is_dir() or artifact.is_symlink():
            raise ValueError("artifact is not a safe directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact contains a symbolic link")
        actual_files = {
            member.relative_to(artifact).as_posix()
            for member in members
            if member.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError(f"artifact file set mismatch: {sorted(actual_files)}")

        rom = (root / ROM_PATH).read_bytes()
        if _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM hash mismatch")
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )

        calls, operations = _resolve_operations(root, rom)
        summary = _summary(calls, operations)
        _verify_payload_metadata(root, payload, payload_raw, bundle, summary)
        _verify_call_partition(payload.get("direct_calls"), calls, operations)
        if payload.get("constant_rom_gpu_operations") != operations:
            raise ValueError("operation witnesses differ from backward resolution")
        bound = [item for item in operations if item["already_bound"]]
        if payload.get("already_bound_operations") != bound:
            raise ValueError("existing binding partition changed")
        _verify_new_sources(payload.get("new_sources"), bundle, rom, operations)
        _verify_manifest(root, manifest, payload_raw, bundle)
        direct_call_count = len(calls)
        new_source_count = 3
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "direct_call_count": direct_call_count,
        "new_source_count": new_source_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
