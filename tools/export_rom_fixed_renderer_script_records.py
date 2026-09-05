#!/usr/bin/env python3
"""Export fixed CFG-consumer renderer script records in the low ROM cluster."""

from __future__ import annotations

import argparse
import ctypes
import errno
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools._vendor.capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from tools._vendor.capstone import arm_const
from tools.export_rom_training_text_script_inventory import _parse_training_record, _sjis_ranges
from tools.thumb_branch import decode_thumb_bl
from tools.verify_rom_training_text_script_inventory import verify_artifact as verify_training
from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory
from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3


SCHEMA = "rom-fixed-renderer-script-records-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000
OFFICIAL = Path("artifacts/rom-fixed-renderer-script-records-v1")
PAYLOAD_NAME = "rom-fixed-renderer-script-records.json"
MANIFEST_NAME = "manifest.json"
TRAINING_DIR = Path("artifacts/rom-training-text-script-inventory-v1")
TRAINING_MANIFEST_SHA256 = "af609bc3b303e2617d79cc254d3b39d67e05f3606654441613309566d23e3c0b"
TRAINING_PAYLOAD_SHA256 = "bc5d636d2dd6076892fbac7ba88879c964df9e819407c72d644cd10c5d9dadcb"
TRAINING_VERIFIER_SHA256 = "8058c27cb313c6d32d613feb9946444932c3d9dc64fe27929489fb1af72e5305"
CFG_UPSTREAM = (
    (Path("artifacts/rom-cfg-inventory-v2/manifest.json"), "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"),
    (Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"), "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"),
    (Path("tools/verify_rom_cfg_inventory.py"), "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"),
    (Path("artifacts/rom-cfg-inventory-v3/manifest.json"), "6aa788611f73856e621f5c74aab544d47b034307a9dc1180f6fd8f81cb1f423b"),
    (Path("artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json"), "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d"),
    (Path("tools/verify_rom_cfg_inventory_v3.py"), "46400e44866a93b571745f30779296cc5686889ac5d465891c648296d2dbe00a"),
)
INTERPRETER_RANGE = (0x067158, 0x06836E)
INTERPRETER_SHA256 = "211812743de17ef5158ef63bd52deb3271c962b9119bf74f1bbd458b6bec96dd"
PARSER_RANGE = (0x06626C, 0x066736)
PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS_RANGE = (0x53D644, 0x53D73C)
SJIS_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"
EXCLUDED_TARGETS = [0x0BC9, 0x0C2E, 0x0C34, 0x14B4, 0x15FC]
CONSUMERS = (
    (0x6C7A2,0x0A65,0x6C7A4),(0x6C806,0x0A93,0x6C808),(0x6C888,0x175D,0x6C88A),
    (0x6C914,0x175D,0x6C916),(0x6C96C,0x177D,0x6C96E),(0x6C990,0x177D,0x6C992),
    (0x70F2C,0x0B9A,0x70F2E),(0x7122C,0x0BC9,0x7122E),(0x71260,0x0BF5,0x71262),
    (0x71276,0x0C2E,0x71278),(0x713F8,0x0CA4,0x71442),(0x71440,0x0CC7,0x71442),
    (0x714BC,0x0C34,0x714F6),(0x7158E,0x0C6C,0x715C8),(0x71614,0x12F0,0x71616),
    (0x716AE,0x12F0,0x716B0),(0x719F8,0x1326,0x719FA),(0x71A08,0x1356,0x71A0A),
    (0x71A14,0x1391,0x71A16),(0x71A24,0x13C3,0x71A26),(0x71A30,0x1428,0x71A32),
    (0x71A3C,0x13F3,0x71A3E),(0x71A4E,0x12FA,0x71A50),(0x71AE4,0x15FC,0x71AE6),
    (0x71BCA,0x1465,0x71BCC),(0x7214E,0x1495,0x72150),(0x721CC,0x1499,0x721CE),
    (0x721D2,0x14B4,0x721D4),(0x7C758,0x15B0,0x7C75A),(0x7C7A4,0x15BA,0x7C7A6),
    (0x8163C,0x1631,0x8163E),(0x81658,0x1725,0x8165A),(0x8179C,0x1725,0x817A0),
    (0x81944,0x1725,0x81946),(0x81A44,0x1725,0x81A46),(0x8177E,0x164F,0x81780),
    (0x817B0,0x172B,0x817B2),(0x81880,0x1671,0x81882),(0x81928,0x16A1,0x8192A),
    (0x819E0,0x16C3,0x819E2),(0x81A3E,0x16EE,0x81A40),
)
RECORDS = (
    (0x0A65,0x0A93,[1,5,4,12,3,4,0]),(0x0A93,0x0ABB,[1,5,4,12,3,4,0]),
    (0x0B9A,0x0BC9,[1,1,1,1,5,0]),(0x0BF5,0x0C2E,[1,5,0]),
    (0x0C6C,0x0CA4,[1,5,4,12,3,0]),(0x0CA4,0x0CC7,[1,5,4,12,3,0]),
    (0x0CC7,0x0CEA,[1,5,4,12,3,0]),(0x12F0,0x12FA,[3,3,3,3,4,0]),
    (0x12FA,0x1326,[1,5,4,12,3,4,0]),(0x1326,0x1356,[1,5,4,12,3,4,0]),
    (0x1356,0x1391,[1,5,4,12,3,4,0]),(0x1391,0x13C3,[1,5,4,12,3,4,0]),
    (0x13C3,0x13F3,[1,5,4,12,3,4,0]),(0x13F3,0x1428,[1,5,4,12,3,4,0]),
    (0x1428,0x1465,[1,5,4,12,3,4,0]),(0x1465,0x1495,[1,5,0]),
    (0x1495,0x1499,[3,4,0]),(0x1499,0x14B4,[1,5,0]),
    (0x15B0,0x15BA,[1,3,0]),(0x15BA,0x15C4,[3,1,0]),
    (0x1631,0x164F,[1,5,0]),(0x164F,0x1671,[1,5,0]),
    (0x1671,0x16A1,[1,5,0]),(0x16A1,0x16C3,[1,5,0]),
    (0x16C3,0x16EE,[1,5,0]),(0x16EE,0x1725,[1,5,0]),
    (0x1725,0x172B,[4,12,3,4,0]),(0x172B,0x175D,[1,5,0]),
    (0x175D,0x177D,[1,5,4,0]),(0x177D,0x1781,[3,4,0]),
)
MERGED_RANGES = [[0x0A65,0x0ABB],[0x0B9A,0x0BC9],[0x0BF5,0x0C2E],
                 [0x0C6C,0x0CEA],[0x12F0,0x14B4],[0x15B0,0x15C4],[0x1631,0x1781]]
PRIMARY_CLASS = "fixed_cfg_consumer_renderer_command_script"
CLAIM_KIND = "fixed_cfg_consumer_renderer_command_script_bytes"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True); cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink(): raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file(): raise ValueError(f"unsafe input path: {relative}")
    return result


