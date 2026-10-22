#!/usr/bin/env python3
"""Analyze one accepted world-map GPU capture into a deterministic manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import tempfile
import uuid
from pathlib import Path
from typing import Any


SCHEMA = "world-map-runtime-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STATE_PATH = "artifacts/runtime-checkpoints/scenario-42-postbattle-world-map.ss9"
STATE_SHA256 = "35fce6be208aa50044bdaa2232eab5986d9ea76340bc08c68b107f34b5a5b5a1"
STATIC_MANIFEST_PATH = "artifacts/world-map-backgrounds-v1/manifest.json"
STATIC_MANIFEST_SHA256 = (
    "b9b879841b7605af80e143a9f2f9bbe2e64754d6390b708033f92cc831bd4dd3"
)
CAPTURE_HASHES = {
    "audit.json": "307c25f37c6cd825f064946e2c5e5d1d09760eab335905f95a8af4e243a43026",
    "frame.png": "21439923ef315e7bd00607088858c180646af0f13cbb26ac97bd5c0a1185863d",
    "guard.json": "138d090b82e8a655e0146b5ec1b4447f87a2454a1875e7f8cfe2e2ba0ef0dc0d",
    "io.bin": "5b2230984638a67e68115e9fe09b5a316ff24de72cd0dcefed24bf1417069aa1",
    "oam.bin": "b3c33732982b1225e5a88b1b89ae3d1340bf8598647d28f899e1d437266c4544",
    "pram.bin": "abb77e6d4f67d6df9a295f174868546de5e1ecdafaf36d6892f49447c9779418",
    "vram.bin": "0b207f2202daa3ba9ba72e7be080d10479c308ce7aad7ecc0cb9aaa3fe1eb50c",
}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _bgr555_rgb(value: int) -> list[int]:
    components = (value & 31, (value >> 5) & 31, (value >> 10) & 31)
    return [component << 3 | component >> 2 for component in components]


def _expand_2bpp(source: bytes, base_index: int) -> bytes:
    if len(source) != 32 or base_index not in (0, 4, 8, 12):
        raise ValueError("invalid dialogue glyph expansion")
    output = bytearray()
    for packed in source:
        pixels = [
            base_index | ((packed >> shift) & 3)
            for shift in (0, 2, 4, 6)
        ]
        output.extend(
            (
                pixels[0] | pixels[1] << 4,
                pixels[2] | pixels[3] << 4,
            )
        )
    return bytes(output)


def _bg_control(raw: int) -> dict[str, Any]:
    return {
        "control": f"0x{raw:04X}",
        "priority": raw & 3,
        "character_base_block": (raw >> 2) & 3,
        "bits_per_pixel": 8 if raw & 0x80 else 4,
        "screen_base_block": (raw >> 8) & 31,
        "size": (raw >> 14) & 3,
    }


def validate_output_target(root: Path, output_dir: Path) -> Path:
    root = root.resolve()
    requested = output_dir.expanduser()
    if requested.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = requested.resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be the repository or its ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("existing output target is not a directory")
        try:
            existing = json.loads(
                (target / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            ) from error
        if existing.get("schema") != SCHEMA:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            )
    return target


def _replace_output(output_dir: Path, files: dict[str, bytes]) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent)
    )
    backup: Path | None = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if output_dir.exists():
            backup = output_dir.parent / (
                f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            )
            output_dir.rename(backup)
        try:
            temporary.rename(output_dir)
        except BaseException:
            if backup is not None and backup.exists() and not output_dir.exists():
                backup.rename(output_dir)
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and output_dir.exists():
            shutil.rmtree(backup)


def export_artifact(
    root: Path | str,
    capture_dir: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    capture_dir = Path(capture_dir).resolve()
    output_dir = validate_output_target(root, Path(output_dir))
    rom = (root / "rom/base.gba").read_bytes()
    if _hash(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    state = root / STATE_PATH
    if _hash(state.read_bytes()) != STATE_SHA256:
        raise ValueError("world-map checkpoint SHA-256 mismatch")
    static_raw = (root / STATIC_MANIFEST_PATH).read_bytes()
    if _hash(static_raw) != STATIC_MANIFEST_SHA256:
        raise ValueError("static world-map manifest SHA-256 mismatch")
    static = json.loads(static_raw.decode("utf-8"))
    if static.get("schema") != "world-map-backgrounds-v1":
        raise ValueError("static world-map manifest schema mismatch")

    capture_files: dict[str, bytes] = {}
    capture_metadata: dict[str, dict[str, Any]] = {}
    for name, expected_hash in CAPTURE_HASHES.items():
        data = (capture_dir / name).read_bytes()
        if _hash(data) != expected_hash:
            raise ValueError(f"capture SHA-256 mismatch: {name}")
        capture_files[name] = data
        capture_metadata[name] = {
            "size": len(data),
            "sha256": expected_hash,
        }
    audit = json.loads(capture_files["audit.json"].decode("utf-8"))
    guard = json.loads(capture_files["guard.json"].decode("utf-8"))
    if (
        audit.get("status") != "capture-complete"
        or audit.get("input_state_sha256") != STATE_SHA256
    ):
        raise ValueError("capture audit identity mismatch")
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("degraded") is not False
        or guard.get("protection_backend") != "posix-process-group"
    ):
        raise ValueError("capture guard did not complete safely")

    io = capture_files["io.bin"]
    vram = capture_files["vram.bin"]
    oam = capture_files["oam.bin"]
    pram = capture_files["pram.bin"]
    if (len(io), len(vram), len(oam), len(pram)) != (
        0x400,
        0x18000,
        0x400,
        0x400,
    ):
        raise ValueError("capture memory domain size mismatch")

    display_control = struct.unpack_from("<H", io, 0)[0]
    enabled_backgrounds = [
        bg for bg in range(4) if display_control & (1 << (8 + bg))
    ]
    bg_controls = [
        struct.unpack_from("<H", io, 8 + bg * 2)[0] for bg in range(4)
    ]
    bg_scroll = [
        [
            struct.unpack_from("<H", io, 0x10 + bg * 4)[0] & 0x1FF,
            struct.unpack_from("<H", io, 0x12 + bg * 4)[0] & 0x1FF,
        ]
        for bg in range(4)
    ]
    if display_control != 0x1940 or enabled_backgrounds != [0, 3]:
        raise ValueError("unexpected world-map display control")
    if bg_controls[0] != 0x0086 or bg_controls[3] != 0x030C:
        raise ValueError("unexpected world-map BG controls")

    page = static["pages"][0]
    background = page["background"]
    graphics = (
        root / "artifacts/world-map-backgrounds-v1" / background["graphics_file"]
    ).read_bytes()
    palette = (
        root / "artifacts/world-map-backgrounds-v1" / background["palette_file"]
    ).read_bytes()
    tilemap = (
        root / "artifacts/world-map-backgrounds-v1" / background["tilemap_file"]
    ).read_bytes()
    graphics_match = vram[0x4000 : 0x4000 + len(graphics)] == graphics
    palette_match = pram[: len(palette)] == palette
    matching_rows = sum(
        vram[y * 64 : y * 64 + 60] == tilemap[y * 60 : (y + 1) * 60]
        for y in range(20)
    )
    if not graphics_match or not palette_match or matching_rows != 20:
        raise ValueError("page zero background does not match static artifact")

    glyph_tiles = bytearray()
    codes: list[str] = []
    for glyph in page["label"]["glyphs"]:
        codes.append(glyph["code"])
        pointer = int(glyph["source_pointer"], 16) - 0x08000000
        source = rom[pointer : pointer + 32]
        if _hash(source) != glyph["source_sha256"]:
            raise ValueError("label glyph source hash mismatch")
        glyph_tiles.extend(_expand_2bpp(source, 8))
    runtime_tiles = vram[0xC000 : 0xC000 + len(glyph_tiles)]
    label_tiles_match = runtime_tiles == bytes(glyph_tiles)
    screen_base = 3 * 0x800
    tile_entries = [
        [
            struct.unpack_from(
                "<H",
                vram,
                screen_base + (row * 32 + column) * 2,
            )[0]
            for column in range(4, 8)
        ]
        for row in (1, 2)
    ]
    expected_entries = [
        [0xE000, 0xE002, 0xE004, 0xE006],
        [0xE001, 0xE003, 0xE005, 0xE007],
    ]
    if tile_entries != expected_entries or not label_tiles_match:
        raise ValueError("runtime label layout does not match ROM glyphs")
    palette_entries = []
    for index in range(232, 236):
        color = struct.unpack_from("<H", pram, index * 2)[0]
        palette_entries.append(
            {
                "global_index": index,
                "bgr555": f"0x{color:04X}",
                "rgb888": _bgr555_rgb(color),
            }
        )

    active_objects = []
    for object_id in range(128):
        attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, object_id * 8)
        affine = bool(attr0 & 0x0100)
        disabled = not affine and bool(attr0 & 0x0200)
        if not disabled:
            active_objects.append((object_id, attr0, attr1, attr2))
    if len(active_objects) != 1:
        raise ValueError("unexpected active OAM object count")
    object_id, attr0, attr1, attr2 = active_objects[0]
    shape = (attr0 >> 14) & 3
    size = (attr1 >> 14) & 3
    dimensions = {
        (2, 0): [16, 8],
    }.get((shape, size))
    if dimensions is None:
        raise ValueError("unexpected selection cursor dimensions")

    manifest = {
        "schema": SCHEMA,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
        },
        "static_dependency": {
            "manifest": STATIC_MANIFEST_PATH,
            "manifest_sha256": STATIC_MANIFEST_SHA256,
            "page_id": 0,
        },
        "capture": {
            "path": "artifacts/world-map-gpu-captures/s42-page0",
            "input_state": STATE_PATH,
            "input_state_sha256": STATE_SHA256,
            "cycle": audit["cycle"],
            "files": capture_metadata,
            "guard": {
                "completion_trigger": guard["completion_trigger"],
                "reason": guard["reason"],
                "exit_code": guard["exit_code"],
                "degraded": guard["degraded"],
                "protection_backend": guard["protection_backend"],
            },
        },
        "registers": {
            "display_control": f"0x{display_control:04X}",
            "background_controls": {
                str(bg): {
                    **_bg_control(bg_controls[bg]),
                    "scroll": bg_scroll[bg],
                    "enabled": bg in enabled_backgrounds,
                }
                for bg in range(4)
            },
        },
        "page_zero_background": {
            "page_id": 0,
            "display_control": f"0x{display_control:04X}",
            "enabled_backgrounds": enabled_backgrounds,
            "obj_enabled": bool(display_control & 0x1000),
            "hardware": {
                "bg": 0,
                "control": "0x0086",
                "priority": 2,
                "character_base": "0x06004000",
                "screen_base": "0x06000000",
                "bits_per_pixel": 8,
                "scroll": bg_scroll[0],
            },
            "graphics_vram_match": "exact",
            "palette_pram_match": "exact",
            "tilemap_rows_matching": matching_rows,
            "tilemap_dimensions": [30, 20],
            "visible_dimensions": [240, 160],
        },
        "page_zero_label": {
            "codes": codes,
            "background": 3,
            "bg_control": "0x030C",
            "priority": 0,
            "character_base": "0x0600C000",
            "screen_base": "0x06001800",
            "screen_position": [32, 8],
            "dimensions": [32, 16],
            "tile_indices": [[0, 2, 4, 6], [1, 3, 5, 7]],
            "palette_bank": 14,
            "tile_pixel_indices": [8, 9, 10, 11],
            "global_palette_indices": [232, 233, 234, 235],
            "palette": palette_entries,
            "all_runtime_tiles_match_rom_glyph_sources": label_tiles_match,
        },
        "selection_cursor": {
            "active_object_count": 1,
            "object_id": object_id,
            "position": [attr1 & 0x1FF, attr0 & 0xFF],
            "dimensions": dimensions,
            "tile_index": attr2 & 0x03FF,
            "priority": (attr2 >> 10) & 3,
            "palette_bank": (attr2 >> 12) & 15,
        },
        "scope": {
            "page_zero_final_composition_captured": True,
            "page_zero_background_binding_complete": True,
            "page_zero_label_runtime_layout_complete": True,
            "page_zero_label_palette_complete": True,
            "page_zero_selection_cursor_oam_complete": True,
            "pages_one_and_two_runtime_composition_complete": False,
            "selection_transition_timing_complete": False,
            "unlock_state_matrix_complete": False,
        },
    }
    files = {
        "manifest.json": (
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
    }
    _replace_output(output_dir, files)
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=Path("artifacts/world-map-gpu-captures/s42-page0"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/world-map-runtime-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_artifact(args.root, args.capture_dir, args.output_dir)
    print(json.dumps(manifest["scope"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
