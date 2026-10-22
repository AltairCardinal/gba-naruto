#!/usr/bin/env python3
"""Export linked runtime timelines and editor keyframes for 79 battle visuals."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_story_scene_timelines import (
    ROM_BASE,
    ROM_SHA256,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    _blend_color,
    _brighten_palette,
    _d_palette_brighten_amount,
    _darken_color,
    _ease,
    _initial_state,
    _layer,
    _layer_colors,
    _rotate_b_palette,
)
from tools.extract_tileset import bgr555_to_rgb, lz77_decompress
from tools.export_tile_asset_bg_layers import render_8bpp_tilemap_indices


SCHEMA = "battle-visual-runtime-timelines-v1"
ENTRY_SCHEMA = "battle-visual-runtime-timeline-entry-v1"
OUTPUT_ARTIFACT = Path("artifacts/battle-visual-runtime-timelines-v1")
CATALOG_ARTIFACT = Path("artifacts/battle-visual-catalog-v1")
CATALOG_MANIFEST_SHA256 = (
    "1ccbdfda751953328104c845e061074150324ca69a569330a25263e5be787bcc"
)
DESCRIPTOR_TABLE_OFFSET = 0x5A320C
DESCRIPTOR_COUNT = 79
DESCRIPTOR_SIZE = 0x44
SENTINEL_IDS = (13, 31, 32, 46)
LINKED_TICKS = 106
KEY_TICKS = (16, 32, 50, 81, 106)
CALLBACK_MODES = {
    0: "common_only",
    1: "d_bg_flicker",
    2: "paired_x_shake_without_d",
    3: "paired_x_shake_then_d",
    4: "secondary_x_motion",
    6: "alpha_enable_and_palette",
    7: "alpha_enable",
    8: "resource_swap_scroll",
}
CODE_SLICES = (
    (
        "standard_consumer",
        0x08099BFC,
        0x08099D70,
        "3b3d94b963029f3b0d66f498482c13e783c6429eb1c70b4564537b073b6d55a1",
    ),
    (
        "glyph_display",
        0x08098EDC,
        0x08098FF8,
        "5e132a3a72e3541b68d5f23ebadc0f463ae86b936669a91c8bf8f4016de5f449",
    ),
    (
        "visual_task",
        0x0809880C,
        0x08098E58,
        "070037f7c19a77e75498fbd666210ccca14ba42888ab27b227b7730f25b8b7d1",
    ),
    (
        "linked_installer",
        0x080990BC,
        0x080995C0,
        "ce8174138ef0466c0131d0e81316e250e101206b7b5f27769bb1d642e6b52a5e",
    ),
    (
        "linked_update",
        0x080995E8,
        0x08099ADE,
        "6748d0ebc18e537d5059d99ae09e42db60e2477da27c080069596e2b1ef6b361",
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _callback_mode(flags: int) -> str:
    mode = flags & 0xFF
    if mode not in CALLBACK_MODES:
        raise ValueError(f"unsupported callback mode {mode}")
    return CALLBACK_MODES[mode]


def _mixed_d_map_c_gfx(
    rom: bytes,
    words: tuple[int, ...],
    c_layer: dict[str, Any],
) -> dict[str, Any] | None:
    if not words[15]:
        return None
    graphics = lz77_decompress(rom, words[10] - ROM_BASE)
    tilemap = lz77_decompress(rom, words[15] - ROM_BASE)
    packed = words[13].to_bytes(4, "little")
    width_tiles, height_tiles = packed[2], packed[3]
    indices = render_8bpp_tilemap_indices(
        graphics,
        tilemap,
        width_tiles=width_tiles,
        height_tiles=height_tiles,
    )
    canvas = bytearray(32 * 32 * 64)
    width = width_tiles * 8
    height = height_tiles * 8
    for y in range(height):
        canvas[y * 256 : y * 256 + width] = indices[
            y * width : (y + 1) * width
        ]
    return {
        "name": "C_GFX_D_MAP",
        "definition": {
            "x_tiles": 0,
            "y_tiles": 0,
            "width_tiles": width_tiles,
            "height_tiles": height_tiles,
            "canvas_width_tiles": 32,
            "canvas_height_tiles": 32,
        },
        "indices": bytes(canvas),
        "canvas": [256, 256],
        "palette": list(c_layer["palette"]),
    }


def _new_state(
    words: tuple[int, ...],
    layers: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    state = _initial_state(words, layers)
    state.update(
        {
            # The standard initializer writes zero to state+0x2A at
            # 0x080985B8. Story controllers may set bit 1 later, but the
            # canonical 0x08099BFC consumer begins with neither suppression.
            "runtime_flags": 0,
            "callback_phase": 0,
            "callback_count": 0,
            "callback_origin_x": 0,
            "registers": {
                "BLDCNT": "0x0000",
                "BLDALPHA": "0x0010",
            },
        }
    )
    return state


def _flag_0100_update(
    state: dict[str, Any],
    tick: int,
) -> list[str]:
    events: list[str] = []
    k = int((tick - 16) / 4)
    raw_alpha = (((16 - k) << 8) | k) & 0xFFFF
    state["registers"]["BLDALPHA"] = f"0x{raw_alpha:04X}"
    if tick == 8 and not state["runtime_flags"] & 2:
        events.append("cue_137")
    if tick == 17:
        state["enabled"]["C"] = True
        state["registers"]["BLDCNT"] = "0x0541"
        events.extend(("c_bg_enabled", "c_alpha_start"))
    if 17 <= tick <= 80:
        state["blend"] = {
            "mode": "alpha_c_over_b",
            "eva": max(0, min(16, k)),
            "evb": max(0, min(16, 16 - k)),
            "evy": 0,
        }
    if tick == 81:
        state["registers"]["BLDCNT"] = "0x0000"
        state["blend"] = {
            "mode": "none",
            "eva": 16,
            "evb": 0,
            "evy": 0,
        }
        events.append("c_alpha_end")
    return events


def _main_update(
    state: dict[str, Any],
    tick: int,
) -> list[str]:
    flags = state["flags"]
    if flags & 0x0100 and tick <= 81:
        return _flag_0100_update(state, tick)

    events: list[str] = []
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


def _alpha_enable(
    state: dict[str, Any],
    tick: int,
) -> list[str]:
    events: list[str] = []
    if 32 <= tick <= 47:
        step = tick - 32
        if tick == 32:
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


def _paired_x_callback(
    state: dict[str, Any],
    tick: int,
    *,
    with_d: bool,
) -> list[str]:
    events: list[str] = []
    phase = state["callback_phase"]
    if phase == 0 and tick == 32:
        state["callback_phase"] = 1
        state["callback_count"] = 0
        state["callback_origin_x"] = state["x"]
        return events
    if phase == 1:
        q = state["callback_count"]
        state["x"] = (
            state["callback_origin_x"] + q
            if q & 1
            else state["callback_origin_x"] - q - 2
        )
        state["callback_count"] = q + 1
        if state["callback_count"] > 56:
            state["callback_phase"] = 10
        return events
    if phase == 10:
        state["x"] = 0
        state["scroll_fixed"]["C"][0] = 0
        state["c_resource"] = "C_GFX_D_MAP"
        events.append("d_tilemap_installed_on_c_path")
        if not with_d:
            state["callback_phase"] = 0xFF
            return events
        state["callback_phase"] = 20
        state["enabled"]["D"] = True
        state["runtime_flags"] |= 1
        state["scroll_fixed"]["D"][0] = 0
        state["callback_count"] = 0
        events.extend(("cue_119", "d_bg_enabled"))
        return events
    if phase == 20:
        state["callback_count"] += 1
        q = state["callback_count"]
        state["scroll_fixed"]["D"][0] = (
            q if q & 1 else -q
        ) << 8
        if q > 34:
            state["callback_phase"] = 30
        return events
    if phase == 30:
        state["callback_origin_x"] = (
            state["callback_origin_x"] + 1
        ) & 0xFFFF
        q = state["callback_count"]
        state["scroll_fixed"]["D"][0] = (
            2 * q if state["callback_origin_x"] & 1 else 1 - 2 * q
        ) << 8
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
        if tick & 3 == 0:
            state["enabled"]["D"] = False
            events.append("d_bg_disabled")
        elif tick & 3 == 2:
            state["enabled"]["D"] = True
            events.append("d_bg_enabled")
    elif mode == "paired_x_shake_without_d":
        events.extend(_paired_x_callback(state, tick, with_d=False))
    elif mode == "paired_x_shake_then_d":
        events.extend(_paired_x_callback(state, tick, with_d=True))
    elif mode == "secondary_x_motion" and tick >= 32:
        if state["secondary_phase"] == 0:
            state["secondary_phase"] = 1
            state["secondary_count"] = 0
            state["secondary_origin_x"] = state["x"]
        if state["secondary_phase"] == 1:
            state["secondary_count"] += 1
            phase = _ease(256 - state["secondary_count"] * 8)
            state["x"] = (
                state["secondary_origin_x"] - 16 + (phase >> 4)
            )
            if state["secondary_count"] > 31:
                state["secondary_phase"] = 2
    elif mode in {"alpha_enable", "alpha_enable_and_palette"}:
        events.extend(_alpha_enable(state, tick))
        if mode == "alpha_enable_and_palette" and tick >= 48:
            amount = _d_palette_brighten_amount(tick)
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


def _record(
    state: dict[str, Any],
    tick: int,
    mode: str,
    events: list[str],
) -> dict[str, Any]:
    return {
        "linked_tick": tick,
        "callback_mode": mode,
        "task_counter": tick,
        "callback_phase": state["callback_phase"],
        "callback_count": state["callback_count"],
        "callback_origin_x": state["callback_origin_x"],
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
        "registers": dict(state["registers"]),
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


def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
    result = dict(state)
    for name in ("scroll_fixed", "enabled", "blend", "registers"):
        result[name] = {
            key: list(value) if isinstance(value, list) else value
            for key, value in state[name].items()
        }
    for name in ("b_palette", "c_palette", "d_palette"):
        value = state[name]
        result[name] = list(value) if value is not None else None
    return result


def _simulate(
    words: tuple[int, ...],
    layers: dict[str, dict[str, Any] | None],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    state = _new_state(words, layers)
    mode = _callback_mode(state["flags"])
    records: list[dict[str, Any]] = []
    snapshots: dict[int, dict[str, Any]] = {}
    for tick in range(1, LINKED_TICKS + 1):
        events = _main_update(state, tick)
        events.extend(_callback(state, tick, mode))
        records.append(_record(state, tick, mode, events))
        if tick in KEY_TICKS:
            snapshots[tick] = _snapshot(state)
    return records, snapshots


def _composite(
    state: dict[str, Any],
    layers: dict[str, dict[str, Any] | None],
) -> Image.Image:
    c_layer = layers[state["c_resource"]]
    active = {"B": layers["B"], "C": c_layer, "D": layers["D"]}
    palettes = {
        "B": state["b_palette"],
        "C": (
            state["c_palette"]
            if state["c_resource"] != "D"
            else state["d_palette"]
        ),
        "D": state["d_palette"],
    }
    base_palette = palettes["C"]
    pixels = [base_palette[0]] * (SCREEN_WIDTH * SCREEN_HEIGHT)
    priorities = {
        "B": 3,
        "C": 1 if state["flags"] & 0x0200 else 2,
        "D": 2 if state["flags"] & 0x0200 else 1,
    }
    for name in sorted(priorities, key=priorities.get, reverse=True):
        layer = active[name]
        palette = palettes[name]
        if layer is None or palette is None or not state["enabled"][name]:
            continue
        colors = _layer_colors(
            layer,
            state["scroll_fixed"][name],
            palette,
        )
        alpha = (
            name == "D"
            and state["blend"]["mode"] == "alpha_d_over_linked"
        ) or (
            name == "C"
            and state["blend"]["mode"] == "alpha_c_over_b"
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
                if alpha
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
    return Image.frombytes(
        "RGBA",
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        bytes(rgba),
    )


def _intro(
    root: Path,
    entry: dict[str, Any],
) -> tuple[dict[str, Any], Image.Image]:
    slots = entry["message"]["binding_slots"]
    count = len(slots)
    geometry = []
    screen = Image.new(
        "RGBA",
        (SCREEN_WIDTH, SCREEN_HEIGHT),
        (0, 0, 0, 255),
    )
    a_layer = next(layer for layer in entry["layers"] if layer["name"] == "A")
    with Image.open(root / a_layer["source_file"]) as source:
        screen.alpha_composite(source.convert("RGBA"), (0, 0))
    glyph_by_slot = {
        glyph["slot"]: glyph for glyph in entry["message"]["glyphs"]
    }
    for slot in slots:
        if slot["skipped"]:
            continue
        x = slot["slot"] * 24 - count * 12 + 132
        item = {
            "slot": slot["slot"],
            "glyph_id": slot["glyph_id"],
            "x": x,
            "y": 16,
            "palette_bank": 13,
            "first_slot_phase_frame": slot["slot"] * 6,
        }
        geometry.append(item)
        glyph = glyph_by_slot[slot["slot"]]
        with Image.open(root / glyph["source_file"]) as source:
            screen.alpha_composite(source.convert("RGBA"), (x, 16))
    timing = {
        "a_scroll_frames": 17,
        "glyph_pre_delay_frames": 8,
        "binding_slot_count": count,
        # Slot zero is created immediately after the pre-delay. The loop
        # then waits after counters 1..(count*6-1).
        "glyph_slot_wait_frames": max(0, 6 * count - 1),
        "glyph_hold_frames": 60,
        "total_before_linked_installer_frames": 84 + 6 * count,
        "glyph_slots": geometry,
    }
    return timing, screen


def _contact_sheet(
    intro: Image.Image,
    snapshots: dict[int, dict[str, Any]],
    layers: dict[str, dict[str, Any] | None],
) -> bytes:
    sheet = Image.new("RGBA", (1440, 190), (0, 0, 0, 255))
    draw = ImageDraw.Draw(sheet)
    panels = [("standard intro", intro)] + [
        (f"linked tick {tick}", _composite(snapshots[tick], layers))
        for tick in KEY_TICKS
    ]
    for index, (label, panel) in enumerate(panels):
        x = index * SCREEN_WIDTH
        sheet.alpha_composite(panel, (x, 0))
        draw.rectangle((x, 160, x + 239, 189), fill=(20, 20, 20, 255))
        draw.text((x + 8, 169), label, fill=(255, 255, 255, 255))
    output = BytesIO()
    sheet.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _build(
    root: Path,
    staging: Path,
) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_bytes = (root / CATALOG_ARTIFACT / "manifest.json").read_bytes()
    if _sha256(catalog_bytes) != CATALOG_MANIFEST_SHA256:
        raise ValueError("battle visual catalog manifest SHA-256 mismatch")
    catalog = json.loads(catalog_bytes)
    if catalog.get("schema") != "battle-visual-catalog-v1":
        raise ValueError("unexpected battle visual catalog schema")
    for name, start, end, expected in CODE_SLICES:
        if _sha256(rom[start - ROM_BASE : end - ROM_BASE]) != expected:
            raise ValueError(f"{name} code slice hash mismatch")

    entries = []
    mode_counts: dict[str, int] = {}
    for descriptor_id, source in enumerate(catalog["entries"]):
        if descriptor_id in SENTINEL_IDS:
            entries.append(
                {
                    "descriptor_id": descriptor_id,
                    "consumer_id": descriptor_id + 1,
                    "playable": False,
                    "reason": "all_zero_sentinel_descriptor",
                    "timeline_json": None,
                    "contact_sheet_png": None,
                    "standard_intro": None,
                    "key_ticks": [],
                }
            )
            continue
        words = struct.unpack_from(
            "<17I",
            rom,
            DESCRIPTOR_TABLE_OFFSET + descriptor_id * DESCRIPTOR_SIZE,
        )
        layers = {name: _layer(rom, words, name) for name in ("B", "C", "D")}
        if layers["B"] is None or layers["C"] is None:
            raise ValueError(f"descriptor {descriptor_id} lacks B/C layer")
        mixed = (
            _mixed_d_map_c_gfx(rom, words, layers["C"])
            if ((words[1] >> 16) & 0xFF) in {2, 3}
            else None
        )
        if mixed is not None:
            layers["C_GFX_D_MAP"] = mixed
        records, snapshots = _simulate(words, layers)
        intro, intro_image = _intro(root, source)
        mode = records[0]["callback_mode"]
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        payload = {
            "schema": ENTRY_SCHEMA,
            "descriptor_id": descriptor_id,
            "consumer_id": descriptor_id + 1,
            "descriptor_flags": source["descriptor"]["decoded"]["flags"],
            "callback_mode": mode,
            "standard_intro": intro,
            "linked_ticks": records,
        }
        timeline_name = f"visual_{descriptor_id:02d}.json"
        timeline_bytes = (
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        (staging / timeline_name).write_bytes(timeline_bytes)
        contact_name = f"visual_{descriptor_id:02d}_contact.png"
        contact_bytes = _contact_sheet(intro_image, snapshots, layers)
        (staging / contact_name).write_bytes(contact_bytes)
        entries.append(
            {
                "descriptor_id": descriptor_id,
                "consumer_id": descriptor_id + 1,
                "playable": True,
                "callback_mode": mode,
                "descriptor_flags": source["descriptor"]["decoded"]["flags"],
                "timeline_json": timeline_name,
                "timeline_json_sha256": _sha256(timeline_bytes),
                "contact_sheet_png": contact_name,
                "contact_sheet_png_sha256": _sha256(contact_bytes),
                "standard_intro": intro,
                "key_ticks": list(KEY_TICKS),
            }
        )

    manifest = {
        "schema": SCHEMA,
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": _sha256(rom),
        },
        "source_artifact": {
            "path": CATALOG_ARTIFACT.as_posix(),
            "manifest_sha256": _sha256(catalog_bytes),
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
        "scope": {
            "standard_consumer_intro_timing_complete": True,
            "message_obj_geometry_complete": True,
            "all_playable_linked_timelines_complete": True,
            "all_callback_modes_within_standard_consumer_complete": True,
            "flag_0100_alpha_sequence_complete": True,
            "offline_keyframe_composites_complete": True,
            "runtime_pixel_equivalence_complete": False,
            "remaining_runtime_validation": [
                "shadow_register_commit_order",
                "window_mask_edges",
                "representative_mgba_golden_frames",
            ],
        },
        "summary": {
            "entry_count": len(entries),
            "playable_count": sum(entry["playable"] for entry in entries),
            "sentinel_ids": list(SENTINEL_IDS),
            "linked_ticks_per_playable_entry": LINKED_TICKS,
            "callback_mode_counts": dict(sorted(mode_counts.items())),
        },
        "entries": entries,
    }
    (staging / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def export_artifact(
    root: Path,
    output: Path = OUTPUT_ARTIFACT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".battle-visual-runtime-",
        dir=output.parent,
    ) as temporary:
        staging = Path(temporary)
        manifest = _build(root, staging)
        output.mkdir(parents=True, exist_ok=True)
        owned = {
            path.name
            for path in output.iterdir()
            if path.name == "manifest.json"
            or path.name.startswith("visual_")
        }
        generated = {path.name for path in staging.iterdir()}
        for name in sorted(owned - generated):
            (output / name).unlink()
        for name in sorted(generated):
            (staging / name).replace(output / name)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=OUTPUT_ARTIFACT)
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output)
    print(
        f"Exported {manifest['summary']['playable_count']} playable "
        f"battle visual timelines to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
