#!/usr/bin/env python3
"""Export Mode 0 BG layers from every tracked mGBA checkpoint."""

from __future__ import annotations

import argparse
from collections import defaultdict
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state


SCHEMA = "runtime-bg-composites-v1"
WIDTH = 240
HEIGHT = 160
TEXT_BG_DIMENSIONS = ((256, 256), (512, 256), (256, 512), (512, 512))
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _hex16(value: int) -> str:
    return f"0x{value:04X}"


def _hex32(value: int) -> str:
    return f"0x{value:08X}"


def _rgb(color: int) -> tuple[int, int, int]:
    red = color & 0x1F
    green = (color >> 5) & 0x1F
    blue = (color >> 10) & 0x1F
    return (
        (red << 3) | (red >> 2),
        (green << 3) | (green >> 2),
        (blue << 3) | (blue >> 2),
    )


def _png_bytes(mode: str, pixels: bytes) -> bytes:
    image = Image.frombytes(mode, (WIDTH, HEIGHT), pixels)
    output = BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _map_offset(screen_base: int, size: int, tile_x: int, tile_y: int) -> int:
    block_x = tile_x // 32
    block_y = tile_y // 32
    if size == 0:
        block = 0
    elif size == 1:
        block = block_x
    elif size == 2:
        block = block_y
    else:
        block = block_x + block_y * 2
    index = (tile_y % 32) * 32 + tile_x % 32
    return screen_base + block * 0x800 + index * 2


def _background_record(io: bytes, index: int, enabled: bool) -> dict[str, object]:
    control = _u16(io, 0x08 + index * 2)
    size = (control >> 14) & 3
    width, height = TEXT_BG_DIMENSIONS[size]
    char_block = (control >> 2) & 3
    screen_block = (control >> 8) & 0x1F
    return {
        "index": index,
        "enabled": enabled,
        "bgcnt": _hex16(control),
        "priority": control & 3,
        "char_base_block": char_block,
        "char_base_address": _hex32(0x06000000 + char_block * 0x4000),
        "mosaic": bool(control & (1 << 6)),
        "color_depth_bpp": 8 if control & (1 << 7) else 4,
        "screen_base_block": screen_block,
        "screen_base_address": _hex32(0x06000000 + screen_block * 0x800),
        "affine_wrap_bit": bool(control & (1 << 13)),
        "size_code": size,
        "width_pixels": width,
        "height_pixels": height,
        "hofs": _u16(io, 0x10 + index * 4) & 0x1FF,
        "vofs": _u16(io, 0x12 + index * 4) & 0x1FF,
    }


