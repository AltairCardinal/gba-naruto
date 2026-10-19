import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_command_blockers import (
    build_command_blocker_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleCommandBlockerAnalysisTest(unittest.TestCase):
    def test_binds_action_80_to_status_driven_side_activation(self):
        manifest = build_command_blocker_manifest(
            ROOT / "rom/base.gba"
        )

        self.assertEqual(
            manifest["identity"],
            "battle_command_blocker_bindings",
        )
        self.assertEqual(
            manifest["action_80"],
            {
                "action_id": 80,
                "template_address": "0x08545958",
                "template_raw_hex":
                    "01053f02000155000302030000000000",
                "effect_code": "0x3F",
                "success_rate_percent": 85,
                "duration_turns": 2,
                "stored_duration_ticks": 4,
            },
        )
        self.assertEqual(
            manifest["effect_handler"]["reaction_state_call"],
            {
                "callsite": "0x08077560",
                "target": "0x0806A8C0",
                "state": "0x30",
            },
        )
        self.assertEqual(
            manifest["effect_handler"]["status_upsert_call"],
            {
                "callsite": "0x0807758A",
                "target": "0x0806C204",
            },
        )
        self.assertEqual(
            manifest["side_activation"]["controller_callsite"],
            "0x080736E4",
        )
        self.assertEqual(
            manifest["side_activation"]["blocker_priority"],
            ["0x3F", "0x3E", "0x3D", "0x0F", "0x11", "0x15"],
        )
        self.assertEqual(
            manifest["side_activation"]["status_query_target"],
            "0x0806C160",
        )
        self.assertEqual(
            manifest["side_activation"]["on_blocker"],
            "skip_unit_activation",
        )
        self.assertEqual(
            manifest["implementation_boundary"]["eligibility_source"],
            "persistent_status_store",
        )
        self.assertEqual(
            manifest["implementation_boundary"]["not_eligibility_source"],
            "reaction_state_byte",
        )

    def test_rom_mismatch_fails_closed(self):
        source = bytearray((ROOT / "rom/base.gba").read_bytes())
        source[0x7536C] ^= 0x01
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tampered.gba"
            target.write_bytes(source)
            with self.assertRaisesRegex(
                ValueError,
                "original ROM SHA-256 mismatch",
            ):
                build_command_blocker_manifest(target)


if __name__ == "__main__":
    unittest.main()
