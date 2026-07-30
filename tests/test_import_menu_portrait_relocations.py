from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class ImportMenuPortraitRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.catalog_path = ROOT / "artifacts/menu-portraits-v1/manifest.json"
        self.catalog = json.loads(
            self.catalog_path.read_text(encoding="utf-8")
        )
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _edit(self, resource: dict, **extra) -> dict:
        aliases = [
            row
            for row in self.catalog["portraits"]
            if row["resource_id"] == resource["resource_id"]
        ]
        return {
            "id": f"portrait-{resource['resource_id']}",
            "resource_id": resource["resource_id"],
            "png": str(
                ROOT / "artifacts/menu-portraits-v1" / aliases[0]["png"]
            ),
            "expected": {
                "gfx_pointer": resource["gfx_pointer"],
                "palette_pointer": resource["palette_pointer"],
                "compressed_sha256": resource["compressed_sha256"],
                "palette_sha256": resource["palette_sha256"],
                "pair_pointer_offsets": sorted(
                    row["pair_file_offset"] for row in aliases
                ),
            },
            **extra,
        }

    def _write_spec(self, edits: list[dict], name: str = "spec.json") -> Path:
        path = self.temp / name
        registry_path = ROOT / "sequel/image-resource-regions.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "menu-portrait-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_catalog": (
                        "artifacts/menu-portraits-v1/manifest.json"
                    ),
                    "source_catalog_sha256": hashlib.sha256(
                        self.catalog_path.read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry_path.read_bytes()
                    ).hexdigest(),
                    "region": "menu-portraits",
                    "region_owner": "menu_portrait_resources",
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_74_pairs_140_payloads_and_622_references(self):
        from tools.import_menu_portrait_relocations import (
            catalog_menu_portrait_payloads,
        )

        resources = catalog_menu_portrait_payloads(ROOT, self.base)

        self.assertEqual(140, len(resources))
        self.assertEqual(
            {"graphics": 70, "palette": 70},
            {
                resource_type: sum(
                    row["resource_type"] == resource_type
                    for row in resources.values()
                )
                for resource_type in ("graphics", "palette")
            },
        )
        self.assertEqual(
            622,
            sum(len(row["logical_aliases"]) for row in resources.values()),
        )
        self.assertEqual(
            set(),
            {
                offset
                for row in resources.values()
                for offset in row["unexpected_pointer_offsets"]
            },
        )
        self.assertEqual(
            74,
            len(
                {
                    alias["resource_id"]
                    for row in resources.values()
                    for alias in row["logical_aliases"]
                }
            ),
        )

    def test_registry_reserves_a_worst_case_menu_portrait_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )

        portraits = regions.require(
            "menu-portraits",
            "menu_portrait_resources",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xA80000, 0xB00000), (portraits.start, portraits.end))
        self.assertEqual((0xB00000, 0xC00000), (future.start, future.end))
        worst_case_lz77 = 4 + (6400 + 7) // 8 + 6400
        worst_case_span = 70 * worst_case_lz77 + 70 * 128 + 140 * 3
        self.assertLess(worst_case_span, portraits.end - portraits.start)

    def test_full_preservation_relocates_140_payloads_and_622_pointers(self):
        from tools.import_menu_portrait_relocations import (
            resolve_menu_portrait_relocation_patches,
        )

        patches = resolve_menu_portrait_relocation_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(resource)
                    for resource in self.catalog["unique_resources"]
                ]
            ),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [patch for patch in patches if "allocation" in patch]
        redirects = [
            patch
            for patch in patches
            if patch.get("asset_type") == "menu_portrait_pointer"
        ]

        self.assertEqual(140, len(allocations))
        self.assertEqual(622, len(redirects))
        self.assertEqual(
            {"graphics": 70, "palette": 70},
            {
                resource_type: sum(
                    patch["resource_type"] == resource_type
                    for patch in allocations
                )
                for resource_type in ("graphics", "palette")
            },
        )
        self.assertEqual(
            140,
            len({patch["new_pointer"] for patch in allocations}),
        )
        self.assertTrue(
            all(
                patch["allocation"]["region"] == "menu-portraits"
                for patch in allocations
            )
        )
        self.assertLessEqual(
            max(
                patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
                for patch in allocations
            ),
            0xB00000,
        )

    def test_changed_png_and_pair_alias_subset_relocate_together(self):
        from tools.import_menu_portrait_relocations import (
            resolve_menu_portrait_relocation_patches,
        )
        from tools.import_menu_portraits import portrait_canvas_to_stream

        resource = self.catalog["unique_resources"][0]
        edit = self._edit(resource)
        source = Path(edit["png"])
        with Image.open(source) as image:
            image.load()
            pixels = bytearray(image.tobytes())
            pixels[0] = (pixels[0] + 1) % 64
            image.frombytes(bytes(pixels))
            edited_png = self.temp / "edited.png"
            image.save(edited_png, transparency=image.info["transparency"])
        target_pair = edit["expected"]["pair_pointer_offsets"][0]
        edit["png"] = str(edited_png)
        edit["target_pair_pointer_offsets"] = [target_pair]

        patches = resolve_menu_portrait_relocation_patches(
            ROOT,
            self._write_spec([edit]),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [patch for patch in patches if "allocation" in patch]
        redirects = [
            patch
            for patch in patches
            if patch.get("asset_type") == "menu_portrait_pointer"
        ]

        self.assertEqual(2, len(allocations))
        self.assertEqual(2, len(redirects))
        self.assertEqual(
            [target_pair, target_pair + 4],
            sorted(patch["offset"] for patch in redirects),
        )
        graphics = next(
            patch
            for patch in allocations
            if patch["resource_type"] == "graphics"
        )
        self.assertEqual(
            portrait_canvas_to_stream(bytes(pixels)),
            lz77_decompress(bytes.fromhex(graphics["after_hex"]), 0),
        )

    def test_cross_pair_shared_graphics_stay_isolated_or_merge_by_payload(self):
        from tools.import_menu_portrait_relocations import (
            resolve_menu_portrait_relocation_patches,
        )

        resource_21 = self.catalog["unique_resources"][21]
        resource_67 = self.catalog["unique_resources"][67]
        self.assertEqual(
            resource_21["gfx_pointer"],
            resource_67["gfx_pointer"],
        )
        edit_21 = self._edit(resource_21)
        edit_67 = self._edit(resource_67)
        pairs_21 = set(edit_21["expected"]["pair_pointer_offsets"])
        pairs_67 = set(edit_67["expected"]["pair_pointer_offsets"])

        single_patches = resolve_menu_portrait_relocation_patches(
            ROOT,
            self._write_spec([edit_21], "shared-single.json"),
            rom=self.base,
            layout=self.layout,
        )
        single_graphics = next(
            patch
            for patch in single_patches
            if patch.get("resource_type") == "graphics"
            and "allocation" in patch
        )
        self.assertEqual(pairs_21, set(single_graphics["target_pointer_offsets"]))
        self.assertEqual(
            pairs_21 | pairs_67,
            set(single_graphics["all_pointer_offsets"]),
        )
        self.assertTrue(
            pairs_67.isdisjoint(single_graphics["target_pointer_offsets"])
        )

        same_patches = resolve_menu_portrait_relocation_patches(
            ROOT,
            self._write_spec([edit_21, edit_67], "shared-same.json"),
            rom=self.base,
            layout=self.layout,
        )
        same_allocations = [
            patch for patch in same_patches if "allocation" in patch
        ]
        same_graphics = [
            patch
            for patch in same_allocations
            if patch["resource_type"] == "graphics"
        ]
        self.assertEqual(3, len(same_allocations))
        self.assertEqual(1, len(same_graphics))
        self.assertEqual([21, 67], same_graphics[0]["resource_ids"])
        self.assertEqual(
            pairs_21 | pairs_67,
            set(same_graphics[0]["target_pointer_offsets"]),
        )

        with Image.open(edit_21["png"]) as image:
            image.load()
            pixels = bytearray(image.tobytes())
            pixels[0] = (pixels[0] + 1) % 64
            image.frombytes(bytes(pixels))
            changed_png = self.temp / "resource-21-changed.png"
            image.save(
                changed_png,
                transparency=image.info["transparency"],
            )
        changed_21 = self._edit(resource_21, png=str(changed_png))
        different_patches = resolve_menu_portrait_relocation_patches(
            ROOT,
            self._write_spec(
                [changed_21, edit_67],
                "shared-different.json",
            ),
            rom=self.base,
            layout=self.layout,
        )
        different_allocations = [
            patch for patch in different_patches if "allocation" in patch
        ]
        different_graphics = [
            patch
            for patch in different_allocations
            if patch["resource_type"] == "graphics"
        ]
        self.assertEqual(4, len(different_allocations))
        self.assertEqual(2, len(different_graphics))
        self.assertEqual(
            [[21], [67]],
            sorted(patch["resource_ids"] for patch in different_graphics),
        )
        self.assertEqual(
            {frozenset(pairs_21), frozenset(pairs_67)},
            {
                frozenset(patch["target_pointer_offsets"])
                for patch in different_graphics
            },
        )
        self.assertEqual(
            2,
            len({patch["new_pointer"] for patch in different_graphics}),
        )

    def test_stale_alias_invalid_subset_and_region_overflow_fail(self):
        from tools.import_menu_portrait_relocations import (
            resolve_menu_portrait_relocation_patches,
        )

        resource = self.catalog["unique_resources"][0]
        stale = self._edit(resource)
        stale["expected"]["pair_pointer_offsets"] = stale["expected"][
            "pair_pointer_offsets"
        ][1:]
        with self.assertRaisesRegex(ValueError, "alias contract"):
            resolve_menu_portrait_relocation_patches(
                ROOT,
                self._write_spec([stale], "stale.json"),
                rom=self.base,
                layout=self.layout,
            )

        invalid_subset = self._edit(resource)
        invalid_subset["target_pair_pointer_offsets"] = [0x100]
        with self.assertRaisesRegex(ValueError, "not canonical"):
            resolve_menu_portrait_relocation_patches(
                ROOT,
                self._write_spec([invalid_subset], "subset.json"),
                rom=self.base,
                layout=self.layout,
            )

        registry = json.loads(
            (ROOT / "sequel/image-resource-regions.json").read_text(
                encoding="utf-8"
            )
        )
        menu = next(
            row for row in registry["regions"] if row["id"] == "menu-portraits"
        )
        future = next(
            row
            for row in registry["regions"]
            if row["id"] == "future-image-resources"
        )
        menu["end"] = "0xA80004"
        future["start"] = "0xA80004"
        tiny_regions = ImageResourceRegions.from_dict(registry, self.layout)
        with self.assertRaisesRegex(ValueError, "exceeds.*registered region"):
            resolve_menu_portrait_relocation_patches(
                ROOT,
                self._write_spec([self._edit(resource)], "overflow.json"),
                rom=self.base,
                layout=self.layout,
                regions=tiny_regions,
            )

    def test_automated_manifest_accepts_portrait_relocation_type(self):
        from tools import automated_test

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "menu-portraits-relocation",
                        "type": "menu_portrait_relocation",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)

        self.assertEqual([], runner.summary()["failures"])

    def test_unified_build_applies_portrait_allocations_and_redirects(self):
        from tools import build_mod

        resource = self.catalog["unique_resources"][0]
        edit = self._edit(resource)
        edit["target_pair_pointer_offsets"] = [
            edit["expected"]["pair_pointer_offsets"][0]
        ]
        build_root = self.temp / "build-root"
        for relative in (
            "rom",
            "sequel/patches",
            "sequel/content/menu-portraits",
            "artifacts/menu-portraits-v1",
        ):
            (build_root / relative).mkdir(parents=True, exist_ok=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        for relative in (
            "sequel/rom-layout.json",
            "sequel/image-resource-regions.json",
            "artifacts/menu-portraits-v1/manifest.json",
        ):
            destination = build_root / relative
            destination.write_bytes((ROOT / relative).read_bytes())

        spec_path = (
            build_root
            / "sequel/content/menu-portraits/relocation.json"
        )
        spec_path.write_text(
            self._write_spec([edit]).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "menu-portraits-relocation",
                            "type": "menu_portrait_relocation",
                            "spec": (
                                "sequel/content/menu-portraits/"
                                "relocation.json"
                            ),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        project_path = build_root / "sequel/project.json"
        project_path.write_text(
            json.dumps(
                {
                    "project_id": "menu-portrait-relocation-test",
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
            ),
            encoding="utf-8",
        )

        with mock.patch.object(build_mod, "ROOT", build_root):
            report = build_mod.build(project_path)

        allocations = [
            row
            for row in report["applied_patches"]
            if row["patch_class"] == "allocation"
        ]
        redirects = [
            row
            for row in report["applied_patches"]
            if row.get("asset_type") == "menu_portrait_pointer"
        ]
        self.assertEqual(2, len(allocations))
        self.assertEqual(2, len(redirects))
        self.assertEqual(
            {"menu-portraits"},
            {row["allocation_region"] for row in allocations},
        )
        self.assertEqual(0x1000000, report["output_rom"]["size"])


if __name__ == "__main__":
    unittest.main()
