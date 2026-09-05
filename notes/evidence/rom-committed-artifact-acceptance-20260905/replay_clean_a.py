"""Verify the authority from a clean detached checkout of commit A."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

RUN=Path(__file__).parent
CLEAN=RUN/'clean-checkout'
COMMIT='47d9a60e668a5c3fe6e1123524864d21a2c93545'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=CLEAN).decode().strip()==COMMIT
assert not subprocess.check_output(['git','status','--porcelain'],cwd=CLEAN).strip()
replay_env=dict(os.environ)
replay_env.pop('PYTHONPATH',None)
replay_env['PYTHONDONTWRITEBYTECODE']='1'
commands=[('clean-a-tests',['python3','-m','unittest','tests.test_staged_legacy_artifact_acceptance',
            'tests.test_verify_legacy_artifact_acceptance','tests.test_rebuild_legacy_artifact_acceptance','-v']),
          ('clean-a-bundle',['python3','tools/verify_legacy_artifact_acceptance.py',
                            '--artifact','artifacts/rom-legacy-acceptance-20260905-v1'])]
results=[]
for label,command in commands:
    completed=subprocess.run(command,cwd=CLEAN,env=replay_env,capture_output=True)
    for suffix,raw in (('.stdout',completed.stdout),('.stderr',completed.stderr)):
        with (RUN/(label+suffix)).open('xb') as stream:
            stream.write(raw)
    assert completed.returncode==0,(label,completed.stderr.decode(errors='replace'))
    results.append({'label':label,'command':command,'exit_code':completed.returncode,
                    'stdout_sha256':hashlib.sha256(completed.stdout).hexdigest()})
report=json.loads((RUN/'clean-a-bundle.stdout').read_bytes())
assert report['artifact_status']=='accepted' and report['verified'] is True
assert hashlib.sha256((RUN/'clean-a-bundle.stdout').read_bytes()).hexdigest()=='42e1d5628834efdf871a175d20feeba66d915b63daae66d669ac710f9821577c'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=CLEAN).strip()
receipt={'status':'clean_committed_authority_verified','commit':COMMIT,
         'commands':results,'bundle_summary':report['summary']}
with (RUN/'clean-a-receipt.json').open('x') as stream:
    json.dump(receipt,stream,sort_keys=True,indent=2);stream.write('\n')
print(json.dumps({'status':receipt['status'],'commit':COMMIT}))
