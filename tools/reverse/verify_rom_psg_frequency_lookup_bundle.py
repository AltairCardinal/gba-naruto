#!/usr/bin/env python3
"""Verify the immutable PSG artifact bundle without live coverage coupling.

The accepted PSG verifier deliberately recognizes only its frozen pre/post
coverage states.  Later independently audited promotions must not rewrite that
historical verifier or receipt.  This wrapper replays the raw-ROM, payload,
binary, manifest, implementation, and accepted-receipt checks while leaving
the current live coverage state to ``tools/audit_rom_byte_coverage.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import verify_rom_psg_frequency_lookup as legacy


VERIFY_SCHEMA = "rom-psg-frequency-lookup-bundle-verification-v1"
WRAPPER_PATH = Path("tools/verify_rom_psg_frequency_lookup_bundle.py")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_artifact_bundle(
    root: Path | str, artifact_dir: Path | str
) -> dict[str, Any]:
    """Rebuild an accepted v1 bundle without reading current live coverage."""

    repository = legacy._validate_root(root)
    files = legacy._artifact_files(repository, artifact_dir)
    try:
        payload = json.loads(files[legacy.JSON_NAME])
        manifest = json.loads(files[legacy.MANIFEST_NAME])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("artifact JSON is invalid") from error
    if (
        not isinstance(payload, dict)
        or legacy._canonical(payload) != files[legacy.JSON_NAME]
    ):
        raise ValueError("payload is not canonical JSON")
    if (
        not isinstance(manifest, dict)
        or legacy._canonical(manifest) != files[legacy.MANIFEST_NAME]
    ):
        raise ValueError("manifest is not canonical JSON")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("accepted artifact status is required")

    expected_payload, expected_bundle = legacy.rebuild_payload(
        repository,
        validate_live_baseline=False,
    )
    if payload != expected_payload:
        raise ValueError("payload differs from independent reconstruction")
    if files[legacy.BIN_NAME] != expected_bundle:
        raise ValueError("binary bundle differs from frozen ROM ranges")

    receipt_files = {
        legacy.JSON_NAME: files[legacy.JSON_NAME],
        legacy.BIN_NAME: files[legacy.BIN_NAME],
    }
    expected_manifest = legacy._accepted_manifest(
        repository,
        expected_payload,
        receipt_files,
    )
    if manifest != expected_manifest:
        raise ValueError("accepted receipt manifest differs from reconstruction")
    legacy_report = legacy._verification_report(
        repository,
        status="accepted",
        payload=expected_payload,
        bundle=expected_bundle,
    )
    verification = manifest.get("verification")
    if (
        not isinstance(verification, dict)
        or verification.get("exit_code") != 0
        or verification.get("report") != legacy_report
        or manifest.get("verifier") != verification
    ):
        raise ValueError("accepted legacy verification receipt changed")

    claims = legacy.expected_coverage_claims(
        expected_payload,
        manifest,
        manifest_sha256=_sha(files[legacy.MANIFEST_NAME]),
    )
    if (
        len(claims) != 5
        or sum(claim["range"][1] - claim["range"][0] for claim in claims)
        != 226
    ):
        raise ValueError("coverage projection claim denominator changed")

    legacy_verifier = legacy._safe_file(repository, legacy.VERIFIER_PATH)
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
        "promotion_bytes": len(expected_bundle),
        "promotion_claim_count": len(claims),
        "promotion_range_count": len(legacy.PROMOTION_RANGES),
        "promotion_packed_sha256": _sha(expected_bundle),
        "producer_count": legacy_report["producer_count"],
        "consumer_instruction_count": legacy_report["consumer_instruction_count"],
        "consumer_block_count": legacy_report["consumer_block_count"],
        "consumer_frontier_count": legacy_report["consumer_frontier_count"],
        "legacy_verifier_sha256": _sha(legacy_verifier.read_bytes()),
        "bundle_verifier_sha256": _sha(wrapper_verifier.read_bytes()),
        "legacy_report": legacy_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-psg-frequency-lookup-v1"),
    )
    args = parser.parse_args()
    try:
        report = verify_artifact_bundle(args.root, args.artifact_dir)
    except (OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema": VERIFY_SCHEMA,
                    "verified": False,
                    "errors": [str(error)],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
