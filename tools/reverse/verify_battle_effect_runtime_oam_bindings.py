#!/usr/bin/env python3
"""Independently reconstruct persisted battle-effect/OAM bindings."""

from __future__ import annotations

import argparse
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


SCHEMA = "battle-effect-runtime-oam-bindings-v1"
ROM_RELATIVE = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_RELATIVE = Path("artifacts/battle-effect-sprite-animations-v1")
CHECKPOINT_PARENT_RELATIVE = Path("artifacts/runtime-screen-composites-v1")
CHECKPOINT_DIRECTORY = Path("artifacts/runtime-checkpoints")
MODE_NAMES = {
    0: "normal",
    1: "semi_transparent",
    2: "obj_window",
    3: "prohibited",
}
SUPPLEMENTAL = (
    (
        "accepted_natural_pixel_ab_baseline",
        1,
        Path("artifacts/battle-effect-group1-pixel-ab-v1"),
        Path("raw/baseline/frame90.ss9"),
    ),
    (
        "accepted_affine_runtime_golden",
        2,
        Path("artifacts/battle-effect-affine-runtime-v1"),
        Path("raw/state-0154.ss9"),
    ),
    (
        "accepted_natural_pixel_ab_baseline",
        5,
        Path("artifacts/battle-effect-group5-pixel-ab-v1"),
        Path("raw/baseline/frame150.ss9"),
    ),
    (
        "accepted_natural_pixel_ab_baseline",
        11,
        Path("artifacts/battle-effect-group11-pixel-ab-v1"),
        Path("raw/baseline/frame106.ss9"),
    ),
    (
        "accepted_natural_pixel_ab_baseline",
        14,
        Path("artifacts/battle-effect-group14-pixel-ab-v1"),
        Path("raw/baseline/frame516.ss9"),
    ),
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


def _tracked_paths(root: Path) -> list[Path]:
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
        raise ValueError("cannot enumerate tracked checkpoints")
    result = sorted(
        root / item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    )
    if not result or any(not path.is_file() for path in result):
        raise ValueError("tracked checkpoint set is invalid")
    return result


def _rebuild_sources(
    root: Path,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    directory = root / SOURCE_RELATIVE
    raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise ValueError("source manifest is not an object")
    if manifest.get("schema") != "battle-effect-sprite-animations-v1":
        raise ValueError("source schema mismatch")
    required_scope = {
        "all_nonzero_resource_groups_complete": True,
        "component_lists_complete": True,
        "component_local_geometry_complete": True,
        "source_tile_coverage_complete": True,
        "oam_shape_size_encoding_complete": True,
        "normal_oam_tile_palette_priority_formula_complete": True,
    }
    if any(manifest.get("scope", {}).get(key) != value for key, value in required_scope.items()):
        raise ValueError("source scope is insufficient")
    resource_input = manifest["inputs"]["resource_manifest"]
    resource_manifest_path = root / resource_input["path"]
    resource_raw = resource_manifest_path.read_bytes()
    if _digest(resource_raw) != resource_input["sha256"]:
        raise ValueError("resource parent hash mismatch")
    resource_directory = resource_manifest_path.parent

    sources = []
    frames = 0
    components = 0
    for group in manifest["groups"]:
        group_id = group["group_id"]
        graphics_meta = group["graphics"]
        palette_meta = group["palette"]
        graphics = (resource_directory / graphics_meta["output_bin"]).read_bytes()
        palette = (resource_directory / palette_meta["output_bin"]).read_bytes()
        if len(graphics) != graphics_meta["decompressed_size"]:
            raise ValueError("source graphics size mismatch")
        if _digest(graphics) != graphics_meta["decompressed_sha256"]:
            raise ValueError("source graphics hash mismatch")
        if len(palette) != 32 or _digest(palette) != palette_meta["decompressed_sha256"]:
            raise ValueError("source palette mismatch")
        for frame in group["frames"]:
            frames += 1
            for component in frame["components"]:
                components += 1
                tile_index = component["tile_index"]
                byte_count = component["width"] * component["height"] // 2
                if tile_index < 0 or tile_index * 32 + byte_count > len(graphics):
                    raise ValueError("source component exceeds group graphics")
                sources.append(
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
    if len(manifest["groups"]) != manifest["group_count"]:
        raise ValueError("source group count mismatch")
    if frames != manifest["frame_definition_count"]:
        raise ValueError("source frame count mismatch")
    if components != manifest["component_count"] or components != len(sources):
        raise ValueError("source component count mismatch")
    return manifest, _digest(raw), sources


def _palette_result(source: bytes, runtime: bytes) -> tuple[int, list[dict[str, Any]]]:
    left = struct.unpack("<16H", source)
    right = struct.unpack("<16H", runtime)
    rows = []
    for index, (source_value, runtime_value) in enumerate(zip(left, right)):
        if source_value != runtime_value:
            rows.append(
                {
                    "color_index": index,
                    "source_bgr555": _h16(source_value),
                    "runtime_bgr555": _h16(runtime_value),
                }
            )
    return len(rows), rows


def _candidate(
    source: dict[str, Any],
    base: int,
    runtime_palette: bytes,
) -> dict[str, Any]:
    count, differences = _palette_result(source["_palette"], runtime_palette)
    row = {key: value for key, value in source.items() if not key.startswith("_")}
    row["obj_vram_load_tile_base"] = base
    row["obj_vram_load_address"] = _address(0x06010000 + base * 32)
    row["palette_difference_count"] = count
    row["palette_differences"] = differences
    return row


def _match_object(
    obj: dict[str, Any],
    vram: bytes,
    pram: bytes,
    sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if obj["colors"] != 16:
        return None
    width, height = obj["dimensions"]
    tile_index = obj["tile_index"]
    palette_bank = obj["palette_bank"]
    if palette_bank is None:
        raise ValueError("4bpp object has no palette bank")
    runtime_palette = pram[0x200 + palette_bank * 32 : 0x220 + palette_bank * 32]
    candidates = []
    for source in sources:
        if (source["width"], source["height"]) != (width, height):
            continue
        base = tile_index - source["component_tile_index"]
        if base < 0:
            continue
        start = 0x10000 + base * 32
        end = start + source["graphics_size"]
        if end > len(vram):
            continue
        if vram[start:end] != source["_graphics"]:
            continue
        candidates.append(_candidate(source, base, runtime_palette))
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
    best = [item for item in candidates if item["palette_difference_count"] == best_distance]
    groups = sorted({item["group_id"] for item in best})
    raw = obj["raw"]
    attr0 = int(raw[0:4], 16)
    attr1 = int(raw[4:8], 16)
    attr2 = int(raw[8:12], 16)
    return {
        "oam_index": obj["index"],
        "attr0": _h16(attr0),
        "attr1": _h16(attr1),
        "attr2": _h16(attr2),
        "affine": obj["affine"],
        "double_size": obj["double_size"],
        "obj_mode": MODE_NAMES[obj["object_mode"]],
        "mosaic": obj["mosaic"],
        "color_mode_bpp": 4,
        "horizontal_flip": None if obj["affine"] else obj["horizontal_flip"],
        "vertical_flip": None if obj["affine"] else obj["vertical_flip"],
        "screen_x_raw": obj["position"]["raw_x"],
        "screen_y_raw": obj["position"]["raw_y"],
        "screen_x": obj["position"]["x"],
        "screen_y": obj["position"]["y"],
        "width": width,
        "height": height,
        "tile_index": tile_index,
        "priority": obj["priority"],
        "palette_bank": palette_bank,
        "runtime_palette_sha256": _digest(runtime_palette),
        "source_candidate_count": len(candidates),
        "best_palette_difference_count": best_distance,
        "best_group_ids": groups,
        "group_resolution": "unique_best_group" if len(groups) == 1 else "ambiguous_best_group",
        "frame_component_resolution": (
            "unique_best_frame_component"
            if len(best) == 1
            else "ambiguous_best_frame_component"
        ),
        "best_candidates": best,
        "source_candidates": candidates,
    }


def _rebuild_state(
    root: Path,
    path: Path,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = path.read_bytes()
    state = load_gba_state(path)
    io = state.read_memory(0x04000000, 0x400)
    pram = state.read_memory(0x05000000, 0x400)
    oam = state.read_memory(0x07000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    decoded = decode_gpu(io, oam)
    mapping_1d = decoded["display"]["obj_character_mapping"] == "1d"
    matches = []
    if mapping_1d:
        for obj in decoded["objects"]:
            match = _match_object(obj, vram, pram, sources)
            if match is not None:
                matches.append(match)
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _digest(raw),
        "size": len(raw),
        "savestate_version_magic": f"0x{state.version_magic:08X}",
        "obj_mapping": "one_dimensional" if mapping_1d else "two_dimensional",
        "regions": {
            "io": {"sha256": _digest(io)},
            "pram": {"sha256": _digest(pram)},
            "hardware_oam": {"sha256": _digest(oam)},
            "vram": {"sha256": _digest(vram)},
        },
        "active_oam_object_count": len(decoded["objects"]),
        "matched_oam_object_count": len(matches),
        "matches": matches,
    }


def _parent_metadata(root: Path) -> tuple[dict[str, Any], set[str]]:
    directory = root / CHECKPOINT_PARENT_RELATIVE
    manifest_raw = (directory / "manifest.json").read_bytes()
    payload_raw = (directory / "runtime-screen-composites.json").read_bytes()
    manifest = json.loads(manifest_raw)
    payload = json.loads(payload_raw)
    if manifest.get("schema") != "git-artifact-promotion-v1":
        raise ValueError("checkpoint parent promotion schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("checkpoint parent is not accepted")
    if manifest.get("artifact_schema") != "runtime-screen-composites-v1":
        raise ValueError("checkpoint parent schema mismatch")
    if manifest.get("files", {}).get("runtime-screen-composites.json") != _digest(payload_raw):
        raise ValueError("checkpoint parent payload hash mismatch")
    rows = payload.get("checkpoints", [])
    if payload.get("schema") != "runtime-screen-composites-v1" or len(rows) != 91:
        raise ValueError("checkpoint parent denominator mismatch")
    return (
        {
            "path": CHECKPOINT_PARENT_RELATIVE.as_posix(),
            "schema": payload["schema"],
            "manifest_sha256": _digest(manifest_raw),
            "payload_sha256": _digest(payload_raw),
            "checkpoint_count": len(rows),
        },
        {row["path"] for row in rows},
    )


def _supplemental_parent(
    root: Path,
    kind: str,
    group_id: int,
    artifact: Path,
    state_relative: Path,
    resource_input: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    directory = root / artifact
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    state_path = directory / state_relative
    state_name = state_relative.as_posix()
    if kind == "accepted_natural_pixel_ab_baseline":
        if manifest.get("schema") != "git-artifact-promotion-v1":
            raise ValueError("supplemental promotion schema mismatch")
        if manifest.get("artifact_status") != "accepted":
            raise ValueError("supplemental is not accepted")
        if manifest.get("base_rom_sha256") != ROM_SHA256:
            raise ValueError("supplemental ROM mismatch")
        if manifest.get("source_catalog") != resource_input["path"]:
            raise ValueError("supplemental resource parent path mismatch")
        if manifest.get("source_catalog_sha256") != resource_input["sha256"]:
            raise ValueError("supplemental resource parent hash mismatch")
        expected_hash = manifest.get("files", {}).get(state_name)
    else:
        if manifest.get("schema") != "battle-effect-affine-runtime-v1":
            raise ValueError("affine supplemental schema mismatch")
        if manifest.get("rom_sha256") != ROM_SHA256:
            raise ValueError("affine supplemental ROM mismatch")
        if manifest.get("resource_binding", {}).get("group_id") != group_id:
            raise ValueError("affine supplemental group mismatch")
        if manifest.get("capture", {}).get("savestate") != state_name:
            raise ValueError("affine supplemental path mismatch")
        expected_hash = manifest.get("capture", {}).get("savestate_sha256")
    if expected_hash != _file_digest(state_path):
        raise ValueError("supplemental state hash mismatch")
    return state_path, {
        "kind": kind,
        "artifact": artifact.as_posix(),
        "manifest_sha256": _digest(manifest_raw),
        "expected_group_id": group_id,
    }


def _group_ids(states: list[dict[str, Any]]) -> list[int]:
    return sorted(
        {
            group_id
            for state in states
            for match in state["matches"]
            if match["group_resolution"] == "unique_best_group"
            for group_id in match["best_group_ids"]
        }
    )


def _reconstruct(root: Path) -> dict[str, Any]:
    rom_path = root / ROM_RELATIVE
    rom_hash = _file_digest(rom_path)
    if rom_hash != ROM_SHA256:
        raise ValueError("base ROM hash mismatch")
    source_manifest, source_hash, sources = _rebuild_sources(root)
    checkpoint_parent, parent_paths = _parent_metadata(root)
    tracked_paths = _tracked_paths(root)
    tracked_names = {path.relative_to(root).as_posix() for path in tracked_paths}
    if not parent_paths.issubset(tracked_names):
        raise ValueError("accepted parent checkpoint is no longer tracked")
    extensions = sorted(tracked_names - parent_paths)
    tracked_states = [_rebuild_state(root, path, sources) for path in tracked_paths]

    supplemental_states = []
    resource_input = source_manifest["inputs"]["resource_manifest"]
    for kind, group_id, artifact, state_relative in SUPPLEMENTAL:
        state_path, parent = _supplemental_parent(
            root,
            kind,
            group_id,
            artifact,
            state_relative,
            resource_input,
        )
        state = _rebuild_state(root, state_path, sources)
        state["supplemental_parent"] = parent
        observed = {
            candidate_group
            for match in state["matches"]
            for candidate_group in match["best_group_ids"]
        }
        if group_id not in observed:
            raise ValueError("supplemental state lacks expected group")
        supplemental_states.append(state)

    tracked_matches = [match for state in tracked_states for match in state["matches"]]
    supplemental_matches = [match for state in supplemental_states for match in state["matches"]]
    tracked_groups = _group_ids(tracked_states)
    supplemental_groups = _group_ids(supplemental_states)
    all_groups = sorted(set(tracked_groups) | set(supplemental_groups))
    summary = {
        "tracked_checkpoint_count": len(tracked_states),
        "tracked_checkpoint_parse_error_count": 0,
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
            "source_component_record_count": len(sources),
        },
        "checkpoint_parent": checkpoint_parent,
        "checkpoint_source": {
            "selection": (
                "accepted runtime-screen-composites-v1 denominator plus later "
                "git-tracked checkpoint extensions"
            ),
            "post_parent_extensions": extensions,
            "parse_errors": [],
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
            "all_accepted_parent_checkpoints_scanned": True,
            "complete_group_graphics_bound_to_active_oam": bool(
                tracked_matches or supplemental_matches
            ),
            "frame_component_candidates_recorded": bool(tracked_matches or supplemental_matches),
            "runtime_palette_differences_recorded": bool(tracked_matches or supplemental_matches),
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


def verify_bindings(
    root: Path | str,
    bindings_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    errors = []
    actual: dict[str, Any] = {}
    try:
        value = json.loads(Path(bindings_path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("bindings JSON must contain an object")
        actual = value
        expected = _reconstruct(root)
        if actual != expected:
            errors.append("bindings differ from independent reconstruction")
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        errors.append(str(error))
    summary = actual.get("summary", {}) if isinstance(actual, dict) else {}
    return {
        "verified": not errors,
        "errors": errors,
        "tracked_checkpoints": summary.get("tracked_checkpoint_count", 0) if not errors else 0,
        "tracked_matches": summary.get("tracked_matched_oam_object_count", 0) if not errors else 0,
        "supplemental_states": summary.get("supplemental_state_count", 0) if not errors else 0,
        "supplemental_matches": (
            summary.get("supplemental_matched_oam_object_count", 0)
            if not errors
            else 0
        ),
        "observed_group_ids": (
            summary.get("all_persisted_observed_group_ids", [])
            if not errors
            else []
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bindings", type=Path, required=True)
    args = parser.parse_args()
    report = verify_bindings(args.root, args.bindings)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
