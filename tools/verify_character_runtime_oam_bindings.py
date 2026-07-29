#!/usr/bin/env python3
"""Independently reconstruct and verify natural character/OAM bindings."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from typing import Any

try:
    from tools.butano.analyze_scenario_41_gpu import decode_gpu
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from butano.analyze_scenario_41_gpu import decode_gpu
    from inspect_mgba_savestate import load_gba_state


SCHEMA = "character-runtime-oam-bindings-v1"
ROM_RELATIVE = Path("rom/base.gba")
EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
SOURCE_RELATIVE = Path("artifacts/character-battle-visuals-v1")
CHECKPOINT_RELATIVE = Path("artifacts/runtime-checkpoints")
MODE_NAMES = {
    0: "normal",
    1: "semi_transparent",
    2: "obj_window",
    3: "prohibited",
}
REGISTER_OFFSETS = {
    "DISPCNT": 0x000,
    "BG0CNT": 0x008,
    "BG1CNT": 0x00A,
    "BG2CNT": 0x00C,
    "BG3CNT": 0x00E,
    "BG0HOFS": 0x010,
    "BG0VOFS": 0x012,
    "BG1HOFS": 0x014,
    "BG1VOFS": 0x016,
    "BG2HOFS": 0x018,
    "BG2VOFS": 0x01A,
    "BG3HOFS": 0x01C,
    "BG3VOFS": 0x01E,
    "WIN0H": 0x040,
    "WIN1H": 0x042,
    "WIN0V": 0x044,
    "WIN1V": 0x046,
    "WININ": 0x048,
    "WINOUT": 0x04A,
    "MOSAIC": 0x04C,
    "BLDCNT": 0x050,
    "BLDALPHA": 0x052,
    "BLDY": 0x054,
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _h16(value: int) -> str:
    return f"0x{value:04X}"


def _tracked_states(root: Path) -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--",
            f"{CHECKPOINT_RELATIVE.as_posix()}/*.ss9",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise ValueError(
            "cannot enumerate tracked checkpoints: "
            + completed.stderr.decode("utf-8", "replace").strip()
        )
    result = sorted(
        root / item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    )
    if not result:
        raise ValueError("no tracked runtime checkpoints found")
    if any(not path.is_file() for path in result):
        raise ValueError("a tracked runtime checkpoint is missing")
    return result


def _source_payload(
    directory: Path,
    metadata: dict[str, Any],
    label: str,
) -> bytes:
    relative = metadata.get("file")
    if not isinstance(relative, str):
        raise ValueError(f"{label} path is missing")
    path = directory / relative
    data = path.read_bytes()
    if len(data) != metadata.get("size"):
        raise ValueError(f"{label} size mismatch")
    if _digest(data) != metadata.get("sha256"):
        raise ValueError(f"{label} SHA-256 mismatch")
    return data


def _rebuild_source_index(
    root: Path,
) -> tuple[
    dict[str, Any],
    str,
    dict[tuple[int, int, str], list[dict[str, Any]]],
]:
    directory = root / SOURCE_RELATIVE
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict):
        raise ValueError("source manifest is not an object")
    if manifest.get("schema") != "character-battle-visuals-v1":
        raise ValueError("source manifest schema mismatch")
    if manifest.get("scope") != {
        "static_source_space_frames": True,
        "pointer_bounded_source_previews": False,
        "component_geometry_and_flips": True,
        "animation_holds": True,
        "screen_space_position": False,
        "camera_and_priority": False,
        "runtime_slot_selection": False,
        "blend_and_palette_transform": False,
        "all_component_termination_semantics_complete": True,
    }:
        raise ValueError("source manifest scope mismatch")

    slots_by_resource: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for slot in manifest["slots"]:
        resource_id = slot["resource_id"]
        if resource_id is not None:
            slots_by_resource[resource_id].append(slot)

    index: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for resource in manifest["resources"]:
        resource_id = resource["resource_id"]
        graphics = _source_payload(
            directory,
            resource["graphics"],
            f"resource {resource_id} graphics",
        )
        palette = _source_payload(
            directory,
            resource["palette"],
            f"resource {resource_id} palette",
        )
        if len(palette) != 32:
            raise ValueError(f"resource {resource_id} palette size is invalid")
        slots = slots_by_resource[resource_id]
        rows = sorted(item["row"] for item in slots)
        character_ids = sorted({item["character_id"] for item in slots})
        visual_slots = sorted({item["visual_slot"] for item in slots})
        semantics = sorted({item["semantic"] for item in slots})
        for frame in resource["frames"]:
            if not frame["render_complete"]:
                raise ValueError("source frame is not complete")
            for component in frame["components"]:
                width = component["width"]
                height = component["height"]
                start = component["tile_offset"] * 32
                end = start + width * height // 2
                if start < 0 or end > len(graphics):
                    raise ValueError("source component exceeds graphics")
                component_bytes = graphics[start:end]
                if not any(component_bytes):
                    continue
                graphics_hash = _digest(component_bytes)
                index[(width, height, graphics_hash)].append(
                    {
                        "resource_id": resource_id,
                        "frame_id": frame["frame_id"],
                        "component_index": component["component_index"],
                        "source_tile_offset": component["tile_offset"],
                        "component_x": component["x"],
                        "component_y": component["y"],
                        "component_horizontal_flip": component[
                            "horizontal_flip"
                        ],
                        "component_vertical_flip": component[
                            "vertical_flip"
                        ],
                        "source_graphics_sha256": graphics_hash,
                        "source_palette_sha256": _digest(palette),
                        "_palette": palette,
                        "slot_rows": rows,
                        "character_ids": character_ids,
                        "visual_slots": visual_slots,
                        "semantics": semantics,
                    }
                )
    return manifest, _digest(manifest_raw), index


def _palette_delta(
    source: bytes,
    runtime: bytes,
) -> tuple[int, list[dict[str, Any]]]:
    source_values = struct.unpack("<16H", source)
    runtime_values = struct.unpack("<16H", runtime)
    differences = []
    for index, (source_value, runtime_value) in enumerate(
        zip(source_values, runtime_values)
    ):
        if source_value == runtime_value:
            continue
        differences.append(
            {
                "color_index": index,
                "source_bgr555": _h16(source_value),
                "runtime_bgr555": _h16(runtime_value),
            }
        )
    return len(differences), differences


def _rebuild_candidate(
    raw_candidate: dict[str, Any],
    runtime_palette: bytes,
    x: int,
    y: int,
    affine: bool,
) -> dict[str, Any]:
    count, differences = _palette_delta(
        raw_candidate["_palette"],
        runtime_palette,
    )
    candidate = {
        key: value
        for key, value in raw_candidate.items()
        if not key.startswith("_")
    }
    candidate["palette_difference_count"] = count
    candidate["palette_differences"] = differences
    candidate["non_affine_task_origin_candidate"] = (
        None
        if affine
        else {
            "x": x - raw_candidate["component_x"],
            "y": y - raw_candidate["component_y"],
        }
    )
    return candidate


def _register_snapshot(io: bytes) -> dict[str, str]:
    return {
        name: _h16(struct.unpack_from("<H", io, offset)[0])
        for name, offset in REGISTER_OFFSETS.items()
    }


def _rebuild_checkpoint(
    root: Path,
    path: Path,
    source_index: dict[tuple[int, int, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    container = path.read_bytes()
    state = load_gba_state(path)
    io = state.read_memory(0x04000000, 0x400)
    pram = state.read_memory(0x05000000, 0x400)
    oam = state.read_memory(0x07000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    decoded_gpu = decode_gpu(io, oam)
    mapping_1d = (
        decoded_gpu["display"]["obj_character_mapping"] == "1d"
    )
    active = len(decoded_gpu["objects"])
    matches: list[dict[str, Any]] = []

    if mapping_1d:
        for obj in decoded_gpu["objects"]:
            if obj["colors"] != 16:
                continue
            object_index = obj["index"]
            raw_attrs = obj["raw"]
            attr0 = int(raw_attrs[0:4], 16)
            attr1 = int(raw_attrs[4:8], 16)
            attr2 = int(raw_attrs[8:12], 16)
            affine = obj["affine"]
            width, height = obj["dimensions"]
            colors = 4
            tile_index = obj["tile_index"]
            start = 0x10000 + tile_index * 32
            end = start + width * height // 2
            if end > len(vram):
                continue
            graphics_hash = _digest(vram[start:end])
            raw_candidates = source_index.get(
                (width, height, graphics_hash)
            )
            if not raw_candidates:
                continue
            bank = obj["palette_bank"]
            if bank is None:
                raise ValueError(
                    f"4bpp OAM object {object_index} has no palette bank"
                )
            palette = pram[0x200 + bank * 32 : 0x220 + bank * 32]
            raw_x = obj["position"]["raw_x"]
            raw_y = obj["position"]["raw_y"]
            x = obj["position"]["x"]
            y = obj["position"]["y"]
            candidates = [
                _rebuild_candidate(item, palette, x, y, affine)
                for item in raw_candidates
            ]
            candidates.sort(
                key=lambda item: (
                    item["palette_difference_count"],
                    item["resource_id"],
                    item["frame_id"],
                    item["component_index"],
                )
            )
            best_distance = candidates[0]["palette_difference_count"]
            best = [
                item
                for item in candidates
                if item["palette_difference_count"] == best_distance
            ]
            matches.append(
                {
                    "oam_index": object_index,
                    "attr0": _h16(attr0),
                    "attr1": _h16(attr1),
                    "attr2": _h16(attr2),
                    "affine": affine,
                    "double_size": obj["double_size"],
                    "obj_mode": MODE_NAMES[obj["object_mode"]],
                    "mosaic": obj["mosaic"],
                    "color_mode_bpp": colors,
                    "horizontal_flip": (
                        None if affine else obj["horizontal_flip"]
                    ),
                    "vertical_flip": (
                        None if affine else obj["vertical_flip"]
                    ),
                    "screen_x_raw": raw_x,
                    "screen_y_raw": raw_y,
                    "screen_x": x,
                    "screen_y": y,
                    "width": width,
                    "height": height,
                    "tile_index": tile_index,
                    "priority": obj["priority"],
                    "palette_bank": bank,
                    "runtime_graphics_sha256": graphics_hash,
                    "runtime_palette_sha256": _digest(palette),
                    "source_candidate_count": len(candidates),
                    "best_palette_difference_count": best_distance,
                    "resolution": (
                        "unique_best_source"
                        if len(best) == 1
                        else "ambiguous_best_source"
                    ),
                    "best_sources": best,
                    "source_candidates": candidates,
                }
            )

    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _digest(container),
        "size": len(container),
        "savestate_version_magic": f"0x{state.version_magic:08X}",
        "regions": {
            "io": {"size": len(io), "sha256": _digest(io)},
            "pram": {"size": len(pram), "sha256": _digest(pram)},
            "oam": {"size": len(oam), "sha256": _digest(oam)},
            "vram": {"size": len(vram), "sha256": _digest(vram)},
        },
        "display_registers": _register_snapshot(io),
        "obj_mapping": (
            "one_dimensional" if mapping_1d else "two_dimensional"
        ),
        "active_oam_object_count": active,
        "matched_oam_object_count": len(matches),
        "matches": matches,
    }


def _reconstruct(root: Path) -> dict[str, Any]:
    rom = root / ROM_RELATIVE
    rom_hash = _file_digest(rom)
    if rom_hash != EXPECTED_ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    source_manifest, source_hash, source_index = _rebuild_source_index(root)
    checkpoints = []
    errors = []
    for path in _tracked_states(root):
        try:
            checkpoints.append(
                _rebuild_checkpoint(root, path, source_index)
            )
        except (OSError, ValueError, struct.error) as error:
            errors.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _file_digest(path),
                    "error": str(error),
                }
            )

    matches = [
        match
        for checkpoint in checkpoints
        for match in checkpoint["matches"]
    ]
    active = sum(
        checkpoint["active_oam_object_count"]
        for checkpoint in checkpoints
    )
    distances = [
        match["best_palette_difference_count"] for match in matches
    ]
    summary = {
        "checkpoint_count": len(checkpoints) + len(errors),
        "checkpoint_parse_error_count": len(errors),
        "one_dimensional_obj_mapping_count": sum(
            item["obj_mapping"] == "one_dimensional"
            for item in checkpoints
        ),
        "active_oam_object_count": active,
        "matched_oam_object_count": len(matches),
        "unmatched_oam_object_count": active - len(matches),
        "checkpoints_with_matches": sum(
            bool(item["matches"]) for item in checkpoints
        ),
        "unique_best_source_count": sum(
            item["resolution"] == "unique_best_source"
            for item in matches
        ),
        "ambiguous_best_source_count": sum(
            item["resolution"] == "ambiguous_best_source"
            for item in matches
        ),
        "palette_exact_match_count": sum(value == 0 for value in distances),
        "palette_difference_at_most_one_count": sum(
            value <= 1 for value in distances
        ),
    }
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_RELATIVE.as_posix(),
            "size": rom.stat().st_size,
            "sha256": rom_hash,
        },
        "source_artifact": {
            "path": SOURCE_RELATIVE.as_posix(),
            "schema": source_manifest["schema"],
            "manifest_sha256": source_hash,
            "resource_count": source_manifest["summary"]["resource_count"],
            "frame_count": source_manifest["summary"]["frame_count"],
            "component_graphics_index_key_count": len(source_index),
        },
        "checkpoint_source": {
            "directory": CHECKPOINT_RELATIVE.as_posix(),
            "selection": "git ls-files -- artifacts/runtime-checkpoints/*.ss9",
            "parse_errors": errors,
        },
        "binding_contract": {
            "graphics_match": (
                "active 4bpp OAM width/height plus exact SHA-256 of the "
                "contiguous 1D OBJ VRAM tile payload"
            ),
            "palette_ranking": (
                "minimum count of unequal BGR555 colors between the source "
                "16-color palette and the OAM-selected runtime OBJ bank"
            ),
            "coordinate_normalization": (
                "x is signed 9-bit; y values 160..255 are represented as "
                "wrapped negative screen coordinates"
            ),
            "origin_candidate": (
                "for non-affine matches only: observed screen coordinate "
                "minus source component-local coordinate; this is an "
                "algebraic candidate, not a traced task writer"
            ),
        },
        "summary": summary,
        "scope": {
            "all_tracked_checkpoints_scanned": (
                not errors
                and summary["checkpoint_count"] == len(checkpoints)
            ),
            "matched_oam_graphics_bound_to_source_components": bool(matches),
            "runtime_palette_differences_recorded": bool(matches),
            "observed_screen_coordinates_and_priority_recorded": bool(matches),
            "natural_task_and_selector_trace_complete": False,
            "all_character_slots_runtime_observed": False,
            "camera_writer_schedule_complete": False,
            "blend_window_and_bg_pixel_composition_complete": False,
            "screen_space_composition_complete": False,
        },
        "checkpoints": checkpoints,
    }


def verify_bindings(
    root: Path | str,
    bindings_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    bindings_path = Path(bindings_path)
    errors = []
    try:
        actual = json.loads(bindings_path.read_text(encoding="utf-8"))
        if not isinstance(actual, dict):
            raise ValueError("bindings JSON must contain an object")
        expected = _reconstruct(root)
        if actual != expected:
            errors.append(
                "bindings do not match independently reconstructed evidence"
            )
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        errors.append(str(error))
        actual = {}
    summary = actual.get("summary", {}) if isinstance(actual, dict) else {}
    return {
        "verified": not errors,
        "errors": errors,
        "checkpoints": summary.get("checkpoint_count", 0) if not errors else 0,
        "matches": summary.get("matched_oam_object_count", 0) if not errors else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--bindings",
        type=Path,
        required=True,
    )
    args = parser.parse_args()
    report = verify_bindings(args.root, args.bindings)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