@lru_cache(maxsize=1)
def _cfg_blocks(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    for path, digest in CFG_UPSTREAM:
        if _sha(_safe_file(root, path).read_bytes()) != digest:
            raise ValueError("canonical CFG upstream identity changed")
    v2_dir = (root / "artifacts/rom-cfg-inventory-v2").resolve(strict=True)
    v3_dir = (root / "artifacts/rom-cfg-inventory-v3").resolve(strict=True)
    if not verify_rom_cfg_inventory(root, v2_dir).get("verified"):
        raise ValueError("canonical CFG v2 verification failed")
    if not verify_rom_cfg_inventory_v3(root, v3_dir).get("verified"):
        raise ValueError("canonical CFG v3 verification failed")
    v2 = json.loads(_safe_file(root, CFG_UPSTREAM[1][0]).read_bytes())
    v3 = json.loads(_safe_file(root, CFG_UPSTREAM[4][0]).read_bytes())
    blocks = list(v2["blocks"]) + list(v3["extension"]["blocks"])
    identity = {path.as_posix(): digest for path, digest in CFG_UPSTREAM}
    return blocks, {"verified": True, "files": identity,
                    "v2_graph_denominator_sha256": v2["graph_denominator_sha256"],
                    "v3_graph_denominator_sha256": v3["graph_denominator_sha256"]}


def _prove_parameter_flow(rom: bytes, site: int, source_register: int) -> int:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB); engine.detail = True
    register_ids = {index: getattr(arm_const, f"ARM_REG_R{index}") for index in range(8)}
    work = [(site + 2, frozenset({register_ids[source_register]}))]
    seen: set[tuple[int, frozenset[int]]] = set(); successes: set[int] = set()
    while work:
        address, taint = work.pop()
        state = (address, taint)
        if state in seen: continue
        seen.add(state)
        if not site < address <= site + 0x100:
            raise ValueError("consumer parameter flow left bounded window")
        decoded = tuple(engine.disasm(rom[address:address + 4], ROM_BASE + address, count=1))
        if len(decoded) != 1 or decoded[0].address != ROM_BASE + address:
            raise ValueError("consumer parameter flow decode failed")
        insn = decoded[0]; next_address = address + insn.size
        if insn.id == arm_const.ARM_INS_BL:
            first, second = struct.unpack_from("<HH", rom, address)
            target = decode_thumb_bl(address, first, second)
            if target == INTERPRETER_RANGE[0]:
                if register_ids[0] not in taint:
                    raise ValueError("consumer literal does not reach interpreter r0")
                successes.add(address); continue
            taint = frozenset(reg for reg in taint if reg not in {register_ids[i] for i in range(4)})
            work.append((next_address, taint)); continue
        if insn.id == arm_const.ARM_INS_B:
            halfword = struct.unpack_from("<H", rom, address)[0]
            target = int(insn.operands[0].imm) - ROM_BASE
            if halfword & 0xF800 == 0xE000:
                work.append((target, taint)); continue
            if halfword & 0xF000 == 0xD000 and (halfword >> 8) & 0xF < 0xE:
                work.extend(((target, taint), (next_address, taint))); continue
            raise ValueError("unsupported consumer branch")
        reads, writes = insn.regs_access(); next_taint = set(taint) - set(writes)
        if insn.id in (arm_const.ARM_INS_MOV, arm_const.ARM_INS_ADD):
            if writes and any(reg in taint for reg in reads):
                # Only register copies/add-immediate-zero may carry an exact pointer.
                immediate_values = [op.imm for op in insn.operands if op.type == arm_const.ARM_OP_IMM]
                if not immediate_values or all(value == 0 for value in immediate_values):
                    next_taint.update(writes)
        work.append((next_address, frozenset(next_taint)))
    if len(successes) != 1:
        raise ValueError("consumer parameter flow has no unique interpreter sink")
    return successes.pop()


