from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.rom_layout import RomLayout


ROOT = Path(__file__).resolve().parents[1]


class ImageResourceRegionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )

    def test_real_registry_partitions_the_parent_without_gaps(self):
        from tools.image_resource_regions import ImageResourceRegions

        registry = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )

        self.assertEqual("sequel-image-assets", registry.parent.id)
        self.assertEqual(
            (0x800000, 0x980000, "tile_asset_resources"),
            (
                registry.require("tile-assets", "tile_asset_resources").start,
                registry.require("tile-assets", "tile_asset_resources").end,
                registry.require("tile-assets", "tile_asset_resources").owner,
            ),
        )
        self.assertEqual(
            (0x980000, 0xA80000, "map_resources"),
            (
                registry.require("map-resources", "map_resources").start,
                registry.require("map-resources", "map_resources").end,
                registry.require("map-resources", "map_resources").owner,
            ),
        )
        self.assertEqual(
            (0xA80000, 0xB00000, "menu_portrait_resources"),
            (
                registry.require(
                    "menu-portraits",
                    "menu_portrait_resources",
                ).start,
                registry.require(
                    "menu-portraits",
                    "menu_portrait_resources",
                ).end,
                registry.require(
                    "menu-portraits",
                    "menu_portrait_resources",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xB00000, 0xC00000),
            (
                registry.require(
                    "future-image-resources",
                    "sequel_image_assets",
                ).start,
                registry.require(
                    "future-image-resources",
                    "sequel_image_assets",
                ).end,
            ),
        )

    def test_overlap_gap_alignment_and_parent_mismatch_are_rejected(self):
        from tools.image_resource_regions import ImageResourceRegions

        source = json.loads(
            (ROOT / "sequel/image-resource-regions.json").read_text(
                encoding="utf-8"
            )
        )
        cases = {
            "overlap": lambda value: value["regions"][1].update(
                {"start": "0x970000"}
            ),
            "gap": lambda value: value["regions"][1].update(
                {"start": "0x990000"}
            ),
            "alignment": lambda value: value["regions"][0].update(
                {"end": "0x980001"}
            ),
            "parent": lambda value: value.update(
                {"parent_partition": "character-battle-visual-bundles"}
            ),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            for name, mutate in cases.items():
                payload = json.loads(json.dumps(source))
                mutate(payload)
                path = Path(temp_dir) / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(name=name), self.assertRaises(ValueError):
                    ImageResourceRegions.from_path(path, self.layout)

    def test_unknown_or_wrong_owner_region_is_rejected(self):
        from tools.image_resource_regions import ImageResourceRegions

        registry = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        with self.assertRaisesRegex(ValueError, "unknown image resource region"):
            registry.require("missing", "nobody")
        with self.assertRaisesRegex(ValueError, "owner mismatch"):
            registry.require("tile-assets", "map_resources")


if __name__ == "__main__":
    unittest.main()
