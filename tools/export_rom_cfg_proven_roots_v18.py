#!/usr/bin/env python3
"""Export the target-local code/literal CFG proven-roots v18 packet."""

from __future__ import annotations

import argparse, bisect, gzip, hashlib, json, shutil, struct, sys, tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path: sys.path.insert(0, str(_path))

from tools.export_rom_cfg_inventory import _build_blocks, _frontier_records
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks
from tools.export_rom_cfg_proven_roots_v2 import _traverse_delta
from tools.export_rom_cfg_proven_roots_v4 import _load_payload
from tools.export_rom_cfg_proven_roots_v7 import _baselines
from tools.rom_cfg_proven_roots_v18_contract import *
from tools.thumb_branch import decode_thumb_b, decode_thumb_bl

def _sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def _canonical(value: object) -> bytes: return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
def _vsha(value: object) -> str: return _sha((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())

def _safe(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True); path = root / relative; resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or path.is_symlink(): raise ValueError(f"unsafe input path: {relative}")
    return resolved

def _baseline(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    mr = _safe(root, PRECOVERAGE_DIR / MANIFEST_NAME).read_bytes(); ar = _safe(root, PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()
    if _sha(mr) != PRECOVERAGE_MANIFEST_SHA256 or _sha(ar) != PRECOVERAGE_ARCHIVE_SHA256: raise ValueError("immutable precoverage identity changed")
    raw = gzip.decompress(ar)
    if len(raw) != PRECOVERAGE_RAW_SIZE or _sha(raw) != PRECOVERAGE_RAW_SHA256: raise ValueError("immutable precoverage payload changed")
    manifest = json.loads(mr); record = manifest.get("files", {}).get("rom-byte-coverage.json.gz")
    if record != {"compression":"gzip","sha256":PRECOVERAGE_ARCHIVE_SHA256,"size":len(ar),"uncompressed_sha256":PRECOVERAGE_RAW_SHA256,"uncompressed_size":PRECOVERAGE_RAW_SIZE}: raise ValueError("immutable precoverage manifest changed")
    coverage = json.loads(raw); summary = coverage.get("summary", {})
    if any(summary.get(k) != v for k, v in BASELINE.items()): raise ValueError("immutable precoverage summary changed")
    segments = coverage.get("segments"); starts=[]; cursor=0
    if not isinstance(segments, list) or len(segments) != BASELINE["segment_count"]: raise ValueError("precoverage segment denominator changed")
    for row in segments:
        interval=row.get("range")
        if not isinstance(interval,list) or len(interval)!=2 or interval[0]!=cursor or interval[1]<=cursor: raise ValueError("precoverage order changed")
        starts.append(cursor); cursor=interval[1]
    if cursor != ROM_SIZE: raise ValueError("precoverage accounting changed")
    return {"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE}, segments, starts

def _segment(segments: list[dict[str,Any]], starts: list[int], offset: int) -> dict[str,Any]:
    row=segments[bisect.bisect_right(starts,offset)-1]
    if not row["range"][0] <= offset < row["range"][1]: raise ValueError("coverage lookup failed")
    return row

def _direct_target(rom: bytes, offset: int) -> tuple[str,int] | None:
    half=struct.unpack_from("<H",rom,offset)[0]
    if offset+4<=len(rom):
        second=struct.unpack_from("<H",rom,offset+2)[0]; target=decode_thumb_bl(offset,half,second)
        if target is not None: return "bl",target
    target=decode_thumb_b(offset,half)
    if target is not None: return "b",target
    if half & 0xF000 == 0xD000 and ((half >> 8) & 15) < 14:
        disp=(half & 255)<<1
        if disp & 0x100: disp-=0x200
        return "bcond",offset+4+disp
    return None

def _producers(rom: bytes, segments: list[dict[str,Any]], starts: list[int]) -> list[dict[str,Any]]:
    by_root={root:[] for root in ROOTS}
    for offset in range(0,len(rom)-1,2):
        branch=_direct_target(rom,offset)
        if branch and branch[1] in by_root: by_root[branch[1]].append((offset,branch[1],branch[0]))
    matches=[row for root in ROOTS for row in by_root[root]]
    if tuple((a,b) for a,b,_ in matches) != PRODUCERS: raise ValueError("target-limited direct producer denominator changed")
    if _sha(b"".join(rom[a:a+(4 if k=='bl' else 2)] for a,_,k in matches)) != PRODUCER_PACKED_SHA256: raise ValueError("producer bytes changed")
    rows=[]
    for offset,target,kind in matches:
        owner=_segment(segments,starts,offset)
        if owner.get("primary_class") in (None,"unknown") or not owner.get("primary_claim_ids"): raise ValueError("producer is not already proven code")
        rows.append({"file_offset":offset,"target_file_offset":target,"kind":kind,"raw_hex":rom[offset:offset+(4 if kind=='bl' else 2)].hex(),"coverage_owner_range":owner["range"],"coverage_owner_class":owner["primary_class"],"coverage_owner_claim_ids":owner["primary_claim_ids"],"accepted_as_root_proof":True})
    return rows

def _merge(intervals):
    out=[]
    for start,end in sorted(intervals):
        if out and start<=out[-1][1]: out[-1][1]=max(out[-1][1],end)
        else: out.append([start,end])
    return out

def _traversal(root: Path, rom: bytes) -> tuple[dict[str,Any],dict[str,Any]]:
    _,baseline_nodes,baseline_owners,_=_baselines(root,rom)
    v7=_load_payload(root,V7_PAYLOAD_PATH,V7_PAYLOAD_SHA256); n7,o7=_nodes_from_blocks(rom,v7["extension"]["blocks"],label="proven_roots_v7")
    baseline_nodes["proven_roots_v7"],baseline_owners["proven_roots_v7"]=n7,o7
    roots=[{"root_id":f"root-thumb-{r:06x}","mode":"thumb","file_offset":r,"gba_address":f"0x{ROM_BASE+r:08X}","entry_size":4,"entry_sha256":_sha(rom[r:r+4]),"sources":[{"file_offset":a} for a,b in PRODUCERS if b==r]} for r in ROOTS]
    if any(row["entry_sha256"]!=ROOT_ENTRY_SHA256 for row in roots): raise ValueError("root entry changed")
    nodes,rejected,incoming,crosses=_traverse_delta(rom,roots,baseline_nodes); blocks,mapping=_build_blocks(rom,nodes,{("thumb",r) for r in ROOTS}); frontiers=_frontier_records(nodes,rejected,incoming,roots,mapping)
    full={"instruction_count":len(nodes),"instruction_bytes":sum(n["size"] for n in nodes.values()),"basic_block_count":len(blocks),"decode_reject_count":len(rejected),"baseline_cross_edge_count":len(crosses),"frontier_count":len(frontiers)}
    if full != FULL_METRICS: raise ValueError("full closure changed")
    lo,hi=TARGET_RANGE; local_nodes={k:n for k,n in nodes.items() if lo<=k[1]<hi}; local_blocks=[b for b in blocks if lo<=b["range"][0]<hi]; local_crosses=[x for x in crosses if lo<=x[0][1]<hi]
    local_frontiers=[[x["source"]["instruction_offset"],x["reason"]] for x in frontiers if lo<=x.get("source",{}).get("instruction_offset",-1)<hi]
    code=_merge([(off,off+n["size"]) for (_,off),n in local_nodes.items()])
    if tuple(map(tuple,code))!=CODE_RANGES or _vsha(code)!=CODE_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in code))!=CODE_PACKED_SHA256: raise ValueError("local code denominator changed")
    bindings=[]
    for (_,off),node in sorted(nodes.items()):
        if node["size"]==2:
            half=struct.unpack_from("<H",rom,off)[0]
            if half&0xF800==0x4800:
                target=((off+4)&~3)+(half&255)*4
                if lo<=target and target+4<=hi: bindings.append([off,target,rom[off:off+2].hex(),rom[target:target+4].hex()])
    targets=sorted({x[1] for x in bindings}); literals=_merge([(x,x+4) for x in targets])
    if tuple(map(tuple,literals))!=LITERAL_RANGES or _vsha(literals)!=LITERAL_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in literals))!=LITERAL_PACKED_SHA256: raise ValueError("local literal denominator changed")
    local={"instruction_count":len(local_nodes),"instruction_bytes":sum(b-a for a,b in code),"basic_block_count":len(local_blocks),"baseline_call_edge_count":len(local_crosses),"frontiers":local_frontiers,"unique_literal_word_count":len(targets),"literal_reference_count":len(bindings),"literal_bytes":sum(b-a for a,b in literals),"literal_binding_vector_sha256":_vsha(bindings)}
    if any(local.get(k)!=v for k,v in LOCAL_METRICS.items()) or local_frontiers != [[0x0910CC,"indirect_pc_target"],[0x0914C8,"indirect_pc_target"]] or any(x[1]!="call_target" for x in local_crosses): raise ValueError("local traversal boundary changed")
    return {"full":full,"local":local},{"code":code,"literals":literals}

