import struct
import unittest

from tools import decode_controller_path_runtime_probe as decoder
from tools.build_controller_path_runtime_probe import OBSERVER_SITES


DUMP_SIZE = 0xC0
DUMP_BASE = 0x0203F040


def write_record(
    dump: bytearray,
    index: int,
    *,
    magic: int | None = None,
    hits: int = 1,
    arg0: int = 0,
    arg1: int = 0,
    arg2: int = 0,
    sequence: int = 1,
    event: int | None = None,
) -> None:
    site = OBSERVER_SITES[index]
    struct.pack_into(
        "<IIIHHII",
        dump,
        site.scratch - DUMP_BASE,
        site.magic if magic is None else magic,
        hits,
        arg0,
        arg1,
        arg2,
        sequence,
        site.event_code if event is None else event,
    )


class DecodeControllerPathRuntimeProbeTests(unittest.TestCase):
    def test_decodes_five_offsets_and_sorts_valid_records_by_uint32_sequence(self):
        dump = bytearray(DUMP_SIZE)
        struct.pack_into("<I", dump, 0, 9)
        write_record(dump, 0, arg0=0xFFFFFFFF, arg1=0xFFFF, arg2=0x8000, sequence=8)
        write_record(dump, 3, arg0=0x80000000, sequence=9)

        decoded = decoder.decode_dump(bytes(dump))

        self.assertEqual(9, decoded["event_counter"])
        self.assertEqual([1, 4], [record["event_code"] for record in decoded["fresh_records"]])
        self.assertEqual("0x00000008", decoded["records"][0]["sequence"])
        self.assertEqual([site.name for site in OBSERVER_SITES], [r["name"] for r in decoded["records"]])
        self.assertEqual("0xFFFFFFFF", decoded["records"][0]["argument0"])
        self.assertEqual(0xFFFF, decoded["records"][0]["argument1"])
        self.assertEqual(0x8000, decoded["records"][0]["argument2"])

    def test_requires_exactly_c0_bytes(self):
        for size in (DUMP_SIZE - 1, DUMP_SIZE + 1):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "exactly 192 bytes"):
                decoder.decode_dump(bytes(size))

    def test_wrong_magic_is_diagnostic_only(self):
        dump = bytearray(DUMP_SIZE)
        write_record(dump, 0, magic=0xFFFFFFFF, sequence=7)
        decoded = decoder.decode_dump(bytes(dump))
        self.assertFalse(decoded["records"][0]["valid"])
        self.assertEqual("0xFFFFFFFF", decoded["records"][0]["magic"])
        self.assertEqual([], decoded["fresh_records"])

    def test_event_magic_mismatch_is_diagnostic_only(self):
        dump = bytearray(DUMP_SIZE)
        write_record(dump, 1, event=5, sequence=7)
        decoded = decoder.decode_dump(bytes(dump))
        self.assertFalse(decoded["records"][1]["valid"])
        self.assertEqual(5, decoded["records"][1]["event_code"])
        self.assertEqual([], decoded["fresh_records"])

    def test_zero_and_stale_records_are_diagnostic_only(self):
        dump = bytearray(DUMP_SIZE)
        write_record(dump, 0, hits=0, sequence=3)
        write_record(dump, 1, hits=2, sequence=0)
        decoded = decoder.decode_dump(bytes(dump))
        self.assertFalse(decoded["records"][0]["valid"])
        self.assertFalse(decoded["records"][1]["valid"])
        self.assertEqual([], decoded["fresh_records"])

    def test_uint32_counter_hits_sequence_and_event_are_preserved(self):
        dump = bytearray(DUMP_SIZE)
        struct.pack_into("<I", dump, 0, 0xFFFFFFFF)
        write_record(dump, 4, hits=0xFFFFFFFF, sequence=0xFFFFFFFF, event=5)
        decoded = decoder.decode_dump(bytes(dump))
        record = decoded["records"][4]
        self.assertEqual(0xFFFFFFFF, decoded["event_counter"])
        self.assertEqual(0xFFFFFFFF, record["hit_count"])
        self.assertEqual("0xFFFFFFFF", record["sequence"])
        self.assertEqual(0xFFFFFFFF, int(record["sequence"], 16))
        self.assertEqual([record], decoded["fresh_records"])


if __name__ == "__main__":
    unittest.main()
