#!/usr/bin/env python3
"""TDD contract for the selector-code source-window promotion artifact."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import export_rom_selector_code_windows as exporter
from tools import verify_rom_selector_code_windows as verifier


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
ROM_BASE = 0x08000000
WINDOWS = [
    (0x06626C, 0x066736),
    (0x066758, 0x066790),
    (0x08A6AC, 0x08A700),
    (0x08AFE0, 0x08B07C),
    (0x08B2C8, 0x08B580),
    (0x08B58C, 0x08B65A),
    (0x08CC80, 0x08CCB4),
    (0x08CD5A, 0x08CDF8),
    (0x097C6C, 0x097C98),
    (0x09C4DC, 0x09C528),
]
PROMOTION_RANGES = [
    (0x0663A6, 0x0663B4),
    (0x0663EE, 0x0663F4),
    (0x066408, 0x06640C),
    (0x066420, 0x066424),
    (0x066438, 0x06643C),
    (0x0664EC, 0x0664F8),
    (0x066526, 0x066530),
    (0x0666CC, 0x0666F8),
    (0x08A6AC, 0x08A700),
    (0x08AFE0, 0x08B07C),
    (0x08B2C8, 0x08B2EA),
    (0x08B356, 0x08B580),
    (0x08B58C, 0x08B5C2),
    (0x08B5E6, 0x08B640),
    (0x08B64E, 0x08B65A),
    (0x08CD5A, 0x08CDF8),
    (0x097C96, 0x097C98),
    (0x09C4FC, 0x09C504),
    (0x09C526, 0x09C528),
]
EXPECTED = {
    "source_window_count": 10,
    "source_window_bytes": 2754,
    "promotion_range_count": 19,
    "promotion_bytes": 1252,
    "source_window_range_denominator_sha256": (
        "c45e828631f019ea506b0b24a0efeb16ed8508377277bc27936e8a8932fa8d43"
    ),
    "promotion_range_denominator_sha256": (
        "1a1e50479424dbd441bc81adeca3c7d9075dc1a8ca13869e94693a71e702563e"
    ),
    "full_bundle_sha256": (
        "4c1d5865350a66b57db7b483f68c6bf97e9c88fcd5372f021358d4ad8c917523"
    ),
    "promotion_bundle_sha256": (
        "2207f28f0e2635b7cff09660d4440d5f8c926017583d210b748a34ac2639672b"
    ),
}
EXPECTED_REPORT = {
    "schema": "rom-selector-code-windows-verification-v1",
    "artifact_schema": "rom-selector-code-windows-v1",
    "verified": True,
    **EXPECTED,
    "primary_overlap_bytes": 1502,
    "bridge_promotion_count": 0,
    "mapper_promotion_count": 0,
    "errors": [],
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_file(root: Path, relative: str) -> None:
    source = ROOT / relative
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_minimal_root(root: Path) -> None:
    for relative in (
        "rom/base.gba",
        "sequel/rom-byte-coverage.json",
        "artifacts/rom-selector-text-bindings-v1/manifest.json",
        "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json",
        "artifacts/rom-selector-text-bindings-v1/selector-text-bytes.bin",
        "artifacts/rom-selector-direct-source-records-v1/manifest.json",
        "artifacts/rom-selector-direct-source-records-v1/rom-selector-direct-source-records.json",
        "artifacts/rom-selector-direct-source-records-v1/rom-selector-direct-source-records.bin",
        "tools/export_rom_selector_text_bindings.py",
        "tools/verify_rom_selector_text_bindings.py",
        "tests/test_export_rom_selector_text_bindings.py",
        "tools/export_rom_selector_direct_source_records.py",
        "tools/verify_rom_selector_direct_source_records.py",
        "tests/test_export_rom_selector_direct_source_records.py",
        "tools/export_rom_selector_code_windows.py",
        "tools/verify_rom_selector_code_windows.py",
        "tests/test_export_rom_selector_code_windows.py",
    ):
        _copy_file(root, relative)


def _rehash(artifact: Path, name: str) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = _json(manifest_path)
    manifest["files"][name] = _sha((artifact / name).read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _coverage_with_batch_claims(
    coverage: dict, *, promotion_batch: str = "rom-selector-code-windows-v1"
) -> dict:
    """Overlay the frozen promotion ranges as if coverage already consumed them."""
    result = json.loads(json.dumps(coverage))
    claims = result["claims"]
    rebuilt_segments = []
    for segment in result["segments"]:
        start, end = segment["range"]
        cursor = start
        overlapping = [
            (index, range_start, range_end)
            for index, (range_start, range_end) in enumerate(PROMOTION_RANGES)
            if start <= range_start and range_end <= end
        ]
        for index, range_start, range_end in overlapping:
            self_id = f"selector-code-window-test-{index:02d}"
            if cursor < range_start:
                prefix = dict(segment)
                prefix["range"] = [cursor, range_start]
                rebuilt_segments.append(prefix)
            rebuilt_segments.append(
                {
                    "range": [range_start, range_end],
                    "primary_class": "consumer_code_slice",
                    "primary_claim_ids": [self_id],
                    "secondary_claim_ids": [],
                }
            )
            claims.append(
                {
                    "id": self_id,
                    "range": [range_start, range_end],
                    "role": "primary",
                    "primary_class": "consumer_code_slice",
                    "claim_kind": "consumer_code_slice",
                    "promotion_batch": promotion_batch,
                    "promoted_from_primary_class": "unknown",
                    "baseline_unknown_only": True,
                    "instruction_only_claimed": False,
                    "runtime_reachability_claimed": False,
                    "safe_editing": False,
                    "allocatable": False,
                    "bytes_sha256": _sha(
                        ROM_PATH.read_bytes()[range_start:range_end]
                    ),
                }
            )
            cursor = range_end
        if cursor < end:
            suffix = dict(segment)
            suffix["range"] = [cursor, end]
            rebuilt_segments.append(suffix)
    result["segments"] = rebuilt_segments
    summary = result["summary"]
    summary["classified_bytes"] += EXPECTED["promotion_bytes"]
    summary["unknown_bytes"] -= EXPECTED["promotion_bytes"]
    summary["claim_count"] += EXPECTED["promotion_range_count"]
    summary["segment_count"] = len(rebuilt_segments)
    summary["consumer_code_slice_bytes"] += EXPECTED["promotion_bytes"]
    summary["consumer_code_slice_claim_count"] += EXPECTED["promotion_range_count"]
    return result


def _thumb_bl(source: int, target: int) -> bytes:
    delta = target - (source + 4)
    if delta & 1 or not -(1 << 22) <= delta < (1 << 22):
        raise ValueError("test BL delta is not encodable")
    first = 0xF000 | ((delta >> 12) & 0x7FF)
    second = 0xF800 | ((delta >> 1) & 0x7FF)
    return first.to_bytes(2, "little") + second.to_bytes(2, "little")


class SelectorCodeWindowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()

    def test_rebuild_contract_counts_ranges_and_all_aggregate_hashes(self) -> None:
        exported, full_bundle, promotion_bundle = exporter.build_payload(ROOT)
        rebuilt, rebuilt_full, rebuilt_promotion = verifier.rebuild_payload(ROOT)
        self.assertEqual(exported, rebuilt)
        self.assertEqual(full_bundle, rebuilt_full)
        self.assertEqual(promotion_bundle, rebuilt_promotion)
        self.assertEqual(exported["summary"]["source_window_count"], 10)
        self.assertEqual(exported["summary"]["source_window_bytes"], 2754)
        self.assertEqual(exported["summary"]["promotion_range_count"], 19)
        self.assertEqual(exported["summary"]["promotion_bytes"], 1252)
        self.assertEqual(exported["summary"]["primary_overlap_bytes"], 1502)
        for key, value in EXPECTED.items():
            self.assertEqual(exported["summary"][key], value, key)
        self.assertEqual(
            [tuple(row["range"]) for row in exported["source_windows"]], WINDOWS
        )
        self.assertEqual(
            [tuple(row["range"]) for row in exported["promotion_ranges"]],
            PROMOTION_RANGES,
        )
        self.assertEqual(
            full_bundle,
            b"".join(self.rom[start:end] for start, end in WINDOWS),
        )
        self.assertEqual(
            promotion_bundle,
            b"".join(self.rom[start:end] for start, end in PROMOTION_RANGES),
        )

    def test_source_windows_have_packed_ranges_and_selector_provenance(self) -> None:
        payload, full_bundle, promotion_bundle = exporter.build_payload(ROOT)
        cursor = 0
        for row in payload["source_windows"]:
            start, end = row["range"]
            self.assertEqual(row["size"], end - start)
            self.assertEqual(row["gba_range"], [f"0x{ROM_BASE + start:08X}", f"0x{ROM_BASE + end:08X}"])
            self.assertEqual(row["raw_sha256"], _sha(self.rom[start:end]))
            self.assertEqual(row["packed_range"], [cursor, cursor + end - start])
            self.assertEqual(row["packed_sha256"], _sha(full_bundle[cursor:cursor + end - start]))
            self.assertTrue(row["selector_evidence"])
            self.assertTrue(row["provenance"])
            cursor = row["packed_range"][1]
        self.assertEqual(cursor, len(full_bundle))
        cursor = 0
        for row in payload["promotion_ranges"]:
            start, end = row["range"]
            self.assertEqual(row["raw_sha256"], _sha(self.rom[start:end]))
            self.assertEqual(row["packed_range"], [cursor, cursor + end - start])
            self.assertEqual(row["packed_sha256"], _sha(promotion_bundle[cursor:cursor + end - start]))
            self.assertEqual(row["primary_class"], "consumer_code_slice")
            self.assertEqual(row["claim_kind"], "consumer_code_slice")
            self.assertTrue(row["baseline_unknown_only"])
            self.assertFalse(row["instruction_only_claimed"])
            self.assertFalse(row["runtime_reachability_claimed"])
            self.assertFalse(row["safe_editing"])
            self.assertFalse(row["allocatable"])
            self.assertEqual(row["promotion_batch"], exporter.SCHEMA)
            cursor = row["packed_range"][1]
        self.assertEqual(cursor, len(promotion_bundle))

    def test_independent_verifier_rejects_payload_manifest_bundle_and_primary_reclaim_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            artifact = Path(raw).resolve() / "artifact"
            exporter.export_artifact(ROOT, artifact)
            for name in (
                exporter.PAYLOAD_NAME,
                exporter.FULL_BUNDLE_NAME,
                exporter.PROMOTION_BUNDLE_NAME,
            ):
                with self.subTest(name=name):
                    tampered = Path(raw).resolve() / (name + "-tampered")
                    shutil.copytree(artifact, tampered)
                    member = tampered / name
                    data = bytearray(member.read_bytes())
                    data[0] ^= 1
                    member.write_bytes(data)
                    _rehash(tampered, name)
                    self.assertFalse(verifier.verify_artifact(ROOT, tampered)["verified"])

            tampered_manifest = Path(raw).resolve() / "manifest-tampered"
            shutil.copytree(artifact, tampered_manifest)
            manifest = _json(tampered_manifest / "manifest.json")
            manifest["scope"]["safe_editing"] = True
            (tampered_manifest / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verifier.verify_artifact(ROOT, tampered_manifest)["verified"])

            primary_reclaim = Path(raw).resolve() / "primary-reclaim"
            shutil.copytree(artifact, primary_reclaim)
            payload_path = primary_reclaim / exporter.PAYLOAD_NAME
            payload = _json(payload_path)
            payload["source_windows"][0]["range"][1] += 2
            payload["promotion_ranges"][0]["baseline_unknown_only"] = False
            payload["promotion_ranges"][0]["primary_class"] = "arm_code"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verifier.verify_artifact(ROOT, primary_reclaim)["verified"])

    def test_semantic_contracts_fail_when_outer_slice_hashes_are_rebound(self) -> None:
        cases = (
            (0x08B02E, "stride"),
            (0x08B084, "stride table base"),
            (0x08B012, "BL callsite"),
            (0x08B422, "direct BL callsite"),
            (0x08B51C, "direct BL callsite"),
            (0x08CC80, "mapper semantic"),
            (0x08CD96, "copy parser boundary"),
            (0x097C82, "selector domain"),
            (0x06678C, "parser boundary"),
        )
        for implementation in (exporter, verifier):
            for gba, label in cases:
                with self.subTest(implementation=implementation.__name__, label=label):
                    tampered = bytearray(self.rom)
                    offset = gba
                    tampered[offset] ^= 1
                    with mock.patch.object(implementation, "ROM_SHA256", _sha(bytes(tampered))):
                        with self.assertRaisesRegex(ValueError, "stride|BL|selector|parser|semantic"):
                            implementation._validate_selector_semantics(
                                ROOT, bytes(tampered)
                            )

    def test_direct_consumer_full_rom_bl_denominator_rejects_an_extra_site(self) -> None:
        for implementation in (exporter, verifier):
            with self.subTest(implementation=implementation.__name__):
                tampered = bytearray(self.rom)
                tampered[0x100:0x104] = _thumb_bl(0x100, 0x08AFE0)
                with mock.patch.object(
                    implementation, "ROM_SHA256", _sha(bytes(tampered))
                ):
                    with self.assertRaisesRegex(ValueError, "BL denominator"):
                        implementation._validate_selector_semantics(
                            ROOT, bytes(tampered)
                        )

    def test_rebuild_accepts_own_post_integration_claims_without_live_hash_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            copied = Path(raw).resolve() / "root"
            _copy_minimal_root(copied)
            coverage_path = copied / "sequel/rom-byte-coverage.json"
            coverage = _coverage_with_batch_claims(_json(coverage_path))
            coverage_path.write_text(
                json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            exported = exporter.rebuild_payload(copied)
            rebuilt = verifier.rebuild_payload(copied)
            self.assertEqual(exported, rebuilt)
            self.assertEqual(exported[0]["summary"]["promotion_range_count"], 19)
            self.assertEqual(exported[0]["summary"]["promotion_bytes"], 1252)

    def test_rebuild_rejects_a_non_batch_primary_in_the_frozen_projection(self) -> None:
        for implementation in (exporter, verifier):
            with self.subTest(implementation=implementation.__name__):
                with tempfile.TemporaryDirectory() as raw:
                    copied = Path(raw).resolve() / "root"
                    _copy_minimal_root(copied)
                    coverage_path = copied / "sequel/rom-byte-coverage.json"
                    coverage = _coverage_with_batch_claims(
                        _json(coverage_path), promotion_batch="wrong-batch"
                    )
                    coverage_path.write_text(
                        json.dumps(
                            coverage, ensure_ascii=False, indent=2, sort_keys=True
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        ValueError, "projection|primary|batch|coverage"
                    ):
                        implementation.rebuild_payload(copied)

    def test_live_batch_segments_are_owned_and_summary_is_recomputed(self) -> None:
        def make_batch_claim_dangling(coverage: dict) -> None:
            segment = next(
                item
                for item in coverage["segments"]
                if tuple(item["range"]) == PROMOTION_RANGES[0]
            )
            size = segment["range"][1] - segment["range"][0]
            segment.update(
                {
                    "primary_class": "unknown",
                    "primary_claim_ids": [],
                }
            )
            coverage["summary"]["classified_bytes"] -= size
            coverage["summary"]["unknown_bytes"] += size

        mutations = {
            "missing promoted-from": lambda coverage: coverage["claims"][-19].pop(
                "promoted_from_primary_class"
            ),
            "segment class mismatch": lambda coverage: next(
                segment
                for segment in coverage["segments"]
                if tuple(segment["range"]) == PROMOTION_RANGES[0]
            ).__setitem__("primary_class", "arm_code"),
            "wrong range owner": lambda coverage: next(
                segment
                for segment in coverage["segments"]
                if tuple(segment["range"]) == PROMOTION_RANGES[0]
            ).__setitem__(
                "primary_claim_ids", ["selector-code-window-test-01"]
            ),
            "dangling batch claim": make_batch_claim_dangling,
            "consumer byte summary mismatch": lambda coverage: coverage["summary"].__setitem__(
                "consumer_code_slice_bytes",
                coverage["summary"]["consumer_code_slice_bytes"] - 1,
            ),
            "consumer claim summary mismatch": lambda coverage: coverage["summary"].__setitem__(
                "consumer_code_slice_claim_count",
                coverage["summary"]["consumer_code_slice_claim_count"] - 1,
            ),
        }
        windows = [{"range": [start, end]} for start, end in WINDOWS]
        for implementation in (exporter, verifier):
            for label, mutate in mutations.items():
                with self.subTest(implementation=implementation.__name__, label=label):
                    with tempfile.TemporaryDirectory() as raw:
                        copied = Path(raw).resolve() / "root"
                        coverage_path = copied / "sequel/rom-byte-coverage.json"
                        coverage_path.parent.mkdir(parents=True)
                        coverage = _coverage_with_batch_claims(
                            _json(ROOT / "sequel/rom-byte-coverage.json")
                        )
                        mutate(coverage)
                        coverage_path.write_text(
                            json.dumps(
                                coverage,
                                ensure_ascii=False,
                                indent=2,
                                sort_keys=True,
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                        with self.assertRaisesRegex(
                            ValueError,
                            "claim|owner|range|summary|totals|batch|segment",
                        ):
                            implementation._load_coverage(
                                copied, self.rom, windows
                            )

    def test_upstream_and_coverage_identity_or_source_window_tamper_fails_closed(self) -> None:
        for implementation in (exporter, verifier):
            with self.subTest(implementation=implementation.__name__):
                for label in ("rom-window", "upstream-selector", "coverage-primary-class"):
                    with self.subTest(label=label), tempfile.TemporaryDirectory() as raw:
                        copied = Path(raw).resolve() / "root"
                        _copy_minimal_root(copied)
                        if label == "rom-window":
                            rom = bytearray((copied / "rom/base.gba").read_bytes())
                            rom[0x0663A6] ^= 1
                            (copied / "rom/base.gba").write_bytes(rom)
                            pattern = "ROM|identity|source"
                        elif label == "upstream-selector":
                            upstream = copied / "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json"
                            payload = _json(upstream)
                            payload["consumer_evidence"]["decoded_semantics"]["renderer_parser"]["range"][1] += 2
                            upstream.write_text(
                                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8",
                            )
                            pattern = "bound source|upstream|selector"
                        else:
                            coverage = copied / "sequel/rom-byte-coverage.json"
                            payload = _json(coverage)
                            unknown = next(segment for segment in payload["segments"] if segment["primary_class"] == "unknown")
                            unknown["primary_class"] = "consumer_code_slice"
                            coverage.write_text(
                                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8",
                            )
                            pattern = "coverage|identity"
                        with self.assertRaisesRegex(ValueError, pattern):
                            implementation.rebuild_payload(copied)

    def test_output_root_ancestor_symlink_extra_and_missing_members_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            with self.assertRaisesRegex(ValueError, "root|ancestor"):
                exporter.export_artifact(ROOT, ROOT)
            with self.assertRaisesRegex(ValueError, "root|ancestor"):
                exporter.export_artifact(ROOT, ROOT.parent)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, linked / "artifact")
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "extra").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replaceable|foreign|member"):
                exporter.export_artifact(ROOT, foreign)
            missing = base / "missing-member"
            missing.mkdir()
            (missing / "manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replaceable|member"):
                exporter.export_artifact(ROOT, missing)
            accepted = base / "accepted"
            exporter.export_artifact(ROOT, accepted)
            (accepted / "unexpected-empty-directory").mkdir()
            with self.assertRaisesRegex(ValueError, "replaceable|member"):
                exporter._validate_output(ROOT, accepted)
            self.assertFalse(verifier.verify_artifact(ROOT, accepted)["verified"])

    def test_verifier_failure_never_publishes_accepted_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            artifact = Path(raw).resolve() / "artifact"
            failed = subprocess.CompletedProcess(
                args=["verifier"],
                returncode=1,
                stdout=b'{"verified": false, "errors": ["forced"]}\n',
                stderr=b"forced failure",
            )
            with mock.patch.object(exporter.subprocess, "run", return_value=failed):
                with self.assertRaisesRegex(ValueError, "independent verifier rejected"):
                    exporter.export_artifact(ROOT, artifact)
            self.assertFalse(artifact.exists())

    def test_repository_artifact_exact_report_and_verifier_does_not_import_exporter(self) -> None:
        artifact = ROOT / "artifacts/rom-selector-code-windows-v1"
        self.assertTrue(artifact.is_dir(), artifact)
        self.assertEqual(verifier.verify_artifact(ROOT, artifact), EXPECTED_REPORT)
        tree = ast.parse(
            (ROOT / "tools/verify_rom_selector_code_windows.py").read_text(
                encoding="utf-8"
            )
        )
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(
            any(name.endswith("export_rom_selector_code_windows") for name in imported),
            imported,
        )
        exporter_tree = ast.parse(
            (ROOT / "tools/export_rom_selector_code_windows.py").read_text(
                encoding="utf-8"
            )
        )
        exporter_imported = []
        for node in ast.walk(exporter_tree):
            if isinstance(node, ast.Import):
                exporter_imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                exporter_imported.append(node.module or "")
        self.assertFalse(
            any(name.endswith("verify_rom_selector_code_windows") for name in exporter_imported),
            exporter_imported,
        )


if __name__ == "__main__":
    unittest.main()
