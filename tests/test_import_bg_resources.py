from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "artifacts/bg-resource-canvases-v1/manifest.json"
TABLE_OFFSET = 0x59903C
TABLE_SIZE = 14 * 16
sys.path.insert(0, str(ROOT / "tools"))


class ImportBgResourcesTests(unittest.TestCase):
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
            for role in ("graphics", "palette", "tilemap"):
                resource = entry[role]
                digest = resource["decompressed_sha256"]
                row = grouped.setdefault(
                    (role, digest),
                    {
                        "role": role,
                        "sha256": digest,
                        "decompressed_size": resource["decompressed_size"],
                        "source_file": resource["file"],
                        "physical_offsets": set(),
                        "entry_ids": set(),
                        "modes": set(),
                    },
                )
                row["physical_offsets"].add(resource["file_offset"])
                row["entry_ids"].add(entry["entry_id"])
                row["modes"].add(entry["mode_flag"])
        return grouped

    def _catalog_source(self, row: dict) -> Path:
        return ROOT / "artifacts/bg-resource-canvases-v1" / row["source_file"]

    def _write_source(self, row: dict, content: bytes, suffix: str = "") -> Path:
        path = self.temp / f"{row['role']}-{row['sha256']}{suffix}.bin"
        path.write_bytes(content)
        return path

    def _write_spec(self, edits: list[dict], name: str = "spec.json") -> Path:
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "bg-resource-import-v1",
                    "source_catalog": (
                        "artifacts/bg-resource-canvases-v1/manifest.json"
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

    def test_catalog_has_complete_31_to_36_to_36_denominator(self):
        self.assertEqual(31, len(self.resources))
        self.assertEqual(
            36,
            sum(len(row["physical_offsets"]) for row in self.resources.values()),
        )
        self.assertEqual(
            36,
            sum(len(row["entry_ids"]) for row in self.resources.values()),
        )

    def test_noop_all_resources_emits_no_patches(self):
        from tools.import_bg_resources import resolve_bg_resource_patches

        edits = [
            self._edit(row, self._catalog_source(row), edit_id=row["sha256"])
            for row in self.resources.values()
        ]
        self.assertEqual(
            [],
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec(edits),
                rom=self.base,
            ),
        )

    def test_equal_content_defaults_to_all_slots_and_can_split_explicitly(self):
        from tools.import_bg_resources import resolve_bg_resource_patches

        row = next(
            item
            for item in self.resources.values()
            if item["role"] == "tilemap" and item["entry_ids"] == {9, 10, 11, 13}
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[2] ^= 0x01
        source = self._write_source(row, bytes(content))
        patches = resolve_bg_resource_patches(
            ROOT,
            self._write_spec([self._edit(row, source)]),
            rom=self.base,
        )
        self.assertEqual(4, len(patches))
        self.assertEqual(
            sorted(row["physical_offsets"]),
            [item["offset"] for item in patches],
        )
        for item in patches:
            self.assertEqual("bg_resource", item["asset_type"])
            self.assertEqual(sorted(row["entry_ids"]), item["affected_entries"])
            self.assertEqual(
                bytes(content),
                lz77_decompress(bytes.fromhex(item["after_hex"]), 0),
            )

        target = [min(row["physical_offsets"])]
        edit = self._edit(row, source)
        edit["target_physical_offsets"] = target
        split = resolve_bg_resource_patches(
            ROOT,
            self._write_spec([edit], "split.json"),
            rom=self.base,
        )
        self.assertEqual(1, len(split))
        self.assertEqual(target, split[0]["target_physical_offsets"])
        self.assertEqual(
            sorted(row["physical_offsets"]),
            split[0]["content_physical_offsets"],
        )
        self.assertEqual(1, len(split[0]["affected_entries"]))

    def test_invalid_targets_duplicates_and_stale_provenance_are_rejected(self):
        from tools.import_bg_resources import resolve_bg_resource_patches

        row = next(
            item
            for item in self.resources.values()
            if len(item["physical_offsets"]) > 1
        )
        offsets = sorted(row["physical_offsets"])
        for target in ([], list(reversed(offsets)), [offsets[0], offsets[0]], [0]):
            with self.subTest(target=target):
                edit = self._edit(row, self._catalog_source(row))
                edit["target_physical_offsets"] = target
                with self.assertRaisesRegex(ValueError, "canonical non-empty subset"):
                    resolve_bg_resource_patches(
                        ROOT,
                        self._write_spec([edit]),
                        rom=self.base,
                    )

        duplicate = self._edit(row, self._catalog_source(row))
        with self.assertRaisesRegex(ValueError, "duplicate BG resource"):
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec([duplicate, dict(duplicate, id="again")]),
                rom=self.base,
            )

        stale = self._edit(row, self._catalog_source(row))
        stale["expected"]["physical_offsets"] = [0]
        with self.assertRaisesRegex(ValueError, "physical offset provenance"):
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec([stale]),
                rom=self.base,
            )

    def test_payload_shapes_and_base_rom_are_fail_closed(self):
        from tools.import_bg_resources import resolve_bg_resource_patches

        for role, expected_size, message in (
            ("palette", 383, "exactly 384 bytes"),
            ("tilemap", 639, "exactly 640 bytes"),
        ):
            row = next(item for item in self.resources.values() if item["role"] == role)
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, message):
                resolve_bg_resource_patches(
                    ROOT,
                    self._write_spec(
                        [self._edit(row, self._write_source(row, bytes(expected_size)))]
                    ),
                    rom=self.base,
                )

        graphics = next(
            item
            for item in self.resources.values()
            if item["role"] == "graphics" and item["modes"] == {1}
        )
        with self.assertRaisesRegex(ValueError, "complete 64-byte 8bpp tiles"):
            resolve_bg_resource_patches(
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

        altered = bytearray(self.base)
        altered[0] ^= 1
        with self.assertRaisesRegex(ValueError, "base ROM hash"):
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            graphics,
                            self._catalog_source(graphics),
                        )
                    ]
                ),
                rom=bytes(altered),
            )

    def test_linked_graphics_palette_and_tilemap_constraints_are_enforced(self):
        from tools.import_bg_resources import resolve_bg_resource_patches

        tilemap = next(
            item
            for item in self.resources.values()
            if item["role"] == "tilemap" and item["entry_ids"] == {2}
        )
        invalid_index = bytearray(self._catalog_source(tilemap).read_bytes())
        invalid_index[:2] = struct.pack("<H", 0x03FF)
        with self.assertRaisesRegex(ValueError, "tile index"):
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            tilemap,
                            self._write_source(tilemap, bytes(invalid_index), "-index"),
                        )
                    ]
                ),
                rom=self.base,
            )

        invalid_bank = bytearray(self._catalog_source(tilemap).read_bytes())
        invalid_bank[:2] = struct.pack("<H", 0xF000)
        with self.assertRaisesRegex(ValueError, "palette index"):
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            tilemap,
                            self._write_source(tilemap, bytes(invalid_bank), "-bank"),
                        )
                    ]
                ),
                rom=self.base,
            )

        graphics = next(
            item
            for item in self.resources.values()
            if item["role"] == "graphics" and item["entry_ids"] == {9}
        )
        invalid_color = bytearray(self._catalog_source(graphics).read_bytes())
        invalid_color[0] = 0xFF
        with self.assertRaisesRegex(ValueError, "8bpp color index"):
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            graphics,
                            self._write_source(graphics, bytes(invalid_color)),
                        )
                    ]
                ),
                rom=self.base,
            )

    def test_overflow_is_atomic(self):
        from tools.import_bg_resources import resolve_bg_resource_patches

        overflow = next(
            item
            for item in self.resources.values()
            if item["role"] == "palette" and item["entry_ids"] == {1}
        )
        noisy = bytes(
            (value * 73 + 19) & 0xFF for value in range(overflow["decompressed_size"])
        )
        valid = next(
            item
            for item in self.resources.values()
            if item["role"] == "graphics" and item["entry_ids"] == {2}
        )
        valid_content = bytearray(self._catalog_source(valid).read_bytes())
        valid_content[0] ^= 1
        with self.assertRaisesRegex(ValueError, "does not fit every physical"):
            resolve_bg_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            valid,
                            self._write_source(valid, bytes(valid_content), "-valid"),
                        ),
                        self._edit(
                            overflow,
                            self._write_source(overflow, noisy, "-overflow"),
                        ),
                    ]
                ),
                rom=self.base,
            )

    def test_build_manifest_dispatch_applies_resource_without_changing_table(self):
        import tools.build_mod as build_mod

        row = next(
            item
            for item in self.resources.values()
            if item["role"] == "graphics" and item["entry_ids"] == {2}
        )
        content = bytearray(self._catalog_source(row).read_bytes())
        content[0] ^= 1
        temp_root = self.temp / "project"
        (temp_root / "rom").mkdir(parents=True)
        (temp_root / "artifacts/bg-resource-canvases-v1").mkdir(parents=True)
        (temp_root / "sequel/content/bg-resources").mkdir(parents=True)
        (temp_root / "sequel/patches").mkdir(parents=True)
        (temp_root / "rom/base.gba").write_bytes(self.base)
        (temp_root / "artifacts/bg-resource-canvases-v1/manifest.json").write_bytes(
            CATALOG_PATH.read_bytes()
        )
        local_source = temp_root / "sequel/content/bg-resources/edited.bin"
        local_source.write_bytes(content)
        edit = self._edit(row, local_source)
        local_spec = temp_root / "sequel/content/bg-resources/edit.json"
        local_spec.write_text(
            json.dumps(
                {
                    "schema": "bg-resource-import-v1",
                    "source_catalog": (
                        "artifacts/bg-resource-canvases-v1/manifest.json"
                    ),
                    "edits": [edit],
                }
            ),
            encoding="utf-8",
        )
        (temp_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "patches": [
                        {
                            "id": "bg-resource-import",
                            "type": "bg_resource",
                            "spec": "sequel/content/bg-resources/edit.json",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "bg-resource-build-test",
            "base_rom": {
                "path": "rom/base.gba",
                "sha1": hashlib.sha1(self.base).hexdigest(),
            },
            "patch_manifest": "sequel/patches/manifest.json",
            "build": {
                "output_rom": "build/test.gba",
                "report": "build/test-report.json",
            },
        }
        project_path = temp_root / "sequel/project.json"
        project_path.write_text(json.dumps(project), encoding="utf-8")
        original_table = self.base[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]

        with patch.object(build_mod, "ROOT", temp_root):
            report = build_mod.build(project_path)

        output = (temp_root / "build/test.gba").read_bytes()
        self.assertEqual(
            original_table,
            output[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE],
        )
        applied = next(
            item
            for item in report["applied_patches"]
            if item["id"].startswith("edit-")
        )
        self.assertEqual("bg_resource", applied["asset_type"])
        self.assertEqual(
            bytes(content),
            lz77_decompress(output, applied["offset"]),
        )

    def test_writeback_audit_closes_capacity_denominator(self):
        from tools.export_bg_resource_writeback_audit import (
            export_bg_resource_writeback_audit,
        )

        output = self.temp / "bg-resource-writeback-v1"
        payload = export_bg_resource_writeback_audit(ROOT, output)
        summary = payload["summary"]
        self.assertEqual(31, summary["content_resource_count"])
        self.assertEqual(36, summary["physical_slot_count"])
        self.assertEqual(36, summary["logical_reference_count"])
        self.assertEqual(31, summary["original_roundtrip_fit_content_count"])
        self.assertEqual(36, summary["original_roundtrip_fit_slot_count"])
        self.assertEqual(20, summary["mutation_fit_all_alias_content_count"])
        self.assertEqual(11, summary["mutation_overflow_content_count"])
        self.assertEqual(21, summary["mutation_fit_slot_count"])
        self.assertEqual(15, summary["mutation_overflow_slot_count"])
        self.assertEqual(0, summary["minimum_original_slot_margin"])
        self.assertEqual(-3, summary["minimum_mutation_slot_margin"])
        self.assertTrue(
            payload["scope"]["linked_resource_validation_complete"]
        )
        self.assertFalse(payload["scope"]["arbitrary_edit_capacity_complete"])
        self.assertFalse(payload["scope"]["resource_relocation_complete"])
        self.assertFalse(payload["scope"]["runtime_pixel_equivalence"])

    def test_independent_audit_verifier_rejects_resigned_semantic_tamper(self):
        verifier_source = (
            ROOT / "tools/verify_bg_resource_writeback_audit.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", verifier_source)
        self.assertNotIn("import tools", verifier_source)

        from tools.export_bg_resource_writeback_audit import (
            export_bg_resource_writeback_audit,
        )
        from tools.verify_bg_resource_writeback_audit import (
            verify_bg_resource_writeback_audit,
        )

        output = self.temp / "bg-resource-writeback-v1"
        export_bg_resource_writeback_audit(ROOT, output)
        report = verify_bg_resource_writeback_audit(ROOT, output)
        self.assertTrue(report["verified"], report["errors"])

        payload_path = output / "bg-resource-writeback.json"
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
        manifest["files"]["bg-resource-writeback.json"] = digest
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = verify_bg_resource_writeback_audit(ROOT, output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("resource records mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
