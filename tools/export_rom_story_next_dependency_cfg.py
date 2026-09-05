#!/usr/bin/env python3
"""Export the frozen story-next dependency CFG packet."""
from __future__ import annotations
import argparse,bisect,gzip,hashlib,heapq,json,struct,sys,tempfile
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
for p in (PROJECT_ROOT,PROJECT_ROOT/"tools/_vendor"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.rom_story_next_dependency_cfg_contract import *
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
def _baseline(root):
    mr=_safe(root,PRECOVERAGE_DIR/MANIFEST_NAME).read_bytes();ar=_safe(root,PRECOVERAGE_DIR/"rom-byte-coverage.json.gz").read_bytes()
    if (len(ar),_sha(mr),_sha(ar))!=(PRECOVERAGE_ARCHIVE_SIZE,PRECOVERAGE_MANIFEST_SHA256,PRECOVERAGE_ARCHIVE_SHA256):raise ValueError("precoverage identity")
    raw=gzip.decompress(ar)
    if (len(raw),_sha(raw))!=(PRECOVERAGE_RAW_SIZE,PRECOVERAGE_RAW_SHA256):raise ValueError("precoverage payload")
    cov=json.loads(raw);summary=cov["summary"]
    if any(summary.get(k)!=v for k,v in BASELINE.items()):raise ValueError("precoverage summary")
    seg=cov["segments"]
    if len(seg)!=BASELINE["segment_count"] or seg[0]["range"][0]!=0 or seg[-1]["range"][1]!=ROM_SIZE or any(seg[i]["range"][1]!=seg[i+1]["range"][0] for i in range(len(seg)-1)):raise ValueError("precoverage partition")
    return {"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE},seg,[x["range"][0] for x in seg]
def _owner(seg,starts,o):
    x=seg[bisect.bisect_right(starts,o)-1]
    if not x["range"][0]<=o<x["range"][1]:raise ValueError("owner lookup")
    return x
def _dependencies(root):
    sm=_safe(root,STORY_ARTIFACT/MANIFEST_NAME).read_bytes();sp=_safe(root,STORY_ARTIFACT/"rom-story-callback-dependency-closures.json").read_bytes();vm=_safe(root,V20_ARTIFACT/MANIFEST_NAME).read_bytes();vp=_safe(root,V20_ARTIFACT/"rom-cfg-proven-roots-v20.json").read_bytes()
    if (len(sm),_sha(sm),len(sp),_sha(sp))!=(STORY_MANIFEST_SIZE,STORY_MANIFEST_SHA256,STORY_PAYLOAD_SIZE,STORY_PAYLOAD_SHA256) or (len(vm),_sha(vm),len(vp),_sha(vp))!=(V20_MANIFEST_SIZE,V20_MANIFEST_SHA256,V20_PAYLOAD_SIZE,V20_PAYLOAD_SHA256):raise ValueError("overlay identity")
    from tools.verify_rom_story_callback_dependency_closures import verify_artifact
    from tools.verify_rom_cfg_proven_roots_v20 import verify_root
    sr=verify_artifact(root,_safe(root,STORY_ARTIFACT));vr=verify_root(root,_safe(root,V20_ARTIFACT))
    if not sr.get("verified") or sr.get("promotion_bytes")!=1932 or not vr.get("verified") or vr.get("promotion_bytes")!=1150:raise ValueError("overlay verification")
    return json.loads(sp),json.loads(vp)
def _cfg_inventory(root):
    mr=_safe(root,CFG_INVENTORY/MANIFEST_NAME).read_bytes();pr=_safe(root,CFG_INVENTORY/"rom-cfg-inventory.json").read_bytes();vr=_safe(root,Path("tools/verify_rom_cfg_inventory.py")).read_bytes()
    if (_sha(mr),_sha(pr),_sha(vr))!=(CFG_INVENTORY_MANIFEST_SHA256,CFG_INVENTORY_PAYLOAD_SHA256,CFG_INVENTORY_VERIFIER_SHA256):raise ValueError("CFG inventory identity")
    from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory
    report=verify_rom_cfg_inventory(root,_safe(root,CFG_INVENTORY))
    if not report.get("verified"):raise ValueError("CFG inventory verification")
    wanted=("block-thumb-065404","block-thumb-08cbf4","block-thumb-08cc18")
    matches=[b for ident in wanted for b in json.loads(pr)["blocks"] if b.get("id")==ident]
    if [b["id"] for b in matches]!=list(wanted):raise ValueError("CFG inventory block denominator")
    blocks=[{"id":b["id"],"range":b["range"],"instruction_count":b["instruction_count"],"bytes_sha256":b["bytes_sha256"]} for b in matches]
    expected=[{"id":"block-thumb-065404","range":[0x065404,0x0654A4],"instruction_count":79,"bytes_sha256":CFG_INVENTORY_BLOCK_BYTES_SHA256},{"id":"block-thumb-08cbf4","range":[0x08CBF4,0x08CC02],"instruction_count":6,"bytes_sha256":CFG_INVENTORY_INTERNAL_BF4_BYTES_SHA256},{"id":"block-thumb-08cc18","range":[0x08CC18,0x08CC26],"instruction_count":6,"bytes_sha256":CFG_INVENTORY_INTERNAL_BLOCK_BYTES_SHA256}]
    if blocks!=expected:raise ValueError("CFG inventory exact entries")
    return {"artifact":CFG_INVENTORY.as_posix(),"manifest_sha256":CFG_INVENTORY_MANIFEST_SHA256,"payload_sha256":CFG_INVENTORY_PAYLOAD_SHA256,"verifier_sha256":CFG_INVENTORY_VERIFIER_SHA256,"verified":True,"entry_blocks":blocks}
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
def _producers(rom,seg,starts):
    rows=[]
    for o in range(0,len(rom)-1,2):
        x=_direct(rom,o)
        if x and x[0]==ROOT:rows.append([o,x[0],x[1],x[2],rom[o:o+x[2]].hex()])
    if rows!=[list(x[:5]) for x in PRODUCERS]:raise ValueError("producer denominator")
    result=[]
    for row,f in zip(rows,PRODUCERS):
        o,t,k,z,raw=row;own=_owner(seg,starts,o);accepted=f[5]
        instruction_only=accepted and tuple(own["range"])==(0x08F8F4,0x08F974) and own.get("primary_claim_ids")==["story-callback-reachable_thumb_code-05-08f8f4"]
        if instruction_only!=accepted or (not accepted and own.get("primary_class")!="unknown"):raise ValueError("producer owner gate")
        result.append({"file_offset":o,"target_file_offset":t,"kind":k,"size":z,"raw_hex":raw,"coverage_owner_range":own["range"],"coverage_owner_class":own["primary_class"],"coverage_owner_claim_ids":own.get("primary_claim_ids",[]),"instruction_only":instruction_only,"accepted_as_root_proof":accepted,"rejection_reason":None if accepted else "shape_match_current_unknown"})
    return result
def _cfg(root,rom,seg,starts,cfg_inventory):
    _decoder_identity(root);e=Cs(CS_ARCH_ARM,CS_MODE_THUMB);e.detail=True;e.skipdata=False;inside=lambda o:any(a<=o<b for a,b in CODE_RANGES)
    q=[ROOT];scheduled={ROOT};nodes={};out=[];front=[]
    while q:
        o=heapq.heappop(q)
        if o in nodes:continue
        if o%2 or not inside(o):raise ValueError("worklist escape")
        n=_decode_thumb(rom,o,e);nodes[o]=n
        for f in n["frontiers"]:front.append((o,f["reason"],n["raw_hex"],n["op_str"]))
        for edge in n["successors"]:
            t=edge["file_offset"]
            if inside(t):
                if t not in scheduled:scheduled.add(t);heapq.heappush(q,t)
            elif edge["kind"]=="call_target":out.append((o,t))
            else:raise ValueError("unbound outbound")
    out.sort();code=_merge((o,o+n["size"]) for o,n in nodes.items());pred={o:[] for o in nodes}
    for o,n in nodes.items():
        for edge in n["successors"]:
            if edge["file_offset"] in nodes:pred[edge["file_offset"]].append(o)
    starts_b={ROOT}
    for o,inc in pred.items():
        if o==ROOT:continue
        if len(inc)!=1:starts_b.add(o);continue
        n=nodes[inc[0]];internal=[x for x in n["successors"] if x["file_offset"] in nodes]
        if n["flow_kind"]!="linear" or len(internal)!=1 or internal[0]["file_offset"]!=o or inc[0]+n["size"]!=o:starts_b.add(o)
    bindings=[]
    for o,n in sorted(nodes.items()):
        if n["size"]==2:
            h=struct.unpack_from("<H",rom,o)[0]
            if h&0xf800==0x4800:
                t=((o+4)&~3)+(h&255)*4;bindings.append([o,t,n["raw_hex"],rom[t:t+4].hex()])
    literals=_merge((x[1],x[1]+4) for x in bindings);metrics={"instruction_count":len(nodes),"instruction_bytes":sum(n["size"] for n in nodes.values()),"basic_block_count":len(starts_b),"decode_reject_count":0,"baseline_call_edge_count":len(out),"frontier_count":len(front),"unique_literal_word_count":len({x[1] for x in bindings}),"literal_reference_count":len(bindings),"literal_bytes":sum(b-a for a,b in literals)}
    if metrics!=METRICS or tuple(map(tuple,code))!=CODE_RANGES or tuple(map(tuple,literals))!=LITERAL_RANGES or tuple(out)!=OPAQUE_CALLS or tuple(front)!=FRONTIERS:raise ValueError("CFG denominator")
    owners=[]
    for source,target in out:
        own=_owner(seg,starts,target)
        if target in {0x065404,0x08CBF4,0x08CC18}:
            expected_source={0x065404:0x088F92,0x08CBF4:0x088552,0x08CC18:0x08862E}[target]
            block=next((b for b in cfg_inventory["entry_blocks"] if b["range"][0]==target),None)
            if source!=expected_source or block is None:raise ValueError("special CFG entry")
            owners.append({"source":source,"target":target,"owner_range":block["range"],"claim_id":block["id"],"owner_artifact":CFG_INVENTORY.as_posix()})
        else:
            a,b,cid=OPAQUE_OWNERS[target]
            if tuple(own["range"])!=(a,b) or own.get("primary_claim_ids")!=[cid] or own.get("primary_class")=="unknown":raise ValueError("opaque owner")
            owners.append({"source":source,"target":target,"owner_range":[a,b],"claim_id":cid,"owner_artifact":PRECOVERAGE_DIR.as_posix()})
    return {**metrics,"code_ranges":code,"literal_ranges":literals,"literal_bindings":bindings,"opaque_calls":[{"source":a,"target":b} for a,b in out],"opaque_call_owners":owners,"frontiers":[{"file_offset":o,"reason":r,"raw_hex":raw,"register":reg} for o,r,raw,reg in front]}
def _implementation(root):return {"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},**{f"{k}_sha256":_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}
def build_payload(root,rom_override=None):
    root=Path(root).resolve(strict=True);rom=_safe(root,ROM_PATH).read_bytes() if rom_override is None else rom_override
    if (len(rom),_sha(rom))!=(ROM_SIZE,ROM_SHA256):raise ValueError("ROM identity")
    baseline,seg,starts=_baseline(root);story,v20=_dependencies(root);inventory=_cfg_inventory(root);producers=_producers(rom,seg,starts);den=_cfg(root,rom,seg,starts,inventory)
    promotion_ranges=CODE_RANGES+LITERAL_RANGES
    for a,b in promotion_ranges+HOLES:
        o=a
        while o<b:
            own=_owner(seg,starts,o)
            if own.get("primary_class")!="unknown":raise ValueError("promotion/hole not current unknown")
            o=min(b,own["range"][1])
    for claims in (story["promotion"]["claims"],v20["promotion"]["claims"]):
        for c in claims:
            a,b=c["range"]
            if any(max(a,x)<min(b,y) for x,y in promotion_ranges):raise ValueError("overlay overlap")
    union=_merge(promotion_ranges)
    if len(union)!=7 or sum(b-a for a,b in union)!=854:raise ValueError("promotion union")
    claims=[{"id":f"story-next-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,rs in (("reachable_thumb_code",CODE_RANGES),("consumed_literal_words",LITERAL_RANGES)) for i,(a,b) in enumerate(rs,1)]
    promotion={"promotion_batch":SCHEMA,"primary_class":"armv4t_story_next_dependency_cfg","claim_kind":"armv4t_story_next_dependency_cfg_exact_bytes","code_ranges":[list(x) for x in CODE_RANGES],"literal_ranges":[list(x) for x in LITERAL_RANGES],"union_ranges":union,"preserved_unknown_holes":[list(x) for x in HOLES],"code_bytes":770,"literal_bytes":84,"promotion_bytes":854,"claim_count":19,"claims":claims}
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"precoverage":baseline,"story_overlay":{"artifact":STORY_ARTIFACT.as_posix(),"manifest_sha256":STORY_MANIFEST_SHA256,"payload_sha256":STORY_PAYLOAD_SHA256,"verified":True,"claim_count":32,"promotion_bytes":1932,"overlap_bytes":0},"v20_overlay":{"artifact":V20_ARTIFACT.as_posix(),"manifest_sha256":V20_MANIFEST_SHA256,"payload_sha256":V20_PAYLOAD_SHA256,"verified":True,"claim_count":18,"promotion_bytes":1150,"overlap_bytes":0},"cfg_inventory":inventory,"root":{"file_offset":ROOT,"entry_sha256":ROOT_ENTRY_SHA256},"producer_denominator":{"scan_range":[0,ROM_SIZE],"stride":2,"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"match_count":2,"matches":producers},"accepted_producers":[x for x in producers if x["accepted_as_root_proof"]],"rejected_producers":[x for x in producers if not x["accepted_as_root_proof"]],"target_local_denominator":den,"promotion":promotion,"coverage_projection":{"baseline_unknown_bytes":93109,"story_overlay_promoted_bytes":1932,"v20_overlay_promoted_bytes":1150,"target_promoted_bytes":854,"cumulative_promoted_bytes":3936,"classified_bytes":6202283,"remaining_unknown_bytes":89173},"implementation":_implementation(root),"scope":{"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"natural_runtime_reachability":False,"global_caller_code_or_indirect_exhaustiveness":False,"computed_or_ram_producers":False,"rejected_producer_validity":False,"frontier_targets_or_structured_returns":False,"existing_owner_reclassification":False,"literal_business_semantics":False,"holes_alignment_padding_or_free_space":False,"abi_or_compiler":False,"editing_writeback_relocation_or_gameplay":False}}
def export(root,output):
    root=Path(root).resolve(strict=True);lex=(Path(output) if Path(output).is_absolute() else root/Path(output)).absolute();out=lex.resolve(strict=False);allowed=(root/EXPERIMENT_OUTPUT_ROOT).resolve();official=(root/OFFICIAL_ARTIFACT).resolve(strict=False)
    if out!=lex or not (out.is_relative_to(allowed) or out==official):raise ValueError("unsafe output")
    if out.exists():raise ValueError("output already exists")
    payload=build_payload(root);raw=_canonical(payload);rel=out.relative_to(root).as_posix();from tools import verify_rom_story_next_dependency_cfg as verifier
    manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"candidate","rom":payload["rom"],"precoverage":payload["precoverage"],"story_overlay":payload["story_overlay"],"v20_overlay":payload["v20_overlay"],"cfg_inventory":payload["cfg_inventory"],"implementation":payload["implementation"],"promotion":payload["promotion"],"coverage_projection":payload["coverage_projection"],"scope":payload["scope"],"producer":{"command":["python3","-I","-S","tools/export_rom_story_next_dependency_cfg.py","--root",".","--output",rel]},"verifier":{"command":["python3","-I","-S","tools/verify_rom_story_next_dependency_cfg.py","--root",".","--artifact",rel],"exit_code":None},"files":{PAYLOAD_NAME:{"sha256":_sha(raw),"size":len(raw)}}}
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent,prefix=".story-next-") as d:
        stage=Path(d)/out.name;stage.mkdir();(stage/PAYLOAD_NAME).write_bytes(raw);(stage/MANIFEST_NAME).write_bytes(_canonical(manifest));report=verifier.verify_root(root,stage,expected_receipt_path=out)
        if not report["verified"]:raise ValueError(report["errors"])
        manifest["artifact_status"]="accepted";manifest["verifier"].update({"exit_code":0,"report":report});(stage/MANIFEST_NAME).write_bytes(_canonical(manifest));stage.rename(out)
    return manifest
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();export(a.root,a.output);return 0
if __name__=="__main__":raise SystemExit(main())