def _consumer_denominator(root: Path, rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    blocks, upstream = _cfg_blocks(root); discovered = []
    for block in blocks:
        if block.get("mode") != "thumb": continue
        start, end = block["range"]
        for site in range(start, end, 2):
            halfword = struct.unpack_from("<H", rom, site)[0]
            if halfword & 0xF800 != 0x4800: continue
            literal = ((site + 4) & ~3) + (halfword & 0xFF) * 4
            target_word = struct.unpack_from("<I", rom, literal)[0]
            if ROM_BASE <= target_word < ROM_BASE + 0x1CD0:
                discovered.append((site, target_word - ROM_BASE, literal, (halfword >> 8) & 7))
    if len(discovered) != 41 or len({site for site, *_ in discovered}) != 41:
        raise ValueError("canonical CFG renderer-literal denominator changed")
    rows = []
    for site, target, literal, register in sorted(discovered):
        callsite = _prove_parameter_flow(rom, site, register)
        rows.append({"site": site, "target": target, "literal_word": literal,
                     "interpreter_callsite": callsite,
                     "path_sha256": _sha(rom[site:callsite + 4]),
                     "accepted": target not in EXCLUDED_TARGETS})
    vector = [[row["site"],row["target"],row["interpreter_callsite"],row["path_sha256"]] for row in rows]
    if _sha(json.dumps(vector,separators=(",",":")).encode()) != "279d25527c69e1cb558b1aacfd3b548a7cdf24d98e12a6366e459520aca83909":
        raise ValueError("consumer interpreter path vector changed")
    return {"sites": rows, "site_count": 41, "accepted_site_count": 36,
            "excluded_site_count": 5, "excluded_targets": EXCLUDED_TARGETS,
            "path_vector_sha256": "279d25527c69e1cb558b1aacfd3b548a7cdf24d98e12a6366e459520aca83909",
            "denominator_scope": "canonical_v2_v3_cfg_pc_relative_literal_consumers"}, upstream


def _records(rom: bytes) -> dict[str, Any]:
    if _sha(rom[INTERPRETER_RANGE[0]:INTERPRETER_RANGE[1]]) != INTERPRETER_SHA256:
        raise ValueError("interpreter semantics changed")
    if _sha(rom[PARSER_RANGE[0]:PARSER_RANGE[1]]) != PARSER_SHA256:
        raise ValueError("renderer parser semantics changed")
    if _sha(rom[SJIS_RANGE[0]:SJIS_RANGE[1]]) != SJIS_SHA256:
        raise ValueError("SJIS range semantics changed")
    sjis = _sjis_ranges(rom); rows = []
    for start, end, opcodes in RECORDS:
        parsed = _parse_training_record(rom, start, 0x1CD0, sjis)
        if parsed["end"] != end or parsed["opcode_sequence"] != opcodes:
            raise ValueError("record parser denominator changed")
        rows.append({"range": [start,end], "opcode_sequence": opcodes,
                     "bytes_sha256": _sha(rom[start:end])})
    vector = [[row["range"][0],row["range"][1]] for row in rows]
    packed = b"".join(rom[a:b] for a,b,_ in RECORDS)
    if _sha(json.dumps(vector,separators=(",",":")).encode()) != "6fa95454d60ccbfa2680dc286114190f52a9226b72c82e368cbae02bc7ad8df3":
        raise ValueError("record range vector changed")
    if _sha(packed) != "badb4ac6c49ea2250909065b2deb5d19cbd8d9768c761447fef6ab92916a60b9":
        raise ValueError("record packed bytes changed")
    if _sha(json.dumps(MERGED_RANGES,separators=(",",":")).encode()) != "a781ac704199e1412224376289d705c1ed4e2766065bcb3334d1495d3297b9ce":
        raise ValueError("merged range vector changed")
    return {"items": rows, "record_count": 30, "record_bytes": 1124,
            "record_vector_sha256": "6fa95454d60ccbfa2680dc286114190f52a9226b72c82e368cbae02bc7ad8df3",
            "packed_bytes_sha256": _sha(packed), "merged_ranges": MERGED_RANGES,
            "merged_range_vector_sha256": "a781ac704199e1412224376289d705c1ed4e2766065bcb3334d1495d3297b9ce"}


def _upstream(root: Path) -> dict[str, Any]:
    identities = ((TRAINING_DIR/MANIFEST_NAME,TRAINING_MANIFEST_SHA256),
        (TRAINING_DIR/"training-text-script-inventory.json",TRAINING_PAYLOAD_SHA256),
        (Path("tools/verify_rom_training_text_script_inventory.py"),TRAINING_VERIFIER_SHA256))
    for path, expected in identities:
        if _sha(_safe_file(root,path).read_bytes()) != expected: raise ValueError("training upstream identity changed")
    report = verify_training(root,(root/TRAINING_DIR).resolve(strict=True))
    if report.get("verified") is not True: raise ValueError("training upstream verification failed")
    return {"verified":True,"manifest_sha256":TRAINING_MANIFEST_SHA256,
        "payload_sha256":TRAINING_PAYLOAD_SHA256,"verifier_sha256":TRAINING_VERIFIER_SHA256}


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if len(rom) != ROM_SIZE: raise ValueError("ROM size changed")
    consumers, cfg_upstream = _consumer_denominator(root, rom); records = _records(rom)
    if verify_identity and _sha(rom) != ROM_SHA256: raise ValueError("ROM identity changed")
    claims = [{"id":f"fixed-renderer-script-{start:04x}","range":[start,end],
        "primary_class":PRIMARY_CLASS,"claim_kind":CLAIM_KIND,
        "bytes_sha256":_sha(rom[start:end])} for start,end,_ in RECORDS]
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":len(rom),"sha256":ROM_SHA256},
        "upstream_training_contract":_upstream(root),"upstream_cfg_contract":cfg_upstream,
        "consumer_denominator":consumers,"records":records,
        "promotion":{"claims":claims,"claim_count":30,"promotion_bytes":1124,
            "promotion_batch":SCHEMA,"promoted_from_primary_class":"unknown"},
        "scope":{"whole_rom_consumer_denominator":False,"startup_semantics":False,
            "opcode_7_or_8_semantics":False,"natural_runtime_reachability":False,
            "unicode_complete":False,"padding_or_free_space":False,"editing_or_relocation_safety":False}}


