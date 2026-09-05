#!/usr/bin/env python3
"""Independently verify the alternate-dialogue table artifact from raw ROM."""
from __future__ import annotations
import argparse,hashlib,json,struct,sys
from pathlib import Path

SCHEMA="rom-alternate-dialogue-table-v1"; ROM=Path("rom/base.gba"); COVERAGE=Path("sequel/rom-byte-coverage.json")
ROM_SHA="1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"; COVERAGE_SHA="b71a91d1e3c469a884f6d434a82ce23e751e201e83728e6ffc040a6226bfed52"
TS,TE=0x459284,0x459414; PAYLOAD="alternate-dialogue-table.json"; BUNDLE="alternate-dialogue-text.bin"; FILES={PAYLOAD,BUNDLE,"manifest.json"}
LIMITATIONS=["computed and indirect producers of 0x080914D8 are not exhausted","natural completeness of every entry path is not claimed","Unicode decoding, editing, write-back, relocation, free space, and allocatable space are not claimed"]
def sha(x):return hashlib.sha256(x).hexdigest()
def safe(root,rel):
 p=root/rel
 if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root):raise ValueError(f"unsafe input: {rel}")
 return p.read_bytes()
def consumer(rom):
 windows={"direct_producer":(0x8F9E8,0x8F9F4,"77fd7ee70320002101f072fd"),"entry_args":(0x914D8,0x914F0,"f0b557464e464546e0b49fb00006000e0b900906090e0c91"),"cpuset_clear":(0x915A0,0x915B0,"ae4f0022079207a8ad4a391c0af098fd"),"mode_and_base":(0x917B0,0x917CC,"4d4a0f92119b1a93504619900c99002901d14a4a0f920cab1b783b70"),"initial_index":(0x91944,0x9195E,"387800280bd17878b8800423f95e8800401880000f9908181090"),"increment":(0x91BE4,0x91BF0,"7878013000218a4678701c04"),"upper_bound":(0x91E4E,0x91E5A,"78782026132800d98fe08de0"),"backedge":(0x91F76,0x91F84,"002601200af0fbfaff2e00d054e4"),"primary_field":(0x919DA,0x919EC,"109a50680221009100210b9a0023d4f7b6fe"),"label_fields":(0x91A20,0x91A68,"0806050e1c042414524610190678a0001c494018630419141691009102212a1c0223d4f789feb00040440068169a009200212a1c0423d4f77ffe01342404230c2414022cdeddd3f7"),"parser_chain":(0x66788,0x6678E,"4946fff76ffd"),"nul_check":(0x6671C,0x66728,"079a1078002800d0abe50798")}
 for n,(a,b,h) in windows.items():
  if rom[a:b].hex()!=h:raise ValueError(f"{n} consumer window changed")
 if struct.unpack_from("<I",rom,0x918EC)[0]!=0x08459284 or struct.unpack_from("<I",rom,0x91860)[0]!=0x05000038:raise ValueError("consumer literal changed")
 return {"direct_producer":"0x0808F9F0","producer_arguments":{"r0":3,"r1":0},"root":"0x080914D8","work_struct":"0x02002880","cpuset_clear_call":"0x080915AC","cpuset_control":"0x05000038","mode_write":"0x080917CA","base_literal":"0x080918EC","table_base":"0x08459284","initial_index":0,"increment_write":"0x08091BEC","index_compare":"0x08091E52 CMP #19","only_state_zero_write":"0x08091F76","dispatcher_backedge":"0x08091F82 -> 0x0809182E","index_domain":[0,19],"index_upper_bound":19,"record_formula":"table_base + index * 20","field_offsets":[4,8,12,16],"renderer":"0x08066758","nul_parser":"0x0806626C","glyph_wrapper":"0x08065F84","glyph_expander":"0x08065EB8","windows":{n:{"range":[a,b],"sha256":sha(rom[a:b])} for n,(a,b,_) in windows.items()}}
