#!/usr/bin/env python3
"""ROM-derived battle portrait content for the Butano script renderer."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlePortraitContentTests(unittest.TestCase):
    def test_extracts_only_the_46_portrait_expression_pairs_used_by_scripts(self):
        from tools.generate_butano_battle_portrait_content import (
            extract_battle_portrait_content,
        )

        content = extract_battle_portrait_content(ROOT)
        self.assertEqual(len(content["resources"]), 46)
        self.assertEqual(
            [(row["portrait_id"], row["expression_id"])
             for row in content["resources"][:4]],
            [(1, 0), (1, 1), (1, 2), (1, 4)],
        )
        self.assertEqual(
            (
                content["resources"][-1]["portrait_id"],
                content["resources"][-1]["expression_id"],
            ),
            (44, 0),
        )
        self.assertEqual(len(content["compressed_gfx"]), 147181)
        self.assertEqual(len(content["palettes"]), 46 * 64)

    def test_resources_are_byte_bound_to_the_original_visual_matrix(self):
        from tools.generate_butano_battle_portrait_content import (
            extract_battle_portrait_content,
        )

        content = extract_battle_portrait_content(ROOT)
        naruto = content["resources"][0]
        self.assertEqual(naruto["gfx_pointer"], 0x08408BD8)
        self.assertEqual(naruto["palette_pointer"], 0x084098C4)
        self.assertEqual(naruto["decompressed_size"], 6400)
        self.assertEqual(
            naruto["decompressed_sha256"],
            "a7eb566c2b1dcfb0357dfa93a526af1132c97fec3d6cfa683760cd3d7e41c64b",
        )
        self.assertEqual(
            naruto["palette_sha256"],
            "cb61b78fb80795ed2f2fc59ed7ceb8f2fd70bde7af7827c0b1a8b9232a01d48c",
        )
        self.assertTrue(
            all(
                resource["gfx_offset"] % 4 == 0
                for resource in content["resources"]
            )
        )
        combined = content["compressed_gfx"] + b"".join(
            int(color).to_bytes(2, "little")
            for color in content["palettes"]
        )
        self.assertEqual(
            hashlib.sha256(combined).hexdigest(),
            "82e4e0080f860b04c314ea740225b7b6e273daa55704bd0ea63d41d92110a01a",
        )

    def test_six_component_layout_reconstructs_the_original_80_by_80_canvas(self):
        from tools.generate_butano_battle_portrait_content import (
            PORTRAIT_COMPONENTS,
        )

        self.assertEqual(
            PORTRAIT_COMPONENTS,
            (
                (64, 64, 16, 16, 0, 256),
                (64, 32, 16, 32, 256, 512),
                (64, 0, 16, 32, 768, 512),
                (32, 64, 32, 16, 1280, 512),
                (0, 64, 32, 16, 1792, 512),
                (0, 0, 64, 64, 2304, 4096),
            ),
        )
        covered = set()
        for x, y, width, height, _, _ in PORTRAIT_COMPONENTS:
            for py in range(y, y + height):
                for px in range(x, x + width):
                    covered.add((px, py))
        self.assertEqual(len(covered), 80 * 80)

    def test_generates_fixed_capacity_header_with_runtime_lookup(self):
        from tools.generate_butano_battle_portrait_content import (
            extract_battle_portrait_content,
            generate_header,
        )

        header = generate_header(extract_battle_portrait_content(ROOT))
        self.assertIn(
            "std::array<battle_presentation_portrait_resource, 46>",
            header,
        )
        self.assertIn(
            "std::array<std::uint8_t, 147181>",
            header,
        )
        self.assertIn(
            "alignas(4) inline constexpr std::array<std::uint8_t",
            header,
        )
        self.assertIn(
            "battle_presentation_portrait_resource_for(",
            header,
        )
        self.assertNotIn("scenario_41_", header)

    def test_command_line_entrypoint_runs_from_the_repository_root(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "portraits.h"
            subprocess.run(
                [
                    sys.executable,
                    "tools/generate_butano_battle_portrait_content.py",
                    "--root",
                    ".",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn(
                "battle_presentation_portrait_resources",
                output.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
