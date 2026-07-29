import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "artifacts/world-map-gpu-captures/s42-page0"


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportWorldMapRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_world_map_runtime import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, CAPTURE, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_binds_capture_checkpoint_and_exact_raw_files(self):
        self.assertEqual("world-map-runtime-v1", self.manifest["schema"])
        self.assertEqual(
            "35fce6be208aa50044bdaa2232eab5986d9ea76340bc08c68b107f34b5a5b5a1",
            self.manifest["capture"]["input_state_sha256"],
        )
        self.assertEqual(
            "artifacts/runtime-checkpoints/scenario-42-postbattle-world-map.ss9",
            self.manifest["capture"]["input_state"],
        )
        self.assertEqual(
            {
                "audit.json": "307c25f37c6cd825f064946e2c5e5d1d09760eab335905f95a8af4e243a43026",
                "frame.png": "21439923ef315e7bd00607088858c180646af0f13cbb26ac97bd5c0a1185863d",
                "guard.json": "138d090b82e8a655e0146b5ec1b4447f87a2454a1875e7f8cfe2e2ba0ef0dc0d",
                "io.bin": "5b2230984638a67e68115e9fe09b5a316ff24de72cd0dcefed24bf1417069aa1",
                "oam.bin": "b3c33732982b1225e5a88b1b89ae3d1340bf8598647d28f899e1d437266c4544",
                "pram.bin": "abb77e6d4f67d6df9a295f174868546de5e1ecdafaf36d6892f49447c9779418",
                "vram.bin": "0b207f2202daa3ba9ba72e7be080d10479c308ce7aad7ecc0cb9aaa3fe1eb50c",
            },
            {
                name: metadata["sha256"]
                for name, metadata in self.manifest["capture"]["files"].items()
            },
        )
        self.assertEqual("success-marker", self.manifest["capture"]["guard"]["completion_trigger"])
        self.assertNotIn("pgid_clean", self.manifest["capture"]["guard"])

    def test_proves_page_zero_background_hardware_binding(self):
        background = self.manifest["page_zero_background"]
        self.assertEqual(0, background["page_id"])
        self.assertEqual("0x1940", background["display_control"])
        self.assertEqual([0, 3], background["enabled_backgrounds"])
        self.assertTrue(background["obj_enabled"])
        self.assertEqual(
            {
                "bg": 0,
                "control": "0x0086",
                "priority": 2,
                "character_base": "0x06004000",
                "screen_base": "0x06000000",
                "bits_per_pixel": 8,
                "scroll": [0, 0],
            },
            background["hardware"],
        )
        self.assertEqual("exact", background["graphics_vram_match"])
        self.assertEqual("exact", background["palette_pram_match"])
        self.assertEqual(20, background["tilemap_rows_matching"])
        self.assertEqual([30, 20], background["tilemap_dimensions"])
        self.assertEqual([240, 160], background["visible_dimensions"])

    def test_proves_runtime_label_layout_palette_and_position(self):
        label = self.manifest["page_zero_label"]
        self.assertEqual(
            ["0x92BB", "0x99DE", "0x9BD6", "0x90EC"],
            label["codes"],
        )
        self.assertEqual(3, label["background"])
        self.assertEqual("0x030C", label["bg_control"])
        self.assertEqual(0, label["priority"])
        self.assertEqual("0x0600C000", label["character_base"])
        self.assertEqual("0x06001800", label["screen_base"])
        self.assertEqual([32, 8], label["screen_position"])
        self.assertEqual([32, 16], label["dimensions"])
        self.assertEqual(
            [[0, 2, 4, 6], [1, 3, 5, 7]],
            label["tile_indices"],
        )
        self.assertEqual(14, label["palette_bank"])
        self.assertEqual([8, 9, 10, 11], label["tile_pixel_indices"])
        self.assertEqual([232, 233, 234, 235], label["global_palette_indices"])
        self.assertEqual(
            ["0x6BDC", "0x4ED5", "0x35EE", "0x1D07"],
            [entry["bgr555"] for entry in label["palette"]],
        )
        self.assertTrue(label["all_runtime_tiles_match_rom_glyph_sources"])

    def test_records_single_active_cursor_and_scope_boundary(self):
        self.assertEqual(
            {
                "active_object_count": 1,
                "object_id": 0,
                "position": [184, 8],
                "dimensions": [16, 8],
                "tile_index": 1014,
                "priority": 0,
                "palette_bank": 15,
            },
            self.manifest["selection_cursor"],
        )
        self.assertEqual(
            {
                "page_zero_final_composition_captured": True,
                "page_zero_background_binding_complete": True,
                "page_zero_label_runtime_layout_complete": True,
                "page_zero_label_palette_complete": True,
                "page_zero_selection_cursor_oam_complete": True,
                "pages_one_and_two_runtime_composition_complete": False,
                "selection_transition_timing_complete": False,
                "unlock_state_matrix_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_rejects_artifact_and_capture_tamper(self):
        from tools.verify_world_map_runtime import verify_artifact

        source = (
            ROOT / "tools/verify_world_map_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, CAPTURE, self.output)
        self.assertTrue(report["verified"], report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(self.output, artifact)
            manifest = artifact / "manifest.json"
            raw = bytearray(manifest.read_bytes())
            raw[-2] ^= 1
            manifest.write_bytes(raw)
            report = verify_artifact(ROOT, CAPTURE, artifact)
            self.assertFalse(report["verified"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(self.output, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["capture"]["files"]["vram.bin"]["size"] = 1
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, CAPTURE, artifact)
            self.assertFalse(report["verified"])

        with tempfile.TemporaryDirectory() as temporary:
            capture = Path(temporary) / "capture"
            shutil.copytree(CAPTURE, capture)
            raw = bytearray((capture / "io.bin").read_bytes())
            raw[0] ^= 1
            (capture / "io.bin").write_bytes(raw)
            report = verify_artifact(ROOT, capture, self.output)
            self.assertFalse(report["verified"])

    def test_export_is_deterministic_and_cli_is_repository_relative(self):
        from tools.export_world_map_runtime import export_artifact

        committed = ROOT / "artifacts/world-map-runtime-v1"
        self.assertEqual(directory_hashes(self.output), directory_hashes(committed))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            second = export_artifact(ROOT, CAPTURE, output)
            self.assertEqual(self.manifest, second)
            self.assertEqual(directory_hashes(self.output), directory_hashes(output))

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_world_map_runtime.py",
                    "--root",
                    ".",
                    "--capture-dir",
                    "artifacts/world-map-gpu-captures/s42-page0",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('"page_zero_final_composition_captured": true', result.stdout)


if __name__ == "__main__":
    unittest.main()