def build_payload(root: Path) -> dict[str, Any]:
    root=root.resolve(strict=True); return _build_from_rom(root,_safe_file(root,ROM_PATH).read_bytes())


def _publish_exclusive(source: Path,destination: Path) -> None:
    parent_fd=os.open(source.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        libc=ctypes.CDLL(None,use_errno=True)
        if sys.platform=="darwin": rename,flag=libc.renameatx_np,0x00000004
        elif hasattr(libc,"renameat2"): rename,flag=libc.renameat2,0x00000001
        else: raise OSError(errno.ENOTSUP,"atomic no-replace unavailable")
        rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];rename.restype=ctypes.c_int
        if rename(parent_fd,os.fsencode(source.name),parent_fd,os.fsencode(destination.name),flag):
            code=ctypes.get_errno();raise OSError(code,os.strerror(code),destination)
        os.fsync(parent_fd)
    finally: os.close(parent_fd)


def export_artifact(root: Path,output: Path) -> Path:
    root=root.resolve(strict=True);output=output if output.is_absolute() else root/output
    parent=output.parent.resolve(strict=True)
    if not parent.is_relative_to(root): raise ValueError("output escapes root")
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    payload=build_payload(root);relative=output.relative_to(root).as_posix();stage=Path(tempfile.mkdtemp(dir=parent,prefix=f".{output.name}."))
    try:
        payload_raw=_canonical(payload);(stage/PAYLOAD_NAME).write_bytes(payload_raw)
        manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"accepted",
            "files":{PAYLOAD_NAME:{"size":len(payload_raw),"sha256":_sha(payload_raw)}},
            "summary":{"consumer_site_count":41,"accepted_site_count":36,"record_count":30,"promotion_bytes":1124},
            "producer":{"command":["python3","tools/export_rom_fixed_renderer_script_records.py","--root",".","--output",relative]},
            "verifier":{"command":["python3","tools/verify_rom_fixed_renderer_script_records.py","--root",".","--artifact",relative]},
            "implementation":{"exporter_sha256":_sha(_safe_file(root,Path("tools/export_rom_fixed_renderer_script_records.py")).read_bytes()),
            "verifier_sha256":_sha(_safe_file(root,Path("tools/verify_rom_fixed_renderer_script_records.py")).read_bytes()),
            "test_sha256":_sha(_safe_file(root,Path("tests/test_export_rom_fixed_renderer_script_records.py")).read_bytes())}}
        (stage/MANIFEST_NAME).write_bytes(_canonical(manifest))
        for path in stage.iterdir():
            with path.open("rb") as handle: os.fsync(handle.fileno())
        fd=os.open(stage,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
        _publish_exclusive(stage,output)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return output


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--root",type=Path,default=Path("."));parser.add_argument("--output",type=Path,default=OFFICIAL);args=parser.parse_args();export_artifact(args.root,args.output);return 0


if __name__=="__main__": raise SystemExit(main())
