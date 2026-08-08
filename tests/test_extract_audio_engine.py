import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.extract_audio_engine import CODE_SIZE, ENGINE_OFFSET, extract
from tools import populate_bank_json

ROOT = Path(__file__).resolve().parent.parent


class AudioEngineTest(unittest.TestCase):
    def test_engine_code_is_lossless_and_real(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        bank = extract(rom)
        self.assertEqual(CODE_SIZE, 0xB8)
        self.assertEqual(bank["verification"], "runtime_verified")
        self.assertEqual(
            bank["runtime_evidence"],
            "artifacts/sappy-engine-master-enable-ab-v1/evidence.json",
        )
        self.assertEqual(bank["entries"][0]["code"], rom[ENGINE_OFFSET:ENGINE_OFFSET + CODE_SIZE].hex())
        self.assertEqual(rom[ENGINE_OFFSET + CODE_SIZE - 2:ENGINE_OFFSET + CODE_SIZE], b"\x00\x47")
        self.assertIn("0x040000A0", bank["hardware_registers"])

    def test_bulk_populator_reuses_canonical_audio_engine_extractor(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            bank_path = temp_root / "sequel/content/sappy-engine/bank.json"
            bank_path.parent.mkdir(parents=True)
            bank_path.write_text('{"entries": []}\n', encoding="utf-8")
            with mock.patch.object(populate_bank_json, "ROOT", temp_root):
                populate_bank_json.populate_sappy_engine(rom)
            self.assertEqual(json.loads(bank_path.read_text(encoding="utf-8")), extract(rom))


if __name__ == "__main__":
    unittest.main()
