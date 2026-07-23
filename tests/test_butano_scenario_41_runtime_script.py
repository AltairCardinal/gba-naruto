import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_scenario_41_acceptance.lua"
BOUNDARY_SCRIPT = ROOT / "tools" / "butano" / "mgba_scenario_41_boundaries.lua"
GOLDEN_SCRIPT = ROOT / "tools" / "butano" / "mgba_scenario_41_golden_route.lua"
ATTACK_TRACE_SCRIPT = (
    ROOT / "tools" / "butano" / "mgba_scenario_41_attack_trace.lua"
)
BUTANO_ATTACK_TRACE_SCRIPT = (
    ROOT / "tools" / "butano" / "mgba_scenario_41_butano_attack_trace.lua"
)
AUDIO_PROBE_SCRIPT = ROOT / "tools" / "butano" / "mgba_scenario_41_audio_probe.lua"


class Scenario41RuntimeScriptTest(unittest.TestCase):
    def test_cold_start_plan_is_explicit_and_bounded(self):
        self.assertTrue(SCRIPT.is_file(), "scenario 41 mGBA acceptance script is missing")
        text = SCRIPT.read_text(encoding="utf-8")
        inputs = [
            (int(down), int(up), key)
            for down, up, key in re.findall(
                r'\{\s*(\d+),\s*(\d+),\s*"(A|Up|Down|Start)"\s*\}', text
            )
        ]
        self.assertEqual(
            inputs,
            [
                (60, 68, "A"),
                (90, 98, "A"),
                (120, 128, "Up"),
                (150, 158, "Up"),
                (180, 188, "Up"),
                (210, 218, "A"),
                (240, 248, "Down"),
                (270, 278, "A"),
                (390, 398, "Start"),
                (480, 488, "Start"),
                (590, 598, "A"),
                (620, 628, "A"),
                (650, 658, "A"),
                (680, 688, "Up"),
                (710, 718, "A"),
                (810, 818, "A"),
                (870, 878, "A"),
            ],
        )
        for name in (
            "intro.png",
            "initial-player-turn.png",
            "initial-move-select.png",
            "turn-2.png",
            "turn-4.png",
            "victory.png",
            "result.png",
            "restart.png",
            "final.ss9",
            "audit.json",
        ):
            with self.subTest(name=name):
                self.assertIn(name, text)
        self.assertNotRegex(text, r"\bos\s*\.\s*(exit|execute)\s*\(")
        self.assertIn("MGBA_S41_DONE_MARKER", text)

    def test_visual_boundary_plan_reaches_technique_and_facing(self):
        self.assertTrue(BOUNDARY_SCRIPT.is_file(), "visual boundary script is missing")
        text = BOUNDARY_SCRIPT.read_text(encoding="utf-8")
        inputs = [
            (int(down), int(up), key)
            for down, up, key in re.findall(
                r'\{\s*(\d+),\s*(\d+),\s*"(A|B|Up|Down)"\s*\}', text
            )
        ]
        self.assertEqual(
            inputs,
            [
                (60, 68, "A"),
                (90, 98, "A"),
                (120, 128, "A"),
                (150, 158, "A"),
                (180, 188, "B"),
                (210, 218, "Down"),
                (240, 248, "A"),
                (270, 278, "Up"),
                (300, 308, "A"),
            ],
        )
        for name in ("move-select.png", "technique-menu.png", "facing.png"):
            self.assertIn(name, text)
        self.assertIn("MGBA_S41_DONE_MARKER", text)

    def test_golden_route_captures_late_original_boundaries(self):
        self.assertTrue(GOLDEN_SCRIPT.is_file(), "golden route script is missing")
        text = GOLDEN_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('{ 360, "A" }', text)
        self.assertNotIn('{ 150, "A" }', text)
        for name in (
            "intro-player-appearance.png",
            "intro-enemy-appearance.png",
            "intro-start-title.png",
            "intro-black.png",
            "intro-dialogue.png",
            "intro-shuriken-transition.png",
        ):
            self.assertIn(name, text)
        for name in (
            "battle-entry.png",
            "action-menu-0.png",
            "action-menu-1.png",
            "end-confirmation.png",
            "defense-confirmation.png",
            "tutorial.png",
            "target-select.png",
            "attack-confirmation.png",
            "attack-animation-000.png",
            "attack-animation-034.png",
            "attack-animation-064.png",
            "attack-animation-104.png",
            "attack-animation-144.png",
            "attack-animation-184.png",
            "attack-animation-224.png",
            "attack-animation-247.png",
            "combat-dialogue.png",
            "combat-popup.png",
            "victory.png",
            "postbattle.png",
            "final.ss9",
        ):
            self.assertIn(name, text)
        self.assertIn("MGBA_S41_DONE_MARKER", text)
        self.assertIn("frame == 2580", text)
        self.assertNotRegex(text, r"\bos\s*\.\s*(exit|execute)\s*\(")

    def test_attack_trace_captures_every_frame_and_audio_wrapper_hits(self):
        self.assertTrue(ATTACK_TRACE_SCRIPT.is_file())
        text = ATTACK_TRACE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("emu:loadStateFile(input_state)", text)
        self.assertIn("0x08061E6C", text)
        self.assertIn("emu:setBreakpoint", text)
        self.assertNotIn('callbacks:add("start"', text)
        self.assertIn("if frame == 1 then", text)
        self.assertIn('string.format("frame-%04d.png", frame)', text)
        self.assertIn('string.format("state-%04d.ss9", frame)', text)
        self.assertIn("[6] = true", text)
        self.assertIn("[69] = true", text)
        self.assertIn("frame == 360", text)
        self.assertIn("MGBA_S41_DONE_MARKER", text)

    def test_butano_attack_trace_captures_each_rendered_animation_frame(self):
        self.assertTrue(BUTANO_ATTACK_TRACE_SCRIPT.is_file())
        text = BUTANO_ATTACK_TRACE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('{ 1580, "A" }', text)
        self.assertIn('string.format("render-%04d.png", frame)', text)
        self.assertIn("frame >= 1578 and frame <= 1870", text)
        self.assertIn("frame == 1870", text)
        self.assertIn("MGBA_S41_DONE_MARKER", text)

    def test_audio_probe_saves_hardware_states_across_the_route(self):
        self.assertTrue(AUDIO_PROBE_SCRIPT.is_file())
        text = AUDIO_PROBE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("emu:saveStateFile", text)
        self.assertIn('string.format("audio-state-%04d.ss9", frame)', text)
        for frame in (20, 500, 1000, 1600, 2200):
            self.assertIn(str(frame), text)
        self.assertIn("MGBA_S41_DONE_MARKER", text)


if __name__ == "__main__":
    unittest.main()