def expected(root,rom):
 c=consumer(rom);targets=[]
 for row in range(20):
  w=struct.unpack_from("<5I",rom,TS+20*row)
  if w[0] not in {1,0x10001,0x20001}:raise ValueError("row flag changed")
  for slot,p in enumerate(w[1:]):
   s=p-0x08000000
   if not 0x458794<=s<TS:raise ValueError("pointer escapes")
   try:e=rom.index(0,s,TS)+1
   except ValueError as x:raise ValueError("missing NUL") from x
   targets.append({"row":row,"slot":slot,"table_offset":TS+20*row+4+4*slot,"pointer":f"0x{p:08X}","range":[s,e],"size":e-s,"sha256":sha(rom[s:e])})
 ordered=sorted(targets,key=lambda x:x["range"])
 if len({x["pointer"] for x in ordered})!=80 or any(y["range"][0]<x["range"][1] for x,y in zip(ordered,ordered[1:])):raise ValueError("target denominator changed")
 gaps=[]
 for i,t in enumerate(ordered):
  a=t["range"][1];b=ordered[i+1]["range"][0] if i<79 else TS;raw=rom[a:b]
  if not raw or any(raw):raise ValueError("gap bytes changed")
  gaps.append({"id":i,"range":[a,b],"size":len(raw),"sha256":sha(raw)})
 bundle=b"".join(rom[x["range"][0]:x["range"][1]] for x in ordered)
 claims=[{"id":"alternate-dialogue-table","primary_class":"alternate_dialogue_record_table","claim_kind":"alternate_dialogue_record_table_bytes","range":[TS,TE],"bytes_sha256":sha(rom[TS:TE])}]+[{"id":f"alternate-dialogue-text-{i:02d}","primary_class":"dialogue_encoded_text","claim_kind":"alternate_dialogue_renderer_consumed_record_bytes","range":x["range"],"bytes_sha256":x["sha256"]} for i,x in enumerate(ordered)]+[{"id":f"alternate-dialogue-gap-{i:02d}","primary_class":"dialogue_inter_record_zero_padding","claim_kind":"alternate_dialogue_parser_bound_zero_padding_bytes","range":x["range"],"bytes_sha256":x["sha256"]} for i,x in enumerate(gaps)]
 impl={"exporter_sha256":sha(safe(root,Path("tools/export_rom_alternate_dialogue_table.py"))),"verifier_sha256":sha(Path(__file__).read_bytes()),"test_sha256":sha(safe(root,Path("tests/test_export_rom_alternate_dialogue_table.py")))}
 historical={"path":str(COVERAGE),"sha256":COVERAGE_SHA,"observed_during_this_build":False,"live_projection_verified":False,"projection_gate":"deferred_to_coverage_auditor"}
 owner_gate={"status":"deferred_to_coverage_auditor","required_points":[{"address":0x8F9F0,"primary_class":"consumer_code_slice","claim_id":"verified-reuse-wram-overview-entry-08f9e2"},{"address":0x914D8,"primary_class":"armv4t_cfg_proven_roots_v18_reachable_thumb_code","claim_id":"cfg-v18-reachable_thumb_code-09-0914d8"},{"address":0x918EC,"primary_class":"armv4t_cfg_proven_roots_v17_consumed_literal_word","claim_id":"cfg-v17-consumed_literal_words-01-091848"},{"address":0x91E52,"primary_class":"armv4t_cfg_proven_roots_v17_reachable_thumb_code","claim_id":"cfg-v17-reachable_thumb_code-10-091d88"},{"address":0x91F82,"primary_class":"armv4t_cfg_proven_roots_v17_reachable_thumb_code","claim_id":"cfg-v17-reachable_thumb_code-13-091f3c"}]}
 payload={"schema":SCHEMA,"rom":{"path":str(ROM),"sha256":ROM_SHA,"size":len(rom)},"historical_coverage_reference":historical,"upstream_owner_gate":owner_gate,"implementation":impl,"consumer":c,"table":{"range":[TS,TE],"row_count":20,"row_size":20,"sha256":sha(rom[TS:TE])},"targets":ordered,"gaps":gaps,"summary":{"row_count":20,"target_count":80,"gap_count":80,"table_bytes":400,"text_bytes":1214,"gap_bytes":1586,"promoted_bytes":3200},"promotion":{"promotion_bytes":3200,"claims":claims},"limitations":LIMITATIONS}
 return payload,bundle
def verify(root,artifact):
 try:
  root=root.resolve(strict=True)
  lexical=artifact if artifact.is_absolute() else root/artifact
  if lexical.is_symlink():raise ValueError("unsafe artifact directory")
  artifact=lexical.resolve(strict=True)
  if not artifact.is_dir() or not artifact.is_relative_to(root):raise ValueError("unsafe artifact directory")
  members=list(artifact.iterdir())
  if any(x.is_symlink() or not x.is_file() for x in members) or {x.name for x in members}!=FILES:raise ValueError("artifact file set changed")
  rom=safe(root,ROM)
  if sha(rom)!=ROM_SHA:raise ValueError("base ROM SHA-256 changed")
  exp,bundle=expected(root,rom);pr=(artifact/PAYLOAD).read_bytes();actual=json.loads(pr);br=(artifact/BUNDLE).read_bytes();manifest=json.loads((artifact/"manifest.json").read_text())
  if actual!=exp:raise ValueError("payload differs from independent raw-ROM reconstruction")
  if br!=bundle:raise ValueError("text bundle differs from raw ROM")
  expected_manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"accepted","files":{PAYLOAD:sha(pr),BUNDLE:sha(br)},"producer":{"command":["python3","tools/export_rom_alternate_dialogue_table.py","--root",".","--output-dir",f"artifacts/{SCHEMA}"],**exp["implementation"]},"rom_sha256":ROM_SHA,"historical_coverage_reference":exp["historical_coverage_reference"],"limitations":LIMITATIONS}
  if manifest!=expected_manifest:raise ValueError("manifest binding changed")
  return {"schema":"rom-alternate-dialogue-table-verification-v1","verified":True,"promotion_bytes":exp["summary"]["promoted_bytes"],**exp["summary"],"errors":[]}
 except Exception as e:return {"schema":"rom-alternate-dialogue-table-verification-v1","verified":False,"errors":[str(e)]}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path.cwd());ap.add_argument("--artifact-dir",type=Path,default=Path(f"artifacts/{SCHEMA}"));a=ap.parse_args();r=verify(a.root,a.artifact_dir);print(json.dumps(r,sort_keys=True));return 0 if r["verified"] else 1
if __name__=="__main__":raise SystemExit(main())
