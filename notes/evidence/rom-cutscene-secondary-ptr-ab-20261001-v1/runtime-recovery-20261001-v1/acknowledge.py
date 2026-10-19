import hashlib,json,shutil
from pathlib import Path
from tools.mgba_runtime_safety import DEFAULT_LATCH_PATH,DEFAULT_BASELINE_PATH,DEFAULT_CRASH_DIR,_snapshot_crash_reports,_load_baseline,_report_records,clear_crash_latch
from tools.macos_mgba_runtime_residue import probe_runtime_residue
root=Path('.').resolve();run=root/'build/experiments/active/cutscene-secondary-ptr-ab/runtime-recovery-20261001-v1';old=root/'build/experiments/active/cutscene-secondary-ptr-ab/runtime-20261001-v1'
preflight=json.loads((run/'preflight-result.json').read_text());assert preflight['dlopen_verified'] is True
assert hashlib.sha256(Path(preflight['library']).read_bytes()).hexdigest()==preflight['library_sha256']
latch=json.loads(DEFAULT_LATCH_PATH.read_text());guard=json.loads((old/'runtime/zero-baseline-1/guard.json').read_text());assert latch['reports']==guard['mgba_crash_reports']
current=_report_records(_snapshot_crash_reports(DEFAULT_CRASH_DIR),_load_baseline(DEFAULT_BASELINE_PATH));assert current==latch['reports'],'unexpected unhandled crash report'
for row in current:
    assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==hashlib.sha256((old/'launch-crash.ips').read_bytes()).hexdigest()
residue=probe_runtime_residue(guard['child_pid']);assert residue['pgid_clean'] is True
clear_crash_latch()
assert not DEFAULT_LATCH_PATH.exists()
shutil.copy2(Path(str(DEFAULT_LATCH_PATH)+'.history.jsonl'),run/'crash-latch-history.jsonl');shutil.copy2(DEFAULT_BASELINE_PATH,run/'crash-baseline-after.json')
(run/'recovery-audit.json').write_text(json.dumps({'acknowledged_crash':current,'cause':'DYLD missing libmgba.0.11.dylib before ROM/Lua execution','library_preflight':preflight,'residue':residue,'clear_interface':'tools.mgba_runtime_safety.clear_crash_latch','latch_cleared':True,'new_resource_experiment_authorized':False},indent=2,sort_keys=True)+'\n')
print('acknowledged owned crash through audited interface')
