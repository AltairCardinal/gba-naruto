#!/usr/bin/env python3
"""Build an editor-facing catalog joining 79 visual descriptors and messages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


SCHEMA = "battle-visual-catalog-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TILE_MANIFEST = Path("artifacts/tile-assets-bg-v2/manifest.json")
GLYPH_MANIFEST = Path("artifacts/battle-presentation-glyphs-v1/manifest.json")
TILE_MANIFEST_SHA256 = (
    "1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749"
)
GLYPH_MANIFEST_SHA256 = (
    "ecc44fde0d886b75397d34181112f5b86dbb791b09e3b85797e9b4013f4e74a7"
)
SELECTION_FORMULA = (
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
        "sha256": (
            "25964b70683af389de5e045168dd4b4fda986b5d3db2ce36ec9e7cbfd59d2494"
        ),
    },
    {
        "name": "message_selector",
        "file_offset": 0x099564,
        "gba_start": "0x08099564",
        "gba_end": "0x08099582",
        "sha256": (
            "835b54df161608218062de4ad9743101456988d29af8fd5c0de165d0b7ebaa47"
        ),
    },
    {
        "name": "glyph_preloader_indexer",
        "file_offset": 0x098138,
        "gba_start": "0x08098138",
        "gba_end": "0x0809816C",
        "sha256": (
            "b724f3a6fb432bf77e0b7ef29dd3d78110baaf1b9e78de457faa6422c7aca898"
        ),
    },
)
PREVIEW_WIDTH = 600
PREVIEW_HEIGHT = 368
LAYER_ORIGINS = {
    "A": (0, 0),
    "B": (304, 0),
    "C": (0, 168),
    "D": (304, 168),
}
GLYPH_Y = 336


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_output_target(root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    if output == root or output in root.parents:
        raise ValueError("output target cannot contain the repository")


def _validate_existing_output(output: Path) -> None:
    if not output.exists():
        return
    manifest = output / "manifest.json"
    if not manifest.is_file():
        raise ValueError("refusing to replace unrelated output directory")
    try:
        schema = _load_json(manifest).get("schema")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("refusing to replace invalid output directory") from exc
    if schema != SCHEMA:
        raise ValueError("refusing to replace unrelated output directory")


def _preview(
    root: Path,
    output: Path,
    descriptor: dict[str, Any],
    message: dict[str, Any],
    glyphs: list[dict[str, Any]],
) -> dict[str, Any]:
    canvas = Image.new("RGBA", (PREVIEW_WIDTH, PREVIEW_HEIGHT), (0, 0, 0, 0))
    panels: list[dict[str, Any]] = []
    for layer in descriptor["layers"]:
        if layer["status"] != "complete":
            continue
        source = root / "artifacts/tile-assets-bg-v2" / layer["layer_png"]
        image = Image.open(source).convert("RGBA")
        x, y = LAYER_ORIGINS[layer["name"]]
        canvas.alpha_composite(image, (x, y))
        panels.append(
            {
                "kind": "layer",
                "name": layer["name"],
                "x": x,
                "y": y,
                "width": image.width,
                "height": image.height,
            }
        )
    for slot, glyph_id in enumerate(message["binding"]["glyph_ids"]):
        if glyph_id == 0xFF:
            continue
        glyph = glyphs[glyph_id]
        source = (
            root
            / "artifacts/battle-presentation-glyphs-v1"
            / glyph["runtime_png_file"]
        )
        image = Image.open(source).convert("RGBA")
        x = slot * 34
        canvas.alpha_composite(image, (x, GLYPH_Y))
        panels.append(
            {
                "kind": "message_glyph",
                "slot": slot,
                "glyph_id": glyph_id,
                "x": x,
                "y": GLYPH_Y,
                "width": image.width,
                "height": image.height,
            }
        )
    relative = Path("previews") / f"visual-{descriptor['descriptor_id']:02d}.png"
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, format="PNG", optimize=False, compress_level=9)
    return {
        "file": relative.as_posix(),
        "sha256": _sha_file(target),
        "width": PREVIEW_WIDTH,
        "height": PREVIEW_HEIGHT,
        "layout": "A/B top row, C/D second row, message glyphs bottom row",
        "panels": panels,
        "is_runtime_composite": False,
    }


def _entry(
    root: Path,
    output: Path,
    descriptor: dict[str, Any],
    message: dict[str, Any],
    glyphs: list[dict[str, Any]],
) -> dict[str, Any]:
    layers = []
    for layer in descriptor["layers"]:
        if layer["status"] != "complete":
            continue
        relative = Path("artifacts/tile-assets-bg-v2") / layer["layer_png"]
        layers.append(
            {
                "name": layer["name"],
                "bits_per_pixel": layer["bits_per_pixel"],
                "source_file": relative.as_posix(),
                "sha256": _sha_file(root / relative),
                "width": layer["definition"]["width_tiles"] * 8,
                "height": layer["definition"]["height_tiles"] * 8,
                "atlas_id": layer["atlas_id"],
            }
        )
    bound_glyphs = []
    binding_slots = []
    for slot, glyph_id in enumerate(message["binding"]["glyph_ids"]):
        binding_slots.append(
            {"slot": slot, "glyph_id": glyph_id, "skipped": glyph_id == 0xFF}
        )
        if glyph_id == 0xFF:
            continue
        glyph = glyphs[glyph_id]
        relative = (
            Path("artifacts/battle-presentation-glyphs-v1")
            / glyph["runtime_png_file"]
        )
        bound_glyphs.append(
            {
                "slot": slot,
                "glyph_id": glyph_id,
                "source_file": relative.as_posix(),
                "sha256": _sha_file(root / relative),
                "width": glyph["width"],
                "height": glyph["height"],
                "palette_bank": 13,
            }
        )
    return {
        "descriptor_id": descriptor["descriptor_id"],
        "consumer_id": descriptor["consumer_id"],
        "descriptor_status": descriptor["status"],
        "descriptor_gba_address": descriptor["descriptor_gba_address"],
        "layers": layers,
        "message": {
            "message_id": message["message_id"],
            "raw_file": (
                Path("artifacts/battle-presentation-glyphs-v1")
                / message["raw_file"]
            ).as_posix(),
            "raw_sha256": message["raw_sha256"],
            "raw_hex": message["raw_hex"],
            "binding_gba_address": message["binding"]["gba_address"],
            "binding_raw_hex": message["binding"]["raw_hex"],
            "binding_slots": binding_slots,
            "glyphs": bound_glyphs,
        },
        "preview": _preview(root, output, descriptor, message, glyphs),
    }


def _write_artifact(root: Path, output: Path) -> dict[str, Any]:
    tile_path = root / TILE_MANIFEST
    glyph_path = root / GLYPH_MANIFEST
    if _sha_file(tile_path) != TILE_MANIFEST_SHA256:
        raise ValueError("tile-assets-bg-v2 manifest hash mismatch")
    if _sha_file(glyph_path) != GLYPH_MANIFEST_SHA256:
        raise ValueError("battle-presentation-glyphs-v1 manifest hash mismatch")
    tile_manifest = _load_json(tile_path)
    glyph_manifest = _load_json(glyph_path)
    descriptors = tile_manifest["descriptors"]
    messages = glyph_manifest["messages"]
    glyphs = glyph_manifest["glyphs"]
    if len(descriptors) != 79 or len(messages) != 79:
        raise ValueError("visual descriptor and message tables must contain 79 rows")
    entries = []
    for descriptor, message in zip(descriptors, messages):
        if descriptor["descriptor_id"] != message["message_id"]:
            raise ValueError("descriptor/message indices diverged")
        entries.append(_entry(root, output, descriptor, message, glyphs))
    rom = root / "rom/base.gba"
    if _sha_file(rom) != ROM_SHA256:
        raise ValueError("base ROM hash mismatch")
    for code_slice in CODE_SLICES:
        start = code_slice["file_offset"]
        end = start + (
            int(code_slice["gba_end"], 16) - int(code_slice["gba_start"], 16)
        )
        with rom.open("rb") as stream:
            stream.seek(start)
            raw = stream.read(end - start)
        if hashlib.sha256(raw).hexdigest() != code_slice["sha256"]:
            raise ValueError(f"consumer slice mismatch: {code_slice['name']}")
    manifest = {
        "schema": SCHEMA,
        "rom": {"file": "rom/base.gba", "sha256": ROM_SHA256},
        "source_artifacts": {
            "tile_assets": {
                "manifest": TILE_MANIFEST.as_posix(),
                "sha256": TILE_MANIFEST_SHA256,
            },
            "presentation_glyphs": {
                "manifest": GLYPH_MANIFEST.as_posix(),
                "sha256": GLYPH_MANIFEST_SHA256,
            },
        },
        "selection_chain": {
            "formula": SELECTION_FORMULA,
            "code_slices": list(CODE_SLICES),
            "same_zero_based_index_verified": True,
        },
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "complete_layer_count": sum(len(entry["layers"]) for entry in entries),
            "glyph_binding_count": sum(
                len(entry["message"]["glyphs"]) for entry in entries
            ),
            "skipped_binding_count": sum(
                slot["skipped"]
                for entry in entries
                for slot in entry["message"]["binding_slots"]
            ),
            "preview_count": len(entries),
            "sentinel_descriptor_ids": [
                entry["descriptor_id"]
                for entry in entries
                if entry["descriptor_status"] == "sentinel"
            ],
        },
        "scope": {
            "all_descriptor_message_bindings_complete": True,
            "all_complete_static_layers_cataloged": True,
            "all_message_glyph_bindings_cataloged": True,
            "editor_preview_sheets_complete": True,
            "runtime_tick_timeline_complete": False,
            "screen_space_composition_complete": False,
            "message_character_decoding_complete": False,
            "natural_language_names_complete": False,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    validate_output_target(root, output)
    _validate_existing_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent)
    )
    backup: Path | None = None
    try:
        manifest = _write_artifact(root, temporary)
        if output.exists():
            backup = Path(
                tempfile.mkdtemp(
                    prefix=f".{output.name}-backup.",
                    dir=output.parent,
                )
            )
            backup.rmdir()
            os.replace(output, backup)
        try:
            os.replace(temporary, output)
        except Exception:
            if backup is not None:
                os.replace(backup, output)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists():
            if not output.exists():
                os.replace(backup, output)
            else:
                shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/battle-visual-catalog-v1"),
    )
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output_dir)
    print(json.dumps(manifest["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