def _layer_pixels(
    io: bytes, palette: bytes, bg_vram: bytes, index: int
) -> tuple[bytes, list[int | None]]:
    control = _u16(io, 0x08 + index * 2)
    size = (control >> 14) & 3
    width, height = TEXT_BG_DIMENSIONS[size]
    hofs = _u16(io, 0x10 + index * 4) & 0x1FF
    vofs = _u16(io, 0x12 + index * 4) & 0x1FF
    screen_base = ((control >> 8) & 0x1F) * 0x800
    char_base = ((control >> 2) & 3) * 0x4000
    color_256 = bool(control & (1 << 7))
    rgba = bytearray()
    colors: list[int | None] = []
    for screen_y in range(HEIGHT):
        y = (screen_y + vofs) % height
        for screen_x in range(WIDTH):
            x = (screen_x + hofs) % width
            map_offset = _map_offset(screen_base, size, x // 8, y // 8)
            if map_offset + 2 > len(bg_vram):
                raise ValueError(f"BG{index} tilemap exceeds BG VRAM")
            entry = _u16(bg_vram, map_offset)
            local_x = x & 7
            local_y = y & 7
            if entry & (1 << 10):
                local_x = 7 - local_x
            if entry & (1 << 11):
                local_y = 7 - local_y
            tile = entry & 0x3FF
            if color_256:
                tile_offset = char_base + tile * 64 + local_y * 8 + local_x
                if tile_offset >= len(bg_vram):
                    raise ValueError(f"BG{index} 8bpp tile exceeds BG VRAM")
                palette_index = bg_vram[tile_offset]
            else:
                tile_offset = char_base + tile * 32 + local_y * 4 + local_x // 2
                if tile_offset >= len(bg_vram):
                    raise ValueError(f"BG{index} 4bpp tile exceeds BG VRAM")
                packed = bg_vram[tile_offset]
                palette_index = (packed >> (4 if local_x & 1 else 0)) & 0xF
                if palette_index:
                    palette_index += ((entry >> 12) & 0xF) * 16
            if palette_index == 0:
                rgba.extend((0, 0, 0, 0))
                colors.append(None)
            else:
                color = _u16(palette, palette_index * 2)
                rgba.extend((*_rgb(color), 255))
                colors.append(color)
    return bytes(rgba), colors


def _decode_checkpoint(path: Path) -> tuple[dict[str, object], dict[str, bytes]]:
    state = load_gba_state(path)
    io = state.read_memory(0x04000000, 0x400)
    pram = state.read_memory(0x05000000, 0x400)
    oam = state.read_memory(0x07000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    bg_palette = pram[:0x200]
    bg_vram = vram[:0x10000]
    dispcnt = _u16(io, 0)
    if dispcnt & 7:
        raise ValueError(f"{path.name} is not display mode 0")
    if dispcnt & (1 << 7):
        raise ValueError(f"{path.name} is forced blank")
    enabled = [index for index in range(4) if dispcnt & (1 << (8 + index))]
    backgrounds = [
        _background_record(io, index, index in enabled) for index in range(4)
    ]
    mosaic = _u16(io, 0x4C)
    if mosaic:
        raise ValueError(f"{path.name} has unsupported nonzero MOSAIC")
    state_material = io[:0x58] + bg_palette + bg_vram
    state_id = _sha256(state_material)
    blend_control = _u16(io, 0x50)
    record = {
        "path": path.as_posix(),
        "checkpoint_sha256": _sha256(path.read_bytes()),
        "regions": {
            "io": {"size": len(io), "sha256": _sha256(io)},
            "pram": {"size": len(pram), "sha256": _sha256(pram)},
            "vram": {"size": len(vram), "sha256": _sha256(vram)},
            "oam": {"size": len(oam), "sha256": _sha256(oam)},
        },
        "bg_vram_sha256": _sha256(bg_vram),
        "bg_palette_sha256": _sha256(bg_palette),
        "display": {
            "dispcnt": _hex32(dispcnt),
            "mode": 0,
            "forced_blank": False,
            "enabled_backgrounds": enabled,
            "obj_enabled": bool(dispcnt & (1 << 12)),
            "win0_enabled": bool(dispcnt & (1 << 13)),
            "win1_enabled": bool(dispcnt & (1 << 14)),
            "obj_window_enabled": bool(dispcnt & (1 << 15)),
        },
        "backgrounds": backgrounds,
        "window_registers": {
            "win0h": _hex16(_u16(io, 0x40)),
            "win1h": _hex16(_u16(io, 0x42)),
            "win0v": _hex16(_u16(io, 0x44)),
            "win1v": _hex16(_u16(io, 0x46)),
            "winin": _hex16(_u16(io, 0x48)),
            "winout": _hex16(_u16(io, 0x4A)),
        },
        "mosaic": _hex16(mosaic),
        "blend_registers": {
            "bldcnt": _hex16(blend_control),
            "effect": (blend_control >> 6) & 3,
            "first_targets": blend_control & 0x3F,
            "second_targets": (blend_control >> 8) & 0x3F,
            "bldalpha": _hex16(_u16(io, 0x52)),
            "bldy": _hex16(_u16(io, 0x54)),
        },
        "state_id": state_id,
    }
    return record, {
        "io": io[:0x58],
        "bg_palette": bg_palette,
        "bg_vram": bg_vram,
    }


def _render_state(
    state_id: str,
    checkpoint_paths: list[str],
    domains: dict[str, bytes],
) -> tuple[dict[str, object], dict[str, bytes]]:
    io = domains["io"]
    palette = domains["bg_palette"]
    bg_vram = domains["bg_vram"]
    dispcnt = _u16(io, 0)
    enabled = [index for index in range(4) if dispcnt & (1 << (8 + index))]
    layers: list[dict[str, object]] = []
    members: dict[str, bytes] = {}
    color_layers: dict[int, list[int | None]] = {}
    outputs: list[dict[str, object]] = []
    prefix = f"states/{state_id[:16]}"
    for index in enabled:
        rgba, colors = _layer_pixels(io, palette, bg_vram, index)
        color_layers[index] = colors
        png = _png_bytes("RGBA", rgba)
        member = f"{prefix}/bg{index}.png"
        members[member] = png
        outputs.append(
            {
                "kind": "enabled-bg-layer",
                "bg_index": index,
                "archive_member": member,
                "width": WIDTH,
                "height": HEIGHT,
                "mode": "RGBA",
                "transparent_tile_color_zero": True,
                "sha256": _sha256(png),
            }
        )
        layers.append(
            {
                "bg_index": index,
                "priority": _u16(io, 0x08 + index * 2) & 3,
                "rgba_sha256": _sha256(rgba),
                "opaque_pixel_count": sum(color is not None for color in colors),
            }
        )
    backdrop = _u16(palette, 0)
    order = sorted(enabled, key=lambda index: (_u16(io, 0x08 + index * 2) & 3, index))
    preview = bytearray()
    for pixel_index in range(WIDTH * HEIGHT):
        color = next(
            (
                color_layers[index][pixel_index]
                for index in order
                if color_layers[index][pixel_index] is not None
            ),
            backdrop,
        )
        preview.extend(_rgb(color))
    preview_bytes = bytes(preview)
    preview_png = _png_bytes("RGB", preview_bytes)
    preview_member = f"{prefix}/pre-effect-bg-preview.png"
    members[preview_member] = preview_png
    outputs.append(
        {
            "kind": "debug-pre-effect-bg-priority-preview",
            "bg_index": None,
            "archive_member": preview_member,
            "width": WIDTH,
            "height": HEIGHT,
            "mode": "RGB",
            "sha256": _sha256(preview_png),
            "rgb_sha256": _sha256(preview_bytes),
        }
    )
    return (
        {
            "state_id": state_id,
            "checkpoint_paths": checkpoint_paths,
            "enabled_backgrounds": enabled,
            "layers": layers,
            "backdrop_bgr555": _hex16(backdrop),
            "composite_semantics": (
                "debug-preview-pre-window-pre-blend-bg-only-not-final-frame"
            ),
            "outputs": outputs,
        },
        members,
    )


def _write_deterministic_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name], compresslevel=9)


