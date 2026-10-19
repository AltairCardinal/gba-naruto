"""Fixed raw literal-address denominator with separately labelled source membership."""
import contextlib,json,sys,struct
from pathlib import Path
HERE=Path(__file__).parent
BASE=Path('notes/evidence/rom-animation-critical-writers-20261001-v1')
sys.path.insert(0,str(Path.cwd()));sys.path.insert(0,str(BASE))
from writers import fixed_graph,local
from tools.verify_rom_cfg_inventory import _decode
PROGRESS=sys.stdout


def main(output=None):
    output=Path(output) if output else HERE
    mraw=(BASE/'manifest.json').read_bytes();assert local.sha(mraw)=='9abb50194d42169b6e07d6a362c0a11249c19cfe59dbb5d78506ee3e6170cd6f'
    for n,i in json.loads(mraw)['files'].items():
        b=(BASE/n).read_bytes();assert len(b)==i['size'] and local.sha(b)==i['sha256']
    prior=json.loads((BASE/'critical-writers-v2.json').read_text())
    for n,i in prior['source_inputs'].items():
        b=Path(n).read_bytes();assert len(b)==i['size'] and local.sha(b)==i['sha256']
    rom,offsets,parent,sha=fixed_graph()
    v20=json.loads(Path('artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json').read_text())
    for start,end in v20['target_local_denominator']['code_ranges']:
        at=start
        while at<end:
            d=_decode(rom,at,'thumb');assert d['accepted'] and at+d['size']<=end
            offsets.add(at);at+=d['size']
    assert len(offsets)==66295
    coverage=json.loads(Path('sequel/rom-byte-coverage.json').read_text())
    def claims(at):
        return [{k:c.get(k) for k in ('id','range','primary_class','claim_kind','evidence_path','evidence_sha256','independent_verifier_path','independent_verifier_sha256')}
                for c in coverage['claims'] if c['range'][0]<=at<c['range'][1]]
    needles=set(range(0x03000070,0x03000080))|{0x03000000}
    occurrences=[]
    for value in sorted(needles):
        token=struct.pack('<I',value);at=rom.find(token)
        while at>=0:
            occurrences.append({'at':at,'value':value,'claims':claims(at)})
            at=rom.find(token,at+1)
    byword={r['at']:r['value'] for r in occurrences if r['at']%4==0}
    refs=[]
    for at in range(0,len(rom)-1,2):
        h=struct.unpack_from('<H',rom,at)[0]
        if h&0xf800!=0x4800:continue
        word=((at+4)&~3)+4*(h&255)
        if word in byword:
            refs.append({'at':at,'literal':word,'value':byword[word],'register':(h>>8)&7,
                         'raw_hex':rom[at:at+2].hex(),'source_instruction_member':at in offsets,
                         'claims':claims(at)})
    ranges=[]
    for at in sorted(offsets):
        size=_decode(rom,at,'thumb')['size']
        if ranges and ranges[-1][1]==at:ranges[-1][1]=at+size
        else:ranges.append([at,at+size])
    result={'rom_sha256':local.sha(rom),'source_instruction_count':len(offsets),'source_ranges':ranges,
            'all_byte_pointer_occurrences':occurrences,'all_halfword_ldr_literal_shapes':refs,
            'needle_values':sorted(needles),'global_writer_exhaustiveness_proven':False,'promotion_bytes':0}
    (output/'counter-inventory.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    lines=[]
    for r in refs:
        if r['source_instruction_member'] or (any(c['primary_class'] not in ('unknown','consumer_code_slice') for c in r['claims']) and r['value'] in (0x03000074,0x03000075)):
            start=max(0,r['at']-12);end=min(len(rom),r['at']+48)
            lines.append(f"REFERENCE {r['at']:06X} value={r['value']:08X} source={r['source_instruction_member']}")
            for i in local.ENGINE.disasm(rom[start:end],start):lines.append(f"{i.address:06X} {i.bytes.hex():8} {i.mnemonic:6} {i.op_str}")
    (output/'counter-windows.txt').write_text('\n'.join(lines)+'\n')
    print('counter words',len(occurrences),'raw refs',len(refs),'source refs',sum(r['source_instruction_member'] for r in refs),file=PROGRESS,flush=True)


if __name__=='__main__':
    with (HERE/'counter-inventory.log').open('x') as s,contextlib.redirect_stdout(s),contextlib.redirect_stderr(s):
        try:main()
        except BaseException:
            import traceback;traceback.print_exc();raise SystemExit(1)
