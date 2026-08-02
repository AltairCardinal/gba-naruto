#!/usr/bin/env python3
"""Build probe-free production ROMs for a natural delayed-effect pixel A/B."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_battle_effect_pixel_ab import (
    FULL_SPEC,
    _apply,
    _find,
    _json,
    _ledger,
    _require_relative_file,
    _require_sha,
    _sha256,
    _sha256_file,
    _topology,
    _write_json,
)
from tools.image_resource_regions import ImageResourceRegions
from tools.import_battle_effect_resource_relocations import (
    REGION_REGISTRY_PATH,
    SPEC_SCHEMA,
    resolve_battle_effect_resource_relocation_patches,
)
from tools.import_battle_effect_resources import ROM_SHA256
from tools.inspect_mgba_savestate import load_gba_state
from tools.rom_layout import RomLayout
from tools.verify_battle_effect_frame_phase import (
    expected_phase_inputs,
    verify_artifact as verify_phase_artifact,
)
from tools.verify_battle_effect_natural_checkpoint import (
    verify_artifact as verify_natural_checkpoint,
)


PROFILE_SCHEMA = "natural-delayed-battle-effect-pixel-ab-profile-v1"
BUILD_SCHEMA = "natural-delayed-battle-effect-pixel-ab-build-v1"
VARIANTS = ("baseline", "candidate")


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"natural delayed pixel {label} must be an integer")
    return value


def _safe_directory(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"natural delayed pixel {label} must be a repository path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"natural delayed pixel {label} must be a safe relative path")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_dir():
        raise ValueError(f"natural delayed pixel {label} must stay inside repository")
    return path


def _rgb(raw: bytes, index: int) -> list[int]:
    color = struct.unpack_from("<H", raw, index * 2)[0]
    return [
        value << 3 | value >> 2
        for value in (color & 0x1F, (color >> 5) & 0x1F, (color >> 10) & 0x1F)
    ]


def _validate_profile(root: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = _json(profile_path)
    group_id = profile.get("group_id")
    sequence_id = profile.get("sequence_id")
    route = (group_id, sequence_id)
    expected_input_modes = {
        (3, 3): "zero-input-active-state",
        (18, 7): "explicit-input-sequence",
    }
    if (
        profile.get("schema") != PROFILE_SCHEMA
        or profile.get("execution_mode") != "natural-delayed-object"
        or profile.get("natural_gameplay_route") is not True
        or profile.get("production_resource_relocation") is not True
        or route not in expected_input_modes
        or profile.get("input_mode") != expected_input_modes[route]
    ):
        raise ValueError("natural delayed pixel profile contract mismatch")
    try:
        input_mode, normalized_inputs = expected_phase_inputs(profile)
    except ValueError as error:
        raise ValueError(f"natural delayed pixel input sequence mismatch: {error}") from error
    if input_mode == "explicit-input-sequence":
        timeout_frames = profile.get("timeout_frames")
        if (
            not isinstance(timeout_frames, int)
            or isinstance(timeout_frames, bool)
            or timeout_frames <= profile["capture_frame"]
        ):
            raise ValueError("natural delayed pixel timeout frame mismatch")

    input_state = _require_relative_file(root, profile.get("input_state"), "input_state")
    _require_sha(input_state, profile.get("input_state_sha256"), "input_state")
    input_evidence = _require_relative_file(
        root, profile.get("input_evidence"), "input_evidence"
    )
    _require_sha(input_evidence, profile.get("input_evidence_sha256"), "input_evidence")
    phase_artifact = _safe_directory(
        root, profile.get("source_natural_phase_artifact"), "source phase artifact"
    )
    phase_manifest = _require_relative_file(
        root, profile.get("source_natural_phase_manifest"), "source phase manifest"
    )
    try:
        _require_sha(
            phase_manifest,
            profile.get("source_natural_phase_manifest_sha256"),
            "source phase",
        )
    except ValueError as error:
        raise ValueError(f"natural delayed pixel source phase mismatch: {error}") from error
    phase_result = verify_phase_artifact(phase_artifact)
    if not phase_result.get("verified") or phase_result.get("group_id") != group_id:
        raise ValueError("natural delayed pixel source phase is not verified")
    phase = _json(phase_manifest)
    if (
        phase.get("artifact_status") != "accepted"
        or phase.get("group_id") != group_id
        or phase.get("input_mode") != input_mode
        or phase.get("inputs") != normalized_inputs
        or phase.get("input_state")
        != {"path": profile["input_state"], "sha256": profile["input_state_sha256"]}
    ):
        raise ValueError("natural delayed pixel source phase contract mismatch")

    delayed = profile.get("delayed_object")
    common_delayed = {
        "slot": 3,
        "state": 1,
        "ninja_tool_id": 67,
        "encoded_action": "0xC3",
        "remaining_turns": 0 if group_id == 3 else 2,
        "resource_group_id": group_id,
    }
    expected_delayed = (
        {**common_delayed, "expiry_action": "0xE4"}
        if group_id == 3
        else {**common_delayed, "x": 13, "y": 6}
    )
    if delayed != expected_delayed:
        raise ValueError("natural delayed pixel object contract mismatch")
    if group_id == 18:
        checkpoint = verify_natural_checkpoint(input_evidence.parent)
        if (
            checkpoint.get("errors")
            or checkpoint.get("group_id") != 18
            or "object-created" not in checkpoint.get("verified_source_states", [])
        ):
            raise ValueError("natural delayed pixel checkpoint evidence is not verified")

    catalogs = profile.get("catalogs")
    if not isinstance(catalogs, dict):
        raise ValueError("natural delayed pixel catalogs mismatch")
    payloads = {}
    for key in ("resource_pairs", "animations", "sequence_bindings"):
        path = _require_relative_file(root, catalogs.get(key), key)
        _require_sha(path, catalogs.get(f"{key}_sha256"), key)
        payloads[key] = _json(path)
    graphics_path = _require_relative_file(
        root, profile.get("source_graphics"), "source_graphics"
    )
    graphics_sha = _require_sha(
        graphics_path, profile.get("source_graphics_sha256"), "source_graphics"
    )
    palette_path = _require_relative_file(
        root, profile.get("source_palette"), "source_palette"
    )
    palette_sha = _require_sha(
        palette_path, profile.get("source_palette_sha256"), "source_palette"
    )
    resource = _find(
        payloads["resource_pairs"].get("entries"), "resource", group_id=group_id
    )
    animation = _find(
        payloads["animations"].get("groups"), "animation", group_id=group_id
    )
    sequence = _find(
        payloads["sequence_bindings"].get("sequences"),
        "sequence",
        sequence_id=sequence_id,
    )
    if (
        resource.get("graphics", {}).get("decompressed_sha256") != graphics_sha
        or resource.get("palette", {}).get("decompressed_sha256") != palette_sha
        or group_id not in sequence.get("nonzero_resource_group_ids", [])
        or sequence_id not in animation.get("sequence_ids", [])
    ):
        raise ValueError("natural delayed pixel catalog binding mismatch")

    frame = _find(animation.get("frames"), "frame", frame_id=profile.get("frame_id"))
    component = _find(
        frame.get("components"),
        "component",
        component_index=profile.get("component_index"),
    )
    pixel = profile.get("component_pixel_xy")
    if not isinstance(pixel, list) or len(pixel) != 2:
        raise ValueError("natural delayed pixel component coordinate mismatch")
    x, y = (_integer(value, "component coordinate") for value in pixel)
    width = _integer(component.get("width"), "component width")
    height = _integer(component.get("height"), "component height")
    tile = _integer(component.get("tile_index"), "component tile")
    if not 0 <= x < width or not 0 <= y < height:
        raise ValueError("natural delayed pixel component coordinate mismatch")
    offset = (tile + (y // 8) * (width // 8) + x // 8) * 32 + (y % 8) * 4 + x // 2 % 4
    source = graphics_path.read_bytes()
    before = _integer(profile.get("before_byte"), "before byte")
    after = _integer(profile.get("after_byte"), "after byte")
    if offset != profile.get("graphics_byte_offset") or source[offset] != before:
        raise ValueError("natural delayed pixel graphics mapping mismatch")
    shift = 4 if x & 1 else 0
    preserved = 0x0F if shift else 0xF0
    if (
        (before >> shift) & 0xF != profile.get("before_index")
        or (after >> shift) & 0xF != profile.get("after_index")
        or before & preserved != after & preserved
    ):
        raise ValueError("natural delayed pixel nibble isolation mismatch")
    palette = palette_path.read_bytes()
    if (
        _rgb(palette, profile["before_index"]) != profile.get("before_rgb")
        or _rgb(palette, profile["after_index"]) != profile.get("after_rgb")
    ):
        raise ValueError("natural delayed pixel palette mapping mismatch")

    runtime = profile.get("runtime_oam")
    if not isinstance(runtime, dict) or runtime.get("phase") != "ack-post":
        raise ValueError("natural delayed pixel runtime OAM mismatch")
    state = load_gba_state(phase_artifact / "raw/ack-post/capture.ss9")
    try:
        attrs = [int(value, 16) for value in runtime["attributes"]]
        vram = int(runtime["obj_vram_address"], 16)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("natural delayed pixel runtime OAM mismatch") from error
    oam = state.read_memory(0x07000000 + runtime["oam_index"] * 8, 6)
    if (
        oam != struct.pack("<HHH", *attrs)
        or attrs[2] & 0x3FF != runtime.get("obj_tile_base")
        or attrs[2] >> 12 != runtime.get("palette_bank")
        or state.read_memory(vram, len(source)) != source
        or state.read_memory(0x05000200 + runtime["palette_bank"] * 32, len(palette)) != palette
        or [((attrs[1] & 0x1FF) + x), ((attrs[0] & 0xFF) + y)] != profile.get("screen_xy")
    ):
        raise ValueError("natural delayed pixel source phase resource mismatch")

    return profile, {
        "graphics_path": graphics_path,
        "palette_path": palette_path,
        "source_edit": _find(
            _json(root / FULL_SPEC).get("edits"),
            "relocation edit",
            resource_type="graphics",
            resource_sha256=graphics_sha,
        ),
        "allocation_offset": _integer(
            profile.get("graphics_allocation_offset"), "allocation offset"
        ),
        "pointer_offset": _integer(profile.get("pair_pointer_offset"), "pointer offset"),
        "encoded_size": _integer(profile.get("expected_encoded_size"), "encoded size"),
        "phase_result": phase_result,
    }


def build_pair(root: Path, profile_path: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    output = Path(output).resolve()
    if root not in profile_path.parents:
        raise ValueError("natural delayed pixel profile must stay inside repository")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("natural delayed pixel output must be empty")
    profile, contract = _validate_profile(root, profile_path)
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("natural delayed pixel base ROM mismatch")
    source = contract["graphics_path"].read_bytes()
    candidate = bytearray(source)
    candidate[profile["graphics_byte_offset"]] = profile["after_byte"]
    candidate = bytes(candidate)
    if [i for i, pair in enumerate(zip(source, candidate, strict=True)) if pair[0] != pair[1]] != [profile["graphics_byte_offset"]]:
        raise ValueError("natural delayed pixel authored graphics isolation mismatch")

    parent_spec = _json(root / FULL_SPEC)
    if parent_spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("natural delayed pixel relocation schema mismatch")
    expected = contract["source_edit"].get("expected", {})
    source_offsets = expected.get("pointer_offsets")
    target_offsets = profile.get("target_pointer_offsets")
    if (
        source_offsets != profile.get("source_pointer_offsets")
        or target_offsets != [contract["pointer_offset"]]
        or not set(target_offsets).issubset(source_offsets)
    ):
        raise ValueError("natural delayed pixel pointer alias mismatch")

    output.mkdir(parents=True, exist_ok=True)
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGION_REGISTRY_PATH, layout)
    variants = {}
    for variant, graphics in (("baseline", source), ("candidate", candidate)):
        variant_dir = output / variant
        variant_dir.mkdir()
        graphics_path = variant_dir / f"group-{profile['group_id']:02d}-graphics-4bpp.bin"
        graphics_path.write_bytes(graphics)
        spec = {key: copy.deepcopy(value) for key, value in parent_spec.items() if key != "edits"}
        edit = copy.deepcopy(contract["source_edit"])
        edit["id"] = f"{profile['profile_id']}-{variant}"
        edit["source_file"] = str(graphics_path)
        edit["target_pointer_offsets"] = target_offsets
        spec["edits"] = [edit]
        spec_path = variant_dir / "spec.json"
        _write_json(spec_path, spec)
        patches = resolve_battle_effect_resource_relocation_patches(
            root, spec_path, rom=base, layout=layout, regions=regions
        )
        ledger = _ledger(patches)
        if (
            len(ledger) != 2
            or ledger[0]["kind"] != "allocation"
            or ledger[0]["offset"] != contract["allocation_offset"]
            or ledger[0]["size"] != contract["encoded_size"]
            or ledger[0]["decompressed_size"] != len(graphics)
            or ledger[1]["kind"] != "redirect"
            or ledger[1]["offset"] != contract["pointer_offset"]
            or ledger[1]["target_pointer_offsets"] != target_offsets
        ):
            raise ValueError("natural delayed pixel patch topology mismatch")
        rom = _apply(base, layout, regions, patches)
        rom_path = variant_dir / f"{variant}.gba"
        rom_path.write_bytes(rom)
        variants[variant] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
            "spec_path": spec_path.relative_to(output).as_posix(),
            "graphics_path": graphics_path.relative_to(output).as_posix(),
            "graphics_sha256": _sha256(graphics),
            "encoded_graphics_size": ledger[0]["size"],
            "graphics_allocation_offset": ledger[0]["offset"],
            "redirect_pointer_offsets": ledger[1]["target_pointer_offsets"],
            "patch_ledger": ledger,
        }

    result = {
        "schema": BUILD_SCHEMA,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256_file(profile_path),
        "profile_id": profile["profile_id"],
        "group_id": profile["group_id"],
        "sequence_id": profile["sequence_id"],
        "execution_mode": profile["execution_mode"],
        "natural_gameplay_route": True,
        "production_resource_relocation": True,
        "input_mode": profile["input_mode"],
        "inputs": profile.get("inputs", []),
        "capture_frame": profile.get("capture_frame"),
        "timeout_frames": profile.get("timeout_frames"),
        "input_state": profile["input_state"],
        "input_state_sha256": profile["input_state_sha256"],
        "input_evidence": profile["input_evidence"],
        "input_evidence_sha256": profile["input_evidence_sha256"],
        "source_natural_phase_artifact": profile["source_natural_phase_artifact"],
        "source_natural_phase_manifest_sha256": profile["source_natural_phase_manifest_sha256"],
        "delayed_object": profile["delayed_object"],
        "source_pointer_offsets": source_offsets,
        "target_pointer_offsets": target_offsets,
        "edit": {
            key: profile[key]
            for key in (
                "frame_id", "component_index", "component_pixel_xy",
                "graphics_byte_offset", "before_byte", "after_byte",
                "before_index", "after_index", "screen_xy", "before_rgb", "after_rgb",
            )
        },
        "runtime_oam": profile["runtime_oam"],
        "same_patch_topology": _topology(variants["baseline"]["patch_ledger"]) == _topology(variants["candidate"]["patch_ledger"]),
        "same_encoded_size": variants["baseline"]["encoded_graphics_size"] == variants["candidate"]["encoded_graphics_size"],
        "probe_free": True,
        "variants": variants,
        "boundary": profile["boundary"],
    }
    if not result["same_patch_topology"] or not result["same_encoded_size"]:
        raise ValueError("natural delayed pixel A/B topology mismatch")
    _write_json(output / "build-manifest.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_pair(args.root, args.profile, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
