"""TDD contract for the fixed eight-row bounded-index u16-pair table."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BoundedIndexU16PairTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_bounded_index_u16_pair_table as exporter
        from tools import verify_rom_bounded_index_u16_pair_table as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.payload = exporter.build_payload(ROOT)

    def test_exact_table_denominator_and_records(self) -> None:
        payload = self.payload
        self.assertEqual("rom-bounded-index-u16-pair-table-v1", payload["schema"])
        table = payload["table"]
        self.assertEqual([0x53F2EE, 0x53F30E], table["range"])
        self.assertEqual(8, table["record_count"])
        self.assertEqual(4, table["record_size"])
        self.assertEqual(list(range(8)), [row["index"] for row in table["records"]])
        self.assertEqual([-4, -6, -7, -8, -6, -4, -2, 0],
                         [row["first_s16"] for row in table["records"]])
        self.assertEqual([0, 4, 7, 9, 9, 7, 4, 0],
                         [row["second_u16"] for row in table["records"]])

    def test_consumer_boundary_and_narrow_scope(self) -> None:
        consumer = self.payload["consumer_contract"]
        self.assertEqual(0x30, consumer["index_field_offset"])
        self.assertEqual(7, consumer["unsigned_max_index"])
        self.assertEqual(4, consumer["record_stride"])
        self.assertEqual([0x08080AE8, 0x08080AF0], consumer["halfword_load_sites"])
        self.assertEqual([0x08, 0x0A], consumer["destination_halfword_offsets"])
        self.assertEqual([0x08080B04], consumer["base_literal_occurrences"])
        self.assertEqual(32, self.payload["promotion"]["promotion_bytes"])
        self.assertEqual(1, self.payload["promotion"]["claim_count"])
        for key in ("natural_runtime_all_indices", "business_field_semantics",
                    "signedness_at_destination", "adjacent_zero_gap",
                    "editing_or_relocation_safety"):
            self.assertFalse(self.payload["scope"][key])

    def test_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(32, report["promotion_bytes"])
            self.assertEqual(8, report["record_count"])

    def test_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_bounded_index_u16_pair_table.py").read_text()
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_bounded_index_u16_pair_table" in row
                             for row in imports))

    def test_independent_cfg_dominator_and_dataflow_mutations_fail(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        raw = self.exporter._raw_consumer_contract(bytes(rom))
        semantic = self.verifier._semantic_consumer_contract(bytes(rom))
        self.assertEqual(raw, semantic)
        self.assertTrue(raw["guard_dominates_halfword_loads"])
        self.assertEqual([0x08080AF6], raw["index_field_writer_sites"])
        for offset in (0x080AAE, 0x080AB0, 0x080AE0,
                       0x080AE4, 0x080AE6, 0x080AE8, 0x080AEC,
                       0x080AEE, 0x080AF0):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaises(ValueError):
                    self.exporter._raw_consumer_contract(bytes(changed))
                with self.assertRaises(ValueError):
                    self.verifier._semantic_consumer_contract(bytes(changed))

    def test_table_consumer_and_literal_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        for offset, pattern in ((0x53F2EE, "table"), (0x080AAC, "consumer"),
                                (0x080AAE, "consumer"), (0x080AB0, "consumer"),
                                (0x080AE0, "consumer"), (0x080AE4, "consumer"),
                                (0x080AE8, "consumer"), (0x080AF0, "consumer"),
                                (0x080B04, "literal")):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    self.exporter._build_from_rom(bytes(changed), verify_identity=False)
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
