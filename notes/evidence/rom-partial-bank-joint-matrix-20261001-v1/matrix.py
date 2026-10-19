"""Read-only archived partial-bank batch; not a formal completion auditor."""
import argparse, copy, hashlib, importlib, json, subprocess, sys, time
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, default=Path.cwd())
p.add_argument('--plan', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(); root = a.root.resolve(); output = a.output.resolve()
sys.path.insert(0, str(root))
from tools.rom_small_cfg_callback_gaps_independent_verifier import read_regular, sha
from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract
plan_raw = read_regular(a.plan.resolve())
assert sha(plan_raw) == '8dd439c4adecbe34b1f888aa2a57bd6b0600c901baf8e7af634c48c69d126594', 'frozen plan drift'
plan = json.loads(plan_raw)
def write(name, value):
    path = output / name; path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
def identities():
    actual = {name: sha(read_regular(root / name)) for name in plan['inputs']}
    assert actual == plan['inputs'], 'frozen input drift'
    return actual
identities()
catalog = json.loads(read_regular(root / 'sequel/bank-proofs.json'))['banks']
full_rows = []
for bank in plan['all_valid_banks']:
    path = f'sequel/content/{bank}/bank.json'; raw = read_regular(root / path)
    schema = json.loads(raw); fields = [v['name'] for v in schema['entry_format']['fields']]
    assert len(fields) == len(set(fields)) and schema['entry_count'] == len(schema['entries'])
    assert sha(raw) == catalog[bank]['bank_sha256']
    full_rows.append({'bank': bank, 'bank_sha256': sha(raw), 'records': schema['entry_count'],
                     'field_ids': fields, 'cells': schema['entry_count'] * len(fields),
                     'live_declared_records_covered': catalog[bank]['coverage']['records_covered'],
                     'live_typed_contract_count': sum(isinstance(v.get('contract'), dict) for v in catalog[bank]['verifiers'])})
assert {'banks':len(full_rows), 'records':sum(r['records'] for r in full_rows), 'cells':sum(r['cells'] for r in full_rows)} == plan['global_denominator']
rows = []
for case in plan['cases']:
    start = time.monotonic(); name = case['bank']; module = importlib.import_module(case['module'])
    if case['kind'] == 'partial':
        result = module.verify_partial_bank(root); proposal = module.proof_binding(root, result)
    else:
        result = module.verify_artifact(root, root / case['artifact'])
        assert result.get('verified') is True, (name, result)
        proposal = module.proof_binding(root, root / case['artifact'], result)
    assert result['verified'] is True and result['exhaustive'] is False and result['physical_gba_verified'] is False
    bank_path = root / f'sequel/content/{name}/bank.json'; schema = json.loads(read_regular(bank_path))
    fields = [v['name'] for v in schema['entry_format']['fields']]; ids = [str(i) for i in range(schema['entry_count'])]
    coverage = proposal['coverage']; all_cells = [{'record_id':i, 'field_id':f} for i in ids for f in fields]
    covered = coverage['cells_covered']; uncovered = coverage['cells_uncovered']
    assert coverage['record_ids_total'] == ids and coverage['field_ids_total'] == fields
    assert coverage['cells_total'] == len(all_cells) and len(covered) == len({(c['record_id'], c['field_id']) for c in covered})
    assert all(c in all_cells for c in covered) and uncovered == [c for c in all_cells if c not in covered]
    assert coverage['record_ids_covered'] == [i for i in ids if any(c['record_id'] == i for c in covered)]
    assert coverage['field_ids_covered'] == [f for f in fields if any(c['field_id'] == f for c in covered)]
    blockers, commands = [], []
    bank_check = _check_bank(root, name, bank_path, proposal, None, blockers, commands)
    assert bank_check['complete'] is False and bank_check['contracted_verifier_count'] == 1 and len(commands) == 1
    v = proposal['verifiers'][0]; command = [sys.executable, *v['command'][1:]]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=180, check=False)
    case_output = output / 'cases' / name; case_output.mkdir(parents=True)
    (case_output/'stdout.json').write_text(completed.stdout); (case_output/'stderr.txt').write_text(completed.stderr)
    assert completed.returncode == 0, (name, completed.stderr)
    actual = json.loads(completed.stdout)
    for key,value in v['contract']['assertions'].items():
        assert actual[key.removeprefix('/')] == value, (name, key)
    cli_blockers=[]; cli = _execute_contract(root, name, command, v['contract'], cli_blockers)
    assert cli['contract_ok'] is True and cli_blockers == []
    rejections = []
    for pointer, value in [('/record_ids_covered', ids), ('/physical_gba_verified', True)]:
        wrong = copy.deepcopy(v['contract']); wrong['assertions'][pointer] = value
        rejected_blockers=[]; rejected = _execute_contract(root,name,command,wrong,rejected_blockers)
        assert rejected['contract_ok'] is False and any('contract mismatch' in x for x in rejected_blockers)
        rejections.append({'changed_assertion':pointer,'expected_rejection':True,'auditor_result':rejected,'blockers':rejected_blockers})
    identities()
    row = {'bank':name, 'scope':case['scope'], 'source_artifact':case['artifact'],
           'bank_sha256':proposal['bank_sha256'], 'coverage':coverage, 'limitations':proposal['limitations'],
           'changed_pixel_count':result['changed_pixel_count'], 'result_scope_flags':{k:result[k] for k in result if any(x in k for x in ['natural','zero_input','physical','exhaustive','shared_lock','current_emulator','portable_offline','scratch_prefix'])},
           'auditor_bank_check':bank_check,'auditor_cli':cli,'negative_claim_checks':rejections,
           'live_coverage':catalog[name]['coverage'], 'new_runtime_samples':0,
           'seconds':round(time.monotonic()-start,3)}
    write(f'cases/{name}/result.json',result); write(f'cases/{name}/proposal.json',proposal)
    write(f'cases/{name}/matrix-row.json',row); rows.append(row)
    print(json.dumps({'finished':name,'cells_covered':len(covered),'cells_total':len(all_cells)}),flush=True)
summary={'banks':len(rows),'records':sum(r['coverage']['records_total'] for r in rows),'cells':sum(r['coverage']['cells_total'] for r in rows),'covered_cells':sum(len(r['coverage']['cells_covered']) for r in rows)}
assert summary == plan['partial_denominator']
summary.update({'uncovered_cells':sum(len(r['coverage']['cells_uncovered']) for r in rows),'auditor_cli_passed':sum(r['auditor_cli']['contract_ok'] for r in rows),'full_bank_gates_rejected':sum(not r['auditor_bank_check']['complete'] for r in rows),'negative_claims_rejected':sum(len(r['negative_claim_checks']) for r in rows),'new_runtime_samples':0})
write('matrix.json',{'schema':'partial-bank-joint-replay-v1','summary':summary,'global_inventory':full_rows,'rows':rows,'scope':plan['scope'],'live_catalog_modified':False,'canonical_written':False})
write('proposals.json',{'schema':'partial-bank-joint-proposals-v1','banks':{r['bank']:json.loads((output/'cases'/r['bank']/'proposal.json').read_text()) for r in rows}})
write('final-identities.json',identities())
print(json.dumps(summary),flush=True)
