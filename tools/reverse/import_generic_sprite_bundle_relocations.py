#!/usr/bin/env python3
"""Relocate the fixed 43-ID generic Sprite bundle into expanded ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.gba_image_export import encode_gba_lz77
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


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
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")
SPEC_SCHEMA = "generic-sprite-bundle-relocation-v1"
PAIR_TABLE_OFFSET = 0x53F140
TILE_OFFSET_TABLE_OFFSET = 0x53F298
ENTRY_COUNT = 43
PAIR_ENTRY_SIZE = 8
COMPONENT_SIZE = 0x14
GRAPHICS_POINTER_OFFSET = 0x080A94
PALETTE_POINTER_OFFSET = 0x080A9C
GRAPHICS_SOURCE_OFFSET = 0x12F298
PALETTE_SOURCE_OFFSET = 0x12F584
SEQUENCE_BYTES = bytes.fromhex("00000100ffff0000")
TERMINATOR = bytes.fromhex("ffff0000")
MAX_COMPONENTS = 2
MAX_RUNTIME_TILE_BASE = 0x39F
MAX_GRAPHICS_TILES = 0x400 - MAX_RUNTIME_TILE_BASE
SUPPORTED_SIZES = {
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

# Every natural caller supplies either tile base 0x34E or 0x39F.  The short
# slice binds the load/move, palette bank and BL to the canonical loader; the
# literal offsets bind the actual tile-base values.
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path")
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_catalog(
    root: Path,
    path: Path,
    expected_hash: str,
    expected_schema: str,
) -> tuple[dict[str, Any], bytes]:
    data = (root / path).read_bytes()
    if _sha256(data) != expected_hash:
        raise ValueError(f"{path} SHA-256 mismatch")
    payload = json.loads(data)
    if not isinstance(payload, dict) or payload.get("schema") != expected_schema:
        raise ValueError(f"{path} schema mismatch")
    return payload, data


def _rom_offset(pointer: int, rom_size: int, label: str) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"{label} pointer 0x{pointer:08X} is outside ROM")
    return offset


def _verify_runtime_tile_capacity(rom: bytes) -> None:
    target = 0x08080A48
    calls = set()
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
        if first & 0x0400:
            displacement -= 1 << 23
        if ROM_BASE + offset + 4 + displacement == target:
            calls.add(ROM_BASE + offset)
    expected_calls = {address for address, _ in CALL_SLICES}
    if calls != expected_calls:
        raise ValueError(
            "generic Sprite loader call-site denominator mismatch: "
            f"expected {sorted(expected_calls)}, got {sorted(calls)}"
        )
    for address, digest in CALL_SLICES:
        offset = address - ROM_BASE
        if _sha256(rom[offset - 4 : offset + 4]) != digest:
            raise ValueError(
                f"generic Sprite loader call slice 0x{address:08X} mismatch"
            )
    values = []
    for offset, expected in CALL_BASE_LITERALS:
        actual = struct.unpack_from("<I", rom, offset)[0]
        if actual != expected:
            raise ValueError(
                f"generic Sprite runtime tile base literal 0x{offset:X} mismatch"
            )
        values.append(actual)
    if max(values) != MAX_RUNTIME_TILE_BASE:
        raise ValueError("generic Sprite maximum runtime tile base mismatch")


def catalog_generic_sprite_bundle(
    root: Path,
    rom: bytes | None = None,
) -> dict[str, Any]:
    """Rebuild the fixed IDs and all 174 exact source pointer references."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("generic Sprite relocation base ROM SHA-256 mismatch")
    static, _ = _read_catalog(
        root,
        STATIC_CATALOG_PATH,
        STATIC_CATALOG_SHA256,
        "sprite-definition-assets-v2",
    )
    animations, _ = _read_catalog(
        root,
        ANIMATION_CATALOG_PATH,
        ANIMATION_CATALOG_SHA256,
        "sprite-definition-animations-v1",
    )
    if (
        static.get("entry_count") != ENTRY_COUNT
        or animations.get("entry_count") != ENTRY_COUNT
        or len(static.get("entries", [])) != ENTRY_COUNT
        or len(animations.get("entries", [])) != ENTRY_COUNT
    ):
        raise ValueError("generic Sprite catalog denominator mismatch")
    _verify_runtime_tile_capacity(base)

    animations_by_id = {row.get("id"): row for row in animations["entries"]}
    expected: dict[int, set[int]] = {}
    reference_kinds: dict[int, set[str]] = {}
    entries: list[dict[str, Any]] = []
    component_count = 0

    def expect(pointer: int, offset: int, kind: str) -> None:
        expected.setdefault(pointer, set()).add(offset)
        reference_kinds.setdefault(pointer, set()).add(kind)

    for entry_id, source in enumerate(static["entries"]):
        if source.get("id") != entry_id or entry_id not in animations_by_id:
            raise ValueError("generic Sprite catalog ID mismatch")
        pair_offset = PAIR_TABLE_OFFSET + entry_id * PAIR_ENTRY_SIZE
        definition_pointer, animation_pointer = struct.unpack_from(
            "<II", base, pair_offset
        )
        if (
            source.get("pair_file_offset") != pair_offset
            or int(source.get("definition_pointer", "0"), 16)
            != definition_pointer
            or int(source.get("animation_pointer", "0"), 16)
            != animation_pointer
        ):
            raise ValueError(f"generic Sprite entry {entry_id} pair mismatch")
        definition_offset = _rom_offset(
            definition_pointer, len(base), "definition"
        )
        animation_offset = _rom_offset(
            animation_pointer, len(base), "animation table"
        )
        component_pointer = struct.unpack_from("<I", base, definition_offset)[0]
        sequence_pointer = struct.unpack_from("<I", base, animation_offset)[0]
        if (
            int(source.get("component_list_pointer", "0"), 16)
            != component_pointer
            or sequence_pointer != definition_pointer + 4
            or base[definition_offset + 4 : definition_offset + 12]
            != SEQUENCE_BYTES
        ):
            raise ValueError(f"generic Sprite entry {entry_id} structure mismatch")
        animation = animations_by_id[entry_id]
        if (
            int(animation.get("animation_table_pointer", "0"), 16)
            != animation_pointer
            or int(animation.get("sequence_pointer", "0"), 16)
            != sequence_pointer
        ):
            raise ValueError(f"generic Sprite entry {entry_id} animation mismatch")

        component_offset = _rom_offset(
            component_pointer, len(base), "component list"
        )
        size = source.get("component_list_size")
        if (
            not isinstance(size, int)
            or base[component_offset : component_offset + size].hex()
            != "".join(
                component["raw_hex"] for component in source["components"]
            )
            + TERMINATOR.hex()
        ):
            raise ValueError(
                f"generic Sprite entry {entry_id} component bytes mismatch"
            )
        tile_base_offset = struct.unpack_from(
            "<H", base, TILE_OFFSET_TABLE_OFFSET + entry_id * 2
        )[0]
        if tile_base_offset != source.get("tile_base_offset"):
            raise ValueError(f"generic Sprite entry {entry_id} tile base mismatch")

        expect(definition_pointer, pair_offset, "definition")
        expect(animation_pointer, pair_offset + 4, "animation_table")
        expect(component_pointer, definition_offset, "component_list")
        expect(sequence_pointer, animation_offset, "sequence")
        entries.append(
            {
                "id": entry_id,
                "pair_offset": pair_offset,
                "definition_pointer": definition_pointer,
                "animation_pointer": animation_pointer,
                "component_pointer": component_pointer,
                "sequence_pointer": sequence_pointer,
                "tile_base_offset": tile_base_offset,
                "component_count": source["component_count"],
            }
        )
        component_count += source["component_count"]

    graphics_pointer = struct.unpack_from("<I", base, GRAPHICS_POINTER_OFFSET)[0]
    palette_pointer = struct.unpack_from("<I", base, PALETTE_POINTER_OFFSET)[0]
    if (
        graphics_pointer != ROM_BASE + GRAPHICS_SOURCE_OFFSET
        or palette_pointer != ROM_BASE + PALETTE_SOURCE_OFFSET
    ):
        raise ValueError("generic Sprite static resource pointer mismatch")
    expect(graphics_pointer, GRAPHICS_POINTER_OFFSET, "graphics")
    expect(palette_pointer, PALETTE_POINTER_OFFSET, "palette")

    actual = {pointer: set() for pointer in expected}
    for offset in range(0, len(base) - 3, 4):
        value = struct.unpack_from("<I", base, offset)[0]
        if value in actual:
            actual[value].add(offset)
    unexpected = []
    missing = []
    for pointer in sorted(expected):
        missing.extend(sorted(expected[pointer] - actual[pointer]))
        unexpected.extend(sorted(actual[pointer] - expected[pointer]))
    if missing:
        raise ValueError(
            f"generic Sprite exact pointer inventory missing {missing}"
        )

    kind_counts = {
        kind: sum(
            len(expected[pointer])
            for pointer in expected
            if kind in reference_kinds[pointer]
        )
        for kind in (
            "definition",
            "animation_table",
            "component_list",
            "sequence",
            "graphics",
            "palette",
        )
    }
    return {
        "entry_count": len(entries),
        "component_count": component_count,
        "graphics_tile_count": (
            static["static_resources"]["graphics"]["tile_count"]
        ),
        "maximum_runtime_tile_base": MAX_RUNTIME_TILE_BASE,
        "maximum_safe_graphics_tiles": MAX_GRAPHICS_TILES,
        "runtime_loader_call_count": len(CALL_SLICES),
        "runtime_tile_bases": sorted(
            {value for _, value in CALL_BASE_LITERALS}
        ),
        "pointer_reference_counts": kind_counts,
        "pointer_reference_count": sum(kind_counts.values()),
        "unexpected_pointer_offsets": unexpected,
        "entries": entries,
    }


