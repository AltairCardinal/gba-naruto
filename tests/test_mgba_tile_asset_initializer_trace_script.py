from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_tile_asset_initializer_trace.lua"


class MgbaTileAssetInitializerTraceScriptTests(unittest.TestCase):
    def test_uses_a_fixed_five_boundary_trace(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "TILE_TRACE_INPUT_STATE",
            "TILE_TRACE_INPUT_STATE_SHA256",
            "TILE_TRACE_OUTPUT_DIR",
            "TILE_TRACE_DONE_MARKER",
            "TILE_TRACE_RUN_ID",
            "TILE_TRACE_ROM_SHA256",
            '"initializer-entry", address = 0x080983B8',
            '"scene-panel-result", address = 0x0808BECC',
            '"controller-entry", address = 0x0808C214',
            '"presentation-selector", address = 0x0808C18C',
            '"presentation-call", address = 0x0808C1D8',
            '"descriptor-selected", address = 0x08098462',
            '"graphics-source-load", address = 0x0809848E',
            '"palette-source-load", address = 0x080984A4',
            '"layout-source-load", address = 0x080984B6',
            'emu:readRegister("r8")',
            '"required_hit_count":',
            "emu:saveStateFile",
            "emu:screenshot",
            "emu:setKeys(0)",
        ):
            self.assertIn(token, text)

    def test_supports_one_explicit_a_pulse_without_recovery_inputs(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "TILE_TRACE_A_DOWN_FRAME",
            "TILE_TRACE_A_UP_FRAME",
            "C.GBA_KEY.A",
            '"recovery_inputs":[]',
            "frame_limit <= 900",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
