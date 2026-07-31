from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class ImportResidualWramDerivedTilemapRelocationsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        from tools.import_residual_wram_derived_tilemap_relocations import (
            catalog_residual_wram_derived_tilemaps,
        )

        self.catalog = catalog_residual_wram_derived_tilemaps(ROOT, self.base)
        self.files = {}
        for record in self.catalog:
            path = self.temp / f"{record['source_pointer']:08x}.bin"
            path.write_bytes(record["decoded"])
            self.files[record["source_pointer"]] = path

    def tearDown(self):
        self.temporary.cleanup()

    def _spec(self, replacements=None):
        from tools.import_residual_wram_derived_tilemap_relocations import (
            ABI_PATH,
            ABI_SHA256,
        )

        registry = ROOT / "sequel/image-resource-regions.json"
        files = self.files if replacements is None else replacements
        path = self.temp / "relocation.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "residual-wram-derived-tilemap-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "abi_artifact": ABI_PATH.as_posix(),
                    "abi_sha256": ABI_SHA256,
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry.read_bytes()
                    ).hexdigest(),
                    "region": "residual-wram-derived-tilemaps",
                    "region_owner": "residual_wram_derived_tilemaps",
                    "resources": [
                        {
                            "source_pointer": f"0x{pointer:08X}",
                            "tilemap_file": str(files[pointer]),
                        }
                        for pointer in sorted(files)
                    ],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_four_sources_and_transfer_contracts(self):
        self.assertEqual(
            [0x083F2108, 0x084634B8, 0x0846356C, 0x084635D8],
            [row["source_pointer"] for row in self.catalog],
        )
        self.assertEqual(
            [
                ("direct_cpu_crop_tilemap", 40, 10, [10], (1, 16)),
                ("transformed_strided_queue_tilemap", 12, 12, [12], (0, 54)),
                ("transformed_strided_queue_tilemap", 12, 12, [13], (0, 75)),
                ("transformed_strided_queue_tilemap", 12, 12, [13], (0, 95)),
            ],
            [
                (
                    row["classification"],
                    row["width_entries"],
                    row["height_entries"],
                    row["palette_banks"],
                    row["tile_index_range"],
                )
                for row in self.catalog
            ],
        )

    def test_registry_reserves_literal_safe_two_kib(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        current = regions.require(
            "residual-wram-derived-tilemaps",
            "residual_wram_derived_tilemaps",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )
        self.assertEqual((0xBC1400, 0xBC1C00), (current.start, current.end))
        self.assertEqual((0xBC1C00, 0xC00000), (future.start, future.end))

    def test_preservation_relocates_all_payloads_and_roots(self):
        from tools.build_mod import apply_patch
        from tools.import_residual_wram_derived_tilemap_relocations import (
            resolve_residual_wram_derived_tilemap_relocation_patches,
        )
        from tools.patch_safety import PatchSafetyGate

        patches = resolve_residual_wram_derived_tilemap_relocation_patches(
            ROOT,
            self._spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        redirects = [row for row in patches if "allocation" not in row]
        self.assertEqual(4, len(allocations))
        self.assertEqual(4, len(redirects))
        self.assertEqual(
            [0xBC1400, 0xBC148C, 0xBC1540, 0xBC15AC],
            [row["offset"] for row in allocations],
        )
        self.assertEqual(
            [0x08BD60, 0x090BDC, 0x090DDC, 0x090DE8],
            [row["offset"] for row in redirects],
        )

        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        output = bytearray(self.layout.expanded_base())
        gate = PatchSafetyGate(
            self.base,
            layout=self.layout,
            image_regions=regions,
        )
        for patch in patches:
            apply_patch(output, patch, gate=gate)
        for allocation in allocations:
            self.assertEqual(
                self.files[allocation["source_pointer"]].read_bytes(),
                lz77_decompress(output, allocation["offset"]),
            )

    def test_valid_edits_pass_and_invalid_tilemap_contracts_fail(self):
        from tools.import_residual_wram_derived_tilemap_relocations import (
            resolve_residual_wram_derived_tilemap_relocation_patches,
        )

        edited = {}
        for row in self.catalog:
            values = list(
                struct.unpack(
                    f"<{row['entry_count']}H",
                    row["decoded"],
                )
            )
            values[0] = (
                row["palette_banks"][0] << 12
                | row["tile_index_range"][1]
                | 0x0C00
            )
            path = self.temp / f"edited-{row['source_pointer']:08x}.bin"
            path.write_bytes(struct.pack(f"<{len(values)}H", *values))
            edited[row["source_pointer"]] = path
        patches = resolve_residual_wram_derived_tilemap_relocation_patches(
            ROOT,
            self._spec(edited),
            rom=self.base,
            layout=self.layout,
        )
        self.assertEqual(4, len([row for row in patches if "allocation" in row]))

        pointer = self.catalog[0]["source_pointer"]
        original = self.files[pointer].read_bytes()
        invalid = {
            "size": original[:-2],
            "tile": struct.pack("<H", 17) + original[2:],
            "palette": struct.pack("<H", 0xB001) + original[2:],
        }
        for name, data in invalid.items():
            path = self.temp / f"invalid-{name}.bin"
            path.write_bytes(data)
            replacements = dict(self.files)
            replacements[pointer] = path
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_residual_wram_derived_tilemap_relocation_patches(
                    ROOT,
                    self._spec(replacements),
                    rom=self.base,
                    layout=self.layout,
                )

    def test_literal_worst_case_fits_and_overflow_fails_closed(self):
        from tools.gba_image_export import encode_gba_lz77
        from tools.import_residual_wram_derived_tilemap_relocations import (
            resolve_residual_wram_derived_tilemap_relocation_patches,
        )

        cursor = 0
        for row in self.catalog:
            cursor = (cursor + 3) & ~3
            cursor += (
                4
                + row["decoded_size"]
                + (row["decoded_size"] + 7) // 8
            )
        self.assertEqual(1888, cursor)
        self.assertLessEqual(cursor, 0x800)
        with mock.patch(
            "tools.import_residual_wram_derived_tilemap_relocations."
            "encode_gba_lz77",
            side_effect=lambda data: encode_gba_lz77(data) + bytes(0x801),
        ), self.assertRaisesRegex(ValueError, "registered region"):
            resolve_residual_wram_derived_tilemap_relocation_patches(
                ROOT,
                self._spec(),
                rom=self.base,
                layout=self.layout,
            )

    def test_automated_manifest_and_unified_build_accept_batch_type(self):
        from tools import automated_test, build_mod
        from tools.import_residual_wram_derived_tilemap_relocations import (
            ABI_PATH,
        )

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "residual-wram-derived-tilemaps",
                        "type": "residual_wram_derived_tilemap_relocation",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)
        self.assertEqual([], runner.summary()["failures"])

        build_root = self.temp / "build-root"
        for relative in (
            "rom",
            "sequel/patches",
            "sequel/content/residual-wram-derived-tilemaps",
            ABI_PATH.parent,
        ):
            (build_root / relative).mkdir(parents=True, exist_ok=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        for relative in (
            "sequel/rom-layout.json",
            "sequel/image-resource-regions.json",
            ABI_PATH,
        ):
            destination = build_root / relative
            destination.write_bytes((ROOT / relative).read_bytes())
        replacements = {}
        for pointer, source in self.files.items():
            destination = (
                build_root
                / "sequel/content/residual-wram-derived-tilemaps"
                / source.name
            )
            destination.write_bytes(source.read_bytes())
            replacements[pointer] = destination
        spec = json.loads(self._spec(replacements).read_text())
        spec_path = (
            build_root
            / "sequel/content/residual-wram-derived-tilemaps/relocation.json"
        )
        spec_path.write_text(json.dumps(spec))
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "residual-wram-derived-tilemaps",
                            "type": (
                                "residual_wram_derived_tilemap_relocation"
                            ),
                            "spec": (
                                "sequel/content/"
                                "residual-wram-derived-tilemaps/"
                                "relocation.json"
                            ),
                        }
                    ],
                }
            )
        )
        project = build_root / "sequel/project.json"
        project.write_text(
            json.dumps(
                {
                    "project_id": "residual-wram-derived-tilemap-test",
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
            )
        )
        with mock.patch.object(build_mod, "ROOT", build_root):
            report = build_mod.build(project)
        self.assertEqual(0x1000000, report["output_rom"]["size"])
        self.assertEqual(8, len(report["applied_patches"]))


if __name__ == "__main__":
    unittest.main()
