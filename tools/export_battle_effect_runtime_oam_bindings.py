#!/usr/bin/env python3
"""Bind battle-effect source groups to OAM observed in persisted states."""

from __future__ import annotations

import argparse
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


SCHEMA = "battle-effect-runtime-oam-bindings-v1"
ROM_RELATIVE = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_RELATIVE = Path("artifacts/battle-effect-sprite-animations-v1")
CHECKPOINT_PARENT_RELATIVE = Path("artifacts/runtime-screen-composites-v1")
CHECKPOINT_DIRECTORY = Path("artifacts/runtime-checkpoints")
OBJ_VRAM_OFFSET = 0x10000
OBJ_PALETTE_OFFSET = 0x200
OAM_OBJECT_COUNT = 128
OAM_OBJECT_SIZE = 8
SIZES = {
    0: {0: (8, 8), 1: (16, 16), 2: (32, 32), 3: (64, 64)},
    1: {0: (16, 8), 1: (32, 8), 2: (32, 16), 3: (64, 32)},
    2: {0: (8, 16), 1: (8, 32), 2: (16, 32), 3: (32, 64)},
}
OBJ_MODES = {
    0: "normal",
    1: "semi_transparent",
    2: "obj_window",
    3: "prohibited",
}
SUPPLEMENTAL_SPECS = (
    {
        "kind": "accepted_natural_pixel_ab_baseline",
        "expected_group_id": 1,
        "artifact": Path("artifacts/battle-effect-group1-pixel-ab-v1"),
        "state": Path("raw/baseline/frame90.ss9"),
    },
    {
        "kind": "accepted_affine_runtime_golden",
        "expected_group_id": 2,
        "artifact": Path("artifacts/battle-effect-affine-runtime-v1"),
        "state": Path("raw/state-0154.ss9"),
    },
    {
        "kind": "accepted_natural_pixel_ab_baseline",
        "expected_group_id": 5,
        "artifact": Path("artifacts/battle-effect-group5-pixel-ab-v1"),
        "state": Path("raw/baseline/frame150.ss9"),
    },
    {
        "kind": "accepted_natural_pixel_ab_baseline",
        "expected_group_id": 11,
        "artifact": Path("artifacts/battle-effect-group11-pixel-ab-v1"),
        "state": Path("raw/baseline/frame106.ss9"),
    },
    {
        "kind": "accepted_natural_pixel_ab_baseline",
        "expected_group_id": 14,
        "artifact": Path("artifacts/battle-effect-group14-pixel-ab-v1"),
        "state": Path("raw/baseline/frame516.ss9"),
    },
)


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


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _read_object(path: Path) -> dict[str, Any]:
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
    paths = sorted(
        root / item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    )
    if not paths:
        raise ValueError("no tracked runtime checkpoints found")
    if any(not path.is_file() for path in paths):
        raise ValueError("a tracked runtime checkpoint is missing")
    return paths


