#!/usr/bin/env python3
"""Independently verify the fixed-ID generic Sprite relocation artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import sys
from collections import deque
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ARTIFACT_ID = "generic-sprite-bundle-relocation-v1"
PAYLOAD_SCHEMA = "generic-sprite-bundle-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STATIC_CATALOG_PATH = Path("artifacts/sprite-definition-assets-v2/manifest.json")
STATIC_CATALOG_SHA256 = (
    "ee36523b6a02edb4b803f1835da3dd0d5e460102fc18507b121854d43b882e68"
)
ANIMATION_CATALOG_PATH = Path(
    "artifacts/sprite-definition-animations-v1/manifest.json"
)
ANIMATION_CATALOG_SHA256 = (
    "e432003728c8ea28b95723eeb4f68f9a8cf95b74185eb39fdd6075c71c16b583"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
PAIR_TABLE_OFFSET = 0x53F140
TILE_OFFSET_TABLE_OFFSET = 0x53F298
ENTRY_COUNT = 43
GRAPHICS_POINTER_OFFSET = 0x080A94
PALETTE_POINTER_OFFSET = 0x080A9C
SEQUENCE_BYTES = bytes.fromhex("00000100ffff0000")
TERMINATOR = bytes.fromhex("ffff0000")
MAX_RUNTIME_TILE_BASE = 0x39F
MAX_GRAPHICS_TILES = 97
CALL_SLICES = (
    (0x0806CD18, "39b38a5374444ec03c780b664afdb0c8d557a967afcf3b647bd6dd5716333b70"),
    (0x0806CD90, "566d9cca4a324c216bff658f536be4997b23c5efb4f865d57496aaf20f2a5889"),
    (0x0806CE04, "99096d96e08605ad1ec38945b032a09782309ff018ce1cfeaad3ac9e18083948"),
    (0x0806CE7C, "232db0bb9dfc01024638b78b0f0f41a75d01527fb152ac8daf8d1bcf6081293b"),
    (0x0806CEF0, "143cd40eed99b4694e0243c2f7f5b4ce5bc6a2acb24528aaf921a3a2cf8a2461"),
    (0x0806CF68, "216b79c7a29587b5639524ef5bc43e4e220e6eece3b6952860d291a3f3b7fa51"),
    (0x0806CFDC, "ca82804245c9cdf63123e481171b4ba8f2a274d4acc5a102df2b4c6f17d10659"),
    (0x0806D054, "79224f931d9872894b2896a6ab98ae038399313cf39bc920365b34d55381a07e"),
    (0x0806D0C8, "ffd703de92f2ab2351752148eacf7b47afed251f49600121068c79c68467935c"),
    (0x080725BC, "b506e5a9500d78c71691aeceb78c7b01b26f6f24fd13737947ce9bf95a603902"),
    (0x080726B8, "4b988b59658fd56e95f9fd985925f9d4f7581b9282774b2af70fba584a8994dd"),
    (0x0807AAE8, "8f7afd725323a56d87e376d78bbd62440e9e8cfccc0aff1f6ef0d01ebddd5c62"),
)
CALL_BASE_LITERALS = (
    (0x06CD4C, 0x34E),
    (0x06CDC0, 0x34E),
    (0x06CE38, 0x34E),
    (0x06CEAC, 0x34E),
    (0x06CF24, 0x34E),
    (0x06CF98, 0x34E),
    (0x06D010, 0x34E),
    (0x06D084, 0x34E),
    (0x06D110, 0x34E),
    (0x0725FC, 0x34E),
    (0x0726F8, 0x34E),
    (0x07AB2C, 0x39F),
)
EXPECTED_SCOPE = {
    "proved": (
        "All 43 fixed generic Sprite IDs, 45 source components, the canonical "
        "graphics/palette payloads and all 174 exact source pointer references "
        "are accounted for; 45 payload allocations, 88 external pointer "
        "patches and 43 tile-base writes rebuild a 16 MiB ROM."
    ),
    "editable": (
        "The shared graphics pack may contain 1..97 complete 4bpp tiles, the "
        "palette remains one 16-color bank, and each fixed ID may contain "
        "1..2 valid GBA OBJ components, matching the proved source maximum. "
        "Animation 0 remains the proved "
        "single-frame hold-one-tick then stop sequence."
    ),
    "not_proved": (
        "Adding Sprite IDs, adding animations or frames, scene-specific "
        "resource overwrites, natural selection of every ID, or final "
        "screen-composited pixel/timing equivalence after modification."
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/import_generic_sprite_bundle_relocations.py",
    "tools/export_sprite_definition_runtime_chain.py",
    "tools/verify_sprite_definition_runtime_chain.py",
    "tools/export_sprite_definition_animations.py",
    "tools/verify_sprite_definition_animations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_generic_sprite_bundle_relocation_audit.py",
    "tools/verify_generic_sprite_bundle_relocation_audit.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _encode(data: bytes) -> bytes:
    output = bytearray(
        (0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, len(data) >> 16)
    )
    positions: dict[bytes, deque[int]] = {}
    cursor = 0
    while cursor < len(data):
        flag_offset = len(output)
        output.append(0)
        flags = 0
        for token in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                key = data[cursor : cursor + 3]
                for previous in reversed(positions.get(key, ())):
                    distance = cursor - previous
                    if distance > 0x1000:
                        break
                    length = 3
                    while (
                        length < 18
                        and cursor + length < len(data)
                        and data[previous + length] == data[cursor + length]
                    ):
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                    if length == 18:
                        break
            if best_length >= 3:
                flags |= 1 << (7 - token)
                encoded = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((encoded >> 8, encoded & 0xFF))
                advance = best_length
            else:
                output.append(data[cursor])
                advance = 1
            for position in range(cursor, cursor + advance):
                if position + 3 > len(data):
                    continue
                key = data[position : position + 3]
                bucket = positions.setdefault(key, deque())
                bucket.append(position)
                while bucket and position - bucket[0] > 0x1000:
                    bucket.popleft()
            cursor += advance
        output[flag_offset] = flags
    return bytes(output)


def _component(component: dict[str, Any]) -> dict[str, Any]:
    return {
        key: component[key]
        for key in (
            "tile_offset",
            "flag_02",
            "flag_03",
            "horizontal_position_input",
            "vertical_position_input",
            "width",
            "height",
            "transform_factor_0c",
            "transform_factor_0e",
            "unknown_10_byte",
            "oam_attribute_byte",
            "unknown_12",
        )
    }


def _encode_component(component: dict[str, Any]) -> bytes:
    return struct.pack(
        "<HBBhhhhhhBBH",
        component["tile_offset"],
        component["flag_02"],
        component["flag_03"],
        component["horizontal_position_input"],
        component["vertical_position_input"],
        component["width"],
        component["height"],
        component["transform_factor_0c"],
        component["transform_factor_0e"],
        component["unknown_10_byte"],
        component["oam_attribute_byte"],
        component["unknown_12"],
    )


def _source(
    root: Path,
    base: bytes,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    target = 0x08080A48
    calls = set()
    for offset in range(0, len(base) - 3, 2):
        first, second = struct.unpack_from("<HH", base, offset)
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
        if first & 0x0400:
            displacement -= 1 << 23
        if ROM_BASE + offset + 4 + displacement == target:
            calls.add(ROM_BASE + offset)
    if calls != {address for address, _ in CALL_SLICES}:
        raise ValueError("independent generic Sprite loader call denominator mismatch")
    for address, digest in CALL_SLICES:
        offset = address - ROM_BASE
        if _sha256(base[offset - 4 : offset + 4]) != digest:
            raise ValueError("independent generic Sprite loader call slice mismatch")
    tile_bases = []
    for offset, expected in CALL_BASE_LITERALS:
        actual = struct.unpack_from("<I", base, offset)[0]
        if actual != expected:
            raise ValueError("independent generic Sprite tile base mismatch")
        tile_bases.append(actual)
    if max(tile_bases) != MAX_RUNTIME_TILE_BASE:
        raise ValueError("independent generic Sprite maximum tile base mismatch")
    if _sha256_file(root / STATIC_CATALOG_PATH) != STATIC_CATALOG_SHA256:
        raise ValueError("independent static catalog hash mismatch")
    if _sha256_file(root / ANIMATION_CATALOG_PATH) != ANIMATION_CATALOG_SHA256:
        raise ValueError("independent animation catalog hash mismatch")
    static = _json(root / STATIC_CATALOG_PATH)
    animations = _json(root / ANIMATION_CATALOG_PATH)
    if (
        static.get("schema") != "sprite-definition-assets-v2"
        or animations.get("schema") != "sprite-definition-animations-v1"
        or len(static.get("entries", [])) != ENTRY_COUNT
        or len(animations.get("entries", [])) != ENTRY_COUNT
    ):
        raise ValueError("independent generic Sprite catalog shape mismatch")
    animation_by_id = {row["id"]: row for row in animations["entries"]}
    expected: dict[int, set[int]] = {}

    def expect(pointer: int, offset: int) -> None:
        expected.setdefault(pointer, set()).add(offset)

    component_count = 0
    for entry_id, entry in enumerate(static["entries"]):
        if entry["id"] != entry_id:
            raise ValueError("independent generic Sprite entry order mismatch")
        pair_offset = PAIR_TABLE_OFFSET + entry_id * 8
        definition, animation = struct.unpack_from("<II", base, pair_offset)
        component = struct.unpack_from("<I", base, definition - ROM_BASE)[0]
        sequence = struct.unpack_from("<I", base, animation - ROM_BASE)[0]
        if (
            definition != int(entry["definition_pointer"], 16)
            or animation != int(entry["animation_pointer"], 16)
            or component != int(entry["component_list_pointer"], 16)
            or sequence != definition + 4
            or sequence
            != int(animation_by_id[entry_id]["sequence_pointer"], 16)
            or base[sequence - ROM_BASE : sequence - ROM_BASE + 8]
            != SEQUENCE_BYTES
        ):
            raise ValueError("independent generic Sprite pointer chain mismatch")
        component_bytes = (
            b"".join(
                _encode_component(_component(item))
                for item in entry["components"]
            )
            + TERMINATOR
        )
        if (
            base[component - ROM_BASE : component - ROM_BASE + len(component_bytes)]
            != component_bytes
        ):
            raise ValueError("independent generic Sprite component mismatch")
        if struct.unpack_from(
            "<H", base, TILE_OFFSET_TABLE_OFFSET + entry_id * 2
        )[0] != entry["tile_base_offset"]:
            raise ValueError("independent generic Sprite tile base mismatch")
        expect(definition, pair_offset)
        expect(animation, pair_offset + 4)
        expect(component, definition - ROM_BASE)
        expect(sequence, animation - ROM_BASE)
        component_count += len(entry["components"])
    graphics_pointer = struct.unpack_from("<I", base, GRAPHICS_POINTER_OFFSET)[0]
    palette_pointer = struct.unpack_from("<I", base, PALETTE_POINTER_OFFSET)[0]
    expect(graphics_pointer, GRAPHICS_POINTER_OFFSET)
    expect(palette_pointer, PALETTE_POINTER_OFFSET)
    actual = {pointer: set() for pointer in expected}
    for offset in range(0, len(base) - 3, 4):
        value = struct.unpack_from("<I", base, offset)[0]
        if value in actual:
            actual[value].add(offset)
    if actual != expected:
        raise ValueError("independent generic Sprite exact pointer inventory mismatch")
    reference_count = sum(len(offsets) for offsets in expected.values())
    if component_count != 45 or reference_count != 174:
        raise ValueError("independent generic Sprite denominator mismatch")
    return static, animations, reference_count


def _expected_spec(
    root: Path,
    base: bytes,
    static: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "generic-sprite-bundle-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_static_catalog": STATIC_CATALOG_PATH.as_posix(),
        "source_static_catalog_sha256": _sha256_file(
            root / STATIC_CATALOG_PATH
        ),
        "source_animation_catalog": ANIMATION_CATALOG_PATH.as_posix(),
        "source_animation_catalog_sha256": _sha256_file(
            root / ANIMATION_CATALOG_PATH
        ),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(root / REGISTRY_PATH),
        "region": "generic-sprite-bundle",
        "region_owner": "generic_sprite_resources",
        "graphics_file": (
            STATIC_CATALOG_PATH.parent
            / static["static_resources"]["graphics"]["output_bin"]
        ).as_posix(),
        "palette_file": (
            STATIC_CATALOG_PATH.parent
            / static["static_resources"]["palette"]["output_bin"]
        ).as_posix(),
        "entries": [
            {
                "id": entry["id"],
                "tile_base_offset": entry["tile_base_offset"],
                "components": [
                    _component(component)
                    for component in entry["components"]
                ],
            }
            for entry in static["entries"]
        ],
    }


def _rebuild(
    root: Path,
    base: bytes,
    layout: RomLayout,
    region_start: int,
    region_end: int,
    spec: dict[str, Any],
    *,
    graphics_override: bytes | None = None,
) -> tuple[bytes, dict[str, int], list[dict[str, Any]]]:
    output = bytearray(layout.expanded_base())
    graphics = (
        (root / spec["graphics_file"]).read_bytes()
        if graphics_override is None
        else graphics_override
    )
    palette = (root / spec["palette_file"]).read_bytes()
    if (
        not graphics
        or len(graphics) % 32
        or len(graphics) // 32 > MAX_GRAPHICS_TILES
        or len(palette) != 32
    ):
        raise ValueError("independent generic Sprite source payload mismatch")
    ids = [entry.get("id") for entry in spec.get("entries", [])]
    if (
        len(ids) != ENTRY_COUNT
        or set(ids) != set(range(ENTRY_COUNT))
        or len(ids) != len(set(ids))
    ):
        raise ValueError("independent generic Sprite authored ID mismatch")
    graphics_tiles = len(graphics) // 32
    supported_sizes = {
        (8, 8),
        (16, 16),
        (32, 32),
        (64, 64),
        (16, 8),
        (32, 8),
        (32, 16),
        (64, 32),
        (8, 16),
        (8, 32),
        (16, 32),
        (32, 64),
    }
    for entry in spec["entries"]:
        components = entry.get("components")
        if not isinstance(components, list) or not 1 <= len(components) <= 2:
            raise ValueError("independent generic Sprite component count mismatch")
        tile_base = entry.get("tile_base_offset")
        if (
            isinstance(tile_base, bool)
            or not isinstance(tile_base, int)
            or not 0 <= tile_base < graphics_tiles
        ):
            raise ValueError("independent generic Sprite tile base mismatch")
        for component in components:
            width, height = component.get("width"), component.get("height")
            if (width, height) not in supported_sizes:
                raise ValueError("independent generic Sprite OBJ size mismatch")
            tile_offset = component.get("tile_offset")
            if (
                isinstance(tile_offset, bool)
                or not isinstance(tile_offset, int)
                or tile_base
                + tile_offset
                + width * height // 64
                > graphics_tiles
            ):
                raise ValueError("independent generic Sprite tile range mismatch")
    cursor = region_start
    allocations = []

    def allocate(data: bytes, resource_type: str, **metadata: Any) -> int:
        nonlocal cursor
        cursor = (cursor + 3) & ~3
        offset = cursor
        cursor += len(data)
        if cursor > region_end:
            raise ValueError("independent generic Sprite region overflow")
        if any(value != 0xFF for value in output[offset:cursor]):
            raise ValueError("independent generic Sprite allocation is not blank")
        output[offset:cursor] = data
        allocations.append(
            {
                "resource_type": resource_type,
                "offset": offset,
                **metadata,
            }
        )
        return offset

    graphics_encoded = _encode(graphics)
    palette_encoded = _encode(palette)
    graphics_offset = allocate(
        graphics_encoded,
        "graphics",
        decompressed_size=len(graphics),
        encoded_size=len(graphics_encoded),
        replacement_sha256=_sha256(graphics),
        tile_count=graphics_tiles,
        source_file=spec["graphics_file"],
    )
    palette_offset = allocate(
        palette_encoded,
        "palette",
        decompressed_size=len(palette),
        encoded_size=len(palette_encoded),
        replacement_sha256=_sha256(palette),
        source_file=spec["palette_file"],
    )
    output[GRAPHICS_POINTER_OFFSET : GRAPHICS_POINTER_OFFSET + 4] = struct.pack(
        "<I", ROM_BASE + graphics_offset
    )
    output[PALETTE_POINTER_OFFSET : PALETTE_POINTER_OFFSET + 4] = struct.pack(
        "<I", ROM_BASE + palette_offset
    )

    for entry in spec["entries"]:
        entry_id = entry["id"]
        component_bytes = (
            b"".join(_encode_component(component) for component in entry["components"])
            + TERMINATOR
        )
        cursor = (cursor + 3) & ~3
        bundle_offset = cursor
        component_pointer = ROM_BASE + bundle_offset
        definition_offset = bundle_offset + len(component_bytes)
        definition_pointer = ROM_BASE + definition_offset
        sequence_pointer = definition_pointer + 4
        animation_offset = definition_offset + 12
        animation_pointer = ROM_BASE + animation_offset
        bundle = (
            component_bytes
            + struct.pack("<I", component_pointer)
            + SEQUENCE_BYTES
            + struct.pack("<I", sequence_pointer)
        )
        allocate(
            bundle,
            "entry_bundle",
            entry_id=entry_id,
            component_count=len(entry["components"]),
            tile_base_offset=entry["tile_base_offset"],
            definition_pointer=definition_pointer,
            animation_pointer=animation_pointer,
            component_pointer=component_pointer,
            sequence_pointer=sequence_pointer,
        )
        pair_offset = PAIR_TABLE_OFFSET + entry_id * 8
        output[pair_offset : pair_offset + 8] = struct.pack(
            "<II", definition_pointer, animation_pointer
        )
        tile_offset = TILE_OFFSET_TABLE_OFFSET + entry_id * 2
        output[tile_offset : tile_offset + 2] = struct.pack(
            "<H", entry["tile_base_offset"]
        )
    allocation_end = max(
        row["offset"]
        + (
            row.get("encoded_size")
            if row["resource_type"] != "entry_bundle"
            else len(
                b"".join(
                    _encode_component(component)
                    for component in spec["entries"][row["entry_id"]]["components"]
                )
                + TERMINATOR
            )
            + 16
        )
        for row in allocations
    )
    summary = {
        "entry_count": 43,
        "component_count": sum(
            len(entry["components"]) for entry in spec["entries"]
        ),
        "graphics_tile_count": graphics_tiles,
        "maximum_runtime_tile_base": MAX_RUNTIME_TILE_BASE,
        "maximum_safe_graphics_tiles": MAX_GRAPHICS_TILES,
        "runtime_loader_call_count": len(CALL_SLICES),
        "runtime_tile_bases": sorted(
            {value for _, value in CALL_BASE_LITERALS}
        ),
        "source_pointer_reference_count": 174,
        "unexpected_source_pointer_count": 0,
        "allocation_count": 45,
        "pointer_patch_count": 88,
        "tile_base_patch_count": 43,
        "allocation_start": region_start,
        "allocation_end": allocation_end,
        "region_end": region_end,
        "stored_payload_bytes": sum(
            (
                row["encoded_size"]
                if row["resource_type"] != "entry_bundle"
                else len(
                    b"".join(
                        _encode_component(component)
                        for component in spec["entries"][row["entry_id"]][
                            "components"
                        ]
                    )
                    + TERMINATOR
                )
                + 16
            )
            for row in allocations
        ),
        "allocation_span": allocation_end - region_start,
        "remaining_bytes": region_end - allocation_end,
        "applied_patch_count": 176,
    }
    return bytes(output), summary, allocations


def _capability_fixture(
    root: Path,
    base: bytes,
    layout: RomLayout,
    region_start: int,
    region_end: int,
    spec: dict[str, Any],
) -> tuple[dict[str, Any], str, int, int]:
    fixture = copy.deepcopy(spec)
    original = (root / spec["graphics_file"]).read_bytes()
    extension = bytes((index * 73 + 19) & 0xFF for index in range(48 * 32))
    graphics = original + extension
    added = dict(fixture["entries"][0]["components"][0])
    added["tile_offset"] = 96
    added["horizontal_position_input"] = 8
    fixture["entries"][0]["components"].append(added)
    rebuilt, _, allocations = _rebuild(
        root,
        base,
        layout,
        region_start,
        region_end,
        fixture,
        graphics_override=graphics,
    )
    allocation_end = max(
        row["offset"]
        + (
            row["encoded_size"]
            if row["resource_type"] != "entry_bundle"
            else len(
                b"".join(
                    _encode_component(component)
                    for component in fixture["entries"][row["entry_id"]][
                        "components"
                    ]
                )
                + TERMINATOR
            )
            + 16
        )
        for row in allocations
    )
    output_hash = _sha256(rebuilt)
    component_count = sum(
        len(entry["components"]) for entry in fixture["entries"]
    )
    expected = {
        "schema": "generic-sprite-bundle-capability-fixture-v1",
        "construction": (
            "Append 48 deterministic 4bpp tiles to the canonical 49-tile "
            "pack and add a second ID-0 8x8 component at tile 96."
        ),
        "graphics_tile_count": len(graphics) // 32,
        "graphics_sha256": _sha256(graphics),
        "component_count": component_count,
        "entry_0_component_count": len(
            fixture["entries"][0]["components"]
        ),
        "allocation_count": len(allocations),
        "pointer_patch_count": 88,
        "tile_base_patch_count": 43,
        "allocation_end": allocation_end,
        "output_rom_sha256": output_hash,
    }
    return expected, output_hash, len(graphics) // 32, component_count


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    rebuilt_hash = ""
    verified_entries = 0
    verified_source_pointers = 0
    fixture_hash = ""
    fixture_tiles = 0
    fixture_components = 0
    try:
        root = Path(root).resolve()
        artifact = Path(artifact)
        if not artifact.is_absolute():
            artifact = root / artifact
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != {"manifest.json", PAYLOAD_NAME, SPEC_NAME}:
            raise ValueError("generic Sprite artifact file set mismatch")
        manifest = _json(artifact / "manifest.json")
        payload = _json(artifact / PAYLOAD_NAME)
        spec = _json(artifact / SPEC_NAME)
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_id") != ARTIFACT_ID
            or manifest.get("artifact_schema") != PAYLOAD_SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("payload_file") != PAYLOAD_NAME
            or manifest.get("scope") != EXPECTED_SCOPE
            or payload.get("schema") != PAYLOAD_SCHEMA
            or payload.get("scope") != EXPECTED_SCOPE
        ):
            raise ValueError("generic Sprite artifact identity mismatch")
        file_hashes = {
            name: _sha256_file(artifact / name)
            for name in (PAYLOAD_NAME, SPEC_NAME)
        }
        if (
            manifest.get("files") != file_hashes
            or manifest.get("payload_sha256") != file_hashes[PAYLOAD_NAME]
        ):
            raise ValueError("generic Sprite artifact file hash mismatch")

        base = (root / "rom/base.gba").read_bytes()
        if _sha256(base) != ROM_SHA256:
            raise ValueError("generic Sprite independent base ROM mismatch")
        static, _, reference_count = _source(root, base)
        expected_spec = _expected_spec(root, base, static)
        if spec != expected_spec:
            raise ValueError("generic Sprite authoring spec mismatch")
        verified_entries = len(static["entries"])
        verified_source_pointers = reference_count

        layout_path = root / "sequel/rom-layout.json"
        layout = RomLayout.from_path(layout_path, base)
        regions = ImageResourceRegions.from_path(root / REGISTRY_PATH, layout)
        region = regions.require(
            "generic-sprite-bundle",
            "generic_sprite_resources",
        )
        rebuilt, summary, allocations = _rebuild(
            root,
            base,
            layout,
            region.start,
            region.end,
            spec,
        )
        rebuilt_hash = _sha256(rebuilt)
        if payload.get("summary") != summary or manifest.get("summary") != summary:
            raise ValueError("generic Sprite audit summary mismatch")
        if payload.get("output_rom_sha256") != rebuilt_hash:
            raise ValueError("generic Sprite output ROM hash mismatch")
        (
            expected_fixture,
            fixture_hash,
            fixture_tiles,
            fixture_components,
        ) = _capability_fixture(
            root,
            base,
            layout,
            region.start,
            region.end,
            spec,
        )
        if payload.get("capability_fixture") != expected_fixture:
            raise ValueError("generic Sprite capability fixture mismatch")
        expected_allocations = [
            {
                key: row[key]
                for key in (
                    "resource_type",
                    "offset",
                    "decompressed_size",
                    "encoded_size",
                    "replacement_sha256",
                    "tile_count",
                    "entry_id",
                    "component_count",
                    "tile_base_offset",
                    "definition_pointer",
                    "animation_pointer",
                    "component_pointer",
                    "sequence_pointer",
                    "source_file",
                )
                if key in row
            }
            for row in allocations
        ]
        actual_allocations = [
            {
                key: row[key]
                for key in row
                if key != "id"
            }
            for row in payload.get("allocations", [])
        ]
        if actual_allocations != expected_allocations:
            raise ValueError("generic Sprite allocation audit mismatch")
        expected_implementation = {
            path: _sha256_file(root / path)
            for path in IMPLEMENTATION_PATHS
        }
        if payload.get("implementation") != expected_implementation:
            raise ValueError("generic Sprite implementation hash mismatch")
        if payload.get("authoring_spec") != {
            "file": SPEC_NAME,
            "sha256": file_hashes[SPEC_NAME],
        }:
            raise ValueError("generic Sprite authoring spec binding mismatch")
        if payload.get("base_rom") != {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": _sha256(base),
        }:
            raise ValueError("generic Sprite base ROM binding mismatch")
        if payload.get("layout") != {
            "path": "sequel/rom-layout.json",
            "sha256": _sha256_file(layout_path),
            "target_rom_size": layout.target_rom_size,
            "partition": regions.parent.id,
            "owner": regions.parent.owner,
        }:
            raise ValueError("generic Sprite layout binding mismatch")
        if payload.get("catalogs") != {
            "static": {
                "path": STATIC_CATALOG_PATH.as_posix(),
                "sha256": _sha256_file(root / STATIC_CATALOG_PATH),
            },
            "animation": {
                "path": ANIMATION_CATALOG_PATH.as_posix(),
                "sha256": _sha256_file(root / ANIMATION_CATALOG_PATH),
            },
        }:
            raise ValueError("generic Sprite catalog binding mismatch")
        if payload.get("region_registry") != {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": _sha256_file(root / REGISTRY_PATH),
            "region": region.id,
            "owner": region.owner,
            "start": region.start,
            "end": region.end,
        }:
            raise ValueError("generic Sprite region binding mismatch")
    except Exception as error:
        errors.append(str(error))
    return {
        "errors": errors,
        "verified_entries": verified_entries,
        "verified_source_pointers": verified_source_pointers,
        "rebuilt_output_rom_sha256": rebuilt_hash,
        "verified_fixture_tiles": fixture_tiles,
        "verified_fixture_components": fixture_components,
        "capability_fixture_output_rom_sha256": fixture_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    result = verify_audit(args.root, args.artifact)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
