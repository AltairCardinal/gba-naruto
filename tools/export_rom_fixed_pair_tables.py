#!/usr/bin/env python3
"""Export the deliberately narrow A/B fixed-pair-table packet."""
from __future__ import annotations
import argparse, ctypes, errno, gzip, hashlib, json, os, shutil, sys, tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
from tools import rom_fixed_pair_tables_contract as c
PAYLOAD_NAME, MANIFEST_NAME = c.PAYLOAD_NAME, c.MANIFEST_NAME

def _sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def _canonical(value: Any) -> bytes: return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _u16(rom: bytes, address: int) -> int: return int.from_bytes(rom[address-c.ROM_BASE:address-c.ROM_BASE+2], "little")
def _u32(rom: bytes, address: int) -> int: return int.from_bytes(rom[address-c.ROM_BASE:address-c.ROM_BASE+4], "little")
def _occurrences(raw: bytes, needle: bytes) -> list[int]:
    out=[]; start=0
    while (found:=raw.find(needle,start)) >= 0: out.append(found); start=found+1
    return out

def _identity(rom: bytes, strict: bool) -> None:
    if strict and (len(rom) != c.ROM_SIZE or _sha(rom) != c.ROM_SHA256): raise ValueError("ROM identity changed")
    for bounds, digest, raw_hex in ((c.TABLE_A_RANGE,c.TABLE_A_SHA256,c.TABLE_A_RAW_HEX),(c.TABLE_B_RANGE,c.TABLE_B_SHA256,c.TABLE_B_RAW_HEX),(c.COMBINED_RANGE,c.COMBINED_SHA256,None)):
        raw=rom[slice(*bounds)]
        if _sha(raw)!=digest or (raw_hex and raw.hex()!=raw_hex): raise ValueError("table bytes changed")

def _a_consumer(rom: bytes) -> dict[str, Any]:
    # This exact local loop is decoded as raw Thumb halfwords, including its guard.
    expected={0x807c0d2:0x2200,0x807c0d4:0x4692,0x807c0d6:0x4c21,0x807c0dc:0x4008,
      0x807c0de:0x2800,0x807c0e0:0xd107,0x807c0e2:0x0848,0x807c0e4:0x0040,
      0x807c0e6:0x1900,0x807c0ea:0x5e81,0x807c0f8:0x4650,0x807c0fa:0x3001,
      0x807c100:0x4682,0x807c102:0x2809,0x807c104:0xd9e8}
    if any(_u16(rom,a)!=v for a,v in expected.items()): raise ValueError("A raw Thumb loop changed")
    literal=((0x807c0d6+4)&~3)+((_u16(rom,0x807c0d6)&255)*4)
    if literal!=c.A_LITERAL_WORD_SITE or _u32(rom,literal)!=c.A_BASE_VALUE: raise ValueError("A literal/base changed")
    if _occurrences(rom,c.A_BASE_VALUE.to_bytes(4,"little")) != [literal-c.ROM_BASE]: raise ValueError("A literal denominator changed")
    # sl starts at zero, executes 0..9 due to BLS; odd values branch over LDRSH.
    offsets=list(range(0,10,2))
    return {"base_literal_load_site":c.A_CONSUMER_SITE,"base_literal_occurrences":[literal],"base_literal_value":c.A_BASE_VALUE,"iteration_compare":9,"iteration_count":10,"load_count":len(offsets),"load_offsets":offsets,"load_kind":"ldrsh","cfg":{"reachable_instruction_count":26,"frontier_count":0,"raw_thumb_guard_sites":[0x807c0dc,0x807c0de,0x807c0e0,0x807c102,0x807c104]}}

