from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "artifacts/battle-effect-resource-pairs-v1/manifest.json"
TABLE_OFFSET = 0x59911C
TABLE_SIZE = 19 * 8
sys.path.insert(0, str(ROOT / "tools"))


class ImportBattleEffectResourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.resources = self._resources_by_identity()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _resources_by_identity(self) -> dict[tuple[str, str], dict]:
        grouped: dict[tuple[str, str], dict] = {}
        for entry in self.catalog["entries"]:
            for role in ("graphics", "palette"):
                resource = entry[role]
                digest = resource["decompressed_sha256"]
                key = (role, digest)
                row = grouped.setdefault(
                    key,
                    {
                        "role": role,
                        "sha256": digest,
                        "decompressed_size": resource["decompressed_size"],
                        "source_file": resource["output_bin"],
                        "physical_offsets": set(),
                        "group_ids": set(),
                    },
                )
                row["physical_offsets"].add(resource["file_offset"])
                row["group_ids"].add(entry["group_id"])
        return grouped

    def _write_source(self, row: dict, content: bytes) -> Path:
        path = self.temp / f"{row['role']}-{row['sha256']}.bin"
        path.write_bytes(content)
        return path

    def _write_spec(self, edits: list[dict]) -> Path:
        path = self.temp / "spec.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "battle-effect-resource-import-v1",
                    "source_catalog": (
                        "artifacts/battle-effect-resource-pairs-v1/"
                        "manifest.json"
                    ),
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def _edit(self, row: dict, source: Path, *, edit_id: str = "edit") -> dict:
        return {
            "id": edit_id,
            "resource_type": row["role"],
            "resource_sha256": row["sha256"],
            "source_file": str(source),
            "expected": {
                "decompressed_size": row["decompressed_size"],
                "physical_offsets": sorted(row["physical_offsets"]),
            },
        }

    def _catalog_source(self, row: dict) -> Path:
        return (
            ROOT
            / "artifacts/battle-effect-resource-pairs-v1"
            / row["source_file"]
        )

    def test_catalog_has_complete_36_to_35_to_34_denominator(self):
        self.assertEqual(34, len(self.resources))
        self.assertEqual(
            35,
            sum(len(row["physical_offsets"]) for row in self.resources.values()),
        )
        self.assertEqual(
            36,
            sum(len(row["group_ids"]) for row in self.resources.values()),
        )

    def test_noop_all_resources_emits_no_patches(self):
        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        edits = [
            self._edit(
                row,
                self._catalog_source(row),
                edit_id=row["sha256"],
            )
            for row in self.resources.values()
        ]
        self.assertEqual(
            [],
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec(edits),
                rom=self.base,
            ),
        )

    def test_shared_group_graphics_edit_updates_one_slot_and_both_aliases(self):
        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "graphics"
            and value["group_ids"] == {2, 3}
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[0] ^= 1
        patches = resolve_battle_effect_resource_patches(
            ROOT,
            self._write_spec(
                [self._edit(row, self._write_source(row, bytes(content)))]
            ),
            rom=self.base,
        )

        self.assertEqual(1, len(patches))
        item = patches[0]
        self.assertEqual([2, 3], item["affected_groups"])
        self.assertEqual(2, len(item["logical_aliases"]))
        self.assertEqual(sorted(row["physical_offsets"]), [item["offset"]])
        self.assertEqual("battle_effect_resource", item["asset_type"])
        self.assertEqual(
            bytes(content),
            lz77_decompress(bytes.fromhex(item["after_hex"]), 0),
        )
        self.assertEqual(
            len(bytes.fromhex(item["before_hex"])),
            len(bytes.fromhex(item["after_hex"])),
        )

    def test_shared_palette_content_updates_both_physical_slots_atomically(self):
        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "palette"
            and value["group_ids"] == {16, 17}
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[2] ^= 1
        patches = resolve_battle_effect_resource_patches(
            ROOT,
            self._write_spec(
                [self._edit(row, self._write_source(row, bytes(content)))]
            ),
            rom=self.base,
        )

        self.assertEqual(2, len(patches))
        self.assertEqual(
            sorted(row["physical_offsets"]),
            [item["offset"] for item in patches],
        )
        for item in patches:
            self.assertEqual([16, 17], item["affected_groups"])
            self.assertEqual(2, len(item["logical_aliases"]))
            self.assertEqual(
                bytes(content),
                lz77_decompress(bytes.fromhex(item["after_hex"]), 0),
            )

    def test_explicit_physical_target_can_split_equal_palette_content(self):
        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "palette"
            and value["group_ids"] == {16, 17}
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[2] ^= 1
        edit = self._edit(row, self._write_source(row, bytes(content)))
        edit["target_physical_offsets"] = [min(row["physical_offsets"])]
        patches = resolve_battle_effect_resource_patches(
            ROOT,
            self._write_spec([edit]),
            rom=self.base,
        )

        self.assertEqual(1, len(patches))
        self.assertEqual([16], patches[0]["affected_groups"])
        self.assertEqual(
            [min(row["physical_offsets"])],
            patches[0]["target_physical_offsets"],
        )
        self.assertEqual(
            sorted(row["physical_offsets"]),
            patches[0]["content_physical_offsets"],
        )

    def test_invalid_or_conflicting_physical_targets_are_rejected(self):
        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "palette"
            and value["group_ids"] == {16, 17}
        )
        offsets = sorted(row["physical_offsets"])
        invalid_targets = (
            [],
            list(reversed(offsets)),
            [offsets[0], offsets[0]],
            [0],
        )
        for target in invalid_targets:
            with self.subTest(target=target):
                edit = self._edit(row, self._catalog_source(row))
                edit["target_physical_offsets"] = target
                with self.assertRaisesRegex(
                    ValueError,
                    "canonical non-empty subset",
                ):
                    resolve_battle_effect_resource_patches(
                        ROOT,
                        self._write_spec([edit]),
                        rom=self.base,
                    )

        content = bytearray(self._catalog_source(row).read_bytes())
        content[2] ^= 1
        first = self._edit(
            row,
            self._write_source(row, bytes(content)),
            edit_id="first",
        )
        first["target_physical_offsets"] = [offsets[0]]
        second = dict(first, id="second")
        with self.assertRaisesRegex(
            ValueError,
            "duplicate battle-effect resource",
        ):
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec([first, second]),
                rom=self.base,
            )

    def test_overflow_is_atomic_and_provenance_and_duplicates_are_rejected(self):
        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        overflow = next(
            value
            for value in self.resources.values()
            if value["role"] == "graphics"
            and 0x3426D8 in value["physical_offsets"]
        )
        overflow_content = bytearray(self._catalog_source(overflow).read_bytes())
        overflow_content[0] ^= 1
        valid = next(
            value
            for value in self.resources.values()
            if value["role"] == "palette"
        )
        valid_content = bytearray(self._catalog_source(valid).read_bytes())
        valid_content[2] ^= 1
        with self.assertRaisesRegex(ValueError, "does not fit every physical"):
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            valid,
                            self._write_source(valid, bytes(valid_content)),
                            edit_id="valid-first",
                        ),
                        self._edit(
                            overflow,
                            self._write_source(
                                overflow,
                                bytes(overflow_content),
                            ),
                            edit_id="overflow-second",
                        ),
                    ]
                ),
                rom=self.base,
            )

        stale = self._edit(valid, self._catalog_source(valid))
        stale["expected"]["physical_offsets"] = [0]
        with self.assertRaisesRegex(ValueError, "physical offset provenance"):
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec([stale]),
                rom=self.base,
            )

        edit = self._edit(valid, self._catalog_source(valid))
        with self.assertRaisesRegex(ValueError, "duplicate battle-effect resource"):
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec([edit, dict(edit, id="duplicate")]),
                rom=self.base,
            )

    def test_resource_format_and_base_rom_are_fail_closed(self):
        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        graphics = next(
            value
            for value in self.resources.values()
            if value["role"] == "graphics"
        )
        with self.assertRaisesRegex(ValueError, "complete 32-byte 4bpp tiles"):
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            graphics,
                            self._write_source(
                                graphics,
                                self._catalog_source(graphics).read_bytes()[:-1],
                            ),
                        )
                    ]
                ),
                rom=self.base,
            )

        palette = next(
            value
            for value in self.resources.values()
            if value["role"] == "palette"
        )
        with self.assertRaisesRegex(ValueError, "exactly 32 bytes"):
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            palette,
                            self._write_source(palette, bytes(31)),
                        )
                    ]
                ),
                rom=self.base,
            )

        altered_base = bytearray(self.base)
        altered_base[0] ^= 1
        with self.assertRaisesRegex(ValueError, "base ROM hash"):
            resolve_battle_effect_resource_patches(
                ROOT,
                self._write_spec(
                    [self._edit(palette, self._catalog_source(palette))]
                ),
                rom=bytes(altered_base),
            )

    def test_build_manifest_dispatch_applies_resource_without_changing_table(self):
        import tools.build_mod as build_mod

        from tools.import_battle_effect_resources import (
            resolve_battle_effect_resource_patches,
        )

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "palette"
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[2] ^= 1

        temp_root = self.temp / "project"
        (temp_root / "rom").mkdir(parents=True)
        (
            temp_root / "artifacts/battle-effect-resource-pairs-v1"
        ).mkdir(parents=True)
        (
            temp_root / "sequel/content/battle-effect-resources"
        ).mkdir(parents=True)
        (temp_root / "sequel/patches").mkdir(parents=True)
        (temp_root / "rom/base.gba").write_bytes(self.base)
        (
            temp_root
            / "artifacts/battle-effect-resource-pairs-v1/manifest.json"
        ).write_bytes(CATALOG_PATH.read_bytes())
        local_source = (
            temp_root
            / "sequel/content/battle-effect-resources/edited.bin"
        )
        local_source.write_bytes(content)
        local_spec = (
            temp_root
            / "sequel/content/battle-effect-resources/edit.json"
        )
        local_spec.write_bytes(
            self._write_spec(
                [self._edit(row, local_source)]
            ).read_bytes()
        )
        (temp_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "patches": [
                        {
                            "id": "battle-effect-resource-import",
                            "type": "battle_effect_resource",
                            "spec": (
                                "sequel/content/battle-effect-resources/"
                                "edit.json"
                            ),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "battle-effect-resource-build-test",
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

        expected = resolve_battle_effect_resource_patches(
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
        for item in expected:
            self.assertEqual(
                bytes(content),
                lz77_decompress(output, item["offset"]),
            )
        self.assertEqual(
            len(expected),
            sum(
                item.get("asset_type") == "battle_effect_resource"
                for item in report["applied_patches"]
            ),
        )
        applied = [
            item
            for item in report["applied_patches"]
            if item.get("asset_type") == "battle_effect_resource"
        ]
        self.assertEqual(
            sorted(row["physical_offsets"]),
            applied[0]["content_physical_offsets"],
        )
        self.assertEqual(
            sorted(row["physical_offsets"]),
            applied[0]["target_physical_offsets"],
        )

    def test_writeback_audit_records_complete_capacity_denominator(self):
        from tools.export_battle_effect_resource_writeback_audit import (
            export_battle_effect_resource_writeback_audit,
        )

        output = self.temp / "battle-effect-resource-writeback-v1"
        payload = export_battle_effect_resource_writeback_audit(ROOT, output)
        self.assertEqual(34, payload["summary"]["content_resource_count"])
        self.assertEqual(35, payload["summary"]["physical_slot_count"])
        self.assertEqual(36, payload["summary"]["logical_reference_count"])
        self.assertEqual(
            35,
            payload["summary"]["original_roundtrip_fit_slot_count"],
        )
        self.assertEqual(
            32,
            payload["summary"]["mutation_fit_slot_count"],
        )
        self.assertEqual(
            3,
            payload["summary"]["mutation_overflow_slot_count"],
        )
        self.assertTrue(
            payload["scope"]["explicit_physical_slot_targeting_available"]
        )
        self.assertFalse(payload["scope"]["arbitrary_edit_capacity_complete"])
        self.assertFalse(payload["scope"]["resource_relocation_complete"])
        self.assertFalse(payload["scope"]["pointer_rewrite_complete"])
        self.assertFalse(payload["scope"]["runtime_pixel_equivalence"])

    def test_independent_audit_verifier_rejects_resigned_semantic_tamper(self):
        from tools.export_battle_effect_resource_writeback_audit import (
            export_battle_effect_resource_writeback_audit,
        )
        from tools.verify_battle_effect_resource_writeback_audit import (
            verify_battle_effect_resource_writeback_audit,
        )

        output = self.temp / "battle-effect-resource-writeback-v1"
        export_battle_effect_resource_writeback_audit(ROOT, output)
        report = verify_battle_effect_resource_writeback_audit(ROOT, output)
        self.assertTrue(report["verified"], report["errors"])

        payload_path = output / "battle-effect-resource-writeback.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["resources"][0]["physical_slots"][0]["slot_size"] += 1
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest["payload_sha256"] = digest
        manifest["files"][
            "battle-effect-resource-writeback.json"
        ] = digest
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = verify_battle_effect_resource_writeback_audit(ROOT, output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("resource records mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
