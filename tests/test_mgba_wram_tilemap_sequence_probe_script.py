from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_wram_tilemap_sequence_probe.lua"


class MgbaWramTilemapSequenceProbeScriptTests(unittest.TestCase):
    def test_probe_accepts_a_validated_multi_input_schedule(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('required_env("MGBA_WRAM_INPUT_SCHEDULE")', text)
        self.assertIn("parse_schedule", text)
        self.assertIn("input intervals overlap", text)
        self.assertIn("input interval exceeds capture frame", text)
        self.assertIn("key_mask = 1 << key", text)
        self.assertIn("emu:setKeys(active_keys)", text)
        self.assertLess(text.index("emu:loadStateFile"), text.index("emu:setBreakpoint"))

    def test_probe_captures_choice_route_and_correlated_queue_states(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for address in (
            "0x0808F814",
            "0x0808F81C",
            "0x0808F83C",
            "0x0808F73C",
            "0x0808F894",
            "0x0808F89C",
            "0x0808F8A0",
            "0x0808F916",
            "0x0808F9E2",
            "0x0808F9EC",
            "0x0808F9F8",
            "0x080914D8",
            "0x0809182E",
            "0x08091AB0",
            "0x08091B70",
            "0x08091BBC",
            "0x08091BF6",
            "0x08091000",
            "0x08090B5C",
            "0x08090B60",
            "0x08090CB0",
            "0x08090D56",
            "0x08090D62",
            "0x08090DC4",
            "0x08090DD0",
            "0x08090F3C",
            "0x0806365C",
        ):
            self.assertIn(address, text)
        self.assertIn("0x0200A760", text)
        self.assertIn('"correlated_queue_hits":', text)
        self.assertIn('target.name .. "-hit.ss9"', text)
        self.assertIn('"schema":"mgba-wram-tilemap-sequence-probe-v2"', text)
        self.assertIn("write_file(done_marker", text)
        self.assertNotIn("os.exit", text)

    def test_probe_records_optional_controlled_ewram_byte_patches(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('os.getenv("MGBA_WRAM_MEMORY_PATCHES") or ""', text)
        self.assertIn("parse_memory_patches", text)
        self.assertIn("controlled patch address must be in EWRAM", text)
        self.assertIn("before = emu:read8(patch.address)", text)
        self.assertIn("emu:write8(patch.address, patch.after)", text)
        self.assertIn("assert(emu:read8(patch.address) == patch.after", text)
        self.assertIn('\',"memory_patches":\'', text)

    def test_probe_closes_each_transformed_source_through_post_consumer_vram(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for source in ("0x084634B8", "0x0846356C", "0x084635D8"):
            self.assertIn(source, text)
        self.assertIn("0x0200A640", text)
        self.assertIn("0x0200A760", text)
        self.assertIn("0x06000806", text)
        self.assertIn("source_stride_halfwords = 12", text)
        self.assertIn("row_count = 12", text)
        self.assertIn("queue_consumer_post", text)
        self.assertIn("load_post", text)
        self.assertIn('"-load-staging.bin"', text)
        self.assertIn("read_range(STAGING_SOURCE, 12 * 12 * 2)", text)
        self.assertIn("read_strided_rows", text)
        self.assertIn("post_rows == pending.output_rows", text)
        self.assertIn('load_cycle = emu:currentCycle()', text)
        self.assertIn('load_post_cycle = emu:currentCycle()', text)
        self.assertIn('submit_cycle = emu:currentCycle()', text)
        self.assertIn('queue_pre_cycle = emu:currentCycle()', text)
        self.assertIn('pending.queue_pre_event', text)
        self.assertIn('pending.queue_post_event', text)
        self.assertIn('events[#events + 1] = pending.queue_pre_event', text)
        self.assertIn('events[#events + 1] = pending.queue_post_event', text)
        self.assertIn(',"queue_post_cycle":', text)
        self.assertIn('\',"source_results":\'', text)
        self.assertIn('\',"missing_stages":\'', text)
        self.assertIn('"natural-sources-closed"', text)
        self.assertIn('"controlled-sources-closed"', text)
        self.assertIn('"incomplete"', text)
        self.assertNotIn('total_hits > 0 and "targets-observed"', text)

    def test_probe_marks_controlled_parent_states_as_non_natural(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('required_env("MGBA_WRAM_INPUT_PROVENANCE")', text)
        self.assertIn(
            'input_provenance == "natural" or input_provenance == "controlled"',
            text,
        )
        self.assertIn("local evidence_mode = input_provenance", text)
        self.assertIn("if #memory_patches > 0 then", text)
        self.assertIn('evidence_mode = "controlled"', text)
        self.assertIn('\',"evidence_mode":\'', text)


if __name__ == "__main__":
    unittest.main()
