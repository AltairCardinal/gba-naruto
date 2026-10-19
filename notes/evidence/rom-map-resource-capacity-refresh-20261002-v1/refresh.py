import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tools.export_map_resource_writeback_audit import export_map_resource_writeback_audit
from tools.verify_map_resource_writeback_audit import verify_map_resource_writeback_audit,_expected_payload
root=Path.cwd();run=root/'build/experiments/active/map-roundtrip/capacity-refresh-20261002-v1'
old=root/'artifacts/map-resource-writeback-v1';old_report=verify_map_resource_writeback_audit(root,old)
assert not old_report['verified']
outputs=[]
for name in ['refresh-a','refresh-b']:
 target=run/name;export_map_resource_writeback_audit(root,target)
 report=verify_map_resource_writeback_audit(root,target);assert report['verified'],report
 actual=json.loads((target/'map-resource-writeback.json').read_text());assert actual==_expected_payload(root)
 outputs.append(actual)
assert outputs[0]==outputs[1]
before=json.loads((old/'map-resource-writeback.json').read_text());after=outputs[0].copy()
before.pop('implementation');after.pop('implementation');assert before==after
for n in ['manifest.json','map-resource-writeback.json']:assert (run/'refresh-a'/n).read_bytes()==(run/'refresh-b'/n).read_bytes()
(run/'result.json').write_text(json.dumps({'verified':True,'old_rejected':old_report,'two_rebuilds_exact':True,'semantic_payload_unchanged':True,'runtime_executed':False},indent=2,sort_keys=True)+'\n')
