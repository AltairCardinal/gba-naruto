#!/usr/bin/env python3
"""Independently verify the text-BG loop continuation packet."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # type: ignore


SCHEMA = "rom-text-bg-loop-continuation-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
PAYLOAD_NAME = "rom-text-bg-loop-continuation.json"
MANIFEST_NAME = "manifest.json"
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
BASELINE_SHA = "e48c8f6d0df1d3469be2336caa71f628d82a51d4e637d6df42ebded412359c36"
ROOT = 0x08ACC8
PRODUCER = 0x08B644
SOURCE_RANGE = [0x08B640, 0x08B64E]
CODE_RANGE = [0x08ACC8, 0x08ACF2]
LITERAL_RANGE = [0x08AEB4, 0x08AEC0]
CODE_CLASS = "armv4t_text_bg_loop_continuation_reachable_thumb_code"
LITERAL_CLASS = "armv4t_text_bg_loop_continuation_consumed_literal_word"
EXPECTED_SCOPE = {
    "natural_runtime_reachability": False, "code_after_0x08acf2": False,
    "literal_business_semantics": False, "adjacent_padding_or_free_space": False,
    "editing_relocation_or_writeback": False,
}
UPSTREAM_ARTIFACT = Path("artifacts/residual-text-bg-tilemap-resource-ownership-v1")
UPSTREAM_PAYLOAD = "resource-ownership.json"
UPSTREAM_MANIFEST_SHA = "a4db6c9ecfb5bf1d4a408630900a1d6b061f0a04aa30191479522904a71b8ccc"
UPSTREAM_PAYLOAD_SHA = "95c4baf0febd70151d68c08d276bb694daa1f544035466f9b078f73e538d8741"
SOURCE_PATH_RANGES = ((0x08B58C,0x08B60A),(0x08B644,0x08B648))
SOURCE_PATH_PACKED_SHA = "bd33f635a92ec41c617e3638c0c3f7b0183c8f5b80cd52414da2038d3e323d97"
SOURCE_PATH_SEMANTIC_SHA = "be2a286014fa336d32da7ac145f3971617514e36bcab632c48cbd36067203675"
BOUNDARY_RANGE = [0x08ACF2,0x08AD08]
BOUNDARY_CLAIMS = ["verified-reuse-wram-selection-bg-setup-08acf2"]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    lexical = base / relative
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    resolved = lexical.resolve(strict=True)
    if lexical.is_symlink() or not resolved.is_relative_to(base) or not resolved.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _safe_artifact(root: Path, artifact: Path) -> Path:
    base = root.resolve(strict=True)
    lexical = artifact if artifact.is_absolute() else base / artifact
    try:
        relative = lexical.relative_to(base)
    except ValueError as error:
        raise ValueError("unsafe artifact path") from error
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("unsafe artifact path")
    resolved = cursor.resolve(strict=True)
    if not resolved.is_relative_to(base) or not resolved.is_dir():
        raise ValueError("unsafe artifact path")
    return resolved


def _decode_bl(offset: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _producer_forms(rom: bytes) -> dict[str, list[int]]:
    forms = {key: [] for key in ("thumb_bl", "thumb_b", "thumb_bcond", "arm_b_bl",
                                 "aligned_arm_pointer", "thumb_pointer")}
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if _decode_bl(offset, first, second) == ROOT:
            forms["thumb_bl"].append(offset)
        if first & 0xF800 == 0xE000:
            displacement = (first & 0x7FF) << 1
            if displacement & 0x800:
                displacement -= 0x1000
            if offset + 4 + displacement == ROOT:
                forms["thumb_b"].append(offset)
        if first & 0xF000 == 0xD000 and ((first >> 8) & 0xF) < 0xE:
            displacement = (first & 0xFF) << 1
            if displacement & 0x100:
                displacement -= 0x200
            if offset + 4 + displacement == ROOT:
                forms["thumb_bcond"].append(offset)
        if struct.unpack_from("<I", rom, offset)[0] == ROM_BASE + ROOT + 1:
            forms["thumb_pointer"].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        word = struct.unpack_from("<I", rom, offset)[0]
        if word == ROM_BASE + ROOT:
            forms["aligned_arm_pointer"].append(offset)
        if word >> 28 != 0xF and (word >> 25) & 7 == 5:
            displacement = (word & 0xFFFFFF) << 2
            if displacement & 0x02000000:
                displacement -= 0x04000000
            if offset + 8 + displacement == ROOT:
                forms["arm_b_bl"].append(offset)
    return forms


def _coverage_state(raw: bytes) -> tuple[str, dict[str, Any], dict[str, Any]]:
    coverage = json.loads(raw)
    rows = coverage.get("segments")
    if not isinstance(rows, list) or not rows:
        raise ValueError("coverage segments missing")
    starts, cursor = [], 0
    for row in rows:
        interval = row.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or interval[1] <= cursor:
            raise ValueError("coverage segment denominator changed")
        starts.append(cursor); cursor = interval[1]
    if cursor != ROM_SIZE:
        raise ValueError("coverage accounting changed")
    def at(offset: int) -> dict[str, Any]:
        row = rows[bisect.bisect_right(starts, offset) - 1]
        if not row["range"][0] <= offset < row["range"][1]:
            raise ValueError("coverage lookup failed")
        return row
    source = at(PRODUCER)
    if source.get("range") != SOURCE_RANGE or source.get("primary_class") != "consumer_code_slice" or source.get("primary_claim_ids") != ["verified-reuse-text-bg-loop-link-08b640"]:
        raise ValueError("producer source owner changed")
    boundary = at(CODE_RANGE[1])
    if boundary.get("range") != BOUNDARY_RANGE or boundary.get("primary_class") != "consumer_code_slice" or boundary.get("primary_claim_ids") != BOUNDARY_CLAIMS:
        raise ValueError("opaque boundary owner changed")
    observed: list[str] = []
    for start, end, cls in ((*CODE_RANGE, CODE_CLASS), (*LITERAL_RANGE, LITERAL_CLASS)):
        offset = start; local: set[str] = set()
        while offset < end:
            row = at(offset)
            if row.get("primary_class") == "unknown": local.add("baseline")
            elif row.get("primary_class") == cls:
                local.add("post-promotion")
            else: raise ValueError("unexpected promotion coverage owner")
            offset = min(row["range"][1], end)
        if len(local) != 1: raise ValueError("mixed promotion coverage state")
        observed.extend(local)
    if len(set(observed)) != 1: raise ValueError("mixed packet coverage state")
    state = observed[0]
    if state == "baseline" and _sha(raw) != BASELINE_SHA:
        raise ValueError("baseline coverage identity changed")
    return state, {"range": SOURCE_RANGE, "primary_class": "consumer_code_slice",
                   "primary_claim_ids": ["verified-reuse-text-bg-loop-link-08b640"]}, {
                   "range": BOUNDARY_RANGE, "primary_class": "consumer_code_slice",
                   "primary_claim_ids": BOUNDARY_CLAIMS}


def _source_membership(root: Path, rom: bytes) -> dict[str, Any]:
    from tools.verify_residual_text_bg_tilemap_resource_ownership import verify_artifact
    upstream = _safe_artifact(root, UPSTREAM_ARTIFACT)
    manifest_raw = _safe_file(root, UPSTREAM_ARTIFACT / MANIFEST_NAME).read_bytes()
    payload_raw = _safe_file(root, UPSTREAM_ARTIFACT / UPSTREAM_PAYLOAD).read_bytes()
    if _sha(manifest_raw) != UPSTREAM_MANIFEST_SHA or _sha(payload_raw) != UPSTREAM_PAYLOAD_SHA:
        raise ValueError("upstream text-BG ownership identity changed")
    report = verify_artifact(root, upstream)
    if report.get("verified") is not True:
        raise ValueError("upstream text-BG ownership verification failed")
    payload = json.loads(payload_raw)
    if payload.get("scope",{}).get("static_natural_caller_chain_complete") is not True or payload.get("ownership_record",{}).get("natural_entry_callers") != ["0x0808F844","0x0808FA04"] or payload.get("ownership_record",{}).get("resource_setup_function") != "0x0808B58C":
        raise ValueError("upstream static caller chain changed")
    cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB); decoded=[]
    for start,end in SOURCE_PATH_RANGES:
        rows=list(cs.disasm(rom[start:end],ROM_BASE+start))
        if sum(row.size for row in rows)!=end-start: raise ValueError("source membership path decode changed")
        decoded.extend(rows)
    semantic=[[x.address-ROM_BASE,x.size,x.mnemonic,x.op_str] for x in decoded]
    packed=b"".join(rom[a:b] for a,b in SOURCE_PATH_RANGES)
    if len(decoded)!=55 or len(packed)!=130 or _sha(packed)!=SOURCE_PATH_PACKED_SHA or _sha(_canonical(semantic))!=SOURCE_PATH_SEMANTIC_SHA:
        raise ValueError("source membership path denominator changed")
    braw=struct.unpack_from("<H",rom,0x08B608)[0]
    displacement=(braw&0x7ff)<<1
    if displacement&0x800: displacement-=0x1000
    if braw&0xf800!=0xe000 or 0x08B608+4+displacement!=PRODUCER or _decode_bl(PRODUCER,*struct.unpack_from("<HH",rom,PRODUCER))!=ROOT:
        raise ValueError("source membership branch chain changed")
    return {"upstream_artifact":UPSTREAM_ARTIFACT.as_posix(),"upstream_manifest_sha256":UPSTREAM_MANIFEST_SHA,"upstream_payload_sha256":UPSTREAM_PAYLOAD_SHA,"upstream_verified":True,"natural_entry_callers":[0x08F844,0x08FA04],"root_file_offset":0x08B58C,"path_ranges":[list(x) for x in SOURCE_PATH_RANGES],"instruction_count":55,"instruction_bytes":130,"packed_sha256":SOURCE_PATH_PACKED_SHA,"semantic_instruction_vector_sha256":SOURCE_PATH_SEMANTIC_SHA,"terminal_branch":{"file_offset":0x08B608,"target_file_offset":PRODUCER},"producer_instruction_membership_proven":True}


def _expected_payload(root: Path, rom: bytes, coverage_raw: bytes) -> dict[str, Any]:
    state, source, boundary = _coverage_state(coverage_raw)
    forms = _producer_forms(rom)
    expected_forms = {key: [] for key in forms}; expected_forms["thumb_bl"] = [PRODUCER]
    if forms != expected_forms: raise ValueError("target-limited producer denominator changed")
    producer_raw = rom[PRODUCER:PRODUCER+4]
    if producer_raw.hex() != "fff740fb" or _sha(producer_raw) != "f7e047cc350bda582135e51f36c556fb0e6445de6ee9c286ae9383c6bbefdc7a":
        raise ValueError("producer bytes changed")
    cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    decoded = list(cs.disasm(rom[CODE_RANGE[0]:CODE_RANGE[1]], ROM_BASE + CODE_RANGE[0]))
    if len(decoded) != 21 or sum(x.size for x in decoded) != 42 or any(x.size != 2 for x in decoded):
        raise ValueError("Thumb instruction denominator changed")
    semantic = [[x.address-ROM_BASE, x.size, x.mnemonic, x.op_str] for x in decoded]
    bindings: list[list[int]] = []
    for row in decoded:
        offset = row.address-ROM_BASE; halfword = struct.unpack_from("<H",rom,offset)[0]
        if halfword & 0xF800 == 0x4800:
            literal=((offset+4)&~3)+(halfword&0xFF)*4
            bindings.append([offset,literal,struct.unpack_from("<I",rom,literal)[0]])
    if bindings != [[0x08ACD4,0x08AEB4,0x02002880],[0x08ACD6,0x08AEB8,0x0300004C],
                    [0x08ACE4,0x08AEB8,0x0300004C],[0x08ACE8,0x08AEBC,0x03000054]]:
        raise ValueError("literal binding denominator changed")
    code_sha=_sha(rom[CODE_RANGE[0]:CODE_RANGE[1]]); literal_sha=_sha(rom[LITERAL_RANGE[0]:LITERAL_RANGE[1]])
    if code_sha!="63b9d3ea83926af1934f0941783b87c11fd20e4f1d574077042c433103444b60" or literal_sha!="bcdc220c3e327144ba44963a55291fe4bf8d4357ca1de84904b883b8bb1f4525":
        raise ValueError("target bytes changed")
    claims=[
        {"id":"text-bg-loop-continuation-code","range":CODE_RANGE,"role":"primary","kind":"reachable_thumb_code","primary_class":CODE_CLASS,"claim_kind":"reachable_thumb_code","mode":"thumb","promotion_batch":SCHEMA,"promoted_from_primary_class":"unknown","bytes_sha256":code_sha},
        {"id":"text-bg-loop-continuation-literals","range":LITERAL_RANGE,"role":"primary","kind":"consumed_literal_words","primary_class":LITERAL_CLASS,"claim_kind":"consumed_literal_word","promotion_batch":SCHEMA,"promoted_from_primary_class":"unknown","bytes_sha256":literal_sha},
    ]
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":len(rom),"sha256":_sha(rom)},
        "coverage_baseline":{"path":COVERAGE_PATH.as_posix(),"historical_sha256":BASELINE_SHA,"observed_during_artifact_build":True},
        "producer_denominator":{"target_file_offset":ROOT,"forms":forms,"matching_producer_count":1,"producer_raw_hex":producer_raw.hex(),"producer_bytes_sha256":_sha(producer_raw)},
        "source_owner":source,
        "source_membership":_source_membership(root,rom),
        "opaque_boundary_owner":boundary,
        "target_local_cfg":{"root_file_offset":ROOT,"mode":"thumb","instruction_count":21,"basic_block_count":1,"frontier_count":0,"code_range":CODE_RANGE,"code_bytes":42,"code_bytes_sha256":code_sha,"semantic_instruction_vector":semantic,"semantic_instruction_vector_sha256":_sha(_canonical(semantic)),"boundary":{"source_file_offset":0x08ACF0,"target_file_offset":0x08ACF2,"edge_kind":"opaque_boundary","reason":"accepted_owner_beginning"},"literal_bindings":bindings,"literal_reference_count":4,"unique_literal_word_count":3,"literal_range":LITERAL_RANGE,"literal_bytes":12,"literal_bytes_sha256":literal_sha},
        "promotion":{"batch":SCHEMA,"claims":claims,"code_bytes":42,"literal_bytes":12,"promotion_bytes":54},"scope":EXPECTED_SCOPE}


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    try:
        root=root.resolve(strict=True); directory=_safe_artifact(root,artifact)
        allowed={MANIFEST_NAME,PAYLOAD_NAME}
        if {p.name for p in directory.iterdir()} != allowed or any(p.is_symlink() for p in directory.iterdir()):
            raise ValueError("artifact file denominator changed")
        manifest_raw=(directory/MANIFEST_NAME).read_bytes(); payload_raw=(directory/PAYLOAD_NAME).read_bytes()
        manifest=json.loads(manifest_raw); payload=json.loads(payload_raw)
        if _canonical(manifest)!=manifest_raw or _canonical(payload)!=payload_raw: raise ValueError("artifact JSON is not canonical")
        rom=_safe_file(root,ROM_PATH).read_bytes(); coverage_raw=_safe_file(root,COVERAGE_PATH).read_bytes()
        if len(rom)!=ROM_SIZE or _sha(rom)!=ROM_SHA256: raise ValueError("base ROM identity changed")
        coverage_state=_coverage_state(coverage_raw)[0]
        expected=_expected_payload(root,rom,coverage_raw)
        if payload!=expected: raise ValueError("payload contract changed")
        relative=directory.relative_to(root).as_posix()
        expected_manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"accepted","files":{PAYLOAD_NAME:{"size":len(payload_raw),"sha256":_sha(payload_raw)}},"summary":{"producer_count":1,"instruction_count":21,"code_bytes":42,"literal_word_count":3,"literal_bytes":12,"promotion_bytes":54},"producer":{"command":["python3","tools/export_rom_text_bg_loop_continuation.py","--root",".","--output",relative]},"verifier":{"command":["python3","tools/verify_rom_text_bg_loop_continuation.py","--root",".","--artifact",relative]},"implementation":{"exporter_sha256":_sha(_safe_file(root,Path("tools/export_rom_text_bg_loop_continuation.py")).read_bytes()),"verifier_sha256":_sha(_safe_file(root,Path("tools/verify_rom_text_bg_loop_continuation.py")).read_bytes()),"test_sha256":_sha(_safe_file(root,Path("tests/test_export_rom_text_bg_loop_continuation.py")).read_bytes())}}
        if manifest!=expected_manifest: raise ValueError("manifest contract changed")
        return {"schema":VERIFY_SCHEMA,"verified":True,"contract_ok":True,"errors":[],"rom_sha256":ROM_SHA256,"coverage_state":coverage_state,"producer_count":1,"instruction_count":21,"code_bytes":42,"literal_word_count":3,"literal_bytes":12,"promotion_bytes":54,"frontier_count":0,"source_membership_proven":True,"opaque_boundary_owner_verified":True,"nonclaims":EXPECTED_SCOPE}
    except Exception as error:
        return {"schema":VERIFY_SCHEMA,"verified":False,"contract_ok":False,"errors":[str(error)]}


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--root",type=Path,default=Path("."));parser.add_argument("--artifact",type=Path,required=True);args=parser.parse_args()
    report=verify_artifact(args.root,args.artifact);print(json.dumps(report,sort_keys=True));return 0 if report["verified"] else 1


if __name__=="__main__": raise SystemExit(main())
