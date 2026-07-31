from __future__ import annotations

import hashlib
import json
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


class ImportDirectImagePaletteRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        from tools.import_direct_image_palette_relocations import (
            catalog_direct_image_palettes,
        )

        self.catalog = catalog_direct_image_palettes(ROOT, self.base)
        self.resources = []
        for row in self.catalog["resources"]:
            source_pointer = row["source_pointer"]
            palette = self.temp / f"{source_pointer:08x}.bgr555.bin"
            if row["storage_kind"] == "lz77":
                raw = lz77_decompress(
                    self.base,
                    source_pointer - ROM_BASE,
                )
            else:
                offset = source_pointer - ROM_BASE
                raw = self.base[offset : offset + row["decoded_size"]]
            palette.write_bytes(raw)
            self.resources.append(
                {
                    "source_pointer": f"0x{source_pointer:08X}",
                    "palette_file": str(palette),
                }
            )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_spec(
        self,
        *,
        resources: list[dict] | None = None,
        name: str = "relocation.json",
    ) -> Path:
        from tools.import_direct_image_palette_relocations import (
            DIRECT_INVENTORY_PATH,
            GRAPHICS_CATALOG_PATH,
            LZ_INVENTORY_PATH,
        )

        registry = ROOT / "sequel/image-resource-regions.json"
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "direct-image-palette-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "lz77_inventory": LZ_INVENTORY_PATH.as_posix(),
                    "lz77_inventory_sha256": hashlib.sha256(
                        (ROOT / LZ_INVENTORY_PATH).read_bytes()
                    ).hexdigest(),
                    "graphics_catalog": GRAPHICS_CATALOG_PATH.as_posix(),
                    "graphics_catalog_sha256": hashlib.sha256(
                        (ROOT / GRAPHICS_CATALOG_PATH).read_bytes()
                    ).hexdigest(),
                    "direct_inventory": DIRECT_INVENTORY_PATH.as_posix(),
                    "direct_inventory_sha256": hashlib.sha256(
                        (ROOT / DIRECT_INVENTORY_PATH).read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry.read_bytes()
                    ).hexdigest(),
                    "region": "direct-image-palettes",
                    "region_owner": "direct_image_palettes",
                    "resources": (
                        resources if resources is not None else self.resources
                    ),
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_all_logical_sources_physical_spans_and_roots(self):
        from tools.import_direct_image_palette_relocations import (
            catalog_direct_image_palettes,
        )

        catalog = catalog_direct_image_palettes(ROOT, self.base)

        self.assertEqual(18, catalog["logical_source_count"])
        self.assertEqual(17, catalog["physical_resource_count"])
        self.assertEqual(29, catalog["pointer_reference_count"])
        self.assertEqual(3, catalog["lz77_resource_count"])
        self.assertEqual(14, catalog["raw_resource_count"])
        self.assertEqual(96, catalog["lz77_decoded_size"])
        self.assertEqual(672, catalog["raw_physical_size"])
        self.assertEqual(72, catalog["overlap_locked_size"])
        self.assertEqual(2, catalog["unresolved_graphics_palette_count"])
        self.assertEqual([], catalog["unexpected_pointer_offsets"])

        parent = next(
            row
            for row in catalog["resources"]
            if row["source_pointer"] == 0x08405FF0
        )
        self.assertEqual(256, parent["decoded_size"])
        self.assertEqual(
            {
                "source_pointer": 0x08406010,
                "parent_offset": 0x20,
                "pointer_offsets": [0x08C2A4],
            },
            parent["range_aliases"][0],
        )
        self.assertEqual(
            {
                "offset": 0xB8,
                "size": 72,
                "overlap_pointer": 0x084060A8,
            },
            parent["locked_ranges"][0],
        )

    def test_registry_reserves_direct_image_palette_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        palettes = regions.require(
            "direct-image-palettes",
            "direct_image_palettes",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xBC0000, 0xBC0400), (palettes.start, palettes.end))
        self.assertEqual((0xBC0400, 0xC00000), (future.start, future.end))

    def test_full_preservation_relocates_seventeen_payloads_and_all_roots(self):
        from tools.build_mod import apply_patch
        from tools.import_direct_image_palette_relocations import (
            resolve_direct_image_palette_relocation_patches,
        )
        from tools.patch_safety import PatchSafetyGate

        patches = resolve_direct_image_palette_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        redirects = [
            row
            for row in patches
            if row.get("asset_type") == "direct_image_palette_pointer"
        ]
        self.assertEqual(17, len(allocations))
        self.assertEqual(29, len(redirects))

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
            pointer = allocation["new_pointer"]
            self.assertTrue(0x08BC0000 <= pointer < 0x08BC0400)
            expected = Path(allocation["source_file"]).read_bytes()
            if allocation["storage_kind"] == "lz77":
                actual = lz77_decompress(output, pointer - ROM_BASE)
            else:
                start = pointer - ROM_BASE
                actual = output[start : start + allocation["decoded_size"]]
            self.assertEqual(expected, actual)

        parent = next(
            row
            for row in allocations
            if row["source_pointer"] == 0x08405FF0
        )
        alias = next(
            row
            for row in redirects
            if row["source_pointer"] == 0x08406010
        )
        self.assertEqual(parent["new_pointer"] + 0x20, alias["new_pointer"])

    def test_all_editable_physical_palettes_and_range_alias_can_change(self):
        from tools.import_direct_image_palette_relocations import (
            resolve_direct_image_palette_relocation_patches,
        )

        for index, resource in enumerate(self.resources):
            path = Path(resource["palette_file"])
            raw = bytearray(path.read_bytes())
            raw[2] ^= (index + 1) & 0xFF
            if int(resource["source_pointer"], 16) == 0x08405FF0:
                raw[0x22] ^= 0x5A
            path.write_bytes(raw)

        patches = resolve_direct_image_palette_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        self.assertEqual(17, len(allocations))
        self.assertEqual(
            {
                hashlib.sha256(
                    Path(row["palette_file"]).read_bytes()
                ).hexdigest()
                for row in self.resources
            },
            {row["replacement_sha256"] for row in allocations},
        )

    def test_cross_domain_overlap_tail_is_locked(self):
        from tools.import_direct_image_palette_relocations import (
            resolve_direct_image_palette_relocation_patches,
        )

        parent = next(
            row
            for row in self.resources
            if int(row["source_pointer"], 16) == 0x08405FF0
        )
        path = Path(parent["palette_file"])
        raw = bytearray(path.read_bytes())
        raw[0xB8] ^= 0xFF
        path.write_bytes(raw)

        with self.assertRaisesRegex(ValueError, "overlap-locked"):
            resolve_direct_image_palette_relocation_patches(
                ROOT,
                self._write_spec(),
                rom=self.base,
                layout=self.layout,
            )

    def test_wrong_size_missing_duplicate_and_unknown_resources_fail(self):
        from tools.import_direct_image_palette_relocations import (
            resolve_direct_image_palette_relocation_patches,
        )

        cases: dict[str, list[dict]] = {}
        wrong_size = json.loads(json.dumps(self.resources))
        wrong_path = self.temp / "wrong-size.bgr555.bin"
        wrong_path.write_bytes(
            Path(wrong_size[0]["palette_file"]).read_bytes() + b"\0\0"
        )
        wrong_size[0]["palette_file"] = str(wrong_path)
        cases["wrong-size"] = wrong_size
        cases["missing"] = json.loads(json.dumps(self.resources[:-1]))
        duplicate = json.loads(json.dumps(self.resources))
        duplicate[-1]["source_pointer"] = duplicate[0]["source_pointer"]
        cases["duplicate"] = duplicate
        unknown = json.loads(json.dumps(self.resources))
        unknown[-1]["source_pointer"] = "0x08FFFFFF"
        cases["unknown"] = unknown

        for name, resources in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_direct_image_palette_relocation_patches(
                    ROOT,
                    self._write_spec(
                        resources=resources,
                        name=f"{name}.json",
                    ),
                    rom=self.base,
                    layout=self.layout,
                )

    def test_region_overflow_fails_before_returning_patches(self):
        from tools.gba_image_export import encode_gba_lz77
        from tools.import_direct_image_palette_relocations import (
            resolve_direct_image_palette_relocation_patches,
        )

        with mock.patch(
            "tools.import_direct_image_palette_relocations.encode_gba_lz77",
            side_effect=lambda data: encode_gba_lz77(data) + bytes(0x401),
        ), self.assertRaisesRegex(ValueError, "registered region"):
            resolve_direct_image_palette_relocation_patches(
                ROOT,
                self._write_spec(),
                rom=self.base,
                layout=self.layout,
            )

    def test_automated_manifest_and_unified_build_accept_relocation_type(self):
        from tools import automated_test, build_mod
        from tools.import_direct_image_palette_relocations import (
            DIRECT_INVENTORY_PATH,
            GRAPHICS_CATALOG_PATH,
            LZ_INVENTORY_PATH,
        )

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "direct-image-palettes",
                        "type": "direct_image_palette_relocation",
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
            "sequel/content/direct-image-palettes",
            LZ_INVENTORY_PATH.parent,
            GRAPHICS_CATALOG_PATH.parent,
            DIRECT_INVENTORY_PATH.parent,
        ):
            (build_root / relative).mkdir(parents=True, exist_ok=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        for relative in (
            "sequel/rom-layout.json",
            "sequel/image-resource-regions.json",
            LZ_INVENTORY_PATH,
            GRAPHICS_CATALOG_PATH,
            DIRECT_INVENTORY_PATH,
        ):
            destination = build_root / relative
            destination.write_bytes((ROOT / relative).read_bytes())

        spec = json.loads(self._write_spec().read_text())
        for resource in spec["resources"]:
            source = Path(resource["palette_file"])
            destination = (
                build_root
                / "sequel/content/direct-image-palettes"
                / source.name
            )
            destination.write_bytes(source.read_bytes())
            resource["palette_file"] = str(destination)
        spec_path = (
            build_root
            / "sequel/content/direct-image-palettes/relocation.json"
        )
        spec_path.write_text(json.dumps(spec))
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "direct-image-palettes",
                            "type": "direct_image_palette_relocation",
                            "spec": (
                                "sequel/content/direct-image-palettes/"
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
                    "project_id": "direct-image-palettes-test",
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
        self.assertEqual(
            17,
            sum(
                row["patch_class"] == "allocation"
                for row in report["applied_patches"]
            ),
        )
        self.assertEqual(46, len(report["applied_patches"]))


if __name__ == "__main__":
    unittest.main()
