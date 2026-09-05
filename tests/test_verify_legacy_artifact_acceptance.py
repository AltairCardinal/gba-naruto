"""Independent historical acceptance must reject swapped or incomplete evidence."""
import base64
import copy
import gzip
import hashlib
import importlib
import json
import unittest
from unittest import mock

COVERAGE = 'sequel/rom-byte-coverage.json'
PROOF = 'sequel/reverse-engineering-proof.json'
PREFIX = 'notes/evidence/rom-evidence-selector-repair-20260905/'
FORMAL = PREFIX + 'formal-report.json'
GUARD = PREFIX + 'formal-guard.json'
AUDITOR = 'tools/audit_rom_byte_coverage.py'
FORMAL_AUDITOR = 'tools/audit_reverse_engineering_proof.py'
ROOTS = ['artifacts/direct', 'artifacts/aggregate', 'artifacts/baseline']


def raw(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def fixture():
    files = {}
    def put(path, value):
        files[path] = ('100644', value if isinstance(value, bytes) else raw(value))
    put('tools/direct.py', b'direct verifier\n')
    put('tools/aggregate.py', b'aggregate verifier\n')
    put(AUDITOR, b'from tools.aggregate import verify\nverify()\n')
    put(FORMAL_AUDITOR, b'formal auditor\n')
    put(ROOTS[0] + '/manifest.json', {'schema': 'legacy'})
    put(ROOTS[1] + '/manifest.json', {'schema': 'legacy'})
    put(ROOTS[1] + '/payload.json', {'ranges': [{'range': [0, 2]}]})
    baseline = raw({'schema': 'rom-byte-coverage-v1', 'summary': {'unknown_bytes': 4}})
    compressed = gzip.compress(baseline, mtime=0)
    put(ROOTS[2] + '/rom-byte-coverage.json.gz', compressed)
    put(ROOTS[2] + '/manifest.json', {'coverage': {
        'archive': {'file': 'rom-byte-coverage.json.gz', 'compression': 'gzip',
                    'sha256': sha(compressed), 'size': len(compressed)},
        'raw': {'sha256': sha(baseline), 'size': len(baseline)}}})
    claim = {'id': 'aggregate-0', 'promotion_manifest_path': ROOTS[1]+'/manifest.json',
             'promotion_manifest_sha256': sha(files[ROOTS[1]+'/manifest.json'][1]),
             'evidence_path': ROOTS[1]+'/payload.json',
             'evidence_sha256': sha(files[ROOTS[1]+'/payload.json'][1]),
             'evidence_selector': '/ranges/0', 'range': [0, 2],
             'independent_verifier_path': 'tools/aggregate.py',
             'independent_verifier_sha256': sha(files['tools/aggregate.py'][1])}
    summary = {'classified_bytes': 2, 'unknown_bytes': 2, 'claim_count': 1, 'segment_count': 2}
    put(COVERAGE, {'schema': 'rom-byte-coverage-v1', 'base_rom': {'sha256': 'a'*64, 'size': 4},
                   'summary': summary, 'claims': [claim], 'semantic_classification_complete': False,
                   'state_inventory_complete': True})
    verifiers = [
        {'command': ['python3', AUDITOR, '--root', '.'],
         'script_sha256': sha(files[AUDITOR][1]),
         'contract': {'format': 'json', 'assertions': {'/verified': True, '/summary/unknown_bytes': 2}}},
        {'command': ['python3', 'tools/direct.py', '--artifact', ROOTS[0]],
         'script_sha256': sha(files['tools/direct.py'][1]),
         'contract': {'format': 'json', 'assertions': {'/verified': True}}}]
    put(PROOF, {'base_rom': {'sha256': 'a'*64, 'size': 4}, 'gates': {'rom_byte_coverage': {
        'evidence': [{'path': COVERAGE, 'sha256': sha(files[COVERAGE][1])}],
        'verifiers': verifiers}}})
    put(FORMAL, {'schema': 'reverse-engineering-proof-audit-v2', 'complete': False,
                 'blockers': ['unknown remains'],
                 'trust_anchor': {'spec_sha256': sha(files[PROOF][1]),
                                  'verified': False, 'externally_supplied': False},
                 'verifiers_executed': [
                     {'command': ['/python3', *v['command'][1:]], 'contract_ok': True,
                      'exit_code': 0, **({'execution': 'reused-in-process'} if i == 0 else {})}
                     for i, v in enumerate(verifiers)],
                 'gate_results': {'rom_byte_coverage': {
                     'contracted_verifier_count': 2, 'hash_bound_verifier_count': 2,
                     'evidence_valid': True, 'rom_coverage_audit': {
                         'schema': 'rom-byte-coverage-audit-v1', 'verified': True, 'errors': [],
                         'semantic_classification_complete': False, 'state_inventory_complete': True,
                         'summary': summary}}}})
    put(GUARD, {'exit_code': 0, 'degraded': False, 'reason': 'completed',
                'command': ['/bin/sh', '-c', 'python3 -u '+FORMAL_AUDITOR+
                            ' --root . --spec '+PROOF+' --execute-verifiers --allow-incomplete'
                            ' --output build/frozen/formal-report.json > build/frozen/formal.log 2>&1']})
    return files


class HistoricalAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = importlib.import_module('tools.verify_legacy_artifact_acceptance')

    def mutate_json(self, files, path, change):
        value = json.loads(files[path][1]); change(value); files[path] = ('100644', raw(value))

    def test_requires_the_selector_repair_formal_receipt_domain(self):
        repaired = 'notes/evidence/rom-evidence-selector-repair-20260905/'
        historical = 'notes/evidence/rom-post-story-four-packet-tier2-20260905/'
        files = fixture()
        files[repaired+'formal-report.json'] = files.pop(FORMAL)
        files[repaired+'formal-guard.json'] = files.pop(GUARD)
        self.assertEqual(3, len(self.verifier.inspect_snapshot(files, ROOTS)['roots']))
        files[historical+'formal-report.json'] = files.pop(repaired+'formal-report.json')
        files[historical+'formal-guard.json'] = files.pop(repaired+'formal-guard.json')
        with self.assertRaisesRegex(ValueError, 'missing snapshot member'):
            self.verifier.inspect_snapshot(files, ROOTS)

    def test_three_distinct_bridges_preserve_unknown_and_do_not_reexecute_semantics(self):
        result = self.verifier.inspect_snapshot(fixture(), ROOTS)
        self.assertEqual(3, len(result['roots']))
        self.assertEqual('direct_proof_verifier', result['roots'][ROOTS[0]]['bridge_kind'])
        self.assertEqual('aggregate_coverage_verifier', result['roots'][ROOTS[1]]['bridge_kind'])
        self.assertEqual('immutable_precoverage_binding', result['roots'][ROOTS[2]]['bridge_kind'])
        self.assertIsNone(result['roots'][ROOTS[1]]['claim_verifiers'][0]['report_sha256'])
        self.assertEqual(2, result['summary']['unknown_bytes'])
        self.assertEqual(0, result['summary']['newly_classified_bytes'])
        self.assertFalse(result['summary']['semantic_verifiers_reexecuted'])

    def test_rejects_formal_proof_and_coverage_substitution(self):
        for path, change in [
            (FORMAL, lambda x: x['trust_anchor'].update(spec_sha256='0'*64)),
            (FORMAL, lambda x: x['gate_results']['rom_byte_coverage']['rom_coverage_audit']['summary'].update(unknown_bytes=0)),
            (COVERAGE, lambda x: x['summary'].update(unknown_bytes=0)),
            (PROOF, lambda x: x['gates']['rom_byte_coverage']['evidence'][0].update(sha256='0'*64)),
        ]:
            with self.subTest(path=path):
                files=fixture();self.mutate_json(files,path,change)
                with self.assertRaises(ValueError): self.verifier.inspect_snapshot(files, ROOTS)

    def test_preserves_isolated_python_flags_while_binding_the_actual_script(self):
        files=fixture()
        self.mutate_json(files,PROOF,lambda x:x['gates']['rom_byte_coverage']['verifiers'][1]['command'].__setitem__(slice(1,1),['-I','-S']))
        self.mutate_json(files,FORMAL,lambda x:x['trust_anchor'].update(spec_sha256=sha(files[PROOF][1])))
        self.mutate_json(files,FORMAL,lambda x:x['verifiers_executed'][1]['command'].__setitem__(slice(1,1),['-I','-S']))
        self.assertEqual([1],self.verifier.inspect_snapshot(files,ROOTS)['roots'][ROOTS[0]]['proof_verifier_indices'])
        self.mutate_json(files,FORMAL,lambda x:x['verifiers_executed'][1]['command'].remove('-I'))
        with self.assertRaises(ValueError):self.verifier.inspect_snapshot(files,ROOTS)

    def test_rejects_missing_failed_or_argument_changed_formal_command(self):
        for change in [lambda x:x['verifiers_executed'].pop(),
                       lambda x:x['verifiers_executed'][1].update(contract_ok=False),
                       lambda x:x['verifiers_executed'][1]['command'].append('--skip'),
                       lambda x:x['verifiers_executed'].append(copy.deepcopy(x['verifiers_executed'][1]))]:
            files=fixture();self.mutate_json(files,FORMAL,change)
            with self.assertRaises(ValueError): self.verifier.inspect_snapshot(files,ROOTS)

    def test_rejects_guard_degraded_failed_and_wrong_spec(self):
        for change in [lambda x:x.update(degraded=True), lambda x:x.update(exit_code=1),
                       lambda x:x['command'].__setitem__(2,x['command'][2].replace(PROOF,'wrong.json'))]:
            files=fixture();self.mutate_json(files,GUARD,change)
            with self.assertRaises(ValueError): self.verifier.inspect_snapshot(files,ROOTS)

    def test_rejects_wrong_claim_manifest_evidence_selector_and_verifier(self):
        # Rebind the outer receipt intentionally: the independent inner links must fail.
        for field,value in [('promotion_manifest_sha256','0'*64),('evidence_sha256','0'*64),
                            ('evidence_selector','/ranges/9'),('independent_verifier_sha256','0'*64)]:
            files=fixture();self.mutate_json(files,COVERAGE,lambda x:x['claims'][0].update({field:value}))
            self.mutate_json(files,PROOF,lambda x:x['gates']['rom_byte_coverage']['evidence'][0].update(sha256=sha(files[COVERAGE][1])))
            self.mutate_json(files,FORMAL,lambda x:x['trust_anchor'].update(spec_sha256=sha(files[PROOF][1])))
            with self.assertRaises(ValueError): self.verifier.inspect_snapshot(files,ROOTS)

    def test_rejects_incomplete_baseline_or_wrong_raw_identity(self):
        for action in ['missing','corrupt','wrong-raw']:
            files=fixture()
            if action=='missing': del files[ROOTS[2]+'/rom-byte-coverage.json.gz']
            elif action=='corrupt': files[ROOTS[2]+'/rom-byte-coverage.json.gz']=('100644',b'bad')
            else:self.mutate_json(files,ROOTS[2]+'/manifest.json',lambda x:x['coverage']['raw'].update(sha256='0'*64))
            with self.assertRaises(ValueError): self.verifier.inspect_snapshot(files,ROOTS)

    def test_rejects_unsafe_path_nonregular_mode_and_duplicate_root(self):
        for name,mode in [('../escape','100644'),('/absolute','100644'),('x//y','100644'),('x','120000')]:
            files=fixture();files[name]=(mode,b'x')
            with self.assertRaises(ValueError): self.verifier.inspect_snapshot(files,ROOTS)
        with self.assertRaises(ValueError):self.verifier.inspect_snapshot(fixture(),ROOTS+[ROOTS[0]])

    def test_archive_rejects_duplicate_json_and_noncanonical_base64(self):
        with self.assertRaises(ValueError): self.verifier.decode_snapshot(gzip.compress(b'{"files":{},"files":{}}'))
        payload={'schema':'legacy-artifact-snapshot-v1','files':{'safe':{'mode':'100644','data_base64':'@@'}}}
        with self.assertRaises(ValueError): self.verifier.decode_snapshot(gzip.compress(raw(payload)))

    def test_direct_bridge_requires_an_explicit_success_contract(self):
        files=fixture()
        self.mutate_json(files,PROOF,lambda x:x['gates']['rom_byte_coverage']['verifiers'][1]['contract']['assertions'].update({'/verified':False}))
        self.mutate_json(files,FORMAL,lambda x:x['trust_anchor'].update(spec_sha256=sha(files[PROOF][1])))
        with self.assertRaises(ValueError):self.verifier.inspect_snapshot(files,ROOTS)

    def test_pinned_bundle_rejects_coherently_rewritten_or_incomplete_inputs(self):
        files=fixture()
        def package(inputs,roots):
            inspected=self.verifier.inspect_snapshot(inputs,roots)
            archive=gzip.compress(raw({'schema':'legacy-artifact-snapshot-v1','files':{
                p:{'mode':mode,'data_base64':base64.b64encode(value).decode()} for p,(mode,value) in inputs.items()}}),mtime=0)
            catalog=raw({'schema':'legacy-artifact-acceptance-catalog-v1',**inspected,
                         'input_files':self.verifier.identities(inputs)})
            return {'catalog.json':('100644',catalog),'snapshot.json.gz':('100644',archive),
                    'manifest.json':('100644',b'modern manifest')}
        original=package(files,ROOTS)
        with mock.patch.object(self.verifier,'BUNDLE_IDENTITIES',self.verifier.identities(original),create=True):
            self.assertEqual('accepted',self.verifier.verify_bundle_members(original)['artifact_status'])
            altered=copy.deepcopy(files);del altered[ROOTS[0]+'/manifest.json']
            omitted=package(altered,ROOTS[1:])
            altered=copy.deepcopy(files);altered[FORMAL_AUDITOR]=('100644',b'substituted auditor')
            wrong_tool=package(altered,ROOTS)
            altered=copy.deepcopy(files)
            self.mutate_json(altered,GUARD,lambda x:x['command'].__setitem__(2,x['command'][2].replace('build/frozen/','build/other/')))
            wrong_run=package(altered,ROOTS)
            for candidate in (omitted,wrong_tool,wrong_run,{**original,'extra':('100644',b'x')},
                              {**original,'manifest.json':('100755',b'modern manifest')}):
                with self.subTest(candidate=list(candidate)):
                    with self.assertRaises(ValueError):self.verifier.verify_bundle_members(candidate)

    def test_reuses_each_immutable_payload_parse_within_one_snapshot(self):
        files=fixture()
        self.mutate_json(files,COVERAGE,lambda x:x['claims'].append({**x['claims'][0],'id':'aggregate-1'}))
        self.mutate_json(files,PROOF,lambda x:x['gates']['rom_byte_coverage']['evidence'][0].update(sha256=sha(files[COVERAGE][1])))
        self.mutate_json(files,FORMAL,lambda x:x['trust_anchor'].update(spec_sha256=sha(files[PROOF][1])))
        with mock.patch.object(self.verifier,'parse',wraps=self.verifier.parse) as parser:
            self.verifier.inspect_snapshot(files,ROOTS)
        payload=files[ROOTS[1]+'/payload.json'][1]
        self.assertEqual(1,sum(c.args[0]==payload for c in parser.call_args_list))

    def test_catalog_rejects_omitted_member_and_swapped_bridge(self):
        files=fixture();inspection=self.verifier.inspect_snapshot(files,ROOTS)
        snapshot=gzip.compress(raw({'schema':'legacy-artifact-snapshot-v1','files':{
            p:{'mode':mode,'data_base64':base64.b64encode(value).decode()} for p,(mode,value) in files.items()}}),mtime=0)
        catalog={'schema':'legacy-artifact-acceptance-catalog-v1',**inspection,
                 'input_files':{p:{'mode':mode,'size':len(value),'sha256':sha(value)} for p,(mode,value) in files.items()}}
        self.verifier.verify_archive(raw(catalog),snapshot)
        for change in [lambda x:x['roots'][ROOTS[0]]['members'].clear(),
                       lambda x:x['roots'][ROOTS[2]].update(bridge_kind='direct_proof_verifier'),
                       lambda x:x['input_files'].pop(GUARD)]:
            changed=copy.deepcopy(catalog);change(changed)
            with self.assertRaises(ValueError):self.verifier.verify_archive(raw(changed),snapshot)


if __name__ == '__main__':
    unittest.main()
