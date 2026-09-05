#!/usr/bin/env python3
"""Export the dependency-gated target-local CFG proven-roots v19 packet."""

from __future__ import annotations

import argparse, bisect, gzip, hashlib, json, shutil, struct, sys, tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_path) not in sys.path: sys.path.insert(0, str(_path))

from tools.export_rom_cfg_inventory import _build_blocks, _frontier_records
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks
from tools.export_rom_cfg_proven_roots_v2 import _traverse_delta
from tools.export_rom_cfg_proven_roots_v4 import _load_payload
from tools.export_rom_cfg_proven_roots_v7 import _baselines
from tools.rom_cfg_proven_roots_v19_contract import *
from tools.thumb_branch import decode_thumb_b, decode_thumb_bl


def _sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def _canonical(value: object) -> bytes: return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
def _vsha(value: object) -> str: return _sha((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())


def _safe(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True); path = root / relative; resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or path.is_symlink(): raise ValueError(f"unsafe input path: {relative}")
    return resolved


def _baseline(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    manifest_raw = _safe(root, PRECOVERAGE_DIR / MANIFEST_NAME).read_bytes()
    archive_raw = _safe(root, PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()
    if _sha(manifest_raw) != PRECOVERAGE_MANIFEST_SHA256 or len(archive_raw) != PRECOVERAGE_ARCHIVE_SIZE or _sha(archive_raw) != PRECOVERAGE_ARCHIVE_SHA256: raise ValueError("immutable precoverage identity changed")
    expected = {"compression":"gzip","sha256":PRECOVERAGE_ARCHIVE_SHA256,"size":PRECOVERAGE_ARCHIVE_SIZE,"uncompressed_sha256":PRECOVERAGE_RAW_SHA256,"uncompressed_size":PRECOVERAGE_RAW_SIZE}
    if json.loads(manifest_raw) != {"files":{"rom-byte-coverage.json.gz":expected},"schema":"rom-byte-coverage-precoverage-v1"}: raise ValueError("immutable precoverage manifest changed")
    raw = gzip.decompress(archive_raw)
    if len(raw) != PRECOVERAGE_RAW_SIZE or _sha(raw) != PRECOVERAGE_RAW_SHA256: raise ValueError("immutable precoverage payload changed")
    coverage = json.loads(raw); summary = coverage.get("summary", {})
    if any(summary.get(k) != v for k, v in BASELINE.items()): raise ValueError("immutable precoverage summary changed")
    segments = coverage.get("segments"); starts = []; cursor = 0
    if not isinstance(segments, list) or len(segments) != BASELINE["segment_count"]: raise ValueError("precoverage segment denominator changed")
    for row in segments:
        interval = row.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or interval[1] <= cursor: raise ValueError("precoverage segment order changed")
        starts.append(cursor); cursor = interval[1]
    if cursor != ROM_SIZE: raise ValueError("precoverage accounting changed")
    return {"artifact":PRECOVERAGE_DIR.as_posix(),"manifest_sha256":PRECOVERAGE_MANIFEST_SHA256,"archive_sha256":PRECOVERAGE_ARCHIVE_SHA256,"raw_sha256":PRECOVERAGE_RAW_SHA256,**BASELINE}, segments, starts


def _segment(segments: list[dict[str, Any]], starts: list[int], offset: int) -> dict[str, Any]:
    row = segments[bisect.bisect_right(starts, offset) - 1]
    if not row["range"][0] <= offset < row["range"][1]: raise ValueError("coverage lookup failed")
    return row


def _upstream(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = _safe(root, Path(UPSTREAM_ARTIFACT)); manifest_raw = _safe(root, Path(UPSTREAM_ARTIFACT) / MANIFEST_NAME).read_bytes(); payload_raw = _safe(root, Path(UPSTREAM_ARTIFACT) / "rom-boot-interwork-continuation.json").read_bytes()
    if (len(manifest_raw), _sha(manifest_raw), len(payload_raw), _sha(payload_raw)) != (UPSTREAM_MANIFEST_SIZE, UPSTREAM_MANIFEST_SHA256, UPSTREAM_PAYLOAD_SIZE, UPSTREAM_PAYLOAD_SHA256): raise ValueError("upstream continuation artifact identity changed")
    manifest = json.loads(manifest_raw); payload = json.loads(payload_raw)
    if _canonical(manifest) != manifest_raw or _canonical(payload) != payload_raw: raise ValueError("upstream continuation JSON is not canonical")
    from tools.verify_rom_boot_interwork_continuation import verify_root
    report = verify_root(root, artifact)
    if not report.get("verified") or report.get("promotion_bytes") != 94: raise ValueError("upstream continuation independent verification failed")
    claims = payload.get("promotion", {}).get("claims", [])
    claim = next((row for row in claims if row.get("id") == UPSTREAM_CODE_CLAIM_ID), None)
    if claim is None or tuple(claim.get("range", ())) != UPSTREAM_CODE_RANGE or claim.get("kind") not in (None, "reachable_thumb_code"): raise ValueError("upstream continuation code claim changed")
    if not (UPSTREAM_CODE_RANGE[0] <= PRODUCER[0] and PRODUCER[0] + 4 <= UPSTREAM_CODE_RANGE[1]): raise ValueError("producer escaped upstream code claim")
    ref = {"artifact_dir":UPSTREAM_ARTIFACT,"manifest_sha256":UPSTREAM_MANIFEST_SHA256,"payload_sha256":UPSTREAM_PAYLOAD_SHA256,"verified":True,"promotion_bytes":94,"dependency_claim_id":UPSTREAM_CODE_CLAIM_ID,"dependency_code_range":list(UPSTREAM_CODE_RANGE)}
    return ref, claim


def _direct_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    half = struct.unpack_from("<H", rom, offset)[0]
    if offset + 4 <= len(rom):
        target = decode_thumb_bl(offset, half, struct.unpack_from("<H", rom, offset + 2)[0])
        if target is not None: return "bl", target
    target = decode_thumb_b(offset, half)
    if target is not None: return "b", target
    if half & 0xF000 == 0xD000 and ((half >> 8) & 15) < 14:
        disp = (half & 255) << 1
        if disp & 0x100: disp -= 0x200
        return "bcond", offset + 4 + disp
    return None


def _producer(rom: bytes) -> dict[str, Any]:
    denominator = {"decoder_kinds":["thumb_bl","thumb_b","thumb_bcond"],"rom_range":[0,len(rom)],"stride":2,"target_file_offset":ROOT}
    if _vsha(denominator) != PRODUCER_SCAN_DENOMINATOR_SHA256: raise ValueError("producer scan denominator changed")
    matches = []
    for offset in range(0, len(rom) - 1, 2):
        branch = _direct_target(rom, offset)
        if branch and branch[1] == ROOT: matches.append([offset, ROOT, branch[0], 4 if branch[0] == "bl" else 2, rom[offset:offset+(4 if branch[0] == "bl" else 2)].hex()])
    if _vsha(matches) != PRODUCER_VECTOR_SHA256 or matches != [[*PRODUCER[:2], PRODUCER[2], 4, PRODUCER[3]]]: raise ValueError("target-limited producer vector changed")
    if _sha(rom[PRODUCER[0]:PRODUCER[0]+4]) != PRODUCER_PACKED_SHA256: raise ValueError("producer bytes changed")
    return {"file_offset":PRODUCER[0],"target_file_offset":ROOT,"kind":"bl","size":4,"raw_hex":PRODUCER[3],"owner_source":"validated_upstream_dependency","owner_claim_id":UPSTREAM_CODE_CLAIM_ID,"accepted_as_root_proof":True}


def _merge(rows: list[tuple[int, int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for start, end in sorted(rows):
        if out and start <= out[-1][1]: out[-1][1] = max(out[-1][1], end)
        else: out.append([start, end])
    return out


def _traversal(root: Path, rom: bytes) -> tuple[dict[str, Any], list[list[int]], list[list[int]]]:
    _, baseline_nodes, baseline_owners, _ = _baselines(root, rom)
    v7 = _load_payload(root, V7_PAYLOAD_PATH, V7_PAYLOAD_SHA256); n7, o7 = _nodes_from_blocks(rom, v7["extension"]["blocks"], label="proven_roots_v7"); baseline_nodes["proven_roots_v7"], baseline_owners["proven_roots_v7"] = n7, o7
    roots = [{"root_id":f"root-thumb-{ROOT:06x}","mode":"thumb","file_offset":ROOT,"gba_address":f"0x{ROM_BASE+ROOT:08X}","entry_size":4,"entry_sha256":_sha(rom[ROOT:ROOT+4]),"sources":[{"file_offset":PRODUCER[0]}]}]
    if roots[0]["entry_sha256"] != ROOT_ENTRY_SHA256: raise ValueError("root entry changed")
    nodes, rejected, incoming, crosses = _traverse_delta(rom, roots, baseline_nodes); blocks, mapping = _build_blocks(rom, nodes, {("thumb", ROOT)}); frontiers = _frontier_records(nodes, rejected, incoming, roots, mapping)
    code = _merge([(offset, offset + node["size"]) for (_, offset), node in nodes.items()])
    if tuple(map(tuple, code)) != CODE_RANGES or _vsha(code) != CODE_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in code)) != CODE_PACKED_SHA256: raise ValueError("target code denominator changed")
    bindings = []
    for (_, offset), node in sorted(nodes.items()):
        if node["size"] == 2:
            half = struct.unpack_from("<H", rom, offset)[0]
            if half & 0xF800 == 0x4800:
                target = ((offset + 4) & ~3) + (half & 255) * 4
                if TARGET_RANGE[0] <= target and target + 4 <= TARGET_RANGE[1]: bindings.append([offset,target,rom[offset:offset+2].hex(),rom[target:target+4].hex()])
    literals = _merge([(target, target + 4) for target in sorted({row[1] for row in bindings})])
    if tuple(map(tuple,literals)) != LITERAL_RANGES or _vsha(literals) != LITERAL_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in literals)) != LITERAL_PACKED_SHA256 or _vsha(bindings) != LITERAL_BINDING_VECTOR_SHA256: raise ValueError("literal denominator changed")
    frontier_rows = [[row["source"]["instruction_offset"], row["reason"]] for row in frontiers]
    opaque = sorted([[source[1], target[1]] for source, kind, _, target in crosses if kind == "call_target"])
    metrics = {"instruction_count":len(nodes),"instruction_bytes":sum(b-a for a,b in code),"basic_block_count":len(blocks),"decode_reject_count":len(rejected),"baseline_call_edge_count":len(crosses),"frontier_count":len(frontiers),"unique_literal_word_count":len({row[1] for row in bindings}),"literal_reference_count":len(bindings),"literal_bytes":sum(b-a for a,b in literals)}
    if metrics != METRICS or tuple(map(tuple,frontier_rows)) != FRONTIERS or tuple(map(tuple,opaque)) != OPAQUE_CALLS or any(row[1] != "call_target" for row in crosses):
        raise ValueError(f"target CFG boundary changed: metrics={metrics!r}, frontiers={frontier_rows!r}, opaque={opaque!r}, crosses={crosses!r}")
    return {**metrics,"frontiers":frontier_rows,"opaque_baseline_calls":opaque,"literal_binding_vector_sha256":_vsha(bindings)}, code, literals


def _implementation(root: Path) -> dict[str, Any]: return {"binding":"contract-exporter-verifier-tests-hash-bound","paths":{k:p.as_posix() for k,p in IMPLEMENTATION_PATHS.items()},**{f"{k}_sha256":_sha(_safe(root,p).read_bytes()) for k,p in IMPLEMENTATION_PATHS.items()}}


def _frozen_baseline_entry(root: Path, target: int) -> dict[str, Any]:
    mr=_safe(root,V2_ARTIFACT/MANIFEST_NAME).read_bytes();pr=_safe(root,V2_ARTIFACT/V2_PAYLOAD_NAME).read_bytes()
    if (len(mr),_sha(mr),len(pr),_sha(pr))!=(V2_MANIFEST_SIZE,V2_MANIFEST_SHA256,V2_PAYLOAD_SIZE,V2_PAYLOAD_SHA256):raise ValueError("frozen v2 baseline identity changed")
    manifest=json.loads(mr);payload=json.loads(pr)
    if manifest.get("artifact_schema")!="rom-cfg-inventory-v2" or manifest.get("files",{}).get(V2_PAYLOAD_NAME)!={"sha256":V2_PAYLOAD_SHA256,"size":V2_PAYLOAD_SIZE} or payload.get("schema")!="rom-cfg-inventory-v2" or payload.get("rom",{}).get("sha256")!=ROM_SHA256:raise ValueError("frozen v2 baseline contract changed")
    matches=[row for row in payload.get("blocks",[]) if row.get("range",[None])[0]==target]
    if len(matches)!=1:raise ValueError("opaque target is not a unique frozen baseline block entry")
    row=matches[0];owner={"artifact":V2_ARTIFACT.as_posix(),"block_id":row.get("id"),"mode":row.get("mode"),"range":row.get("range"),"bytes_sha256":row.get("bytes_sha256")}
    if owner!=OPAQUE_BASELINE_ENTRY:raise ValueError("opaque frozen baseline owner changed")
    return owner


def build_payload(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True); rom = _safe(root, ROM_PATH).read_bytes() if rom_override is None else rom_override
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256: raise ValueError("base ROM identity changed")
    baseline, segments, starts = _baseline(root); upstream, _ = _upstream(root); producer = _producer(rom); denominator, code, literals = _traversal(root, rom); denominator["opaque_baseline_entry"]=_frozen_baseline_entry(root,0x063604)
    for start, end in code + literals:
        cursor = start
        while cursor < end:
            owner = _segment(segments, starts, cursor)
            if owner.get("primary_class") != "unknown": raise ValueError("target promotion escaped immutable baseline unknown")
            cursor = min(end, owner["range"][1])
    union = _merge([(a,b) for a,b in code+literals])
    if tuple(map(tuple,union)) != UNION_RANGES or _vsha(union) != UNION_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in union)) != UNION_PACKED_SHA256 or _vsha([list(x) for x in HOLES]) != HOLE_RANGE_SHA256 or _sha(b"".join(rom[a:b] for a,b in HOLES)) != HOLE_PACKED_SHA256: raise ValueError("target union/hole denominator changed")
    claims = [{"id":f"cfg-v19-{kind}-{i:02d}-{a:06x}","kind":kind,"range":[a,b],"bytes_sha256":_sha(rom[a:b])} for kind,rows in (("reachable_thumb_code",code),("consumed_literal_words",literals)) for i,(a,b) in enumerate(rows,1)]
    promotion = {"promotion_batch":SCHEMA,"primary_class":"armv4t_cfg_proven_roots_v19","claim_kind":"armv4t_cfg_proven_roots_v19_exact_bytes","target_range":list(TARGET_RANGE),"code_ranges":code,"literal_ranges":literals,"union_ranges":union,"preserved_unknown_gaps":[list(x) for x in HOLES],"code_bytes":1600,"literal_bytes":60,"promotion_bytes":1660,"preserved_unknown_bytes":12,"claims":claims}
    return {"schema":SCHEMA,"rom":{"path":ROM_PATH.as_posix(),"size":ROM_SIZE,"sha256":ROM_SHA256},"precoverage":baseline,"upstream_continuation_artifact":upstream,"dependency_dag":{"edges":[["immutable_precoverage","boot_interwork_continuation"],["boot_interwork_continuation","cfg_proven_roots_v19"]],"cycle_free":True,"atomic_projection_required":True},"root":{"file_offset":ROOT,"entry_sha256":ROOT_ENTRY_SHA256},"accepted_producers":[producer],"target_local_denominator":denominator,"promotion":promotion,"coverage_projection":{"baseline_unknown_bytes":BASELINE["unknown_bytes"],"dependency_promoted_bytes":94,"target_promoted_bytes":1660,"atomic_remaining_unknown_bytes":BASELINE["unknown_bytes"]-1754},"implementation":_implementation(root),"scope":{"raw_rom_redecoded":True,"target_limited_direct_producer_denominator":True,"producer_owner_is_validated_dependency_overlay":True,"natural_runtime_reachability":False,"target_outside_subtree_classification":False,"alignment_gap_classification":False}}


def export(root: Path, output: Path) -> dict[str, Any]:
    root=root.resolve(strict=True); lexical=(output if output.is_absolute() else root/output).absolute(); output=lexical.resolve(strict=False); allowed=(root/EXPERIMENT_OUTPUT_ROOT).resolve(); official=(root/OFFICIAL_ARTIFACT).resolve(strict=False)
    if output != lexical or not (output.is_relative_to(allowed) or output == official) or lexical.is_symlink(): raise ValueError("output outside v19 scope or uses a symlink ancestor")
    payload=build_payload(root); raw=_canonical(payload); rel=output.relative_to(root).as_posix(); from tools import verify_rom_cfg_proven_roots_v19 as verifier
    manifest={"schema":"git-artifact-promotion-v1","artifact_schema":SCHEMA,"artifact_status":"candidate","rom":payload["rom"],"precoverage":payload["precoverage"],"upstream_continuation_artifact":payload["upstream_continuation_artifact"],"dependency_dag":payload["dependency_dag"],"implementation":payload["implementation"],"promotion":payload["promotion"],"coverage_projection":payload["coverage_projection"],"scope":payload["scope"],"producer":{"command":["python3","-I","-S","tools/export_rom_cfg_proven_roots_v19.py","--root",".","--output",rel]},"verifier":{"command":["python3","-I","-S","tools/verify_rom_cfg_proven_roots_v19.py","--root",".","--artifact",rel],"exit_code":None},"files":{PAYLOAD_NAME:{"sha256":_sha(raw),"size":len(raw)}}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix=".v19-") as temp:
        stage=Path(temp)/output.name; stage.mkdir(); (stage/PAYLOAD_NAME).write_bytes(raw); (stage/MANIFEST_NAME).write_bytes(_canonical(manifest)); report=verifier.verify_root(root,stage,expected_receipt_path=output)
        if not report["verified"]: raise ValueError(report["errors"])
        manifest["artifact_status"]="accepted"; manifest["verifier"].update({"exit_code":0,"report":report}); (stage/MANIFEST_NAME).write_bytes(_canonical(manifest))
        if output.exists():
            if not output.is_dir() or any(output.iterdir()): raise ValueError("output must be absent or empty")
            output.rmdir()
        shutil.move(stage,output)
    return manifest


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,required=True); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args(); export(args.root,args.output); return 0


if __name__ == "__main__": raise SystemExit(main())
