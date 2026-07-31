from __future__ import annotations

import hashlib
import json
import shutil
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
CATALOG = Path("artifacts/cutscene-obj-v1/manifest.json")
ROM_BASE = 0x08000000


class ImportCutsceneObjBundleRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        self.catalog = json.loads((ROOT / CATALOG).read_text())
        self.resources = []
        for source in self.catalog["resources"]:
            resource_id = source["resource_id"]
            graphics = self.temp / f"resource_{resource_id}.4bpp.bin"
            palette = self.temp / f"resource_{resource_id}.bgr555.bin"
            graphics.write_bytes(
                lz77_decompress(
                    self.base,
                    int(source["gfx_pointer"], 16) - ROM_BASE,
                )
            )
            palette.write_bytes(
                lz77_decompress(
                    self.base,
                    int(source["palette_pointer"], 16) - ROM_BASE,
                )
            )
            self.resources.append(
                {
                    "id": resource_id,
                    "graphics_file": str(graphics),
                    "palette_file": str(palette),
                    "frames": [
                        {
                            "id": frame["frame_id"],
                            "components": [
                                {
                                    "tile_offset": frame["tile_offset"],
                                    "x_offset": frame["x_offset"],
                                    "y_offset": frame["y_offset"],
                                    "width": frame["width"],
                                    "height": frame["height"],
                                }
                            ],
                        }
                        for frame in source["frames"]
                    ],
                    "animations": [
                        {
                            "id": frame["frame_id"],
                            "keyframes": [
                                {
                                    "frame_id": frame["frame_id"],
                                    "duration_ticks": frame["duration_ticks"],
                                }
                            ],
                        }
                        for frame in source["frames"]
                    ],
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
                    "schema": "cutscene-obj-bundle-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
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
                    "region": "cutscene-obj-bundle",
                    "region_owner": "cutscene_obj_resources",
                    "resources": (
                        resources if resources is not None else self.resources
                    ),
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_four_ids_ten_frames_and_all_source_references(self):
        from tools.import_cutscene_obj_bundle_relocations import (
            catalog_cutscene_obj_bundle,
        )

        catalog = catalog_cutscene_obj_bundle(ROOT, self.base)

        self.assertEqual(4, catalog["resource_count"])
        self.assertEqual([2, 2, 2, 4], catalog["frame_counts"])
        self.assertEqual(10, catalog["frame_count"])
        self.assertEqual(10, catalog["animation_count"])
        self.assertEqual(256, catalog["maximum_safe_graphics_tiles"])
        self.assertEqual(0x300, catalog["runtime_tile_base"])
        self.assertEqual(4, catalog["runtime_loader_call_count"])
        self.assertEqual(
            {
                "graphics": 4,
                "palette": 4,
                "definition_table": 4,
                "animation_table": 4,
                "definition": 10,
                "animation": 10,
            },
            catalog["pointer_reference_counts"],
        )
        self.assertEqual(36, catalog["pointer_reference_count"])
        self.assertEqual([], catalog["unexpected_pointer_offsets"])

    def test_registry_reserves_cutscene_obj_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        cutscene = regions.require(
            "cutscene-obj-bundle",
            "cutscene_obj_resources",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xBA0000, 0xBB0000), (cutscene.start, cutscene.end))
        self.assertEqual((0xBC0C00, 0xC00000), (future.start, future.end))

    def test_full_preservation_relocates_twelve_payloads_and_sixteen_roots(self):
        from tools.build_mod import apply_patch
        from tools.import_cutscene_obj_bundle_relocations import (
            resolve_cutscene_obj_bundle_relocation_patches,
        )
        from tools.patch_safety import PatchSafetyGate

        patches = resolve_cutscene_obj_bundle_relocation_patches(
            ROOT,
            self._write_spec(),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [row for row in patches if "allocation" in row]
        redirects = [
            row
            for row in patches
            if row.get("asset_type") == "cutscene_obj_bundle_pointer"
        ]
        self.assertEqual(12, len(allocations))
        self.assertEqual(16, len(redirects))
        self.assertEqual(
            {"graphics": 4, "palette": 4, "resource_bundle": 4},
            {
                role: sum(row["resource_type"] == role for row in allocations)
                for role in ("graphics", "palette", "resource_bundle")
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
        for resource_id in range(4):
            resource_pair = 0x53DF70 + resource_id * 8
            sprite_pair = 0x53DF90 + resource_id * 8
            pointers = [
                int.from_bytes(output[offset : offset + 4], "little")
                for offset in (
                    resource_pair,
                    resource_pair + 4,
                    sprite_pair,
                    sprite_pair + 4,
                )
            ]
            self.assertTrue(
                all(
                    0x08BA0000 <= pointer < 0x08BB0000
                    for pointer in pointers
                )
            )

    def test_256_tiles_variable_components_and_timeline_are_supported(self):
        from tools.import_cutscene_obj_bundle_relocations import (
            resolve_cutscene_obj_bundle_relocation_patches,
        )

        resources = json.loads(json.dumps(self.resources))
        graphics = Path(resources[0]["graphics_file"])
        graphics.write_bytes(graphics.read_bytes() + bytes(128 * 32))
        resources[0]["frames"][1]["components"][0]["tile_offset"] = 192
        resources[0]["frames"][0]["components"].append(
            {
                **resources[0]["frames"][0]["components"][0],
                "tile_offset": 64,
                "x_offset": 32,
            }
        )
        resources[0]["animations"][0]["keyframes"] = [
            {"frame_id": 0, "duration_ticks": 12},
            {"frame_id": 1, "duration_ticks": 3},
        ]

        patches = resolve_cutscene_obj_bundle_relocation_patches(
            ROOT,
            self._write_spec(resources=resources, name="maximum.json"),
            rom=self.base,
            layout=self.layout,
        )
        resource = next(
            row
            for row in patches
            if row.get("resource_type") == "resource_bundle"
            and row.get("resource_id") == 0
        )
        graphics_patch = next(
            row
            for row in patches
            if row.get("resource_type") == "graphics"
            and row.get("resource_id") == 0
        )

        self.assertEqual(256, graphics_patch["tile_count"])
        self.assertEqual([2, 1], resource["component_counts"])
        self.assertEqual([2, 1], resource["keyframe_counts"])

    def test_unsupported_capacity_shape_frame_count_and_id_fail_atomically(self):
        from tools.import_cutscene_obj_bundle_relocations import (
            resolve_cutscene_obj_bundle_relocation_patches,
        )

        resources = json.loads(json.dumps(self.resources))
        graphics = self.temp / "resource_0_257_tiles.4bpp.bin"
        graphics.write_bytes(
            Path(resources[0]["graphics_file"]).read_bytes()
            + bytes(129 * 32)
        )
        resources[0]["graphics_file"] = str(graphics)
        with self.assertRaisesRegex(ValueError, "1..256"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(resources=resources, name="257-tiles.json"),
                rom=self.base,
                layout=self.layout,
            )

        resources = json.loads(json.dumps(self.resources))
        resources[0]["frames"][1]["components"][0]["tile_offset"] = 65
        with self.assertRaisesRegex(ValueError, "tile range"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(resources=resources, name="bad-range.json"),
                rom=self.base,
                layout=self.layout,
            )

        resources = json.loads(json.dumps(self.resources))
        resources[0]["frames"][0]["components"][0]["height"] = 8
        with self.assertRaisesRegex(ValueError, "supported GBA OBJ shape"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(resources=resources, name="bad-shape.json"),
                rom=self.base,
                layout=self.layout,
            )

        resources = json.loads(json.dumps(self.resources))
        resources[0]["frames"][0]["components"].extend(
            [
                dict(resources[0]["frames"][0]["components"][0]),
                dict(resources[0]["frames"][0]["components"][0]),
            ]
        )
        with self.assertRaisesRegex(ValueError, "1..2 components"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(
                    resources=resources,
                    name="three-components.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

        resources = json.loads(json.dumps(self.resources))
        resources[0]["animations"][0]["keyframes"] = []
        with self.assertRaisesRegex(ValueError, "non-empty keyframes"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(resources=resources, name="empty-timeline.json"),
                rom=self.base,
                layout=self.layout,
            )

        resources = json.loads(json.dumps(self.resources))
        resources[0]["animations"][0]["keyframes"][0]["frame_id"] = 2
        with self.assertRaisesRegex(ValueError, "frame ID"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(resources=resources, name="bad-keyframe.json"),
                rom=self.base,
                layout=self.layout,
            )

        resources = json.loads(json.dumps(self.resources))
        resources[0]["frames"].pop()
        with self.assertRaisesRegex(ValueError, "fixed frame counts"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(resources=resources, name="bad-frames.json"),
                rom=self.base,
                layout=self.layout,
            )

        resources = json.loads(json.dumps(self.resources))
        resources[-1]["id"] = 2
        with self.assertRaisesRegex(ValueError, "exactly IDs 0..3"):
            resolve_cutscene_obj_bundle_relocation_patches(
                ROOT,
                self._write_spec(resources=resources, name="bad-ids.json"),
                rom=self.base,
                layout=self.layout,
            )

    def test_region_overflow_fails_before_returning_patches(self):
        from tools.import_cutscene_obj_bundle_relocations import (
            resolve_cutscene_obj_bundle_relocation_patches,
        )

        registry = json.loads(
            (ROOT / "sequel/image-resource-regions.json").read_text()
        )
        cutscene = next(
            row
            for row in registry["regions"]
            if row["id"] == "cutscene-obj-bundle"
        )
        residual = next(
            row
            for row in registry["regions"]
            if row["id"] == "residual-lz77-graphics"
        )
        cutscene["end"] = "0xBA0004"
        residual["start"] = "0xBA0004"
        tiny = ImageResourceRegions.from_dict(registry, self.layout)

        with self.assertRaisesRegex(ValueError, "exceeds.*registered region"):
            resolve_cutscene_obj_bundle_relocation_patches(
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
                        "id": "cutscene-obj-bundle",
                        "type": "cutscene_obj_bundle_relocation",
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
            "sequel/content/cutscene-obj",
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
            ROOT / CATALOG.parent,
            build_root / CATALOG.parent,
        )
        spec = json.loads(self._write_spec().read_text())
        for resource in spec["resources"]:
            for field in ("graphics_file", "palette_file"):
                source = Path(resource[field])
                destination = (
                    build_root
                    / "sequel/content/cutscene-obj"
                    / source.name
                )
                destination.write_bytes(source.read_bytes())
                resource[field] = str(destination)
        spec_path = (
            build_root / "sequel/content/cutscene-obj/relocation.json"
        )
        spec_path.write_text(json.dumps(spec))
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "cutscene-obj-bundle",
                            "type": "cutscene_obj_bundle_relocation",
                            "spec": (
                                "sequel/content/cutscene-obj/"
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
                    "project_id": "cutscene-obj-bundle-test",
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
            12,
            sum(
                row["patch_class"] == "allocation"
                for row in report["applied_patches"]
            ),
        )


if __name__ == "__main__":
    unittest.main()
