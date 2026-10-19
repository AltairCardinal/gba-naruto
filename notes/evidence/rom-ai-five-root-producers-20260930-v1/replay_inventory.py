"""Reuse existing raw Thumb BL/B and exact pointer scans; no CFG promotion."""
from pathlib import Path
import hashlib,json,sys,bisect
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.thumb_branch import iter_thumb_direct_branches
from tools.find_pointer_refs import scan_references
from tools.analyze_rom_ai_entry_domains import read_coverage,ROM_SHA256
rom=(root/'rom/base.gba').read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(rom)==ROM_SHA256
coverage=read_coverage(root);claims={r['id']:r for r in coverage['claims']};segments=coverage['segments'];starts=[r['range'][0] for r in segments]
targets=[0x84274,0x851f8,0x6aa64,0x6acac,0x6e1b4];result={a:{'thumb_bl_b_shapes':[],'exact_word_occurrences':[]} for a in targets}
for branch in iter_thumb_direct_branches(rom,rom_base=0x08000000):
 target=branch.target-0x08000000
 if target not in result:continue
 offset=branch.address-0x08000000;size=4 if branch.mnemonic=='bl' else 2;segment=segments[bisect.bisect_right(starts,offset)-1];owners=[claims[i] for i in segment['primary_claim_ids']]
 eligible=[r for r in owners if r['range'][0]<=offset and offset+size<=r['range'][1] and r.get('mode')=='thumb' and r.get('instruction_only_claimed') is not False and ('reachable_instruction_bytes' in r['claim_kind'] or 'direct_thumb_bl_producer' in r['claim_kind'])]
 result[target]['thumb_bl_b_shapes'].append({'offset':offset,'mnemonic':branch.mnemonic,'raw_hex':rom[offset:offset+size].hex(),'primary_class':segment['primary_class'],'primary_owner_ids':segment['primary_claim_ids'],'instruction_owner_candidate_ids':[r['id'] for r in eligible],'producer_semantics_or_natural_reachability_proved':False})
for target in targets:
 for tag in [0,1]:
  report=scan_references(rom,target+tag,aligned_only=False)
  result[target]['exact_word_occurrences'].append({'word':0x08000000+target+tag,'tag':tag,'offsets':[r['offset'] for r in report['references']],'instruction_or_consumer_binding_proved':False})
modules={p:sha((root/p).read_bytes()) for p in ['tools/thumb_branch.py','tools/find_pointer_refs.py','tools/analyze_rom_ai_entry_domains.py']}
print(json.dumps({'schema':'rom-ai-five-root-producer-preflight-v1','rom_sha256':ROM_SHA256,'historical_coverage_sha256':coverage['rom']['sha256'] if False else 'b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2','input_tools':modules,'scan_range':[0,len(rom)],'thumb_branch_alignment':2,'pointer_alignment':1,'scope':'Thumb BL and unconditional B shapes plus exact tagged/untagged words; not conditional B, ARM, interwork or computed producers','promotion_bytes':0,'incoming_producer_denominator_complete':False,'targets':{f'{k:06x}':v for k,v in result.items()}},indent=2,sort_keys=True))
