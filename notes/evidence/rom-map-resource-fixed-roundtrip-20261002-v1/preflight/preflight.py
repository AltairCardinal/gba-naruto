import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tools import verify_map_resource_writeback_audit as v
from tools.import_map_resources import _validate_linked_map_view
root=Path.cwd();run=root/'build/experiments/active/map-roundtrip/preflight-20261002-v1'
p=v._expected_payload(root);rom=(root/'rom/base.gba').read_bytes();cat=json.loads((root/v.CATALOG_PATH).read_text())
out={'capacity':v.verify_map_resource_writeback_audit(root,root/'artifacts/map-resource-writeback-v1'),'rows':[]}
try:_validate_linked_map_view(cat,{},rom);out['baseline_domain_valid']=True
except ValueError as e:out['baseline_domain_valid']=False;out['baseline_error']=str(e)
for r in p['resources']:
 b=bytearray(v._decompress(rom,r['physical_slots'][0]['file_offset']));b[r['mutation']['offset']]^=1
 try:_validate_linked_map_view(cat,{(r['resource_type'],r['resource_sha256']):bytes(b)},rom);error=None
 except ValueError as e:error=str(e)
 out['rows'].append({'id':r['resource_type']+':'+r['resource_sha256'],'capacity_fit':r['mutation_fit_all_aliases'],'domain_valid':error is None,'error':error})
out['summary']={k:sum((x['domain_valid'],x['capacity_fit'])==t for x in out['rows']) for k,t in [('legal_fit',(True,True)),('legal_overflow',(True,False)),('illegal_fit',(False,True)),('illegal_overflow',(False,False))]}
(run/'preflight.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
