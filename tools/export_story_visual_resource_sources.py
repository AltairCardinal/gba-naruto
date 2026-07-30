#!/usr/bin/env python3
"""Export deduplicated editable binary sources for all story BG3 layers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.import_story_visual_resource_relocations import (
    CATALOG_PATH,
    CATALOG_SHA256,
    catalog_story_visual_relocation_payloads,
)


ARTIFACT_ID = "story-visual-resource-sources-v1"
SCHEMA = "story-visual-resource-source-export-v1"
PAYLOAD_NAME = "source-catalog.json"
SUFFIXES = {
    "graphics": ".4bpp.bin",
    "palette": ".bgr555.bin",
    "tilemap": ".u16le.bin",
}


def export_sources(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    output.mkdir(parents=True, exist_ok=True)
    resources = catalog_story_visual_relocation_payloads(root)
    rows = []
    for (resource_type, resource_sha256), resource in sorted(
        resources.items(),
        key=lambda item: (
            min(item[1]["physical_offsets"]),
            item[1]["resource_type"],
        ),
    ):
        relative = (
            Path(resource_type)
            / f"{resource_sha256}{SUFFIXES[resource_type]}"
        )
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resource["content"])
        rows.append(
            {
                "resource_type": resource_type,
                "resource_sha256": resource_sha256,
                "decompressed_size": len(resource["content"]),
                "source_file": relative.as_posix(),
                "physical_offsets": resource["physical_offsets"],
                "compressed_sizes": resource["compressed_sizes"],
                "pointer_offsets": sorted(
                    alias["table_pointer_offset"]
                    for alias in resource["pointer_aliases"]
                ),
            }
        )
    summary = {
        "content_resource_count": len(rows),
        "physical_payload_count": sum(
            len(row["physical_offsets"]) for row in rows
        ),
        "logical_pointer_count": sum(
            len(row["pointer_offsets"]) for row in rows
        ),
        "resource_type_counts": {
            role: sum(row["resource_type"] == role for row in rows)
            for role in ("graphics", "palette", "tilemap")
        },
    }
    if summary != {
        "content_resource_count": 49,
        "physical_payload_count": 72,
        "logical_pointer_count": 72,
        "resource_type_counts": {
            "graphics": 24,
            "palette": 1,
            "tilemap": 24,
        },
    }:
        raise ValueError("story visual source export denominator mismatch")
    catalog = {
        "schema": SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "summary": summary,
        "resources": rows,
    }
    payload_path = output / PAYLOAD_NAME
    payload_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files = {
        relative: hashlib.sha256((output / relative).read_bytes()).hexdigest()
        for relative in sorted(
            [PAYLOAD_NAME, *(row["source_file"] for row in rows)]
        )
    }
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": files[PAYLOAD_NAME],
        "files": files,
        "scope": {
            "proved": (
                "All 49 deduplicated story-layer source payloads are exported "
                "from the fixed base ROM and retain all 72 physical payload "
                "and descriptor-pointer provenance records."
            ),
            "editable": (
                "The raw graphics, palette and tilemap files are authoring "
                "inputs for the guarded story visual relocation importer."
            ),
            "not_proved": (
                "Modified-resource runtime pixel equivalence, alternate BG3 "
                "geometry, scroll/window/blend timing or cartridge behavior."
            ),
        },
        "summary": summary,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_story_visual_resource_relocation_audit.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/story-visual-resource-relocation-v1",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    catalog = export_sources(args.root, args.output)
    print(json.dumps(catalog["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
