import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_battle_preparation_input_diagnostic.lua"
)


class BattlePreparationInputDiagnosticScriptTest(unittest.TestCase):
    def test_reads_maxmod_song_pointer_from_mm_layer_songadr(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "MAXMOD_LAYER_MAIN_SONG_ADDRESS_OFFSET = 0x14",
            script,
        )
        self.assertIn(
            "MAXMOD_LAYER_MAIN_VALID_OFFSET = 0x29",
            script,
        )
        self.assertRegex(
            script,
            re.compile(
                r"maxmod_layer_main_address\s*\+\s*"
                r"MAXMOD_LAYER_MAIN_SONG_ADDRESS_OFFSET"
            ),
        )

    def test_reports_maxmod_mixer_output_state(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MAXMOD_NUM_ACTIVE_CHANNELS_ADDRESS",
            "MAXMOD_WAVE_BUFFER_POINTER_ADDRESS",
            "MAXMOD_MIX_CHANNELS_POINTER_ADDRESS",
            "MAXMOD_MIX_LENGTH_ADDRESS",
            "maxmod_wave_nonzero_bytes",
            "maxmod_active_mix_channels",
            "maxmod_mix_volume_sum",
            "soundcnt_h",
            "maxmod_pattern_read_address",
            "maxmod_channel_mask",
            "maxmod_module_channels_address",
            "maxmod_allocated_module_channels",
            "maxmod_active_channels_address",
            "maxmod_disabled_active_channels",
            "maxmod_reserved_active_channels",
            "maxmod_background_active_channels",
            "maxmod_foreground_active_channels",
            "maxmod_custom_active_channels",
            "maxmod_module_channel_count",
            "maxmod_current_layer_channel_count",
            "maxmod_module_channels_with_flags",
            "maxmod_module_channels_with_instrument",
            "maxmod_first_allocated_module_index",
            "maxmod_first_allocated_mix_index",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)


if __name__ == "__main__":
    unittest.main()
