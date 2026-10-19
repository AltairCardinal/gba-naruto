import unittest
from pathlib import Path

from tools.extract_audio_engine import CODE_SIZE, ENGINE_OFFSET, extract

ROOT = Path(__file__).resolve().parent.parent


class AudioEngineTest(unittest.TestCase):
    def test_engine_code_is_lossless_and_real(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        bank = extract(rom)
        self.assertEqual(bank["verification"], "code_verified")
        self.assertEqual(bank["entries"][0]["code"], rom[ENGINE_OFFSET:ENGINE_OFFSET + CODE_SIZE].hex())
        self.assertIn("0x040000A0", bank["hardware_registers"])


if __name__ == "__main__":
    unittest.main()
