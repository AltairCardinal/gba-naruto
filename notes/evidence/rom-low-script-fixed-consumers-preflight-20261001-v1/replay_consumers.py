"""Read-only fixed CFG literal candidates; no new accepted records."""
import hashlib
import json
import struct
from pathlib import Path
from tools.verify_rom_fixed_renderer_script_records import _cfg_blocks, _prove_parameter_flow, _parse

root=Path('.')
rom=(root/'rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest()=='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
pools=[(0x578c,0x7554),(0x42ab,0x542e),(0xcea,0x12f0)]
blocks,contract=_cfg_blocks(root)
sjis=tuple((int.from_bytes(rom[p:p+2],'little'),int.from_bytes(rom[p:p+2],'little')+rom[p+2]) for p in range(0x53d644,0x53d73c,8))
rows=[]
for block in blocks:
    if block.get('mode')!='thumb':continue
    a,b=block['range']
    for at in range(a,b,2):
        half=struct.unpack_from('<H',rom,at)[0]
        if half&0xf800!=0x4800:continue
        literal=((at+4)&~3)+4*(half&255)
        target=struct.unpack_from('<I',rom,literal)[0]-0x08000000
        pool=next(((lo,hi) for lo,hi in pools if lo<=target<hi),None)
        if pool is None:continue
        row={'site':at,'literal':literal,'target':target,'block_id':block['id'],'pool':list(pool)}
        try:
            row['interpreter_callsite']=_prove_parameter_flow(rom,at,(half>>8)&7)
            row['parameter_flow_replayed']=True
            try:
                end,ops=_parse(rom,target,pool[1],sjis)
                row['syntax_candidate_range']=[target,end]
                row['syntax_opcode_sequence']=ops
            except ValueError as error:row['syntax_exclusion']=str(error)
        except ValueError as error:
            row['parameter_flow_replayed']=False
            row['parameter_flow_exclusion']=str(error)
        rows.append(row)
print(json.dumps({'schema':'low-script-three-pool-literal-preflight-v1','rom_sha256':hashlib.sha256(rom).hexdigest(),
                  'pool_denominator':pools,'upstream_cfg_contract':contract,'literal_candidates':sorted(rows,key=lambda r:r['site']),
                  'literal_candidate_count':len(rows),'accepted_new_record_count':0,'promotion_bytes':0,
                  'scope':'Pinned v2/v3 literal sites only; candidate dataflow/syntax; no whole-ROM roots, full runtime/callee proof or physical table expansion.'},sort_keys=True,indent=2))
