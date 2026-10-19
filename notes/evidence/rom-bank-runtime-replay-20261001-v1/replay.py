from pathlib import Path
import hashlib,json,subprocess,time,sys
root=Path('.').resolve()
run=root/'build/experiments/active/bank-runtime-replay/existing-11-20261001-v1'
plan=json.loads((run/'plan.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(root/'sequel/bank-proofs.json')==plan['bank_proofs_sha256']
rows=[]
for case in plan['cases']:
    bank=case['bank'];out=run/'cases'/bank;out.mkdir(parents=True)
    print(json.dumps({'starting':bank}),flush=True)
    before={p:sha(root/p) for p in case['inputs']}
    assert before==case['inputs'],(bank,'initial identity drift')
    started=time.monotonic()
    try:
        result=subprocess.run([sys.executable,*case['command'][1:]],cwd=root,text=True,capture_output=True,timeout=plan['child_timeout_s'],check=False)
        stdout,stderr=result.stdout,result.stderr;exit_code=result.returncode;timed_out=False
    except subprocess.TimeoutExpired as error:
        stdout=error.stdout or b'';stderr=error.stderr or b''
        if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
        if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
        exit_code=None;timed_out=True
    (out/'stdout.txt').write_text(stdout);(out/'stderr.txt').write_text(stderr)
    try:payload=json.loads(stdout)
    except json.JSONDecodeError:payload=None
    after={p:sha(root/p) for p in case['inputs']}
    assert before==after,(bank,'identity drift during replay')
    row={'bank':bank,'command':case['command'],'exit_code':exit_code,'timed_out':timed_out,'seconds':round(time.monotonic()-started,3),'json_payload':payload,'input_identity_unchanged':True,'stdout_sha256':sha(out/'stdout.txt'),'stderr_sha256':sha(out/'stderr.txt')}
    rows.append(row);(out/'result.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
    (run/'progress.json').write_text(json.dumps({'completed':len(rows),'total':len(plan['cases']),'last':bank},indent=2)+'\n')
    print(json.dumps({'finished':bank,'exit_code':exit_code,'seconds':row['seconds']}),flush=True)
assert sha(root/'sequel/bank-proofs.json')==plan['bank_proofs_sha256']
report={'schema':'bank-existing-runtime-replay-v1','case_count':len(rows),'exit_zero_count':sum(r['exit_code']==0 for r in rows),'case_results':rows,'new_runtime_samples':0,'global_exhaustive_claim':False}
(run/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({'completed':len(rows),'exit_zero_count':report['exit_zero_count']}),flush=True)
