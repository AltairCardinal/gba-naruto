#!/usr/bin/env python3
"""Verify a v15 candidate packet with an anchored verifier and dependencies."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
LEGACY_VERIFIER_PATH = Path("tools/verify_rom_cfg_proven_roots_v15.py")
BUNDLE_PATH = Path("tools/verify_rom_cfg_proven_roots_v15_bundle.py")


def _require_isolated_cli_runtime() -> None:
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v15 bundle CLI requires isolated Python -I -S isolation")
    if any(name == "capstone" or name.startswith("capstone.") for name in sys.modules):
        raise RuntimeError("CFG v15 bundle CLI rejects preloaded Capstone modules")
    if any(os.environ.get(name) for name in ("PYTHONPATH", "PYTHONHOME", "LIBCAPSTONE_PATH")):
        raise RuntimeError("CFG v15 bundle CLI rejects runtime path overrides")


try:
    _require_isolated_cli_runtime()
except RuntimeError as error:
    if __name__ == "__main__":
        print(json.dumps({"schema": "rom-cfg-proven-roots-v15-bundle-verification-v1", "verified": False, "errors": [str(error)]}, sort_keys=True))
        raise SystemExit(1)
    raise
for _root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from tools.rom_cfg_proven_roots_v15_contract import (  # noqa: E402
    BUNDLE_VERIFY_SCHEMA,
    EXPERIMENT_OUTPUT_ROOT,
    MANIFEST_NAME,
    NONCLAIMS,
    OFFICIAL_ARTIFACT,
    PAYLOAD_NAME,
    PROMOTION_PACKED_SHA256,
    PROMOTION_SEMANTIC_RANGE_SHA256,
    PROMOTION_UNION_RANGE_SHA256,
    ROM_SHA256,
    SCHEMA,
    VERIFY_SCHEMA,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _canonical_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    if _canonical_json(value) != raw:
        raise ValueError(f"{label} is not canonical JSON")
    return value


def _safe_file(root: Path, relative: str | Path) -> Path:
    root = Path(root).resolve(strict=True)
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("v15 path is not repository-relative")
    current = root
    for component in rel.parts[:-1]:
        current = current / component
        if current.is_symlink():
            raise ValueError("v15 dependency path uses a symlink")
    candidate = root / rel
    if candidate.is_symlink():
        raise ValueError("v15 dependency uses a symlink")
    return candidate.resolve(strict=True)


def _artifact_file(artifact: Path, name: str) -> Path:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("v15 artifact directory is missing or uses a symlink")
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("v15 artifact file set uses a symlink or is incomplete")
    return path


def _assert_artifact_shape(artifact: Path) -> None:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("v15 artifact directory is missing or uses a symlink")
    members = list(artifact.rglob("*"))
    files = {path.relative_to(artifact).as_posix() for path in members if path.is_file()}
    if files != {MANIFEST_NAME, PAYLOAD_NAME} or any(path.is_symlink() for path in members):
        raise ValueError("v15 artifact file set changed")


def _load_artifact(artifact: Path) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    _assert_artifact_shape(artifact)
    payload_path = _artifact_file(artifact, PAYLOAD_NAME)
    manifest_path = _artifact_file(artifact, MANIFEST_NAME)
    payload_raw = payload_path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    payload = _canonical_object(payload_raw, "v15 payload")
    manifest = _canonical_object(manifest_raw, "v15 manifest")
    file_record = manifest.get("files", {}).get(PAYLOAD_NAME)
    if not isinstance(file_record, dict) or file_record.get("size") != len(payload_raw) or file_record.get("sha256") != _sha(payload_raw):
        raise ValueError("v15 payload receipt identity changed")
    if manifest.get("artifact_schema") != SCHEMA or payload.get("schema") != SCHEMA:
        raise ValueError("v15 artifact schema changed")
    if manifest.get("artifact_status") != "accepted":
        raise ValueError("v15 artifact is not an accepted immutable bundle")
    return payload, manifest, payload_raw


def _runtime_dependency_expected(payload: dict[str, Any]) -> dict[str, str]:
    implementation = payload.get("implementation")
    if not isinstance(implementation, dict):
        raise ValueError("v15 implementation receipt is missing")
    dependencies = implementation.get("runtime_dependency_sha256")
    if not isinstance(dependencies, dict) or not dependencies:
        raise ValueError("v15 runtime dependency receipt is missing")
    if any(not isinstance(path, str) or not isinstance(digest, str) or len(digest) != 64 for path, digest in dependencies.items()):
        raise ValueError("v15 runtime dependency receipt is malformed")
    return dict(dependencies)


def _artifact_relative_path(root: Path, artifact: Path) -> str:
    root = Path(root).resolve(strict=True)
    candidate = Path(artifact).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.is_symlink():
        raise ValueError("v15 artifact directory uses a symlink")
    try:
        lexical_relative = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("v15 artifact directory is not repository-relative") from error
    current = root
    for component in lexical_relative.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("v15 artifact path uses a symlink")
    resolved = candidate.resolve(strict=True)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("v15 artifact directory escaped repository root") from error
    if not relative.parts:
        raise ValueError("v15 artifact directory cannot be repository root")
    return relative.as_posix()


def _anchor_runtime_dependencies(root: Path, expected: dict[str, str]) -> None:
    for relative, digest in sorted(expected.items()):
        path = _safe_file(root, relative)
        if _sha(path.read_bytes()) != digest:
            raise ValueError(f"runtime dependency identity changed: {relative}")


LEGACY_VERIFIER_SHA256 = "163f04429f5bdd117f540cdf2421c483ff110e6eab1042403fe29ab7736dc167"


def _load_legacy(path: Path, source: bytes) -> types.ModuleType:
    module_name = f"_cfg_proven_roots_v15_legacy_{_sha(source)[:16]}"
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = "tools"
    module.__spec__ = importlib.util.spec_from_loader(module_name, loader=None)
    sys.modules[module_name] = module
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_anchored_legacy(root: Path, dependencies: dict[str, str]) -> types.ModuleType:
    path = _safe_file(root, LEGACY_VERIFIER_PATH)
    source = path.read_bytes()
    if _sha(source) != LEGACY_VERIFIER_SHA256:
        raise ValueError("legacy verifier identity changed before dynamic load")
    _anchor_runtime_dependencies(root, dependencies)
    module = _load_legacy(path, source)
    _anchor_runtime_dependencies(root, dependencies)
    return module


def _receipt_matches(root: Path, artifact: Path, manifest: dict[str, Any]) -> None:
    producer = manifest.get("producer")
    verifier = manifest.get("verifier")
    if not isinstance(producer, dict) or not isinstance(verifier, dict):
        raise ValueError("v15 promotion receipt is missing")
    producer_command = producer.get("command")
    verifier_command = verifier.get("command")
    expected_producer = ["python3", "-I", "-S", "tools/export_rom_cfg_proven_roots_v15.py", "--root", ".", "--output-dir"]
    expected_verifier = ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v15.py", "--root", ".", "--artifact-dir"]
    if not isinstance(producer_command, list) or producer_command[:-1] != expected_producer or not isinstance(verifier_command, list) or verifier_command[:-1] != expected_verifier or producer_command[-1] != verifier_command[-1]:
        raise ValueError("v15 promotion receipt command changed")
    recorded = Path(producer_command[-1])
    if recorded.is_absolute() or ".." in recorded.parts:
        raise ValueError("v15 promotion receipt path must be repository-relative")
    target = (Path(root).resolve(strict=True) / recorded).resolve(strict=False)
    allowed = (Path(root).resolve(strict=True) / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    official = (Path(root).resolve(strict=True) / OFFICIAL_ARTIFACT).resolve(strict=False)
    if target != official and (target == allowed or allowed not in target.parents):
        raise ValueError("v15 promotion receipt path escaped experiment subtree")
    if target != artifact.resolve(strict=True):
        raise ValueError("v15 promotion receipt path does not match actual artifact directory")


def _expected_legacy_report() -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "control_flow_oracle": "armv4t-raw-encoding",
        "rom_sha256": ROM_SHA256,
        "target_root_count": 4,
        "target_roots": [0x09A3E0, 0x0611F4, 0x0618FC, 0x08B6F0],
        "accepted_roots": [0x0611F4, 0x0618FC, 0x08B6F0, 0x09A3E0],
        "rejected_roots": [0x09C0F4],
        "producer_count": 5,
        "target_decoded_instruction_count": 197,
        "target_decoded_basic_block_count": 31,
        "target_reachable_instruction_bytes": 398,
        "target_frontier_count": 3,
        "target_frontiers": [[0x061274, "indirect_pc_target"], [0x061934, "indirect_pc_target"], [0x08B798, "indirect_pc_target"]],
        "target_instruction_internal_edge_count": 208,
        "target_block_internal_edge_count": 42,
        "target_external_call_edge_count": 2,
        "target_literal_reference_count": 17,
        "target_unique_literal_word_count": 13,
        "target_literal_bytes": 52,
        "promotion_range_count": 10,
        "semantic_promotion_range_count": 10,
        "promotion_union_range_count": 7,
        "promotion_bytes": 450,
        "promotion_code_bytes": 398,
        "promotion_literal_bytes": 52,
        "hole_bytes": 386,
        "semantic_range_vector_sha256": PROMOTION_SEMANTIC_RANGE_SHA256,
        "union_range_vector_sha256": PROMOTION_UNION_RANGE_SHA256,
        "promotion_packed_sha256": PROMOTION_PACKED_SHA256,
        "nonclaims": {name: False for name in NONCLAIMS},
    }


def _bundle_report(legacy: dict[str, Any]) -> dict[str, Any]:
    expected = _expected_legacy_report()
    if legacy != expected:
        raise ValueError("anchored legacy verifier report changed")
    return {
        "schema": BUNDLE_VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "artifact_bundle_verified": True,
        "legacy_receipt_verified": True,
        "legacy_control_flow_rebuilt": True,
        "live_coverage_verified": False,
        "rom_sha256": legacy["rom_sha256"],
        "target_root_count": legacy["target_root_count"],
        "accepted_root_count": len(legacy["accepted_roots"]),
        "target_roots": legacy["target_roots"],
        "accepted_roots": legacy["accepted_roots"],
        "rejected_root_count": len(legacy["rejected_roots"]),
        "rejected_roots": legacy["rejected_roots"],
        "producer_count": legacy["producer_count"],
        "decoded_instruction_count": legacy["target_decoded_instruction_count"],
        "decoded_basic_block_count": legacy["target_decoded_basic_block_count"],
        "target_decoded_instruction_count": legacy["target_decoded_instruction_count"],
        "target_decoded_basic_block_count": legacy["target_decoded_basic_block_count"],
        "target_reachable_instruction_bytes": legacy["target_reachable_instruction_bytes"],
        "reachable_instruction_bytes": legacy["target_reachable_instruction_bytes"],
        "target_frontier_count": legacy["target_frontier_count"],
        "frontier_count": legacy["target_frontier_count"],
        "target_frontiers": legacy["target_frontiers"],
        "target_instruction_internal_edge_count": legacy["target_instruction_internal_edge_count"],
        "target_block_internal_edge_count": legacy["target_block_internal_edge_count"],
        "target_external_call_edge_count": legacy["target_external_call_edge_count"],
        "external_call_edge_count": legacy["target_external_call_edge_count"],
        "target_literal_reference_count": legacy["target_literal_reference_count"],
        "target_unique_literal_word_count": legacy["target_unique_literal_word_count"],
        "target_literal_bytes": legacy["target_literal_bytes"],
        "promotion_range_count": legacy["promotion_range_count"],
        "semantic_promotion_range_count": legacy["semantic_promotion_range_count"],
        "promotion_union_range_count": legacy["promotion_union_range_count"],
        "promotion_bytes": legacy["promotion_bytes"],
        "promotion_code_bytes": legacy["promotion_code_bytes"],
        "promotion_literal_bytes": legacy["promotion_literal_bytes"],
        "literal_only_bytes": legacy["promotion_literal_bytes"],
        "hole_bytes": legacy["hole_bytes"],
        "preserved_unknown_hole_bytes": legacy["hole_bytes"],
        "semantic_range_vector_sha256": legacy["semantic_range_vector_sha256"],
        "union_range_vector_sha256": legacy["union_range_vector_sha256"],
        "promotion_packed_sha256": legacy["promotion_packed_sha256"],
        "nonclaims": copy.deepcopy(legacy["nonclaims"]),
    }


def verify_bundle(root: Path, artifact_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact_dir).expanduser()
    if not artifact.is_absolute():
        artifact = root / artifact
    artifact = artifact.absolute()
    payload, manifest, _payload_raw = _load_artifact(artifact)
    expected_relative_path = _artifact_relative_path(root, artifact)
    if payload.get("artifact_relative_path") != expected_relative_path:
        raise ValueError("v15 payload artifact-relative path does not match actual artifact")
    _receipt_matches(root, artifact, manifest)
    implementation = payload.get("implementation")
    if not isinstance(implementation, dict):
        raise ValueError("v15 implementation receipt is missing")
    if implementation.get("verifier_sha256") != LEGACY_VERIFIER_SHA256:
        raise ValueError("legacy verifier identity does not match artifact receipt")
    current_bundle = _safe_file(root, BUNDLE_PATH)
    if implementation.get("bundle_verifier_sha256") != _sha(current_bundle.read_bytes()):
        raise ValueError("bundle verifier identity does not match artifact receipt")
    dependencies = _runtime_dependency_expected(payload)
    legacy = _load_anchored_legacy(root, dependencies)
    verifier = getattr(legacy, "verify_rom_cfg_proven_roots_v15", None)
    if not callable(verifier):
        raise ValueError("anchored legacy verifier callable is missing")
    report = verifier(root, artifact)
    if not isinstance(report, dict) or not report.get("verified"):
        raise ValueError("anchored legacy verifier rejected artifact")
    return _bundle_report(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify_bundle(args.root, args.artifact_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        report = {
            "schema": BUNDLE_VERIFY_SCHEMA,
            "verified": False,
            "errors": [str(error)],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
