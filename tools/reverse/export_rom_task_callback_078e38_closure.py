#!/usr/bin/env python3
"""Export the frozen Tier-1 0x078E38 task-callback closure."""

from __future__ import annotations
import argparse, bisect, ctypes, errno, gzip, hashlib, heapq, json, os, secrets, stat, struct, sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path: sys.path.insert(0, str(_path))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone import arm_const
from tools import rom_task_callback_078e38_contract as C
from tools.thumb_branch import decode_thumb_b, decode_thumb_bl

def _sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def _canonical(value: Any) -> bytes: return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode()
def _packed(rom, ranges): return b"".join(rom[a:b] for a,b in ranges)
def _vsha(value): return _sha(json.dumps(value,sort_keys=True,separators=(",",":")).encode())

def _read_repo_file(root: Path, rel: Path) -> bytes:
    root=root.resolve(strict=True);rel=Path(rel)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("unsafe repository input")
    directory_flags=os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(root,directory_flags)
    try:
        for part in rel.parts[:-1]:
            child=os.open(part,directory_flags,dir_fd=fd);os.close(fd);fd=child
        file_flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
        child=os.open(rel.parts[-1],file_flags,dir_fd=fd)
        try:
            before=os.fstat(child)
            if not stat.S_ISREG(before.st_mode):raise ValueError("repository input is not regular")
            chunks=[]
            while True:
                chunk=os.read(child,1024*1024)
                if not chunk:break
                chunks.append(chunk)
            after=os.fstat(child)
            identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
            if identity(before)!=identity(after):raise ValueError("repository input changed while reading")
            return b"".join(chunks)
        finally:os.close(child)
    finally:os.close(fd)

def _decode(rom: bytes, offset: int, engine: Cs) -> dict[str, Any]:
    insns=tuple(engine.disasm(rom[offset:offset+4],0x08000000+offset,count=1))
    if len(insns)!=1: raise ValueError("closure decode failure")
    ins=insns[0]; raw=rom[offset:offset+ins.size]
    if ins.size not in (2,4) or (ins.size==4 and ins.id!=arm_const.ARM_INS_BL):
        raise ValueError("closure unsupported instruction")
    h=int.from_bytes(raw[:2],"little"); successors=[]; frontier=[]; conditional=False
    target=None
    if ins.size==4: target=decode_thumb_bl(offset,h,int.from_bytes(raw[2:4],"little")); kind="call"
    else:
        if h&0xF000==0xD000 and ((h>>8)&15)<14:
            displacement=(h&0xff)<<1
            if displacement&0x100:displacement-=0x200
            target=offset+4+displacement;conditional=True
        else:target=decode_thumb_b(offset,h)
        kind="branch"
    if target is not None:
        successors.append(("call_target" if kind=="call" else "branch_target",target))
        if kind=="call" or conditional: successors.append(("fallthrough",offset+ins.size))
        flow="call" if kind=="call" else ("conditional_branch" if conditional else "unconditional_branch")
    elif h&0xFF87==0x4700:
        flow="indirect_branch"; frontier.append("indirect_pc_target")
    elif ins.id==arm_const.ARM_INS_SVC:
        flow="supervisor_call"; frontier.append("bios_swi_external"); successors.append(("fallthrough",offset+ins.size))
    else:
        flow="linear"; successors.append(("fallthrough",offset+ins.size))
    return {"offset":offset,"size":ins.size,"raw_hex":raw.hex(),"mnemonic":ins.mnemonic,
            "op_str":ins.op_str,"flow_kind":flow,"successors":successors,"frontiers":frontier}

def _merge(rows):
    out=[]
    for a,b in sorted(rows):
        if out and a<=out[-1][1]: out[-1][1]=max(out[-1][1],b)
        else: out.append([a,b])
    return out

