#!/usr/bin/env python3
"""Independently verify the frozen 0x078E38 task-callback closure artifact."""

from __future__ import annotations
import argparse,bisect,gzip,hashlib,heapq,json,os,stat,struct,sys
from pathlib import Path
from typing import Any
PROJECT_ROOT=Path(__file__).resolve().parents[1]
for _p in (PROJECT_ROOT,PROJECT_ROOT/"tools/_vendor"):
    if str(_p) not in sys.path:sys.path.insert(0,str(_p))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from capstone import arm_const
from tools import rom_task_callback_078e38_contract as C
from tools.thumb_branch import decode_thumb_b,decode_thumb_bl

def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _canonical(value):return (json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
def _packed(rom,ranges):return b"".join(rom[a:b] for a,b in ranges)
def _vsha(value):return _sha(json.dumps(value,sort_keys=True,separators=(",",":")).encode())
def _read_regular_at(directory_fd,name):
    flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(name,flags,dir_fd=directory_fd)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):raise ValueError(f"artifact member not regular: {name}")
        chunks=[]
        while True:
            chunk=os.read(fd,1024*1024)
            if not chunk:break
            chunks.append(chunk)
        after=os.fstat(fd);identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
        if identity(before)!=identity(after):raise ValueError(f"artifact member changed: {name}")
        return b"".join(chunks)
    finally:os.close(fd)

def _read_repo_file(root,rel):
    root=Path(root).resolve(strict=True);rel=Path(rel)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:raise ValueError("unsafe repository input")
    flags=os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0);fd=os.open(root,flags)
    try:
        for part in rel.parts[:-1]:
            child=os.open(part,flags,dir_fd=fd);os.close(fd);fd=child
        return _read_regular_at(fd,rel.parts[-1])
    finally:os.close(fd)

def _artifact_parts(root,artifact):
    value=Path(artifact)
    if ".." in value.parts:raise ValueError("unsafe artifact path")
    raw=value if value.is_absolute() else root/value
    absolute=Path(os.path.abspath(raw))
    try:return absolute,absolute.relative_to(root)
    except ValueError as exc:raise ValueError("unsafe artifact path") from exc

def _open_artifact(root,artifact):
    absolute,relative=_artifact_parts(root,artifact)
    flags=os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0);fd=os.open(root,flags)
    try:
        for part in relative.parts:
            child=os.open(part,flags,dir_fd=fd);os.close(fd);fd=child
        return absolute,fd
    except Exception:
        os.close(fd);raise

def _decode_node(rom,offset,engine):
    rows=tuple(engine.disasm(rom[offset:offset+4],0x08000000+offset,count=1))
    if len(rows)!=1:raise ValueError("raw closure decode")
    ins=rows[0];raw=rom[offset:offset+ins.size]
    if ins.size not in (2,4) or (ins.size==4 and ins.id!=arm_const.ARM_INS_BL):raise ValueError("raw closure instruction")
    h=int.from_bytes(raw[:2],"little");edges=[];front=[];target=None
    if ins.size==4:target=decode_thumb_bl(offset,h,int.from_bytes(raw[2:4],"little"));call=True;cond=False
    else:
        call=False;cond=h&0xf000==0xd000 and ((h>>8)&15)<14
        if cond:
            d=(h&255)<<1
            if d&0x100:d-=0x200
            target=offset+4+d
        else:target=decode_thumb_b(offset,h)
    if target is not None:
        edges.append(("call_target" if call else "branch_target",target))
        if call or cond:edges.append(("fallthrough",offset+ins.size))
        flow="call" if call else ("conditional_branch" if cond else "unconditional_branch")
    elif h&0xff87==0x4700:flow="indirect_branch";front=["indirect_pc_target"]
    elif ins.id==arm_const.ARM_INS_SVC:flow="supervisor_call";front=["bios_swi_external"];edges=[("fallthrough",offset+ins.size)]
    else:flow="linear";edges=[("fallthrough",offset+ins.size)]
    return {"offset":offset,"size":ins.size,"raw_hex":raw.hex(),"mnemonic":ins.mnemonic,"op_str":ins.op_str,"flow":flow,"edges":edges,"front":front}