def _implementation(root): return {"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},**{f"{k}_sha256":_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}

def build_payload(root: Path, rom_override: bytes|None=None) -> dict[str,Any]:
    root=root.resolve(strict=True); rom=_safe(root,ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256: raise ValueError("base ROM identity changed")
    baseline,segments,starts=_baseline(root); producers=_producers(rom,segments,starts); traversal,ranges=_traversal(root,rom)
    semantic=ranges["code"]+ranges["literals"]
    for start,end in semantic:
        cursor=start
        while cursor<end:
            owner=_segment(segments,starts,cursor)
            if owner.get("primary_class")!="unknown": raise ValueError("promotion escaped baseline unknown")
            cursor=min(end,owner["range"][1])
    union=_merge(semantic)
    if _vsha(union)!=UNION_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in union))!=UNION_PACKED_SHA256: raise ValueError("union denominator changed")
    claims=[{"id":f"cfg-v18-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,rows in (("reachable_thumb_code",ranges["code"]),("consumed_literal_words",ranges["literals"])) for i,(a,b) in enumerate(rows,1)]
    promotion={"promotion_batch":SCHEMA,"primary_class":"armv4t_cfg_proven_roots_v18","claim_kind":"armv4t_cfg_proven_roots_v18_exact_bytes","target_range":list(TARGET_RANGE),"code_ranges":ranges["code"],"literal_ranges":ranges["literals"],"union_ranges":union,"preserved_unknown_gaps":[list(x) for x in GAPS],"code_bytes":1386,"literal_bytes":96,"promotion_bytes":1482,"preserved_unknown_bytes":8,"claims":claims}
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"precoverage":baseline,"roots":[{"file_offset":r,"entry_sha256":ROOT_ENTRY_SHA256} for r in ROOTS],"accepted_producers":producers,"full_closure_denominator":traversal["full"],"target_local_denominator":traversal["local"],"promotion":promotion,"coverage_projection":{"baseline_unknown_bytes":BASELINE["unknown_bytes"],"promoted_bytes":1482,"remaining_unknown_bytes":BASELINE["unknown_bytes"]-1482},"implementation":_implementation(root),"scope":{"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"target_outside_subtree_classification":False,"natural_runtime_reachability":False,"alignment_gap_classification":False}}

def export(root:Path,output:Path)->dict[str,Any]:
    root=root.resolve(strict=True); output=(output if output.is_absolute() else root/output).absolute(); allowed=(root/EXPERIMENT_OUTPUT_ROOT).resolve(); official=(root/OFFICIAL_ARTIFACT).absolute()
    if not (output.is_relative_to(allowed) or output==official) or output.is_symlink(): raise ValueError("output outside v18 scope")
    payload=build_payload(root); raw=_canonical(payload); rel=output.relative_to(root).as_posix(); from tools import verify_rom_cfg_proven_roots_v18 as verifier
    manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"candidate","rom":payload["rom"],"precoverage":payload["precoverage"],"implementation":payload["implementation"],"promotion":payload["promotion"],"coverage_projection":payload["coverage_projection"],"scope":payload["scope"],"producer":{"command":["python3","-I","-S","tools/export_rom_cfg_proven_roots_v18.py","--root",".","--output",rel]},"verifier":{"command":["python3","-I","-S","tools/verify_rom_cfg_proven_roots_v18.py","--root",".","--artifact",rel],"exit_code":None},"files":{PAYLOAD_NAME:{"sha256":_sha(raw),"size":len(raw)}}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix=".v18-") as temp:
        stage=Path(temp)/output.name; stage.mkdir(); (stage/PAYLOAD_NAME).write_bytes(raw); (stage/MANIFEST_NAME).write_bytes(_canonical(manifest)); report=verifier.verify_root(root,stage,expected_receipt_path=output)
        if not report["verified"]: raise ValueError(report["errors"])
        manifest["artifact_status"]="accepted"; manifest["verifier"].update({"exit_code":0,"report":report}); (stage/MANIFEST_NAME).write_bytes(_canonical(manifest))
        if output.exists():
            if not output.is_dir() or any(output.iterdir()): raise ValueError("output must be absent or empty")
            output.rmdir()
        shutil.move(stage,output)
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();export(a.root,a.output);return 0
if __name__=="__main__": raise SystemExit(main())