def _return_candidate(rom, nodes):
    a,b=C.EPILOGUE
    if rom[a:b].hex()!=C.EPILOGUE_RAW_HEX or _sha(rom[a:b])!=C.EPILOGUE_SHA256:
        raise ValueError("return candidate epilogue changed")
    sp_rows={o:n["raw_hex"] for o,n in nodes.items()
             if "sp" in n["op_str"] or n["mnemonic"] in ("push","pop")}
    if sp_rows!=C.STACK_SITES: raise ValueError("return candidate SP observation changed")
    if nodes[0x079144]["raw_hex"]!="0047" or nodes[0x079144]["op_str"]!="r0":
        raise ValueError("return candidate final branch changed")
    return {"epilogue_range":[a,b],"epilogue_sha256":C.EPILOGUE_SHA256,
            "terminal_branch":{"source":0x079144,"raw_hex":"0047","register":"r0"},
            "observed_stack_site_count":len(sp_rows),
            "opaque_callee_stack_effects_proven":False,"structured_return_proven":False}

def _cfg(rom: bytes) -> dict[str,Any]:
    inside=lambda o:any(a<=o<b for a,b in C.CODE_RANGES)
    eng=Cs(CS_ARCH_ARM,CS_MODE_THUMB);eng.detail=True;eng.skipdata=False
    pending=[C.ROOT];nodes={};calls=[]
    while pending:
        o=heapq.heappop(pending)
        if o in nodes: continue
        if o%2 or not inside(o): raise ValueError("closure worklist escaped")
        n=_decode(rom,o,eng);nodes[o]=n
        for kind,t in n["successors"]:
            if inside(t): heapq.heappush(pending,t)
            elif kind=="call_target": calls.append((o,t))
            else: raise ValueError("closure non-call edge escaped")
    frontiers=[{"source":o,"reason":reason} for o,n in sorted(nodes.items()) for reason in n["frontiers"]]
    if tuple((row["source"],row["reason"]) for row in frontiers)!=tuple(
        (row["source"],row["reason"]) for row in C.FRONTIERS
    ): raise ValueError("closure frontier denominator changed")
    code=_merge((o,o+n["size"]) for o,n in nodes.items())
    pred={o:[] for o in nodes}
    for o,n in nodes.items():
        for _,t in n["successors"]:
            if t in nodes: pred[t].append(o)
    starts={C.ROOT}
    for o,inc in pred.items():
        if o==C.ROOT: continue
        if len(inc)!=1: starts.add(o);continue
        p=nodes[inc[0]];internal=[t for _,t in p["successors"] if t in nodes]
        if p["flow_kind"]!="linear" or internal!=[o] or inc[0]+p["size"]!=o: starts.add(o)
    blocks=[]
    for start in sorted(starts):
        o=start
        while True:
            n=nodes[o]; internal=[t for _,t in n["successors"] if t in nodes]; nxt=o+n["size"]
            if n["flow_kind"]!="linear" or internal!=[nxt] or nxt in starts: break
            o=nxt
        blocks.append([start,o+nodes[o]["size"]])
    bindings=[]
    for o,n in sorted(nodes.items()):
        h=int.from_bytes(rom[o:o+2],"little")
        if n["size"]==2 and h&0xF800==0x4800:
            t=((o+4)&~3)+(h&255)*4;bindings.append([o,t,rom[t:t+4].hex()])
    literals=_merge((t,t+4) for _,t,_ in bindings)
    metrics={"instruction_count":len(nodes),"basic_block_count":len(blocks),
             "code_bytes":sum(n["size"] for n in nodes.values()),
             "literal_reference_count":len(bindings),"unique_literal_word_count":len({x[1] for x in bindings}),
             "literal_bytes":sum(b-a for a,b in literals),"opaque_call_count":len(calls),
             "opaque_unique_target_count":len({x[1] for x in calls}),"structured_return_count":0,
             "frontier_count":len(frontiers)}
    if metrics!=C.METRICS or tuple(map(tuple,code))!=C.CODE_RANGES or tuple(map(tuple,literals))!=C.LITERAL_RANGES:
        raise ValueError("closure denominator changed")
    if tuple(map(tuple,blocks))!=C.BLOCK_RANGES or tuple(calls)!=C.OPAQUE_CALLS: raise ValueError("closure block/call denominator changed")
    if _vsha(blocks)!=C.BLOCK_RANGE_VECTOR_SHA256: raise ValueError("closure block vector changed")
    code_raw=_packed(rom,C.CODE_RANGES);lit_raw=_packed(rom,C.LITERAL_RANGES)
    address_union=_packed(rom,sorted(C.CODE_RANGES+C.LITERAL_RANGES))
    hashes=(_sha(code_raw),_sha(lit_raw),_sha(code_raw+lit_raw),_sha(address_union),_sha(_packed(rom,C.HOLES)))
    expected=(C.CODE_PACKED_SHA256,C.LITERAL_PACKED_SHA256,C.CODE_THEN_LITERAL_SHA256,C.ADDRESS_ORDER_UNION_SHA256,C.HOLES_PACKED_SHA256)
    if hashes!=expected: raise ValueError("closure or literal byte identity changed")
    return {**metrics,"code_ranges":code,"literal_ranges":literals,"holes":[list(x) for x in C.HOLES],
            "code_bytes_sha256":hashes[0],"literal_bytes_sha256":hashes[1],
            "code_then_literal_sha256":hashes[2],"address_order_union_sha256":hashes[3],
            "holes_bytes_sha256":hashes[4],"blocks":blocks,"literal_bindings":bindings,
            "opaque_calls":[{"source":a,"target":b} for a,b in calls],"frontiers":frontiers,
            "return_candidate":_return_candidate(rom,nodes)}

