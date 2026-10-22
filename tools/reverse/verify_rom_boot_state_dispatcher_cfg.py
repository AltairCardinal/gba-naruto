#!/usr/bin/env python3
"""Independently verify the boot-state dispatcher CFG packet."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path
import struct
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))

from tools.thumb_branch import decode_thumb_b, decode_thumb_bl
from tools.verify_rom_boot_interwork_continuation import verify_artifact as verify_upstream
from tools._vendor.capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

SCHEMA="rom-boot-state-dispatcher-cfg-v1"; VERIFY_SCHEMA=f"{SCHEMA}-verification-v1"
ROM_PATH=Path("rom/base.gba");ROM_SIZE=6_291_456;ROM_SHA256="1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME="rom-boot-state-dispatcher-cfg.json";MANIFEST_NAME="manifest.json"
UPSTREAM=Path("artifacts/rom-boot-interwork-continuation-v1")
UPSTREAM_FILES=((UPSTREAM/MANIFEST_NAME,"beb4220307bbc0b99b58d6652bfd3f7339928d9e30b104f0fde06c7ed62d82ff"),(UPSTREAM/"rom-boot-interwork-continuation.json","43ba163ac9f8313b9579c660ab701a51006186b45f2b96247fd2e58f0c16babd"),(Path("tools/verify_rom_boot_interwork_continuation.py"),"8da8303e47e8666a9883fc411fd274ab1d8bf3651da95a4530dabd152bdcec58"))
DISPATCHER=(0x064670,0x0646D0);DISPATCHER_SHA="b825f224bf8677ace2b5936e48afcc7e3a1950ac72ed397bbdbbf1cb0af1ba51"
ROOT_SPECS=(("root_63adc",0x063ADC,0x063C34,0x063C2E),("root_63c34",0x063C34,0x063F7C,0x063F78),("root_63f7c",0x063F7C,0x0642DC,0x0642D8),("root_642dc",0x0642DC,0x064394,0x064392),("root_64394",0x064394,0x064478,0x064472))
CODE=[[408284,408382],[408404,408452],[408456,408624],[408628,408790],[408816,409320],[409336,409466],[409468,409518],[409536,409770],[409780,409836],[409840,409896],[409904,409948],[409952,410086],[410096,410152],[410156,410214],[410224,410268],[410272,410330],[410332,410382],[410404,410586],[410604,410608],[410612,410662],[410668,410688],[410692,410710],[410716,410740]]
LITERALS=[[408384,408404],[408452,408456],[408624,408628],[408792,408816],[409320,409336],[409520,409536],[409772,409780],[409836,409840],[409896,409904],[409948,409952],[410088,410096],[410152,410156],[410216,410224],[410268,410272],[410384,410404],[410588,410604],[410608,410612],[410664,410668],[410688,410692],[410712,410716],[410740,410744]]
HOLES=[[408382,408384],[408790,408792],[409466,409468],[409518,409520],[409770,409772],[410086,410088],[410214,410216],[410330,410332],[410382,410384],[410586,410588],[410662,410664],[410710,410712]]
PRODUCERS=[[0x06109A,0x064670,"bl",4,"03f0e9fa"],[0x0646B0,0x063ADC,"bl",4,"fff714fa"],[0x0646B6,0x063C34,"bl",4,"fff7bdfa"],[0x0646BC,0x063F7C,"bl",4,"fff75efc"],[0x0646C2,0x0642DC,"bl",4,"fff70bfe"],[0x0646C8,0x064394,"bl",4,"fff764fe"]]
OPAQUE=[[408410,639204],[408708,639196],[409578,400076],[409608,400000],[410552,639788],[410570,639668],[410640,639788],[410672,639668]]
CODE_SHA="317a042eb54cee46eff733c8dd19be71b73b7a5b7a3d240097a5322ed6d460e4";LITERAL_SHA="026339c45f3ec48ebefe3e194933bbd62daa792bc8b9d11ffe112e2cc56e3245";HOLE_SHA="9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0";BINDING_SHA="6dc27eb222f284bc49914ed2a3dee06ae9cb0802527a8165e00de757f7caa78a"

def _sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def _canonical(value:Any)->bytes:return (json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
def _safe_file(root:Path,relative:Path)->Path:
    base=root.resolve(strict=True);cursor=base
    for part in relative.parts:
        cursor/=part
        if cursor.is_symlink():raise ValueError("unsafe input path")
    result=cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():raise ValueError("unsafe input path")
    return result
def _safe_artifact(root:Path,artifact:Path)->Path:
    candidate=artifact if artifact.is_absolute() else root/artifact
    resolved=candidate.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):raise ValueError("artifact escapes root")
    cursor=root.resolve(strict=True)
    for part in candidate.relative_to(root).parts:
        cursor/=part
        if cursor.is_symlink():raise ValueError("artifact symlink ancestor")
    return resolved
def _packed(rom:bytes,ranges:list[list[int]])->bytes:return b"".join(rom[a:b] for a,b in ranges)
def _merge(nodes:dict[int,int])->list[list[int]]:
    out=[]
    for offset,size in sorted(nodes.items()):
        if out and offset<=out[-1][1]:out[-1][1]=max(out[-1][1],offset+size)
        else:out.append([offset,offset+size])
    return out

def _walk(rom:bytes,name:str,root:int,end:int,return_bx:int)->tuple[dict[int,int],list[list[int]]]:
    pending=[root];nodes={};external=[]
    while pending:
        offset=heapq.heappop(pending)
        if offset in nodes:continue
        if not root<=offset<end:raise ValueError("closure escaped frozen bound")
        half=struct.unpack_from("<H",rom,offset)[0]
        if offset==return_bx:
            if half!=0x4700 or rom[offset-2:offset+2].hex()!="01bc0047":raise ValueError("structured return epilogue changed")
            nodes[offset]=2;continue
        if half&0xF800==0xF000:
            target=decode_thumb_bl(offset,half,struct.unpack_from("<H",rom,offset+2)[0])
            if target is None:raise ValueError("unexpected Thumb-2 prefix")
            nodes[offset]=4;successors=[offset+4]
            if root<=target<end:successors.append(target)
            else:external.append([offset,target])
        elif half&0xF000==0xD000 and ((half>>8)&15)<14:
            delta=(half&255)<<1
            if delta&0x100:delta-=0x200
            nodes[offset]=2;successors=[offset+2,offset+4+delta]
        elif half&0xF800==0xE000:
            target=decode_thumb_b(offset,half)
            if target is None:raise ValueError("branch decode failed")
            nodes[offset]=2;successors=[target]
        elif half&0xFF00==0xBD00 or half&0xFF87==0x4700:
            raise ValueError("unexpected indirect or return frontier")
        else:nodes[offset]=2;successors=[offset+2]
        for target in successors:
            if not root<=target<end:raise ValueError("non-call edge escaped frozen bound")
            if target not in nodes:heapq.heappush(pending,target)
    return nodes,external

def _return_contract(rom:bytes,nodes:dict[int,int])->dict[str,Any]:
    aliases=sorted(offset for offset in nodes if struct.unpack_from("<H",rom,offset)[0]==0x4668)
    stores=sorted([offset,(struct.unpack_from("<H",rom,offset)[0]&255)*4] for offset in nodes if struct.unpack_from("<H",rom,offset)[0]&0xF800==0x9000)
    expected=[[0x063C7C,0],[0x063CA2,12],[0x063CCE,8],[0x063CD2,4],[0x063CF6,8],[0x063CFA,4],[0x063CFE,8],[0x063D00,4],[0x063D30,8],[0x063D36,8],[0x063D4E,4],[0x063D54,4],[0x063DCA,16],[0x063E26,16],[0x063E5E,16],[0x063ED6,12],[0x06402A,0],[0x064036,0],[0x064040,4],[0x06404C,4]]
    if aliases!=[0x063C7E] or stores!=expected:raise ValueError("structured return SP alias/store denominator changed")
    if rom[0x063C7A:0x063C88].hex()!="1a480090684619491a4a38f02afa":raise ValueError("CpuFastSet callsite changed")
    if tuple(struct.unpack_from("<III",rom,0x063CE4))!=(0xFF00FF00,0x02000A00,0x01000050):raise ValueError("CpuFastSet arguments changed")
    if rom[0x09C0DC:0x09C0E0].hex()!="0cdf7047":raise ValueError("CpuFastSet wrapper changed")
    return {"sp_alias_sites":aliases,"sp_relative_store_sites_and_offsets":stores,"saved_lr_offset_at_cpufastset":0x30,"max_direct_sp_store_offset":0x10,"cpufastset_callsite":0x063C84,"cpufastset_wrapper":0x09C0DC,"cpufastset_swi":0x0C,"source":"sp","destination":"0x02000A00","control":"0x01000050","fill_mode":True,"source_read_bytes":4,"saved_lr_slot_written":False,"cpufastset_source_only":True}

def _independent_direct_target(rom:bytes,offset:int)->tuple[int,str,int]|None:
    first=struct.unpack_from("<H",rom,offset)[0]
    if offset+4<=len(rom):
        second=struct.unpack_from("<H",rom,offset+2)[0]
        if first&0xF800==0xF000 and second&0xF800==0xF800:
            delta=((first&0x7FF)<<12)|((second&0x7FF)<<1)
            if delta&0x400000:delta-=0x800000
            return offset+4+delta,"bl",4
    if first&0xF800==0xE000:
        delta=(first&0x7FF)<<1
        if delta&0x800:delta-=0x1000
        return offset+4+delta,"b",2
    condition=(first>>8)&15
    if first&0xF000==0xD000 and condition<14:
        delta=(first&255)<<1
        if delta&0x100:delta-=0x200
        return offset+4+delta,"bcond",2
    return None

def _capstone_confirm_producers(rom:bytes,rows:list[list[Any]])->None:
    engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
    for offset,target,kind,size,_ in rows:
        decoded=list(engine.disasm(rom[offset:offset+size],0x08000000+offset,count=1))
        if len(decoded)!=1 or decoded[0].size!=size:
            raise ValueError("independent Capstone producer decode failed")
        mnemonic=decoded[0].mnemonic
        observed_kind="bl" if mnemonic=="bl" else ("b" if mnemonic=="b" else "bcond" if mnemonic.startswith("b") else None)
        try:observed_target=int(decoded[0].op_str.removeprefix("#"),16)-0x08000000
        except ValueError as error:raise ValueError("independent Capstone producer target failed") from error
        if (observed_kind,observed_target)!=(kind,target):
            raise ValueError("independent Capstone producer denominator changed")

def _upstream(root:Path)->dict[str,Any]:
    for path,digest in UPSTREAM_FILES:
        if _sha(_safe_file(root,path).read_bytes())!=digest:raise ValueError("upstream continuation identity changed")
    if verify_upstream(root,(root/UPSTREAM).resolve(strict=True)).get("verified") is not True:raise ValueError("upstream continuation verification failed")
    payload=json.loads(_safe_file(root,UPSTREAM_FILES[1][0]).read_bytes());owners=[row for row in payload["promotion"]["claims"] if row["range"][0]<=0x06109A and 0x06109E<=row["range"][1]]
    if len(owners)!=1:raise ValueError("producer source membership changed")
    return {"verified":True,"files":{p.as_posix():d for p,d in UPSTREAM_FILES},"producer_owner_claim_id":owners[0]["id"],"producer_source":0x06109A}

def _rebuild(rom:bytes,root:Path|None=None)->dict[str,Any]:
    if root is None:root=PROJECT_ROOT
    targets={row[1] for row in PRODUCERS};found=[]
    for offset in range(0,len(rom)-1,2):
        decoded=_independent_direct_target(rom,offset)
        if decoded is not None and decoded[0] in targets:
            target,kind,size=decoded;found.append([offset,target,kind,size,rom[offset:offset+size].hex()])
    if found!=PRODUCERS:raise ValueError("producer denominator changed")
    _capstone_confirm_producers(rom,found)
    raw=rom[DISPATCHER[0]:DISPATCHER[1]]
    if _sha(raw)!=DISPATCHER_SHA:raise ValueError("dispatcher identity changed")
    if rom[0x064670:0x06468E].hex()!="00b507480178002928d0072008400138052823d880000349401800688746":raise ValueError("dispatcher state/index semantics changed")
    if struct.unpack_from("<II",rom,0x064690)!=(0x03005CBC,0x08064698):raise ValueError("dispatcher literals changed")
    slots=[struct.unpack_from("<I",rom,0x064698+i*4)[0] for i in range(6)]
    if slots!=[0x080646CC,0x080646B0,0x080646B6,0x080646BC,0x080646C2,0x080646C8] or rom[0x0646CC:0x0646D0].hex()!="01bc0047":raise ValueError("dispatcher table/return changed")
    all_nodes={};opaque=[];root_rows=[]
    expected=((156,314),(397,796),(393,790),(81,162),(89,186))
    for spec,counts in zip(ROOT_SPECS,expected,strict=True):
        name,start,end,return_bx=spec
        if struct.unpack_from("<H",rom,start)[0]&0x0100==0:raise ValueError("structured return prologue changed")
        nodes,edges=_walk(rom,*spec);all_nodes.update(nodes);opaque.extend(edges)
        if (len(nodes),sum(nodes.values()))!=counts:raise ValueError("root-local denominator changed")
        root_rows.append({"name":name,"root":start,"bound":[start,end],"return_bx":return_bx,"instruction_count":counts[0],"code_bytes":counts[1],"basic_block_count":[34,120,87,23,25][len(root_rows)]})
    code=_merge(all_nodes);bindings=[]
    for offset in sorted(all_nodes):
        half=struct.unpack_from("<H",rom,offset)[0]
        if half&0xF800==0x4800:
            literal=((offset+4)&~3)+(half&255)*4;bindings.append([offset,literal,struct.unpack_from("<I",rom,literal)[0]])
    literals=[]
    for offset in sorted({row[1] for row in bindings}):
        if literals and offset<=literals[-1][1]:literals[-1][1]=max(literals[-1][1],offset+4)
        else:literals.append([offset,offset+4])
    return_contract=_return_contract(rom,all_nodes)
    if code!=CODE or literals!=LITERALS or sorted(opaque)!=OPAQUE:raise ValueError("closure denominator changed")
    if _sha(_packed(rom,code))!=CODE_SHA or _sha(_packed(rom,literals))!=LITERAL_SHA:raise ValueError("closure bytes changed")
    if _sha(json.dumps(bindings,separators=(",",":")).encode())!=BINDING_SHA:raise ValueError("literal binding denominator changed")
    if _sha(_packed(rom,HOLES))!=HOLE_SHA:raise ValueError("hole denominator changed")
    producer={"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"range":[0,len(rom)],"stride":2,"targets":sorted(targets),"matches":found,"match_count":6,"vector_sha256":_sha(json.dumps(found,separators=(",",":")).encode())}
    dispatcher={"range":list(DISPATCHER),"bytes_sha256":DISPATCHER_SHA,"state_address":"0x03005CBC","mask":7,"subtract":1,"unsigned_max":5,"table_range":[0x064698,0x0646B0],"slots":slots,"slot_count":6,"structured_return":0x0646CE}
    closure={"roots":root_rows,"root_count":5,"instruction_count":1116,"code_bytes":2248,"code_ranges":code,"literal_reference_count":49,"unique_literal_word_count":47,"literal_bytes":188,"literal_ranges":literals,"opaque_calls":sorted(opaque),"opaque_call_count":8,"structured_return_count":5,"frontier_count":0,"structured_return_contract":return_contract,"preserved_unknown_holes":HOLES,"preserved_unknown_bytes":24}
    return {"producer_denominator":producer,"dispatcher":dispatcher,"target_closure":closure}

def _expected(root:Path,rom:bytes)->dict[str,Any]:
    rebuilt=_rebuild(rom,root);claims=[]
    for kind,ranges in (("reachable_thumb_code",CODE),("consumed_literal_words",LITERALS)):
        for i,(start,end) in enumerate(ranges,1):claims.append({"id":f"boot-state-{kind}-{i:02d}-{start:06x}","range":[start,end],"claim_kind":kind,"bytes_sha256":_sha(rom[start:end])})
    claims.append({"id":"boot-state-dispatcher-064670","range":list(DISPATCHER),"claim_kind":"bounded_state_dispatcher_bytes","bytes_sha256":DISPATCHER_SHA})
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":len(rom),"sha256":ROM_SHA256},"upstream_continuation":_upstream(root),**rebuilt,"promotion":{"promotion_batch":SCHEMA,"promoted_from_primary_class":"unknown","claims":claims,"claim_count":45,"target_code_bytes":2248,"target_literal_bytes":188,"dispatcher_bytes":96,"promotion_bytes":2532},"scope":{"natural_runtime_reachability":False,"ram_state_writer_denominator":False,"opaque_callee_semantics":False,"padding_or_free_space":False,"editing_or_relocation_safety":False}}

def verify_artifact(root:Path,artifact:Path,*,expected_artifact:Path|None=None)->dict[str,Any]:
    try:
        root=root.resolve(strict=True);directory=_safe_artifact(root,artifact)
        if {p.name for p in directory.iterdir()}!={PAYLOAD_NAME,MANIFEST_NAME} or any(p.is_symlink() for p in directory.iterdir()):raise ValueError("artifact file denominator changed")
        pr=(directory/PAYLOAD_NAME).read_bytes();mr=(directory/MANIFEST_NAME).read_bytes();payload=json.loads(pr);manifest=json.loads(mr)
        if pr!=_canonical(payload) or mr!=_canonical(manifest):raise ValueError("artifact JSON not canonical")
        rom=_safe_file(root,ROM_PATH).read_bytes()
        if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256:raise ValueError("ROM identity changed")
        if payload!=_expected(root,rom):raise ValueError("payload contract changed")
        receipt=expected_artifact if expected_artifact is not None else directory
        receipt=receipt if receipt.is_absolute() else root/receipt
        relative=receipt.resolve(strict=False).relative_to(root).as_posix();exporter=Path("tools/export_rom_boot_state_dispatcher_cfg.py");verifier=Path("tools/verify_rom_boot_state_dispatcher_cfg.py");test=Path("tests/test_export_rom_boot_state_dispatcher_cfg.py")
        expected={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"accepted","files":{PAYLOAD_NAME:{"size":len(pr),"sha256":_sha(pr)}},"summary":{"root_count":5,"promotion_bytes":2532,"frontier_count":0},"producer":{"command":["python3",exporter.as_posix(),"--root",".","--output",relative]},"verifier":{"command":["python3",verifier.as_posix(),"--root",".","--artifact",relative]},"implementation":{"exporter_sha256":_sha(_safe_file(root,exporter).read_bytes()),"verifier_sha256":_sha(_safe_file(root,verifier).read_bytes()),"test_sha256":_sha(_safe_file(root,test).read_bytes())}}
        if manifest!=expected:raise ValueError("manifest contract changed")
        return {"schema":VERIFY_SCHEMA,"verified":True,"contract_ok":True,"errors":[],"promotion_bytes":2532,"frontier_count":0,"root_count":5}
    except Exception as error:return {"schema":VERIFY_SCHEMA,"verified":False,"contract_ok":False,"errors":[str(error)],"promotion_bytes":0,"frontier_count":None,"root_count":None}

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--root",type=Path,default=Path("."));parser.add_argument("--artifact",type=Path,required=True);args=parser.parse_args();report=verify_artifact(args.root,args.artifact);print(json.dumps(report,sort_keys=True));return 0 if report["verified"] else 1
if __name__=="__main__":raise SystemExit(main())
