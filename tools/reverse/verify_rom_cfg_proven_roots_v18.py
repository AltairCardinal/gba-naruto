#!/usr/bin/env python3
"""Independently rebuild raw denominators for CFG proven-roots v18."""

from __future__ import annotations

import argparse, bisect, gzip, hashlib, json, struct, sys
from pathlib import Path
from typing import Any

PROJECT_ROOT=Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT,PROJECT_ROOT/"tools/_vendor"):
    if str(_path) not in sys.path: sys.path.insert(0,str(_path))
from tools.export_rom_cfg_inventory import _build_blocks,_frontier_records
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks
from tools.export_rom_cfg_proven_roots_v2 import _traverse_delta
from tools.export_rom_cfg_proven_roots_v4 import _load_payload
from tools.export_rom_cfg_proven_roots_v7 import _baselines
from tools.rom_cfg_proven_roots_v18_contract import *
from tools.thumb_branch import decode_thumb_b,decode_thumb_bl

def _sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def _canonical(x:object)->bytes:return (json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
def _vsha(x:object)->str:return _sha((json.dumps(x,sort_keys=True,separators=(",",":"))+"\n").encode())
def _safe(root:Path,relative:Path)->Path:
    root=root.resolve(strict=True);path=root/relative;resolved=path.resolve(strict=True)
    if not resolved.is_relative_to(root) or path.is_symlink():raise ValueError("unsafe input")
    return resolved
def _load_baseline(root):
    mr=_safe(root,PRECOVERAGE_DIR/MANIFEST_NAME).read_bytes();ar=_safe(root,PRECOVERAGE_DIR/"rom-byte-coverage.json.gz").read_bytes()
    if _sha(mr)!=PRECOVERAGE_MANIFEST_SHA256 or _sha(ar)!=PRECOVERAGE_ARCHIVE_SHA256:raise ValueError("precoverage identity changed")
    raw=gzip.decompress(ar)
    if len(raw)!=PRECOVERAGE_RAW_SIZE or _sha(raw)!=PRECOVERAGE_RAW_SHA256:raise ValueError("precoverage payload changed")
    record=json.loads(mr).get("files",{}).get("rom-byte-coverage.json.gz")
    if record!={"compression":"gzip","sha256":PRECOVERAGE_ARCHIVE_SHA256,"size":len(ar),"uncompressed_sha256":PRECOVERAGE_RAW_SHA256,"uncompressed_size":PRECOVERAGE_RAW_SIZE}:raise ValueError("precoverage manifest changed")
    cov=json.loads(raw);summary=cov.get("summary",{})
    if any(summary.get(k)!=v for k,v in BASELINE.items()):raise ValueError("precoverage summary changed")
    seg=cov.get("segments");starts=[];cursor=0
    if not isinstance(seg,list) or len(seg)!=BASELINE["segment_count"]:raise ValueError("segment denominator changed")
    for row in seg:
        if row.get("range",[None])[0]!=cursor or row["range"][1]<=cursor:raise ValueError("segment order changed")
        starts.append(cursor);cursor=row["range"][1]
    if cursor!=ROM_SIZE:raise ValueError("segment accounting changed")
    return {"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE},seg,starts
def _segment(seg,starts,off):
    row=seg[bisect.bisect_right(starts,off)-1]
    if not row["range"][0]<=off<row["range"][1]:raise ValueError("coverage lookup failed")
    return row
def _target(rom,off):
    h=struct.unpack_from("<H",rom,off)[0]
    if off+4<=len(rom):
        t=decode_thumb_bl(off,h,struct.unpack_from("<H",rom,off+2)[0])
        if t is not None:return "bl",t
    t=decode_thumb_b(off,h)
    if t is not None:return "b",t
    if h&0xF000==0xD000 and ((h>>8)&15)<14:
        d=(h&255)<<1
        if d&0x100:d-=0x200
        return "bcond",off+4+d
def _merge(rows):
    out=[]
    for a,b in sorted(rows):
        if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out
def _implementation(root):return {"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},**{f"{k}_sha256":_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}

def _raw(root,rom,segments,starts):
    by={r:[] for r in ROOTS}
    for off in range(0,len(rom)-1,2):
        branch=_target(rom,off)
        if branch and branch[1] in by:by[branch[1]].append((off,branch[1],branch[0]))
    matches=[x for r in ROOTS for x in by[r]]
    if tuple((a,b) for a,b,_ in matches)!=PRODUCERS or _sha(b"".join(rom[a:a+(4 if k=='bl' else 2)] for a,_,k in matches))!=PRODUCER_PACKED_SHA256:raise ValueError("raw producer denominator changed")
    producers=[]
    for off,target,kind in matches:
        owner=_segment(segments,starts,off)
        if owner.get("primary_class") in (None,"unknown") or not owner.get("primary_claim_ids"):raise ValueError("raw producer owner unproven")
        producers.append({"file_offset":off,"target_file_offset":target,"kind":kind,"raw_hex":rom[off:off+(4 if kind=='bl' else 2)].hex(),"coverage_owner_range":owner["range"],"coverage_owner_class":owner["primary_class"],"coverage_owner_claim_ids":owner["primary_claim_ids"],"accepted_as_root_proof":True})
    _,bn,bo,_=_baselines(root,rom);v7=_load_payload(root,V7_PAYLOAD_PATH,V7_PAYLOAD_SHA256);n7,o7=_nodes_from_blocks(rom,v7["extension"]["blocks"],label="proven_roots_v7");bn["proven_roots_v7"],bo["proven_roots_v7"]=n7,o7
    roots=[{"root_id":f"root-thumb-{r:06x}","mode":"thumb","file_offset":r,"gba_address":f"0x{ROM_BASE+r:08X}","entry_size":4,"entry_sha256":_sha(rom[r:r+4]),"sources":[{"file_offset":a} for a,b in PRODUCERS if b==r]} for r in ROOTS]
    if any(x["entry_sha256"]!=ROOT_ENTRY_SHA256 for x in roots):raise ValueError("root entry changed")
    nodes,rejected,incoming,crosses=_traverse_delta(rom,roots,bn);blocks,mapping=_build_blocks(rom,nodes,{("thumb",r) for r in ROOTS});frontiers=_frontier_records(nodes,rejected,incoming,roots,mapping)
    full={"instruction_count":len(nodes),"instruction_bytes":sum(n["size"] for n in nodes.values()),"basic_block_count":len(blocks),"decode_reject_count":len(rejected),"baseline_cross_edge_count":len(crosses),"frontier_count":len(frontiers)}
    if full!=FULL_METRICS:raise ValueError("raw full closure changed")
    lo,hi=TARGET_RANGE;local_nodes={k:n for k,n in nodes.items() if lo<=k[1]<hi};local_blocks=[b for b in blocks if lo<=b["range"][0]<hi];local_crosses=[x for x in crosses if lo<=x[0][1]<hi];local_frontiers=[[x["source"]["instruction_offset"],x["reason"]] for x in frontiers if lo<=x.get("source",{}).get("instruction_offset",-1)<hi]
    code=_merge([(off,off+n["size"]) for (_,off),n in local_nodes.items()])
    if tuple(map(tuple,code))!=CODE_RANGES or _vsha(code)!=CODE_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in code))!=CODE_PACKED_SHA256:raise ValueError("raw code projection changed")
    bindings=[]
    for (_,off),node in sorted(nodes.items()):
        if node["size"]==2:
            h=struct.unpack_from("<H",rom,off)[0]
            if h&0xF800==0x4800:
                t=((off+4)&~3)+(h&255)*4
                if lo<=t and t+4<=hi:bindings.append([off,t,rom[off:off+2].hex(),rom[t:t+4].hex()])
    targets=sorted({x[1] for x in bindings});literals=_merge([(t,t+4) for t in targets])
    if tuple(map(tuple,literals))!=LITERAL_RANGES or _vsha(literals)!=LITERAL_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in literals))!=LITERAL_PACKED_SHA256:raise ValueError("raw literal projection changed")
    local={"instruction_count":len(local_nodes),"instruction_bytes":sum(b-a for a,b in code),"basic_block_count":len(local_blocks),"baseline_call_edge_count":len(local_crosses),"frontiers":local_frontiers,"unique_literal_word_count":len(targets),"literal_reference_count":len(bindings),"literal_bytes":sum(b-a for a,b in literals),"literal_binding_vector_sha256":_vsha(bindings)}
    if any(local.get(k)!=v for k,v in LOCAL_METRICS.items()) or local_frontiers != [[0x0910CC,"indirect_pc_target"],[0x0914C8,"indirect_pc_target"]] or any(x[1]!="call_target" for x in local_crosses):raise ValueError("raw local boundary changed")
    union=_merge(code+literals)
    if _vsha(union)!=UNION_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in union))!=UNION_PACKED_SHA256:raise ValueError("raw union changed")
    return producers,full,local,code,literals,union

