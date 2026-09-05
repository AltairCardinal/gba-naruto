#!/usr/bin/env python3
"""Independently verify the seven-family consumed-literal packet."""
from __future__ import annotations
import argparse,bisect,hashlib,json,struct
from pathlib import Path
from typing import Any

ROM=Path('rom/base.gba'); ROM_SIZE=6291456; ROM_SHA='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
COVERAGE=Path('sequel/rom-byte-coverage.json'); COVERAGE_SHA='66a5e95bd2927f9db13435f6862a052ad60634cfbd3a8b5dfad07459a4a12329'
CONTRACT_SHA='86b3cd6e0321b97ad11b28c19a31e3786217375c3fa8a26e4f4bc2c5b7796f32'
PAYLOAD_NAME='rom-cfg-proven-roots-batch-consumed-literals.json'
PROMOTION_BATCH='rom-cfg-proven-roots-batch-consumed-literals-v1'; PRIMARY_CLASS='armv4t_cfg_proven_roots_batch_consumed_literal_word'; CLAIM_KIND=PRIMARY_CLASS+'_bytes'
VERSIONS=(2,3,4,5,7,8,9)
SOURCE_HASHES={
2:('a3683f3d21ec5a162b4cdb97c70b639ff261d9ff5e0f3bb4941848205bb4d9ca','a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba','e40028e04b2225c904105bd40959b8413f8dc4bcb1fa7cb99d1e9d3d28755c03','3d834e1e92c1ea1c7cf4146ac6f23b940ea864c69783c341af64ba462545fe55','defed8cf5664bb57b58d48835d796022ac802844c1d59d3f3de5314938c3b496'),
3:('4aa979aa65408163e577f7d728ba32a99a13bd6c9615c40f28a570036e5ba275','f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2','6b4f9ad6410d202af9abc8462b73d6ea879029d377ea88e6c8ee9f36fd12674b','15b06ae23285d397244ce49d153e3c4b93305af8d5a0b2dd81abe3b3655f5250','0e86b1b0da8b8743ae25afebe6435156caa9a93c1824d547ae2266c794caa74e'),
4:('e306ac59b4b9a815702fda8aef54058908fb9113a5afad4be938c69d42d67404','d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb','e92c1f6748a8898bd504f1ea72d10a134b22ae078515d2f40c2cdad3842b566f','2520457a4862c628f86a236529d0d29fa227212b8b526e42f301b8f89a9606ba','58808081937e3953726f67108a1e74f322b91e2bb4938679bfcae1bad270d3cc'),
5:('f6deb37d40ae4ea83e220adc8303c64646a9280d34d6c325d8ea0492963dcd8d','680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040','75c0e29bfe9d87f3ad53f393e3a8a9b98fe9cd9e5b6e5bec5e37756652f34c41','ec188e5e674b87a1cdda4fa6848d6fe5a2d9fb0617ea6d818be43237d05997f9','f777368b0a80c8cf6093dc8554c29748a598c493d1945107eb2b07eba80c918a'),
7:('da9a1b5fe7ce8e7889fbba9fe8251c907ed18f6b273cbcc3be145101ece99114','184e9b84df829fb1ad41f272aabe931c1a1f86111eebd60629ad2d2a23d89a06','660850bf9f26a9e5e2f75390320772638cddb068c5949f96c757b02b141c1706','30e67f172e8a34c85e93838bd7863f1d1417823c83b1cf2a74fa8cd61aae01a5','8864768ac5cadccd4db70cd9ad889027e2e5bdf7f14f507b15c1923a2932054e'),
8:('0c9194507c50b7f2c00c6ee09b517211f64b7b344475952fe3c908b1e54e0002','5fa1150d2ed9f785d50132a9eae316af192d70838fbee3061d7d3010c35fb1d6','8b146a31ba0690240a21971f34716950cd17ac82f5208cd5a172f134f939ce05','88d2726fbe2657105759d23ae04f95ae2685ad2ad416640a8a5bbd2bb826b254','f3c542d29b8b9bcbeafcfb08efaed585fcd6f6974b4b641aaa8b9cb7149be4b3'),
9:('1914d6244ceaa7791cb4c77d97143151b4f28183ea857c052c9c51d3c8a09e6b','fb961c6d0ba5cdb56c016a5d10b149d87e5ce9158bcb1e6e9deae8664c46555b','51aef64e7cec4d95cf565ad852155dc50f45c127c50bebf0f8968b4d009a9d00','b75ed5bad517fb08ebf2ae08d336c1dcee6ab334c4927559f41a2fcfad399935','1842489062ba30d0e2aace37b34ef7c843b8969c766992bd831990ae954b8581')}
V3_PACKET=(Path('artifacts/rom-cfg-v3-consumed-literals-v1/manifest.json'),'2ab82e1747256f0b0f8c7cd22b96d1cd802aeffb40cebea56b6a417de8f72940',Path('artifacts/rom-cfg-v3-consumed-literals-v1/rom-cfg-v3-consumed-literals.json'),'1407aa1204218c4861e620192226a5b4cd718172e5983f03f2f953263f186b4d')
BASE={'classified_bytes':6138856,'unknown_bytes':152600,'claim_count':15666,'segment_count':17182}
PROJECT={'classified_bytes':6140112,'unknown_bytes':151344,'claim_count':15782,'segment_count':17250,'delta':{'classified_bytes':1256,'unknown_bytes':-1256,'claim_count':116,'segment_count':68}}
EXPECTED={'block_count':1205,'instruction_count':6490,'instruction_bytes':13488,'source_instruction_count':376,'unique_target_word_count':314,'target_bytes':1256,'merged_target_range_count':116,'block_vector_sha256':'e11d5ce898648ebd0e3d8289b915bce421a90b6088e6b9ac0fbed39b37ad54e6','family_vector_sha256':'c588fbb0977b574535fe9119e42515172d6ea5da3822ef15fa2bc7ff0a1bbeb1','source_vector_sha256':'a31cf75b56466d10f5709ed67bb3ced5c7a9a979684de0385b8b73af63e0aced','source_offset_vector_sha256':'ddb38d1a912c3dc6421ff33efae8cdf825d853bbca730c77f71fb84242d86afe','target_vector_sha256':'33f69b5ca6d465b8c3a92d8937108df59388ab85a5aac3059b7fa8dc0ff7357f','target_offset_vector_sha256':'7e87f1da67026609cb5dd06ff7e45039578da62f738ec945ee3b56db64ccb26e','range_vector_sha256':'39c1548d8d085f63129260e02189f445d72e362d80b6b0852fa7de2ac512cc45','packed_target_bytes_sha256':'84f2b235b43dcac36608d964606d3290f0291524d6fe8ddcaeea85f79bd0374e'}

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def can(x:Any)->bytes:return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def bound(root:Path,p:Path,h:str)->bytes:
 b=(root/p).read_bytes()
 if sha(b)!=h: raise ValueError(f'bound input identity changed: {p}')
 return b
