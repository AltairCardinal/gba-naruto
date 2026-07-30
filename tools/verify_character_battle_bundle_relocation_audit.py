#!/usr/bin/env python3
"""Independently rebuild and verify the full character bundle relocation."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
TABLE_OFFSET = 0x596D5C
TABLE_ENTRY_SIZE = 16
ARTIFACT_ID = "character-battle-bundle-relocation-v1"
PAYLOAD_NAME = "relocation-audit.json"
NORMAL_OR_ANOMALOUS_TRAILERS = {
    bytes.fromhex("ffff0000"),
    bytes.fromhex("fffb0000"),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _pointer(value: object) -> int:
    return int(str(value), 16)


def _source(rom: bytes, row: dict[str, Any], label: str) -> bytes:
    pointer = _pointer(row["gba_pointer"])
    size = int(row["size"])
    offset = pointer - ROM_BASE
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"{label} is outside base ROM")
    data = rom[offset : offset + size]
    if _sha256(data) != row["sha256"]:
        raise ValueError(f"{label} SHA-256 mismatch")
    return data


def _split_region(
    region: bytes,
    records: list[dict[str, Any]],
    label: str,
) -> list[bytes]:
    result = []
    cursor = 0
    for index, record in enumerate(records):
        size = int(record["raw_size"])
        raw = region[cursor : cursor + size]
        if len(raw) != size or _sha256(raw) != record["raw_sha256"]:
            raise ValueError(f"{label} record {index} mismatch")
        result.append(raw)
        cursor += size
    if cursor != len(region):
        raise ValueError(f"{label} records do not consume the region")
    return result


def _expect_references(
    resource: dict[str, Any],
) -> dict[int, set[int]]:
    expected: dict[int, set[int]] = {}

    def add(pointer: int, offset: int) -> None:
        expected.setdefault(pointer, set()).add(offset)

    descriptor = resource["descriptor"]
    for row in resource["slot_rows"]:
        offset = TABLE_OFFSET + row * TABLE_ENTRY_SIZE
        add(_pointer(descriptor["frame_pointer_table"]), offset)
        add(_pointer(descriptor["animation_pointer_table"]), offset + 4)
        add(_pointer(descriptor["graphics"]), offset + 8)
    frame_table_offset = _pointer(
        resource["frame_pointer_table"]["gba_pointer"]
    ) - ROM_BASE
    for index, frame in enumerate(resource["frames"]):
        add(_pointer(frame["component_list_pointer"]), frame_table_offset + index * 4)
    animation_table_offset = _pointer(
        resource["animation_pointer_table"]["gba_pointer"]
    ) - ROM_BASE
    for index, animation in enumerate(resource["animations"]):
        add(_pointer(animation["timeline_pointer"]), animation_table_offset + index * 4)
    return expected


def _lz77_end(rom: bytes, start: int) -> int | None:
    """Return the exclusive end of a strict GBA type-0x10 stream."""
    if start < 0 or start + 4 > len(rom) or rom[start] != 0x10:
        return None
    declared = int.from_bytes(rom[start + 1 : start + 4], "little")
    if declared <= 0:
        return None
    cursor = start + 4
    produced = 0
    try:
        while produced < declared:
            flags = rom[cursor]
            cursor += 1
            for bit in range(7, -1, -1):
                if produced >= declared:
                    break
                if flags & (1 << bit):
                    first = rom[cursor]
                    second = rom[cursor + 1]
                    cursor += 2
                    length = (first >> 4) + 3
                    distance = (((first & 0x0F) << 8) | second) + 1
                    if distance > produced or produced + length > declared:
                        return None
                    produced += length
                else:
                    cursor += 1
                    produced += 1
    except IndexError:
        return None
    return cursor


def _pointed_lz77_spans(rom: bytes) -> list[dict[str, Any]]:
    """Find strict LZ77 records reached by an aligned ROM pointer."""
    pointer_sources: dict[int, list[int]] = {}
    for offset in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, offset)[0]
        target = value - ROM_BASE
        if 0 <= target < len(rom) and rom[target] == 0x10:
            pointer_sources.setdefault(target, []).append(offset)
    spans = []
    for start, sources in sorted(pointer_sources.items()):
        end = _lz77_end(rom, start)
        if end is not None:
            spans.append(
                {
                    "start": start,
                    "end": end,
                    "pointer_sources": sources,
                }
            )
    return spans


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        promotion_path = artifact / "manifest.json"
        promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
        payload_path = artifact / PAYLOAD_NAME
        manifest = json.loads(payload_path.read_text(encoding="utf-8"))
        payload_digest = _sha256_file(payload_path)
        spec_path = artifact / "full-relocation-spec.json"
        expected_files = {
            PAYLOAD_NAME: payload_digest,
            spec_path.name: _sha256_file(spec_path),
        }
        actual_files = {
            path.relative_to(artifact).as_posix(): _sha256_file(path)
            for path in artifact.rglob("*")
            if path.is_file() and path != promotion_path
        }
        expected_command = [
            "python3",
            "tools/verify_character_battle_bundle_relocation_audit.py",
            "--root",
            ".",
            "--artifact",
            f"artifacts/{ARTIFACT_ID}",
        ]
        if promotion.get("schema") != "git-artifact-promotion-v1":
            raise ValueError("promotion manifest schema mismatch")
        if (
            promotion.get("artifact_id") != ARTIFACT_ID
            or promotion.get("artifact_schema")
            != "character-battle-bundle-relocation-audit-v1"
            or promotion.get("artifact_status") != "accepted"
        ):
            raise ValueError("promotion identity/status mismatch")
        if (
            promotion.get("payload_file") != PAYLOAD_NAME
            or promotion.get("payload_sha256") != payload_digest
            or promotion.get("files") != expected_files
            or actual_files != expected_files
        ):
            raise ValueError("promotion payload/file inventory mismatch")
        if promotion.get("verifier") != {
            "command": expected_command,
            "exit_code": 0,
        }:
            raise ValueError("promotion verifier evidence mismatch")
        if manifest.get("schema") != "character-battle-bundle-relocation-audit-v1":
            raise ValueError("audit schema mismatch")
        if (
            promotion.get("scope") != manifest.get("scope")
            or promotion.get("summary") != manifest.get("summary")
        ):
            raise ValueError("promotion scope/summary mismatch")
        base_path = root / manifest["base_rom"]["path"]
        base = base_path.read_bytes()
        if (
            len(base) != manifest["base_rom"]["size"]
            or _sha256(base) != manifest["base_rom"]["sha256"]
        ):
            raise ValueError("base ROM provenance mismatch")
        layout_path = root / manifest["layout"]["path"]
        if _sha256_file(layout_path) != manifest["layout"]["sha256"]:
            raise ValueError("layout SHA-256 mismatch")
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        target_size = int(layout["target_rom_size"], 0)
        fill_byte = int(layout["fill_byte"], 0)
        partition = next(
            row
            for row in layout["partitions"]
            if row["id"] == manifest["layout"]["partition"]
        )
        partition_start = int(partition["start"], 0)
        partition_end = int(partition["end"], 0)
        if (
            partition["owner"] != manifest["layout"]["owner"]
            or partition["origin"] != "expanded_ff"
            or partition_start < len(base)
            or partition_end > target_size
        ):
            raise ValueError("relocation partition mismatch")

        catalog_path = root / manifest["catalog"]["path"]
        catalog_bytes = catalog_path.read_bytes()
        if _sha256(catalog_bytes) != manifest["catalog"]["sha256"]:
            raise ValueError("catalog SHA-256 mismatch")
        catalog = json.loads(catalog_bytes)
        if (
            catalog.get("schema") != "character-battle-visuals-v1"
            or len(catalog["resources"]) != 250
            or len(catalog["slots"]) != 558
        ):
            raise ValueError("catalog identity mismatch")
        table = base[
            TABLE_OFFSET : TABLE_OFFSET
            + catalog["table"]["entry_count"] * catalog["table"]["entry_size"]
        ]
        if _sha256(table) != catalog["table"]["sha256"]:
            raise ValueError("descriptor table provenance mismatch")

        spec_path = artifact / manifest["authoring_spec"]["file"]
        if _sha256_file(spec_path) != manifest["authoring_spec"]["sha256"]:
            raise ValueError("authoring spec SHA-256 mismatch")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if (
            spec.get("schema") != "character-battle-bundle-import-v1"
            or spec.get("base_rom_sha256") != _sha256(base)
            or spec.get("catalog_sha256") != _sha256(catalog_bytes)
            or len(spec.get("edits", [])) != 250
        ):
            raise ValueError("authoring spec provenance mismatch")
        expected_spec_keys = {
            "schema",
            "description",
            "base_rom_sha256",
            "catalog",
            "catalog_sha256",
            "partition",
            "owner",
            "edits",
        }
        if (
            set(spec) != expected_spec_keys
            or spec.get("catalog") != manifest["catalog"]["path"]
            or spec.get("partition") != manifest["layout"]["partition"]
            or spec.get("owner") != manifest["layout"]["owner"]
        ):
            raise ValueError("authoring preservation spec contract mismatch")
        expected_edit_keys = {
            "id",
            "resource_id",
            "expected_descriptor",
            "expected_slot_rows",
            "graphics_file",
            "graphics_sha256",
        }
        for resource, edit in zip(catalog["resources"], spec["edits"]):
            expected_graphics_file = str(
                Path(manifest["catalog"]["path"]).parent
                / resource["graphics"]["file"]
            )
            if (
                set(edit) != expected_edit_keys
                or edit.get("id")
                != f"resource-{resource['resource_id']:03d}-relocation"
                or edit.get("graphics_file") != expected_graphics_file
            ):
                raise ValueError(
                    "authoring preservation edit contract mismatch: "
                    f"resource {resource['resource_id']}"
                )

        for relative, expected in manifest["implementation"].items():
            if _sha256_file(root / relative) != expected:
                raise ValueError(f"implementation hash mismatch: {relative}")

        output = bytearray(
            base + bytes([fill_byte]) * (target_size - len(base))
        )
        cursor = partition_start
        expected_references: dict[int, set[int]] = {}
        resource_audit = {
            row["resource_id"]: row for row in manifest["resources"]
        }
        if sorted(resource_audit) != list(range(250)):
            raise ValueError("audit resource IDs are incomplete")
        descriptor_rows: set[int] = set()
        frame_total = component_total = animation_total = keyframe_total = 0
        tile_total = 0
        anomaly_count = 0
        for resource_id, (resource, edit) in enumerate(
            zip(catalog["resources"], spec["edits"])
        ):
            if (
                resource["resource_id"] != resource_id
                or edit["resource_id"] != resource_id
                or edit["expected_descriptor"] != resource["descriptor"]
                or edit["expected_slot_rows"] != resource["slot_rows"]
            ):
                raise ValueError(f"resource {resource_id} identity mismatch")
            graphics_path = root / edit["graphics_file"]
            graphics = graphics_path.read_bytes()
            if (
                _sha256(graphics) != edit["graphics_sha256"]
                or _sha256(graphics) != resource["graphics"]["sha256"]
                or len(graphics) != resource["graphics"]["size"]
            ):
                raise ValueError(f"resource {resource_id} graphics mismatch")
            palette = _source(
                base,
                resource["palette"],
                f"resource {resource_id} palette",
            )
            component_region = _source(
                base,
                resource["component_region"],
                f"resource {resource_id} component region",
            )
            frames = _split_region(
                component_region,
                resource["frames"],
                f"resource {resource_id} frames",
            )
            for frame in frames:
                if frame[-4:] not in NORMAL_OR_ANOMALOUS_TRAILERS:
                    raise ValueError(f"resource {resource_id} trailer mismatch")
                anomaly_count += frame[-4:] == bytes.fromhex("fffb0000")
            timeline_region = _source(
                base,
                resource["timeline_region"],
                f"resource {resource_id} timeline region",
            )
            animations = _split_region(
                timeline_region,
                resource["animations"],
                f"resource {resource_id} animations",
            )
            if any(animation[-4:] != bytes.fromhex("ffff0000") for animation in animations):
                raise ValueError(f"resource {resource_id} animation terminator mismatch")

            palette_offset = cursor
            graphics_offset = palette_offset + len(palette)
            component_offset = graphics_offset + len(graphics)
            frame_table_offset = component_offset + len(component_region)
            timeline_offset = frame_table_offset + len(frames) * 4
            animation_table_offset = timeline_offset + len(timeline_region)
            frame_pointers = []
            position = component_offset
            for frame in frames:
                frame_pointers.append(ROM_BASE + position)
                position += len(frame)
            animation_pointers = []
            position = timeline_offset
            for animation in animations:
                animation_pointers.append(ROM_BASE + position)
                position += len(animation)
            frame_table = struct.pack(f"<{len(frames)}I", *frame_pointers)
            animation_table = struct.pack(
                f"<{len(animations)}I",
                *animation_pointers,
            )
            bundle = (
                palette
                + graphics
                + component_region
                + frame_table
                + timeline_region
                + animation_table
            )
            end = cursor + len(bundle)
            if end > partition_end:
                raise ValueError("independent rebuild exceeds relocation partition")
            output[cursor:end] = bundle
            pointers = {
                "palette": ROM_BASE + palette_offset,
                "graphics": ROM_BASE + graphics_offset,
                "component_region": ROM_BASE + component_offset,
                "frame_pointer_table": ROM_BASE + frame_table_offset,
                "timeline_region": ROM_BASE + timeline_offset,
                "animation_pointer_table": ROM_BASE + animation_table_offset,
            }
            audit = resource_audit[resource_id]
            expected_pointer_text = {
                key: f"0x{value:08X}" for key, value in pointers.items()
            }
            if (
                audit["offset"] != cursor
                or audit["bundle_size"] != len(bundle)
                or audit["bundle_sha256"] != _sha256(bundle)
                or audit["new_pointers"] != expected_pointer_text
                or audit["slot_rows"] != resource["slot_rows"]
            ):
                raise ValueError(f"resource {resource_id} audit row mismatch")
            descriptor = struct.pack(
                "<4I",
                pointers["frame_pointer_table"],
                pointers["animation_pointer_table"],
                pointers["graphics"],
                pointers["palette"],
            )
            for row in resource["slot_rows"]:
                if row in descriptor_rows:
                    raise ValueError(f"descriptor row {row} is multiply owned")
                descriptor_rows.add(row)
                offset = TABLE_OFFSET + row * TABLE_ENTRY_SIZE
                output[offset : offset + TABLE_ENTRY_SIZE] = descriptor

            for target, sources in _expect_references(resource).items():
                expected_references.setdefault(target, set()).update(sources)
            cursor = end
            frame_total += len(frames)
            component_total += resource["component_count"]
            animation_total += len(animations)
            keyframe_total += resource["keyframe_count"]
            tile_total += len(graphics) // 32

        actual_references = {
            pointer: set() for pointer in expected_references
        }
        pointed_lz77_spans = _pointed_lz77_spans(base)
        target_values = set(expected_references)
        for offset in range(0, len(base) - 3, 4):
            value = struct.unpack_from("<I", base, offset)[0]
            if value in target_values:
                actual_references[value].add(offset)
        unexpected = []
        compressed_payload_coincidences = []
        missing = []
        for pointer in sorted(expected_references):
            for offset in sorted(
                actual_references[pointer] - expected_references[pointer]
            ):
                container = next(
                    (
                        span
                        for span in pointed_lz77_spans
                        if span["start"] < offset < span["end"]
                    ),
                    None,
                )
                if container is None:
                    unexpected.append((pointer, offset))
                else:
                    compressed_payload_coincidences.append(
                        {
                            "pointer": f"0x{pointer:08X}",
                            "source_offset": offset,
                            "classification": (
                                "pointed_lz77_payload_coincidence"
                            ),
                            "container_start": container["start"],
                            "container_end": container["end"],
                            "container_pointer_sources": container[
                                "pointer_sources"
                            ],
                        }
                    )
            missing.extend(
                (pointer, offset)
                for offset in sorted(
                    expected_references[pointer] - actual_references[pointer]
                )
            )
        if unexpected or missing:
            raise ValueError(
                f"pointer reference inventory mismatch: "
                f"unexpected={unexpected[:10]} missing={missing[:10]}"
            )
        manifest_coincidences = sorted(
            (
                row["resource_id"],
                coincidence,
            )
            for row in manifest["resources"]
            for coincidence in row["compressed_payload_coincidences"]
        )
        verified_coincidences = []
        for pointer, sources in expected_references.items():
            for coincidence in compressed_payload_coincidences:
                if coincidence["pointer"] == f"0x{pointer:08X}":
                    resource_id = next(
                        row["resource_id"]
                        for row in catalog["resources"]
                        if pointer in _expect_references(row)
                    )
                    verified_coincidences.append((resource_id, coincidence))
        if sorted(verified_coincidences) != manifest_coincidences:
            raise ValueError("compressed payload coincidence audit mismatch")

        summary = manifest["summary"]
        expected_summary = {
            "resource_count": 250,
            "descriptor_slot_count": 342,
            "allocation_start": partition_start,
            "allocation_end": cursor,
            "allocated_bytes": cursor - partition_start,
            "partition_end": partition_end,
            "remaining_bytes": partition_end - cursor,
            "frame_count": frame_total,
            "component_count": component_total,
            "animation_count": animation_total,
            "keyframe_count": keyframe_total,
            "tile_count": tile_total,
            "compressed_payload_coincidence_count": len(
                compressed_payload_coincidences
            ),
            "unexpected_external_reference_count": 0,
        }
        for key, expected in expected_summary.items():
            if summary.get(key) != expected:
                raise ValueError(
                    f"audit summary {key} mismatch: "
                    f"expected {expected} got {summary.get(key)}"
                )
        if anomaly_count != 1:
            raise ValueError("FBFF trailer denominator mismatch")
        rebuilt_output_sha256 = _sha256(bytes(output))
        if rebuilt_output_sha256 != manifest["output_rom_sha256"]:
            raise ValueError("independently rebuilt output ROM SHA-256 mismatch")
        verified_resources = 250
        verified_descriptors = len(descriptor_rows)
        verified_compressed_payload_coincidences = len(
            compressed_payload_coincidences
        )
    except (
        KeyError,
        IndexError,
        OSError,
        StopIteration,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        struct.error,
    ) as error:
        errors.append(str(error))
        rebuilt_output_sha256 = ""
        verified_resources = 0
        verified_descriptors = 0
        verified_compressed_payload_coincidences = 0

    return {
        "schema": "character-battle-bundle-relocation-verification-v1",
        "errors": errors,
        "verified_resources": verified_resources,
        "verified_descriptors": verified_descriptors,
        "verified_compressed_payload_coincidences": (
            verified_compressed_payload_coincidences
        ),
        "rebuilt_output_rom_sha256": rebuilt_output_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independently verify full character bundle relocation audit."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/character-battle-bundle-relocation-v1"),
    )
    args = parser.parse_args()
    artifact = (
        args.artifact
        if args.artifact.is_absolute()
        else args.root / args.artifact
    )
    result = verify_audit(args.root, artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
