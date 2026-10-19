"""Seal the verified full-renderer packet; preserve modes and ancestor evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path.cwd().resolve()
HERE=Path(__file__).resolve().parent
out=ROOT/'notes/evidence/rom-animation-full-renderer-20261001-v1'
assert not out.exists()
result=HERE/'batch-v3'
authority=json.loads((result/'full-renderer.json').read_text())
assert len(authority['frames'])==3684 and authority['native_trace_count']==7368
assert (result/'full-traces.jsonl.gz').read_bytes()==(HERE/'batch-v2/full-traces.jsonl.gz').read_bytes()
with gzip.open(result/'full-traces.jsonl.gz','rb') as archive:
 for row,raw in zip(authority['cases'],archive,strict=True):
  assert hashlib.sha256(raw).hexdigest()==row['record_sha256']
out.mkdir()
for path in sorted(HERE.iterdir()):
 if path.is_file() and not path.name.startswith('.'):
  shutil.copy2(path,out/path.name)
for name in ('full-renderer.json','full-traces.jsonl.gz'):
 shutil.copy2(result/name,out/name)
manifest={'schema':'animation-full-renderer-evidence-manifest-v1','files':{}}
for path in sorted(out.iterdir()):
 raw=path.read_bytes();manifest['files'][path.name]={'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
(out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
print('SEALED',len(manifest['files']),'members')
for name in ('manifest.json','full-renderer.json'):
 print(name,hashlib.sha256((out/name).read_bytes()).hexdigest())
