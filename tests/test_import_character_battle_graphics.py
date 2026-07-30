from __future__ import annotations

import hashlib
import json
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


class ImportCharacterBattleGraphicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.graphics = self._graphics_by_pointer()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _graphics_by_pointer(self) -> dict[int, dict]:
        grouped: dict[int, dict] = {}
        for resource in self.catalog["resources"]:
            graphics = resource["graphics"]
            pointer = int(graphics["gba_pointer"], 16)
            offset = pointer - 0x08000000
            maximum_tile_end = max(
                component["tile_end"]
                for frame in resource["frames"]
                for component in frame["components"]
            )
            self.assertNotIn(offset, grouped)
            grouped[offset] = {
                "file_offset": offset,
                "gba_pointer": graphics["gba_pointer"],
                "sha256": graphics["sha256"],
                "source_file": graphics["file"],
                "size": graphics["size"],
                "tile_count": graphics["tile_count"],
                "maximum_component_tile_end": maximum_tile_end,
                "resource_id": resource["resource_id"],
                "slot_rows": resource["slot_rows"],
                "component_count": resource["component_count"],
            }
        return grouped

    def _catalog_source(self, row: dict) -> Path:
        return (
            ROOT
            / "artifacts/character-battle-visuals-v1"
            / row["source_file"]
        )

    def _write_source(self, row: dict, content: bytes) -> Path:
        path = self.temp / f"graphics-{row['resource_id']:03d}.bin"
        path.write_bytes(content)
        return path

    def _edit(self, row: dict, source: Path, *, edit_id: str = "edit") -> dict:
        return {
            "id": edit_id,
            "graphics_pointer": row["gba_pointer"],
            "graphics_sha256": row["sha256"],
            "source_file": str(source),
            "expected": {
                "file_offset": row["file_offset"],
                "size": row["size"],
                "tile_count": row["tile_count"],
                "maximum_component_tile_end": row[
                    "maximum_component_tile_end"
                ],
                "resource_id": row["resource_id"],
                "slot_rows": row["slot_rows"],
            },
        }

    def _write_spec(self, edits: list[dict]) -> Path:
        path = self.temp / "spec.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "character-battle-graphics-import-v1",
                    "source_catalog": (
                        "artifacts/character-battle-visuals-v1/manifest.json"
                    ),
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_250_to_250_to_342_and_component_denominator(self):
        self.assertEqual(250, len(self.graphics))
        self.assertEqual(
            250,
            len({row["sha256"] for row in self.graphics.values()}),
        )
        self.assertEqual(
            342,
            sum(len(row["slot_rows"]) for row in self.graphics.values()),
        )
        self.assertEqual(
            2190,
            sum(row["component_count"] for row in self.graphics.values()),
        )
        self.assertEqual(
            60430,
            sum(row["tile_count"] for row in self.graphics.values()),
        )
        self.assertTrue(
            all(
                row["tile_count"] == row["maximum_component_tile_end"]
                for row in self.graphics.values()
            )
        )
        spans = sorted(
            (offset, offset + row["size"])
            for offset, row in self.graphics.items()
        )
        self.assertTrue(
            all(
                left_end <= right_start
                for (_, left_end), (right_start, _) in zip(spans, spans[1:])
            )
        )

    def test_noop_all_graphics_emits_no_patches(self):
        from tools.import_character_battle_graphics import (
            resolve_character_battle_graphics_patches,
        )

        edits = [
            self._edit(
                row,
                self._catalog_source(row),
                edit_id=f"graphics-{row['resource_id']:03d}",
            )
            for row in self.graphics.values()
        ]
        self.assertEqual(
            [],
            resolve_character_battle_graphics_patches(
                ROOT,
                self._write_spec(edits),
                rom=self.base,
            ),
        )

    def test_edit_updates_one_physical_graphics_and_all_logical_aliases(self):
        from tools.import_character_battle_graphics import (
            resolve_character_battle_graphics_patches,
        )

        row = max(
            self.graphics.values(),
            key=lambda item: len(item["slot_rows"]),
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[0] ^= 1
        patches = resolve_character_battle_graphics_patches(
            ROOT,
            self._write_spec(
                [self._edit(row, self._write_source(row, bytes(content)))]
            ),
            rom=self.base,
        )
        self.assertEqual(1, len(patches))
        item = patches[0]
        self.assertEqual("bytes", item["type"])
        self.assertEqual("character_battle_graphics", item["asset_type"])
        self.assertEqual(row["file_offset"], item["offset"])
        self.assertEqual(row["gba_pointer"], item["graphics_pointer"])
        self.assertEqual(row["sha256"], item["graphics_sha256"])
        self.assertEqual(
            hashlib.sha256(content).hexdigest(),
            item["replacement_sha256"],
        )
        self.assertEqual(row["resource_id"], item["affected_resource_id"])
        self.assertEqual(row["slot_rows"], item["affected_slot_rows"])
        self.assertEqual(row["size"], len(bytes.fromhex(item["before_hex"])))
        self.assertEqual(bytes(content), bytes.fromhex(item["after_hex"]))

    def test_rejects_wrong_length_stale_provenance_duplicates_and_unknown(self):
        from tools.import_character_battle_graphics import (
            resolve_character_battle_graphics_patches,
        )

        row = next(iter(self.graphics.values()))
        short = self._catalog_source(row).read_bytes()[:-32]
        with self.assertRaisesRegex(ValueError, "exactly .* bytes"):
            resolve_character_battle_graphics_patches(
                ROOT,
                self._write_spec(
                    [self._edit(row, self._write_source(row, short))]
                ),
                rom=self.base,
            )

        stale = self._edit(row, self._catalog_source(row))
        stale["expected"]["maximum_component_tile_end"] -= 1
        with self.assertRaisesRegex(ValueError, "component provenance"):
            resolve_character_battle_graphics_patches(
                ROOT,
                self._write_spec([stale]),
                rom=self.base,
            )

        edit = self._edit(row, self._catalog_source(row))
        with self.assertRaisesRegex(
            ValueError,
            "duplicate character battle graphics",
        ):
            resolve_character_battle_graphics_patches(
                ROOT,
                self._write_spec([edit, dict(edit, id="duplicate")]),
                rom=self.base,
            )

        unknown = self._edit(row, self._catalog_source(row))
        unknown["graphics_pointer"] = "0x08000000"
        with self.assertRaisesRegex(
            ValueError,
            "unknown character battle graphics",
        ):
            resolve_character_battle_graphics_patches(
                ROOT,
                self._write_spec([unknown]),
                rom=self.base,
            )

    def test_rejects_altered_base_rom(self):
        from tools.import_character_battle_graphics import (
            resolve_character_battle_graphics_patches,
        )

        row = next(iter(self.graphics.values()))
        altered = bytearray(self.base)
        altered[0] ^= 1
        with self.assertRaisesRegex(ValueError, "base ROM hash"):
            resolve_character_battle_graphics_patches(
                ROOT,
                self._write_spec(
                    [self._edit(row, self._catalog_source(row))]
                ),
                rom=bytes(altered),
            )

    def test_build_manifest_dispatch_applies_graphics_without_changing_table(self):
        from tools import build_mod

        row = next(iter(self.graphics.values()))
        content = bytearray(self._catalog_source(row).read_bytes())
        content[0] ^= 1
        temp_root = self.temp / "project-root"
        (temp_root / "rom").mkdir(parents=True)
        (
            temp_root / "artifacts/character-battle-visuals-v1"
        ).mkdir(parents=True)
        (
            temp_root / "sequel/content/character-battle-graphics"
        ).mkdir(parents=True)
        (temp_root / "sequel/patches").mkdir(parents=True)
        (temp_root / "rom/base.gba").write_bytes(self.base)
        (
            temp_root
            / "artifacts/character-battle-visuals-v1/manifest.json"
        ).write_bytes(CATALOG_PATH.read_bytes())
        local_source = (
            temp_root
            / "sequel/content/character-battle-graphics/edited.bin"
        )
        local_source.write_bytes(content)
        local_spec = (
            temp_root
            / "sequel/content/character-battle-graphics/edit.json"
        )
        local_spec.write_text(
            json.dumps(
                {
                    "schema": "character-battle-graphics-import-v1",
                    "source_catalog": (
                        "artifacts/character-battle-visuals-v1/manifest.json"
                    ),
                    "edits": [self._edit(row, local_source)],
                }
            ),
            encoding="utf-8",
        )
        (temp_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "patches": [
                        {
                            "id": "character-battle-graphics-import",
                            "type": "character_battle_graphics",
                            "spec": (
                                "sequel/content/character-battle-graphics/"
                                "edit.json"
                            ),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "character-battle-graphics-build-test",
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
        original_table = self.base[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
        with patch.object(build_mod, "ROOT", temp_root):
            report = build_mod.build(project_path)
        output = (temp_root / "build/output.gba").read_bytes()
        self.assertEqual(
            original_table,
            output[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE],
        )
        self.assertEqual(
            bytes(content),
            output[row["file_offset"] : row["file_offset"] + row["size"]],
        )
        applied = next(
            item
            for item in report["applied_patches"]
            if item.get("asset_type") == "character_battle_graphics"
        )
        self.assertEqual(row["resource_id"], applied["affected_resource_id"])
        self.assertEqual(row["slot_rows"], applied["affected_slot_rows"])

    def test_writeback_audit_closes_full_fixed_length_denominator(self):
        from tools.export_character_battle_graphics_writeback_audit import (
            export_character_battle_graphics_writeback_audit,
        )

        output = self.temp / "character-battle-graphics-writeback-v1"
        payload = export_character_battle_graphics_writeback_audit(ROOT, output)
        summary = payload["summary"]
        self.assertEqual(250, summary["physical_graphics_count"])
        self.assertEqual(250, summary["unique_content_count"])
        self.assertEqual(250, summary["resource_count"])
        self.assertEqual(342, summary["slot_reference_count"])
        self.assertEqual(2004, summary["frame_count"])
        self.assertEqual(2190, summary["component_count"])
        self.assertEqual(60430, summary["tile_count"])
        self.assertEqual(1933760, summary["graphics_byte_count"])
        self.assertEqual(250, summary["original_roundtrip_count"])
        self.assertEqual(250, summary["mutation_writeback_count"])
        self.assertTrue(
            payload["scope"][
                "arbitrary_fixed_length_raw_graphics_writeback_complete"
            ]
        )
        self.assertFalse(payload["scope"]["variable_length_writeback_complete"])
        self.assertFalse(payload["scope"]["frame_structure_writeback_complete"])
        self.assertFalse(payload["scope"]["runtime_pixel_equivalence"])

    def test_independent_verifier_rejects_resigned_semantic_tamper(self):
        verifier_source = (
            ROOT
            / "tools/verify_character_battle_graphics_writeback_audit.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", verifier_source)
        self.assertNotIn("import tools", verifier_source)

        from tools.export_character_battle_graphics_writeback_audit import (
            export_character_battle_graphics_writeback_audit,
        )
        from tools.verify_character_battle_graphics_writeback_audit import (
            verify_character_battle_graphics_writeback_audit,
        )

        output = self.temp / "character-battle-graphics-writeback-v1"
        export_character_battle_graphics_writeback_audit(ROOT, output)
        report = verify_character_battle_graphics_writeback_audit(ROOT, output)
        self.assertTrue(report["verified"], report["errors"])

        payload_path = output / "character-battle-graphics-writeback.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["resources"][0]["graphics_size"] += 32
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest["payload_sha256"] = digest
        manifest["files"][
            "character-battle-graphics-writeback.json"
        ] = digest
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = verify_character_battle_graphics_writeback_audit(ROOT, output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("resource records mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
