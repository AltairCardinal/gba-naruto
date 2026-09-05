"""Evidence selectors must resolve to the actual record that owns each claim."""
import hashlib
import gzip
import json
from pathlib import Path
import unittest

from tools import audit_rom_byte_coverage as auditor

ROOT = Path(__file__).resolve().parents[1]
FAST = {'rom-event-handler-cfg-v1', 'rom-sprite-component-source-v1',
        'rom-cfg-proven-roots-v16', 'rom-cfg-proven-roots-v16-consumed-literals-v1'}


def pointer(document, selector):
    for part in selector.removeprefix('/').split('/'):
        part=part.replace('~1','/').replace('~0','~')
        document=document[int(part)] if isinstance(document,list) else document[part]
    return document


class CoverageEvidenceSelectorRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom=(ROOT/'rom/base.gba').read_bytes()
        cls.coverage=json.loads((ROOT/'sequel/rom-byte-coverage.json').read_bytes())
        claims=cls.coverage['claims']
        cls.fast=auditor._fast_audit_four_packet_claims(ROOT,cls.rom,
            [c for c in claims if c.get('promotion_batch') not in FAST])
        cls.v10=auditor._cfg_proven_roots_v10_claims(ROOT,cls.rom,
            [c for c in claims if c.get('promotion_batch') != 'cfg-proven-roots-v10'])

    def test_fast_packet_selectors_resolve_to_matching_original_records(self):
        self.assertEqual(116,len(self.fast))
        docs={}
        for claim in self.fast:
            with self.subTest(claim=claim['id']):
                path=claim['evidence_path']
                if path not in docs:docs[path]=json.loads((ROOT/path).read_bytes())
                selected=pointer(docs[path],claim['evidence_selector'])
                interval=selected['range'] if isinstance(selected,dict) else selected[:2]
                self.assertEqual(claim['range'],interval)
                if isinstance(selected,dict):
                    self.assertEqual(claim['id'],selected['id'])
                    self.assertEqual(claim['bytes_sha256'],selected['bytes_sha256'])
                a,b=interval
                self.assertEqual(hashlib.sha256(self.rom[a:b]).hexdigest(),claim['bytes_sha256'])

    def test_v10_selectors_bind_blocks_not_merged_code_intervals(self):
        code=[c for c in self.v10 if c['claim_kind']==auditor.CFG_PROVEN_ROOTS_V10_CODE_KIND]
        self.assertEqual(7,len(code))
        doc=json.loads((ROOT/code[0]['evidence_path']).read_bytes())
        for claim in code:
            with self.subTest(claim=claim['id']):
                selected=pointer(doc,claim['evidence_selector'])
                self.assertIsInstance(selected,dict)
                self.assertEqual(claim['range'],selected['range'])
                self.assertEqual(claim['source_blocks'][0]['block_id'],selected['id'])
                self.assertEqual(claim['bytes_sha256'],selected['bytes_sha256'])

    def test_repairs_only_metadata_preserving_all_existing_claim_semantics(self):
        prior={c['id']:c for c in self.coverage['claims']}
        for claim in [*self.fast,*self.v10]:
            self.assertEqual({k:v for k,v in prior[claim['id']].items() if k!='evidence_selector'},
                             {k:v for k,v in claim.items() if k!='evidence_selector'})
        self.assertEqual(87749,self.coverage['summary']['unknown_bytes'])


