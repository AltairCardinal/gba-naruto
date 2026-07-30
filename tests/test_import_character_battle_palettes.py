from __future__ import annotations

from collections import defaultdict
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


class ImportCharacterBattlePalettesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.palettes = self._palettes_by_pointer()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _palettes_by_pointer(self) -> dict[int, dict]:
        grouped: dict[int, dict] = {}
        for resource in self.catalog["resources"]:
            pointer = int(resource["palette"]["gba_pointer"], 16)
            offset = pointer - 0x08000000
            row = grouped.setdefault(
                offset,
                {
                    "file_offset": offset,
                    "gba_pointer": resource["palette"]["gba_pointer"],
                    "sha256": resource["palette"]["sha256"],
                    "source_files": set(),
                    "resource_ids": [],
                    "slot_rows": [],
                },
            )
            self.assertEqual(row["sha256"], resource["palette"]["sha256"])
            row["source_files"].add(resource["palette"]["file"])
            row["resource_ids"].append(resource["resource_id"])
            row["slot_rows"].extend(resource["slot_rows"])
        return grouped

    def _write_source(self, row: dict, content: bytes) -> Path:
        path = self.temp / f"palette-{row['file_offset']:06x}.bin"
        path.write_bytes(content)
        return path

    def _catalog_source(self, row: dict) -> Path:
        return (
            ROOT
            / "artifacts/character-battle-visuals-v1"
            / sorted(row["source_files"])[0]
        )

    def _edit(self, row: dict, source: Path, *, edit_id: str = "edit") -> dict:
        return {
            "id": edit_id,
            "palette_pointer": row["gba_pointer"],
            "palette_sha256": row["sha256"],
            "source_file": str(source),
            "expected": {
                "file_offset": row["file_offset"],
                "resource_ids": sorted(row["resource_ids"]),
                "slot_rows": sorted(row["slot_rows"]),
            },
        }

    def _write_spec(self, edits: list[dict]) -> Path:
        path = self.temp / "spec.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "character-battle-palette-import-v1",
                    "source_catalog": (
                        "artifacts/character-battle-visuals-v1/manifest.json"
                    ),
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_has_complete_48_to_250_to_342_denominator(self):
        self.assertEqual(48, len(self.palettes))
        self.assertEqual(
            250,
            sum(len(row["resource_ids"]) for row in self.palettes.values()),
        )
        self.assertEqual(
            342,
            sum(len(row["slot_rows"]) for row in self.palettes.values()),
        )
        spans = sorted((offset, offset + 32) for offset in self.palettes)
        self.assertTrue(
            all(left_end <= right_start for (_, left_end), (right_start, _) in zip(
                spans, spans[1:]
            ))
        )

    def test_noop_all_palettes_emits_no_patches(self):
        from tools.import_character_battle_palettes import (
            resolve_character_battle_palette_patches,
        )

        edits = [
            self._edit(
                row,
                self._catalog_source(row),
                edit_id=f"palette-{offset:06x}",
            )
            for offset, row in sorted(self.palettes.items())
        ]
        self.assertEqual(
            [],
            resolve_character_battle_palette_patches(
                ROOT,
                self._write_spec(edits),
                rom=self.base,
            ),
        )

    def test_edit_updates_one_physical_palette_and_all_pointer_aliases(self):
        from tools.import_character_battle_palettes import (
            resolve_character_battle_palette_patches,
        )

        row = max(
            self.palettes.values(),
            key=lambda value: len(value["slot_rows"]),
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[2] ^= 1
        patches = resolve_character_battle_palette_patches(
            ROOT,
            self._write_spec(
                [self._edit(row, self._write_source(row, bytes(content)))]
            ),
            rom=self.base,
        )

        self.assertEqual(1, len(patches))
        item = patches[0]
        self.assertEqual("bytes", item["type"])
        self.assertEqual("character_battle_palette", item["asset_type"])
        self.assertEqual(row["file_offset"], item["offset"])
        self.assertEqual(row["gba_pointer"], item["palette_pointer"])
        self.assertEqual(row["sha256"], item["palette_sha256"])
        self.assertEqual(hashlib.sha256(content).hexdigest(), item["replacement_sha256"])
        self.assertEqual(sorted(row["resource_ids"]), item["affected_resource_ids"])
        self.assertEqual(sorted(row["slot_rows"]), item["affected_slot_rows"])
        self.assertEqual(32, len(bytes.fromhex(item["before_hex"])))
        self.assertEqual(bytes(content), bytes.fromhex(item["after_hex"]))

    def test_equal_content_at_distinct_pointers_remains_independently_editable(self):
        from tools.import_character_battle_palettes import (
            resolve_character_battle_palette_patches,
        )

        by_content: dict[str, list[dict]] = defaultdict(list)
        for row in self.palettes.values():
            by_content[row["sha256"]].append(row)
        rows = next(values for values in by_content.values() if len(values) > 1)
        target = rows[0]
        untouched = rows[1]
        content = bytearray(self._catalog_source(target).read_bytes())
        content[4] ^= 1
        patches = resolve_character_battle_palette_patches(
            ROOT,
            self._write_spec(
                [self._edit(target, self._write_source(target, bytes(content)))]
            ),
            rom=self.base,
        )

        self.assertEqual([target["file_offset"]], [item["offset"] for item in patches])
        self.assertNotEqual(target["file_offset"], untouched["file_offset"])

    def test_rejects_wrong_length_stale_provenance_duplicates_and_unknown_pointer(self):
        from tools.import_character_battle_palettes import (
            resolve_character_battle_palette_patches,
        )

        row = next(iter(self.palettes.values()))
        short = self._edit(row, self._write_source(row, bytes(30)))
        with self.assertRaisesRegex(ValueError, "exactly 32 bytes"):
            resolve_character_battle_palette_patches(
                ROOT,
                self._write_spec([short]),
                rom=self.base,
            )

        source = self._catalog_source(row)
        stale = self._edit(row, source)
        stale["expected"]["slot_rows"] = []
        with self.assertRaisesRegex(ValueError, "slot-row provenance"):
            resolve_character_battle_palette_patches(
                ROOT,
                self._write_spec([stale]),
                rom=self.base,
            )

        edit = self._edit(row, source)
        with self.assertRaisesRegex(ValueError, "duplicate character battle palette"):
            resolve_character_battle_palette_patches(
                ROOT,
                self._write_spec([edit, dict(edit, id="duplicate")]),
                rom=self.base,
            )

        unknown = self._edit(row, source)
        unknown["palette_pointer"] = "0x08000000"
        with self.assertRaisesRegex(ValueError, "unknown character battle palette"):
            resolve_character_battle_palette_patches(
                ROOT,
                self._write_spec([unknown]),
                rom=self.base,
            )

    def test_build_manifest_dispatch_applies_fixed_length_palette(self):
        from tools import build_mod
        from tools.import_character_battle_palettes import (
            resolve_character_battle_palette_patches,
        )

        row = next(iter(self.palettes.values()))
        content = bytearray(self._catalog_source(row).read_bytes())
        content[2] ^= 1
        temp_root = self.temp / "project-root"
        (temp_root / "rom").mkdir(parents=True)
        (temp_root / "sequel/patches").mkdir(parents=True)
        (
            temp_root / "artifacts/character-battle-visuals-v1"
        ).mkdir(parents=True)
        (
            temp_root / "sequel/content/character-battle-palettes"
        ).mkdir(parents=True)
        (temp_root / "rom/base.gba").write_bytes(self.base)
        (
            temp_root
            / "artifacts/character-battle-visuals-v1/manifest.json"
        ).write_bytes(CATALOG_PATH.read_bytes())
        local_source = (
            temp_root
            / "sequel/content/character-battle-palettes/edited.bin"
        )
        local_source.write_bytes(content)
        local_spec = (
            temp_root
            / "sequel/content/character-battle-palettes/edit.json"
        )
        local_spec.write_bytes(
            self._write_spec([self._edit(row, local_source)]).read_bytes()
        )
        (temp_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "patches": [
                        {
                            "id": "character-battle-palette-import",
                            "type": "character_battle_palette",
                            "spec": (
                                "sequel/content/character-battle-palettes/edit.json"
                            ),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "character-battle-palette-build-test",
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

        expected = resolve_character_battle_palette_patches(
            temp_root,
            local_spec,
            rom=self.base,
        )
        with patch.object(build_mod, "ROOT", temp_root):
            report = build_mod.build(project_path)

        output = (temp_root / "build/output.gba").read_bytes()
        self.assertEqual(
            self.base[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE],
            output[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE],
        )
        self.assertEqual(bytes(content), output[row["file_offset"] : row["file_offset"] + 32])
        applied = [
            item
            for item in report["applied_patches"]
            if item.get("asset_type") == "character_battle_palette"
        ]
        self.assertEqual(len(expected), len(applied))
        self.assertEqual(sorted(row["resource_ids"]), applied[0]["affected_resource_ids"])
        self.assertEqual(sorted(row["slot_rows"]), applied[0]["affected_slot_rows"])

    def test_writeback_audit_and_independent_verifier_cover_all_palettes(self):
        from tools.export_character_battle_palette_writeback_audit import (
            export_character_battle_palette_writeback_audit,
        )
        from tools.verify_character_battle_palette_writeback_audit import (
            verify_character_battle_palette_writeback_audit,
        )

        output = self.temp / "character-battle-palette-writeback-v1"
        payload = export_character_battle_palette_writeback_audit(ROOT, output)
        self.assertEqual(48, payload["summary"]["physical_palette_count"])
        self.assertEqual(40, payload["summary"]["unique_content_count"])
        self.assertEqual(250, payload["summary"]["resource_reference_count"])
        self.assertEqual(342, payload["summary"]["slot_reference_count"])
        self.assertEqual(48, payload["summary"]["mutation_writeback_count"])
        self.assertTrue(
            payload["scope"]["arbitrary_fixed_length_palette_writeback_complete"]
        )
        self.assertFalse(payload["scope"]["graphics_writeback_complete"])
        self.assertFalse(payload["scope"]["runtime_pixel_equivalence"])

        verifier_source = (
            ROOT / "tools/verify_character_battle_palette_writeback_audit.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", verifier_source)
        self.assertNotIn("import tools", verifier_source)
        report = verify_character_battle_palette_writeback_audit(ROOT, output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])

        payload_path = output / "character-battle-palette-writeback.json"
        tampered = json.loads(payload_path.read_text(encoding="utf-8"))
        tampered["palettes"][0]["slot_rows"] = []
        payload_path.write_text(
            json.dumps(tampered, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest["payload_sha256"] = digest
        manifest["files"]["character-battle-palette-writeback.json"] = digest
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = verify_character_battle_palette_writeback_audit(ROOT, output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("palette records mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
