#!/usr/bin/env python3
"""Verify the accepted SoundMain relocated-CFG bundle against external anchors.

The stage-one verifier predates later repository-wide coverage changes and
reads the live coverage file while checking the artifact payload.  This
wrapper first pins every accepted packet member and its candidate receipt to
immutable external identities, then delegates the packet checks to that
verifier with only its coverage-baseline helper replaced by the baseline
embedded in the accepted payload.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCHEMA = "rom-soundmain-relocated-cfg-bundle-verification-v1"
WRAPPER_PATH = Path("tools/verify_rom_soundmain_relocated_cfg_bundle.py")
LEGACY_VERIFIER_PATH = Path("tools/verify_rom_soundmain_relocated_cfg.py")
ARTIFACT_SCHEMA = "rom-soundmain-relocated-cfg-v1"
MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "rom-soundmain-relocated-cfg.json"
BUNDLE_NAME = "rom-soundmain-relocated-cfg.bin"
EXPECTED_FILES = {MANIFEST_NAME, PAYLOAD_NAME, BUNDLE_NAME}

FROZEN_MANIFEST_SIZE = 15_878
FROZEN_MANIFEST_SHA256 = (
    "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37"
)
FROZEN_PAYLOAD_SIZE = 352_934
FROZEN_PAYLOAD_SHA256 = (
    "63543ece1982ced20eb0818faf3b6f1848e72ba6dcdb68105fa8b2e3e07e477a"
)
FROZEN_BUNDLE_SIZE = 924
FROZEN_BUNDLE_SHA256 = (
    "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331"
)
FROZEN_LEGACY_VERIFIER_SIZE = 82_001
FROZEN_LEGACY_VERIFIER_SHA256 = (
    "321d5ca5b7d6f887a21ec93c1bb06640f6e1397248273068bb5a13d3d7167d82"
)
FROZEN_CANDIDATE_MANIFEST_SHA256 = (
    "16aedff95afaf1e24f49cd74c01ded1f46433a79b5b708145dfa9a582fd2fa28"
)

EXPECTED_CANDIDATE_IDENTITY = {
    "artifact_status": "candidate",
    "manifest_sha256": FROZEN_CANDIDATE_MANIFEST_SHA256,
    "payload_sha256": FROZEN_PAYLOAD_SHA256,
    "bundle_sha256": FROZEN_BUNDLE_SHA256,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _root_path(root: Path | str) -> Path:
    value = Path(root).expanduser().resolve()
    if not value.is_dir():
        raise ValueError(f"repository root is not a directory: {value}")
    return value


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository path uses a symlink: {cursor}")
    if not cursor.is_file():
        raise ValueError(f"required file missing: {relative}")
    return cursor


def _safe_artifact(root: Path, artifact: Path | str) -> Path:
    value = Path(artifact)
    if not value.is_absolute():
        value = root / value
    absolute = value.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"artifact path uses a symlink: {cursor}")
    resolved = value.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError("artifact must stay inside repository root")
    if not resolved.is_dir():
        raise ValueError("artifact is not a directory")
    entries = list(resolved.iterdir())
    if {item.name for item in entries} != EXPECTED_FILES or any(
        item.is_symlink() or not item.is_file() for item in entries
    ):
        raise ValueError("artifact file set changed")
    return resolved


def _anchored_bytes(
    path: Path, *, label: str, size: int, sha256: str
) -> bytes:
    raw = path.read_bytes()
    if len(raw) != size:
        raise ValueError(f"{label} identity changed (size)")
    if _sha(raw) != sha256:
        raise ValueError(f"{label} identity changed")
    return raw


def _load_anchored_legacy(root: Path) -> ModuleType:
    """Hash the exact stage1 source before Python executes any of it."""

    path = _safe_file(root, LEGACY_VERIFIER_PATH)
    verified_source = _anchored_bytes(
        path,
        label="stage1 verifier",
        size=FROZEN_LEGACY_VERIFIER_SIZE,
        sha256=FROZEN_LEGACY_VERIFIER_SHA256,
    )
    name = "_anchored_verify_rom_soundmain_relocated_cfg"
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[name] = module
    code = compile(
        verified_source,
        str(path),
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    exec(code, module.__dict__)
    return module


def _frozen_coverage(
    baseline: dict[str, Any], *_args: object, **_kwargs: object
) -> dict[str, Any]:
    """Return the accepted payload's historical coverage projection only."""

    return copy.deepcopy(baseline)