def _baseline(root):
    mr=_read_repo_file(root,C.PRECOVERAGE/C.MANIFEST_NAME); ar=_read_repo_file(root,C.PRECOVERAGE/"rom-byte-coverage.json.gz")
    if (len(mr),_sha(mr),len(ar),_sha(ar))!=(C.PRECOVERAGE_MANIFEST_SIZE,C.PRECOVERAGE_MANIFEST_SHA256,C.PRECOVERAGE_ARCHIVE_SIZE,C.PRECOVERAGE_ARCHIVE_SHA256): raise ValueError("precoverage identity changed")
    raw=gzip.decompress(ar)
    if (len(raw),_sha(raw))!=(C.PRECOVERAGE_RAW_SIZE,C.PRECOVERAGE_RAW_SHA256): raise ValueError("precoverage payload identity changed")
    cov=json.loads(raw);seg=cov["segments"]
    if any(cov["summary"].get(k)!=v for k,v in C.PRECOVERAGE_SUMMARY.items()) or len(seg)!=C.PRECOVERAGE_SUMMARY["segment_count"]: raise ValueError("precoverage denominator changed")
    if seg[0]["range"][0]!=0 or seg[-1]["range"][1]!=C.ROM_SIZE or any(seg[i]["range"][1]!=seg[i+1]["range"][0] for i in range(len(seg)-1)): raise ValueError("precoverage partition changed")
    return cov,seg,[x["range"][0] for x in seg]

def _owner(seg,starts,o):
    row=seg[bisect.bisect_right(starts,o)-1]
    if not row["range"][0]<=o<row["range"][1]: raise ValueError("coverage owner lookup")
    return row

