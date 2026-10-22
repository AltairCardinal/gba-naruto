#!/usr/bin/env python3
"""Independently verify the accepted page-zero world-map GPU evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_HASH = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STATE_RELATIVE = "artifacts/runtime-checkpoints/scenario-42-postbattle-world-map.ss9"
STATE_HASH = "35fce6be208aa50044bdaa2232eab5986d9ea76340bc08c68b107f34b5a5b5a1"
STATIC_RELATIVE = "artifacts/world-map-backgrounds-v1/manifest.json"
STATIC_HASH = "b9b879841b7605af80e143a9f2f9bbe2e64754d6390b708033f92cc831bd4dd3"
RAW_HASHES = {
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


def _rgb(value: int) -> list[int]:
    values = (value & 31, (value >> 5) & 31, (value >> 10) & 31)
    return [(component << 3) | (component >> 2) for component in values]


def _expand(source: bytes) -> bytes:
    output = bytearray()
    for packed in source:
        pixels = [8 | ((packed >> shift) & 3) for shift in (0, 2, 4, 6)]
        output.extend(
            (
                pixels[0] | pixels[1] << 4,
                pixels[2] | pixels[3] << 4,
            )
        )
    return bytes(output)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path.name}")
    return payload


def verify_artifact(
    root: Path | str,
    capture_dir: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    capture_dir = Path(capture_dir).resolve()
    artifact_dir = Path(artifact_dir).resolve()
    errors: list[str] = []
    try:
        rom = (root / "rom/base.gba").read_bytes()
        if _hash(rom) != ROM_HASH:
            raise ValueError("base ROM SHA-256 mismatch")
        if _hash((root / STATE_RELATIVE).read_bytes()) != STATE_HASH:
            raise ValueError("checkpoint SHA-256 mismatch")
        static_raw = (root / STATIC_RELATIVE).read_bytes()
        if _hash(static_raw) != STATIC_HASH:
            raise ValueError("static manifest SHA-256 mismatch")
        static = json.loads(static_raw.decode("utf-8"))
        if static.get("schema") != "world-map-backgrounds-v1":
            raise ValueError("static manifest schema mismatch")
        raw = {}
        for name, digest in RAW_HASHES.items():
            data = (capture_dir / name).read_bytes()
            if _hash(data) != digest:
                raise ValueError(f"capture SHA-256 mismatch: {name}")
            raw[name] = data
        manifest = _read_json(artifact_dir / "manifest.json")
        actual_files = {
            path.relative_to(artifact_dir).as_posix()
            for path in artifact_dir.rglob("*")
            if path.is_file()
        }
        if actual_files != {"manifest.json"}:
            raise ValueError("runtime artifact file set mismatch")
        audit = json.loads(raw["audit.json"].decode("utf-8"))
        guard = json.loads(raw["guard.json"].decode("utf-8"))
        io, oam, pram, vram = (
            raw["io.bin"],
            raw["oam.bin"],
            raw["pram.bin"],
            raw["vram.bin"],
        )
        if (len(io), len(oam), len(pram), len(vram)) != (
            0x400,
            0x400,
            0x400,
            0x18000,
        ):
            raise ValueError("GPU domain size mismatch")
        if (
            audit.get("status") != "capture-complete"
            or audit.get("input_state_sha256") != STATE_HASH
        ):
            raise ValueError("capture audit mismatch")
        if (
            guard.get("reason") != "completed"
            or guard.get("exit_code") != 0
            or guard.get("completion_trigger") != "success-marker"
            or guard.get("degraded") is not False
            or guard.get("protection_backend") != "posix-process-group"
        ):
            raise ValueError("guard evidence mismatch")

        dispcnt = struct.unpack_from("<H", io, 0)[0]
        controls = [struct.unpack_from("<H", io, 8 + index * 2)[0] for index in range(4)]
        scroll = [
            [
                struct.unpack_from("<H", io, 0x10 + index * 4)[0] & 0x1FF,
                struct.unpack_from("<H", io, 0x12 + index * 4)[0] & 0x1FF,
            ]
            for index in range(4)
        ]
        enabled = [index for index in range(4) if dispcnt & (1 << (8 + index))]
        if dispcnt != 0x1940 or controls[0] != 0x0086 or controls[3] != 0x030C:
            raise ValueError("world-map register mismatch")

        page = static["pages"][0]
        background = page["background"]
        artifact_root = root / "artifacts/world-map-backgrounds-v1"
        graphics = (artifact_root / background["graphics_file"]).read_bytes()
        palette = (artifact_root / background["palette_file"]).read_bytes()
        tilemap = (artifact_root / background["tilemap_file"]).read_bytes()
        rows = sum(
            vram[y * 64 : y * 64 + 60] == tilemap[y * 60 : (y + 1) * 60]
            for y in range(20)
        )
        if (
            vram[0x4000 : 0x4000 + len(graphics)] != graphics
            or pram[: len(palette)] != palette
            or rows != 20
        ):
            raise ValueError("runtime background mismatch")

        glyph_bytes = bytearray()
        codes = []
        for glyph in page["label"]["glyphs"]:
            codes.append(glyph["code"])
            offset = int(glyph["source_pointer"], 16) - 0x08000000
            source = rom[offset : offset + 32]
            if _hash(source) != glyph["source_sha256"]:
                raise ValueError("glyph source mismatch")
            glyph_bytes.extend(_expand(source))
        if vram[0xC000 : 0xC100] != bytes(glyph_bytes):
            raise ValueError("runtime glyph tile mismatch")
        label_entries = [
            [
                struct.unpack_from(
                    "<H",
                    vram,
                    0x1800 + (row * 32 + column) * 2,
                )[0]
                for column in range(4, 8)
            ]
            for row in (1, 2)
        ]
        if label_entries != [
            [0xE000, 0xE002, 0xE004, 0xE006],
            [0xE001, 0xE003, 0xE005, 0xE007],
        ]:
            raise ValueError("runtime label tilemap mismatch")
        palette_entries = []
        for index in range(232, 236):
            color = struct.unpack_from("<H", pram, index * 2)[0]
            palette_entries.append(
                {
                    "global_index": index,
                    "bgr555": f"0x{color:04X}",
                    "rgb888": _rgb(color),
                }
            )

        objects = []
        for object_id in range(128):
            attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, object_id * 8)
            if not (not (attr0 & 0x0100) and (attr0 & 0x0200)):
                objects.append((object_id, attr0, attr1, attr2))
        if len(objects) != 1:
            raise ValueError("active OAM count mismatch")
        object_id, attr0, attr1, attr2 = objects[0]

        expected_sections = {
            "schema": "world-map-runtime-v1",
            "rom": {"path": "rom/base.gba", "sha256": ROM_HASH},
            "static_dependency": {
                "manifest": STATIC_RELATIVE,
                "manifest_sha256": STATIC_HASH,
                "page_id": 0,
            },
            "page_zero_background": {
                "page_id": 0,
                "display_control": "0x1940",
                "enabled_backgrounds": enabled,
                "obj_enabled": bool(dispcnt & 0x1000),
                "hardware": {
                    "bg": 0,
                    "control": "0x0086",
                    "priority": 2,
                    "character_base": "0x06004000",
                    "screen_base": "0x06000000",
                    "bits_per_pixel": 8,
                    "scroll": scroll[0],
                },
                "graphics_vram_match": "exact",
                "palette_pram_match": "exact",
                "tilemap_rows_matching": rows,
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
                "all_runtime_tiles_match_rom_glyph_sources": True,
            },
            "selection_cursor": {
                "active_object_count": 1,
                "object_id": object_id,
                "position": [attr1 & 0x1FF, attr0 & 0xFF],
                "dimensions": [16, 8],
                "tile_index": attr2 & 0x3FF,
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
        for key, expected in expected_sections.items():
            if manifest.get(key) != expected:
                raise ValueError(f"manifest section mismatch: {key}")
        capture = manifest.get("capture", {})
        if (
            capture.get("path") != "artifacts/world-map-gpu-captures/s42-page0"
            or capture.get("input_state") != STATE_RELATIVE
            or capture.get("input_state_sha256") != STATE_HASH
            or capture.get("cycle") != audit["cycle"]
            or capture.get("files")
            != {
                name: {
                    "size": len(raw[name]),
                    "sha256": digest,
                }
                for name, digest in RAW_HASHES.items()
            }
            or capture.get("guard")
            != {
                "completion_trigger": "success-marker",
                "reason": "completed",
                "exit_code": 0,
                "degraded": False,
                "protection_backend": "posix-process-group",
            }
        ):
            raise ValueError("capture manifest section mismatch")
        registers = manifest.get("registers", {})
        if registers.get("display_control") != "0x1940":
            raise ValueError("register manifest mismatch")
        for index, raw_control in enumerate(controls):
            entry = registers.get("background_controls", {}).get(str(index), {})
            expected = {
                "control": f"0x{raw_control:04X}",
                "priority": raw_control & 3,
                "character_base_block": (raw_control >> 2) & 3,
                "bits_per_pixel": 8 if raw_control & 0x80 else 4,
                "screen_base_block": (raw_control >> 8) & 31,
                "size": (raw_control >> 14) & 3,
                "scroll": scroll[index],
                "enabled": index in enabled,
            }
            if entry != expected:
                raise ValueError(f"BG{index} register metadata mismatch")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "verified": not errors,
        "page_count": 1 if not errors else 0,
        "errors": errors,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=Path("artifacts/world-map-gpu-captures/s42-page0"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/world-map-runtime-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = verify_artifact(args.root, args.capture_dir, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
