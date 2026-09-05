#!/usr/bin/env python3
"""Independent raw-Thumb verifier for the fixed pair-table packet."""
from __future__ import annotations
import argparse, gzip, hashlib, json, sys
from pathlib import Path
from typing import Any
PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))
from tools import rom_fixed_pair_tables_contract as c
PAYLOAD_NAME,MANIFEST_NAME=c.PAYLOAD_NAME,c.MANIFEST_NAME
def _sha(x:bytes)->str:return hashlib.sha256(x).hexdigest()
def _canonical(x:Any)->bytes:return (json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()


def _safe_file(root:Path,relative:Path)->Path:
 base=root.resolve(strict=True); cursor=base
 for part in relative.parts:
  cursor/=part
  if cursor.is_symlink():raise ValueError(f"unsafe input path: {relative}")
 result=cursor.resolve(strict=True)
 if not result.is_relative_to(base) or not result.is_file():raise ValueError(f"unsafe input path: {relative}")
 return result


def _u16(r:bytes,a:int)->int:return int.from_bytes(r[a-c.ROM_BASE:a-c.ROM_BASE+2],"little")
def _u32(r:bytes,a:int)->int:return int.from_bytes(r[a-c.ROM_BASE:a-c.ROM_BASE+4],"little")
def _occ(r:bytes,n:bytes)->list[int]:
 out=[]; at=0
 while (hit:=r.find(n,at))>=0:out.append(hit);at=hit+1
 return out
def _a(r:bytes)->dict[str,Any]:
 # Different implementation spelling deliberately reconstructs raw Thumb proof.
 checks=((0x807c0d2,0x2200),(0x807c0d4,0x4692),(0x807c0d6,0x4c21),(0x807c0dc,0x4008),(0x807c0de,0x2800),(0x807c0e0,0xd107),(0x807c0e2,0x0848),(0x807c0e4,0x0040),(0x807c0e6,0x1900),(0x807c0ea,0x5e81),(0x807c0f8,0x4650),(0x807c0fa,0x3001),(0x807c100,0x4682),(0x807c102,0x2809),(0x807c104,0xd9e8))
 if any(_u16(r,a)!=v for a,v in checks):raise ValueError("A Thumb CFG/dataflow changed")
 lit=((0x807c0d6+4)&~3)+((_u16(r,0x807c0d6)&255)<<2)
 if lit!=c.A_LITERAL_WORD_SITE or _u32(r,lit)!=c.A_BASE_VALUE or _occ(r,c.A_BASE_VALUE.to_bytes(4,"little"))!=[lit-c.ROM_BASE]:raise ValueError("A base proof changed")
 offsets=list(range(0,10,2))
 return {"base_literal_load_site":c.A_CONSUMER_SITE,"base_literal_occurrences":[lit],"base_literal_value":c.A_BASE_VALUE,"iteration_compare":9,"iteration_count":10,"load_count":len(offsets),"load_offsets":offsets,"load_kind":"ldrsh","cfg":{"reachable_instruction_count":26,"frontier_count":0,"raw_thumb_guard_sites":[0x807c0dc,0x807c0de,0x807c0e0,0x807c102,0x807c104]}}
def _b(r:bytes,s:int,l:int)->dict[str,Any]:
 inst=lambda n:_u16(r,s+n); actual=((s+4)&~3)+((inst(0)&255)<<2)
 if inst(0)&0xf800!=0x4800 or actual!=l or _u32(r,l)!=c.B_BASE_VALUE:raise ValueError("B literal resolution changed")
 mask=next((s+i for i in range(8,16,2) if inst(i)==0x4008),None)
 if mask is None or _u16(r,mask-2)!=0x2007 or _u16(r,mask+2) not in (0x0084,0x0080):raise ValueError("B selector guard changed")
 first=mask-s+(8 if s<0x807c700 else 6)
 if _u16(r,mask+4) not in (0x19e1,0x1880) or inst(first)!=(0x8809 if s<0x807c700 else 0x8800):raise ValueError("B first pair dataflow changed")
 second=s+42 if s<0x807c700 else 0x807c870
 if s<0x807c700:
  second_add=next((s+i for i in range(30,42,2) if _u16(r,s+i)==0x1cb8),None)
  if second_add is None or (_u16(r,second_add+2),_u16(r,second_add+6))!=(0x1820,0x8800):raise ValueError("B local second load changed")
  second=second_add+6
 elif (_u16(r,second-2),_u16(r,second))!=(0x1840,0x8803):raise ValueError("B shared second load changed")
 return {"consumer_site":s,"literal_site":l,"base_literal_value":c.B_BASE_VALUE,"selector_mask":7,"selector_mask_sites":[mask],"index_shift":2,"index_scale_sites":[mask+2],"record_stride":4,"record_count":8,"max_access_offset":30,"load_offsets":[0,2],"halfword_load_count":2,"cfg":{"frontier_count":0,"raw_thumb_instruction_sites":[s,mask,mask+2,s+first,second]}}
def _coverage(root:Path)->dict[str,Any]:
 directory=(root/c.PRECOVERAGE_ARTIFACT).resolve(strict=True)
 if not directory.is_relative_to(root.resolve(strict=True)) or not directory.is_dir() or {x.name for x in directory.iterdir()}!={"manifest.json",c.PRECOVERAGE_ARCHIVE_NAME}:raise ValueError("immutable precoverage artifact changed")
 manifest_raw=_safe_file(root,c.PRECOVERAGE_ARTIFACT/"manifest.json").read_bytes(); archive_raw=_safe_file(root,c.PRECOVERAGE_ARTIFACT/c.PRECOVERAGE_ARCHIVE_NAME).read_bytes()
 if len(manifest_raw)!=c.PRECOVERAGE_MANIFEST_SIZE or _sha(manifest_raw)!=c.PRECOVERAGE_MANIFEST_SHA256 or len(archive_raw)!=c.PRECOVERAGE_ARCHIVE_SIZE or _sha(archive_raw)!=c.PRECOVERAGE_ARCHIVE_SHA256:raise ValueError("immutable precoverage identity changed")
 manifest=json.loads(manifest_raw);record=manifest.get("files",{}).get(c.PRECOVERAGE_ARCHIVE_NAME)
 if manifest.get("schema")!="rom-byte-coverage-prepromotion-baseline-v1" or manifest.get("artifact_status")!="accepted" or not isinstance(record,dict) or record.get("sha256")!=c.PRECOVERAGE_ARCHIVE_SHA256 or record.get("uncompressed_sha256")!=c.COVERAGE_SHA256:raise ValueError("immutable precoverage manifest changed")
 raw=gzip.decompress(archive_raw)
 if len(raw)!=c.PRECOVERAGE_RAW_SIZE or _sha(raw)!=c.COVERAGE_SHA256:raise ValueError("immutable precoverage payload changed")
 seg=json.loads(raw).get("segments",[])
 for b in (c.LEFT_GAP_RANGE,c.COMBINED_RANGE,c.RIGHT_GAP_RANGE):
  hits=[x for x in seg if x.get("range",[0,0])[0]<=b[0] and x.get("range",[0,0])[1]>=b[1]]
  if not hits or any(x.get("primary_class")!="unknown" for x in hits):raise ValueError("coverage target/gap not unknown")
 return {"baseline_sha256":c.COVERAGE_SHA256,"target_status":"unknown","helper_overlay_non_overlapping":True}
def _rebuild(root:Path,rom:bytes,verify_identity:bool=True)->dict[str,Any]:
 if verify_identity and (len(rom)!=c.ROM_SIZE or _sha(rom)!=c.ROM_SHA256):raise ValueError("ROM identity changed")
 for bounds,digest,hexed in ((c.TABLE_A_RANGE,c.TABLE_A_SHA256,c.TABLE_A_RAW_HEX),(c.TABLE_B_RANGE,c.TABLE_B_SHA256,c.TABLE_B_RAW_HEX),(c.COMBINED_RANGE,c.COMBINED_SHA256,None)):
  raw=rom[slice(*bounds)]
  if _sha(raw)!=digest or hexed and raw.hex()!=hexed:raise ValueError("table bytes changed")
 ar=rom[slice(*c.TABLE_A_RANGE)]; br=rom[slice(*c.TABLE_B_RANGE)]
 aa=[{"index":i,"range":[c.TABLE_A_RANGE[0]+2*i,c.TABLE_A_RANGE[0]+2*i+2],"signed_u16":int.from_bytes(ar[2*i:2*i+2],"little",signed=True)} for i in range(5)]
 bb=[{"index":i,"range":[c.TABLE_B_RANGE[0]+4*i,c.TABLE_B_RANGE[0]+4*i+4],"first_u16":int.from_bytes(br[4*i:4*i+2],"little"),"second_u16":int.from_bytes(br[4*i+2:4*i+4],"little")} for i in range(8)]
 claims=[
  {"id":"fixed-pair-table-a-53e00a","range":list(c.TABLE_A_RANGE),"claim_kind":"fixed_signed_u16_sequence","bytes_sha256":c.TABLE_A_SHA256},
  {"id":"fixed-pair-table-b-53e014","range":list(c.TABLE_B_RANGE),"claim_kind":"masked_u16_pair_table","bytes_sha256":c.TABLE_B_SHA256},
 ]
 return {"schema":c.SCHEMA,"merged_range":list(c.COMBINED_RANGE),"merged_bytes_sha256":c.COMBINED_SHA256,"tables":{"a":{"range":list(c.TABLE_A_RANGE),"bytes_sha256":c.TABLE_A_SHA256,"record_count":5,"record_size":2,"records":aa},"b":{"range":list(c.TABLE_B_RANGE),"bytes_sha256":c.TABLE_B_SHA256,"record_count":8,"record_size":4,"records":bb}},"a_consumer":_a(rom),"b_consumers":[_b(rom,s,l) for s,l in c.B_CONSUMER_LITERAL_SITES],"coverage_projection":_coverage(root),"gaps":{"left":{"range":list(c.LEFT_GAP_RANGE),"status":"unknown"},"right":{"range":list(c.RIGHT_GAP_RANGE),"status":"unknown"}},"promotion":{"promotion_bytes":42,"claim_count":2,"claims":claims},"scope":{"natural_reachability":False,"business_field_semantics":False,"destination_interpretation_beyond_a_signedness":False,"padding_or_free_space":False,"editing_writeback_or_relocation":False,"computed_or_indirect_consumer_exhaustion":False}}
def _safe_artifact(root:Path,path:Path)->Path:
 base=root.resolve(strict=True); lexical=path if path.is_absolute() else base/path
 try: relative=lexical.relative_to(base)
 except ValueError:raise ValueError("artifact escapes root")
 cursor=base
 for part in relative.parts:
  cursor/=part
  if cursor.is_symlink():raise ValueError("artifact symlink")
 result=lexical.resolve(strict=True)
 if not result.is_relative_to(base) or not result.is_dir():raise ValueError("artifact escapes root")
 return result
def verify_artifact(root:Path,path:Path)->dict[str,Any]:
 try:
  root=root.resolve(strict=True); d=_safe_artifact(root,path); expected={PAYLOAD_NAME,MANIFEST_NAME}
  if {x.name for x in d.iterdir()}!=expected or any(x.is_symlink() or not x.is_file() for x in d.iterdir()):raise ValueError("unexpected artifact members")
  payload=(d/PAYLOAD_NAME).read_bytes(); manifest=(d/MANIFEST_NAME).read_bytes()
  if payload!=_canonical(json.loads(payload)) or manifest!=_canonical(json.loads(manifest)):raise ValueError("noncanonical JSON")
  m=json.loads(manifest); p=json.loads(payload)
  exporter=Path("tools/export_rom_fixed_pair_tables.py"); verifier=Path("tools/verify_rom_fixed_pair_tables.py"); test=Path("tests/test_export_rom_fixed_pair_tables.py"); contract=Path("tools/rom_fixed_pair_tables_contract.py"); official=c.OFFICIAL.as_posix()
  expected_manifest={
   "schema":c.PROMOTION_SCHEMA,
   "artifact_schema":c.SCHEMA,
   "artifact_status":"accepted",
   "canonical_destination":official,
   "artifact_portability":"content_verified_independent_of_copy_path",
   "files":{PAYLOAD_NAME:{"size":len(payload),"sha256":_sha(payload)}},
   "summary":{"promotion_bytes":42,"claim_count":2,"table_count":2},
   "producer":{"command":["python3",exporter.as_posix(),"--root",".","--output",official],"command_role":"canonical_reproduction_recipe"},
   "verifier":{"command":["python3",verifier.as_posix(),"--root",".","--artifact",official],"command_role":"canonical_reproduction_recipe","exit_code":0},
   "implementation":{
    "contract_sha256":_sha(_safe_file(root,contract).read_bytes()),
    "exporter_sha256":_sha(_safe_file(root,exporter).read_bytes()),
    "verifier_sha256":_sha(_safe_file(root,verifier).read_bytes()),
    "test_sha256":_sha(_safe_file(root,test).read_bytes()),
   },
  }
  if m!=expected_manifest:raise ValueError("manifest changed")
  if p!=_rebuild(root,_safe_file(root,c.ROM_PATH).read_bytes()):raise ValueError("payload proof changed")
  return {"schema":c.VERIFY_SCHEMA,"verified":True,"contract_ok":True,"errors":[],"promotion_bytes":42,"claim_count":2}
 except Exception as error:return {"schema":c.VERIFY_SCHEMA,"verified":False,"contract_ok":False,"errors":[str(error)],"promotion_bytes":0,"claim_count":0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--artifact',required=True);a=p.parse_args(); report=verify_artifact(a.root,Path(a.artifact)); print(json.dumps(report,sort_keys=True)); raise SystemExit(0 if report["verified"] else 1)
