#!/usr/bin/env python3
"""Independently verify a profile-driven battle-effect single-pixel A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.inspect_mgba_savestate import load_gba_state, png_screen_fingerprint
from tools.render_mode0_checkpoint import render_checkpoint
from tools.verify_menu_portrait_writeback_audit import (
    _decompress_lz77,
    _encode_lz77,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PROFILE_SCHEMA = "battle-effect-pixel-ab-profile-v1"
BUILD_SCHEMA = "battle-effect-pixel-ab-build-v1"
EVIDENCE_SCHEMA = "battle-effect-pixel-ab-runtime-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
MGBA_BINARY_SHA256 = (
    "20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408"
)
MGBA_BUILD_MANIFEST_SHA256 = (
    "9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d"
)
VARIANTS = ("baseline", "candidate")
INPUT_KEYS = {"A", "B", "L", "R", "Up", "Down", "Left", "Right", "Start"}
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
IMPLEMENTATION_PATHS = (
    "tools/build_battle_effect_pixel_ab.py",
    "tools/export_battle_effect_pixel_ab_evidence.py",
    "tools/verify_battle_effect_pixel_ab_evidence.py",
    "tools/import_battle_effect_resource_relocations.py",
    "tools/import_battle_effect_resources.py",
    "tools/build_mod.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tools/run_macos_mgba_input_sequence.py",
    "tools/mgba_input_sequence_replay.lua",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _safe_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"battle-effect pixel {label} is not a repository path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"battle-effect pixel {label} is not a safe relative path")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"battle-effect pixel {label} escapes the repository")
    return path


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("battle-effect pixel byte lengths differ")
    return [
        index
        for index, (before, after) in enumerate(zip(left, right))
        if before != after
    ]


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("battle-effect pixel screenshot geometry mismatch")
        return image.convert("RGB").tobytes()


def _pixel_changes(left: bytes, right: bytes) -> list[dict[str, Any]]:
    changes = []
    for index in range(240 * 160):
        offset = index * 3
        before = list(left[offset : offset + 3])
        after = list(right[offset : offset + 3])
        if before != after:
            changes.append(
                {
                    "x": index % 240,
                    "y": index // 240,
                    "before_rgb": before,
                    "after_rgb": after,
                }
            )
    return changes


def _one(rows: object, label: str, **criteria: object) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ValueError(f"battle-effect pixel {label} is not a list")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and all(row.get(key) == value for key, value in criteria.items())
    ]
    if len(matches) != 1:
        raise ValueError(f"battle-effect pixel {label} match is not unique")
    return matches[0]


def _selector_scope(selector: object) -> dict[str, bool]:
    if not isinstance(selector, dict) or selector.get("kind") not in {
        "ninja_tool",
        "active_action",
    }:
        raise ValueError("battle-effect pixel selector scope mismatch")
    return {
        f"natural_{selector['kind']}_route": True,
        "production_relocation_route": True,
        "single_group_single_frame_single_pixel": True,
        "all_18_effect_groups_runtime_verified": False,
        "all_group_frames_runtime_verified": False,
        "full_affine_blend_timing_audio_equivalence": False,
        "physical_gba_verified": False,
    }


def _raw_files(profile: dict[str, Any]) -> tuple[str, ...]:
    frame = profile["runtime_input"]["capture_frame"]
    group = profile["group_id"]
    files = ["build-manifest.json"]
    for variant in VARIANTS:
        files.extend(
            (
                f"{variant}/audit.json",
                f"{variant}/frame{frame}.png",
                f"{variant}/frame{frame}.ss9",
                f"{variant}/group-{group:02d}-graphics-4bpp.bin",
                f"{variant}/guard.json",
                f"{variant}/sentinel.json",
                f"{variant}/spec.json",
            )
        )
    return tuple(files)


def _verify_checkpoint(root: Path, profile: dict[str, Any]) -> None:
    state_path = _safe_file(root, profile.get("input_state"), "input_state")
    evidence_path = _safe_file(root, profile.get("input_evidence"), "input_evidence")
    if (
        _sha256_file(state_path) != profile.get("input_state_sha256")
        or _sha256_file(evidence_path) != profile.get("input_evidence_sha256")
    ):
        raise ValueError("battle-effect pixel checkpoint hash mismatch")
    checkpoint = _json(evidence_path)
    parent = checkpoint.get("input", {})
    parent_path = _safe_file(root, parent.get("path"), "checkpoint parent")
    next_binding = checkpoint.get("boundary", {}).get("next_runtime_binding", {})
    selector_kind = profile.get("selector", {}).get("kind")
    expected_next_input = {
        "key": profile["runtime_input"]["key"],
        "down_frame": profile["runtime_input"]["down_frame"],
        "up_frame": profile["runtime_input"]["up_frame"],
    }
    expected_next_binding = {
        "encoded_action_id": profile["selector"]["encoded_action_id"],
        "resource_group_id": profile["group_id"],
        "sequence_id": profile["sequence_id"],
    }
    if selector_kind == "active_action":
        route = checkpoint.get("route_segments")
        zero = checkpoint.get("zero_input", {})
        if not isinstance(route, list) or not route:
            raise ValueError("battle-effect pixel active-action route is incomplete")
        cursor = parent.get("sha256")
        run_ids: set[str] = set()
        for segment in route:
            if (
                not isinstance(segment, dict)
                or segment.get("input_state_sha256") != cursor
                or not isinstance(segment.get("inputs"), list)
                or not segment["inputs"]
                or not isinstance(segment.get("run_id"), str)
                or segment["run_id"] in run_ids
            ):
                raise ValueError("battle-effect pixel active-action route chain mismatch")
            for event in segment["inputs"]:
                if (
                    not isinstance(event, dict)
                    or event.get("key") not in INPUT_KEYS
                    or not 0
                    <= event.get("down_frame", -1)
                    < event.get("up_frame", -1)
                    or event.get("hold_frames")
                    != event["up_frame"] - event["down_frame"]
                ):
                    raise ValueError("battle-effect pixel active-action route input mismatch")
            run_ids.add(segment["run_id"])
            cursor = segment.get("output_state_sha256")
        if (
            checkpoint.get("schema")
            != "runtime-active-action-confirmation-evidence-v1"
            or checkpoint.get("artifact_status") != "accepted"
            or checkpoint.get("output", {}).get("path") != profile["input_state"]
            or checkpoint.get("output", {}).get("sha256")
            != profile["input_state_sha256"]
            or cursor != profile["input_state_sha256"]
            or png_screen_fingerprint(state_path).get("rgb_pixels_sha256")
            != checkpoint.get("output", {}).get("embedded_rgb_sha256")
            or _sha256_file(parent_path) != parent.get("sha256")
            or checkpoint.get("provenance", {}).get("base_rom_sha256") != ROM_SHA256
            or checkpoint.get("provenance", {}).get("mgba_binary_sha256")
            != MGBA_BINARY_SHA256
            or checkpoint.get("provenance", {}).get("mgba_build_manifest_sha256")
            != MGBA_BUILD_MANIFEST_SHA256
            or checkpoint.get("provenance", {}).get("replay_script")
            != "tools/mgba_single_input_replay.lua"
            or _sha256_file(root / "tools/mgba_single_input_replay.lua")
            != checkpoint.get("provenance", {}).get("replay_script_sha256")
            or checkpoint.get("boundary", {}).get("final_confirmation_pressed") is not False
            or checkpoint.get("boundary", {}).get("next_input") != expected_next_input
            or next_binding != expected_next_binding
            or checkpoint.get("scope")
            != {
                "natural_active_action_route": True,
                "post_confirmation_effect_runtime": False,
                "zero_input_stability_verified": True,
            }
            or zero.get("input_state_sha256") != profile["input_state_sha256"]
            or zero.get("reason") != "completed"
            or zero.get("exit_code") != 0
            or zero.get("degraded") is not False
            or zero.get("pgid_clean") is not True
            or zero.get("mgba_listener_clean") is not True
            or zero.get("replay_script") != "tools/mgba_checkpoint_replay.lua"
            or _sha256_file(root / "tools/mgba_checkpoint_replay.lua")
            != zero.get("replay_script_sha256")
        ):
            raise ValueError("battle-effect pixel active-action checkpoint contract mismatch")
        return
    if (
        checkpoint.get("schema") != "runtime-checkpoint-input-sequence-evidence-v1"
        or checkpoint.get("artifact_status") != "accepted"
        or checkpoint.get("capture_frame") != 800
        or checkpoint.get("output", {}).get("path") != profile["input_state"]
        or checkpoint.get("output", {}).get("sha256")
        != profile["input_state_sha256"]
        or checkpoint.get("output", {}).get("png_sha256")
        != checkpoint.get("output", {}).get("segmented_reference_png_sha256")
        or png_screen_fingerprint(state_path).get("rgb_pixels_sha256")
        != checkpoint.get("output", {}).get("embedded_rgb_sha256")
        or _sha256_file(parent_path) != parent.get("sha256")
        or checkpoint.get("provenance", {}).get("base_rom_sha256") != ROM_SHA256
        or checkpoint.get("provenance", {}).get("mgba_binary_sha256")
        != MGBA_BINARY_SHA256
        or checkpoint.get("provenance", {}).get("mgba_build_manifest_sha256")
        != MGBA_BUILD_MANIFEST_SHA256
        or checkpoint.get("provenance", {}).get("replay_script")
        != "tools/mgba_input_sequence_replay.lua"
        or _sha256_file(root / "tools/mgba_input_sequence_replay.lua")
        != checkpoint.get("provenance", {}).get("replay_script_sha256")
        or checkpoint.get("guard", {}).get("reason") != "completed"
        or checkpoint.get("guard", {}).get("exit_code") != 0
        or checkpoint.get("guard", {}).get("degraded") is not False
        or checkpoint.get("guard", {}).get("pgid_clean") is not True
        or checkpoint.get("guard", {}).get("mgba_listener_clean") is not True
        or checkpoint.get("boundary", {}).get("final_confirmation_pressed") is not False
        or checkpoint.get("boundary", {}).get("next_input") != expected_next_input
        or next_binding != expected_next_binding
        or len(checkpoint.get("inputs", [])) != 10
        or checkpoint.get("scope", {}).get(
            "historical_segmented_reference_hash_recorded_equal"
        )
        is not True
    ):
        raise ValueError("battle-effect pixel checkpoint evidence contract mismatch")


def _verify_profile(root: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = _json(profile_path)
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("battle-effect pixel profile schema mismatch")
    _verify_checkpoint(root, profile)
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("battle-effect pixel base ROM mismatch")

    catalogs = profile.get("catalogs")
    if not isinstance(catalogs, dict):
        raise ValueError("battle-effect pixel catalogs are invalid")
    payloads = {}
    for name in ("resource_pairs", "animations", "sequence_bindings"):
        path = _safe_file(root, catalogs.get(name), name)
        if _sha256_file(path) != catalogs.get(f"{name}_sha256"):
            raise ValueError(f"battle-effect pixel {name} hash mismatch")
        payloads[name] = _json(path)

    group = profile.get("group_id")
    sequence_id = profile.get("sequence_id")
    resource = _one(payloads["resource_pairs"].get("entries"), "resource", group_id=group)
    graphics_row = resource.get("graphics", {})
    palette_row = resource.get("palette", {})
    compressed_offset = graphics_row.get("file_offset")
    compressed_size = graphics_row.get("compressed_size")
    if not isinstance(compressed_offset, int) or not isinstance(compressed_size, int):
        raise ValueError("battle-effect pixel compressed graphics metadata mismatch")
    compressed = base[compressed_offset : compressed_offset + compressed_size]
    source = _decompress_lz77(compressed, 0)
    source_path = _safe_file(root, profile.get("source_graphics"), "source_graphics")
    if (
        len(payloads["resource_pairs"].get("entries", [])) != 18
        or resource.get("table_entry_file_offset") != profile.get("pair_pointer_offset")
        or base[profile["pair_pointer_offset"] : profile["pair_pointer_offset"] + 8].hex()
        != resource.get("pair_raw_hex")
        or _sha256(compressed) != graphics_row.get("compressed_sha256")
        or len(source) != graphics_row.get("decompressed_size")
        or _sha256(source) != graphics_row.get("decompressed_sha256")
        or source != source_path.read_bytes()
        or _sha256(source) != profile.get("source_graphics_sha256")
        or compressed_size != profile.get("expected_encoded_size")
    ):
        raise ValueError("battle-effect pixel resource catalog contract mismatch")

    animation = _one(payloads["animations"].get("groups"), "animation", group_id=group)
    frame = _one(animation.get("frames"), "frame", frame_id=profile.get("frame_id"))
    component = _one(
        frame.get("components"),
        "component",
        component_index=profile.get("component_index"),
    )
    pixel_x, pixel_y = profile.get("component_pixel_xy", [None, None])
    width = component.get("width")
    tile = component.get("tile_index")
    calculated_offset = (
        (tile + (pixel_y // 8) * (width // 8) + pixel_x // 8) * 32
        + (pixel_y % 8) * 4
        + (pixel_x % 8) // 2
    )
    offset = profile.get("graphics_byte_offset")
    before = profile.get("before_byte")
    after = profile.get("after_byte")
    low_nibble = pixel_x % 2 == 0
    preserved_mask = 0xF0 if low_nibble else 0x0F
    if (
        sequence_id not in animation.get("sequence_ids", [])
        or calculated_offset != offset
        or source[offset] != before
        or (before & 0xF if low_nibble else before >> 4) != profile.get("before_index")
        or (after & 0xF if low_nibble else after >> 4) != profile.get("after_index")
        or before & preserved_mask != after & preserved_mask
    ):
        raise ValueError("battle-effect pixel animation/pixel mapping mismatch")

    selector = profile.get("selector", {})
    selector_kind = selector.get("kind")
    if selector_kind == "ninja_tool":
        binding = _one(
            payloads["sequence_bindings"].get("ninja_tool_bindings"),
            "ninja tool",
            ninja_tool_id=selector.get("id"),
        )
        binding_encoded_action_id = binding.get("encoded_action_id")
    elif selector_kind == "active_action":
        binding = _one(
            payloads["sequence_bindings"].get("active_action_bindings"),
            "active action",
            action_id=selector.get("id"),
        )
        binding_encoded_action_id = binding.get("action_id")
    else:
        raise ValueError("battle-effect pixel selector kind mismatch")
    sequence = _one(
        payloads["sequence_bindings"].get("sequences"),
        "sequence",
        sequence_id=sequence_id,
    )
    if (
        binding_encoded_action_id != selector.get("encoded_action_id")
        or binding.get("sequence_id") != sequence_id
        or group not in sequence.get("nonzero_resource_group_ids", [])
    ):
        raise ValueError("battle-effect pixel action binding mismatch")

    attributes = profile.get("runtime_oam", {}).get("attributes", [])
    attr0, attr1, attr2 = (int(value, 16) for value in attributes)
    if (
        [(attr1 & 0x1FF) + pixel_x, (attr0 & 0xFF) + pixel_y]
        != profile.get("screen_xy")
        or attr2 & 0x3FF != profile["runtime_oam"].get("obj_tile_base")
        or attr2 >> 12 != profile["runtime_oam"].get("palette_bank")
    ):
        raise ValueError("battle-effect pixel OAM screen mapping mismatch")
    palette_path = _safe_file(
        root,
        str(Path(profile["catalogs"]["resource_pairs"]).parent / palette_row["output_bin"]),
        "palette",
    )
    return profile, {
        "base": base,
        "source": source,
        "resource": resource,
        "palette": palette_path.read_bytes(),
    }


def _ledger(profile: dict[str, Any], source_sha: str, graphics: bytes) -> list[dict[str, Any]]:
    encoded = _encode_lz77(graphics)
    allocation = profile["graphics_allocation_offset"]
    pointer_offset = profile["pair_pointer_offset"]
    pointer = 0x08000000 + allocation
    return [
        {
            "id": "battle-effect-graphics-000",
            "kind": "allocation",
            "asset_type": "battle_effect_resource_relocation",
            "resource_type": "graphics",
            "resource_sha256": source_sha,
            "replacement_sha256": _sha256(graphics),
            "offset": allocation,
            "size": len(encoded),
            "after_sha256": _sha256(encoded),
            "after_hex": None,
            "new_pointer": pointer,
            "target_pointer_offsets": [pointer_offset],
            "allocation": {
                "owner": "sequel_image_assets",
                "partition": "sequel-image-assets",
                "region": "battle-effects",
                "region_owner": "battle_effect_resources",
            },
            "decompressed_size": len(graphics),
        },
        {
            "id": f"battle-effect-graphics-000.pointer-{pointer_offset:x}",
            "kind": "redirect",
            "asset_type": "battle_effect_resource_pointer",
            "resource_type": "graphics",
            "resource_sha256": source_sha,
            "replacement_sha256": None,
            "offset": pointer_offset,
            "size": 4,
            "after_sha256": _sha256(pointer.to_bytes(4, "little")),
            "after_hex": pointer.to_bytes(4, "little").hex(),
            "new_pointer": pointer,
            "target_pointer_offsets": [pointer_offset],
            "allocation": None,
            "decompressed_size": None,
        },
    ]


def _rebuild_rom(base: bytes, profile: dict[str, Any], graphics: bytes) -> bytes:
    encoded = _encode_lz77(graphics)
    if (
        len(encoded) != profile["expected_encoded_size"]
        or _decompress_lz77(encoded, 0) != graphics
    ):
        raise ValueError("battle-effect pixel independent LZ77 mismatch")
    output = bytearray(base + bytes([0xFF]) * (0x1000000 - len(base)))
    allocation = profile["graphics_allocation_offset"]
    output[allocation : allocation + len(encoded)] = encoded
    pointer = (0x08000000 + allocation).to_bytes(4, "little")
    offset = profile["pair_pointer_offset"]
    output[offset : offset + 4] = pointer
    return bytes(output)


def _verify_build(
    root: Path,
    raw: Path,
    profile_path: Path,
    profile: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    build = _json(raw / "build-manifest.json")
    group = profile["group_id"]
    graphics = {
        variant: (raw / variant / f"group-{group:02d}-graphics-4bpp.bin").read_bytes()
        for variant in VARIANTS
    }
    candidate = bytearray(contract["source"])
    candidate[profile["graphics_byte_offset"]] = profile["after_byte"]
    if graphics != {"baseline": contract["source"], "candidate": bytes(candidate)}:
        raise ValueError("battle-effect pixel authored graphics mismatch")
    rebuilt = {
        variant: _rebuild_rom(contract["base"], profile, content)
        for variant, content in graphics.items()
    }
    selector_id_key = (
        "ninja_tool_id"
        if profile["selector"]["kind"] == "ninja_tool"
        else "active_action_id"
    )
    expected_binding = {
        selector_id_key: profile["selector"]["id"],
        "encoded_action_id": profile["selector"]["encoded_action_id"],
        "sequence_id": profile["sequence_id"],
        "group_id": group,
    }
    expected_edit = {
        key: profile[key]
        for key in (
            "frame_id", "component_index", "component_pixel_xy",
            "graphics_byte_offset", "before_byte", "after_byte",
            "before_index", "after_index", "screen_xy", "before_rgb", "after_rgb",
        )
    }
    if (
        build.get("schema") != BUILD_SCHEMA
        or build.get("profile") != profile_path.relative_to(root).as_posix()
        or build.get("profile_sha256") != _sha256_file(profile_path)
        or build.get("profile_id") != profile["profile_id"]
        or build.get("base_rom_sha256") != ROM_SHA256
        or build.get("input_state") != profile["input_state"]
        or build.get("input_state_sha256") != profile["input_state_sha256"]
        or build.get("input_evidence") != profile["input_evidence"]
        or build.get("input_evidence_sha256") != profile["input_evidence_sha256"]
        or build.get("runtime_input") != profile["runtime_input"]
        or build.get("runtime_oam") != profile["runtime_oam"]
        or build.get("binding") != expected_binding
        or build.get("edit") != expected_edit
        or build.get("catalogs") != profile["catalogs"]
        or build.get("same_patch_topology") is not True
        or build.get("same_encoded_size") is not True
    ):
        raise ValueError("battle-effect pixel build metadata mismatch")
    source_sha = profile["source_graphics_sha256"]
    for variant in VARIANTS:
        row = build.get("variants", {}).get(variant, {})
        expected = {
            "rom_path": f"{variant}/{variant}.gba",
            "rom_sha256": _sha256(rebuilt[variant]),
            "rom_size": 0x1000000,
            "spec_path": f"{variant}/spec.json",
            "graphics_path": f"{variant}/group-{group:02d}-graphics-4bpp.bin",
            "graphics_sha256": _sha256(graphics[variant]),
            "encoded_graphics_size": profile["expected_encoded_size"],
            "graphics_allocation_offset": profile["graphics_allocation_offset"],
            "patch_ledger": _ledger(profile, source_sha, graphics[variant]),
        }
        if row != expected:
            raise ValueError(f"battle-effect pixel {variant} ROM reconstruction mismatch")
        spec = _json(raw / variant / "spec.json")
        edit = spec.get("edits", [None])
        if (
            spec.get("schema") != "battle-effect-resource-relocation-v1"
            or spec.get("base_rom_sha256") != ROM_SHA256
            or len(edit) != 1
            or edit[0].get("id") != f"{profile['profile_id']}-{variant}"
            or edit[0].get("resource_type") != "graphics"
            or edit[0].get("resource_sha256") != source_sha
            or edit[0].get("source_file")
            != f"raw/{variant}/group-{group:02d}-graphics-4bpp.bin"
        ):
            raise ValueError(f"battle-effect pixel {variant} spec mismatch")
    return build, graphics


def _verify_runtime(root: Path, raw: Path, profile: dict[str, Any], build: dict[str, Any], graphics: dict[str, bytes], palette: bytes) -> tuple[dict[str, list[int]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    frame = profile["runtime_input"]["capture_frame"]
    event = {
        "key": profile["runtime_input"]["key"],
        "down_frame": profile["runtime_input"]["down_frame"],
        "up_frame": profile["runtime_input"]["up_frame"],
        "hold_frames": profile["runtime_input"]["up_frame"] - profile["runtime_input"]["down_frame"],
    }
    states = {}
    runs = {}
    for variant in VARIANTS:
        audit = _json(raw / variant / "audit.json")
        guard = _json(raw / variant / "guard.json")
        state_path = raw / variant / f"frame{frame}.ss9"
        png_path = raw / variant / f"frame{frame}.png"
        if (
            audit != _json(raw / variant / "sentinel.json")
            or audit.get("success") is not True
            or audit.get("status") != "capture-complete"
            or audit.get("evidence_mode") != "single-input"
            or audit.get("audit") != f"raw/{variant}/audit.json"
            or audit.get("input_state") != profile["input_state"]
            or audit.get("inputs") != [event]
            or audit.get("capture_frame") != frame
            or audit.get("automatic_inputs") != []
            or audit.get("recovery_inputs") != []
            or audit.get("binary_sha256") != MGBA_BINARY_SHA256
            or audit.get("build_manifest_sha256")
            != MGBA_BUILD_MANIFEST_SHA256
            or audit.get("replay_script_sha256")
            != _sha256_file(root / "tools/mgba_single_input_replay.lua")
            or audit.get("input_state_sha256") != profile["input_state_sha256"]
            or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
            or audit.get("staged_rom_sha256") != audit.get("rom_sha256")
            or audit.get("output_state_sha256") != _sha256_file(state_path)
            or audit.get("output_png_sha256") != _sha256_file(png_path)
            or audit.get("guard_summary_sha256") != _sha256_file(raw / variant / "guard.json")
            or audit.get("pgid_clean") is not True
            or audit.get("runtime_residue", {}).get("pgid_clean") is not True
            or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
            or guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("degraded") is not False
            or guard.get("completion_trigger") != "success-marker"
            or guard.get("protection_backend") != "posix-process-group"
            or guard.get("cwd") != "."
            or guard.get("command") != ["mGBA", "--script", "tools/mgba_single_input_replay.lua", f"runtime-only/{variant}/staged.gba"]
            or guard.get("child_pid") != audit.get("child_pgid")
            or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
            or any(value.startswith("/") for value in _strings(audit))
            or any(value.startswith("/") for value in _strings(guard))
        ):
            raise ValueError(f"battle-effect pixel {variant} runtime provenance mismatch")
        states[variant] = load_gba_state(state_path)
        runs[variant] = {
            "run_id": audit["run_id"],
            "rom_sha256": audit["rom_sha256"],
            "state_sha256": audit["output_state_sha256"],
            "png_sha256": audit["output_png_sha256"],
            "binary_sha256": audit["binary_sha256"],
            "build_manifest_sha256": audit["build_manifest_sha256"],
            "replay_script_sha256": audit["replay_script_sha256"],
            "guard_sha256": audit["guard_summary_sha256"],
            "child_pgid": audit["child_pgid"],
            "peak_tree_rss_mib": audit["peak_tree_rss_mib"],
            "pgid_clean": True,
        }
    differences = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    changed = int(profile["runtime_oam"]["obj_vram_address"], 16) - 0x06000000 + profile["graphics_byte_offset"]
    expected = {name: [] for name in DOMAINS}
    expected["VRAM"] = [changed]
    if differences != expected:
        raise ValueError("battle-effect pixel runtime memory mismatch")
    vram = int(profile["runtime_oam"]["obj_vram_address"], 16)
    pram = 0x05000200 + profile["runtime_oam"]["palette_bank"] * 32
    oam = 0x07000000 + profile["runtime_oam"]["oam_index"] * 8
    expected_oam = b"".join(int(value, 16).to_bytes(2, "little") for value in profile["runtime_oam"]["attributes"])
    for variant in VARIANTS:
        rendered, _ = render_checkpoint(raw / variant / f"frame{frame}.ss9")
        if (
            states[variant].read_memory(vram, len(graphics[variant])) != graphics[variant]
            or states[variant].read_memory(pram, len(palette)) != palette
            or states[variant].read_memory(oam, 6) != expected_oam
            or rendered != _rgb(raw / variant / f"frame{frame}.png")
        ):
            raise ValueError(f"battle-effect pixel {variant} natural route mismatch")
    baseline_rgb = _rgb(raw / "baseline" / f"frame{frame}.png")
    candidate_rgb = _rgb(raw / "candidate" / f"frame{frame}.png")
    changes = _pixel_changes(baseline_rgb, candidate_rgb)
    expected_pixels = [{
        "x": profile["screen_xy"][0],
        "y": profile["screen_xy"][1],
        "before_rgb": profile["before_rgb"],
        "after_rgb": profile["after_rgb"],
    }]
    if changes != expected_pixels:
        raise ValueError("battle-effect pixel final pixel mismatch")
    return differences, changes, runs


def _verify(root: Path, artifact: Path) -> None:
    root = root.resolve(strict=True)
    artifact = artifact.resolve(strict=True)
    manifest = _json(artifact / "manifest.json")
    profile_path = _safe_file(root, manifest.get("profile"), "profile")
    profile, contract = _verify_profile(root, profile_path)
    raw = artifact / "raw"
    expected_files = {
        Path("manifest.json"),
        Path("runtime-evidence.json"),
        *(Path("raw") / name for name in _raw_files(profile)),
    }
    actual_files = {path.relative_to(artifact) for path in artifact.rglob("*") if path.is_file()}
    if any(path.is_symlink() for path in artifact.rglob("*")) or actual_files != expected_files:
        raise ValueError("battle-effect pixel artifact file set mismatch")
    for path in artifact.rglob("*.json"):
        if any(value.startswith("/") for value in _strings(_json(path))):
            raise ValueError("battle-effect pixel artifact contains absolute paths")
    expected_files_hash = {
        path.relative_to(artifact).as_posix(): _sha256_file(path)
        for path in sorted(artifact.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    expected_scope = _selector_scope(profile["selector"])
    if (
        manifest.get("schema") != PROMOTION_SCHEMA
        or manifest.get("artifact_schema") != EVIDENCE_SCHEMA
        or manifest.get("artifact_id") != f"battle-effect-group{profile['group_id']}-pixel-ab-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("base_rom_sha256") != ROM_SHA256
        or manifest.get("parent")
        != {"path": profile["input_state"], "sha256": profile["input_state_sha256"]}
        or manifest.get("source_catalog")
        != profile["catalogs"]["resource_pairs"]
        or manifest.get("source_catalog_sha256")
        != profile["catalogs"]["resource_pairs_sha256"]
        or manifest.get("profile_sha256") != _sha256_file(profile_path)
        or manifest.get("payload_file") != "runtime-evidence.json"
        or manifest.get("payload_sha256") != _sha256_file(artifact / "runtime-evidence.json")
        or manifest.get("files") != expected_files_hash
        or manifest.get("raw_files")
        != {name: _sha256_file(raw / name) for name in _raw_files(profile)}
        or manifest.get("implementation_sha256")
        != {path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS}
        or manifest.get("scope") != expected_scope
        or manifest.get("verifier", {}).get("exit_code") != 0
        or manifest.get("verifier", {}).get("result")
        != {"errors": [], "verified": True}
        or not isinstance(manifest.get("verifier", {}).get("command"), list)
    ):
        raise ValueError("battle-effect pixel manifest mismatch")
    build, graphics = _verify_build(root, raw, profile_path, profile, contract)
    differences, changes, runs = _verify_runtime(
        root, raw, profile, build, graphics, contract["palette"]
    )
    input_state = load_gba_state(root / profile["input_state"])
    if input_state.read_memory(0x06010000, 0x8000).find(graphics["baseline"]) >= 0:
        raise ValueError("battle-effect pixel pre-load boundary mismatch")
    evidence = _json(artifact / "runtime-evidence.json")
    frame = profile["runtime_input"]["capture_frame"]
    event = {
        "key": profile["runtime_input"]["key"],
        "down_frame": profile["runtime_input"]["down_frame"],
        "up_frame": profile["runtime_input"]["up_frame"],
        "hold_frames": profile["runtime_input"]["up_frame"] - profile["runtime_input"]["down_frame"],
    }
    runtime = evidence.get("runtime", {})
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("verified") is not True
        or evidence.get("profile") != profile_path.relative_to(root).as_posix()
        or evidence.get("profile_sha256") != _sha256_file(profile_path)
        or evidence.get("binding") != build["binding"]
        or evidence.get("edit") != build["edit"]
        or evidence.get("input") != {
            "path": profile["input_state"], "sha256": profile["input_state_sha256"],
            "event": event, "capture_frame": frame, "resource_absent_before_input": True,
        }
        or runtime.get("memory_differences") != differences
        or runtime.get("graphics_vram_address") != profile["runtime_oam"]["obj_vram_address"]
        or runtime.get("changed_vram_address") != f"0x{0x06000000 + differences['VRAM'][0]:08X}"
        or runtime.get("baseline_vram_byte") != profile["before_byte"]
        or runtime.get("candidate_vram_byte") != profile["after_byte"]
        or runtime.get("oam_entry") != profile["runtime_oam"]["oam_index"]
        or runtime.get("oam_attributes") != profile["runtime_oam"]["attributes"]
        or runtime.get("palette_bank") != profile["runtime_oam"]["palette_bank"]
        or runtime.get("renderer_exact") is not True
        or runtime.get("pixels", {}).get("count") != 1
        or runtime.get("pixels", {}).get("changes") != changes
        or evidence.get("runs") != runs
        or evidence.get("scope") != expected_scope
    ):
        raise ValueError("battle-effect pixel signed semantic evidence mismatch")


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        _verify(Path(root), Path(artifact))
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as error:
        return {"errors": [str(error)], "verified": False}
    return {"errors": [], "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = verify_evidence(args.root, args.artifact)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
