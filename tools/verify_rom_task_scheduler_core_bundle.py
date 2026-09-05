#!/usr/bin/env python3
"""Verify the immutable task-scheduler artifact without live coverage coupling.

The accepted legacy verifier intentionally binds the scheduler packet's frozen
pre/post coverage states.  Later, independently audited promotions may classify
the three historical two-byte gaps without rewriting that artifact or its
receipt.  This wrapper rebuilds the raw-ROM packet against an explicit frozen
coverage view and leaves the current live coverage state to the repository-wide
coverage auditor.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = ROOT / "tools/_vendor"
for import_root in (ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools import verify_rom_task_scheduler_core as legacy


VERIFY_SCHEMA = "rom-task-scheduler-core-bundle-verification-v1"
WRAPPER_PATH = Path("tools/verify_rom_task_scheduler_core_bundle.py")
LEGACY_VERIFIER_PATH = Path("tools/verify_rom_task_scheduler_core.py")

FROZEN_COVERAGE_BASELINE = {
    "base_rom": {
        "path": "rom/base.gba",
        "sha256": legacy.ROM_SHA256,
        "size": legacy.ROM_SIZE,
    },
    "claim_count": 14_459,
    "classified_bytes": 6_120_972,
    "path": "sequel/rom-byte-coverage.json",
    "schema": "rom-byte-coverage-v1",
    "segment_count": 16_568,
    "sha256": legacy.COVERAGE_SHA256,
    "target_segments": [
        {
            "primary_claim_ids": [],
            "primary_class": "unknown",
            "range": [0x061AE4, 0x061D7C],
        },
        {
            "primary_claim_ids": ["cfg-thumb-0000-061d7c"],
            "primary_class": "armv4t_cfg_reachable_thumb_code",
            "range": [0x061D7C, 0x061DEA],
        },
        {
            "primary_claim_ids": [],
            "primary_class": "unknown",
            "range": [0x061DEA, 0x061E00],
        },
        {
            "primary_claim_ids": ["cfg-thumb-0001-061e00"],
            "primary_class": "armv4t_cfg_reachable_thumb_code",
            "range": [0x061E00, 0x061E1C],
        },
    ],
    "unknown_bytes": 170_484,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frozen_coverage(*_args: object, **_kwargs: object) -> tuple[dict[str, Any], bytearray]:
    """Return the exact historical scheduler view without reading live coverage."""

    unknown = bytearray(legacy.ROM_SIZE)
    for start, end in (
        *legacy.CODE_RANGES,
        *legacy.LITERAL_RANGES,
        *legacy.UNCLASSIFIED_RANGES,
    ):
        unknown[start:end] = b"\x01" * (end - start)
    return copy.deepcopy(FROZEN_COVERAGE_BASELINE), unknown


def _frozen_coverage_state(
    *_args: object, **_kwargs: object
) -> tuple[dict[str, Any], bytearray, dict[str, dict[str, Any]]]:
    coverage, unknown = _frozen_coverage()
    snapshots = legacy.PROVENANCE_CLAIM_SNAPSHOTS
    claims = [
        snapshots["consumer_code_slice"],
        snapshots["function_pointer_table"],
        *snapshots["opaque_targets"].values(),
    ]
    return coverage, unknown, {claim["id"]: copy.deepcopy(claim) for claim in claims}


def verify_artifact_bundle(
    root: Path | str, artifact_dir: Path | str
) -> dict[str, Any]:
    """Rebuild an accepted scheduler bundle without consulting live coverage."""

    repository = legacy._root(Path(root))
    directory = legacy._artifact_dir(Path(artifact_dir))
    manifest, manifest_raw = legacy._load_json(
        directory / legacy.MANIFEST_NAME, "manifest"
    )
    payload, payload_raw = legacy._load_json(
        directory / legacy.PAYLOAD_NAME, "payload"
    )
    bundle = (directory / legacy.BUNDLE_NAME).read_bytes()
    rom = legacy._read_rom(repository)

    with mock.patch.object(
        legacy, "_load_coverage", side_effect=_frozen_coverage
    ), mock.patch.object(
        legacy, "_coverage_state", side_effect=_frozen_coverage_state
    ):
        expected_payload, expected_bundle = legacy._expected(repository, rom)
    if payload != expected_payload:
        key = next(
            (
                key
                for key in expected_payload
                if payload.get(key) != expected_payload[key]
            ),
            "payload-shape",
        )
        raise ValueError(f"payload {key} changed")
    if bundle != expected_bundle:
        raise ValueError("packed promotion binary changed")

    expected_files = {
        legacy.PAYLOAD_NAME: {
            "size": len(payload_raw),
            "sha256": _sha(payload_raw),
        },
        legacy.BUNDLE_NAME: {
            "size": len(bundle),
            "sha256": _sha(bundle),
        },
    }
    if manifest.get("files") != expected_files:
        raise ValueError("manifest file receipt changed")
    if (
        manifest.get("schema") != legacy.PROMOTION_SCHEMA
        or manifest.get("artifact_schema") != legacy.SCHEMA
        or manifest.get("artifact_status") != "accepted"
    ):
        raise ValueError("manifest schema or accepted status changed")

    projection = (
        "rom",
        "coverage_baseline",
        "provenance_inputs",
        "entry_proof",
        "promotion",
        "summary",
        "implementation",
        "scope",
        "limitations",
    )
    if any(manifest.get(key) != payload[key] for key in projection):
        raise ValueError("manifest projection changed")
    producer_command, verifier_command = legacy._commands()
    if manifest.get("producer") != {
        "command": producer_command,
        "implementation": payload["implementation"],
    }:
        raise ValueError("producer receipt changed")

    legacy_report = legacy._stable_report(payload)
    verification = {
        "schema": legacy.VERIFY_SCHEMA,
        "command": verifier_command,
        "exit_code": 0,
        "report": legacy_report,
        "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
    }
    if (
        manifest.get("verifier") != verification
        or manifest.get("verification") != verification
    ):
        raise ValueError("accepted legacy verification receipt changed")

    promotion_ranges = payload.get("promotion_ranges")
    if (
        not isinstance(promotion_ranges, list)
        or len(promotion_ranges) != 7
        or len(bundle) != 308
        or payload.get("promotion", {}).get("unclassified_unknown_bytes") != 6
    ):
        raise ValueError("scheduler promotion denominator changed")

    legacy_verifier = legacy._safe_file(repository, LEGACY_VERIFIER_PATH)
    wrapper_verifier = legacy._safe_file(repository, WRAPPER_PATH)
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "artifact_schema": legacy.SCHEMA,
        "artifact_status": "accepted",
        "artifact_bundle_verified": True,
        "legacy_receipt_verified": True,
        "live_coverage_verified": False,
        "rom_sha256": legacy.ROM_SHA256,
        "promotion_bytes": len(bundle),
        "promotion_claim_count": len(promotion_ranges),
        "promotion_range_count": len(promotion_ranges),
        "unclassified_historical_bytes": payload["promotion"][
            "unclassified_unknown_bytes"
        ],
        "legacy_verifier_sha256": _sha(legacy_verifier.read_bytes()),
        "bundle_verifier_sha256": _sha(wrapper_verifier.read_bytes()),
        "summary": payload["summary"],
        "promotion": payload["promotion"],
        "legacy_report": legacy_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-task-scheduler-core-v1"),
    )
    args = parser.parse_args()
    try:
        report = verify_artifact_bundle(args.root, args.artifact_dir)
    except (OSError, ValueError) as error:
        print(
            json.dumps(
                {"schema": VERIFY_SCHEMA, "verified": False, "errors": [str(error)]},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
