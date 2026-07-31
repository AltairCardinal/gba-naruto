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
            (0xB00000, 0xB40000, "regular_bg_resources"),
            (
                registry.require(
                    "regular-bg",
                    "regular_bg_resources",
                ).start,
                registry.require(
                    "regular-bg",
                    "regular_bg_resources",
                ).end,
                registry.require(
                    "regular-bg",
                    "regular_bg_resources",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xB40000, 0xB50000, "battle_effect_resources"),
            (
                registry.require(
                    "battle-effects",
                    "battle_effect_resources",
                ).start,
                registry.require(
                    "battle-effects",
                    "battle_effect_resources",
                ).end,
                registry.require(
                    "battle-effects",
                    "battle_effect_resources",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xB50000, 0xB71000, "story_visual_resources"),
            (
                registry.require(
                    "story-visual-layers",
                    "story_visual_resources",
                ).start,
                registry.require(
                    "story-visual-layers",
                    "story_visual_resources",
                ).end,
                registry.require(
                    "story-visual-layers",
                    "story_visual_resources",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xB71000, 0xB90000, "world_map_background_resources"),
            (
                registry.require(
                    "world-map-backgrounds",
                    "world_map_background_resources",
                ).start,
                registry.require(
                    "world-map-backgrounds",
                    "world_map_background_resources",
                ).end,
                registry.require(
                    "world-map-backgrounds",
                    "world_map_background_resources",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xB90000, 0xBA0000, "generic_sprite_resources"),
            (
                registry.require(
                    "generic-sprite-bundle",
                    "generic_sprite_resources",
                ).start,
                registry.require(
                    "generic-sprite-bundle",
                    "generic_sprite_resources",
                ).end,
                registry.require(
                    "generic-sprite-bundle",
                    "generic_sprite_resources",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xBA0000, 0xBB0000, "cutscene_obj_resources"),
            (
                registry.require(
                    "cutscene-obj-bundle",
                    "cutscene_obj_resources",
                ).start,
                registry.require(
                    "cutscene-obj-bundle",
                    "cutscene_obj_resources",
                ).end,
                registry.require(
                    "cutscene-obj-bundle",
                    "cutscene_obj_resources",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xBB0000, 0xBC0000, "residual_lz77_graphics"),
            (
                registry.require(
                    "residual-lz77-graphics",
                    "residual_lz77_graphics",
                ).start,
                registry.require(
                    "residual-lz77-graphics",
                    "residual_lz77_graphics",
                ).end,
                registry.require(
                    "residual-lz77-graphics",
                    "residual_lz77_graphics",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xBC0000, 0xBC0400, "direct_image_palettes"),
            (
                registry.require(
                    "direct-image-palettes",
                    "direct_image_palettes",
                ).start,
                registry.require(
                    "direct-image-palettes",
                    "direct_image_palettes",
                ).end,
                registry.require(
                    "direct-image-palettes",
                    "direct_image_palettes",
                ).owner,
            ),
        )
        self.assertEqual(
            (0xBC0400, 0xC00000),
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
