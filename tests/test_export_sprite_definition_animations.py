#!/usr/bin/env python3
"""ROM-backed generic Sprite animation sequence export."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class SpriteDefinitionAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_sprite_definition_animations import (
            export_sprite_definition_animations,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "animations"
        cls.manifest = export_sprite_definition_animations(
            ROOT,
            cls.output_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_closes_all_43_single_frame_sequences(self):
        self.assertEqual(
            "sprite-definition-animations-v1",
            self.manifest["schema"],
        )
        self.assertEqual(43, self.manifest["entry_count"])
        self.assertEqual(43, self.manifest["sequence_count"])
        self.assertEqual(43, self.manifest["keyframe_count"])
        self.assertEqual(43, self.manifest["single_frame_sequence_count"])
        self.assertEqual(43, self.manifest["terminated_sequence_count"])
        self.assertEqual(0, self.manifest["looping_sequence_count"])

        for entry in self.manifest["entries"]:
            timeline = json.loads(
                (self.output_dir / entry["timeline_json"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                [{"frame_index": 0, "duration_ticks": 1}],
                timeline["keyframes"],
            )
            self.assertEqual(
                {
                    "frame_index": -1,
                    "raw_hex": "ffff0000",
                    "generic_task_flags": "0x00000049",
                    "policy": "stop",
                },
                timeline["terminator"],
            )
            self.assertEqual(1, timeline["total_duration_ticks"])

    def test_links_every_frame_to_existing_static_asset(self):
        static = json.loads(
            (
                ROOT
                / "artifacts/sprite-definition-assets-v2/manifest.json"
            ).read_text(encoding="utf-8")
        )
        static_by_id = {entry["id"]: entry for entry in static["entries"]}
        for entry in self.manifest["entries"]:
            source = static_by_id[entry["id"]]
            self.assertEqual(source["asset"]["png"], entry["source_png"])
            self.assertEqual(
                source["asset"]["png_sha256"],
                entry["source_png_sha256"],
            )
            with Image.open(self.output_dir / entry["contact_sheet_png"]) as image:
                self.assertEqual("RGBA", image.mode)
                self.assertEqual(190, image.height)

    def test_independent_verifier_accepts_export(self):
        from tools.verify_sprite_definition_animations import (
            verify_sprite_definition_animations,
        )

        result = verify_sprite_definition_animations(ROOT, self.output_dir)
        self.assertEqual(43, result["verified_entries"])
        self.assertEqual([], result["errors"])

    def test_verifier_rejects_semantic_tampering_with_updated_hash(self):
        from tools.verify_sprite_definition_animations import (
            verify_sprite_definition_animations,
        )

        manifest_path = self.output_dir / "manifest.json"
        item = self.manifest["entries"][0]
        timeline_path = self.output_dir / item["timeline_json"]
        original_manifest = manifest_path.read_bytes()
        original_timeline = timeline_path.read_bytes()
        manifest = json.loads(original_manifest)
        timeline = json.loads(original_timeline)
        timeline["keyframes"][0]["duration_ticks"] = 2
        timeline["total_duration_ticks"] = 2
        tampered = (
            json.dumps(timeline, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        manifest["entries"][0]["timeline_json_sha256"] = hashlib.sha256(
            tampered
        ).hexdigest()
        try:
            timeline_path.write_bytes(tampered)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_sprite_definition_animations(
                ROOT,
                self.output_dir,
            )
        finally:
            timeline_path.write_bytes(original_timeline)
            manifest_path.write_bytes(original_manifest)
        self.assertIn("entry 0 timeline keyframes mismatch", result["errors"])
        self.assertIn("entry 0 duration mismatch", result["errors"])

    def test_verifier_rejects_forged_scope_code_and_terminal_claims(self):
        from tools.verify_sprite_definition_animations import (
            verify_sprite_definition_animations,
        )

        manifest_path = self.output_dir / "manifest.json"
        original = manifest_path.read_bytes()
        manifest = json.loads(original)
        manifest["scope"]["scene_specific_overwrite_checked"] = True
        manifest["code_slices"][0]["sha256"] = "0" * 64
        manifest["entries"][0]["terminal_policy"] = "loop"
        try:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_sprite_definition_animations(
                ROOT,
                self.output_dir,
            )
        finally:
            manifest_path.write_bytes(original)
        self.assertIn("scope contract mismatch", result["errors"])
        self.assertIn("code slice manifest mismatch", result["errors"])
        self.assertIn("entry 0 terminal policy mismatch", result["errors"])


if __name__ == "__main__":
    unittest.main()
