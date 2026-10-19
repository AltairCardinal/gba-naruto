"""Independent raw verification of the three frozen direct-wrapper roots.

No wrapper exporter imports. The accepted upstream raw decoders are reused
only to establish source instruction and opaque-entry membership.
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

CONTRACT_SHA256 = "065dae442f4f1276b6b41b42f5d5e56d550a043dea5a5a73090ab9fa886174ac"
CLAIM_FIELDS = {"id", "range", "claim_kind", "primary_class", "mode", "instruction_only_claimed",
                "evidence_path", "evidence_sha256", "evidence_selector", "independent_verifier_path",
                "independent_verifier_sha256", "promotion_manifest_path", "promotion_manifest_sha256"}


def canonical(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
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
                raise ValueError("nonregular input")
            chunks = []
            while chunk := os.read(leaf, 1024 * 1024):
                chunks.append(chunk)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if (identity(before) != identity(os.fstat(leaf)) or identity(before) != identity(
                    os.stat(path.name, dir_fd=fd, follow_symlinks=False))):
                raise ValueError("input changed during reading")
            return b"".join(chunks)
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def _pinned(root, pin):
    p = Path(pin["path"])
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("unsafe pinned path")
    raw = _read(root / p)
    if len(raw) != pin["size"] or sha(raw) != pin["sha256"]:
        raise ValueError(f"pinned input identity: {p}")
    return raw


def _branch(rom, offset):
    first = int.from_bytes(rom[offset:offset + 2], "little")
    if first >> 11 == 30 and offset + 4 <= len(rom):
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        if second >> 11 == 31:
            displacement = (first % 2048) * 4096 + (second % 2048) * 2
            if displacement >= 4194304:
                displacement -= 8388608
            return "thumb_bl", offset + 4 + displacement, 4
    if first >> 11 == 28:
        immediate = first % 2048
        return "thumb_b", offset + 4 + (immediate - (2048 if immediate >= 1024 else 0)) * 2, 2
    if first >> 12 == 13 and (first >> 8) % 16 < 14:
        immediate = first % 256
        return "thumb_bcond", offset + 4 + (immediate - (256 if immediate >= 128 else 0)) * 2, 2
    return None


def scan_producers(rom, targets):
    result = {target: [] for target in targets}
    for offset in range(0, len(rom) - 1, 2):
        item = _branch(rom, offset)
        if item is not None and item[1] in result:
            kind, target, size = item
            result[target].append({"kind": kind, "source": offset, "target": target,
                                   "size": size, "raw_hex": rom[offset:offset + size].hex()})
    return [row for target in targets for row in result[target]]


def _merge(rows):
    result = []
    for a, b in sorted(rows):
        if result and a == result[-1][1]:
            result[-1][1] = b
        elif result and a < result[-1][1]:
            raise ValueError("overlapping raw instructions")
        else:
            result.append([a, b])
    return result


def rebuild_closure(rom, contract):
    code = contract["code_ranges"]
    literals = contract["literal_ranges"]
    holes = contract["holes"]
    domains = sorted(code + literals + holes)
    if any(not 0 <= a < b <= len(rom) for a, b in domains) or any(
            a[1] > b[0] for a, b in zip(domains, domains[1:])):
        raise ValueError("invalid closure domains")
    inside = lambda o, size: any(a <= o and o + size <= b for a, b in code)
    todo = list(contract["roots"])
    nodes = {}
    occupied = set()
    bindings, frontiers = [], []
    while todo:
        offset = min(todo)
        todo.remove(offset)
        if offset in nodes:
            continue
        if offset % 2 or not inside(offset, 2) or offset in occupied:
            raise ValueError("raw worklist outside instruction boundary")
        h = int.from_bytes(rom[offset:offset + 2], "little")
        branch = _branch(rom, offset)
        if branch:
            kind, target, size = branch
            flow = {"thumb_bl": "call", "thumb_b": "unconditional_branch", "thumb_bcond": "conditional_branch"}[kind]
            edges = [{"kind": "call_target" if size == 4 else "branch_target", "target": target,
                      "scope": "opaque" if size == 4 and target in contract["opaque_entries"] else "internal"}]
            if kind != "thumb_b":
                edges.append({"kind": "fallthrough", "target": offset + size, "scope": "internal"})
        elif h & 0xFF87 == 0x4700:
            size, flow, edges = 2, "indirect_branch", []
            frontiers.append({"source": offset, "register": (h >> 3) & 15, "reason": "indirect_pc_target"})
        else:
            supported = (h < 0x2000 or h >> 11 in (6, 9, 13)
                         or h & 0xFE00 == 0xB400 and h & 0x1FF
                         or h & 0xFF00 == 0xBC00 and h & 255)
            if not supported:
                raise ValueError("unsupported raw Thumb-1 instruction")
            size, flow = 2, "linear"
            edges = [{"kind": "fallthrough", "target": offset + 2, "scope": "internal"}]
        if not inside(offset, size) or any(o in occupied for o in range(offset, offset + size)):
            raise ValueError("raw instruction overlap or truncated BL")
        occupied.update(range(offset, offset + size))
        node = {"offset": offset, "size": size, "raw_hex": rom[offset:offset + size].hex(),
                "flow": flow, "edges": edges}
        nodes[offset] = node
        for edge in edges:
            if edge["scope"] == "internal":
                target = edge["target"]
                if target % 2 or not inside(target, 2):
                    raise ValueError("raw successor enters literal, hole or outside code")
                todo.append(target)
        if size == 2 and h >> 11 == 9:
            word = ((offset + 4) // 4 + (h % 256)) * 4
            if not any(a <= word and word + 4 <= b for a, b in literals):
                raise ValueError("raw literal outside declared range")
            bindings.append([offset, word, rom[word:word + 4].hex()])
    ordered = [nodes[o] for o in sorted(nodes)]
    if _merge((o, o + row["size"]) for o, row in nodes.items()) != code:
        raise ValueError("complete raw code denominator")
    if {r[1] for r in bindings} != {o for a, b in literals for o in range(a, b, 4)}:
        raise ValueError("complete raw literal denominator")
    predecessors = {o: [] for o in nodes}
    for o, node in nodes.items():
        for edge in node["edges"]:
            if edge["scope"] == "internal":
                if edge["target"] not in nodes:
                    raise ValueError("successor enters instruction middle")
                predecessors[edge["target"]].append(o)
    starts = set(contract["roots"])
    for offset, incoming in predecessors.items():
        if len(incoming) != 1 or nodes[incoming[0]]["flow"] != "linear":
            starts.add(offset)
    blocks = []
    for start in sorted(starts):
        last = start
        while nodes[last]["flow"] == "linear":
            nxt = last + nodes[last]["size"]
            if nxt in starts:
                break
            last = nxt
        blocks.append([start, last + nodes[last]["size"]])
    summary = {"root_count": len(contract["roots"]), "instruction_count": len(nodes),
               "basic_block_count": len(blocks), "code_bytes": len(occupied),
               "literal_bytes": sum(b - a for a, b in literals),
               "promotion_bytes": len(occupied) + sum(b - a for a, b in literals),
               "claim_count": len(code) + len(literals), "frontier_count": len(frontiers),
               "structured_return_count": 0,
               "opaque_call_count": sum(e["scope"] == "opaque" for n in ordered for e in n["edges"]),
               "producer_count": len(contract["expected_producers"])}
    result = {"nodes": ordered, "blocks": blocks, "code_ranges": code, "literal_ranges": literals,
              "literal_bindings": sorted(bindings), "frontiers": sorted(frontiers, key=lambda r: r["source"]),
              "holes": holes, "summary": summary}
    for key in ("nodes", "blocks", "literal_bindings", "frontiers", "summary"):
        if result[key] != contract["expected_" + key]:
            raise ValueError(f"raw closure {key} differs from frozen contract")
    return result


def _owners(baseline, start, end):
    return [copy.deepcopy(s) for s in baseline["segments"] if s["range"][0] < end and start < s["range"][1]]


def _source_replay(root, rom, blobs, producers, baseline):
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise ValueError("decoder library override")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    event = importlib.import_module("tools.verify_rom_event_handler_cfg")
    text_bg = importlib.import_module("tools.verify_rom_text_bg_task_closure")
    inventory = importlib.import_module("tools.verify_rom_cfg_inventory")
    for module in (event, text_bg, inventory):
        expected = root / "tools" / (module.__name__.split(".")[-1] + ".py")
        if Path(module.__file__).absolute() != expected:
            raise ValueError("raw decoder module path")
    inventory._decoder_identity(root)
    event._assert_oracle_identities(root)
    event_payload = json.loads(blobs["artifacts/rom-event-handler-cfg-v1/rom-event-handler-cfg.json"])
    cfg, promotion = event._rebuild(rom)
    if cfg != event_payload["cfg"] or promotion != event_payload["promotion"]:
        raise ValueError("event-handler raw closure identity")
    event_members = {}
    for entry in event.C.ACCEPTED_ROOTS:
        nodes, _, _ = event._decode_root(rom, entry)
        for (_, offset), node in nodes.items():
            event_members.setdefault(offset, []).append((entry, node))
    bg_payload = json.loads(blobs["artifacts/rom-text-bg-task-closure-v1/rom-text-bg-task-closure.json"])
    bg_closure = text_bg._rebuild_closure(rom)
    if bg_closure != bg_payload["closure"]:
        raise ValueError("text-BG raw closure identity")
    bg_members = {}
    for spec in text_bg.ROOT_SPECS:
        nodes, _ = text_bg._walk_root(rom, *spec)
        for offset, size in nodes.items():
            bg_members.setdefault(offset, []).append((spec[1], size))
    claims = {c["id"]: c for c in baseline["claims"]}
    memberships = []
    for row in producers:
        site, target = row["source"], row["target"]
        is_bg = site == 0x8C800
        entries = bg_members.get(site, []) if is_bg else event_members.get(site, [])
        if not entries or any((value if is_bg else value["size"]) != row["size"] for _, value in entries):
            raise ValueError("producer lacks upstream raw instruction membership")
        artifact_path = ("artifacts/rom-text-bg-task-closure-v1/rom-text-bg-task-closure.json" if is_bg
                         else "artifacts/rom-event-handler-cfg-v1/rom-event-handler-cfg.json")
        kind = ("text_bg_task_closure_reachable_instruction_bytes" if is_bg else "event_handler_reachable_instruction_bytes")
        owner_ids = []
        for segment in _owners(baseline, site, site + row["size"]):
            if len(segment["primary_claim_ids"]) != 1:
                raise ValueError("producer primary owner")
            claim = claims[segment["primary_claim_ids"][0]]
            if claim["claim_kind"] != kind or claim["evidence_path"] != artifact_path or claim["evidence_sha256"] != sha(blobs[artifact_path]):
                raise ValueError("producer source artifact owner")
            owner_ids.append(claim["id"])
        memberships.append({"source": site, "target": target, "size": row["size"],
                            "upstream_payload": artifact_path,
                            "accepted_roots_reaching_source": sorted(entry for entry, _ in entries),
                            "owner_claim_ids": sorted(set(owner_ids))})
    opaque = []
    for entry, artifact_path in (
        (0x7ADBC, "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"),
        (0x7B888, "artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json"),
    ):
        payload = json.loads(blobs[artifact_path])
        blocks = payload.get("blocks", payload.get("extension", {}).get("blocks", []))
        selected = [b for b in blocks if b["range"][0] == entry and b["mode"] == "thumb"]
        if len(selected) != 1:
            raise ValueError("opaque entry is not an accepted block start")
        _, entries, _, _ = inventory._verify_blocks(rom, selected)
        if ("thumb", entry) not in entries:
            raise ValueError("opaque entry raw instruction boundary")
        segments = _owners(baseline, *selected[0]["range"])
        owners = [claims[cid] for s in segments for cid in s["primary_claim_ids"]]
        if not owners or any(c["evidence_path"] != artifact_path or c.get("mode") != "thumb" for c in owners):
            raise ValueError("opaque entry canonical owner")
        opaque.append({"entry": entry, "block": selected[0], "owner_claim_ids": sorted({c["id"] for c in owners}),
                       "upstream_payload": artifact_path})
    return {"producer_instruction_membership": memberships, "opaque_entry_membership": opaque,
            "upstream_event_instruction_count": cfg["instruction_count"],
            "upstream_text_bg_instruction_count": bg_closure["instruction_count"],
            "upstream_whole_verifiers_replayed_here": False,
            "source_full_lifecycle_replayed_here": False}


def verify_candidate(root, contract_path, candidate):
    root = Path(root).absolute()
    raw = _read(contract_path)
    if sha(raw) != CONTRACT_SHA256:
        raise ValueError("public contract identity")
    contract = json.loads(raw)
    rom = _pinned(root, contract["rom"])
    blobs = {p["path"]: _pinned(root, p) for p in contract["upstream_inputs"]}
    baseline_raw = gzip.decompress(_pinned(root, contract["baseline_archive"]))
    if len(baseline_raw) != contract["baseline_raw_size"] or sha(baseline_raw) != contract["baseline_raw_sha256"]:
        raise ValueError("immutable baseline identity")
    baseline = json.loads(baseline_raw)
    cursor = 0
    for segment in baseline["segments"]:
        a, b = segment["range"]
        if a != cursor or b <= a:
            raise ValueError("baseline partition")
        cursor = b
    if cursor != len(rom):
        raise ValueError("baseline domain")
    claims = {row["id"]: row for row in baseline["claims"]}
    producers = scan_producers(rom, contract["roots"])
    for row in producers:
        a, b = row["source"], row["source"] + row["size"]
        row["owners"] = [{"intersection": [max(a, s["range"][0]), min(b, s["range"][1])],
                          "segment": s, "claims": [{k: v for k, v in claims[cid].items() if k in CLAIM_FIELDS}
                                                     for cid in s["primary_claim_ids"]]}
                         for s in _owners(baseline, a, b)]
    if producers != contract["expected_producers"]:
        raise ValueError("raw full-ROM target-limited producer denominator")
    pointers = {}
    for entry in contract["roots"]:
        value = 0x08000001 + entry
        needle = value.to_bytes(4, "little")
        occurrences, start = [], 0
        while (offset := rom.find(needle, start)) >= 0:
            occurrences.append(offset)
            start = offset + 1
        pointers[hex(value)] = occurrences
    if pointers != contract["root_pointer_occurrences"]:
        raise ValueError("root pointer occurrence denominator")
    closure = rebuild_closure(rom, contract)
    promotion = []
    for a, b, kind in sorted([[a, b, "reachable_thumb_code"] for a, b in closure["code_ranges"]]
                             + [[a, b, "consumed_literal_words"] for a, b in closure["literal_ranges"]]):
        owners = _owners(baseline, a, b)
        if not owners or any(s["primary_class"] != "unknown" or s["primary_claim_ids"] or s["secondary_claim_ids"] for s in owners):
            raise ValueError("promotion is not wholly unknown")
        promotion.append({"id": f"three-direct-wrapper-{kind}-{len(promotion):02d}-{a:06x}",
                          "kind": kind, "range": [a, b], "bytes_sha256": sha(rom[a:b]), "baseline_owners": owners})
    expected = {"schema": contract["output_schema"], "rom": contract["rom"],
                "upstream_inputs": contract["upstream_inputs"], "roots": contract["roots"],
                "producers": producers, "root_pointer_occurrences": pointers, "scope": contract["scope"],
                "baseline": {"archive_reference": contract["baseline_archive"], "archive_observed_during_this_build": False,
                             "raw_sha256": sha(baseline_raw), "raw_size": len(baseline_raw)},
                "closure": closure,
                "promotion": {"claim_count": len(promotion), "promotion_bytes": closure["summary"]["promotion_bytes"], "claims": promotion}}
    if canonical(candidate) != canonical(expected):
        raise ValueError("candidate differs from independent raw reconstruction")
    upstream = _source_replay(root, rom, blobs, producers, baseline)
    for pin in contract["upstream_inputs"]:
        _pinned(root, pin)
    return {"schema": "rom-three-direct-wrapper-candidate-verification-v1", "verified": True,
            **closure["summary"], **upstream, "scope": contract["scope"], "canonical_promoted": False,
            "public_contract_sha256": CONTRACT_SHA256, "candidate_payload_sha256": sha(canonical(candidate)),
            "upstream_inputs": contract["upstream_inputs"],
            "baseline_archive_observed_by_verifier": True, "baseline_archive": contract["baseline_archive"],
            "baseline_raw_sha256": sha(baseline_raw)}