class SelectorRepairCanonicalBindingTests(unittest.TestCase):
    def test_current_repaired_claim_selectors_resolve_to_their_byte_ranges(self):
        coverage=json.loads((ROOT/'sequel/rom-byte-coverage.json').read_bytes());documents={}
        selected=[c for c in coverage['claims'] if c.get('promotion_batch') in FAST or
                  (c.get('promotion_batch')=='cfg-proven-roots-v10' and c['claim_kind']==auditor.CFG_PROVEN_ROOTS_V10_CODE_KIND)]
        self.assertEqual(123,len(selected))
        for claim in selected:
            with self.subTest(claim=claim['id']):
                path=claim['evidence_path']
                if path not in documents:documents[path]=json.loads((ROOT/path).read_bytes())
                record=pointer(documents[path],claim['evidence_selector'])
                self.assertEqual(claim['range'],record['range'] if isinstance(record,dict) else record[:2])

    def test_current_proof_binds_updated_auditor_and_exact_project_input(self):
        proof=json.loads((ROOT/'sequel/reverse-engineering-proof.json').read_bytes())
        for gate in proof['gates'].values():
            for evidence in gate.get('evidence',[]):
                if evidence['path']=='sequel/project.json':
                    self.assertEqual(hashlib.sha256((ROOT/evidence['path']).read_bytes()).hexdigest(),evidence['sha256'])
        specs=[v for v in proof['gates']['rom_byte_coverage']['verifiers'] if 'tools/audit_rom_byte_coverage.py' in v['command']]
        self.assertEqual(1,len(specs))
        self.assertEqual(hashlib.sha256((ROOT/'tools/audit_rom_byte_coverage.py').read_bytes()).hexdigest(),specs[0]['script_sha256'])


class SelectorRepairReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=ROOT/'notes/evidence/rom-evidence-selector-repair-20260905'
        cls.manifest=json.loads((cls.directory/'manifest.json').read_bytes())
        cls.before=json.loads(gzip.decompress((cls.directory/'coverage-before.json.gz').read_bytes()))
        cls.after_raw=gzip.decompress((cls.directory/'coverage-after.json.gz').read_bytes())
        cls.after=json.loads(cls.after_raw)
        cls.proof_raw=(cls.directory/'proof-after.json').read_bytes()
        cls.formal=json.loads((cls.directory/'formal-report.json').read_bytes())
        cls.guard=json.loads((cls.directory/'formal-guard.json').read_bytes())

    def test_permanent_manifest_binds_exact_historical_members(self):
        actual={p.name for p in self.directory.iterdir()}
        self.assertEqual(set(self.manifest['files'])|{'manifest.json'},actual)
        for name,expected in self.manifest['files'].items():
            with self.subTest(member=name):
                raw=(self.directory/name).read_bytes()
                self.assertEqual({'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)},expected)
        self.assertEqual(self.manifest['after_coverage_sha256'],hashlib.sha256(self.after_raw).hexdigest())
        self.assertEqual(self.manifest['after_proof_sha256'],hashlib.sha256(self.proof_raw).hexdigest())

    def test_formal_binds_repaired_snapshot_and_successful_nondegraded_contracts(self):
        self.assertEqual(hashlib.sha256(self.proof_raw).hexdigest(),self.formal['trust_anchor']['spec_sha256'])
        self.assertEqual(106,len(self.formal['verifiers_executed']))
        self.assertTrue(all(v['contract_ok'] is True and v['exit_code']==0 for v in self.formal['verifiers_executed']))
        gate=self.formal['gate_results']['rom_byte_coverage']
        self.assertTrue(gate['evidence_valid']);self.assertEqual(96,gate['contracted_verifier_count'])
        self.assertEqual([],gate['rom_coverage_audit']['errors'])
        self.assertEqual(self.after['summary'],gate['rom_coverage_audit']['summary'])
        self.assertEqual((0,False,'completed'),(self.guard['exit_code'],self.guard['degraded'],self.guard['reason']))
        self.assertFalse(self.formal['complete']);self.assertEqual(175,len(self.formal['blockers']))
        self.assertFalse(self.formal['trust_anchor']['verified'])

    def test_archived_diff_contains_exactly_123_selector_only_repairs(self):
        self.assertEqual(self.before['summary'],self.after['summary'])
        self.assertEqual(self.before['segments'],self.after['segments'])
        self.assertEqual(len(self.before['claims']),len(self.after['claims']))
        changed=0
        for before,after in zip(self.before['claims'],self.after['claims']):
            self.assertEqual({k:v for k,v in before.items() if k!='evidence_selector'},
                             {k:v for k,v in after.items() if k!='evidence_selector'})
            changed+=before.get('evidence_selector')!=after.get('evidence_selector')
        self.assertEqual(123,changed);self.assertEqual(87749,self.after['summary']['unknown_bytes'])
