import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import decode_controller_path_runtime_probe as decoder
from tools.build_controller_path_runtime_probe import OBSERVER_SITES


DUMP_SIZE = 0xC0
DUMP_BASE = 0x0203F040


def make_dump(event_counter: int = 0) -> bytearray:
    dump = bytearray(DUMP_SIZE)
    struct.pack_into("<I", dump, 0, event_counter)
    return dump


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
    def test_decodes_five_offsets_and_orders_valid_records_by_modular_age(self):
        dump = make_dump(1)
        write_record(
            dump,
            0,
            arg0=0xFFFFFFFF,
            arg1=0xFFFF,
            arg2=0x8000,
            sequence=0xFFFFFFFF,
        )
        write_record(dump, 3, arg0=0x80000000, sequence=1)

        decoded = decoder.decode_dump(bytes(dump))

        self.assertEqual("single_dump_decode", decoded["mode"])
        self.assertFalse(decoded["freshness_evaluated"])
        self.assertNotIn("fresh_records", decoded)
        self.assertEqual(1, decoded["event_counter"])
        self.assertEqual(
            [1, 4], [record["event_code"] for record in decoded["valid_records"]]
        )
        self.assertEqual("0xFFFFFFFF", decoded["records"][0]["sequence"])
        self.assertEqual(
            [site.name for site in OBSERVER_SITES],
            [record["name"] for record in decoded["records"]],
        )
        self.assertEqual("0xFFFFFFFF", decoded["records"][0]["argument0"])
        self.assertEqual(0xFFFF, decoded["records"][0]["argument1"])
        self.assertEqual(0x8000, decoded["records"][0]["argument2"])

    def test_requires_exactly_c0_bytes(self):
        for size in (DUMP_SIZE - 1, DUMP_SIZE + 1):
            with self.subTest(size=size), self.assertRaisesRegex(
                ValueError, "exactly 192 bytes"
            ):
                decoder.decode_dump(bytes(size))

    def test_wrong_magic_is_diagnostic_only(self):
        dump = make_dump()
        write_record(dump, 0, magic=0xFFFFFFFF, sequence=7)
        decoded = decoder.decode_dump(bytes(dump))
        self.assertFalse(decoded["records"][0]["valid"])
        self.assertEqual("0xFFFFFFFF", decoded["records"][0]["magic"])
        self.assertEqual([], decoded["valid_records"])

    def test_event_magic_mismatch_is_diagnostic_only(self):
        dump = make_dump()
        write_record(dump, 1, event=5, sequence=7)
        decoded = decoder.decode_dump(bytes(dump))
        self.assertFalse(decoded["records"][1]["valid"])
        self.assertEqual(5, decoded["records"][1]["event_code"])
        self.assertEqual([], decoded["valid_records"])

    def test_zero_hit_and_sequence_are_diagnostic_only(self):
        dump = make_dump()
        write_record(dump, 0, hits=0, sequence=3)
        write_record(dump, 1, hits=2, sequence=0)
        decoded = decoder.decode_dump(bytes(dump))
        self.assertFalse(decoded["records"][0]["valid"])
        self.assertFalse(decoded["records"][1]["valid"])
        self.assertEqual([], decoded["valid_records"])

    def test_uint32_counter_hits_sequence_and_event_are_preserved(self):
        dump = make_dump(0xFFFFFFFF)
        write_record(dump, 4, hits=0xFFFFFFFF, sequence=0xFFFFFFFF, event=5)
        decoded = decoder.decode_dump(bytes(dump))
        record = decoded["records"][4]
        self.assertEqual(0xFFFFFFFF, decoded["event_counter"])
        self.assertEqual(0xFFFFFFFF, record["hit_count"])
        self.assertEqual("0xFFFFFFFF", record["sequence"])
        self.assertEqual(0xFFFFFFFF, int(record["sequence"], 16))
        self.assertEqual([record], decoded["valid_records"])


