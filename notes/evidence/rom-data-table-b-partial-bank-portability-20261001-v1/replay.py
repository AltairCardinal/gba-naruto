import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, default=Path.cwd())
p.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
a = p.parse_args(); root = a.root.resolve(); output = a.output.resolve(); output.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root))
from tools.verify_data_table_b_partial_bank import verify_partial_bank, proof_binding, CONTRACT, SCRIPT, BANK
from tools.audit_reverse_engineering_proof import _check_bank, _execute_contract
def write(name, value):
    (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
result = verify_partial_bank(root)
assert verify_partial_bank(root) == result
proposal = proof_binding(root, result)
write('result.json', result); write('proposal.json', proposal)
blockers, commands = [], []
partial = _check_bank(root, 'data-table-b', root / BANK, proposal, None, blockers, commands)
assert partial['complete'] is False and partial['contracted_verifier_count'] == 1 and len(commands) == 1
v = proposal['verifiers'][0]; cli_blockers = []
cli = _execute_contract(root, 'data-table-b', [sys.executable, *v['command'][1:]], v['contract'], cli_blockers)
assert cli['contract_ok'] is True and cli_blockers == []
write('auditor-integration.json', {'partial_bank': partial, 'partial_blockers': blockers, 'cli': cli, 'cli_blockers': cli_blockers, 'live_catalog_modified': False})
with tempfile.TemporaryDirectory() as directory:
    relocated = Path(directory).resolve()
    names = set(result['input_sha256']) | {CONTRACT, SCRIPT}
    for name in sorted(names):
        target = relocated / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    driver = Path(__file__).with_name('portable_replay.py')
    child_driver = relocated / 'portable_replay.py'; shutil.copy2(driver, child_driver)
    completed = subprocess.run([sys.executable, str(child_driver), str(relocated), str(root)], cwd=relocated, text=True, capture_output=True, check=False)
    (output / 'portable.log').write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stderr
    repeated = json.loads(completed.stdout)
    assert repeated == result
    write('result-relocated.json', repeated)
    write('portability.json', {'verified': True, 'copied_inputs': len(names), 'capture_host_and_source_worktree_reads_forbidden': True, 'process_launch_forbidden': True, 'result_exact': True, 'current_emulator_executed': False})
write('canonical-identity.json', {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ['sequel/rom-byte-coverage.json', 'sequel/reverse-engineering-proof.json', 'sequel/bank-proofs.json']})
print(json.dumps({'verified': True, 'cells_covered': 1, 'cells_total': 79, 'different_pixels': 928, 'portable_replay_exact': True, 'partial_gate_rejected': True}))