def _merge(rows):
    out=[]
    for a,b in sorted(rows):
        if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out

def _rebuild_closure(rom):
    inside=lambda x:any(a<=x<b for a,b in C.CODE_RANGES)
    engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);engine.detail=True;engine.skipdata=False
    pending=[C.ROOT];nodes={};calls=[]
    while pending:
        offset=heapq.heappop(pending)
        if offset in nodes:continue
        if offset%2 or not inside(offset):raise ValueError("raw closure worklist escape")
        node=_decode_node(rom,offset,engine);nodes[offset]=node
        for kind,target in node["edges"]:
            if inside(target):heapq.heappush(pending,target)
            elif kind=="call_target":calls.append((offset,target))
            else:raise ValueError("raw closure outbound branch")
    frontiers=[{"source":o,"reason":reason} for o,n in sorted(nodes.items()) for reason in n["front"]]
    if tuple((row["source"],row["reason"]) for row in frontiers)!=tuple(
        (row["source"],row["reason"]) for row in C.FRONTIERS
    ):raise ValueError("raw closure frontier denominator")
    code=_merge((o,o+n["size"]) for o,n in nodes.items())
    pred={o:[] for o in nodes}
    for o,n in nodes.items():
        for _,t in n["edges"]:
            if t in nodes:pred[t].append(o)
    starts={C.ROOT}
    for o,incoming in pred.items():
        if o==C.ROOT:continue
        if len(incoming)!=1:starts.add(o);continue
        before=nodes[incoming[0]];internal=[t for _,t in before["edges"] if t in nodes]
        if before["flow"]!="linear" or internal!=[o] or incoming[0]+before["size"]!=o:starts.add(o)
    blocks=[]
    for start in sorted(starts):
        o=start
        while True:
            n=nodes[o];inside_edges=[t for _,t in n["edges"] if t in nodes];nxt=o+n["size"]
            if n["flow"]!="linear" or inside_edges!=[nxt] or nxt in starts:break
            o=nxt
        blocks.append([start,o+nodes[o]["size"]])
    bindings=[]
    for o,n in sorted(nodes.items()):
        h=int.from_bytes(rom[o:o+2],"little")
        if n["size"]==2 and h&0xf800==0x4800:
            target=((o+4)&~3)+(h&255)*4;bindings.append([o,target,rom[target:target+4].hex()])
    literals=_merge((t,t+4) for _,t,_ in bindings)
    metrics={"instruction_count":len(nodes),"basic_block_count":len(blocks),"code_bytes":sum(n["size"] for n in nodes.values()),"literal_reference_count":len(bindings),"unique_literal_word_count":len({x[1] for x in bindings}),"literal_bytes":sum(b-a for a,b in literals),"opaque_call_count":len(calls),"opaque_unique_target_count":len({x[1] for x in calls}),"structured_return_count":0,"frontier_count":len(frontiers)}
    if metrics!=C.METRICS or tuple(map(tuple,code))!=C.CODE_RANGES or tuple(map(tuple,literals))!=C.LITERAL_RANGES or tuple(map(tuple,blocks))!=C.BLOCK_RANGES or tuple(calls)!=C.OPAQUE_CALLS:raise ValueError("raw closure denominator")
    hashes={"code_bytes_sha256":_sha(_packed(rom,C.CODE_RANGES)),"literal_bytes_sha256":_sha(_packed(rom,C.LITERAL_RANGES)),"code_then_literal_sha256":_sha(_packed(rom,C.CODE_RANGES)+_packed(rom,C.LITERAL_RANGES)),"address_order_union_sha256":_sha(_packed(rom,sorted(C.CODE_RANGES+C.LITERAL_RANGES))),"holes_bytes_sha256":_sha(_packed(rom,C.HOLES))}
    if tuple(hashes.values())!=(C.CODE_PACKED_SHA256,C.LITERAL_PACKED_SHA256,C.CODE_THEN_LITERAL_SHA256,C.ADDRESS_ORDER_UNION_SHA256,C.HOLES_PACKED_SHA256) or _vsha(blocks)!=C.BLOCK_RANGE_VECTOR_SHA256:raise ValueError("raw closure identity")
    sp={o:n["raw_hex"] for o,n in nodes.items() if "sp" in n["op_str"] or n["mnemonic"] in ("push","pop")}
    if rom[slice(*C.EPILOGUE)].hex()!=C.EPILOGUE_RAW_HEX or _sha(rom[slice(*C.EPILOGUE)])!=C.EPILOGUE_SHA256 or sp!=C.STACK_SITES or nodes[0x079144]["raw_hex"]!="0047" or nodes[0x079144]["op_str"]!="r0":raise ValueError("return candidate observation")
    candidate={"epilogue_range":list(C.EPILOGUE),"epilogue_sha256":C.EPILOGUE_SHA256,
               "terminal_branch":{"source":0x079144,"raw_hex":"0047","register":"r0"},
               "observed_stack_site_count":len(sp),"opaque_callee_stack_effects_proven":False,
               "structured_return_proven":False}
    return {**metrics,**hashes,"code_ranges":code,"literal_ranges":literals,"holes":[list(x) for x in C.HOLES],"blocks":blocks,"literal_bindings":bindings,"opaque_calls":[{"source":a,"target":b} for a,b in calls],"frontiers":frontiers,"return_candidate":candidate}