class CompareControllerPathRuntimeProbeTests(unittest.TestCase):
    def test_accepts_uint32_wrap_for_hit_sequence_and_shared_boundary(self):
        baseline = make_dump(0xFFFFFFFF)
        final = make_dump(1)
        write_record(baseline, 0, hits=0xFFFFFFFF, sequence=0xFFFFFFFE)
        write_record(final, 0, hits=1, sequence=1)

        compared = decoder.compare_dumps(bytes(baseline), bytes(final))

        self.assertEqual("baseline_final_compare", compared["mode"])
        self.assertTrue(compared["freshness_evaluated"])
        self.assertEqual([1], [r["event_code"] for r in compared["fresh_records"]])

    def test_orders_fresh_records_by_shared_modular_sequence(self):
        baseline = make_dump(0xFFFFFFFE)
        final = make_dump(1)
        write_record(baseline, 0, hits=3, sequence=0xFFFFFFFC)
        write_record(baseline, 1, hits=7, sequence=0xFFFFFFFD)
        write_record(final, 0, hits=4, sequence=0xFFFFFFFF)
        write_record(final, 1, hits=8, sequence=1)

        compared = decoder.compare_dumps(bytes(baseline), bytes(final))

        self.assertEqual(
            [1, 2], [record["event_code"] for record in compared["fresh_records"]]
        )

    def test_old_valid_record_without_change_is_not_fresh(self):
        baseline = make_dump(77)
        final = make_dump(77)
        write_record(baseline, 2, hits=3, sequence=42)
        write_record(final, 2, hits=3, sequence=42)

        compared = decoder.compare_dumps(bytes(baseline), bytes(final))

        self.assertEqual([], compared["fresh_records"])
        self.assertEqual(
            [3],
            [record["event_code"] for record in compared["final"]["valid_records"]],
        )

    def test_requires_both_hit_count_and_sequence_to_advance(self):
        cases = (
            (10, 10, 90, 101, "zero hit delta"),
            (10, 11, 90, 90, "zero sequence delta"),
        )
        for base_hits, final_hits, base_sequence, final_sequence, label in cases:
            with self.subTest(label=label):
                baseline = make_dump(100)
                final = make_dump(101)
                write_record(baseline, 0, hits=base_hits, sequence=base_sequence)
                write_record(final, 0, hits=final_hits, sequence=final_sequence)
                self.assertEqual(
                    [],
                    decoder.compare_dumps(bytes(baseline), bytes(final))["fresh_records"],
                )

    def test_rejects_ordinary_backwards_hit_or_sequence(self):
        cases = (
            (10, 9, 90, 101, "backwards hit"),
            (10, 11, 90, 89, "backwards sequence"),
        )
        for base_hits, final_hits, base_sequence, final_sequence, label in cases:
            with self.subTest(label=label):
                baseline = make_dump(100)
                final = make_dump(101)
                write_record(baseline, 0, hits=base_hits, sequence=base_sequence)
                write_record(final, 0, hits=final_hits, sequence=final_sequence)
                self.assertEqual(
                    [],
                    decoder.compare_dumps(bytes(baseline), bytes(final))["fresh_records"],
                )

    def test_rejects_half_range_ambiguity(self):
        cases = (
            (1, 0x80000001, 90, 101, 100, "hit delta"),
            (1, 2, 1, 0x80000001, 0, "sequence delta"),
            (1, 2, 1, 0x80000000, 0, "shared boundary delta"),
        )
        for base_hits, final_hits, base_sequence, final_sequence, boundary, label in cases:
            with self.subTest(label=label):
                baseline = make_dump(boundary)
                final = make_dump(final_sequence)
                write_record(baseline, 0, hits=base_hits, sequence=base_sequence)
                write_record(final, 0, hits=final_hits, sequence=final_sequence)
                self.assertEqual(
                    [],
                    decoder.compare_dumps(bytes(baseline), bytes(final))["fresh_records"],
                )

    def test_rejects_sequence_not_after_baseline_shared_boundary(self):
        baseline = make_dump(100)
        final = make_dump(101)
        write_record(baseline, 0, hits=1, sequence=90)
        write_record(final, 0, hits=2, sequence=95)

        compared = decoder.compare_dumps(bytes(baseline), bytes(final))

        self.assertEqual([], compared["fresh_records"])

    def test_rejects_invalid_final_record(self):
        baseline = make_dump(100)
        final = make_dump(101)
        write_record(baseline, 0, hits=1, sequence=90)
        write_record(final, 0, magic=0xFFFFFFFF, hits=2, sequence=101)

        compared = decoder.compare_dumps(bytes(baseline), bytes(final))

        self.assertEqual([], compared["fresh_records"])


class ControllerPathDecoderCliTests(unittest.TestCase):
    def test_cli_distinguishes_single_decode_from_baseline_final_compare(self):
        baseline = make_dump(100)
        final = make_dump(101)
        write_record(baseline, 0, hits=1, sequence=90)
        write_record(final, 0, hits=2, sequence=101)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_path = root / "baseline.bin"
            final_path = root / "final.bin"
            decoded_path = root / "decoded.json"
            compared_path = root / "compared.json"
            baseline_path.write_bytes(baseline)
            final_path.write_bytes(final)

            with patch(
                "sys.argv",
                ["decoder", "decode", str(final_path), str(decoded_path)],
            ):
                self.assertEqual(0, decoder.main())
            with patch(
                "sys.argv",
                [
                    "decoder",
                    "compare",
                    str(baseline_path),
                    str(final_path),
                    str(compared_path),
                ],
            ):
                self.assertEqual(0, decoder.main())

            decoded = json.loads(decoded_path.read_text(encoding="utf-8"))
            compared = json.loads(compared_path.read_text(encoding="utf-8"))
            self.assertEqual("single_dump_decode", decoded["mode"])
            self.assertNotIn("fresh_records", decoded)
            self.assertEqual("baseline_final_compare", compared["mode"])
            self.assertEqual([1], [r["event_code"] for r in compared["fresh_records"]])


if __name__ == "__main__":
    unittest.main()
