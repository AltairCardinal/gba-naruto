import unittest

from tools.verify_save_state_records import record_offsets, save_checksum, validate_bank, validate_sram_dump


def fixture_bank():
    lengths = [8, 20]
    offsets = record_offsets(lengths)
    return {
        "table_offset": 0x20, "entry_count": 2, "entry_size": 8,
        "entries": [
            {"descriptor_index": 0, "ewram_buffer": 0x02026804, "payload_length": 8, "sram_record_offset": offsets[0]},
            {"descriptor_index": 1, "ewram_buffer": 0x020240AC, "payload_length": 20, "sram_record_offset": offsets[1]},
        ],
    }


class SaveStateVerificationTests(unittest.TestCase):
    def test_offsets_advance_by_length_plus_twenty(self):
        self.assertEqual(record_offsets([8, 20, 24]), [0, 28, 68])

    def test_validate_bank_matches_rom_descriptors(self):
        bank = fixture_bank(); rom = bytearray(0x40)
        rom[0x20:0x28] = (0x02026804).to_bytes(4, "little") + (8).to_bytes(4, "little")
        rom[0x28:0x30] = (0x020240AC).to_bytes(4, "little") + (20).to_bytes(4, "little")
        report = validate_bank(bank, bytes(rom))
        self.assertTrue(report["ok"])
        self.assertEqual(report["record_offsets"], [0, 28])
        self.assertEqual(report["total_sram_span"], 68)

    def test_validate_sram_variable_length_checksums(self):
        bank = fixture_bank(); sram = bytearray(0x10000)
        for entry in bank["entries"]:
            payload = bytes(range(entry["payload_length"]))
            offset = entry["sram_record_offset"]
            record = bytes(19) + payload + bytes([save_checksum(payload)])
            sram[offset:offset + len(record)] = record
        report = validate_sram_dump(bank, bytes(sram))
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual([8, 20], [item["payload_length"] for item in report["records"]])

    def test_bad_checksum_is_rejected(self):
        bank = fixture_bank(); sram = bytes(0x10000)
        report = validate_sram_dump(bank, sram)
        self.assertFalse(report["ok"])
        self.assertIn("checksum mismatch", report["issues"][0])

    def test_real_wasm_32k_save_size_is_accepted(self):
        bank = fixture_bank(); sram = bytearray(0x8000)
        for entry in bank["entries"]:
            offset = entry["sram_record_offset"]
            payload = bytes([1]) * entry["payload_length"]
            record = bytes(19) + payload + bytes([save_checksum(payload)])
            sram[offset:offset+len(record)] = record
        self.assertTrue(validate_sram_dump(bank, bytes(sram))["ok"])


if __name__ == "__main__":
    unittest.main()
