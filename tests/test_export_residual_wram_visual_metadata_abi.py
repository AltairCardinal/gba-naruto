import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportResidualWramVisualMetadataAbiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_residual_wram_visual_metadata_abi import (
            export_artifact,
        )

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_all_seven_wram_visual_metadata_abis(self):
        self.assertEqual(
            {
                "wram_visual_metadata_denominator": 7,
                "tilemap_source_count": 7,
                "direct_strided_queue_count": 3,
                "direct_cpu_crop_count": 1,
                "transformed_strided_queue_count": 3,
                "remaining_unresolved_count": 0,
                "tilemap_entry_count": 1489,
                "tilemap_payload_bytes": 2978,
            },
            self.payload["summary"],
        )
        self.assertEqual([], self.payload["remaining_unresolved"])
        self.assertTrue(
            self.payload["scope"]["all_seven_source_abis_complete"]
        )

    def test_records_crop_upload_contract(self):
        record = self._records()["0x083F2108"]
        self.assertEqual("direct_cpu_halfword_crop", record["submit_route"])
        self.assertEqual("0x02002880", record["wram_buffer"])
        self.assertEqual("0x0808B79C", record["submit_consumer"])
        self.assertEqual("0x06001100", record["vram_destination"])
        self.assertEqual(
            {"index": 2, "row": 4, "column": 0},
            record["screenblock"],
        )
        self.assertEqual(
            {
                "source_width_entries": 40,
                "source_height_entries": 10,
                "submitted_width_entries": 32,
                "submitted_height_entries": 10,
                "source_row_stride_bytes": 80,
                "destination_row_stride_bytes": 64,
                "discarded_right_entries_per_row": 8,
            },
            record["transfer_geometry"],
        )
        self.assertEqual([10], record["tilemap"]["palette_banks"])
        self.assertEqual([1, 16], record["tilemap"]["tile_index_range"])

    def test_records_three_transformed_queue_contracts(self):
        records = self._records()
        expected = {
            "0x084634B8": ([12], [0, 54], 4, 4),
            "0x0846356C": ([13], [0, 75], 6, 7),
            "0x084635D8": ([13], [0, 95], 14, 12),
        }
        for pointer, contract in expected.items():
            with self.subTest(pointer=pointer):
                record = records[pointer]
                tilemap = record["tilemap"]
                self.assertEqual(
                    "coordinate_clipped_tile_bias_then_strided_queue",
                    record["submit_route"],
                )
                self.assertEqual("0x0200A640", record["wram_buffer"])
                self.assertEqual("0x0200A760", record["output_buffer"])
                self.assertEqual("0x06000806", record["vram_destination"])
                self.assertEqual(
                    {"index": 1, "row": 0, "column": 3},
                    record["screenblock"],
                )
                self.assertEqual(700, record["transform"]["tile_index_add"])
                self.assertEqual("0x02BC", record["transform"]["default_entry"])
                self.assertEqual([12, 12], record["transform"]["coordinate_bounds"])
                self.assertEqual(12, tilemap["width_entries"])
                self.assertEqual(12, tilemap["height_entries"])
                self.assertEqual(contract[0], tilemap["palette_banks"])
                self.assertEqual(contract[1], tilemap["tile_index_range"])
                self.assertEqual(contract[2], tilemap["horizontal_flip_count"])
                self.assertEqual(contract[3], tilemap["vertical_flip_count"])

    def test_bundle_and_manifest_are_exact(self):
        bundle = (self.output / "tilemap-sources.bin").read_bytes()
        self.assertEqual(2978, len(bundle))
        for record in self.payload["tilemap_sources"]:
            start = record["bundle_offset"]
            data = bundle[start : start + record["decompressed_size"]]
            self.assertEqual(
                record["decompressed_sha256"],
                hashlib.sha256(data).hexdigest(),
            )
        manifest = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            "residual-wram-visual-metadata-abi-v2",
            manifest["artifact_schema"],
        )

    def test_exporter_is_deterministic_and_runs_as_a_script(self):
        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_residual_wram_visual_metadata_abi.py",
                    "--root",
                    ".",
                    "--output",
                    str(second),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                self._hashes(self.output),
                self._hashes(second),
            )

    def test_promoted_artifact_passes_independent_verifier(self):
        from tools.verify_residual_wram_visual_metadata_abi import (
            verify_artifact,
        )

        source = (
            ROOT / "tools/verify_residual_wram_visual_metadata_abi.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_residual_wram_visual_metadata_abi",
            source,
        )
        report = verify_artifact(
            ROOT,
            ROOT / "artifacts/residual-wram-visual-metadata-abi-v2",
        )
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(7, report["verified_tilemap_sources"])

    def test_verifier_rejects_rehashed_semantic_tamper(self):
        from tools.verify_residual_wram_visual_metadata_abi import (
            verify_artifact,
        )

        for pointer, field_path, replacement in (
            (
                "0x083F2108",
                ("transfer_geometry", "submitted_width_entries"),
                31,
            ),
            (
                "0x084634B8",
                ("transform", "tile_index_add"),
                0,
            ),
            (
                "0x0846356C",
                ("vram_destination",),
                "0x06000800",
            ),
        ):
            with self.subTest(pointer=pointer), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                payload_path = (
                    tampered / "residual-wram-visual-metadata-abi.json"
                )
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                record = next(
                    row
                    for row in payload["tilemap_sources"]
                    if row["source_pointer"] == pointer
                )
                target = record
                for key in field_path[:-1]:
                    target = target[key]
                target[field_path[-1]] = replacement
                payload_path.write_text(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                manifest_path = tampered / "manifest.json"
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
                payload_hash = hashlib.sha256(
                    payload_path.read_bytes()
                ).hexdigest()
                manifest["files"][payload_path.name] = payload_hash
                manifest["payload_sha256"] = payload_hash
                manifest_path.write_text(
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

    def _records(self):
        return {
            record["source_pointer"]: record
            for record in self.payload["tilemap_sources"]
        }

    @staticmethod
    def _hashes(directory):
        return {
            path.relative_to(directory): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in directory.rglob("*")
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
