#!/usr/bin/env python3
"""Export the dependency-gated CFG proven-roots v20 packet."""

from __future__ import annotations
import argparse, bisect, gzip, hashlib, heapq, json, shutil, struct, sys, tempfile
from pathlib import Path

PROJECT_ROOT=Path(__file__).resolve().parents[1]
for p in (PROJECT_ROOT,PROJECT_ROOT/"tools/_vendor"):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.rom_cfg_proven_roots_v20_contract import *
from tools.thumb_branch import decode_thumb_b,decode_thumb_bl
from tools.verify_rom_boot_interwork_continuation import _decode_thumb,_decoder_identity

def _sha(raw): return hashlib.sha256(raw).hexdigest()
def _canonical(v): return (json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
def _safe(root,rel):
    root=root.resolve(strict=True); lexical=root/rel
    for parent in (lexical,*lexical.parents):
        if parent==root.parent: break
        if parent.is_symlink(): raise ValueError(f"unsafe symlink input: {rel}")
    out=lexical.resolve(strict=True)
    if not out.is_relative_to(root): raise ValueError(f"unsafe input: {rel}")
    return out
def _merge(rows):
    out=[]
    for a,b in sorted(rows):
        if out and a<=out[-1][1]: out[-1][1]=max(out[-1][1],b)
        else: out.append([a,b])
    return out
def _segment(segments,starts,o): return segments[bisect.bisect_right(starts,o)-1]
def _baseline(root):
    mr=_safe(root,PRECOVERAGE_DIR/MANIFEST_NAME).read_bytes(); ar=_safe(root,PRECOVERAGE_DIR/"rom-byte-coverage.json.gz").read_bytes()
    if (len(ar),_sha(mr),_sha(ar))!=(PRECOVERAGE_ARCHIVE_SIZE,PRECOVERAGE_MANIFEST_SHA256,PRECOVERAGE_ARCHIVE_SHA256): raise ValueError("immutable baseline identity changed")
    raw=gzip.decompress(ar)
    if (len(raw),_sha(raw))!=(PRECOVERAGE_RAW_SIZE,PRECOVERAGE_RAW_SHA256): raise ValueError("immutable baseline payload changed")
    cov=json.loads(raw); summary=cov.get("summary",{})
    if any(summary.get(k)!=v for k,v in BASELINE.items()): raise ValueError("immutable baseline summary changed")
    seg=cov.get("segments",[]); starts=[r["range"][0] for r in seg]
    if len(seg)!=BASELINE["segment_count"] or not seg or seg[0]["range"][0]!=0 or seg[-1]["range"][1]!=ROM_SIZE or any(seg[i]["range"][1]!=seg[i+1]["range"][0] for i in range(len(seg)-1)): raise ValueError("baseline segments changed")
    return {"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE},seg,starts
def _dependencies(root):
    sm=_safe(root,STORY_ARTIFACT/MANIFEST_NAME).read_bytes(); sp=_safe(root,STORY_ARTIFACT/"rom-story-callback-dependency-closures.json").read_bytes()
    um=_safe(root,UPSTREAM_ARTIFACT/MANIFEST_NAME).read_bytes(); up=_safe(root,UPSTREAM_ARTIFACT/UPSTREAM_PAYLOAD_NAME).read_bytes()
    if (len(sm),_sha(sm),len(sp),_sha(sp))!=(STORY_MANIFEST_SIZE,STORY_MANIFEST_SHA256,STORY_PAYLOAD_SIZE,STORY_PAYLOAD_SHA256): raise ValueError("story overlay identity changed")
    if (len(um),_sha(um),len(up),_sha(up))!=(UPSTREAM_MANIFEST_SIZE,UPSTREAM_MANIFEST_SHA256,UPSTREAM_PAYLOAD_SIZE,UPSTREAM_PAYLOAD_SHA256): raise ValueError("upstream identity changed")
    from tools.verify_rom_story_callback_dependency_closures import verify_artifact
    from tools.verify_rom_boot_interwork_continuation import verify_root
    sr=verify_artifact(root,_safe(root,STORY_ARTIFACT)); ur=verify_root(root,_safe(root,UPSTREAM_ARTIFACT))
    if not sr.get("verified") or sr.get("promotion_bytes")!=1932 or not ur.get("verified"): raise ValueError("dependency verification failed")
    claim=next((x for x in json.loads(up)["promotion"]["claims"] if x["id"]==UPSTREAM_CODE_CLAIM_ID),None)
    if not claim or tuple(claim["range"])!=UPSTREAM_CODE_RANGE: raise ValueError("upstream claim changed")
    return ({"artifact":STORY_ARTIFACT.as_posix(),"manifest_sha256":STORY_MANIFEST_SHA256,"payload_sha256":STORY_PAYLOAD_SHA256,"verified":True,"claim_count":32,"promotion_bytes":1932},json.loads(sp)["promotion"]["claims"],{"artifact":UPSTREAM_ARTIFACT.as_posix(),"manifest_sha256":UPSTREAM_MANIFEST_SHA256,"payload_sha256":UPSTREAM_PAYLOAD_SHA256,"verified":True,"dependency_claim_id":UPSTREAM_CODE_CLAIM_ID,"dependency_code_range":list(UPSTREAM_CODE_RANGE)})
def _target(rom,o):
    h=struct.unpack_from("<H",rom,o)[0]
    if o+4<=len(rom):
        t=decode_thumb_bl(o,h,struct.unpack_from("<H",rom,o+2)[0])
        if t is not None:return "bl",t,4
    t=decode_thumb_b(o,h)
    if t is not None:return "b",t,2
    if h&0xf000==0xd000 and ((h>>8)&15)<14:
        d=(h&255)<<1; d=d-0x200 if d&0x100 else d
        return "bcond",o+4+d,2
def _producers(rom,segments,starts):
    matches=[]
    for o in range(0,len(rom)-1,2):
        x=_target(rom,o)
        if x and x[1]==ROOT: matches.append((o,ROOT,*x))
    if [[o,t,k,z,rom[o:o+z].hex()] for o,t,k,_,z in matches] != [list(x[:5]) for x in PRODUCERS]: raise ValueError("producer denominator changed")
    rows=[]
    for (o,t,k,_,z), frozen in zip(matches,PRODUCERS):
        owner=_segment(segments,starts,o); accepted=frozen[5]
        instruction_only=accepted and owner.get("primary_claim_ids")==[UPSTREAM_CODE_CLAIM_ID] and tuple(owner["range"])==UPSTREAM_CODE_RANGE
        if accepted!=instruction_only: 
            if accepted: raise ValueError("accepted producer owner changed")
        if not accepted and (owner.get("primary_class")!="consumer_code_slice" or tuple(owner["range"])!=(0x0612BC,0x0614E4)): raise ValueError("rejected producer owner changed")
        rows.append({"file_offset":o,"target_file_offset":t,"kind":k,"size":z,"raw_hex":rom[o:o+z].hex(),"coverage_owner_range":owner["range"],"coverage_owner_class":owner["primary_class"],"coverage_owner_claim_ids":owner.get("primary_claim_ids",[]),"instruction_only":instruction_only,"accepted_as_root_proof":accepted,"rejection_reason":None if accepted else "coverage_owner_not_instruction_only"})
    return rows
def _traversal(root,rom):
    _decoder_identity(root); engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);engine.detail=True;engine.skipdata=False
    inside=lambda o:any(a<=o<b for a,b in CODE_RANGES)
    pending=[ROOT]; seen={ROOT};nodes={};out=[];front=[]
    while pending:
        o=heapq.heappop(pending)
        if o in nodes:continue
        if o%2 or not inside(o): raise ValueError("traversal escaped frozen code")
        n=_decode_thumb(rom,o,engine);nodes[o]=n
        for f in n["frontiers"]:front.append([o,f["reason"],n["raw_hex"],n["op_str"]])
        for e in n["successors"]:
            t=e["file_offset"]
            if inside(t):
                if t not in seen:seen.add(t);heapq.heappush(pending,t)
            elif e["kind"]=="call_target":out.append([o,t])
            else:raise ValueError("unbound outbound edge")
    code=_merge((o,o+n["size"]) for o,n in nodes.items())
    pred={o:[] for o in nodes}
    for o,n in nodes.items():
        for e in n["successors"]:
            if e["file_offset"] in nodes:pred[e["file_offset"]].append(o)
    starts={ROOT}
    for o,inc in pred.items():
        if o==ROOT:continue
        if len(inc)!=1:starts.add(o);continue
        p=nodes[inc[0]]; internal=[e for e in p["successors"] if e["file_offset"] in nodes]
        if p["flow_kind"]!="linear" or len(internal)!=1 or internal[0]["file_offset"]!=o or inc[0]+p["size"]!=o:starts.add(o)
    block_for={};blocks=[]
    for start in sorted(starts):
        o=start;count=0
        while o in nodes and o not in block_for:
            n=nodes[o];block_for[o]=start;count+=1;internal=[e for e in n["successors"] if e["file_offset"] in nodes]
            if n["flow_kind"]!="linear" or len(internal)!=1:break
            t=internal[0]["file_offset"]
            if t in starts or t!=o+n["size"]:break
            o=t
        blocks.append([start,o+nodes[o]["size"],count])
    bindings=[]
    for o,n in sorted(nodes.items()):
        if n["size"]==2:
            h=struct.unpack_from("<H",rom,o)[0]
            if h&0xf800==0x4800:
                t=((o+4)&~3)+(h&255)*4;bindings.append([o,t,n["raw_hex"],rom[t:t+4].hex()])
    literals=_merge((x[1],x[1]+4) for x in bindings)
    metrics={"instruction_count":len(nodes),"instruction_bytes":sum(n["size"] for n in nodes.values()),"basic_block_count":len(blocks),"decode_reject_count":0,"baseline_call_edge_count":len(out),"frontier_count":len(front),"unique_literal_word_count":len({x[1] for x in bindings}),"literal_reference_count":len(bindings),"literal_bytes":sum(b-a for a,b in literals)}
    if tuple(map(tuple,code))!=CODE_RANGES or tuple(map(tuple,literals))!=LITERAL_RANGES or metrics!=METRICS or tuple(map(tuple,out))!=OPAQUE_CALLS or tuple((x[0],x[1],x[2],x[3]) for x in front)!=FRONTIERS: raise ValueError("CFG denominator changed")
    return {**metrics,"code_ranges":code,"literal_ranges":literals,"literal_bindings":bindings,"frontiers":[{"file_offset":o,"reason":r,"raw_hex":raw,"register":reg} for o,r,raw,reg in front],"opaque_calls":[{"source":a,"target":b} for a,b in out]},code,literals
def _implementation(root): return {"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},**{f"{k}_sha256":_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}
def build_payload(root,rom_override=None):
    root=Path(root).resolve(strict=True);rom=_safe(root,ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256:raise ValueError("base ROM identity changed")
    baseline,seg,starts=_baseline(root);story,story_claims,upstream=_dependencies(root);producers=_producers(rom,seg,starts);den,_,_=_traversal(root,rom)
    owners=[]
    for target,(a,b,cid) in OPAQUE_OWNERS.items():
        row=_segment(seg,starts,target)
        if tuple(row["range"])!=(a,b) or row.get("primary_claim_ids")!=[cid] or target<a or target>=b:raise ValueError("opaque owner changed")
        owners.append({"entry_file_offset":target,"coverage_owner_range":[a,b],"coverage_owner_claim_id":cid,"accepted":True})
    den["opaque_target_owners"]=owners
    promotion_ranges=UNKNOWN_CODE_RANGES+UNKNOWN_LITERAL_RANGES
    for a,b in promotion_ranges:
        o=a
        while o<b:
            row=_segment(seg,starts,o)
            if row.get("primary_class")!="unknown":raise ValueError("promotion escaped current unknown")
            o=min(b,row["range"][1])
    for claim in story_claims:
        a,b=claim["range"]
        if any(max(a,c)<min(b,d) for c,d in promotion_ranges):raise ValueError("story overlay overlaps v20")
    union=_merge(promotion_ranges)
    if len(union)!=10 or sum(b-a for a,b in union)!=1150:raise ValueError("promotion union changed")
    claims=[{"id":f"cfg-v20-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,ranges in (("reachable_thumb_code",UNKNOWN_CODE_RANGES),("consumed_literal_words",UNKNOWN_LITERAL_RANGES)) for i,(a,b) in enumerate(ranges,1)]
    promotion={"promotion_batch":SCHEMA,"primary_class":"armv4t_cfg_proven_roots_v20","claim_kind":"armv4t_cfg_proven_roots_v20_exact_bytes","code_ranges":[list(x) for x in UNKNOWN_CODE_RANGES],"literal_ranges":[list(x) for x in UNKNOWN_LITERAL_RANGES],"union_ranges":union,"code_bytes":1070,"literal_bytes":80,"promotion_bytes":1150,"claim_count":18,"claims":claims,"existing_owner_code_provenance_bytes":1796}
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"precoverage":baseline,"story_overlay":{**story,"overlap_bytes":0},"upstream_continuation_artifact":upstream,"root":{"file_offset":ROOT,"entry_sha256":ROOT_ENTRY_SHA256},"producer_denominator":{"scan_range":[0,ROM_SIZE],"stride":2,"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"match_count":2,"matches":producers},"accepted_producers":[x for x in producers if x["accepted_as_root_proof"]],"rejected_producers":[x for x in producers if not x["accepted_as_root_proof"]],"target_local_denominator":den,"promotion":promotion,"coverage_projection":{"baseline_unknown_bytes":93109,"story_overlay_promoted_bytes":1932,"unknown_after_story_overlay":91177,"v20_promoted_bytes":1150,"remaining_unknown_bytes":90027,"classified_bytes":6201429,"cumulative_promoted_bytes":3082},"implementation":_implementation(root),"scope":{"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"natural_runtime_reachability":False,"global_caller_or_code_exhaustiveness":False,"indirect_computed_or_ram_producers":False,"rejected_producer_validity":False,"frontier_target_or_structured_return":False,"existing_owner_reclassification":False,"literal_business_semantics":False,"holes_alignment_padding_or_free_space":False,"abi_or_compiler":False,"editing_writeback_relocation_or_gameplay":False}}
def export(root,output):
    root=Path(root).resolve(strict=True);lexical=(Path(output) if Path(output).is_absolute() else root/Path(output)).absolute();resolved=lexical.resolve(strict=False);allowed=(root/EXPERIMENT_OUTPUT_ROOT).resolve();official=(root/OFFICIAL_ARTIFACT).resolve(strict=False)
    if resolved!=lexical or not (resolved.is_relative_to(allowed) or resolved==official):raise ValueError("output outside v20 scope or uses symlink ancestor")
    if resolved.exists():raise ValueError("output already exists")
    payload=build_payload(root);raw=_canonical(payload);rel=resolved.relative_to(root).as_posix();from tools import verify_rom_cfg_proven_roots_v20 as verifier
    manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"candidate","rom":payload["rom"],"precoverage":payload["precoverage"],"story_overlay":payload["story_overlay"],"upstream_continuation_artifact":payload["upstream_continuation_artifact"],"implementation":payload["implementation"],"promotion":payload["promotion"],"coverage_projection":payload["coverage_projection"],"scope":payload["scope"],"producer":{"command":["python3","-I","-S","tools/export_rom_cfg_proven_roots_v20.py","--root",".","--output",rel]},"verifier":{"command":["python3","-I","-S","tools/verify_rom_cfg_proven_roots_v20.py","--root",".","--artifact",rel],"exit_code":None},"files":{PAYLOAD_NAME:{"sha256":_sha(raw),"size":len(raw)}}}
    resolved.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=resolved.parent,prefix=".v20-") as temp:
        stage=Path(temp)/resolved.name;stage.mkdir();(stage/PAYLOAD_NAME).write_bytes(raw);(stage/MANIFEST_NAME).write_bytes(_canonical(manifest));report=verifier.verify_root(root,stage,expected_receipt_path=resolved)
        if not report["verified"]:raise ValueError(report["errors"])
        manifest["artifact_status"]="accepted";manifest["verifier"].update({"exit_code":0,"report":report});(stage/MANIFEST_NAME).write_bytes(_canonical(manifest));stage.rename(resolved)
    return manifest
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();export(a.root,a.output);return 0
if __name__=="__main__":raise SystemExit(main())
