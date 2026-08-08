from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MgbaBattleEncountersStoryVisualTraceScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (
            ROOT / "tools/mgba_battle_encounters_story_visual_trace.lua"
        ).read_text(encoding="utf-8")

    def test_traces_the_complete_control_and_resource_chain(self):
        for address in (
            "0x08097BBC",
            "0x0808FA2C",
            "0x0808A69C",
            "0x08087C9C",
            "0x08087DE8",
            "0x0809C0E8",
            "0x08087EC0",
        ):
            self.assertIn(address, self.script)
        for name in (
            "chapter-opcode-14",
            "story-state-dispatch",
            "story-wrapper",
            "story-loader",
            "descriptor-0-select",
            "gfx-decompress",
            "palette-decompress",
            "tilemap-decompress",
            "overlay-first-vblank",
        ):
            self.assertIn(name, self.script)

    def test_uses_event_loop_callbacks_and_fail_closed_environment(self):
        self.assertIn('callbacks:add("frame"', self.script)
        self.assertIn("overlay_vblank_count = overlay_vblank_count + 1", self.script)
        self.assertIn("overlay_vblank_count == 8", self.script)
        self.assertIn("STORY_TRACE_INPUT_STATE_SHA256", self.script)
        self.assertIn("STORY_TRACE_SCRIPT_SHA256", self.script)
        self.assertIn("STORY_TRACE_ROM_SHA256", self.script)
        self.assertIn("STORY_TRACE_DONE_MARKER", self.script)
        self.assertNotIn("emu:frameAdvance()", self.script)
        self.assertNotIn("while not complete", self.script)


if __name__ == "__main__":
    unittest.main()
