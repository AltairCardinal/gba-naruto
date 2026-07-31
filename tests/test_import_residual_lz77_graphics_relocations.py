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
INVENTORY = Path(
    "artifacts/rom-pointer-lz77-inventory-v1/"
    "rom-pointer-lz77-inventory.json"
)
CATALOG = Path(
    "artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json"
)


class ImportResidualLz77GraphicsRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        inventory = json.loads((ROOT / INVENTORY).read_text())
        records = [
            row
            for row in inventory["new_records"]
            if row["classification"]["kind"] == "graphics"
        ]
        self.resources = []
        for row in records:
            source_pointer = int(row["gba_address"], 16)
            graphics = self.temp / f"{source_pointer:08x}.4bpp.bin"
            graphics.write_bytes(
                lz77_decompress(self.base, source_pointer - ROM_BASE)
            )
            self.resources.append(
                {
                    "source_pointer": f"0x{source_pointer:08X}",
                    "graphics_file": str(graphics),
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
        registry = ROOT / "sequel/image-resource-regions.json"
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "residual-lz77-graphics-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_inventory": INVENTORY.as_posix(),
                    "source_inventory_sha256": hashlib.sha256(
                        (ROOT / INVENTORY).read_bytes()
                    ).hexdigest(),
                    "source_catalog": CATALOG.as_posix(),
                    "source_catalog_sha256": hashlib.sha256(
                        (ROOT / CATALOG).read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry.read_bytes()
                    ).hexdigest(),
                    "region": "residual-lz77-graphics",
                    "region_owner": "residual_lz77_graphics",
                    "resources": (
                        resources if resources is not None else self.resources
                    ),
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_twenty_graphics_and_all_pointer_references(self):
        from tools.import_residual_lz77_graphics_relocations import (
            catalog_residual_lz77_graphics,
        )

        catalog = catalog_residual_lz77_graphics(ROOT, self.base)

        self.assertEqual(20, catalog["resource_count"])
        self.assertEqual(34, catalog["pointer_reference_count"])
        self.assertEqual(36_640, catalog["decompressed_size"])
        self.assertEqual(16_574, catalog["compressed_size"])
        self.assertEqual(2, catalog["unresolved_palette_count"])
        self.assertEqual([], catalog["unexpected_pointer_offsets"])

    def test_registry_reserves_residual_lz77_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        residual = regions.require(
            "residual-lz77-graphics",
            "residual_lz77_graphics",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xBB0000, 0xBC0000), (residual.start, residual.end))
        self.assertEqual((0xBC0000, 0xC00000), (future.start, future.end))

    def test_full_preservation_relocates_twenty_payloads_and_thirty_four_roots(
        self,
    ):
        from tools.build_mod import apply_patch
        from tools.import_residual_lz77_graphics_relocations import (
            resolve_residual_lz77_graphics_relocation_patches,
        )
        from tools.patch_safety import PatchSafetyGate

        patches = resolve_residual_lz77_graphics_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        redirects = [
            row
            for row in patches
            if row.get("asset_type") == "residual_lz77_graphics_pointer"
        ]
        self.assertEqual(20, len(allocations))
        self.assertEqual(34, len(redirects))

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
            pointer = allocation["new_pointer"]
            self.assertTrue(0x08BB0000 <= pointer < 0x08BC0000)
            self.assertEqual(
                Path(allocation["source_file"]).read_bytes(),
                lz77_decompress(output, pointer - ROM_BASE),
            )

    def test_same_size_content_replacement_is_supported(self):
        from tools.import_residual_lz77_graphics_relocations import (
            resolve_residual_lz77_graphics_relocation_patches,
        )

        graphics = Path(self.resources[0]["graphics_file"])
        replacement = bytearray(graphics.read_bytes())
        replacement[:32] = bytes(range(32))
        graphics.write_bytes(replacement)

        patches = resolve_residual_lz77_graphics_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocation = next(
            row
            for row in patches
            if row.get("source_pointer")
            == int(self.resources[0]["source_pointer"], 16)
            and "allocation" in row
        )
        self.assertEqual(hashlib.sha256(replacement).hexdigest(),
                         allocation["replacement_sha256"])
        self.assertEqual(len(replacement), allocation["decompressed_size"])

    def test_wrong_size_missing_duplicate_and_unknown_resources_fail_atomically(
        self,
    ):
        from tools.import_residual_lz77_graphics_relocations import (
            resolve_residual_lz77_graphics_relocation_patches,
        )

        cases: dict[str, list[dict]] = {}
        wrong_size = json.loads(json.dumps(self.resources))
        wrong_file = Path(wrong_size[0]["graphics_file"])
        wrong_file.write_bytes(wrong_file.read_bytes() + bytes(32))
        cases["wrong_size"] = wrong_size
        cases["missing"] = json.loads(json.dumps(self.resources[:-1]))
        duplicate = json.loads(json.dumps(self.resources))
        duplicate[-1]["source_pointer"] = duplicate[0]["source_pointer"]
        cases["duplicate"] = duplicate
        unknown = json.loads(json.dumps(self.resources))
        unknown[-1]["source_pointer"] = "0x08FFFFFF"
        cases["unknown"] = unknown

        for name, resources in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                resolve_residual_lz77_graphics_relocation_patches(
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
        from tools.import_residual_lz77_graphics_relocations import (
            resolve_residual_lz77_graphics_relocation_patches,
        )

        with mock.patch(
            "tools.import_residual_lz77_graphics_relocations."
            "encode_gba_lz77",
            side_effect=lambda data: encode_gba_lz77(data) + bytes(0x4001),
        ), self.assertRaisesRegex(ValueError, "registered region"):
            resolve_residual_lz77_graphics_relocation_patches(
                ROOT,
                self._write_spec(),
                rom=self.base,
                layout=self.layout,
            )

    def test_automated_manifest_and_unified_build_accept_relocation_type(self):
        from tools import automated_test, build_mod

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "residual-lz77-graphics",
                        "type": "residual_lz77_graphics_relocation",
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
            "sequel/content/residual-lz77-graphics",
            INVENTORY.parent,
            CATALOG.parent,
        ):
            (build_root / relative).mkdir(parents=True, exist_ok=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        for relative in (
            "sequel/rom-layout.json",
            "sequel/image-resource-regions.json",
            INVENTORY,
            CATALOG,
        ):
            destination = build_root / relative
            destination.write_bytes((ROOT / relative).read_bytes())

        spec = json.loads(self._write_spec().read_text())
        for resource in spec["resources"]:
            source = Path(resource["graphics_file"])
            destination = (
                build_root
                / "sequel/content/residual-lz77-graphics"
                / source.name
            )
            destination.write_bytes(source.read_bytes())
            resource["graphics_file"] = str(destination)
        spec_path = (
            build_root
            / "sequel/content/residual-lz77-graphics/relocation.json"
        )
        spec_path.write_text(json.dumps(spec))
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "residual-lz77-graphics",
                            "type": "residual_lz77_graphics_relocation",
                            "spec": (
                                "sequel/content/residual-lz77-graphics/"
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
                    "project_id": "residual-lz77-graphics-test",
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
            20,
            sum(
                row["patch_class"] == "allocation"
                for row in report["applied_patches"]
            ),
        )
        self.assertEqual(54, len(report["applied_patches"]))


if __name__ == "__main__":
    unittest.main()
