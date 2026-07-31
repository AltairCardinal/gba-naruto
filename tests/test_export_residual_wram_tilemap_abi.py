import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportResidualWramTilemapAbiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_residual_wram_tilemap_abi import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_three_of_seven_wram_visual_metadata_abis(self):
        self.assertEqual(
            {
                "wram_visual_metadata_denominator": 7,
                "direct_tilemap_queue_abi_count": 3,
                "remaining_unresolved_count": 4,
                "tilemap_entry_count": 657,
                "tilemap_payload_bytes": 1314,
            },
            self.payload["summary"],
        )
        self.assertEqual(
            ["0x0834928C", "0x083F1C98", "0x085B67E0"],
            [record["source_pointer"] for record in self.payload["tilemaps"]],
        )
        self.assertEqual(
            ["0x083F2108", "0x084634B8", "0x0846356C", "0x084635D8"],
            self.payload["remaining_unresolved"],
        )

    def test_records_exact_wram_to_strided_vram_queue_contracts(self):
        records = {
            record["source_pointer"]: record
            for record in self.payload["tilemaps"]
        }
        self.assertEqual(
            (15, 20, "0x0600001E", 300, [1], [6, 67], 20, 15),
            self._contract(records["0x0834928C"]),
        )
        self.assertEqual(
            (24, 12, "0x0600F810", 288, [8], [0, 267], 0, 0),
            self._contract(records["0x083F1C98"]),
        )
        self.assertEqual(
            (23, 3, "0x0600FC4E", 69, [9], [0, 86], 0, 0),
            self._contract(records["0x085B67E0"]),
        )
        self.assertTrue(
            all(
                record["load_route"] == "LZ77UnCompWram_wrapper"
                and record["submit_route"] == "strided_gpu_copy_queue"
                and record["queue_consumer"] == "0x0806365C"
                for record in records.values()
            )
        )
        self.assertEqual(
            [(0, 0, 15), (31, 0, 8), (31, 17, 7)],
            [
                (
                    record["screenblock"]["index"],
                    record["screenblock"]["row"],
                    record["screenblock"]["column"],
                )
                for record in records.values()
            ],
        )

    @staticmethod
    def _contract(record):
        tilemap = record["tilemap"]
        return (
            tilemap["width_entries"],
            tilemap["height_entries"],
            record["vram_destination"],
            tilemap["entry_count"],
            tilemap["palette_banks"],
            tilemap["tile_index_range"],
            tilemap["horizontal_flip_count"],
            tilemap["vertical_flip_count"],
        )

    def test_bundle_and_manifest_are_exact_and_deterministic(self):
        bundle = (self.output / "tilemaps.bin").read_bytes()
        self.assertEqual(1314, len(bundle))
        for record in self.payload["tilemaps"]:
            start = record["bundle_offset"]
            data = bundle[start : start + record["decompressed_size"]]
            self.assertEqual(
                record["decompressed_sha256"],
                hashlib.sha256(data).hexdigest(),
            )
        manifest = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {"residual-wram-tilemap-abi.json", "tilemaps.bin"},
            set(manifest["files"]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "artifact"
            from tools.export_residual_wram_tilemap_abi import export_artifact

            export_artifact(ROOT, second)
            self.assertEqual(
                {
                    path.relative_to(self.output): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in self.output.rglob("*")
                    if path.is_file()
                },
                {
                    path.relative_to(second): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in second.rglob("*")
                    if path.is_file()
                },
            )

    def test_manifest_pins_direct_decoder_dependencies(self):
        manifest = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            {
                "tools/extract_tileset.py",
                "tools/gba_image_export.py",
            }.issubset(manifest["implementation"])
        )

    def test_manifest_is_a_promotable_accepted_artifact(self):
        manifest = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual(
            "residual-wram-tilemap-abi-v1",
            manifest["artifact_schema"],
        )
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            "residual-wram-tilemap-abi.json",
            manifest["payload_file"],
        )
        self.assertEqual(
            {
                "command": [
                    "python3",
                    "tools/verify_residual_wram_tilemap_abi.py",
                    "--root",
                    ".",
                    "--artifact",
                    "artifacts/residual-wram-tilemap-abi-v1",
                ],
                "exit_code": 0,
            },
            manifest["verifier"],
        )

    def test_promoted_artifact_passes_the_independent_verifier(self):
        from tools.verify_residual_wram_tilemap_abi import verify_artifact

        report = verify_artifact(
            ROOT,
            ROOT / "artifacts/residual-wram-tilemap-abi-v1",
        )
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(3, report["verified_tilemaps"])

    def test_exporter_starts_as_a_clean_script(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_residual_wram_tilemap_abi.py",
                    "--root",
                    ".",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)

    def test_independent_verifier_rejects_rehashed_semantic_tamper(self):
        from tools.verify_residual_wram_tilemap_abi import verify_artifact

        source = (
            ROOT / "tools/verify_residual_wram_tilemap_abi.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_residual_wram_tilemap_abi",
            source,
        )
        self.assertNotIn(
            "import tools.export_residual_wram_tilemap_abi",
            source,
        )
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(3, report["verified_tilemaps"])
        for field, value in (
            ("vram_destination", "0x06000020"),
            ("queue_call", "0x0808ADAC"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                payload_path = tampered / "residual-wram-tilemap-abi.json"
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                payload["tilemaps"][0][field] = value
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
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"][payload_path.name] = hashlib.sha256(
                    payload_path.read_bytes()
                ).hexdigest()
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
                rejected = verify_artifact(ROOT, tampered)
                self.assertFalse(rejected["verified"])
                self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "residual-wram-tilemap-abi.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
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
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])


if __name__ == "__main__":
    unittest.main()
