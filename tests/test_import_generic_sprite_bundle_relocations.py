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
STATIC_CATALOG = Path("artifacts/sprite-definition-assets-v2/manifest.json")
ANIMATION_CATALOG = Path(
    "artifacts/sprite-definition-animations-v1/manifest.json"
)


class ImportGenericSpriteBundleRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        self.static = json.loads((ROOT / STATIC_CATALOG).read_text())
        self.animations = json.loads((ROOT / ANIMATION_CATALOG).read_text())
        self.graphics = self.temp / "graphics.4bpp.bin"
        self.palette = self.temp / "palette.bgr555.bin"
        self.graphics.write_bytes(
            (
                ROOT
                / STATIC_CATALOG.parent
                / self.static["static_resources"]["graphics"]["output_bin"]
            ).read_bytes()
        )
        self.palette.write_bytes(
            (
                ROOT
                / STATIC_CATALOG.parent
                / self.static["static_resources"]["palette"]["output_bin"]
            ).read_bytes()
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _component(component: dict) -> dict:
        return {
            key: component[key]
            for key in (
                "tile_offset",
                "flag_02",
                "flag_03",
                "horizontal_position_input",
                "vertical_position_input",
                "width",
                "height",
                "transform_factor_0c",
                "transform_factor_0e",
                "unknown_10_byte",
                "oam_attribute_byte",
                "unknown_12",
            )
        }

    def _entries(self) -> list[dict]:
        return [
            {
                "id": entry["id"],
                "tile_base_offset": entry["tile_base_offset"],
                "components": [
                    self._component(component)
                    for component in entry["components"]
                ],
            }
            for entry in self.static["entries"]
        ]

    def _write_spec(
        self,
        *,
        graphics: Path | None = None,
        palette: Path | None = None,
        entries: list[dict] | None = None,
        name: str = "spec.json",
    ) -> Path:
        registry = ROOT / "sequel/image-resource-regions.json"
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "generic-sprite-bundle-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_static_catalog": STATIC_CATALOG.as_posix(),
                    "source_static_catalog_sha256": hashlib.sha256(
                        (ROOT / STATIC_CATALOG).read_bytes()
                    ).hexdigest(),
                    "source_animation_catalog": ANIMATION_CATALOG.as_posix(),
                    "source_animation_catalog_sha256": hashlib.sha256(
                        (ROOT / ANIMATION_CATALOG).read_bytes()
                    ).hexdigest(),
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        registry.read_bytes()
                    ).hexdigest(),
                    "region": "generic-sprite-bundle",
                    "region_owner": "generic_sprite_resources",
                    "graphics_file": str(graphics or self.graphics),
                    "palette_file": str(palette or self.palette),
                    "entries": entries if entries is not None else self._entries(),
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_fixed_43_ids_and_174_exact_pointer_references(self):
        from tools.import_generic_sprite_bundle_relocations import (
            catalog_generic_sprite_bundle,
        )

        catalog = catalog_generic_sprite_bundle(ROOT, self.base)

        self.assertEqual(43, catalog["entry_count"])
        self.assertEqual(45, catalog["component_count"])
        self.assertEqual(49, catalog["graphics_tile_count"])
        self.assertEqual(97, catalog["maximum_safe_graphics_tiles"])
        self.assertEqual(927, catalog["maximum_runtime_tile_base"])
        self.assertEqual(12, catalog["runtime_loader_call_count"])
        self.assertEqual([0x34E, 0x39F], catalog["runtime_tile_bases"])
        self.assertEqual(
            {
                "definition": 43,
                "animation_table": 43,
                "component_list": 43,
                "sequence": 43,
                "graphics": 1,
                "palette": 1,
            },
            catalog["pointer_reference_counts"],
        )
        self.assertEqual(174, catalog["pointer_reference_count"])
        self.assertEqual([], catalog["unexpected_pointer_offsets"])

    def test_registry_reserves_generic_sprite_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        sprite = regions.require(
            "generic-sprite-bundle",
            "generic_sprite_resources",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xB90000, 0xBA0000), (sprite.start, sprite.end))
        self.assertEqual((0xBC0400, 0xC00000), (future.start, future.end))

    def test_full_preservation_relocates_all_payloads_and_exact_references(self):
        from tools.build_mod import apply_patch
        from tools.extract_tileset import lz77_decompress
        from tools.import_generic_sprite_bundle_relocations import (
            resolve_generic_sprite_bundle_relocation_patches,
        )
        from tools.patch_safety import PatchSafetyGate

        patches = resolve_generic_sprite_bundle_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        redirects = [
            row
            for row in patches
            if row.get("asset_type") == "generic_sprite_bundle_pointer"
        ]
        tile_bases = [
            row
            for row in patches
            if row.get("asset_type") == "generic_sprite_tile_base"
        ]

        self.assertEqual(45, len(allocations))
        self.assertEqual(88, len(redirects))
        self.assertEqual(43, len(tile_bases))
        self.assertEqual(
            {"graphics": 1, "palette": 1, "entry_bundle": 43},
            {
                role: sum(row["resource_type"] == role for row in allocations)
                for role in ("graphics", "palette", "entry_bundle")
            },
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
        resource_allocations = {
            row["resource_type"]: row
            for row in allocations
            if row["resource_type"] in {"graphics", "palette"}
        }
        for role, expected in (
            ("graphics", self.graphics.read_bytes()),
            ("palette", self.palette.read_bytes()),
        ):
            encoded = bytes.fromhex(resource_allocations[role]["after_hex"])
            self.assertEqual(expected, lz77_decompress(encoded, 0))
        for entry in self.static["entries"]:
            pair = 0x53F140 + entry["id"] * 8
            definition, animation = (
                int.from_bytes(output[pair : pair + 4], "little"),
                int.from_bytes(output[pair + 4 : pair + 8], "little"),
            )
            self.assertGreaterEqual(definition - 0x08000000, 0xB90000)
            self.assertGreaterEqual(animation - 0x08000000, 0xB90000)

    def test_97_tile_graphics_and_variable_component_list_are_supported(self):
        from tools.import_generic_sprite_bundle_relocations import (
            resolve_generic_sprite_bundle_relocation_patches,
        )

        expanded = self.temp / "97-tiles.4bpp.bin"
        expanded.write_bytes(self.graphics.read_bytes() + bytes(48 * 32))
        entries = self._entries()
        entries[0]["components"].append(
            {
                **entries[0]["components"][0],
                "tile_offset": 96,
                "horizontal_position_input": 8,
            }
        )

        patches = resolve_generic_sprite_bundle_relocation_patches(
            ROOT,
            self._write_spec(
                graphics=expanded,
                entries=entries,
                name="expanded.json",
            ),
            rom=self.base,
            layout=self.layout,
        )
        entry_zero = next(
            row
            for row in patches
            if row.get("resource_type") == "entry_bundle"
            and row.get("entry_id") == 0
        )

        self.assertEqual(2, entry_zero["component_count"])
        self.assertEqual(97, next(
            row["tile_count"]
            for row in patches
            if row.get("resource_type") == "graphics"
        ))

    def test_98_tiles_invalid_component_and_invalid_id_set_fail_atomically(self):
        from tools.import_generic_sprite_bundle_relocations import (
            resolve_generic_sprite_bundle_relocation_patches,
        )

        too_large = self.temp / "98-tiles.4bpp.bin"
        too_large.write_bytes(self.graphics.read_bytes() + bytes(49 * 32))
        with self.assertRaisesRegex(ValueError, "1..97"):
            resolve_generic_sprite_bundle_relocation_patches(
                ROOT,
                self._write_spec(graphics=too_large, name="too-large.json"),
                rom=self.base,
                layout=self.layout,
            )

        entries = self._entries()
        entries[0]["components"][0]["tile_offset"] = 49
        with self.assertRaisesRegex(ValueError, "tile range"):
            resolve_generic_sprite_bundle_relocation_patches(
                ROOT,
                self._write_spec(entries=entries, name="bad-tile.json"),
                rom=self.base,
                layout=self.layout,
            )

        entries = self._entries()
        entries[0]["components"].extend(
            [dict(entries[0]["components"][0])] * 2
        )
        with self.assertRaisesRegex(ValueError, "1..2 components"):
            resolve_generic_sprite_bundle_relocation_patches(
                ROOT,
                self._write_spec(entries=entries, name="three-components.json"),
                rom=self.base,
                layout=self.layout,
            )

        entries = self._entries()
        entries[-1]["id"] = 41
        with self.assertRaisesRegex(ValueError, "exactly IDs 0..42"):
            resolve_generic_sprite_bundle_relocation_patches(
                ROOT,
                self._write_spec(entries=entries, name="duplicate-id.json"),
                rom=self.base,
                layout=self.layout,
            )

    def test_region_overflow_fails_before_returning_patches(self):
        from tools.import_generic_sprite_bundle_relocations import (
            resolve_generic_sprite_bundle_relocation_patches,
        )

        registry = json.loads(
            (ROOT / "sequel/image-resource-regions.json").read_text()
        )
        sprite = next(
            row
            for row in registry["regions"]
            if row["id"] == "generic-sprite-bundle"
        )
        cutscene = next(
            row
            for row in registry["regions"]
            if row["id"] == "cutscene-obj-bundle"
        )
        sprite["end"] = "0xB90004"
        cutscene["start"] = "0xB90004"
        tiny = ImageResourceRegions.from_dict(registry, self.layout)

        with self.assertRaisesRegex(ValueError, "exceeds.*registered region"):
            resolve_generic_sprite_bundle_relocation_patches(
                ROOT,
                self._write_spec(name="overflow.json"),
                rom=self.base,
                layout=self.layout,
                regions=tiny,
            )

    def test_automated_manifest_and_unified_build_accept_bundle_type(self):
        from tools import automated_test, build_mod

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "generic-sprite-bundle",
                        "type": "generic_sprite_bundle_relocation",
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
            "sequel/content/generic-sprites",
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
            ROOT / STATIC_CATALOG.parent,
            build_root / STATIC_CATALOG.parent,
        )
        shutil.copytree(
            ROOT / ANIMATION_CATALOG.parent,
            build_root / ANIMATION_CATALOG.parent,
        )
        spec = json.loads(self._write_spec().read_text())
        graphics = build_root / "sequel/content/generic-sprites/graphics.bin"
        palette = build_root / "sequel/content/generic-sprites/palette.bin"
        graphics.write_bytes(self.graphics.read_bytes())
        palette.write_bytes(self.palette.read_bytes())
        spec["graphics_file"] = str(graphics)
        spec["palette_file"] = str(palette)
        spec_path = build_root / "sequel/content/generic-sprites/relocation.json"
        spec_path.write_text(json.dumps(spec))
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "generic-sprite-bundle",
                            "type": "generic_sprite_bundle_relocation",
                            "spec": (
                                "sequel/content/generic-sprites/"
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
                    "project_id": "generic-sprite-bundle-test",
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
            45,
            sum(
                row["patch_class"] == "allocation"
                for row in report["applied_patches"]
            ),
        )


if __name__ == "__main__":
    unittest.main()
