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


class ImportResidualTextBgTilemapRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        from tools.import_residual_text_bg_tilemap_relocations import (
            catalog_residual_text_bg_tilemap,
        )

        self.catalog = catalog_residual_text_bg_tilemap(ROOT, self.base)
        self.tilemap = self.temp / "tilemap.bin"
        self.tilemap.write_bytes(self.catalog["decoded"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_spec(
        self,
        *,
        tilemap_file: Path | None = None,
        name: str = "relocation.json",
    ) -> Path:
        from tools.import_residual_text_bg_tilemap_relocations import (
            INVENTORY_PATH,
        )

        registry = ROOT / "sequel/image-resource-regions.json"
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "residual-text-bg-tilemap-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "inventory": INVENTORY_PATH.as_posix(),
                    "inventory_sha256": hashlib.sha256(
                        (ROOT / INVENTORY_PATH).read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry.read_bytes()
                    ).hexdigest(),
                    "region": "residual-text-bg-tilemap",
                    "region_owner": "residual_text_bg_tilemap",
                    "source_pointer": "0x08349368",
                    "tilemap_file": str(tilemap_file or self.tilemap),
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_the_single_text_bg_tilemap_and_root(self):
        catalog = self.catalog

        self.assertEqual(0x08349368, catalog["source_pointer"])
        self.assertEqual(178, catalog["compressed_size"])
        self.assertEqual(0x0834941A, catalog["compressed_end_pointer"])
        self.assertEqual(1280, catalog["decoded_size"])
        self.assertEqual([0x08B464], catalog["pointer_offsets"])
        self.assertEqual([0x0808B348], catalog["literal_load_users"])
        self.assertEqual("0x06001000", catalog["destination"])
        self.assertEqual(640, catalog["entry_count"])
        self.assertEqual((0, 5), catalog["tile_index_range"])
        self.assertEqual([1], catalog["palette_banks"])
        self.assertEqual(0, catalog["horizontal_flip_count"])
        self.assertEqual(12, catalog["vertical_flip_count"])
        self.assertEqual(
            "92015fd81bfad3066111a9d094a367a29d4d7e3b7cfeef7489cb36414611d963",
            catalog["code_window_sha256"],
        )
        self.assertEqual(
            {
                0x1000: 516,
                0x1001: 1,
                0x1002: 10,
                0x1003: 1,
                0x1004: 4,
                0x1005: 96,
                0x1801: 1,
                0x1802: 10,
                0x1803: 1,
            },
            catalog["word_histogram"],
        )
        self.assertEqual(
            "0876b9165e63106e30681dd9ca5831d629ba8903a9f0d05fd5cbf8f1088e920c",
            hashlib.sha256(catalog["decoded"]).hexdigest(),
        )

    def test_registry_reserves_two_kib_after_direct_palettes(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        tilemap = regions.require(
            "residual-text-bg-tilemap",
            "residual_text_bg_tilemap",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xBC0400, 0xBC0C00), (tilemap.start, tilemap.end))
        self.assertEqual((0xBC0C00, 0xC00000), (future.start, future.end))

    def test_preservation_relocates_payload_and_only_root_into_full_rom(self):
        from tools.build_mod import apply_patch
        from tools.import_residual_text_bg_tilemap_relocations import (
            resolve_residual_text_bg_tilemap_relocation_patches,
        )
        from tools.patch_safety import PatchSafetyGate

        patches = resolve_residual_text_bg_tilemap_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        self.assertEqual(2, len(patches))
        allocation = next(row for row in patches if "allocation" in row)
        redirect = next(row for row in patches if "allocation" not in row)
        self.assertEqual(0xBC0400, allocation["offset"])
        self.assertEqual(0x08BC0400, allocation["new_pointer"])
        self.assertEqual(0x08B464, redirect["offset"])
        self.assertEqual(allocation["new_pointer"], redirect["new_pointer"])

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
        self.assertEqual(
            self.tilemap.read_bytes(),
            lz77_decompress(output, allocation["offset"]),
        )

    def test_valid_tile_and_flip_edit_is_accepted(self):
        from tools.import_residual_text_bg_tilemap_relocations import (
            resolve_residual_text_bg_tilemap_relocation_patches,
        )

        entries = list(struct.unpack("<640H", self.tilemap.read_bytes()))
        entries[0] = 0x1000 | 5 | (1 << 10) | (1 << 11)
        self.tilemap.write_bytes(struct.pack("<640H", *entries))

        patches = resolve_residual_text_bg_tilemap_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocation = next(row for row in patches if "allocation" in row)
        self.assertEqual(640, allocation["entry_count"])
        self.assertEqual([1], allocation["palette_banks"])
        self.assertEqual(1, allocation["horizontal_flip_count"])

    def test_wrong_size_tile_index_palette_bank_and_overflow_fail(self):
        from tools.gba_image_export import encode_gba_lz77
        from tools.import_residual_text_bg_tilemap_relocations import (
            resolve_residual_text_bg_tilemap_relocation_patches,
        )

        original = self.tilemap.read_bytes()
        invalid: dict[str, bytes] = {
            "size": original[:-2],
            "tile": struct.pack("<H", 6) + original[2:],
            "palette": struct.pack("<H", 0x2000) + original[2:],
        }
        for name, data in invalid.items():
            path = self.temp / f"{name}.bin"
            path.write_bytes(data)
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_residual_text_bg_tilemap_relocation_patches(
                    ROOT,
                    self._write_spec(tilemap_file=path, name=f"{name}.json"),
                    rom=self.base,
                    layout=self.layout,
                )

        with mock.patch(
            "tools.import_residual_text_bg_tilemap_relocations.encode_gba_lz77",
            side_effect=lambda data: encode_gba_lz77(data) + bytes(0x801),
        ), self.assertRaisesRegex(ValueError, "registered region"):
            resolve_residual_text_bg_tilemap_relocation_patches(
                ROOT,
                self._write_spec(),
                rom=self.base,
                layout=self.layout,
            )

    def test_automated_manifest_and_unified_build_accept_relocation_type(self):
        from tools import automated_test, build_mod
        from tools.import_residual_text_bg_tilemap_relocations import (
            INVENTORY_PATH,
        )

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "residual-text-bg-tilemap",
                        "type": "residual_text_bg_tilemap_relocation",
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
            "sequel/content/residual-text-bg-tilemap",
            INVENTORY_PATH.parent,
        ):
            (build_root / relative).mkdir(parents=True, exist_ok=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        for relative in (
            "sequel/rom-layout.json",
            "sequel/image-resource-regions.json",
            INVENTORY_PATH,
        ):
            destination = build_root / relative
            destination.write_bytes((ROOT / relative).read_bytes())
        tilemap = (
            build_root
            / "sequel/content/residual-text-bg-tilemap/tilemap.bin"
        )
        tilemap.write_bytes(self.tilemap.read_bytes())
        spec = json.loads(self._write_spec().read_text())
        spec["tilemap_file"] = str(tilemap)
        spec_path = (
            build_root
            / "sequel/content/residual-text-bg-tilemap/relocation.json"
        )
        spec_path.write_text(json.dumps(spec))
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "residual-text-bg-tilemap",
                            "type": "residual_text_bg_tilemap_relocation",
                            "spec": (
                                "sequel/content/residual-text-bg-tilemap/"
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
                    "project_id": "residual-text-bg-tilemap-test",
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
        self.assertEqual(2, len(report["applied_patches"]))


if __name__ == "__main__":
    unittest.main()
