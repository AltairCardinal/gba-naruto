#!/usr/bin/env python3
"""Correlate natural character OAM origins with live unit grid records."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import uuid

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.verify_character_runtime_oam_bindings import (
        verify_bindings as verify_parent_bindings,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state
    from verify_character_runtime_oam_bindings import (
        verify_bindings as verify_parent_bindings,
    )


SCHEMA = "character-runtime-unit-oam-bindings-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_DIRECTORY = Path("artifacts/character-runtime-oam-bindings-v1")
SOURCE_BINDINGS = SOURCE_DIRECTORY / "bindings.json"
SOURCE_PROMOTION = SOURCE_DIRECTORY / "manifest.json"
SOURCE_SCHEMA = "character-runtime-oam-bindings-v1"
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
UNIT_POOL_RECORD_COUNT = 13
UNIT_POOL_SIZE = UNIT_RECORD_SIZE * UNIT_POOL_RECORD_COUNT
FIRST_LIVE_UNIT_SLOT = 1
LAST_LIVE_UNIT_SLOT = 12
CHARACTER_ID_OFFSET = 0x00
GRID_X_OFFSET = 0xC4
GRID_Y_OFFSET = 0xC5
X_PIXELS_PER_GRID = 32
X_CENTER_OFFSET = 16
X_MODULUS = 512
Y_PIXELS_PER_GRID = 16
Y_CENTER_OFFSET = 8
Y_MODULUS = 256


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _digest_bytes(payload)


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _normalize_wrapped_delta(delta: int, modulus: int) -> int:
    return ((delta + modulus // 2) % modulus) - modulus // 2


def _load_parent(root: Path) -> tuple[dict[str, Any], str, str]:
    bindings_path = root / SOURCE_BINDINGS
    report = verify_parent_bindings(root, bindings_path)
    if not report["verified"]:
        raise ValueError(
            "source OAM bindings failed independent verification: "
            + "; ".join(report["errors"])
        )
    parent = _read_object(bindings_path)
    if parent.get("schema") != SOURCE_SCHEMA:
        raise ValueError("source OAM bindings schema mismatch")
    if parent.get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("source OAM bindings ROM mismatch")
    promotion_path = root / SOURCE_PROMOTION
    promotion = _read_object(promotion_path)
    if (
        promotion.get("schema") != "git-artifact-promotion-v1"
        or promotion.get("artifact_status") != "accepted"
        or promotion.get("artifact_schema") != SOURCE_SCHEMA
    ):
        raise ValueError("source OAM promotion manifest is not accepted")
    bindings_hash = _digest_path(bindings_path)
    if promotion.get("files", {}).get("bindings.json") != bindings_hash:
        raise ValueError("source OAM promotion hash mismatch")
    return parent, bindings_hash, _digest_path(promotion_path)


def _live_units(unit_pool: bytes) -> list[dict[str, Any]]:
    if len(unit_pool) != UNIT_POOL_SIZE:
        raise ValueError("unit pool byte length mismatch")
    result = []
    for slot in range(FIRST_LIVE_UNIT_SLOT, LAST_LIVE_UNIT_SLOT + 1):
        start = slot * UNIT_RECORD_SIZE
        record = unit_pool[start : start + UNIT_RECORD_SIZE]
        character_id = record[CHARACTER_ID_OFFSET]
        if not character_id:
            continue
        result.append(
            {
                "slot": slot,
                "record_address": f"0x{UNIT_POOL_BASE + start:08X}",
                "record_sha256": _digest_bytes(record),
                "character_id": character_id,
                "grid_x": record[GRID_X_OFFSET],
                "grid_y": record[GRID_Y_OFFSET],
            }
        )
    return result


def _source_character_ids(match: dict[str, Any]) -> list[int]:
    return sorted(
        {
            character_id
            for source in match["best_sources"]
            for character_id in source["character_ids"]
        }
    )


def _source_origin_candidates(match: dict[str, Any]) -> list[dict[str, int]]:
    origins = {
        (origin["x"], origin["y"])
        for source in match["best_sources"]
        if (origin := source["non_affine_task_origin_candidate"]) is not None
    }
    return [{"x": x, "y": y} for x, y in sorted(origins)]


def _candidate_view(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        key: unit[key]
        for key in (
            "slot",
            "record_address",
            "character_id",
            "grid_x",
            "grid_y",
        )
    }


def _predicted_origin(
    unit: dict[str, Any],
    *,
    bg0_hofs: int,
    bg0_vofs: int,
) -> dict[str, int]:
    return {
        "x": (
            unit["grid_x"] * X_PIXELS_PER_GRID
            - bg0_hofs
            + X_CENTER_OFFSET
        )
        % X_MODULUS,
        "y": (
            unit["grid_y"] * Y_PIXELS_PER_GRID
            - bg0_vofs
            + Y_CENTER_OFFSET
        )
        % Y_MODULUS,
    }


def _build_observation(
    match: dict[str, Any],
    live_units: list[dict[str, Any]],
    *,
    bg0_hofs: int,
    bg0_vofs: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    character_ids = _source_character_ids(match)
    origins = _source_origin_candidates(match)
    candidates = [
        unit for unit in live_units if unit["character_id"] in character_ids
    ]
    exact = []
    for unit in candidates:
        predicted = _predicted_origin(
            unit,
            bg0_hofs=bg0_hofs,
            bg0_vofs=bg0_vofs,
        )
        for origin in origins:
            if (
                origin["x"] % X_MODULUS == predicted["x"]
                and origin["y"] % Y_MODULUS == predicted["y"]
            ):
                exact.append(
                    {
                        "slot": unit["slot"],
                        "observed_origin": origin,
                        "predicted_origin_mod": predicted,
                    }
                )
    exact = sorted(
        {
            (
                item["slot"],
                item["observed_origin"]["x"],
                item["observed_origin"]["y"],
                item["predicted_origin_mod"]["x"],
                item["predicted_origin_mod"]["y"],
            )
            for item in exact
        }
    )
    exact_records = [
        {
            "slot": slot,
            "observed_origin": {"x": origin_x, "y": origin_y},
            "predicted_origin_mod": {
                "x": predicted_x,
                "y": predicted_y,
            },
        }
        for slot, origin_x, origin_y, predicted_x, predicted_y in exact
    ]
    exact_slots = sorted({item["slot"] for item in exact_records})

    observed_offset = None
    if not candidates:
        spatial_resolution = "no_live_character_candidate"
    elif len(exact_slots) == 1:
        spatial_resolution = "unique_base_grid_anchor_observation"
    elif len(exact_slots) > 1:
        spatial_resolution = "ambiguous_base_grid_anchor_observation"
    elif len(candidates) == 1 and len(origins) == 1:
        spatial_resolution = "single_live_character_candidate_with_offset"
        unit = candidates[0]
        origin = origins[0]
        predicted = _predicted_origin(
            unit,
            bg0_hofs=bg0_hofs,
            bg0_vofs=bg0_vofs,
        )
        observed_offset = {
            "slot": unit["slot"],
            "observed_origin": origin,
            "predicted_origin_mod": predicted,
            "delta": {
                "x": _normalize_wrapped_delta(
                    origin["x"] - predicted["x"],
                    X_MODULUS,
                ),
                "y": _normalize_wrapped_delta(
                    origin["y"] - predicted["y"],
                    Y_MODULUS,
                ),
            },
        }
    else:
        spatial_resolution = "unresolved_spatial_candidates"

    observation = {
        "oam_index": match["oam_index"],
        "parent_match_sha256": _canonical_digest(match),
        "source_resolution": match["resolution"],
        "source_character_ids": character_ids,
        "source_origin_candidates": origins,
        "live_character_candidates": [
            _candidate_view(unit) for unit in candidates
        ],
        "base_grid_anchor_candidates": exact_records,
        "spatial_resolution": spatial_resolution,
        "observed_offset": observed_offset,
        "unit_ownership": None,
    }
    model_row = {
        "bg0_hofs": bg0_hofs,
        "bg0_vofs": bg0_vofs,
        "origins": origins,
        "candidates": candidates,
    }
    return observation, model_row


def _axis_model_ranking(
    rows: list[dict[str, Any]],
    *,
    axis: str,
    pixels_min: int,
    pixels_max: int,
    modulus: int,
) -> list[dict[str, int]]:
    scroll_key = "bg0_hofs" if axis == "x" else "bg0_vofs"
    grid_key = "grid_x" if axis == "x" else "grid_y"
    hits: dict[tuple[int, int], set[int]] = defaultdict(set)
    for row_index, row in enumerate(rows):
        for pixels_per_grid in range(pixels_min, pixels_max + 1):
            offsets = {
                (
                    origin[axis]
                    + row[scroll_key]
                    - pixels_per_grid * unit[grid_key]
                )
                % modulus
                for origin in row["origins"]
                for unit in row["candidates"]
            }
            for center_offset in offsets:
                hits[(pixels_per_grid, center_offset)].add(row_index)
    ranked = [
        {
            "pixels_per_grid": pixels_per_grid,
            "center_offset": center_offset,
            "matching_observation_count": len(observations),
        }
        for (pixels_per_grid, center_offset), observations in hits.items()
    ]
    return sorted(
        ranked,
        key=lambda item: (
            -item["matching_observation_count"],
            item["pixels_per_grid"],
            item["center_offset"],
        ),
    )


def _model_selection(
    rows: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible = [row for row in rows if row["candidates"] and row["origins"]]
    x_ranked = _axis_model_ranking(
        eligible,
        axis="x",
        pixels_min=1,
        pixels_max=64,
        modulus=X_MODULUS,
    )
    y_ranked = _axis_model_ranking(
        eligible,
        axis="y",
        pixels_min=1,
        pixels_max=32,
        modulus=Y_MODULUS,
    )
    expected_x = (X_PIXELS_PER_GRID, X_CENTER_OFFSET)
    expected_y = (Y_PIXELS_PER_GRID, Y_CENTER_OFFSET)
    if (
        (x_ranked[0]["pixels_per_grid"], x_ranked[0]["center_offset"])
        != expected_x
        or (y_ranked[0]["pixels_per_grid"], y_ranked[0]["center_offset"])
        != expected_y
    ):
        raise ValueError("observed corpus no longer selects the base grid model")
    return {
        "eligible_observation_count": len(eligible),
        "x": {
            "search_pixels_per_grid": {"minimum": 1, "maximum": 64},
            "center_offset_domain": {
                "minimum": 0,
                "maximum": X_MODULUS - 1,
            },
            "best": x_ranked[0],
            "runner_up": x_ranked[1],
        },
        "y": {
            "search_pixels_per_grid": {"minimum": 1, "maximum": 32},
            "center_offset_domain": {
                "minimum": 0,
                "maximum": Y_MODULUS - 1,
            },
            "best": y_ranked[0],
            "runner_up": y_ranked[1],
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


def build_bindings(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = root / ROM_PATH
    rom_hash = _digest_path(rom_path)
    if rom_hash != ROM_SHA256:
        raise ValueError(f"base ROM SHA-256 mismatch: {rom_hash}")

    parent, parent_hash, promotion_hash = _load_parent(root)
    if parent["summary"]["checkpoint_parse_error_count"]:
        raise ValueError("source OAM bindings contain checkpoint parse errors")

    checkpoints = []
    all_observations = []
    model_rows = []
    for parent_checkpoint in parent["checkpoints"]:
        path = root / parent_checkpoint["path"]
        state = load_gba_state(path)
        unit_pool = state.read_memory(UNIT_POOL_BASE, UNIT_POOL_SIZE)
        live_units = _live_units(unit_pool)
        bg0_hofs = (
            int(parent_checkpoint["display_registers"]["BG0HOFS"], 16)
            & (X_MODULUS - 1)
        )
        bg0_vofs = (
            int(parent_checkpoint["display_registers"]["BG0VOFS"], 16)
            & 0x1FF
        )
        observations = []
        for match in parent_checkpoint["matches"]:
            observation, model_row = _build_observation(
                match,
                live_units,
                bg0_hofs=bg0_hofs,
                bg0_vofs=bg0_vofs,
            )
            observations.append(observation)
            all_observations.append(observation)
            model_rows.append(model_row)
        checkpoints.append(
            {
                "path": parent_checkpoint["path"],
                "sha256": parent_checkpoint["sha256"],
                "savestate_version_magic": parent_checkpoint[
                    "savestate_version_magic"
                ],
                "parent_checkpoint_sha256": _canonical_digest(
                    parent_checkpoint
                ),
                "display_scroll": {
                    "bg0_hofs_raw": bg0_hofs,
                    "bg0_vofs_raw": bg0_vofs,
                },
                "unit_pool": {
                    "address": f"0x{UNIT_POOL_BASE:08X}",
                    "size": len(unit_pool),
                    "sha256": _digest_bytes(unit_pool),
                    "live_unit_count": len(live_units),
                    "live_units": live_units,
                },
                "oam_unit_observations": observations,
            }
        )

    model_selection = _model_selection(model_rows, all_observations)
    counts = defaultdict(int)
    for observation in all_observations:
        counts[observation["spatial_resolution"]] += 1
    live_unit_count = sum(
        checkpoint["unit_pool"]["live_unit_count"]
        for checkpoint in checkpoints
    )
    summary = {
        "checkpoint_count": len(checkpoints),
        "live_unit_record_count": live_unit_count,
        "oam_observation_count": len(all_observations),
        "observations_with_live_character_candidates": sum(
            bool(observation["live_character_candidates"])
            for observation in all_observations
        ),
        "observations_without_live_character_candidates": counts[
            "no_live_character_candidate"
        ],
        "unique_base_grid_anchor_observation_count": counts[
            "unique_base_grid_anchor_observation"
        ],
        "ambiguous_base_grid_anchor_observation_count": counts[
            "ambiguous_base_grid_anchor_observation"
        ],
        "single_live_character_candidate_with_offset_count": counts[
            "single_live_character_candidate_with_offset"
        ],
        "unresolved_spatial_candidate_count": counts[
            "unresolved_spatial_candidates"
        ],
        "unit_ownership_binding_count": sum(
            observation["unit_ownership"] is not None
            for observation in all_observations
        ),
    }
    return {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": rom_path.stat().st_size,
            "sha256": rom_hash,
        },
        "source_oam_bindings": {
            "path": SOURCE_BINDINGS.as_posix(),
            "schema": parent["schema"],
            "sha256": parent_hash,
            "promotion_manifest_path": SOURCE_PROMOTION.as_posix(),
            "promotion_manifest_sha256": promotion_hash,
            "checkpoint_count": parent["summary"]["checkpoint_count"],
            "matched_oam_object_count": parent["summary"][
                "matched_oam_object_count"
            ],
        },
        "unit_pool_contract": {
            "base_address": f"0x{UNIT_POOL_BASE:08X}",
            "record_size": UNIT_RECORD_SIZE,
            "record_count": UNIT_POOL_RECORD_COUNT,
            "candidate_slot_first": FIRST_LIVE_UNIT_SLOT,
            "candidate_slot_last": LAST_LIVE_UNIT_SLOT,
            "live_record_predicate": "character_id != 0",
            "character_id_offset": f"0x{CHARACTER_ID_OFFSET:02X}",
            "grid_x_offset": f"0x{GRID_X_OFFSET:02X}",
            "grid_y_offset": f"0x{GRID_Y_OFFSET:02X}",
        },
        "coordinate_model": {
            "x": {
                "formula": (
                    "(grid_x * 32 - BG0HOFS + 16) modulo 512"
                ),
                "pixels_per_grid": X_PIXELS_PER_GRID,
                "center_offset": X_CENTER_OFFSET,
                "modulus": X_MODULUS,
                "canonical_delta_range": {"minimum": -256, "maximum": 255},
            },
            "y": {
                "formula": (
                    "(grid_y * 16 - BG0VOFS + 8) modulo 256"
                ),
                "pixels_per_grid": Y_PIXELS_PER_GRID,
                "center_offset": Y_CENTER_OFFSET,
                "modulus": Y_MODULUS,
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
            "model_selection": model_selection,
        },
        "summary": summary,
        "scope": {
            "all_parent_oam_checkpoints_reused": (
                len(checkpoints) == parent["summary"]["checkpoint_count"]
            ),
            "unit_pool_raw_bytes_hash_bound": bool(checkpoints),
            "live_unit_records_observed": bool(live_unit_count),
            "character_id_overlap_recorded": bool(all_observations),
            "grid_to_non_affine_origin_base_model_observed": (
                counts["unique_base_grid_anchor_observation"] > 0
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export_bindings(args.root, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"character-runtime-unit-oam-bindings: {error}")
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