def _upstream(root,rom,seg,starts):
    raws={}
    for path,size,digest in C.UPSTREAM_IDENTITIES:
        raw=_read_repo_file(root,path)
        if (len(raw),_sha(raw))!=(size,digest): raise ValueError(f"upstream identity changed: {path}")
        raws[path.as_posix()]=raw
    cfg=json.loads(raws["artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"])
    source=[x for x in cfg["blocks"] if x["id"]=="block-thumb-0792b0"]
    veneer=[x for x in cfg["blocks"] if x["id"]=="block-thumb-09c114"]
    if len(source)!=1 or source[0]["range"]!=list(C.SOURCE_RANGE) or source[0]["bytes_sha256"]!=C.SOURCE_SHA256: raise ValueError("source accepted block changed")
    if len(veneer)!=1 or veneer[0]["range"]!=list(C.VENEER_RANGE) or veneer[0]["bytes_sha256"]!=C.VENEER_SHA256: raise ValueError("veneer accepted block changed")
    lit=json.loads(raws["artifacts/rom-cfg-v2-consumed-literals-v1/rom-cfg-v2-consumed-literals.json"])
    expected={"source_file_offset":0x0792BE,"source_raw_hex":"2e48","target_file_offset":0x079378,"target_raw_hex":"398e0708"}
    if len(lit["source_to_target"])<=1038 or lit["source_to_target"][1038]!=expected: raise ValueError("source_to_target 1038 changed")
    scene=json.loads(raws["artifacts/scene-visual-composites-v1/scene-visual-composites.json"])
    if scene["code_evidence"]["allocator"]!={"start":"0x080626B4","end_exclusive":"0x08062768","size":180,"sha256":C.ALLOCATOR_SHA256}: raise ValueError("allocator accepted owner changed")
    v20=json.loads(raws["artifacts/rom-cfg-proven-roots-v20/rom-cfg-proven-roots-v20.json"])
    claims=[x for x in v20["promotion"]["claims"] if x["id"]==C.OWNER_CLAIMS["dispatcher"]]
    if len(claims)!=1 or claims[0]["range"]!=[0x062924,0x06298C]: raise ValueError("dispatcher accepted owner changed")
    field=json.loads(raws["artifacts/character-runtime-oam-task-bindings-v1/bindings.json"])["static_contract"]
    if field["task_pool"]!={"base":"0x03003BB8","record_size":60,"slot_count":128,"last_slot":"0x0300597C"} or field["task_fields"]["callback_u32"]!="0x28": raise ValueError("task field contract changed")
    expected_owners=((0x0792BE,C.OWNER_CLAIMS["source"]),(0x0626B4,C.OWNER_CLAIMS["allocator"]),(0x062940,C.OWNER_CLAIMS["dispatcher"]),(0x09C114,C.OWNER_CLAIMS["veneer"]))
    for o,cid in expected_owners:
        if _owner(seg,starts,o).get("primary_claim_ids")!=[cid]: raise ValueError("lifecycle coverage owner changed")
    return {"identities":{p.as_posix():{"size":s,"sha256":h} for p,s,h in C.UPSTREAM_IDENTITIES},"source_to_target_index":1038,"owner_claim_ids":C.OWNER_CLAIMS,"whole_field_artifact_verifier_claimed":False}

def _direct_target(rom,o):
    h=struct.unpack_from("<H",rom,o)[0]; t=decode_thumb_bl(o,h,struct.unpack_from("<H",rom,o+2)[0]) if o+4<=len(rom) else None
    if t is not None:return t,"thumb_bl",4
    if h&0xF000==0xD000 and ((h>>8)&15)<14:
        d=(h&255)<<1
        if d&0x100:d-=0x200
        return o+4+d,"thumb_bcond",2
    t=decode_thumb_b(o,h)
    if t is not None:return t,"thumb_b",2

def _scan_direct_matches(rom,entries,excluded_range):
    direct=[]
    for o in range(0,len(rom)-1,2):
        if excluded_range[0]<=o<excluded_range[1]:continue
        item=_direct_target(rom,o)
        if item and item[0] in entries:direct.append([o,*item])
    return direct