def _integer(
    value: object,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{label} must be in {minimum}..{maximum}")
    return value


def _encode_component(
    component: object,
    *,
    entry_id: int,
    component_id: int,
    tile_base: int,
    graphics_tiles: int,
) -> bytes:
    if not isinstance(component, dict):
        raise ValueError(
            f"entry {entry_id} component {component_id} must be an object"
        )
    label = f"entry {entry_id} component {component_id}"
    tile_offset = _integer(component.get("tile_offset"), f"{label} tile_offset", 0, 0x3FF)
    flag_02 = _integer(component.get("flag_02"), f"{label} flag_02", 0, 0xFF)
    flag_03 = _integer(component.get("flag_03"), f"{label} flag_03", 0, 0xFF)
    x = _integer(
        component.get("horizontal_position_input"),
        f"{label} horizontal_position_input",
        -0x8000,
        0x7FFF,
    )
    y = _integer(
        component.get("vertical_position_input"),
        f"{label} vertical_position_input",
        -0x8000,
        0x7FFF,
    )
    width = _integer(component.get("width"), f"{label} width", 1, 64)
    height = _integer(component.get("height"), f"{label} height", 1, 64)
    if (width, height) not in SUPPORTED_SIZES:
        raise ValueError(f"{label} OBJ size is unsupported")
    transform_0c = _integer(
        component.get("transform_factor_0c"),
        f"{label} transform_factor_0c",
        -0x8000,
        0x7FFF,
    )
    transform_0e = _integer(
        component.get("transform_factor_0e"),
        f"{label} transform_factor_0e",
        -0x8000,
        0x7FFF,
    )
    unknown_10 = _integer(
        component.get("unknown_10_byte"),
        f"{label} unknown_10_byte",
        0,
        0xFF,
    )
    oam_attribute = _integer(
        component.get("oam_attribute_byte"),
        f"{label} oam_attribute_byte",
        0,
        0xFF,
    )
    unknown_12 = _integer(
        component.get("unknown_12"),
        f"{label} unknown_12",
        0,
        0xFFFF,
    )
    tile_end = tile_base + tile_offset + width * height // 64
    if tile_end > graphics_tiles:
        raise ValueError(
            f"{label} tile range ends at {tile_end}, beyond "
            f"graphics tile count {graphics_tiles}"
        )
    return struct.pack(
        "<HBBhhhhhhBBH",
        tile_offset,
        flag_02,
        flag_03,
        x,
        y,
        width,
        height,
        transform_0c,
        transform_0e,
        unknown_10,
        oam_attribute,
        unknown_12,
    )


def _allocation(
    *,
    patch_id: str,
    offset: int,
    data: bytes,
    resource_type: str,
    region_id: str,
    region_owner: str,
    **metadata: object,
) -> dict[str, Any]:
    return {
        "id": patch_id,
        "type": "bytes",
        "offset": offset,
        "before_hex": (b"\xFF" * len(data)).hex(),
        "after_hex": data.hex(),
        "patch_class": "allocation",
        "allocation": {
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
            "region": region_id,
            "region_owner": region_owner,
        },
        "asset_type": "generic_sprite_bundle_allocation",
        "resource_type": resource_type,
        **metadata,
    }


def _redirect(
    base: bytes,
    *,
    patch_id: str,
    offset: int,
    pointer: int,
    role: str,
    **metadata: object,
) -> dict[str, Any]:
    return {
        "id": patch_id,
        "type": "bytes",
        "offset": offset,
        "before_hex": base[offset : offset + 4].hex(),
        "after_hex": struct.pack("<I", pointer).hex(),
        "patch_class": "game_effective",
        "asset_type": "generic_sprite_bundle_pointer",
        "pointer_role": role,
        "new_pointer": pointer,
        **metadata,
    }


def resolve_generic_sprite_bundle_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic full-bundle relocation for all fixed generic IDs."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("generic Sprite relocation base ROM SHA-256 mismatch")
    catalog = catalog_generic_sprite_bundle(root, base)
    if catalog["unexpected_pointer_offsets"]:
        raise ValueError("generic Sprite source has unexpected external references")

    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("generic Sprite relocation spec schema mismatch")
    required = {
        "base_rom_sha256": ROM_SHA256,
        "source_static_catalog": STATIC_CATALOG_PATH.as_posix(),
        "source_static_catalog_sha256": STATIC_CATALOG_SHA256,
        "source_animation_catalog": ANIMATION_CATALOG_PATH.as_posix(),
        "source_animation_catalog_sha256": ANIMATION_CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region": "generic-sprite-bundle",
        "region_owner": "generic_sprite_resources",
    }
    for key, expected in required.items():
        if spec.get(key) != expected:
            raise ValueError(f"generic Sprite relocation {key} mismatch")
    registry_path = root / REGION_REGISTRY_PATH
    registry_hash = _sha256(registry_path.read_bytes())
    if spec.get("region_registry_sha256") != registry_hash:
        raise ValueError("generic Sprite region registry SHA-256 mismatch")

    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "generic-sprite-bundle",
        "generic_sprite_resources",
    )

    graphics_path = _resolve(root, spec.get("graphics_file"), "graphics_file")
    palette_path = _resolve(root, spec.get("palette_file"), "palette_file")
    graphics = graphics_path.read_bytes()
    palette = palette_path.read_bytes()
    if (
        not graphics
        or len(graphics) % 32
        or len(graphics) // 32 > MAX_GRAPHICS_TILES
    ):
        raise ValueError(
            f"generic Sprite graphics must contain 1..{MAX_GRAPHICS_TILES} "
            "complete 4bpp tiles"
        )
    if len(palette) != 32:
        raise ValueError("generic Sprite palette must contain exactly 16 colors")
    graphics_tiles = len(graphics) // 32

    authored = spec.get("entries")
    if not isinstance(authored, list) or len(authored) != ENTRY_COUNT:
        raise ValueError("generic Sprite entries must contain exactly IDs 0..42")
    ids = [
        row.get("id") if isinstance(row, dict) else None
        for row in authored
    ]
    if (
        any(isinstance(value, bool) or not isinstance(value, int) for value in ids)
        or set(ids) != set(range(ENTRY_COUNT))
        or len(ids) != len(set(ids))
    ):
        raise ValueError("generic Sprite entries must contain exactly IDs 0..42")
    authored_by_id = {row["id"]: row for row in authored}

    encoded_entries = []
    for entry_id in range(ENTRY_COUNT):
        entry = authored_by_id[entry_id]
        tile_base = _integer(
            entry.get("tile_base_offset"),
            f"entry {entry_id} tile_base_offset",
            0,
            graphics_tiles - 1,
        )
        components = entry.get("components")
        if (
            not isinstance(components, list)
            or not 1 <= len(components) <= MAX_COMPONENTS
        ):
            raise ValueError(
                f"entry {entry_id} must contain 1..{MAX_COMPONENTS} components"
            )
        encoded = b"".join(
            _encode_component(
                component,
                entry_id=entry_id,
                component_id=component_id,
                tile_base=tile_base,
                graphics_tiles=graphics_tiles,
            )
            for component_id, component in enumerate(components)
        )
        encoded_entries.append(
            {
                "id": entry_id,
                "tile_base_offset": tile_base,
                "component_count": len(components),
                "component_bytes": encoded + TERMINATOR,
            }
        )

    graphics_encoded = encode_gba_lz77(graphics)
    palette_encoded = encode_gba_lz77(palette)
    cursor = region.start
    allocations: list[dict[str, Any]] = []

    def allocate(data: bytes, resource_type: str, **metadata: object) -> int:
        nonlocal cursor
        cursor = (cursor + region.alignment - 1) & -region.alignment
        offset = cursor
        cursor += len(data)
        if cursor > region.end:
            raise ValueError(
                "generic Sprite relocation exceeds registered region "
                f"0x{region.start:X}..0x{region.end:X}"
            )
        allocations.append(
            _allocation(
                patch_id=f"generic-sprite-{resource_type}-{offset:06x}",
                offset=offset,
                data=data,
                resource_type=resource_type,
                region_id=region.id,
                region_owner=region.owner,
                **metadata,
            )
        )
        return offset

    graphics_offset = allocate(
        graphics_encoded,
        "graphics",
        decompressed_size=len(graphics),
        encoded_size=len(graphics_encoded),
        replacement_sha256=_sha256(graphics),
        tile_count=graphics_tiles,
        source_file=str(graphics_path),
    )
    palette_offset = allocate(
        palette_encoded,
        "palette",
        decompressed_size=len(palette),
        encoded_size=len(palette_encoded),
        replacement_sha256=_sha256(palette),
        source_file=str(palette_path),
    )

    relocated_entries = []
    for entry in encoded_entries:
        cursor = (cursor + region.alignment - 1) & -region.alignment
        bundle_offset = cursor
        component_pointer = ROM_BASE + bundle_offset
        definition_offset = bundle_offset + len(entry["component_bytes"])
        definition_pointer = ROM_BASE + definition_offset
        sequence_pointer = definition_pointer + 4
        animation_offset = definition_offset + 12
        animation_pointer = ROM_BASE + animation_offset
        bundle = (
            entry["component_bytes"]
            + struct.pack("<I", component_pointer)
            + SEQUENCE_BYTES
            + struct.pack("<I", sequence_pointer)
        )
        allocated = allocate(
            bundle,
            "entry_bundle",
            entry_id=entry["id"],
            component_count=entry["component_count"],
            tile_base_offset=entry["tile_base_offset"],
            definition_pointer=definition_pointer,
            animation_pointer=animation_pointer,
            component_pointer=component_pointer,
            sequence_pointer=sequence_pointer,
        )
        if allocated != bundle_offset:
            raise AssertionError("generic Sprite bundle alignment drift")
        relocated_entries.append(
            {
                **entry,
                "definition_pointer": definition_pointer,
                "animation_pointer": animation_pointer,
            }
        )

    redirects = [
        _redirect(
            base,
            patch_id="generic-sprite-graphics-pointer",
            offset=GRAPHICS_POINTER_OFFSET,
            pointer=ROM_BASE + graphics_offset,
            role="graphics",
        ),
        _redirect(
            base,
            patch_id="generic-sprite-palette-pointer",
            offset=PALETTE_POINTER_OFFSET,
            pointer=ROM_BASE + palette_offset,
            role="palette",
        ),
    ]
    tile_base_patches = []
    for entry in relocated_entries:
        entry_id = entry["id"]
        pair_offset = PAIR_TABLE_OFFSET + entry_id * PAIR_ENTRY_SIZE
        redirects.extend(
            [
                _redirect(
                    base,
                    patch_id=f"generic-sprite-{entry_id:02d}-definition-pointer",
                    offset=pair_offset,
                    pointer=entry["definition_pointer"],
                    role="definition",
                    entry_id=entry_id,
                ),
                _redirect(
                    base,
                    patch_id=f"generic-sprite-{entry_id:02d}-animation-pointer",
                    offset=pair_offset + 4,
                    pointer=entry["animation_pointer"],
                    role="animation_table",
                    entry_id=entry_id,
                ),
            ]
        )
        tile_offset = TILE_OFFSET_TABLE_OFFSET + entry_id * 2
        tile_base_patches.append(
            {
                "id": f"generic-sprite-{entry_id:02d}-tile-base",
                "type": "bytes",
                "offset": tile_offset,
                "before_hex": base[tile_offset : tile_offset + 2].hex(),
                "after_hex": struct.pack(
                    "<H", entry["tile_base_offset"]
                ).hex(),
                "patch_class": "game_effective",
                "asset_type": "generic_sprite_tile_base",
                "entry_id": entry_id,
                "tile_base_offset": entry["tile_base_offset"],
            }
        )
    return [*allocations, *redirects, *tile_base_patches]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve fixed-ID generic Sprite bundle relocation patches."
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    base = (root / "rom/base.gba").read_bytes()
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    patches = resolve_generic_sprite_bundle_relocation_patches(
        root,
        args.spec,
        rom=base,
        layout=layout,
    )
    encoded = json.dumps(
        {"schema": SPEC_SCHEMA, "patches": patches},
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
