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
CATALOG_PATH = Path("artifacts/map-canvases-v1/manifest.json")
REGISTRY_PATH = Path("sequel/image-resource-regions.json")


class ImportMapResourceRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        self.regions = ImageResourceRegions.from_path(
            ROOT / REGISTRY_PATH,
            self.layout,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _resources(self):
        from tools.import_map_resource_relocations import (
            catalog_map_resource_relocations,
        )

        return catalog_map_resource_relocations(ROOT, self.base)

    @staticmethod
    def _edit(resource: dict, **extra) -> dict:
        return {
            "id": (
                f"{resource['resource_type']}-"
                f"{resource['source_sha256'][:12]}"
            ),
            "resource_type": resource["resource_type"],
            "source_sha256": resource["source_sha256"],
            "expected_physical_offsets": resource["physical_offsets"],
            "expected_header_pointer_offsets": [
                row["header_pointer_offset"]
                for row in resource["logical_aliases"]
            ],
            **extra,
        }

    def _write_spec(self, edits: list[dict], name: str = "spec.json") -> Path:
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "map-resource-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_catalog": CATALOG_PATH.as_posix(),
                    "source_catalog_sha256": hashlib.sha256(
                        (ROOT / CATALOG_PATH).read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": REGISTRY_PATH.as_posix(),
                    "region_registry_sha256": hashlib.sha256(
                        (ROOT / REGISTRY_PATH).read_bytes()
                    ).hexdigest(),
                    "region": "map-resources",
                    "region_owner": "map_resources",
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_166_content_217_physical_and_249_references(self):
        resources = self._resources()
        self.assertEqual(166, len(resources))
        self.assertEqual(
            217,
            sum(len(row["physical_offsets"]) for row in resources.values()),
        )
        self.assertEqual(
            249,
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

    def test_preservation_relocation_redirects_every_header_alias(self):
        from tools.import_map_resource_relocations import (
            resolve_map_resource_relocation_patches,
        )

        resource = max(
            self._resources().values(),
            key=lambda row: len(row["logical_aliases"]),
        )
        patches = resolve_map_resource_relocation_patches(
            ROOT,
            self._write_spec([self._edit(resource)]),
            rom=self.base,
            layout=self.layout,
            regions=self.regions,
        )

        allocation, *redirects = patches
        self.assertEqual(0x980000, allocation["offset"])
        self.assertEqual("map-resources", allocation["allocation"]["region"])
        self.assertEqual(
            resource["source_content"],
            lz77_decompress(bytes.fromhex(allocation["after_hex"]), 0),
        )
        self.assertEqual(
            {
                row["header_pointer_offset"]
                for row in resource["logical_aliases"]
            },
            {row["offset"] for row in redirects},
        )

    def test_variable_length_graphics_and_alias_split_are_supported(self):
        from tools.import_map_resource_relocations import (
            resolve_map_resource_relocation_patches,
        )

        resource = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "tile_graphics"
            and len(row["logical_aliases"]) > 1
        )
        replacement = resource["source_content"] + bytes(32)
        source = self.temp / "expanded-tiles.bin"
        source.write_bytes(replacement)
        target = [resource["logical_aliases"][0]["header_pointer_offset"]]
        patches = resolve_map_resource_relocation_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        content_file=str(source),
                        content_sha256=hashlib.sha256(replacement).hexdigest(),
                        target_header_pointer_offsets=target,
                    )
                ]
            ),
            rom=self.base,
            layout=self.layout,
            regions=self.regions,
        )

        self.assertEqual(2, len(patches))
        self.assertEqual(
            replacement,
            lz77_decompress(bytes.fromhex(patches[0]["after_hex"]), 0),
        )
        self.assertEqual(target, [patches[1]["offset"]])

    def test_stale_alias_invalid_linked_view_and_overflow_fail_atomically(self):
        from tools.import_map_resource_relocations import (
            resolve_map_resource_relocation_patches,
        )

        resource = next(iter(self._resources().values()))
        edit = self._edit(resource)
        edit["expected_header_pointer_offsets"] = []
        with self.assertRaisesRegex(ValueError, "header pointer contract"):
            resolve_map_resource_relocation_patches(
                ROOT,
                self._write_spec([edit], "stale.json"),
                rom=self.base,
                layout=self.layout,
                regions=self.regions,
            )

        graphics = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "tile_graphics"
        )
        bad = self.temp / "bad-tiles.bin"
        bad.write_bytes(bytes(32))
        with self.assertRaisesRegex(ValueError, "tile index"):
            resolve_map_resource_relocation_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            graphics,
                            content_file=str(bad),
                        )
                    ],
                    "bad-view.json",
                ),
                rom=self.base,
                layout=self.layout,
                regions=self.regions,
            )

        registry = json.loads(
            (ROOT / REGISTRY_PATH).read_text(encoding="utf-8")
        )
        registry["regions"][1]["end"] = "0x980004"
        registry["regions"][2]["start"] = "0x980004"
        tiny = ImageResourceRegions.from_dict(registry, self.layout)
        with self.assertRaisesRegex(ValueError, "region capacity"):
            resolve_map_resource_relocation_patches(
                ROOT,
                self._write_spec(
                    [self._edit(graphics)],
                    "overflow.json",
                ),
                rom=self.base,
                layout=self.layout,
                regions=tiny,
            )

    def test_unified_build_combines_tile_and_map_relocations_without_overlap(self):
        from tools import build_mod
        from tools.import_tile_asset_resources import (
            CATALOG_PATH as TILE_CATALOG_PATH,
            catalog_tile_asset_resources,
        )

        map_resource = next(iter(self._resources().values()))
        tile_resource = next(
            iter(catalog_tile_asset_resources(ROOT, self.base).values())
        )
        build_root = self.temp / "combined-build"
        for relative in (
            "rom",
            "sequel/patches",
            "sequel/content/map-resources",
            "sequel/content/tile-assets",
            "artifacts/map-canvases-v1",
            "artifacts/tile-assets-bg-v2",
        ):
            (build_root / relative).mkdir(parents=True, exist_ok=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        for relative in (
            "sequel/rom-layout.json",
            "sequel/image-resource-regions.json",
            CATALOG_PATH.as_posix(),
            TILE_CATALOG_PATH.as_posix(),
        ):
            destination = build_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / relative).read_bytes())

        map_spec = (
            build_root / "sequel/content/map-resources/relocation.json"
        )
        map_spec.write_text(
            self._write_spec([self._edit(map_resource)]).read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        tile_spec = build_root / "sequel/content/tile-assets/relocation.json"
        tile_spec.write_text(
            json.dumps(
                {
                    "schema": "tile-asset-resource-import-v2",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_catalog": TILE_CATALOG_PATH.as_posix(),
                    "source_catalog_sha256": hashlib.sha256(
                        (ROOT / TILE_CATALOG_PATH).read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": REGISTRY_PATH.as_posix(),
                    "region_registry_sha256": hashlib.sha256(
                        (ROOT / REGISTRY_PATH).read_bytes()
                    ).hexdigest(),
                    "region": "tile-assets",
                    "region_owner": "tile_asset_resources",
                    "edits": [
                        {
                            "id": "tile-preservation",
                            "resource_type": tile_resource["resource_type"],
                            "source_pointer": tile_resource["source_pointer"],
                            "source_sha256": tile_resource["source_sha256"],
                            "expected_pointer_offsets": [
                                row["pointer_offset"]
                                for row in tile_resource["logical_aliases"]
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "tile-relocation",
                            "type": "tile_asset_resource",
                            "spec": (
                                "sequel/content/tile-assets/relocation.json"
                            ),
                        },
                        {
                            "id": "map-relocation",
                            "type": "map_resource_relocation",
                            "spec": (
                                "sequel/content/map-resources/relocation.json"
                            ),
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        project_path = build_root / "sequel/project.json"
        project_path.write_text(
            json.dumps(
                {
                    "project_id": "combined-image-relocation-test",
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
        self.assertEqual(2, len(allocations))
        self.assertEqual(
            {"tile-assets", "map-resources"},
            {row["allocation_region"] for row in allocations},
        )
        self.assertLess(
            next(
                row["offset"]
                for row in allocations
                if row["allocation_region"] == "tile-assets"
            ),
            next(
                row["offset"]
                for row in allocations
                if row["allocation_region"] == "map-resources"
            ),
        )

    def test_automated_manifest_accepts_map_relocation_type(self):
        from tools import automated_test

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "map-relocation",
                        "type": "map_resource_relocation",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)
        self.assertEqual([], runner.summary()["failures"])


if __name__ == "__main__":
    unittest.main()