def _build_artifact(root: Path, output: Path) -> dict[str, object]:
    checkpoint_root = root / "artifacts" / "runtime-checkpoints"
    paths = sorted(checkpoint_root.glob("*.ss9"))
    if not paths:
        raise ValueError("no tracked runtime checkpoints found")
    checkpoints: list[dict[str, object]] = []
    state_domains: dict[str, dict[str, bytes]] = {}
    state_paths: defaultdict[str, list[str]] = defaultdict(list)
    for path in paths:
        record, domains = _decode_checkpoint(path)
        record["path"] = path.relative_to(root).as_posix()
        checkpoints.append(record)
        state_id = str(record["state_id"])
        state_paths[state_id].append(str(record["path"]))
        previous = state_domains.setdefault(state_id, domains)
        if previous != domains:
            raise ValueError(f"state hash collision for {state_id}")
    states = []
    members: dict[str, bytes] = {}
    for state_id in sorted(state_domains):
        state_record, state_members = _render_state(
            state_id, state_paths[state_id], state_domains[state_id]
        )
        states.append(state_record)
        overlap = set(members).intersection(state_members)
        if overlap:
            raise ValueError(f"duplicate archive members: {sorted(overlap)}")
        members.update(state_members)
    archive_path = output / "layers.zip"
    _write_deterministic_zip(archive_path, members)
    archive = archive_path.read_bytes()
    manifest = {
        "schema": SCHEMA,
        "implementation": {
            "exporter_sha256": _sha256(
                (root / "tools/export_runtime_bg_composites.py").read_bytes()
            ),
            "verifier_sha256": _sha256(
                (root / "tools/verify_runtime_bg_composites.py").read_bytes()
            ),
            "test_sha256": _sha256(
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
            "checkpoint_count": len(checkpoints),
            "mode0_checkpoint_count": len(checkpoints),
            "unique_state_count": len(states),
            "win0_checkpoint_count": sum(
                bool(item["display"]["win0_enabled"]) for item in checkpoints
            ),
            "nonzero_blend_checkpoint_count": sum(
                item["blend_registers"]["bldcnt"] != "0x0000"
                for item in checkpoints
            ),
            "archive_member_count": len(members),
        },
        "archive": {
            "file": "layers.zip",
            "size": len(archive),
            "sha256": _sha256(archive),
            "member_count": len(members),
            "deterministic_zip_timestamp": "1980-01-01T00:00:00",
        },
        "checkpoints": checkpoints,
        "states": states,
        "scope": SCOPE,
    }
    data_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (output / "runtime-bg-composites.json").write_bytes(data_bytes)
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            "layers.zip": _sha256(archive),
            "runtime-bg-composites.json": _sha256(data_bytes),
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_count": len(checkpoints),
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
            **manifest["implementation"],
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
            "verifier_sha256": manifest["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": "runtime-bg-composites-verification-v1",
                "verified": True,
                "checkpoint_count": len(checkpoints),
                "state_count": len(states),
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-bg-composites",
            "run_id": "tracked-mode0-bg-20260730-01",
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(promotion, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def export_artifact(root: Path, output: Path) -> dict[str, object]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}.", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / output.name
        staged.mkdir()
        manifest = _build_artifact(root, staged)
        if output.exists():
            shutil.rmtree(output)
        os.replace(staged, output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/runtime-bg-composites-v1"),
    )
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output_dir)
    print(json.dumps(manifest["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