def _direct(rom,o):
    h=struct.unpack_from("<H",rom,o)[0];t=decode_thumb_bl(o,h,struct.unpack_from("<H",rom,o+2)[0]) if o+4<=len(rom) else None
    if t is not None:return t,"thumb_bl",4
    if h&0xf000==0xd000 and ((h>>8)&15)<14:
        d=(h&255)<<1
        if d&0x100:d-=0x200
        return o+4+d,"thumb_bcond",2
    t=decode_thumb_b(o,h)
    if t is not None:return t,"thumb_b",2

def _scan_direct_matches(rom,entries,excluded_range):
    direct=[]
    for o in range(0,len(rom)-1,2):
        if excluded_range[0]<=o<excluded_range[1]:continue
        item=_direct(rom,o)
        if item and item[0] in entries:direct.append([o,*item])
    return direct

def _rebuild_lifecycle(rom):
    if (_sha(rom[slice(*C.SOURCE_RANGE)]),_sha(rom[slice(*C.ALLOCATOR_RANGE)]),_sha(rom[slice(*C.DISPATCHER_RANGE)]),_sha(rom[slice(*C.VENEER_RANGE)]))!=(C.SOURCE_SHA256,C.ALLOCATOR_SHA256,C.DISPATCHER_SHA256,C.VENEER_SHA256):raise ValueError("raw lifecycle identity")
    if rom[0x792be:0x792c2].hex()!="2e480490" or _direct(rom,0x792ca)!=(0x626b4,"thumb_bl",4) or rom[0x6272a:0x6272e].hex()!="05431560" or rom[0x6275e:0x62762].hex()!="0e989062" or _direct(rom,0x62954)!=(0x9c114,"thumb_bl",4) or rom[0x9c114:0x9c116].hex()!="0847":raise ValueError("raw lifecycle semantics")
    found=[];cursor=0
    while True:
        at=rom.find(C.POINTER_BYTES,cursor)
        if at<0:break
        found.append(at);cursor=at+1
    entries={a for a,_ in C.BLOCK_RANGES};direct=_scan_direct_matches(rom,entries,C.ENVELOPE)
    if tuple(found)!=C.POINTER_OCCURRENCES or direct:raise ValueError("raw lifecycle producer denominator")
    return {"callback_pointer":0x08078E39,"pointer_occurrences":found,"callback_stack_store":0x0792C0,"callback_stack_offset":0x10,"allocator_callsite":0x0792CA,"allocator_root":0x0626B4,"allocator_arg8_load":0x06275E,"allocator_callback_store":0x062760,"active_flag_store":0x06272C,"callback_field":0x28,"pool_base":0x03003BB8,"pool_records":128,"record_size":0x3C,"dispatcher_root":0x062940,"dispatcher_active_flag_test":0x062944,"dispatcher_callback_load":0x06294C,"dispatcher_task_argument":0x062952,"dispatcher_veneer_callsite":0x062954,"dispatch_veneer":0x09C114,"source_owner_verified":True,"allocator_owner_verified":True,"dispatcher_owner_verified":True,"field_contract_replayed":True,"whole_field_artifact_verifier_claimed":False}

