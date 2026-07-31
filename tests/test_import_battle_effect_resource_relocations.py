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
from tools.import_battle_effect_resources import (
    CATALOG_PATH,
    _catalog_resources,
)
from tools.rom_layout import RomLayout


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class ImportBattleEffectResourceRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.catalog_path = ROOT / CATALOG_PATH
        self.catalog = json.loads(
            self.catalog_path.read_text(encoding="utf-8")
        )
        self.resources = _catalog_resources(self.catalog, self.base)
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
                    "schema": "battle-effect-resource-relocation-v1",
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
                    "region": "battle-effects",
                    "region_owner": "battle_effect_resources",
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_catalog_closes_34_contents_35_payloads_and_36_references(self):
        from tools.import_battle_effect_resource_relocations import (
            catalog_battle_effect_relocation_payloads,
        )

        resources = catalog_battle_effect_relocation_payloads(
            ROOT,
            self.base,
        )

        self.assertEqual(34, len(resources))
        self.assertEqual(
            {"graphics": 17, "palette": 17},
            {
                role: sum(
                    row["resource_type"] == role
                    for row in resources.values()
                )
                for role in ("graphics", "palette")
            },
        )
        self.assertEqual(
            35,
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

    def test_registry_reserves_worst_case_battle_effect_region(self):
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            self.layout,
        )
        effects = regions.require(
            "battle-effects",
            "battle_effect_resources",
        )
        future = regions.require(
            "future-image-resources",
            "sequel_image_assets",
        )

        self.assertEqual((0xB40000, 0xB50000), (effects.start, effects.end))
        self.assertEqual((0xBC0000, 0xC00000), (future.start, future.end))
        worst_case = sum(
            4
            + row["decompressed_size"]
            + (row["decompressed_size"] + 7) // 8
            + 3
            for row in self.resources.values()
        )
        self.assertLess(worst_case, effects.end - effects.start)

    def test_full_preservation_relocates_34_payloads_and_36_pointers(self):
        from tools.import_battle_effect_resource_relocations import (
            resolve_battle_effect_resource_relocation_patches,
        )

        patches = resolve_battle_effect_resource_relocation_patches(
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
            if patch.get("asset_type") == "battle_effect_resource_pointer"
        ]

        self.assertEqual(34, len(allocations))
        self.assertEqual(36, len(redirects))
        self.assertEqual(
            {"graphics": 17, "palette": 17},
            {
                role: sum(
                    patch["resource_type"] == role
                    for patch in allocations
                )
                for role in ("graphics", "palette")
            },
        )
        self.assertLessEqual(
            max(
                patch["offset"] + len(bytes.fromhex(patch["after_hex"]))
                for patch in allocations
            ),
            0xB50000,
        )

    def test_shared_source_pointer_alias_can_split_one_group(self):
        from tools.import_battle_effect_resource_relocations import (
            resolve_battle_effect_resource_relocation_patches,
        )

        resource = next(
            row
            for row in self.resources.values()
            if row["resource_type"] == "graphics"
            and len(row["physical_offsets"]) == 1
            and len(row["logical_aliases"]) == 2
            and {
                alias["group_id"] for alias in row["logical_aliases"]
            }
            == {2, 3}
        )
        source = ROOT / CATALOG_PATH.parent / resource["source_files"][0]
        content = bytearray(source.read_bytes())
        content[0] ^= 1
        edited = self.temp / "graphics.bin"
        edited.write_bytes(content)
        target = [resource["logical_aliases"][0]["table_pointer_offset"]]
        patches = resolve_battle_effect_resource_relocation_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        source_file=edited,
                        target_pointer_offsets=target,
                    )
                ],
                "shared-pointer-split.json",
            ),
            rom=self.base,
            layout=self.layout,
        )
        allocations = [patch for patch in patches if "allocation" in patch]
        redirects = [
            patch
            for patch in patches
            if patch.get("asset_type") == "battle_effect_resource_pointer"
        ]

        self.assertEqual(1, len(allocations))
        self.assertEqual(1, len(redirects))
        self.assertEqual(target, allocations[0]["target_pointer_offsets"])
        self.assertEqual(2, len(allocations[0]["all_pointer_offsets"]))
        self.assertEqual(
            {2},
            {
                alias["group_id"]
                for alias in allocations[0]["logical_aliases"]
            },
        )

    def test_duplicate_palette_content_can_merge_or_split_groups_16_and_17(self):
        from tools.import_battle_effect_resource_relocations import (
            resolve_battle_effect_resource_relocation_patches,
        )

        resource = next(
            row
            for row in self.resources.values()
            if row["resource_type"] == "palette"
            and len(row["physical_offsets"]) == 2
            and {
                alias["group_id"] for alias in row["logical_aliases"]
            }
            == {16, 17}
        )
        default_patches = resolve_battle_effect_resource_relocation_patches(
            ROOT,
            self._write_spec(
                [self._edit(resource)],
                "duplicate-palette-default.json",
            ),
            rom=self.base,
            layout=self.layout,
        )
        default_allocations = [
            patch for patch in default_patches if "allocation" in patch
        ]
        default_redirects = [
            patch
            for patch in default_patches
            if patch.get("asset_type") == "battle_effect_resource_pointer"
        ]

        self.assertEqual(1, len(default_allocations))
        self.assertEqual(2, len(default_redirects))
        self.assertEqual(2, len(default_allocations[0]["physical_offsets"]))
        self.assertEqual(
            {16, 17},
            {
                alias["group_id"]
                for alias in default_allocations[0]["logical_aliases"]
            },
        )

        target_alias = next(
            alias
            for alias in resource["logical_aliases"]
            if alias["group_id"] == 16
        )
        target = [target_alias["table_pointer_offset"]]
        split_patches = resolve_battle_effect_resource_relocation_patches(
            ROOT,
            self._write_spec(
                [
                    self._edit(
                        resource,
                        target_pointer_offsets=target,
                    )
                ],
                "duplicate-palette-split.json",
            ),
            rom=self.base,
            layout=self.layout,
        )
        split_allocations = [
            patch for patch in split_patches if "allocation" in patch
        ]
        split_redirects = [
            patch
            for patch in split_patches
            if patch.get("asset_type") == "battle_effect_resource_pointer"
        ]

        self.assertEqual(1, len(split_allocations))
        self.assertEqual(1, len(split_redirects))
        self.assertEqual(target, split_allocations[0]["target_pointer_offsets"])
        self.assertEqual(
            {16},
            {
                alias["group_id"]
                for alias in split_allocations[0]["logical_aliases"]
            },
        )

    def test_duplicate_claim_invalid_alias_and_region_overflow_fail(self):
        from tools.import_battle_effect_resource_relocations import (
            resolve_battle_effect_resource_relocation_patches,
        )

        resource = next(iter(self.resources.values()))
        target = [resource["logical_aliases"][0]["table_pointer_offset"]]
        first = self._edit(resource, target_pointer_offsets=target)
        duplicate = self._edit(resource, target_pointer_offsets=target)
        duplicate["id"] += "-duplicate"
        with self.assertRaisesRegex(ValueError, "claimed twice"):
            resolve_battle_effect_resource_relocation_patches(
                ROOT,
                self._write_spec([first, duplicate], "duplicate.json"),
                rom=self.base,
                layout=self.layout,
            )

        invalid = self._edit(
            resource,
            target_pointer_offsets=[0x100],
        )
        with self.assertRaisesRegex(ValueError, "not canonical"):
            resolve_battle_effect_resource_relocation_patches(
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
        effects = next(
            row
            for row in registry["regions"]
            if row["id"] == "battle-effects"
        )
        story = next(
            row
            for row in registry["regions"]
            if row["id"] == "story-visual-layers"
        )
        effects["end"] = "0xB40004"
        story["start"] = "0xB40004"
        tiny_regions = ImageResourceRegions.from_dict(registry, self.layout)
        with self.assertRaisesRegex(ValueError, "exceeds.*registered region"):
            resolve_battle_effect_resource_relocation_patches(
                ROOT,
                self._write_spec([self._edit(resource)], "overflow.json"),
                rom=self.base,
                layout=self.layout,
                regions=tiny_regions,
            )

    def test_invalid_graphics_format_fails_before_allocation(self):
        from tools.import_battle_effect_resource_relocations import (
            resolve_battle_effect_resource_relocation_patches,
        )

        resource = next(
            row
            for row in self.resources.values()
            if row["resource_type"] == "graphics"
        )
        invalid = self.temp / "invalid.bin"
        invalid.write_bytes(b"\x00" * (resource["decompressed_size"] - 1))
        with self.assertRaisesRegex(ValueError, "complete 32-byte"):
            resolve_battle_effect_resource_relocation_patches(
                ROOT,
                self._write_spec(
                    [self._edit(resource, source_file=invalid)],
                    "invalid-format.json",
                ),
                rom=self.base,
                layout=self.layout,
            )

    def test_automated_manifest_accepts_effect_relocation_type(self):
        from tools import automated_test

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "battle-effects-relocation",
                        "type": "battle_effect_resource_relocation",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)
        self.assertEqual([], runner.summary()["failures"])

    def test_unified_build_applies_effect_allocations_and_redirects(self):
        from tools import build_mod

        resource = next(
            row
            for row in self.resources.values()
            if len(row["logical_aliases"]) == 2
        )
        build_root = self.temp / "build-root"
        for relative in (
            "rom",
            "sequel/patches",
            "sequel/content/battle-effects",
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
            / "sequel/content/battle-effects/relocation.json"
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
                            "id": "battle-effects-relocation",
                            "type": "battle_effect_resource_relocation",
                            "spec": (
                                "sequel/content/battle-effects/"
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
                    "project_id": "battle-effect-relocation-test",
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
            if row.get("asset_type") == "battle_effect_resource_pointer"
        ]
        self.assertEqual(1, len(allocations))
        self.assertEqual(2, len(redirects))
        self.assertEqual(
            {"battle-effects"},
            {row["allocation_region"] for row in allocations},
        )
        self.assertEqual(0x1000000, report["output_rom"]["size"])


if __name__ == "__main__":
    unittest.main()
