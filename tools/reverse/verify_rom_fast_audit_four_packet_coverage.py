#!/usr/bin/env python3
"""Replay four frozen packet verifiers against their immutable coverage baseline.

The packets were correctly produced from coverage SHA-256 064370aa..., but the
original verifiers intentionally fail once the mutable canonical coverage file
advances.  This verifier restores that exact historical input in a temporary
root, runs the four original independent verifiers unchanged, and separately
checks that the current canonical coverage contains the exact promoted packet
denominator.  It therefore removes a mutable-path dependency without weakening
the original raw-ROM and artifact checks.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.verify_rom_cfg_proven_roots_v16 import verify_rom_cfg_proven_roots_v16
from tools.verify_rom_cfg_proven_roots_v16_consumed_literals import verify_root
from tools.verify_rom_event_handler_cfg import verify_rom_event_handler_cfg
from tools.verify_rom_sprite_component_source import verify_rom_sprite_component_source


SCHEMA = "rom-fast-audit-four-packet-coverage-verification-v1"
BASELINE_DIR = Path("artifacts/rom-fast-audit-four-packet-baseline-v1")
BASELINE_MANIFEST_SHA256 = (
    "a4d57f767cff2931efe6b6e09c5d0a27280bb0fea654b8718abcb44f6c572a63"
)
BASELINE_ARCHIVE_SHA256 = (
    "c9572df49eca8f3ae65cb8fdc88f816dc7289f53055c730aaf746b28d840d42a"
)
BASELINE_COVERAGE_SHA256 = (
    "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa"
)
PACKETS: tuple[
    tuple[str, Callable[[Path, Path], dict[str, Any]], str, int, int], ...
] = (
    (
        "rom-event-handler-cfg-v1",
        verify_rom_event_handler_cfg,
        "f47e7e5a570ae6a1fc1a7bff11064df0b53bf60136314a799c0cc3962bfc36d3",
        40,
        4_062,
    ),
    (
        "rom-sprite-component-source-v1",
        verify_rom_sprite_component_source,
        "70bad678100f3f525f8f83dd67a79ed7492078be08c620bcca6e2e61862f7912",
        4,
        2_096,
    ),
    (
        "rom-cfg-proven-roots-v16",
        verify_rom_cfg_proven_roots_v16,
        "6dc8535453445edc07c975e003cb8cf2bf58b1f7e8ccfbae1e782aed7a7bc24a",
        21,
        778,
    ),
    (
        "rom-cfg-proven-roots-v16-consumed-literals-v1",
        verify_root,
        "f4f957c828b337191005a5a6c70a9fe578701ee67e468a5eed06b60096556478",
        51,
        204,
    ),
)
REPLAY_DEPENDENCY_ARTIFACTS = (
    "audio",
    "scene-visual-transition-timelines-v1",
    "rom-boot-framebuffers-v1",
    "rom-cfg-seeds-v1",
    "rom-cfg-inventory-v2",
    "rom-cfg-inventory-v3",
    "rom-cfg-proven-roots-v1",
    "rom-cfg-proven-roots-v2",
    "rom-cfg-proven-roots-v3",
    "rom-cfg-proven-roots-v4",
    "rom-cfg-proven-roots-v5",
    "rom-cfg-proven-roots-v6",
    "rom-cfg-proven-roots-v7",
    "rom-battle-controller-cfg-v1",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file(root: Path, relative: Path) -> Path:
    path = root / relative
    resolved = path.resolve(strict=True)
    resolved.relative_to(root)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"unsafe or missing input: {relative}")
    return resolved


def _load_baseline(root: Path) -> bytes:
    manifest_raw = _safe_file(root, BASELINE_DIR / "manifest.json").read_bytes()
    if _sha(manifest_raw) != BASELINE_MANIFEST_SHA256:
        raise ValueError("frozen baseline manifest identity changed")
    manifest = json.loads(manifest_raw)
    archive_path = _safe_file(root, BASELINE_DIR / "rom-byte-coverage.json.gz")
    archive_raw = archive_path.read_bytes()
    record = manifest.get("files", {}).get("rom-byte-coverage.json.gz", {})
    if (
        manifest.get("artifact_schema")
        != "rom-fast-audit-four-packet-baseline-v1"
        or manifest.get("artifact_status") != "accepted"
        or _sha(archive_raw) != BASELINE_ARCHIVE_SHA256
        or record.get("sha256") != BASELINE_ARCHIVE_SHA256
        or record.get("size") != len(archive_raw)
    ):
        raise ValueError("frozen baseline archive contract changed")
    try:
        raw = gzip.decompress(archive_raw)
    except (OSError, EOFError) as error:
        raise ValueError("frozen baseline archive is invalid") from error
    if (
        _sha(raw) != BASELINE_COVERAGE_SHA256
        or record.get("uncompressed_sha256") != BASELINE_COVERAGE_SHA256
        or record.get("uncompressed_size") != len(raw)
    ):
        raise ValueError("frozen baseline coverage identity changed")
    return raw


def _copy_replay_root(root: Path, target: Path, baseline_raw: bytes) -> None:
    for directory in ("tools", "tests", "notes"):
        shutil.copytree(root / directory, target / directory)
    (target / "rom").mkdir()
    shutil.copy2(root / "rom/base.gba", target / "rom/base.gba")
    (target / "sequel").mkdir()
    shutil.copytree(root / "sequel/content", target / "sequel/content")
    (target / "sequel/rom-byte-coverage.json").write_bytes(baseline_raw)
    (target / "artifacts").mkdir()
    for batch in {
        *(packet[0] for packet in PACKETS),
        *REPLAY_DEPENDENCY_ARTIFACTS,
    }:
        shutil.copytree(root / "artifacts" / batch, target / "artifacts" / batch)


def _check_current_coverage(root: Path) -> tuple[str, dict[str, dict[str, int]]]:
    raw = _safe_file(root, Path("sequel/rom-byte-coverage.json")).read_bytes()
    coverage = json.loads(raw)
    expected = {batch: (count, size, verifier_sha) for batch, _, verifier_sha, count, size in PACKETS}
    observed: dict[str, dict[str, int]] = {}
    seen_ranges: list[tuple[int, int]] = []
    for batch, (expected_count, expected_size, verifier_sha) in expected.items():
        claims = [
            claim
            for claim in coverage.get("claims", [])
            if claim.get("promotion_batch") == batch
        ]
        size = sum(claim["range"][1] - claim["range"][0] for claim in claims)
        if len(claims) != expected_count or size != expected_size:
            raise ValueError(f"canonical packet denominator changed: {batch}")
        for claim in claims:
            start, end = claim.get("range", [0, 0])
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start >= end
                or claim.get("role") != "primary"
                or claim.get("promoted_from_primary_class") != "unknown"
                or claim.get("baseline_unknown_only") is not True
                or claim.get("independent_verifier_sha256") != verifier_sha
            ):
                raise ValueError(f"canonical packet claim contract changed: {batch}")
            seen_ranges.append((start, end))
        observed[batch] = {"claim_count": len(claims), "promotion_bytes": size}
    seen_ranges.sort()
    if any(left[1] > right[0] for left, right in zip(seen_ranges, seen_ranges[1:])):
        raise ValueError("canonical fast-audit packet claims overlap")
    if coverage.get("summary", {}).get("fast_audit_four_packet_bytes") != 7_140:
        raise ValueError("canonical fast-audit byte summary changed")
    if coverage.get("summary", {}).get("fast_audit_four_packet_claim_count") != 116:
        raise ValueError("canonical fast-audit claim summary changed")
    return _sha(raw), observed


def verify(root: Path) -> dict[str, Any]:
    try:
        root = Path(root).resolve(strict=True)
        baseline_raw = _load_baseline(root)
        canonical_sha, observed = _check_current_coverage(root)
        packet_reports: dict[str, dict[str, Any]] = {}
        replay_parent = root / "build/experiments/active"
        replay_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="rom-fast-audit-replay-", dir=replay_parent
        ) as tmp:
            replay_root = Path(tmp)
            _copy_replay_root(root, replay_root, baseline_raw)
            for batch, verifier, _, _, _ in PACKETS:
                report = verifier(replay_root, replay_root / "artifacts" / batch)
                if report.get("verified") is not True:
                    raise ValueError(f"frozen verifier replay failed: {batch}: {report}")
                packet_reports[batch] = {
                    "verified": True,
                    "report_sha256": _sha(
                        (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    ),
                    **observed[batch],
                }
        return {
            "schema": SCHEMA,
            "verified": True,
            "errors": [],
            "baseline_coverage_sha256": BASELINE_COVERAGE_SHA256,
            "canonical_coverage_sha256": canonical_sha,
            "packet_count": len(PACKETS),
            "promotion_bytes": 7_140,
            "promotion_claim_count": 116,
            "packets": packet_reports,
        }
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {"schema": SCHEMA, "verified": False, "errors": [str(error)]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = verify(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
