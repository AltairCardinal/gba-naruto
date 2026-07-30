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
CATALOG_PATH = Path("artifacts/tile-assets-bg-v2/manifest.json")
sys.path.insert(0, str(ROOT / "tools"))


class ImportTileAssetResourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _resources(self):
        from tools.import_tile_asset_resources import (
            catalog_tile_asset_resources,
        )

        return catalog_tile_asset_resources(ROOT, self.base)

    def _write_spec(
        self,
        edits: list[dict],
        name: str = "spec.json",
    ) -> Path:
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "tile-asset-resource-import-v2",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_catalog": CATALOG_PATH.as_posix(),
                    "source_catalog_sha256": hashlib.sha256(
                        (ROOT / CATALOG_PATH).read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        (
                            ROOT / "sequel/image-resource-regions.json"
                        ).read_bytes()
                    ).hexdigest(),
                    "region": "tile-assets",
                    "region_owner": "tile_asset_resources",
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _edit(resource: dict, **extra) -> dict:
        return {
            "id": f"{resource['resource_type']}-{resource['source_offset']:06x}",
            "resource_type": resource["resource_type"],
            "source_pointer": resource["source_pointer"],
            "source_sha256": resource["source_sha256"],
            "expected_pointer_offsets": [
                row["pointer_offset"] for row in resource["logical_aliases"]
            ],
            **extra,
        }

    def test_catalog_closes_all_323_resources_and_709_pointer_references(self):
        resources = self._resources()
        self.assertEqual(323, len(resources))
        self.assertEqual(
            {"graphics": 107, "tilemap": 108, "palette": 108},
            {
                kind: sum(
                    row["resource_type"] == kind
                    for row in resources.values()
                )
                for kind in ("graphics", "tilemap", "palette")
            },
        )
        self.assertEqual(
            709,
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

    def test_v1_spec_is_rejected_after_region_contract_upgrade(self):
        from tools.import_tile_asset_resources import (
            resolve_tile_asset_resource_patches,
        )

        resource = next(iter(self._resources().values()))
        spec_path = self._write_spec([self._edit(resource)])
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["schema"] = "tile-asset-resource-import-v1"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            "expected schema tile-asset-resource-import-v2",
        ):
            resolve_tile_asset_resource_patches(
                ROOT,
                spec_path,
                rom=self.base,
                layout=self.layout,
            )

    def test_preservation_relocation_allocates_and_redirects_every_alias(self):
        from tools.import_tile_asset_resources import (
            resolve_tile_asset_resource_patches,
        )

        resource = max(
            (
                row
                for row in self._resources().values()
                if row["resource_type"] == "graphics"
            ),
            key=lambda row: len(row["logical_aliases"]),
        )
        patches = resolve_tile_asset_resource_patches(
            ROOT,
            self._write_spec([self._edit(resource)]),
            rom=self.base,
            layout=self.layout,
        )
        allocation = patches[0]
        redirects = patches[1:]
        self.assertEqual("tile_asset_resource", allocation["asset_type"])
        self.assertEqual(0x800000, allocation["offset"])
        self.assertEqual(
            "sequel-image-assets",
            allocation["allocation"]["partition"],
        )
        self.assertEqual("tile-assets", allocation["allocation"]["region"])
        self.assertEqual(
            resource["source_content"],
            lz77_decompress(bytes.fromhex(allocation["after_hex"]), 0),
        )
        self.assertEqual(
            len(resource["logical_aliases"]),
            len(redirects),
        )
        self.assertEqual(
            {
                row["pointer_offset"] for row in resource["logical_aliases"]
            },
            {row["offset"] for row in redirects},
        )
        self.assertTrue(
            all(
                row["asset_type"] == "tile_asset_resource_pointer"
                for row in redirects
            )
        )

    def test_variable_length_graphics_and_alias_split_are_supported(self):
        from tools.import_tile_asset_resources import (
            resolve_tile_asset_resource_patches,
        )

        resource = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "graphics"
            and len(row["logical_aliases"]) > 1
            and row["bits_per_pixel"] == [4]
        )
        replacement = resource["source_content"] + bytes(32)
        source = self.temp / "expanded-graphics.bin"
        source.write_bytes(replacement)
        target = [resource["logical_aliases"][0]["pointer_offset"]]
        patches = resolve_tile_asset_resource_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        content_file=str(source),
                        content_sha256=hashlib.sha256(replacement).hexdigest(),
                        target_pointer_offsets=target,
                    )
                ]
            ),
            rom=self.base,
            layout=self.layout,
        )
        self.assertEqual(2, len(patches))
        self.assertEqual(replacement, lz77_decompress(
            bytes.fromhex(patches[0]["after_hex"]),
            0,
        ))
        self.assertEqual(target, [patches[1]["offset"]])

    def test_invalid_palette_and_cross_layer_tile_index_are_rejected(self):
        from tools.import_tile_asset_resources import (
            resolve_tile_asset_resource_patches,
        )

        palette = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "palette"
        )
        bad_palette = self.temp / "bad-palette.bin"
        bad_palette.write_bytes(palette["source_content"] + b"\0\0")
        with self.assertRaisesRegex(ValueError, "palette size"):
            resolve_tile_asset_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            palette,
                            content_file=str(bad_palette),
                        )
                    ],
                    "bad-palette.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

    def test_8bpp_pixels_and_tilemap_reserved_palette_bits_are_validated(self):
        from tools.import_tile_asset_resources import (
            resolve_tile_asset_resource_patches,
        )

        graphics = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "graphics"
            and row["bits_per_pixel"] == [8]
        )
        content = bytearray(graphics["source_content"])
        content[0] = 0xFF
        bad_graphics = self.temp / "bad-8bpp-graphics.bin"
        bad_graphics.write_bytes(content)
        with self.assertRaisesRegex(ValueError, "pixel index"):
            resolve_tile_asset_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            graphics,
                            content_file=str(bad_graphics),
                        )
                    ],
                    "bad-8bpp-graphics.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

        tilemap = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "tilemap"
            and row["bits_per_pixel"] == [8]
        )
        content = bytearray(tilemap["source_content"])
        first = int.from_bytes(content[:2], "little")
        content[:2] = (first | 0x1000).to_bytes(2, "little")
        bad_tilemap = self.temp / "bad-8bpp-tilemap.bin"
        bad_tilemap.write_bytes(content)
        with self.assertRaisesRegex(ValueError, "palette bank"):
            resolve_tile_asset_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            tilemap,
                            content_file=str(bad_tilemap),
                        )
                    ],
                    "bad-8bpp-tilemap.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

        tilemap = next(
            row
            for row in self._resources().values()
            if row["resource_type"] == "tilemap"
            and all(
                alias["layer_status"] == "complete"
                for alias in row["logical_aliases"]
            )
        )
        content = bytearray(tilemap["source_content"])
        content[0:2] = (0x03FF).to_bytes(2, "little")
        bad_tilemap = self.temp / "bad-tilemap.bin"
        bad_tilemap.write_bytes(content)
        with self.assertRaisesRegex(ValueError, "tile index"):
            resolve_tile_asset_resource_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            tilemap,
                            content_file=str(bad_tilemap),
                        )
                    ],
                    "bad-tilemap.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

    def test_stale_alias_contract_and_partition_overflow_fail_atomically(self):
        from tools.import_tile_asset_resources import (
            resolve_tile_asset_resource_patches,
        )

        resource = next(iter(self._resources().values()))
        edit = self._edit(resource)
        edit["expected_pointer_offsets"] = []
        with self.assertRaisesRegex(ValueError, "pointer offset contract"):
            resolve_tile_asset_resource_patches(
                ROOT,
                self._write_spec([edit], "stale.json"),
                rom=self.base,
                layout=self.layout,
            )

        payload = json.loads(
            (ROOT / "sequel/image-resource-regions.json").read_text(
                encoding="utf-8"
            )
        )
        payload["regions"][0]["end"] = "0x800004"
        payload["regions"][1]["start"] = "0x800004"
        tiny_regions = ImageResourceRegions.from_dict(payload, self.layout)
        with self.assertRaisesRegex(ValueError, "partition capacity"):
            resolve_tile_asset_resource_patches(
                ROOT,
                self._write_spec([self._edit(resource)], "overflow.json"),
                rom=self.base,
                layout=self.layout,
                regions=tiny_regions,
            )

    def test_unified_build_applies_tile_asset_allocation_and_redirects(self):
        from tools import build_mod

        resource = max(
            self._resources().values(),
            key=lambda row: len(row["logical_aliases"]),
        )
        build_root = self.temp / "build-root"
        (build_root / "rom").mkdir(parents=True)
        (build_root / "sequel/patches").mkdir(parents=True)
        (build_root / "sequel/content/tile-assets").mkdir(parents=True)
        (build_root / "artifacts/tile-assets-bg-v2").mkdir(parents=True)
        (build_root / "rom/custom-base.gba").write_bytes(self.base)
        (build_root / "sequel/rom-layout.json").write_bytes(
            (ROOT / "sequel/rom-layout.json").read_bytes()
        )
        (build_root / "sequel/image-resource-regions.json").write_bytes(
            (ROOT / "sequel/image-resource-regions.json").read_bytes()
        )
        (build_root / CATALOG_PATH).write_bytes(
            (ROOT / CATALOG_PATH).read_bytes()
        )
        local_spec = (
            build_root / "sequel/content/tile-assets/relocation.json"
        )
        local_spec.write_text(
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
                            "id": "tile-assets-relocation",
                            "type": "tile_asset_resource",
                            "spec": "sequel/content/tile-assets/relocation.json",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        project = {
            "project_id": "tile-assets-relocation-build-test",
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
        project_path = build_root / "sequel/project.json"
        project_path.write_text(json.dumps(project), encoding="utf-8")

        with mock.patch.object(build_mod, "ROOT", build_root):
            report = build_mod.build(project_path)

        self.assertEqual(0x1000000, report["output_rom"]["size"])
        self.assertEqual(1, report["patch_class_counts"]["allocation"])
        allocation = next(
            row
            for row in report["applied_patches"]
            if row.get("asset_type") == "tile_asset_resource"
        )
        self.assertEqual(
            "sequel-image-assets",
            allocation["allocation_partition"],
        )
        self.assertEqual(
            len(resource["logical_aliases"]),
            sum(
                row.get("asset_type") == "tile_asset_resource_pointer"
                for row in report["applied_patches"]
            ),
        )

    def test_automated_manifest_accepts_tile_asset_resource_type(self):
        from tools import automated_test

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "tile-assets-relocation",
                        "type": "tile_asset_resource",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)

        self.assertEqual([], runner.summary()["failures"])


if __name__ == "__main__":
    unittest.main()
