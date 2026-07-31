from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RebuildImageRelocationArtifactsTests(unittest.TestCase):
    def test_plan_rebuilds_sources_then_all_thirteen_audits_and_verifiers(self):
        from tools.rebuild_image_relocation_artifacts import build_plan

        plan = build_plan(ROOT)

        self.assertEqual(
            "tools/export_story_visual_resource_sources.py",
            plan[0][1],
        )
        self.assertEqual(27, len(plan))
        self.assertEqual(
            {
                "character-battle-bundle-relocation-v1",
                "tile-asset-resource-relocation-v1",
                "map-resource-relocation-v1",
                "menu-portrait-relocation-v1",
                "bg-resource-relocation-v1",
                "battle-effect-resource-relocation-v1",
                "story-visual-resource-relocation-v1",
                "world-map-background-relocation-v1",
                "generic-sprite-bundle-relocation-v1",
                "cutscene-obj-bundle-relocation-v1",
                "residual-lz77-graphics-relocation-v1",
                "direct-image-palette-relocation-v1",
                "residual-text-bg-tilemap-relocation-v1",
            },
            {
                argument.split("/", 1)[1]
                for command in plan
                for argument in command
                if argument.startswith("artifacts/")
                and argument.endswith("-relocation-v1")
            },
        )
        for command in plan:
            self.assertEqual("python3", command[0])
            self.assertIn("--root", command)


if __name__ == "__main__":
    unittest.main()
