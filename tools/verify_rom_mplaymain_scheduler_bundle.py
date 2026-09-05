#!/usr/bin/env python3
"""Verify the immutable MPlayMain scheduler bundle without live coverage.

The accepted MPlayMain scheduler artifact predates later repository-wide
coverage changes.  Its legacy verifier reads the live coverage file directly,
so this wrapper supplies the exact historical coverage view and then delegates
the raw-ROM, payload, binary, manifest, and receipt checks to that verifier.
The current coverage auditor remains responsible for live coverage state.
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

from tools import verify_rom_mplaymain_scheduler as legacy


VERIFY_SCHEMA = "rom-mplaymain-scheduler-bundle-verification-v1"
WRAPPER_PATH = Path("tools/verify_rom_mplaymain_scheduler_bundle.py")
LEGACY_VERIFIER_PATH = Path("tools/verify_rom_mplaymain_scheduler.py")

FROZEN_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
FROZEN_COVERAGE_SHA256 = (
    "17aa05ec2919606ac4728106daf08b3d06a033ccd3c723dc17fd7ad1bdec9ad0"
)
FROZEN_COVERAGE_BASELINE: dict[str, Any] = {
    "path": "sequel/rom-byte-coverage.json",
    "sha256": FROZEN_COVERAGE_SHA256,
    "summary": {
        "classified_bytes": 6_121_877,
        "unknown_bytes": 169_579,
        "claim_count": 14_482,
        "segment_count": 16_591,
    },
    "target_segments": [
        {"range": [0x09A3DC, 0x09A684], "primary_class": "unknown"},
        {"range": [0x09A684, 0x09A686], "claim_id": "cfg-thumb-0752-09a684"},
        {"range": [0x09A686, 0x09A694], "primary_class": "unknown"},
    ],
}

FROZEN_UNKNOWN_RANGES = (
    (0x09A3DC, 0x09A684),
    (0x09A686, 0x09A694),
)
FROZEN_OWNER_CLAIMS: dict[str, dict[str, Any]] = {
    "cfg-thumb-0752-09a684": {
        "id": "cfg-thumb-0752-09a684",
        "range": [0x09A684, 0x09A686],
        "bytes_sha256": "477db9ac7ca5efc12e37f882656b8fe5a363ffeb99b2e565a953d10c3c91ab21",
    },
    "boot-thumb-handoff-code-21-099d8c": {
        "id": "boot-thumb-handoff-code-21-099d8c",
        "range": [0x099D8C, 0x099DF6],
        "bytes_sha256": "e7a6401e55670ff34e9913eec698dab27f6a9ae0b14fd8b59325a6d630d1be3a",
    },
    "boot-thumb-handoff-code-22-09a1ae": {
        "id": "boot-thumb-handoff-code-22-09a1ae",
        "range": [0x09A1AE, 0x09A1B0],
        "bytes_sha256": "477db9ac7ca5efc12e37f882656b8fe5a363ffeb99b2e565a953d10c3c91ab21",
    },
}

EXPECTED_SUMMARY = {
    "instruction_count": 289,
    "instruction_bytes": 600,
    "code_bytes": 600,
    "block_count": 81,
    "internal_edge_count": 117,
    "external_edge_count": 12,
    "external_target_count": 7,
    "literal_ref_count": 4,
    "literal_word_count": 3,
    "literal_bytes": 12,
    "frontier_count": 1,
    "return_count": 1,
    "raw_indirect_pc_count": 0,
    "owned_indirect_veneer_count": 1,
    "promoted_bytes": 612,
    "owned_provenance_bytes": 2,
    "unclassified_unknown_bytes": 2,
    "budget_exhausted": False,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frozen_coverage(
    *_args: object, **_kwargs: object
) -> tuple[dict[str, Any], bytearray, dict[str, dict[str, Any]]]:
    """Return only the accepted artifact's historical coverage projection."""

    unknown = bytearray(legacy.ROM_SIZE)
    for start, end in FROZEN_UNKNOWN_RANGES:
        unknown[start:end] = b"\x01" * (end - start)
    return (
        copy.deepcopy(FROZEN_COVERAGE_BASELINE),
        unknown,
        copy.deepcopy(FROZEN_OWNER_CLAIMS),
    )


