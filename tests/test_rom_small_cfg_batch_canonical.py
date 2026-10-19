"""Inspect actual Tier-2 canonical; candidates and arithmetic are insufficient."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BATCH = 'rom-small-cfg-dependency-batch-v1'


class CanonicalBatchTests(unittest.TestCase):
    def test_landed_batch_is_exact_disjoint_and_preserves_unknown_holes(self):
        coverage = json.loads((ROOT/'sequel/rom-byte-coverage.json').read_text())
        claims = [r for r in coverage['claims'] if r.get('promotion_batch') == BATCH]
        self.assertEqual(len(claims),21,'Tier-1 candidate has not been materialized in canonical')
        self.assertEqual(sum(b-a for a,b in (r['range'] for r in claims)),118)
        spans = sorted(r['range'] for r in claims)
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])))
        self.assertEqual((coverage['summary']['classified_bytes'],coverage['summary']['unknown_bytes']),
                         (6203825,87631))
        self.assertEqual(coverage['summary']['cfg_reachable_thumb_code_bytes'],173136)
        self.assertEqual(coverage['summary']['cfg_primary_claim_count'],4064)
        self.assertEqual(coverage['summary']['cfg_code_claim_kind_count'],55)
        for a,b in [(0x7ADFE,0x7AE00),(0x7B8B2,0x7B8B4),(0x7DCD2,0x7DCD4)]:
            segments = [r for r in coverage['segments'] if r['range'][0]<b and a<r['range'][1]]
            self.assertTrue(segments)
            self.assertTrue(all(r['primary_class']=='unknown' for r in segments))
        for row in claims:
            segments=[r for r in coverage['segments'] if r['range'][0]<row['range'][1]
                      and row['range'][0]<r['range'][1]]
            self.assertTrue(all(r['primary_claim_ids']==[row['id']] for r in segments))
            self.assertTrue(row['current_unknown_verified_by_auditor'])

    def test_proof_binds_current_canonical_and_batch_verifier_contract(self):
        import hashlib
        proof=json.loads((ROOT/'sequel/reverse-engineering-proof.json').read_text())
        gate=proof['gates']['rom_byte_coverage']
        evidence={row['path']:row['sha256'] for row in gate['evidence']}
        path='artifacts/rom-small-cfg-dependency-batch-v1/manifest.json'
        self.assertIn(path,evidence,'published batch is absent from formal proof')
        self.assertEqual(evidence[path],hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
        self.assertEqual(evidence['sequel/rom-byte-coverage.json'],
            hashlib.sha256((ROOT/'sequel/rom-byte-coverage.json').read_bytes()).hexdigest())
        verifiers=[row for row in gate['verifiers'] if 'tools/verify_rom_small_cfg_dependency_batch.py' in row['command']]
        self.assertEqual(len(verifiers),1)
        assertions=verifiers[0]['contract']['assertions']
        self.assertEqual((assertions['/promotion_bytes'],assertions['/claim_count'],assertions['/packet_count']),
                         (118,21,4))
        self.assertFalse(assertions['/natural_runtime_reachability_claimed'])

    def test_permanent_formal_receipt_proves_execution_and_preserves_incomplete(self):
        import hashlib
        receipt=ROOT/'notes/evidence/rom-small-cfg-batch-formal-20260930-v1'
        manifest=json.loads((receipt/'manifest.json').read_text())
        for name,row in manifest['files'].items():
            raw=(receipt/name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            self.assertEqual(len(raw),row['size_bytes'])
        report=json.loads((receipt/'formal-report.json').read_text())
        guard=json.loads((receipt/'formal-guard.json').read_text())
        self.assertEqual((guard['reason'],guard['exit_code'],guard['degraded']),
                         ('completed',0,False))
        self.assertFalse(report['complete'])
        self.assertEqual(len(report['blockers']),175)
        self.assertEqual(len(report['verifiers_executed']),107)
        self.assertTrue(all(v['contract_ok'] and v['exit_code']==0
                            for v in report['verifiers_executed']))
        selected=[v for v in report['verifiers_executed']
                  if 'tools/verify_rom_small_cfg_dependency_batch.py' in v['command']]
        self.assertEqual(len(selected),1)
        gate=report['gate_results']['rom_byte_coverage']
        self.assertEqual(gate['contracted_verifier_count'],97)
        self.assertTrue(gate['rom_coverage_audit']['verified'])
        self.assertEqual(gate['rom_coverage_audit']['summary']['unknown_bytes'],87631)
        spec=(receipt/'proof-after.json').read_bytes()
        self.assertEqual(report['trust_anchor']['spec_sha256'],hashlib.sha256(spec).hexdigest())


if __name__ == '__main__':
    unittest.main()
