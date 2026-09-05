"""Preserve final raw formal receipts and the exact before/after source states."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path('/Users/altair/github/gba-naruto-reverse')
RUN=Path(__file__).parent
DEST=ROOT/'notes/evidence/rom-evidence-selector-repair-20260905'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def preserve(path, raw):
    if path.exists():
        assert path.read_bytes()==raw,path
    else:
        with path.open('xb') as stream:
            stream.write(raw)


manifest_path=DEST/'manifest.json'
manifest_raw=manifest_path.read_bytes()
assert sha(manifest_raw)=='09b45b099df09f5217cc09c24d1318d0b2426511904403987ead2c8c8e1f31ae'
manifest=json.loads(manifest_raw)
coverage=(ROOT/'sequel/rom-byte-coverage.json').read_bytes()
proof=(ROOT/'sequel/reverse-engineering-proof.json').read_bytes()
assert sha(coverage)==manifest['after_coverage_sha256']
assert sha(proof)==manifest['after_proof_sha256']
assert sha((RUN/'formal-report.json').read_bytes())=='aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc'
assert sha((RUN/'formal-guard.json').read_bytes())=='3e1722f8979fa68723acf3e5940cf7eacd5beaabde6d19c2c14bf277a6736c54'
formal=json.loads((RUN/'formal-report.json').read_bytes())
assert formal['trust_anchor']['spec_sha256']==sha(proof)
assert len(formal['verifiers_executed'])==106 and all(v['contract_ok'] is True and v['exit_code']==0 for v in formal['verifiers_executed'])
assert len(formal['blockers'])==175 and formal['complete'] is False
preserve(DEST/'manifest.before-formal.json',manifest_raw)
for name in ('formal-report.json','formal-guard.json','formal.log','permanent-formal-binding-red.log'):
    preserve(DEST/name,(RUN/name).read_bytes())
preserve(DEST/'coverage-after.json.gz',gzip.compress(coverage,compresslevel=9,mtime=0))
preserve(DEST/'proof-after.json',proof)
manifest.update(status='formal_contracts_verified',committed_artifacts_at_recording=False,
                formal_contracts=106,rom_contracts=96,global_complete=False,global_blockers=175)
manifest['files']={p.name:{'sha256':sha(p.read_bytes()),'size_bytes':p.stat().st_size}
                   for p in sorted(DEST.iterdir()) if p.name!='manifest.json'}
temp=manifest_path.with_suffix('.json.tmp')
with temp.open('x') as stream:
    json.dump(manifest,stream,sort_keys=True,indent=2);stream.write('\n')
temp.replace(manifest_path)
print(json.dumps({'status':manifest['status'],'members':len(manifest['files']),
                  'manifest_sha256':sha(manifest_path.read_bytes())}))
