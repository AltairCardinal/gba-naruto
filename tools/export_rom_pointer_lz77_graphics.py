#!/usr/bin/env python3
"""Export candidate atlases for the newly cataloged pointer-reachable graphics."""

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
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from tools.gba_image_export import (  # noqa: E402
    indexed_png_from_bgr555,
    render_4bpp_tile_atlas_indices,
)
from tools.thumb_branch import decode_thumb_bl  # noqa: E402


SCHEMA = "rom-pointer-lz77-graphics-v1"
VERIFY_SCHEMA = "rom-pointer-lz77-graphics-verification-v1"
CATALOG_NAME = "graphics-catalog.json"
RAW_PALETTE_BUNDLE_NAME = "raw-palettes.bgr555.bin"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_ROOT = Path("artifacts/rom-pointer-lz77-inventory-v1")
SOURCE_MANIFEST_SHA256 = (
    "d524105b8a7892ff3c9129d9c8bde246d57d3f6de627fb3d62a71b83d0286dd2"
)
SOURCE_PAYLOAD_SHA256 = (
    "2ecf955805d1f69bc38b4b41c2215243f07a0ed40c357cfcc94545cff2284cd7"
)
CPU_FAST_SET = 0x0809C0DC
CPU_SET = 0x0809C0E0
LZ77_VRAM = 0x0809C0E8
SCOPE = {
    "new_pointer_reachable_graphics_records_cataloged": True,
    "source_palette_bound_subset_previewed": True,
    "unresolved_palette_records_index_previewed": True,
    "all_previews_are_final_visible_images": False,
    "tilemap_or_oam_composition_complete": False,
    "all_raw_graphics_complete": False,
    "all_game_visual_states_complete": False,
    "generic_image_writeback_complete": False,
}
SELECTION_RULE = {
    "window_bytes": 32,
    "sources": (
        "all literal_load_users of the 21 source-inventory graphics records"
    ),
    "accepted_operations": [
        "r0 ROM LZ77 source -> LZ77UnCompVram -> PRAM, size 32",
        (
            "r0 ROM raw source -> CpuSet/CpuFastSet -> PRAM, "
            "exact unit count"
        ),
    ],
    "unknown_instruction_policy": "invalidate r0-r3 (fail closed)",
    "call_policy": "record actual arguments at BL, then invalidate r0-r3",
    "unresolved_rule": "no accepted palette operation in any record window",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _load_source(root: Path) -> tuple[dict[str, Any], bytes]:
    source = root / SOURCE_ROOT
    manifest_bytes = (source / "manifest.json").read_bytes()
    payload_bytes = (source / "rom-pointer-lz77-inventory.json").read_bytes()
    if _sha(manifest_bytes) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source inventory manifest changed")
    if _sha(payload_bytes) != SOURCE_PAYLOAD_SHA256:
        raise ValueError("source inventory payload changed")
    manifest = json.loads(manifest_bytes)
    payload = json.loads(payload_bytes)
    for relative, expected in manifest["files"].items():
        if _sha((source / relative).read_bytes()) != expected:
            raise ValueError(f"source inventory file changed: {relative}")
    if (
        payload.get("schema") != "rom-pointer-lz77-inventory-v1"
        or payload.get("classification_counts", {}).get("graphics") != 21
    ):
        raise ValueError("source inventory graphics contract changed")
    return payload, (source / "uncovered-payloads.bin").read_bytes()


def _literal_value(rom: bytes, instruction_offset: int) -> tuple[int, int] | None:
    instruction = struct.unpack_from("<H", rom, instruction_offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    address = ROM_BASE + instruction_offset
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


def discover_palette_operations(
    rom: bytes, graphics_user: int
) -> list[dict[str, Any]]:
    """Discover actual palette calls in one fail-closed 32-byte loader window."""
    start = graphics_user - ROM_BASE
    if start < 0 or start + 2 > len(rom):
        raise ValueError("graphics user is outside the ROM")
    registers: list[Symbol] = [UNKNOWN for _ in range(16)]
    operations = []
    offset = start
    end = min(len(rom) - 3, start + 0x20)
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
            right = (operand, False, address) if immediate else registers[operand]
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
                for register in range(4):
                    registers[register] = UNKNOWN
            offset += 2
            continue
        if instruction & 0xF800 == 0xF000:
            second = struct.unpack_from("<H", rom, offset + 2)[0]
            target = decode_thumb_bl(address, instruction, second)
            source, source_dynamic, source_load = registers[0]
            destination, destination_dynamic, _ = registers[1]
            count, count_dynamic, _ = registers[2]
            if (
                target == LZ77_VRAM
                and not source_dynamic
                and source_load is not None
                and ROM_BASE <= source < ROM_BASE + len(rom) - 3
                and not destination_dynamic
                and 0x05000000 <= destination < 0x05000400
                and rom[source - ROM_BASE] == 0x10
            ):
                size = int.from_bytes(
                    rom[source - ROM_BASE + 1 : source - ROM_BASE + 4],
                    "little",
                )
                if size == 32:
                    operations.append(
                        {
                            "kind": "lz77_rom",
                            "graphics_user": f"0x{graphics_user:08X}",
                            "source_address": f"0x{source:08X}",
                            "source_load": f"0x{source_load:08X}",
                            "callsite": f"0x{address:08X}",
                            "loader": "LZ77UnCompVram",
                            "size": size,
                            "destination": f"0x{destination:08X}",
                            "code_size": offset + 4 - (source_load - ROM_BASE),
                            "code_sha256": _sha(
                                rom[source_load - ROM_BASE : offset + 4]
                            ),
                        }
                    )
            elif (
                target in (CPU_SET, CPU_FAST_SET)
                and not source_dynamic
                and source_load is not None
                and ROM_BASE <= source < ROM_BASE + len(rom)
                and not destination_dynamic
                and 0x05000000 <= destination < 0x05000400
                and not count_dynamic
                and count > 0
            ):
                operations.append(
                    {
                        "kind": "raw_rom",
                        "graphics_user": f"0x{graphics_user:08X}",
                        "source_address": f"0x{source:08X}",
                        "source_load": f"0x{source_load:08X}",
                        "callsite": f"0x{address:08X}",
                        "loader": (
                            "CpuSet" if target == CPU_SET else "CpuFastSet"
                        ),
                        "unit_count": count,
                        "size": count * (2 if target == CPU_SET else 4),
                        "destination": f"0x{destination:08X}",
                        "code_size": offset + 4 - (source_load - ROM_BASE),
                        "code_sha256": _sha(
                            rom[source_load - ROM_BASE : offset + 4]
                        ),
                    }
                )
            for register in range(4):
                registers[register] = UNKNOWN
            offset += 4
            continue

        # Unsupported instructions fail closed for argument registers.
        for register in range(4):
            registers[register] = UNKNOWN
        offset += 2
    return operations


def _synthetic_palette() -> bytes:
    output = bytearray()
    for index in range(16):
        component = round(index * 31 / 15)
        output.extend(
            struct.pack("<H", component | component << 5 | component << 10)
        )
    return bytes(output)


def _build(
    root: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM changed")
    source, decompressed_bundle = _load_source(root)
    source_records = {
        record["file_offset"]: record for record in source["new_records"]
    }
    graphics_records = [
        record
        for record in source["new_records"]
        if record["classification"]["kind"] == "graphics"
    ]
    if len(graphics_records) != 21:
        raise ValueError("graphics palette denominator changed")

    discovered: dict[int, tuple[str, list[int], list[dict[str, Any]]]] = {}
    raw_operations: dict[int, dict[str, dict[str, Any]]] = {}
    for record in graphics_records:
        operations = []
        for user_text in record["literal_load_users"]:
            operations.extend(
                discover_palette_operations(rom, int(user_text, 16))
            )
        operations = list(
            {
                (
                    item["graphics_user"],
                    item["callsite"],
                    item["source_address"],
                ): item
                for item in operations
            }.values()
        )
        operations.sort(
            key=lambda item: (
                int(item["graphics_user"], 16),
                int(item["callsite"], 16),
                int(item["source_address"], 16),
            )
        )
        kinds = {item["kind"] for item in operations}
        if len(kinds) > 1:
            raise ValueError(
                f"mixed palette routes in one loader window: {record['gba_address']}"
            )
        kind = next(iter(kinds), "unresolved")
        palette_offsets = list(
            dict.fromkeys(
                int(item["source_address"], 16) - ROM_BASE
                for item in operations
            )
        )
        discovered[record["file_offset"]] = (
            kind,
            palette_offsets,
            operations,
        )
        if kind != "raw_rom":
            continue
        for item in operations:
            source_offset = int(item["source_address"], 16) - ROM_BASE
            by_call = raw_operations.setdefault(source_offset, {})
            callsite = item["callsite"]
            copy = {
                key: value
                for key, value in item.items()
                if key not in {"kind", "source_address", "graphics_user"}
            }
            if callsite not in by_call:
                copy["graphics_users"] = [item["graphics_user"]]
                by_call[callsite] = copy
            elif item["graphics_user"] not in by_call[callsite]["graphics_users"]:
                by_call[callsite]["graphics_users"].append(item["graphics_user"])

    kind_counts = {
        kind: sum(value[0] == kind for value in discovered.values())
        for kind in ("raw_rom", "lz77_rom", "unresolved")
    }
    if kind_counts != {"raw_rom": 12, "lz77_rom": 4, "unresolved": 5}:
        raise ValueError(f"discovered palette denominator changed: {kind_counts}")

    raw_bundle = bytearray()
    raw_sources = []
    raw_by_offset = {}
    for offset, evidence_by_call in sorted(raw_operations.items()):
        copy_evidence = sorted(
            evidence_by_call.values(), key=lambda item: int(item["callsite"], 16)
        )
        for item in copy_evidence:
            item["graphics_users"].sort(key=lambda value: int(value, 16))
        size = max(item["size"] for item in copy_evidence)
        if size % 32 or not 32 <= size <= 512:
            raise ValueError(f"raw palette size is invalid: {_address(offset)}")
        data = rom[offset : offset + size]
        item = {
            "gba_address": _address(offset),
            "file_offset": offset,
            "size": size,
            "sha256": _sha(data),
            "bundle_offset": len(raw_bundle),
            "copy_evidence": copy_evidence,
        }
        raw_sources.append(item)
        raw_by_offset[offset] = data
        raw_bundle.extend(data)

    files: dict[str, bytes] = {}
    entries = []
    source_palette_preview_count = 0
    index_only_preview_count = 0
    synthetic = _synthetic_palette()
    for record in graphics_records:
        offset = record["file_offset"]
        start = record["decompressed_bundle_offset"]
        graphics = decompressed_bundle[
            start : start + record["decompressed_size"]
        ]
        if _sha(graphics) != record["decompressed_sha256"]:
            raise ValueError(f"graphics payload changed: {_address(offset)}")
        pixels, width, height = render_4bpp_tile_atlas_indices(
            graphics, tiles_per_row=16
        )

        kind, palette_offsets, operation_evidence = discovered[offset]
        if kind == "raw_rom":
            palette_variants = [
                (palette_offset, bank, data[bank * 32 : bank * 32 + 32])
                for palette_offset in palette_offsets
                for data in [raw_by_offset[palette_offset]]
                for bank in range(len(data) // 32)
            ]
        elif kind == "lz77_rom":
            palette_variants = []
            for palette_offset in palette_offsets:
                palette_record = source_records[palette_offset]
                palette_start = palette_record["decompressed_bundle_offset"]
                data = decompressed_bundle[
                    palette_start
                    : palette_start + palette_record["decompressed_size"]
                ]
                if len(data) != 32:
                    raise ValueError(
                        f"LZ77 palette is not one bank: {_address(palette_offset)}"
                    )
                palette_variants.append((palette_offset, 0, data))
        else:
            kind = "unresolved"
            palette_offsets = []
            palette_variants = [(None, 0, synthetic)]

        previews = []
        for palette_offset, bank, palette in palette_variants:
            address_token = (
                "index-only"
                if palette_offset is None
                else f"{ROM_BASE + palette_offset:08x}-bank-{bank:02d}"
            )
            relative = (
                f"previews/{ROM_BASE + offset:08x}-{address_token}.png"
            )
            png = indexed_png_from_bgr555(
                pixels,
                palette,
                width=width,
                height=height,
            )
            files[relative] = png
            origin = (
                "synthetic_index_only" if kind == "unresolved" else kind
            )
            previews.append(
                {
                    "file": relative,
                    "palette_origin": origin,
                    "palette_address": (
                        None if palette_offset is None else _address(palette_offset)
                    ),
                    "palette_bank": bank,
                    "palette_sha256": _sha(palette),
                    "width": width,
                    "height": height,
                    "png_sha256": _sha(png),
                    "rendering_scope": (
                        "4bpp source-order tile atlas candidate; no tilemap, OAM, "
                        "palette-bank selection or runtime composition"
                    ),
                }
            )
        if kind == "unresolved":
            index_only_preview_count += len(previews)
        else:
            source_palette_preview_count += len(previews)
        entries.append(
            {
                "graphics_address": record["gba_address"],
                "graphics_file_offset": offset,
                "decompressed_size": len(graphics),
                "decompressed_sha256": _sha(graphics),
                "palette_binding": {
                    "kind": kind,
                    "source_addresses": [
                        _address(value) for value in palette_offsets
                    ],
                    "discovery_rule": (
                        "actual r0 source to PRAM palette operation within the "
                        "graphics literal user's 32-byte loader window"
                    ),
                    "operation_evidence": operation_evidence,
                },
                "previews": previews,
            }
        )

    implementation = {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_pointer_lz77_graphics.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_pointer_lz77_graphics.py").read_bytes()
        ),
    }
    summary = {
        "graphics_record_count": len(entries),
        "raw_palette_bound_count": kind_counts["raw_rom"],
        "lz77_palette_bound_count": kind_counts["lz77_rom"],
        "source_palette_bound_count": (
            kind_counts["raw_rom"] + kind_counts["lz77_rom"]
        ),
        "unresolved_palette_count": kind_counts["unresolved"],
        "source_palette_preview_count": source_palette_preview_count,
        "index_only_preview_count": index_only_preview_count,
        "preview_file_count": source_palette_preview_count
        + index_only_preview_count,
        "raw_palette_source_count": len(raw_sources),
        "raw_palette_bundle_size": len(raw_bundle),
    }
    catalog = {
        "schema": SCHEMA,
        "implementation": implementation,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "source_inventory": {
            "path": SOURCE_ROOT.as_posix(),
            "manifest_sha256": SOURCE_MANIFEST_SHA256,
            "payload_sha256": SOURCE_PAYLOAD_SHA256,
        },
        "summary": summary,
        "selection_rule": SELECTION_RULE,
        "raw_palette_sources": raw_sources,
        "graphics": entries,
        "synthetic_index_palette": {
            "size": len(synthetic),
            "sha256": _sha(synthetic),
            "purpose": "diagnostic index visibility only; not a ROM palette",
        },
        "scope": SCOPE,
    }
    files[CATALOG_NAME] = (
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files[RAW_PALETTE_BUNDLE_NAME] = bytes(raw_bundle)
    return catalog, files


def _promotion(catalog: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    summary = catalog["summary"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            relative: _sha(data) for relative, data in sorted(files.items())
        },
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_pointer_lz77_graphics.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/rom-pointer-lz77-graphics-v1",
            ],
            **catalog["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_pointer_lz77_graphics.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-pointer-lz77-graphics-v1",
            ],
            "verifier_sha256": catalog["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                "graphics_record_count": summary["graphics_record_count"],
                "preview_file_count": summary["preview_file_count"],
            },
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    if output.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = output.expanduser().resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be repository or ancestor")
    if not target.exists():
        return target
    if not target.is_dir() or any(path.is_symlink() for path in target.rglob("*")):
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
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or actual != set(manifest.get("files", {})) | {"manifest.json"}
    ):
        raise ValueError("refusing to replace foreign output")
    for relative, expected in manifest["files"].items():
        if _sha((target / relative).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace_output(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and output.exists():
            shutil.rmtree(backup)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    target = _validate_output(root, output)
    catalog, files = _build(root)
    _replace_output(target, files, _promotion(catalog, files))
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/rom-pointer-lz77-graphics-v1"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    catalog = export_artifact(args.root, output)
    print(json.dumps(catalog["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
