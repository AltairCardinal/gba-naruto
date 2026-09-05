#!/usr/bin/env python3
"""Independently verify proven-roots-v1 consumed literal words."""

from __future__ import annotations
import argparse, bisect, hashlib, json, struct
from pathlib import Path
from typing import Any

ROM_PATH=Path("rom/base.gba"); ROM_SIZE=6_291_456; ROM_SHA256="1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_DIR=Path("artifacts/rom-cfg-proven-roots-v1"); SOURCE_MANIFEST=SOURCE_DIR/"manifest.json"; SOURCE_PAYLOAD=SOURCE_DIR/"rom-cfg-proven-roots.json"
SOURCE_EXPORTER=Path("tools/export_rom_cfg_proven_roots.py"); SOURCE_VERIFIER=Path("tools/verify_rom_cfg_proven_roots.py"); SOURCE_TEST=Path("tests/test_export_rom_cfg_proven_roots.py")
COVERAGE_PATH=Path("sequel/rom-byte-coverage.json"); PAYLOAD_NAME="rom-cfg-v1-consumed-literals.json"
CONTRACT_SHA256="5d2cb670f89716be222c3e49773241de4af9555131577c11967632138eed15c2"
SOURCE_CLASS="armv4t_cfg_proven_roots_reachable_thumb_code"; PRIMARY_CLASS="armv4t_cfg_v1_consumed_literal_word"; CLAIM_KIND="armv4t_cfg_v1_consumed_literal_word_bytes"; PROMOTION_BATCH="rom-cfg-v1-consumed-literals-v1"
IDENTITIES={SOURCE_MANIFEST:"ea1230fe24cf111a91044c059468a1467e46c471363780b23c2a0311bab8644a",SOURCE_PAYLOAD:"7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54",SOURCE_EXPORTER:"89b91383f4cd2aa8d078042c2f7f64678f9ece15c2ac3288b3edefacf1ccb2e9",SOURCE_VERIFIER:"693d9381f429346376a6400bea20025ca0c56e1e68d0bf3164b070ea722aa4d7",SOURCE_TEST:"4a50d9a883d51eb2e292fd320ab1c8f9ae06540f225b08f22bd7915d19abbfa3",COVERAGE_PATH:"7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a"}
EXPECTED={"root_count":2,"frontier_count":28,"thumb_block_count":1203,"thumb_instruction_count":6166,"thumb_instruction_bytes":12966,"source_instruction_count":398,"unique_target_word_count":349,"target_bytes":1396,"merged_target_range_count":108,"thumb_block_denominator_sha256":"9981574883cfcd5bc3140b2f6675250f90f76f4bd17fb54d37d6cf81ace0debf","source_vector_sha256":"13a39f875640e0fabc063ba1808dc2ee76a1aac7a0eb32028e0bf190cd1c669e","source_offset_vector_sha256":"6809cabbe715dea3fa3e1b34a8df519c2ba42a61bbaa07c9ad58a002068a77e8","target_vector_sha256":"6d27dae19472da3af537eae608bef2452cdcb7d08c5afaa56ca88faa0a36eb39","target_offset_vector_sha256":"40afcc71bf1c027e0f9e8e9b2c2f6390c65fa88587c1548411e4b596b8703512","range_vector_sha256":"3e11c9a40b7a747314bd2478501ef830e1d4f38a5cca64c4423f1a85041923a1","packed_target_bytes_sha256":"d897ef21cc05a36da5ec60038dacda0efd9e2601c8ddfe49167a0091d79b8926"}
BASELINE={"classified_bytes":6127684,"unknown_bytes":163772,"claim_count":14720,"segment_count":16693}
PROJECTION={"classified_bytes":6129080,"unknown_bytes":162376,"claim_count":14828,"segment_count":16750,"delta":{"classified_bytes":1396,"unknown_bytes":-1396,"claim_count":108,"segment_count":57}}
NON_CLAIMS=["No v2, v6, other proven-roots, ARM or non-PC-relative load source is included.","No traversal is expanded and none of the 28 frontiers is resolved.","Only the 349 exact consumed words are promoted; adjacent unknown bytes remain unknown.","Loaded values receive no business, pointer, table, resource, editing, relocation, padding, or free-space meaning."]

