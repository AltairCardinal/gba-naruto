#!/usr/bin/env python3
"""Audit how much of the reverse engineering corpus the Butano remake actually uses.

The Butano remake line (``codex/butano-foundation-research``) and the reverse
engineering line (``codex/reverse-engineering``) are deliberately kept apart.
That separation makes one question impossible to answer from either tree alone:

    of the reverse results that are already finished, how many should the
    Butano remake be using, and how many is it not using?

Three machine receipts on the Butano side already measure parts of this:

* ``artifacts/butano-reverse-gap-v1/gap.json``
  -- "is the family named by the remake's build chain?" (264 artifact families)
* ``artifacts/butano-usable-backlog-v1/backlog.json``
  -- "is the family closed (accepted), does it carry payload, is it consumed?"
* ``artifacts/butano-wiring-coverage-v1/wiring.json``
  -- "how is the family actually wired?" (nine mutually exclusive states)

This tool does not measure anything new.  It joins those three receipts on the
family id and answers the question above under explicitly named denominators,
because the honest answer differs by unit:

* ``artifact family`` -- 264 units.  A family is the reverse tree's unit of
  promotion: one directory under ``artifacts/`` with a manifest.
* ``note`` -- 436 units.  A note is one conclusion document.  A note that is
  classified ``needs_guard`` carries a conclusion about the original game that
  the remake has *not* turned into a gate yet.

The three receipts are read as-is; this tool re-derives nothing from the
reverse tree, so it cannot drift from the numbers the Butano line publishes.
It fails closed: a missing receipt, a family count that does not agree across
receipts, or a bucket that does not add up is a non-zero exit with a named
reason -- never a quietly shorter report.

Usage::

    python3 tools/butano_reverse_utilization_audit.py
    python3 tools/butano_reverse_utilization_audit.py \\
        --butano-root D:/Shell/Github/gba-naruto-butano \\
        --out-dir artifacts/butano-utilization-audit-v1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_BUTANO_ROOT = Path("D:/Shell/Github/gba-naruto-butano")

GAP_RECEIPT = Path("artifacts/butano-reverse-gap-v1/gap.json")
BACKLOG_RECEIPT = Path("artifacts/butano-usable-backlog-v1/backlog.json")
WIRING_RECEIPT = Path("artifacts/butano-wiring-coverage-v1/wiring.json")
NOTES_INDEX = Path("artifacts/reverse-notes-index-v1/notes-index.json")

# Notes buckets whose disposition is decided.  ``needs_guard`` is the one that
# answers "a finished conclusion the remake is not using yet"; the others are
# either out of scope, unfinished, or undecided.
NOTES_DECIDED_BUCKETS = ("implemented_in_code", "needs_guard")
NOTES_UNFINISHED_BUCKETS = ("missing_evidence", "needs_human_review")


class AuditError(RuntimeError):
    """A named, fail-closed reason."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AuditError(f"receipt not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditError(f"receipt is not valid JSON: {path}: {exc}") from exc


