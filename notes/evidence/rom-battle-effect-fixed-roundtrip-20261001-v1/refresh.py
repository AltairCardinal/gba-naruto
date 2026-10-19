import hashlib,json,shutil,sys
from pathlib import Path
root=Path.cwd().resolve();sys.path.insert(0,str(root))
from tools.export_battle_effect_resource_writeback_audit import export_battle_effect_resource_writeback_audit
from tools.verify_battle_effect_resource_writeback_audit import verify_battle_effect_resource_writeback_audit,_expected_payload,PAYLOAD_NAME
run=Path(__file__).resolve().parent
def write(name,value):
    (run/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
old=root/'artifacts/battle-effect-resource-writeback-v1'
old_identity={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old.iterdir() if p.is_file()}
rejected=verify_battle_effect_resource_writeback_audit(root,old)
assert rejected['verified'] is False and rejected['errors']==['implementation mismatch'],rejected
write('old-verifier.json',rejected)
payloads=[]
for name in ['refresh','refresh-repeat']:
    out=run/name;assert not out.exists()
    payload=export_battle_effect_resource_writeback_audit(root,out)
    report=verify_battle_effect_resource_writeback_audit(root,out)
    assert report['verified'] is True,report
    assert payload==_expected_payload(root)
    write(name+'-verifier.json',report);payloads.append(payload)
assert payloads[0]==payloads[1]
for p in (run/'refresh').iterdir():assert p.read_bytes()==(run/'refresh-repeat'/p.name).read_bytes()
old_payload=json.loads((old/PAYLOAD_NAME).read_text())
changes={name:{'old':old_payload['implementation'][name],'current':value} for name,value in payloads[0]['implementation'].items() if old_payload['implementation'][name]!=value}
assert set(changes)=={'tests/test_import_battle_effect_resources.py'},changes
left=dict(old_payload);right=dict(payloads[0]);left.pop('implementation');right.pop('implementation');assert left==right
assert old_identity=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old.iterdir() if p.is_file()}
write('refresh-summary.json',{'verified':True,'old_identity':old_identity,'changed_implementation':changes,'semantic_payload_unchanged':True,'two_regenerations_byte_exact':True,'summary':payloads[0]['summary'],'scope':payloads[0]['scope'],'current_runtime_executed':False})
print(json.dumps({'refreshed':True,'resources':34,'slots':35,'logical_references':36}))