def _rebuild_inputs(root,rom):
    manifest=_read_repo_file(root,C.PRECOVERAGE/C.MANIFEST_NAME);archive=_read_repo_file(root,C.PRECOVERAGE/"rom-byte-coverage.json.gz")
    if (len(manifest),_sha(manifest),len(archive),_sha(archive))!=(C.PRECOVERAGE_MANIFEST_SIZE,C.PRECOVERAGE_MANIFEST_SHA256,C.PRECOVERAGE_ARCHIVE_SIZE,C.PRECOVERAGE_ARCHIVE_SHA256):raise ValueError("precoverage identity")
    raw=gzip.decompress(archive)
    if (len(raw),_sha(raw))!=(C.PRECOVERAGE_RAW_SIZE,C.PRECOVERAGE_RAW_SHA256):raise ValueError("precoverage raw identity")
    cov=json.loads(raw);seg=cov["segments"];starts=[x["range"][0] for x in seg]
    if any(cov["summary"].get(k)!=v for k,v in C.PRECOVERAGE_SUMMARY.items()) or len(seg)!=C.PRECOVERAGE_SUMMARY["segment_count"]:raise ValueError("precoverage summary")
    if seg[0]["range"][0]!=0 or seg[-1]["range"][1]!=C.ROM_SIZE or any(seg[i]["range"][1]!=seg[i+1]["range"][0] for i in range(len(seg)-1)):raise ValueError("precoverage partition")
    def owner(o):
        row=seg[bisect.bisect_right(starts,o)-1]
        if not row["range"][0]<=o<row["range"][1]:raise ValueError("owner lookup")
        return row
    for a,b in C.CODE_RANGES+C.LITERAL_RANGES+C.HOLES:
        o=a
        while o<b:
            row=owner(o)
            if row["primary_class"]!="unknown" or row.get("primary_claim_ids"):raise ValueError("target owner")
            o=min(b,row["range"][1])
    for o,cid in ((0x792be,C.OWNER_CLAIMS["source"]),(0x626b4,C.OWNER_CLAIMS["allocator"]),(0x62940,C.OWNER_CLAIMS["dispatcher"]),(0x9c114,C.OWNER_CLAIMS["veneer"])):
        if owner(o).get("primary_claim_ids")!=[cid]:raise ValueError("lifecycle owner")
    blobs={}
    for path,size,digest in C.UPSTREAM_IDENTITIES:
        data=_read_repo_file(root,path)
        if (len(data),_sha(data))!=(size,digest):raise ValueError("upstream identity")
        blobs[path.as_posix()]=data
    cfg=json.loads(blobs["artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"])
    source=[x for x in cfg["blocks"] if x["id"]=="block-thumb-0792b0"]
    veneer=[x for x in cfg["blocks"] if x["id"]=="block-thumb-09c114"]
    if len(source)!=1 or source[0]["range"]!=list(C.SOURCE_RANGE) or source[0]["bytes_sha256"]!=C.SOURCE_SHA256:raise ValueError("upstream source CFG record")
    if len(veneer)!=1 or veneer[0]["range"]!=list(C.VENEER_RANGE) or veneer[0]["bytes_sha256"]!=C.VENEER_SHA256:raise ValueError("upstream veneer CFG record")
    lit=json.loads(blobs["artifacts/rom-cfg-v2-consumed-literals-v1/rom-cfg-v2-consumed-literals.json"])["source_to_target"][1038]
    if lit!={"source_file_offset":0x792be,"source_raw_hex":"2e48","target_file_offset":0x79378,"target_raw_hex":"398e0708"}:raise ValueError("upstream literal 1038")
    scene=json.loads(blobs["artifacts/scene-visual-composites-v1/scene-visual-composites.json"])["code_evidence"]["allocator"]
    if scene!={"start":"0x080626B4","end_exclusive":"0x08062768","size":180,"sha256":C.ALLOCATOR_SHA256}:raise ValueError("upstream allocator")
    v20=json.loads(blobs["artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json"])["promotion"]["claims"]
    dispatcher=[x for x in v20 if x["id"]==C.OWNER_CLAIMS["dispatcher"]]
    if len(dispatcher)!=1 or dispatcher[0]["range"]!=[0x062924,0x06298C]:raise ValueError("upstream dispatcher")
    field=json.loads(blobs["artifacts/character-runtime-oam-task-bindings-v1/bindings.json"])["static_contract"]
    if field["task_pool"]!={"base":"0x03003BB8","record_size":60,"slot_count":128,"last_slot":"0x0300597C"} or field["task_fields"]["callback_u32"]!="0x28":raise ValueError("upstream field contract")
    return {"identities":{p.as_posix():{"size":s,"sha256":h} for p,s,h in C.UPSTREAM_IDENTITIES},"source_to_target_index":1038,"owner_claim_ids":C.OWNER_CLAIMS,"whole_field_artifact_verifier_claimed":False}

