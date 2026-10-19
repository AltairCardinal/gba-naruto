import contextlib
import json
from pathlib import Path
import sys
import traceback

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
from tools.export_cutscene_obj_secondary_ptr_ab import export_artifact
from tools.verify_cutscene_obj_secondary_ptr_ab import verify_artifact, proof_binding, canonical, sha, BANK
from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract

run = ROOT / 'build/experiments/active/cutscene-secondary-ptr-contract/tier1-20261001-v1'
source = ROOT / 'notes/evidence/rom-cutscene-secondary-ptr-shared-lock-20261001-v1/source'
with (run / 'publication.log').open('w', buffering=1) as log:
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            artifact = export_artifact(ROOT, source, run / 'final')
            first = verify_artifact(ROOT, artifact)
            second = verify_artifact(ROOT, artifact)
            assert first == second and first['verified'] is True
            (run / 'verification.json').write_bytes(canonical(first))
            (run / 'verification-repeated.json').write_bytes(canonical(second))
            proof = proof_binding(ROOT, artifact, first)
            (run / 'partial-bank-proposal.json').write_bytes(canonical(proof))
            row = proof['verifiers'][0]
            blockers = []
            replay = _execute_contract(ROOT, 'cutscene-scripts', [sys.executable, *row['command'][1:]], row['contract'], blockers)
            assert replay['contract_ok'] is True, blockers
            commands, incomplete = [], []
            bank = _check_bank(ROOT, 'cutscene-scripts', ROOT / BANK, proof, None, incomplete, commands)
            assert bank['complete'] is False and bank['contracted_verifier_count'] == 1
            assert any('not exhaustively ID-bound' in b for b in incomplete)
            assert any('field coverage is not exhaustive' in b for b in incomplete)
            (run / 'auditor-integration.json').write_bytes(canonical({'replay': replay, 'blockers': blockers,
                                                                   'bank': bank, 'bank_gate_blockers': incomplete}))
            identities = {p: sha((ROOT / p).read_bytes()) for p in
                          ('sequel/rom-byte-coverage.json', 'sequel/reverse-engineering-proof.json', 'sequel/bank-proofs.json')}
            assert list(identities.values()) == ['b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2',
                '465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568',
                'f52524fbba244cf0497ffa021503702da9a185485c13027872f2a65dad56bed2']
            (run / 'canonical-identity.json').write_bytes(canonical(identities))
            print(json.dumps({'verified': True, 'cells': '1/16', 'pixels': 778, 'canonical_written': False}))
        except BaseException:
            traceback.print_exc()
            raise
