#!/usr/bin/env python3
"""TDD contract for the pre-battle menu controller CFG candidate packet."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "build/experiments/active/prebattle-menu-controller-cfg/luna-r1-20260904"


class PrebattleMenuControllerCfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_prebattle_menu_controller_cfg as exporter
        from tools import rom_prebattle_menu_controller_cfg_contract as contract
        from tools import verify_rom_prebattle_menu_controller_cfg as verifier

        cls.exporter = exporter
        cls.contract = contract
        cls.verifier = verifier
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_real_identity_producer_and_selector_binding(self) -> None:
        payload = self.payload
        self.assertEqual(self.contract.SCHEMA, payload["schema"])
        self.assertEqual(
            {"path": "rom/base.gba", "size": 6_291_456,
             "sha256": self.contract.ROM_SHA256},
            payload["rom"],
        )
        self.assertEqual(self.contract.COVERAGE_SHA256,
                         payload["coverage_baseline"]["sha256"])
        producer = payload["producer_denominator"]
        self.assertEqual(
            [[0x08F894, 0x08F190, "bl", 4, "fff77cfc"]],
            producer["matches"],
        )
        self.assertEqual(self.contract.PRODUCER_SCAN_DENOMINATOR_SHA256,
                         producer["denominator_sha256"])
        self.assertEqual("story-callback-reachable_thumb_code-04-08f872",
                         producer["owner_claim_id"])
        selector = payload["selector_binding"]
        self.assertEqual([0x08F380, 0x08F394], selector["range"])
        self.assertEqual(0x08F392, selector["indirect_site"])
        self.assertEqual(5, selector["max_selector"])
        self.assertEqual(0x08F398, selector["pc_literal_site"])
        self.assertEqual(0x0808F39C, selector["table_base_value"])
        self.assertEqual(list(self.contract.TABLE_TARGETS), selector["table_targets"])
        self.assertEqual(self.contract.TABLE_SHA256, selector["table_sha256"])

    def test_exact_recursive_traversal_dependency_and_frontiers(self) -> None:
        payload = self.payload
        denominator = payload["target_local_denominator"]
        self.assertEqual(786, denominator["instruction_count"])
        self.assertEqual(1752, denominator["instruction_bytes"])
        self.assertEqual(699, denominator["current_unknown_instruction_count"])
        self.assertEqual(1564, denominator["current_unknown_code_bytes"])
        self.assertEqual(87, denominator["dependency_instruction_count"])
        self.assertEqual(188, denominator["dependency_code_bytes"])
        self.assertEqual(83, denominator["opaque_call_count"])
        self.assertEqual(35, denominator["opaque_unique_target_count"])
        self.assertEqual(
            [[0x06889E, "indirect_pc_target"], [0x068D1C, "indirect_pc_target"],
             [0x08793C, "indirect_pc_target"], [0x08CE22, "indirect_pc_target"],
             [0x08EED6, "indirect_pc_target"], [0x08EF26, "indirect_pc_target"],
             [0x08F4C8, "indirect_pc_target"]],
            denominator["frontiers"],
        )
        self.assertEqual(
            self.contract.DEPENDENCY_CODE_RANGES,
            tuple(map(tuple, denominator["dependency_code_ranges"])),
        )
        promotion = payload["promotion"]
        self.assertEqual(1564, promotion["code_bytes"])
        self.assertEqual(332, promotion["literal_bytes"])
        self.assertEqual(24, promotion["jump_table_bytes"])
        self.assertEqual(1920, promotion["promotion_bytes"])
        self.assertEqual(self.contract.CURRENT_UNKNOWN_CODE_RANGES,
                         tuple(map(tuple, promotion["code_ranges"])))
        self.assertEqual(self.contract.CURRENT_UNKNOWN_LITERAL_RANGES,
                         tuple(map(tuple, promotion["literal_ranges"])))
        self.assertEqual([0x08F39C, 0x08F3B4], promotion["jump_table_range"])
        self.assertEqual(self.contract.UNION_RANGES,
                         tuple(map(tuple, promotion["union_ranges"])))

    def test_recursive_unknown_callees_and_code_dependencies_are_bound(self) -> None:
        denominator = self.payload["target_local_denominator"]
        opaque = denominator["opaque_calls"]
        self.assertEqual(83, len(opaque))
        self.assertEqual(35, len({row[1] for row in opaque}))
        self.assertEqual(self.contract.OPAQUE_CALL_VECTOR_SHA256,
                         denominator["opaque_call_vector_sha256"])
        self.assertIn([0x08F284, 0x08F2A2],
                      [list(row) for row in denominator["dependency_code_ranges"]])
        self.assertIn([0x08CD5A, 0x08CDF8],
                      [list(row) for row in denominator["dependency_code_ranges"]])

    def test_literal_binding_denominator_and_jump_table_are_frozen(self) -> None:
        promotion = self.payload["promotion"]
        self.assertEqual(84, promotion["literal_reference_count"])
        self.assertEqual(83, promotion["unique_literal_word_count"])
        self.assertEqual(self.contract.LITERAL_RANGE_SHA256,
                         promotion["literal_range_sha256"])
        self.assertEqual(self.contract.LITERAL_PACKED_SHA256,
                         promotion["literal_packed_sha256"])
        self.assertEqual(self.contract.TABLE_SHA256,
                         promotion["jump_table_packed_sha256"])

    def test_denominator_hashes_are_recomputed_not_echoed(self) -> None:
        for name in (
            "PRODUCER_MATCH_VECTOR_SHA256",
            "OPAQUE_CALL_VECTOR_SHA256",
            "PROMOTION_RANGE_SHA256",
            "PRODUCER_OWNER_CLAIM_ID",
            "PRODUCER_OWNER_PRIMARY_CLASS",
        ):
            with self.subTest(name=name), mock.patch.object(
                self.contract, name, "0" * 64
            ):
                with self.assertRaises(ValueError):
                    self.exporter.build_payload(ROOT)
                with self.assertRaises(ValueError):
                    self.verifier._rebuild(ROOT)

        forged_union = ((0, self.contract.PROMOTION_BYTES),)
        forged_vector = self.verifier._vsha([list(row) for row in forged_union])
        forged_packed = hashlib.sha256(
            self.rom[:self.contract.PROMOTION_BYTES]
        ).hexdigest()
        with mock.patch.multiple(
            self.contract,
            UNION_RANGES=forged_union,
            PROMOTION_RANGE_SHA256=forged_vector,
            PROMOTION_PACKED_SHA256=forged_packed,
        ):
            with self.assertRaises(ValueError):
                self.exporter.build_payload(ROOT)
            with self.assertRaises(ValueError):
                self.verifier._rebuild(ROOT)

    def test_upstream_full_verifier_is_a_release_gate_not_an_inner_rebuild(self) -> None:
        with mock.patch(
            "tools.verify_rom_story_state_callback_cfg.verify_artifact",
            side_effect=AssertionError("full upstream verifier entered inner rebuild"),
        ):
            self.assertEqual(self.contract.SCHEMA,
                             self.exporter.build_payload(ROOT)["schema"])
            self.assertEqual(self.contract.SCHEMA,
                             self.verifier._rebuild(ROOT)["schema"])
        failed = {"verified": False, "promotion_bytes": None}
        with mock.patch(
            "tools.verify_rom_story_state_callback_cfg.verify_artifact",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "upstream independent"):
                self.exporter._verify_upstream_artifact(ROOT)
            with self.assertRaisesRegex(ValueError, "upstream independent"):
                self.verifier._verify_upstream_artifact(ROOT)

    def test_mutations_fail_closed(self) -> None:
        cases = (
            (0x08F894, "producer"), (0x08F386, "selector"),
            (0x08F398, "table"), (0x08F39C, "table"),
            (0x08768C, "decode"), (0x08CD40, "decode"),
            (0x08CD5A, "dependency"), (0x08F284, "dependency"),
            (0x068848, "decode"), (0x06889E, "frontier"),
            (0x068D1C, "frontier"), (0x08793C, "frontier"),
            (0x08CE22, "frontier"), (0x08EED6, "frontier"),
            (0x08EF26, "frontier"), (0x08F4C8, "frontier"),
            (0x08F1F4, "literal"),
        )
        for offset, label in cases:
            with self.subTest(offset=hex(offset)):
                changed = bytearray(self.rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, label):
                    self.exporter.build_payload(ROOT, bytes(changed),
                                                verify_identity=False)
                with self.assertRaisesRegex(ValueError, label):
                    self.verifier._rebuild(ROOT, bytes(changed),
                                           verify_identity=False)

    def test_coverage_overlap_and_identity_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            root = Path(raw)
            shutil.copytree(ROOT / "rom", root / "rom")
            precoverage = root / self.contract.PRECOVERAGE_ARTIFACT
            precoverage.parent.mkdir(parents=True)
            shutil.copytree(
                ROOT / self.contract.PRECOVERAGE_ARTIFACT, precoverage)
            archive = precoverage / self.contract.PRECOVERAGE_ARCHIVE_NAME
            changed = bytearray(archive.read_bytes())
            changed[-1] ^= 1
            archive.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "coverage"):
                self.exporter.build_payload(root)

    def test_artifact_roundtrip_tamper_and_existing_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            base = Path(raw)
            artifact = base / "candidate"
            with mock.patch.object(
                self.exporter, "_verify_upstream_artifact"
            ) as export_gate, mock.patch.object(
                self.verifier, "_verify_upstream_artifact"
            ) as verify_gate:
                self.exporter.export_artifact(ROOT, artifact)
                report = self.verifier.verify_artifact(ROOT, artifact)
            self.assertEqual(1, export_gate.call_count)
            self.assertEqual(2, verify_gate.call_count)
            self.assertTrue(report["verified"], report)
            self.assertEqual(1920, report["promotion_bytes"])
            manifest = json.loads((artifact / "manifest.json").read_text())
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(
                "content_verified_independent_of_copy_path",
                manifest["artifact_portability"],
            )
            self.assertEqual(
                ["python3", "tools/export_rom_prebattle_menu_controller_cfg.py",
                 "--root", ".", "--output",
                 "artifacts/rom-prebattle-menu-controller-cfg-v1"],
                manifest["producer"]["command"],
            )
            self.assertEqual(
                ["python3", "tools/verify_rom_prebattle_menu_controller_cfg.py",
                 "--root", ".", "--artifact",
                 "artifacts/rom-prebattle-menu-controller-cfg-v1"],
                manifest["verifier"]["command"],
            )
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, artifact)
            with mock.patch.object(self.verifier, "_verify_upstream_artifact"):
                for name, mutate in (
                    ("manifest", self._mutate_manifest),
                    ("implementation", self._mutate_implementation),
                    ("producer-receipt", self._mutate_producer_receipt),
                    ("payload", self._mutate_payload),
                    ("extra", lambda p: (p / "extra").write_text("x")),
                ):
                    with self.subTest(name=name):
                        target = base / name
                        shutil.copytree(artifact, target)
                        mutate(target)
                        self.assertFalse(
                            self.verifier.verify_artifact(ROOT, target)["verified"]
                        )

    def test_official_destination_is_an_exact_authorized_output(self) -> None:
        official = ROOT / self.contract.OFFICIAL_ARTIFACT
        self.assertTrue(self.exporter._authorized_output(ROOT, official)[1])
        with self.assertRaises(ValueError):
            self.exporter._authorized_output(
                ROOT, ROOT / "artifacts/rom-prebattle-menu-controller-cfg-v1-extra"
            )

    def test_symlink_and_atomic_no_replace_guards(self) -> None:
        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            base = Path(raw)
            outside = base / "outside"
            outside.mkdir()
            alias = base / "alias"
            alias.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, alias / "candidate")
            source = base / "source"
            destination = base / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "payload").write_text("new")
            (destination / "keep").write_text("keep")
            with self.assertRaises(FileExistsError):
                self.exporter._publish_exclusive(source, destination)
            self.assertTrue((source / "payload").exists())
            self.assertEqual("keep", (destination / "keep").read_text())

    def test_verifier_is_independent_and_rebuilds_raw_payload(self) -> None:
        source = (ROOT / "tools/verify_rom_prebattle_menu_controller_cfg.py").read_text()
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_prebattle_menu_controller_cfg" in row
                             for row in imports))
        self.assertEqual(self.payload, self.verifier._rebuild(ROOT, self.rom))

    @staticmethod
    def _mutate_manifest(path: Path) -> None:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifact_status"] = "rejected"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _mutate_implementation(path: Path) -> None:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["implementation"]["exporter"]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _mutate_producer_receipt(path: Path) -> None:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.setdefault("producer", {})["command"] = ["false"]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    def _mutate_payload(self, path: Path) -> None:
        payload_path = path / self.exporter.PAYLOAD_NAME
        payload = json.loads(payload_path.read_text())
        payload["promotion"]["promotion_bytes"] += 1
        raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
        payload_path.write_bytes(raw)
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][self.exporter.PAYLOAD_NAME] = {
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    unittest.main()
