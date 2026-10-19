import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMAND_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_commands.h"
)
RUNTIME_SCRIPTS = (
    ROOT / "tools" / "butano" / "mgba_battle_09_character_actions.lua",
    ROOT / "tools" / "butano" / "mgba_battle_09_multi_unit.lua",
    ROOT / "tools" / "butano" / "mgba_battle_32_dynamic_deployment.lua",
    ROOT / "tools" / "butano" / "mgba_battle_41_shared_runtime.lua",
    ROOT / "tools" / "butano" / "mgba_battle_campaign_route.lua",
    ROOT
    / "tools"
    / "butano"
    / "mgba_battlefield_object_type_2_runtime.lua",
)


def command_value(command_name: str) -> int:
    source = COMMAND_HEADER.read_text(encoding="utf-8")
    match = re.search(
        r"enum class battle_command_type[^{]*\{(?P<body>[^}]*)\}",
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("battle_command_type enum not found")

    entries = [
        entry.strip().split("=", 1)[0].strip()
        for entry in match.group("body").split(",")
        if entry.strip()
    ]
    return entries.index(command_name)


class ButanoBattleCommandTelemetryContractTest(unittest.TestCase):
    def test_lua_end_action_value_matches_cpp_command_enum(self):
        expected_value = command_value("end_action")

        for script in RUNTIME_SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                match = re.search(
                    r"local COMMAND_END_ACTION = (?P<value>\d+)",
                    source,
                )
                self.assertIsNotNone(match)
                self.assertEqual(
                    int(match.group("value")),
                    expected_value,
                    "mGBA route would select the wrong command",
                )


if __name__ == "__main__":
    unittest.main()
