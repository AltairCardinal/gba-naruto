"""Publish one Tier-1 display packet, keeping live projection separate."""
from pathlib import Path
import json
from tools import export_rom_display_text_delta as exporter
from tools import verify_rom_display_text_delta as verifier
from tools.experiment_workspace import _validate_promotion_manifest
root=Path('.').resolve();run=Path(__file__).parent.absolute();final=run/'final'
exporter.export_artifact(root,final)
a=verifier.verify_artifact(root,final);b=verifier.verify_artifact(root,final)
assert a==b and a['verified']and a['promotion_bytes']==1053
assert _validate_promotion_manifest(final)['artifact_status']=='accepted'
for name,r in [('verifier.json',a),('verifier-stable.json',b)]:
 (run/name).write_bytes(verifier.canonical(r))
raw=verifier.read_regular(root/'sequel/rom-byte-coverage.json');assert verifier.sha(raw)=='b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2'
claims=verifier.project_unknown_claims(root,final,json.loads(raw)['segments'])
receipt={'schema':'display-text-observed-unknown-projection-v1','observed_current_coverage_sha256':verifier.sha(raw),'observed_during_this_run':True,'packet_sha256':verifier.sha(verifier.read_regular(final/verifier.PAYLOAD)),'claim_count':len(claims),'projected_unknown_bytes':sum(r['range'][1]-r['range'][0]for r in claims),'canonical_written':False,'tier2_triggered':False,'scope':'Observed live input; not part of stable payload or claim identity.'}
(run/'current-projection.json').write_bytes(verifier.canonical(receipt))
print(json.dumps({'verified':a['verified'],'consumer_count':a['consumer_count'],'record_count':a['record_count'],'pending_bytes':a['promotion_bytes'],'projected_unknown_bytes':receipt['projected_unknown_bytes'],'canonical_written':False},sort_keys=True))
