#!/usr/bin/env python3
"""Independently verify live-unit/grid observations for character OAM."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.verify_character_runtime_oam_bindings import (
        verify_bindings as verify_parent,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state
    from verify_character_runtime_oam_bindings import (
        verify_bindings as verify_parent,
    )


SCHEMA = "character-runtime-unit-oam-bindings-v1"
ROM_RELATIVE = Path("rom/base.gba")
ROM_DIGEST = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_DIRECTORY = Path("artifacts/character-runtime-oam-bindings-v1")
PARENT_RELATIVE = PARENT_DIRECTORY / "bindings.json"
PARENT_PROMOTION_RELATIVE = PARENT_DIRECTORY / "manifest.json"
PARENT_SCHEMA = "character-runtime-oam-bindings-v1"
BATTLE_RECORD_BASE = 0x020240C0
BATTLE_RECORD_STRIDE = 468
BATTLE_RECORD_COUNT = 13
BATTLE_REGION_SIZE = BATTLE_RECORD_STRIDE * BATTLE_RECORD_COUNT
UNIT_FIRST = 1
UNIT_LAST = 12
CHARACTER_FIELD = 0
GRID_X_FIELD = 0xC4
GRID_Y_FIELD = 0xC5


def _bytes_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _path_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object_hash(value: Any) -> str:
    return _bytes_hash(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _validated_parent(
    root: Path,
) -> tuple[dict[str, Any], str, str]:
    parent_path = root / PARENT_RELATIVE
    parent_report = verify_parent(root, parent_path)
    if not parent_report["verified"]:
        raise ValueError(
            "parent OAM evidence verification failed: "
            + "; ".join(parent_report["errors"])
        )
    parent = _json_object(parent_path)
    if parent.get("schema") != PARENT_SCHEMA:
        raise ValueError("parent OAM schema mismatch")
    if parent.get("rom", {}).get("sha256") != ROM_DIGEST:
        raise ValueError("parent OAM ROM mismatch")
    promotion_path = root / PARENT_PROMOTION_RELATIVE
    promotion = _json_object(promotion_path)
    parent_hash = _path_hash(parent_path)
    if promotion != {
        **promotion,
        "schema": "git-artifact-promotion-v1",
        "artifact_status": "accepted",
        "artifact_schema": PARENT_SCHEMA,
    }:
        raise ValueError("parent promotion identity mismatch")
    if promotion.get("files", {}).get("bindings.json") != parent_hash:
        raise ValueError("parent promotion payload hash mismatch")
    return parent, parent_hash, _path_hash(promotion_path)


def _decode_live_records(region: bytes) -> list[dict[str, Any]]:
    if len(region) != BATTLE_REGION_SIZE:
        raise ValueError("battle unit region length mismatch")
    records = []
    for slot in range(UNIT_FIRST, UNIT_LAST + 1):
        offset = slot * BATTLE_RECORD_STRIDE
        record = region[offset : offset + BATTLE_RECORD_STRIDE]
        character_id = record[CHARACTER_FIELD]
        if character_id == 0:
            continue
        records.append(
            {
                "slot": slot,
                "record_address": f"0x{BATTLE_RECORD_BASE + offset:08X}",
                "record_sha256": _bytes_hash(record),
                "character_id": character_id,
                "grid_x": record[GRID_X_FIELD],
                "grid_y": record[GRID_Y_FIELD],
            }
        )
    return records


def _match_characters(match: dict[str, Any]) -> list[int]:
    values = set()
    for source in match["best_sources"]:
        values.update(source["character_ids"])
    return sorted(values)


def _match_origins(match: dict[str, Any]) -> list[dict[str, int]]:
    values = set()
    for source in match["best_sources"]:
        origin = source["non_affine_task_origin_candidate"]
        if origin is not None:
            values.add((origin["x"], origin["y"]))
    return [{"x": x, "y": y} for x, y in sorted(values)]


def _public_unit(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot": record["slot"],
        "record_address": record["record_address"],
        "character_id": record["character_id"],
        "grid_x": record["grid_x"],
        "grid_y": record["grid_y"],
    }


def _grid_projection(
    record: dict[str, Any],
    horizontal_scroll: int,
    vertical_scroll: int,
) -> dict[str, int]:
    return {
        "x": (
            record["grid_x"] * 32 - horizontal_scroll + 16
        )
        & 0x1FF,
        "y": (
            record["grid_y"] * 16 - vertical_scroll + 8
        )
        & 0xFF,
    }


def _signed_residual(observed: int, predicted: int, mask: int) -> int:
    modulus = mask + 1
    raw = (observed - predicted) & mask
    return raw - modulus if raw >= modulus // 2 else raw


def _observation_from_parent(
    match: dict[str, Any],
    records: list[dict[str, Any]],
    horizontal_scroll: int,
    vertical_scroll: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_characters = _match_characters(match)
    origins = _match_origins(match)
    candidate_records = [
        record
        for record in records
        if record["character_id"] in source_characters
    ]
    base_candidates = []
    for record in candidate_records:
        projected = _grid_projection(
            record,
            horizontal_scroll,
            vertical_scroll,
        )
        for origin in origins:
            if (
                (origin["x"] & 0x1FF) == projected["x"]
                and (origin["y"] & 0xFF) == projected["y"]
            ):
                base_candidates.append(
                    {
                        "slot": record["slot"],
                        "observed_origin": origin,
                        "predicted_origin_mod": projected,
                    }
                )
    unique_base = {
        (
            item["slot"],
            item["observed_origin"]["x"],
            item["observed_origin"]["y"],
            item["predicted_origin_mod"]["x"],
            item["predicted_origin_mod"]["y"],
        )
        for item in base_candidates
    }
    base_candidates = [
        {
            "slot": slot,
            "observed_origin": {"x": observed_x, "y": observed_y},
            "predicted_origin_mod": {
                "x": predicted_x,
                "y": predicted_y,
            },
        }
        for slot, observed_x, observed_y, predicted_x, predicted_y
        in sorted(unique_base)
    ]
    base_slots = {item["slot"] for item in base_candidates}

    offset = None
    if not candidate_records:
        resolution = "no_live_character_candidate"
    elif len(base_slots) == 1:
        resolution = "unique_base_grid_anchor_observation"
    elif len(base_slots) > 1:
        resolution = "ambiguous_base_grid_anchor_observation"
    elif len(candidate_records) == 1 and len(origins) == 1:
        resolution = "single_live_character_candidate_with_offset"
        record = candidate_records[0]
        origin = origins[0]
        projected = _grid_projection(
            record,
            horizontal_scroll,
            vertical_scroll,
        )
        offset = {
            "slot": record["slot"],
            "observed_origin": origin,
            "predicted_origin_mod": projected,
            "delta": {
                "x": _signed_residual(origin["x"], projected["x"], 0x1FF),
                "y": _signed_residual(origin["y"], projected["y"], 0xFF),
            },
        }
    else:
        resolution = "unresolved_spatial_candidates"

    observation = {
        "oam_index": match["oam_index"],
        "parent_match_sha256": _object_hash(match),
        "source_resolution": match["resolution"],
        "source_character_ids": source_characters,
        "source_origin_candidates": origins,
        "live_character_candidates": [
            _public_unit(record) for record in candidate_records
        ],
        "base_grid_anchor_candidates": base_candidates,
        "spatial_resolution": resolution,
        "observed_offset": offset,
        "unit_ownership": None,
    }
    fit_row = {
        "horizontal_scroll": horizontal_scroll,
        "vertical_scroll": vertical_scroll,
        "origins": origins,
        "records": candidate_records,
    }
    return observation, fit_row


def _rank_single_axis(
    rows: list[dict[str, Any]],
    *,
    coordinate: str,
    grid_coordinate: str,
    scroll_coordinate: str,
    maximum_scale: int,
    modulus: int,
) -> list[dict[str, int]]:
    coverage: dict[tuple[int, int], set[int]] = defaultdict(set)
    for index, row in enumerate(rows):
        for scale in range(1, maximum_scale + 1):
            intercepts = set()
            for origin in row["origins"]:
                for record in row["records"]:
                    intercepts.add(
                        (
                            origin[coordinate]
                            + row[scroll_coordinate]
                            - scale * record[grid_coordinate]
                        )
                        % modulus
                    )
            for intercept in intercepts:
                coverage[(scale, intercept)].add(index)
    candidates = []
    for (scale, intercept), indices in coverage.items():
        candidates.append(
            {
                "pixels_per_grid": scale,
                "center_offset": intercept,
                "matching_observation_count": len(indices),
            }
        )
    candidates.sort(
        key=lambda item: (
            -item["matching_observation_count"],
            item["pixels_per_grid"],
            item["center_offset"],
        )
    )
    return candidates


def _fit_evidence(
    rows: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible = [
        row for row in rows if row["origins"] and row["records"]
    ]
    x_models = _rank_single_axis(
        eligible,
        coordinate="x",
        grid_coordinate="grid_x",
        scroll_coordinate="horizontal_scroll",
        maximum_scale=64,
        modulus=512,
    )
    y_models = _rank_single_axis(
        eligible,
        coordinate="y",
        grid_coordinate="grid_y",
        scroll_coordinate="vertical_scroll",
        maximum_scale=32,
        modulus=256,
    )
    if (
        x_models[0]["pixels_per_grid"] != 32
        or x_models[0]["center_offset"] != 16
        or y_models[0]["pixels_per_grid"] != 16
        or y_models[0]["center_offset"] != 8
    ):
        raise ValueError("independent model search selected another transform")
    return {
        "eligible_observation_count": len(eligible),
        "x": {
            "search_pixels_per_grid": {"minimum": 1, "maximum": 64},
            "center_offset_domain": {"minimum": 0, "maximum": 511},
            "best": x_models[0],
            "runner_up": x_models[1],
        },
        "y": {
            "search_pixels_per_grid": {"minimum": 1, "maximum": 32},
            "center_offset_domain": {"minimum": 0, "maximum": 255},
            "best": y_models[0],
            "runner_up": y_models[1],
        },
        "joint_matching_observation_count": sum(
            observation["spatial_resolution"]
            in {
                "unique_base_grid_anchor_observation",
                "ambiguous_base_grid_anchor_observation",
            }
            for observation in observations
        ),
    }


def _reconstruct(root: Path) -> dict[str, Any]:
    rom = root / ROM_RELATIVE
    rom_hash = _path_hash(rom)
    if rom_hash != ROM_DIGEST:
        raise ValueError("base ROM SHA-256 mismatch")
    parent, parent_hash, promotion_hash = _validated_parent(root)
    if parent["summary"]["checkpoint_parse_error_count"] != 0:
        raise ValueError("parent OAM corpus contains parse failures")

    checkpoints = []
    observations = []
    fit_rows = []
    for parent_checkpoint in parent["checkpoints"]:
        state = load_gba_state(root / parent_checkpoint["path"])
        region = state.read_memory(BATTLE_RECORD_BASE, BATTLE_REGION_SIZE)
        records = _decode_live_records(region)
        horizontal_scroll = (
            int(parent_checkpoint["display_registers"]["BG0HOFS"], 16)
            & 0x1FF
        )
        vertical_scroll = (
            int(parent_checkpoint["display_registers"]["BG0VOFS"], 16)
            & 0x1FF
        )
        checkpoint_observations = []
        for match in parent_checkpoint["matches"]:
            observation, fit_row = _observation_from_parent(
                match,
                records,
                horizontal_scroll,
                vertical_scroll,
            )
            checkpoint_observations.append(observation)
            observations.append(observation)
            fit_rows.append(fit_row)
        checkpoints.append(
            {
                "path": parent_checkpoint["path"],
                "sha256": parent_checkpoint["sha256"],
                "savestate_version_magic": parent_checkpoint[
                    "savestate_version_magic"
                ],
                "parent_checkpoint_sha256": _object_hash(
                    parent_checkpoint
                ),
                "display_scroll": {
                    "bg0_hofs_raw": horizontal_scroll,
                    "bg0_vofs_raw": vertical_scroll,
                },
                "unit_pool": {
                    "address": f"0x{BATTLE_RECORD_BASE:08X}",
                    "size": len(region),
                    "sha256": _bytes_hash(region),
                    "live_unit_count": len(records),
                    "live_units": records,
                },
                "oam_unit_observations": checkpoint_observations,
            }
        )

    resolution_counts = defaultdict(int)
    for observation in observations:
        resolution_counts[observation["spatial_resolution"]] += 1
    live_record_count = sum(
        item["unit_pool"]["live_unit_count"] for item in checkpoints
    )
    summary = {
        "checkpoint_count": len(checkpoints),
        "live_unit_record_count": live_record_count,
        "oam_observation_count": len(observations),
        "observations_with_live_character_candidates": sum(
            bool(item["live_character_candidates"]) for item in observations
        ),
        "observations_without_live_character_candidates": resolution_counts[
            "no_live_character_candidate"
        ],
        "unique_base_grid_anchor_observation_count": resolution_counts[
            "unique_base_grid_anchor_observation"
        ],
        "ambiguous_base_grid_anchor_observation_count": resolution_counts[
            "ambiguous_base_grid_anchor_observation"
        ],
        "single_live_character_candidate_with_offset_count": resolution_counts[
            "single_live_character_candidate_with_offset"
        ],
        "unresolved_spatial_candidate_count": resolution_counts[
            "unresolved_spatial_candidates"
        ],
        "unit_ownership_binding_count": sum(
            item["unit_ownership"] is not None for item in observations
        ),
    }
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_RELATIVE.as_posix(),
            "size": rom.stat().st_size,
            "sha256": rom_hash,
        },
        "source_oam_bindings": {
            "path": PARENT_RELATIVE.as_posix(),
            "schema": parent["schema"],
            "sha256": parent_hash,
            "promotion_manifest_path": PARENT_PROMOTION_RELATIVE.as_posix(),
            "promotion_manifest_sha256": promotion_hash,
            "checkpoint_count": parent["summary"]["checkpoint_count"],
            "matched_oam_object_count": parent["summary"][
                "matched_oam_object_count"
            ],
        },
        "unit_pool_contract": {
            "base_address": f"0x{BATTLE_RECORD_BASE:08X}",
            "record_size": BATTLE_RECORD_STRIDE,
            "record_count": BATTLE_RECORD_COUNT,
            "candidate_slot_first": UNIT_FIRST,
            "candidate_slot_last": UNIT_LAST,
            "live_record_predicate": "character_id != 0",
            "character_id_offset": f"0x{CHARACTER_FIELD:02X}",
            "grid_x_offset": f"0x{GRID_X_FIELD:02X}",
            "grid_y_offset": f"0x{GRID_Y_FIELD:02X}",
        },
        "coordinate_model": {
            "x": {
                "formula": "(grid_x * 32 - BG0HOFS + 16) modulo 512",
                "pixels_per_grid": 32,
                "center_offset": 16,
                "modulus": 512,
                "canonical_delta_range": {"minimum": -256, "maximum": 255},
            },
            "y": {
                "formula": "(grid_y * 16 - BG0VOFS + 8) modulo 256",
                "pixels_per_grid": 16,
                "center_offset": 8,
                "modulus": 256,
                "canonical_delta_range": {"minimum": -128, "maximum": 127},
            },
            "origin_source": (
                "parent non_affine_task_origin_candidate; observed screen "
                "coordinate minus source component-local coordinate"
            ),
            "interpretation": (
                "a corpus-level spatial anchor observation, not a traced "
                "unit constructor, selector, camera, or OAM ownership writer"
            ),
            "model_selection": _fit_evidence(fit_rows, observations),
        },
        "summary": summary,
        "scope": {
            "all_parent_oam_checkpoints_reused": (
                len(checkpoints) == parent["summary"]["checkpoint_count"]
            ),
            "unit_pool_raw_bytes_hash_bound": bool(checkpoints),
            "live_unit_records_observed": bool(live_record_count),
            "character_id_overlap_recorded": bool(observations),
            "grid_to_non_affine_origin_base_model_observed": (
                resolution_counts["unique_base_grid_anchor_observation"] > 0
            ),
            "repeated_character_spatial_candidates_disambiguated": True,
            "live_unit_oam_ownership_proven": False,
            "unit_constructor_or_selector_trace_complete": False,
            "camera_offset_writer_schedule_complete": False,
            "nonzero_presentation_offset_semantics_complete": False,
            "unit_animation_state_to_source_frame_complete": False,
            "all_live_units_visualized": False,
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
        actual = _json_object(bindings_path)
        expected = _reconstruct(root)
        if actual != expected:
            errors.append(
                "bindings do not match independently reconstructed evidence"
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
        actual = {}
    summary = actual.get("summary", {}) if isinstance(actual, dict) else {}
    return {
        "verified": not errors,
        "errors": errors,
        "checkpoints": (
            summary.get("checkpoint_count", 0) if not errors else 0
        ),
        "observations": (
            summary.get("oam_observation_count", 0) if not errors else 0
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
