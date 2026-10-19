import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_runtime_scene.cpp"
)
PREPARATION = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_preparation_scene.cpp"
)
AUDIO_RUNTIME = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_audio_runtime.h"
)
class BattleAudioRuntimeWiringTest(unittest.TestCase):
    def test_runtime_drives_audio_from_battle_semantics(self):
        source = RUNTIME.read_text(encoding="utf-8")

        self.assertIn(
            '#include "konoha/battle_audio_runtime.h"',
            source,
        )
        self.assertIn("dispatch_battle_audio", source)
        for event in (
            "preparation_opened",
            "battle_opened",
            "ui_confirmed",
            "ui_cancelled",
            "ui_navigated",
            "input_rejected",
            "action_confirmed",
            "technique_title",
            "action_movie",
            "impact",
            "combat_popup",
            "victory_shown",
            "result_shown",
            "level_up_shown",
        ):
            self.assertRegex(
                source,
                rf"battle_audio_event::\s*{re.escape(event)}",
            )

        self.assertRegex(
            source,
            r"presentation_event\s*\.\s*special_combination",
        )
        self.assertRegex(
            source,
            r"battle_audio_event::\s*combat_popup\s*,\s*"
            r"special_combination",
        )
        self.assertIn("observed_combat_stage", source)

    def test_preparation_scene_starts_prebattle_music(self):
        source = PREPARATION.read_text(encoding="utf-8")

        self.assertIn(
            '#include "konoha/battle_audio_runtime.h"',
            source,
        )
        self.assertRegex(
            source,
            r"battle_audio_event::\s*preparation_opened",
        )

    def test_current_music_only_adapter_keeps_the_proven_route_configuration(self):
        compiler = shutil.which("clang++") or shutil.which("g++")
        self.assertIsNotNone(compiler, "a host C++ compiler is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bn_assert.h").write_text(
                '#include <stdexcept>\n'
                '#define BN_ERROR(...) throw std::runtime_error("unknown cue")\n'
            )
            (root / "audio_stub.h").write_text(
                '#pragma once\n#include <vector>\n'
                'namespace bn { inline std::vector<int> played;\n'
                'struct item { int cue; void play() const { played.push_back(cue); } }; }\n'
            )
            for kind, cues in (
                ("music", (2, 5, 8, 14, 15)),
                ("sound", (102, 103, 104, 105, 112, 116, 117, 126, 138, 149, 157, 158)),
            ):
                (root / f"bn_{kind}_items.h").write_text(
                    '#include "audio_stub.h"\n'
                    f'namespace bn::{kind}_items {{\n'
                    + ''.join(f'inline const item sound_{cue:03d}{{{cue}}};\n' for cue in cues)
                    + '}\n'
                )
            (root / "main.cpp").write_text('''
#include "konoha/battle_audio_runtime.h"
#include <iostream>
int main() {
    using namespace konoha;
    battle_audio_director director;
    for(int repeat = 0; repeat < 512; ++repeat) {
        bn::played.clear();
        dispatch_battle_audio(director, battle_audio_event::battle_opened);
        dispatch_battle_audio(director, battle_audio_event::ui_confirmed);
        dispatch_battle_audio(director, battle_audio_event::ui_cancelled);
        dispatch_battle_audio(director, battle_audio_event::ui_navigated);
        dispatch_battle_audio(director, battle_audio_event::input_rejected);
        dispatch_battle_audio(director, battle_audio_event::action_confirmed);
        dispatch_battle_audio(director, battle_audio_event::action_movie);
        dispatch_battle_audio(director, battle_audio_event::impact);
        dispatch_battle_audio(director, battle_audio_event::combat_popup);
        dispatch_battle_audio(director, battle_audio_event::victory_shown);
        dispatch_battle_audio(director, battle_audio_event::result_shown);
        // Short SFX remain disabled: the real emulator route timed out.
        const std::vector<int> expected{14};
        if(bn::played != expected) {
            std::cerr << "music-only playback boundary changed";
            return 1;
        }
    }
    try { play_battle_music(999); } catch(const std::runtime_error&) { return 0; }
    std::cerr << "unknown music cue was silently accepted";
    return 2;
}
''')
            built = subprocess.run(
                [compiler, "-std=c++23", "-Wall", "-Wextra", "-Werror",
                 "-I", str(root), "-I", str(ROOT / "butano-sequel/game/include"),
                 str(root / "main.cpp"), "-o", str(root / "test-audio")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run(
                [str(root / "test-audio")], capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_long_postbattle_wav_cues_are_not_submitted(self):
        source = AUDIO_RUNTIME.read_text(encoding="utf-8")

        self.assertNotIn("battle_audio_command_kind::play_music_once", source)
        self.assertNotRegex(source, r"sound_items::sound_0?5[12]")

    def test_outcome_audio_waits_for_combat_presentation(self):
        source = RUNTIME.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"if\s*\(\s*!\s*presentation\.busy\(\)"
            r"\s*&&\s*!\s*controller\.presentation_pending\(\)"
            r"\s*\)\s*\{\s*dispatch_battle_phase_audio",
        )

if __name__ == "__main__":
    unittest.main()
