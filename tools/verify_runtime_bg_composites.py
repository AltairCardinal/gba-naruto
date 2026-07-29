#!/usr/bin/env python3
"""Independently rebuild and verify runtime-bg-composites-v1."""

from __future__ import annotations

import argparse
from collections import defaultdict
from io import BytesIO
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

from PIL import Image


SCHEMA = "runtime-bg-composites-v1"
WIDTH = 240
HEIGHT = 160
STATE_SIZE = 0x61000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DIMENSIONS = ((256, 256), (512, 256), (256, 512), (512, 512))
SCOPE = {
    "all_tracked_mode0_checkpoint_bg_inputs_decoded": True,
    "enabled_text_bg_tilemap_char_palette_scroll_priority_decoded": True,
    "per_checkpoint_bg_layer_pixels_rendered": True,
    "pre_effect_bg_priority_preview_rendered": True,
    "mosaic_observed_disabled_in_all_inputs": True,
    "static_regular_bg_entry_identity_complete": False,
    "disabled_background_visibility_complete": False,
    "final_bg_obj_backdrop_priority_complete": False,
    "window_mask_pixel_composition_complete": False,
    "obj_window_pixel_composition_complete": False,
    "blend_and_brightness_pixel_composition_complete": False,
    "palette_transform_semantics_complete": False,
    "camera_or_scroll_writer_schedule_complete": False,
    "cross_frame_transition_timing_complete": False,
    "final_screen_composition_complete": False,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _h16(value: int) -> str:
    return f"0x{value:04X}"


def _h32(value: int) -> str:
    return f"0x{value:08X}"


def _rgb(color: int) -> tuple[int, int, int]:
    r, g, b = color & 31, (color >> 5) & 31, (color >> 10) & 31
    return (
        (r << 3) | (r >> 2),
        (g << 3) | (g >> 2),
        (b << 3) | (b >> 2),
    )


def _png(mode: str, pixels: bytes) -> bytes:
    image = Image.frombytes(mode, (WIDTH, HEIGHT), pixels)
    output = BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _state(path: Path) -> bytes:
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path.name}: invalid PNG signature")
    cursor = len(PNG_SIGNATURE)
    payloads: list[bytes] = []
    while cursor < len(raw):
        if cursor + 12 > len(raw):
            raise ValueError(f"{path.name}: truncated PNG chunk")
        size = struct.unpack_from(">I", raw, cursor)[0]
        tag = raw[cursor + 4 : cursor + 8]
        payload_start = cursor + 8
        payload_end = payload_start + size
        if payload_end + 4 > len(raw):
            raise ValueError(f"{path.name}: truncated PNG payload")
        payload = raw[payload_start:payload_end]
        stored_crc = struct.unpack_from(">I", raw, payload_end)[0]
        if stored_crc != zlib.crc32(tag + payload) & 0xFFFFFFFF:
            raise ValueError(f"{path.name}: PNG CRC mismatch")
        if tag == b"gbAs":
            payloads.append(payload)
        cursor = payload_end + 4
        if tag == b"IEND":
            break
    if cursor != len(raw) or len(payloads) != 1:
        raise ValueError(f"{path.name}: invalid savestate container")
    decompressor = zlib.decompressobj()
    state = decompressor.decompress(payloads[0], STATE_SIZE + 1)
    state += decompressor.flush()
    if (
        len(state) != STATE_SIZE
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise ValueError(f"{path.name}: invalid gbAs payload")
    version = struct.unpack_from("<I", state, 0)[0]
    if not 0x01000000 <= version <= 0x0100000B:
        raise ValueError(f"{path.name}: unsupported state version")
    return state


def _memory(state: bytes, address: int, size: int) -> bytes:
    regions = (
        (0x04000000, 0x400, 0x400),
        (0x05000000, 0x400, 0x800),
        (0x07000000, 0x400, 0xC00),
        (0x06000000, 0x18000, 0x1000),
    )
    for base, length, offset in regions:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[offset + relative : offset + relative + size]
    raise ValueError(f"unsupported memory range 0x{address:08X}+0x{size:X}")


def _map_offset(base: int, size: int, tile_x: int, tile_y: int) -> int:
    if size == 0:
        block = 0
    elif size == 1:
        block = tile_x // 32
    elif size == 2:
        block = tile_y // 32
    else:
        block = tile_x // 32 + (tile_y // 32) * 2
    return base + block * 0x800 + ((tile_y % 32) * 32 + tile_x % 32) * 2


def _background(io: bytes, index: int, enabled: bool) -> dict[str, object]:
    control = _u16(io, 8 + index * 2)
    size = (control >> 14) & 3
    width, height = DIMENSIONS[size]
    char_block = (control >> 2) & 3
    screen_block = (control >> 8) & 31
    return {
        "index": index,
        "enabled": enabled,
        "bgcnt": _h16(control),
        "priority": control & 3,
        "char_base_block": char_block,
        "char_base_address": _h32(0x06000000 + char_block * 0x4000),
        "mosaic": bool(control & 0x40),
        "color_depth_bpp": 8 if control & 0x80 else 4,
        "screen_base_block": screen_block,
        "screen_base_address": _h32(0x06000000 + screen_block * 0x800),
        "affine_wrap_bit": bool(control & 0x2000),
        "size_code": size,
        "width_pixels": width,
        "height_pixels": height,
        "hofs": _u16(io, 0x10 + index * 4) & 0x1FF,
        "vofs": _u16(io, 0x12 + index * 4) & 0x1FF,
    }


def _layer(
    io: bytes, palette: bytes, vram: bytes, index: int
) -> tuple[bytes, list[int | None]]:
    control = _u16(io, 8 + index * 2)
    size = (control >> 14) & 3
    width, height = DIMENSIONS[size]
    scroll_x = _u16(io, 0x10 + index * 4) & 0x1FF
    scroll_y = _u16(io, 0x12 + index * 4) & 0x1FF
    map_base = ((control >> 8) & 31) * 0x800
    char_base = ((control >> 2) & 3) * 0x4000
    is_8bpp = bool(control & 0x80)
    rgba = bytearray()
    colors: list[int | None] = []
    for sy in range(HEIGHT):
        y = (sy + scroll_y) % height
        for sx in range(WIDTH):
            x = (sx + scroll_x) % width
            offset = _map_offset(map_base, size, x // 8, y // 8)
            if offset + 2 > len(vram):
                raise ValueError(f"BG{index}: tilemap outside BG VRAM")
            entry = _u16(vram, offset)
            px, py = x & 7, y & 7
            if entry & 0x400:
                px = 7 - px
            if entry & 0x800:
                py = 7 - py
            tile = entry & 0x3FF
            if is_8bpp:
                tile_offset = char_base + tile * 64 + py * 8 + px
                if tile_offset >= len(vram):
                    raise ValueError(f"BG{index}: tile outside BG VRAM")
                palette_index = vram[tile_offset]
            else:
                tile_offset = char_base + tile * 32 + py * 4 + px // 2
                if tile_offset >= len(vram):
                    raise ValueError(f"BG{index}: tile outside BG VRAM")
                packed = vram[tile_offset]
                palette_index = (packed >> (4 if px & 1 else 0)) & 15
                if palette_index:
                    palette_index += ((entry >> 12) & 15) * 16
            if not palette_index:
                rgba.extend((0, 0, 0, 0))
                colors.append(None)
            else:
                color = _u16(palette, palette_index * 2)
                rgba.extend((*_rgb(color), 255))
                colors.append(color)
    return bytes(rgba), colors


def _checkpoint(root: Path, path: Path) -> tuple[dict[str, object], dict[str, bytes]]:
    state = _state(path)
    io = _memory(state, 0x04000000, 0x400)
    pram = _memory(state, 0x05000000, 0x400)
    oam = _memory(state, 0x07000000, 0x400)
    full_vram = _memory(state, 0x06000000, 0x18000)
    palette, vram = pram[:0x200], full_vram[:0x10000]
    dispcnt = _u16(io, 0)
    if dispcnt & 7 or dispcnt & 0x80:
        raise ValueError(f"{path.name}: unsupported display state")
    enabled = [index for index in range(4) if dispcnt & (1 << (8 + index))]
    mosaic = _u16(io, 0x4C)
    if mosaic:
        raise ValueError(f"{path.name}: nonzero mosaic")
    blend = _u16(io, 0x50)
    state_id = _sha(io[:0x58] + palette + vram)
    return (
        {
            "path": path.relative_to(root).as_posix(),
            "checkpoint_sha256": _sha(path.read_bytes()),
            "regions": {
                "io": {"size": len(io), "sha256": _sha(io)},
                "pram": {"size": len(pram), "sha256": _sha(pram)},
                "vram": {"size": len(full_vram), "sha256": _sha(full_vram)},
                "oam": {"size": len(oam), "sha256": _sha(oam)},
            },
            "bg_vram_sha256": _sha(vram),
            "bg_palette_sha256": _sha(palette),
            "display": {
                "dispcnt": _h32(dispcnt),
                "mode": 0,
                "forced_blank": False,
                "enabled_backgrounds": enabled,
                "obj_enabled": bool(dispcnt & 0x1000),
                "win0_enabled": bool(dispcnt & 0x2000),
                "win1_enabled": bool(dispcnt & 0x4000),
                "obj_window_enabled": bool(dispcnt & 0x8000),
            },
            "backgrounds": [
                _background(io, index, index in enabled) for index in range(4)
            ],
            "window_registers": {
                "win0h": _h16(_u16(io, 0x40)),
                "win1h": _h16(_u16(io, 0x42)),
                "win0v": _h16(_u16(io, 0x44)),
                "win1v": _h16(_u16(io, 0x46)),
                "winin": _h16(_u16(io, 0x48)),
                "winout": _h16(_u16(io, 0x4A)),
            },
            "mosaic": _h16(mosaic),
            "blend_registers": {
                "bldcnt": _h16(blend),
                "effect": (blend >> 6) & 3,
                "first_targets": blend & 63,
                "second_targets": (blend >> 8) & 63,
                "bldalpha": _h16(_u16(io, 0x52)),
                "bldy": _h16(_u16(io, 0x54)),
            },
            "state_id": state_id,
        },
        {"io": io[:0x58], "palette": palette, "vram": vram},
    )


def _state_record(
    state_id: str, paths: list[str], domains: dict[str, bytes]
) -> tuple[dict[str, object], dict[str, bytes]]:
    io, palette, vram = domains["io"], domains["palette"], domains["vram"]
    dispcnt = _u16(io, 0)
    enabled = [index for index in range(4) if dispcnt & (1 << (8 + index))]
    members: dict[str, bytes] = {}
    outputs, layers = [], []
    colors: dict[int, list[int | None]] = {}
    prefix = f"states/{state_id[:16]}"
    for index in enabled:
        rgba, values = _layer(io, palette, vram, index)
        colors[index] = values
        raw = _png("RGBA", rgba)
        member = f"{prefix}/bg{index}.png"
        members[member] = raw
        outputs.append(
            {
                "kind": "enabled-bg-layer",
                "bg_index": index,
                "archive_member": member,
                "width": WIDTH,
                "height": HEIGHT,
                "mode": "RGBA",
                "transparent_tile_color_zero": True,
                "sha256": _sha(raw),
            }
        )
        layers.append(
            {
                "bg_index": index,
                "priority": _u16(io, 8 + index * 2) & 3,
                "rgba_sha256": _sha(rgba),
                "opaque_pixel_count": sum(value is not None for value in values),
            }
        )
    order = sorted(enabled, key=lambda i: (_u16(io, 8 + i * 2) & 3, i))
    backdrop = _u16(palette, 0)
    rgb = bytearray()
    for position in range(WIDTH * HEIGHT):
        color = next(
            (
                colors[index][position]
                for index in order
                if colors[index][position] is not None
            ),
            backdrop,
        )
        rgb.extend(_rgb(color))
    pixels = bytes(rgb)
    raw = _png("RGB", pixels)
    member = f"{prefix}/pre-effect-bg-preview.png"
    members[member] = raw
    outputs.append(
        {
            "kind": "debug-pre-effect-bg-priority-preview",
            "bg_index": None,
            "archive_member": member,
            "width": WIDTH,
            "height": HEIGHT,
            "mode": "RGB",
            "sha256": _sha(raw),
            "rgb_sha256": _sha(pixels),
        }
    )
    return (
        {
            "state_id": state_id,
            "checkpoint_paths": paths,
            "enabled_backgrounds": enabled,
            "layers": layers,
            "backdrop_bgr555": _h16(backdrop),
            "composite_semantics": (
                "debug-preview-pre-window-pre-blend-bg-only-not-final-frame"
            ),
            "outputs": outputs,
        },
        members,
    )


def _archive(members: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name], compresslevel=9)
    return output.getvalue()


def _expected(
    root: Path,
) -> tuple[dict[str, object], bytes, dict[str, object]]:
    records = []
    domains_by_id: dict[str, dict[str, bytes]] = {}
    paths_by_id: defaultdict[str, list[str]] = defaultdict(list)
    for path in sorted((root / "artifacts/runtime-checkpoints").glob("*.ss9")):
        record, domains = _checkpoint(root, path)
        records.append(record)
        state_id = str(record["state_id"])
        paths_by_id[state_id].append(str(record["path"]))
        previous = domains_by_id.setdefault(state_id, domains)
        if previous != domains:
            raise ValueError(f"state collision {state_id}")
    states, members = [], {}
    for state_id in sorted(domains_by_id):
        state_record, state_members = _state_record(
            state_id, paths_by_id[state_id], domains_by_id[state_id]
        )
        states.append(state_record)
        if set(members).intersection(state_members):
            raise ValueError("duplicate archive member")
        members.update(state_members)
    archive = _archive(members)
    expected = {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha(
                (root / "tools/export_runtime_bg_composites.py").read_bytes()
            ),
            "verifier_sha256": _sha(
                (root / "tools/verify_runtime_bg_composites.py").read_bytes()
            ),
            "test_sha256": _sha(
                (root / "tests/test_export_runtime_bg_composites.py").read_bytes()
            ),
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_glob": "*.ss9",
        },
        "decoder": {
            "display_mode_requirement": 0,
            "screen_size": [WIDTH, HEIGHT],
            "memory_region_sizes": {
                "io": 0x400,
                "pram": 0x400,
                "vram": 0x18000,
                "oam": 0x400,
            },
            "bg_palette_size": 0x200,
            "bg_vram_size": 0x10000,
            "mode0_text_bg_only": True,
        },
        "summary": {
            "checkpoint_count": len(records),
            "mode0_checkpoint_count": len(records),
            "unique_state_count": len(states),
            "win0_checkpoint_count": sum(
                bool(item["display"]["win0_enabled"]) for item in records
            ),
            "nonzero_blend_checkpoint_count": sum(
                item["blend_registers"]["bldcnt"] != "0x0000"
                for item in records
            ),
            "archive_member_count": len(members),
        },
        "archive": {
            "file": "layers.zip",
            "size": len(archive),
            "sha256": _sha(archive),
            "member_count": len(members),
            "deterministic_zip_timestamp": "1980-01-01T00:00:00",
        },
        "checkpoints": records,
        "states": states,
        "scope": SCOPE,
    }
    data_bytes = (
        json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            "layers.zip": _sha(archive),
            "runtime-bg-composites.json": _sha(data_bytes),
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_count": len(records),
            "unique_state_count": len(states),
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_runtime_bg_composites.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/runtime-bg-composites-v1",
            ],
            **expected["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_runtime_bg_composites.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/runtime-bg-composites-v1",
            ],
            "verifier_sha256": expected["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": "runtime-bg-composites-verification-v1",
                "verified": True,
                "checkpoint_count": len(records),
                "state_count": len(states),
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-bg-composites",
            "run_id": "tracked-mode0-bg-20260730-01",
        },
    }
    return expected, archive, promotion


