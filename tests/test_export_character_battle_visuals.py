import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportCharacterBattleVisualsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_character_battle_visuals import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_complete_sparse_character_slot_matrix(self):
        manifest = self.manifest
        self.assertEqual(
            "character-battle-visuals-v1",
            manifest["schema"],
        )
        self.assertEqual(
            "baa3f86793e15d0d4abd44fcf10518da15ba0d76588b918838c3660e042e01dc",
            manifest["table"]["sha256"],
        )
        self.assertEqual(
            "5a0d06474ee94f5d3fd68cfe6c90224ce5a4cc8ffbb8ceeb6c4529c67ecd1b0b",
            manifest["consumer"]["selector"]["sha256"],
        )
        self.assertEqual(
            (
                "0x08596CCC + character_id * 0x90 + "
                "visual_slot * 0x10"
            ),
            manifest["consumer"]["descriptor_formula"],
        )
        self.assertEqual(
            [5, 6, 7, 8],
            manifest["consumer"]["left_facing_empty_slot_fallback"][
                "from_slots"
            ],
        )
        self.assertEqual(62, manifest["summary"]["character_count"])
        self.assertEqual(9, manifest["summary"]["slots_per_character"])
        self.assertEqual(558, manifest["summary"]["slot_count"])
        self.assertEqual(342, manifest["summary"]["populated_slot_count"])
        self.assertEqual(216, manifest["summary"]["empty_slot_count"])
        self.assertEqual(250, manifest["summary"]["resource_count"])
        self.assertEqual(48, manifest["summary"]["unique_palette_count"])
        self.assertEqual(40, manifest["summary"]["unique_palette_content_count"])
        self.assertEqual(2004, manifest["summary"]["frame_count"])
        self.assertEqual(2190, manifest["summary"]["component_count"])
        self.assertEqual(784, manifest["summary"]["animation_count"])
        self.assertEqual(3187, manifest["summary"]["keyframe_count"])
        self.assertEqual(60430, manifest["summary"]["resource_tile_count"])
        self.assertEqual(2674, manifest["summary"]["logical_frame_count"])
        self.assertEqual(2860, manifest["summary"]["logical_component_count"])
        self.assertEqual(1045, manifest["summary"]["logical_animation_count"])
        self.assertEqual(4246, manifest["summary"]["logical_keyframe_count"])
        self.assertEqual(
            [62, 62, 62, 62, 62, 8, 8, 8, 8],
            manifest["summary"]["populated_slots_by_visual_slot"],
        )
        self.assertEqual(
            2003,
            manifest["summary"]["renderer_terminator_frame_count"],
        )
        self.assertEqual(
            1,
            manifest["summary"]["anomalous_frame_trailer_count"],
        )
        self.assertEqual(
            2004,
            manifest["summary"]["verified_static_source_space_frame_count"],
        )
        self.assertEqual(
            0,
            manifest["summary"]["provisional_pointer_bounded_frame_count"],
        )
        self.assertTrue(
            manifest["scope"][
                "all_component_termination_semantics_complete"
            ]
        )
        self.assertTrue(
            manifest["scope"]["static_source_space_frames"]
        )
        self.assertFalse(
            manifest["scope"]["pointer_bounded_source_previews"]
        )

        self.assertEqual(558, len(manifest["slots"]))
        self.assertEqual(250, len(manifest["resources"]))
        self.assertEqual(
            list(range(1, 63)),
            sorted({slot["character_id"] for slot in manifest["slots"]}),
        )
        self.assertEqual(
            list(range(9)),
            sorted({slot["visual_slot"] for slot in manifest["slots"]}),
        )
        self.assertTrue(
            all(
                slot["resource_id"] is None
                for slot in manifest["slots"]
                if not slot["populated"]
            )
        )
        anomalous_slot = manifest["slots"][227]
        self.assertEqual(26, anomalous_slot["character_id"])
        self.assertEqual(2, anomalous_slot["visual_slot"])
        anomalous_resource = manifest["resources"][
            anomalous_slot["resource_id"]
        ]
        self.assertEqual(
            "fffb0000",
            anomalous_resource["frames"][2]["frame_trailer_raw_hex"],
        )
        self.assertFalse(
            anomalous_resource["frames"][2]["renderer_terminator"]
        )
        self.assertTrue(
            anomalous_resource["frames"][2]["render_complete"]
        )
        self.assertEqual(
            "runtime_verified_single_byte_corrupt_terminator",
            anomalous_resource["frames"][2]["interpretation"],
        )
        self.assertEqual(
            {
                "evidence": "artifacts/character-fbff-runtime-v1/manifest.json",
                "raw_signed_value": -1025,
                "normalization": "fffb0000 -> ffff0000",
                "control_rom_sha256": (
                    "3f55e607829db4497a1f49200514777c8"
                    "9df01f3624fd849005b96247502507a"
                ),
            },
            anomalous_resource["frames"][2]["termination_resolution"],
        )

    def test_preserves_frames_components_timelines_and_source_bytes(self):
        manifest = self.manifest
        first_slot = manifest["slots"][0]
        self.assertEqual(1, first_slot["character_id"])
        self.assertEqual(0, first_slot["visual_slot"])
        self.assertEqual(
            "field_idle_and_movement",
            first_slot["semantic"],
        )

        resource = manifest["resources"][first_slot["resource_id"]]
        self.assertEqual(20, resource["frame_count"])
        self.assertEqual(12, resource["animation_count"])
        self.assertEqual(
            [
                {"frame_id": 0, "hold_frames": 8},
                {"frame_id": 1, "hold_frames": 8},
                {"frame_id": 2, "hold_frames": 8},
                {"frame_id": 1, "hold_frames": 8},
            ],
            resource["animations"][0]["keyframes"],
        )
        self.assertEqual(
            "afd089ccaf2855ea2e5f79088051e8bb"
            "09b2d2e4a420ad0c49be37fc605c81ee",
            resource["frames"][0]["pixel_sha256"],
        )

        for resource in manifest["resources"]:
            for key in (
                "component_region",
                "frame_pointer_table",
                "timeline_region",
                "animation_pointer_table",
                "graphics",
                "palette",
            ):
                source = resource[key]
                path = self.output / source["file"]
                self.assertTrue(path.is_file(), path)
                self.assertEqual(
                    source["sha256"],
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            for frame in resource["frames"]:
                path = self.output / frame["png"]
                self.assertTrue(path.is_file(), path)
                self.assertEqual(
                    frame["png_sha256"],
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )

    def test_independent_verifier_accepts_export_and_rejects_tamper(self):
        from tools.verify_character_battle_visuals import verify_artifact

        verifier_source = (
            ROOT / "tools" / "verify_character_battle_visuals.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", verifier_source)
        self.assertNotIn("import tools", verifier_source)

        report = verify_artifact(ROOT, self.output)
        self.assertEqual(
            "character-battle-visuals-verification-v1", report["schema"]
        )
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertEqual(558, report["slots"])
        self.assertEqual(250, report["resources"])
        self.assertEqual(2004, report["frames"])

        first_png = (
            self.output
            / self.manifest["resources"][0]["frames"][0]["png"]
        )
        original = first_png.read_bytes()
        try:
            first_png.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            tampered = verify_artifact(ROOT, self.output)
            self.assertFalse(tampered["verified"])
            self.assertEqual(0, tampered["slots"])
            self.assertEqual(0, tampered["resources"])
            self.assertTrue(tampered["errors"])
            self.assertTrue(
                any(
                    "PNG" in error or "png" in error
                    for error in tampered["errors"]
                )
            )
        finally:
            first_png.write_bytes(original)

        manifest_path = self.output / "manifest.json"
        original_manifest = manifest_path.read_bytes()
        try:
            tampered_manifest = json.loads(original_manifest)
            tampered_manifest["slots"][0]["resource_id"] = 1
            manifest_path.write_text(
                json.dumps(tampered_manifest),
                encoding="utf-8",
            )
            tampered = verify_artifact(ROOT, self.output)
            self.assertTrue(tampered["errors"])
            self.assertTrue(
                any("slot" in error for error in tampered["errors"])
            )
        finally:
            manifest_path.write_bytes(original_manifest)

        graphics_path = (
            self.output / self.manifest["resources"][0]["graphics"]["file"]
        )
        original_graphics = graphics_path.read_bytes()
        try:
            graphics_path.write_bytes(
                bytes([original_graphics[0] ^ 1]) + original_graphics[1:]
            )
            self.assertTrue(
                verify_artifact(ROOT, self.output)["errors"]
            )
        finally:
            graphics_path.write_bytes(original_graphics)

        try:
            tampered_manifest = json.loads(original_manifest)
            tampered_manifest["resources"][0]["animations"][0][
                "keyframes"
            ][0]["hold_frames"] += 1
            manifest_path.write_text(
                json.dumps(tampered_manifest),
                encoding="utf-8",
            )
            self.assertTrue(
                verify_artifact(ROOT, self.output)["errors"]
            )
        finally:
            manifest_path.write_bytes(original_manifest)

        extra = self.output / "unexpected.bin"
        try:
            extra.write_bytes(b"unexpected")
            self.assertTrue(
                verify_artifact(ROOT, self.output)["errors"]
            )
        finally:
            extra.unlink()

    def test_output_target_rejects_repository_and_unrelated_directory(self):
        from tools.export_character_battle_visuals import (
            export_artifact,
            validate_output_target,
        )

        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT)
        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT.parent)

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            unrelated = Path(temporary) / "existing"
            unrelated.mkdir()
            sentinel = unrelated / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, unrelated)
            self.assertEqual(
                "user data",
                sentinel.read_text(encoding="utf-8"),
            )

            symlink = temporary_root / "artifact-link"
            symlink.symlink_to(unrelated, target_is_directory=True)
            with self.assertRaises(ValueError):
                validate_output_target(ROOT, symlink)

            legitimate = temporary_root / "legitimate-artifact"
            legitimate.mkdir()
            (legitimate / "manifest.json").write_text(
                json.dumps({"schema": "character-battle-visuals-v1"}),
                encoding="utf-8",
            )
            stale = legitimate / "stale.bin"
            stale.write_bytes(b"stale")
            replacement = export_artifact(ROOT, legitimate)
            self.assertEqual(
                "character-battle-visuals-v1",
                replacement["schema"],
            )
            self.assertFalse(stale.exists())
            self.assertTrue((legitimate / "manifest.json").is_file())

    def test_export_is_deterministic_and_cli_is_repository_relative(self):
        from tools.export_character_battle_visuals import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "artifact"
            second_manifest = export_artifact(ROOT, second)
            self.assertEqual(self.manifest, second_manifest)
            self.assertEqual(
                directory_hashes(self.output),
                directory_hashes(second),
            )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "cli-artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_character_battle_visuals.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('"resources": 250', result.stdout)
            self.assertTrue((output / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