def validate_coverage(cov:dict[str,Any],baseline_mode:bool)->list[dict[str,Any]]:
 if cov.get('schema')!='rom-byte-coverage-v1':raise ValueError('coverage schema changed')
 summary=cov.get('summary');claims=cov.get('claims');segs=cov.get('segments')
 if not isinstance(summary,dict) or not isinstance(claims,list) or not isinstance(segs,list):raise ValueError('coverage structure changed')
 if baseline_mode:
  if any(summary.get(k)!=v for k,v in BASE.items()) or len(claims)!=BASE['claim_count'] or len(segs)!=BASE['segment_count']:raise ValueError('coverage baseline summary changed')
  return segs
 if summary.get('claim_count')!=len(claims) or summary.get('segment_count')!=len(segs):raise ValueError('coverage summary denominator changed')
 cursor=classified=unknown=0
 for i,seg in enumerate(segs):
  interval=seg.get('range')
  if not isinstance(interval,list) or len(interval)!=2 or interval[0]!=cursor or not isinstance(interval[1],int) or interval[1]<=cursor:raise ValueError(f'coverage segment {i} changed')
  size=interval[1]-cursor
  if seg.get('primary_class')=='unknown':unknown+=size
  else:classified+=size
  cursor=interval[1]
 if cursor!=ROM_SIZE or classified+unknown!=ROM_SIZE or summary.get('classified_bytes')!=classified or summary.get('unknown_bytes')!=unknown:raise ValueError('coverage summary changed')
 return segs
def _thumb_width(data:bytes,offset:int,end:int)->int:
 if offset<0 or offset+2>end:raise ValueError('Thumb boundary escaped block')
 first=struct.unpack_from('<H',data,offset)[0]
 if first&0xf800==0xf000 and offset+4<=end and struct.unpack_from('<H',data,offset+2)[0]&0xf800==0xf800:return 4
 return 2
def _ldr_target(offset:int,halfword:int)->int:
 if halfword&0xf800!=0x4800:raise ValueError('not LDR literal')
 return ((offset+4)&~3)+(halfword&255)*4
