"""Raw handler graph inventory must retain call/return uncertainty."""
import unittest
from unittest.mock import patch
from pathlib import Path

from tools.analyze_rom_renderer_handler_graphs import analyze, walk_handler
from tools.thumb_branch import encode_thumb_bl

ROOT = Path(__file__).resolve().parents[1]


class HandlerGraphTests(unittest.TestCase):
    def test_internal_bl_target_is_included_and_return_remains_conditional(self):
        raw = encode_thumb_bl(0, 6) + bytes.fromhex('01e00120ffe7')
        report = walk_handler(raw, 0, (0, 10), {10})
        self.assertEqual([0, 4, 6, 8], [row['offset'] for row in report['instructions']])
        self.assertTrue(report['calls'][0]['internal'])
        self.assertFalse(report['calls'][0]['return_proven'])
        self.assertIn({'source': 0, 'target': 6, 'kind': 'internal_call_target'}, report['edges'])
        self.assertIn({'source': 0, 'target': 4, 'kind': 'conditional_call_return'}, report['edges'])

    def test_external_bl_does_not_claim_callee_or_return(self):
        raw = encode_thumb_bl(0, 200) + bytes.fromhex('c046')
        report = walk_handler(raw, 0, (0, 6), {6})
        self.assertFalse(report['calls'][0]['internal'])
        self.assertEqual(200, report['calls'][0]['target'])
        self.assertFalse(report['calls'][0]['return_proven'])
        self.assertEqual([0, 4], [row['offset'] for row in report['instructions']])

    def test_no_linear_decode_of_skipped_literal(self):
        raw = bytes.fromhex('00e0ffffc046')
        report = walk_handler(raw, 0, (0, 6), {6})
        self.assertEqual([0, 4], [row['offset'] for row in report['instructions']])

    def test_stack_slot_store_is_decoded_from_halfword(self):
        report = walk_handler(bytes.fromhex('0593189005e0'), 0, (0, 6), {18})
        self.assertEqual([{'offset': 0, 'source_register': 3, 'sp_relative_offset': 20},
                          {'offset': 2, 'source_register': 0, 'sp_relative_offset': 96}],
                         report['direct_sp_word_stores'])

    def test_unowned_target_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'instruction membership'):
            walk_handler(bytes.fromhex('00e0ffffc046'), 0, (0, 6), {6}, {0: 2})

    def test_indirect_exit_is_frontier_and_never_structured_return(self):
        report = walk_handler(bytes.fromhex('7047'), 0, (0, 2), set())
        self.assertEqual('indirect_pc_target', report['frontiers'][0]['kind'])
        self.assertFalse(report['structured_return_proven'])

    def test_context_switch_is_not_ordinary_call_return(self):
        raw = encode_thumb_bl(0, 0x9C574) + bytes.fromhex('c046')
        report = walk_handler(raw, 0, (0, 6), {6}, context_targets={0x9C574})
        self.assertIn({'source': 0, 'target': 4, 'kind': 'conditional_context_resumption'}, report['edges'])
        self.assertFalse(report['calls'][0]['same_context_resumption_proven'])
        self.assertNotIn({'source': 0, 'target': 4, 'kind': 'conditional_call_return'}, report['edges'])

    def test_cached_cfg_does_not_hide_changed_upstream_file(self):
        from tools.verify_rom_fixed_renderer_script_records import _cfg_blocks
        _cfg_blocks(ROOT)
        original_read = Path.read_bytes
        changed_path = ROOT / 'artifacts/rom-cfg-inventory-v2/manifest.json'

        def changed_read(path):
            return b'changed upstream' if path == changed_path else original_read(path)

        with patch.object(Path, 'read_bytes', changed_read):
            with self.assertRaisesRegex(ValueError, 'upstream identity'):
                analyze(ROOT)

    def test_actual_handler_inventory(self):
        report = analyze(ROOT)
        seven, eight = report['handlers']
        self.assertEqual([0x67F50, 0x67F84],
                         [s['offset'] for s in seven['direct_sp_word_stores'] if s['sp_relative_offset'] == 20])
        self.assertEqual([0x68174, 0x68194],
                         [s['offset'] for s in eight['direct_sp_word_stores'] if s['sp_relative_offset'] == 20])
        self.assertIn({'source': 0x68038, 'target': 0x6835E, 'kind': 'b'}, seven['edges'])
        self.assertIn(0x67810, [c['target'] for c in seven['calls'] if c['internal']])
        self.assertEqual(0x26C, report['context_switch_dependency']['arm_target'])
        self.assertEqual([0x67CFE, 0x68108], report['context_switch_dependency']['handler_callsites'])
        self.assertFalse(report['context_switch_dependency']['same_context_resumption_proven'])
        self.assertFalse(report['complete_handler_semantics_proven'])
        self.assertEqual(0, report['promotion_bytes'])
