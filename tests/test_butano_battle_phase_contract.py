from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_scene_controller.h"
)
SCRIPT_DIR = ROOT / "tools" / "butano"


class ButanoBattlePhaseContractTests(unittest.TestCase):
    def test_mgba_phase_constants_match_controller_enum(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        match = re.search(
            r"enum class battle_scene_phase[^{]*\{(?P<body>.*?)\};",
            controller,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        names = [
            entry.strip()
            for entry in match.group("body").split(",")
            if entry.strip()
        ]
        phase_values = {name: index for index, name in enumerate(names)}

        checked = 0
        for script in sorted(SCRIPT_DIR.glob("*.lua")):
            source = script.read_text(encoding="utf-8")
            for constant, value in re.findall(
                r"local PHASE_([A-Z_]+)\s*=\s*([0-9]+)",
                source,
            ):
                phase_name = constant.lower()
                if phase_name.startswith("deploy_"):
                    continue
                self.assertIn(phase_name, phase_values, script.name)
                self.assertEqual(
                    int(value),
                    phase_values[phase_name],
                    f"{script.name}: PHASE_{constant}",
                )
                checked += 1

        self.assertGreater(checked, 20)
