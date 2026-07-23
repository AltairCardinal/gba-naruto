import tempfile
import unittest
from pathlib import Path

from tools.butano.export_scenario_41_combat_reference import (
    COMBAT_CHECKPOINTS,
    export_combat_reference,
)
from tools.butano.render_scenario_41_gpu import render_boundary


ROOT = Path(__file__).resolve().parents[1]


class Scenario41CombatReferenceTest(unittest.TestCase):
    def test_exports_hash_bound_combat_ui_and_dialogue_boundaries(self):
        self.assertEqual(
            tuple(COMBAT_CHECKPOINTS),
            (
                "action-menu-0",
                "action-menu-1",
                "end-confirmation",
                "defense-confirmation",
                "target-select",
                "attack-confirmation",
                "combat-dialogue",
                "combat-popup",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reference"
            manifest = export_combat_reference(ROOT / "rom/base.gba", output)
            self.assertEqual(set(manifest["boundaries"]), set(COMBAT_CHECKPOINTS))
            for name, checkpoint in COMBAT_CHECKPOINTS.items():
                with self.subTest(boundary=name):
                    self.assertEqual(
                        manifest["boundaries"][name]["screen"]["rgb_pixels_sha256"],
                        checkpoint.screen_sha256,
                    )
                    self.assertEqual(len(render_boundary(output / name)), 240 * 160 * 3)


if __name__ == "__main__":
    unittest.main()
