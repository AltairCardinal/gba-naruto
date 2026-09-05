"""TDD contract tests for the fixed u8-index consumer tail packet."""

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

from tools import export_rom_fixed_index_u8_tail as exporter
from tools import verify_rom_fixed_index_u8_tail as verifier

ROOT = Path(__file__).resolve().parents[1]
ROM = (ROOT / "rom/base.gba").read_bytes()
EXPERIMENT = ROOT / "build/experiments/active/fixed-index-u8-tail-20260905"


class FixedIndexU8TailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = exporter.build_payload(ROOT)

    def test_exact_four_byte_promotion_and_narrow_scope(self) -> None:
        payload = self.payload
        self.assertEqual("rom-fixed-index-u8-tail-v1", payload["schema"])
        self.assertEqual([0x53E492, 0x53E496], payload["lookup_binding"]["candidate_range"])
        self.assertEqual("2b2c363f", payload["lookup_binding"]["candidate_raw_hex"])
        self.assertEqual([43, 44, 54, 63], payload["lookup_binding"]["candidate_values_u8"])
        self.assertEqual([0x6E, 0x6F, 0x70, 0x71], payload["lookup_binding"]["fixed_indices"])
        self.assertEqual(1, payload["promotion"]["claim_count"])
        self.assertEqual(4, payload["promotion"]["promotion_bytes"])
        self.assertEqual([[0x53E492, 0x53E496]],
                         [row["range"] for row in payload["promotion"]["claims"]])
        self.assertTrue(all(value is False for value in payload["scope"].values()))

    def test_consumer_literal_and_complete_caller_denominators(self) -> None:
        payload = self.payload
        self.assertEqual([0x7C724, 0x7C7B2], payload["consumer"]["range"])
        self.assertEqual("0006000e214d224a80180078", payload["consumer"]["proof_raw_hex"])
        self.assertEqual(0x0853E424, payload["consumer"]["literal_value"])
        denominator = payload["caller_denominator"]
        self.assertEqual(13, denominator["target_limited_bl_count"])
        self.assertEqual(list(exporter.CALL_OFFSETS), denominator["target_limited_bl_offsets"])
        self.assertNotIn("dynamic_call_offsets", denominator)
        self.assertEqual(
            list(exporter.EXCLUDED_NON_FIXED_CALL_OFFSETS),
            denominator["excluded_non_fixed_call_offsets"],
        )
        self.assertEqual([0x6E, 0x6F, 0x70, 0x71],
                         [row["index_u8"] for row in denominator["fixed_immediate_callers"]])
        self.assertEqual([0x7C7B8], denominator["literal_word_occurrences"])
        self.assertEqual([0x7C72E], denominator["literal_ldr_offsets"])

    def test_exporter_and_verifier_independently_rebuild_same_payload(self) -> None:
        self.assertEqual(self.payload, verifier.rebuild_payload(ROOT))
        source = (ROOT / "tools/verify_rom_fixed_index_u8_tail.py").read_text()
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_fixed_index_u8_tail" in item for item in imports))

    def test_coverage_identity_unknown_gate_and_existing_owners(self) -> None:
        baseline = self.payload["coverage_baseline"]
        self.assertEqual("2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01",
                         baseline["sha256"])
        self.assertTrue(baseline["candidate_current_unknown"])
        self.assertTrue(baseline["provenance_owners_preserved"])
        self.assertEqual(
            "artifacts/rom-post-story-dependency-precoverage-v1",
            baseline["snapshot_artifact"],
        )

    def test_replays_immutable_precoverage_without_reading_live_coverage(self) -> None:
        for implementation in (exporter, verifier):
            original = implementation._safe_file

            def reject_live(root, relative, *, _original=original):
                if relative == Path("sequel/rom-byte-coverage.json"):
                    raise AssertionError("live coverage must not be read")
                return _original(root, relative)

            with mock.patch.object(
                implementation, "_safe_file", side_effect=reject_live
            ):
                if implementation is exporter:
                    payload = implementation.build_payload(ROOT)
                else:
                    payload = implementation.rebuild_payload(ROOT)
            self.assertEqual(
                "artifacts/rom-post-story-dependency-precoverage-v1",
                payload["coverage_baseline"]["snapshot_artifact"],
            )

    def test_owner_gate_covers_every_byte_and_rejects_split_or_gap(self) -> None:
        expected_range = (10, 20)
        expected_class = "expected"
        expected_ids = ("claim",)
        accepted = {
            "segments": [
                {"range": [10, 15], "primary_class": expected_class,
                 "primary_claim_ids": ["claim"], "secondary_claim_ids": []},
                {"range": [15, 20], "primary_class": expected_class,
                 "primary_claim_ids": ["claim"], "secondary_claim_ids": []},
            ]
        }
        for implementation in (exporter._assert_owner_range, verifier._assert_owner_range):
            implementation(accepted, expected_range, expected_class, expected_ids)
            for bad in (
                {"segments": [accepted["segments"][0],
                              {**accepted["segments"][1], "primary_class": "changed"}]},
                {"segments": [{**accepted["segments"][0], "range": [10, 14]},
                              accepted["segments"][1]]},
            ):
                with self.assertRaises(ValueError):
                    implementation(bad, expected_range, expected_class, expected_ids)

    def test_representative_single_byte_rom_mutations_fail_closed(self) -> None:
        offsets = [0x53E492, 0x7C728, 0x7C72E, 0x7C732, 0x7C7B8,
                   0x7EB10, 0x7EB14, 0x7EBB8, 0x7EC6A, 0x7EC8C]
        for offset in offsets:
            with self.subTest(offset=hex(offset)):
                changed = bytearray(ROM)
                changed[offset] ^= 1
                for implementation in (exporter._build_from_rom, verifier._rebuild_from_rom):
                    with self.subTest(implementation=implementation.__module__):
                        with self.assertRaises(ValueError):
                            implementation(ROOT, bytes(changed), verify_identity=False)

    def test_full_rom_scanners_are_ordered_and_complete(self) -> None:
        self.assertEqual(list(exporter.CALL_OFFSETS), exporter._scan_target_bl(ROM, 0x7C724))
        self.assertEqual(list(verifier.CALL_OFFSETS), verifier._raw_scan_calls(ROM))
        self.assertEqual([0x7C7B8], exporter._scan_word(ROM, exporter.LITERAL_RAW))
        self.assertEqual([0x7C7B8], verifier._raw_scan_word(ROM))
        self.assertEqual([0x7C72E], exporter._scan_literal_loads(ROM, 0x7C7B8))
        self.assertEqual([0x7C72E], verifier._raw_scan_ldr_to_literal(ROM))

    def test_export_roundtrip_manifest_and_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, output)
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual((4, 1, 13, 4, 9),
                             (report["promotion_bytes"], report["claim_count"],
                              report["target_limited_bl_count"], report["fixed_caller_count"],
                              report["excluded_non_fixed_call_count"]))
            self.assertNotIn("dynamic_caller_count", report)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({"manifest.json", exporter.PAYLOAD_NAME},
                             {path.name for path in output.iterdir()})

    def test_artifact_tampering_and_extra_member_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            base = Path(raw); original = base / "original"
            exporter.export_artifact(ROOT, original)
            for label in ("payload", "manifest", "extra"):
                changed = base / label; shutil.copytree(original, changed)
                if label == "payload":
                    path = changed / exporter.PAYLOAD_NAME
                    value = json.loads(path.read_text()); value["promotion"]["promotion_bytes"] = 5
                    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
                elif label == "manifest":
                    path = changed / "manifest.json"
                    value = json.loads(path.read_text()); value["summary"]["claim_count"] = 2
                    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
                else:
                    (changed / "extra").write_text("x")
                self.assertFalse(verifier.verify_artifact(ROOT, changed)["verified"])

    def test_atomic_no_replace_and_symlink_guards(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            base = Path(raw); output = base / "output"
            exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                exporter.export_artifact(ROOT, output)
            alias = base / "alias"; alias.symlink_to(output, target_is_directory=True)
            self.assertFalse(verifier.verify_artifact(ROOT, alias)["verified"])
            source, destination = base / "source", base / "destination"
            source.mkdir(); destination.mkdir()
            (source / "new").write_text("new"); (destination / "keep").write_text("keep")
            with self.assertRaises(FileExistsError):
                exporter._publish_exclusive(source, destination)
            self.assertEqual("keep", (destination / "keep").read_text())

    def test_output_traversal_is_rejected_before_creating_any_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            base = Path(raw)
            escaped = base / "escaped"
            traversal = base / "unused" / ".." / "escaped" / "artifact"
            with self.assertRaises(ValueError):
                exporter.export_artifact(ROOT, traversal)
            self.assertFalse(escaped.exists())

    def test_manifest_binds_all_implementation_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"; exporter.export_artifact(ROOT, output)
            manifest = json.loads((output / "manifest.json").read_text())
            for name, path in {"contract": exporter.CONTRACT_PATH,
                               "exporter": exporter.EXPORTER_PATH,
                               "verifier": exporter.VERIFIER_PATH,
                               "test": exporter.TEST_PATH}.items():
                digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(digest, manifest["implementation"][name + "_sha256"])

    def test_direct_cli_export_and_verify_wiring(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            subprocess.run(
                ["python3", "tools/export_rom_fixed_index_u8_tail.py", "--root", ".",
                 "--output", output.relative_to(ROOT).as_posix()],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            result = subprocess.run(
                ["python3", "tools/verify_rom_fixed_index_u8_tail.py", "--root", ".",
                 "--artifact", output.relative_to(ROOT).as_posix()],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            self.assertTrue(json.loads(result.stdout)["verified"])


if __name__ == "__main__":
    unittest.main()