def _source_components(
    root: Path,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    directory = root / SOURCE_RELATIVE
    manifest_path = directory / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if not isinstance(manifest, dict):
        raise ValueError("battle-effect source manifest is not an object")
    if manifest.get("schema") != "battle-effect-sprite-animations-v1":
        raise ValueError("battle-effect source schema mismatch")
    scope = manifest.get("scope", {})
    required_scope = (
        "all_nonzero_resource_groups_complete",
        "component_lists_complete",
        "component_local_geometry_complete",
        "source_tile_coverage_complete",
        "oam_shape_size_encoding_complete",
        "normal_oam_tile_palette_priority_formula_complete",
    )
    if any(not scope.get(name) for name in required_scope):
        raise ValueError("battle-effect source artifact is incomplete")

    resource_input = manifest.get("inputs", {}).get("resource_manifest", {})
    resource_manifest_relative = resource_input.get("path")
    if not isinstance(resource_manifest_relative, str):
        raise ValueError("battle-effect resource manifest path is missing")
    resource_manifest_path = root / resource_manifest_relative
    resource_manifest_raw = resource_manifest_path.read_bytes()
    if _digest(resource_manifest_raw) != resource_input.get("sha256"):
        raise ValueError("battle-effect resource manifest hash mismatch")
    resource_directory = resource_manifest_path.parent

    components: list[dict[str, Any]] = []
    frame_count = 0
    component_count = 0
    for group in manifest.get("groups", []):
        group_id = group["group_id"]
        graphics_meta = group["graphics"]
        palette_meta = group["palette"]
        graphics_path = resource_directory / graphics_meta["output_bin"]
        palette_path = resource_directory / palette_meta["output_bin"]
        graphics = graphics_path.read_bytes()
        palette = palette_path.read_bytes()
        if len(graphics) != graphics_meta["decompressed_size"]:
            raise ValueError(f"group {group_id} graphics size mismatch")
        if _digest(graphics) != graphics_meta["decompressed_sha256"]:
            raise ValueError(f"group {group_id} graphics hash mismatch")
        if len(palette) != palette_meta["decompressed_size"] or len(palette) != 32:
            raise ValueError(f"group {group_id} palette size mismatch")
        if _digest(palette) != palette_meta["decompressed_sha256"]:
            raise ValueError(f"group {group_id} palette hash mismatch")
        for frame in group["frames"]:
            frame_count += 1
            for component in frame["components"]:
                component_count += 1
                tile_index = component["tile_index"]
                byte_count = component["width"] * component["height"] // 2
                if tile_index < 0 or tile_index * 32 + byte_count > len(graphics):
                    raise ValueError(
                        f"group {group_id} frame {frame['frame_id']} component exceeds graphics"
                    )
                components.append(
                    {
                        "group_id": group_id,
                        "sequence_ids": group["sequence_ids"],
                        "frame_id": frame["frame_id"],
                        "component_index": component["component_index"],
                        "component_tile_index": tile_index,
                        "component_x": component["x"],
                        "component_y": component["y"],
                        "width": component["width"],
                        "height": component["height"],
                        "horizontal_flip": component["horizontal_flip"],
                        "vertical_flip": component["vertical_flip"],
                        "scale_x": component["scale_x"],
                        "scale_y": component["scale_y"],
                        "angle_offset": component["angle_offset"],
                        "affine_mode": component["affine_mode"],
                        "graphics_size": len(graphics),
                        "graphics_sha256": _digest(graphics),
                        "palette_sha256": _digest(palette),
                        "_graphics": graphics,
                        "_palette": palette,
                    }
                )
    if len(manifest.get("groups", [])) != manifest.get("group_count"):
        raise ValueError("battle-effect group count mismatch")
    if frame_count != manifest.get("frame_definition_count"):
        raise ValueError("battle-effect frame count mismatch")
    if component_count != manifest.get("component_count"):
        raise ValueError("battle-effect component count mismatch")
    return manifest, _digest(manifest_raw), components


def _palette_delta(source: bytes, runtime: bytes) -> tuple[int, list[dict[str, Any]]]:
    source_values = struct.unpack("<16H", source)
    runtime_values = struct.unpack("<16H", runtime)
    differences = [
        {
            "color_index": index,
            "source_bgr555": _h16(source_value),
            "runtime_bgr555": _h16(runtime_value),
        }
        for index, (source_value, runtime_value) in enumerate(
            zip(source_values, runtime_values)
        )
        if source_value != runtime_value
    ]
    return len(differences), differences


def _public_candidate(
    source: dict[str, Any],
    *,
    load_tile_base: int,
    runtime_palette: bytes,
) -> dict[str, Any]:
    difference_count, differences = _palette_delta(
        source["_palette"], runtime_palette
    )
    result = {
        key: value for key, value in source.items() if not key.startswith("_")
    }
    result["obj_vram_load_tile_base"] = load_tile_base
    result["obj_vram_load_address"] = _address(
        0x06010000 + load_tile_base * 32
    )
    result["palette_difference_count"] = difference_count
    result["palette_differences"] = differences
    return result


def _match_oam_entry(
    *,
    oam_index: int,
    attr0: int,
    attr1: int,
    attr2: int,
    vram: bytes,
    pram: bytes,
    source_components: list[dict[str, Any]],
) -> dict[str, Any] | None:
    shape = (attr0 >> 14) & 3
    size = (attr1 >> 14) & 3
    if shape not in SIZES or attr0 & 0x2000:
        return None
    width, height = SIZES[shape][size]
    tile_index = attr2 & 0x03FF
    palette_bank = (attr2 >> 12) & 0xF
    runtime_palette = pram[
        OBJ_PALETTE_OFFSET + palette_bank * 32 :
        OBJ_PALETTE_OFFSET + (palette_bank + 1) * 32
    ]
    candidates = []
    for source in source_components:
        if source["width"] != width or source["height"] != height:
            continue
        load_tile_base = tile_index - source["component_tile_index"]
        if load_tile_base < 0:
            continue
        start = OBJ_VRAM_OFFSET + load_tile_base * 32
        end = start + source["graphics_size"]
        if end > len(vram):
            continue
        if _digest(vram[start:end]) != source["graphics_sha256"]:
            continue
        candidates.append(
            _public_candidate(
                source,
                load_tile_base=load_tile_base,
                runtime_palette=runtime_palette,
            )
        )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item["palette_difference_count"],
            item["group_id"],
            item["frame_id"],
            item["component_index"],
            item["obj_vram_load_tile_base"],
        )
    )
    best_distance = candidates[0]["palette_difference_count"]
    best = [
        candidate
        for candidate in candidates
        if candidate["palette_difference_count"] == best_distance
    ]
    best_group_ids = sorted({candidate["group_id"] for candidate in best})
    affine = bool(attr0 & 0x0100)
    raw_x = attr1 & 0x01FF
    raw_y = attr0 & 0x00FF
    screen_x = raw_x if raw_x < 0x100 else raw_x - 0x200
    screen_y = raw_y if raw_y < 160 else raw_y - 0x100
    return {
        "oam_index": oam_index,
        "attr0": _h16(attr0),
        "attr1": _h16(attr1),
        "attr2": _h16(attr2),
        "affine": affine,
        "double_size": bool(affine and attr0 & 0x0200),
        "obj_mode": OBJ_MODES[(attr0 >> 10) & 3],
        "mosaic": bool(attr0 & 0x1000),
        "color_mode_bpp": 4,
        "horizontal_flip": None if affine else bool(attr1 & 0x1000),
        "vertical_flip": None if affine else bool(attr1 & 0x2000),
        "screen_x_raw": raw_x,
        "screen_y_raw": raw_y,
        "screen_x": screen_x,
        "screen_y": screen_y,
        "width": width,
        "height": height,
        "tile_index": tile_index,
        "priority": (attr2 >> 10) & 3,
        "palette_bank": palette_bank,
        "runtime_palette_sha256": _digest(runtime_palette),
        "source_candidate_count": len(candidates),
        "best_palette_difference_count": best_distance,
        "best_group_ids": best_group_ids,
        "group_resolution": (
            "unique_best_group"
            if len(best_group_ids) == 1
            else "ambiguous_best_group"
        ),
        "frame_component_resolution": (
            "unique_best_frame_component"
            if len(best) == 1
            else "ambiguous_best_frame_component"
        ),
        "best_candidates": best,
        "source_candidates": candidates,
    }


