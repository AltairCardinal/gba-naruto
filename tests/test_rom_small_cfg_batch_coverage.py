"""Fail-closed live projection; fixed precoverage remains reproducible afterward."""
import copy
import gzip
import json
from pathlib import Path
import unittest
from tools import audit_rom_byte_coverage as auditor

ROOT = Path(__file__).resolve().parents[1]
BATCH = 'rom-small-cfg-dependency-batch-v1'


class SmallBatchProjectionTests(unittest.TestCase):
    def project(self, prior):
        helper = getattr(auditor, '_small_cfg_dependency_batch_claims', None)
        self.assertIsNotNone(helper, 'verified four-packet batch lacks a live coverage projection')
        return helper(ROOT, (ROOT/'rom/base.gba').read_bytes(), prior)

    def baseline(self):
        return json.loads(gzip.decompress((ROOT/'notes/evidence/rom-evidence-selector-repair-20260905/coverage-after.json.gz').read_bytes()))

    def test_exact_typed_projection_and_cfg_aggregate(self):
        baseline = self.baseline()
        claims = self.project(baseline['claims'])
        self.assertEqual((len(claims),sum(b-a for a,b in (r['range'] for r in claims))), (21,118))
        spans = [r['range'] for r in claims]
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])))
        by_kind = {}
        for row in claims:
            by_kind[row['claim_kind']] = by_kind.get(row['claim_kind'],0)+row['range'][1]-row['range'][0]
            self.assertTrue(row['current_unknown_verified_by_auditor'])
            self.assertFalse(row['runtime_reachability_claimed'])
        self.assertEqual(by_kind, {'small_cfg_dependency_reachable_instruction_bytes':78,
            'small_cfg_dependency_consumed_literal_word_bytes':12,
            'small_cfg_dependency_alignment_bytes':24,
            'small_cfg_dependency_dispatch_table_bytes':4})
        before = auditor._cfg_code_aggregate(baseline['claims'])
        after = auditor._cfg_code_aggregate(baseline['claims']+claims)
        self.assertEqual(after['cfg_reachable_thumb_code_bytes']-before['cfg_reachable_thumb_code_bytes'],78)
        self.assertEqual(after['cfg_primary_claim_count']-before['cfg_primary_claim_count'],5)
        self.assertEqual(after['cfg_code_claim_kind_count']-before['cfg_code_claim_kind_count'],1)

    def test_live_overlap_is_rejected_without_changing_input(self):
        baseline = self.baseline()
        claims = self.project(baseline['claims'])
        prior = baseline['claims']+[claims[0]]
        before = copy.deepcopy(prior)
        with self.assertRaises(ValueError):
            self.project(prior)
        self.assertEqual(prior,before)


if __name__ == '__main__':
    unittest.main()
