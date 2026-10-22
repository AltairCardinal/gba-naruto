#!/usr/bin/env python3
"""Verify both accepted bounded CGB CFG bundles through immutable anchors.

The two stage-one verifiers predate the proof auditor's mandatory success
``schema`` field.  This wrapper does not reinterpret their results: it pins
both verifier implementations and all six accepted artifact files, executes
the frozen verifiers in isolated Python processes, requires their exact
accepted reports, and emits one structured proof contract.  It deliberately
does not read the live ROM-byte coverage manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


VERIFY_SCHEMA = "rom-cgb-bounded-cfg-bundle-verification-v1"
WRAPPER_PATH = Path("tools/verify_rom_cgb_bounded_cfg_bundle.py")


SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "rom-cgb-helper-bounded-cfg-v1",
        "default_dir": Path("artifacts/rom-cgb-helper-bounded-cfg-v1"),
        "artifact_schema": "rom-cgb-helper-bounded-cfg-v1",
        "manifest": (
            "manifest.json",
            1_609,
            "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1",
        ),
        "payload": (
            "rom-cgb-helper-bounded-cfg.json",
            42_154,
            "dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960",
        ),
        "binary": (
            "rom-cgb-helper-bounded-cfg.bin",
            180,
            "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc",
        ),
        "contract_sha256": (
            "e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7"
        ),
        "legacy_verifier": (
            Path("tools/verify_rom_cgb_helper_bounded_cfg.py"),
            38_455,
            "d09f828511215b59fe8b60ba4bcf7e63fca48fc36d4c105e75175fa3b11179f3",
        ),
        "candidate_identity": {
            "artifact_status": "candidate",
            "bundle_sha256": (
                "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc"
            ),
            "manifest_sha256": (
                "cad4873e706f5425e75ee080af43096420be41a85d0f0cdf863496f0f792b3ad"
            ),
            "payload_sha256": (
                "dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960"
            ),
        },
        "promotion": {
            "claim_count": 9,
            "code_bytes": 164,
            "literal_bytes": 16,
            "total_bytes": 180,
            "range_vector_sha256": (
                "ea942377babe2613c9affe8711b6480f6e9e27e60da7aeb483112790de3b85b3"
            ),
            "packed_bytes_sha256": (
                "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc"
            ),
        },
    },
    {
        "id": "rom-cgbsound-bounded-cfg-v1",
        "default_dir": Path("artifacts/rom-cgbsound-bounded-cfg-v1"),
        "artifact_schema": "rom-cgbsound-bounded-cfg-v1",
        "manifest": (
            "manifest.json",
            1_594,
            "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e",
        ),
        "payload": (
            "rom-cgbsound-bounded-cfg.json",
            178_551,
            "362a3dc1b5819a57310482b7fbdd94bb2f79e9d439ea44713798140d1d79b18d",
        ),
        "binary": (
            "rom-cgbsound-bounded-cfg.bin",
            1_084,
            "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151",
        ),
        "contract_sha256": (
            "12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a"
        ),
        "legacy_verifier": (
            Path("tools/verify_rom_cgbsound_bounded_cfg.py"),
            38_958,
            "6af3510f319c58cdb9cf70c115f6a1b2b3ffc0b4fb331f247604dbdb8e637961",
        ),
        "candidate_identity": {
            "artifact_status": "candidate",
            "bundle_sha256": (
                "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151"
            ),
            "manifest_sha256": (
                "15e52e11fd9be4fa5ae7f485c65e8775b8e9c2bf01c05cfbef178e28e0ea65d4"
            ),
            "payload_sha256": (
                "362a3dc1b5819a57310482b7fbdd94bb2f79e9d439ea44713798140d1d79b18d"
            ),
        },
        "promotion": {
            "claim_count": 19,
            "code_bytes": 1_008,
            "literal_bytes": 76,
            "total_bytes": 1_084,
            "range_vector_sha256": (
                "3386a673407d2191f9b9427725f95e3864b92009ea32de433d28c9665c618f57"
            ),
            "packed_bytes_sha256": (
                "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151"
            ),
        },
    },
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _root_path(root: Path | str) -> Path:
    value = Path(root).expanduser().resolve()
    if not value.is_dir():
        raise ValueError(f"repository root is not a directory: {value}")
    return value


def _safe_path(root: Path, value: Path | str, *, directory: bool) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    absolute = path.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository path uses a symlink: {cursor}")
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("repository path escapes root")
    if directory and not resolved.is_dir():
        raise ValueError("artifact is not a directory")
    if not directory and not resolved.is_file():
        raise ValueError("required file is missing")
    return resolved


def _anchored_bytes(path: Path, *, label: str, size: int, sha256: str) -> bytes:
    raw = path.read_bytes()
    if len(raw) != size or _sha(raw) != sha256:
        raise ValueError(f"{label} identity changed")
    return raw


def _canonical_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    canonical = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if canonical != raw:
        raise ValueError(f"{label} is not canonical JSON")
    return value


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("repository path escapes root") from error


def _verify_one(root: Path, artifact_dir: Path | str, spec: dict[str, Any]) -> dict[str, Any]:
    artifact = _safe_path(root, artifact_dir, directory=True)
    expected_names = {
        spec["manifest"][0],
        spec["payload"][0],
        spec["binary"][0],
    }
    entries = list(artifact.iterdir())
    if {item.name for item in entries} != expected_names or any(
        item.is_symlink() or not item.is_file() for item in entries
    ):
        raise ValueError(f"{spec['id']} artifact file set changed")

    files: dict[str, bytes] = {}
    for kind in ("manifest", "payload", "binary"):
        name, size, sha256 = spec[kind]
        files[kind] = _anchored_bytes(
            artifact / name,
            label=f"{spec['id']} {kind}",
            size=size,
            sha256=sha256,
        )
    manifest = _canonical_json(files["manifest"], label=f"{spec['id']} manifest")
    payload = _canonical_json(files["payload"], label=f"{spec['id']} payload")
    if (
        manifest.get("artifact_schema") != spec["artifact_schema"]
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("contract_sha256") != spec["contract_sha256"]
        or manifest.get("acceptance", {}).get("source_candidate_identity")
        != spec["candidate_identity"]
        or manifest.get("verification", {}).get("status") != "verified"
        or manifest.get("verification", {}).get("contract_ok") is not True
        or manifest.get("verifier", {}).get("sha256")
        != spec["legacy_verifier"][2]
    ):
        raise ValueError(f"{spec['id']} accepted manifest receipt changed")
    if payload.get("schema") != spec["artifact_schema"]:
        raise ValueError(f"{spec['id']} payload schema changed")
    promotion_value = payload.get("promotion")
    if not isinstance(promotion_value, dict) or any(
        promotion_value.get(key) != expected
        for key, expected in spec["promotion"].items()
    ):
        raise ValueError(f"{spec['id']} promotion denominator changed")
    frontier_count = payload.get("cfg", {}).get("frontier_count")
    if frontier_count != 0:
        raise ValueError(f"{spec['id']} frontier denominator changed")

    script_relative, script_size, script_sha256 = spec["legacy_verifier"]
    script = _safe_path(root, script_relative, directory=False)
    _anchored_bytes(
        script,
        label=f"{spec['id']} legacy verifier",
        size=script_size,
        sha256=script_sha256,
    )
    command = [
        sys.executable,
        "-I",
        "-S",
        _relative(root, script),
        _relative(root, artifact),
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=300,
    )
    if completed.returncode != 0:
        raise ValueError(f"{spec['id']} legacy verifier failed")
    try:
        legacy_report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"{spec['id']} legacy verifier output is not JSON") from error
    expected_legacy_report = {
        "artifact_status": "accepted",
        "bundle_sha256": spec["binary"][2],
        "candidate_identity": spec["candidate_identity"],
        "contract_ok": True,
        "verified": True,
    }
    if legacy_report != expected_legacy_report:
        raise ValueError(f"{spec['id']} legacy verifier report changed")

    promotion = spec["promotion"]
    return {
        "artifact_schema": spec["artifact_schema"],
        "artifact_status": "accepted",
        "manifest_sha256": spec["manifest"][2],
        "payload_sha256": spec["payload"][2],
        "bundle_sha256": spec["binary"][2],
        "contract_sha256": spec["contract_sha256"],
        "legacy_verifier_sha256": script_sha256,
        "legacy_report": legacy_report,
        "promotion_bytes": promotion["total_bytes"],
        "promotion_claim_count": promotion["claim_count"],
        "code_bytes": promotion["code_bytes"],
        "literal_bytes": promotion["literal_bytes"],
        "range_vector_sha256": promotion["range_vector_sha256"],
        "frontier_count": frontier_count,
    }


def verify_bundles(
    root: Path | str,
    helper_artifact: Path | str = SPECS[0]["default_dir"],
    cgbsound_artifact: Path | str = SPECS[1]["default_dir"],
) -> dict[str, Any]:
    repository = _root_path(root)
    helper = _verify_one(repository, helper_artifact, SPECS[0])
    cgbsound = _verify_one(repository, cgbsound_artifact, SPECS[1])
    wrapper = _safe_path(repository, WRAPPER_PATH, directory=False)
    artifacts = {
        SPECS[0]["id"]: helper,
        SPECS[1]["id"]: cgbsound,
    }
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "artifact_count": len(artifacts),
        "artifact_bundles_verified": True,
        "legacy_receipts_verified": True,
        "live_coverage_verified": False,
        "promotion_bytes": sum(item["promotion_bytes"] for item in artifacts.values()),
        "promotion_claim_count": sum(
            item["promotion_claim_count"] for item in artifacts.values()
        ),
        "wrapper_verifier_sha256": _sha(wrapper.read_bytes()),
        "artifacts": artifacts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--helper-artifact",
        type=Path,
        default=SPECS[0]["default_dir"],
    )
    parser.add_argument(
        "--cgbsound-artifact",
        type=Path,
        default=SPECS[1]["default_dir"],
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = verify_bundles(
            args.root,
            args.helper_artifact,
            args.cgbsound_artifact,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as error:
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
