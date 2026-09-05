"""Execute the manifest's exact verifier and deterministic reconstruction commands."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('/Users/altair/github/gba-naruto-reverse')
RUN=Path(__file__).parent
final=RUN/'final'
manifest=json.loads((final/'manifest.json').read_bytes())


def run(command, name):
    completed=subprocess.run(command,cwd=ROOT,capture_output=True)
    with (RUN/(name+'.json')).open('xb') as stream:
        stream.write(completed.stdout)
    with (RUN/(name+'.stderr')).open('xb') as stream:
        stream.write(completed.stderr)
    assert completed.returncode==0,(name,completed.stderr.decode(errors='replace'))
    return json.loads(completed.stdout),completed.stdout


before={p.name:p.read_bytes() for p in final.iterdir()}
verification,first=run(manifest['verifier']['command'],'bundle-verifier-v1')
assert verification['verified'] is True and verification['artifact_status']=='accepted'
rebuilt,_=run(manifest['producer']['command'],'bundle-rebuild-v1')
assert rebuilt['rebuilt'] is True
original=manifest['files']['snapshot.json.gz']
assert rebuilt['sha256']==original['sha256'] and rebuilt['size']==original['size']
assert (RUN/'rebuilt-snapshot-v4.json.gz').read_bytes()==before['snapshot.json.gz']
_,second=run(manifest['verifier']['command'],'bundle-verifier-v2')
assert first==second,'verifier receipt must remain stable after reconstruction'
assert before=={p.name:p.read_bytes() for p in final.iterdir()}
report={'status':'full_bundle_verified_and_rebuilt_not_promoted_or_committed',
        'verifier_report_sha256':hashlib.sha256(first).hexdigest(),
        'snapshot_sha256':rebuilt['sha256'],'summary':verification['summary']}
with (RUN/'bundle-reproduction-v1.json').open('x') as stream:
    json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
print(json.dumps(report,sort_keys=True))