def _b_consumer(rom: bytes, site: int, literal: int) -> dict[str, Any]:
    # All nine paths have LDR literal, mov #7, ANDS, LSL #2, add base, LDRH.
    words=[_u16(rom,site+i) for i in range(0,22,2)]
    literal_at=((site+4)&~3)+((words[0]&255)*4)
    if (words[0]&0xf800)!=0x4800 or literal_at!=literal or _u32(rom,literal)!=c.B_BASE_VALUE: raise ValueError("B literal/base changed")
    mask_site=next((site+i for i in range(8,16,2) if _u16(rom,site+i)==0x4008),None)
    if mask_site is None or _u16(rom,mask_site-2)!=0x2007 or _u16(rom,mask_site+2) not in (0x0084,0x0080): raise ValueError("B selector guard changed")
    first_load = mask_site + (8 if site < 0x807c700 else 6)
    if _u16(rom,mask_site+4) not in (0x19e1,0x1880) or _u16(rom,first_load)!=(0x8809 if site<0x807c700 else 0x8800): raise ValueError("B first pair dataflow changed")
    # The first six use their own base+2 path; switch arms converge at 0x807c870.
    second_site = site+42 if site < 0x807c700 else 0x807c870
    if site < 0x807c700:
        second_add=next((site+i for i in range(30,42,2) if _u16(rom,site+i)==0x1cb8),None)
        if second_add is None or (_u16(rom,second_add+2),_u16(rom,second_add+6)) != (0x1820,0x8800): raise ValueError("B second pair dataflow changed")
        second_site=second_add+6
    else:
        if (_u16(rom,second_site),_u16(rom,second_site-2)) != (0x8803,0x1840): raise ValueError("B shared second pair dataflow changed")
    return {"consumer_site":site,"literal_site":literal,"base_literal_value":c.B_BASE_VALUE,"selector_mask":7,"selector_mask_sites":[mask_site],"index_shift":2,"index_scale_sites":[mask_site+2],"record_stride":4,"record_count":8,"max_access_offset":30,"load_offsets":[0,2],"halfword_load_count":2,"cfg":{"frontier_count":0,"raw_thumb_instruction_sites":[site,mask_site,mask_site+2,first_load,second_site]}}

def _coverage(root: Path) -> dict[str, Any]:
    directory = (root / c.PRECOVERAGE_ARTIFACT).resolve(strict=True)
    if not directory.is_relative_to(root.resolve(strict=True)) or not directory.is_dir() \
            or {path.name for path in directory.iterdir()} \
            != {"manifest.json", c.PRECOVERAGE_ARCHIVE_NAME}:
        raise ValueError("immutable precoverage artifact changed")
    manifest_raw = _safe_file(root, c.PRECOVERAGE_ARTIFACT / "manifest.json").read_bytes()
    archive_raw = _safe_file(root, c.PRECOVERAGE_ARTIFACT / c.PRECOVERAGE_ARCHIVE_NAME).read_bytes()
    if len(manifest_raw) != c.PRECOVERAGE_MANIFEST_SIZE \
            or _sha(manifest_raw) != c.PRECOVERAGE_MANIFEST_SHA256 \
            or len(archive_raw) != c.PRECOVERAGE_ARCHIVE_SIZE \
            or _sha(archive_raw) != c.PRECOVERAGE_ARCHIVE_SHA256:
        raise ValueError("immutable precoverage identity changed")
    manifest = json.loads(manifest_raw)
    record = manifest.get("files", {}).get(c.PRECOVERAGE_ARCHIVE_NAME)
    if manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1" \
            or manifest.get("artifact_status") != "accepted" \
            or not isinstance(record, dict) \
            or record.get("sha256") != c.PRECOVERAGE_ARCHIVE_SHA256 \
            or record.get("uncompressed_sha256") != c.COVERAGE_SHA256:
        raise ValueError("immutable precoverage manifest changed")
    raw = gzip.decompress(archive_raw)
    if len(raw) != c.PRECOVERAGE_RAW_SIZE or _sha(raw) != c.COVERAGE_SHA256:
        raise ValueError("immutable precoverage payload changed")
    ledger=json.loads(raw); segments=ledger.get("segments",[])
    def status(bounds):
      hits=[x for x in segments if x.get("range",[0,0])[0]<=bounds[0] and x.get("range",[0,0])[1]>=bounds[1]]
      if not hits or any(x.get("primary_class")!="unknown" for x in hits): raise ValueError("coverage no longer unknown")
    for x in (c.LEFT_GAP_RANGE,c.COMBINED_RANGE,c.RIGHT_GAP_RANGE): status(x)
    return {"baseline_sha256":c.COVERAGE_SHA256,"target_status":"unknown","helper_overlay_non_overlapping":True}

