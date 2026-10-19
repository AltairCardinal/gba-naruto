import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import export_rom_renderer_script_pointer_pool_records as exporter
from tools import verify_rom_renderer_script_pointer_pool_records as verifier


def _mutated_rom(rom: bytes, offset: int, value: int) -> bytes:
    mutated = bytearray(rom)
    mutated[offset] = value
    return bytes(mutated)


class StructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_pool_covers_27_records_and_1542_bytes(self):
        records = self.payload["records"]
        self.assertEqual(records["record_count"], 27)
        self.assertEqual(records["record_bytes"], 1542)
        self.assertEqual(records["range"], [0x0CEA, 0x12F0])
        self.assertEqual(records["root"], 0x0CEA)
        self.assertEqual(records["terminator_offset"], 0x12F0)

    def test_records_are_gapless_and_share_one_opcode_sequence(self):
        items = self.payload["records"]["items"]
        self.assertEqual(items[0]["range"][0], 0x0CEA)
        self.assertEqual(items[-1]["range"][1], 0x12F0)
        for index in range(1, len(items)):
            self.assertEqual(items[index - 1]["range"][1], items[index]["range"][0])
        for item in items:
            self.assertEqual(item["opcodes"], [1, 5, 4, 12, 3, 0])

    def test_pool_does_not_overlap_its_accepted_neighbours(self):
        self.assertEqual(exporter.LEFT_NEIGHBOUR_RANGE[1], 0x0CEA)
        self.assertEqual(exporter.RIGHT_NEIGHBOUR_RANGE[0], 0x12F0)

    def test_pointer_table_has_one_null_slot_and_matching_roots(self):
        table = self.payload["pointer_table"]
        self.assertEqual(table["slot_count"], 28)
        self.assertEqual(table["slots"][0], 0)
        roots = [item["range"][0] for item in self.payload["records"]["items"]]
        for index, root in enumerate(roots):
            self.assertEqual(table["slots"][index + 1], 0x08000000 + root)

    def test_consumer_contract_binds_one_literal_and_one_interpreter_call(self):
        consumer = self.payload["consumer_contract"]
        self.assertEqual(consumer["literal_value"], 0x0853DF00)
        self.assertEqual(consumer["literal_occurrence_denominator"], {"0x0853DF00": [0x071350]})
        self.assertEqual(consumer["interpreter_call_site"], 0x071340)
        self.assertEqual(consumer["interpreter_call_target"], 0x067158)

    def test_scope_never_claims_runtime_or_lifecycle_closure(self):
        for key, value in self.payload["scope"].items():
            self.assertFalse(value, key)

    def test_promotion_claims_exactly_the_pool(self):
        promotion = self.payload["promotion"]
        self.assertEqual(promotion["claim_count"], 1)
        self.assertEqual(promotion["promotion_bytes"], 1542)
        self.assertEqual(promotion["claims"][0]["range"], [0x0CEA, 0x12F0])
        self.assertEqual(promotion["promoted_from_primary_class"], "unknown")
        self.assertEqual(
            promotion["claims"][0]["primary_class"],
            "fixed_cfg_consumer_renderer_command_script",
        )


