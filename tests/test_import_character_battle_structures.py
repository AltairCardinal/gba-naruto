from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "artifacts/character-battle-visuals-v1/manifest.json"
TABLE_OFFSET = 0x596D5C
TABLE_SIZE = 558 * 16
sys.path.insert(0, str(ROOT / "tools"))


class ImportCharacterBattleStructuresTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.base = (ROOT / "rom/base.gba").read_bytes()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _resource(self, resource_id: int = 0) -> dict:
        return self.catalog["resources"][resource_id]

    def _expected(self, resource: dict) -> dict:
        return {
            "component_region_sha256": resource["component_region"]["sha256"],
            "timeline_region_sha256": resource["timeline_region"]["sha256"],
            "frame_count": resource["frame_count"],
            "component_count": resource["component_count"],
            "animation_count": resource["animation_count"],
            "keyframe_count": resource["keyframe_count"],
            "tile_count": resource["graphics"]["tile_count"],
            "slot_rows": resource["slot_rows"],
        }

    def _write_spec(self, edits: list[dict]) -> Path:
        path = self.temp / "spec.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "character-battle-structure-import-v1",
                    "source_catalog": (
                        "artifacts/character-battle-visuals-v1/manifest.json"
                    ),
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def _edit(
        self,
        resource: dict,
        *,
        component_edits: list[dict] | None = None,
        keyframe_edits: list[dict] | None = None,
    ) -> dict:
        return {
            "id": f"resource-{resource['resource_id']}",
            "resource_id": resource["resource_id"],
            "expected": self._expected(resource),
            "component_edits": component_edits or [],
            "keyframe_edits": keyframe_edits or [],
        }

    def test_catalog_closes_complete_structure_denominator(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        self.assertEqual(
            [],
            resolve_character_battle_structure_patches(
                ROOT,
                self._write_spec([]),
                rom=self.base,
            ),
        )
        self.assertEqual(250, len(self.catalog["resources"]))
        self.assertEqual(
            2004,
            sum(row["frame_count"] for row in self.catalog["resources"]),
        )
        self.assertEqual(
            2190,
            sum(row["component_count"] for row in self.catalog["resources"]),
        )
        self.assertEqual(
            784,
            sum(row["animation_count"] for row in self.catalog["resources"]),
        )
        self.assertEqual(
            3187,
            sum(row["keyframe_count"] for row in self.catalog["resources"]),
        )
        self.assertEqual(
            342,
            sum(len(row["slot_rows"]) for row in self.catalog["resources"]),
        )

    def test_component_semantic_edit_reencodes_one_fixed_record(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        resource = self._resource()
        source = resource["frames"][0]["components"][0]
        patches = resolve_character_battle_structure_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        component_edits=[
                            {
                                "frame_id": 0,
                                "component_index": 0,
                                "tile_offset": source["tile_offset"] + 1,
                                "horizontal_flip": True,
                                "vertical_flip": True,
                                "x": source["x"] + 1,
                                "y": source["y"] - 1,
                                "width": source["width"],
                                "height": source["height"],
                            }
                        ],
                    )
                ]
            ),
            rom=self.base,
        )
        self.assertEqual(1, len(patches))
        item = patches[0]
        self.assertEqual("character_battle_structure", item["asset_type"])
        self.assertEqual("component", item["structure_type"])
        self.assertEqual(0, item["resource_id"])
        self.assertEqual(0, item["frame_id"])
        self.assertEqual(0, item["component_index"])
        values = struct.unpack("<HBBhhHHHHBBH", bytes.fromhex(item["after_hex"]))
        self.assertEqual(source["tile_offset"] + 1, values[0])
        self.assertEqual(3, values[1])
        self.assertEqual(source["x"] + 1, values[3])
        self.assertEqual(source["y"] - 1, values[4])
        self.assertEqual(resource["slot_rows"], item["affected_slot_rows"])

    def test_all_supported_obj_shapes_and_flip_states_accept_exact_tile_boundary(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        resource = self._resource()
        shapes = (
            (8, 8),
            (16, 16),
            (32, 32),
            (64, 64),
            (16, 8),
            (32, 8),
            (32, 16),
            (64, 32),
            (8, 16),
            (8, 32),
            (16, 32),
            (32, 64),
        )
        edits = []
        for frame_id, (width, height) in enumerate(shapes):
            tile_span = (width // 8) * (height // 8)
            edits.append(
                {
                    "frame_id": frame_id,
                    "component_index": 0,
                    "tile_offset": (
                        resource["graphics"]["tile_count"] - tile_span
                    ),
                    "horizontal_flip": bool(frame_id & 1),
                    "vertical_flip": bool(frame_id & 2),
                    "width": width,
                    "height": height,
                }
            )
        patches = resolve_character_battle_structure_patches(
            ROOT,
            self._write_spec(
                [self._edit(resource, component_edits=edits)]
            ),
            rom=self.base,
        )
        self.assertEqual(12, len(patches))
        for item, shape in zip(patches, shapes):
            values = struct.unpack(
                "<HBBhhHHHHBBH",
                bytes.fromhex(item["after_hex"]),
            )
            self.assertEqual(shape, (values[5], values[6]))
            tile_end = values[0] + (values[5] // 8) * (values[6] // 8)
            self.assertEqual(resource["graphics"]["tile_count"], tile_end)

    def test_keyframe_semantic_edit_reencodes_one_fixed_record(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        resource = self._resource()
        source = resource["animations"][0]["keyframes"][0]
        replacement_frame = (
            source["frame_id"] + 1
        ) % resource["frame_count"]
        patches = resolve_character_battle_structure_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        keyframe_edits=[
                            {
                                "animation_id": 0,
                                "keyframe_index": 0,
                                "frame_id": replacement_frame,
                                "hold_frames": source["hold_frames"] + 1,
                            }
                        ],
                    )
                ]
            ),
            rom=self.base,
        )
        self.assertEqual(1, len(patches))
        item = patches[0]
        self.assertEqual("keyframe", item["structure_type"])
        self.assertEqual(
            (replacement_frame, source["hold_frames"] + 1),
            struct.unpack("<HH", bytes.fromhex(item["after_hex"])),
        )

    def test_shared_resource_edit_discloses_all_slot_aliases(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        resource = next(
            row
            for row in self.catalog["resources"]
            if len(row["slot_rows"]) > 1
        )
        source = resource["animations"][0]["keyframes"][0]
        patches = resolve_character_battle_structure_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        keyframe_edits=[
                            {
                                "animation_id": 0,
                                "keyframe_index": 0,
                                "frame_id": source["frame_id"],
                                "hold_frames": source["hold_frames"] + 1,
                            }
                        ],
                    )
                ]
            ),
            rom=self.base,
        )
        self.assertEqual(resource["slot_rows"], patches[0]["affected_slot_rows"])
        self.assertEqual(
            len(resource["slot_rows"]),
            len(patches[0]["logical_aliases"]),
        )

    def test_anomalous_fbff_trailer_is_preserved_outside_component_patch(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        resource = self._resource(147)
        frame = resource["frames"][2]
        self.assertEqual("fffb0000", frame["frame_trailer_raw_hex"])
        source = frame["components"][0]
        patches = resolve_character_battle_structure_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        component_edits=[
                            {
                                "frame_id": 2,
                                "component_index": 0,
                                "x": source["x"] + 1,
                            }
                        ],
                    )
                ]
            ),
            rom=self.base,
        )
        self.assertEqual(1, len(patches))
        item = patches[0]
        self.assertEqual(0x25A8E4, item["offset"] + 20)
        self.assertEqual(
            bytes.fromhex("fffb0000"),
            self.base[0x25A8E4 : 0x25A8E8],
        )
        self.assertEqual(20, len(bytes.fromhex(item["after_hex"])))

    def test_invalid_component_and_keyframe_semantics_are_rejected(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        resource = self._resource()
        component = resource["frames"][0]["components"][0]
        invalid_components = (
            (
                {
                    "frame_id": 0,
                    "component_index": 0,
                    "tile_offset": resource["graphics"]["tile_count"] - 1,
                    "width": 64,
                    "height": 64,
                },
                "tile range",
            ),
            (
                {
                    "frame_id": 0,
                    "component_index": 0,
                    "tile_offset": component["tile_offset"],
                    "width": 24,
                    "height": 24,
                },
                "supported OBJ size",
            ),
            (
                {
                    "frame_id": 0,
                    "component_index": 0,
                    "tile_offset": component["tile_offset"],
                    "x": 40000,
                },
                "signed 16-bit",
            ),
        )
        for component_edit, message in invalid_components:
            with self.subTest(component_edit=component_edit):
                with self.assertRaisesRegex(ValueError, message):
                    resolve_character_battle_structure_patches(
                        ROOT,
                        self._write_spec(
                            [
                                self._edit(
                                    resource,
                                    component_edits=[component_edit],
                                )
                            ]
                        ),
                        rom=self.base,
                    )

        for keyframe_edit, message in (
            (
                {
                    "animation_id": 0,
                    "keyframe_index": 0,
                    "frame_id": resource["frame_count"],
                },
                "frame_id",
            ),
            (
                {
                    "animation_id": 0,
                    "keyframe_index": 0,
                    "hold_frames": 0,
                },
                "hold_frames",
            ),
        ):
            with self.subTest(keyframe_edit=keyframe_edit):
                with self.assertRaisesRegex(ValueError, message):
                    resolve_character_battle_structure_patches(
                        ROOT,
                        self._write_spec(
                            [
                                self._edit(
                                    resource,
                                    keyframe_edits=[keyframe_edit],
                                )
                            ]
                        ),
                        rom=self.base,
                    )

    def test_duplicates_stale_provenance_and_altered_base_are_rejected(self):
        from tools.import_character_battle_structures import (
            resolve_character_battle_structure_patches,
        )

        resource = self._resource()
        component = {
            "frame_id": 0,
            "component_index": 0,
            "x": resource["frames"][0]["components"][0]["x"] + 1,
        }
        duplicate = self._edit(
            resource,
            component_edits=[component, dict(component)],
        )
        with self.assertRaisesRegex(ValueError, "duplicate component edit"):
            resolve_character_battle_structure_patches(
                ROOT,
                self._write_spec([duplicate]),
                rom=self.base,
            )

        stale = self._edit(resource)
        stale["expected"]["component_count"] -= 1
        with self.assertRaisesRegex(ValueError, "provenance"):
            resolve_character_battle_structure_patches(
                ROOT,
                self._write_spec([stale]),
                rom=self.base,
            )

        altered = bytearray(self.base)
        altered[0] ^= 1
        with self.assertRaisesRegex(ValueError, "base ROM hash"):
            resolve_character_battle_structure_patches(
                ROOT,
                self._write_spec([self._edit(resource)]),
                rom=bytes(altered),
            )

    def test_build_manifest_applies_structure_without_changing_pointer_tables(self):
        from tools import build_mod

        resource = self._resource()
        source = resource["frames"][0]["components"][0]
        temp_root = self.temp / "project-root"
        (temp_root / "rom").mkdir(parents=True)
        (
            temp_root / "artifacts/character-battle-visuals-v1"
        ).mkdir(parents=True)
        (
            temp_root / "sequel/content/character-battle-structures"
        ).mkdir(parents=True)
        (temp_root / "sequel/patches").mkdir(parents=True)
        (temp_root / "rom/base.gba").write_bytes(self.base)
        (
            temp_root
            / "artifacts/character-battle-visuals-v1/manifest.json"
        ).write_bytes(CATALOG_PATH.read_bytes())
        spec = self._write_spec(
            [
                self._edit(
                    resource,
                    component_edits=[
                        {
                            "frame_id": 0,
                            "component_index": 0,
                            "x": source["x"] + 1,
                        }
                    ],
                    keyframe_edits=[
                        {
                            "animation_id": 0,
                            "keyframe_index": 0,
                            "hold_frames": (
                                resource["animations"][0]["keyframes"][0][
                                    "hold_frames"
                                ]
                                + 1
                            ),
                        }
                    ],
                )
            ]
        )
        local_spec = (
            temp_root
            / "sequel/content/character-battle-structures/edit.json"
        )
        local_spec.write_bytes(spec.read_bytes())
        (temp_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "patches": [
                        {
                            "id": "character-battle-structure-import",
                            "type": "character_battle_structure",
                            "spec": (
                                "sequel/content/character-battle-structures/"
                                "edit.json"
                            ),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "character-battle-structure-build-test",
            "base_rom": {
                "path": "rom/base.gba",
                "sha1": hashlib.sha1(self.base).hexdigest(),
            },
            "patch_manifest": "sequel/patches/manifest.json",
            "build": {
                "output_rom": "build/output.gba",
                "report": "build/report.json",
            },
        }
        project_path = temp_root / "sequel/project.json"
        project_path.write_text(json.dumps(project), encoding="utf-8")
        frame_table_offset = (
            int(resource["frame_pointer_table"]["gba_pointer"], 16)
            - 0x08000000
        )
        frame_table_size = resource["frame_pointer_table"]["size"]
        animation_table_offset = (
            int(resource["animation_pointer_table"]["gba_pointer"], 16)
            - 0x08000000
        )
        animation_table_size = resource["animation_pointer_table"]["size"]
        original_table = self.base[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
        with patch.object(build_mod, "ROOT", temp_root):
            report = build_mod.build(project_path)
        output = (temp_root / "build/output.gba").read_bytes()
        self.assertEqual(
            original_table,
            output[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE],
        )
        self.assertEqual(
            self.base[
                frame_table_offset : frame_table_offset + frame_table_size
            ],
            output[
                frame_table_offset : frame_table_offset + frame_table_size
            ],
        )
        self.assertEqual(
            self.base[
                animation_table_offset :
                animation_table_offset + animation_table_size
            ],
            output[
                animation_table_offset :
                animation_table_offset + animation_table_size
            ],
        )
        applied = [
            item
            for item in report["applied_patches"]
            if item.get("asset_type") == "character_battle_structure"
        ]
        self.assertEqual(2, len(applied))

    def test_writeback_audit_closes_same_layout_structure_denominator(self):
        from tools.export_character_battle_structure_writeback_audit import (
            export_character_battle_structure_writeback_audit,
        )

        output = self.temp / "character-battle-structure-writeback-v1"
        payload = export_character_battle_structure_writeback_audit(
            ROOT,
            output,
        )
        summary = payload["summary"]
        self.assertEqual(250, summary["resource_count"])
        self.assertEqual(342, summary["slot_reference_count"])
        self.assertEqual(2004, summary["frame_count"])
        self.assertEqual(2190, summary["component_count"])
        self.assertEqual(784, summary["animation_count"])
        self.assertEqual(3187, summary["keyframe_count"])
        self.assertEqual(2190, summary["component_roundtrip_count"])
        self.assertEqual(2190, summary["component_mutation_count"])
        self.assertEqual(3187, summary["keyframe_roundtrip_count"])
        self.assertEqual(3187, summary["keyframe_mutation_count"])
        self.assertEqual(1, summary["anomalous_trailer_count"])
        self.assertTrue(
            payload["scope"]["component_semantic_writeback_complete"]
        )
        self.assertTrue(
            payload["scope"]["keyframe_semantic_writeback_complete"]
        )
        self.assertFalse(
            payload["scope"]["variable_count_structure_writeback_complete"]
        )
        self.assertFalse(payload["scope"]["runtime_pixel_equivalence"])

    def test_independent_structure_verifier_rejects_resigned_tamper(self):
        verifier_source = (
            ROOT
            / "tools/verify_character_battle_structure_writeback_audit.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", verifier_source)
        self.assertNotIn("import tools", verifier_source)

        from tools.export_character_battle_structure_writeback_audit import (
            export_character_battle_structure_writeback_audit,
        )
        from tools.verify_character_battle_structure_writeback_audit import (
            verify_character_battle_structure_writeback_audit,
        )

        output = self.temp / "character-battle-structure-writeback-v1"
        export_character_battle_structure_writeback_audit(ROOT, output)
        report = verify_character_battle_structure_writeback_audit(ROOT, output)
        self.assertTrue(report["verified"], report["errors"])

        payload_path = output / "character-battle-structure-writeback.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["resources"][0]["component_count"] += 1
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest["payload_sha256"] = digest
        manifest["files"][
            "character-battle-structure-writeback.json"
        ] = digest
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = verify_character_battle_structure_writeback_audit(ROOT, output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("resource records mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
