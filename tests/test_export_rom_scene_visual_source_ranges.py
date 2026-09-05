#!/usr/bin/env python3
"""TDD contract for the frozen scene-visual source-range promotion."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools import export_rom_scene_visual_source_ranges as exporter
from tools import verify_rom_scene_visual_source_ranges as verifier


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
ARTIFACT = ROOT / "artifacts/rom-scene-visual-source-ranges-v1"
RUN_DIR = ROOT / "build/experiments/active/luna-scene-visual-source-ranges-20260820/r1"

ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "b95e1239420e416fe03244d8e3584adc5dd93470dfa8bfe8e501addb78c3f2cd"
FULL_RANGE_SHA256 = "6140246af1cf1a3c23e32ecf8d2e5b059a209f2d0a33131499a2bdb82c12743c"
CANDIDATE_RANGE_SHA256 = "6e8715e8eb59ad0a4912f5c714401c65b7911f4ec58b95d8d9d4fd7ae5e4e755"
PROMOTION_RANGE_SHA256 = "13dc504bebbff131700bb77869afb29e98a2f032d60bab4165eba90bcb2be7df"
PROMOTION_BUNDLE_SHA256 = "2eec5a820e1f79cc817e5976dc710e889adbee1038a4247652812a695832bc95"
VERIFY_SCHEMA = "rom-scene-visual-source-ranges-verification-v1"
EXPECTED_PRODUCER_COMMAND = [
    "python3",
    "tools/export_rom_scene_visual_source_ranges.py",
    "--root",
    ".",
    "--output-dir",
    "build/experiments/active/luna-scene-visual-source-ranges-20260820/r2/final",
]
EXPECTED_VERIFIER_COMMAND = [
    "python3",
    "tools/verify_rom_scene_visual_source_ranges.py",
    "--root",
    ".",
    "--artifact-dir",
    "build/experiments/active/luna-scene-visual-source-ranges-20260820/r2/final",
]
EXPECTED_MANIFEST_KEYS = {
    "schema",
    "artifact_schema",
    "artifact_status",
    "files",
    "producer",
    "verifier",
    "rom",
    "source_identity",
    "coverage_baseline",
    "scope",
    "limitations",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _copy_artifact(source: Path, target: Path) -> None:
    shutil.copytree(source, target, symlinks=True)


def _copy_verifier_root(source: Path, target: Path) -> None:
    for relative in (
        "rom",
        "artifacts/scene-visual-packs-v1",
        "artifacts/rom-scene-visual-source-ranges-v1",
        "tools/verify_scene_visual_packs.py",
        "tools/export_rom_scene_visual_source_ranges.py",
        "tools/verify_rom_scene_visual_source_ranges.py",
        "tests/test_export_rom_scene_visual_source_ranges.py",
        "sequel/rom-byte-coverage.json",
    ):
        source_path = source / relative
        target_path = target / relative
        if source_path.is_dir():
            shutil.copytree(source_path, target_path, symlinks=True)
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


class SceneVisualSourceRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()

    def test_frozen_denominators_counts_bytes_and_hashes(self):
        payload, bundle = exporter.build_payload(ROOT)
        rebuilt, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(payload, rebuilt)
        self.assertEqual(bundle, rebuilt_bundle)
        self.assertEqual(len(bundle), 3257)
        self.assertEqual(_sha(bundle), PROMOTION_BUNDLE_SHA256)

        source = payload["source_denominator"]
        candidate = payload["candidate_denominator"]
        overlap = payload["overlap_denominator"]
        promotion = payload["promotion_denominator"]
        self.assertEqual((source["range_count"], source["byte_count"]), (57, 88756))
        self.assertEqual((candidate["range_count"], candidate["byte_count"]), (29, 3288))
        self.assertEqual((overlap["range_count"], overlap["byte_count"]), (1, 31))
        self.assertEqual((promotion["range_count"], promotion["byte_count"]), (29, 3257))
        self.assertEqual(source["range_vector_sha256"], FULL_RANGE_SHA256)
        self.assertEqual(candidate["range_vector_sha256"], CANDIDATE_RANGE_SHA256)
        self.assertEqual(promotion["range_vector_sha256"], PROMOTION_RANGE_SHA256)
        self.assertEqual(
            payload["summary"]["candidate_class_counts"],
            {
                "shared_obj_palette": {"range_count": 2, "byte_count": 64},
                "background_palette": {"range_count": 9, "byte_count": 2304},
                "definition": {"range_count": 9, "byte_count": 728},
                "animation": {"range_count": 9, "byte_count": 192},
            },
        )

    def test_pack5_definition_is_split_only_for_promotion(self):
        payload, _ = exporter.build_payload(ROOT)
        candidate = [
            row["range"]
            for row in payload["candidate_denominator"]["records"]
            if row["source_id"] == "pack-05-definition"
        ]
        promotion = [
            row["range"]
            for row in payload["promotion_denominator"]["records"]
            if row["source_id"] == "pack-05-definition"
        ]
        self.assertEqual(candidate, [[0x407BF0, 0x407C50]])
        self.assertEqual(promotion, [[0x407C0F, 0x407C50]])
        self.assertEqual(
            payload["overlap_denominator"]["records"][0]["range"],
            [0x407BF0, 0x407C0F],
        )

    def test_pack5_candidate_state_boundary_is_explicit(self):
        payload, _ = exporter.build_payload(ROOT)
        record = next(
            row
            for row in payload["candidate_denominator"]["records"]
            if row["source_id"] == "pack-05-definition"
        )
        self.assertEqual(record["baseline_state"], "mixed")
        self.assertEqual(record["promotion_state"], "mixed")
        self.assertEqual(record["known_slices"], [[0x407BF0, 0x407C0F]])
        self.assertEqual(record["unknown_slices"], [[0x407C0F, 0x407C50]])

    def test_promotion_slices_stay_within_promotion_range(self):
        payload, _ = exporter.build_payload(ROOT)
        promotion = payload["promotion_denominator"]["records"]
        for record in promotion:
            start, end = record["range"]
            for field in ("known_slices", "unknown_slices"):
                for slice_start, slice_end in record.get(field, []):
                    self.assertGreaterEqual(slice_start, start)
                    self.assertLessEqual(slice_end, end)
        pack5 = next(row for row in promotion if row["source_id"] == "pack-05-definition")
        self.assertNotIn("known_slices", pack5)
        self.assertNotIn("unknown_slices", pack5)

    def test_manifest_freezes_top_level_verifier_and_commands(self):
        manifest = _json(ARTIFACT / "manifest.json")
        self.assertEqual(set(manifest), EXPECTED_MANIFEST_KEYS)
        self.assertNotIn("verification", manifest)
        self.assertEqual(manifest["producer"]["command"], EXPECTED_PRODUCER_COMMAND)
        self.assertEqual(
            set(manifest["verifier"]),
            {"schema", "command", "exit_code", "report", "verifier_sha256"},
        )
        self.assertEqual(manifest["verifier"]["schema"], VERIFY_SCHEMA)
        self.assertEqual(manifest["verifier"]["command"], EXPECTED_VERIFIER_COMMAND)

    def test_manifest_command_resigning_and_canonical_rewrite_fail_closed(self):
        for field in ("producer", "verifier"):
            with tempfile.TemporaryDirectory() as raw:
                tampered = Path(raw) / field
                _copy_artifact(ARTIFACT, tampered)
                manifest = _json(tampered / "manifest.json")
                if field not in manifest:
                    self.fail(f"manifest missing top-level {field} evidence")
                manifest[field]["command"] = list(manifest[field]["command"])
                manifest[field]["command"][-1] = "tampered-output"
                (tampered / "manifest.json").write_bytes(_canonical(manifest))
                self.assertFalse(verifier.verify_artifact(ROOT, tampered)["verified"])

        with tempfile.TemporaryDirectory() as raw:
            tampered = Path(raw) / "manifest-key"
            _copy_artifact(ARTIFACT, tampered)
            manifest = _json(tampered / "manifest.json")
            manifest["resigned"] = True
            (tampered / "manifest.json").write_bytes(_canonical(manifest))
            self.assertFalse(verifier.verify_artifact(ROOT, tampered)["verified"])

    def test_verifier_report_has_frozen_top_level_schema(self):
        report = verifier.verify_artifact(ROOT, ARTIFACT)
        self.assertEqual(report["schema"], VERIFY_SCHEMA)
        self.assertTrue(report["verified"], report["errors"])

    def test_frozen_artifact_verification_ignores_live_coverage_drift(self):
        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            temp_root = Path(raw) / "root"
            _copy_verifier_root(ROOT, temp_root)
            coverage_path = temp_root / "sequel/rom-byte-coverage.json"
            coverage = _json(coverage_path)
            coverage["summary"]["unknown_bytes"] += 1
            coverage_path.write_bytes(_canonical(coverage))
            artifact = temp_root / "artifacts/rom-scene-visual-source-ranges-v1"
            report = verifier.verify_artifact(temp_root, artifact)
            self.assertTrue(report["verified"], report["errors"])

    def test_export_and_explicit_baseline_validation_reject_coverage_drift(self):
        payload, _ = exporter.build_payload(ROOT)
        baseline = _json(ROOT / "sequel/rom-byte-coverage.json")
        drifted = copy.deepcopy(baseline)
        drifted["summary"]["unknown_bytes"] += 1
        with self.assertRaisesRegex(ValueError, "baseline|coverage|summary|identity"):
            verifier.validate_baseline(ROOT, payload, drifted)

        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            temp_root = Path(raw) / "root"
            _copy_verifier_root(ROOT, temp_root)
            coverage_path = temp_root / "sequel/rom-byte-coverage.json"
            coverage = _json(coverage_path)
            coverage["summary"]["unknown_bytes"] += 1
            coverage_path.write_bytes(_canonical(coverage))
            with self.assertRaisesRegex(ValueError, "coverage|baseline|identity"):
                exporter.build_payload(temp_root)

    def test_source_records_rebuild_table_palettes_lz77_and_parser_extents(self):
        payload, _ = exporter.build_payload(ROOT)
        records = payload["source_denominator"]["records"]
        self.assertEqual(
            {record["kind"] for record in records},
            {"source_table", "lz77", "shared_obj_palette", "background_palette", "definition", "animation"},
        )
        self.assertEqual(
            {record["kind"]: sum(1 for row in records if row["kind"] == record["kind"]) for record in records},
            {
                "source_table": 1,
                "lz77": 27,
                "shared_obj_palette": 2,
                "background_palette": 9,
                "definition": 9,
                "animation": 9,
            },
        )
        self.assertEqual(
            {record["kind"]: sum(row["size"] for row in records if row["kind"] == record["kind"]) for record in records},
            {
                "source_table": 252,
                "lz77": 85216,
                "shared_obj_palette": 64,
                "background_palette": 2304,
                "definition": 728,
                "animation": 192,
            },
        )
        self.assertTrue(all(row["raw_sha256"] == _sha(self.rom[row["range"][0] : row["range"][1]]) for row in records))
        self.assertTrue(all(row["range"][0] < row["range"][1] for row in records))

    def test_source_rom_baseline_and_upstream_verifier_identity_are_bound(self):
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["rom"], {"path": "rom/base.gba", "size": 6291456, "sha256": ROM_SHA256})
        self.assertEqual(payload["coverage_baseline"]["sha256"], COVERAGE_SHA256)
        self.assertEqual(payload["coverage_baseline"]["summary"], {
            "classified_bytes": 6102121,
            "unknown_bytes": 189335,
            "claim_count": 13872,
            "segment_count": 16119,
        })
        source = payload["source_identity"]
        self.assertEqual(source["artifact_path"], "artifacts/scene-visual-packs-v1")
        self.assertEqual(source["manifest_sha256"], _sha((ROOT / "artifacts/scene-visual-packs-v1/manifest.json").read_bytes()))
        self.assertEqual(source["verifier_path"], "tools/verify_scene_visual_packs.py")
        self.assertEqual(source["verifier_sha256"], _sha((ROOT / source["verifier_path"]).read_bytes()))
        self.assertTrue(source["verifier_report"]["verified"])

    def test_candidate_is_current_unknown_except_one_exact_primary_overlap(self):
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["overlap_denominator"]["records"], [{
            "range": [0x407BF0, 0x407C0F],
            "size": 31,
            "source_id": "pack-05-definition",
            "primary_class": "lz77_syntax_unbound",
            "primary_claim_ids": ["unbound-lz77-35-407bec"],
        }])
        self.assertTrue(all(row["baseline_state"] == "current_unknown" for row in payload["promotion_denominator"]["records"]))

    def test_parser_pointer_count_and_terminator_changes_fail_closed(self):
        for implementation in (exporter, verifier):
            with self.subTest(implementation=implementation.__name__, case="table pointer"):
                tampered = bytearray(self.rom)
                tampered[0x5A4CE8] ^= 1
                with self.assertRaisesRegex(ValueError, "ROM|table|source"):
                    implementation.rebuild_from_rom(ROOT, bytes(tampered))
            with self.subTest(implementation=implementation.__name__, case="definition terminator"):
                tampered = bytearray(self.rom)
                tampered[0x407BF0 + 20 - 1] ^= 1
                with self.assertRaisesRegex(ValueError, "ROM|definition|terminator|component"):
                    implementation.rebuild_from_rom(ROOT, bytes(tampered))
            with self.subTest(implementation=implementation.__name__, case="animation terminator"):
                tampered = bytearray(self.rom)
                tampered[0x406090 + 6] ^= 1
                with self.assertRaisesRegex(ValueError, "ROM|animation|timeline|terminator"):
                    implementation.rebuild_from_rom(ROOT, bytes(tampered))

    def test_baseline_class_range_and_owner_misbindings_fail_closed(self):
        payload, _ = exporter.build_payload(ROOT)
        baseline = _json(ROOT / "sequel/rom-byte-coverage.json")
        for label, mutate in (
            ("class", lambda item: item.__setitem__("primary_class", "unknown")),
            ("range", lambda item: item.__setitem__("range", [0x407BF0, 0x407C10])),
            ("owner", lambda item: item.__setitem__("primary_claim_ids", ["wrong-owner"])),
        ):
            tampered = copy.deepcopy(baseline)
            target = next(item for item in tampered["segments"] if item["range"][0] < 0x407C0F and item["range"][1] > 0x407BF0 and item["primary_class"] == "lz77_syntax_unbound")
            mutate(target)
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "baseline|overlap|owner|coverage"):
                    verifier.validate_baseline(ROOT, payload, tampered)

    def test_verifier_is_independent_of_exporter_and_coverage_auditor(self):
        source = (ROOT / "tools/verify_rom_scene_visual_source_ranges.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        rendered = "\n".join(ast.unparse(node) for node in imports)
        self.assertNotIn("export_rom_scene_visual_source_ranges", rendered)
        self.assertNotIn("audit_rom_byte_coverage", rendered)

    def test_committed_artifact_is_exact_and_independently_verified(self):
        report = verifier.verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report["summary"]["promotion_bytes"], 3257)
        self.assertEqual(report["bundle_sha256"], PROMOTION_BUNDLE_SHA256)
        self.assertEqual(
            {path.relative_to(ARTIFACT).as_posix() for path in ARTIFACT.rglob("*")},
            {"manifest.json", "rom-scene-visual-source-ranges.json", "rom-scene-visual-source-ranges.bin"},
        )

    def test_rehashed_payload_bundle_manifest_and_noncanonical_files_fail(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            for name in ("payload", "bundle"):
                tampered = base / f"{name}-tampered"
                _copy_artifact(ARTIFACT, tampered)
                path = tampered / ("rom-scene-visual-source-ranges.json" if name == "payload" else "rom-scene-visual-source-ranges.bin")
                data = bytearray(path.read_bytes())
                data[0] ^= 1
                path.write_bytes(data)
                manifest = _json(tampered / "manifest.json")
                manifest["files"][path.name] = _sha(bytes(data))
                (tampered / "manifest.json").write_bytes(_canonical(manifest))
                self.assertFalse(verifier.verify_artifact(ROOT, tampered)["verified"])

            noncanonical = base / "noncanonical"
            _copy_artifact(ARTIFACT, noncanonical)
            payload_path = noncanonical / "rom-scene-visual-source-ranges.json"
            payload = _json(payload_path)
            payload_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            manifest = _json(noncanonical / "manifest.json")
            manifest["files"][payload_path.name] = _sha(payload_path.read_bytes())
            (noncanonical / "manifest.json").write_bytes(_canonical(manifest))
            self.assertFalse(verifier.verify_artifact(ROOT, noncanonical)["verified"])

    def test_extra_missing_and_symlink_members_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            for label in ("extra", "missing"):
                tampered = base / label
                _copy_artifact(ARTIFACT, tampered)
                if label == "extra":
                    (tampered / "extra.txt").write_text("x", encoding="utf-8")
                else:
                    (tampered / "rom-scene-visual-source-ranges.bin").unlink()
                self.assertFalse(verifier.verify_artifact(ROOT, tampered)["verified"])

            linked = base / "member-symlink"
            _copy_artifact(ARTIFACT, linked)
            target = base / "outside.bin"
            target.write_bytes((linked / "rom-scene-visual-source-ranges.bin").read_bytes())
            (linked / "rom-scene-visual-source-ranges.bin").unlink()
            (linked / "rom-scene-visual-source-ranges.bin").symlink_to(target)
            self.assertFalse(verifier.verify_artifact(ROOT, linked)["verified"])

            real = base / "real"
            real.mkdir()
            parent = base / "linked"
            parent.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, parent / "artifact")

    def test_export_rejects_root_ancestor_foreign_and_does_not_publish_failed_candidate(self):
        with self.assertRaisesRegex(ValueError, "root|ancestor"):
            exporter.export_artifact(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "root|ancestor"):
            exporter.export_artifact(ROOT, ROOT.parent)
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign"):
                exporter.export_artifact(ROOT, foreign)

            target = base / "not-published"
            with mock.patch.object(exporter, "verify_artifact", return_value={"verified": False, "errors": ["forced"]}):
                with self.assertRaisesRegex(ValueError, "verifier"):
                    exporter.export_artifact(ROOT, target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