def _expected_payload(root,rom):
    closure=_rebuild_closure(rom);lifecycle=_rebuild_lifecycle(rom);upstream=_rebuild_inputs(root,rom)
    claims=[{"id":f"task-callback-078e38-{kind}-{i:02d}-{a:06x}","kind":kind,
             "range":[a,b],"bytes_sha256":_sha(rom[a:b]),"baseline_unknown_only":True}
            for kind,ranges in (("reachable_thumb_code",C.CODE_RANGES),("consumed_literal_words",C.LITERAL_RANGES))
            for i,(a,b) in enumerate(ranges,1)]
    promotion={"promotion_batch":C.SCHEMA,"primary_class":"armv4t_task_callback_078e38_closure",
               "claims":claims,"claim_count":16,"code_ranges":[list(x) for x in C.CODE_RANGES],
               "literal_ranges":[list(x) for x in C.LITERAL_RANGES],"promotion_bytes":778,
               "unknown_holes":[list(x) for x in C.HOLES],"unknown_hole_bytes":10,
               "holes_remain_primary_class":"unknown"}
    return {"schema":C.SCHEMA,
            "rom":{"path":C.ROM_PATH.as_posix(),"size":len(rom),"sha256":C.ROM_SHA256},
            "precoverage":{"artifact":C.PRECOVERAGE.as_posix(),**C.PRECOVERAGE_SUMMARY,
                           "manifest_sha256":C.PRECOVERAGE_MANIFEST_SHA256,
                           "archive_sha256":C.PRECOVERAGE_ARCHIVE_SHA256,
                           "raw_sha256":C.PRECOVERAGE_RAW_SHA256},
            "upstream":upstream,
            "producer":{"scan_range":[0,C.ROM_SIZE],"stride":2,
                        "decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],
                        "target_set":"root_and_internal_block_entries","direct_matches":[],
                        "pointer_bytes":C.POINTER_BYTES.hex(),
                        "pointer_occurrences":list(C.POINTER_OCCURRENCES)},
            "lifecycle":lifecycle,"closure":closure,"promotion":promotion,
            "scope":{"bounded_static_thumb_closure":True,"natural_runtime_reachability":False,
                     "global_indirect_or_computed_producers":False,"opaque_callee_semantics":False,
                     "structured_return_proven":False,"holes_padding_free_or_allocatable":False,
                     "editing_writeback_or_relocation_safety":False}}

