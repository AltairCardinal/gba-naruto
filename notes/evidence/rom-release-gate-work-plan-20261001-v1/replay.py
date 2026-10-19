"""Replay only seven existing read-only fixed-slot resource verifiers."""
import hashlib
import json
import subprocess
from pathlib import Path

run = Path(__file__).resolve().parent
path = Path('sequel/reverse-engineering-proof.json')
raw = path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568'
proof = json.loads(raw)
gate = proof['gates']['resource_roundtrip']
assert len(gate['verifiers']) == 7
assert gate['coverage']['case_ids_covered'] == []
rows = []
for item in gate['verifiers']:
    command = item['command']
    script = command[1]
    assert script.startswith('tools/verify_') and script.endswith('_writeback_audit.py')
    observed = hashlib.sha256(Path(script).read_bytes()).hexdigest()
    assert observed == item['script_sha256']
    name = Path(script).stem
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    (run / (name + '.stdout')).write_text(result.stdout)
    (run / (name + '.stderr')).write_text(result.stderr)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = None
    rows.append({'command': command, 'script_sha256': observed, 'exit_code': result.returncode,
                 'report': report, 'stderr_tail': result.stderr[-1000:]})
print(json.dumps({'schema': 'release-resource-replay-plan-v1', 'proof_sha256': hashlib.sha256(raw).hexdigest(),
                  'rows': rows, 'successes': sum(r['exit_code'] == 0 for r in rows),
                  'scope': 'Existing fixed-slot archive verification only; no new edited ROM, build, UI, emulator launch or strict gate acceptance.'},sort_keys=True,indent=2))
