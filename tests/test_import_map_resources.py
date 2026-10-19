from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "artifacts/map-canvases-v1/manifest.json"
sys.path.insert(0, str(ROOT / "tools"))


class ImportMapResourcesTests(unittest.TestCase):
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
            for role, resource in entry["resources"].items():
                if resource is None:
                    continue
                key = (role, resource["sha256"])
                row = grouped.setdefault(
                    key,
                    {
                        "role": role,
                        "sha256": resource["sha256"],
                        "decompressed_size": resource["decompressed_size"],
                        "source_file": resource["output_bin"],
                        "physical_offsets": set(),
                        "map_ids": set(),
                    },
                )
                row["physical_offsets"].add(resource["file_offset"])
                row["map_ids"].add(entry["map_id"])
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
                    "schema": "map-resource-import-v1",
                    "source_catalog": (
                        "artifacts/map-canvases-v1/manifest.json"
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

    def test_catalog_has_166_content_resources_and_217_physical_slots(self):
        self.assertEqual(166, len(self.resources))
        self.assertEqual(
            217,
            sum(len(row["physical_offsets"]) for row in self.resources.values()),
        )

    def test_noop_all_resources_emits_no_patches(self):
        from tools.import_map_resources import resolve_map_resource_patches

        edits = []
        for row in self.resources.values():
            source = ROOT / "artifacts/map-canvases-v1" / row["source_file"]
            edits.append(self._edit(row, source, edit_id=row["sha256"]))
        self.assertEqual(
            [],
            resolve_map_resource_patches(
                ROOT,
                self._write_spec(edits),
                rom=self.base,
            ),
        )

    def test_edit_updates_every_physical_alias_with_fixed_length_guards(self):
        from tools.import_map_resources import resolve_map_resource_patches

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "collision_grid"
            and value["sha256"] == "b5519b9ecc7124c0da001af9f3901f2a1ef2bbd94799366474a12b016db66c91"
            and len(value["physical_offsets"]) > 1
        )
        content = bytearray(
            (
                ROOT
                / "artifacts/map-canvases-v1"
                / row["source_file"]
            ).read_bytes()
        )
        content[0] ^= 1
        patches = resolve_map_resource_patches(
            ROOT,
            self._write_spec(
                [self._edit(row, self._write_source(row, bytes(content)))]
            ),
            rom=self.base,
        )

        self.assertEqual(
            sorted(row["physical_offsets"]),
            [item["offset"] for item in patches],
        )
        self.assertEqual(
            sorted(row["map_ids"]),
            sorted(
                {
                    alias["map_id"]
                    for item in patches
                    for alias in item["logical_aliases"]
                }
            ),
        )
        for item in patches:
            self.assertEqual("bytes", item["type"])
            self.assertEqual("map_resource", item["asset_type"])
            self.assertEqual(row["role"], item["resource_type"])
            self.assertEqual(row["sha256"], item["resource_sha256"])
            self.assertEqual(
                len(bytes.fromhex(item["before_hex"])),
                len(bytes.fromhex(item["after_hex"])),
            )
            patched = bytearray(self.base)
            offset = item["offset"]
            after = bytes.fromhex(item["after_hex"])
            patched[offset : offset + len(after)] = after
            self.assertEqual(
                bytes(content),
                lz77_decompress(bytes(patched), offset),
            )

    def test_rejects_atomic_alias_overflow_stale_provenance_and_duplicates(self):
        from tools.import_map_resources import resolve_map_resource_patches

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "bg_palette"
        )
        noisy = bytes((index * 73 + 19) & 0xFF for index in range(
            row["decompressed_size"]
        ))
        spec = self._write_spec(
            [self._edit(row, self._write_source(row, noisy))]
        )
        with self.assertRaisesRegex(ValueError, "does not fit every physical"):
            resolve_map_resource_patches(ROOT, spec, rom=self.base)

        good = ROOT / "artifacts/map-canvases-v1" / row["source_file"]
        stale = self._edit(row, good)
        stale["expected"]["physical_offsets"] = [0]
        with self.assertRaisesRegex(ValueError, "physical offset provenance"):
            resolve_map_resource_patches(
                ROOT,
                self._write_spec([stale]),
                rom=self.base,
            )

        edit = self._edit(row, good)
        with self.assertRaisesRegex(ValueError, "duplicate map resource"):
            resolve_map_resource_patches(
                ROOT,
                self._write_spec([edit, dict(edit, id="duplicate")]),
                rom=self.base,
            )

    def test_rejects_layout_indices_outside_linked_metatile_resources(self):
        from tools.import_map_resources import resolve_map_resource_patches

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "primary_layout"
        )
        content = bytearray(
            (
                ROOT
                / "artifacts/map-canvases-v1"
                / row["source_file"]
            ).read_bytes()
        )
        content[0:2] = b"\xFF\xFF"
        with self.assertRaisesRegex(ValueError, "metatile index"):
            resolve_map_resource_patches(
                ROOT,
                self._write_spec(
                    [self._edit(row, self._write_source(row, bytes(content)))]
                ),
                rom=self.base,
            )

    def test_rejects_metatile_indices_outside_linked_tiles_and_palettes(self):
        from tools.import_map_resources import resolve_map_resource_patches

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "metatile_definitions"
        )
        original = bytearray(
            (
                ROOT
                / "artifacts/map-canvases-v1"
                / row["source_file"]
            ).read_bytes()
        )
        original_value = int.from_bytes(original[0:2], "little")
        invalid_cases = (
            (
                "tile index",
                (original_value & 0xFC00) | 0x03FF,
            ),
            (
                "palette bank",
                (original_value & 0x0FFF) | 0xF000,
            ),
        )
        for expected_error, replacement_value in invalid_cases:
            with self.subTest(expected_error=expected_error):
                content = bytearray(original)
                content[0:2] = replacement_value.to_bytes(2, "little")
                with self.assertRaisesRegex(ValueError, expected_error):
                    resolve_map_resource_patches(
                        ROOT,
                        self._write_spec(
                            [
                                self._edit(
                                    row,
                                    self._write_source(row, bytes(content)),
                                )
                            ]
                        ),
                        rom=self.base,
                    )

    def test_build_manifest_dispatch_applies_map_resource_edit(self):
        import tools.build_mod as build_mod

        from tools.import_map_resources import resolve_map_resource_patches

        row = next(
            value
            for value in self.resources.values()
            if value["role"] == "collision_grid"
            and value["sha256"] == "b5519b9ecc7124c0da001af9f3901f2a1ef2bbd94799366474a12b016db66c91"
        )
        content = bytearray(
            (
                ROOT
                / "artifacts/map-canvases-v1"
                / row["source_file"]
            ).read_bytes()
        )
        content[0] ^= 1

        temp_root = self.temp / "project"
        (temp_root / "rom").mkdir(parents=True)
        (temp_root / "artifacts/map-canvases-v1").mkdir(parents=True)
        (temp_root / "sequel/content/map-resources").mkdir(parents=True)
        (temp_root / "sequel/patches").mkdir(parents=True)
        (temp_root / "rom/base.gba").write_bytes(self.base)
        (temp_root / "artifacts/map-canvases-v1/manifest.json").write_bytes(
            CATALOG_PATH.read_bytes()
        )
        local_source = (
            temp_root / "sequel/content/map-resources/edited.bin"
        )
        local_source.write_bytes(content)
        local_spec = temp_root / "sequel/content/map-resources/edit.json"
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
                            "id": "map-resource-import",
                            "type": "map_resource",
                            "spec": (
                                "sequel/content/map-resources/edit.json"
                            ),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "map-resource-build-test",
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

        expected_patches = resolve_map_resource_patches(
            temp_root,
            local_spec,
            rom=self.base,
        )
        with patch.object(build_mod, "ROOT", temp_root):
            report = build_mod.build(project_path)

        output = (temp_root / "build/output.gba").read_bytes()
        self.assertEqual(
            self.base[0x53D910 : 0x53D910 + 47 * 32],
            output[0x53D910 : 0x53D910 + 47 * 32],
        )
        for expected in expected_patches:
            self.assertEqual(
                bytes(content),
                lz77_decompress(output, expected["offset"]),
            )
        self.assertEqual(
            len(expected_patches),
            sum(
                item.get("asset_type") == "map_resource"
                for item in report["applied_patches"]
            ),
        )

    def test_writeback_audit_closes_complete_denominator_and_records_overflow(self):
        from tools.export_map_resource_writeback_audit import (
            export_map_resource_writeback_audit,
        )

        output = self.temp / "map-resource-writeback-v1"
        payload = export_map_resource_writeback_audit(ROOT, output)
        self.assertEqual(166, payload["summary"]["content_resource_count"])
        self.assertEqual(217, payload["summary"]["physical_slot_count"])
        self.assertEqual(249, payload["summary"]["logical_reference_count"])
        self.assertEqual(
            166,
            payload["summary"]["original_roundtrip_fit_content_count"],
        )
        self.assertEqual(
            217,
            payload["summary"]["original_roundtrip_fit_slot_count"],
        )
        self.assertEqual(
            70,
            payload["summary"]["mutation_fit_all_alias_content_count"],
        )
        self.assertEqual(
            96,
            payload["summary"]["mutation_overflow_content_count"],
        )
        self.assertEqual(91, payload["summary"]["mutation_fit_slot_count"])
        self.assertEqual(126, payload["summary"]["mutation_overflow_slot_count"])
        self.assertTrue(
            payload["scope"]["linked_resource_index_validation_complete"]
        )
        self.assertFalse(payload["scope"]["arbitrary_edit_capacity_complete"])
        self.assertFalse(payload["scope"]["resource_relocation_complete"])
        self.assertFalse(payload["scope"]["runtime_pixel_equivalence"])

    def test_independent_writeback_audit_verifier_rejects_resigned_tamper(self):
        from tools.export_map_resource_writeback_audit import (
            export_map_resource_writeback_audit,
        )
        from tools.verify_map_resource_writeback_audit import (
            verify_map_resource_writeback_audit,
        )

        output = self.temp / "map-resource-writeback-v1"
        export_map_resource_writeback_audit(ROOT, output)
        report = verify_map_resource_writeback_audit(ROOT, output)
        self.assertTrue(report["verified"], report["errors"])

        payload_path = output / "map-resource-writeback.json"
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
        manifest["files"]["map-resource-writeback.json"] = digest
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = verify_map_resource_writeback_audit(ROOT, output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("resource records mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