def _load_artifact(
    root: Path, artifact_dir: Path | str
) -> tuple[Path, dict[str, Any], bytes, dict[str, Any], dict[str, bytes]]:
    """Load the three immutable artifact members through the legacy guards."""

    return legacy._load_artifact(root, artifact_dir)


def verify_artifact_bundle(
    root: Path | str, artifact_dir: Path | str
) -> dict[str, Any]:
    """Verify an accepted scheduler bundle without consulting live coverage."""

    repository = legacy._root(Path(root))
    directory, payload, bundle, manifest, files = _load_artifact(
        repository, artifact_dir
    )

    # The legacy verifier is intentionally retained as the authoritative
    # packet verifier.  Only its coverage input is replaced, and the patch is
    # scoped so callers' live verifier behavior is restored on return.
    with mock.patch.object(
        legacy, "_coverage", side_effect=_frozen_coverage
    ):
        legacy_report = legacy.verify_artifact(repository, directory)

    if (
        not isinstance(legacy_report, dict)
        or legacy_report.get("verified") is not True
        or legacy_report.get("contract_ok") is not True
        or legacy_report.get("artifact_status") != "accepted"
        or legacy_report.get("summary") != EXPECTED_SUMMARY
    ):
        raise ValueError("accepted legacy verification receipt changed")

    if payload.get("schema") != legacy.SCHEMA:
        raise ValueError("payload schema changed")
    if payload.get("rom") != {
        "path": legacy.ROM_PATH.as_posix(),
        "size": legacy.ROM_SIZE,
        "sha256": FROZEN_ROM_SHA256,
    }:
        raise ValueError("payload ROM binding changed")
    if payload.get("summary") != EXPECTED_SUMMARY:
        raise ValueError("payload summary changed")

    promotion_ranges = payload.get("promotion_ranges")
    claims = payload.get("coverage_claims")
    promotion = payload.get("promotion")
    if (
        not isinstance(promotion_ranges, list)
        or len(promotion_ranges) != 2
        or not isinstance(claims, list)
        or len(claims) != 2
        or not isinstance(promotion, dict)
        or promotion.get("union_bytes") != 612
        or promotion.get("unclassified_unknown_bytes") != 2
        or len(bundle) != 612
    ):
        raise ValueError("scheduler promotion denominator changed")

    verifier_path = legacy._safe_file(repository, LEGACY_VERIFIER_PATH)
    verifier_sha256 = _sha(verifier_path.read_bytes())
    expected_verifier = {
        "path": LEGACY_VERIFIER_PATH.as_posix(),
        "sha256": verifier_sha256,
        "command": [
            "python3",
            LEGACY_VERIFIER_PATH.as_posix(),
            "--artifact",
            legacy.ARTIFACT_RELATIVE.as_posix(),
        ],
    }
    if manifest.get("verifier") != expected_verifier:
        raise ValueError("accepted legacy verifier receipt changed")
    expected_verification = {
        "status": "verified",
        "contract_ok": True,
        "schema": legacy.VERIFY_SCHEMA,
        "summary": EXPECTED_SUMMARY,
    }
    if manifest.get("verification") != expected_verification:
        raise ValueError("accepted legacy verification receipt changed")

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
        "rom_sha256": FROZEN_ROM_SHA256,
        "promotion_bytes": len(bundle),
        "promotion_claim_count": len(claims),
        "promotion_range_count": len(promotion_ranges),
        "promotion_packed_sha256": _sha(bundle),
        "unclassified_historical_bytes": promotion[
            "unclassified_unknown_bytes"
        ],
        "legacy_verifier_sha256": verifier_sha256,
        "bundle_verifier_sha256": _sha(wrapper_verifier.read_bytes()),
        "summary": EXPECTED_SUMMARY,
        "promotion": promotion,
        "legacy_report": legacy_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-mplaymain-scheduler-v1"),
    )
    args = parser.parse_args()
    try:
        report = verify_artifact_bundle(args.root, args.artifact_dir)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
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
