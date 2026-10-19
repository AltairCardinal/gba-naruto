"""Source-bound callback/helper inventory; only existing decoder/closure logic."""
import contextlib,json,sys,struct,hashlib
from pathlib import Path
ROOT=Path.cwd(); HERE=Path(__file__).parent
BASE=ROOT/'notes/evidence/rom-animation-interprocedural-identities-20261001-v1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from analyze_batch import fixed_graph
from closure import noncall_closure
from callee_effects import local
from tools.verify_rom_cfg_inventory import _decode
PROGRESS=sys.stdout

def main():
    m=json.loads((BASE/'manifest.json').read_text())
    assert local.sha((BASE/'manifest.json').read_bytes())=='1aca46ee19d8af2ddf051f1daa1fbfec1cd660245578020f689303116ff78e70'
    for n,i in m['files'].items():
        b=(BASE/n).read_bytes();assert len(b)==i['size'] and local.sha(b)==i['sha256']
    rom,offsets,parent,sha=fixed_graph()
    v20raw=Path('artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json').read_bytes()
    assert local.sha(v20raw)=='5d3186a688973b1733b0117aedee7c689a5270497c83f8726d4d2540bcfe1543'
    v20=json.loads(v20raw)
    assert json.loads((HERE/'v20-source-replay.json').read_text())['verified']
    for start,end in v20['target_local_denominator']['code_ranges']:
        at=start
        while at<end:
            i=_decode(rom,at,'thumb');assert i['accepted'] and at+i['size']<=end
            offsets.add(at);at+=i['size']
    decoded={at:_decode(rom,at,'thumb') for at in offsets}
    result={'source_sha256':sha,'rom_sha256':local.sha(rom),'source_instruction_count':len(offsets),'roots':{},'pool_literals':[],'shape_stores':[],'promotion_bytes':0,'natural_execution_proven':False}
    for at in sorted(offsets):
        h=struct.unpack_from('<H',rom,at)[0]
        if h&0xf800==0x4800:
            word=((at+4)&~3)+4*(h&255);v=struct.unpack_from('<I',rom,word)[0]
            if 0x03003bb8<=v<=0x030059b8:result['pool_literals'].append({'at':at,'literal':word,'value':v})
        i=decoded[at]
        if i['mnemonic'] in ('str','strh','strb','stm','stmia'):
            inst=next(local.ENGINE.disasm(rom[at:at+i['size']],at,count=1))
            if i['mnemonic'] in ('stm','stmia') or (len(inst.operands)>1 and inst.operands[1].mem.disp in (0,0x14,0x16,0x18,0x1c,0x20,0x28)):
                result['shape_stores'].append({'at':at,'raw_hex':rom[at:at+i['size']].hex(),'mnemonic':i['mnemonic'],'operands':i['op_str'],'typed_object_writer':False})
    lines=[]
    for root in (0x626b4,0x62788,0x62798,0x627b0,0x62924,0x6321c,0x8aa50,0x8ee40,0x8a84c,0x8a4d8,0x6254c,0x625a4):
        c=noncall_closure(rom,root,offsets,decoded=decoded)
        result['roots'][root]=c
        lines.append(f'ROOT {root:06X} nodes={len(c["nodes"])} children={c["child_targets"]} frontiers={c["frontiers"]}')
        for at in c['nodes']:
            i=decoded[at];lines.append(f'{at:06X} {rom[at:at+i["size"]].hex():8} {i["mnemonic"]:6} {i["op_str"]}')
        print('Inventoried',hex(root),len(c['nodes']),file=PROGRESS,flush=True)
    (HERE/'inventory-v2.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    (HERE/'closures-v2.txt').write_text('\n'.join(lines)+'\n')
    print('pool literal references',len(result['pool_literals']),'shape stores',len(result['shape_stores']),file=PROGRESS,flush=True)

if __name__=='__main__':
    with (HERE/'inventory-v2.log').open('x') as s,contextlib.redirect_stdout(s),contextlib.redirect_stderr(s):
        try:main()
        except BaseException:
            import traceback;traceback.print_exc();raise SystemExit(1)
