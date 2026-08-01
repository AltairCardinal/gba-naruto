#!/usr/bin/env python3
"""Independently verify the natural battle-effect group 5 pixel A/B artifact."""

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

from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from tools.verify_menu_portrait_writeback_audit import (
    _decompress_lz77,
    _encode_lz77,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "battle-effect-group5-pixel-ab-runtime-v1"
INPUT_PATH = Path("artifacts/runtime-checkpoints/scenario-41-attack-confirmation.ss9")
INPUT_SHA256 = "544cffbaea182a55d1963447965d95750984a915cae9877d66d6bc3aebbd560f"
CATALOG_PATH = Path("artifacts/battle-effect-resource-pairs-v1/manifest.json")
CATALOG_SHA256 = "716ac580326077127797c634d1f19bbc0aadcfd4db9c577730728b112f002963"
PALETTE_PATH = Path(
    "artifacts/battle-effect-resource-pairs-v1/group-05-palette-bgr555.bin"
)
BASELINE_GRAPHICS_SHA256 = "6628fdc3365f8d6f16b134797be5f9a1c7cb48662ffeeea634ace058c659bb32"
CANDIDATE_GRAPHICS_SHA256 = "8a418cc83c61101ac7380e5313f4b0577bb42465a378ab21fb617b22af2f43e1"
PALETTE_SHA256 = "c00b7ea1d6748f60c387c12d2083da584a65a7e654e61a95bdfe25d1a803dc61"
SOURCE_GRAPHICS_OFFSET = 0x342938
PAIR_POINTER_OFFSET = 0x599144
GRAPHICS_ALLOCATION_OFFSET = 0xB40000
GRAPHICS_POINTER = 0x08B40000
REGION_REGISTRY_SHA256 = (
    "a7781118b2395f9b34399a96d7f2bc69bc410c1c75e994777f94b2c7c905914f"
)
BASELINE_ROM_SHA256 = "699674cc9316e3c9d307ac093dc8145273097bd393ae67630dd31631a9b18179"
CANDIDATE_ROM_SHA256 = "981f7cfcbee103ed7ff5ea78b6467c6dddf4ae0830382e7af4f0cd3221636aae"
BASELINE_RGB_SHA256 = "f79234f8ad45ef93064d9c5e6685e7ea4d5d6b4e5c8c7dafa0225865c2a64581"
CANDIDATE_RGB_SHA256 = "7215dae544256cbbc207e08821668810971c571ae4fbd9145c261ec30cb328f5"
RAW_FILES = (
    "build-manifest.json",
    "baseline/audit.json",
    "baseline/frame150.png",
    "baseline/frame150.ss9",
    "baseline/group-05-graphics-4bpp.bin",
    "baseline/guard.json",
    "baseline/sentinel.json",
    "baseline/spec.json",
    "candidate/audit.json",
    "candidate/frame150.png",
    "candidate/frame150.ss9",
    "candidate/group-05-graphics-4bpp.bin",
    "candidate/guard.json",
    "candidate/sentinel.json",
    "candidate/spec.json",
)
IMPLEMENTATION_PATHS = (
    "tools/build_battle_effect_group5_pixel_ab.py",
    "tools/export_battle_effect_group5_pixel_ab_evidence.py",
    "tools/verify_battle_effect_group5_pixel_ab_evidence.py",
    "tools/import_battle_effect_resource_relocations.py",
    "tools/import_battle_effect_resources.py",
    "tools/gba_image_export.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/build_mod.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
)
DOMAINS = {
    "EWRAM": (0x02000000, 0x40000),
    "IWRAM": (0x03000000, 0x8000),
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
}
EXPECTED_DIFFERENCES = {
    "EWRAM": [],
    "IWRAM": [],
    "IO": [],
    "PRAM": [],
    "VRAM": [0x12600],
    "OAM": [],
}
EXPECTED_PIXELS = [
    {
        "x": 160,
        "y": 48,
        "before_rgb": [255, 222, 198],
        "after_rgb": [189, 123, 115],
    }
]
EXPECTED_SCOPE = {
    "natural_action_5_attack": True,
    "production_relocation_route": True,
    "sequence_6_group_5_frame_1_graphics_single_pixel": True,
    "all_18_effect_groups_runtime_verified": False,
    "all_group_5_frames_runtime_verified": False,
    "affine_blend_timing_audio_equivalence": False,
    "physical_gba_verified": False,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("battle-effect group 5 verifier byte lengths differ")
    return [
        index for index, (before, after) in enumerate(zip(left, right))
        if before != after
    ]


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("battle-effect group 5 verifier screenshot geometry mismatch")
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


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _catalog_contract(root: Path, base: bytes) -> bytes:
    catalog_path = root / CATALOG_PATH
    if _sha256_file(catalog_path) != CATALOG_SHA256:
        raise ValueError("battle-effect group 5 independent catalog hash mismatch")
    catalog = _json(catalog_path)
    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 18:
        raise ValueError("battle-effect group 5 independent catalog denominator mismatch")
    entry = next(row for row in entries if row.get("group_id") == 5)
    graphics = entry.get("graphics", {})
    palette = entry.get("palette", {})
    compressed = base[SOURCE_GRAPHICS_OFFSET : SOURCE_GRAPHICS_OFFSET + 1165]
    decoded = _decompress_lz77(compressed, 0)
    if (
        entry.get("table_entry_file_offset") != PAIR_POINTER_OFFSET
        or entry.get("pair_raw_hex") != "38293408c82d3408"
        or base[PAIR_POINTER_OFFSET : PAIR_POINTER_OFFSET + 8].hex()
        != entry.get("pair_raw_hex")
        or graphics.get("file_offset") != SOURCE_GRAPHICS_OFFSET
        or graphics.get("compressed_size") != 1165
        or graphics.get("compressed_sha256") != _sha256(compressed)
        or graphics.get("decompressed_size") != 3840
        or graphics.get("decompressed_sha256") != BASELINE_GRAPHICS_SHA256
        or len(decoded) != 3840
        or _sha256(decoded) != BASELINE_GRAPHICS_SHA256
        or palette.get("decompressed_sha256") != PALETTE_SHA256
    ):
        raise ValueError("battle-effect group 5 independent catalog contract mismatch")
    return decoded


def _expected_patch_ledger(graphics: bytes) -> list[dict[str, Any]]:
    encoded = _encode_lz77(graphics)
    if len(encoded) != 1165 or _decompress_lz77(encoded, 0) != graphics:
        raise ValueError("battle-effect group 5 independent LZ77 contract mismatch")
    return [
        {
            "id": "battle-effect-graphics-000",
            "kind": "allocation",
            "asset_type": "battle_effect_resource_relocation",
            "resource_type": "graphics",
            "resource_sha256": BASELINE_GRAPHICS_SHA256,
            "replacement_sha256": _sha256(graphics),
            "offset": GRAPHICS_ALLOCATION_OFFSET,
            "size": len(encoded),
            "after_sha256": _sha256(encoded),
            "after_hex": None,
            "new_pointer": GRAPHICS_POINTER,
            "target_pointer_offsets": [PAIR_POINTER_OFFSET],
            "allocation": {
                "owner": "sequel_image_assets",
                "partition": "sequel-image-assets",
                "region": "battle-effects",
                "region_owner": "battle_effect_resources",
            },
            "decompressed_size": 3840,
        },
        {
            "id": "battle-effect-graphics-000.pointer-599144",
            "kind": "redirect",
            "asset_type": "battle_effect_resource_pointer",
            "resource_type": "graphics",
            "resource_sha256": BASELINE_GRAPHICS_SHA256,
            "replacement_sha256": None,
            "offset": PAIR_POINTER_OFFSET,
            "size": 4,
            "after_sha256": _sha256(bytes.fromhex("0000b408")),
            "after_hex": "0000b408",
            "new_pointer": GRAPHICS_POINTER,
            "target_pointer_offsets": [PAIR_POINTER_OFFSET],
            "allocation": None,
            "decompressed_size": None,
        },
    ]


def _rebuild_rom(base: bytes, graphics: bytes) -> bytes:
    encoded = _encode_lz77(graphics)
    if len(encoded) != 1165:
        raise ValueError("battle-effect group 5 independent encoded size mismatch")
    output = bytearray(base + bytes([0xFF]) * (0x1000000 - len(base)))
    output[
        GRAPHICS_ALLOCATION_OFFSET : GRAPHICS_ALLOCATION_OFFSET + len(encoded)
    ] = encoded
    output[PAIR_POINTER_OFFSET : PAIR_POINTER_OFFSET + 4] = GRAPHICS_POINTER.to_bytes(
        4, "little"
    )
    return bytes(output)


def _verify_spec(root: Path, raw: Path, variant: str) -> None:
    spec = _json(raw / variant / "spec.json")
    expected = {
        "schema": "battle-effect-resource-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": "sequel/image-resource-regions.json",
        "region_registry_sha256": REGION_REGISTRY_SHA256,
        "region": "battle-effects",
        "region_owner": "battle_effect_resources",
        "edits": [
            {
                "id": f"group-05-graphics-pixel-ab-{variant}",
                "resource_type": "graphics",
                "resource_sha256": BASELINE_GRAPHICS_SHA256,
                "source_file": f"raw/{variant}/group-05-graphics-4bpp.bin",
                "expected": {
                    "decompressed_size": 3840,
                    "physical_offsets": [SOURCE_GRAPHICS_OFFSET],
                    "pointer_offsets": [PAIR_POINTER_OFFSET],
                },
            }
        ],
    }
    if (
        _sha256_file(root / "sequel/image-resource-regions.json")
        != REGION_REGISTRY_SHA256
        or spec != expected
    ):
        raise ValueError(
            f"battle-effect group 5 independent {variant} authoring spec mismatch"
        )


def _verify_build(root: Path, raw: Path, build: dict[str, Any]) -> dict[str, bytes]:
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("battle-effect group 5 independent base ROM mismatch")
    catalog_graphics = _catalog_contract(root, base)
    graphics = {
        variant: (raw / variant / "group-05-graphics-4bpp.bin").read_bytes()
        for variant in ("baseline", "candidate")
    }
    if (
        graphics["baseline"] != catalog_graphics
        or _sha256(graphics["candidate"]) != CANDIDATE_GRAPHICS_SHA256
        or _diff(graphics["baseline"], graphics["candidate"]) != [0x200]
        or graphics["baseline"][0x200] != 0x02
        or graphics["candidate"][0x200] != 0x04
    ):
        raise ValueError("battle-effect group 5 independent graphics contract mismatch")

    expected_edit = {
        "group_id": 5,
        "sequence_id": 6,
        "frame_id": 1,
        "graphics_byte_offset": 0x200,
        "tile_id": 16,
        "tile_pixel_xy": [0, 0],
        "frame_pixel_xy": [0, 0],
        "screen_xy": [160, 48],
        "before_byte": 2,
        "after_byte": 4,
        "before_index": 2,
        "after_index": 4,
    }
    if (
        build.get("schema") != "battle-effect-group5-pixel-ab-build-v1"
        or build.get("base_rom_sha256") != ROM_SHA256
        or build.get("source_catalog") != CATALOG_PATH.as_posix()
        or build.get("source_catalog_sha256") != CATALOG_SHA256
        or build.get("input_state") != INPUT_PATH.as_posix()
        or build.get("input_state_sha256") != INPUT_SHA256
        or build.get("input")
        != {"key": "A", "down_frame": 5, "up_frame": 13, "capture_frame": 150}
        or build.get("edit") != expected_edit
        or build.get("runtime_contract")
        != {
            "before_rgb": [255, 222, 198],
            "after_rgb": [189, 123, 115],
            "oam_attributes": ["0x0030", "0x80A0", "0x5930"],
            "oam_index": 1,
            "obj_tile_base": 288,
            "obj_vram_address": "0x06012400",
            "palette_bank": 5,
        }
    ):
        raise ValueError("battle-effect group 5 independent build metadata mismatch")

    rebuilt = {
        variant: _rebuild_rom(base, content)
        for variant, content in graphics.items()
    }
    expected_rom_hashes = {
        "baseline": BASELINE_ROM_SHA256,
        "candidate": CANDIDATE_ROM_SHA256,
    }
    for variant in ("baseline", "candidate"):
        _verify_spec(root, raw, variant)
        row = build.get("variants", {}).get(variant, {})
        expected_row = {
            "rom_path": f"{variant}/{variant}.gba",
            "rom_sha256": expected_rom_hashes[variant],
            "rom_size": 0x1000000,
            "spec_path": f"{variant}/spec.json",
            "graphics_path": f"{variant}/group-05-graphics-4bpp.bin",
            "graphics_sha256": _sha256(graphics[variant]),
            "encoded_graphics_size": 1165,
            "graphics_allocation_offset": GRAPHICS_ALLOCATION_OFFSET,
            "patch_ledger": _expected_patch_ledger(graphics[variant]),
        }
        if row != expected_row or _sha256(rebuilt[variant]) != expected_rom_hashes[variant]:
            raise ValueError(
                f"battle-effect group 5 independent {variant} ROM reconstruction mismatch"
            )

    changed = _diff(rebuilt["baseline"], rebuilt["candidate"])
    isolation = build.get("isolation", {})
    if (
        isolation.get("decoded_offsets") != [0x200]
        or isolation.get("rom_changed_offsets") != changed
        or isolation.get("rom_changed_offset_count") != len(changed)
        or isolation.get("changed_rom_span") != [changed[0], changed[-1] + 1]
        or isolation.get("same_patch_topology") is not True
        or isolation.get("same_allocation_offsets") is not True
        or isolation.get("same_redirect_pointers") is not True
        or any(
            not GRAPHICS_ALLOCATION_OFFSET <= offset < GRAPHICS_ALLOCATION_OFFSET + 1165
            for offset in changed
        )
    ):
        raise ValueError("battle-effect group 5 independent ROM isolation mismatch")
    return graphics


def _runtime_provenance(raw: Path, variant: str, build: dict[str, Any]) -> None:
    audit = _json(raw / variant / "audit.json")
    guard = _json(raw / variant / "guard.json")
    if (
        audit != _json(raw / variant / "sentinel.json")
        or audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("evidence_mode") != "single-input"
        or audit.get("audit") != f"raw/{variant}/audit.json"
        or audit.get("build_manifest") != "toolchain/mgba-build-manifest.json"
        or audit.get("input_state") != INPUT_PATH.as_posix()
        or audit.get("output_png") != f"raw/{variant}/frame150.png"
        or audit.get("output_state") != f"raw/{variant}/frame150.ss9"
        or audit.get("replay_script") != "tools/mgba_single_input_replay.lua"
        or audit.get("sentinel") != f"raw/{variant}/sentinel.json"
        or audit.get("staged_rom") != f"runtime-only/{variant}/staged.gba"
        or audit.get("capture_frame") != 150
        or audit.get("inputs")
        != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("input_state_sha256") != INPUT_SHA256
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        or audit.get("staged_rom_sha256") != audit.get("rom_sha256")
        or audit.get("output_state_sha256")
        != _sha256_file(raw / variant / "frame150.ss9")
        or audit.get("output_png_sha256")
        != _sha256_file(raw / variant / "frame150.png")
        or audit.get("guard_summary_sha256")
        != _sha256_file(raw / variant / "guard.json")
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("protection_backend") != "posix-process-group"
        or guard.get("cwd") != "."
        or guard.get("command")
        != [
            "mGBA",
            "--script",
            "tools/mgba_single_input_replay.lua",
            f"runtime-only/{variant}/staged.gba",
        ]
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
        or any(value.startswith("/") for value in _strings(audit))
        or any(value.startswith("/") for value in _strings(guard))
    ):
        raise ValueError(
            f"battle-effect group 5 independent {variant} runtime provenance mismatch"
        )


def _verify(root: Path, artifact: Path) -> None:
    root = root.resolve()
    artifact = artifact.resolve()
    raw = artifact / "raw"
    expected_files = {
        Path("manifest.json"),
        Path("runtime-evidence.json"),
        *(Path("raw") / name for name in RAW_FILES),
    }
    actual_files = {
        path.relative_to(artifact) for path in artifact.rglob("*") if path.is_file()
    }
    if any(path.is_symlink() for path in artifact.rglob("*")):
        raise ValueError("battle-effect group 5 artifact must not contain symlinks")
    if actual_files != expected_files:
        raise ValueError("battle-effect group 5 artifact file set mismatch")
    for path in artifact.rglob("*.json"):
        if any(value.startswith("/") for value in _strings(_json(path))):
            raise ValueError("battle-effect group 5 artifact contains absolute paths")

    manifest = _json(artifact / "manifest.json")
    evidence = _json(artifact / "runtime-evidence.json")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_id") != "battle-effect-group5-pixel-ab-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("base_rom_sha256") != ROM_SHA256
        or manifest.get("parent")
        != {"path": INPUT_PATH.as_posix(), "sha256": INPUT_SHA256}
        or manifest.get("source_catalog") != CATALOG_PATH.as_posix()
        or manifest.get("source_catalog_sha256") != CATALOG_SHA256
        or manifest.get("payload_file") != "runtime-evidence.json"
        or manifest.get("payload_sha256")
        != _sha256_file(artifact / "runtime-evidence.json")
        or manifest.get("scope") != EXPECTED_SCOPE
        or manifest.get("verifier", {}).get("exit_code") != 0
        or manifest.get("verifier", {}).get("result")
        != {"errors": [], "verified": True}
    ):
        raise ValueError("battle-effect group 5 manifest contract mismatch")
    expected_hashes = {
        path.relative_to(artifact).as_posix(): _sha256_file(path)
        for path in sorted(artifact.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    if manifest.get("files") != expected_hashes:
        raise ValueError("battle-effect group 5 artifact file hash mismatch")
    if manifest.get("raw_files") != {
        name: _sha256_file(raw / name) for name in RAW_FILES
    }:
        raise ValueError("battle-effect group 5 raw file hash mismatch")
    if manifest.get("implementation_sha256") != {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }:
        raise ValueError("battle-effect group 5 implementation hash mismatch")
    if _sha256_file(root / INPUT_PATH) != INPUT_SHA256:
        raise ValueError("battle-effect group 5 input checkpoint hash mismatch")
    if _sha256_file(root / CATALOG_PATH) != CATALOG_SHA256:
        raise ValueError("battle-effect group 5 catalog hash mismatch")
    if _sha256_file(root / PALETTE_PATH) != PALETTE_SHA256:
        raise ValueError("battle-effect group 5 palette hash mismatch")

    build = _json(raw / "build-manifest.json")
    graphics = _verify_build(root, raw, build)

    for variant in ("baseline", "candidate"):
        _runtime_provenance(raw, variant, build)
    states = {
        variant: load_gba_state(raw / variant / "frame150.ss9")
        for variant in ("baseline", "candidate")
    }
    differences = {
        name: _diff(
            states["baseline"].read_memory(address, size),
            states["candidate"].read_memory(address, size),
        )
        for name, (address, size) in DOMAINS.items()
    }
    if differences != EXPECTED_DIFFERENCES:
        raise ValueError("battle-effect group 5 independent memory isolation mismatch")
    palette = (root / PALETTE_PATH).read_bytes()
    for variant in ("baseline", "candidate"):
        state = states[variant]
        rendered, _ = render_checkpoint(raw / variant / "frame150.ss9")
        if (
            state.read_memory(0x06012400, 3840) != graphics[variant]
            or state.read_memory(0x050002A0, 32) != palette
            or state.read_memory(0x07000008, 8).hex() != "3000a08030590000"
            or rendered != _rgb(raw / variant / "frame150.png")
        ):
            raise ValueError(
                f"battle-effect group 5 independent {variant} route mismatch"
            )
    baseline_rgb = _rgb(raw / "baseline/frame150.png")
    candidate_rgb = _rgb(raw / "candidate/frame150.png")
    if (
        _sha256(baseline_rgb) != BASELINE_RGB_SHA256
        or _sha256(candidate_rgb) != CANDIDATE_RGB_SHA256
        or _pixel_changes(baseline_rgb, candidate_rgb) != EXPECTED_PIXELS
    ):
        raise ValueError("battle-effect group 5 independent final pixel mismatch")
    input_state = load_gba_state(root / INPUT_PATH)
    if input_state.read_memory(0x06010000, 0x8000).find(graphics["baseline"]) >= 0:
        raise ValueError("battle-effect group 5 independent pre-load mismatch")

    if (
        evidence.get("schema") != SCHEMA
        or evidence.get("verified") is not True
        or evidence.get("edit") != build.get("edit")
        or evidence.get("input")
        != {
            "path": INPUT_PATH.as_posix(),
            "sha256": INPUT_SHA256,
            "event": {"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8},
            "capture_frame": 150,
            "resource_absent_before_input": True,
        }
        or evidence.get("runtime", {}).get("memory_differences") != differences
        or evidence.get("runtime", {}).get("graphics_vram_address") != "0x06012400"
        or evidence.get("runtime", {}).get("changed_vram_address") != "0x06012600"
        or evidence.get("runtime", {}).get("oam_entry") != 1
        or evidence.get("runtime", {}).get("oam_xy") != [160, 48]
        or evidence.get("runtime", {}).get("oam_tile") != 304
        or evidence.get("runtime", {}).get("palette_bank") != 5
        or evidence.get("runtime", {}).get("pixels", {}).get("changes")
        != EXPECTED_PIXELS
        or evidence.get("runtime", {}).get("renderer_exact") is not True
        or evidence.get("scope") != EXPECTED_SCOPE
    ):
        raise ValueError("battle-effect group 5 signed semantic evidence mismatch")


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        _verify(Path(root), Path(artifact))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
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
