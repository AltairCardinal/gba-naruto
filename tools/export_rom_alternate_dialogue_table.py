#!/usr/bin/env python3
"""Export the fixed 20-row alternate-dialogue table closure."""
from __future__ import annotations

import argparse, ctypes, errno, hashlib, json, os, shutil, struct, tempfile
from pathlib import Path

SCHEMA="rom-alternate-dialogue-table-v1"; ROM=Path("rom/base.gba"); COVERAGE=Path("sequel/rom-byte-coverage.json")
ROM_SHA="1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA="b71a91d1e3c469a884f6d434a82ce23e751e201e83728e6ffc040a6226bfed52"
TABLE_START,TABLE_END,ROWS,ROW_SIZE=0x459284,0x459414,20,20
PAYLOAD="alternate-dialogue-table.json"; BUNDLE="alternate-dialogue-text.bin"; FILES={PAYLOAD,BUNDLE,"manifest.json"}
LIMITATIONS=["computed and indirect producers of 0x080914D8 are not exhausted","natural completeness of every entry path is not claimed","Unicode decoding, editing, write-back, relocation, free space, and allocatable space are not claimed"]

def sha(x:bytes)->str:return hashlib.sha256(x).hexdigest()
def _safe(root:Path, rel:Path)->bytes:
    p=root/rel
    if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root): raise ValueError(f"unsafe input: {rel}")
    return p.read_bytes()
def _window(rom:bytes,a:int,b:int,h:str,name:str):
    if rom[a:b].hex()!=h: raise ValueError(f"{name} consumer window changed")

def _consumer(rom:bytes)->dict:
    windows={
      "direct_producer":(0x8F9E8,0x8F9F4,"77fd7ee70320002101f072fd"),
      "entry_args":(0x914D8,0x914F0,"f0b557464e464546e0b49fb00006000e0b900906090e0c91"),
      "cpuset_clear":(0x915A0,0x915B0,"ae4f0022079207a8ad4a391c0af098fd"),
      "mode_and_base":(0x917B0,0x917CC,"4d4a0f92119b1a93504619900c99002901d14a4a0f920cab1b783b70"),
      "initial_index":(0x91944,0x9195E,"387800280bd17878b8800423f95e8800401880000f9908181090"),
      "increment":(0x91BE4,0x91BF0,"7878013000218a4678701c04"),
      "upper_bound":(0x91E4E,0x91E5A,"78782026132800d98fe08de0"),
      "backedge":(0x91F76,0x91F84,"002601200af0fbfaff2e00d054e4"),
      "primary_field":(0x919DA,0x919EC,"109a50680221009100210b9a0023d4f7b6fe"),
      "label_fields":(0x91A20,0x91A68,"0806050e1c042414524610190678a0001c494018630419141691009102212a1c0223d4f789feb00040440068169a009200212a1c0423d4f77ffe01342404230c2414022cdeddd3f7"),
      "parser_chain":(0x66788,0x6678E,"4946fff76ffd"),
      "nul_check":(0x6671C,0x66728,"079a1078002800d0abe50798"),
    }
    for n,(a,b,h) in windows.items(): _window(rom,a,b,h,n)
    if struct.unpack_from("<I",rom,0x918EC)[0]!=0x08459284: raise ValueError("alternate table base literal changed")
    if struct.unpack_from("<I",rom,0x91860)[0]!=0x05000038: raise ValueError("CpuSet clear control changed")
    return {"direct_producer":"0x0808F9F0","producer_arguments":{"r0":3,"r1":0},"root":"0x080914D8","work_struct":"0x02002880","cpuset_clear_call":"0x080915AC","cpuset_control":"0x05000038","mode_write":"0x080917CA","base_literal":"0x080918EC","table_base":"0x08459284","initial_index":0,"increment_write":"0x08091BEC","index_compare":"0x08091E52 CMP #19","only_state_zero_write":"0x08091F76","dispatcher_backedge":"0x08091F82 -> 0x0809182E","index_domain":[0,19],"index_upper_bound":19,"record_formula":"table_base + index * 20","field_offsets":[4,8,12,16],"renderer":"0x08066758","nul_parser":"0x0806626C","glyph_wrapper":"0x08065F84","glyph_expander":"0x08065EB8","windows":{n:{"range":[a,b],"sha256":sha(rom[a:b])} for n,(a,b,_) in windows.items()}}