def _families(gap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [
        r
        for r in gap.get("rows") or []
        if r.get("kind") == "artifact" and isinstance(r.get("id"), str)
    ]
    if not rows:
        raise AuditError("gap receipt carries no artifact family rows")
    return {r["id"]: r for r in rows}


def _by_id(rows: Any, what: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise AuditError(f"{what} receipt carries no rows")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("id"), str):
            out[r["id"]] = r
    if not out:
        raise AuditError(f"{what} receipt carries no rows keyed by id")
    return out


def audit(butano_root: Path) -> dict[str, Any]:
    gap = _load_json(butano_root / GAP_RECEIPT)
    backlog = _load_json(butano_root / BACKLOG_RECEIPT)
    wiring = _load_json(butano_root / WIRING_RECEIPT)
    notes_index = _load_json(butano_root / NOTES_INDEX)

    fam = _families(gap)
    bl = _by_id(backlog.get("rows"), "backlog")
    wi = _by_id(wiring.get("source_rows"), "wiring")

    missing = sorted(set(fam) - set(bl)) + sorted(set(fam) - set(wi))
    if missing:
        raise AuditError(
            f"family ids present in gap but missing from a sibling receipt: "
            f"{missing[:5]} (total {len(missing)})"
        )
    for name, other in (("backlog", bl), ("wiring", wi)):
        extra = sorted(set(other) - set(fam))
        if extra:
            raise AuditError(
                f"{name} receipt has families the gap receipt does not: "
                f"{extra[:5]} (total {len(extra)})"
            )

    total = len(fam)

    # ---- layer A: artifact families -------------------------------------
    wired = {f: r for f, r in fam.items() if r.get("status") == "build"}
    unwired = {f: r for f, r in fam.items() if r.get("status") != "build"}

    unwired_by_state = Counter(wi[f]["state"] for f in unwired)
    wired_by_state = Counter(wi[f]["state"] for f in wired)

    # Strong lineage: a product or an importer declares the family and a test
    # gates it.  local-rederived-identical is weaker -- the remake re-exported
    # the bytes itself instead of importing the reverse result.
    declared_strong = {
        f
        for f in wired
        if wi[f]["state"] in ("imported-and-gated", "wired-and-gated")
    }
    local_rederived = {
        f for f in wired if wi[f]["state"] == "local-rederived-identical"
    }
    verified_only = {f for f in wired if wi[f]["state"] == "verified-against"}

    # The shelf: closed (accepted), carries payload, nobody wired it.
    shelf = [
        f
        for f in fam
        if bl[f].get("accepted")
        and bl[f].get("has_payload")
        and not bl[f].get("consumed")
    ]
    shelf_by_tier = Counter(bl[f].get("tier") for f in shelf)
    # Directly importable and closed but unwired.  The only two are read as
    # evidence by a verifier, which is a consumption, not an import.
    shelf_importable = [
        f for f in shelf if bl[f].get("tier") in ("asset-direct", "table-direct")
    ]
    # ``verified-against`` means the remake reads the family as evidence in a
    # verifier but does not consume its payload.  That is a weaker form of use,
    # so it is separated from "nobody ever touched it".
    shelf_importable_unwired = [
        f
        for f in shelf_importable
        if wi[f]["state"] not in ("imported-and-gated", "wired-and-gated")
    ]
    shelf_importable_touched = [
        f for f in shelf_importable_unwired if wi[f]["state"] == "verified-against"
    ]
    shelf_importable_untouched = [
        f for f in shelf_importable_unwired if wi[f]["state"] != "verified-against"
    ]

    accepted = [f for f in fam if bl[f].get("accepted")]
    consumed_accepted = [f for f in accepted if bl[f].get("consumed")]

    by_category: dict[str, Counter] = defaultdict(Counter)
    for f, r in fam.items():
        by_category[r.get("category", "unknown")][r.get("status", "unknown")] += 1

    # ---- layer B: notes (conclusions) -----------------------------------
    notes_summary = notes_index.get("summary") or {}
    buckets = dict(notes_summary.get("by_bucket") or {})
    notes_total = int(notes_summary.get("total") or 0)
    if not buckets or not notes_total:
        raise AuditError("notes index carries no bucket summary")
    if sum(buckets.values()) != notes_total:
        raise AuditError(
            f"notes buckets do not add up: {sum(buckets.values())} != {notes_total}"
        )

    needs_guard = int(buckets.get("needs_guard", 0))
    implemented = int(buckets.get("implemented_in_code", 0))
    decided = sum(int(buckets.get(b, 0)) for b in NOTES_DECIDED_BUCKETS)
    finished = decided + sum(int(buckets.get(b, 0)) for b in NOTES_UNFINISHED_BUCKETS)
    out_of_scope = int(buckets.get("not_applicable", 0))

    def pct(num: int, den: int) -> float:
        return round(100.0 * num / den, 1) if den else 0.0

    ratios = {
        # R1 -- material: closed + importable, but not wired into the remake.
        "R1_importable_closed_unwired": {
            "numerator": len(shelf_importable_unwired),
            "denominator": len(accepted),
            "denominator_label": "accepted (closed) artifact families",
            "percent": pct(len(shelf_importable_unwired), len(accepted)),
            "family_ids": sorted(shelf_importable_unwired),
            "of_which_read_as_evidence_only": sorted(shelf_importable_touched),
            "of_which_never_touched": sorted(shelf_importable_untouched),
        },
        # R1b -- the strict form: closed, importable, and nobody even reads it.
        "R1b_importable_closed_never_touched": {
            "numerator": len(shelf_importable_untouched),
            "denominator": len(accepted),
            "denominator_label": "accepted (closed) artifact families",
            "percent": pct(len(shelf_importable_untouched), len(accepted)),
            "family_ids": sorted(shelf_importable_untouched),
        },
        # R2 -- specification: finished conclusions not turned into gates.
        "R2_finished_conclusions_not_gated": {
            "numerator": needs_guard,
            "denominator": notes_total,
            "denominator_label": "all reverse notes",
            "percent": pct(needs_guard, notes_total),
        },
        "R2b_finished_conclusions_not_gated_of_decided": {
            "numerator": needs_guard,
            "denominator": decided,
            "denominator_label": "notes that are decided (implemented or needs_guard)",
            "percent": pct(needs_guard, decided),
        },
        # R3 -- every family that carries payload but is not in the build chain.
        "R3_payload_families_not_in_build_chain": {
            "numerator": len(shelf),
            "denominator": total,
            "denominator_label": "all artifact families",
            "percent": pct(len(shelf), total),
        },
        # R4 -- every family outside the build chain, for any reason.
        "R4_all_families_not_in_build_chain": {
            "numerator": len(unwired),
            "denominator": total,
            "denominator_label": "all artifact families",
            "percent": pct(len(unwired), total),
        },
    }

    return {
        "schema": "konoha.butano-reverse-utilization-audit.v1",
        "inputs": {
            "butano_root": str(butano_root),
            "gap_receipt": str(GAP_RECEIPT),
            "backlog_receipt": str(BACKLOG_RECEIPT),
            "wiring_receipt": str(WIRING_RECEIPT),
            "notes_index": str(NOTES_INDEX),
            "reverse_commit": (gap.get("index") or {}).get("reverse_commit"),
            "reverse_dirty": (gap.get("index") or {}).get("reverse_dirty"),
            "rom_sha256": (gap.get("index") or {}).get("rom_sha256"),
            "gap_generated_at": gap.get("generated_at"),
            "backlog_generated_at": backlog.get("generated_at"),
            "wiring_generated_at": wiring.get("generated_at"),
            "notes_generated_at": notes_index.get("generated_at"),
        },
        "artifact_families": {
            "total": total,
            "in_build_chain": len(wired),
            "not_in_build_chain": len(unwired),
            "in_build_chain_by_state": dict(sorted(wired_by_state.items())),
            "not_in_build_chain_by_state": dict(sorted(unwired_by_state.items())),
            "lineage_of_wired": {
                "declared_and_gated": len(declared_strong),
                "local_rederived_identical": len(local_rederived),
                "verified_against_only": len(verified_only),
            },
            "accepted_closed": len(accepted),
            "accepted_and_consumed": len(consumed_accepted),
            "shelf_closed_with_payload_unwired": len(shelf),
            "shelf_by_tier": dict(sorted(shelf_by_tier.items())),
            "shelf_importable_unwired": sorted(shelf_importable_unwired),
            "shelf_importable_untouched": sorted(shelf_importable_untouched),
            "by_category": {
                c: dict(sorted(s.items())) for c, s in sorted(by_category.items())
            },
        },
        "notes": {
            "total": notes_total,
            "by_bucket": dict(sorted(buckets.items())),
            "implemented_in_code": implemented,
            "needs_guard": needs_guard,
            "decided_total": decided,
            "finished_total": finished,
            "out_of_scope": out_of_scope,
            "needs_guard_without_any_test_reference": notes_summary.get(
                "needs_guard_without_any_test_reference"
            ),
        },
        "ratios": ratios,
    }


def render_markdown(report: dict[str, Any]) -> str:
    af = report["artifact_families"]
    nt = report["notes"]
    r = report["ratios"]
    lines: list[str] = []
    a = lines.append
    a("# Butano 重制版对逆向成果的利用审计")
    a("")
    a("（由 `tools/butano_reverse_utilization_audit.py` 从三份机读收据 join 生成）")
    a("")
    a(f"- 逆向提交：`{report['inputs']['reverse_commit']}`（dirty="
      f"{report['inputs']['reverse_dirty']}）")
    a(f"- ROM SHA-256：`{report['inputs']['rom_sha256']}`")
    a("")

    a("## 1. 成果族层（264 个逆向成果族）")
    a("")
    a("| 判定 | 族数 | 占比 |")
    a("| --- | ---: | ---: |")
    a(f"| 进 Butano 构建链 | {af['in_build_chain']} | "
      f"{100*af['in_build_chain']/af['total']:.1f}% |")
    a(f"| 未进构建链 | {af['not_in_build_chain']} | "
      f"{100*af['not_in_build_chain']/af['total']:.1f}% |")
    a("")
    a("已接线族按血缘强度：")
    a("")
    a("| 血缘 | 族数 | 含义 |")
    a("| --- | ---: | --- |")
    lin = af["lineage_of_wired"]
    a(f"| 声明式接线且有门禁 | {lin['declared_and_gated']} | 导入器/provenance 载体钉住族 |")
    a(f"| 复刻侧重导出且逐字节相同 | {lin['local_rederived_identical']} | "
      "字节对，但血缘是本地重导出，不是导入 |")
    a(f"| 只作 verifier 证据 | {lin['verified_against_only']} | 不消费 payload |")
    a("")
    a("未进构建链的族按状态：")
    a("")
    a("| 状态 | 族数 |")
    a("| --- | ---: |")
    for k, v in af["not_in_build_chain_by_state"].items():
        a(f"| `{k}` | {v} |")
    a("")

    a("## 2. 结论层（436 篇逆向笔记）")
    a("")
    a("| 桶 | 条数 | 占比 |")
    a("| --- | ---: | ---: |")
    for k, v in nt["by_bucket"].items():
        a(f"| `{k}` | {v} | {100*v/nt['total']:.1f}% |")
    a("")

    a("## 3. 「应当被使用但未使用」的比例")
    a("")
    a("| 口径 | 分子 | 分母 | 比例 |")
    a("| --- | ---: | ---: | ---: |")
    for key, label in (
        ("R1_importable_closed_unwired", "R1 可导入且已闭合、却没接进构建链"),
        ("R1b_importable_closed_never_touched",
         "R1b 同上，但连 verifier 都没读过（严格口径）"),
        ("R2_finished_conclusions_not_gated", "R2 已闭合结论、却没转成门禁（对全部笔记）"),
        ("R2b_finished_conclusions_not_gated_of_decided",
         "R2b 同上，对「已判定」的笔记"),
        ("R3_payload_families_not_in_build_chain", "R3 带 payload 却不在构建链的成果族"),
        ("R4_all_families_not_in_build_chain", "R4 全部不在构建链的成果族"),
    ):
        v = r[key]
        a(f"| {label} | {v['numerator']} | {v['denominator']} | {v['percent']}% |")
    a("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--butano-root", type=Path, default=DEFAULT_BUTANO_ROOT)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        report = audit(args.butano_root)
    except AuditError as exc:
        print(f"AUDIT FAILED: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "utilization.json").write_text(
            text + "\n", encoding="utf-8", newline="\n"
        )
        (args.out_dir / "utilization.md").write_text(
            render_markdown(report), encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.out_dir / 'utilization.json'}")
        print(f"wrote {args.out_dir / 'utilization.md'}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
