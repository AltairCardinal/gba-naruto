"""TDD contract for the frozen A/B fixed pair-table packet."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
# This test replaces an unaudited, stalled Luna residue.  Its RED evidence is
# recorded under the current Terra run and all fixture values below are checked
# directly against the frozen raw bytes.
RUN_DIR = ROOT / "build/experiments/active/fixed-pair-tables/terra-r1-20260904"


class FixedPairTablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_fixed_pair_tables as exporter
        from tools import verify_rom_fixed_pair_tables as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.payload = exporter.build_payload(ROOT)

    def test_exact_tables_and_merged_range(self) -> None:
        payload = self.payload
        self.assertEqual("rom-fixed-pair-tables-v1", payload["schema"])
        tables = payload["tables"]
        self.assertEqual([0x53E00A, 0x53E034], payload["merged_range"])
        self.assertEqual(
            "302b9316bccc3a094764c7c1a21e24e053ceea53ff5490a258bb78fa95067d86",
            payload["merged_bytes_sha256"],
        )

        a = tables["a"]
        self.assertEqual([0x53E00A, 0x53E014], a["range"])
        self.assertEqual(5, a["record_count"])
        self.assertEqual(2, a["record_size"])
        self.assertEqual([512, -1024, 768, -512, 256],
                         [row["signed_u16"] for row in a["records"]])
        self.assertEqual(list(range(5)), [row["index"] for row in a["records"]])

        b = tables["b"]
        self.assertEqual([0x53E014, 0x53E034], b["range"])
        self.assertEqual(8, b["record_count"])
        self.assertEqual(4, b["record_size"])
        self.assertEqual(list(range(8)), [row["index"] for row in b["records"]])
        self.assertEqual([0, 65526, 10, 0, 5, 65531, 15, 5],
                         [row["first_u16"] for row in b["records"]])
        self.assertEqual([0, 10, 20, 30, 5, 15, 25, 35],
                         [row["second_u16"] for row in b["records"]])

    def test_raw_cfg_and_dataflow_denominators(self) -> None:
        payload = self.payload
        a = payload["a_consumer"]
        self.assertEqual(0x0807C0D6, a["base_literal_load_site"])
        self.assertEqual([0x0807C15C], a["base_literal_occurrences"])
        self.assertEqual(9, a["iteration_compare"])
        self.assertEqual(10, a["iteration_count"])
        self.assertEqual(5, a["load_count"])
        self.assertEqual([0, 2, 4, 6, 8], a["load_offsets"])
        self.assertEqual("ldrsh", a["load_kind"])
        self.assertEqual(26, a["cfg"]["reachable_instruction_count"])
        self.assertEqual(0, a["cfg"]["frontier_count"])

        consumers = payload["b_consumers"]
        self.assertEqual(9, len(consumers))
        self.assertEqual(
            [0x0807BA38, 0x0807BB34, 0x0807BD14, 0x0807BF1C,
             0x0807C00A, 0x0807C18C, 0x0807C7F8, 0x0807C824,
             0x0807C844],
            [row["consumer_site"] for row in consumers],
        )
        for row in consumers:
            self.assertEqual(0x0853E014, row["base_literal_value"])
            self.assertEqual(7, row["selector_mask"])
            self.assertEqual(2, row["index_shift"])
            self.assertEqual(4, row["record_stride"])
            self.assertEqual(8, row["record_count"])
            self.assertEqual(30, row["max_access_offset"])
            self.assertEqual([0, 2], row["load_offsets"])
            self.assertEqual(2, row["halfword_load_count"])
            self.assertEqual(0, row["cfg"]["frontier_count"])
            self.assertGreaterEqual(len(row["selector_mask_sites"]), 1)
            self.assertEqual(len(row["selector_mask_sites"]),
                             len(row["index_scale_sites"]))

    def test_coverage_projection_and_preserved_gaps(self) -> None:
        payload = self.payload
        projection = payload["coverage_projection"]
        self.assertEqual(
            "ae7c69330285bd3d668612b057a793f1b98edda5e0df421a8bda6f5e90290024",
            projection["baseline_sha256"],
        )
        self.assertEqual("unknown", projection["target_status"])
        self.assertEqual([0x53DFBF, 0x53E00A], payload["gaps"]["left"]["range"])
        self.assertEqual([0x53E034, 0x53E496], payload["gaps"]["right"]["range"])
        self.assertEqual("unknown", payload["gaps"]["left"]["status"])
        self.assertEqual("unknown", payload["gaps"]["right"]["status"])
        self.assertEqual(42, payload["promotion"]["promotion_bytes"])
        self.assertEqual(2, payload["promotion"]["claim_count"])
        self.assertEqual(
            [
                {
                    "id": "fixed-pair-table-a-53e00a",
                    "range": [0x53E00A, 0x53E014],
                    "claim_kind": "fixed_signed_u16_sequence",
                    "bytes_sha256": (
                        "cc82a04afbe44c3d7a74aa855326899f3"
                        "cd23d9ad22432dda5edc4157bff2dd6"
                    ),
                },
                {
                    "id": "fixed-pair-table-b-53e014",
                    "range": [0x53E014, 0x53E034],
                    "claim_kind": "masked_u16_pair_table",
                    "bytes_sha256": (
                        "2dec89836378ee4d332104d626748e46"
                        "a2fa34d5f36cf2aff2ee9c177195b7c4"
                    ),
                },
            ],
            payload["promotion"]["claims"],
        )
        for value in payload["scope"].values():
            self.assertFalse(value)

    def test_exporter_and_verifier_rebuild_same_contract(self) -> None:
        rom = (ROOT / "rom/base.gba").read_bytes()
        raw = self.exporter._build_from_rom(ROOT, rom)
        semantic = self.verifier._rebuild(ROOT, rom)
        self.assertEqual(raw, semantic)

    def test_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_fixed_pair_tables.py").read_text()
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_fixed_pair_tables" in row for row in imports))

    def test_consumer_and_table_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        a_sites = {
            0x0807C0D2, 0x0807C0D4, 0x0807C0D6, 0x0807C0DC,
            0x0807C0DE, 0x0807C0E0, 0x0807C0E2, 0x0807C0E4,
            0x0807C0E6, 0x0807C0EA, 0x0807C0F8, 0x0807C0FA,
            0x0807C100, 0x0807C102, 0x0807C104, 0x0807C15C,
        }
        b_sites = {
            address
            for row in self.payload["b_consumers"]
            for address in [
                row["literal_site"], *row["cfg"]["raw_thumb_instruction_sites"]
            ]
        }
        offsets = sorted({0x53E00A, 0x53E014, *a_sites, *b_sites})
        for address in offsets:
            with self.subTest(address=hex(address)):
                changed = bytearray(rom)
                file_offset = address if address < 0x08000000 else address - 0x08000000
                changed[file_offset] ^= 1
                with self.assertRaises(ValueError):
                    self.exporter._build_from_rom(ROOT, bytes(changed),
                                                  verify_identity=False)
                with self.assertRaises(ValueError):
                    self.verifier._rebuild(ROOT, bytes(changed),
                                           verify_identity=False)

    def test_artifact_roundtrip_existing_output_and_manifest_guards(self) -> None:
        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            base = Path(raw)
            original = base / "original"
            self.exporter.export_artifact(ROOT, original)
            report = self.verifier.verify_artifact(ROOT, original)
            self.assertTrue(report["verified"])
            self.assertTrue(report["contract_ok"])
            self.assertEqual([], report["errors"])
            self.assertEqual(42, report["promotion_bytes"])
            self.assertEqual(2, report["claim_count"])
            manifest = json.loads((original / "manifest.json").read_text())
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(
                "artifacts/rom-fixed-pair-tables-v1",
                manifest["canonical_destination"],
            )
            self.assertEqual(0, manifest["verifier"]["exit_code"])
            self.assertEqual(
                "canonical_reproduction_recipe",
                manifest["verifier"]["command_role"],
            )
            self.assertEqual(
                {
                    "contract_sha256",
                    "exporter_sha256",
                    "verifier_sha256",
                    "test_sha256",
                },
                set(manifest["implementation"]),
            )
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, original)

            for name, mutate in (
                ("status", lambda path: self._mutate_manifest(
                    path, "artifact_status", "rejected")),
                ("implementation", lambda path: self._mutate_manifest(
                    path, "implementation", {})),
                ("extra", lambda path: (path / "extra.txt").write_text(
                    "unexpected", encoding="utf-8")),
                ("payload", self._mutate_payload),
                ("noncanonical", self._make_payload_noncanonical),
            ):
                with self.subTest(name=name):
                    candidate = base / name
                    shutil.copytree(original, candidate)
                    mutate(candidate)
                    self.assertFalse(
                        self.verifier.verify_artifact(ROOT, candidate)["verified"]
                    )

    def test_symlink_member_ancestor_and_atomic_no_replace(self) -> None:
        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            base = Path(raw)
            original = base / "original"
            self.exporter.export_artifact(ROOT, original)
            payload = original / self.exporter.PAYLOAD_NAME
            foreign = base / "foreign.json"
            foreign.write_bytes(payload.read_bytes())
            payload.unlink()
            payload.symlink_to(foreign)
            self.assertFalse(self.verifier.verify_artifact(ROOT, original)["verified"])

            alias = base / "alias"
            alias.symlink_to(base, target_is_directory=True)
            self.assertFalse(
                self.verifier.verify_artifact(ROOT, alias / "original")["verified"]
            )

            source = base / "source"
            destination = base / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "new").write_text("new", encoding="utf-8")
            (destination / "keep").write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.exporter._publish_exclusive(source, destination)
            self.assertEqual("keep", (destination / "keep").read_text())
            self.assertTrue((source / "new").is_file())

    def test_exporter_rejects_non_staging_and_external_destinations(self) -> None:
        forbidden = ROOT / "notes" / "fixed-pair-output"
        with self.assertRaisesRegex(ValueError, "build/experiments"):
            self.exporter.export_artifact(ROOT, forbidden)
        traversal = (
            ROOT / "build" / "experiments" / ".." /
            "fixed-pair-output-traversal"
        )
        with self.assertRaisesRegex(ValueError, "build/experiments"):
            self.exporter.export_artifact(ROOT, traversal)
        with tempfile.TemporaryDirectory() as raw:
            external = Path(raw) / "fixed-pair-output"
            with self.assertRaisesRegex(ValueError, "escapes root"):
                self.exporter.export_artifact(ROOT, external)

    @staticmethod
    def _mutate_manifest(path: Path, key: str, value: object) -> None:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest[key] = value
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _make_payload_noncanonical(self, path: Path) -> None:
        payload_path = path / self.exporter.PAYLOAD_NAME
        payload = json.loads(payload_path.read_text())
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        payload_path.write_bytes(raw)
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][self.exporter.PAYLOAD_NAME] = {
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
