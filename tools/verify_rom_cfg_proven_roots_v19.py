#!/usr/bin/env python3
"""Independently rebuild and verify the dependency-gated CFG v19 packet."""

from __future__ import annotations

import argparse, bisect, gzip, hashlib, heapq, json, struct, sys
from pathlib import Path
from typing import Any

PROJECT_ROOT=Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT,PROJECT_ROOT/"tools/_vendor"):
    if str(_path) not in sys.path: sys.path.insert(0,str(_path))

from tools.rom_cfg_proven_roots_v19_contract import *
from tools.thumb_branch import decode_thumb_b,decode_thumb_bl
from tools.verify_rom_boot_interwork_continuation import _decode_thumb, _decoder_identity


def _sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def _canonical(value:object)->bytes:return (json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
def _vsha(value:object)->str:return _sha((json.dumps(value,sort_keys=True,separators=(",",":"))+"\n").encode())
def _safe(root:Path,relative:Path)->Path:
    root=root.resolve(strict=True);path=root/relative;resolved=path.resolve(strict=True)
    if not resolved.is_relative_to(root) or path.is_symlink():raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _baseline(root:Path):
    mr=_safe(root,PRECOVERAGE_DIR/MANIFEST_NAME).read_bytes();ar=_safe(root,PRECOVERAGE_DIR/"rom-byte-coverage.json.gz").read_bytes()
    expected={"compression":"gzip","sha256":PRECOVERAGE_ARCHIVE_SHA256,"size":PRECOVERAGE_ARCHIVE_SIZE,"uncompressed_sha256":PRECOVERAGE_RAW_SHA256,"uncompressed_size":PRECOVERAGE_RAW_SIZE}
    if _sha(mr)!=PRECOVERAGE_MANIFEST_SHA256 or len(ar)!=PRECOVERAGE_ARCHIVE_SIZE or _sha(ar)!=PRECOVERAGE_ARCHIVE_SHA256 or json.loads(mr)!={"files":{"rom-byte-coverage.json.gz":expected},"schema":"rom-byte-coverage-precoverage-v1"}:raise ValueError("immutable precoverage identity changed")
    raw=gzip.decompress(ar)
    if len(raw)!=PRECOVERAGE_RAW_SIZE or _sha(raw)!=PRECOVERAGE_RAW_SHA256:raise ValueError("immutable precoverage payload changed")
    coverage=json.loads(raw);summary=coverage.get("summary",{})
    if any(summary.get(k)!=v for k,v in BASELINE.items()):raise ValueError("immutable precoverage summary changed")
    segments=coverage.get("segments");starts=[];cursor=0
    if not isinstance(segments,list) or len(segments)!=BASELINE["segment_count"]:raise ValueError("precoverage segment denominator changed")
    for row in segments:
        interval=row.get("range")
        if not isinstance(interval,list) or len(interval)!=2 or interval[0]!=cursor or interval[1]<=cursor:raise ValueError("precoverage segment order changed")
        starts.append(cursor);cursor=interval[1]
    if cursor!=ROM_SIZE:raise ValueError("precoverage accounting changed")
    return {"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE},segments,starts


def _segment(segments,starts,offset):
    row=segments[bisect.bisect_right(starts,offset)-1]
    if not row["range"][0]<=offset<row["range"][1]:raise ValueError("coverage lookup failed")
    return row


def _upstream(root:Path):
    artifact=_safe(root,Path(UPSTREAM_ARTIFACT));mr=_safe(root,Path(UPSTREAM_ARTIFACT)/MANIFEST_NAME).read_bytes();pr=_safe(root,Path(UPSTREAM_ARTIFACT)/"rom-boot-interwork-continuation.json").read_bytes()
    if (len(mr),_sha(mr),len(pr),_sha(pr))!=(UPSTREAM_MANIFEST_SIZE,UPSTREAM_MANIFEST_SHA256,UPSTREAM_PAYLOAD_SIZE,UPSTREAM_PAYLOAD_SHA256):raise ValueError("upstream continuation artifact identity changed")
    manifest=json.loads(mr);payload=json.loads(pr)
    if _canonical(manifest)!=mr or _canonical(payload)!=pr:raise ValueError("upstream continuation JSON is not canonical")
    from tools.verify_rom_boot_interwork_continuation import verify_root as verify_upstream
    report=verify_upstream(root,artifact)
    if not report.get("verified") or report.get("promotion_bytes")!=94:raise ValueError("upstream independent verification failed")
    claim=next((row for row in payload.get("promotion",{}).get("claims",[]) if row.get("id")==UPSTREAM_CODE_CLAIM_ID),None)
    if claim is None or tuple(claim.get("range",()))!=UPSTREAM_CODE_RANGE or not (UPSTREAM_CODE_RANGE[0]<=PRODUCER[0] and PRODUCER[0]+4<=UPSTREAM_CODE_RANGE[1]):raise ValueError("upstream dependency claim changed")
    return {"artifact_dir":UPSTREAM_ARTIFACT,"manifest_sha256":UPSTREAM_MANIFEST_SHA256,"payload_sha256":UPSTREAM_PAYLOAD_SHA256,"verified":True,"promotion_bytes":94,"dependency_claim_id":UPSTREAM_CODE_CLAIM_ID,"dependency_code_range":list(UPSTREAM_CODE_RANGE)}


def _target(rom,offset):
    half=struct.unpack_from("<H",rom,offset)[0]
    if offset+4<=len(rom):
        target=decode_thumb_bl(offset,half,struct.unpack_from("<H",rom,offset+2)[0])
        if target is not None:return "bl",target
    target=decode_thumb_b(offset,half)
    if target is not None:return "b",target
    if half&0xF000==0xD000 and ((half>>8)&15)<14:
        disp=(half&255)<<1
        if disp&0x100:disp-=0x200
        return "bcond",offset+4+disp


def _producer(rom):
    denominator={"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"rom_range":[0,len(rom)],"stride":2,"target_file_offset":ROOT}
    if _vsha(denominator)!=PRODUCER_SCAN_DENOMINATOR_SHA256:raise ValueError("producer scan denominator changed")
    matches=[]
    for offset in range(0,len(rom)-1,2):
        branch=_target(rom,offset)
        if branch and branch[1]==ROOT:matches.append([offset,ROOT,branch[0],4 if branch[0]=="bl" else 2,rom[offset:offset+(4 if branch[0]=="bl" else 2)].hex()])
    if matches!=[[*PRODUCER[:2],PRODUCER[2],4,PRODUCER[3]]] or _vsha(matches)!=PRODUCER_VECTOR_SHA256 or _sha(rom[PRODUCER[0]:PRODUCER[0]+4])!=PRODUCER_PACKED_SHA256:raise ValueError("raw producer denominator changed")
    return {"file_offset":PRODUCER[0],"target_file_offset":ROOT,"kind":"bl","size":4,"raw_hex":PRODUCER[3],"owner_source":"validated_upstream_dependency","owner_claim_id":UPSTREAM_CODE_CLAIM_ID,"accepted_as_root_proof":True}


def _merge(rows):
    out=[]
    for start,end in sorted(rows):
        if out and start<=out[-1][1]:out[-1][1]=max(out[-1][1],end)
        else:out.append([start,end])
    return out


def _traversal(root,rom):
    _decoder_identity(root)
    from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
    engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);engine.detail=True;engine.skipdata=False
    def in_code(offset):return any(start<=offset<end for start,end in CODE_RANGES)
    pending=[ROOT];scheduled={ROOT};nodes={};outbound=[];frontier_rows=[]
    while pending:
        offset=heapq.heappop(pending)
        if offset in nodes:continue
        if not in_code(offset) or offset%2:raise ValueError("independent traversal escaped frozen code ranges")
        node=_decode_thumb(rom,offset,engine);nodes[offset]=node
        for item in node["frontiers"]:
            frontier_rows.append([offset,item["reason"]])
        for edge in node["successors"]:
            target=edge["file_offset"]
            if in_code(target):
                if target not in scheduled:scheduled.add(target);heapq.heappush(pending,target)
            elif edge["kind"]=="call_target":outbound.append(["thumb",offset,"call_target","v2","thumb",target])
            else:raise ValueError("independent traversal has an unbound outbound edge")
    code=_merge([(offset,offset+node["size"]) for offset,node in nodes.items()])
    if tuple(map(tuple,code))!=CODE_RANGES or _vsha(code)!=CODE_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in code))!=CODE_PACKED_SHA256:raise ValueError("raw code denominator changed")
    bindings=[]
    for offset,node in sorted(nodes.items()):
        if node["size"]==2:
            half=struct.unpack_from("<H",rom,offset)[0]
            if half&0xF800==0x4800:
                target=((offset+4)&~3)+(half&255)*4
                if TARGET_RANGE[0]<=target and target+4<=TARGET_RANGE[1]:bindings.append([offset,target,rom[offset:offset+2].hex(),rom[target:target+4].hex()])
    literals=_merge([(target,target+4) for target in sorted({row[1] for row in bindings})])
    if tuple(map(tuple,literals))!=LITERAL_RANGES or _vsha(literals)!=LITERAL_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in literals))!=LITERAL_PACKED_SHA256 or _vsha(bindings)!=LITERAL_BINDING_VECTOR_SHA256:raise ValueError("raw literal denominator changed")
    predecessors={offset:[] for offset in nodes}
    for offset,node in nodes.items():
        for edge in node["successors"]:
            if edge["file_offset"] in nodes:predecessors[edge["file_offset"]].append(offset)
    starts={ROOT}
    for offset,incoming in predecessors.items():
        if offset==ROOT:continue
        if len(incoming)!=1:starts.add(offset);continue
        predecessor=nodes[incoming[0]];internal=[edge for edge in predecessor["successors"] if edge["file_offset"] in nodes]
        if predecessor["flow_kind"]!="linear" or len(internal)!=1 or internal[0]["file_offset"]!=offset or predecessor["file_offset"]+predecessor["size"]!=offset:starts.add(offset)
    block_ids={};blocks=[]
    for start in sorted(starts):
        members=[];offset=start
        while offset in nodes and offset not in block_ids:
            node=nodes[offset];members.append(node);block_ids[offset]=f"block-thumb-{start:06x}";internal=[edge for edge in node["successors"] if edge["file_offset"] in nodes]
            if node["flow_kind"]!="linear" or len(internal)!=1:break
            target=internal[0]["file_offset"]
            if target in starts or target!=offset+node["size"]:break
            offset=target
        last=members[-1];end=last["file_offset"]+last["size"]
        blocks.append({"id":f"block-thumb-{start:06x}","mode":"thumb","range":[start,end],"instruction_count":len(members),"bytes_sha256":_sha(rom[start:end]),"terminator":{"file_offset":last["file_offset"],"size":last["size"],"mnemonic":last["mnemonic"],"op_str":last["op_str"],"flow_kind":last["flow_kind"],"conditional":last["conditional"]},"successors":[]})
    edges=[]
    for block in blocks:
        source=block["terminator"]["file_offset"]
        for edge in nodes[source]["successors"]:
            target=edge["file_offset"]
            if target in nodes:
                row={"kind":edge["kind"],"mode":"thumb","file_offset":target,"block_id":block_ids[target]};block["successors"].append(row);edges.append([block["id"],edge["kind"],"thumb",target,block_ids[target]])
    block_vector=[[b["id"],b["mode"],b["range"],b["instruction_count"],b["bytes_sha256"],[b["terminator"][k] for k in ("file_offset","size","mnemonic","op_str","flow_kind","conditional")],sorted([[s["mode"],s["file_offset"],s["kind"],s["block_id"]] for s in b["successors"]])] for b in blocks]
    edges.sort(key=lambda row:(row[0],row[3],row[1]))
    outbound.sort();frontier_rows.sort();opaque=[[row[1],row[5]] for row in outbound]
    if _vsha(block_vector)!=BLOCK_VECTOR_SHA256 or _vsha(edges)!=INTERNAL_EDGE_VECTOR_SHA256 or _vsha(outbound)!=OUTBOUND_VECTOR_SHA256 or _vsha(frontier_rows)!=FRONTIER_VECTOR_SHA256:raise ValueError("independent CFG vector identity changed")
    metrics={"instruction_count":len(nodes),"instruction_bytes":sum(b-a for a,b in code),"basic_block_count":len(blocks),"decode_reject_count":0,"baseline_call_edge_count":len(outbound),"frontier_count":len(frontier_rows),"unique_literal_word_count":len({row[1] for row in bindings}),"literal_reference_count":len(bindings),"literal_bytes":sum(b-a for a,b in literals)}
    if metrics!=METRICS or tuple(map(tuple,frontier_rows))!=FRONTIERS or tuple(map(tuple,opaque))!=OPAQUE_CALLS:raise ValueError("raw target CFG boundary changed")
    union=_merge(code+literals)
    if tuple(map(tuple,union))!=UNION_RANGES or _vsha(union)!=UNION_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in union))!=UNION_PACKED_SHA256 or _vsha([list(x) for x in HOLES])!=HOLE_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in HOLES))!=HOLE_PACKED_SHA256:raise ValueError("raw union/hole denominator changed")
    return {**metrics,"frontiers":frontier_rows,"opaque_baseline_calls":opaque,"literal_binding_vector_sha256":_vsha(bindings)},code,literals,union