def _sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def _canonical(value:Any)->bytes:return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _thumb_instruction_width(data:bytes,offset:int,end:int)->int:
    if offset<0 or offset+2>end or end>len(data):raise ValueError("Thumb instruction boundary escaped block")
    first=struct.unpack_from("<H",data,offset)[0]
    if first&0xF800==0xF000:
        if offset+4>end:raise ValueError("truncated Thumb BL instruction")
        if struct.unpack_from("<H",data,offset+2)[0]&0xF800==0xF800:return 4
    return 2
def _decode_ldr_literal_target(offset:int,halfword:int)->int:
    if halfword&0xF800!=0x4800:raise ValueError("not Thumb LDR-literal")
    return ((offset+4)&~3)+(halfword&0xFF)*4
def _bound(root:Path,relative:Path)->bytes:
    data=(root/relative).read_bytes()
    if _sha(data)!=IDENTITIES[relative]:raise ValueError(f"bound input identity changed: {relative}")
    return data

def _inputs(root:Path):
    rom=(root/ROM_PATH).read_bytes()
    if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256:raise ValueError("base ROM identity changed")
    manifest=json.loads(_bound(root,SOURCE_MANIFEST)); source=json.loads(_bound(root,SOURCE_PAYLOAD))
    for path in (SOURCE_EXPORTER,SOURCE_VERIFIER,SOURCE_TEST):_bound(root,path)
    coverage_bytes=(root/COVERAGE_PATH).read_bytes();coverage=json.loads(coverage_bytes)
    if manifest.get("artifact_schema")!="rom-cfg-proven-roots-v1" or source.get("schema")!="rom-cfg-proven-roots-v1":raise ValueError("source schema changed")
    extension=source.get("extension",{})
    if len(source.get("roots",[]))!=EXPECTED["root_count"] or len(extension.get("frontiers",[]))!=EXPECTED["frontier_count"]:raise ValueError("source denominator changed")
    baseline_mode=_sha(coverage_bytes)==IDENTITIES[COVERAGE_PATH]
    if coverage.get("schema")!="rom-byte-coverage-v1":raise ValueError("coverage schema changed")
    if baseline_mode and any(coverage.get("summary",{}).get(k)!=v for k,v in BASELINE.items()):raise ValueError("coverage baseline changed")
    segments=coverage.get("segments")
    if not isinstance(segments,list) or (baseline_mode and len(segments)!=BASELINE["segment_count"]):raise ValueError("coverage denominator changed")
    starts=[];cursor=0
    for i,s in enumerate(segments):
        r=s.get("range")
        if not isinstance(r,list) or len(r)!=2 or r[0]!=cursor or not isinstance(r[1],int) or r[1]<=cursor:raise ValueError(f"coverage segment {i} changed")
        starts.append(cursor);cursor=r[1]
    if cursor!=ROM_SIZE:raise ValueError("coverage denominator changed")
    def segment_at(offset:int):return segments[bisect.bisect_right(starts,offset)-1]
    return rom,source,segment_at,baseline_mode

