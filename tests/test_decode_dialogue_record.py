#!/usr/bin/env python3
"""Regression tests for localized dialogue record token boundaries."""

from __future__ import annotations

import unittest


class DialogueRecordDecoderTests(unittest.TestCase):
    def test_load_mapping_reads_named_glyphs_but_not_unresolved_codes(self):
        from tools.decode_dialogue_record import load_mapping

        mapping = load_mapping()
        self.assertEqual(19, len(mapping))
        self.assertEqual("法", mapping[bytes.fromhex("92D7")])
        self.assertNotIn(bytes.fromhex("8B62"), mapping)

    def test_independent_0a_splits_segments_without_dropping_8b62(self):
        from tools.decode_dialogue_record import decode_record, load_mapping

        segments, unknowns = decode_record(
            bytes.fromhex("92D78B620A95C4"),
            load_mapping(),
        )
        self.assertEqual(["法[8B62]", "最"], segments)
        self.assertEqual([bytes.fromhex("8B62")], unknowns)


if __name__ == "__main__":
    unittest.main()
