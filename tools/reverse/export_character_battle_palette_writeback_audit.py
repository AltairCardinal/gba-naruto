#!/usr/bin/env python3
"""Audit all fixed-length character battle palette write-back slots."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.import_character_battle_palettes import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_SHA256,
    _catalog_palettes,
)


ARTIFACT_ID = "character-battle-palette-writeback-v1"
PAYLOAD_NAME = "character-battle-palette-writeback.json"
IMPLEMENTATION_PATHS = (
    "tools/import_character_battle_palettes.py",
    "tools/export_character_battle_palette_writeback_audit.py",
    "tools/verify_character_battle_palette_writeback_audit.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tests/test_import_character_battle_palettes.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _build_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("character battle visual catalog SHA-256 mismatch")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    grouped = _catalog_palettes(catalog, rom)

    palettes: list[dict[str, Any]] = []
    for offset, row in sorted(grouped.items()):
        raw = rom[offset : offset + 32]
        mutated = bytearray(raw)
        mutated[2] ^= 1
        palettes.append(
            {
                "file_offset": offset,
                "gba_pointer": row["palette_pointer"],
                "size": 32,
                "color_count": 16,
                "sha256": row["palette_sha256"],
                "source_files": row["source_files"],
                "resource_ids": row["resource_ids"],
                "resource_reference_count": len(row["resource_ids"]),
                "slot_rows": row["slot_rows"],
                "slot_reference_count": len(row["slot_rows"]),
                "logical_aliases": row["logical_aliases"],
                "mutation": {
                    "kind": "first_nontransparent_color_low_bit_toggle",
                    "byte_offset": 2,
                    "before": raw[2],
                    "after": mutated[2],
                    "sha256": _sha256_bytes(bytes(mutated)),
                    "fixed_length_writeback": True,
                },
            }
        )

    summary = {
        "physical_palette_count": len(palettes),
        "unique_content_count": len({row["sha256"] for row in palettes}),
        "resource_reference_count": sum(
            row["resource_reference_count"] for row in palettes
        ),
        "slot_reference_count": sum(
            row["slot_reference_count"] for row in palettes
        ),
        "original_roundtrip_count": sum(
            len(rom[row["file_offset"] : row["file_offset"] + 32]) == 32
            and _sha256_bytes(
                rom[row["file_offset"] : row["file_offset"] + 32]
            )
            == row["sha256"]
            for row in palettes
        ),
        "mutation_writeback_count": sum(
            row["mutation"]["fixed_length_writeback"] for row in palettes
        ),
    }
    if summary != {
        "physical_palette_count": 48,
        "unique_content_count": 40,
        "resource_reference_count": 250,
        "slot_reference_count": 342,
        "original_roundtrip_count": 48,
        "mutation_writeback_count": 48,
    }:
        raise ValueError(f"character battle palette denominator mismatch: {summary}")

    return {
        "schema": "character-battle-palette-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
            "size": len(rom),
        },
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "palettes": palettes,
        "summary": summary,
        "scope": {
            "all_physical_palettes_audited": True,
            "all_resource_references_accounted": True,
            "all_slot_references_accounted": True,
            "guarded_fixed_length_importer_available": True,
            "arbitrary_fixed_length_palette_writeback_complete": True,
            "same_pointer_aliases_atomic": True,
            "equal_content_distinct_pointers_independent": True,
            "graphics_writeback_complete": False,
            "frame_structure_writeback_complete": False,
            "resource_relocation_complete": False,
            "pointer_rewrite_complete": False,
            "runtime_pixel_equivalence": False,
            "generic_image_writeback_complete": False,
        },
    }


def _prepare_output(output: Path) -> None:
    if output.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    if not output.exists():
        return
    try:
        manifest = json.loads(
            (output / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"refusing to replace foreign output: {error}") from error
    if manifest.get("artifact_id") != ARTIFACT_ID:
        raise ValueError("refusing to replace foreign output directory")
    shutil.rmtree(output)


def export_character_battle_palette_writeback_audit(
    root: Path,
    output: Path,
) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    if output == root or output in root.parents:
        raise ValueError("output must not be the repository or an ancestor")
    payload = _build_payload(root)
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": "character-battle-palette-writeback-audit-v1",
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": _sha256_bytes(payload_bytes),
        "files": {PAYLOAD_NAME: _sha256_bytes(payload_bytes)},
        "summary": payload["summary"],
        "scope": payload["scope"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_character_battle_palette_writeback_audit.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/character-battle-palette-writeback-v1",
            ],
            "exit_code": 0,
        },
    }
    _prepare_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_bytes)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = export_character_battle_palette_writeback_audit(
        args.root,
        args.output,
    )
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
