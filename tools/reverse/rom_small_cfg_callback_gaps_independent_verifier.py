"""Read-only raw verifier for the additive callback gap candidate.

The accepted upstream verifier rebuilds the complete callback instruction
closure. This module independently derives gaps and ownership; it never imports
the gap producer or claims to rerun the upstream registration lifecycle.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import sys

CONTRACT_SHA256 = "bc8d545f5bb9619935abc4fe52b4651967f3fe8d4dbd330cf2688fe74b18164a"


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_regular(path):
    """Anchor every path component and reject symlinks and nonregular leaves."""
    path = Path(path)
    if ".." in path.parts:
        raise ValueError("unsafe input path")
    path = path.absolute()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(leaf)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("input is not regular")
            chunks = []
            while chunk := os.read(leaf, 1024 * 1024):
                chunks.append(chunk)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if identity(before) != identity(os.fstat(leaf)):
                raise ValueError("input changed while reading")
            if identity(before) != identity(os.stat(path.name, dir_fd=fd, follow_symlinks=False)):
                raise ValueError("input member replaced")
            return b"".join(chunks)
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def read_pinned(root, identity):
    relative = Path(identity["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe pinned input")
    raw = read_regular(root / relative)
    if len(raw) != identity["size"] or sha(raw) != identity["sha256"]:
        raise ValueError(f"input identity: {relative}")
    return raw


def _ranges(rows, rom, alignment):
    previous = -1
    result = []
    for row in rows:
        if (not isinstance(row, list) or len(row) != 2
                or any(type(x) is not int for x in row)):
            raise ValueError("invalid range")
        a, b = row
        if not 0 <= a < b <= len(rom) or a < previous or a % alignment or b % alignment:
            raise ValueError("unordered or unaligned range")
        result.append((a, b))
        previous = b
    if not result:
        raise ValueError("empty domain")
    return result


def derive_boundaries(rom, closure):
    code = _ranges(closure["code_ranges"], rom, 2)
    literals = _ranges(closure["literal_ranges"], rom, 4)
    domains = sorted([(a, b, "code") for a, b in code]
                     + [(a, b, "literal") for a, b in literals])
    if any(first[1] > second[0] for first, second in zip(domains, domains[1:])):
        raise ValueError("overlapping domains")
    words = {o for a, b in literals for o in range(a, b, 4)}
    consumers = set()
    observed = set()
    bindings = []
    for source, target, raw_hex in closure["literal_bindings"]:
        if (source in consumers or source % 2
                or not any(a <= source and source + 2 <= b for a, b in code)):
            raise ValueError("literal source membership")
        h = int.from_bytes(rom[source:source + 2], "little")
        if h >> 11 != 9 or ((source + 4) // 4 + (h & 255)) * 4 != target:
            raise ValueError("literal load instruction")
        if target not in words or rom[target:target + 4].hex() != raw_hex:
            raise ValueError("literal consumed word")
        consumers.add(source)
        observed.add(target)
        bindings.append([source, target, raw_hex])
    if observed != words:
        raise ValueError("literal word denominator")
    rows = []
    for (a, b, left), (c, d, right) in zip(domains, domains[1:]):
        if (left, right) != ("code", "literal") or b == c:
            continue
        if c != ((b + 3) // 4) * 4 or c - b != 2 or rom[b:c] != b"\x00\x00":
            raise ValueError("raw align4 gap")
        offset = b - 2
        h = int.from_bytes(rom[offset:b], "little")
        terminal = {"offset": offset, "raw_hex": rom[offset:b].hex()}
        if h >> 11 == 28:
            signed = h & 2047
            if signed >= 1024:
                signed -= 2048
            target = offset + 4 + signed * 2
            if not any(start <= target < stop for start, stop in code):
                raise ValueError("branch target outside verified code")
            terminal.update(kind="unconditional_branch", target=target)
        elif h & 0xFF87 == 0x4700:
            terminal.update(kind="indirect_pc_target", register=(h >> 3) & 15)
        else:
            raise ValueError("fallthrough or unsupported terminal")
        rows.append({
            "id": f"task-callback-078e38-align4-{len(rows):02d}-{b:06x}",
            "kind": "artifact_bound_align4_bytes", "range": [b, c],
            "bytes_sha256": sha(rom[b:c]), "left_code_range": [a, b],
            "right_literal_range": [c, d],
            "right_literal_bindings": sorted(row for row in bindings if c <= row[1] < d),
            "terminal": terminal,
        })
    if [row["range"] for row in rows] != closure["holes"]:
        raise ValueError("gap versus complete source holes denominator")
    return rows


def _project(rows, baseline, source, contract, rom):
    segments = baseline["segments"]
    cursor = 0
    for segment in segments:
        start, end = segment["range"]
        if start != cursor or end <= start:
            raise ValueError("baseline segment denominator")
        cursor = end
    if cursor != len(rom):
        raise ValueError("baseline coverage domain")
    claims = {row["id"]: row for row in baseline["claims"]}
    source_claims = source["promotion"]["claims"]
    result = copy.deepcopy(rows)
    for row in result:
        provenance = {}
        for side, key in (("left", "left_code_range"), ("gap", "range"), ("right", "right_literal_range")):
            start, end = row[key]
            owners = [copy.deepcopy(s) for s in segments if s["range"][0] < end and start < s["range"][1]]
            if not owners:
                raise ValueError("missing owner segment")
            if side == "gap":
                if any(s["primary_class"] != "unknown" or s["primary_claim_ids"]
                       or s["secondary_claim_ids"] or not isinstance(s.get("unknown_reason"), str)
                       for s in owners):
                    raise ValueError("gap is not wholly unknown")
            else:
                matching = [(i, c) for i, c in enumerate(source_claims) if c["range"] == [start, end]]
                if len(matching) != 1:
                    raise ValueError("complete source owner range")
                index, source_claim = matching[0]
                owner = claims[source_claim["id"]]
                expected_kind = ("task_callback_078e38_closure_reachable_instruction_bytes" if side == "left"
                                 else "task_callback_078e38_closure_consumed_literal_word_bytes")
                if (owner["range"] != [start, end] or owner["role"] != "primary"
                        or owner["claim_kind"] != expected_kind
                        or owner["bytes_sha256"] != sha(rom[start:end])
                        or owner["evidence_path"] != contract["source_payload"]["path"]
                        or owner["evidence_sha256"] != contract["source_payload"]["sha256"]
                        or owner["evidence_selector"] != f"/promotion/claims/{index}"
                        or any(s["primary_claim_ids"] != [owner["id"]] for s in owners)):
                    raise ValueError("primary source owner identity")
            provenance[side] = owners
        row["baseline_owners"] = provenance
    return result


def verify_candidate(root, contract_path, candidate):
    root = Path(root).absolute()
    contract_raw = read_regular(contract_path)
    if sha(contract_raw) != CONTRACT_SHA256:
        raise ValueError("public contract identity")
    contract = json.loads(contract_raw)
    inputs = {pin["path"]: read_pinned(root, pin) for pin in contract["source_inputs"]}
    rom = read_pinned(root, contract["rom"])
    archive = read_pinned(root, contract["baseline_archive"])
    baseline_raw = gzip.decompress(archive)
    if len(baseline_raw) != contract["baseline_raw_size"] or sha(baseline_raw) != contract["baseline_raw_sha256"]:
        raise ValueError("immutable baseline identity")
    source = json.loads(inputs[contract["source_payload"]["path"]])
    baseline = json.loads(baseline_raw)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    upstream = importlib.import_module("tools.verify_rom_task_callback_078e38_closure")
    if Path(upstream.__file__).absolute() != root / "tools/verify_rom_task_callback_078e38_closure.py":
        raise ValueError("raw replay module path")
    closure = upstream._rebuild_closure(rom)
    if closure != source["closure"]:
        raise ValueError("raw source closure differs from accepted artifact")
    rows = derive_boundaries(rom, closure)
    if rows != contract["expected_boundaries"]:
        raise ValueError("derived boundary denominator")
    boundaries = _project(rows, baseline, source, contract, rom)
    summary = {
        "gap_count": len(rows), "promotion_bytes": sum(b - a for a, b in (r["range"] for r in rows)),
        "unconditional_branch_count": sum(r["terminal"]["kind"] == "unconditional_branch" for r in rows),
        "indirect_pc_target_count": sum(r["terminal"]["kind"] == "indirect_pc_target" for r in rows),
    }
    expected = {
        "schema": contract["output_schema"], "rom": contract["rom"],
        "source_inputs": contract["source_inputs"], "scope": contract["scope"],
        "baseline": {"archive_observed_during_this_build": False,
                     "archive_reference": contract["baseline_archive"],
                     "raw_sha256": contract["baseline_raw_sha256"], "raw_size": contract["baseline_raw_size"]},
        "summary": summary, "boundaries": boundaries,
        "promotion": {"claim_count": len(rows), "promotion_bytes": summary["promotion_bytes"],
                      "claims": [{k: r[k] for k in ("id", "kind", "range", "bytes_sha256")} for r in rows]},
    }
    if canonical(candidate) != canonical(expected):
        raise ValueError("candidate does not equal independent raw reconstruction")
    # Confirm all pinned source inputs still have their initial identities.
    for pin in contract["source_inputs"]:
        read_pinned(root, pin)
    return {
        "schema": "rom-task-callback-five-gaps-candidate-verification-v1", "verified": True,
        **summary, "candidate_payload_sha256": sha(canonical(candidate)),
        "public_contract_sha256": CONTRACT_SHA256,
        "source_inputs": contract["source_inputs"],
        "baseline_archive_observed_by_verifier": True,
        "baseline_archive": contract["baseline_archive"], "baseline_raw_sha256": sha(baseline_raw),
        "source_instruction_count": closure["instruction_count"],
        "source_literal_binding_count": len(closure["literal_bindings"]),
        "source_block_count": closure["basic_block_count"], "source_frontiers": closure["frontiers"],
        "source_full_lifecycle_replayed_here": False, "canonical_promoted": False,
        "scope": contract["scope"],
    }
