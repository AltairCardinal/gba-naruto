#!/usr/bin/env python3
"""Verify the accepted CFG proven-roots v12 bundle without live coverage.

The accepted v12 artifact records the pre-promotion coverage manifest as a
historical receipt.  The frozen legacy verifier reads that path at runtime,
which is no longer valid after the promotion has been applied.  This wrapper
first pins the legacy verifier byte-for-byte, then reuses only its raw-ROM and
accepted-upstream reconstruction helpers.  The historical coverage receipt is
reconstructed from immutable constants and is never opened from the working
tree.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any


VERIFY_SCHEMA = "rom-cfg-proven-roots-v12-bundle-verification-v1"
WRAPPER_PATH = Path("tools/verify_rom_cfg_proven_roots_v12_bundle.py")
DEFAULT_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v12")
MANIFEST_NAME = "manifest.json"
MANIFEST_SIZE = 335_832
MANIFEST_SHA256 = (
    "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677"
)
PAYLOAD_NAME = "rom-cfg-proven-roots-v12.json"
PAYLOAD_SIZE = 327_605
PAYLOAD_SHA256 = (
    "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee"
)
LEGACY_VERIFIER_PATH = Path("tools/verify_rom_cfg_proven_roots_v12.py")
LEGACY_VERIFIER_SIZE = 36_084
LEGACY_VERIFIER_SHA256 = (
    "1043291dfb16b90ef025242b976a4bf89a6a0173a0ac4904fc3534d625acbede"
)
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
HISTORICAL_COVERAGE_PATH = Path("sequel") / "rom-byte-coverage.json"
HISTORICAL_COVERAGE = {
    "path": HISTORICAL_COVERAGE_PATH.as_posix(),
    "sha256": "05215215595f0614f0461fa7502703ca62ccaa07159ddb27810f9903a31ef6d6",
    "classified_bytes": 6_125_883,
    "unknown_bytes": 165_573,
    "promotion_bytes": 500,
    "known_overlap_bytes": 0,
}
PRELOADED_DEPENDENCY_PREFIXES = (
    "capstone",
    "tools.verify_rom_cfg_inventory",
    "tools.export_rom_cfg_inventory",
    "tools._vendor.capstone",
)
ANCHORED_BOOTSTRAP = (
    "import hashlib, sys\n"
    "source = sys.stdin.buffer.read()\n"
    "display = sys.argv[1]\n"
    "sys.argv = [display, *sys.argv[2:]]\n"
    "namespace = {'__name__': '__main__', '__file__': display, "
    "'__package__': None, "
    "'__executing_source_sha256__': hashlib.sha256(source).hexdigest()}\n"
    "exec(compile(source, display, 'exec', dont_inherit=True, optimize=0), "
    "namespace, namespace)\n"
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _repository_root(root: Path | str) -> Path:
    value = Path(root).expanduser().resolve()
    if not value.is_dir():
        raise ValueError(f"repository root is not a directory: {value}")
    return value


def _safe_path(
    root: Path,
    value: Path | str,
    *,
    directory: bool,
) -> Path:
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


def _anchored_bytes(
    path: Path,
    *,
    label: str,
    size: int,
    sha256: str,
) -> bytes:
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


def _require_isolated_runtime() -> None:
    if not sys.flags.isolated or not sys.flags.no_site:
        raise ValueError("v12 bundle verifier requires an isolated -I -S runtime")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise ValueError("v12 bundle verifier rejects LIBCAPSTONE_PATH overrides")
    preloaded = sorted(
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(f"{prefix}.")
            for prefix in PRELOADED_DEPENDENCY_PREFIXES
        )
    )
    if preloaded:
        raise ValueError(
            "v12 bundle verifier rejects preloaded decoder dependencies: "
            + ", ".join(preloaded)
        )


def _load_legacy(path: Path, verified_source: bytes) -> ModuleType:
    """Execute exactly the legacy bytes whose identity was already checked."""

    name = "_verified_rom_cfg_proven_roots_v12_legacy"
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[name] = module
    try:
        code = compile(
            verified_source,
            str(path),
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__)
    finally:
        sys.modules.pop(name, None)
    return module


def _load_anchored_legacy(root: Path) -> ModuleType:
    legacy_path = _safe_path(root, LEGACY_VERIFIER_PATH, directory=False)
    verified_source = _anchored_bytes(
        legacy_path,
        label="legacy verifier",
        size=LEGACY_VERIFIER_SIZE,
        sha256=LEGACY_VERIFIER_SHA256,
    )
    return _load_legacy(legacy_path, verified_source)


def _expected_payload(
    root: Path,
    rom: bytes,
    legacy: ModuleType,
) -> dict[str, Any]:
    if legacy.COVERAGE_EXPECTED != HISTORICAL_COVERAGE:
        raise ValueError("legacy historical coverage receipt changed")
    original = legacy._coverage_baseline
    legacy._coverage_baseline = lambda _root: copy.deepcopy(HISTORICAL_COVERAGE)
    try:
        value = legacy._expected_payload(root, rom)
    finally:
        legacy._coverage_baseline = original
    return value


def _verify_bundle_in_process(
    root: Path | str,
    artifact_dir: Path | str = DEFAULT_ARTIFACT,
) -> dict[str, Any]:
    _require_isolated_runtime()
    repository = _repository_root(root)
    artifact = _safe_path(repository, artifact_dir, directory=True)
    members = list(artifact.iterdir())
    if (
        {member.name for member in members} != {MANIFEST_NAME, PAYLOAD_NAME}
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("v12 artifact file set changed")

    manifest_raw = _anchored_bytes(
        artifact / MANIFEST_NAME,
        label="v12 manifest",
        size=MANIFEST_SIZE,
        sha256=MANIFEST_SHA256,
    )
    payload_raw = _anchored_bytes(
        artifact / PAYLOAD_NAME,
        label="v12 payload",
        size=PAYLOAD_SIZE,
        sha256=PAYLOAD_SHA256,
    )
    manifest = _canonical_json(manifest_raw, label="v12 manifest")
    payload = _canonical_json(payload_raw, label="v12 payload")

    legacy = _load_anchored_legacy(repository)

    rom = _anchored_bytes(
        _safe_path(repository, ROM_PATH, directory=False),
        label="ROM",
        size=ROM_SIZE,
        sha256=ROM_SHA256,
    )
    expected_payload = _expected_payload(repository, rom, legacy)
    expected_payload_raw = (
        json.dumps(expected_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    if payload_raw != expected_payload_raw or payload != expected_payload:
        raise ValueError("v12 payload contract differs from immutable reconstruction")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("v12 artifact status changed")
    expected_manifest = legacy._expected_manifest(
        repository,
        manifest,
        expected_payload,
        payload_raw,
        "accepted",
    )
    expected_manifest_raw = (
        json.dumps(expected_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    if manifest_raw != expected_manifest_raw or manifest != expected_manifest:
        raise ValueError("v12 manifest or legacy receipt changed")

    source = expected_payload["source"]["summary"]
    target = expected_payload["target"]["summary"]
    promotion = expected_payload["promotion"]
    wrapper = _safe_path(repository, WRAPPER_PATH, directory=False)
    executing_source_sha256 = globals().get("__executing_source_sha256__")
    if executing_source_sha256 is None:
        executing_source_sha256 = _sha(wrapper.read_bytes())
    if (
        not isinstance(executing_source_sha256, str)
        or len(executing_source_sha256) != 64
    ):
        raise ValueError("v12 executing wrapper identity is invalid")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "artifact_schema": expected_payload["schema"],
        "artifact_status": "accepted",
        "artifact_bundle_verified": True,
        "legacy_receipt_verified": True,
        "legacy_control_flow_rebuilt": True,
        "live_coverage_verified": False,
        "rom_sha256": ROM_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "payload_sha256": PAYLOAD_SHA256,
        "legacy_verifier_sha256": LEGACY_VERIFIER_SHA256,
        "wrapper_verifier_sha256": executing_source_sha256,
        "promotion_bytes": promotion["promotion_bytes"],
        "promotion_range_count": promotion["promotion_range_count"],
        "promotion_code_bytes": promotion["promotion_code_bytes"],
        "promotion_literal_bytes": promotion["promotion_literal_bytes"],
        "promotion_range_vector_sha256": promotion["range_vector_sha256"],
        "promotion_packed_sha256": promotion["packed_sha256"],
        "hole_bytes": promotion["hole_bytes"],
        "holes": expected_payload["target"]["holes"],
        "source_decoded_instruction_count": source["decoded_instruction_count"],
        "source_decoded_basic_block_count": source[
            "decoded_basic_block_count"
        ],
        "source_reachable_instruction_bytes": source[
            "reachable_instruction_bytes"
        ],
        "source_frontier_count": source["frontier_count"],
        "target_decoded_instruction_count": target["decoded_instruction_count"],
        "target_decoded_basic_block_count": target[
            "decoded_basic_block_count"
        ],
        "target_reachable_instruction_bytes": target[
            "reachable_instruction_bytes"
        ],
        "target_frontier_count": target["frontier_count"],
        "target_literal_reference_count": target["literal_reference_count"],
        "target_unique_literal_word_count": target[
            "unique_literal_word_count"
        ],
    }


def verify_bundle(
    root: Path | str,
    artifact_dir: Path | str = DEFAULT_ARTIFACT,
) -> dict[str, Any]:
    """Run the verifier in a fresh isolated process and return its report."""

    repository = _repository_root(root)
    wrapper = _safe_path(repository, WRAPPER_PATH, directory=False)
    artifact = _safe_path(repository, artifact_dir, directory=True)
    wrapper_source = wrapper.read_bytes()
    command = [
        sys.executable,
        "-I",
        "-S",
        "-c",
        ANCHORED_BOOTSTRAP,
        wrapper.as_posix(),
        "--root",
        repository.as_posix(),
        "--artifact-dir",
        artifact.as_posix(),
    ]
    completed = subprocess.run(
        command,
        cwd=repository,
        input=wrapper_source,
        capture_output=True,
        check=False,
        timeout=300,
    )
    try:
        stdout = completed.stdout.decode("utf-8")
        stderr = completed.stderr.decode("utf-8")
        report = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("v12 isolated verifier output is not JSON") from error
    if not isinstance(report, dict):
        raise ValueError("v12 isolated verifier report is not an object")
    if completed.returncode != 0 or report.get("verified") is not True:
        errors = report.get("errors")
        detail = "; ".join(errors) if isinstance(errors, list) else str(errors)
        raise ValueError(f"v12 isolated bundle verification failed: {detail}")
    if stderr:
        raise ValueError("v12 isolated verifier emitted stderr")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = _verify_bundle_in_process(args.root, args.artifact_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "schema": VERIFY_SCHEMA,
                    "verified": False,
                    "errors": [str(error)],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
