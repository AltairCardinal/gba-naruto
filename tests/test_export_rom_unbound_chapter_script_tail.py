"""TDD contract tests for the unbound chapter-script tail packet.

The first RED run intentionally executes this file before the two product
modules exist.  The tests then become the frozen public contract for the
small packet and its independent verifier.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/unbound-chapter-tail-luna-20260901"


class UnboundChapterScriptTailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # RED: this import is expected to fail on the first run, before the
        # exporter and verifier are implemented.
        from tools import export_rom_unbound_chapter_script_tail as exporter
        from tools import verify_rom_unbound_chapter_script_tail as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def _export(self, directory: Path) -> Path:
        output = directory / "artifact"
        self.exporter.export_artifact(ROOT, output)
        return output

    def test_frozen_tail_vector_and_unbound_roots(self) -> None:
        payload = self.payload
        self.assertEqual("rom-chapter-script-unbound-tail-v1", payload["schema"])
        vector = payload["root_vector"]
        self.assertEqual([0x060FA4, 0x060FAC], vector["file_range"])
        self.assertEqual("dfbf0508d3c60508", vector["bytes"])
        self.assertEqual(
            "ff3c2f49e8e01470390987ec0e7978068910c45f3ea0f020c1bb0c5f588e553f",
            vector["sha256"],
        )
        self.assertEqual(
            [(45, 0x05BFDF), (46, 0x05C6D3)],
            [(row["slot"], row["target_file_offset"]) for row in vector["entries"]],
        )
        self.assertEqual("fixed_physical_tail_root_vector", vector["kind"])
        self.assertFalse(vector["natural_reachability_asserted"])
        self.assertFalse(vector["consumer_asserted"])

    def test_two_root_closures_count_edges_and_keep_duplicate_0x32_successors(self) -> None:
        payload = self.payload
        summary = payload["closure"]["summary"]
        self.assertEqual(128, summary["node_count"])
        self.assertEqual(128, summary["directed_edge_count"])
        self.assertEqual(13, summary["terminal_node_count"])
        self.assertEqual(
            {"0x00": 13, "0x01": 47, "0x02": 4, "0x04": 3, "0x08": 47, "0x12": 12, "0x32": 2},
            summary["opcode_counts"],
        )
        self.assertEqual("preserve_order_and_duplicates", payload["grammar"]["edge_policy"])
        root = next(row for row in payload["nodes"] if row["file_offset"] == 0x05C6D3)
        self.assertEqual(11, len(root["successors"]))
        self.assertEqual(root["successors"][0], root["successors"][-1])
        self.assertEqual(0, summary["frontier_count"])
        self.assertEqual(0, len(payload["closure"]["frontiers"]))

    def test_frozen_range_and_bundle(self) -> None:
        payload = self.payload
        self.assertEqual(
            [[0x05BFDF, 0x05C5DC], [0x05C6D3, 0x05CD40]],
            payload["closure"]["merged_ranges"],
        )
        self.assertEqual(3178, payload["closure"]["summary"]["consumed_bytes"])
        self.assertEqual(
            "7f6400492903560a93ba7d226a75986dbb298e78040156b0dc4bcf4cda5655e4",
            payload["closure"]["bundle_sha256"],
        )

    def test_claims_are_exact_for_both_unbound_roots(self) -> None:
        claims = self.payload["promotion"]["claims"]
        self.assertEqual(3, len(claims))
        self.assertEqual(
            {
                "chapter_script_unbound_root_pointer_vector",
                "chapter_script_syntax_unbound",
            },
            {row["primary_class"] for row in claims},
        )
        self.assertIn(0x05BFDF, [row["range"][0] for row in claims])
        self.assertEqual(3186, self.payload["promotion"]["promotion_bytes"])

    def test_happy_path_is_atomic_and_independently_verified(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            report = self.verifier.verify_artifact(ROOT, artifact)
            self.assertTrue(report["verified"], report)
            self.assertEqual(3186, report["promotion_bytes"])
            self.assertEqual(
                {"manifest.json", self.exporter.PAYLOAD_NAME, self.exporter.BUNDLE_NAME},
                {path.name for path in artifact.iterdir()},
            )

    def test_red_initial_missing_modules_are_part_of_the_tdd_contract(self) -> None:
        self.assertTrue((ROOT / "tools/export_rom_unbound_chapter_script_tail.py").is_file())
        self.assertTrue((ROOT / "tools/verify_rom_unbound_chapter_script_tail.py").is_file())

    def test_rom_tamper_fails_closed(self) -> None:
        bad = bytearray(self.rom)
        bad[0x05C6D3] ^= 1
        with self.assertRaises(ValueError):
            self.exporter.build_payload(ROOT, rom_override=bytes(bad))

    def test_current_coverage_is_not_a_replay_input(self) -> None:
        current = ROOT / self.exporter.BASELINE_COVERAGE_PATH
        self.assertNotEqual(
            self.exporter.BASELINE_SHA256,
            hashlib.sha256(current.read_bytes()).hexdigest(),
        )
        self.assertNotIn("coverage_baseline", self.payload)
        self.assertEqual(
            {
                "path": "sequel/rom-byte-coverage.json",
                "sha256": self.exporter.BASELINE_SHA256,
                "observed_during_this_build": False,
                "projection_gate_deferred_to": "tools/audit_rom_byte_coverage.py",
            },
            self.payload["historical_coverage_reference"],
        )
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            report = self.verifier.verify_artifact(ROOT, artifact)
            self.assertTrue(report["verified"], report)
            self.assertFalse(report["current_unknown_checked"])
            self.assertTrue(report["coverage_projection_gate_deferred"])

    def test_payload_bundle_and_manifest_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            payload_path = artifact / self.exporter.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["promotion"]["promotion_bytes"] += 1
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

            artifact = self._export(Path(raw) / "bundle")
            bundle = artifact / self.exporter.BUNDLE_NAME
            bundle.write_bytes(bundle.read_bytes()[:-1] + bytes([bundle.read_bytes()[-1] ^ 1]))
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

            artifact = self._export(Path(raw) / "manifest")
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifact_status"] = "accepted"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_extra_file_and_symlink_output_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw, tempfile.TemporaryDirectory() as outside:
            root = Path(raw)
            foreign = root / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, foreign)

            link = root / "link"
            os.symlink(outside, link)
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, link / "artifact")

    def test_slot_pointer_tamper_and_claim_overreach_fail_closed(self) -> None:
        bad = bytearray(self.rom)
        bad[0x060FA4] ^= 1
        with self.assertRaises(ValueError):
            self.exporter.build_payload(ROOT, rom_override=bytes(bad))

        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            path = artifact / self.exporter.PAYLOAD_NAME
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["promotion"]["claims"][1]["range"][1] += 1
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_semantic_scope_and_closure_receipt_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            path = artifact / self.exporter.PAYLOAD_NAME
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["scope"]["consumer_bound"] = True
            payload["scope"]["natural_reachability_complete"] = True
            payload["scope"]["editing_safety_proven"] = True
            payload["limitations"] = []
            payload["grammar"]["edge_policy"] = "deduplicate"
            payload["closure"]["node_vector_sha256"] = "0" * 64
            payload["closure"]["frontiers"] = [0x05CD40]
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw_payload = path.read_bytes()
            manifest["files"][self.exporter.PAYLOAD_NAME] = {
                "size": len(raw_payload),
                "sha256": hashlib.sha256(raw_payload).hexdigest(),
            }
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_artifact_children_and_report_output_reject_symlinks(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw, tempfile.TemporaryDirectory() as outside:
            artifact = self._export(Path(raw))
            payload = artifact / self.exporter.PAYLOAD_NAME
            foreign_payload = Path(outside) / "payload.json"
            foreign_payload.write_bytes(payload.read_bytes())
            payload.unlink()
            os.symlink(foreign_payload, payload)
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

            report_target = Path(outside) / "keep.json"
            report_target.write_text("keep", encoding="utf-8")
            report_link = Path(raw) / "report.json"
            os.symlink(report_target, report_link)
            with self.assertRaises(ValueError):
                self.verifier.write_report_atomic(
                    report_link,
                    {"schema": "test", "verified": False},
                )
            self.assertEqual("keep", report_target.read_text(encoding="utf-8"))

    def test_verifier_rejects_artifact_through_ancestor_symlink(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            root = Path(raw)
            real_parent = root / "real"
            artifact = self._export(real_parent)
            alias = root / "alias"
            os.symlink(real_parent, alias)
            report = self.verifier.verify_artifact(ROOT, alias / artifact.name)
            self.assertFalse(report["verified"], report)

    def test_verifier_is_independent_from_unbound_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_unbound_chapter_script_tail.py").read_text(encoding="utf-8")
        imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_unbound_chapter_script_tail" in ast.unparse(node) for node in imports))


if __name__ == "__main__":
    unittest.main()
