#!/usr/bin/env python3
"""Independently raw-decode and verify CFG proven-roots v20."""

from __future__ import annotations
import argparse,bisect,gzip,hashlib,heapq,json,struct,sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
for p in (PROJECT_ROOT,PROJECT_ROOT/"tools/_vendor"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.rom_cfg_proven_roots_v20_contract import *
from tools.thumb_branch import decode_thumb_b,decode_thumb_bl
from tools.verify_rom_boot_interwork_continuation import _decode_thumb,_decoder_identity

def _sha(b):return hashlib.sha256(b).hexdigest()
def _canonical(v):return (json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
def _safe(root,rel):
    root=root.resolve(strict=True);p=root/rel
    for x in (p,*p.parents):
        if x==root.parent:break
        if x.is_symlink():raise ValueError("symlink input")
    p=p.resolve(strict=True)
    if not p.is_relative_to(root):raise ValueError("input escape")
    return p
def _merge(rows):
    out=[]
    for a,b in sorted(rows):
        if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out
def _raw_baseline(root):
    mr=_safe(root,PRECOVERAGE_DIR/MANIFEST_NAME).read_bytes();ar=_safe(root,PRECOVERAGE_DIR/"rom-byte-coverage.json.gz").read_bytes()
    if (len(ar),_sha(mr),_sha(ar))!=(PRECOVERAGE_ARCHIVE_SIZE,PRECOVERAGE_MANIFEST_SHA256,PRECOVERAGE_ARCHIVE_SHA256):raise ValueError("baseline identity")
    raw=gzip.decompress(ar)
    if (len(raw),_sha(raw))!=(PRECOVERAGE_RAW_SIZE,PRECOVERAGE_RAW_SHA256):raise ValueError("baseline payload")
    cov=json.loads(raw);s=cov["summary"]
    if any(s.get(k)!=v for k,v in BASELINE.items()):raise ValueError("baseline summary")
    seg=cov["segments"]
    if len(seg)!=BASELINE["segment_count"] or seg[0]["range"][0]!=0 or seg[-1]["range"][1]!=ROM_SIZE or any(seg[i]["range"][1]!=seg[i+1]["range"][0] for i in range(len(seg)-1)):raise ValueError("baseline partition")
    return seg,[x["range"][0] for x in seg]
def _owner(seg,starts,o):
    x=seg[bisect.bisect_right(starts,o)-1]
    if not x["range"][0]<=o<x["range"][1]:raise ValueError("owner lookup")
    return x
def _direct(rom,o):
    h=struct.unpack_from("<H",rom,o)[0]
    if o+4<=len(rom):
        t=decode_thumb_bl(o,h,struct.unpack_from("<H",rom,o+2)[0])
        if t is not None:return t,"bl",4
    t=decode_thumb_b(o,h)
    if t is not None:return t,"b",2
    if h&0xf000==0xd000 and ((h>>8)&15)<14:
        d=(h&255)<<1;d=d-0x200 if d&0x100 else d
        return o+4+d,"bcond",2
def _raw_producers(rom,seg,starts):
    rows=[]
    for o in range(0,len(rom)-1,2):
        x=_direct(rom,o)
        if x and x[0]==ROOT:rows.append([o,x[0],x[1],x[2],rom[o:o+x[2]].hex()])
    if rows!=[list(x[:5]) for x in PRODUCERS]:raise ValueError("raw producer denominator")
    accepted=[];rejected=[]
    for row,frozen in zip(rows,PRODUCERS):
        o,t,k,z,raw=row;own=_owner(seg,starts,o);ok=frozen[5]
        instruction_only=(own.get("primary_claim_ids")==[UPSTREAM_CODE_CLAIM_ID] and tuple(own["range"])==UPSTREAM_CODE_RANGE)
        if ok!=instruction_only or (not ok and (own.get("primary_class")!="consumer_code_slice" or tuple(own["range"])!=(0x0612BC,0x0614E4))):raise ValueError("producer owner")
        item={"file_offset":o,"target_file_offset":t,"kind":k,"size":z,"raw_hex":raw,"coverage_owner_range":own["range"],"coverage_owner_class":own["primary_class"],"coverage_owner_claim_ids":own.get("primary_claim_ids",[]),"instruction_only":instruction_only,"accepted_as_root_proof":ok,"rejection_reason":None if ok else "coverage_owner_not_instruction_only"}
        (accepted if ok else rejected).append(item)
    return accepted,rejected
def _raw_cfg(root,rom):
    _decoder_identity(root);e=Cs(CS_ARCH_ARM,CS_MODE_THUMB);e.detail=True;e.skipdata=False;inside=lambda o:any(a<=o<b for a,b in CODE_RANGES)
    q=[ROOT];scheduled={ROOT};nodes={};out=[];front=[]
    while q:
        o=heapq.heappop(q)
        if o in nodes:continue
        if o%2 or not inside(o):raise ValueError("raw worklist escape")
        n=_decode_thumb(rom,o,e);nodes[o]=n
        for f in n["frontiers"]:front.append((o,f["reason"],n["raw_hex"],n["op_str"]))
        for edge in n["successors"]:
            t=edge["file_offset"]
            if inside(t):
                if t not in scheduled:scheduled.add(t);heapq.heappush(q,t)
            elif edge["kind"]=="call_target":out.append((o,t))
            else:raise ValueError("raw outbound")
    code=_merge((o,o+n["size"]) for o,n in nodes.items());pred={o:[] for o in nodes}
    for o,n in nodes.items():
        for edge in n["successors"]:
            if edge["file_offset"] in nodes:pred[edge["file_offset"]].append(o)
    starts={ROOT}
    for o,inc in pred.items():
        if o==ROOT:continue
        if len(inc)!=1:starts.add(o);continue
        n=nodes[inc[0]];internal=[x for x in n["successors"] if x["file_offset"] in nodes]
        if n["flow_kind"]!="linear" or len(internal)!=1 or internal[0]["file_offset"]!=o or inc[0]+n["size"]!=o:starts.add(o)
    claimed=set();blocks=0
    for start in sorted(starts):
        o=start
        while o in nodes and o not in claimed:
            n=nodes[o];claimed.add(o);internal=[x for x in n["successors"] if x["file_offset"] in nodes]
            if n["flow_kind"]!="linear" or len(internal)!=1:break
            t=internal[0]["file_offset"]
            if t in starts or t!=o+n["size"]:break
            o=t
        blocks+=1
    bindings=[]
    for o,n in sorted(nodes.items()):
        if n["size"]==2:
            h=struct.unpack_from("<H",rom,o)[0]
            if h&0xf800==0x4800:
                t=((o+4)&~3)+(h&255)*4;bindings.append([o,t,n["raw_hex"],rom[t:t+4].hex()])
    literals=_merge((x[1],x[1]+4) for x in bindings)
    metrics={"instruction_count":len(nodes),"instruction_bytes":sum(n["size"] for n in nodes.values()),"basic_block_count":blocks,"decode_reject_count":0,"baseline_call_edge_count":len(out),"frontier_count":len(front),"unique_literal_word_count":len({x[1] for x in bindings}),"literal_reference_count":len(bindings),"literal_bytes":sum(b-a for a,b in literals)}
    if metrics!=METRICS or tuple(map(tuple,code))!=CODE_RANGES or tuple(map(tuple,literals))!=LITERAL_RANGES or tuple(out)!=OPAQUE_CALLS or tuple(front)!=FRONTIERS:raise ValueError("raw CFG denominator")
    return metrics,code,literals,bindings,front,out
def _dependencies(root):
    sm=_safe(root,STORY_ARTIFACT/MANIFEST_NAME).read_bytes();sp=_safe(root,STORY_ARTIFACT/"rom-story-callback-dependency-closures.json").read_bytes();um=_safe(root,UPSTREAM_ARTIFACT/MANIFEST_NAME).read_bytes();up=_safe(root,UPSTREAM_ARTIFACT/UPSTREAM_PAYLOAD_NAME).read_bytes()
    if (len(sm),_sha(sm),len(sp),_sha(sp))!=(STORY_MANIFEST_SIZE,STORY_MANIFEST_SHA256,STORY_PAYLOAD_SIZE,STORY_PAYLOAD_SHA256) or (len(um),_sha(um),len(up),_sha(up))!=(UPSTREAM_MANIFEST_SIZE,UPSTREAM_MANIFEST_SHA256,UPSTREAM_PAYLOAD_SIZE,UPSTREAM_PAYLOAD_SHA256):raise ValueError("dependency identity")
    from tools.verify_rom_story_callback_dependency_closures import verify_artifact
    from tools.verify_rom_boot_interwork_continuation import verify_root as verify_upstream
    sr=verify_artifact(root,_safe(root,STORY_ARTIFACT));ur=verify_upstream(root,_safe(root,UPSTREAM_ARTIFACT))
    if not sr.get("verified") or sr.get("promotion_bytes")!=1932 or not ur.get("verified"):raise ValueError("dependency verifier")
    return json.loads(sp),json.loads(up)
def _failure(e):return {"schema":VERIFY_SCHEMA,"verified":False,"errors":[str(e)],"promotion_bytes":0}
def verify_root(root,artifact,*,expected_receipt_path=None):
    try:
        root=Path(root).resolve(strict=True);artifact=(Path(artifact) if Path(artifact).is_absolute() else root/Path(artifact)).absolute()
        if artifact.resolve(strict=False)!=artifact or artifact.is_symlink() or not artifact.is_dir() or {p.name for p in artifact.iterdir()}!={PAYLOAD_NAME,MANIFEST_NAME} or any(p.is_symlink() or not p.is_file() for p in artifact.iterdir()):raise ValueError("artifact file set")
        pr=(artifact/PAYLOAD_NAME).read_bytes();mr=(artifact/MANIFEST_NAME).read_bytes();payload=json.loads(pr);manifest=json.loads(mr)
        if pr!=_canonical(payload) or mr!=_canonical(manifest):raise ValueError("noncanonical JSON")
        rom=_safe(root,ROM_PATH).read_bytes()
        if (len(rom),_sha(rom))!=(ROM_SIZE,ROM_SHA256):raise ValueError("ROM identity")
        seg,starts=_raw_baseline(root);story_payload,upstream_payload=_dependencies(root);accepted,rejected=_raw_producers(rom,seg,starts);metrics,code,literals,bindings,front,out=_raw_cfg(root,rom)
        expected_keys={"schema","rom","precoverage","story_overlay","upstream_continuation_artifact","root","producer_denominator","accepted_producers","rejected_producers","target_local_denominator","promotion","coverage_projection","implementation","scope"}
        if set(payload)!=expected_keys or payload["schema"]!=SCHEMA or payload["root"]!={"file_offset":ROOT,"entry_sha256":ROOT_ENTRY_SHA256}:raise ValueError("payload root/schema")
        if payload["rom"]!={"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256}:raise ValueError("payload ROM")
        expected_precoverage={"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE}
        if payload["precoverage"]!=expected_precoverage:raise ValueError("payload precoverage")
        claim=next((x for x in upstream_payload.get("promotion",{}).get("claims",[]) if x.get("id")==UPSTREAM_CODE_CLAIM_ID),None)
        if claim is None or tuple(claim.get("range",()))!=UPSTREAM_CODE_RANGE:raise ValueError("upstream dependency claim")
        expected_upstream={"artifact":UPSTREAM_ARTIFACT.as_posix(),"manifest_sha256":UPSTREAM_MANIFEST_SHA256,"payload_sha256":UPSTREAM_PAYLOAD_SHA256,"verified":True,"dependency_claim_id":UPSTREAM_CODE_CLAIM_ID,"dependency_code_range":list(UPSTREAM_CODE_RANGE)}
        if payload["upstream_continuation_artifact"]!=expected_upstream:raise ValueError("payload upstream")
        if payload["accepted_producers"]!=accepted or payload["rejected_producers"]!=rejected or payload["producer_denominator"]["matches"]!=accepted+rejected or payload["producer_denominator"]["match_count"]!=2:raise ValueError("payload producers")
        if payload["producer_denominator"]!={"scan_range":[0,ROM_SIZE],"stride":2,"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"match_count":2,"matches":accepted+rejected}:raise ValueError("producer denominator payload")
        den=payload["target_local_denominator"]
        if any(den.get(k)!=v for k,v in metrics.items()) or den.get("code_ranges")!=code or den.get("literal_ranges")!=literals or den.get("literal_bindings")!=bindings or den.get("frontiers")!= [{"file_offset":o,"reason":r,"raw_hex":raw,"register":reg} for o,r,raw,reg in front] or den.get("opaque_calls")!= [{"source":a,"target":b} for a,b in out]:raise ValueError("payload CFG")
        expected_owners=[]
        for target,(a,b,cid) in OPAQUE_OWNERS.items():
            own=_owner(seg,starts,target)
            if tuple(own["range"])!=(a,b) or own.get("primary_claim_ids")!=[cid]:raise ValueError("opaque exact owner")
            expected_owners.append({"entry_file_offset":target,"coverage_owner_range":[a,b],"coverage_owner_claim_id":cid,"accepted":True})
        if den.get("opaque_target_owners")!=expected_owners:raise ValueError("opaque owner payload")
        if set(den)!={*metrics,"code_ranges","literal_ranges","literal_bindings","frontiers","opaque_calls","opaque_target_owners"}:raise ValueError("CFG payload keys")
        ranges=UNKNOWN_CODE_RANGES+UNKNOWN_LITERAL_RANGES
        for a,b in ranges:
            o=a
            while o<b:
                own=_owner(seg,starts,o)
                if own.get("primary_class")!="unknown":raise ValueError("not current unknown")
                o=min(b,own["range"][1])
        for claim in story_payload["promotion"]["claims"]:
            a,b=claim["range"]
            if any(max(a,c)<min(b,d) for c,d in ranges):raise ValueError("story overlap")
        union=_merge(ranges);claims=[{"id":f"cfg-v20-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,rs in (("reachable_thumb_code",UNKNOWN_CODE_RANGES),("consumed_literal_words",UNKNOWN_LITERAL_RANGES)) for i,(a,b) in enumerate(rs,1)]
        expected_promotion={"promotion_batch":SCHEMA,"primary_class":"armv4t_cfg_proven_roots_v20","claim_kind":"armv4t_cfg_proven_roots_v20_exact_bytes","code_ranges":[list(x) for x in UNKNOWN_CODE_RANGES],"literal_ranges":[list(x) for x in UNKNOWN_LITERAL_RANGES],"union_ranges":union,"code_bytes":1070,"literal_bytes":80,"promotion_bytes":1150,"claim_count":18,"claims":claims,"existing_owner_code_provenance_bytes":1796}
        if payload["promotion"]!=expected_promotion or len(union)!=10 or sum(b-a for a,b in union)!=1150:raise ValueError("promotion payload")
        if payload["story_overlay"]!={"artifact":STORY_ARTIFACT.as_posix(),"manifest_sha256":STORY_MANIFEST_SHA256,"payload_sha256":STORY_PAYLOAD_SHA256,"verified":True,"claim_count":32,"promotion_bytes":1932,"overlap_bytes":0}:raise ValueError("story overlay payload")
        projection={"baseline_unknown_bytes":93109,"story_overlay_promoted_bytes":1932,"unknown_after_story_overlay":91177,"v20_promoted_bytes":1150,"remaining_unknown_bytes":90027,"classified_bytes":6201429,"cumulative_promoted_bytes":3082}
        if payload["coverage_projection"]!=projection:raise ValueError("coverage projection")
        expected_implementation={"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},**{f"{k}_sha256":_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}
        if payload["implementation"]!=expected_implementation:raise ValueError("implementation binding")
        expected_scope={"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"natural_runtime_reachability":False,"global_caller_or_code_exhaustiveness":False,"indirect_computed_or_ram_producers":False,"rejected_producer_validity":False,"frontier_target_or_structured_return":False,"existing_owner_reclassification":False,"literal_business_semantics":False,"holes_alignment_padding_or_free_space":False,"abi_or_compiler":False,"editing_writeback_relocation_or_gameplay":False}
        if payload["scope"]!=expected_scope:raise ValueError("scope payload")
        for k in ("rom","precoverage","story_overlay","upstream_continuation_artifact","implementation","promotion","coverage_projection","scope"):
            if manifest.get(k)!=payload[k]:raise ValueError("manifest projection")
        if manifest.get("files",{}).get(PAYLOAD_NAME)!={"sha256":_sha(pr),"size":len(pr)}:raise ValueError("manifest file binding")
        receipt=Path(expected_receipt_path).absolute() if expected_receipt_path is not None else artifact;rel=receipt.relative_to(root).as_posix();ec=["python3","-I","-S","tools/export_rom_cfg_proven_roots_v20.py","--root",".","--output",rel];vc=["python3","-I","-S","tools/verify_rom_cfg_proven_roots_v20.py","--root",".","--artifact",rel]
        if manifest.get("schema")!="git-artifact-promotion-v1" or manifest.get("artifact_schema")!=SCHEMA or manifest.get("producer",{}).get("command")!=ec or manifest.get("verifier",{}).get("command")!=vc:raise ValueError("manifest command")
        success={"schema":VERIFY_SCHEMA,"verified":True,"errors":[],"rom_sha256":ROM_SHA256,"root_count":1,"producer_match_count":2,"accepted_producer_count":1,"rejected_producer_count":1,"instruction_count":1405,"basic_block_count":249,"code_bytes":2866,"literal_word_count":39,"literal_bytes":156,"opaque_call_count":17,"frontier_count":3,"story_overlay_bytes":1932,"story_overlap_bytes":0,"promotion_bytes":1150,"remaining_unknown_bytes":90027}
        status=manifest.get("artifact_status")
        if status=="candidate":
            if manifest["verifier"].get("exit_code") is not None or "report" in manifest["verifier"]:raise ValueError("candidate receipt")
        elif status=="accepted":
            if manifest["verifier"].get("exit_code")!=0 or manifest["verifier"].get("report")!=success:raise ValueError("accepted receipt")
        else:raise ValueError("artifact status")
        return success
    except Exception as e:return _failure(e)
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--artifact",type=Path,required=True);a=p.parse_args();r=verify_root(a.root,a.artifact);print(json.dumps(r,sort_keys=True));return 0 if r["verified"] else 1
if __name__=="__main__":raise SystemExit(main())
