#!/usr/bin/env python3
"""Decode scenario 41 reference GPU registers and OAM without emulation."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


REGION_SIZES = {
    "io": 0x400,
    "pram": 0x400,
    "oam": 0x400,
    "vram": 0x18000,
}
_OBJ_DIMENSIONS = {
    0: ((8, 8), (16, 16), (32, 32), (64, 64)),
    1: ((16, 8), (32, 8), (32, 16), (64, 32)),
    2: ((8, 16), (8, 32), (16, 32), (32, 64)),
}
_TEXT_BG_DIMENSIONS = ((256, 256), (512, 256), (256, 512), (512, 512))
_AFFINE_BG_DIMENSIONS = ((128, 128), (256, 256), (512, 512), (1024, 1024))


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _s32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def _decode_background(io: bytes, index: int, mode: int) -> dict[str, object]:
    control = _u16(io, 0x08 + index * 2)
    size = (control >> 14) & 3
    affine = index >= 2 and mode in (1, 2)
    result: dict[str, object] = {
        "control": f"0x{control:04X}",
        "priority": control & 3,
        "character_base_block": (control >> 2) & 3,
        "character_base": f"0x{0x06000000 + ((control >> 2) & 3) * 0x4000:08X}",
        "mosaic": bool(control & (1 << 6)),
        "colors": 256 if control & (1 << 7) else 16,
        "screen_base_block": (control >> 8) & 0x1F,
        "screen_base": f"0x{0x06000000 + ((control >> 8) & 0x1F) * 0x800:08X}",
        "affine_wrap": bool(control & (1 << 13)),
        "size_code": size,
        "affine": affine,
        "dimensions": list(
            _AFFINE_BG_DIMENSIONS[size] if affine else _TEXT_BG_DIMENSIONS[size]
        ),
    }
    if affine:
        base = 0x20 if index == 2 else 0x30
        result["affine_parameters"] = {
            "pa": _u16(io, base),
            "pb": _u16(io, base + 2),
            "pc": _u16(io, base + 4),
            "pd": _u16(io, base + 6),
            "reference_x_raw": _s32(io, base + 8),
            "reference_y_raw": _s32(io, base + 12),
        }
    else:
        result["scroll"] = {
            "x": _u16(io, 0x10 + index * 4) & 0x1FF,
            "y": _u16(io, 0x12 + index * 4) & 0x1FF,
        }
    return result


def _window_range(value: int) -> dict[str, int]:
    return {"left": (value >> 8) & 0xFF, "right": value & 0xFF}


def _window(io: bytes, horizontal_offset: int, vertical_offset: int) -> dict[str, int]:
    horizontal = _window_range(_u16(io, horizontal_offset))
    vertical = _window_range(_u16(io, vertical_offset))
    return {
        "left": horizontal["left"],
        "right": horizontal["right"],
        "top": vertical["left"],
        "bottom": vertical["right"],
    }


def _decode_objects(oam: bytes) -> list[dict[str, object]]:
    objects = []
    for index in range(128):
        offset = index * 8
        attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, offset)
        affine = bool(attr0 & (1 << 8))
        if not affine and attr0 & (1 << 9):
            continue
        shape = (attr0 >> 14) & 3
        if shape not in _OBJ_DIMENSIONS:
            raise ValueError(f"active OAM entry {index} uses prohibited shape 3")
        size = (attr1 >> 14) & 3
        raw_x = attr1 & 0x1FF
        raw_y = attr0 & 0xFF
        color_256 = bool(attr0 & (1 << 13))
        obj_mode = (attr0 >> 10) & 3
        objects.append(
            {
                "index": index,
                "raw": f"{attr0:04x}{attr1:04x}{attr2:04x}",
                "position": {
                    "x": raw_x - 512 if raw_x >= 256 else raw_x,
                    "y": raw_y - 256 if raw_y >= 160 else raw_y,
                    "raw_x": raw_x,
                    "raw_y": raw_y,
                },
                "shape": shape,
                "size": size,
                "dimensions": list(_OBJ_DIMENSIONS[shape][size]),
                "affine": affine,
                "double_size": bool(attr0 & (1 << 9)) if affine else False,
                "affine_parameter_index": (attr1 >> 9) & 0x1F if affine else None,
                "horizontal_flip": bool(attr1 & (1 << 12)) if not affine else False,
                "vertical_flip": bool(attr1 & (1 << 13)) if not affine else False,
                "object_mode": obj_mode,
                "mosaic": bool(attr0 & (1 << 12)),
                "colors": 256 if color_256 else 16,
                "tile_index": attr2 & 0x3FF,
                "priority": (attr2 >> 10) & 3,
                "palette_bank": None if color_256 else (attr2 >> 12) & 0xF,
            }
        )
    return objects


def decode_gpu(io: bytes, oam: bytes) -> dict[str, object]:
    """Decode the display state from exact serialized I/O and OAM regions."""

    if len(io) != REGION_SIZES["io"]:
        raise ValueError(f"I/O region must be 0x{REGION_SIZES['io']:X} bytes")
    if len(oam) != REGION_SIZES["oam"]:
        raise ValueError(f"OAM region must be 0x{REGION_SIZES['oam']:X} bytes")
    dispcnt = _u16(io, 0)
    mode = dispcnt & 7
    if mode > 5:
        raise ValueError(f"reserved GBA display mode {mode}")
    enabled_backgrounds = [index for index in range(4) if dispcnt & (1 << (8 + index))]
    windows = {
        "win0": _window(io, 0x40, 0x44),
        "win1": _window(io, 0x42, 0x46),
        "inside_control": f"0x{_u16(io, 0x48):04X}",
        "outside_control": f"0x{_u16(io, 0x4A):04X}",
    }
    blend_control = _u16(io, 0x50)
    alpha = _u16(io, 0x52)
    brightness = _u16(io, 0x54)
    return {
        "display": {
            "control": f"0x{dispcnt:04X}",
            "mode": mode,
            "frame_select": bool(dispcnt & (1 << 4)),
            "obj_character_mapping": "1d" if dispcnt & (1 << 6) else "2d",
            "forced_blank": bool(dispcnt & (1 << 7)),
            "enabled_backgrounds": enabled_backgrounds,
            "obj_enabled": bool(dispcnt & (1 << 12)),
            "windows": {
                "win0_enabled": bool(dispcnt & (1 << 13)),
                "win1_enabled": bool(dispcnt & (1 << 14)),
                "obj_window_enabled": bool(dispcnt & (1 << 15)),
            },
        },
        "backgrounds": {
            str(index): _decode_background(io, index, mode)
            for index in enabled_backgrounds
        },
        "windows": windows,
        "blend": {
            "control": f"0x{blend_control:04X}",
            "effect": (blend_control >> 6) & 3,
            "first_targets": blend_control & 0x3F,
            "second_targets": (blend_control >> 8) & 0x3F,
            "eva": alpha & 0x1F,
            "evb": (alpha >> 8) & 0x1F,
            "evy": brightness & 0x1F,
        },
        "objects": _decode_objects(oam),
    }


def _read_region(boundary: Path, name: str) -> bytes:
    data = (boundary / f"{name}.bin").read_bytes()
    expected = REGION_SIZES[name]
    if len(data) != expected:
        raise ValueError(f"{name} region is {len(data)} bytes; expected {expected}")
    return data


def analyze_boundary(path: Path) -> dict[str, object]:
    """Analyze one directory produced by export_scenario_41_reference.py."""

    path = Path(path)
    manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
    if path.name not in manifest["boundaries"]:
        raise ValueError(f"boundary {path.name!r} is absent from manifest")
    source = manifest["boundaries"][path.name]
    loaded = {name: _read_region(path, name) for name in REGION_SIZES}
    for name, data in loaded.items():
        actual = hashlib.sha256(data).hexdigest()
        expected = source["regions"][name]["sha256"]
        if actual != expected:
            raise ValueError(f"{path.name} {name} SHA-256 mismatch")
    decoded = decode_gpu(loaded["io"], loaded["oam"])
    return {
        "schema_version": 1,
        "boundary": path.name,
        "screen": source["screen"],
        "resource_regions": {
            name: {
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for name, data in loaded.items()
        },
        **decoded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.reference / "manifest.json").read_text(encoding="utf-8"))
    analysis = {
        "schema_version": 1,
        "boundaries": {
            name: analyze_boundary(args.reference / name)
            for name in sorted(manifest["boundaries"])
        },
    }
    args.output.write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "boundary_count": len(analysis["boundaries"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
