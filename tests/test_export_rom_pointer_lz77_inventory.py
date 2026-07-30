import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
UNBOUND_ADDRESSES = [
    "0x080B9E94",
    "0x080B9F5C",
    "0x0812C8B0",
    "0x0812D134",
    "0x0812D2F0",
    "0x083481E0",
    "0x08348668",
    "0x08348A3C",
    "0x08348F00",
    "0x0834928C",
    "0x08349368",
    "0x0834943C",
    "0x083496F8",
    "0x083F00C8",
    "0x083F08F4",
    "0x083F0AC8",
    "0x083F1C98",
    "0x083F2108",
    "0x083F21E4",
    "0x083F2A18",
    "0x08405EA4",
    "0x08405F10",
    "0x08457D3C",
    "0x084580C8",
    "0x084634B8",
    "0x0846356C",
    "0x084635D8",
    "0x08463688",
    "0x085B6000",
    "0x085B67E0",
    "0x085B6880",
]


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportRomPointerLz77InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_pointer_lz77_inventory import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)
        cls.manifest = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_builds_a_finite_pointer_reachable_denominator(self):
        self.assertEqual("rom-pointer-lz77-inventory-v1", self.payload["schema"])
        self.assertEqual(ROM_SHA256, self.payload["rom"]["sha256"])
        self.assertEqual(
            {
                "strict_lz77_record_count": 1099,
                "aligned_pointer_reachable_record_count": 896,
                "previously_bound_record_count": 865,
                "newly_exported_record_count": 31,
                "remaining_unbound_record_count": 0,
            },
            self.payload["summary"],
        )
        self.assertEqual(
            UNBOUND_ADDRESSES,
            [record["gba_address"] for record in self.payload["new_records"]],
        )

    def test_losslessly_packs_every_new_compressed_and_decompressed_record(self):
        compressed = (self.output / "uncovered-records.lz77.bin").read_bytes()
        decompressed = (self.output / "uncovered-payloads.bin").read_bytes()
        self.assertEqual(31, len(self.payload["new_records"]))
        self.assertEqual(
            18286,
            sum(record["compressed_size"] for record in self.payload["new_records"]),
        )
        self.assertEqual(
            40994,
            sum(record["decompressed_size"] for record in self.payload["new_records"]),
        )
        for record in self.payload["new_records"]:
            compressed_slice = compressed[
                record["compressed_bundle_offset"] :
                record["compressed_bundle_offset"] + record["compressed_size"]
            ]
            decompressed_slice = decompressed[
                record["decompressed_bundle_offset"] :
                record["decompressed_bundle_offset"] + record["decompressed_size"]
            ]
            self.assertEqual(
                record["compressed_sha256"],
                hashlib.sha256(compressed_slice).hexdigest(),
            )
            self.assertEqual(
                record["decompressed_sha256"],
                hashlib.sha256(decompressed_slice).hexdigest(),
            )

    def test_binds_records_to_aligned_pointer_and_literal_load_evidence(self):
        records = {
            record["gba_address"]: record for record in self.payload["new_records"]
        }
        for record in records.values():
            self.assertEqual(0, record["file_offset"] % 4)
            self.assertTrue(record["aligned_pointer_references"])
            self.assertTrue(record["literal_load_users"])
        self.assertEqual(
            ["0x0806F184", "0x0807304C"],
            records["0x0812C8B0"]["aligned_pointer_references"],
        )
        self.assertEqual(
            ["0x0806F120", "0x08073024"],
            records["0x0812C8B0"]["literal_load_users"],
        )
        self.assertEqual(
            ["0x08087070", "0x0808C018", "0x0808C588"],
            records["0x08405EA4"]["aligned_pointer_references"],
        )

    def test_classifies_only_code_proven_hardware_routes(self):
        self.assertEqual(
            {
                "graphics": 21,
                "palette": 3,
                "visual_metadata": 7,
            },
            self.payload["classification_counts"],
        )
        records = {
            record["gba_address"]: record for record in self.payload["new_records"]
        }
        self.assertEqual("graphics", records["0x080B9E94"]["classification"]["kind"])
        self.assertEqual(
            ["0x06002000"],
            records["0x080B9E94"]["classification"]["destination_addresses"],
        )
        self.assertEqual("palette", records["0x080B9F5C"]["classification"]["kind"])
        self.assertEqual(
            ["0x05000180"],
            records["0x080B9F5C"]["classification"]["destination_addresses"],
        )
        self.assertEqual(
            "visual_metadata",
            records["0x0834928C"]["classification"]["kind"],
        )
        self.assertEqual(
            "LZ77UnCompWram_wrapper",
            records["0x0834928C"]["classification"]["load_route"],
        )
        self.assertEqual(
            ["0x0600E800", "0x06006800"],
            records["0x08405EA4"]["classification"]["destination_addresses"],
        )
        rom = (ROOT / "rom/base.gba").read_bytes()
        for record in records.values():
            windows = record["classification"]["code_windows"]
            self.assertEqual(
                record["literal_load_users"],
                [window["gba_start"] for window in windows],
            )
            for window in windows:
                start = int(window["gba_start"], 16) - 0x08000000
                data = rom[start : start + window["size"]]
                self.assertEqual(16, window["size"])
                self.assertEqual(
                    window["sha256"], hashlib.sha256(data).hexdigest()
                )

    def test_pins_the_exact_upstream_artifact_registry(self):
        registry = self.payload["upstream_binding_registry"]
        self.assertEqual(17, len(registry["files"]))
        self.assertEqual(865, registry["bound_record_count"])
        self.assertEqual(
            896,
            registry["bound_record_count"]
            + self.payload["summary"]["newly_exported_record_count"],
        )
        for item in registry["files"]:
            path = ROOT / item["path"]
            self.assertEqual(
                item["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            if item["path"] != "artifacts/dialogue-font-v2/manifest.json":
                self.assertGreater(item["bound_record_count"], 0)

    def test_excludes_boundary_addresses_from_upstream_bindings(self):
        registry = {
            item["path"]: item
            for item in self.payload["upstream_binding_registry"]["files"]
        }
        dialogue = registry["artifacts/dialogue-font-v2/manifest.json"]
        self.assertEqual(0, dialogue["bound_record_count"])
        self.assertEqual([], dialogue["bound_addresses"])

        records = {
            record["gba_address"]: record for record in self.payload["new_records"]
        }
        recovered = records["0x085B6000"]
        self.assertEqual("graphics", recovered["classification"]["kind"])
        self.assertEqual(
            ["0x06016600", "0x06010000", "dynamic_obj_vram_slot"],
            recovered["classification"]["destination_addresses"],
        )

    def test_scope_does_not_promote_the_inventory_to_all_graphics(self):
        self.assertEqual(
            {
                "strict_lz77_syntax_scan_complete": True,
                "aligned_pointer_reachable_lz77_denominator_complete": True,
                "all_denominator_records_artifact_bound": True,
                "uncovered_records_losslessly_exported": True,
                "all_records_are_graphics": False,
                "raw_uncompressed_graphics_complete": False,
                "raw_palettes_complete": False,
                "procedural_graphics_complete": False,
                "runtime_reachability_complete": False,
                "natural_language_identity_complete": False,
                "generic_image_writeback_complete": False,
                "all_game_visual_states_complete": False,
            },
            self.payload["scope"],
        )

    def test_independent_verifier_accepts_and_rejects_tamper(self):
        from tools.verify_rom_pointer_lz77_inventory import verify_artifact

        source = (
            ROOT / "tools" / "verify_rom_pointer_lz77_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(896, report["aligned_pointer_reachable_record_count"])
        self.assertEqual(0, report["remaining_unbound_record_count"])

        for relative in (
            "uncovered-records.lz77.bin",
            "uncovered-payloads.bin",
            "rom-pointer-lz77-inventory.json",
            "manifest.json",
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                path = tampered / relative
                raw = bytearray(path.read_bytes())
                raw[-1] ^= 1
                path.write_bytes(raw)
                rejected = verify_artifact(ROOT, tampered)
                self.assertFalse(rejected["verified"], relative)
                self.assertTrue(rejected["errors"], relative)

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "rom-pointer-lz77-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["new_records"][0]["classification"]["kind"] = "visual_metadata"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["rom-pointer-lz77-inventory.json"] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(
                any("classification mismatch" in error for error in rejected["errors"]),
                rejected["errors"],
            )

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "rom-pointer-lz77-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["selection_rule"]["source_alignment"] = 8
            payload["rom"]["path"] = "rom/other.gba"
            payload["rom"]["size"] += 4
            payload["bundles"]["compressed"]["file"] = "other.bin"
            payload["upstream_binding_registry"]["method"] = "trust every string"
            compressed_path = tampered / "uncovered-records.lz77.bin"
            compressed_path.write_bytes(compressed_path.read_bytes() + b"junk")
            payload["bundles"]["compressed"]["size"] += 4
            payload["bundles"]["compressed"]["sha256"] = hashlib.sha256(
                compressed_path.read_bytes()
            ).hexdigest()
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["rom-pointer-lz77-inventory.json"] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest["files"]["uncovered-records.lz77.bin"] = hashlib.sha256(
                compressed_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"], rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "rom-pointer-lz77-inventory.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            registry_files = payload["upstream_binding_registry"]["files"]
            registry_files.append(dict(registry_files[0]))
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["rom-pointer-lz77-inventory.json"] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"], rejected["errors"])

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_pointer_lz77_inventory import export_artifact

        with tempfile.TemporaryDirectory() as tmp:
            repeated = Path(tmp) / "artifact"
            export_artifact(ROOT, repeated)
            self.assertEqual(directory_hashes(self.output), directory_hashes(repeated))

            foreign = Path(tmp) / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("owned by someone else")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, foreign)
            self.assertEqual(
                "owned by someone else", (foreign / "keep.txt").read_text()
            )


if __name__ == "__main__":
    unittest.main()