def _rebuild_payload(root:Path)->dict[str,Any]:
 root=root.resolve();rom=(root/ROM).read_bytes()
 if len(rom)!=ROM_SIZE or sha(rom)!=ROM_SHA:raise ValueError('base ROM identity changed')
 cov_bytes=(root/COVERAGE).read_bytes();cov_sha=sha(cov_bytes)
 baseline_mode=cov_sha==COVERAGE_SHA;cov=json.loads(cov_bytes);segs=validate_coverage(cov,baseline_mode)
 starts=[x['range'][0] for x in segs]
 def owner(o:int):return segs[bisect.bisect_right(starts,o)-1]
 sources=[];block_vector=[];families=[];source_artifacts=[];target_families={}
 for v in VERSIONS:
  name=f'rom-cfg-proven-roots-v{v}';d=Path('artifacts')/name; paths=(d/'manifest.json',d/f'{name}.json',Path(f'tools/export_rom_cfg_proven_roots_v{v}.py'),Path(f'tools/verify_rom_cfg_proven_roots_v{v}.py'),Path(f'tests/test_export_rom_cfg_proven_roots_v{v}.py'))
  raws=[bound(root,p,h) for p,h in zip(paths,SOURCE_HASHES[v])];src=json.loads(raws[1]);blocks=[b for b in src['extension']['blocks'] if b.get('mode')=='thumb'];raw_count=owner_count=ic=ib=0;raw_targets=set();family_targets={};family_sources=[]
  for b in blocks:
   block_vector.append({'family':f'v{v}','id':b['id'],'range':b['range'],'instruction_count':b['instruction_count'],'bytes_sha256':b['bytes_sha256']});o,e=b['range']
   if sha(rom[o:e])!=b['bytes_sha256']:raise ValueError('source block bytes changed')
   count=0
   while o<e:
    z=_thumb_width(rom,o,e)
    h=struct.unpack_from('<H',rom,o)[0];ic+=1;ib+=z;count+=1
    if z==2 and h&0xf800==0x4800:
     t=_ldr_target(o,h);raw_count+=1;raw_targets.add(t);q=owner(o)
     if q['primary_class']==f'armv4t_cfg_proven_roots_v{v}_reachable_thumb_code' and q['range'][0]<=o and o+2<=q['range'][1]:
      owner_count+=1;tq=owner(t)
      if tq['primary_class']==('unknown' if baseline_mode else PRIMARY_CLASS) and tq['range'][0]<=t and t+4<=tq['range'][1]:
       row={'source_family':f'v{v}','source_file_offset':o,'source_raw_hex':rom[o:o+2].hex(),'target_file_offset':t,'target_raw_hex':rom[t:t+4].hex()};family_sources.append(row);family_targets.setdefault(t,[]).append(o);target_families.setdefault(t,set()).add(v)
    o+=z
   if count!=b['instruction_count'] or o!=e:raise ValueError('block instruction denominator changed')
  sources+=family_sources;families.append({'family':f'v{v}','block_count':len(blocks),'instruction_count':ic,'instruction_bytes':ib,'raw_source_instruction_count':raw_count,'raw_unique_target_word_count':len(raw_targets),'source_owner_eligible_instruction_count':owner_count,'source_instruction_count':len(family_sources),'unique_target_word_count':len(family_targets),'target_bytes':len(family_targets)*4});source_artifacts.append({'family':f'v{v}','path':d.as_posix(),'manifest_sha256':SOURCE_HASHES[v][0],'payload_sha256':SOURCE_HASHES[v][1],'exporter_sha256':SOURCE_HASHES[v][2],'verifier_sha256':SOURCE_HASHES[v][3],'test_sha256':SOURCE_HASHES[v][4]})
 sources.sort(key=lambda x:(x['source_file_offset'],x['target_file_offset'],x['source_family']));targets={}
 for x in sources:targets.setdefault(x['target_file_offset'],[]).append({'source_family':x['source_family'],'source_file_offset':x['source_file_offset']})
 target_rows=[{'target_file_offset':t,'target_raw_hex':rom[t:t+4].hex(),'sources':s} for t,s in sorted(targets.items())];ranges=[]
 for t in sorted(targets):
  if ranges and t==ranges[-1][1]:ranges[-1][1]+=4
  else:ranges.append([t,t+4])
 records=[{'range':r,'bytes_sha256':sha(rom[r[0]:r[1]])} for r in ranges];packed=b''.join(rom[t:t+4] for t in sorted(targets))
 denominator={'block_count':len(block_vector),'instruction_count':sum(x['instruction_count'] for x in families),'instruction_bytes':sum(x['instruction_bytes'] for x in families),'source_instruction_count':len(sources),'unique_target_word_count':len(targets),'target_bytes':len(packed),'merged_target_range_count':len(ranges),'block_vector_sha256':sha(can(block_vector)),'family_vector_sha256':sha(can(families)),'source_vector_sha256':sha(can(sources)),'source_offset_vector_sha256':sha(can([x['source_file_offset'] for x in sources])),'target_vector_sha256':sha(can(target_rows)),'target_offset_vector_sha256':sha(can(sorted(targets))),'range_vector_sha256':sha(can(records)),'packed_target_bytes_sha256':sha(packed)}
 if denominator!=EXPECTED:raise ValueError('batch literal denominator changed')
 v3=json.loads(bound(root,V3_PACKET[2],V3_PACKET[3]));v3_targets={x['target_file_offset'] for x in v3['target_words']}
 return {'schema':'rom-cfg-proven-roots-batch-consumed-literals-v1','rom':{'path':ROM.as_posix(),'size':ROM_SIZE,'sha256':ROM_SHA},'public_contract_sha256':CONTRACT_SHA,'source_artifacts':source_artifacts,'coverage_baseline':{'path':COVERAGE.as_posix(),'sha256':COVERAGE_SHA,'summary':BASE},'families':families,'denominator':denominator,'source_to_target':sources,'target_words':target_rows,'cross_family_target_overlap_word_count':sum(len(v)>1 for v in target_families.values()),'v3_packet_target_overlap_word_count':len(set(targets)&v3_targets),'promotion':{'promotion_batch':PROMOTION_BATCH,'primary_class':PRIMARY_CLASS,'claim_kind':CLAIM_KIND,'ranges':ranges,'range_records':records},'coverage_projection':PROJECT,'scope':{'frozen_family_membership_reused':True,'source_owner_restricted_per_family':True,'targets_complete_current_unknown':True,'cfg_traversal_expanded':False,'loaded_value_semantics_proven':False},'non_claims':['No CFG traversal or frontier is expanded.','No adjacent unknown byte or whole segment is promoted.','Loaded values are not interpreted as pointers, constants, tables, resources, or business semantics.']}

