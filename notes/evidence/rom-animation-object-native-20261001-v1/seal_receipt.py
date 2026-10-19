"""Copy verified results and provenance into a fresh notes packet without editing ancestors."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path.cwd().resolve()
HERE=Path(__file__).resolve().parent
out=ROOT/'notes/evidence/rom-animation-object-native-20261001-v1'
assert not out.exists()
result=HERE/'batch-v4'
authority=json.loads((result/'object-native.json').read_text())
assert len(authority['cases'])==5381 and authority['unit_tests']==16
assert (result/'native-traces.jsonl.gz').read_bytes()==(HERE/'batch-v3/native-traces.jsonl.gz').read_bytes()
archive=gzip.open(result/'native-traces.jsonl.gz','rb')
for row,raw in zip(authority['cases'],archive,strict=True):
 assert hashlib.sha256(raw).hexdigest()==row['record_sha256']
out.mkdir()
for path in sorted(HERE.iterdir()):
 if path.is_file() and not path.name.startswith('.'):
  shutil.copyfile(path,out/path.name)
for name in ('object-native.json','native-traces.jsonl.gz'):
 shutil.copyfile(result/name,out/name)
manifest={'schema':'animation-object-native-evidence-manifest-v1','files':{}}
for path in sorted(out.iterdir()):
 raw=path.read_bytes();manifest['files'][path.name]={'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
(out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
print('SEALED',len(manifest['files']),'members')
print('manifest',hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest())
print('authority',hashlib.sha256((out/'object-native.json').read_bytes()).hexdigest())
print('provider',hashlib.sha256((out/'provider-contract.json').read_bytes()).hexdigest())
print('inputs',len(authority['inputs']))
print('cases',dict(__import__('collections').Counter(r['family'] for r in authority['cases'])))