def _scan_state(
    root: Path,
    path: Path,
    source_components: list[dict[str, Any]],
    *,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    container = path.read_bytes()
    state = load_gba_state(path)
    io = state.read_memory(0x04000000, 0x400)
    pram = state.read_memory(0x05000000, 0x400)
    oam = state.read_memory(0x07000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    hashes = {
        "io": _digest(io),
        "pram": _digest(pram),
        "hardware_oam": _digest(oam),
        "vram": _digest(vram),
    }
    if expected is not None:
        if _digest(container) != expected["checkpoint_sha256"]:
            raise ValueError(f"checkpoint hash differs from parent: {path}")
        for name, digest in hashes.items():
            if digest != expected["domains"][name]["sha256"]:
                raise ValueError(f"{name} differs from checkpoint parent: {path}")

    dispcnt = struct.unpack_from("<H", io, 0)[0]
    mapping_1d = bool(dispcnt & 0x40)
    active_count = 0
    matches = []
    if mapping_1d:
        for oam_index in range(OAM_OBJECT_COUNT):
            attr0, attr1, attr2 = struct.unpack_from(
                "<HHH", oam, oam_index * OAM_OBJECT_SIZE
            )
            affine = bool(attr0 & 0x0100)
            if not affine and attr0 & 0x0200:
                continue
            active_count += 1
            match = _match_oam_entry(
                oam_index=oam_index,
                attr0=attr0,
                attr1=attr1,
                attr2=attr2,
                vram=vram,
                pram=pram,
                source_components=source_components,
            )
            if match is not None:
                matches.append(match)
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _digest(container),
        "size": len(container),
        "savestate_version_magic": f"0x{state.version_magic:08X}",
        "obj_mapping": "one_dimensional" if mapping_1d else "two_dimensional",
        "regions": {
            name: {"sha256": digest}
            for name, digest in hashes.items()
        },
        "active_oam_object_count": active_count,
        "matched_oam_object_count": len(matches),
        "matches": matches,
    }


def _checkpoint_parent(
    root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    list[str],
]:
    directory = root / CHECKPOINT_PARENT_RELATIVE
    manifest_path = directory / "manifest.json"
    payload_path = directory / "runtime-screen-composites.json"
    manifest_raw = manifest_path.read_bytes()
    payload_raw = payload_path.read_bytes()
    manifest = json.loads(manifest_raw)
    payload = json.loads(payload_raw)
    if manifest.get("schema") != "git-artifact-promotion-v1":
        raise ValueError("checkpoint parent promotion schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("checkpoint parent is not accepted")
    if manifest.get("artifact_schema") != "runtime-screen-composites-v1":
        raise ValueError("checkpoint parent artifact schema mismatch")
    if manifest.get("files", {}).get("runtime-screen-composites.json") != _digest(
        payload_raw
    ):
        raise ValueError("checkpoint parent payload hash mismatch")
    if payload.get("schema") != "runtime-screen-composites-v1":
        raise ValueError("checkpoint parent payload schema mismatch")
    rows = payload.get("checkpoints", [])
    if len(rows) != 91 or payload.get("summary", {}).get("checkpoint_count") != 91:
        raise ValueError("checkpoint parent denominator is not 91")
    by_path = {row["path"]: row for row in rows}
    if len(by_path) != len(rows):
        raise ValueError("checkpoint parent contains duplicate paths")
    tracked = [path.relative_to(root).as_posix() for path in _tracked_checkpoints(root)]
    parent_paths = sorted(by_path)
    missing_parent_paths = sorted(set(parent_paths) - set(tracked))
    if missing_parent_paths:
        raise ValueError("an accepted parent checkpoint is no longer tracked")
    post_parent_extensions = sorted(set(tracked) - set(parent_paths))
    return (
        {
            "path": CHECKPOINT_PARENT_RELATIVE.as_posix(),
            "schema": payload["schema"],
            "manifest_sha256": _digest(manifest_raw),
            "payload_sha256": _digest(payload_raw),
            "checkpoint_count": len(rows),
        },
        payload,
        by_path,
        post_parent_extensions,
    )


def _supplemental_parent(
    root: Path,
    spec: dict[str, Any],
    resource_manifest_input: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    directory = root / spec["artifact"]
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    state_relative = spec["state"].as_posix()
    state_path = directory / spec["state"]
    if not state_path.is_file():
        raise ValueError(f"supplemental state is missing: {state_path}")
    if spec["kind"] == "accepted_natural_pixel_ab_baseline":
        if manifest.get("schema") != "git-artifact-promotion-v1":
            raise ValueError("pixel A/B supplemental promotion schema mismatch")
        if manifest.get("artifact_status") != "accepted":
            raise ValueError("pixel A/B supplemental is not accepted")
        if manifest.get("base_rom_sha256") != ROM_SHA256:
            raise ValueError("pixel A/B supplemental ROM hash mismatch")
        if manifest.get("source_catalog") != resource_manifest_input.get("path"):
            raise ValueError("pixel A/B supplemental source catalog path mismatch")
        if manifest.get("source_catalog_sha256") != resource_manifest_input.get(
            "sha256"
        ):
            raise ValueError("pixel A/B supplemental source catalog hash mismatch")
        expected_hash = manifest.get("files", {}).get(state_relative)
    else:
        if manifest.get("schema") != "battle-effect-affine-runtime-v1":
            raise ValueError("affine supplemental schema mismatch")
        if manifest.get("rom_sha256") != ROM_SHA256:
            raise ValueError("affine supplemental ROM hash mismatch")
        binding = manifest.get("resource_binding", {})
        if binding.get("group_id") != spec["expected_group_id"]:
            raise ValueError("affine supplemental group identity mismatch")
        capture = manifest.get("capture", {})
        if capture.get("savestate") != state_relative:
            raise ValueError("affine supplemental state path mismatch")
        expected_hash = capture.get("savestate_sha256")
    if expected_hash != _file_digest(state_path):
        raise ValueError("supplemental state hash mismatch")
    return state_path, {
        "kind": spec["kind"],
        "artifact": spec["artifact"].as_posix(),
        "manifest_sha256": _digest(manifest_raw),
        "expected_group_id": spec["expected_group_id"],
    }


def _observed_group_ids(states: list[dict[str, Any]]) -> list[int]:
    return sorted(
        {
            group_id
            for state in states
            for match in state.get("matches", [])
            if match["group_resolution"] == "unique_best_group"
            for group_id in match["best_group_ids"]
        }
    )


def build_bindings(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = root / ROM_RELATIVE
    rom_hash = _file_digest(rom_path)
    if rom_hash != ROM_SHA256:
        raise ValueError(f"base ROM SHA-256 mismatch: {rom_hash}")
    source_manifest, source_hash, source_components = _source_components(root)
    (
        checkpoint_parent,
        _,
        parent_rows,
        post_parent_extensions,
    ) = _checkpoint_parent(root)

    tracked_states = []
    tracked_errors = []
    for relative, parent_row in sorted(parent_rows.items()):
        path = root / relative
        try:
            tracked_states.append(
                _scan_state(
                    root,
                    path,
                    source_components,
                    expected=parent_row,
                )
            )
        except (OSError, ValueError, struct.error) as error:
            tracked_errors.append(
                {
                    "path": relative,
                    "sha256": _file_digest(path),
                    "error": str(error),
                }
            )
    for relative in post_parent_extensions:
        path = root / relative
        try:
            tracked_states.append(
                _scan_state(root, path, source_components)
            )
        except (OSError, ValueError, struct.error) as error:
            tracked_errors.append(
                {
                    "path": relative,
                    "sha256": _file_digest(path),
                    "error": str(error),
                }
            )
    tracked_states.sort(key=lambda item: item["path"])

    supplemental_states = []
    for spec in SUPPLEMENTAL_SPECS:
        state_path, parent = _supplemental_parent(
            root,
            spec,
            source_manifest["inputs"]["resource_manifest"],
        )
        state = _scan_state(root, state_path, source_components)
        state["supplemental_parent"] = parent
        observed = {
            group_id
            for match in state["matches"]
            for group_id in match["best_group_ids"]
        }
        if spec["expected_group_id"] not in observed:
            raise ValueError(
                "supplemental state does not independently bind expected group "
                f"{spec['expected_group_id']}: {state_path}"
            )
        supplemental_states.append(state)

    tracked_matches = [
        match for state in tracked_states for match in state["matches"]
    ]
    supplemental_matches = [
        match for state in supplemental_states for match in state["matches"]
    ]
    tracked_groups = _observed_group_ids(tracked_states)
    supplemental_groups = _observed_group_ids(supplemental_states)
    all_groups = sorted(set(tracked_groups) | set(supplemental_groups))
    summary = {
        "tracked_checkpoint_count": len(tracked_states) + len(tracked_errors),
        "tracked_checkpoint_parse_error_count": len(tracked_errors),
        "tracked_active_oam_object_count": sum(
            state["active_oam_object_count"] for state in tracked_states
        ),
        "tracked_matched_oam_object_count": len(tracked_matches),
        "tracked_checkpoints_with_matches": sum(
            bool(state["matches"]) for state in tracked_states
        ),
        "tracked_observed_group_ids": tracked_groups,
        "supplemental_state_count": len(supplemental_states),
        "supplemental_matched_oam_object_count": len(supplemental_matches),
        "supplemental_observed_group_ids": supplemental_groups,
        "all_persisted_observed_group_ids": all_groups,
        "all_persisted_observed_group_count": len(all_groups),
    }
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_RELATIVE.as_posix(),
            "size": rom_path.stat().st_size,
            "sha256": rom_hash,
        },
        "source_artifact": {
            "path": SOURCE_RELATIVE.as_posix(),
            "schema": source_manifest["schema"],
            "manifest_sha256": source_hash,
            "group_count": source_manifest["group_count"],
            "frame_count": source_manifest["frame_definition_count"],
            "component_count": source_manifest["component_count"],
            "source_component_record_count": len(source_components),
        },
        "checkpoint_parent": checkpoint_parent,
        "checkpoint_source": {
            "selection": (
                "accepted runtime-screen-composites-v1 denominator plus later "
                "git-tracked checkpoint extensions"
            ),
            "post_parent_extensions": post_parent_extensions,
            "parse_errors": tracked_errors,
        },
        "binding_contract": {
            "group_graphics_identity": (
                "infer OBJ load tile base as attr2.tile_index minus source "
                "component tile index, then require exact SHA-256 of the "
                "complete source group graphics at that OBJ VRAM base"
            ),
            "component_candidate": (
                "require exact OAM shape/size and retain every frame/component "
                "whose full-group identity matches"
            ),
            "palette_ranking": (
                "rank exact-graphics candidates by the count of unequal BGR555 "
                "colors in the OAM-selected runtime palette bank"
            ),
            "tracked_vs_supplemental": (
                "the accepted 91-checkpoint denominator and five pre-existing "
                "accepted runtime evidence states are counted separately"
            ),
        },
        "summary": summary,
        "scope": {
            "all_accepted_parent_checkpoints_scanned": (
                not tracked_errors
                and len(tracked_states) == checkpoint_parent["checkpoint_count"]
                + len(post_parent_extensions)
            ),
            "complete_group_graphics_bound_to_active_oam": bool(
                tracked_matches or supplemental_matches
            ),
            "frame_component_candidates_recorded": bool(
                tracked_matches or supplemental_matches
            ),
            "runtime_palette_differences_recorded": bool(
                tracked_matches or supplemental_matches
            ),
            "supplemental_states_separate_from_tracked_denominator": True,
            "natural_task_and_selector_trace_complete": False,
            "all_effect_groups_runtime_observed": len(all_groups) == 18,
            "all_group_frames_runtime_observed": False,
            "cross_frame_timing_complete": False,
            "blend_window_audio_coupling_complete": False,
            "physical_gba_verified": False,
        },
        "tracked_checkpoints": tracked_states,
        "supplemental_states": supplemental_states,
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export_bindings(args.root, args.output)
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        print(f"battle-effect-runtime-oam-bindings: {error}")
        return 1
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
