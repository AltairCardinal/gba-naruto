#!/usr/bin/env python3
"""Verify the immutable u8-triplet artifact without live coverage coupling."""

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

from tools import verify_rom_u8_indexed_u8_triplet_lookup as legacy


VERIFY_SCHEMA = "rom-u8-indexed-u8-triplet-lookup-bundle-verification-v1"
WRAPPER_PATH = Path(
    "tools/verify_rom_u8_indexed_u8_triplet_lookup_bundle.py"
)
LEGACY_VERIFIER_PATH = Path(
    "tools/verify_rom_u8_indexed_u8_triplet_lookup.py"
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_artifact_bundle(
    root: Path | str, artifact_dir: Path | str
) -> dict[str, Any]:
    """Rebuild an accepted triplet bundle without reading current coverage."""

    repository = legacy._validate_root(Path(root))
    artifact = legacy._artifact_path(repository, Path(artifact_dir))
    members = list(artifact.iterdir())
    expected_members = {"manifest.json", legacy.JSON_NAME, legacy.BIN_NAME}
    if {item.name for item in members} != expected_members or any(
        item.is_symlink() or not item.is_file() for item in members
    ):
        raise ValueError("artifact file denominator changed")

    manifest_path = legacy._artifact_file(artifact, "manifest.json")
    payload_path = legacy._artifact_file(artifact, legacy.JSON_NAME)
    bundle_path = legacy._artifact_file(artifact, legacy.BIN_NAME)
    manifest_raw = manifest_path.read_bytes()
    payload_raw = payload_path.read_bytes()
    bundle = bundle_path.read_bytes()
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        payload = json.loads(payload_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("artifact JSON is invalid") from error
    if not isinstance(manifest, dict) or manifest_raw != legacy._canonical(manifest):
        raise ValueError("artifact manifest is not canonical JSON")
    if not isinstance(payload, dict) or payload_raw != legacy._canonical(payload):
        raise ValueError("artifact payload is not canonical JSON")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("accepted artifact status is required")

    expected_payload, expected_bundle = legacy.rebuild_payload(
        repository,
        validate_live_baseline=False,
    )
    if payload != expected_payload:
        raise ValueError("artifact payload differs from independent reconstruction")
    if bundle != expected_bundle:
        raise ValueError("artifact bundle differs from independent reconstruction")

    expected_manifest = legacy._expected_manifest(
        repository,
        artifact,
        expected_payload,
        payload_raw,
        bundle,
        status="accepted",
    )
    if manifest != expected_manifest:
        raise ValueError("accepted artifact manifest differs from reconstruction")

    legacy_report = legacy._report(
        repository,
        expected_payload,
        _sha(payload_raw),
        _sha(bundle),
        status="accepted",
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
        manifest_sha256=_sha(manifest_raw),
    )
    if (
        len(claims) != 2
        or sum(claim["range"][1] - claim["range"][0] for claim in claims) != 19
    ):
        raise ValueError("coverage projection claim denominator changed")

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
        "promotion_claim_count": len(claims),
        "promotion_range_count": len(legacy.PROMOTION_RANGES),
        "promotion_range_vector_sha256": (
            expected_payload["promotion"]["range_vector_sha256"]
        ),
        "promotion_packed_sha256": _sha(bundle),
        "consumer_instruction_count": legacy_report["consumer_instruction_count"],
        "consumer_block_count": legacy_report["consumer_block_count"],
        "consumer_frontier_count": legacy_report["consumer_frontier_count"],
        "table_record_count": legacy_report["table_record_count"],
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
        default=legacy.ARTIFACT_RELATIVE,
    )
    args = parser.parse_args()
    try:
        report = verify_artifact_bundle(args.root, args.artifact_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
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