def _intended_relative(root,artifact):
    absolute,relative=_artifact_parts(root,artifact)
    allowed=root/C.EXPERIMENT_ROOT;official=root/C.OFFICIAL_ARTIFACT
    if absolute!=official and not (absolute!=allowed and absolute.is_relative_to(allowed)):
        raise ValueError("intended artifact path is outside allowed outputs")
    return relative.as_posix()

def _report(status,errors):
    okay=not errors
    return {"schema":C.VERIFY_SCHEMA,"verified":okay,"errors":errors,"contract_ok":okay,
            "artifact_status":status,"promotion_bytes":778 if okay else None,
            "instruction_count":C.METRICS["instruction_count"] if okay else None,
            "frontier_count":C.METRICS["frontier_count"] if okay else None}

def verify_artifact(root,artifact,*,intended_artifact=None):
    errors=[];status=None;directory_fd=None
    try:
        root=Path(root).resolve(strict=True);_,directory_fd=_open_artifact(root,artifact)
        if set(os.listdir(directory_fd))!={C.PAYLOAD_NAME,C.MANIFEST_NAME}:raise ValueError("artifact member denominator")
        pr=_read_regular_at(directory_fd,C.PAYLOAD_NAME);mr=_read_regular_at(directory_fd,C.MANIFEST_NAME)
        payload=json.loads(pr);manifest=json.loads(mr)
        if pr!=_canonical(payload) or mr!=_canonical(manifest):raise ValueError("noncanonical artifact")
        rom=_read_repo_file(root,C.ROM_PATH)
        if (len(rom),_sha(rom),_sha(rom[slice(*C.ENVELOPE)]))!=(C.ROM_SIZE,C.ROM_SHA256,C.ENVELOPE_SHA256):raise ValueError("ROM identity")
        expected_payload=_expected_payload(root,rom)
        if payload!=expected_payload:raise ValueError("payload exact contract mismatch")
        intended=artifact if intended_artifact is None else intended_artifact
        relative=_intended_relative(root,intended)
        implementation={k:{"path":p.as_posix(),"sha256":_sha(_read_repo_file(root,p))}
                        for k,p in C.IMPLEMENTATION_PATHS.items()}
        verifier_command=["python3","tools/verify_rom_task_callback_078e38_closure.py","--root",".","--artifact",relative]
        base={"schema":"git-artifact-promotion-v1","artifact_schema":C.SCHEMA,
              "files":{C.PAYLOAD_NAME:{"size":len(pr),"sha256":_sha(pr)}},
              "summary":C.METRICS|{"promotion_bytes":778,"claim_count":16,"unknown_hole_bytes":10},
              "implementation":implementation,
              "producer":{"command":["python3","tools/export_rom_task_callback_078e38_closure.py","--root",".","--output",relative]}}
        status=manifest.get("artifact_status")
        if status=="candidate":
            expected={**base,"artifact_status":"candidate","verifier":{"command":verifier_command,"exit_code":None}}
        elif status=="accepted":
            candidate_report=_report("candidate",[])
            expected={**base,"artifact_status":"accepted","verifier":{"command":verifier_command,"exit_code":0,"report":candidate_report}}
        else:raise ValueError("artifact status contract")
        if manifest!=expected:raise ValueError("manifest exact contract mismatch")
    except Exception as e:errors.append(str(e))
    finally:
        if directory_fd is not None:os.close(directory_fd)
    return _report(status,errors)

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=Path("."));p.add_argument("--artifact",type=Path,default=C.OFFICIAL_ARTIFACT);a=p.parse_args();report=verify_artifact(a.root,a.artifact);print(json.dumps(report,indent=2,sort_keys=True));return 0 if report["verified"] else 1
if __name__=="__main__":raise SystemExit(main())
