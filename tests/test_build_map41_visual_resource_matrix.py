from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom/base.gba"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


class BuildMap41VisualResourceMatrixTests(unittest.TestCase):
    def test_builds_four_single_factor_roms_with_one_shared_patch_topology(self):
        from tools.build_map41_visual_resource_matrix import build_matrix_roms

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "matrix"
            manifest = build_matrix_roms(ROOT, output)

            self.assertEqual("map41-visual-resource-matrix-build-v1", manifest["schema"])
            self.assertEqual(
                ["baseline", "tile_graphics", "bg_palette", "metatile_definitions"],
                list(manifest["variants"]),
            )
            self.assertTrue(manifest["isolation"]["shared_patch_topology"])
            self.assertTrue(manifest["isolation"]["only_map41_headers_redirected"])
            self.assertEqual(
                {
                    "tile_graphics": {
                        "source_pointer": "0x0811B4E0",
                        "target_header_pointer_offset": "0x0053DE34",
                        "decoded_byte_offsets": [0x2A20],
                        "before_hex": "34",
                        "after_hex": "35",
                    },
                    "bg_palette": {
                        "source_pointer": "0x0811DC1C",
                        "target_header_pointer_offset": "0x0053DE38",
                        "decoded_byte_offsets": [0x4A],
                        "before_hex": "0d",
                        "after_hex": "0c",
                    },
                    "metatile_definitions": {
                        "source_pointer": "0x0811DEB4",
                        "target_header_pointer_offset": "0x0053DE44",
                        "decoded_byte_offsets": [0x230],
                        "before_hex": "19",
                        "after_hex": "1a",
                    },
                },
                manifest["edits"],
            )

            baseline_resources = {
                resource_type: (output / "baseline" / f"{resource_type}.bin").read_bytes()
                for resource_type in manifest["resources"]
            }
            expected_diffs = {
                "tile_graphics": {"tile_graphics": [0x2A20]},
                "bg_palette": {"bg_palette": [0x4A]},
                "metatile_definitions": {"metatile_definitions": [0x230]},
            }
            for variant in ("tile_graphics", "bg_palette", "metatile_definitions"):
                for resource_type, baseline in baseline_resources.items():
                    candidate = (
                        output / variant / f"{resource_type}.bin"
                    ).read_bytes()
                    self.assertEqual(
                        expected_diffs[variant].get(resource_type, []),
                        _changed_offsets(baseline, candidate),
                    )

            base = BASE_ROM.read_bytes()
            target_offsets = {0x53DE34, 0x53DE38, 0x53DE44}
            pointer_sets = []
            topology_sets = []
            for variant, metadata in manifest["variants"].items():
                rom = (output / metadata["rom_path"]).read_bytes()
                self.assertEqual(0x1000000, len(rom))
                self.assertEqual(metadata["rom_sha256"], _sha256(rom))
                pointer_sets.append(
                    tuple(rom[offset : offset + 4] for offset in sorted(target_offsets))
                )
                topology_sets.append(
                    [
                        (
                            patch["kind"],
                            patch["offset"],
                            patch["resource_type"],
                            patch["target_header_pointer_offsets"],
                            patch["new_pointer"],
                        )
                        for patch in metadata["patch_ledger"]
                    ]
                )
                for resource in manifest["resources"].values():
                    for offset in resource["preserved_header_pointer_offsets"]:
                        self.assertEqual(
                            base[offset : offset + 4],
                            rom[offset : offset + 4],
                            f"{variant} changed preserved header 0x{offset:X}",
                        )
            self.assertTrue(all(pointers == pointer_sets[0] for pointers in pointer_sets))
            self.assertTrue(
                all(topology == topology_sets[0] for topology in topology_sets)
            )

    def test_rejects_non_contract_pixel_edit(self):
        from tools.build_map41_visual_resource_matrix import build_matrix_roms

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "fixed matrix contract"):
                build_matrix_roms(
                    ROOT,
                    Path(temporary) / "matrix",
                    tile_graphics_after=0x36,
                )


if __name__ == "__main__":
    unittest.main()
