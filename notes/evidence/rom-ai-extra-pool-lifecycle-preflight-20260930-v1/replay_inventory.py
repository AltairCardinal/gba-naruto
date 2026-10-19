"""Fixed three-source initialization evidence; not a global RAM invariant."""
from pathlib import Path
import sys,json,hashlib
from collections import Counter
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tools.analyze_rom_ai_entry_domains import read_coverage,ROM_SHA256
from tools.extract_positions import extract_positions
rom=(root/'rom/base.gba').read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(rom)==ROM_SHA256
coverage=read_coverage(root);points=[]
for a,size in [(0x6ab1e,2),(0x6abca,2),(0x6abcc,2),(0x6abce,2),(0x6abd0,2),(0x6abd2,4),(0x6abe8,4),(0x6a780,2),(0x6a78c,2),(0x6a78e,2),(0x6ad6e,2),(0x6ad7a,2),(0x6ad90,2),(0x6e2a0,4),(0x6e2cc,2),(0x9c3ec,2),(0x9c406,2),(0x9c414,2),(0x9c416,2),(0x9c420,2),(0x9c448,2)]:
 owners=[r for r in coverage['claims'] if r['role']=='primary' and r['range'][0]<=a and a+size<=r['range'][1]]
 assert len(owners)==1 and owners[0].get('mode')=='thumb' and 'reachable_instruction_bytes' in owners[0]['claim_kind']
 points.append({'offset':a,'raw_hex':rom[a:a+size].hex(),'owner':owners[0]})
assert rom[0x6abce:0x6abd2].hex()=='ea225200'
assert rom[0x6a780:0x6a790].hex()=='c03002680f235b421a400a4302607047'
rows=[r for r in extract_positions(rom)['entries'] if r['selector']]
mask6=[r for r in rows if (r['affiliation']|r['aux_u32']|16)&14==6];alternate=[r for r in rows if r['selector'] in (250,251,252)]
content=[]
for r in mask6:content.append({'id':r['id'],'offset':r['rom_offset'],'selector':r['selector'],'raw_affiliation':r['affiliation'],'raw_flags':r['aux_u32'],'raw_plus_0e':bytes.fromhex(r['raw_hex'])[14]})
assert len(content)==12 and all(r['raw_plus_0e']==6 and r['raw_affiliation']==1 for r in content)
assert len(alternate)==24 and all((r['affiliation']|r['aux_u32']|16)&14==0 for r in alternate)
print(json.dumps({'schema':'rom-ai-extra-pool-initialization-preflight-v1','rom_sha256':ROM_SHA256,'points':points,'windows':{f'{a:06x}..{b:06x}':sha(rom[a:b]) for a,b in [(0x6abca,0x6abee),(0x6abee,0x6ac70),(0x6a780,0x6a790),(0x6ad58,0x6adc4),(0x6e274,0x6e2d0),(0x9c3ec,0x9c44a)]},'copy_call_length':468,'copy_includes_relative_cd_offset':205,'aligned_copy_shape_counts':{'sixteen_byte_groups':29,'final_word_bytes':4},'post_copy_helper_recognized_word_store':{'relative_offset':192,'size':4,'formula':'(word & 0xFFFFFFF1) | r1'},'mask6_fixed_content_records':content,'alternate_records':24,'alternate_raw_initial_mask_counts':dict(Counter(str((r['affiliation']|r['aux_u32']|16)&14) for r in alternate)),'scope':'fixed instruction windows and formation contents; declared copy/alignment arithmetic only, not complete callee/ABI/async or lifecycle semantics','ordinary_paired_cd_write_offset':0x6ad90,'alternate_main_only_cd_write_offset':0x6e2cc,'all_cd_cc_c0_writers_closed':False,'real_matrix_index_domain_proved':False,'copy_helper_complete_semantic_contract_proved':False,'natural_runtime_reachability_proved':False,'promotion_bytes':0,'decision':'keep_unknown'},indent=2,sort_keys=True))