def verify_artifact(root: Path, artifact: Path) -> dict[str, object]:
    errors: list[str] = []
    root, artifact = Path(root).resolve(), Path(artifact).resolve()
    try:
        expected, expected_archive, expected_promotion = _expected(root)
    except Exception as error:
        return {
            "schema": "runtime-bg-composites-verification-v1",
            "verified": False,
            "checkpoint_count": 0,
            "state_count": 0,
            "errors": [f"rebuild failed: {error}"],
        }
    try:
        actual = json.loads(
            (artifact / "runtime-bg-composites.json").read_text(encoding="utf-8")
        )
    except Exception as error:
        actual = {}
        errors.append(f"manifest read failed: {error}")
    if actual != expected:
        errors.append("runtime data does not match independent reconstruction")
    try:
        promotion = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        if promotion != expected_promotion:
            errors.append("promotion manifest does not match reconstruction")
    except Exception as error:
        errors.append(f"promotion manifest read failed: {error}")
    try:
        archive = (artifact / "layers.zip").read_bytes()
        if archive != expected_archive:
            errors.append("layers.zip does not match independent reconstruction")
        with zipfile.ZipFile(BytesIO(archive)) as bundle:
            if bundle.testzip() is not None:
                errors.append("layers.zip has a corrupt member")
    except Exception as error:
        errors.append(f"archive verification failed: {error}")
    files = sorted(
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    )
    if files != ["layers.zip", "manifest.json", "runtime-bg-composites.json"]:
        errors.append(f"unexpected artifact files: {files}")
    return {
        "schema": "runtime-bg-composites-verification-v1",
        "verified": not errors,
        "checkpoint_count": len(expected["checkpoints"]),
        "state_count": len(expected["states"]),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/runtime-bg-composites-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