def _lifecycle(rom):
    if _sha(rom[slice(*C.SOURCE_RANGE)])!=C.SOURCE_SHA256 or _sha(rom[slice(*C.ALLOCATOR_RANGE)])!=C.ALLOCATOR_SHA256 or _sha(rom[slice(*C.DISPATCHER_RANGE)])!=C.DISPATCHER_SHA256 or _sha(rom[slice(*C.VENEER_RANGE)])!=C.VENEER_SHA256: raise ValueError("lifecycle slice changed")
    if rom[0x0792BE:0x0792C2].hex()!="2e480490" or _direct_target(rom,0x0792CA)!=(0x0626B4,"thumb_bl",4): raise ValueError("lifecycle source registration changed")
    if rom[0x06272A:0x06272E].hex()!="05431560" or rom[0x06275E:0x062762].hex()!="0e989062": raise ValueError("lifecycle allocator field changed")
    if rom[0x062940:0x062958].hex()!="3968012001400692002905d0b96a002902d0381c39f0defb" or _direct_target(rom,0x062954)!=(0x09C114,"thumb_bl",4) or rom[0x09C114:0x09C116].hex()!="0847": raise ValueError("lifecycle dispatcher changed")
    ptr=[];start=0
    while True:
        at=rom.find(C.POINTER_BYTES,start)
        if at<0:break
        ptr.append(at);start=at+1
    if tuple(ptr)!=C.POINTER_OCCURRENCES: raise ValueError("lifecycle callback pointer denominator changed")
    entries={a for a,_ in C.BLOCK_RANGES}
    direct=_scan_direct_matches(rom,entries,C.ENVELOPE)
    if direct: raise ValueError("lifecycle direct producer denominator changed")
    return {"callback_pointer":0x08078E39,"pointer_occurrences":ptr,"callback_stack_store":0x0792C0,"callback_stack_offset":0x10,"allocator_callsite":0x0792CA,"allocator_root":0x0626B4,"allocator_arg8_load":0x06275E,"allocator_callback_store":0x062760,"active_flag_store":0x06272C,"callback_field":0x28,"pool_base":0x03003BB8,"pool_records":128,"record_size":0x3C,"dispatcher_root":0x062940,"dispatcher_active_flag_test":0x062944,"dispatcher_callback_load":0x06294C,"dispatcher_task_argument":0x062952,"dispatcher_veneer_callsite":0x062954,"dispatch_veneer":0x09C114,"source_owner_verified":True,"allocator_owner_verified":True,"dispatcher_owner_verified":True,"field_contract_replayed":True,"whole_field_artifact_verifier_claimed":False}

