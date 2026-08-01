#!/usr/bin/env python3
"""Independently verify the natural menu-portrait single-pixel A/B artifact."""

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
from tools.verify_menu_portrait_writeback_audit import _encode_lz77


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/menu-portraits-v1/manifest.json")
CATALOG_SHA256 = "cd54c20d774a2aa69c7a41db396ca344157320882602b03a00ccd83851a791b3"
INPUT_PATH = Path("artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-9.ss9")
INPUT_SHA256 = "5635916176865f63b12154ea1c68e202393baaf6e1427473fb6be8a84b18eba8"
PAIR_OFFSET = 0x5A4E14
GRAPHICS_OFFSET = 0xA80000
PALETTE_OFFSET = 0xA80CEC
STREAM_OFFSET = 5184
COMPONENTS = (
    (64, 64, 16, 16, 0, 256),
    (64, 32, 16, 32, 256, 512),
    (64, 0, 16, 32, 768, 512),
    (32, 64, 32, 16, 1280, 512),
    (0, 64, 32, 16, 1792, 512),
    (0, 0, 64, 64, 2304, 4096),
)
RAW_FILES = (
    "build-manifest.json",
    "baseline/audit.json",
    "baseline/frame80.png",
    "baseline/frame80.ss9",
    "baseline/guard.json",
    "baseline/portrait.png",
    "baseline/sentinel.json",
    "baseline/spec.json",
    "candidate/audit.json",
    "candidate/frame80.png",
    "candidate/frame80.ss9",
    "candidate/guard.json",
    "candidate/portrait.png",
    "candidate/sentinel.json",
    "candidate/spec.json",
)
IMPLEMENTATION_PATHS = (
    "tools/build_menu_portrait_pixel_ab.py",
    "tools/export_menu_portrait_pixel_ab_evidence.py",
    "tools/verify_menu_portrait_pixel_ab_evidence.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/build_mod.py",
    "tools/image_resource_regions.py",
    "tools/patch_safety.py",
    "tools/rom_layout.py",
    "tools/import_menu_portrait_relocations.py",
    "tools/import_menu_portraits.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
)
EXPECTED_SCOPE = {
    "natural_show_portrait_load": True,
    "production_relocation_route": True,
    "row_1_variant_0_single_pixel": True,
    "all_311_portraits_runtime_verified": False,
    "all_portrait_transitions_runtime_verified": False,
    "physical_gba_verified": False,
}
DOMAINS = {
    "IO": (0x04000000, 0x400),
    "PRAM": (0x05000000, 0x400),
    "VRAM": (0x06000000, 0x18000),
    "OAM": (0x07000000, 0x400),
    "IWRAM": (0x03000000, 0x8000),
    "EWRAM": (0x02000000, 0x40000),
}
EXPECTED_DIFFERENCES = {
    "EWRAM": [0x3CC0],
    "IWRAM": [],
    "IO": [],
    "PRAM": [],
    "VRAM": [0x11440],
    "OAM": [],
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _diff(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("portrait independent domains differ in size")
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


def _portrait_stream(pixels: bytes) -> bytes:
    if len(pixels) != 6400:
        raise ValueError("portrait independent canvas size mismatch")
    output = bytearray(6400)
    covered = bytearray(6400)
    for x, y, width, height, target_offset, target_size in COMPONENTS:
        if width * height != target_size:
            raise ValueError("portrait independent component size mismatch")
        tiles_wide = width // 8
        for local_y in range(height):
            tile_y, pixel_y = divmod(local_y, 8)
            for local_x in range(width):
                tile_x, pixel_x = divmod(local_x, 8)
                source = (y + local_y) * 80 + x + local_x
                target = (
                    target_offset
                    + (tile_y * tiles_wide + tile_x) * 64
                    + pixel_y * 8
                    + pixel_x
                )
                if covered[target]:
                    raise ValueError("portrait independent components overlap")
                output[target] = pixels[source]
                covered[target] = 1
    if not all(covered):
        raise ValueError("portrait independent components leave gaps")
    return bytes(output)


def _rgb555(red: int, green: int, blue: int) -> int:
    return (
        (red * 31 + 127) // 255
        | ((green * 31 + 127) // 255) << 5
        | ((blue * 31 + 127) // 255) << 10
    )


def _portrait(path: Path, original_palette: bytes) -> tuple[bytes, bytes]:
    with Image.open(path) as image:
        image.load()
        if (
            image.mode != "P"
            or image.size != (80, 80)
            or image.info.get("transparency") != 0
        ):
            raise ValueError("portrait independent PNG contract mismatch")
        pixels = image.tobytes()
        palette = image.getpalette()
        if palette is None or max(pixels) >= 64:
            raise ValueError("portrait independent palette contract mismatch")
    encoded = bytearray()
    for index in range(64):
        rgb = palette[index * 3 : index * 3 + 3]
        value = _rgb555(*rgb)
        original = int.from_bytes(original_palette[index * 2 : index * 2 + 2], "little")
        encoded.extend(((value & 0x7FFF) | (original & 0x8000)).to_bytes(2, "little"))
    return _portrait_stream(pixels), bytes(encoded)


def _rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.size != (240, 160):
            raise ValueError("portrait runtime PNG dimensions mismatch")
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


def _catalog_contract(root: Path, base: bytes) -> tuple[dict[str, Any], bytes]:
    catalog_path = root / CATALOG_PATH
    if _sha256_file(catalog_path) != CATALOG_SHA256:
        raise ValueError("portrait independent catalog hash mismatch")
    catalog = _json(catalog_path)
    resource = next(
        row for row in catalog["unique_resources"] if row["resource_id"] == 0
    )
    aliases = [row for row in catalog["portraits"] if row["resource_id"] == 0]
    target = next(
        row
        for row in aliases
        if row["portrait_id"] == 1
        and row["variant"] == 0
        and row["pair_file_offset"] == PAIR_OFFSET
    )
    if len(aliases) != 36 or target["png"] != "portrait_01_variant_0.png":
        raise ValueError("portrait independent resource alias mismatch")
    palette_offset = resource["palette_file_offset"]
    palette = base[palette_offset : palette_offset + 128]
    if (
        _sha256(palette) != resource["palette_sha256"]
        or int.from_bytes(base[PAIR_OFFSET : PAIR_OFFSET + 4], "little")
        != int(resource["gfx_pointer"], 0)
        or int.from_bytes(base[PAIR_OFFSET + 4 : PAIR_OFFSET + 8], "little")
        != int(resource["palette_pointer"], 0)
    ):
        raise ValueError("portrait independent source provenance mismatch")
    return resource, palette


def _rebuild_rom(
    base: bytes,
    stream: bytes,
    palette: bytes,
) -> bytes:
    encoded = _encode_lz77(stream)
    if len(encoded) != 3306:
        raise ValueError("portrait independent encoded size mismatch")
    rom = bytearray(base + bytes([0xFF]) * (0x1000000 - len(base)))
    rom[GRAPHICS_OFFSET : GRAPHICS_OFFSET + len(encoded)] = encoded
    rom[PALETTE_OFFSET : PALETTE_OFFSET + 128] = palette
    rom[PAIR_OFFSET : PAIR_OFFSET + 4] = (0x08A80000).to_bytes(4, "little")
    rom[PAIR_OFFSET + 4 : PAIR_OFFSET + 8] = (0x08A80CEC).to_bytes(4, "little")
    return bytes(rom)


def _verify_audit(raw: Path, variant: str, build: dict[str, Any]) -> None:
    audit = _json(raw / variant / "audit.json")
    sentinel = _json(raw / variant / "sentinel.json")
    guard = _json(raw / variant / "guard.json")
    if audit != sentinel:
        raise ValueError("portrait independent audit/sentinel mismatch")
    if (
        audit.get("success") is not True
        or audit.get("status") != "capture-complete"
        or audit.get("inputs")
        != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
        or audit.get("input_state_sha256") != INPUT_SHA256
        or audit.get("output_state_sha256") != _sha256_file(raw / variant / "frame80.ss9")
        or audit.get("output_png_sha256") != _sha256_file(raw / variant / "frame80.png")
        or audit.get("guard_summary_sha256") != _sha256_file(raw / variant / "guard.json")
        or audit.get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("pgid_clean") is not True
        or audit.get("runtime_residue", {}).get("mgba_listener_clean") is not True
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("child_pid") != audit.get("child_pgid")
        or guard.get("peak_tree_rss_mib") != audit.get("peak_tree_rss_mib")
    ):
        raise ValueError("portrait independent runtime provenance mismatch")


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
        path.relative_to(artifact)
        for path in artifact.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("portrait independent artifact file set mismatch")

    manifest = _json(artifact / "manifest.json")
    evidence = _json(artifact / "runtime-evidence.json")
    verifier = manifest.get("verifier")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != "menu-portrait-pixel-ab-runtime-v1"
        or manifest.get("artifact_id") != "menu-portrait-pixel-ab-v1"
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
        or not isinstance(verifier, dict)
        or verifier.get("exit_code") != 0
        or verifier.get("command")
        != [
            "python3",
            "tools/verify_menu_portrait_pixel_ab_evidence.py",
            "--root",
            ".",
            "--artifact",
            "artifacts/menu-portrait-pixel-ab-v1",
        ]
        or verifier.get("result") != {"errors": [], "verified": True}
        or evidence.get("schema") != "menu-portrait-pixel-ab-runtime-v1"
        or evidence.get("verified") is not True
        or evidence.get("scope") != EXPECTED_SCOPE
    ):
        raise ValueError("portrait independent manifest/evidence contract mismatch")
    expected_inventory = {
        path.as_posix(): _sha256_file(artifact / path)
        for path in sorted(expected_files - {Path("manifest.json")})
    }
    if manifest.get("files") != expected_inventory:
        raise ValueError("portrait independent promotion file hash mismatch")
    if manifest.get("raw_files") != {
        name: _sha256_file(raw / name) for name in RAW_FILES
    }:
        raise ValueError("portrait independent raw file hash mismatch")
    if manifest.get("implementation_sha256") != {
        path: _sha256_file(root / path) for path in IMPLEMENTATION_PATHS
    }:
        raise ValueError("portrait independent implementation hash mismatch")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("portrait independent base ROM mismatch")
    resource, original_palette = _catalog_contract(root, base)
    build = _json(raw / "build-manifest.json")
    if (
        build.get("schema") != "menu-portrait-pixel-ab-build-v1"
        or build.get("input_state") != INPUT_PATH.as_posix()
        or build.get("input_state_sha256") != INPUT_SHA256
        or build.get("edit")
        != {
            "portrait_id": 1,
            "variant": 0,
            "resource_id": 0,
            "pair_pointer_offset": PAIR_OFFSET,
            "canvas_xy": [40, 40],
            "canvas_byte_offset": 3240,
            "stream_byte_offset": STREAM_OFFSET,
            "before_index": 52,
            "after_index": 14,
        }
        or set(build.get("variants", {})) != {"baseline", "candidate"}
    ):
        raise ValueError("portrait independent build manifest mismatch")

    streams: dict[str, bytes] = {}
    palettes: dict[str, bytes] = {}
    for variant in ("baseline", "candidate"):
        stream, palette = _portrait(raw / variant / "portrait.png", original_palette)
        streams[variant] = stream
        palettes[variant] = palette
        row = build["variants"][variant]
        rebuilt = _rebuild_rom(base, stream, palette)
        if (
            _sha256(stream) != row["graphics_sha256"]
            or _sha256(palette) != row["palette_sha256"]
            or _sha256(rebuilt) != row["rom_sha256"]
            or len(row.get("patch_ledger", [])) != 4
            or [patch["offset"] for patch in row["patch_ledger"]]
            != [GRAPHICS_OFFSET, PALETTE_OFFSET, PAIR_OFFSET, PAIR_OFFSET + 4]
        ):
            raise ValueError(f"portrait independent {variant} ROM rebuild mismatch")
        _verify_audit(raw, variant, build)
    if (
        _diff(streams["baseline"], streams["candidate"]) != [STREAM_OFFSET]
        or streams["baseline"][STREAM_OFFSET] != 52
        or streams["candidate"][STREAM_OFFSET] != 14
        or palettes["baseline"] != palettes["candidate"]
        or palettes["baseline"] != original_palette
    ):
        raise ValueError("portrait independent authored isolation mismatch")

    input_state = load_gba_state(root / INPUT_PATH)
    if (
        _sha256_file(root / INPUT_PATH) != INPUT_SHA256
        or input_state.read_u32(0x030011F0) != 0x08031F42
        or base.find(bytes.fromhex("02000100"), 0x31F42, 0x32000) != 0x31F6E
        or input_state.read_memory(0x06010000, 6400) in streams.values()
    ):
        raise ValueError("portrait independent natural pre-load boundary mismatch")

    states = {
        variant: load_gba_state(raw / variant / "frame80.ss9")
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
        raise ValueError("portrait independent runtime memory isolation mismatch")
    for variant in ("baseline", "candidate"):
        state = states[variant]
        screenshot = _rgb(raw / variant / "frame80.png")
        if (
            state.read_memory(0x06010000, 6400) != streams[variant]
            or state.read_memory(0x05000200, 128) != original_palette
            or render_checkpoint(raw / variant / "frame80.ss9")[0] != screenshot
        ):
            raise ValueError(f"portrait independent {variant} runtime route mismatch")
    if states["baseline"].read_memory(0x07000008, 48) != states[
        "candidate"
    ].read_memory(0x07000008, 48):
        raise ValueError("portrait independent OAM changed")
    baseline_rgb = _rgb(raw / "baseline/frame80.png")
    candidate_rgb = _rgb(raw / "candidate/frame80.png")
    changes = _pixel_changes(baseline_rgb, candidate_rgb)
    expected_changes = [
        {
            "x": 56,
            "y": 48,
            "before_rgb": [239, 189, 165],
            "after_rgb": [99, 74, 57],
        }
    ]
    if changes != expected_changes:
        raise ValueError("portrait independent final pixel mismatch")

    if (
        evidence.get("edit") != build["edit"]
        or evidence.get("runtime", {}).get("memory_differences") != differences
        or evidence.get("runtime", {}).get("pixels", {}).get("changes") != changes
        or evidence.get("runtime", {}).get("pixels", {}).get("count") != 1
        or evidence.get("runtime", {}).get("pixels", {}).get("bbox") != [56, 48, 56, 48]
        or evidence.get("runtime", {}).get("baseline_vram_byte") != 52
        or evidence.get("runtime", {}).get("candidate_vram_byte") != 14
        or evidence.get("runtime", {}).get("baseline_ewram_byte") != 52
        or evidence.get("runtime", {}).get("candidate_ewram_byte") != 14
        or evidence.get("input", {}).get("target_absent_before_input") is not True
        or set(evidence.get("runs", {})) != {"baseline", "candidate"}
    ):
        raise ValueError("portrait independent semantic evidence mismatch")


def verify_evidence(root: Path, artifact: Path) -> dict[str, Any]:
    errors = []
    try:
        _verify(Path(root), Path(artifact))
    except Exception as error:  # verifier reports all fail-closed errors uniformly
        errors.append(str(error))
    return {"verified": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = verify_evidence(args.root, args.artifact)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
