#!/usr/bin/env python3
"""Audit same-layout character battle component and keyframe write-back."""

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

from tools.import_character_battle_structures import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_SHA256,
    _catalog_structures,
    _component_after,
    _keyframe_after,
)


ARTIFACT_ID = "character-battle-structure-writeback-v1"
PAYLOAD_NAME = "character-battle-structure-writeback.json"
IMPLEMENTATION_PATHS = (
    "tools/import_character_battle_structures.py",
    "tools/export_character_battle_structure_writeback_audit.py",
    "tools/verify_character_battle_structure_writeback_audit.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tests/test_import_character_battle_structures.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _resource_record(
    catalog_resource: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    component_evidence = []
    for (frame_id, component_index), source in sorted(
        row["component_targets"].items()
    ):
        roundtrip, _ = _component_after(source, {}, row["tile_count"])
        if roundtrip != source["raw"]:
            raise ValueError(
                f"resource {row['resource_id']} component round-trip mismatch"
            )
        mutation, semantic = _component_after(
            source,
            {"horizontal_flip": not source["horizontal_flip"]},
            row["tile_count"],
        )
        if mutation == source["raw"]:
            raise ValueError("component mutation did not change bytes")
        component_evidence.append(
            {
                "frame_id": frame_id,
                "component_index": component_index,
                "file_offset": source["offset"],
                "source_sha256": _sha256_bytes(source["raw"]),
                "roundtrip_sha256": _sha256_bytes(roundtrip),
                "mutation_sha256": _sha256_bytes(mutation),
                "source_tile_end": source["tile_end"],
                "mutation_tile_end": semantic["tile_end"],
            }
        )
    keyframe_evidence = []
    for (animation_id, keyframe_index), source in sorted(
        row["keyframe_targets"].items()
    ):
        roundtrip, _ = _keyframe_after(
            source,
            {},
            row["frame_count"],
        )
        if roundtrip != source["raw"]:
            raise ValueError(
                f"resource {row['resource_id']} keyframe round-trip mismatch"
            )
        new_hold = (
            source["hold_frames"] + 1
            if source["hold_frames"] < 0xFFFF
            else source["hold_frames"] - 1
        )
        mutation, semantic = _keyframe_after(
            source,
            {"hold_frames": new_hold},
            row["frame_count"],
        )
        if mutation == source["raw"]:
            raise ValueError("keyframe mutation did not change bytes")
        keyframe_evidence.append(
            {
                "animation_id": animation_id,
                "keyframe_index": keyframe_index,
                "file_offset": source["offset"],
                "source_sha256": _sha256_bytes(source["raw"]),
                "roundtrip_sha256": _sha256_bytes(roundtrip),
                "mutation_sha256": _sha256_bytes(mutation),
                "mutation_frame_id": semantic["frame_id"],
                "mutation_hold_frames": semantic["hold_frames"],
            }
        )
    anomaly_count = sum(
        frame["frame_trailer_raw_hex"] == "fffb0000"
        for frame in catalog_resource["frames"]
    )
    return {
        "resource_id": row["resource_id"],
        "component_region": {
            key: catalog_resource["component_region"][key]
            for key in ("gba_pointer", "size", "sha256")
        },
        "frame_pointer_table": {
            key: catalog_resource["frame_pointer_table"][key]
            for key in ("gba_pointer", "size", "sha256")
        },
        "timeline_region": {
            key: catalog_resource["timeline_region"][key]
            for key in ("gba_pointer", "size", "sha256")
        },
        "animation_pointer_table": {
            key: catalog_resource["animation_pointer_table"][key]
            for key in ("gba_pointer", "size", "sha256")
        },
        "frame_count": row["frame_count"],
        "component_count": row["component_count"],
        "animation_count": row["animation_count"],
        "keyframe_count": row["keyframe_count"],
        "tile_count": row["tile_count"],
        "slot_reference_count": len(row["slot_rows"]),
        "slot_rows": row["slot_rows"],
        "logical_aliases": row["logical_aliases"],
        "anomalous_trailer_count": anomaly_count,
        "component_roundtrip_count": len(component_evidence),
        "component_mutation_count": len(component_evidence),
        "component_evidence_sha256": _canonical_sha256(
            component_evidence
        ),
        "keyframe_roundtrip_count": len(keyframe_evidence),
        "keyframe_mutation_count": len(keyframe_evidence),
        "keyframe_evidence_sha256": _canonical_sha256(
            keyframe_evidence
        ),
    }


def _build_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("character battle visual catalog SHA-256 mismatch")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = _catalog_structures(catalog, rom)
    resources = [
        _resource_record(catalog["resources"][resource_id], rows[resource_id])
        for resource_id in sorted(rows)
    ]
    summary = {
        "resource_count": len(resources),
        "slot_reference_count": sum(
            row["slot_reference_count"] for row in resources
        ),
        "frame_count": sum(row["frame_count"] for row in resources),
        "component_count": sum(
            row["component_count"] for row in resources
        ),
        "animation_count": sum(
            row["animation_count"] for row in resources
        ),
        "keyframe_count": sum(
            row["keyframe_count"] for row in resources
        ),
        "component_roundtrip_count": sum(
            row["component_roundtrip_count"] for row in resources
        ),
        "component_mutation_count": sum(
            row["component_mutation_count"] for row in resources
        ),
        "keyframe_roundtrip_count": sum(
            row["keyframe_roundtrip_count"] for row in resources
        ),
        "keyframe_mutation_count": sum(
            row["keyframe_mutation_count"] for row in resources
        ),
        "anomalous_trailer_count": sum(
            row["anomalous_trailer_count"] for row in resources
        ),
    }
    expected = {
        "resource_count": 250,
        "slot_reference_count": 342,
        "frame_count": 2004,
        "component_count": 2190,
        "animation_count": 784,
        "keyframe_count": 3187,
        "component_roundtrip_count": 2190,
        "component_mutation_count": 2190,
        "keyframe_roundtrip_count": 3187,
        "keyframe_mutation_count": 3187,
        "anomalous_trailer_count": 1,
    }
    if summary != expected:
        raise ValueError(
            f"character battle structure denominator mismatch: {summary}"
        )
    scope = {
        "all_resources_audited": True,
        "all_slot_aliases_accounted": True,
        "all_frames_and_components_audited": True,
        "all_animations_and_keyframes_audited": True,
        "pointer_tables_immutable": True,
        "terminators_immutable": True,
        "anomalous_trailer_preserved": True,
        "component_semantic_writeback_complete": True,
        "keyframe_semantic_writeback_complete": True,
        "variable_count_structure_writeback_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_slot_selection_complete": False,
        "runtime_pixel_equivalence": False,
    }
    return {
        "schema": "character-battle-structure-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
            "size": len(rom),
        },
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
            "table_sha256": catalog["table"]["sha256"],
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "mutation_models": {
            "component": "toggle horizontal flip bit",
            "keyframe": "increment non-maximum hold by one frame",
            "purpose": (
                "prove every existing semantic slot has a length-preserving "
                "write-back path"
            ),
        },
        "resources": resources,
        "summary": summary,
        "scope": scope,
    }


def _prepare_output(output: Path) -> None:
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


def export_character_battle_structure_writeback_audit(
    root: Path,
    output: Path,
) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=output.parent,
        prefix=f".{ARTIFACT_ID}-",
    ) as directory:
        temporary = Path(directory) / ARTIFACT_ID
        temporary.mkdir()
        payload = _build_payload(root)
        payload_path = temporary / PAYLOAD_NAME
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files = {PAYLOAD_NAME: _sha256(payload_path)}
        manifest = {
            "schema": "git-artifact-promotion-v1",
            "artifact_id": ARTIFACT_ID,
            "artifact_schema": payload["schema"],
            "artifact_status": "accepted",
            "payload_file": PAYLOAD_NAME,
            "payload_sha256": files[PAYLOAD_NAME],
            "files": files,
            "scope": payload["scope"],
            "summary": payload["summary"],
            "verifier": {
                "command": [
                    "python3",
                    "tools/verify_character_battle_structure_writeback_audit.py",
                    "--root",
                    ".",
                    "--artifact",
                    f"artifacts/{ARTIFACT_ID}",
                ],
                "exit_code": 0,
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _prepare_output(output)
        temporary.rename(output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    payload = export_character_battle_structure_writeback_audit(
        args.root,
        output,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
