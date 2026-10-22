#!/usr/bin/env python3
"""Independent raw-ROM verifier for boot register-init dependency CFG."""
from __future__ import annotations
import argparse,bisect,gzip,hashlib,heapq,json,struct,sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
for p in (PROJECT_ROOT,PROJECT_ROOT/"tools/_vendor"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from tools.rom_boot_register_init_dependency_cfg_contract import *
from tools.thumb_branch import decode_thumb_b,decode_thumb_bl
from tools.verify_rom_boot_interwork_continuation import _decode_thumb,_decoder_identity

def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _vsha(value):return _sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
def _canonical(value):return (json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
def _safe(root,rel):
    root=root.resolve(strict=True);rel=Path(rel)
    if rel.is_absolute() or ".." in rel.parts:raise ValueError("unsafe repository input")
    p=root
    for part in rel.parts:
        p/=part
        if p.is_symlink():raise ValueError("symlink repository input")
    p=p.resolve(strict=True)
    if not p.is_relative_to(root) or not p.is_file():raise ValueError("repository input escape")
    return p
def _merge(rows):
    out=[]
    for a,b in sorted(rows):
        if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out
def _owner(segments,starts,offset):
    row=segments[bisect.bisect_right(starts,offset)-1]
    if not row["range"][0]<=offset<row["range"][1]:raise ValueError("owner lookup")
    return row
def _baseline(root):
    mr=_safe(root,PRECOVERAGE_DIR/MANIFEST_NAME).read_bytes();ar=_safe(root,PRECOVERAGE_DIR/"rom-byte-coverage.json.gz").read_bytes()
    if (_sha(mr),len(ar),_sha(ar))!=(PRECOVERAGE_MANIFEST_SHA256,PRECOVERAGE_ARCHIVE_SIZE,PRECOVERAGE_ARCHIVE_SHA256):raise ValueError("precoverage identity")
    raw=gzip.decompress(ar)
    if (len(raw),_sha(raw))!=(PRECOVERAGE_RAW_SIZE,PRECOVERAGE_RAW_SHA256):raise ValueError("precoverage payload")
    cov=json.loads(raw);summary=cov.get("summary",{})
    if any(summary.get(k)!=v for k,v in BASELINE.items()):raise ValueError("precoverage summary")
    seg=cov.get("segments",[])
    if len(seg)!=BASELINE["segment_count"] or seg[0]["range"][0]!=0 or seg[-1]["range"][1]!=ROM_SIZE or any(seg[i]["range"][1]!=seg[i+1]["range"][0] for i in range(len(seg)-1)):raise ValueError("precoverage partition")
    return {"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE},seg,[x["range"][0] for x in seg]
def _read_artifact(root,directory,name,size_m,sha_m,size_p,sha_p):
    mr=_safe(root,directory/MANIFEST_NAME).read_bytes();pr=_safe(root,directory/name).read_bytes()
    if (len(mr),_sha(mr),len(pr),_sha(pr))!=(size_m,sha_m,size_p,sha_p):raise ValueError("upstream artifact identity")
    return json.loads(pr)
def _validate_producer_block(block):
    expected={"id":"block-thumb-06109e","range":[0x06109E,0x0610A2],"mode":"thumb","instruction_count":1,"bytes_sha256":PRODUCER[5],"terminator":{"conditional":False,"file_offset":0x06109E,"flow_kind":"call","mnemonic":"bl","op_str":"#0x806178c","raw_hex":"00f075fb","size":4},"call_target_successor":{"kind":"call_target","mode":"thumb","resolution":"opaque_external_edge","source_block_id":"block-thumb-06109e","source_instruction_offset":0x06109E,"target_gba_address":"0x0806178C","target_offset":ROOT}}
    if block!=expected:raise ValueError("continuation producer block")
    return block
def _producer_block(payload):
    rows=[x for x in payload.get("thumb_continuation",{}).get("blocks",[]) if x.get("id")=="block-thumb-06109e"]
    if len(rows)!=1:raise ValueError("continuation producer block denominator")
    row=rows[0];calls=[x for x in row.get("successors",[]) if x.get("kind")=="call_target"]
    if len(calls)!=1:raise ValueError("continuation producer call-target denominator")
    return _validate_producer_block({"id":row.get("id"),"range":row.get("range"),"mode":row.get("mode"),"instruction_count":row.get("instruction_count"),"bytes_sha256":row.get("bytes_sha256"),"terminator":row.get("terminator"),"call_target_successor":calls[0]})
def _overlays(root,target):
    specs=(("story_callback",STORY_ARTIFACT,STORY_PAYLOAD_NAME,STORY_MANIFEST_SIZE,STORY_MANIFEST_SHA256,STORY_PAYLOAD_SIZE,STORY_PAYLOAD_SHA256,STORY_VERIFIER,STORY_VERIFIER_SHA256,32,1932),("v20",V20_ARTIFACT,V20_PAYLOAD_NAME,V20_MANIFEST_SIZE,V20_MANIFEST_SHA256,V20_PAYLOAD_SIZE,V20_PAYLOAD_SHA256,V20_VERIFIER,V20_VERIFIER_SHA256,18,1150),("story_next",STORY_NEXT_ARTIFACT,STORY_NEXT_PAYLOAD_NAME,STORY_NEXT_MANIFEST_SIZE,STORY_NEXT_MANIFEST_SHA256,STORY_NEXT_PAYLOAD_SIZE,STORY_NEXT_PAYLOAD_SHA256,STORY_NEXT_VERIFIER,STORY_NEXT_VERIFIER_SHA256,19,854))
    from tools.verify_rom_story_callback_dependency_closures import verify_artifact
    from tools.verify_rom_cfg_proven_roots_v20 import verify_root as verify_v20
    from tools.verify_rom_story_next_dependency_cfg import verify_root as verify_next
    reports=(verify_artifact(root,root/STORY_ARTIFACT),verify_v20(root,root/V20_ARTIFACT),verify_next(root,root/STORY_NEXT_ARTIFACT));occupied=[];rows=[]
    for report,s in zip(reports,specs):
        name,directory,pname,ms,mh,ps,ph,vpath,vh,count,total=s
        payload=_read_artifact(root,directory,pname,ms,mh,ps,ph)
        if _sha(_safe(root,vpath).read_bytes())!=vh or not report.get("verified") or report.get("promotion_bytes")!=total:raise ValueError("overlay verifier")
        claims=payload["promotion"]["claims"];ranges=[tuple(x["range"]) for x in claims]
        if len(claims)!=count or sum(b-a for a,b in ranges)!=total or any(max(a,x)<min(b,y) for a,b in ranges for x,y in occupied+list(target)):raise ValueError("ordered overlay denominator")
        occupied.extend(ranges);rows.append({"name":name,"artifact":directory.as_posix(),"manifest_sha256":mh,"payload_sha256":ph,"verifier_sha256":vh,"verified":True,"claim_count":count,"promotion_bytes":total,"overlap_bytes":0})
    return rows
def _producer_owner(root,rom,segments,starts):
    payload=_read_artifact(root,CONTINUATION_ARTIFACT,CONTINUATION_PAYLOAD_NAME,CONTINUATION_MANIFEST_SIZE,CONTINUATION_MANIFEST_SHA256,CONTINUATION_PAYLOAD_SIZE,CONTINUATION_PAYLOAD_SHA256)
    if _sha(_safe(root,CONTINUATION_VERIFIER).read_bytes())!=CONTINUATION_VERIFIER_SHA256:raise ValueError("continuation verifier identity")
    from tools.verify_rom_boot_interwork_continuation import verify_root
    if not verify_root(root,root/CONTINUATION_ARTIFACT).get("verified"):raise ValueError("continuation independent verifier")
    cov=_owner(segments,starts,PRODUCER[0]);claim=next((x for x in payload["promotion"]["claims"] if x.get("id")=="continuation-code-06108a-0610d4"),None)
    if claim is None or tuple(cov["range"])!=(0x06108A,0x0610D4) or cov.get("primary_class")!="armv4t_boot_interwork_continuation_code" or cov.get("primary_claim_ids")!=[claim["id"]] or claim.get("sha256")!=_sha(rom[0x06108A:0x0610D4]):raise ValueError("producer owner")
    return {"artifact":CONTINUATION_ARTIFACT.as_posix(),"manifest_sha256":CONTINUATION_MANIFEST_SHA256,"payload_sha256":CONTINUATION_PAYLOAD_SHA256,"verifier_sha256":CONTINUATION_VERIFIER_SHA256,"verified":True,"claim_id":claim["id"],"primary_class":cov["primary_class"],"range":cov["range"],"mode":"thumb","bytes_sha256":claim["sha256"],"producer_block":_producer_block(payload)}
def _direct(rom,o):
    h=struct.unpack_from("<H",rom,o)[0]
    if o+4<=len(rom):
        t=decode_thumb_bl(o,h,struct.unpack_from("<H",rom,o+2)[0])
        if t is not None:return t,"thumb_bl",4
    t=decode_thumb_b(o,h)
    if t is not None:return t,"thumb_b",2
    if h&0xf000==0xd000 and ((h>>8)&15)<14:
        d=(h&255)<<1;d=d-0x200 if d&0x100 else d
        return o+4+d,"thumb_bcond",2
def _producer_denominator(rom):
    rows=[]
    for o in range(0,0x600000,2):
        item=_direct(rom,o)
        if item and item[0]==ROOT:
            t,k,z=item;raw=rom[o:o+z];rows.append({"file_offset":o,"target_file_offset":t,"kind":k,"size":z,"raw_hex":raw.hex(),"bytes_sha256":_sha(raw),"accepted_as_root_proof":True})
    expected={"file_offset":PRODUCER[0],"target_file_offset":PRODUCER[1],"kind":PRODUCER[2],"size":PRODUCER[3],"raw_hex":PRODUCER[4],"bytes_sha256":PRODUCER[5],"accepted_as_root_proof":True}
    if rows!=[expected]:raise ValueError("raw producer denominator")
    return {"scan_range":[0,0x600000],"stride":2,"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"match_count":1,"matches":rows}
def _literal_bindings(rom,nodes):
    rows=[]
    for o,n in sorted(nodes.items()):
        h=struct.unpack_from("<H",rom,o)[0]
        if n["size"]==2 and h&0xf800==0x4800:
            t=((o+4)&~3)+(h&255)*4;raw=rom[t:t+4];rows.append({"source":o,"source_raw_hex":n["raw_hex"],"target":t,"word_hex":raw.hex(),"word_u32":int.from_bytes(raw,"little"),"word_sha256":_sha(raw)})
    return rows
def _raw_cfg(root,rom):
    _decoder_identity(root);engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);engine.detail=True;engine.skipdata=False;inside=lambda o:any(a<=o<b for a,b in CODE_RANGES)
    pending=[ROOT];seen={ROOT};nodes={};calls=[];front=[]
    while pending:
        o=heapq.heappop(pending)
        if o in nodes:continue
        if o%2 or not inside(o):raise ValueError("raw worklist escape")
        n=_decode_thumb(rom,o,engine);nodes[o]=n
        for f in n["frontiers"]:front.append((o,f["reason"],n["raw_hex"],n["op_str"]))
        for edge in n["successors"]:
            t=edge["file_offset"]
            if inside(t):
                if t not in seen:seen.add(t);heapq.heappush(pending,t)
            elif edge["kind"]=="call_target":calls.append((o,t,n["raw_hex"]))
            else:raise ValueError("raw outbound")
    code=_merge((o,o+n["size"]) for o,n in nodes.items());pred={o:[] for o in nodes}
    for o,n in nodes.items():
        for edge in n["successors"]:
            if edge["file_offset"] in nodes:pred[edge["file_offset"]].append(o)
    starts={ROOT}
    for o,inc in pred.items():
        if o==ROOT:continue
        if len(inc)!=1:starts.add(o);continue
        n=nodes[inc[0]];inside_edges=[x for x in n["successors"] if x["file_offset"] in nodes]
        if n["flow_kind"]!="linear" or len(inside_edges)!=1 or inside_edges[0]["file_offset"]!=o or inc[0]+n["size"]!=o:starts.add(o)
    blocks=[];block_vector=[]
    for start in sorted(starts):
        o=start
        while True:
            n=nodes[o];inside_edges=[x for x in n["successors"] if x["file_offset"] in nodes];nxt=o+n["size"]
            if n["flow_kind"]!="linear" or len(inside_edges)!=1 or inside_edges[0]["file_offset"]!=nxt or nxt in starts:break
            o=nxt
        end=o+nodes[o]["size"];blocks.append([start,end]);last=nodes[o]
        block_vector.append({"start":start,"end":end,"instruction_count":sum(1 for x in nodes if start<=x<end),"bytes_sha256":_sha(rom[start:end]),"terminator":{"file_offset":o,"raw_hex":last["raw_hex"],"mnemonic":last["mnemonic"],"op_str":last["op_str"],"flow_kind":last["flow_kind"],"conditional":last["conditional"]},"successors":[{"kind":x["kind"],"target":x["file_offset"],"resolution":"internal" if x["file_offset"] in nodes else "opaque_existing_entry"} for x in last["successors"]],"frontier":[{"reason":x["reason"]} for x in last["frontiers"]]})
    bindings=_literal_bindings(rom,nodes);literals=_merge((x["target"],x["target"]+4) for x in bindings)
    metrics={"instruction_count":len(nodes),"instruction_bytes":sum(x["size"] for x in nodes.values()),"basic_block_count":len(blocks),"literal_reference_count":len(bindings),"unique_literal_word_count":len({x["target"] for x in bindings}),"literal_bytes":sum(b-a for a,b in literals),"opaque_call_count":len(calls),"frontier_count":len(front),"structured_return_count":sum(x["flow_kind"]=="return" for x in nodes.values())}
    code_hashes=tuple(_sha(rom[a:b]) for a,b in CODE_RANGES);literal_hashes=tuple(_sha(rom[a:b]) for a,b in LITERAL_RANGES)
    if metrics!=METRICS or tuple(map(tuple,code))!=CODE_RANGES or tuple(map(tuple,blocks))!=BLOCK_RANGES or tuple(map(tuple,literals))!=LITERAL_RANGES or tuple(calls)!=OPAQUE_CALLS or tuple(front)!=FRONTIERS or code_hashes!=CODE_RANGE_SHA256S or literal_hashes!=LITERAL_RANGE_SHA256S or _sha(b"".join(rom[a:b] for a,b in CODE_RANGES))!=PACKED_CODE_SHA256 or _sha(b"".join(rom[a:b] for a,b in LITERAL_RANGES))!=PACKED_LITERAL_SHA256:raise ValueError("raw CFG denominator")
    block_hash=_vsha(block_vector);binding_hash=_vsha(bindings)
    if block_hash!=BLOCK_VECTOR_SHA256 or binding_hash!=LITERAL_BINDING_VECTOR_SHA256:raise ValueError("raw canonical vector identity")
    return {**metrics,"code_ranges":code,"code_range_sha256s":list(code_hashes),"packed_code_sha256":PACKED_CODE_SHA256,"block_ranges":blocks,"block_vector":block_vector,"block_vector_sha256":block_hash,"literal_ranges":literals,"literal_range_sha256s":list(literal_hashes),"literal_bindings":bindings,"literal_binding_vector_sha256":binding_hash,"packed_literal_sha256":PACKED_LITERAL_SHA256,"opaque_calls":[{"source":a,"target":b,"raw_hex":raw,"resolution":"opaque_existing_entry"} for a,b,raw in calls],"frontiers":[{"file_offset":a,"reason":r,"raw_hex":raw,"register":reg} for a,r,raw,reg in front]}
def _inventory(root,rom,segments,starts):
    mr=_safe(root,CFG_INVENTORY/MANIFEST_NAME).read_bytes();pr=_safe(root,CFG_INVENTORY/CFG_INVENTORY_PAYLOAD_NAME).read_bytes();vr=_safe(root,CFG_INVENTORY_VERIFIER).read_bytes()
    if (_sha(mr),_sha(pr),_sha(vr))!=(CFG_INVENTORY_MANIFEST_SHA256,CFG_INVENTORY_PAYLOAD_SHA256,CFG_INVENTORY_VERIFIER_SHA256):raise ValueError("inventory identity")
    from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory
    if not verify_rom_cfg_inventory(root,root/CFG_INVENTORY).get("verified"):raise ValueError("inventory verifier")
    matches=[x for x in json.loads(pr)["blocks"] if x.get("id")=="block-thumb-09c0e0"]
    if len(matches)!=1:raise ValueError("inventory exact entry")
    b=matches[0];entry={"id":b["id"],"range":b["range"],"mode":b["mode"],"instruction_count":b["instruction_count"],"bytes_sha256":b["bytes_sha256"],"raw_hex":rom[0x09C0E0:0x09C0E2].hex()};owner=_owner(segments,starts,0x09C0E0)
    owner_record={"range":owner["range"],"primary_class":owner["primary_class"],"claim_id":owner["primary_claim_ids"][0]}
    _validate_inventory_records(entry,owner_record)
    return {"artifact":CFG_INVENTORY.as_posix(),"manifest_sha256":CFG_INVENTORY_MANIFEST_SHA256,"payload_sha256":CFG_INVENTORY_PAYLOAD_SHA256,"verifier_sha256":CFG_INVENTORY_VERIFIER_SHA256,"verified":True,"entry_block":entry,"owner":owner_record}
def _validate_inventory_records(entry,owner):
    expected_entry={"id":"block-thumb-09c0e0","range":[0x09C0E0,0x09C0E2],"mode":"thumb","instruction_count":1,"bytes_sha256":"38ac888b30c3f43dc0b29840880256705d34b3f73035d6daa036c7b61ab5db6e","raw_hex":"0bdf"}
    expected_owner={"range":[0x09C0D8,0x09C0F4],"primary_class":"armv4t_cfg_reachable_thumb_code","claim_id":"cfg-thumb-0773-09c0d8"}
    if entry!=expected_entry or owner!=expected_owner:raise ValueError("CFG exact entry/owner")
    return entry,owner
def _implementation(root):return {"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},"sha256":{k:_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}
def _expected(root,rom):
    baseline,segments,starts=_baseline(root);target=CODE_RANGES+LITERAL_RANGES;overlays=_overlays(root,target);owner=_producer_owner(root,rom,segments,starts);producer=_producer_denominator(rom);cfg=_raw_cfg(root,rom);inventory=_inventory(root,rom,segments,starts)
    for a,b in target+(UNKNOWN_HOLE,):
        o=a
        while o<b:
            row=_owner(segments,starts,o)
            if row.get("primary_class")!="unknown":raise ValueError("target/hole owner")
            o=min(b,row["range"][1])
    hrow=_owner(segments,starts,UNKNOWN_HOLE[0]);hole={"range":list(UNKNOWN_HOLE),"raw_hex":rom[UNKNOWN_HOLE[0]:UNKNOWN_HOLE[1]].hex(),"primary_class":hrow["primary_class"],"claim_ids":hrow.get("primary_claim_ids",[])};exrows=[]
    for a,b,cls,cid in EXCLUSION_OWNERS:
        row=_owner(segments,starts,a)
        if row.get("range")!=[a,b] or row.get("primary_class")!=cls or row.get("primary_claim_ids")!=[cid]:raise ValueError("exclusion owner")
        exrows.append({"range":[a,b],"primary_class":cls,"claim_id":cid,"bytes_sha256":_sha(rom[a:b]),"raw_hex":rom[a:b].hex()})
    if _sha(b"".join(rom[a:b] for a,b in UNION_RANGES))!=PACKED_PROMOTION_SHA256:raise ValueError("promotion bytes")
    claims=[{"id":f"boot-register-init-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,ranges in (("reachable_thumb_code",CODE_RANGES),("consumed_literal_words",LITERAL_RANGES)) for i,(a,b) in enumerate(ranges,1)]
    promotion={"promotion_batch":SCHEMA,"primary_class":"armv4t_boot_register_init_dependency_cfg","claim_kind":"armv4t_boot_register_init_dependency_cfg_exact_bytes","code_ranges":[list(x) for x in CODE_RANGES],"literal_ranges":[list(x) for x in LITERAL_RANGES],"union_ranges":[list(x) for x in UNION_RANGES],"preserved_unknown_holes":[list(UNKNOWN_HOLE)],"outside_worklist_existing_owner_exclusions":[list(EXCLUSION)],"code_bytes":318,"literal_bytes":128,"promotion_bytes":446,"claim_count":8,"packed_promotion_sha256":PACKED_PROMOTION_SHA256,"claims":claims}
    scope={"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"natural_runtime_reachability":False,"global_caller_code_or_indirect_exhaustiveness":False,"computed_or_ram_producers":False,"frontier_targets_or_structured_returns":False,"existing_owner_reclassification":False,"literal_business_semantics":False,"holes_alignment_padding_or_free_space":False,"abi_or_compiler":False,"editing_writeback_relocation_or_gameplay":False}
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"precoverage":baseline,"overlays":overlays,"producer_owner":owner,"root":{"file_offset":ROOT,"raw_hex":ROOT_ENTRY_RAW,"entry_sha256":ROOT_ENTRY_SHA256},"producer_denominator":producer,"cfg_inventory":inventory,"target_local_denominator":cfg,"preserved_unknown_holes":[hole],"outside_worklist_existing_owner_exclusions":[{"kind":"outside_worklist_existing_owner_exclusion","range":list(EXCLUSION),"raw_hex":rom[EXCLUSION[0]:EXCLUSION[1]].hex(),"owner_segments":exrows}],"promotion":promotion,"coverage_projection":{"baseline_unknown_bytes":93109,"story_overlay_promoted_bytes":1932,"v20_overlay_promoted_bytes":1150,"story_next_overlay_promoted_bytes":854,"target_promoted_bytes":446,"cumulative_promoted_bytes":4382,"classified_bytes":6202729,"remaining_unknown_bytes":88727},"implementation":_implementation(root),"scope":scope}
def _failure(error):return {"schema":VERIFY_SCHEMA,"verified":False,"errors":[str(error)],"promotion_bytes":0}
def verify_root(root,artifact,*,expected_receipt_path=None):
    try:
        root=Path(root).resolve(strict=True);artifact=(Path(artifact) if Path(artifact).is_absolute() else root/Path(artifact)).absolute()
        if artifact.resolve(strict=False)!=artifact or artifact.is_symlink() or not artifact.is_dir() or {x.name for x in artifact.iterdir()}!={PAYLOAD_NAME,MANIFEST_NAME} or any(x.is_symlink() or not x.is_file() for x in artifact.iterdir()):raise ValueError("artifact file set")
        pr=(artifact/PAYLOAD_NAME).read_bytes();mr=(artifact/MANIFEST_NAME).read_bytes();payload=json.loads(pr);manifest=json.loads(mr)
        if pr!=_canonical(payload) or mr!=_canonical(manifest):raise ValueError("noncanonical JSON")
        rom=_safe(root,ROM_PATH).read_bytes()
        if (len(rom),_sha(rom))!=(ROM_SIZE,ROM_SHA256):raise ValueError("ROM identity")
        expected=_expected(root,rom)
        if payload!=expected:raise ValueError("payload differs from independent raw reconstruction")
        for key in ("rom","precoverage","overlays","producer_owner","cfg_inventory","implementation","promotion","coverage_projection","scope"):
            if manifest.get(key)!=payload[key]:raise ValueError("manifest projection")
        if manifest.get("files",{}).get(PAYLOAD_NAME)!={"sha256":_sha(pr),"size":len(pr)}:raise ValueError("manifest file binding")
        receipt=Path(expected_receipt_path).absolute() if expected_receipt_path is not None else artifact
        if not receipt.is_relative_to(root):raise ValueError("receipt escape")
        rel=receipt.relative_to(root).as_posix();ec=["python3","-I","-S","tools/export_rom_boot_register_init_dependency_cfg.py","--root",".","--output",rel];vc=["python3","-I","-S","tools/verify_rom_boot_register_init_dependency_cfg.py","--root",".","--artifact",rel]
        if manifest.get("schema")!="git-artifact-promotion-v1" or manifest.get("artifact_schema")!=SCHEMA or manifest.get("producer",{}).get("command")!=ec or manifest.get("verifier",{}).get("command")!=vc:raise ValueError("manifest receipt")
        success={"schema":VERIFY_SCHEMA,"verified":True,"errors":[],"rom_sha256":ROM_SHA256,"instruction_count":154,"basic_block_count":12,"literal_word_count":32,"opaque_call_count":3,"frontier_count":3,"structured_return_count":0,"promotion_bytes":446,"remaining_unknown_bytes":88727}
        if manifest.get("artifact_status")=="candidate":
            if manifest["verifier"].get("exit_code") is not None or "report" in manifest["verifier"]:raise ValueError("candidate receipt")
        elif manifest.get("artifact_status")=="accepted":
            if manifest["verifier"].get("exit_code")!=0 or manifest["verifier"].get("report")!=success:raise ValueError("accepted receipt")
        else:raise ValueError("artifact status")
        return success
    except Exception as error:return _failure(error)
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--artifact",type=Path,required=True);a=p.parse_args();r=verify_root(a.root,a.artifact);print(json.dumps(r,sort_keys=True));return 0 if r["verified"] else 1
if __name__=="__main__":raise SystemExit(main())
