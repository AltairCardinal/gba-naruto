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
ROM_BASE = 0x08000000


class ImportResidualWramTilemapRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        from tools.import_residual_wram_tilemap_relocations import (
            catalog_residual_wram_tilemaps,
        )

        self.catalog = catalog_residual_wram_tilemaps(ROOT, self.base)
        self.tilemaps: dict[int, Path] = {}
        for record in self.catalog:
            path = self.temp / f"{record['source_pointer']:08x}.bin"
            path.write_bytes(record["decoded"])
            self.tilemaps[record["source_pointer"]] = path

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_spec(
        self,
        *,
        replacements: dict[int, Path] | None = None,
        name: str = "relocation.json",
    ) -> Path:
        from tools.import_residual_wram_tilemap_relocations import (
            ABI_PATH,
            ABI_SHA256,
        )

        registry = ROOT / "sequel/image-resource-regions.json"
        paths = self.tilemaps if replacements is None else replacements
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "residual-wram-tilemap-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "abi_artifact": ABI_PATH.as_posix(),
                    "abi_sha256": ABI_SHA256,
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry.read_bytes()
                    ).hexdigest(),
                    "region": "residual-wram-tilemaps",
                    "region_owner": "residual_wram_tilemaps",
                    "resources": [
                        {
                            "source_pointer": f"0x{pointer:08X}",
                            "tilemap_file": str(paths[pointer]),
                        }
                        for pointer in sorted(paths)
                    ],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_three_sources_roots_and_queue_contracts(self):
        self.assertEqual(
            [0x0834928C, 0x083F1C98, 0x085B67E0],
            [row["source_pointer"] for row in self.catalog],
        )
        self.assertEqual(
            [
                (600, [0x08AEE0], 15, 20, [1], (6, 67), "0x0600001E"),
                (576, [0x08BD38], 24, 12, [8], (0, 267), "0x0600F810"),
                (138, [0x08BD48], 23, 3, [9], (0, 86), "0x0600FC4E"),
            ],
            [
                (
                    row["decoded_size"],
                    row["pointer_offsets"],
                    row["width_entries"],
                    row["height_entries"],
                    row["palette_banks"],
                    row["tile_index_range"],
                    row["vram_destination"],
                )
                for row in self.catalog
            ],
        )

    def test_registry_reserves_two_kib_and_preserves_future_capacity(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        current = regions.require(
            "residual-wram-tilemaps",
            "residual_wram_tilemaps",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )
        self.assertEqual((0xBC0C00, 0xBC1400), (current.start, current.end))
        self.assertEqual((0xBC1C00, 0xC00000), (future.start, future.end))

    def test_preservation_relocates_all_payloads_and_all_roots(self):
        from tools.build_mod import apply_patch
        from tools.import_residual_wram_tilemap_relocations import (
            resolve_residual_wram_tilemap_relocation_patches,
        )
        from tools.patch_safety import PatchSafetyGate

        patches = resolve_residual_wram_tilemap_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        redirects = [row for row in patches if "allocation" not in row]
        self.assertEqual(3, len(allocations))
        self.assertEqual(3, len(redirects))
        self.assertEqual(
            [0xBC0C00, 0xBC0CDC, 0xBC0EA4],
            [row["offset"] for row in allocations],
        )
        self.assertEqual(
            [0x08AEE0, 0x08BD38, 0x08BD48],
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
        self.assertEqual(0x1000000, len(output))
        for allocation in allocations:
            self.assertEqual(
                self.tilemaps[allocation["source_pointer"]].read_bytes(),
                lz77_decompress(output, allocation["offset"]),
            )

    def test_valid_edits_are_accepted_and_invalid_geometry_is_rejected(self):
        from tools.import_residual_wram_tilemap_relocations import (
            resolve_residual_wram_tilemap_relocation_patches,
        )

        edited: dict[int, Path] = {}
        for record in self.catalog:
            pointer = record["source_pointer"]
            values = list(
                struct.unpack(
                    f"<{record['entry_count']}H",
                    self.tilemaps[pointer].read_bytes(),
                )
            )
            values[0] = (
                record["palette_banks"][0] << 12
                | record["tile_index_range"][1]
                | (1 << 10)
                | (1 << 11)
            )
            path = self.temp / f"edited-{pointer:08x}.bin"
            path.write_bytes(struct.pack(f"<{len(values)}H", *values))
            edited[pointer] = path
        patches = resolve_residual_wram_tilemap_relocation_patches(
            ROOT,
            self._write_spec(replacements=edited, name="edited.json"),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        self.assertEqual(3, len(allocations))
        self.assertTrue(
            all(row["horizontal_flip_count"] >= 1 for row in allocations)
        )
        self.assertTrue(
            all(row["vertical_flip_count"] >= 1 for row in allocations)
        )

        source = self.catalog[0]["source_pointer"]
        original = self.tilemaps[source].read_bytes()
        invalid = {
            "size": original[:-2],
            "tile": struct.pack("<H", 68) + original[2:],
            "palette": struct.pack("<H", 0x2006) + original[2:],
        }
        for name, data in invalid.items():
            candidate = self.temp / f"invalid-{name}.bin"
            candidate.write_bytes(data)
            replacements = dict(self.tilemaps)
            replacements[source] = candidate
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_residual_wram_tilemap_relocation_patches(
                    ROOT,
                    self._write_spec(
                        replacements=replacements,
                        name=f"invalid-{name}.json",
                    ),
                    rom=self.base,
                    layout=self.layout,
                )

    def test_literal_worst_case_fits_and_overflow_fails_closed(self):
        from tools.gba_image_export import encode_gba_lz77
        from tools.import_residual_wram_tilemap_relocations import (
            resolve_residual_wram_tilemap_relocation_patches,
        )

        literal_bound = sum(
            4 + row["decoded_size"] + (row["decoded_size"] + 7) // 8
            for row in self.catalog
        )
        self.assertEqual(1491, literal_bound)
        cursor = 0
        for row in self.catalog:
            cursor = (cursor + 3) & ~3
            cursor += (
                4
                + row["decoded_size"]
                + (row["decoded_size"] + 7) // 8
            )
        self.assertEqual(1492, cursor)
        self.assertLessEqual(cursor, 0x800)

        with mock.patch(
            "tools.import_residual_wram_tilemap_relocations.encode_gba_lz77",
            side_effect=lambda data: encode_gba_lz77(data) + bytes(0x801),
        ), self.assertRaisesRegex(ValueError, "registered region"):
            resolve_residual_wram_tilemap_relocation_patches(
                ROOT,
                self._write_spec(),
                rom=self.base,
                layout=self.layout,
            )

    def test_automated_manifest_and_unified_build_accept_batch_type(self):
        from tools import automated_test, build_mod
        from tools.import_residual_wram_tilemap_relocations import ABI_PATH

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "residual-wram-tilemaps",
                        "type": "residual_wram_tilemap_relocation",
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
            "sequel/content/residual-wram-tilemaps",
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
        replacement_paths: dict[int, Path] = {}
        for pointer, source in self.tilemaps.items():
            destination = (
                build_root
                / "sequel/content/residual-wram-tilemaps"
                / source.name
            )
            destination.write_bytes(source.read_bytes())
            replacement_paths[pointer] = destination
        spec = json.loads(
            self._write_spec(replacements=replacement_paths).read_text()
        )
        spec_path = (
            build_root
            / "sequel/content/residual-wram-tilemaps/relocation.json"
        )
        spec_path.write_text(json.dumps(spec))
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "residual-wram-tilemaps",
                            "type": "residual_wram_tilemap_relocation",
                            "spec": (
                                "sequel/content/residual-wram-tilemaps/"
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
                    "project_id": "residual-wram-tilemap-test",
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
        self.assertEqual(6, len(report["applied_patches"]))


if __name__ == "__main__":
    unittest.main()
