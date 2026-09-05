"""TDD contract for the V17/V18 producer-bound helper CFG packet."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V17V18HelperCfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_v17_v18_helper_cfg as exporter
        from tools import verify_rom_v17_v18_helper_cfg as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.payload = exporter.build_payload(ROOT)

    def test_exact_cfg_literal_hole_and_return_denominators(self) -> None:
        payload = self.payload
        self.assertEqual("rom-v17-v18-helper-cfg-v1", payload["schema"])
        closure = payload["target_closure"]
        self.assertEqual(11, closure["root_count"])
        self.assertEqual(575, closure["instruction_count"])
        self.assertEqual(81, closure["basic_block_count"])
        self.assertEqual(1198, closure["code_bytes"])
        self.assertEqual(14, closure["literal_reference_count"])
        self.assertEqual(14, closure["unique_literal_word_count"])
        self.assertEqual(56, closure["literal_bytes"])
        self.assertEqual(24, closure["opaque_accepted_exit_count"])
        self.assertEqual(11, closure["structured_return_count"])
        self.assertEqual(0, closure["frontier_count"])
        self.assertEqual(12, closure["preserved_unknown_bytes"])
        self.assertEqual(
            [[0x090656, 0x090658], [0x0906DE, 0x0906E0],
             [0x090756, 0x090758], [0x0908D2, 0x0908D4],
             [0x090A0A, 0x090A0C], [0x090A8E, 0x090A90]],
            closure["preserved_unknown_holes"],
        )

    def test_producer_denominator_preserves_unbound_and_data_false_positive(self) -> None:
        denominator = self.payload["producer_denominator"]
        self.assertEqual(99_909, denominator["decoded_direct_branch_count"])
        self.assertEqual(34, denominator["root_match_count"])
        self.assertEqual(33, denominator["accepted_root_producer_count"])
        self.assertEqual(1, denominator["rejected_unbound_root_producer_count"])
        self.assertEqual(0x090FF0,
                         denominator["rejected_unbound_root_producers"][0]["file_offset"])
        self.assertEqual(0x090758,
                         denominator["rejected_unbound_root_producers"][0]["target_file_offset"])
        self.assertEqual(1, denominator["rejected_data_false_positive_count"])
        self.assertEqual(0x485DAE,
                         denominator["rejected_data_false_positives"][0]["file_offset"])

    def test_exact_promotion_and_narrow_scope(self) -> None:
        promotion = self.payload["promotion"]
        self.assertEqual(14, promotion["claim_count"])
        self.assertEqual(1198, promotion["target_code_bytes"])
        self.assertEqual(56, promotion["target_literal_bytes"])
        self.assertEqual(1254, promotion["promotion_bytes"])
        for key in (
            "natural_runtime_reachability",
            "all_inbound_producers_accepted",
            "indirect_or_computed_producer_exhaustiveness",
            "business_semantics_or_abi",
            "padding_or_free_space",
            "editing_or_relocation_safety",
        ):
            self.assertFalse(self.payload["scope"][key])

    def test_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertTrue(report["contract_ok"], report)
            self.assertEqual(1254, report["promotion_bytes"])
            self.assertEqual(0, report["frontier_count"])

    def test_verifier_does_not_import_exporter(self) -> None:
        path = ROOT / "tools/verify_rom_v17_v18_helper_cfg.py"
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(path.read_text()))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_v17_v18_helper_cfg" in row for row in imports))
        rebuilt = self.verifier._rebuild((ROOT / "rom/base.gba").read_bytes())
        self.assertEqual(575, rebuilt["target_closure"]["instruction_count"])
        self.assertEqual(33,
                         rebuilt["producer_denominator"]["accepted_root_producer_count"])
        with self.assertRaisesRegex(ValueError, "illegal Thumb"):
            self.verifier._decode(b"\x00\xe8", 0)

    def test_producer_code_literal_hole_and_exit_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        cases = (
            (0x091790, "producer"),
            (0x090FF0, "producer"),
            (0x485DAE, "producer"),
            (0x090758, "closure"),
            (0x0909B0, "literal"),
            (0x090656, "hole"),
            (0x0908BE, "exit"),
        )
        for offset, pattern in cases:
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    self.exporter._build_from_rom(ROOT, bytes(changed),
                                                  verify_identity=False)
                with self.assertRaisesRegex(ValueError, pattern):
                    self.verifier._rebuild(bytes(changed), verify_identity=False)

    def test_artifact_contract_and_existing_output_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            original = base / "original"
            self.exporter.export_artifact(ROOT, original)
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, original)
            for name, mutate in (
                ("payload", self._mutate_payload),
                ("status", lambda path: self._mutate_manifest(
                    path, "artifact_status", "rejected")),
                ("implementation", lambda path: self._mutate_manifest(
                    path, "implementation", {})),
                ("extra", lambda path: (path / "extra.txt").write_text("unexpected")),
            ):
                with self.subTest(name=name):
                    candidate = base / name
                    shutil.copytree(original, candidate)
                    mutate(candidate)
                    self.assertFalse(
                        self.verifier.verify_artifact(ROOT, candidate)["verified"]
                    )

    def test_symlink_and_exclusive_publish_guards(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            output = base / "candidate"
            self.exporter.export_artifact(ROOT, output)
            alias = base / "alias"
            alias.symlink_to(base, target_is_directory=True)
            self.assertFalse(
                self.verifier.verify_artifact(ROOT, alias / "candidate")["verified"]
            )
            source = base / "source"
            destination = base / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "new").write_text("new")
            (destination / "keep").write_text("keep")
            with self.assertRaises(FileExistsError):
                self.exporter._publish_exclusive(source, destination)
            self.assertEqual("keep", (destination / "keep").read_text())
            with self.assertRaisesRegex(ValueError, "staging output"):
                self.exporter.export_artifact(ROOT, ROOT / "notes/bad-helper-artifact")
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(
                "canonical_reproduction_recipe",
                manifest["producer"]["command_role"],
            )
            self.assertEqual(
                "artifacts/rom-v17-v18-helper-cfg-v1",
                manifest["canonical_destination"],
            )

    @staticmethod
    def _mutate_manifest(path: Path, key: str, value: object) -> None:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest[key] = value
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                            indent=2, sort_keys=True) + "\n")

    def _mutate_payload(self, path: Path) -> None:
        payload_path = path / self.exporter.PAYLOAD_NAME
        payload = json.loads(payload_path.read_text())
        payload["promotion"]["promotion_bytes"] += 1
        raw = (json.dumps(payload, ensure_ascii=False, indent=2,
                          sort_keys=True) + "\n").encode()
        payload_path.write_bytes(raw)
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][self.exporter.PAYLOAD_NAME] = {
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                            indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    unittest.main()