def _build_from_rom(root: Path, rom: bytes, verify_identity: bool=True) -> dict[str, Any]:
    _identity(rom,verify_identity); a_raw=rom[slice(*c.TABLE_A_RANGE)]; b_raw=rom[slice(*c.TABLE_B_RANGE)]
    a_records=[{"index":i,"range":[c.TABLE_A_RANGE[0]+2*i,c.TABLE_A_RANGE[0]+2*i+2],"signed_u16":int.from_bytes(a_raw[2*i:2*i+2],"little",signed=True)} for i in range(5)]
    b_records=[{"index":i,"range":[c.TABLE_B_RANGE[0]+4*i,c.TABLE_B_RANGE[0]+4*i+4],"first_u16":int.from_bytes(b_raw[4*i:4*i+2],"little"),"second_u16":int.from_bytes(b_raw[4*i+2:4*i+4],"little")} for i in range(8)]
    claims = [
        {
            "id": "fixed-pair-table-a-53e00a",
            "range": list(c.TABLE_A_RANGE),
            "claim_kind": "fixed_signed_u16_sequence",
            "bytes_sha256": c.TABLE_A_SHA256,
        },
        {
            "id": "fixed-pair-table-b-53e014",
            "range": list(c.TABLE_B_RANGE),
            "claim_kind": "masked_u16_pair_table",
            "bytes_sha256": c.TABLE_B_SHA256,
        },
    ]
    return {"schema":c.SCHEMA,"merged_range":list(c.COMBINED_RANGE),"merged_bytes_sha256":c.COMBINED_SHA256,"tables":{"a":{"range":list(c.TABLE_A_RANGE),"bytes_sha256":c.TABLE_A_SHA256,"record_count":5,"record_size":2,"records":a_records},"b":{"range":list(c.TABLE_B_RANGE),"bytes_sha256":c.TABLE_B_SHA256,"record_count":8,"record_size":4,"records":b_records}},"a_consumer":_a_consumer(rom),"b_consumers":[_b_consumer(rom,s,l) for s,l in c.B_CONSUMER_LITERAL_SITES],"coverage_projection":_coverage(root),"gaps":{"left":{"range":list(c.LEFT_GAP_RANGE),"status":"unknown"},"right":{"range":list(c.RIGHT_GAP_RANGE),"status":"unknown"}},"promotion":{"promotion_bytes":42,"claim_count":2,"claims":claims},"scope":{"natural_reachability":False,"business_field_semantics":False,"destination_interpretation_beyond_a_signedness":False,"padding_or_free_space":False,"editing_writeback_or_relocation":False,"computed_or_indirect_consumer_exhaustion":False}}
def build_payload(root: Path) -> dict[str, Any]: return _build_from_rom(root,(root/c.ROM_PATH).read_bytes())

def _publish_exclusive(source: Path,destination: Path)->None:
    source = source.absolute()
    destination = destination.absolute()
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd,
                  os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            if code == errno.EEXIST:
                raise FileExistsError(destination)
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)

def export_artifact(root: Path,destination: Path)->Path:
    root = root.resolve(strict=True)
    lexical = destination if destination.is_absolute() else root / destination
    try:
        relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("output escapes root") from error
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("output has symlink ancestor")
    destination = lexical.resolve(strict=False)
    if not destination.is_relative_to(root):
        raise ValueError("output escapes root")
    resolved_relative = destination.relative_to(root)
    if (resolved_relative != c.OFFICIAL
            and resolved_relative.parts[:2] != ("build", "experiments")):
        raise ValueError("staging output must be under build/experiments")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".fixed-pair-",dir=destination.parent))
    try:
      payload=_canonical(build_payload(root)); (stage/PAYLOAD_NAME).write_bytes(payload)
      exporter=Path("tools/export_rom_fixed_pair_tables.py")
      verifier=Path("tools/verify_rom_fixed_pair_tables.py")
      test=Path("tests/test_export_rom_fixed_pair_tables.py")
      contract=Path("tools/rom_fixed_pair_tables_contract.py")
      official=c.OFFICIAL.as_posix()
      manifest={
          "schema":c.PROMOTION_SCHEMA,
          "artifact_schema":c.SCHEMA,
          "artifact_status":"accepted",
          "canonical_destination":official,
          "artifact_portability":"content_verified_independent_of_copy_path",
          "files":{PAYLOAD_NAME:{"size":len(payload),"sha256":_sha(payload)}},
          "summary":{"promotion_bytes":42,"claim_count":2,"table_count":2},
          "producer":{"command":["python3",exporter.as_posix(),"--root",".","--output",official],"command_role":"canonical_reproduction_recipe"},
          "verifier":{"command":["python3",verifier.as_posix(),"--root",".","--artifact",official],"command_role":"canonical_reproduction_recipe","exit_code":0},
          "implementation":{
              "contract_sha256":_sha(_safe_file(root,contract).read_bytes()),
              "exporter_sha256":_sha(_safe_file(root,exporter).read_bytes()),
              "verifier_sha256":_sha(_safe_file(root,verifier).read_bytes()),
              "test_sha256":_sha(_safe_file(root,test).read_bytes()),
          },
      }
      (stage/MANIFEST_NAME).write_bytes(_canonical(manifest)); _publish_exclusive(stage,destination); return destination
    finally:
      if stage.exists(): shutil.rmtree(stage)

if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path('.')); p.add_argument('--output',required=True); args=p.parse_args(); export_artifact(args.root,Path(args.output))
