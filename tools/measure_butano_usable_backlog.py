#!/usr/bin/env python3
"""Measure the reverse results the remake could use but does not use yet.

``tools/measure_butano_reverse_gap.py`` answers "is this result referenced?".
That is a *reachability* question, and reachability is not usability: a family
can be perfectly importable and still sit at ``doc`` status because nobody
wired it up, and a family can be mentioned in every note in the tree and still
be nothing but a code-flow analysis that the remake cannot eat.

This tool asks the second question, with the same rule as the first one: the
answer must be produced by a script over the whole population, never by a
hand-kept list of family names.  A hand-kept list would rot the moment the
reverse work tree promotes a new family, and it would smuggle the author's
own opinion into a number that is supposed to be measured.

The measurement chains four filters, each of them objective and each of them
recorded per family in the receipt:

1.  **Population -- artifact families only.**  A family is a signed result: it
    has a manifest that pins the SHA-256 of its own files.  Notes and
    documents are prose; they are measured separately, by the notes index,
    which already buckets them by what the remake would have to do with them.
2.  **Accepted.**  The family's manifest must carry ``artifact_status:
    "accepted"``.  That is the same flag the importers enforce
    (``tools/butano/import_rom_reverse_families.py``: ``ACCEPTED_STATUS``), so
    a family that is not ``accepted`` is not a result the remake may use --
    ``candidate``, ``disproved`` and ``superseded`` are not results.
3.  **Carries a payload.**  A family with no files has nothing to import.
4.  **Not consumed.**  The gap receipt's status must not be ``build``.

What survives is the *unused shelf*.  Each family on it is then classified by
how directly it can be used, which is the part the user actually needs:

``asset-direct``
    The payload holds bytes the remake's asset pipeline can already read:
    PNG pixels (a pixel baseline or a reference frame), ``.4bpp``/``.8bpp``
    tile data, ``.bgr555`` palettes, ``.lz77`` ROM blobs, ``.s3m``/``.wav``
    audio.  Importing one is a generator call, not an interpretation.
``table-direct``
    The payload is a structured table about content (bindings, ownership,
    provenance, composites, catalogs).  Importing one needs a single small
    generator that maps the table into ``sequel/content/<name>/bank.json``.
``analysis-only``
    The payload describes control flow, coverage denominators or audit
    evidence.  It is the reverse project's own bookkeeping; it constrains how
    the remake may behave but it is not something the remake can import.
``unclassified``
    The payload matched neither vocabulary.  It is reported as its own
    bucket instead of being forced into one, because a forced classification
    is exactly the kind of guess this tool exists to avoid.

The table/analysis split is a *vocabulary probe* over the top-level keys of
the family's JSON payloads, minus a boilerplate set of keys that every
result carries.  Both vocabularies are published in this file, and the
receipt records, per family, which key triggered the verdict, so any row can
be audited against the payload it claims to describe.

Usage::

    python3 tools/measure_butano_usable_backlog.py \\
        --root . \\
        --index artifacts/reverse-results-index-v1/index.json \\
        --gap artifacts/butano-reverse-gap-v1/gap.json \\
        --out-dir artifacts/butano-usable-backlog-v1
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

BACKLOG_SCHEMA = "konoha.butano-usable-backlog.v1"

#: Suffixes the remake's asset pipeline can read as-is.  A payload file with
#: one of these suffixes is directly importable.
ASSET_SUFFIXES = frozenset(
    {".png", ".4bpp", ".8bpp", ".bgr555", ".lz77", ".s3m", ".wav"}
)

#: A payload file whose name marks it as one half of an A/B pair.  These are
#: acceptance baselines: the pixel the original ROM drew.  The remake consumes
#: them exactly like the imported pixel-A/B families -- as a 1:1 target.
BASELINE_STEMS = ("baseline", "candidate")

#: Files that are part of the result's own bookkeeping rather than its
#: payload.  A family is measured by what it *delivers*, not by what it
#: wrote down about itself.
BOOKKEEPING_NAMES = frozenset({"manifest.json", "inputs.json"})

#: Suffixes that hold a *receipt*, not a payload.  The reverse work tree
#: stores its byte-coverage projections as gzipped JSON (``rom-byte-coverage
#: .json.gz``): that is the reverse project's own bookkeeping about which ROM
#: bytes are still unknown, and the remake cannot import it.  Counting it as
#: payload would put eleven coverage receipts on the shelf and make the
#: backlog look like it holds renderable content.
RECEIPT_SUFFIXES = frozenset({".gz"})

#: Keys every result carries.  They say how the result was produced, not what
#: it contains, so they carry no signal in the vocabulary probe.
BOILERPLATE_KEYS = frozenset(
    {
        "artifact_id",
        "artifact_status",
        "boundary",
        "files",
        "implementation",
        "limitations",
        "promotion",
        "public_contract_sha256",
        "rom",
        "schema",
        "scope",
        "source",
        "source_artifact",
        "source_artifacts",
        "sources",
        "summary",
        "upstream",
        "upstream_evidence",
        "upstream_receipts",
    }
)

#: Top-level keys that mark a payload as a table the remake can map into its
#: content spine.
TABLE_MARKERS = frozenset(
    {
        "a_consumer",
        "affine_runtime_goldens",
        "background_scroll_tracks",
        "b_consumers",
        "binding_contract",
        "bindings",
        "catalog",
        "checkpoints",
        "classification_contract",
        "constant_rom_gpu_transfers",
        "consumer",
        "consumer_contract",
        "consumer_evidence",
        "consumers",
        "controller_model",
        "copy_operation_union",
        "copy_operations",
        "entries",
        "initializer_binding",
        "layers",
        "local_dma_consumer",
        "logical_outputs",
        "ownership_record",
        "ownership_records",
        "physical_palettes",
        "pointer_tables",
        "queue",
        "queue_contract",
        "records",
        "resource_provenance",
        "resources",
        "selection_rule",
        "slots",
        "source_catalog",
        "source_inventory",
        "source_registry",
        "states",
        "supplemental_states",
        "table",
        "table_consumers",
        "tables",
        "targets",
        "tilemap_sources",
        "tilemaps",
        "writeback",
    }
)

#: Keys that describe *control flow*.  A payload built around them describes
#: how the original ROM's code runs; the remake cannot import that.  These
#: keys veto a table verdict: a payload that carries both a content table and
#: a control-flow description has to be read before it can be mapped.
STRUCTURAL_MARKERS = frozenset(
    {
        "accepted_producers",
        "blocks",
        "bundles",
        "candidate_windows",
        "cfg",
                "code_ranges",
        "edges",
                "external_edges",
        "frontiers",
        "instructions",
        "literal_binding_vector",
        "literal_binding_vector_sha256",
                "literal_ranges",
        "packed_binary",
        "packed_bytes",
        "packed_bytes_sha256",
        "packed_layout",
        "raw_indirect_pc_sites",
        "rejected_producers",
        "rejected_targets",
        "root",
        "roots",
        "source_membership",
        "source_to_target",
        "target_closure",
        "target_local_denominator",
        "target_words",
        "unclassified_unknown_ranges",
        "v3_packet_target_overlap_word_count",
    }
)

#: Keys that describe the reverse project's own *coverage bookkeeping*.  They
#: are ubiquitous -- nearly every ROM-side result carries them -- so they must
#: not veto a table verdict.  A content table that also states which bytes are
#: still unknown is still a content table; the bookkeeping around it is not
#: the payload.
COVERAGE_MARKERS = frozenset(
    {
        "coverage",
        "coverage_baseline",
        "coverage_baseline_source",
        "coverage_claims",
        "coverage_projection",
        "classified_ranges",
        "literal_bindings",
        "excluded_ranges",
        "literal_denominator",
        "non_claims",
        "precoverage",
        "producer_denominator",
        "promotion_ranges",
        "public_contract_sha256",
        "range_denominator_sha256",
        "source_denominator",
    }
)


#: The four verdicts a family with a payload can get.
TIER_ASSET = "asset-direct"
TIER_TABLE = "table-direct"
TIER_ANALYSIS = "analysis-only"
TIER_UNCLASSIFIED = "unclassified"
TIER_NO_PAYLOAD = "no-payload"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_files(reverse_root: Path, family_path: str) -> list[dict[str, Any]]:
    """Every payload file of a family, with its size.

    The manifest and the inputs file are the result's own bookkeeping and are
    not payload.  A compressed coverage projection is a receipt, not payload
    either (see ``RECEIPT_SUFFIXES``).  A file of zero bytes carries nothing.
    """
    base = reverse_root / family_path
    if not base.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.name in BOOKKEEPING_NAMES:
            continue
        if path.suffix.lower() in RECEIPT_SUFFIXES:
            continue
        try:
            size = path.stat().st_size
        except OSError:  # pragma: no cover - defensive
            continue
        if size == 0:
            continue
        found.append(
            {
                "name": str(path.relative_to(base)),
                "suffix": path.suffix.lower(),
                "bytes": size,
            }
        )
    return found


def _json_top_level_keys(reverse_root: Path, family_path: str) -> tuple[set[str], list[str]]:
    """The top-level keys of every JSON payload, and the files they came from.

    A JSON payload that is a list has no top-level keys of its own, so the
    keys of its first object element are used instead -- otherwise a list of
    records would be read as "no structure" and the family would be lost.
    """
    base = reverse_root / family_path
    keys: set[str] = set()
    sources: list[str] = []
    if not base.is_dir():
        return keys, sources
    for path in sorted(base.rglob("*.json")):
        if path.name in BOOKKEEPING_NAMES:
            continue
        try:
            data = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            keys |= {str(key) for key in data}
        elif isinstance(data, list):
            keys.add("__list__")
            for item in data:
                if isinstance(item, dict):
                    keys |= {str(key) for key in item}
                    break
        else:
            continue
        sources.append(str(path.relative_to(base)))
    return keys, sources


def _classify(
    payload: list[dict[str, Any]],
    json_keys: set[str],
) -> tuple[str, dict[str, Any]]:
    """Decide how directly a family can be used, and record the evidence."""
    asset_files = [item for item in payload if item["suffix"] in ASSET_SUFFIXES]
    if asset_files:
        kinds = sorted({item["suffix"] for item in asset_files})
        baselines = sorted(
            item["name"]
            for item in asset_files
            if Path(item["name"]).stem.lower().startswith(BASELINE_STEMS)
        )
        return TIER_ASSET, {
            "asset_files": [item["name"] for item in asset_files][:12],
            "asset_suffixes": kinds,
            "baseline_files": baselines,
        }

    probe = {key for key in json_keys if key not in BOILERPLATE_KEYS}
    table_hits = sorted(probe & TABLE_MARKERS)
    structural_hits = sorted(probe & STRUCTURAL_MARKERS)
    coverage_hits = sorted(probe & COVERAGE_MARKERS)
    evidence = {
        "table_markers": table_hits,
        "structural_markers": structural_hits,
        "coverage_markers": coverage_hits,
    }
    if table_hits and not structural_hits:
        # A content table.  The coverage keys around it are the reverse
        # project's bookkeeping and do not change what the payload is.
        return TIER_TABLE, evidence
    if not table_hits and (structural_hits or coverage_hits):
        return TIER_ANALYSIS, evidence
    if table_hits and structural_hits:
        # Both a content table and a control-flow description: the payload has
        # to be read before it can be mapped, so it is not a verdict.
        return TIER_UNCLASSIFIED, evidence
    return TIER_UNCLASSIFIED, {
        **evidence,
        "unclassified_keys": sorted(probe)[:12],
    }


def measure(
    root: Path,
    index_path: Path,
    gap_path: Path,
    notes_index_path: Path | None,
) -> dict[str, Any]:
    for path in (index_path, gap_path):
        if not path.is_file():
            raise FileNotFoundError(f"input not found: {path}")

    index = _read_json(index_path)
    gap = _read_json(gap_path)
    source = index.get("source") or {}
    reverse_root = Path(str(source.get("reverse_root") or ""))
    if not reverse_root.is_dir():
        raise FileNotFoundError(f"reverse work tree not found: {reverse_root}")

    gap_status = {
        str(row.get("id")): str(row.get("status"))
        for row in (gap.get("rows") or [])
        if row.get("id")
    }

    rows: list[dict[str, Any]] = []
    for entry in index.get("entries") or []:
        if entry.get("kind") != "artifact":
            continue
        family_id = str(entry.get("id") or "")
        if not family_id:
            continue
        family_path = str(entry.get("path") or "")
        manifest_rel = str(entry.get("manifest") or "")
        manifest_path = reverse_root / manifest_rel if manifest_rel else None

        artifact_status: str | None = None
        manifest_error: str | None = None
        scope_closed: bool | None = None
        scope_open_claims: list[str] = []
        if manifest_path is not None and manifest_path.is_file():
            try:
                manifest = _read_json(manifest_path)
            except (OSError, json.JSONDecodeError) as exc:
                manifest_error = f"unreadable manifest: {exc}"
            else:
                if isinstance(manifest, dict):
                    value = manifest.get("artifact_status")
                    artifact_status = str(value) if value is not None else None
                    # The manifest's ``scope`` block states what the result
                    # does *not* claim.  A family whose payload is perfectly
                    # importable can still say "natural runtime reachability:
                    # false", and that difference decides whether the remake
                    # may rely on it.
                    scope = manifest.get("scope")
                    if isinstance(scope, dict) and scope:
                        scope_open_claims = sorted(
                            str(key) for key, flag in scope.items() if flag is False
                        )
                        scope_closed = not scope_open_claims
                else:
                    manifest_error = "manifest is not an object"
        elif manifest_path is not None:
            manifest_error = "manifest missing from the reverse work tree"

        payload = _payload_files(reverse_root, family_path)
        json_keys, json_sources = _json_top_level_keys(reverse_root, family_path)
        status = gap_status.get(family_id, "none")
        accepted = artifact_status == "accepted"
        consumed = status == "build"

        if not payload:
            tier, evidence = TIER_NO_PAYLOAD, {}
        else:
            tier, evidence = _classify(payload, json_keys)

        rows.append(
            {
                "id": family_id,
                "category": str(entry.get("category") or "other"),
                "path": family_path,
                "artifact_status": artifact_status,
                "accepted": accepted,
                "consumed": consumed,
                "consumption_status": status,
                "has_payload": bool(payload),
                "payload_bytes": sum(item["bytes"] for item in payload),
                "payload_files": [item["name"] for item in payload][:12],
                "payload_file_count": len(payload),
                "json_payloads": json_sources[:6],
                "tier": tier,
                "evidence": evidence,
                "scope_closed": scope_closed,
                "scope_open_claims": scope_open_claims,
                "manifest_error": manifest_error,
            }
        )

    rows.sort(key=lambda row: (row["tier"], row["category"], row["id"]))

    shelf = [
        row
        for row in rows
        if row["accepted"] and row["has_payload"] and not row["consumed"]
    ]
    by_tier: dict[str, int] = {}
    for row in shelf:
        by_tier[row["tier"]] = by_tier.get(row["tier"], 0) + 1

    # The notes class is measured by the notes index, which already buckets
    # every note by what the remake would have to do with it.  Reusing it
    # keeps one number per population instead of two.
    notes_summary: dict[str, Any] | None = None
    if notes_index_path is not None and notes_index_path.is_file():
        notes = _read_json(notes_index_path)
        summary = notes.get("summary") or {}
        notes_summary = {
            "index": str(notes_index_path.relative_to(root))
            if notes_index_path.is_relative_to(root)
            else str(notes_index_path),
            "index_sha256": _sha256(notes_index_path),
            "total": summary.get("total"),
            "by_bucket": summary.get("by_bucket"),
            "needs_guard_without_any_test_reference": summary.get(
                "needs_guard_without_any_test_reference"
            ),
        }

    ledger = index.get("ledger") or []
    ledger_missing = sorted(
        str(item.get("id")) for item in ledger if item.get("status") == "missing"
    )

    return {
        "schema": BACKLOG_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": {
            "index": {
                "path": str(index_path.relative_to(root))
                if index_path.is_relative_to(root)
                else str(index_path),
                "sha256": _sha256(index_path),
            },
            "gap": {
                "path": str(gap_path.relative_to(root))
                if gap_path.is_relative_to(root)
                else str(gap_path),
                "sha256": _sha256(gap_path),
            },
            "reverse_root": str(reverse_root),
            "reverse_commit": source.get("commit"),
            "reverse_dirty": source.get("dirty"),
            "rom_sha256": source.get("rom_sha256"),
        },
        "rules": {
            "population": "index entries with kind == artifact",
            "accepted": 'manifest artifact_status == "accepted"',
            "has_payload": "at least one non-empty file that is not manifest.json/inputs.json and not a "
            + ", ".join(sorted(RECEIPT_SUFFIXES))
            + " receipt",
            "consumed": "gap receipt status == build",
            "shelf": "accepted and has_payload and not consumed",
            "tier_asset": "payload has a file with suffix in " + ", ".join(sorted(ASSET_SUFFIXES)),
            "tier_table": "JSON top-level keys hit the table vocabulary and no structural marker",
            "tier_analysis": "no table marker, and at least one structural or coverage marker",
            "tier_unclassified": "both a table marker and a structural marker, or no marker at all",
            "boilerplate_keys": sorted(BOILERPLATE_KEYS),
            "table_markers": sorted(TABLE_MARKERS),
            "structural_markers": sorted(STRUCTURAL_MARKERS),
            "coverage_markers": sorted(COVERAGE_MARKERS),
        },
        "summary": {
            "families_total": len(rows),
            "families_accepted": sum(1 for row in rows if row["accepted"]),
            "families_consumed": sum(1 for row in rows if row["consumed"]),
            "families_accepted_with_payload": sum(
                1 for row in rows if row["accepted"] and row["has_payload"]
            ),
            "shelf_total": len(shelf),
            "shelf_by_tier": dict(sorted(by_tier.items())),
            "shelf_payload_bytes": sum(row["payload_bytes"] for row in shelf),
            "shelf_scope_closed": sum(1 for row in shelf if row["scope_closed"] is True),
            "shelf_scope_open": sum(1 for row in shelf if row["scope_closed"] is False),
            "shelf_no_scope": sum(1 for row in shelf if row["scope_closed"] is None),
            "ledger_missing": len(ledger_missing),
            "notes": notes_summary,
        },
        "shelf": shelf,
        "ledger_missing": ledger_missing,
        "rows": rows,
    }


def _tier_zh(tier: str) -> str:
    return {
        TIER_ASSET: "资产直取",
        TIER_TABLE: "一次生成器",
        TIER_ANALYSIS: "仅判读",
        TIER_UNCLASSIFIED: "待判定",
    }.get(tier, tier)


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    inputs = payload["inputs"]
    lines: list[str] = []
    lines.append("# 未被使用但可直接用于复刻的逆向成果（自动生成）")
    lines.append("")
    lines.append("本文件由 `tools/measure_butano_usable_backlog.py` 生成，不要手工编辑。")
    lines.append("")
    lines.append("上一份差异清单（`artifacts/butano-reverse-gap-v1/gap.md`）回答的是「有没有被引用」；")
    lines.append("本文件回答的是「**能不能直接用**」。两者的分母相同，口径不同。")
    lines.append("")
    lines.append("## 输入")
    lines.append("")
    lines.append(f"- 索引：`{inputs['index']['path']}`（SHA-256 `{inputs['index']['sha256'][:16]}…`）")
    lines.append(f"- 差异清单：`{inputs['gap']['path']}`（SHA-256 `{inputs['gap']['sha256'][:16]}…`）")
    lines.append(f"- 逆向 commit：`{inputs['reverse_commit']}`（工作树 dirty={inputs['reverse_dirty']}）")
    lines.append(f"- ROM SHA-256：`{inputs['rom_sha256']}`")
    lines.append("")
    lines.append("## 过滤链与判定口径")
    lines.append("")
    rules = payload["rules"]
    for key in (
        "population",
        "accepted",
        "has_payload",
        "consumed",
        "shelf",
        "tier_asset",
        "tier_table",
        "tier_analysis",
        "tier_unclassified",
    ):
        lines.append(f"- **{key}**：`{rules[key]}`")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("| --- | ---: |")
    lines.append(f"| 成果族总数 | {summary['families_total']} |")
    lines.append(f"| 其中 `accepted` | {summary['families_accepted']} |")
    lines.append(f"| 其中已被构建链消费 | {summary['families_consumed']} |")
    lines.append(f"| `accepted` 且带 payload | {summary['families_accepted_with_payload']} |")
    lines.append(f"| **未被使用的货架（shelf）** | **{summary['shelf_total']}** |")
    lines.append(f"| 货架 payload 总量 | {summary['shelf_payload_bytes']:,} 字节 |")
    lines.append(
        f"| 货架里 scope **全部闭合**的族 | {summary.get('shelf_scope_closed', 0)} |"
    )
    lines.append(
        f"| 货架里 scope 仍有未闭合声明的族 | {summary.get('shelf_scope_open', 0)} |"
    )
    lines.append(f"| 货架里 manifest 没写 scope 的族 | {summary.get('shelf_no_scope', 0)} |")
    lines.append(f"| 台账 `missing` | {summary['ledger_missing']} |")
    lines.append("")
    lines.append("### 货架分层")
    lines.append("")
    lines.append("| 层 | 含义 | 族数 |")
    lines.append("| --- | --- | ---: |")
    meaning = {
        TIER_ASSET: "payload 是 remake 资产管线能直接读的字节（像素／图块／调色板／LZ77／音频）",
        TIER_TABLE: "payload 是内容表，接入只需一个生成器",
        TIER_ANALYSIS: "payload 是控制流／覆盖分母／审计证据——约束行为，但不能导入",
        TIER_UNCLASSIFIED: "两类词表都命中或都没命中，不强行归类",
    }
    for tier, count in summary["shelf_by_tier"].items():
        lines.append(f"| `{tier}`（{_tier_zh(tier)}） | {meaning.get(tier, '')} | {count} |")
    lines.append("")
    if summary.get("notes"):
        notes = summary["notes"]
        lines.append("## notes 侧（复用 notes 索引的既有分桶）")
        lines.append("")
        lines.append(f"- 索引：`{notes['index']}`")
        lines.append(f"- note 文件总数：{notes.get('total')}")
        buckets = notes.get("by_bucket") or {}
        for bucket, count in sorted(buckets.items()):
            lines.append(f"  - `{bucket}`：{count}")
        lines.append(
            f"- `needs_guard` 里**连测试都没引用**的：{notes.get('needs_guard_without_any_test_reference')}"
        )
        lines.append("")
    lines.append("## 货架明细")
    lines.append("")
    for tier in (TIER_ASSET, TIER_TABLE, TIER_UNCLASSIFIED, TIER_ANALYSIS):
        group = [row for row in payload["shelf"] if row["tier"] == tier]
        if not group:
            continue
        lines.append(f"### `{tier}`（{_tier_zh(tier)}）— {len(group)} 族")
        lines.append("")
        lines.append("| 族 | 类别 | payload | 字节 | 判定证据 | scope |")
        lines.append("| --- | --- | --- | ---: | --- | --- |")
        for row in group:
            evidence = row["evidence"]
            if tier == TIER_ASSET:
                mark = ", ".join(evidence.get("asset_suffixes") or [])
                if evidence.get("baseline_files"):
                    mark += "；baseline: " + ", ".join(evidence["baseline_files"][:3])
            elif tier == TIER_TABLE:
                mark = "table: " + ", ".join(evidence.get("table_markers") or [])
            elif tier == TIER_ANALYSIS:
                mark = "structural: " + ", ".join(evidence.get("structural_markers") or [])
                if evidence.get("coverage_markers"):
                    mark += ("；" if mark else "") + "coverage: " + ", ".join(
                        evidence["coverage_markers"][:4]
                    )
            else:
                mark = "table: " + ", ".join(evidence.get("table_markers") or [])
                mark += ("；" if mark else "") + "structural: " + ", ".join(
                    evidence.get("structural_markers") or []
                )
            files = ", ".join(f"`{name}`" for name in row["payload_files"][:4])
            if row.get("scope_closed") is True:
                scope = "scope 全闭合"
            elif row.get("scope_closed") is False:
                scope = "scope 未闭合: " + ", ".join(row.get("scope_open_claims") or [])[:2]
            else:
                scope = "manifest 无 scope"
            lines.append(
                f"| `{row['id']}` | {row['category']} | {files} | {row['payload_bytes']:,} "
                f"| {mark} | {scope} |"
            )
        lines.append("")
    lines.append("## 边界声明")
    lines.append("")
    lines.append("- 分层是**词表探针**的结果，不是逐族人工判定；每个族的判定证据都写在明细表里，可逐行复核。")
    lines.append("- `analysis-only` 的族**不是无用**：它们约束 remake 的行为（哪些字节被消费、")
    lines.append("  哪些分母成立），但它们不是可导入的素材。")
    lines.append("- 本清单不把「已被引用」当「已使用」：`build` 才是消费，文档提及不是。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the reverse results the remake could use but does not use."
    )
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument(
        "--index",
        default=Path("artifacts/reverse-results-index-v1/index.json"),
        type=Path,
    )
    parser.add_argument(
        "--gap",
        default=Path("artifacts/butano-reverse-gap-v1/gap.json"),
        type=Path,
    )
    parser.add_argument(
        "--notes-index",
        default=Path("artifacts/reverse-notes-index-v1/notes-index.json"),
        type=Path,
    )
    parser.add_argument(
        "--out-dir", default=Path("artifacts/butano-usable-backlog-v1"), type=Path
    )
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        payload = measure(
            root=root,
            index_path=args.index,
            gap_path=args.gap,
            notes_index_path=args.notes_index,
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "backlog.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path = out_dir / "backlog.md"
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    summary = payload["summary"]
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(
        f"families={summary['families_total']} accepted={summary['families_accepted']} "
        f"shelf={summary['shelf_total']}"
    )
    for tier, count in summary["shelf_by_tier"].items():
        print(f"  {tier}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
