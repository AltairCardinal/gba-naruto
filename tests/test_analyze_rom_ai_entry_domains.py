"""Finite local gate evidence must not imply full scorer index validity."""
from pathlib import Path
import importlib
import json
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]

class AiEntryDomainsTests(unittest.TestCase):
    def module(self):
        return importlib.import_module('tools.analyze_rom_ai_entry_domains')

    def test_local_gate_domains_disprove_unconditional_eight_row_bound(self):
        m=self.module()
        self.assertEqual(tuple(range(1,255)),m.local_domain('primary_selected_candidate'))
        self.assertEqual(tuple(range(256)),m.local_domain('secondary_selected_candidate'))
        self.assertEqual(tuple(range(1,256)),m.local_domain('planner_nonzero'))
        with self.assertRaises(ValueError):m.local_domain('unknown_gate')

    def test_real_pinned_input_keeps_unknown_and_exposes_callee_and_exhaustion(self):
        report=self.module().analyze(ROOT)
        self.assertTrue(report['verified'])
        self.assertEqual(report['promotion_bytes'],0)
        self.assertEqual(report['decision'],'keep_unknown')
        self.assertFalse(report['scorer_index_domain_closed'])
        self.assertFalse(report['natural_runtime_reachability_proved'])
        self.assertEqual(report['known_planner_producers'],[0x7425a,0x7434e])
        self.assertEqual(report['deferred_obligations'],[
            'all scorer/planner incoming producers',
            'loop exhaustion slot 13 state',
            'callee 0x067158 and planner intermediate side effects',
            'all CD writers/copies and controlling state lifecycle',
        ])
        self.assertEqual(report['gates']['primary_selected_candidate']['first_above_7'],8)
        self.assertEqual(report['gates']['secondary_selected_candidate']['maximum'],255)
        self.assertEqual(report['gates']['planner_nonzero']['count'],255)

    def test_changed_rom_fails_closed_before_analysis(self):
        m=self.module();rom=bytearray((ROOT/'rom/base.gba').read_bytes());rom[0x74240]^=1
        with self.assertRaisesRegex(ValueError,'ROM identity'):
            m.analyze(ROOT,rom_bytes=bytes(rom))

    def test_consumer_slice_cannot_replace_instruction_owner(self):
        m=self.module();coverage=m.read_coverage(ROOT)
        owner=next(r for r in coverage['claims'] if r['id']==m.point_owner(coverage,0x74240)['id'])
        owner['claim_kind']='consumer_code_slice';owner['instruction_only_claimed']=False
        with self.assertRaisesRegex(ValueError,'instruction owner'):
            m.check_points(coverage,(ROOT/'rom/base.gba').read_bytes())

    def test_explicit_non_instruction_owner_flag_fails_closed(self):
        m=self.module();coverage=m.read_coverage(ROOT)
        owner=m.point_owner(coverage,0x74240)
        owner['instruction_only_claimed']=False
        with self.assertRaisesRegex(ValueError,'instruction owner'):
            m.check_points(coverage,(ROOT/'rom/base.gba').read_bytes())

    def test_existing_target_limited_bl_denominator_is_historical_reference(self):
        report=self.module().analyze(ROOT)
        source=report['historical_planner_direct_bl_denominator']
        self.assertEqual(source['target_offset'],0x851f8)
        self.assertEqual(source['producer_offsets'],[0x7425a,0x7434e])
        self.assertEqual(source['scan_range'],[0,6291456])
        self.assertFalse(source['raw_scan_replayed_here'])
        self.assertFalse(report['incoming_producer_denominator_complete'])

    def test_cli_is_repeatedly_stable_and_no_promotion(self):
        cmd=[sys.executable,'tools/analyze_rom_ai_entry_domains.py','--root',str(ROOT)]
        a=subprocess.check_output(cmd,cwd=ROOT);b=subprocess.check_output(cmd,cwd=ROOT)
        self.assertEqual(a,b);self.assertEqual(json.loads(a)['promotion_bytes'],0)

if __name__=='__main__':unittest.main()