def _read_artifact(artifact:Path):
 if artifact.is_symlink() or not artifact.is_dir():raise ValueError('artifact directory missing or symlink')
 members=list(artifact.iterdir())
 if {p.name for p in members}!={'manifest.json',PAYLOAD_NAME} or any(p.is_symlink() or not p.is_file() for p in members):raise ValueError('artifact file set changed')
 mb=(artifact/'manifest.json').read_bytes();pb=(artifact/PAYLOAD_NAME).read_bytes();m=json.loads(mb);p=json.loads(pb)
 if m.get('files',{}).get(PAYLOAD_NAME)!={'sha256':sha(pb),'size':len(pb)}:raise ValueError('payload identity mismatch')
 return m,p,pb

def verify_root(root:Path,artifact:Path):
 m,p,pb=_read_artifact(artifact);expected=_rebuild_payload(root)
 if p!=expected:raise ValueError('payload does not match independently rebuilt contract')
 expected_manifest={'schema':'git-artifact-promotion-v1','artifact_schema':'rom-cfg-proven-roots-batch-consumed-literals-artifact-v1','artifact_status':'accepted','payload_schema':p['schema'],'public_contract_sha256':CONTRACT_SHA,'rom':p['rom'],'source_artifacts':p['source_artifacts'],'coverage_baseline':p['coverage_baseline'],'denominator':p['denominator'],'promotion':p['promotion'],'coverage_projection':p['coverage_projection'],'scope':p['scope'],'non_claims':p['non_claims'],'verifier':{'command':['python3','-I','-S','tools/verify_rom_cfg_proven_roots_batch_consumed_literals.py','--root','.','--artifact','artifacts/rom-cfg-proven-roots-batch-consumed-literals-v1'],'exit_code':0},'files':{PAYLOAD_NAME:{'sha256':sha(pb),'size':len(pb)}}}
 if m!=expected_manifest:raise ValueError('manifest does not match independently rebuilt contract')
 return {'schema':'rom-cfg-proven-roots-batch-consumed-literals-verification-v1','verified':True,'contract_ok':True,'families':expected['families'],'denominator':expected['denominator'],'artifact':{'manifest_sha256':sha((artifact/'manifest.json').read_bytes()),'payload_sha256':sha(pb)}}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--artifact',type=Path,required=True);a=p.parse_args();print(json.dumps(verify_root(a.root.resolve(),a.artifact.absolute()),indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