def _implementation(root):return {"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},**{f"{k}_sha256":_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}
def _frozen_baseline_entry(root:Path,target:int)->dict[str,Any]:
    mr=_safe(root,V2_ARTIFACT/MANIFEST_NAME).read_bytes();pr=_safe(root,V2_ARTIFACT/V2_PAYLOAD_NAME).read_bytes()
    if (len(mr),_sha(mr),len(pr),_sha(pr))!=(V2_MANIFEST_SIZE,V2_MANIFEST_SHA256,V2_PAYLOAD_SIZE,V2_PAYLOAD_SHA256):raise ValueError("frozen v2 baseline identity changed")
    manifest=json.loads(mr);payload=json.loads(pr)
    if manifest.get("artifact_schema")!="rom-cfg-inventory-v2" or manifest.get("files",{}).get(V2_PAYLOAD_NAME)!={"sha256":V2_PAYLOAD_SHA256,"size":V2_PAYLOAD_SIZE} or payload.get("schema")!="rom-cfg-inventory-v2" or payload.get("rom",{}).get("sha256")!=ROM_SHA256:raise ValueError("frozen v2 baseline contract changed")
    matches=[row for row in payload.get("blocks",[]) if row.get("range",[None])[0]==target]
    if len(matches)!=1:raise ValueError("opaque target is not a unique frozen baseline block entry")
    row=matches[0];owner={"artifact":V2_ARTIFACT.as_posix(),"block_id":row.get("id"),"mode":row.get("mode"),"range":row.get("range"),"bytes_sha256":row.get("bytes_sha256")}
    if owner!=OPAQUE_BASELINE_ENTRY:raise ValueError("opaque frozen baseline owner changed")
    return owner
def _failure(error):return {"schema":VERIFY_SCHEMA,"verified":False,"errors":[str(error)],"promotion_bytes":0,"preserved_unknown_gap_count":len(HOLES)}


def verify_root(root:Path,artifact:Path,*,expected_receipt_path:Path|None=None)->dict[str,Any]:
    try:
        root=root.resolve(strict=True);artifact=(artifact if artifact.is_absolute() else root/artifact).absolute()
        if artifact.is_symlink() or not artifact.is_dir() or {p.name for p in artifact.iterdir()}!={PAYLOAD_NAME,MANIFEST_NAME}:raise ValueError("artifact file set changed")
        pr=(artifact/PAYLOAD_NAME).read_bytes();mr=(artifact/MANIFEST_NAME).read_bytes();payload=json.loads(pr);manifest=json.loads(mr)
        if _canonical(payload)!=pr or _canonical(manifest)!=mr:raise ValueError("noncanonical JSON")
        rom=_safe(root,ROM_PATH).read_bytes()
        if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256:raise ValueError("ROM identity changed")
        baseline,segments,starts=_baseline(root);upstream=_upstream(root);producer=_producer(rom);denominator,code,literals,union=_traversal(root,rom);denominator["opaque_baseline_entry"]=_frozen_baseline_entry(root,0x063604)
        for start,end in code+literals:
            cursor=start
            while cursor<end:
                owner=_segment(segments,starts,cursor)
                if owner.get("primary_class")!="unknown":raise ValueError("target promotion escaped immutable baseline unknown")
                cursor=min(end,owner["range"][1])
        claims=[{"id":f"cfg-v19-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,rows in (("reachable_thumb_code",code),("consumed_literal_words",literals)) for i,(a,b) in enumerate(rows,1)]
        promotion={"promotion_batch":SCHEMA,"primary_class":"armv4t_cfg_proven_roots_v19","claim_kind":"armv4t_cfg_proven_roots_v19_exact_bytes","target_range":list(TARGET_RANGE),"code_ranges":code,"literal_ranges":literals,"union_ranges":union,"preserved_unknown_gaps":[list(x) for x in HOLES],"code_bytes":1600,"literal_bytes":60,"promotion_bytes":1660,"preserved_unknown_bytes":12,"claims":claims}
        expected={"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"precoverage":baseline,"upstream_continuation_artifact":upstream,"dependency_dag":{"edges":[["immutable_precoverage","boot_interwork_continuation"],["boot_interwork_continuation","cfg_proven_roots_v19"]],"cycle_free":True,"atomic_projection_required":True},"root":{"file_offset":ROOT,"entry_sha256":ROOT_ENTRY_SHA256},"accepted_producers":[producer],"target_local_denominator":denominator,"promotion":promotion,"coverage_projection":{"baseline_unknown_bytes":BASELINE["unknown_bytes"],"dependency_promoted_bytes":94,"target_promoted_bytes":1660,"atomic_remaining_unknown_bytes":BASELINE["unknown_bytes"]-1754},"implementation":_implementation(root),"scope":{"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"producer_owner_is_validated_dependency_overlay":True,"natural_runtime_reachability":False,"target_outside_subtree_classification":False,"alignment_gap_classification":False}}
        if payload!=expected:raise ValueError("payload differs from independent raw rebuild")
        for key in ("rom","precoverage","upstream_continuation_artifact","dependency_dag","implementation","promotion","coverage_projection","scope"):
            if manifest.get(key)!=payload.get(key):raise ValueError(f"manifest {key} projection changed")
        if manifest.get("files",{}).get(PAYLOAD_NAME)!={"sha256":_sha(pr),"size":len(pr)}:raise ValueError("manifest payload binding changed")
        receipt=expected_receipt_path.absolute() if expected_receipt_path is not None else artifact;rel=receipt.relative_to(root).as_posix();export_cmd=["python3","-I","-S","tools/export_rom_cfg_proven_roots_v19.py","--root",".","--output",rel];verify_cmd=["python3","-I","-S","tools/verify_rom_cfg_proven_roots_v19.py","--root",".","--artifact",rel]
        if manifest.get("schema")!="git-artifact-promotion-v1" or manifest.get("artifact_schema")!=SCHEMA or manifest.get("producer",{}).get("command")!=export_cmd or manifest.get("verifier",{}).get("command")!=verify_cmd:raise ValueError("manifest command contract changed")
        success={"schema":VERIFY_SCHEMA,"verified":True,"errors":[],"rom_sha256":ROM_SHA256,"precoverage_sha256":PRECOVERAGE_RAW_SHA256,"upstream_manifest_sha256":UPSTREAM_MANIFEST_SHA256,"root_count":1,"accepted_producer_count":1,"instruction_count":798,"code_bytes":1600,"literal_word_count":15,"literal_bytes":60,"promotion_bytes":1660,"preserved_unknown_gap_count":6}
        if manifest.get("artifact_status")=="candidate":
            if manifest["verifier"].get("exit_code") is not None or "report" in manifest["verifier"]:raise ValueError("candidate receipt changed")
        elif manifest.get("artifact_status")=="accepted":
            report=manifest["verifier"].get("report",{})
            if manifest["verifier"].get("exit_code")!=0 or report!=success:raise ValueError("accepted receipt changed")
        else:raise ValueError("artifact status changed")
        return success
    except Exception as error:return _failure(error)


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--root",type=Path,required=True);parser.add_argument("--artifact",type=Path,required=True);args=parser.parse_args();report=verify_root(args.root,args.artifact);print(json.dumps(report,sort_keys=True));return 0 if report["verified"] else 1


if __name__=="__main__":raise SystemExit(main())
