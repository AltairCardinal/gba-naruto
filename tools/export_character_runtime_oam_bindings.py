#!/usr/bin/env python3
"""Bind character source components to natural runtime OAM in saved checkpoints."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
from typing import Any
import uuid

try:
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state


SCHEMA = "character-runtime-oam-bindings-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_ARTIFACT = Path("artifacts/character-battle-visuals-v1")
CHECKPOINT_DIRECTORY = Path("artifacts/runtime-checkpoints")
OBJ_VRAM_OFFSET = 0x10000
OBJ_PALETTE_OFFSET = 0x200
OAM_OBJECT_COUNT = 128
OAM_OBJECT_SIZE = 8
SIZES = {
    0: {
        0: (8, 8),
        1: (16, 16),
        2: (32, 32),
        3: (64, 64),
    },
    1: {
        0: (16, 8),
        1: (32, 8),
        2: (32, 16),
        3: (64, 32),
    },
    2: {
        0: (8, 16),
        1: (8, 32),
        2: (16, 32),
        3: (32, 64),
    },
}
OBJ_MODES = {
    0: "normal",
    1: "semi_transparent",
    2: "obj_window",
    3: "prohibited",
}
DISPLAY_REGISTERS = {
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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hex16(value: int) -> str:
    return f"0x{value:04X}"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _tracked_checkpoints(root: Path) -> list[Path]:
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--",
            f"{CHECKPOINT_DIRECTORY.as_posix()}/*.ss9",
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
    paths = [
        root / raw.decode("utf-8")
        for raw in completed.stdout.split(b"\0")
        if raw
    ]
    if not paths:
        raise ValueError("no tracked runtime checkpoints found")
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"tracked checkpoint is missing: {missing[0]}")
    return sorted(paths)


def _validate_source_file(
    artifact_dir: Path,
    metadata: dict[str, Any],
    *,
    label: str,
) -> bytes:
    relative = metadata.get("file")
    if not isinstance(relative, str):
        raise ValueError(f"{label} file path is missing")
    path = artifact_dir / relative
    if not path.is_file():
        raise ValueError(f"{label} file is missing: {relative}")
    data = path.read_bytes()
    if len(data) != metadata.get("size"):
        raise ValueError(f"{label} size mismatch")
    if _sha256_bytes(data) != metadata.get("sha256"):
        raise ValueError(f"{label} hash mismatch")
    return data


def _source_index(
    root: Path,
) -> tuple[
    dict[str, Any],
    str,
    dict[tuple[int, int, str], list[dict[str, Any]]],
]:
    artifact_dir = root / SOURCE_ARTIFACT
    manifest_path = artifact_dir / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != "character-battle-visuals-v1":
        raise ValueError("character source artifact schema mismatch")
    scope = manifest.get("scope", {})
    if (
        not scope.get("static_source_space_frames")
        or not scope.get("all_component_termination_semantics_complete")
    ):
        raise ValueError("character source artifact is not statically complete")

    slots_by_resource: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for slot in manifest.get("slots", []):
        resource_id = slot.get("resource_id")
        if resource_id is not None:
            slots_by_resource[resource_id].append(slot)

    index: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for resource in manifest.get("resources", []):
        resource_id = resource["resource_id"]
        graphics = _validate_source_file(
            artifact_dir,
            resource["graphics"],
            label=f"resource {resource_id} graphics",
        )
        palette = _validate_source_file(
            artifact_dir,
            resource["palette"],
            label=f"resource {resource_id} palette",
        )
        if len(palette) != 32:
            raise ValueError(f"resource {resource_id} palette must be 32 bytes")
        resource_slots = slots_by_resource[resource_id]
        slot_rows = sorted(slot["row"] for slot in resource_slots)
        character_ids = sorted(
            {slot["character_id"] for slot in resource_slots}
        )
        visual_slots = sorted(
            {slot["visual_slot"] for slot in resource_slots}
        )
        semantics = sorted({slot["semantic"] for slot in resource_slots})
        for frame in resource["frames"]:
            if not frame.get("render_complete"):
                raise ValueError(
                    f"resource {resource_id} frame {frame['frame_id']} is incomplete"
                )
            for component in frame["components"]:
                width = component["width"]
                height = component["height"]
                byte_count = width * height // 2
                start = component["tile_offset"] * 32
                end = start + byte_count
                if start < 0 or end > len(graphics):
                    raise ValueError(
                        f"resource {resource_id} component graphics exceed source"
                    )
                payload = graphics[start:end]
                if not any(payload):
                    continue
                key = (width, height, _sha256_bytes(payload))
                index[key].append(
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
                        "source_graphics_sha256": key[2],
                        "source_palette_sha256": _sha256_bytes(palette),
                        "_palette": palette,
                        "slot_rows": slot_rows,
                        "character_ids": character_ids,
                        "visual_slots": visual_slots,
                        "semantics": semantics,
                    }
                )
    if not index:
        raise ValueError("character source component index is empty")
    return manifest, _sha256_bytes(manifest_raw), index


def _palette_comparison(
    source: bytes,
    runtime: bytes,
) -> tuple[int, list[dict[str, Any]]]:
    source_colors = struct.unpack("<16H", source)
    runtime_colors = struct.unpack("<16H", runtime)
    differences = [
        {
            "color_index": index,
            "source_bgr555": _hex16(source_color),
            "runtime_bgr555": _hex16(runtime_color),
        }
        for index, (source_color, runtime_color) in enumerate(
            zip(source_colors, runtime_colors)
        )
        if source_color != runtime_color
    ]
    return len(differences), differences


def _candidate_record(
    candidate: dict[str, Any],
    *,
    runtime_palette: bytes,
    screen_x: int,
    screen_y: int,
    affine: bool,
) -> dict[str, Any]:
    difference_count, differences = _palette_comparison(
        candidate["_palette"],
        runtime_palette,
    )
    result = {
        key: value
        for key, value in candidate.items()
        if not key.startswith("_")
    }
    result["palette_difference_count"] = difference_count
    result["palette_differences"] = differences
    result["non_affine_task_origin_candidate"] = (
        None
        if affine
        else {
            "x": screen_x - candidate["component_x"],
            "y": screen_y - candidate["component_y"],
        }
    )
    return result


def _display_registers(io: bytes) -> dict[str, str]:
    return {
        name: _hex16(struct.unpack_from("<H", io, offset)[0])
        for name, offset in DISPLAY_REGISTERS.items()
    }


def _scan_checkpoint(
    root: Path,
    path: Path,
    source_index: dict[tuple[int, int, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    raw = path.read_bytes()
    state = load_gba_state(path)
    io = state.read_memory(0x04000000, 0x400)
    pram = state.read_memory(0x05000000, 0x400)
    oam = state.read_memory(0x07000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    one_dimensional = bool(dispcnt & 0x40)
    active_count = 0
    matches: list[dict[str, Any]] = []

    if one_dimensional:
        for oam_index in range(OAM_OBJECT_COUNT):
            offset = oam_index * OAM_OBJECT_SIZE
            attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, offset)
            affine = bool(attr0 & 0x0100)
            if not affine and attr0 & 0x0200:
                continue
            shape = (attr0 >> 14) & 3
            size = (attr1 >> 14) & 3
            if shape not in SIZES:
                raise ValueError(
                    f"active OAM object {oam_index} uses prohibited shape 3"
                )
            active_count += 1
            width, height = SIZES[shape][size]
            color_mode_bpp = 8 if attr0 & 0x2000 else 4
            if color_mode_bpp != 4:
                continue
            tile_index = attr2 & 0x03FF
            byte_count = width * height // 2
            start = OBJ_VRAM_OFFSET + tile_index * 32
            end = start + byte_count
            if end > len(vram):
                continue
            runtime_graphics = vram[start:end]
            key = (
                width,
                height,
                _sha256_bytes(runtime_graphics),
            )
            source_candidates = source_index.get(key)
            if not source_candidates:
                continue

            palette_bank = (attr2 >> 12) & 0xF
            palette_start = OBJ_PALETTE_OFFSET + palette_bank * 32
            runtime_palette = pram[palette_start : palette_start + 32]
            raw_x = attr1 & 0x01FF
            raw_y = attr0 & 0x00FF
            screen_x = raw_x if raw_x < 0x100 else raw_x - 0x200
            screen_y = raw_y if raw_y < 160 else raw_y - 0x100
            candidates = [
                _candidate_record(
                    candidate,
                    runtime_palette=runtime_palette,
                    screen_x=screen_x,
                    screen_y=screen_y,
                    affine=affine,
                )
                for candidate in source_candidates
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
            best_sources = [
                candidate
                for candidate in candidates
                if candidate["palette_difference_count"] == best_distance
            ]
            matches.append(
                {
                    "oam_index": oam_index,
                    "attr0": _hex16(attr0),
                    "attr1": _hex16(attr1),
                    "attr2": _hex16(attr2),
                    "affine": affine,
                    "double_size": bool(affine and attr0 & 0x0200),
                    "obj_mode": OBJ_MODES[(attr0 >> 10) & 3],
                    "mosaic": bool(attr0 & 0x1000),
                    "color_mode_bpp": color_mode_bpp,
                    "horizontal_flip": (
                        None if affine else bool(attr1 & 0x1000)
                    ),
                    "vertical_flip": (
                        None if affine else bool(attr1 & 0x2000)
                    ),
                    "screen_x_raw": raw_x,
                    "screen_y_raw": raw_y,
                    "screen_x": screen_x,
                    "screen_y": screen_y,
                    "width": width,
                    "height": height,
                    "tile_index": tile_index,
                    "priority": (attr2 >> 10) & 3,
                    "palette_bank": palette_bank,
                    "runtime_graphics_sha256": key[2],
                    "runtime_palette_sha256": _sha256_bytes(runtime_palette),
                    "source_candidate_count": len(candidates),
                    "best_palette_difference_count": best_distance,
                    "resolution": (
                        "unique_best_source"
                        if len(best_sources) == 1
                        else "ambiguous_best_source"
                    ),
                    "best_sources": best_sources,
                    "source_candidates": candidates,
                }
            )

    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha256_bytes(raw),
        "size": len(raw),
        "savestate_version_magic": f"0x{state.version_magic:08X}",
        "regions": {
            "io": {"size": len(io), "sha256": _sha256_bytes(io)},
            "pram": {"size": len(pram), "sha256": _sha256_bytes(pram)},
            "oam": {"size": len(oam), "sha256": _sha256_bytes(oam)},
            "vram": {"size": len(vram), "sha256": _sha256_bytes(vram)},
        },
        "display_registers": _display_registers(io),
        "obj_mapping": (
            "one_dimensional" if one_dimensional else "two_dimensional"
        ),
        "active_oam_object_count": active_count,
        "matched_oam_object_count": len(matches),
        "matches": matches,
    }


def build_bindings(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = root / ROM_PATH
    rom_hash = _sha256_path(rom_path)
    if rom_hash != ROM_SHA256:
        raise ValueError(f"base ROM SHA-256 mismatch: {rom_hash}")

    source_manifest, source_manifest_hash, source_index = _source_index(root)
    checkpoints = []
    parse_errors = []
    for path in _tracked_checkpoints(root):
        try:
            checkpoints.append(_scan_checkpoint(root, path, source_index))
        except (OSError, ValueError, struct.error) as error:
            parse_errors.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _sha256_path(path),
                    "error": str(error),
                }
            )

    matches = [
        match
        for checkpoint in checkpoints
        for match in checkpoint["matches"]
    ]
    best_distances = [
        match["best_palette_difference_count"] for match in matches
    ]
    active_count = sum(
        checkpoint["active_oam_object_count"] for checkpoint in checkpoints
    )
    summary = {
        "checkpoint_count": len(checkpoints) + len(parse_errors),
        "checkpoint_parse_error_count": len(parse_errors),
        "one_dimensional_obj_mapping_count": sum(
            checkpoint["obj_mapping"] == "one_dimensional"
            for checkpoint in checkpoints
        ),
        "active_oam_object_count": active_count,
        "matched_oam_object_count": len(matches),
        "unmatched_oam_object_count": active_count - len(matches),
        "checkpoints_with_matches": sum(
            bool(checkpoint["matches"]) for checkpoint in checkpoints
        ),
        "unique_best_source_count": sum(
            match["resolution"] == "unique_best_source"
            for match in matches
        ),
        "ambiguous_best_source_count": sum(
            match["resolution"] == "ambiguous_best_source"
            for match in matches
        ),
        "palette_exact_match_count": sum(
            distance == 0 for distance in best_distances
        ),
        "palette_difference_at_most_one_count": sum(
            distance <= 1 for distance in best_distances
        ),
    }
    all_scanned = (
        not parse_errors
        and summary["checkpoint_count"] == len(checkpoints)
    )
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": rom_path.stat().st_size,
            "sha256": rom_hash,
        },
        "source_artifact": {
            "path": SOURCE_ARTIFACT.as_posix(),
            "schema": source_manifest["schema"],
            "manifest_sha256": source_manifest_hash,
            "resource_count": source_manifest["summary"]["resource_count"],
            "frame_count": source_manifest["summary"]["frame_count"],
            "component_graphics_index_key_count": len(source_index),
        },
        "checkpoint_source": {
            "directory": CHECKPOINT_DIRECTORY.as_posix(),
            "selection": "git ls-files -- artifacts/runtime-checkpoints/*.ss9",
            "parse_errors": parse_errors,
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
            "all_tracked_checkpoints_scanned": all_scanned,
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


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_bindings(
    root: Path | str,
    output: Path | str,
) -> dict[str, Any]:
    result = build_bindings(root)
    _write_json_atomic(Path(output), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path of the deterministic bindings JSON to create.",
    )
    args = parser.parse_args()
    try:
        result = export_bindings(args.root, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"character-runtime-oam-bindings: {error}")
        return 1
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "output": str(args.output),
                "summary": result["summary"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
