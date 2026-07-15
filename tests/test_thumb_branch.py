import struct
import unittest

from tools.thumb_branch import (
    ThumbBranch,
    decode_thumb_b,
    decode_thumb_bl,
    encode_thumb_bl,
    find_thumb_branches,
    iter_thumb_direct_branches,
)


class ThumbBranchTests(unittest.TestCase):
    def test_bl_round_trips_forward_and_backward(self):
        for source, target in ((0x08000100, 0x08012340), (0x08012340, 0x08000100)):
            first, second = struct.unpack("<HH", encode_thumb_bl(source, target))
            self.assertEqual(decode_thumb_bl(source, first, second), target)

    def test_bl_rejects_odd_and_out_of_range_targets(self):
        with self.assertRaisesRegex(ValueError, "halfword aligned"):
            encode_thumb_bl(0x08000100, 0x08000103)
        with self.assertRaisesRegex(ValueError, "outside ARMv4T range"):
            encode_thumb_bl(0x08000000, 0x08800004)

    def test_decoders_reject_non_direct_branch_encodings(self):
        self.assertIsNone(decode_thumb_bl(0x08000000, 0xE000, 0xF800))
        self.assertIsNone(decode_thumb_b(0x08000000, 0xD001))

    def test_unconditional_b_decodes_positive_and_negative_displacements(self):
        self.assertEqual(decode_thumb_b(0x08000100, 0xE001), 0x08000106)
        self.assertEqual(decode_thumb_b(0x08000100, 0xE7FD), 0x080000FE)

    def test_scan_obeys_exclusive_range_and_requires_complete_bl(self):
        base = 0x08000000
        blob = bytearray(16)
        blob[4:8] = encode_thumb_bl(base + 4, base + 14)
        blob[8:10] = struct.pack("<H", 0xE001)
        branches = list(iter_thumb_direct_branches(bytes(blob), rom_base=base, start=base + 4, end=base + 10))
        self.assertEqual(
            branches,
            [
                ThumbBranch(base + 4, base + 14, "bl", "#0x0800000e"),
                ThumbBranch(base + 8, base + 14, "b", "#0x0800000e"),
            ],
        )
        self.assertEqual(list(iter_thumb_direct_branches(bytes(blob), rom_base=base, start=base + 4, end=base + 6)), [])

    def test_scan_validates_address_mapping_and_alignment(self):
        blob = bytes(8)
        for kwargs, message in (
            ({"start": 0x08000001}, "halfword aligned"),
            ({"end": 0x08000009}, "mapped ROM range"),
            ({"start": 0x08000006, "end": 0x08000004}, "start must not exceed end"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                list(iter_thumb_direct_branches(blob, rom_base=0x08000000, **kwargs))

    def test_find_filters_by_exact_target(self):
        base = 0x09000000
        blob = encode_thumb_bl(base, base + 8) + encode_thumb_bl(base + 4, base)
        self.assertEqual(
            [branch.address for branch in find_thumb_branches(blob, base + 8, rom_base=base)],
            [base],
        )


if __name__ == "__main__":
    unittest.main()
