#!/usr/bin/env python3
"""Replay one controlled map-sprites cell, preserving the 43 x 2 denominator."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_map_sprites_definition_pixel_ab import verify_artifact

SCHEMA = "map-sprites-partial-bank-verification-v1"
CONTRACT_PATH = "tools/data/map-sprites-partial-bank-contract-v1.json"
CONTRACT_SHA256 = "ed5482dce37d3baa7bdf69410839d8cab65dc5a01c34fa05c0a2ad5036cc2db2"
BANK_PATH = "sequel/content/map-sprites/bank.json"
ARTIFACT_PATH = "artifacts/map-sprites-definition-id1-pixel-ab-v1"
SCRIPT_PATH = "tools/verify_map_sprites_partial_bank.py"
FIELDS = ("definition_ptr", "animation_ptr")
LIMITATIONS = (
    "Only record 1 definition_ptr has controlled materialization pixel A/B evidence.",
    "Natural loader reentry, animation_ptr and the other 42 records are unverified.",
    "Physical GBA execution and exhaustive bank semantics are unverified.",
)


def _file(root: Path, relative: str) -> bytes:
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"missing input: {relative}") from error
    if resolved != candidate.absolute() or not resolved.is_file():
        raise ValueError(f"input must be a regular non-symlink file: {relative}")
    return resolved.read_bytes()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_partial_bank(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    contract_bytes = _file(root, CONTRACT_PATH)
    if _sha(contract_bytes) != CONTRACT_SHA256:
        raise ValueError("contract hash mismatch")
    contract = json.loads(contract_bytes)
    if contract["schema"] != "map-sprites-partial-bank-inputs-v1":
        raise ValueError("contract schema mismatch")
    inputs = contract["inputs"]
    for relative, expected in inputs.items():
        if _sha(_file(root, relative)) != expected:
            raise ValueError(f"input hash mismatch: {relative}")

    bank = json.loads(_file(root, BANK_PATH))
    fields = [field["name"] for field in bank["entry_format"]["fields"]]
    if bank["entry_count"] != 43 or bank["entry_size"] != 8 or fields != list(FIELDS):
        raise ValueError("fixed bank denominator mismatch")
    rom = _file(root, "rom/base.gba")
    for index, entry in enumerate(bank["entries"]):
        offset = 0x53F140 + 8 * index
        if entry["_index"] != index or entry["_raw_offset"] != offset:
            raise ValueError("bank record identity mismatch")
        pair = struct.unpack_from("<II", rom, offset)
        if pair != tuple(entry[field] for field in FIELDS):
            raise ValueError("bank ROM pair mismatch")

    observed = verify_artifact(root, root / ARTIFACT_PATH)
    if observed["verified"] is not True or observed["entry_id"] != 1:
        raise ValueError("controlled record identity mismatch")
    all_cells = [
        {"record_id": str(index), "field_id": field}
        for index in range(43)
        for field in FIELDS
    ]
    covered = [{"record_id": "1", "field_id": "definition_ptr"}]
    manifest = f"{ARTIFACT_PATH}/manifest.json"
    return {
        "schema": SCHEMA,
        "verified": True,
        "scope": "controlled_materialization_pixel_ab",
        "bank": "map-sprites",
        "bank_sha256": inputs[BANK_PATH],
        "evidence_sha256": {manifest: inputs[manifest]},
        "input_sha256": inputs,
        "contract_sha256": CONTRACT_SHA256,
        "record_ids_total": [str(index) for index in range(43)],
        "record_ids_covered": ["1"],
        "field_ids_total": list(FIELDS),
        "field_ids_covered": ["definition_ptr"],
        "cells_total": len(all_cells),
        "cells_covered": covered,
        "cells_uncovered": [cell for cell in all_cells if cell not in covered],
        "changed_pixel_count": observed["changed_pixel_count"],
        "bbox_inclusive": observed["bbox_inclusive"],
        "natural_loader_reentry": False,
        "physical_gba_verified": False,
        "exhaustive": False,
        "limitations": list(LIMITATIONS),
    }


def proof_binding(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Build a partial catalog proposal; never mutate the live catalog."""
    root = Path(root).resolve(strict=True)
    if result != verify_partial_bank(root):
        raise ValueError("result mismatch")
    assertions = {f"/{key}": value for key, value in result.items()}
    return {
        "catalog_classification": "runtime_verified",
        "bank_sha256": result["bank_sha256"],
        "coverage": {
            "status": "artifact_verified_controlled_materialization",
            "records_total": 43,
            "records_covered": 1,
            **{
                key: result[key]
                for key in (
                    "record_ids_total", "record_ids_covered", "field_ids_total",
                    "field_ids_covered", "cells_total", "cells_covered", "cells_uncovered",
                )
            },
        },
        "evidence": [
            {"path": name, "sha256": digest}
            for name, digest in result["evidence_sha256"].items()
        ],
        "verifiers": [
            {
                "command": ["python3", SCRIPT_PATH, "--root", "."],
                "script_sha256": _sha(_file(root, SCRIPT_PATH)),
                "contract": {"format": "json", "assertions": assertions},
            }
        ],
        "limitations": list(LIMITATIONS),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = verify_partial_bank(args.root)
    except (ValueError, OSError) as error:
        print(json.dumps({"schema": SCHEMA, "verified": False, "errors": [str(error)]}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
