import hashlib
import json
import shutil
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportRuntimeBgCompositesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_runtime_bg_composites import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)
        cls.promotion = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_every_existing_checkpoint_as_mode0_bg_state(self):
        self.assertEqual("runtime-bg-composites-v1", self.manifest["schema"])
        self.assertEqual(91, self.manifest["summary"]["checkpoint_count"])
        self.assertEqual(91, self.manifest["summary"]["mode0_checkpoint_count"])
        self.assertGreater(self.manifest["summary"]["unique_state_count"], 1)
        self.assertEqual(
            91,
            len(self.manifest["checkpoints"]),
        )
        for checkpoint in self.manifest["checkpoints"]:
            self.assertEqual(0, checkpoint["display"]["mode"])
            self.assertEqual(4, len(checkpoint["backgrounds"]))
            self.assertEqual(64, len(checkpoint["checkpoint_sha256"]))
            self.assertEqual(64, len(checkpoint["bg_vram_sha256"]))
            self.assertEqual(64, len(checkpoint["bg_palette_sha256"]))
            self.assertIn("state_id", checkpoint)
        self.assertEqual(5, self.manifest["summary"]["win0_checkpoint_count"])
        self.assertEqual(91, self.manifest["summary"]["nonzero_blend_checkpoint_count"])

    def test_records_exact_mode0_controls_and_pre_effect_scope(self):
        checkpoint = next(
            item
            for item in self.manifest["checkpoints"]
            if item["path"].endswith("scenario-41-player-turn.ss9")
        )
        self.assertEqual("0x00001D40", checkpoint["display"]["dispcnt"])
        self.assertEqual([0, 2, 3], checkpoint["display"]["enabled_backgrounds"])
        for index, background in enumerate(checkpoint["backgrounds"]):
            self.assertEqual(index, background["index"])
            self.assertIn(background["color_depth_bpp"], (4, 8))
            self.assertIn(background["width_pixels"], (256, 512))
            self.assertIn(background["height_pixels"], (256, 512))
            self.assertTrue(background["char_base_address"].startswith("0x06"))
            self.assertTrue(background["screen_base_address"].startswith("0x06"))
        self.assertEqual(
            {
                "all_tracked_mode0_checkpoint_bg_inputs_decoded": True,
                "enabled_text_bg_tilemap_char_palette_scroll_priority_decoded": True,
                "per_checkpoint_bg_layer_pixels_rendered": True,
                "pre_effect_bg_priority_preview_rendered": True,
                "mosaic_observed_disabled_in_all_inputs": True,
                "static_regular_bg_entry_identity_complete": False,
                "disabled_background_visibility_complete": False,
                "final_bg_obj_backdrop_priority_complete": False,
                "window_mask_pixel_composition_complete": False,
                "obj_window_pixel_composition_complete": False,
                "blend_and_brightness_pixel_composition_complete": False,
                "palette_transform_semantics_complete": False,
                "camera_or_scroll_writer_schedule_complete": False,
                "cross_frame_transition_timing_complete": False,
                "final_screen_composition_complete": False,
            },
            self.manifest["scope"],
        )

    def test_manifest_binds_exporter_verifier_and_test_sources(self):
        expected = {
            "exporter_sha256": hashlib.sha256(
                (ROOT / "tools/export_runtime_bg_composites.py").read_bytes()
            ).hexdigest(),
            "verifier_sha256": hashlib.sha256(
                (ROOT / "tools/verify_runtime_bg_composites.py").read_bytes()
            ).hexdigest(),
            "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        self.assertEqual(expected, self.manifest["implementation"])

    def test_promotion_manifest_accepts_and_hashes_only_two_payload_files(self):
        self.assertEqual("git-artifact-promotion-v1", self.promotion["schema"])
        self.assertEqual(
            "runtime-bg-composites-v1",
            self.promotion["artifact_schema"],
        )
        self.assertEqual("accepted", self.promotion["artifact_status"])
        self.assertEqual(
            {"layers.zip", "runtime-bg-composites.json"},
            set(self.promotion["files"]),
        )
        for relative, expected in self.promotion["files"].items():
            self.assertEqual(
                expected,
                hashlib.sha256((self.output / relative).read_bytes()).hexdigest(),
            )
        self.assertEqual(0, self.promotion["verifier"]["exit_code"])
        self.assertTrue(self.promotion["verifier"]["report"]["verified"])

    def test_text_bg_block_mapping_flip_bpp_and_zero_transparency(self):
        from tools.export_runtime_bg_composites import _layer_pixels, _map_offset

        self.assertEqual(0x0810, _map_offset(0x0800, 0, 8, 0))
        self.assertEqual(0x1010, _map_offset(0x0800, 1, 40, 0))
        self.assertEqual(0x1010, _map_offset(0x0800, 2, 8, 32))
        self.assertEqual(0x2010, _map_offset(0x0800, 3, 40, 32))

        io = bytearray(0x58)
        palette = bytearray(0x200)
        vram = bytearray(0x10000)
        struct.pack_into("<H", io, 0x08, 0x0100)
        struct.pack_into("<H", vram, 0x0800, 0x2C00)
        vram[7 * 4 + 3] = 0x50
        struct.pack_into("<H", palette, 37 * 2, 0x001F)
        rgba, _ = _layer_pixels(bytes(io), bytes(palette), bytes(vram), 0)
        self.assertEqual(bytes((255, 0, 0, 255)), rgba[:4])
        self.assertEqual(bytes((0, 0, 0, 0)), rgba[4:8])

        io = bytearray(0x58)
        palette = bytearray(0x200)
        vram = bytearray(0x10000)
        struct.pack_into("<H", io, 0x08, 0x0180)
        vram[0] = 7
        struct.pack_into("<H", palette, 7 * 2, 0x03E0)
        rgba, _ = _layer_pixels(bytes(io), bytes(palette), bytes(vram), 0)
        self.assertEqual(bytes((0, 255, 0, 255)), rgba[:4])
        self.assertEqual(bytes((0, 0, 0, 0)), rgba[4:8])

    def test_archives_hash_bound_unique_state_layers_and_pre_effect_previews(self):
        states = self.manifest["states"]
        self.assertEqual(
            self.manifest["summary"]["unique_state_count"],
            len(states),
        )
        archive = self.output / self.manifest["archive"]["file"]
        self.assertEqual(
            self.manifest["archive"]["sha256"],
            hashlib.sha256(archive.read_bytes()).hexdigest(),
        )
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(
                self.manifest["archive"]["member_count"],
                len(bundle.namelist()),
            )
            for state in states:
                self.assertEqual(64, len(state["state_id"]))
                for output in state["outputs"]:
                    raw = bundle.read(output["archive_member"])
                    self.assertEqual(
                        output["sha256"],
                        hashlib.sha256(raw).hexdigest(),
                    )
                    self.assertEqual(240, output["width"])
                    self.assertEqual(160, output["height"])
                self.assertEqual(
                    "debug-preview-pre-window-pre-blend-bg-only-not-final-frame",
                    state["composite_semantics"],
                )

    def test_independent_verifier_rebuilds_and_rejects_tampering(self):
        from tools.verify_runtime_bg_composites import verify_artifact

        source = (
            ROOT / "tools" / "verify_runtime_bg_composites.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(91, report["checkpoint_count"])
        self.assertEqual(
            self.manifest["summary"]["unique_state_count"],
            report["state_count"],
        )

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            manifest_path = tampered / "runtime-bg-composites.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoints"][0]["backgrounds"][0]["hofs"] ^= 1
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            output = tampered / self.manifest["archive"]["file"]
            raw = bytearray(output.read_bytes())
            raw[-16] ^= 1
            output.write_bytes(raw)
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])
