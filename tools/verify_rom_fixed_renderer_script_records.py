#!/usr/bin/env python3
"""Independently verify fixed CFG-consumer renderer script records."""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any

PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))

from tools._vendor.capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from tools._vendor.capstone import arm_const
from tools.thumb_branch import decode_thumb_bl
from tools.verify_rom_training_text_script_inventory import verify_artifact as verify_training
from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory
from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3

SCHEMA="rom-fixed-renderer-script-records-v1";VERIFY_SCHEMA=f"{SCHEMA}-verification-v1"
ROM_PATH=Path("rom/base.gba");ROM_SIZE=6_291_456;ROM_SHA256="1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b";ROM_BASE=0x08000000
PAYLOAD_NAME="rom-fixed-renderer-script-records.json";MANIFEST_NAME="manifest.json"
TRAINING_DIR=Path("artifacts/rom-training-text-script-inventory-v1")
TRAINING=("af609bc3b303e2617d79cc254d3b39d67e05f3606654441613309566d23e3c0b","bc5d636d2dd6076892fbac7ba88879c964df9e819407c72d644cd10c5d9dadcb","8058c27cb313c6d32d613feb9946444932c3d9dc64fe27929489fb1af72e5305")
CFG_UPSTREAM=((Path("artifacts/rom-cfg-inventory-v2/manifest.json"),"ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"),(Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"),"b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"),(Path("tools/verify_rom_cfg_inventory.py"),"a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"),(Path("artifacts/rom-cfg-inventory-v3/manifest.json"),"6aa788611f73856e621f5c74aab544d47b034307a9dc1180f6fd8f81cb1f423b"),(Path("artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json"),"596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d"),(Path("tools/verify_rom_cfg_inventory_v3.py"),"46400e44866a93b571745f30779296cc5686889ac5d465891c648296d2dbe00a"))
INTERPRETER=(0x067158,0x06836E,"211812743de17ef5158ef63bd52deb3271c962b9119bf74f1bbd458b6bec96dd")
PARSER=(0x06626C,0x066736,"b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be")
SJIS=(0x53D644,0x53D73C,"10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1")
EXCLUDED=[0x0BC9,0x0C2E,0x0C34,0x14B4,0x15FC]
SITES=((0x6C7A2,0x0A65,0x6C7A4),(0x6C806,0x0A93,0x6C808),(0x6C888,0x175D,0x6C88A),(0x6C914,0x175D,0x6C916),(0x6C96C,0x177D,0x6C96E),(0x6C990,0x177D,0x6C992),(0x70F2C,0x0B9A,0x70F2E),(0x7122C,0x0BC9,0x7122E),(0x71260,0x0BF5,0x71262),(0x71276,0x0C2E,0x71278),(0x713F8,0x0CA4,0x71442),(0x71440,0x0CC7,0x71442),(0x714BC,0x0C34,0x714F6),(0x7158E,0x0C6C,0x715C8),(0x71614,0x12F0,0x71616),(0x716AE,0x12F0,0x716B0),(0x719F8,0x1326,0x719FA),(0x71A08,0x1356,0x71A0A),(0x71A14,0x1391,0x71A16),(0x71A24,0x13C3,0x71A26),(0x71A30,0x1428,0x71A32),(0x71A3C,0x13F3,0x71A3E),(0x71A4E,0x12FA,0x71A50),(0x71AE4,0x15FC,0x71AE6),(0x71BCA,0x1465,0x71BCC),(0x7214E,0x1495,0x72150),(0x721CC,0x1499,0x721CE),(0x721D2,0x14B4,0x721D4),(0x7C758,0x15B0,0x7C75A),(0x7C7A4,0x15BA,0x7C7A6),(0x8163C,0x1631,0x8163E),(0x81658,0x1725,0x8165A),(0x8179C,0x1725,0x817A0),(0x81944,0x1725,0x81946),(0x81A44,0x1725,0x81A46),(0x8177E,0x164F,0x81780),(0x817B0,0x172B,0x817B2),(0x81880,0x1671,0x81882),(0x81928,0x16A1,0x8192A),(0x819E0,0x16C3,0x819E2),(0x81A3E,0x16EE,0x81A40))
RECORDS=((0x0A65,0x0A93,[1,5,4,12,3,4,0]),(0x0A93,0x0ABB,[1,5,4,12,3,4,0]),(0x0B9A,0x0BC9,[1,1,1,1,5,0]),(0x0BF5,0x0C2E,[1,5,0]),(0x0C6C,0x0CA4,[1,5,4,12,3,0]),(0x0CA4,0x0CC7,[1,5,4,12,3,0]),(0x0CC7,0x0CEA,[1,5,4,12,3,0]),(0x12F0,0x12FA,[3,3,3,3,4,0]),(0x12FA,0x1326,[1,5,4,12,3,4,0]),(0x1326,0x1356,[1,5,4,12,3,4,0]),(0x1356,0x1391,[1,5,4,12,3,4,0]),(0x1391,0x13C3,[1,5,4,12,3,4,0]),(0x13C3,0x13F3,[1,5,4,12,3,4,0]),(0x13F3,0x1428,[1,5,4,12,3,4,0]),(0x1428,0x1465,[1,5,4,12,3,4,0]),(0x1465,0x1495,[1,5,0]),(0x1495,0x1499,[3,4,0]),(0x1499,0x14B4,[1,5,0]),(0x15B0,0x15BA,[1,3,0]),(0x15BA,0x15C4,[3,1,0]),(0x1631,0x164F,[1,5,0]),(0x164F,0x1671,[1,5,0]),(0x1671,0x16A1,[1,5,0]),(0x16A1,0x16C3,[1,5,0]),(0x16C3,0x16EE,[1,5,0]),(0x16EE,0x1725,[1,5,0]),(0x1725,0x172B,[4,12,3,4,0]),(0x172B,0x175D,[1,5,0]),(0x175D,0x177D,[1,5,4,0]),(0x177D,0x1781,[3,4,0]))
MERGED=[[0x0A65,0x0ABB],[0x0B9A,0x0BC9],[0x0BF5,0x0C2E],[0x0C6C,0x0CEA],[0x12F0,0x14B4],[0x15B0,0x15C4],[0x1631,0x1781]]
PRIMARY_CLASS="fixed_cfg_consumer_renderer_command_script";CLAIM_KIND="fixed_cfg_consumer_renderer_command_script_bytes"

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
    if not candidate.resolve(strict=True).is_relative_to(root.resolve(strict=True)):raise ValueError("artifact escapes root")
    cursor=root.resolve(strict=True)
    for part in candidate.relative_to(root).parts:
        cursor/=part
        if cursor.is_symlink():raise ValueError("artifact symlink ancestor")
    return cursor.resolve(strict=True)

def _renderer_end(data:bytes,start:int,limit:int,ranges:tuple[tuple[int,int],...])->int:
    cursor=start
    while cursor<limit:
        first=data[cursor]
        if first==0:return cursor+1
        if first==1:width=2
        elif first==2:width=3
        elif 0x80<=first<=0x9f:width=2
        elif first>=0xa0:
            if cursor+1>=limit:raise ValueError("truncated renderer pair")
            code=first<<8|data[cursor+1];width=2 if any(a<=code<b for a,b in ranges) else 1
        else:width=1
        if cursor+width>limit:raise ValueError("truncated renderer token")
        cursor+=width
    raise ValueError("renderer terminator missing")
def _parse(data:bytes,start:int,limit:int,ranges:tuple[tuple[int,int],...])->tuple[int,list[int]]:
    cursor=start;opcodes=[];widths={1:7,3:2,4:1,12:1}
    while cursor<limit:
        opcode=data[cursor];opcodes.append(opcode)
        if opcode==0:cursor+=1;return cursor,opcodes
        if opcode in widths:cursor+=widths[opcode]
        elif opcode==5:
            if cursor+2>limit:raise ValueError("truncated renderer command")
            cursor=_renderer_end(data,cursor+2,limit,ranges)
        else:raise ValueError(f"unsupported opcode {opcode}")
        if cursor>limit:raise ValueError("truncated fixed command")
    raise ValueError("record terminator missing")

def _upstream(root:Path)->dict[str,Any]:
    paths=(TRAINING_DIR/MANIFEST_NAME,TRAINING_DIR/"training-text-script-inventory.json",Path("tools/verify_rom_training_text_script_inventory.py"))
    if tuple(_sha(_safe_file(root,path).read_bytes()) for path in paths)!=TRAINING:raise ValueError("training upstream identity changed")
    report=verify_training(root,(root/TRAINING_DIR).resolve(strict=True))
    if report.get("verified") is not True:raise ValueError("training upstream verification failed")
    return {"verified":True,"manifest_sha256":TRAINING[0],"payload_sha256":TRAINING[1],"verifier_sha256":TRAINING[2]}

@lru_cache(maxsize=1)
def _cfg_blocks(root:Path)->tuple[list[dict[str,Any]],dict[str,Any]]:
    for path,digest in CFG_UPSTREAM:
        if _sha(_safe_file(root,path).read_bytes())!=digest:raise ValueError("canonical CFG upstream identity changed")
    v2_dir=(root/"artifacts/rom-cfg-inventory-v2").resolve(strict=True);v3_dir=(root/"artifacts/rom-cfg-inventory-v3").resolve(strict=True)
    if not verify_rom_cfg_inventory(root,v2_dir).get("verified"):raise ValueError("canonical CFG v2 verification failed")
    if not verify_rom_cfg_inventory_v3(root,v3_dir).get("verified"):raise ValueError("canonical CFG v3 verification failed")
    v2=json.loads(_safe_file(root,CFG_UPSTREAM[1][0]).read_bytes());v3=json.loads(_safe_file(root,CFG_UPSTREAM[4][0]).read_bytes())
    return list(v2["blocks"])+list(v3["extension"]["blocks"]),{"verified":True,"files":{p.as_posix():d for p,d in CFG_UPSTREAM},"v2_graph_denominator_sha256":v2["graph_denominator_sha256"],"v3_graph_denominator_sha256":v3["graph_denominator_sha256"]}

def _prove_parameter_flow(rom:bytes,site:int,source_register:int)->int:
    engine=Cs(CS_ARCH_ARM,CS_MODE_THUMB);engine.detail=True
    regs={i:getattr(arm_const,f"ARM_REG_R{i}") for i in range(8)};work=[(site+2,frozenset({regs[source_register]}))];seen=set();successes=set()
    while work:
        address,taint=work.pop();state=(address,taint)
        if state in seen:continue
        seen.add(state)
        if not site<address<=site+0x100:raise ValueError("consumer parameter flow left bounded window")
        decoded=tuple(engine.disasm(rom[address:address+4],ROM_BASE+address,count=1))
        if len(decoded)!=1 or decoded[0].address!=ROM_BASE+address:raise ValueError("consumer parameter flow decode failed")
        insn=decoded[0];nxt=address+insn.size
        if insn.id==arm_const.ARM_INS_BL:
            target=decode_thumb_bl(address,*struct.unpack_from("<HH",rom,address))
            if target==INTERPRETER[0]:
                if regs[0] not in taint:raise ValueError("consumer literal does not reach interpreter r0")
                successes.add(address);continue
            taint=frozenset(reg for reg in taint if reg not in {regs[i] for i in range(4)});work.append((nxt,taint));continue
        if insn.id==arm_const.ARM_INS_B:
            half=struct.unpack_from("<H",rom,address)[0];target=int(insn.operands[0].imm)-ROM_BASE
            if half&0xf800==0xe000:work.append((target,taint));continue
            if half&0xf000==0xd000 and (half>>8)&15<14:work.extend(((target,taint),(nxt,taint)));continue
            raise ValueError("unsupported consumer branch")
        reads,writes=insn.regs_access();next_taint=set(taint)-set(writes)
        if insn.id in (arm_const.ARM_INS_MOV,arm_const.ARM_INS_ADD) and writes and any(r in taint for r in reads):
            immediates=[op.imm for op in insn.operands if op.type==arm_const.ARM_OP_IMM]
            if not immediates or all(value==0 for value in immediates):next_taint.update(writes)
        work.append((nxt,frozenset(next_taint)))
    if len(successes)!=1:raise ValueError("consumer parameter flow has no unique interpreter sink")
    return successes.pop()

def _rebuild(rom:bytes,root:Path|None=None)->dict[str,Any]:
    if root is None:root=PROJECT_ROOT
    blocks,cfg_upstream=_cfg_blocks(root);discovered=[]
    for block in blocks:
        if block.get("mode")!="thumb":continue
        start,end=block["range"]
        for site in range(start,end,2):
            half=struct.unpack_from("<H",rom,site)[0]
            if half&0xf800!=0x4800:continue
            literal=((site+4)&~3)+(half&255)*4;word=struct.unpack_from("<I",rom,literal)[0]
            if ROM_BASE<=word<ROM_BASE+0x1cd0:discovered.append((site,word-ROM_BASE,literal,(half>>8)&7))
    if len(discovered)!=41 or len({row[0] for row in discovered})!=41:raise ValueError("canonical CFG renderer-literal denominator changed")
    rows=[]
    for site,target,literal,register in sorted(discovered):
        callsite=_prove_parameter_flow(rom,site,register)
        rows.append({"site":site,"target":target,"literal_word":literal,"interpreter_callsite":callsite,"path_sha256":_sha(rom[site:callsite+4]),"accepted":target not in EXCLUDED})
    vector=[[r["site"],r["target"],r["interpreter_callsite"],r["path_sha256"]] for r in rows]
    if _sha(json.dumps(vector,separators=(",",":")).encode())!="279d25527c69e1cb558b1aacfd3b548a7cdf24d98e12a6366e459520aca83909":raise ValueError("consumer path vector changed")
    for start,end,digest in (INTERPRETER,PARSER,SJIS):
        if _sha(rom[start:end])!=digest:raise ValueError("interpreter semantics changed" if start==INTERPRETER[0] else "parser semantics changed")
    ranges=tuple((int.from_bytes(rom[SJIS[0]+i*8:SJIS[0]+i*8+2],"little"),0) for i in range(31));ranges=tuple((a,a+rom[SJIS[0]+i*8+2]) for i,(a,_) in enumerate(ranges))
    items=[]
    for start,end,opcodes in RECORDS:
        parsed_end,parsed_opcodes=_parse(rom,start,0x1cd0,ranges)
        if parsed_end!=end or parsed_opcodes!=opcodes:raise ValueError("record parser denominator changed")
        items.append({"range":[start,end],"opcode_sequence":opcodes,"bytes_sha256":_sha(rom[start:end])})
    rv=[[a,b] for a,b,_ in RECORDS];packed=b"".join(rom[a:b] for a,b,_ in RECORDS)
    if _sha(json.dumps(rv,separators=(",",":")).encode())!="6fa95454d60ccbfa2680dc286114190f52a9226b72c82e368cbae02bc7ad8df3" or _sha(packed)!="badb4ac6c49ea2250909065b2deb5d19cbd8d9768c761447fef6ab92916a60b9":raise ValueError("record identity changed")
    consumers={"sites":rows,"site_count":41,"accepted_site_count":36,"excluded_site_count":5,"excluded_targets":EXCLUDED,"path_vector_sha256":"279d25527c69e1cb558b1aacfd3b548a7cdf24d98e12a6366e459520aca83909","denominator_scope":"canonical_v2_v3_cfg_pc_relative_literal_consumers"}
    records={"items":items,"record_count":30,"record_bytes":1124,"record_vector_sha256":"6fa95454d60ccbfa2680dc286114190f52a9226b72c82e368cbae02bc7ad8df3","packed_bytes_sha256":_sha(packed),"merged_ranges":MERGED,"merged_range_vector_sha256":"a781ac704199e1412224376289d705c1ed4e2766065bcb3334d1495d3297b9ce"}
    return {"upstream_cfg_contract":cfg_upstream,"consumer_denominator":consumers,"records":records}

def _expected(root:Path,rom:bytes)->dict[str,Any]:
    rebuilt=_rebuild(rom,root);claims=[{"id":f"fixed-renderer-script-{a:04x}","range":[a,b],"primary_class":PRIMARY_CLASS,"claim_kind":CLAIM_KIND,"bytes_sha256":_sha(rom[a:b])} for a,b,_ in RECORDS]
    return {"schema":SCHEMA,"rom":{"path":"rom/base.gba","size":len(rom),"sha256":ROM_SHA256},"upstream_training_contract":_upstream(root),**rebuilt,"promotion":{"claims":claims,"claim_count":30,"promotion_bytes":1124,"promotion_batch":SCHEMA,"promoted_from_primary_class":"unknown"},"scope":{"whole_rom_consumer_denominator":False,"startup_semantics":False,"opcode_7_or_8_semantics":False,"natural_runtime_reachability":False,"unicode_complete":False,"padding_or_free_space":False,"editing_or_relocation_safety":False}}

def verify_artifact(root:Path,artifact:Path)->dict[str,Any]:
    try:
        root=root.resolve(strict=True);directory=_safe_artifact(root,artifact)
        if {p.name for p in directory.iterdir()}!={PAYLOAD_NAME,MANIFEST_NAME} or any(p.is_symlink() for p in directory.iterdir()):raise ValueError("artifact file denominator changed")
        pr=(directory/PAYLOAD_NAME).read_bytes();mr=(directory/MANIFEST_NAME).read_bytes();payload=json.loads(pr);manifest=json.loads(mr)
        if pr!=_canonical(payload) or mr!=_canonical(manifest):raise ValueError("artifact JSON not canonical")
        rom=_safe_file(root,ROM_PATH).read_bytes()
        if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256:raise ValueError("ROM identity changed")
        if payload!=_expected(root,rom):raise ValueError("payload contract changed")
        relative=directory.relative_to(root).as_posix();writer="tools/"+"export_"+"rom_fixed_renderer_script_records.py";test="tests/test_"+"export_"+"rom_fixed_renderer_script_records.py"
        expected={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"accepted","files":{PAYLOAD_NAME:{"size":len(pr),"sha256":_sha(pr)}},"summary":{"consumer_site_count":41,"accepted_site_count":36,"record_count":30,"promotion_bytes":1124},"producer":{"command":["python3",writer,"--root",".","--output",relative]},"verifier":{"command":["python3","tools/verify_rom_fixed_renderer_script_records.py","--root",".","--artifact",relative]},"implementation":{"exporter_sha256":_sha(_safe_file(root,Path(writer)).read_bytes()),"verifier_sha256":_sha(_safe_file(root,Path("tools/verify_rom_fixed_renderer_script_records.py")).read_bytes()),"test_sha256":_sha(_safe_file(root,Path(test)).read_bytes())}}
        if manifest!=expected:raise ValueError("manifest contract changed")
        return {"schema":VERIFY_SCHEMA,"verified":True,"contract_ok":True,"errors":[],"consumer_site_count":41,"accepted_site_count":36,"record_count":30,"promotion_bytes":1124}
    except Exception as error:return {"schema":VERIFY_SCHEMA,"verified":False,"contract_ok":False,"errors":[str(error)]}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,default=Path("."));p.add_argument("--artifact",type=Path,required=True);a=p.parse_args();report=verify_artifact(a.root,a.artifact);print(json.dumps(report,sort_keys=True));return 0 if report["verified"] else 1
if __name__=="__main__":raise SystemExit(main())
