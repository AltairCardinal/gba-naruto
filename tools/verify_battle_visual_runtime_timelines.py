#!/usr/bin/env python3
"""Independently verify battle visual runtime timeline semantics and files."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_story_scene_timelines import (
    _blend_color,
    _brighten_palette,
    _darken_color,
    _layer,
    _layer_colors,
)
from tools.extract_tileset import bgr555_to_rgb, lz77_decompress
from tools.export_tile_asset_bg_layers import render_8bpp_tilemap_indices


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/battle-visual-catalog-v1/manifest.json")
CATALOG_SHA256 = (
    "1ccbdfda751953328104c845e061074150324ca69a569330a25263e5be787bcc"
)
DESCRIPTOR_TABLE_OFFSET = 0x5A320C
DESCRIPTOR_SIZE = 0x44
SENTINELS = (13, 31, 32, 46)
MODES = {
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
EXPECTED_SCOPE = {
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
}
_CONTACT_CACHE: dict[tuple[str, int], bytes] = {}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _signed(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _ease(value: int) -> int:
    value = struct.unpack("<h", struct.pack("<H", value & 0xFFFF))[0]
    return value * value >> 8


def _initial(words: tuple[int, ...]) -> dict[str, Any]:
    packed = struct.pack("<17I", *words)
    anchor_x, anchor_y = packed[0], packed[1]
    flags = words[1] >> 16
    d_complete = bool(words[14] and words[15] and words[16])
    d_loaded = d_complete and not flags & 0x0400
    return {
        "anchor_x": anchor_x,
        "anchor_y": anchor_y,
        "direction_x": _signed(packed[2]),
        "direction_y": _signed(packed[3]),
        "amplitude": words[1] & 0xFFFF,
        "flags": flags,
        "x": anchor_x * 8,
        "y": anchor_y * 8,
        "scroll": {
            "B": [240 << 8, -8 << 8],
            "C": [anchor_x * 8 << 8, (anchor_y * 8 - 8) << 8],
            "D": [anchor_x * 8 << 8, (anchor_y * 8 - 8) << 8],
        },
        "enabled": {
            "B": True,
            "C": not bool(flags & 0x0100),
            "D": d_loaded and not bool(flags & 0x0900),
        },
        "runtime_flags": 0,
        "c_resource": "C",
        "blend": {"mode": "none", "eva": 16, "evb": 0, "evy": 0},
        "registers": {"BLDCNT": "0x0000", "BLDALPHA": "0x0010"},
        "callback_phase": 0,
        "callback_count": 0,
        "callback_origin_x": 0,
        "secondary_phase": 0,
        "secondary_count": 0,
        "secondary_origin_x": 0,
        "swap_scroll_count": 0,
    }


def _flag_0100(state: dict[str, Any], tick: int) -> list[str]:
    events = []
    k = int((tick - 16) / 4)
    raw = (((16 - k) << 8) | k) & 0xFFFF
    state["registers"]["BLDALPHA"] = f"0x{raw:04X}"
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


def _main(state: dict[str, Any], tick: int) -> list[str]:
    flags = state["flags"]
    if flags & 0x0100 and tick <= 81:
        return _flag_0100(state, tick)
    events = []
    if tick <= 32:
        phase = _ease(256 - tick * 8)
        distance = state["amplitude"] - (
            state["amplitude"] * phase >> 8
        )
        if state["direction_x"]:
            state["x"] = state["anchor_x"] * 8 + (
                -distance if state["direction_x"] < 0 else distance
            )
        if state["direction_y"]:
            state["y"] = state["anchor_y"] * 8 + (
                -distance if state["direction_y"] < 0 else distance
            )
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
        state["scroll"]["C"] = [state["x"] << 8, (state["y"] - 8) << 8]
        state["scroll"]["D"] = [state["x"] << 8, (state["y"] - 8) << 8]
    return events


def _paired(
    state: dict[str, Any],
    tick: int,
    with_d: bool,
) -> list[str]:
    events = []
    phase = state["callback_phase"]
    if phase == 0 and tick == 32:
        state["callback_phase"] = 1
        state["callback_count"] = 0
        state["callback_origin_x"] = state["x"]
    elif phase == 1:
        q = state["callback_count"]
        state["x"] = (
            state["callback_origin_x"] + q
            if q & 1
            else state["callback_origin_x"] - q - 2
        )
        state["callback_count"] += 1
        if state["callback_count"] > 56:
            state["callback_phase"] = 10
    elif phase == 10:
        state["x"] = 0
        state["scroll"]["C"][0] = 0
        state["c_resource"] = "C_GFX_D_MAP"
        events.append("d_tilemap_installed_on_c_path")
        if with_d:
            state["callback_phase"] = 20
            state["enabled"]["D"] = True
            state["runtime_flags"] |= 1
            state["scroll"]["D"][0] = 0
            state["callback_count"] = 0
            events.extend(("cue_119", "d_bg_enabled"))
        else:
            state["callback_phase"] = 0xFF
    elif phase == 20:
        state["callback_count"] += 1
        q = state["callback_count"]
        state["scroll"]["D"][0] = (q if q & 1 else -q) << 8
        if q > 34:
            state["callback_phase"] = 30
    elif phase == 30:
        state["callback_origin_x"] = (
            state["callback_origin_x"] + 1
        ) & 0xFFFF
        q = state["callback_count"]
        state["scroll"]["D"][0] = (
            2 * q if state["callback_origin_x"] & 1 else 1 - 2 * q
        ) << 8
    return events


def _callback(state: dict[str, Any], tick: int, mode: str) -> list[str]:
    events = []
    state["scroll"]["B"][0] += 2 << 8
    if tick & 1:
        events.append("b_palette_rotate_2_9")
    if mode == "d_bg_flicker":
        if tick & 3 == 0:
            state["enabled"]["D"] = False
            events.append("d_bg_disabled")
        elif tick & 3 == 2:
            state["enabled"]["D"] = True
            events.append("d_bg_enabled")
    elif mode == "paired_x_shake_without_d":
        events.extend(_paired(state, tick, False))
    elif mode == "paired_x_shake_then_d":
        events.extend(_paired(state, tick, True))
    elif mode == "secondary_x_motion" and tick >= 32:
        if state["secondary_phase"] == 0:
            state["secondary_phase"] = 1
            state["secondary_count"] = 0
            state["secondary_origin_x"] = state["x"]
        if state["secondary_phase"] == 1:
            state["secondary_count"] += 1
            phase = _ease(256 - state["secondary_count"] * 8)
            state["x"] = state["secondary_origin_x"] - 16 + (phase >> 4)
            if state["secondary_count"] > 31:
                state["secondary_phase"] = 2
    elif mode in {"alpha_enable", "alpha_enable_and_palette"}:
        if 32 <= tick <= 47:
            step = tick - 32
            if tick == 32:
                state["enabled"]["D"] = True
                state["runtime_flags"] |= 1
                state["scroll"]["D"][0] = 0
                events.append("d_bg_enabled")
            state["blend"] = {
                "mode": "alpha_d_over_linked",
                "eva": step,
                "evb": 16 - step,
                "evy": 0,
            }
        if mode == "alpha_enable_and_palette" and tick >= 32:
            state["scroll"]["D"][1] -= 0x40
    elif mode == "resource_swap_scroll":
        if tick == 50:
            state["runtime_flags"] |= 1
            state["scroll"]["C"][1] = (-8 << 8) + 0x3000
            state["swap_scroll_count"] = 0
            events.append("c_path_scroll_override")
        elif tick >= 58 and state["swap_scroll_count"] <= 15:
            state["scroll"]["C"][1] -= 0x400
            state["swap_scroll_count"] += 1
            if state["swap_scroll_count"] == 16:
                events.append("c_path_trailing_row_cleared")
    return events


def _expected_ticks(words: tuple[int, ...]) -> list[dict[str, Any]]:
    state = _initial(words)
    mode = MODES[state["flags"] & 0xFF]
    records = []
    for tick in range(1, 107):
        events = _main(state, tick)
        events.extend(_callback(state, tick, mode))
        records.append(
            {
                "linked_tick": tick,
                "callback_mode": mode,
                "task_counter": tick,
                "callback_phase": state["callback_phase"],
                "callback_count": state["callback_count"],
                "callback_origin_x": state["callback_origin_x"],
                "position_pixels": [state["x"], state["y"]],
                "scroll_fixed_8_8": {
                    key: list(value) for key, value in state["scroll"].items()
                },
                "scroll_pixels": {
                    key: [value[0] // 256, value[1] // 256]
                    for key, value in state["scroll"].items()
                },
                "bg_enabled": dict(state["enabled"]),
                "runtime_flags": state["runtime_flags"],
                "c_display_resource": state["c_resource"],
                "blend": dict(state["blend"]),
                "registers": dict(state["registers"]),
                "b_palette_rotation": (tick + 1) // 2 % 8,
                "d_palette_brighten": (
                    min((tick - 48) >> 3, 7) * 2
                    if tick >= 48
                    and words[14]
                    and state["flags"] & 0xFF == 6
                    else 0
                ),
                "events": events,
            }
        )
    return records


def _expected_intro(source: dict[str, Any]) -> dict[str, Any]:
    slots = source["message"]["binding_slots"]
    count = len(slots)
    geometry = [
        {
            "slot": slot["slot"],
            "glyph_id": slot["glyph_id"],
            "x": slot["slot"] * 24 - count * 12 + 132,
            "y": 16,
            "palette_bank": 13,
            "first_slot_phase_frame": slot["slot"] * 6,
        }
        for slot in slots
        if not slot["skipped"]
    ]
    return {
        "a_scroll_frames": 17,
        "glyph_pre_delay_frames": 8,
        "binding_slot_count": count,
        "glyph_slot_wait_frames": max(0, 6 * count - 1),
        "glyph_hold_frames": 60,
        "total_before_linked_installer_frames": 84 + 6 * count,
        "glyph_slots": geometry,
    }


def _mixed_layer(
    rom: bytes,
    words: tuple[int, ...],
    c_layer: dict[str, Any],
) -> dict[str, Any]:
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
    canvas = bytearray(256 * 256)
    width = width_tiles * 8
    for y in range(height_tiles * 8):
        canvas[y * 256 : y * 256 + width] = indices[
            y * width : (y + 1) * width
        ]
    return {
        "name": "C_GFX_D_MAP",
        "indices": bytes(canvas),
        "canvas": [256, 256],
        "palette": list(c_layer["palette"]),
    }


def _rotate_palette(palette: list[int], count: int) -> list[int]:
    result = list(palette)
    for _ in range(count):
        saved = result[2]
        result[2:9] = result[3:10]
        result[9] = saved
    return result


def _render_record(
    record: dict[str, Any],
    flags: int,
    layers: dict[str, dict[str, Any] | None],
) -> Image.Image:
    b_palette = _rotate_palette(
        list(layers["B"]["palette"]),
        record["b_palette_rotation"],
    )
    c_palette = list(layers["C"]["palette"])
    d_palette = (
        list(layers["D"]["palette"])
        if layers["D"] is not None
        else None
    )
    if d_palette is not None and record["d_palette_brighten"]:
        d_palette = _brighten_palette(
            d_palette,
            record["d_palette_brighten"],
        )
    c_resource = record["c_display_resource"]
    c_layer = layers[c_resource]
    active = {"B": layers["B"], "C": c_layer, "D": layers["D"]}
    palettes = {
        "B": b_palette,
        "C": d_palette if c_resource == "D" else c_palette,
        "D": d_palette,
    }
    pixels = [palettes["C"][0]] * (240 * 160)
    priorities = {
        "B": 3,
        "C": 1 if flags & 0x0200 else 2,
        "D": 2 if flags & 0x0200 else 1,
    }
    for name in sorted(priorities, key=priorities.get, reverse=True):
        layer = active[name]
        palette = palettes[name]
        if (
            layer is None
            or palette is None
            or not record["bg_enabled"][name]
        ):
            continue
        colors = _layer_colors(
            layer,
            record["scroll_fixed_8_8"][name],
            palette,
        )
        alpha = (
            name == "D"
            and record["blend"]["mode"] == "alpha_d_over_linked"
        ) or (
            name == "C"
            and record["blend"]["mode"] == "alpha_c_over_b"
        )
        for index, color in enumerate(colors):
            if color is None:
                continue
            pixels[index] = (
                _blend_color(
                    pixels[index],
                    color,
                    record["blend"]["eva"],
                    record["blend"]["evb"],
                )
                if alpha
                else color
            )
    if record["blend"]["mode"] == "brightness_decrease":
        pixels = [
            _darken_color(color, record["blend"]["evy"])
            for color in pixels
        ]
    rgba = bytearray()
    for color in pixels:
        rgba.extend((*bgr555_to_rgb(color), 255))
    return Image.frombytes("RGBA", (240, 160), bytes(rgba))


def _expected_contact(
    root: Path,
    rom: bytes,
    source: dict[str, Any],
    words: tuple[int, ...],
    records: list[dict[str, Any]],
) -> bytes:
    descriptor_id = source["descriptor_id"]
    cache_key = (str(root), descriptor_id)
    cached = _CONTACT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    intro = Image.new("RGBA", (240, 160), (0, 0, 0, 255))
    a_source = next(
        layer["source_file"]
        for layer in source["layers"]
        if layer["name"] == "A"
    )
    with Image.open(root / a_source) as image:
        intro.alpha_composite(image.convert("RGBA"), (0, 0))
    count = len(source["message"]["binding_slots"])
    glyph_by_slot = {
        glyph["slot"]: glyph for glyph in source["message"]["glyphs"]
    }
    for slot in source["message"]["binding_slots"]:
        if slot["skipped"]:
            continue
        x = slot["slot"] * 24 - count * 12 + 132
        with Image.open(root / glyph_by_slot[slot["slot"]]["source_file"]) as image:
            intro.alpha_composite(image.convert("RGBA"), (x, 16))

    layers = {name: _layer(rom, words, name) for name in ("B", "C", "D")}
    if ((words[1] >> 16) & 0xFF) in {2, 3}:
        layers["C_GFX_D_MAP"] = _mixed_layer(
            rom,
            words,
            layers["C"],
        )
    by_tick = {record["linked_tick"]: record for record in records}
    panels = [("standard intro", intro)] + [
        (
            f"linked tick {tick}",
            _render_record(by_tick[tick], words[1] >> 16, layers),
        )
        for tick in (16, 32, 50, 81, 106)
    ]
    sheet = Image.new("RGBA", (1440, 190), (0, 0, 0, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (label, panel) in enumerate(panels):
        x = index * 240
        sheet.alpha_composite(panel, (x, 0))
        draw.rectangle((x, 160, x + 239, 189), fill=(20, 20, 20, 255))
        draw.text((x + 8, 169), label, fill=(255, 255, 255, 255))
    stream = BytesIO()
    sheet.save(stream, format="PNG", optimize=False, compress_level=9)
    result = stream.getvalue()
    _CONTACT_CACHE[cache_key] = result
    return result


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact)
    if not artifact.is_absolute():
        artifact = root / artifact
    errors: list[str] = []
    try:
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "battle-visual-runtime-timelines-verification-v1",
            "verified": False,
            "verified_timeline_count": 0,
            "errors": [f"manifest unreadable: {exc}"],
        }
    rom = (root / "rom/base.gba").read_bytes()
    catalog_bytes = (root / CATALOG_PATH).read_bytes()
    catalog = json.loads(catalog_bytes)
    if _sha(rom) != ROM_SHA256:
        errors.append("ROM SHA-256 mismatch")
    if _sha(catalog_bytes) != CATALOG_SHA256:
        errors.append("catalog SHA-256 mismatch")
    if manifest.get("schema") != "battle-visual-runtime-timelines-v1":
        errors.append("manifest schema mismatch")
    expected_rom = {
        "path": "rom/base.gba",
        "size": len(rom),
        "sha256": _sha(rom),
    }
    if manifest.get("rom") != expected_rom:
        errors.append("ROM manifest mismatch")
    expected_source = {
        "path": "artifacts/battle-visual-catalog-v1",
        "manifest_sha256": _sha(catalog_bytes),
    }
    if manifest.get("source_artifact") != expected_source:
        errors.append("source artifact manifest mismatch")
    if manifest.get("scope") != EXPECTED_SCOPE:
        errors.append("scope mismatch")
    expected_slices = [
        {
            "name": name,
            "start_gba_address": f"0x{start:08X}",
            "end_gba_address_exclusive": f"0x{end:08X}",
            "sha256": expected,
        }
        for name, start, end, expected in CODE_SLICES
    ]
    if manifest.get("code_slices") != expected_slices:
        errors.append("code slice manifest mismatch")
    for name, start, end, expected in CODE_SLICES:
        if _sha(rom[start - ROM_BASE : end - ROM_BASE]) != expected:
            errors.append(f"{name} ROM code slice mismatch")

    entries = manifest.get("entries", [])
    if len(entries) != 79:
        errors.append("entry count mismatch")
    mode_counts: dict[str, int] = {}
    for descriptor_id in range(79):
        if descriptor_id in SENTINELS:
            continue
        words = struct.unpack_from(
            "<17I",
            rom,
            DESCRIPTOR_TABLE_OFFSET + descriptor_id * DESCRIPTOR_SIZE,
        )
        mode = MODES[(words[1] >> 16) & 0xFF]
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
    expected_summary = {
        "entry_count": 79,
        "playable_count": 75,
        "sentinel_ids": list(SENTINELS),
        "linked_ticks_per_playable_entry": 106,
        "callback_mode_counts": dict(sorted(mode_counts.items())),
    }
    if manifest.get("summary") != expected_summary:
        errors.append("summary mismatch")
    verified = 0
    expected_files = {"manifest.json"}
    for descriptor_id in range(min(79, len(entries))):
        entry = entries[descriptor_id]
        if (
            entry.get("descriptor_id") != descriptor_id
            or entry.get("consumer_id") != descriptor_id + 1
        ):
            errors.append(f"entry {descriptor_id} index mismatch")
            continue
        if descriptor_id in SENTINELS:
            expected_entry = {
                "descriptor_id": descriptor_id,
                "consumer_id": descriptor_id + 1,
                "playable": False,
                "reason": "all_zero_sentinel_descriptor",
                "timeline_json": None,
                "contact_sheet_png": None,
                "standard_intro": None,
                "key_ticks": [],
            }
            if entry != expected_entry:
                errors.append(f"entry {descriptor_id} sentinel mismatch")
            continue
        source = catalog["entries"][descriptor_id]
        words = struct.unpack_from(
            "<17I",
            rom,
            DESCRIPTOR_TABLE_OFFSET + descriptor_id * DESCRIPTOR_SIZE,
        )
        timeline_name = entry.get("timeline_json")
        contact_name = entry.get("contact_sheet_png")
        expected_files.update((timeline_name, contact_name))
        try:
            timeline_bytes = (artifact / timeline_name).read_bytes()
            payload = json.loads(timeline_bytes)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            errors.append(f"entry {descriptor_id} timeline unreadable: {exc}")
            continue
        expected_payload = {
            "schema": "battle-visual-runtime-timeline-entry-v1",
            "descriptor_id": descriptor_id,
            "consumer_id": descriptor_id + 1,
            "descriptor_flags": source["descriptor"]["decoded"]["flags"],
            "callback_mode": MODES[(words[1] >> 16) & 0xFF],
            "standard_intro": _expected_intro(source),
            "linked_ticks": _expected_ticks(words),
        }
        expected_timeline_bytes = (
            json.dumps(
                expected_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        if payload != expected_payload:
            errors.append(f"entry {descriptor_id} timeline semantic mismatch")
        if timeline_bytes != expected_timeline_bytes:
            errors.append(f"entry {descriptor_id} timeline serialization mismatch")
        if _sha(expected_timeline_bytes) != entry.get("timeline_json_sha256"):
            errors.append(f"entry {descriptor_id} timeline hash mismatch")
        expected_entry_fields = {
            "descriptor_id": descriptor_id,
            "consumer_id": descriptor_id + 1,
            "playable": True,
            "callback_mode": MODES[(words[1] >> 16) & 0xFF],
            "descriptor_flags": source["descriptor"]["decoded"]["flags"],
            "timeline_json": f"visual_{descriptor_id:02d}.json",
            "timeline_json_sha256": _sha(expected_timeline_bytes),
            "contact_sheet_png": f"visual_{descriptor_id:02d}_contact.png",
            "standard_intro": _expected_intro(source),
            "key_ticks": [16, 32, 50, 81, 106],
        }
        for key, expected_value in expected_entry_fields.items():
            if entry.get(key) != expected_value:
                errors.append(
                    f"entry {descriptor_id} manifest {key} mismatch"
                )
        try:
            contact_bytes = (artifact / contact_name).read_bytes()
            expected_contact = _expected_contact(
                root,
                rom,
                source,
                words,
                expected_payload["linked_ticks"],
            )
            if contact_bytes != expected_contact:
                errors.append(
                    f"entry {descriptor_id} contact sheet pixel rebuild mismatch"
                )
            if _sha(expected_contact) != entry.get("contact_sheet_png_sha256"):
                errors.append(f"entry {descriptor_id} contact sheet hash mismatch")
            with Image.open(artifact / contact_name) as image:
                if image.size != (1440, 190) or image.mode != "RGBA":
                    errors.append(
                        f"entry {descriptor_id} contact sheet metadata mismatch"
                    )
        except (OSError, TypeError) as exc:
            errors.append(f"entry {descriptor_id} contact sheet unreadable: {exc}")
        verified += 1

    actual_files = {
        path.name for path in artifact.iterdir() if path.is_file()
    }
    if actual_files != expected_files:
        errors.append("artifact file set mismatch")
    return {
        "schema": "battle-visual-runtime-timelines-verification-v1",
        "verified": not errors,
        "verified_timeline_count": verified,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/battle-visual-runtime-timelines-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
