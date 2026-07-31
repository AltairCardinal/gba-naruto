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
from tools.import_bg_resources import (
    CATALOG_PATH,
    _catalog_resources,
)
from tools.rom_layout import RomLayout


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class ImportBgResourceRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.catalog_path = ROOT / CATALOG_PATH
        self.catalog = json.loads(
            self.catalog_path.read_text(encoding="utf-8")
        )
        self.resources, _ = _catalog_resources(self.catalog, self.base)
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

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
                    for alias in resource["logical_aliases"]
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
                    "schema": "bg-resource-relocation-v1",
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
                    "region": "regular-bg",
                    "region_owner": "regular_bg_resources",
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_31_contents_36_payloads_and_36_references(self):
        from tools.import_bg_resource_relocations import (
            catalog_bg_relocation_payloads,
        )

        resources = catalog_bg_relocation_payloads(ROOT, self.base)

        self.assertEqual(31, len(resources))
        self.assertEqual(
            {"graphics": 11, "palette": 12, "tilemap": 8},
            {
                resource_type: sum(
                    row["resource_type"] == resource_type
                    for row in resources.values()
                )
                for resource_type in ("graphics", "palette", "tilemap")
            },
        )
        self.assertEqual(
            36,
            sum(len(row["physical_offsets"]) for row in resources.values()),
        )
        self.assertEqual(
            36,
            sum(len(row["pointer_aliases"]) for row in resources.values()),
        )
        self.assertFalse(
            any(
                row["unexpected_pointer_offsets"]
                for row in resources.values()
            )
        )

    def test_registry_reserves_worst_case_regular_bg_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        regular_bg = regions.require(
            "regular-bg",
            "regular_bg_resources",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )
        battle_effects = regions.require(
            "battle-effects",
            "battle_effect_resources",
        )

        self.assertEqual(
            (0xB00000, 0xB40000),
            (regular_bg.start, regular_bg.end),
        )
        self.assertEqual(
            (0xB40000, 0xB50000),
            (battle_effects.start, battle_effects.end),
        )
        self.assertEqual((0xBC0000, 0xC00000), (future.start, future.end))
        worst_case = sum(
            4
            + row["decompressed_size"]
            + (row["decompressed_size"] + 7) // 8
            + 3
            for row in self.resources.values()
        )
        self.assertLess(worst_case, regular_bg.end - regular_bg.start)

    def test_full_preservation_relocates_31_payloads_and_36_pointers(self):
        from tools.import_bg_resource_relocations import (
            resolve_bg_resource_relocation_patches,
        )

        patches = resolve_bg_resource_relocation_patches(
            ROOT,
            self._write_spec(
                [self._edit(row) for row in self.resources.values()]
            ),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [patch for patch in patches if "allocation" in patch]
        redirects = [
            patch
            for patch in patches
            if patch.get("asset_type") == "bg_resource_pointer"
        ]

        self.assertEqual(31, len(allocations))
        self.assertEqual(36, len(redirects))
        self.assertEqual(
            {"graphics": 11, "palette": 12, "tilemap": 8},
            {
                resource_type: sum(
                    patch["resource_type"] == resource_type
                    for patch in allocations
                )
                for resource_type in ("graphics", "palette", "tilemap")
            },
        )
        self.assertLessEqual(
            max(
                patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
                for patch in allocations
            ),
            0xB40000,
        )

    def test_alias_subset_relocates_without_touching_sibling_descriptor(self):
        from tools.import_bg_resource_relocations import (
            resolve_bg_resource_relocation_patches,
        )

        resource = next(
            row
            for row in self.resources.values()
            if row["resource_type"] == "graphics"
            and len(row["physical_offsets"]) == 2
        )
        source = ROOT / CATALOG_PATH.parent / resource["source_files"][0]
        content = bytearray(source.read_bytes())
        content[0] ^= 1
        edited = self.temp / "graphics.bin"
        edited.write_bytes(content)
        target = [resource["logical_aliases"][0]["table_pointer_offset"]]
        patches = resolve_bg_resource_relocation_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        source_file=edited,
                        target_pointer_offsets=target,
                    )
                ],
                "alias-split.json",
            ),
            rom=self.base,
            layout=self.layout,
        )

        allocations = [patch for patch in patches if "allocation" in patch]
        redirects = [
            patch
            for patch in patches
            if patch.get("asset_type") == "bg_resource_pointer"
        ]
        self.assertEqual(1, len(allocations))
        self.assertEqual(target, allocations[0]["target_pointer_offsets"])
        self.assertEqual(target, [patch["offset"] for patch in redirects])
        self.assertEqual(
            2,
            len(allocations[0]["all_pointer_offsets"]),
        )

    def test_invalid_alias_and_region_overflow_fail_atomically(self):
        from tools.import_bg_resource_relocations import (
            resolve_bg_resource_relocation_patches,
        )

        resource = next(iter(self.resources.values()))
        invalid = self._edit(
            resource,
            target_pointer_offsets=[0x100],
        )
        with self.assertRaisesRegex(ValueError, "not canonical"):
            resolve_bg_resource_relocation_patches(
                ROOT,
                self._write_spec([invalid], "invalid.json"),
                rom=self.base,
                layout=self.layout,
            )

        registry = json.loads(
            (ROOT / "sequel/image-resource-regions.json").read_text(
                encoding="utf-8"
            )
        )
        regular_bg = next(
            row for row in registry["regions"] if row["id"] == "regular-bg"
        )
        battle_effects = next(
            row
            for row in registry["regions"]
            if row["id"] == "battle-effects"
        )
        regular_bg["end"] = "0xB00004"
        battle_effects["start"] = "0xB00004"
        tiny_regions = ImageResourceRegions.from_dict(registry, self.layout)
        with self.assertRaisesRegex(ValueError, "exceeds.*registered region"):
            resolve_bg_resource_relocation_patches(
                ROOT,
                self._write_spec([self._edit(resource)], "overflow.json"),
                rom=self.base,
                layout=self.layout,
                regions=tiny_regions,
            )

    def test_duplicate_claim_and_cross_resource_violation_fail_atomically(self):
        from tools.import_bg_resource_relocations import (
            resolve_bg_resource_relocation_patches,
        )

        resource = next(iter(self.resources.values()))
        target = [resource["logical_aliases"][0]["table_pointer_offset"]]
        first = self._edit(
            resource,
            target_pointer_offsets=target,
        )
        duplicate = self._edit(
            resource,
            target_pointer_offsets=target,
        )
        duplicate["id"] += "-duplicate"
        with self.assertRaisesRegex(ValueError, "claimed twice"):
            resolve_bg_resource_relocation_patches(
                ROOT,
                self._write_spec(
                    [first, duplicate],
                    "duplicate-claim.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

        tilemap = next(
            row
            for row in self.resources.values()
            if row["resource_type"] == "tilemap"
            and any(
                alias["mode_flag"] == 0
                for alias in row["logical_aliases"]
            )
        )
        source = ROOT / CATALOG_PATH.parent / tilemap["source_files"][0]
        content = bytearray(source.read_bytes())
        first_cell = int.from_bytes(content[:2], "little")
        content[:2] = ((first_cell & 0x0FFF) | 0xF000).to_bytes(2, "little")
        invalid_tilemap = self.temp / "invalid-tilemap.bin"
        invalid_tilemap.write_bytes(content)
        with self.assertRaisesRegex(ValueError, "palette index"):
            resolve_bg_resource_relocation_patches(
                ROOT,
                self._write_spec(
                    [
                        self._edit(
                            tilemap,
                            source_file=invalid_tilemap,
                        )
                    ],
                    "invalid-linked-view.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

    def test_automated_manifest_accepts_bg_relocation_type(self):
        from tools import automated_test

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "regular-bg-relocation",
                        "type": "bg_resource_relocation",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)

        self.assertEqual([], runner.summary()["failures"])

    def test_unified_build_applies_bg_allocations_and_redirects(self):
        from tools import build_mod

        resource = next(
            row
            for row in self.resources.values()
            if row["resource_type"] == "graphics"
            and len(row["physical_offsets"]) == 2
        )
        build_root = self.temp / "build-root"
        for relative in (
            "rom",
            "sequel/patches",
            "sequel/content/bg-resources",
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
            build_root / "sequel/content/bg-resources/relocation.json"
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
                            "id": "regular-bg-relocation",
                            "type": "bg_resource_relocation",
                            "spec": (
                                "sequel/content/bg-resources/"
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
                    "project_id": "bg-relocation-test",
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
            if row.get("asset_type") == "bg_resource_pointer"
        ]
        self.assertEqual(1, len(allocations))
        self.assertEqual(2, len(redirects))
        self.assertEqual(
            {"regular-bg"},
            {row["allocation_region"] for row in allocations},
        )
        self.assertEqual(0x1000000, report["output_rom"]["size"])


if __name__ == "__main__":
    unittest.main()
