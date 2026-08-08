#!/usr/bin/env python3
"""Build a production-relocated controlled battle-effect pixel pair."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import struct
import sys
import tarfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    _profile_screen_pixels,
    _runtime_oam_instances,
)
from tools.build_controlled_battle_effect_direct_spawn_probe import (
    CASES_BY_ID,
    HOOK,
    HOOK_OFFSET,
    SOUND_MAIN,
    STUB,
    STUB_OFFSET,
    STUB_SIZE,
    build_stub,
    encode_thumb_bl,
)
from tools.build_controlled_battle_effect_sequence_probe import (
    HOOK as SEQUENCE_HOOK,
    HOOK_OFFSET as SEQUENCE_HOOK_OFFSET,
    SOUND_MAIN as SEQUENCE_SOUND_MAIN,
    STUB as SEQUENCE_STUB,
    STUB_OFFSET as SEQUENCE_STUB_OFFSET,
    STUB_SIZE as SEQUENCE_STUB_SIZE,
    _stub as build_sequence_stub,
)
from tools.build_mod import apply_patch
from tools.image_resource_regions import ImageResourceRegions
from tools.import_battle_effect_resource_relocations import (
    REGION_REGISTRY_PATH,
    SPEC_SCHEMA,
    resolve_battle_effect_resource_relocation_patches,
)
from tools.import_battle_effect_resources import ROM_SHA256
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


PROFILE_SCHEMA = "controlled-battle-effect-pixel-ab-profile-v1"
BUILD_SCHEMA = "controlled-battle-effect-pixel-ab-build-v1"
VARIANTS = ("baseline", "candidate")
SEQUENCE_CASES = {
    "group-06-sequence-08": (6, 8),
}


def _require_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"controlled battle-effect pixel {label} must be an integer")
    return value


def _bgr555_rgb8(raw: bytes, index: int) -> list[int]:
    color = struct.unpack_from("<H", raw, index * 2)[0]
    return [
        value << 3 | value >> 2
        for value in (
            color & 0x1F,
            (color >> 5) & 0x1F,
            (color >> 10) & 0x1F,
        )
    ]


def _archive_member_sha256(archive: Path, member_name: str) -> str:
    with tarfile.open(archive, "r:") as source:
        matches = [member for member in source.getmembers() if member.name == member_name]
        if len(matches) != 1 or not matches[0].isfile():
            raise ValueError("controlled battle-effect pixel ack state member mismatch")
        stream = source.extractfile(matches[0])
        if stream is None:
            raise ValueError("controlled battle-effect pixel ack state member is unreadable")
        return _sha256(stream.read())


def _install_probe(
    rom: bytes, *, case_id: str, sequence_id: int, execution_mode: str
) -> tuple[bytes, dict[str, int]]:
    if execution_mode == "controlled-direct-spawn":
        case = CASES_BY_ID.get(case_id)
        if case is None:
            raise ValueError(f"unknown controlled direct-spawn case: {case_id}")
        hook, hook_offset, sound_main = HOOK, HOOK_OFFSET, SOUND_MAIN
        stub, stub_offset, stub_size = STUB, STUB_OFFSET, STUB_SIZE
        stub_bytes = build_stub(case)
    elif execution_mode == "controlled-sequence-injection":
        if SEQUENCE_CASES.get(case_id) != (6, 8) or sequence_id != 8:
            raise ValueError(f"unknown controlled sequence case: {case_id}")
        hook = SEQUENCE_HOOK
        hook_offset = SEQUENCE_HOOK_OFFSET
        sound_main = SEQUENCE_SOUND_MAIN
        stub = SEQUENCE_STUB
        stub_offset = SEQUENCE_STUB_OFFSET
        stub_size = SEQUENCE_STUB_SIZE
        stub_bytes = build_sequence_stub(sequence_id)
    else:
        raise ValueError("controlled battle-effect pixel execution mode mismatch")
    if rom[hook_offset:hook_offset + 4] != encode_thumb_bl(hook, sound_main):
        raise ValueError("controlled battle-effect pixel SoundMain hook mismatch")
    if any(rom[stub_offset:stub_offset + stub_size]):
        raise ValueError("controlled battle-effect pixel stub region is not zero-filled")
    output = bytearray(rom)
    output[hook_offset:hook_offset + 4] = encode_thumb_bl(hook, stub)
    output[stub_offset:stub_offset + stub_size] = stub_bytes
    return bytes(output), {
        "hook_offset": hook_offset,
        "stub_offset": stub_offset,
        "stub_size": stub_size,
    }


def _validate_profile(root: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = _json(profile_path)
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("controlled battle-effect pixel profile schema mismatch")
    execution_mode = profile.get("execution_mode")
    if execution_mode not in {
        "controlled-direct-spawn",
        "controlled-sequence-injection",
    }:
        raise ValueError("controlled battle-effect pixel execution mode mismatch")
    if profile.get("natural_gameplay_route") is not False:
        raise ValueError("controlled battle-effect pixel cannot claim natural gameplay")
    if profile.get("production_resource_relocation") is not True:
        raise ValueError("controlled battle-effect pixel must use production relocation")

    case_id = profile.get("case_id")
    case = CASES_BY_ID.get(case_id)
    group_id = _require_int(profile.get("group_id"), "group_id")
    sequence_id = _require_int(profile.get("sequence_id"), "sequence_id")
    if execution_mode == "controlled-direct-spawn":
        if case_id not in {
            "group-03-sequence-03-side-0-direct-spawn",
            "group-18-sequence-07-direct-spawn",
        } or case is None:
            raise ValueError("controlled battle-effect pixel case contract mismatch")
        expected_case = (case.group_id, case.sequence_id)
    else:
        expected_case = SEQUENCE_CASES.get(case_id)
        if expected_case is None:
            raise ValueError("controlled battle-effect pixel case contract mismatch")
    if (group_id, sequence_id) != expected_case:
        raise ValueError("controlled battle-effect pixel group/sequence mismatch")

    catalogs = profile.get("catalogs")
    if not isinstance(catalogs, dict):
        raise ValueError("controlled battle-effect pixel catalogs mismatch")
    payloads: dict[str, dict[str, Any]] = {}
    for key in ("resource_pairs", "animations", "sequence_bindings"):
        path = _require_relative_file(root, catalogs.get(key), key)
        _require_sha(path, catalogs.get(f"{key}_sha256"), key)
        payloads[key] = _json(path)

    graphics_path = _require_relative_file(root, profile.get("source_graphics"), "source_graphics")
    graphics_sha = _require_sha(
        graphics_path, profile.get("source_graphics_sha256"), "source_graphics"
    )
    palette_path = _require_relative_file(root, profile.get("source_palette"), "source_palette")
    palette_sha = _require_sha(
        palette_path, profile.get("source_palette_sha256"), "source_palette"
    )
    input_state = _require_relative_file(root, profile.get("input_state"), "input_state")
    _require_sha(input_state, profile.get("input_state_sha256"), "input_state")

    runtime_key = (
        "direct_runtime"
        if execution_mode == "controlled-direct-spawn"
        else "controlled_runtime"
    )
    runtime = profile.get(runtime_key)
    if not isinstance(runtime, dict):
        raise ValueError(f"controlled battle-effect pixel {runtime_key} mismatch")
    runtime_paths = {}
    for key in ("evidence", "manifest", "archive"):
        path = _require_relative_file(root, runtime.get(key), f"{runtime_key}.{key}")
        _require_sha(path, runtime.get(f"{key}_sha256"), f"{runtime_key}.{key}")
        runtime_paths[key] = path
    ack_member = runtime.get("ack_state_member")
    if not isinstance(ack_member, str) or not ack_member.startswith("source/"):
        raise ValueError("controlled battle-effect pixel ack state member mismatch")
    if _archive_member_sha256(runtime_paths["archive"], ack_member) != runtime.get(
        "ack_state_sha256"
    ):
        raise ValueError("controlled battle-effect pixel ack state hash mismatch")

    runtime_evidence = _json(runtime_paths["evidence"])
    runtime_case = _find(runtime_evidence.get("cases"), "runtime case", case_id=case_id)
    ack_phase = _find(runtime_case.get("phases"), "runtime ack phase", name="ack-post")
    target_task = ack_phase.get("target_task")
    if execution_mode == "controlled-direct-spawn":
        if (
            runtime_case.get("group_id") != group_id
            or runtime_case.get("sequence_id") != sequence_id
            or runtime_case.get("side") != case.side
            or runtime_case.get("resource", {}).get("graphics_sha256") != graphics_sha
            or runtime_case.get("resource", {}).get("palette_sha256") != palette_sha
            or ack_phase.get("savestate_sha256") != runtime.get("ack_state_sha256")
            or not isinstance(target_task, dict)
            or target_task.get("tile_base")
            != profile.get("runtime_oam", {}).get("obj_tile_base")
            or target_task.get("palette_bank")
            != profile.get("runtime_oam", {}).get("palette_bank")
        ):
            raise ValueError("controlled battle-effect pixel direct runtime evidence mismatch")
    elif (
        runtime_case.get("verdict") != "verified_target_transaction"
        or runtime_case.get("group_id") != group_id
        or runtime_case.get("sequence_id") != sequence_id
        or ack_phase.get("savestate_sha256") != runtime.get("ack_state_sha256")
        or runtime_case.get("task_oam", {}).get("output_frame_id")
        != profile.get("frame_id")
    ):
        raise ValueError("controlled battle-effect pixel sequence runtime evidence mismatch")
    if target_task is None:
        target_task = {
            "tile_base": profile.get("runtime_oam", {}).get("obj_tile_base"),
            "palette_bank": profile.get("runtime_oam", {}).get("palette_bank"),
        }

    resource = _find(payloads["resource_pairs"].get("entries"), "resource pair", group_id=group_id)
    animation_group = _find(payloads["animations"].get("groups"), "animation group", group_id=group_id)
    sequence = _find(payloads["sequence_bindings"].get("sequences"), "sequence", sequence_id=sequence_id)
    if (
        resource.get("graphics", {}).get("decompressed_sha256") != graphics_sha
        or resource.get("palette", {}).get("decompressed_sha256") != palette_sha
        or sequence_id not in animation_group.get("sequence_ids", [])
        or group_id not in sequence.get("nonzero_resource_group_ids", [])
    ):
        raise ValueError("controlled battle-effect pixel catalog binding mismatch")

    frame_id = _require_int(profile.get("frame_id"), "frame_id")
    component_index = _require_int(profile.get("component_index"), "component_index")
    frame = _find(animation_group.get("frames"), "frame", frame_id=frame_id)
    component = _find(frame.get("components"), "component", component_index=component_index)
    pixel = profile.get("component_pixel_xy")
    screen = profile.get("screen_xy")
    if not isinstance(pixel, list) or len(pixel) != 2 or not isinstance(screen, list) or len(screen) != 2:
        raise ValueError("controlled battle-effect pixel coordinates mismatch")
    pixel_x, pixel_y = (_require_int(value, "component pixel") for value in pixel)
    width = _require_int(component.get("width"), "component width")
    height = _require_int(component.get("height"), "component height")
    tile_index = _require_int(component.get("tile_index"), "component tile")
    if not (0 <= pixel_x < width and 0 <= pixel_y < height):
        raise ValueError("controlled battle-effect pixel lies outside component")
    calculated_offset = (
        (tile_index + (pixel_y // 8) * (width // 8) + pixel_x // 8) * 32
        + (pixel_y % 8) * 4
        + (pixel_x % 8) // 2
    )
    offset = _require_int(profile.get("graphics_byte_offset"), "graphics offset")
    source = graphics_path.read_bytes()
    before = _require_int(profile.get("before_byte"), "before byte")
    after = _require_int(profile.get("after_byte"), "after byte")
    shift = 4 if pixel_x & 1 else 0
    preserved_mask = 0x0F if shift else 0xF0
    if (
        calculated_offset != offset
        or source[offset] != before
        or ((before >> shift) & 0xF) != profile.get("before_index")
        or ((after >> shift) & 0xF) != profile.get("after_index")
        or before & preserved_mask != after & preserved_mask
    ):
        raise ValueError("controlled battle-effect pixel nibble mapping mismatch")

    runtime_oam = profile.get("runtime_oam")
    if not isinstance(runtime_oam, dict) or runtime_oam.get("phase") != "ack-post":
        raise ValueError("controlled battle-effect pixel runtime OAM mismatch")
    try:
        attr0, attr1, attr2 = (int(value, 16) for value in runtime_oam["attributes"])
        obj_vram = int(runtime_oam["obj_vram_address"], 16)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("controlled battle-effect pixel runtime OAM mismatch") from error
    expected_tile = (obj_vram - 0x06010000) // 32 + tile_index
    mapped_x = width - 1 - pixel_x if attr1 & 0x1000 else pixel_x
    mapped_y = height - 1 - pixel_y if attr1 & 0x2000 else pixel_y
    if (
        not isinstance(runtime_oam.get("oam_index"), int)
        or runtime_oam.get("obj_tile_base") != expected_tile
        or runtime_oam.get("palette_bank") != target_task.get("palette_bank")
        or attr2 & 0x3FF != expected_tile
        or (attr2 >> 12) & 0xF != runtime_oam.get("palette_bank")
        or attr0 & 0x0100
        or [((attr1 & 0x1FF) + mapped_x), ((attr0 & 0xFF) + mapped_y)] != screen
    ):
        raise ValueError("controlled battle-effect pixel runtime OAM mapping mismatch")
    instances = _runtime_oam_instances(
        profile,
        pixel_x,
        pixel_y,
        component_width=width,
        component_height=height,
    )
    bindings = runtime_case.get("task_oam", {}).get(
        "bindings", runtime_case.get("oam_bindings", [])
    )
    binding_by_index = {
        row.get("oam_index"): row for row in bindings if isinstance(row, dict)
    }
    for instance in instances:
        rendered_component = _find(
            frame.get("components"),
            "runtime OAM animation component",
            component_index=instance["component_index"],
        )
        binding = binding_by_index.get(instance["oam_index"], {})
        if (
            rendered_component.get("tile_index") != tile_index
            or rendered_component.get("width") != width
            or rendered_component.get("height") != height
            or (
                execution_mode == "controlled-sequence-injection"
                and [binding.get(key) for key in ("attr0", "attr1", "attr2")]
                != instance["attributes"]
            )
        ):
            raise ValueError("controlled battle-effect pixel runtime OAM instance mismatch")
    _profile_screen_pixels(profile)

    palette = palette_path.read_bytes()
    if (
        _bgr555_rgb8(palette, profile["before_index"]) != profile.get("before_rgb")
        or _bgr555_rgb8(palette, profile["after_index"]) != profile.get("after_rgb")
    ):
        raise ValueError("controlled battle-effect pixel palette color mismatch")
    return profile, {
        "case": case,
        "runtime_key": runtime_key,
        "graphics_path": graphics_path,
        "resource": resource,
        "allocation_offset": _require_int(profile.get("graphics_allocation_offset"), "allocation offset"),
        "pointer_offset": _require_int(profile.get("pair_pointer_offset"), "pointer offset"),
        "expected_encoded_size": _require_int(profile.get("expected_encoded_size"), "encoded size"),
    }


def build_pair(root: Path, profile_path: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    output = Path(output).resolve()
    if root not in profile_path.parents:
        raise ValueError("controlled battle-effect pixel profile must stay inside repository")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("controlled battle-effect pixel output directory must be empty")
    profile, contract = _validate_profile(root, profile_path)

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("controlled battle-effect pixel base ROM identity mismatch")
    source = contract["graphics_path"].read_bytes()
    candidate = bytearray(source)
    candidate[profile["graphics_byte_offset"]] = profile["after_byte"]
    candidate = bytes(candidate)
    if [
        index
        for index, pair in enumerate(zip(source, candidate, strict=True))
        if pair[0] != pair[1]
    ] != [profile["graphics_byte_offset"]]:
        raise ValueError("controlled battle-effect pixel graphics isolation mismatch")

    parent_spec = _json(root / FULL_SPEC)
    if parent_spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("controlled battle-effect pixel relocation schema mismatch")
    source_edit = _find(
        parent_spec.get("edits"),
        "relocation edit",
        resource_type="graphics",
        resource_sha256=profile["source_graphics_sha256"],
    )
    expected = source_edit.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("controlled battle-effect pixel relocation provenance is missing")
    source_pointer_offsets = expected.get("pointer_offsets")
    if profile.get("source_pointer_offsets", source_pointer_offsets) != source_pointer_offsets:
        raise ValueError("controlled battle-effect pixel source pointer aliases mismatch")
    target_pointer_offsets = profile.get(
        "target_pointer_offsets", [contract["pointer_offset"]]
    )
    if (
        not isinstance(source_pointer_offsets, list)
        or not isinstance(target_pointer_offsets, list)
        or target_pointer_offsets != [contract["pointer_offset"]]
        or not set(target_pointer_offsets).issubset(source_pointer_offsets)
    ):
        raise ValueError("controlled battle-effect pixel target pointer alias mismatch")

    output.mkdir(parents=True, exist_ok=True)
    layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    regions = ImageResourceRegions.from_path(root / REGION_REGISTRY_PATH, layout)
    variants: dict[str, dict[str, Any]] = {}
    for variant, graphics in (("baseline", source), ("candidate", candidate)):
        variant_dir = output / variant
        variant_dir.mkdir()
        graphics_path = variant_dir / f"group-{profile['group_id']:02d}-graphics-4bpp.bin"
        graphics_path.write_bytes(graphics)
        spec = {key: copy.deepcopy(value) for key, value in parent_spec.items() if key != "edits"}
        edit = copy.deepcopy(source_edit)
        edit["id"] = f"{profile['profile_id']}-{variant}"
        edit["source_file"] = str(graphics_path)
        edit["target_pointer_offsets"] = target_pointer_offsets
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
            or ledger[0]["size"] != contract["expected_encoded_size"]
            or ledger[0]["decompressed_size"] != len(graphics)
            or ledger[1]["kind"] != "redirect"
            or ledger[1]["offset"] != contract["pointer_offset"]
        ):
            raise ValueError("controlled battle-effect pixel patch topology mismatch")
        relocated = _apply(base, layout, regions, patches)
        rom, probe_layout = _install_probe(
            relocated,
            case_id=profile["case_id"],
            sequence_id=profile["sequence_id"],
            execution_mode=profile["execution_mode"],
        )
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
            "probe": {
                "hook_offset": probe_layout["hook_offset"],
                "hook_sha256": _sha256(
                    rom[probe_layout["hook_offset"]:probe_layout["hook_offset"] + 4]
                ),
                "stub_offset": probe_layout["stub_offset"],
                "stub_size": probe_layout["stub_size"],
                "stub_sha256": _sha256(
                    rom[
                        probe_layout["stub_offset"]:
                        probe_layout["stub_offset"] + probe_layout["stub_size"]
                    ]
                ),
            },
        }

    result = {
        "schema": BUILD_SCHEMA,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256_file(profile_path),
        "profile_id": profile["profile_id"],
        "case_id": profile["case_id"],
        "group_id": profile["group_id"],
        "sequence_id": profile["sequence_id"],
        "execution_mode": profile["execution_mode"],
        "natural_gameplay_route": profile["natural_gameplay_route"],
        "production_resource_relocation": profile["production_resource_relocation"],
        "base_rom": "rom/base.gba",
        "base_rom_sha256": ROM_SHA256,
        "input_state": profile["input_state"],
        "input_state_sha256": profile["input_state_sha256"],
        "runtime_oam": profile["runtime_oam"],
        contract["runtime_key"]: profile[contract["runtime_key"]],
        "catalogs": profile["catalogs"],
        "source_pointer_offsets": source_pointer_offsets,
        "target_pointer_offsets": target_pointer_offsets,
        "edit": {
            key: profile[key]
            for key in (
                "frame_id",
                "component_index",
                "component_pixel_xy",
                "graphics_byte_offset",
                "before_byte",
                "after_byte",
                "before_index",
                "after_index",
                "screen_xy",
                "before_rgb",
                "after_rgb",
            )
        },
        "same_patch_topology": _topology(variants["baseline"]["patch_ledger"])
        == _topology(variants["candidate"]["patch_ledger"]),
        "same_encoded_size": variants["baseline"]["encoded_graphics_size"]
        == variants["candidate"]["encoded_graphics_size"],
        "same_probe_bytes": variants["baseline"]["probe"] == variants["candidate"]["probe"],
        "variants": variants,
        "boundary": profile["boundary"],
    }
    if "screen_pixels" in profile:
        result["edit"]["screen_pixels"] = profile["screen_pixels"]
    if not all(
        result[key]
        for key in ("same_patch_topology", "same_encoded_size", "same_probe_bytes")
    ):
        raise ValueError("controlled battle-effect pixel A/B topology mismatch")
    _write_json(output / "build-manifest.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_pair(args.root, args.profile, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