def _build_from_rom(root:Path,rom:bytes,*,verify_rom_identity=True):
    if len(rom)!=C.ROM_SIZE or (verify_rom_identity and _sha(rom)!=C.ROM_SHA256): raise ValueError("ROM identity changed")
    if _sha(rom[slice(*C.ENVELOPE)])!=C.ENVELOPE_SHA256: raise ValueError("closure envelope changed")
    cov,seg,starts=_baseline(root);cfg=_cfg(rom);up=_upstream(root,rom,seg,starts);life=_lifecycle(rom)
    for a,b in C.CODE_RANGES+C.LITERAL_RANGES+C.HOLES:
        o=a
        while o<b:
            row=_owner(seg,starts,o)
            if row["primary_class"]!="unknown" or row.get("primary_claim_ids"): raise ValueError("promotion range is not current unknown")
            o=min(b,row["range"][1])
    claims=[{"id":f"task-callback-078e38-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b]),"baseline_unknown_only":True} for kind,ranges in (("reachable_thumb_code",C.CODE_RANGES),("consumed_literal_words",C.LITERAL_RANGES)) for i,(a,b) in enumerate(ranges,1)]
    promotion={"promotion_batch":C.SCHEMA,"primary_class":"armv4t_task_callback_078e38_closure","claims":claims,"claim_count":16,"code_ranges":[list(x) for x in C.CODE_RANGES],"literal_ranges":[list(x) for x in C.LITERAL_RANGES],"promotion_bytes":778,"unknown_holes":[list(x) for x in C.HOLES],"unknown_hole_bytes":10,"holes_remain_primary_class":"unknown"}
    return {"schema":C.SCHEMA,"rom":{"path":C.ROM_PATH.as_posix(),"size":len(rom),"sha256":C.ROM_SHA256},"precoverage":{"artifact":C.PRECOVERAGE.as_posix(),**C.PRECOVERAGE_SUMMARY,"manifest_sha256":C.PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":C.PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":C.PRECOVERAGE_RAW_SHA256},"upstream":up,"producer":{"scan_range":[0,C.ROM_SIZE],"stride":2,"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"target_set":"root_and_internal_block_entries","direct_matches":[],"pointer_bytes":C.POINTER_BYTES.hex(),"pointer_occurrences":list(C.POINTER_OCCURRENCES)},"lifecycle":life,"closure":cfg,"promotion":promotion,"scope":{"bounded_static_thumb_closure":True,"natural_runtime_reachability":False,"global_indirect_or_computed_producers":False,"opaque_callee_semantics":False,"structured_return_proven":False,"holes_padding_free_or_allocatable":False,"editing_writeback_or_relocation_safety":False}}

def build_payload(root):
    root=Path(root).resolve(strict=True);return _build_from_rom(root,_read_repo_file(root,C.ROM_PATH))

def _publish_exclusive_at(parent_fd,source_name,destination_name):
    libc=ctypes.CDLL(None,use_errno=True)
    if sys.platform=="darwin":rename,flag=libc.renameatx_np,0x4
    elif hasattr(libc,"renameat2"):rename,flag=libc.renameat2,0x1
    else:raise OSError(errno.ENOTSUP,"atomic no-replace rename unavailable")
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(parent_fd,os.fsencode(source_name),parent_fd,os.fsencode(destination_name),flag):
        code=ctypes.get_errno()
        if code==errno.EEXIST:raise FileExistsError(destination_name)
        raise OSError(code,os.strerror(code),destination_name)
    os.fsync(parent_fd)

def _publish_exclusive(source,destination):
    source=Path(source);destination=Path(destination)
    if source.parent!=destination.parent:raise ValueError("publish parent mismatch")
    fd=os.open(source.parent,os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0))
    try:_publish_exclusive_at(fd,source.name,destination.name)
    finally:os.close(fd)

def _output_parent(root,output):
    requested=Path(output)
    if ".." in requested.parts:raise ValueError("unsafe output path")
    raw=requested if requested.is_absolute() else root/requested
    out=Path(os.path.abspath(raw))
    try:relative=out.relative_to(root)
    except ValueError as exc:raise ValueError("unsafe output path") from exc
    allowed=root/C.EXPERIMENT_ROOT;official=root/C.OFFICIAL_ARTIFACT
    if out!=official and not (out!=allowed and out.is_relative_to(allowed)):
        raise ValueError("unsafe output path")
    flags=os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(root,flags)
    try:
        try:
            for part in relative.parts[:-1]:
                child=os.open(part,flags,dir_fd=fd);os.close(fd);fd=child
        except OSError as exc:
            raise ValueError("unsafe output parent") from exc
        try:os.stat(relative.parts[-1],dir_fd=fd,follow_symlinks=False)
        except FileNotFoundError:pass
        else:raise FileExistsError(out)
        return out,fd
    except Exception:
        os.close(fd);raise

def _write_file_at(directory_fd,name,raw):
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(name,flags,0o644,dir_fd=directory_fd)
    try:
        view=memoryview(raw)
        while view:
            written=os.write(fd,view)
            if written<=0:raise OSError("short artifact write")
            view=view[written:]
        os.fsync(fd)
    finally:os.close(fd)

def _replace_file_at(directory_fd,name,raw):
    temporary=f".{name}-{secrets.token_hex(8)}"
    try:
        _write_file_at(directory_fd,temporary,raw)
        os.replace(temporary,name,src_dir_fd=directory_fd,dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:os.unlink(temporary,dir_fd=directory_fd)
        except FileNotFoundError:pass

def _remove_stage_at(parent_fd,name,identity):
    try:named=os.stat(name,dir_fd=parent_fd,follow_symlinks=False)
    except FileNotFoundError:return
    if (named.st_dev,named.st_ino)!=identity or not stat.S_ISDIR(named.st_mode):return
    flags=os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0)
    directory_fd=os.open(name,flags,dir_fd=parent_fd)
    try:
        for child in os.listdir(directory_fd):os.unlink(child,dir_fd=directory_fd)
    finally:os.close(directory_fd)
    try:os.rmdir(name,dir_fd=parent_fd)
    except FileNotFoundError:pass

def export_artifact(root,output):
    from tools import verify_rom_task_callback_078e38_closure as independent_verifier

    root=Path(root).resolve(strict=True);out,parent_fd=_output_parent(root,output)
    payload=build_payload(root);raw=_canonical(payload);relative=out.relative_to(root).as_posix()
    implementation={k:{"path":p.as_posix(),"sha256":_sha(_read_repo_file(root,p))} for k,p in C.IMPLEMENTATION_PATHS.items()}
    command=["python3","tools/verify_rom_task_callback_078e38_closure.py","--root",".","--artifact",relative]
    base={"schema":"git-artifact-promotion-v1","artifact_schema":C.SCHEMA,
          "files":{C.PAYLOAD_NAME:{"size":len(raw),"sha256":_sha(raw)}},
          "summary":C.METRICS|{"promotion_bytes":778,"claim_count":16,"unknown_hole_bytes":10},
          "implementation":implementation,
          "producer":{"command":["python3","tools/export_rom_task_callback_078e38_closure.py","--root",".","--output",relative]}}
    candidate={**base,"artifact_status":"candidate","verifier":{"command":command,"exit_code":None}}
    stage_name=f".{out.name}-{secrets.token_hex(12)}";stage_fd=None;stage_identity=None;published=False
    try:
        os.mkdir(stage_name,0o700,dir_fd=parent_fd)
        named=os.stat(stage_name,dir_fd=parent_fd,follow_symlinks=False)
        stage_identity=(named.st_dev,named.st_ino)
        flags=os.O_RDONLY|os.O_DIRECTORY|getattr(os,"O_NOFOLLOW",0)
        stage_fd=os.open(stage_name,flags,dir_fd=parent_fd)
        opened=os.fstat(stage_fd)
        if (opened.st_dev,opened.st_ino)!=stage_identity:raise ValueError("staging identity changed")
        _write_file_at(stage_fd,C.PAYLOAD_NAME,raw)
        _write_file_at(stage_fd,C.MANIFEST_NAME,_canonical(candidate))
        os.fsync(stage_fd);os.fsync(parent_fd)
        stage_path=out.parent/stage_name
        report=independent_verifier.verify_artifact(root,stage_path,intended_artifact=out)
        if not report.get("verified") or not report.get("contract_ok"):
            raise ValueError(f"independent verifier rejected candidate: {report.get('errors')}")
        # Publish only the candidate first.  The held stage_fd is the authority:
        # an attacker swapping stage_name before rename is detected before the
        # accepted receipt is ever written.
        _publish_exclusive_at(parent_fd,stage_name,out.name);published=True
        named=os.stat(out.name,dir_fd=parent_fd,follow_symlinks=False)
        published_identity=(named.st_dev,named.st_ino)
        opened=os.fstat(stage_fd)
        if published_identity!=stage_identity or published_identity!=(opened.st_dev,opened.st_ino):
            _remove_stage_at(parent_fd,out.name,published_identity)
            raise ValueError("published artifact identity does not match verified staging")
        accepted={**base,"artifact_status":"accepted","verifier":{"command":command,"exit_code":0,"report":report}}
        _replace_file_at(stage_fd,C.MANIFEST_NAME,_canonical(accepted))
        final_report=independent_verifier.verify_artifact(root,out)
        if not final_report.get("verified") or not final_report.get("contract_ok"):
            raise ValueError(f"independent verifier rejected accepted artifact: {final_report.get('errors')}")
        final_named=os.stat(out.name,dir_fd=parent_fd,follow_symlinks=False)
        final_opened=os.fstat(stage_fd)
        if (final_named.st_dev,final_named.st_ino)!=stage_identity or (final_opened.st_dev,final_opened.st_ino)!=stage_identity:
            raise ValueError("published artifact identity changed after final verification")
        stage_identity=None
    finally:
        if stage_fd is not None:os.close(stage_fd)
        if stage_identity is not None:
            _remove_stage_at(parent_fd,out.name if published else stage_name,stage_identity)
        os.close(parent_fd)
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=Path("."));p.add_argument("--output",type=Path,default=C.OFFICIAL_ARTIFACT);a=p.parse_args();export_artifact(a.root,a.output);return 0
if __name__=="__main__":raise SystemExit(main())