def verify_artifact_bundle(
    root: Path | str, artifact_dir: Path | str
) -> dict[str, Any]:
    """Verify an accepted SoundMain bundle without consulting live coverage."""

    repository = _root_path(root)
    legacy = _load_anchored_legacy(repository)
    directory = _safe_artifact(repository, artifact_dir)

    # These anchors are intentionally checked before installing the coverage
    # patch or invoking the stage-one verifier.  They prevent a copied
    # artifact from changing its own receipt and then asking the legacy
    # verifier to bless the synchronized replacement.
    manifest_path = directory / MANIFEST_NAME
    payload_path = directory / PAYLOAD_NAME
    bundle_path = directory / BUNDLE_NAME
    manifest_raw = _anchored_bytes(
        manifest_path,
        label="accepted manifest",
        size=FROZEN_MANIFEST_SIZE,
        sha256=FROZEN_MANIFEST_SHA256,
    )
    payload_raw = _anchored_bytes(
        payload_path,
        label="accepted payload",
        size=FROZEN_PAYLOAD_SIZE,
        sha256=FROZEN_PAYLOAD_SHA256,
    )
    bundle_raw = _anchored_bytes(
        bundle_path,
        label="accepted binary",
        size=FROZEN_BUNDLE_SIZE,
        sha256=FROZEN_BUNDLE_SHA256,
    )
    # _load_artifact keeps the legacy canonical-JSON and artifact-path guards
    # authoritative while the byte anchors above remain the external trust
    # boundary.
    del manifest_raw, payload_raw, bundle_raw
    directory, payload, bundle, manifest, files = legacy._load_artifact(
        repository, directory
    )
    del files
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("accepted artifact status is required")

    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, dict):
        raise ValueError("accepted candidate identity missing")
    if acceptance.get("candidate_identity") != EXPECTED_CANDIDATE_IDENTITY:
        raise ValueError("accepted manifest candidate identity changed")

    frozen_baseline = payload.get("coverage_baseline")
    if not isinstance(frozen_baseline, dict):
        raise ValueError("payload frozen coverage baseline changed")

    # The legacy verifier remains authoritative for the packet.  This is the
    # sole patched legacy helper, and it returns only the payload-embedded
    # historical projection; no live coverage file is read.
    with mock.patch.object(
        legacy,
        "_coverage_baseline",
        side_effect=lambda *_args, **_kwargs: _frozen_coverage(frozen_baseline),
    ):
        legacy_report = legacy.verify_artifact(repository, directory)

    if (
        not isinstance(legacy_report, dict)
        or legacy_report.get("verified") is not True
        or legacy_report.get("contract_ok") is not True
        or legacy_report.get("artifact_status") != "accepted"
        or legacy_report.get("summary") != payload.get("summary")
    ):
        raise ValueError("accepted legacy verification receipt changed")

    promotion = payload.get("promotion")
    promotion_ranges = payload.get("promotion_ranges")
    claims = payload.get("coverage_claims")
    if (
        not isinstance(promotion, dict)
        or not isinstance(promotion_ranges, list)
        or not isinstance(claims, list)
        or len(bundle) != FROZEN_BUNDLE_SIZE
        or promotion.get("semantic_bytes") != FROZEN_BUNDLE_SIZE
        or promotion.get("semantic_packed_sha256") != FROZEN_BUNDLE_SHA256
    ):
        raise ValueError("SoundMain promotion denominator changed")
    semantic_union_ranges = promotion.get("semantic_union_ranges")
    if not isinstance(semantic_union_ranges, list):
        raise ValueError("SoundMain promotion union changed")

    wrapper_path = _safe_file(repository, WRAPPER_PATH)
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_status": "accepted",
        "artifact_bundle_verified": True,
        "legacy_receipt_verified": True,
        "candidate_identity_verified": True,
        "live_coverage_verified": False,
        "rom_sha256": payload["rom"]["sha256"],
        "promotion_bytes": len(bundle),
        "promotion_claim_count": len(claims),
        "promotion_range_count": len(promotion_ranges),
        "promotion_union_range_count": len(semantic_union_ranges),
        "deferred_alignment_gap_bytes": promotion[
            "deferred_alignment_gap_bytes"
        ],
        "promotion_packed_sha256": _sha(bundle),
        "accepted_manifest_sha256": FROZEN_MANIFEST_SHA256,
        "candidate_manifest_sha256": FROZEN_CANDIDATE_MANIFEST_SHA256,
        "legacy_verifier_sha256": FROZEN_LEGACY_VERIFIER_SHA256,
        "bundle_verifier_sha256": _sha(wrapper_path.read_bytes()),
        "summary": payload["summary"],
        "promotion": promotion,
        "legacy_report": legacy_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-soundmain-relocated-cfg-v1"),
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