def _rebuild(root:Path)->dict[str,Any]:
    rom,source,segment_at,baseline_mode=_inputs(root);blocks=[b for b in source["extension"]["blocks"] if b.get("mode")=="thumb"]
    if len(blocks)!=EXPECTED["thumb_block_count"]:raise ValueError("Thumb block denominator changed")
    block_rows=[{"id":b.get("id"),"range":b.get("range"),"instruction_count":b.get("instruction_count"),"bytes_sha256":b.get("bytes_sha256")} for b in blocks]
    if _sha(_canonical(block_rows))!=EXPECTED["thumb_block_denominator_sha256"]:raise ValueError("Thumb block denominator changed")
    sources=[];target_sources={};ic=ib=0;previous_end=-1
    for block in blocks:
        start,end=block.get("range",[None,None])
        if not isinstance(start,int) or not isinstance(end,int) or start<previous_end or not 0<=start<end<=len(rom):raise ValueError("Thumb block order or range changed")
        previous_end=end
        if _sha(rom[start:end])!=block.get("bytes_sha256"):raise ValueError("Thumb block bytes changed")
        offset=start;bc=0
        while offset<end:
            width=_thumb_instruction_width(rom,offset,end);halfword=struct.unpack_from("<H",rom,offset)[0];owner=segment_at(offset)
            if width==2 and halfword&0xF800==0x4800 and owner.get("primary_class")==SOURCE_CLASS and owner["range"][0]<=offset and offset+2<=owner["range"][1]:
                target=_decode_ldr_literal_target(offset,halfword)
                if target+4<=len(rom):
                    target_owner=segment_at(target)
                    expected_target_class="unknown" if baseline_mode else PRIMARY_CLASS
                    if target_owner.get("primary_class")==expected_target_class and target_owner["range"][0]<=target and target+4<=target_owner["range"][1]:
                        sources.append({"source_file_offset":offset,"source_raw_hex":rom[offset:offset+2].hex(),"target_file_offset":target,"target_raw_hex":rom[target:target+4].hex()});target_sources.setdefault(target,[]).append(offset)
            offset+=width;bc+=1;ic+=1;ib+=width
        if offset!=end or bc!=block.get("instruction_count"):raise ValueError("Thumb instruction denominator changed")
    targets=[{"target_file_offset":t,"target_raw_hex":rom[t:t+4].hex(),"source_file_offsets":ss} for t,ss in sorted(target_sources.items())];ranges=[]
    for t in sorted(target_sources):
        if ranges and t==ranges[-1][1]:ranges[-1][1]+=4
        else:ranges.append([t,t+4])
    records=[{"range":r,"bytes_sha256":_sha(rom[r[0]:r[1]])} for r in ranges];packed=b"".join(rom[t:t+4] for t in sorted(target_sources))
    denominator={"source_instruction_count":len(sources),"unique_target_word_count":len(targets),"target_bytes":len(packed),"merged_target_range_count":len(ranges),"source_vector_sha256":_sha(_canonical(sources)),"source_offset_vector_sha256":_sha(_canonical([r["source_file_offset"] for r in sources])),"target_vector_sha256":_sha(_canonical(targets)),"target_offset_vector_sha256":_sha(_canonical(sorted(target_sources))),"range_vector_sha256":_sha(_canonical(records)),"packed_target_bytes_sha256":_sha(packed)}
    for k,v in denominator.items():
        if EXPECTED.get(k)!=v:raise ValueError(f"literal denominator changed: {k}")
    if (ic,ib)!=(EXPECTED["thumb_instruction_count"],EXPECTED["thumb_instruction_bytes"]):raise ValueError("decoded Thumb denominator changed")
    source_artifact={"path":SOURCE_DIR.as_posix(),"manifest_sha256":IDENTITIES[SOURCE_MANIFEST],"payload_sha256":IDENTITIES[SOURCE_PAYLOAD],"source_exporter_sha256":IDENTITIES[SOURCE_EXPORTER],"source_verifier_sha256":IDENTITIES[SOURCE_VERIFIER],"source_test_sha256":IDENTITIES[SOURCE_TEST]};coverage={"path":COVERAGE_PATH.as_posix(),"sha256":IDENTITIES[COVERAGE_PATH],"source_primary_class":SOURCE_CLASS,"summary":BASELINE};summary={k:denominator[k] for k in ("source_instruction_count","unique_target_word_count","target_bytes","merged_target_range_count")};scope={"frozen_v1_extension_membership_reused":True,"source_owner_restricted_to_v1_cfg":True,"target_words_complete_current_unknown":True,"cfg_traversal_expanded":False,"frontiers_resolved":False,"loaded_value_semantics_proven":False}
    return {"schema":"rom-cfg-v1-consumed-literals-v1","rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"public_contract_sha256":CONTRACT_SHA256,"source_artifact":source_artifact,"coverage_baseline":coverage,"source_denominator":{"summary":{"block_count":len(blocks),"instruction_count":ic,"instruction_bytes":ib},"thumb_block_denominator_sha256":EXPECTED["thumb_block_denominator_sha256"]},"literal_denominator":denominator,"source_to_target":sources,"target_words":targets,"promotion":{"promotion_batch":PROMOTION_BATCH,"primary_class":PRIMARY_CLASS,"claim_kind":CLAIM_KIND,"ranges":ranges,"range_records":records},"coverage_projection":PROJECTION,"summary":summary,"scope":scope,"non_claims":NON_CLAIMS}

def _artifact(path:Path):
    if path.is_symlink() or not path.is_dir():raise ValueError("artifact directory is missing or a symlink")
    members=list(path.iterdir())
    if {x.name for x in members}!={"manifest.json",PAYLOAD_NAME} or any(x.is_symlink() or not x.is_file() for x in members):raise ValueError("artifact file set changed")
    manifest=json.loads((path/"manifest.json").read_bytes());payload_bytes=(path/PAYLOAD_NAME).read_bytes();payload=json.loads(payload_bytes);record=manifest.get("files",{}).get(PAYLOAD_NAME,{})
    if record!={"sha256":_sha(payload_bytes),"size":len(payload_bytes)}:raise ValueError("payload identity does not match artifact file record")
    return manifest,payload,payload_bytes

def verify_root(root:Path,artifact:Path)->dict[str,Any]:
    root=root.resolve();artifact=artifact.absolute();manifest,payload,payload_bytes=_artifact(artifact);expected=_rebuild(root)
    if payload!=expected:raise ValueError("payload does not match independently rebuilt contract")
    expected_manifest={"schema":"git-artifact-promotion-v1","artifact_schema":"rom-cfg-v1-consumed-literals-artifact-v1","artifact_status":"accepted","payload_schema":expected["schema"],"public_contract_sha256":CONTRACT_SHA256,"rom":expected["rom"],"source_artifact":expected["source_artifact"],"coverage_baseline":expected["coverage_baseline"],"literal_denominator":expected["literal_denominator"],"promotion":expected["promotion"],"coverage_projection":expected["coverage_projection"],"summary":expected["summary"],"scope":expected["scope"],"non_claims":expected["non_claims"],"verifier":{"command":["python3","-I","-S","tools/verify_rom_cfg_v1_consumed_literals.py","--root",".","--artifact","artifacts/rom-cfg-v1-consumed-literals-v1"],"exit_code":0},"files":{PAYLOAD_NAME:{"sha256":_sha(payload_bytes),"size":len(payload_bytes)}}}
    if manifest!=expected_manifest:raise ValueError("artifact manifest does not match independently rebuilt contract")
    return {"schema":"rom-cfg-v1-consumed-literals-verification-v1","verified":True,"contract_ok":True,"artifact":{"path":artifact.as_posix(),"manifest_sha256":_sha((artifact/"manifest.json").read_bytes()),"payload_sha256":_sha(payload_bytes)},"source_denominator":{"thumb_block_count":EXPECTED["thumb_block_count"],"thumb_instruction_count":EXPECTED["thumb_instruction_count"],"thumb_instruction_bytes":EXPECTED["thumb_instruction_bytes"],"thumb_block_denominator_sha256":EXPECTED["thumb_block_denominator_sha256"]},"literal_denominator":expected["literal_denominator"],"summary":expected["summary"],"coverage_projection":PROJECTION}
def main()->int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--root",type=Path,default=Path("."));parser.add_argument("--artifact",type=Path,required=True);args=parser.parse_args();print(json.dumps(verify_root(args.root,args.artifact),indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
