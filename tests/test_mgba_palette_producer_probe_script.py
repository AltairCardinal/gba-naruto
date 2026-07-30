import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_palette_producer_probe.lua"


class MgbaPaletteProducerProbeScriptTests(unittest.TestCase):
    def test_probe_loads_a_checkpoint_and_captures_the_queue_callsite(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for environment_name in [
            "MGBA_PALETTE_INPUT_STATE",
            "MGBA_PALETTE_INPUT_STATE_SHA256",
            "MGBA_PALETTE_INPUT_KEY",
            "MGBA_PALETTE_INPUT_DOWN_FRAME",
            "MGBA_PALETTE_INPUT_UP_FRAME",
            "MGBA_PALETTE_ROM_SHA256",
            "MGBA_PALETTE_OUTPUT_DIR",
            "MGBA_PALETTE_DONE_MARKER",
            "MGBA_PALETTE_RUN_ID",
        ]:
            self.assertIn(environment_name, text)
        self.assertIn("assert(emu:loadStateFile(input_state)", text)
        self.assertIn("emu:setBreakpoint", text)
        self.assertIn("0x08096536", text)
        self.assertIn("0x080635B8", text)
        self.assertIn("0x0809653B", text)
        self.assertIn("emu:setRangeWatchpoint", text)
        self.assertIn("0x02002880", text)
        self.assertIn("0x02002900", text)
        self.assertIn("C.WATCHPOINT_TYPE.WRITE_CHANGE", text)

    def test_probe_applies_one_optional_a_pulse_and_checks_the_real_handler_state(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('input_key == "None" or input_key == "A"', text)
        self.assertIn("C.GBA_KEY.A", text)
        self.assertIn("emu:addKey(input_key_code)", text)
        self.assertIn("emu:clearKey(input_key_code)", text)
        self.assertIn(',"inputs":', text)
        self.assertIn("inputs_json()", text)
        self.assertIn("state == 0x40", text)
        self.assertNotIn("state == 0x41", text)

    def test_probe_persists_reusable_evidence_without_exiting_mgba(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('output_dir .. "/startup.json"', text)
        self.assertIn('output_dir .. "/hit.ss9"', text)
        self.assertIn('output_dir .. "/timeout.ss9"', text)
        self.assertIn('output_dir .. "/scratch.bin"', text)
        self.assertIn('output_dir .. "/writes.json"', text)
        self.assertIn('output_dir .. "/audit.json"', text)
        self.assertIn("write_file(done_marker, payload)", text)
        self.assertIn("emu:clearBreakpoint", text)
        self.assertNotIn("os.exit", text)

    def test_probe_records_arguments_state_and_last_writer_order(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for register in ["r0", "r1", "r2", "r4"]:
            self.assertIn(f'emu:readRegister("{register}")', text)
        self.assertIn("emu:currentCycle()", text)
        self.assertIn("info.address", text)
        self.assertIn("info.oldValue", text)
        self.assertIn("info.newValue", text)
        self.assertIn("info.width", text)
        self.assertIn("write_events", text)

    def test_probe_records_the_opcode_helper_mode_and_state_dispatch_chain(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for address in [
            "0x08097966",
            "0x08096B74",
            "0x08096B9C",
            "0x08096BD4",
            "0x08096BE4",
            "0x0809C0E0",
            "0x0809651C",
        ]:
            self.assertIn(address, text)
        self.assertIn("trace_events", text)
        self.assertIn('output_dir .. "/trace.json"', text)
        self.assertIn("trace_breakpoints", text)
        self.assertIn("target_slot", text)
        self.assertIn("scratch_first", text)
        self.assertIn('name = "palette_fill_mode_0"', text)
        self.assertIn("expected_lr = 0x08096BE5", text)
        self.assertNotIn('name = "palette_fill_mode_1"', text)

    def test_probe_timeout_is_terminal_and_preserves_negative_evidence(self):
        text = SCRIPT.read_text(encoding="utf-8")
        timeout_block = text[text.index("if frame >= timeout_frames then") :]
        self.assertIn("capture_complete = true", timeout_block)
        self.assertIn('write_file(output_dir .. "/writes.json", writes_json())', timeout_block)
        self.assertIn('output_dir .. "/portrait-slots.bin"', timeout_block)
        self.assertIn('output_dir .. "/portrait-slot0-state.bin"', timeout_block)
        self.assertIn('output_dir .. "/portrait-slot1-state.bin"', timeout_block)
        self.assertIn("emu:saveStateFile", timeout_block)
        self.assertIn("emu:screenshot", timeout_block)
        self.assertIn("write_file(done_marker, payload)", timeout_block)
        self.assertIn("is_readable_state_pointer(slot0)", timeout_block)
        self.assertIn("is_readable_state_pointer(slot1)", timeout_block)

    def test_probe_fails_closed_if_observers_are_not_installed(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("scratch_watchpoint and scratch_watchpoint > 0", text)
        self.assertIn("enqueue_breakpoint and enqueue_breakpoint > 0", text)
        startup_index = text.index('output_dir .. "/startup.json"')
        self.assertLess(
            text.index("scratch_watchpoint and scratch_watchpoint > 0"),
            startup_index,
        )
        self.assertLess(
            text.index("enqueue_breakpoint and enqueue_breakpoint > 0"),
            startup_index,
        )


if __name__ == "__main__":
    unittest.main()
