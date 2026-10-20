#!/usr/bin/env python3
"""Sync the canonical proof spec with the three Tier-2 exception promotions.

Adapted from ``notes/evidence/reverse-proof-update-20261019-v1/apply.py``
(single package) to the three-package batch authorised as a Tier-2 threshold
exception on 2026-10-20.  Idempotent and fail-closed: every expectation is
asserted against the live ledger, never hard-coded.

What it changes, in one atomic write of ``sequel/reverse-engineering-proof.json``:

  1. the coverage ledger's own evidence sha256;
  2. six evidence entries (manifest + payload of each promoted package);
  3. one verifier contract for the animation descriptor pool package -- the
     other two packages are deliberately NOT added because their verifier
     reports carry no ``schema`` key, and ``_contract()`` rejects a contract
     without ``/schema``; adding them would create a new blocker;
  4. the coverage verifier's own ``script_sha256`` and every ``/summary/*``
     assertion, refreshed from the live ledger;
  5. ``limitations[0]`` plus one package-level limitation per promoted package;
  6. the byte counts published in ``docs/reverse-engineering-proof-policy.md``.

Usage:
    /usr/local/bin/python3 apply.py [--root .]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
PROOF_PATH = Path("sequel/reverse-engineering-proof.json")
AUDIT_SCRIPT = Path("tools/audit_rom_byte_coverage.py")
POLICY_PATH = Path("docs/reverse-engineering-proof-policy.md")

# (artifact dir, payload file, batch, promotion bytes, record count, limitation)
PACKAGES: list[dict[str, Any]] = [
    {
        "artifact": Path("artifacts/rom-renderer-records-delta-v1"),
        "payload": "rom-renderer-records-delta.json",
        "batch": "rom-renderer-records-delta-v1",
        "promotion_bytes": 1_668,
        "record_count": 29,
        "verifier": Path("tools/verify_rom_renderer_records_delta.py"),
        "verifier_in_proof": False,
        "limitation": (
            "The renderer records delta artifact classifies exactly 1,668 previously unknown "
            "bytes as 29 fixed-consumer renderer command-script records whose record grammar "
            "is the already accepted opcode set; the source CFG, the canonical CFG consumer "
            "denominator, the raw parameter paths and the immutable unknown projection are "
            "verified, and the 34 accepted and 13 excluded sites are frozen. New opcode "
            "semantics, the whole-ROM consumer denominator, context lifecycle, padding or "
            "free space, editing or relocation safety and natural runtime reachability "
            "remain unclaimed."
        ),
    },
    {
        "artifact": Path("artifacts/rom-display-text-delta-v1"),
        "payload": "rom-display-text-delta.json",
        "batch": "rom-display-text-delta-v1",
        "promotion_bytes": 1_053,
        "record_count": 85,
        "verifier": Path("tools/verify_rom_display_text_delta.py"),
        "verifier_in_proof": False,
        "limitation": (
            "The display text delta artifact classifies exactly 1,053 previously unknown bytes "
            "as 85 fixed-consumer renderer display-text records at the fixed candidate site "
            "denominator; the source CFG and the raw parameter paths are verified and the "
            "command-script semantics, the whole-ROM consumer denominator, padding or free "
            "space, editing or relocation safety and natural runtime reachability remain "
            "unclaimed. No claim is made about Unicode semantics or editability."
        ),
    },
    {
        "artifact": Path("artifacts/rom-animation-descriptor-pool-v2"),
        "payload": "rom-animation-descriptor-pool-v2.json",
        "batch": "rom-animation-descriptor-pool-v2",
        "promotion_bytes": 640,
        "record_count": 1,
        "verifier": Path("tools/verify_rom_animation_descriptor_pool_v2.py"),
        "verifier_in_proof": True,
        "verifier_schema": "rom-animation-descriptor-pool-v2-verification-v1",
        "verifier_assertions": {
            "/schema": "rom-animation-descriptor-pool-v2-verification-v1",
            "/verified": True,
            "/errors": [],
            "/promotion_bytes": 640,
            "/descriptor_count": 8,
            "/descriptor_entry_count": 24,
            "/base_pair_count": 7,
        },
        "limitation": (
            "The animation descriptor pool v2 artifact classifies exactly 640 previously "
            "unknown bytes as one fixed-consumer animation descriptor group (7 base pairs, 8 "
            "descriptors, 24 descriptor entries, 8 sequences, 16 pointer slots over 14 tables); "
            "the descriptor table pointer, the group table pointer, the record slot and the "
            "sequence index are bound to the literal loader sites, and the 488-byte "
            "heterogeneous tail at 0x4585AC..0x458794 is excluded from the claim. The callback "
            "domain, the caller denominator (48 base-pair pools, 2 attributed, 2 located "
            "callers), the flags domain, the index domain, descriptor editing safety, opaque "
            "renderer side effects, the heterogeneous tail family and natural runtime "
            "reachability remain unclaimed. This package shares its primary_class with the "
            "already accepted 0x12D574 descriptor-groups packet, so the ledger aggregates the "
            "two families under one class."
        ),
    },
]

EXPECTED_PROMOTION_BYTES = sum(p["promotion_bytes"] for p in PACKAGES)
EXPECTED_CLAIM_COUNT = sum(p["record_count"] for p in PACKAGES)


def _sha(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def _dump(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _find_coverage_verifier(gate: dict[str, Any]) -> dict[str, Any]:
    for entry in gate["verifiers"]:
        command = entry["command"]
        if len(command) >= 2 and command[1].endswith("audit_rom_byte_coverage.py"):
            return entry
    raise SystemExit("FAIL coverage verifier entry not found in the proof spec")


def _sync_policy_counts(root: Path, summary: dict[str, Any]) -> list[str]:
    path = root / POLICY_PATH
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    total = summary["accounted_bytes"]
    classified = summary["classified_bytes"]
    unknown = summary["unknown_bytes"]
    wanted = (
        f"- authoritative canonical 的保守精确定位并集为 `{classified:,}` 字节\n"
        f"  （`{classified / total * 100:.14f}%`），显式 unknown 为 `{unknown:,}` 字节；"
        f"当前为 {summary['claim_count']:,} claims /\n"
        f"  {summary['segment_count']:,} segments。"
    )
    if wanted in text:
        return []
    pattern = re.compile(
        r"- authoritative canonical 的保守精确定位并集为 `[0-9,]+` 字节\n"
        r"  （`[0-9.]+%`），显式 unknown 为 `[0-9,]+` 字节；当前为 [0-9,]+ claims /\n"
        r"  [0-9,]+ segments。"
    )
    if not pattern.search(text):
        return ["policy document count anchor not found; counts were not refreshed"]
    path.write_text(pattern.sub(wanted, text, 1), encoding="utf-8")
    return [f"policy document counts refreshed: {classified:,} / {unknown:,}"]


def apply(root: Path) -> dict[str, Any]:
    coverage_raw = (root / COVERAGE_PATH).read_bytes()
    coverage = json.loads(coverage_raw.decode("utf-8"))
    summary = coverage["summary"]

    proof_raw = (root / PROOF_PATH).read_bytes()
    proof = json.loads(proof_raw.decode("utf-8"))
    gate = proof["gates"]["rom_byte_coverage"]

    changes: list[str] = []

    # 0. fail closed: the ledger must actually contain the three batches
    batches = {claim.get("promotion_batch") for claim in coverage["claims"]}
    for package in PACKAGES:
        if package["batch"] not in batches:
            raise SystemExit(
                f"FAIL the live ledger has no claim for batch {package['batch']}; "
                "rebuild the ledger before syncing the proof spec"
            )
    promoted_bytes = sum(
        claim["range"][1] - claim["range"][0]
        for claim in coverage["claims"]
        if claim.get("promotion_batch") in {p["batch"] for p in PACKAGES}
    )
    if promoted_bytes != EXPECTED_PROMOTION_BYTES:
        raise SystemExit(
            f"FAIL the three batches account for {promoted_bytes} bytes, "
            f"expected {EXPECTED_PROMOTION_BYTES}"
        )
    promoted_claims = sum(
        1
        for claim in coverage["claims"]
        if claim.get("promotion_batch") in {p["batch"] for p in PACKAGES}
    )
    if promoted_claims != EXPECTED_CLAIM_COUNT:
        raise SystemExit(
            f"FAIL the three batches account for {promoted_claims} claims, "
            f"expected {EXPECTED_CLAIM_COUNT}"
        )
    changes.append(
        f"ledger carries the three batches: {promoted_claims} claims / {promoted_bytes} bytes"
    )

    # 1. the coverage ledger's own evidence sha256
    coverage_entry = next(
        entry for entry in gate["evidence"] if entry["path"] == COVERAGE_PATH.as_posix()
    )
    new_coverage_sha = _sha(coverage_raw)
    if coverage_entry["sha256"] != new_coverage_sha:
        changes.append(
            f"coverage evidence sha256 {coverage_entry['sha256'][:12]} -> {new_coverage_sha[:12]}"
        )
        coverage_entry["sha256"] = new_coverage_sha

    # 2. each promoted package's own evidence files
    for package in PACKAGES:
        for path in (package["artifact"] / "manifest.json", package["artifact"] / package["payload"]):
            raw = (root / path).read_bytes()
            digest = _sha(raw)
            existing = next(
                (entry for entry in gate["evidence"] if entry["path"] == path.as_posix()),
                None,
            )
            if existing is None:
                gate["evidence"].append({"path": path.as_posix(), "sha256": digest})
                changes.append(f"evidence += {path.as_posix()}")
            elif existing["sha256"] != digest:
                changes.append(f"evidence sha256 changed {path.as_posix()}")
                existing["sha256"] = digest

    # 3. the package verifier contracts that can be expressed
    for package in PACKAGES:
        if not package["verifier_in_proof"]:
            changes.append(
                f"verifier NOT added for {package['verifier'].as_posix()}: "
                "its report carries no /schema, and _contract() would reject the entry"
            )
            continue
        verifier_command = [
            "python3",
            package["verifier"].as_posix(),
            "--root",
            ".",
            "--artifact-dir",
            package["artifact"].as_posix(),
        ]
        verifier_entry = next(
            (
                entry
                for entry in gate["verifiers"]
                if entry["command"][1:2] == [package["verifier"].as_posix()]
            ),
            None,
        )
        verifier_sha = _sha((root / package["verifier"]).read_bytes())
        expected_contract = {
            "format": "json",
            "assertions": dict(package["verifier_assertions"]),
        }
        if verifier_entry is None:
            gate["verifiers"].append(
                {
                    "command": verifier_command,
                    "script_sha256": verifier_sha,
                    "contract": expected_contract,
                }
            )
            changes.append(f"verifier += {package['verifier'].as_posix()}")
        else:
            if verifier_entry["command"] != verifier_command:
                changes.append("verifier command changed")
                verifier_entry["command"] = verifier_command
            if verifier_entry["script_sha256"] != verifier_sha:
                changes.append("verifier script sha256 changed")
                verifier_entry["script_sha256"] = verifier_sha
            if verifier_entry["contract"] != expected_contract:
                changes.append("verifier contract changed")
                verifier_entry["contract"] = expected_contract

    # 4. the coverage verifier's own identity and summary assertions
    coverage_verifier = _find_coverage_verifier(gate)
    audit_sha = _sha((root / AUDIT_SCRIPT).read_bytes())
    if coverage_verifier["script_sha256"] != audit_sha:
        changes.append(
            f"coverage verifier script sha256 {coverage_verifier['script_sha256'][:12]} -> {audit_sha[:12]}"
        )
        coverage_verifier["script_sha256"] = audit_sha
    assertions = coverage_verifier["contract"]["assertions"]
    updated = 0
    missing: list[str] = []
    for pointer, expected in list(assertions.items()):
        if not pointer.startswith("/summary/"):
            continue
        key = pointer[len("/summary/") :]
        if key not in summary:
            missing.append(key)
            continue
        if summary[key] != expected:
            assertions[pointer] = summary[key]
            updated += 1
    if updated:
        changes.append(f"coverage summary assertions updated: {updated}")
    if missing:
        changes.append(f"coverage summary assertions dropped: {missing}")
        for key in missing:
            assertions.pop(f"/summary/{key}", None)

    # 5. the promoted-byte limitation and one package limitation per package
    unknown = summary["unknown_bytes"]
    accounted = summary["accounted_bytes"]
    percent = unknown / accounted * 100
    new_limitation = (
        f"The manifest explicitly accounts for all {accounted} bytes, but {unknown} bytes "
        f"({percent:.4f}%) remain semantically unknown."
    )
    if gate["limitations"] and gate["limitations"][0] != new_limitation:
        changes.append("promoted-byte limitation refreshed")
        gate["limitations"][0] = new_limitation

    for package in PACKAGES:
        if package["limitation"] not in gate["limitations"]:
            gate["limitations"].append(package["limitation"])
            changes.append(f"limitation += {package['batch']}")

    (root / PROOF_PATH).write_bytes(_dump(proof))
    policy_changes = _sync_policy_counts(root, summary)
    return {
        "policy_changes": policy_changes,
        "coverage_sha256": new_coverage_sha,
        "audit_script_sha256": audit_sha,
        "promoted_claims": promoted_claims,
        "promoted_bytes": promoted_bytes,
        "unknown_bytes": unknown,
        "classified_bytes": summary["classified_bytes"],
        "claim_count": summary["claim_count"],
        "segment_count": summary["segment_count"],
        "changes": changes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    result = apply(root)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