class VerifierIndependenceTests(unittest.TestCase):
    def test_verifier_does_not_import_exporter(self):
        source = (ROOT / "tools/verify_rom_renderer_script_pointer_pool_records.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for name in imported:
            self.assertNotIn("export_rom_renderer_script_pointer_pool_records", name)

    def test_verifier_rebuild_matches_exporter_payload(self):
        rebuilt = verifier._rebuild((ROOT / "rom/base.gba").read_bytes())
        self.assertEqual(rebuilt, exporter.build_payload(ROOT))


class MutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def _expect_exporter_failure(self, rom: bytes, message: str):
        with self.assertRaisesRegex(ValueError, message):
            exporter._build_from_rom(ROOT, rom, verify_identity=False)

    def _expect_verifier_failure(self, rom: bytes, message: str):
        with self.assertRaisesRegex(ValueError, message):
            verifier._rebuild(rom, verify_identity=False)

    def test_rom_identity_is_still_checked_by_default(self):
        mutated = _mutated_rom(self.rom, 0x0CEA, 0x02)
        with self.assertRaisesRegex(ValueError, "ROM identity changed"):
            verifier._rebuild(mutated)

    def test_pool_byte_change_is_rejected_by_both_sides(self):
        mutated = _mutated_rom(self.rom, 0x0CEA, 0x02)
        self._expect_exporter_failure(mutated, "unsupported opcode")
        self._expect_verifier_failure(mutated, "unsupported opcode")

    def test_pointer_table_slot_change_is_rejected_by_both_sides(self):
        mutated = _mutated_rom(self.rom, 0x53DF08, 0x00)
        self._expect_exporter_failure(mutated, "pointer slot does not match")
        self._expect_verifier_failure(mutated, "pointer slot does not match")

    def test_null_slot_change_is_rejected_by_both_sides(self):
        mutated = _mutated_rom(self.rom, 0x53DF00, 0x01)
        self._expect_exporter_failure(mutated, "null slot changed")
        self._expect_verifier_failure(mutated, "null slot changed")

    def test_consumer_literal_change_is_rejected_by_both_sides(self):
        mutated = _mutated_rom(self.rom, 0x071351, 0x00)
        self._expect_exporter_failure(mutated, "consumer literal denominator changed")
        self._expect_verifier_failure(mutated, "consumer literal denominator changed")

    def test_consumer_code_change_is_rejected_by_both_sides(self):
        mutated = _mutated_rom(self.rom, 0x071340, 0x00)
        self._expect_exporter_failure(mutated, "consumer identity changed")
        self._expect_verifier_failure(mutated, "consumer identity changed")

    def test_interpreter_change_is_rejected_by_both_sides(self):
        mutated = _mutated_rom(self.rom, 0x067158, 0x00)
        self._expect_exporter_failure(mutated, "interpreter identity changed")
        self._expect_verifier_failure(mutated, "interpreter identity changed")

    def test_neighbour_record_change_is_rejected_by_both_sides(self):
        mutated = _mutated_rom(self.rom, 0x0CC7, 0x00)
        self._expect_exporter_failure(mutated, "left neighbour record identity changed")
        self._expect_verifier_failure(mutated, "left neighbour record identity changed")


class ArtifactTests(unittest.TestCase):
    def test_roundtrip_export_then_verify(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = Path(tmp) / "artifacts" / "rom-renderer-script-pointer-pool-records-v1"
            exporter.export_artifact(ROOT, output)
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report["errors"])
            self.assertEqual(report["record_count"], 27)
            self.assertEqual(report["promotion_bytes"], 1542)

    def test_export_refuses_to_overwrite_an_existing_artifact(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = Path(tmp) / "artifacts" / "rom-renderer-script-pointer-pool-records-v1"
            exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                exporter.export_artifact(ROOT, output)

    def test_verifier_rejects_a_tampered_payload(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = Path(tmp) / "artifacts" / "rom-renderer-script-pointer-pool-records-v1"
            exporter.export_artifact(ROOT, output)
            payload_path = output / exporter.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["records"]["record_count"] = 26
            payload_path.write_bytes(exporter._canonical(payload))
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])

    def test_verifier_rejects_an_extra_artifact_member(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = Path(tmp) / "artifacts" / "rom-renderer-script-pointer-pool-records-v1"
            exporter.export_artifact(ROOT, output)
            (output / "extra.json").write_text("{}", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])

    def test_verifier_rejects_a_missing_artifact_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            report = verifier.verify_artifact(ROOT, Path(tmp) / "absent")
            self.assertFalse(report["verified"])


class CommandLineTests(unittest.TestCase):
    def test_verifier_cli_reports_a_missing_artifact(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/verify_rom_renderer_script_pointer_pool_records.py"),
                    "--root", str(ROOT),
                    "--artifact-dir", str(Path(tmp) / "absent"),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertFalse(json.loads(completed.stdout)["verified"])


if __name__ == "__main__":
    unittest.main()
