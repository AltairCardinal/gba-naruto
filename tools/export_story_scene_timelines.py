#!/usr/bin/env python3
"""Export deterministic 24-row story timelines and editor composites."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import bgr555_to_rgb, lz77_decompress
from tools.export_tile_asset_bg_layers import (
    render_4bpp_tilemap_indices,
    render_8bpp_tilemap_indices,
)


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STORY_TABLE_OFFSET = 0x54229C
STORY_COUNT = 24
STORY_SIZE = 0x10
DESCRIPTOR_TABLE_OFFSET = 0x5A320C
DESCRIPTOR_COUNT = 79
DESCRIPTOR_SIZE = 0x44
BINDING_ARTIFACT = Path("artifacts/story-scene-layer-bindings-v1")
STORY_ARTIFACT = Path("artifacts/story-visual-layers-v1")
OUTPUT_ARTIFACT = Path("artifacts/story-scene-timelines-v1")

CODE_SLICES = (
    ("story_controller", 0x08087C9C, 0x08087F24,
     "fb730c71f0d2351265b4cae19a99379c7f7c43800966fd45caa472d5a0d00fbe"),
    ("palette_transform", 0x08088008, 0x08088154,
     "be7fe314c8f1a86b3c23a4542d0855a2f654e51b89857890d3ec2be27a06b7dd"),
    ("easing", 0x080986E8, 0x080986F8,
     "5901088713ac749b5514172fde6e6a0e638cf5087ee8634483f79a2c326c7968"),
    ("visual_task", 0x0809880C, 0x08098E58,
     "070037f7c19a77e75498fbd666210ccca14ba42888ab27b227b7730f25b8b7d1"),
    ("linked_installer", 0x080990BC, 0x080995C0,
     "ce8174138ef0466c0131d0e81316e250e101206b7b5f27769bb1d642e6b52a5e"),
    ("linked_update", 0x080995E8, 0x08099ADE,
     "6748d0ebc18e537d5059d99ae09e42db60e2477da27c080069596e2b1ef6b361"),
)

CONTROLLER_TIMING = {
    "installer_prelude_frames": 21,
    "installer_internal_update_ticks": 16,
    "controller_update_ticks": 90,
    "linked_update_ticks": 106,
    "palette_transform_frames": 16,
    "overlay_visible_frames": 240,
    "total_wall_frames": 383,
    "overlay_first_wall_frame": 144,
}

CALLBACK_MODES = {
    1: "d_bg_flicker",
    4: "secondary_x_motion",
    6: "alpha_enable_and_palette",
    7: "alpha_enable",
    8: "resource_swap_scroll",
}

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
CONTACT_TICKS = (16, 32, 50, 106)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _signed_byte(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _pointer_offset(pointer: int, rom: bytes) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < len(rom):
        raise ValueError(f"pointer outside ROM: 0x{pointer:08X}")
    return offset


def _palette(rom: bytes, pointer: int, colors: int) -> list[int]:
    offset = _pointer_offset(pointer, rom)
    return list(struct.unpack_from(f"<{colors}H", rom, offset))


def _lz(rom: bytes, pointer: int) -> bytes:
    return lz77_decompress(rom, _pointer_offset(pointer, rom))


def _definition(word: int, *, fixed_b: bool = False) -> dict[str, int]:
    if fixed_b:
        return {
            "x_tiles": 0,
            "y_tiles": 1,
            "width_tiles": 32,
            "height_tiles": 14,
            "canvas_width_tiles": 32,
            "canvas_height_tiles": 32,
        }
    x, y, width, height = word.to_bytes(4, "little")
    return {
        "x_tiles": x,
        "y_tiles": y,
        "width_tiles": width,
        "height_tiles": height,
        "canvas_width_tiles": 64,
        "canvas_height_tiles": 32,
    }


def _layer(
    rom: bytes,
    words: tuple[int, ...],
    name: str,
) -> dict[str, Any] | None:
    if name == "B":
        definition = _definition(0, fixed_b=True)
        gfx_word, map_word, palette_word, bpp = 6, 7, 8, 4
    elif name == "C":
        definition = _definition(words[9])
        gfx_word, map_word, palette_word, bpp = 10, 11, 12, 8
    elif name == "D":
        definition = _definition(words[13])
        gfx_word, map_word, palette_word, bpp = 14, 15, 16, 4
    else:
        raise ValueError(f"unknown layer {name}")
    pointers = (words[gfx_word], words[map_word], words[palette_word])
    if not all(pointers):
        return None
    graphics = _lz(rom, pointers[0])
    tilemap = _lz(rom, pointers[1])
    palette = _palette(rom, pointers[2], 64 if bpp == 8 else 16)
    renderer = (
        render_8bpp_tilemap_indices
        if bpp == 8
        else render_4bpp_tilemap_indices
    )
    pixels = renderer(
        graphics,
        tilemap,
        width_tiles=definition["width_tiles"],
        height_tiles=definition["height_tiles"],
    )
    canvas_width = definition["canvas_width_tiles"] * 8
    canvas_height = definition["canvas_height_tiles"] * 8
    canvas = bytearray(canvas_width * canvas_height)
    width = definition["width_tiles"] * 8
    height = definition["height_tiles"] * 8
    origin_x = definition["x_tiles"] * 8
    origin_y = definition["y_tiles"] * 8
    for y in range(height):
        start = (origin_y + y) * canvas_width + origin_x
        canvas[start : start + width] = pixels[y * width : (y + 1) * width]
    return {
        "name": name,
        "definition": definition,
        "indices": bytes(canvas),
        "canvas": [canvas_width, canvas_height],
        "palette": palette,
    }


def _rotate_b_palette(palette: list[int]) -> list[int]:
    rotated = list(palette)
    saved = rotated[2]
    rotated[2:9] = rotated[3:10]
    rotated[9] = saved
    return rotated


def _brighten_palette(palette: list[int], amount: int) -> list[int]:
    result = list(palette)
    for index in range(1, min(16, len(result))):
        color = result[index]
        red = min(31, (color & 31) + amount)
        green = min(31, ((color >> 5) & 31) + amount)
        blue = min(31, ((color >> 10) & 31) + amount)
        result[index] = red | (green << 5) | (blue << 10)
    return result


def _d_palette_brighten_amount(tick: int) -> int:
    """Return the flag-6 callback's per-channel BGR increment.

    0x08098AA0..0x08098AB8 clamps the phase to 0..7. The following
    ``lsl #17`` converts that phase to ``phase * 2`` before the three
    color-channel additions.
    """
    return min((tick - 48) >> 3, 7) * 2 if tick >= 48 else 0


def _grayscale_color(rom: bytes, color: int) -> int:
    red = color & 31
    green = (color >> 5) & 31
    blue = (color >> 10) & 31
    luminance = (red * 0x12B + green * 0x24B + blue * 0x72) // 1000
    return struct.unpack_from("<H", rom, 0x13E030 + luminance * 2)[0]


def _grayscale_palette(rom: bytes, palette: list[int]) -> list[int]:
    return [_grayscale_color(rom, color) for color in palette]


def _ease(value: int) -> int:
    value = struct.unpack("<h", struct.pack("<H", value & 0xFFFF))[0]
    return (value * value) >> 8


def _initial_state(
    words: tuple[int, ...],
    layers: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    descriptor = struct.pack("<17I", *words)
    anchor_x, anchor_y = descriptor[0], descriptor[1]
    direction_x = _signed_byte(descriptor[2])
    direction_y = _signed_byte(descriptor[3])
    amplitude, flags = struct.unpack_from("<HH", descriptor, 4)
    d_present = layers["D"] is not None
    d_loaded = d_present and not flags & 0x0400
    return {
        "anchor_x": anchor_x,
        "anchor_y": anchor_y,
        "direction_x": direction_x,
        "direction_y": direction_y,
        "amplitude": amplitude,
        "flags": flags,
        "x": anchor_x * 8,
        "y": anchor_y * 8,
        "scroll_fixed": {
            "B": [240 << 8, -8 << 8],
            "C": [anchor_x * 8 << 8, (anchor_y * 8 - 8) << 8],
            "D": [anchor_x * 8 << 8, (anchor_y * 8 - 8) << 8],
        },
        "enabled": {
            "B": True,
            "C": not bool(flags & 0x0100),
            "D": d_loaded and not bool(flags & 0x0900),
        },
        "runtime_flags": 2,
        "c_resource": "C",
        "b_palette": list(layers["B"]["palette"]),
        "c_palette": list(layers["C"]["palette"]),
        "d_palette": (
            list(layers["D"]["palette"]) if layers["D"] is not None else None
        ),
        "original_d_palette": (
            list(layers["D"]["palette"]) if layers["D"] is not None else None
        ),
        "blend": {"mode": "none", "eva": 16, "evb": 0, "evy": 0},
        "secondary_phase": 0,
        "secondary_count": 0,
        "secondary_origin_x": 0,
        "swap_scroll_count": 0,
    }


def _main_update(state: dict[str, Any], tick: int) -> list[str]:
    events: list[str] = []
    flags = state["flags"]
    if tick <= 32:
        phase = _ease(256 - tick * 8)
        distance = state["amplitude"] - (
            state["amplitude"] * phase >> 8
        )
        if state["direction_x"]:
            signed = -distance if state["direction_x"] < 0 else distance
            state["x"] = state["anchor_x"] * 8 + signed
        if state["direction_y"]:
            signed = -distance if state["direction_y"] < 0 else distance
            state["y"] = state["anchor_y"] * 8 + signed
    elif flags & 0x0400:
        if tick == 33:
            state["blend"] = {
                "mode": "brightness_decrease",
                "eva": 16,
                "evb": 0,
                "evy": 0,
            }
            events.append("resource_swap_fade_start")
        elif 34 <= tick <= 49:
            state["blend"]["evy"] = tick - 33
        elif tick == 50:
            state["x"] = 0
            state["y"] = 0
            state["c_resource"] = "D"
            if state["original_d_palette"] is None:
                raise ValueError("0x0400 swap descriptor lacks D resources")
            state["c_palette"] = list(state["original_d_palette"])
            state["blend"]["evy"] = 16
            events.append("d_resources_installed_on_c_path")
        elif 51 <= tick <= 65:
            state["blend"]["evy"] = (66 - tick) * 2
        elif tick == 66:
            state["blend"] = {
                "mode": "none",
                "eva": 16,
                "evb": 0,
                "evy": 0,
            }
            events.append("resource_swap_fade_end")

    if not state["runtime_flags"] & 1:
        x_fixed = state["x"] << 8
        y_fixed = (state["y"] - 8) << 8
        state["scroll_fixed"]["C"] = [x_fixed, y_fixed]
        state["scroll_fixed"]["D"] = [x_fixed, y_fixed]
    return events


def _alpha_enable(state: dict[str, Any], tick: int) -> list[str]:
    events: list[str] = []
    if 32 <= tick <= 47:
        step = tick - 32
        if step == 0:
            state["enabled"]["D"] = True
            state["runtime_flags"] |= 1
            state["scroll_fixed"]["D"][0] = 0
            events.append("d_bg_enabled")
        state["blend"] = {
            "mode": "alpha_d_over_linked",
            "eva": step,
            "evb": 16 - step,
            "evy": 0,
        }
    return events


def _callback(
    state: dict[str, Any],
    tick: int,
    mode: str,
) -> list[str]:
    events: list[str] = []
    state["scroll_fixed"]["B"][0] += 2 << 8
    if tick & 1:
        state["b_palette"] = _rotate_b_palette(state["b_palette"])
        events.append("b_palette_rotate_2_9")

    if mode == "d_bg_flicker":
        residue = tick & 3
        if residue == 0:
            state["enabled"]["D"] = False
            events.append("d_bg_disabled")
        elif residue == 2:
            state["enabled"]["D"] = True
            events.append("d_bg_enabled")
    elif mode == "secondary_x_motion" and tick >= 32:
        if state["secondary_phase"] == 0:
            state["secondary_phase"] = 1
            state["secondary_count"] = 0
            state["secondary_origin_x"] = state["x"]
        if state["secondary_phase"] == 1:
            state["secondary_count"] += 1
            phase = _ease(256 - state["secondary_count"] * 8)
            delta = 16 - (phase >> 4)
            state["x"] = state["secondary_origin_x"] - delta
            if state["secondary_count"] > 31:
                state["secondary_phase"] = 2
    elif mode in {"alpha_enable", "alpha_enable_and_palette"}:
        events.extend(_alpha_enable(state, tick))
        if mode == "alpha_enable_and_palette" and tick >= 48:
            amount = _d_palette_brighten_amount(tick)
            if state["original_d_palette"] is not None:
                state["d_palette"] = _brighten_palette(
                    state["original_d_palette"],
                    amount,
                )
        if mode == "alpha_enable_and_palette" and tick >= 32:
            state["scroll_fixed"]["D"][1] -= 0x40
    elif mode == "resource_swap_scroll":
        if tick == 50:
            state["runtime_flags"] |= 1
            state["scroll_fixed"]["C"][1] = (-8 << 8) + 0x3000
            state["swap_scroll_count"] = 0
            events.append("c_path_scroll_override")
        elif tick >= 58 and state["swap_scroll_count"] <= 15:
            state["scroll_fixed"]["C"][1] -= 0x400
            state["swap_scroll_count"] += 1
            if state["swap_scroll_count"] == 16:
                events.append("c_path_trailing_row_cleared")
    return events


def _state_record(
    state: dict[str, Any],
    tick: int,
    events: list[str],
) -> dict[str, Any]:
    return {
        "linked_tick": tick,
        "wall_frame": 21 + tick,
        "task_counter": tick,
        "position_pixels": [state["x"], state["y"]],
        "scroll_fixed_8_8": {
            key: list(value) for key, value in state["scroll_fixed"].items()
        },
        "scroll_pixels": {
            key: [value[0] // 256, value[1] // 256]
            for key, value in state["scroll_fixed"].items()
        },
        "bg_enabled": dict(state["enabled"]),
        "runtime_flags": state["runtime_flags"],
        "c_display_resource": state["c_resource"],
        "blend": dict(state["blend"]),
        "b_palette_rotation": (tick + 1) // 2 % 8,
        "d_palette_brighten": (
            _d_palette_brighten_amount(tick)
            if tick >= 48
            and state["original_d_palette"] is not None
            and state["flags"] & 0xFF == 6
            else 0
        ),
        "events": events,
    }


def _simulate(
    words: tuple[int, ...],
    layers: dict[str, dict[str, Any] | None],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[int, dict[str, Any]]]:
    state = _initial_state(words, layers)
    mode = CALLBACK_MODES.get(state["flags"] & 0xFF, "common_only")
    records: list[dict[str, Any]] = []
    snapshots: dict[int, dict[str, Any]] = {}
    for tick in range(1, 107):
        events = _main_update(state, tick)
        events.extend(_callback(state, tick, mode))
        records.append(_state_record(state, tick, events))
        if tick in CONTACT_TICKS:
            snapshots[tick] = {
                **state,
                "scroll_fixed": {
                    key: list(value)
                    for key, value in state["scroll_fixed"].items()
                },
                "enabled": dict(state["enabled"]),
                "b_palette": list(state["b_palette"]),
                "c_palette": list(state["c_palette"]),
                "d_palette": (
                    list(state["d_palette"])
                    if state["d_palette"] is not None
                    else None
                ),
                "blend": dict(state["blend"]),
            }
    return state, records, snapshots


def _layer_colors(
    layer: dict[str, Any],
    scroll_fixed: list[int],
    palette: list[int],
) -> list[int | None]:
    width, height = layer["canvas"]
    indices = layer["indices"]
    scroll_x = scroll_fixed[0] // 256
    scroll_y = scroll_fixed[1] // 256
    result: list[int | None] = [None] * (SCREEN_WIDTH * SCREEN_HEIGHT)
    for y in range(SCREEN_HEIGHT):
        source_y = (y + scroll_y) % height
        source_row = source_y * width
        target_row = y * SCREEN_WIDTH
        for x in range(SCREEN_WIDTH):
            index = indices[source_row + (x + scroll_x) % width]
            if index:
                result[target_row + x] = palette[index]
    return result


def _blend_color(bottom: int, top: int, eva: int, evb: int) -> int:
    eva = min(16, max(0, eva))
    evb = min(16, max(0, evb))
    channels = []
    for shift in (0, 5, 10):
        value = (
            ((top >> shift) & 31) * eva
            + ((bottom >> shift) & 31) * evb
        ) >> 4
        channels.append(min(31, value))
    return channels[0] | (channels[1] << 5) | (channels[2] << 10)


def _darken_color(color: int, evy: int) -> int:
    evy = min(16, max(0, evy))
    channels = [
        ((color >> shift) & 31) * (16 - evy) >> 4
        for shift in (0, 5, 10)
    ]
    return channels[0] | (channels[1] << 5) | (channels[2] << 10)


def _composite(
    rom: bytes,
    state: dict[str, Any],
    layers: dict[str, dict[str, Any] | None],
    *,
    grayscale: bool = False,
    overlay: Image.Image | None = None,
) -> Image.Image:
    palettes = {
        "B": list(state["b_palette"]),
        "C": list(state["c_palette"]),
        "D": (
            list(state["d_palette"])
            if state["d_palette"] is not None
            else None
        ),
    }
    if grayscale:
        for name, palette in palettes.items():
            if palette is not None:
                palettes[name] = _grayscale_palette(rom, palette)
    c_layer = layers[state["c_resource"]]
    if c_layer is None:
        raise ValueError("active C display resource is absent")
    active_layers = {
        "B": layers["B"],
        "C": c_layer,
        "D": layers["D"],
    }
    base_palette = palettes["C"]
    pixels = [base_palette[0]] * (SCREEN_WIDTH * SCREEN_HEIGHT)
    priorities = {
        "B": 3,
        "C": 1 if state["flags"] & 0x0200 else 2,
        "D": 2 if state["flags"] & 0x0200 else 1,
    }
    for name in sorted(priorities, key=priorities.get, reverse=True):
        layer = active_layers[name]
        palette = palettes[name]
        if layer is None or palette is None or not state["enabled"][name]:
            continue
        colors = _layer_colors(
            layer,
            state["scroll_fixed"][name],
            palette,
        )
        alpha_d = (
            name == "D"
            and state["blend"]["mode"] == "alpha_d_over_linked"
        )
        for index, color in enumerate(colors):
            if color is None:
                continue
            pixels[index] = (
                _blend_color(
                    pixels[index],
                    color,
                    state["blend"]["eva"],
                    state["blend"]["evb"],
                )
                if alpha_d
                else color
            )
    if state["blend"]["mode"] == "brightness_decrease":
        pixels = [
            _darken_color(color, state["blend"]["evy"])
            for color in pixels
        ]
    rgba = bytearray()
    for color in pixels:
        rgba.extend((*bgr555_to_rgb(color), 255))
    image = Image.frombytes("RGBA", (SCREEN_WIDTH, SCREEN_HEIGHT), bytes(rgba))
    if overlay is not None:
        image.alpha_composite(overlay.crop((0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)))
    return image


def _contact_sheet(
    rom: bytes,
    snapshots: dict[int, dict[str, Any]],
    final_state: dict[str, Any],
    layers: dict[str, dict[str, Any] | None],
    overlay: Image.Image,
) -> bytes:
    sheet = Image.new("RGBA", (1200, 190), (0, 0, 0, 255))
    draw = ImageDraw.Draw(sheet)
    panels: list[tuple[str, Image.Image]] = [
        (
            f"linked tick {tick}",
            _composite(rom, snapshots[tick], layers),
        )
        for tick in CONTACT_TICKS
    ]
    panels.append(
        (
            "overlay wall frame 144",
            _composite(
                rom,
                final_state,
                layers,
                grayscale=True,
                overlay=overlay,
            ),
        )
    )
    for index, (label, panel) in enumerate(panels):
        x = index * SCREEN_WIDTH
        sheet.alpha_composite(panel, (x, 0))
        draw.rectangle((x, 160, x + 239, 189), fill=(20, 20, 20, 255))
        draw.text((x + 8, 169), label, fill=(255, 255, 255, 255))
    from io import BytesIO

    output = BytesIO()
    sheet.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _phases() -> list[dict[str, Any]]:
    return [
        {
            "name": "installer_prelude",
            "start_wall_frame": 1,
            "end_wall_frame": 21,
        },
        {
            "name": "installer_internal_linked_updates",
            "start_wall_frame": 22,
            "end_wall_frame": 37,
            "linked_ticks": [1, 16],
        },
        {
            "name": "controller_linked_updates",
            "start_wall_frame": 38,
            "end_wall_frame": 127,
            "linked_ticks": [17, 106],
        },
        {
            "name": "linked_palette_grayscale_transform",
            "start_wall_frame": 128,
            "end_wall_frame": 143,
        },
        {
            "name": "story_overlay_visible",
            "start_wall_frame": 144,
            "end_wall_frame": 383,
        },
    ]


def _build_outputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    binding_bytes = (root / BINDING_ARTIFACT / "manifest.json").read_bytes()
    bindings = json.loads(binding_bytes)
    if bindings.get("schema") != "story-scene-layer-bindings-v1":
        raise ValueError("unexpected binding artifact schema")
    story_manifest = json.loads(
        (root / STORY_ARTIFACT / "manifest.json").read_text(encoding="utf-8")
    )
    story_layers = {
        item["layer_id"]: item for item in story_manifest["layers"]
    }
    for name, start, end, expected in CODE_SLICES:
        actual = _sha256(rom[start - ROM_BASE : end - ROM_BASE])
        if actual != expected:
            raise ValueError(f"{name} code slice hash mismatch")

    files: dict[str, bytes] = {}
    timelines: list[dict[str, Any]] = []
    story_rows = [
        struct.unpack_from("<4I", rom, STORY_TABLE_OFFSET + index * STORY_SIZE)
        for index in range(STORY_COUNT)
    ]
    for index, row in enumerate(story_rows):
        config_id = row[3] & 0xFF
        words = struct.unpack_from(
            "<17I",
            rom,
            DESCRIPTOR_TABLE_OFFSET + config_id * DESCRIPTOR_SIZE,
        )
        layer_map = {
            name: _layer(rom, words, name) for name in ("B", "C", "D")
        }
        if layer_map["B"] is None or layer_map["C"] is None:
            raise ValueError(f"story {index} lacks required linked layers")
        final_state, records, snapshots = _simulate(words, layer_map)
        overlay_info = story_layers[index]
        overlay_path = root / STORY_ARTIFACT / overlay_info["png"]
        with Image.open(overlay_path) as source:
            overlay = source.convert("RGBA")
        contact_png = _contact_sheet(
            rom,
            snapshots,
            final_state,
            layer_map,
            overlay,
        )
        descriptor_flags = (words[1] >> 16) & 0xFFFF
        callback_mode = CALLBACK_MODES.get(
            descriptor_flags & 0xFF,
            "common_only",
        )
        timeline_payload = {
            "schema": "story-scene-timeline-entry-v1",
            "story_index": index,
            "config_id": config_id,
            "previous_config_id": (
                story_rows[index - 1][3] & 0xFF if index else config_id
            ),
            "callback_mode": callback_mode,
            "phases": _phases(),
            "linked_ticks": records,
            "overlay": {
                "first_wall_frame": 144,
                "last_wall_frame": 383,
                "linked_state_frozen_at_tick": 106,
                "linked_palette_state": "grayscale_transform_complete",
            },
        }
        timeline_name = f"story_{index:02d}_config_{config_id:02d}.json"
        contact_name = f"story_{index:02d}_config_{config_id:02d}_contact.png"
        timeline_bytes = (
            json.dumps(timeline_payload, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        files[timeline_name] = timeline_bytes
        files[contact_name] = contact_png
        d_first_enabled: int | None
        initially_d = _initial_state(words, layer_map)["enabled"]["D"]
        if initially_d:
            d_first_enabled = 0
        elif callback_mode in {"alpha_enable", "alpha_enable_and_palette"}:
            d_first_enabled = 32
        else:
            d_first_enabled = None
        timelines.append(
            {
                "story_index": index,
                "config_id": config_id,
                "previous_config_id": timeline_payload["previous_config_id"],
                "descriptor_flags": f"0x{descriptor_flags:04X}",
                "callback_mode": callback_mode,
                "timeline_json": timeline_name,
                "timeline_json_sha256": _sha256(timeline_bytes),
                "contact_sheet_png": contact_name,
                "contact_sheet_png_sha256": _sha256(contact_png),
                "d_first_enabled_tick": d_first_enabled,
                "d_flicker_task_counter_modulo": (
                    {
                        "modulus": 4,
                        "enabled_residues": [2],
                        "disabled_residues": [0],
                    }
                    if callback_mode == "d_bg_flicker"
                    else None
                ),
                "c_resource_switch_tick": (
                    50 if callback_mode == "resource_swap_scroll" else None
                ),
                "c_resource_after_switch": (
                    "D" if callback_mode == "resource_swap_scroll" else None
                ),
            }
        )

    manifest = {
        "schema": "story-scene-timelines-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": _sha256(rom),
        },
        "source_artifacts": {
            "bindings": {
                "path": str(BINDING_ARTIFACT),
                "manifest_sha256": _sha256(binding_bytes),
            },
            "story_layers": {
                "path": str(STORY_ARTIFACT),
                "manifest_sha256": _sha256(
                    (root / STORY_ARTIFACT / "manifest.json").read_bytes()
                ),
            },
        },
        "code_slices": [
            {
                "name": name,
                "start_gba_address": f"0x{start:08X}",
                "end_gba_address_exclusive": f"0x{end:08X}",
                "sha256": expected,
            }
            for name, start, end, expected in CODE_SLICES
        ],
        "controller_timing": dict(CONTROLLER_TIMING),
        "scope": {
            "offline_deterministic_text_bg_composite": True,
            "all_story_rows": True,
            "all_actual_callback_modes": True,
            "runtime_pixel_equivalence": False,
            "runtime_validation_still_required": [
                "shadow_register_commit_order",
                "window_mask_edges",
                "representative_mgba_golden_frames",
            ],
        },
        "timeline_count": len(timelines),
        "timelines": timelines,
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    files["manifest.json"] = manifest_bytes
    return manifest, files


def export_story_scene_timelines(
    root: Path,
    output_dir: Path = OUTPUT_ARTIFACT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    manifest, files = _build_outputs(root)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".story-scene-timelines-",
        dir=output_dir.parent,
    ) as temporary:
        staging = Path(temporary)
        for name, payload in files.items():
            (staging / name).write_bytes(payload)
        output_dir.mkdir(parents=True, exist_ok=True)
        owned = {
            path.name
            for path in output_dir.iterdir()
            if path.name == "manifest.json"
            or path.name.startswith("story_")
        }
        for name in sorted(owned - set(files)):
            (output_dir / name).unlink()
        for name in sorted(files):
            (staging / name).replace(output_dir / name)
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_ARTIFACT,
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_story_scene_timelines(args.root, args.output_dir)
    print(
        f"Exported {manifest['timeline_count']} story scene timelines "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