def _implementation(root:Path)->dict:
    return {"exporter_sha256":sha(Path(__file__).read_bytes()),"verifier_sha256":sha(_safe(root,Path("tools/verify_rom_alternate_dialogue_table.py"))),"test_sha256":sha(_safe(root,Path("tests/test_export_rom_alternate_dialogue_table.py")))}

def build(root:Path):
    root=root.resolve(strict=True); rom=_safe(root,ROM)
    if sha(rom)!=ROM_SHA: raise ValueError("base ROM SHA-256 changed")
    consumer=_consumer(rom); table=rom[TABLE_START:TABLE_END]
    targets=[]
    for row in range(ROWS):
        words=struct.unpack_from("<5I",rom,TABLE_START+row*ROW_SIZE)
        if words[0] not in {1,0x10001,0x20001}: raise ValueError("row flag changed")
        for slot,p in enumerate(words[1:]):
            start=p-0x08000000
            if not 0x458794<=start<TABLE_START: raise ValueError("target pointer escapes alternate text bank")
            try:end=rom.index(0,start,TABLE_START)+1
            except ValueError as e: raise ValueError("target has no NUL terminator") from e
            targets.append({"row":row,"slot":slot,"table_offset":TABLE_START+row*20+4+slot*4,"pointer":f"0x{p:08X}","range":[start,end],"size":end-start,"sha256":sha(rom[start:end])})
    if len({x["pointer"] for x in targets})!=80: raise ValueError("target pointer denominator changed")
    ordered=sorted(targets,key=lambda x:x["range"])
    if any(b["range"][0]<a["range"][1] for a,b in zip(ordered,ordered[1:])): raise ValueError("targets overlap")
    gaps=[]
    for i,t in enumerate(ordered):
        end=t["range"][1]; nxt=ordered[i+1]["range"][0] if i+1<len(ordered) else TABLE_START
        raw=rom[end:nxt]
        if not raw or any(raw): raise ValueError("alternate dialogue structural zero gap changed")
        gaps.append({"id":i,"range":[end,nxt],"size":len(raw),"sha256":sha(raw)})
    bundle=b"".join(rom[t["range"][0]:t["range"][1]] for t in ordered)
    if len(bundle)!=1214 or sum(g["size"] for g in gaps)!=1586: raise ValueError("alternate dialogue byte denominator changed")
    claims=[{"id":"alternate-dialogue-table","primary_class":"alternate_dialogue_record_table","claim_kind":"alternate_dialogue_record_table_bytes","range":[TABLE_START,TABLE_END],"bytes_sha256":sha(table)}]
    claims += [{"id":f"alternate-dialogue-text-{i:02d}","primary_class":"dialogue_encoded_text","claim_kind":"alternate_dialogue_renderer_consumed_record_bytes","range":t["range"],"bytes_sha256":t["sha256"]} for i,t in enumerate(ordered)]
    claims += [{"id":f"alternate-dialogue-gap-{i:02d}","primary_class":"dialogue_inter_record_zero_padding","claim_kind":"alternate_dialogue_parser_bound_zero_padding_bytes","range":g["range"],"bytes_sha256":g["sha256"]} for i,g in enumerate(gaps)]
    historical={"path":str(COVERAGE),"sha256":COVERAGE_SHA,"observed_during_this_build":False,"live_projection_verified":False,"projection_gate":"deferred_to_coverage_auditor"}
    owner_gate={"status":"deferred_to_coverage_auditor","required_points":[
        {"address":0x8F9F0,"primary_class":"consumer_code_slice","claim_id":"verified-reuse-wram-overview-entry-08f9e2"},
        {"address":0x914D8,"primary_class":"armv4t_cfg_proven_roots_v18_reachable_thumb_code","claim_id":"cfg-v18-reachable_thumb_code-09-0914d8"},
        {"address":0x918EC,"primary_class":"armv4t_cfg_proven_roots_v17_consumed_literal_word","claim_id":"cfg-v17-consumed_literal_words-01-091848"},
        {"address":0x91E52,"primary_class":"armv4t_cfg_proven_roots_v17_reachable_thumb_code","claim_id":"cfg-v17-reachable_thumb_code-10-091d88"},
        {"address":0x91F82,"primary_class":"armv4t_cfg_proven_roots_v17_reachable_thumb_code","claim_id":"cfg-v17-reachable_thumb_code-13-091f3c"},
    ]}
    payload={"schema":SCHEMA,"rom":{"path":str(ROM),"sha256":ROM_SHA,"size":len(rom)},"historical_coverage_reference":historical,"upstream_owner_gate":owner_gate,"implementation":_implementation(root),"consumer":consumer,"table":{"range":[TABLE_START,TABLE_END],"row_count":20,"row_size":20,"sha256":sha(table)},"targets":ordered,"gaps":gaps,"summary":{"row_count":20,"target_count":80,"gap_count":80,"table_bytes":400,"text_bytes":1214,"gap_bytes":1586,"promoted_bytes":3200},"promotion":{"promotion_bytes":3200,"claims":claims},"limitations":LIMITATIONS}
    payload_raw=(json.dumps(payload,indent=2,sort_keys=True)+"\n").encode()
    manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"accepted","files":{PAYLOAD:sha(payload_raw),BUNDLE:sha(bundle)},"producer":{"command":["python3","tools/export_rom_alternate_dialogue_table.py","--root",".","--output-dir",f"artifacts/{SCHEMA}"],**payload["implementation"]},"rom_sha256":ROM_SHA,"historical_coverage_reference":payload["historical_coverage_reference"],"limitations":LIMITATIONS}
    return payload,{PAYLOAD:payload_raw,BUNDLE:bundle,"manifest.json":(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode()}

def _reject_path(root:Path,out:Path)->Path:
    lexical=out if out.is_absolute() else root/out
    if lexical.is_symlink(): raise ValueError("output path uses symlink")
    resolved=lexical.resolve(strict=False)
    if not resolved.is_relative_to(root) or resolved==root: raise ValueError("output path escapes repository")
    if resolved.exists(): raise FileExistsError("exclusive publication refuses existing output")
    return resolved
def _publish_exclusive(src:Path,dst:Path):
    libc=ctypes.CDLL(None,use_errno=True)
    fn=libc.renameatx_np; fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]; fn.restype=ctypes.c_int
    if fn(-2,os.fsencode(src),-2,os.fsencode(dst),4)!=0: raise OSError(ctypes.get_errno(),"atomic exclusive rename failed")
def export(root:Path,out:Path):
    root=root.resolve(strict=True); out=_reject_path(root,out); payload,files=build(root); out.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix=f".{out.name}.tmp-",dir=out.parent))
    try:
        for n,data in files.items():
            p=temp/n
            with p.open("xb") as f:f.write(data);f.flush();os.fsync(f.fileno())
        fd=os.open(temp,os.O_RDONLY);os.fsync(fd);os.close(fd);_publish_exclusive(temp,out)
        fd=os.open(out.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
    finally:
        if temp.exists():shutil.rmtree(temp)
    return payload
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path.cwd());ap.add_argument("--output-dir",type=Path,default=Path(f"artifacts/{SCHEMA}"));a=ap.parse_args()
    try:p=export(a.root,a.output_dir);print(json.dumps(p["summary"],sort_keys=True));return 0
    except Exception as e:print(str(e),file=__import__("sys").stderr);return 1
if __name__=="__main__":raise SystemExit(main())
