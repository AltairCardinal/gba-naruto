#!/usr/bin/env python3
from __future__ import annotations
import ast, json
from pathlib import Path
import tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=json.loads((ROOT/'build/experiments/active/cfg-proven-roots-batch-consumed-literals/preflight-20260901/CONTRACT.json').read_text())

def load():
    try: from tools import export_rom_cfg_proven_roots_batch_consumed_literals as module
    except (ImportError,ModuleNotFoundError) as error: raise AssertionError('batch exporter is absent') from error
    return module

class BatchExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.module=load(); cls.payload=cls.module.build_payload(ROOT)
    def test_frozen_union_and_family_denominators(self):
        self.assertEqual(CONTRACT['families'],self.payload['families'])
        self.assertEqual(CONTRACT['denominator'],self.payload['denominator'])
        self.assertEqual(CONTRACT['coverage_projection'],self.payload['coverage_projection'])
        self.assertEqual(0,self.payload['cross_family_target_overlap_word_count'])
        self.assertEqual(0,self.payload['v3_packet_target_overlap_word_count'])
    def test_exact_sorted_ranges(self):
        ranges=self.payload['promotion']['ranges']; self.assertEqual(sorted(ranges),ranges)
        self.assertEqual(1256,sum(b-a for a,b in ranges)); self.assertEqual(116,len(ranges))
    def test_export_is_closed_and_does_not_import_verifier(self):
        with tempfile.TemporaryDirectory() as raw:
            out=Path(raw)/'candidate';self.module.export(ROOT,out)
            self.assertEqual({'manifest.json',self.module.PAYLOAD_NAME},{p.name for p in out.iterdir()})
        tree=ast.parse((ROOT/'tools/export_rom_cfg_proven_roots_batch_consumed_literals.py').read_text())
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module]
        self.assertFalse(any('verify_rom_cfg_proven_roots_batch_consumed_literals' in x for x in imports))

if __name__=='__main__': unittest.main()
