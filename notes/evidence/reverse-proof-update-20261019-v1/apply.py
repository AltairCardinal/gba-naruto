#!/usr/bin/env python3
"""Apply the renderer-script pointer-pool promotion to the proof ledger.

The proof ledger is a hand-maintained specification that the read-only
auditor ``tools/audit_reverse_engineering_proof.py`` validates.  This script
applies exactly one promotion (the 1,542 byte renderer script pointer-pool
records) to that specification and is idempotent: running it twice produces
the same file.

It reads the freshly rebuilt coverage ledger, so the coverage digest, the
coverage summary assertions and the promoted-byte limitation always describe
the same build.

    python3 notes/evidence/reverse-proof-update-20261019-v1/apply.py --root .
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
PROOF_PATH = Path("sequel/reverse-engineering-proof.json")
AUDIT_SCRIPT = Path("tools/audit_rom_byte_coverage.py")
PACKAGE_ARTIFACT = Path("artifacts/rom-renderer-script-pointer-pool-records-v1")
PACKAGE_MANIFEST = PACKAGE_ARTIFACT / "manifest.json"
PACKAGE_PAYLOAD = PACKAGE_ARTIFACT / "rom-renderer-script-pointer-pool-records.json"
PACKAGE_VERIFIER = Path("tools/verify_rom_renderer_script_pointer_pool_records.py")
PACKAGE_BATCH = "rom-renderer-script-pointer-pool-records-v1"
PACKAGE_PROMOTION_BYTES = 1_542
PACKAGE_RECORD_COUNT = 27


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _dump(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def _find_coverage_verifier(gate: dict[str, Any]) -> dict[str, Any]:
    for entry in gate["verifiers"]:
        if entry["command"][1:2] == ["tools/audit_rom_byte_coverage.py"]:
            return entry
    raise SystemExit("the coverage verifier entry is missing from the proof ledger")


POLICY_PATH = Path("docs/reverse-engineering-proof-policy.md")
POLICY_ANCHOR = """- authoritative canonical 的保守精确定位并集为 `6,203,707` 字节
  （`98.60526720682780%`），显式 unknown 为 `87,749` 字节；当前为 16,891 claims /
  18,664 segments。"""


def _sync_policy_counts(root: Path, summary: dict[str, Any]) -> list[str]:
    """Publish the new canonical counts in the proof policy document.

    The policy document states the authoritative byte totals, and the proof
    audit suite asserts that the document agrees with the live ledger.  A
    promotion that updates the two JSON ledgers but not this document leaves
    the suite red, so the step belongs to the promotion, not to a follow-up.
    """

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
    import re

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

    # 1. the coverage ledger itself
    coverage_entry = next(
        entry for entry in gate["evidence"] if entry["path"] == COVERAGE_PATH.as_posix()
    )
    new_coverage_sha = _sha(coverage_raw)
    if coverage_entry["sha256"] != new_coverage_sha:
        changes.append(
            f"coverage evidence sha256 {coverage_entry['sha256'][:12]} -> {new_coverage_sha[:12]}"
        )
        coverage_entry["sha256"] = new_coverage_sha

    # 2. the promoted package's own evidence files
    for path in (PACKAGE_MANIFEST, PACKAGE_PAYLOAD):
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

    # 3. the promoted package's own verifier contract
    verifier_command = [
        "python3",
        PACKAGE_VERIFIER.as_posix(),
        "--root",
        ".",
        "--artifact-dir",
        PACKAGE_ARTIFACT.as_posix(),
    ]
    verifier_entry = next(
        (
            entry
            for entry in gate["verifiers"]
            if entry["command"][1:2] == [PACKAGE_VERIFIER.as_posix()]
        ),
        None,
    )
    verifier_sha = _sha((root / PACKAGE_VERIFIER).read_bytes())
    expected_contract = {
        "format": "json",
        "assertions": {
            "/schema": f"{PACKAGE_BATCH}-verification-v1",
            "/verified": True,
            "/errors": [],
            "/record_count": PACKAGE_RECORD_COUNT,
            "/promotion_bytes": PACKAGE_PROMOTION_BYTES,
        },
    }
    if verifier_entry is None:
        gate["verifiers"].append(
            {
                "command": verifier_command,
                "script_sha256": verifier_sha,
                "contract": expected_contract,
            }
        )
        changes.append(f"verifier += {PACKAGE_VERIFIER.as_posix()}")
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
        key = pointer[len("/summary/"):]
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

    # 5. the promoted-byte limitation
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

    pool_limitation = (
        f"The renderer script pointer-pool artifact classifies exactly {PACKAGE_PROMOTION_BYTES} "
        f"previously unknown bytes as {PACKAGE_RECORD_COUNT} gapless renderer command records at "
        f"[0x000CEA,0x0012F0), bound to the 28-slot pointer table at [0x0053DF00,0x0053DF70) whose "
        f"slot 0 is null and whose slots 1..27 point at the record roots in order, and to the single "
        f"consumer read at [0x000712D0,0x00071350) whose BL at 0x071340 enters the interpreter at "
        f"0x067158. The record grammar is the already accepted opcode set; natural runtime "
        f"reachability, the RAM row index domain (no <=27 guard exists), the row writer lifecycle, "
        f"the null-slot semantics and consumer completeness remain unclaimed."
    )
    if pool_limitation not in gate["limitations"]:
        gate["limitations"].append(pool_limitation)
        changes.append("limitation += renderer script pointer-pool records")

    (root / PROOF_PATH).write_bytes(_dump(proof))
    policy_changes = _sync_policy_counts(root, summary)
    return {
        "policy_changes": policy_changes,
        "coverage_sha256": new_coverage_sha,
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
    raise SystemExit(main())
