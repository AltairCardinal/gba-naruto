"""Failure-closed syntax preflight, not a promotion or runtime proof."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

from tools.analyze_rom_renderer_excluded_roots import analyze, parse_candidate

ROOT = Path(__file__).resolve().parents[1]


class RendererExcludedRootsTests(unittest.TestCase):
    def test_operand_zero_does_not_terminate_command(self):
        self.assertEqual((4, [7, 0]), parse_candidate(bytes([7, 0, 0, 0]), 0, 4, ()))
        self.assertEqual((3, [8, 0]), parse_candidate(bytes([8, 0, 0]), 0, 3, ()))

    def test_truncated_command_fails(self):
        for raw in [bytes([7, 1]), bytes([8]), bytes([1, 0]), bytes([5])]:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'truncated'):
                parse_candidate(raw, 0, len(raw), ())

    def test_missing_terminator_and_unsupported_opcode_fail(self):
        with self.assertRaisesRegex(ValueError, 'terminator'):
            parse_candidate(bytes([8, 1]), 0, 2, ())
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            parse_candidate(bytes([9, 0]), 0, 2, ())

    def test_bounds_fail_closed(self):
        for start, limit in [(-1, 1), (0, 2), (1, 1)]:
            with self.subTest(start=start, limit=limit), self.assertRaisesRegex(ValueError, 'bounds'):
                parse_candidate(bytes([0]), start, limit, ())

    def test_nested_renderer_terminator_is_not_record_terminator(self):
        raw = bytes([5, 1, 0x80, 0x20, 0, 8, 2, 0])
        self.assertEqual((8, [5, 8, 0]), parse_candidate(raw, 0, len(raw), ()))

    def test_actual_rom_report_and_cli_replay(self):
        report = analyze(ROOT)
        self.assertEqual([[0xBC9, 0xBCD], [0xC2E, 0xC34], [0xC34, 0xC6C],
                          [0x14B4, 0x14BA], [0x15FC, 0x1631]],
                         [row['range'] for row in report['candidates']])
        self.assertEqual(125, report['candidate_unique_bytes'])
        self.assertEqual(125, report['candidate_unknown_intersection_bytes'])
        self.assertEqual(41, report['consumer_site_count'])
        self.assertEqual(5, len(report['excluded_consumers']))
        self.assertEqual(0, report['promotion_bytes'])
        self.assertFalse(report['handler_semantics_closed'])
        self.assertFalse(report['natural_reachability_proven'])
        replay = subprocess.run([sys.executable, str(ROOT / 'tools/analyze_rom_renderer_excluded_roots.py'),
                                 '--root', str(ROOT)], capture_output=True, text=True, check=True)
        self.assertEqual(report, json.loads(replay.stdout))
