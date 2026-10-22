#!/usr/bin/env python3
"""Independently verify the derived 79-entry battle visual catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TILE_MANIFEST = Path("artifacts/tile-assets-bg-v2/manifest.json")
GLYPH_MANIFEST = Path("artifacts/battle-presentation-glyphs-v1/manifest.json")
TILE_SHA256 = "1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749"
GLYPH_SHA256 = "ecc44fde0d886b75397d34181112f5b86dbb791b09e3b85797e9b4013f4e74a7"
FORMULA = (
    "state.message_id = u8(input_id - 1); "
    "descriptor = 0x085A320C + state.message_id * 0x44; "
    "message = u32[0x085A2B08 + state.message_id * 4]"
)
CODE_SLICES = (
    {
        "name": "presentation_initializer_indexer",
        "file_offset": 0x09843A,
        "gba_start": "0x0809843A",
        "gba_end": "0x08098462",
        "sha256": "25964b70683af389de5e045168dd4b4fda986b5d3db2ce36ec9e7cbfd59d2494",
    },
    {
        "name": "message_selector",
        "file_offset": 0x099564,
        "gba_start": "0x08099564",
        "gba_end": "0x08099582",
        "sha256": "835b54df161608218062de4ad9743101456988d29af8fd5c0de165d0b7ebaa47",
    },
    {
        "name": "glyph_preloader_indexer",
        "file_offset": 0x098138,
        "gba_start": "0x08098138",
        "gba_end": "0x0809816C",
        "sha256": "b724f3a6fb432bf77e0b7ef29dd3d78110baaf1b9e78de457faa6422c7aca898",
    },
)
ORIGINS = {"A": (0, 0), "B": (304, 0), "C": (0, 168), "D": (304, 168)}
SCOPE = {
    "all_descriptor_message_bindings_complete": True,
    "all_complete_static_layers_cataloged": True,
    "all_message_glyph_bindings_cataloged": True,
    "editor_preview_sheets_complete": True,
    "lossless_descriptor_schema_complete": True,
    "runtime_layer_installability_complete": True,
    "runtime_tick_timeline_complete": False,
    "screen_space_composition_complete": False,
    "message_character_decoding_complete": False,
    "natural_language_names_complete": False,
}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_descriptor_schema(
    descriptor: dict[str, Any],
) -> dict[str, Any]:
    expected = json.loads(json.dumps(descriptor))
    if descriptor["status"] == "sentinel":
        return expected
    words = [int(value, 16) for value in descriptor["raw_words"]]
    packed = b"".join(word.to_bytes(4, "little") for word in words)
    flags = words[1] >> 16
    expected["decoded"] = {
        "anchor_tiles": [packed[0], packed[1]],
        "direction_signed": [
            int.from_bytes(packed[2:3], "little", signed=True),
            int.from_bytes(packed[3:4], "little", signed=True),
        ],
        "amplitude": words[1] & 0xFFFF,
        "flags": f"0x{flags:04X}",
        "callback_mode": flags & 0xFF,
        "cue_ids": [packed[8], packed[9]],
    }
    for layer in expected["layers"]:
        name = layer["name"]
        complete = layer["status"] == "complete"
        gfx_present = layer["gfx_pointer"] is not None
        suppressed = name == "D" and bool(flags & 0x0400)
        if not gfx_present:
            reason = "gfx_pointer_zero"
        elif not complete:
            reason = "incomplete_resource_triplet"
        elif suppressed:
            reason = "descriptor_flag_0x0400"
        else:
            reason = None
        loadable = complete and not suppressed
        layer["runtime"] = {
            "installer_loadable": loadable,
            "installer_block_reason": reason,
            "initially_enabled": (
                loadable
                and (
                    name in {"A", "B"}
                    or name == "C" and not flags & 0x0100
                    or name == "D" and not flags & 0x0900
                )
            ),
            "dynamic_c_path_source": (
                name == "D" and complete and bool(flags & 0x0400)
            ),
            "dynamic_c_path_switch_tick": (
                50
                if name == "D" and complete and flags & 0x0400
                else None
            ),
        }
    return expected


def _safe_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError(f"path escapes root: {relative}")
    if not path.is_file():
        raise ValueError(f"missing file: {relative}")
    return path


def _expected_preview(
    root: Path,
    descriptor: dict[str, Any],
    message: dict[str, Any],
    glyphs: list[dict[str, Any]],
) -> Image.Image:
    canvas = Image.new("RGBA", (600, 368), (0, 0, 0, 0))
    for layer in descriptor["layers"]:
        if layer["status"] == "complete":
            source = root / "artifacts/tile-assets-bg-v2" / layer["layer_png"]
            canvas.alpha_composite(Image.open(source).convert("RGBA"), ORIGINS[layer["name"]])
    for slot, glyph_id in enumerate(message["binding"]["glyph_ids"]):
        if glyph_id == 0xFF:
            continue
        source = (
            root
            / "artifacts/battle-presentation-glyphs-v1"
            / glyphs[glyph_id]["runtime_png_file"]
        )
        canvas.alpha_composite(Image.open(source).convert("RGBA"), (slot * 34, 336))
    return canvas


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    entry_count = layer_count = glyph_count = skipped_count = 0
    try:
        tile_path = root / TILE_MANIFEST
        glyph_path = root / GLYPH_MANIFEST
        if _sha(tile_path) != TILE_SHA256:
            raise ValueError("tile source manifest hash mismatch")
        if _sha(glyph_path) != GLYPH_SHA256:
            raise ValueError("glyph source manifest hash mismatch")
        rom_path = root / "rom/base.gba"
        if _sha(rom_path) != ROM_SHA256:
            raise ValueError("ROM hash mismatch")
        rom = rom_path.read_bytes()
        for code_slice in CODE_SLICES:
            offset = code_slice["file_offset"]
            size = (
                int(code_slice["gba_end"], 16)
                - int(code_slice["gba_start"], 16)
            )
            if (
                hashlib.sha256(rom[offset : offset + size]).hexdigest()
                != code_slice["sha256"]
            ):
                raise ValueError(f"consumer code mismatch at 0x{offset:06X}")

        tile = _json(tile_path)
        glyph = _json(glyph_path)
        manifest = _json(_safe_file(artifact, "manifest.json"))
        if manifest["schema"] != "battle-visual-catalog-v1":
            raise ValueError("schema mismatch")
        if manifest["rom"] != {"file": "rom/base.gba", "sha256": ROM_SHA256}:
            raise ValueError("ROM declaration mismatch")
        if manifest["source_artifacts"] != {
            "tile_assets": {
                "manifest": TILE_MANIFEST.as_posix(),
                "sha256": TILE_SHA256,
            },
            "presentation_glyphs": {
                "manifest": GLYPH_MANIFEST.as_posix(),
                "sha256": GLYPH_SHA256,
            },
        }:
            raise ValueError("source artifact declaration mismatch")
        if manifest["selection_chain"] != {
            "formula": FORMULA,
            "code_slices": list(CODE_SLICES),
            "same_zero_based_index_verified": True,
        }:
            raise ValueError("selection chain mismatch")
        if manifest["scope"] != SCOPE:
            raise ValueError("scope mismatch")
        entries = manifest["entries"]
        if len(entries) != 79:
            raise ValueError("entry count mismatch")
        expected_files = {"manifest.json"}
        for index, (entry, descriptor, message) in enumerate(
            zip(entries, tile["descriptors"], glyph["messages"])
        ):
            if (
                entry["descriptor_id"] != index
                or entry["consumer_id"] != index + 1
                or entry["message"]["message_id"] != index
                or descriptor["descriptor_id"] != index
                or message["message_id"] != index
                or entry["descriptor_status"] != descriptor["status"]
                or entry["descriptor_gba_address"]
                != descriptor["descriptor_gba_address"]
            ):
                raise ValueError(f"index chain mismatch at {index}")
            if entry.get("descriptor") != _expected_descriptor_schema(
                descriptor
            ):
                raise ValueError(f"descriptor schema mismatch at {index}")
            expected_layers = [
                layer for layer in descriptor["layers"] if layer["status"] == "complete"
            ]
            expected_layer_records = [
                {
                    "name": source["name"],
                    "bits_per_pixel": source["bits_per_pixel"],
                    "source_file": (
                        Path("artifacts/tile-assets-bg-v2")
                        / source["layer_png"]
                    ).as_posix(),
                    "sha256": source["layer_png_sha256"],
                    "width": source["definition"]["width_tiles"] * 8,
                    "height": source["definition"]["height_tiles"] * 8,
                    "atlas_id": source["atlas_id"],
                }
                for source in expected_layers
            ]
            if entry["layers"] != expected_layer_records:
                raise ValueError(f"layer binding mismatch at {index}")
            for actual, source in zip(entry["layers"], expected_layers):
                path = _safe_file(root, actual["source_file"])
                if (
                    actual["sha256"] != source["layer_png_sha256"]
                    or _sha(path) != actual["sha256"]
                ):
                    raise ValueError(f"layer hash mismatch at {index}/{source['name']}")
            ids = message["binding"]["glyph_ids"]
            slots = entry["message"]["binding_slots"]
            expected_slots = [
                {"slot": slot, "glyph_id": glyph_id, "skipped": glyph_id == 0xFF}
                for slot, glyph_id in enumerate(ids)
            ]
            if slots != expected_slots:
                raise ValueError(f"binding slot mismatch at {index}")
            concrete = [
                (slot, glyph_id)
                for slot, glyph_id in enumerate(ids)
                if glyph_id != 0xFF
            ]
            expected_glyph_records = [
                {
                    "slot": slot,
                    "glyph_id": glyph_id,
                    "source_file": (
                        Path("artifacts/battle-presentation-glyphs-v1")
                        / glyph["glyphs"][glyph_id]["runtime_png_file"]
                    ).as_posix(),
                    "sha256": glyph["glyphs"][glyph_id][
                        "runtime_png_sha256"
                    ],
                    "width": glyph["glyphs"][glyph_id]["width"],
                    "height": glyph["glyphs"][glyph_id]["height"],
                    "palette_bank": 13,
                }
                for slot, glyph_id in concrete
            ]
            if entry["message"]["glyphs"] != expected_glyph_records:
                raise ValueError(f"glyph binding mismatch at {index}")
            expected_message = {
                "message_id": index,
                "raw_file": (
                    Path("artifacts/battle-presentation-glyphs-v1")
                    / message["raw_file"]
                ).as_posix(),
                "raw_sha256": message["raw_sha256"],
                "raw_hex": message["raw_hex"],
                "binding_gba_address": message["binding"]["gba_address"],
                "binding_raw_hex": message["binding"]["raw_hex"],
                "binding_slots": expected_slots,
                "glyphs": expected_glyph_records,
            }
            if entry["message"] != expected_message:
                raise ValueError(f"message evidence mismatch at {index}")
            for actual, (_, glyph_id) in zip(
                entry["message"]["glyphs"], concrete
            ):
                source = glyph["glyphs"][glyph_id]
                path = _safe_file(root, actual["source_file"])
                if (
                    actual["sha256"] != source["runtime_png_sha256"]
                    or _sha(path) != actual["sha256"]
                ):
                    raise ValueError(f"glyph hash mismatch at {index}/{glyph_id}")
            preview = entry["preview"]
            expected_panels = []
            for source in expected_layers:
                x, y = ORIGINS[source["name"]]
                expected_panels.append(
                    {
                        "kind": "layer",
                        "name": source["name"],
                        "x": x,
                        "y": y,
                        "width": source["definition"]["width_tiles"] * 8,
                        "height": source["definition"]["height_tiles"] * 8,
                    }
                )
            for slot, glyph_id in concrete:
                expected_panels.append(
                    {
                        "kind": "message_glyph",
                        "slot": slot,
                        "glyph_id": glyph_id,
                        "x": slot * 34,
                        "y": 336,
                        "width": glyph["glyphs"][glyph_id]["width"],
                        "height": glyph["glyphs"][glyph_id]["height"],
                    }
                )
            expected_preview_metadata = {
                "file": f"previews/visual-{index:02d}.png",
                "sha256": preview["sha256"],
                "width": 600,
                "height": 368,
                "layout": "A/B top row, C/D second row, message glyphs bottom row",
                "panels": expected_panels,
                "is_runtime_composite": False,
            }
            if preview != expected_preview_metadata:
                raise ValueError(f"preview metadata mismatch at {index}")
            preview_path = _safe_file(artifact, preview["file"])
            expected_files.add(preview["file"])
            if _sha(preview_path) != preview["sha256"]:
                raise ValueError(f"preview hash mismatch at {index}")
            actual_image = Image.open(preview_path).convert("RGBA")
            expected_image = _expected_preview(root, descriptor, message, glyph["glyphs"])
            if (
                actual_image.size != (600, 368)
                or actual_image.tobytes() != expected_image.tobytes()
            ):
                raise ValueError(f"preview pixels mismatch at {index}")
            layer_count += len(expected_layers)
            glyph_count += len(concrete)
            skipped_count += len(ids) - len(concrete)
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != expected_files:
            raise ValueError("artifact file set mismatch")
        entry_count = len(entries)
        expected_sentinels = [
            item["descriptor_id"]
            for item in tile["descriptors"]
            if item["status"] == "sentinel"
        ]
        if manifest["summary"] != {
            "entry_count": entry_count,
            "complete_layer_count": layer_count,
            "glyph_binding_count": glyph_count,
            "skipped_binding_count": skipped_count,
            "preview_count": entry_count,
            "sentinel_descriptor_ids": expected_sentinels,
        }:
            raise ValueError("summary mismatch")
    except Exception as exc:
        errors.append(str(exc))
    return {
        "verified": not errors,
        "entry_count": entry_count,
        "layer_count": layer_count,
        "glyph_binding_count": glyph_count,
        "skipped_binding_count": skipped_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/battle-visual-catalog-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
