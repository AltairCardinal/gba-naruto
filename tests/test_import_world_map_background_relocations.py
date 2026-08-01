from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
CATALOG_PATH = Path("artifacts/world-map-backgrounds-v1/manifest.json")


class ImportWorldMapBackgroundRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.catalog_path = ROOT / CATALOG_PATH
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _resources(self) -> dict[tuple[str, str], dict]:
        from tools.import_world_map_background_relocations import (
            catalog_world_map_background_relocation_payloads,
        )

        return catalog_world_map_background_relocation_payloads(
            ROOT,
            self.base,
        )

    def _edit(
        self,
        resource: dict,
        *,
        source_file: Path | None = None,
        target_pointer_offsets: list[int] | None = None,
    ) -> dict:
        edit = {
            "id": (
                f"{resource['resource_type']}-"
                f"{resource['resource_sha256'][:12]}"
            ),
            "resource_type": resource["resource_type"],
            "resource_sha256": resource["resource_sha256"],
            "source_file": str(
                source_file
                or CATALOG_PATH.parent / resource["source_files"][0]
            ),
            "expected": {
                "decompressed_size": resource["decompressed_size"],
                "physical_offsets": resource["physical_offsets"],
                "pointer_offsets": sorted(
                    alias["table_pointer_offset"]
                    for alias in resource["pointer_aliases"]
                ),
            },
        }
        if target_pointer_offsets is not None:
            edit["target_pointer_offsets"] = target_pointer_offsets
        return edit

    def _write_spec(self, edits: list[dict], name: str = "spec.json") -> Path:
        registry_path = ROOT / "sequel/image-resource-regions.json"
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "world-map-background-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_catalog": CATALOG_PATH.as_posix(),
                    "source_catalog_sha256": hashlib.sha256(
                        self.catalog_path.read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry_path.read_bytes()
                    ).hexdigest(),
                    "region": "world-map-backgrounds",
                    "region_owner": "world_map_background_resources",
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_7_contents_9_payloads_and_9_references(self):
        resources = self._resources()

        self.assertEqual(7, len(resources))
        self.assertEqual(
            {"graphics": 3, "tilemap": 1, "palette": 3},
            {
                resource_type: sum(
                    row["resource_type"] == resource_type
                    for row in resources.values()
                )
                for resource_type in ("graphics", "tilemap", "palette")
            },
        )
        self.assertEqual(
            9,
            sum(len(row["physical_offsets"]) for row in resources.values()),
        )
        self.assertEqual(
            9,
            sum(len(row["pointer_aliases"]) for row in resources.values()),
        )
        self.assertFalse(
            any(row["unexpected_pointer_offsets"] for row in resources.values())
        )

    def test_registry_reserves_worst_case_world_map_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        world = regions.require(
            "world-map-backgrounds",
            "world_map_background_resources",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xB71000, 0xB90000), (world.start, world.end))
        self.assertEqual((0xBC1C00, 0xC00000), (future.start, future.end))
        worst_case = (
            3 * (4 + 512 * 64 + (512 * 64 + 7) // 8 + 3)
            + 3 * (4 + 1200 + (1200 + 7) // 8 + 3)
            + 3 * (320 + 3)
        )
        self.assertLess(worst_case, world.end - world.start)

    def test_full_preservation_relocates_7_contents_and_9_pointers(self):
        from tools.import_world_map_background_relocations import (
            resolve_world_map_background_relocation_patches,
        )

        resources = self._resources()
        patches = resolve_world_map_background_relocation_patches(
            ROOT,
            self._write_spec([self._edit(row) for row in resources.values()]),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [patch for patch in patches if "allocation" in patch]
        redirects = [
            patch
            for patch in patches
            if patch.get("asset_type") == "world_map_background_pointer"
        ]

        self.assertEqual(7, len(allocations))
        self.assertEqual(9, len(redirects))
        self.assertEqual(
            {"graphics": 3, "tilemap": 1, "palette": 3},
            {
                role: sum(row["resource_type"] == role for row in allocations)
                for role in ("graphics", "tilemap", "palette")
            },
        )
        self.assertLessEqual(
            max(
                row["offset"] + len(bytes.fromhex(row["after_hex"]))
                for row in allocations
            ),
            0xB90000,
        )

    def test_shared_tilemap_alias_can_split_without_touching_siblings(self):
        from tools.import_world_map_background_relocations import (
            resolve_world_map_background_relocation_patches,
        )

        resource = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "tilemap"
        )
        content = bytearray(
            (ROOT / CATALOG_PATH.parent / resource["source_files"][0]).read_bytes()
        )
        content[0:2] = (1).to_bytes(2, "little")
        edited = self.temp / "tilemap.bin"
        edited.write_bytes(content)
        target = [resource["pointer_aliases"][0]["table_pointer_offset"]]
        patches = resolve_world_map_background_relocation_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        source_file=edited,
                        target_pointer_offsets=target,
                    )
                ],
                "split.json",
            ),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        redirects = [
            row
            for row in patches
            if row.get("asset_type") == "world_map_background_pointer"
        ]

        self.assertEqual(1, len(allocations))
        self.assertEqual(target, allocations[0]["target_pointer_offsets"])
        self.assertEqual(target, [row["offset"] for row in redirects])
        self.assertEqual(3, len(allocations[0]["all_pointer_offsets"]))

    def test_invalid_geometry_duplicate_claim_and_overflow_fail_atomically(self):
        from tools.import_world_map_background_relocations import (
            resolve_world_map_background_relocation_patches,
        )

        resources = self._resources()
        graphics = next(
            row for row in resources.values() if row["resource_type"] == "graphics"
        )
        invalid_graphics = self.temp / "invalid.8bpp.bin"
        invalid_graphics.write_bytes(bytes([160]) * graphics["decompressed_size"])
        with self.assertRaisesRegex(ValueError, "palette index"):
            resolve_world_map_background_relocation_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            graphics,
                            source_file=invalid_graphics,
                        )
                    ],
                    "invalid-graphics.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

        source = (
            ROOT
            / CATALOG_PATH.parent
            / graphics["source_files"][0]
        ).read_bytes()
        overlaps_bg3 = self.temp / "513-tiles.8bpp.bin"
        overlaps_bg3.write_bytes(source + bytes(64))
        with self.assertRaisesRegex(ValueError, "1..512"):
            resolve_world_map_background_relocation_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            graphics,
                            source_file=overlaps_bg3,
                        )
                    ],
                    "overlaps-bg3.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

        target = [graphics["pointer_aliases"][0]["table_pointer_offset"]]
        first = self._edit(graphics, target_pointer_offsets=target)
        duplicate = self._edit(graphics, target_pointer_offsets=target)
        duplicate["id"] += "-duplicate"
        with self.assertRaisesRegex(ValueError, "claimed twice"):
            resolve_world_map_background_relocation_patches(
                ROOT,
                self._write_spec([first, duplicate], "duplicate.json"),
                rom=self.base,
                layout=self.layout,
            )

        registry = json.loads(
            (ROOT / "sequel/image-resource-regions.json").read_text(
                encoding="utf-8"
            )
        )
        world = next(
            row
            for row in registry["regions"]
            if row["id"] == "world-map-backgrounds"
        )
        generic_sprite = next(
            row
            for row in registry["regions"]
            if row["id"] == "generic-sprite-bundle"
        )
        world["end"] = "0xB71004"
        generic_sprite["start"] = "0xB71004"
        tiny = ImageResourceRegions.from_dict(registry, self.layout)
        with self.assertRaisesRegex(ValueError, "exceeds.*registered region"):
            resolve_world_map_background_relocation_patches(
                ROOT,
                self._write_spec([self._edit(graphics)], "overflow.json"),
                rom=self.base,
                layout=self.layout,
                regions=tiny,
            )

    def test_automated_manifest_accepts_world_map_relocation_type(self):
        from tools import automated_test

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "world-map-backgrounds-relocation",
                        "type": "world_map_background_relocation",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)
        self.assertEqual([], runner.summary()["failures"])

    def test_unified_build_applies_world_map_allocations_and_redirects(self):
        from tools import build_mod

        resource = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "tilemap"
        )
        build_root = self.temp / "build-root"
        for relative in (
            "rom",
            "sequel/patches",
            "sequel/content/world-map-backgrounds",
        ):
            (build_root / relative).mkdir(parents=True, exist_ok=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        for relative in (
            "sequel/rom-layout.json",
            "sequel/image-resource-regions.json",
        ):
            destination = build_root / relative
            destination.write_bytes((ROOT / relative).read_bytes())
        shutil.copytree(
            ROOT / CATALOG_PATH.parent,
            build_root / CATALOG_PATH.parent,
        )
        spec_path = (
            build_root
            / "sequel/content/world-map-backgrounds/relocation.json"
        )
        spec_path.write_text(
            self._write_spec([self._edit(resource)]).read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "world-map-backgrounds-relocation",
                            "type": "world_map_background_relocation",
                            "spec": (
                                "sequel/content/world-map-backgrounds/"
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
                    "project_id": "world-map-relocation-test",
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
            if row.get("asset_type") == "world_map_background_pointer"
        ]
        self.assertEqual(1, len(allocations))
        self.assertEqual(3, len(redirects))
        self.assertEqual(
            {"world-map-backgrounds"},
            {row["allocation_region"] for row in allocations},
        )
        self.assertEqual(0x1000000, report["output_rom"]["size"])


if __name__ == "__main__":
    unittest.main()