def _failure(error):return {"schema":VERIFY_SCHEMA,"verified":False,"errors":[str(error)],"promotion_bytes":0,"preserved_unknown_gap_count":len(GAPS)}
def verify_root(root:Path,artifact:Path,*,expected_receipt_path:Path|None=None)->dict[str,Any]:
    try:
        root=root.resolve(strict=True);artifact=(artifact if artifact.is_absolute() else root/artifact).absolute()
        if artifact.is_symlink() or not artifact.is_dir() or {p.name for p in artifact.iterdir()}!={PAYLOAD_NAME,MANIFEST_NAME}:raise ValueError("artifact file set changed")
        pr=(artifact/PAYLOAD_NAME).read_bytes();mr=(artifact/MANIFEST_NAME).read_bytes();payload=json.loads(pr);manifest=json.loads(mr)
        if _canonical(payload)!=pr or _canonical(manifest)!=mr:raise ValueError("noncanonical JSON")
        rom=_safe(root,ROM_PATH).read_bytes()
        if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256:raise ValueError("ROM identity changed")
        baseline,segments,starts=_load_baseline(root);producers,full,local,code,literals,union=_raw(root,rom,segments,starts)
        for a,b in code+literals:
            cursor=a
            while cursor<b:
                owner=_segment(segments,starts,cursor)
                if owner.get("primary_class")!="unknown":raise ValueError("promotion escaped unknown")
                cursor=min(b,owner["range"][1])
        claims=[{"id":f"cfg-v18-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,rows in (("reachable_thumb_code",code),("consumed_literal_words",literals)) for i,(a,b) in enumerate(rows,1)]
        promotion={"promotion_batch":SCHEMA,"primary_class":"armv4t_cfg_proven_roots_v18","claim_kind":"armv4t_cfg_proven_roots_v18_exact_bytes","target_range":list(TARGET_RANGE),"code_ranges":code,"literal_ranges":literals,"union_ranges":union,"preserved_unknown_gaps":[list(x) for x in GAPS],"code_bytes":1386,"literal_bytes":96,"promotion_bytes":1482,"preserved_unknown_bytes":8,"claims":claims}
        expected={"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"precoverage":baseline,"roots":[{"file_offset":r,"entry_sha256":ROOT_ENTRY_SHA256} for r in ROOTS],"accepted_producers":producers,"full_closure_denominator":full,"target_local_denominator":local,"promotion":promotion,"coverage_projection":{"baseline_unknown_bytes":BASELINE["unknown_bytes"],"promoted_bytes":1482,"remaining_unknown_bytes":BASELINE["unknown_bytes"]-1482},"implementation":_implementation(root),"scope":{"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"target_outside_subtree_classification":False,"natural_runtime_reachability":False,"alignment_gap_classification":False}}
        if payload!=expected:raise ValueError("payload differs from independent raw rebuild")
        if manifest.get("files",{}).get(PAYLOAD_NAME)!={"sha256":_sha(pr),"size":len(pr)} or any(manifest.get(k)!=payload.get(k) for k in ("rom","precoverage","implementation","promotion","coverage_projection","scope")):raise ValueError("manifest projection changed")
        receipt=expected_receipt_path.absolute() if expected_receipt_path is not None else artifact;rel=receipt.relative_to(root).as_posix();ep=["python3","-I","-S","tools/export_rom_cfg_proven_roots_v18.py","--root",".","--output",rel];ev=["python3","-I","-S","tools/verify_rom_cfg_proven_roots_v18.py","--root",".","--artifact",rel]
        if manifest.get("schema")!="git-artifact-promotion-v1" or manifest.get("artifact_schema")!=SCHEMA or manifest.get("producer",{}).get("command")!=ep or manifest.get("verifier",{}).get("command")!=ev:raise ValueError("manifest contract changed")
        status=manifest.get("artifact_status")
        if status=="candidate":
            if manifest["verifier"].get("exit_code") is not None or "report" in manifest["verifier"]:raise ValueError("candidate receipt changed")
        elif status=="accepted":
            report=manifest["verifier"].get("report",{})
            if manifest["verifier"].get("exit_code")!=0 or not report.get("verified") or report.get("promotion_bytes")!=1482:raise ValueError("accepted receipt changed")
        else:raise ValueError("artifact status changed")
        return {"schema":VERIFY_SCHEMA,"verified":True,"errors":[],"rom_sha256":ROM_SHA256,"precoverage_sha256":PRECOVERAGE_RAW_SHA256,"root_count":2,"accepted_producer_count":4,"instruction_count":617,"code_bytes":1386,"literal_word_count":24,"literal_bytes":96,"promotion_bytes":1482,"preserved_unknown_gap_count":4}
    except Exception as error:return _failure(error)
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--artifact",type=Path,required=True);a=p.parse_args();r=verify_root(a.root,a.artifact);print(json.dumps(r,sort_keys=True));return 0 if r["verified"] else 1
if __name__=="__main__":raise SystemExit(main())
