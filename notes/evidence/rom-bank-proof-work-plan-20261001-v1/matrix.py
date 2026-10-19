"""Read-only bank proof inventory, not a proof auditor or runtime verifier."""
import hashlib
import json
from pathlib import Path

for relative, expected in json.loads(Path(__file__).with_name('inputs.json').read_text()).items():
    assert expected is not None and hashlib.sha256(Path(relative).read_bytes()).hexdigest() == expected, relative

paths = ['sequel/bank-proofs.json', 'tools/audit_reverse_engineering_proof.py']
inputs = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
proofs = json.loads(Path(paths[0]).read_text())['banks']
rows = []
for name, proof in sorted(proofs.items()):
    if proof['catalog_classification'] == 'disproved':
        continue
    path = Path('sequel/content') / name / 'bank.json'
    raw = path.read_bytes()
    inputs[path.as_posix()] = hashlib.sha256(raw).hexdigest()
    assert inputs[path.as_posix()] == proof['bank_sha256'], name
    bank = json.loads(raw)
    fields = [field['name'] for field in bank['entry_format']['fields']]
    assert len(fields) == len(set(fields))
    assert len(bank['entries']) == bank['entry_count'] == proof['coverage']['records_total']
    evidence = []
    for item in proof['evidence']:
        p = Path(item['path'])
        actual = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        inputs[item['path']] = actual
        evidence.append(dict(item, observed_sha256=actual, identity_matches=actual == item['sha256']))
    verifiers = []
    for item in proof.get('verifiers', []):
        command = item['command']
        scripts = [s for s in command if s.startswith('tools/') and s.endswith('.py')]
        identities = {s: hashlib.sha256(Path(s).read_bytes()).hexdigest() if Path(s).is_file() else None for s in scripts}
        inputs.update(identities)
        verifiers.append({'command': command, 'script_identities': identities,
                          'script_identity_matches': bool(scripts) and all(v == item.get('script_sha256') for v in identities.values()),
                          'structured_contract_declared': isinstance(item.get('contract'), dict),
                          'absolute_arguments': [s for s in command if str(s).startswith('/')]})
    coverage = proof['coverage']
    rows.append({'bank': name, 'records': bank['entry_count'], 'schema_field_ids': fields,
                 'declared_coverage': coverage, 'field_denominator_matches_schema': coverage.get('field_ids_total') == fields,
                 'record_field_matrix_size': bank['entry_count'] * len(fields),
                 'schema_fields_not_in_declared_coverage': [f for f in fields if not isinstance(coverage.get('field_ids_covered'),list) or f not in coverage['field_ids_covered']],
                 'verifiers': verifiers, 'evidence': evidence, 'limitations': proof['limitations']})

result = {'schema': 'bank-proof-planning-matrix-v1', 'inputs': inputs, 'rows': rows,
          'summary': {'valid_banks': len(rows), 'declared_records_total': sum(r['records'] for r in rows),
                      'declared_records_covered': sum(r['declared_coverage']['records_covered'] for r in rows),
                      'banks_with_verifier_commands': sum(bool(r['verifiers']) for r in rows),
                      'banks_with_structured_contracts': sum(any(v['structured_contract_declared'] for v in r['verifiers']) for r in rows),
                      'banks_with_field_denominator_mismatch': sum(not r['field_denominator_matches_schema'] for r in rows),
                      'banks_with_absolute_command_arguments': sum(any(v['absolute_arguments'] for v in r['verifiers']) for r in rows),
                      'schema_record_field_matrix_size': sum(r['record_field_matrix_size'] for r in rows),
                      'evidence_identity_mismatches': sum(not e['identity_matches'] for r in rows for e in r['evidence']),
                      'verifier_identity_mismatches': sum(not v['script_identity_matches'] for r in rows for v in r['verifiers'])},
          'scope': 'Declared evidence, schema and command identity inventory only; verifiers not executed. Matrix cells include derived/raw fields and are not physical bytes or required experiment count.',
          'promotion_bytes': 0}
assert result['summary']['valid_banks'] == 22
assert result['summary']['declared_records_total'] == 2954
assert result['summary']['declared_records_covered'] == 23
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
