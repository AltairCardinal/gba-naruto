"""Stable artifact replay plus live unknown projection, outside payload identity."""
import hashlib,json
from pathlib import Path
from tools import verify_rom_renderer_records_delta as verifier
root=Path('.').resolve();run=Path(__file__).resolve().parent;artifact=run/'final'
first=verifier.verify_artifact(root,artifact);second=verifier.verify_artifact(root,artifact)
assert first['verified'] and first==second,(first,second)
raw=(root/'sequel/rom-byte-coverage.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
coverage=json.loads(raw);assert coverage['summary']['unknown_bytes']==87631
claims=verifier.project_unknown_claims(root,artifact,coverage['segments'])
assert len(claims)==29 and sum(b-a for a,b in (c['range']for c in claims))==1668
rom=(root/'rom/base.gba').read_bytes()
for claim in claims:
 a,b=claim['range'];assert hashlib.sha256(rom[a:b]).hexdigest()==claim['bytes_sha256']
assert all(a['range'][1]<=b['range'][0]for a,b in zip(claims,claims[1:]))
for gap in [0x42bd,0x1968,0x19b4,0x1ae7]:assert not any(a<=gap<b for a,b in(c['range']for c in claims))
legacy_inputs=json.loads((root/'notes/evidence/rom-low-script-delta-tier1-20261001-v1/inputs.json').read_bytes())
for relative in ['artifacts/rom-low-script-delta-v1/manifest.json','artifacts/rom-low-script-delta-v1/rom-low-script-delta.json']:
 assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==legacy_inputs[relative]['sha256']
assert [0x42b5,0x42bd]in [c['range']for c in claims] and [0x42c2,0x42c6]in [c['range']for c in claims]
manifest=json.loads((artifact/'manifest.json').read_bytes());assert manifest['artifact_status']=='accepted'
print(json.dumps({'schema':'renderer-records-delta-tier1-acceptance-v1','stable_verifier_report':first,
                  'stable_report_sha256':hashlib.sha256(verifier.canonical(first)).hexdigest(),
                  'accepted_payload_sha256':hashlib.sha256((artifact/verifier.PAYLOAD).read_bytes()).hexdigest(),
                  'accepted_manifest_sha256':hashlib.sha256((artifact/'manifest.json').read_bytes()).hexdigest(),
                  'observed_current_coverage_sha256':hashlib.sha256(raw).hexdigest(),'current_unknown_projection_checked':True,
                  'projected_unknown_bytes':1668,'claims':claims,'legacy_12B_replaced_without_overwriting_history':True,
                  'canonical_unknown_bytes':87631,'canonical_changed':False,'tier1_accepted':True,'tier2_accepted':False,
                  'natural_runtime_reachability':False},sort_keys=True,indent=2))
