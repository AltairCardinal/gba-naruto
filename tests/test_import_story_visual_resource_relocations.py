from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from tools.build_mod import apply_patch
from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout


class ImportStoryVisualResourceRelocationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.layout = RomLayout.from_path(
            ROOT / "sequel/rom-layout.json",
            self.base,
        )
        self.registry_path = ROOT / "sequel/image-resource-regions.json"
        self.regions = ImageResourceRegions.from_path(
            self.registry_path,
            self.layout,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_catalog_closes_all_story_visual_payloads_and_exact_references(self):
        from tools.import_story_visual_resource_relocations import (
            catalog_story_visual_relocation_payloads,
        )

        resources = catalog_story_visual_relocation_payloads(ROOT, self.base)

        self.assertEqual(49, len(resources))
        self.assertEqual(
            {"graphics": 24, "palette": 1, "tilemap": 24},
            {
                resource_type: sum(
                    resource["resource_type"] == resource_type
                    for resource in resources.values()
                )
                for resource_type in ("graphics", "palette", "tilemap")
            },
        )
        self.assertEqual(
            72,
            sum(
                len(resource["physical_offsets"])
                for resource in resources.values()
            ),
        )
        self.assertEqual(
            72,
            sum(
                len(resource["pointer_aliases"])
                for resource in resources.values()
            ),
        )
        self.assertFalse(
            any(
                resource["unexpected_pointer_offsets"]
                for resource in resources.values()
            )
        )
        palette = next(
            resource
            for resource in resources.values()
            if resource["resource_type"] == "palette"
        )
        self.assertEqual(24, len(palette["physical_offsets"]))
        self.assertEqual(24, len(palette["pointer_aliases"]))

    def _resources(self) -> dict:
        from tools.import_story_visual_resource_relocations import (
            catalog_story_visual_relocation_payloads,
        )

        return catalog_story_visual_relocation_payloads(ROOT, self.base)

    def _write_spec(
        self,
        resources: dict,
        *,
        replacements: dict[tuple[str, str], bytes] | None = None,
        target_offsets: dict[tuple[str, str], list[int]] | None = None,
        name: str = "spec.json",
    ) -> Path:
        from tools.import_story_visual_resource_relocations import (
            CATALOG_PATH,
            CATALOG_SHA256,
        )

        replacements = replacements or {}
        target_offsets = target_offsets or {}
        edits = []
        ordered = sorted(
            resources.items(),
            key=lambda item: (
                min(item[1]["physical_offsets"]),
                item[1]["resource_type"],
            ),
        )
        for index, (key, resource) in enumerate(ordered):
            source = self.temp / f"source-{index:02d}.bin"
            source.write_bytes(replacements.get(key, resource["content"]))
            edit = {
                "id": f"{resource['resource_type']}-{index:02d}",
                "resource_type": resource["resource_type"],
                "resource_sha256": resource["resource_sha256"],
                "source_file": str(source),
                "expected": {
                    "decompressed_size": resource["decompressed_size"],
                    "physical_offsets": resource["physical_offsets"],
                    "pointer_offsets": sorted(
                        alias["table_pointer_offset"]
                        for alias in resource["pointer_aliases"]
                    ),
                },
            }
            if key in target_offsets:
                edit["target_pointer_offsets"] = target_offsets[key]
            edits.append(edit)
        path = self.temp / name
        path.write_text(
            json.dumps(
                {
                    "schema": "story-visual-resource-relocation-v1",
                    "base_rom_sha256": hashlib.sha256(self.base).hexdigest(),
                    "source_catalog": CATALOG_PATH.as_posix(),
                    "source_catalog_sha256": CATALOG_SHA256,
                    "partition": "sequel-image-assets",
                    "owner": "sequel_image_assets",
                    "region_registry": "sequel/image-resource-regions.json",
                    "region_registry_sha256": hashlib.sha256(
                        self.registry_path.read_bytes()
                    ).hexdigest(),
                    "region": "story-visual-layers",
                    "region_owner": "story_visual_resources",
                    "edits": edits,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_full_relocation_allocates_49_payloads_and_rewrites_72_pointers(self):
        from tools.import_story_visual_resource_relocations import (
            resolve_story_visual_resource_relocation_patches,
        )

        resources = self._resources()
        spec = self._write_spec(resources)
        patches = resolve_story_visual_resource_relocation_patches(
            ROOT,
            spec,
            rom=self.base,
            layout=self.layout,
            regions=self.regions,
        )
        allocations = [
            patch
            for patch in patches
            if patch.get("asset_type")
            == "story_visual_resource_relocation"
        ]
        redirects = [
            patch
            for patch in patches
            if patch.get("asset_type") == "story_visual_resource_pointer"
        ]

        self.assertEqual(49, len(allocations))
        self.assertEqual(72, len(redirects))
        self.assertEqual(
            {"graphics": 24, "palette": 1, "tilemap": 24},
            {
                role: sum(
                    patch["resource_type"] == role for patch in allocations
                )
                for role in ("graphics", "palette", "tilemap")
            },
        )
        story_region = self.regions.require(
            "story-visual-layers",
            "story_visual_resources",
        )
        gate = PatchSafetyGate(
            self.base,
            layout=self.layout,
            image_regions=self.regions,
        )
        output = bytearray(self.layout.expanded_base())
        for patch in patches:
            apply_patch(output, patch, gate=gate)
        for patch in allocations:
            encoded = bytes.fromhex(patch["after_hex"])
            self.assertGreaterEqual(patch["offset"], story_region.start)
            self.assertLessEqual(patch["offset"] + len(encoded), story_region.end)
            self.assertEqual(
                hashlib.sha256(lz77_decompress(encoded, 0)).hexdigest(),
                patch["replacement_sha256"],
            )
        for patch in redirects:
            self.assertEqual(
                patch["new_pointer"],
                int.from_bytes(
                    output[patch["offset"] : patch["offset"] + 4],
                    "little",
                ),
            )

    def test_joint_graphics_and_tilemap_edit_may_expand_to_all_192_tiles(self):
        from tools.import_story_visual_resource_relocations import (
            STORY_TILE_BASE,
            resolve_story_visual_resource_relocation_patches,
        )

        resources = self._resources()
        layer_zero = {
            resource["resource_type"]: (key, resource)
            for key, resource in resources.items()
            if any(
                alias["layer_id"] == 0
                for alias in resource["pointer_aliases"]
            )
        }
        graphics_key, graphics = layer_zero["graphics"]
        tilemap_key, tilemap = layer_zero["tilemap"]
        replacement_graphics = bytes(
            (index * 73 + 19) & 0xFF for index in range(0x1800)
        )
        entries = [
            0xF000 | (STORY_TILE_BASE + index % 192)
            for index in range(1024)
        ]
        replacement_tilemap = struct.pack("<1024H", *entries)
        spec = self._write_spec(
            resources,
            replacements={
                graphics_key: replacement_graphics,
                tilemap_key: replacement_tilemap,
            },
            name="expanded.json",
        )

        patches = resolve_story_visual_resource_relocation_patches(
            ROOT,
            spec,
            rom=self.base,
            layout=self.layout,
            regions=self.regions,
        )
        graphics_patch = next(
            patch
            for patch in patches
            if patch.get("asset_type")
            == "story_visual_resource_relocation"
            and patch["resource_sha256"] == graphics["resource_sha256"]
        )
        tilemap_patch = next(
            patch
            for patch in patches
            if patch.get("asset_type")
            == "story_visual_resource_relocation"
            and patch["resource_sha256"] == tilemap["resource_sha256"]
        )
        self.assertEqual(0x1800, graphics_patch["decompressed_size"])
        self.assertEqual(0x800, tilemap_patch["decompressed_size"])
        self.assertGreater(
            graphics_patch["encoded_size"],
            graphics["compressed_sizes"][0],
        )

    def test_rejects_palette_bank_or_tile_coverage_that_breaks_linked_view(self):
        from tools.import_story_visual_resource_relocations import (
            resolve_story_visual_resource_relocation_patches,
        )

        resources = self._resources()
        tilemap_key, tilemap = next(
            (key, resource)
            for key, resource in resources.items()
            if resource["resource_type"] == "tilemap"
            and any(
                alias["layer_id"] == 0
                for alias in resource["pointer_aliases"]
            )
        )
        bad = bytearray(tilemap["content"])
        first = struct.unpack_from("<H", bad)[0]
        struct.pack_into("<H", bad, 0, first & 0x0FFF)
        spec = self._write_spec(
            resources,
            replacements={tilemap_key: bytes(bad)},
            name="bad-palette.json",
        )
        with self.assertRaisesRegex(ValueError, "palette bank 15"):
            resolve_story_visual_resource_relocation_patches(
                ROOT,
                spec,
                rom=self.base,
                layout=self.layout,
                regions=self.regions,
            )

        missing = struct.pack("<1024H", *([0xF140] * 1024))
        spec = self._write_spec(
            resources,
            replacements={tilemap_key: missing},
            name="bad-coverage.json",
        )
        with self.assertRaisesRegex(ValueError, "exact contiguous tile range"):
            resolve_story_visual_resource_relocation_patches(
                ROOT,
                spec,
                rom=self.base,
                layout=self.layout,
                regions=self.regions,
            )

    def test_shared_palette_aliases_may_split_without_claim_overlap(self):
        from tools.import_story_visual_resource_relocations import (
            resolve_story_visual_resource_relocation_patches,
        )

        resources = self._resources()
        palette_key, palette = next(
            (key, resource)
            for key, resource in resources.items()
            if resource["resource_type"] == "palette"
        )
        offsets = [
            alias["table_pointer_offset"]
            for alias in palette["pointer_aliases"]
        ]
        spec = self._write_spec(
            resources,
            target_offsets={palette_key: offsets[:12]},
            name="split-a.json",
        )
        payload = json.loads(spec.read_text(encoding="utf-8"))
        palette_edit = next(
            edit for edit in payload["edits"] if edit["resource_type"] == "palette"
        )
        second = dict(palette_edit)
        second["id"] = "palette-second-half"
        second["target_pointer_offsets"] = offsets[12:]
        second_path = self.temp / "palette-second.bin"
        second_path.write_bytes(bytes(reversed(palette["content"])))
        second["source_file"] = str(second_path)
        payload["edits"].append(second)
        spec.write_text(json.dumps(payload), encoding="utf-8")

        patches = resolve_story_visual_resource_relocation_patches(
            ROOT,
            spec,
            rom=self.base,
            layout=self.layout,
            regions=self.regions,
        )
        palette_allocations = [
            patch
            for patch in patches
            if patch.get("asset_type")
            == "story_visual_resource_relocation"
            and patch["resource_type"] == "palette"
        ]
        self.assertEqual(2, len(palette_allocations))
        self.assertEqual(
            [12, 12],
            sorted(
                len(patch["target_pointer_offsets"])
                for patch in palette_allocations
            ),
        )

    def test_shared_palette_aliases_reject_overlapping_claims(self):
        from tools.import_story_visual_resource_relocations import (
            resolve_story_visual_resource_relocation_patches,
        )

        resources = self._resources()
        palette_key, palette = next(
            (key, resource)
            for key, resource in resources.items()
            if resource["resource_type"] == "palette"
        )
        offsets = [
            alias["table_pointer_offset"]
            for alias in palette["pointer_aliases"]
        ]
        spec = self._write_spec(
            resources,
            target_offsets={palette_key: offsets[:12]},
            name="overlap-a.json",
        )
        payload = json.loads(spec.read_text(encoding="utf-8"))
        palette_edit = next(
            edit for edit in payload["edits"] if edit["resource_type"] == "palette"
        )
        overlapping = dict(palette_edit)
        overlapping["id"] = "palette-overlapping-claim"
        overlapping["target_pointer_offsets"] = offsets[6:18]
        replacement = self.temp / "palette-overlapping.bin"
        replacement.write_bytes(bytes(reversed(palette["content"])))
        overlapping["source_file"] = str(replacement)
        payload["edits"].append(overlapping)
        spec.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "claimed twice"):
            resolve_story_visual_resource_relocation_patches(
                ROOT,
                spec,
                rom=self.base,
                layout=self.layout,
                regions=self.regions,
            )

    def test_rejects_unknown_exact_reference_before_allocating(self):
        from tools import import_story_visual_resource_relocations as importer

        resources = self._resources()
        source_pointer = next(iter(resources.values()))["pointer_aliases"][0][
            "source_pointer"
        ]
        mutated = bytearray(self.base)
        mutated[0x100:0x104] = source_pointer.to_bytes(4, "little")
        mutated = bytes(mutated)
        spec = self._write_spec(resources, name="unknown-reference.json")
        payload = json.loads(spec.read_text(encoding="utf-8"))
        payload["base_rom_sha256"] = hashlib.sha256(mutated).hexdigest()
        spec.write_text(json.dumps(payload), encoding="utf-8")

        with mock.patch.object(
            importer,
            "ROM_SHA256",
            hashlib.sha256(mutated).hexdigest(),
        ):
            with self.assertRaisesRegex(ValueError, "unknown exact references"):
                importer.resolve_story_visual_resource_relocation_patches(
                    ROOT,
                    spec,
                    rom=mutated,
                    layout=self.layout,
                    regions=self.regions,
                )

    def test_rejects_valid_edits_when_aggregate_story_region_is_exhausted(self):
        from tools.import_story_visual_resource_relocations import (
            STORY_TILE_BASE,
            resolve_story_visual_resource_relocation_patches,
        )

        resources = self._resources()
        replacements = {}
        maximum_graphics = b"".join(
            hashlib.sha256(index.to_bytes(4, "little")).digest()
            for index in range(0x1800 // 32)
        )
        maximum_tilemap = struct.pack(
            "<1024H",
            *[
                0xF000 | (STORY_TILE_BASE + index % 192)
                for index in range(1024)
            ],
        )
        for key, resource in resources.items():
            if resource["resource_type"] == "graphics":
                replacements[key] = maximum_graphics
            elif resource["resource_type"] == "tilemap":
                replacements[key] = maximum_tilemap
        spec = self._write_spec(
            resources,
            replacements=replacements,
            name="capacity-exhaustion.json",
        )

        with self.assertRaisesRegex(ValueError, "exceeds its registered region"):
            resolve_story_visual_resource_relocation_patches(
                ROOT,
                spec,
                rom=self.base,
                layout=self.layout,
                regions=self.regions,
            )

    def test_automated_manifest_accepts_story_visual_relocation_type(self):
        from tools import automated_test

        runner = automated_test.TestRunner()
        with mock.patch.object(
            automated_test,
            "load_manifest",
            return_value={
                "patches": [
                    {
                        "id": "story-visual-relocation",
                        "type": "story_visual_resource_relocation",
                    }
                ]
            },
        ):
            automated_test.suite_manifest(runner)
        self.assertEqual([], runner.summary()["failures"])

    def test_unified_build_applies_story_allocation_and_pointer_redirect(self):
        from tools import build_mod

        resources = self._resources()
        resource = next(
            row
            for row in resources.values()
            if row["resource_type"] == "graphics"
        )
        key = (resource["resource_type"], resource["resource_sha256"])
        full_spec = self._write_spec(resources, name="build-spec.json")
        spec_payload = json.loads(full_spec.read_text(encoding="utf-8"))
        spec_payload["edits"] = [
            edit
            for edit in spec_payload["edits"]
            if (edit["resource_type"], edit["resource_sha256"]) == key
        ]

        build_root = self.temp / "build-root"
        for relative in (
            "rom",
            "sequel/patches",
            "sequel/content/story-visual-layers",
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
            ROOT / "artifacts/story-visual-layers-v1",
            build_root / "artifacts/story-visual-layers-v1",
        )
        spec_path = (
            build_root / "sequel/content/story-visual-layers/relocation.json"
        )
        spec_path.write_text(json.dumps(spec_payload), encoding="utf-8")
        (build_root / "sequel/patches/manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "patches": [
                        {
                            "id": "story-visual-relocation",
                            "type": "story_visual_resource_relocation",
                            "spec": (
                                "sequel/content/story-visual-layers/"
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
                    "project_id": "story-visual-relocation-test",
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
            if row.get("asset_type") == "story_visual_resource_pointer"
        ]
        self.assertEqual(1, len(allocations))
        self.assertEqual(1, len(redirects))
        self.assertEqual(
            {"story-visual-layers"},
            {row["allocation_region"] for row in allocations},
        )
        self.assertEqual(0x1000000, report["output_rom"]["size"])

    def test_registered_story_region_preserves_future_image_capacity(self):
        registry_path = ROOT / "sequel/image-resource-regions.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        regions = {row["id"]: row for row in registry["regions"]}

        self.assertEqual(
            {
                "id": "story-visual-layers",
                "owner": "story_visual_resources",
                "start": "0xB50000",
                "end": "0xB71000",
                "alignment": 4,
            },
            regions["story-visual-layers"],
        )
        self.assertEqual("0xBC0400", regions["future-image-resources"]["start"])
        self.assertEqual("0xC00000", regions["future-image-resources"]["end"])


if __name__ == "__main__":
    unittest.main()
