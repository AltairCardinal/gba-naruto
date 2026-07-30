import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from patch_safety import PatchSafetyGate
from rom_layout import RomLayout


class CharacterBattleBundleImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()
        cls.catalog = json.loads(
            (
                ROOT / "artifacts/character-battle-visuals-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        cls.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            cls.base,
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _author_frame(self, frame):
        return {
            "components": [
                {
                    "tile_offset": component["tile_offset"],
                    "orientation": component["orientation"],
                    "x": component["x"],
                    "y": component["y"],
                    "width": component["width"],
                    "height": component["height"],
                }
                for component in frame["components"]
            ]
        }

    def _author_animation(self, animation):
        return {
            "keyframes": [
                {
                    "frame_id": keyframe["frame_id"],
                    "hold_frames": keyframe["hold_frames"],
                }
                for keyframe in animation["keyframes"]
            ]
        }

    def _spec(self, resource_id=224):
        resource = self.catalog["resources"][resource_id]
        graphics = (
            ROOT
            / "artifacts/character-battle-visuals-v1"
            / resource["graphics"]["file"]
        ).read_bytes()
        graphics += bytes(range(32))
        graphics_path = self.temp_path / "graphics.bin"
        graphics_path.write_bytes(graphics)

        frames = [self._author_frame(frame) for frame in resource["frames"]]
        frames.append(
            {
                "components": [
                    {
                        "tile_offset": resource["graphics"]["tile_count"],
                        "orientation": 0,
                        "x": 0,
                        "y": 0,
                        "width": 8,
                        "height": 8,
                    }
                ]
            }
        )
        animations = [
            self._author_animation(animation)
            for animation in resource["animations"]
        ]
        animations.append(
            {
                "keyframes": [
                    {
                        "frame_id": len(frames) - 1,
                        "hold_frames": 3,
                    }
                ]
            }
        )
        payload = {
            "schema": "character-battle-bundle-import-v1",
            "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
            "catalog": "artifacts/character-battle-visuals-v1/manifest.json",
            "catalog_sha256": hashlib.sha256(
                (
                    ROOT / "artifacts/character-battle-visuals-v1/manifest.json"
                ).read_bytes()
            ).hexdigest(),
            "partition": "character-battle-visual-bundles",
            "owner": "character_battle_visuals",
            "edits": [
                {
                    "id": "resource-224-expanded",
                    "resource_id": resource_id,
                    "expected_descriptor": resource["descriptor"],
                    "expected_slot_rows": resource["slot_rows"],
                    "graphics_file": str(graphics_path),
                    "graphics_sha256": hashlib.sha256(graphics).hexdigest(),
                    "frames": frames,
                    "animations": animations,
                }
            ],
        }
        path = self.temp_path / "edit.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path, payload, resource, graphics

    def test_variable_bundle_relocates_payload_internal_pointers_and_all_aliases(self):
        from tools.build_mod import apply_patch
        from tools.import_character_battle_bundles import (
            resolve_character_battle_bundle_patches,
        )

        spec_path, _, resource, graphics = self._spec()
        patches = resolve_character_battle_bundle_patches(
            ROOT,
            spec_path,
            rom=self.base,
            layout=self.layout,
        )
        self.assertEqual(1 + len(resource["slot_rows"]), len(patches))
        bundle = patches[0]
        self.assertEqual("character_battle_bundle", bundle["asset_type"])
        self.assertEqual("character-battle-visual-bundles", bundle["allocation"]["partition"])
        self.assertEqual(0x600000, bundle["offset"])
        self.assertEqual(resource["frame_count"] + 1, bundle["frame_count"])
        self.assertEqual(resource["component_count"] + 1, bundle["component_count"])
        self.assertEqual(resource["animation_count"] + 1, bundle["animation_count"])
        self.assertEqual(resource["keyframe_count"] + 1, bundle["keyframe_count"])
        self.assertEqual(len(graphics) // 32, bundle["tile_count"])
        self.assertEqual(resource["slot_rows"], bundle["affected_slot_rows"])
        self.assertEqual([], bundle["unexpected_external_references"])

        data = bytearray(self.layout.expanded_base())
        gate = PatchSafetyGate(self.base, layout=self.layout)
        results = [apply_patch(data, patch, gate=gate) for patch in patches]
        self.assertEqual("allocation", results[0]["patch_class"])
        self.assertTrue(
            all(result["patch_class"] == "game_effective" for result in results[1:])
        )

        pointers = bundle["new_pointers"]
        descriptor = struct.pack(
            "<4I",
            int(pointers["frame_pointer_table"], 16),
            int(pointers["animation_pointer_table"], 16),
            int(pointers["graphics"], 16),
            int(pointers["palette"], 16),
        )
        for row in resource["slot_rows"]:
            offset = 0x596D5C + row * 16
            self.assertEqual(descriptor, data[offset:offset + 16])

        frame_table_offset = int(pointers["frame_pointer_table"], 16) - 0x08000000
        frame_pointers = struct.unpack_from(
            f"<{bundle['frame_count']}I",
            data,
            frame_table_offset,
        )
        self.assertEqual(
            int(pointers["component_region"], 16),
            frame_pointers[0],
        )
        self.assertTrue(
            all(left < right for left, right in zip(frame_pointers, frame_pointers[1:]))
        )
        animation_table_offset = (
            int(pointers["animation_pointer_table"], 16) - 0x08000000
        )
        animation_pointers = struct.unpack_from(
            f"<{bundle['animation_count']}I",
            data,
            animation_table_offset,
        )
        self.assertEqual(
            int(pointers["timeline_region"], 16),
            animation_pointers[0],
        )
        self.assertTrue(
            all(
                left < right
                for left, right in zip(
                    animation_pointers,
                    animation_pointers[1:],
                )
            )
        )

    def test_invalid_new_component_tile_range_fails_before_any_patch(self):
        from tools.import_character_battle_bundles import (
            resolve_character_battle_bundle_patches,
        )

        spec_path, payload, resource, _ = self._spec()
        payload["edits"][0]["frames"][-1]["components"][0]["tile_offset"] = (
            resource["graphics"]["tile_count"] + 1
        )
        spec_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "tile range"):
            resolve_character_battle_bundle_patches(
                ROOT,
                spec_path,
                rom=self.base,
                layout=self.layout,
            )

    def test_omitted_structure_preserves_the_verified_fbff_source_trailer(self):
        from tools.import_character_battle_bundles import (
            resolve_character_battle_bundle_patches,
        )

        spec_path, payload, resource, _ = self._spec(resource_id=147)
        del payload["edits"][0]["frames"]
        del payload["edits"][0]["animations"]
        spec_path.write_text(json.dumps(payload), encoding="utf-8")
        bundle = resolve_character_battle_bundle_patches(
            ROOT,
            spec_path,
            rom=self.base,
            layout=self.layout,
        )[0]
        raw = bytes.fromhex(bundle["after_hex"])
        pointers = bundle["new_pointers"]
        left = int(pointers["component_region"], 16) - 0x08000000 - bundle["offset"]
        right = int(pointers["frame_pointer_table"], 16) - 0x08000000 - bundle["offset"]
        original = (
            ROOT
            / "artifacts/character-battle-visuals-v1"
            / resource["component_region"]["file"]
        ).read_bytes()
        self.assertEqual(original, raw[left:right])
        self.assertIn(bytes.fromhex("fffb0000"), raw[left:right])

    def test_partition_overflow_rejects_the_whole_plan(self):
        from tools.import_character_battle_bundles import (
            resolve_character_battle_bundle_patches,
        )

        spec_path, _, _, _ = self._spec()
        layout_payload = json.loads(
            (ROOT / "sequel/rom-layout.json").read_text(encoding="utf-8")
        )
        partition = next(
            item
            for item in layout_payload["partitions"]
            if item["id"] == "character-battle-visual-bundles"
        )
        partition["end"] = "0x600100"
        small_layout = RomLayout.from_dict(layout_payload, self.base)
        with self.assertRaisesRegex(ValueError, "partition capacity"):
            resolve_character_battle_bundle_patches(
                ROOT,
                spec_path,
                rom=self.base,
                layout=small_layout,
            )

    def test_unified_build_applies_bundle_and_reports_allocation(self):
        from tools import build_mod

        spec_path, payload, resource, _ = self._spec()
        build_root = self.temp_path / "build-root"
        (build_root / "rom").mkdir(parents=True)
        (build_root / "sequel/patches").mkdir(parents=True)
        (build_root / "sequel/content/character-battle-bundles").mkdir(
            parents=True
        )
        (build_root / "artifacts/character-battle-visuals-v1").mkdir(
            parents=True
        )
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        (build_root / "sequel/rom-layout.json").write_bytes(
            (ROOT / "sequel/rom-layout.json").read_bytes()
        )
        (build_root / "artifacts/character-battle-visuals-v1/manifest.json").write_bytes(
            (
                ROOT / "artifacts/character-battle-visuals-v1/manifest.json"
            ).read_bytes()
        )
        local_spec = (
            build_root
            / "sequel/content/character-battle-bundles/edit.json"
        )
        local_spec.write_text(json.dumps(payload), encoding="utf-8")
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "bundle-import",
                            "type": "character_battle_bundle",
                            "spec": "sequel/content/character-battle-bundles/edit.json",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "character-battle-bundle-build-test",
            "base_rom": {
                "path": "rom/custom-base.gba",
                "sha1": hashlib.sha1(self.base).hexdigest(),
            },
            "rom_layout": "sequel/rom-layout.json",
            "patch_manifest": "sequel/patches/manifest.json",
            "build": {
                "output_rom": "build/output.gba",
                "report": "build/report.json",
            },
        }
        project_path = build_root / "sequel/project.json"
        project_path.write_text(json.dumps(project), encoding="utf-8")

        with mock.patch.object(build_mod, "ROOT", build_root):
            report = build_mod.build(project_path)

        self.assertEqual(0x1000000, report["output_rom"]["size"])
        self.assertEqual(1, report["patch_class_counts"]["allocation"])
        bundle = next(
            item
            for item in report["applied_patches"]
            if item.get("asset_type") == "character_battle_bundle"
        )
        self.assertEqual(resource["slot_rows"], bundle["affected_slot_rows"])
        self.assertEqual(
            "character-battle-visual-bundles",
            bundle["allocation_partition"],
        )
        self.assertEqual([], bundle["compressed_payload_coincidences"])


if __name__ == "__main__":
    unittest.main()
