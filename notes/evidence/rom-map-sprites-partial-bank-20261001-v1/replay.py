import json, sys, hashlib
from pathlib import Path
from tools.verify_map_sprites_partial_bank import verify_partial_bank, proof_binding
from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract
root = Path('.').resolve()
run = root / 'build/experiments/active/map-sprites-typed-contract/tier1-20261001-v1'
def write(name, value):
    (run / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
result = verify_partial_bank(root)
repeated = verify_partial_bank(root)
assert result == repeated
proposal = proof_binding(root, result)
write('result.json', result)
write('result-repeated.json', repeated)
write('proposal.json', proposal)
blockers, commands = [], []
partial = _check_bank(root, 'map-sprites', root / 'sequel/content/map-sprites/bank.json', proposal, None, blockers, commands)
assert partial['complete'] is False and partial['contracted_verifier_count'] == 1
assert len(commands) == 1
cli_blockers = []
v = proposal['verifiers'][0]
cli = _execute_contract(root, 'map-sprites', [sys.executable, *v['command'][1:]], v['contract'], cli_blockers)
assert cli['contract_ok'] is True and cli_blockers == []
write('auditor-integration.json', {'partial_bank': partial, 'partial_blockers': blockers, 'cli': cli, 'cli_blockers': cli_blockers, 'live_catalog_modified': False})
write('canonical-identity.json', {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ['sequel/rom-byte-coverage.json', 'sequel/reverse-engineering-proof.json', 'sequel/bank-proofs.json']})
print(json.dumps({'verified': True, 'cells_total': result['cells_total'], 'cells_covered': len(result['cells_covered']), 'partial_gate_rejected': not partial['complete']}))
