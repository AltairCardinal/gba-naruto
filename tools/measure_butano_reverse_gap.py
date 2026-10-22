#!/usr/bin/env python3
"""Measure, from the whole tree, what the remake has and has not taken from the
reverse engineering results.

The reverse work tree holds the verified results: the artifact families with
manifests, 427 notes, 65 documents.  The remake tree holds the Butano build.
Nothing in the repository states which of those results the remake actually
consumes, which ones it re-derived locally from the original ROM, and which
ones nobody ever touched.

That gap is the input a roadmap has to be built from, so it has to be a number
produced by a script over the whole tree -- never a hand-kept list.  The
classification rules are deliberately conservative:

``build``
    the remake's build chain (``butano-sequel/``, ``tools/``) references the
    family.  This is the only status that means "the remake uses it".
``local_artifact``
    only the tree's own ``artifacts/`` reference it.  The result exists in
    this tree, usually because the remake re-derived it from the original ROM
    instead of importing the reverse result.  Present, but not imported.
``test``
    only ``tests/`` reference it.  A contract exists, no production use.
``doc``
    only ``docs/`` or ``notes/`` mention it.  A mention, not a use.
``none``
    nothing in the tree references it.  This is the real gap.

The index machinery (``tools/build_reverse_results_index.py`` and
``artifacts/reverse-results-index-v1/``) mentions every family by
construction, so it is excluded and the exclusion is reported.

The rebuild ledger (``docs/reverse-results-index/ledger.json``) is ground truth
for the items it covers and is merged into the rows, not kept apart: a family
whose ledger entry says ``missing`` is reported as missing even when the
family name appears in prose somewhere.

Usage::

    python3 tools/measure_butano_reverse_gap.py \\
        --root . \\
        --index artifacts/reverse-results-index-v1/index.json \\
        --out-dir artifacts/butano-reverse-gap-v1
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

GAP_SCHEMA = "konoha.butano-reverse-gap.v1"

# Kinds that carry a result a remake could consume.  ``tool`` and ``test``
# are machinery, not results, and are counted separately.
RESULT_KINDS = ("artifact", "note", "doc")
MACHINERY_KINDS = ("tool", "test")

# Where a reference lands decides the status.  First match wins.
SCAN_ROOTS: tuple[tuple[str, str], ...] = (
    ("butano-sequel", "build"),
    ("tools", "build"),
    ("artifacts", "local_artifact"),
    ("tests", "test"),
    ("docs", "doc"),
    ("notes", "doc"),
    ("sequel", "build"),
)

# Never scanned: noise, vendored code, generated output.
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "build",
    "third_party",
    ".pi",
}

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".cmake",
    ".cpp",
    ".css",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".json",
    ".lua",
    ".md",
    ".mako",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

# The index builder and its output mention every family; they are the
# measuring apparatus, not a consumer.  The gap receipt does the same: it
# names every family in every row, so a second run would read its own output
# as a reference and lift every `doc` and `none` row into `local_artifact`.
# Without this exclusion the measurement is not repeatable, which would make
# the "claiming a result raises its status" gate of M7 unreadable.
EXCLUDED_PREFIXES = (
    "artifacts/reverse-results-index-v1/",
    "tools/build_reverse_results_index.py",
    "artifacts/butano-reverse-gap-v1/",
    "artifacts/reverse-notes-index-v1/",
    "artifacts/butano-reverse-m3-import-v1/",
    # The roadmap quotes the untouched families in prose, and the theory note
    # quotes the consumed ones.  Counting those as references would mean that
    # writing the report *improves* the measurement, which is a self reference
    # artefact: it was observed to lift all 15 untouched families from `none`
    # to `doc` purely because the roadmap lists them under "never touched".
    "docs/butano-reverse-gap-roadmap.md",
    "notes/full-customization-and-fidelity-theory-20261020.md",
    # The notes index classifies every reverse note, so it names all 427 of
    # them.  It is a bulk enumerator of the measured population, exactly like
    # the roadmap: its hits are classification, not consumption.  Its own
    # receipt keeps the honest pre-index status.
    "docs/reverse-results-index/notes-index.md",
    # The S49 roster receipt is a *measurement* of one battle, not a
    # consumption of a family: it names the reverse family it was cross
    # checked against, and the honest consumption signal is the verifier in
    # tools/ that reads that family at runtime.  Counting the receipt would
    # count the same family twice.
    "artifacts/s49-original-battle14-roster-v1/",
    # Same reasoning for the post-battle settlement receipt: it is a
    # measurement of one battle, and the honest consumption signal is the
    # verifier in tools/ that produces it.
    "artifacts/s49-result-settlement-v1/",
    # Same for the same-frame GPU receipts: they are measurements of one
    # frame, and the family they were compared against is not consumed by
    # them.
    "artifacts/s49-original-movegrid-frame-v1/",
    "artifacts/s49-original-banner-frame-v1/",
    "artifacts/s49-original-movegrid-mechanism-v1/",
    # The usable-backlog receipt enumerates every family in its rows, exactly
    # like this receipt does.  Counting it would lift every untouched family
    # from `none`/`doc` to `local_artifact` and make a second run of this
    # tool disagree with the first -- the same self-reference artefact the
    # exclusions above exist to prevent.
    "artifacts/butano-usable-backlog-v1/",
    # The wiring-coverage receipt enumerates every family too, and it names
    # the products as well.  Same self-reference artefact as above.
    "artifacts/butano-wiring-coverage-v1/",
)
EXCLUDED_PREFIXES_OUTPUT = (
    "artifacts/reverse-results-index-v1",
    "tools/build_reverse_results_index.py",
    "artifacts/butano-reverse-gap-v1",
    "artifacts/reverse-notes-index-v1",
    "artifacts/butano-reverse-m3-import-v1",
    "docs/butano-reverse-gap-roadmap.md",
    "notes/full-customization-and-fidelity-theory-20261020.md",
    "docs/reverse-results-index/notes-index.md",
    "artifacts/s49-original-battle14-roster-v1",
    "artifacts/s49-result-settlement-v1",
    "artifacts/s49-original-movegrid-frame-v1",
    "artifacts/s49-original-banner-frame-v1",
    "artifacts/s49-original-movegrid-mechanism-v1",
    "artifacts/butano-usable-backlog-v1",
    "artifacts/butano-wiring-coverage-v1",
)

MAX_FILE_BYTES = 4 * 1024 * 1024

# Identifiers shorter than this are too generic to search for directly
# ("audio" would match every sentence); they are only matched in their
# ``artifacts/<id>`` path form.
MIN_BARE_IDENTIFIER = 8


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_excluded(rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def _collect_text_files(root: Path) -> list[tuple[str, str]]:
    """Return every scannable text file as ``(relative path, text)``."""
    found: list[tuple[str, str]] = []
    for scan_root, _status in SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel_parts = path.relative_to(root).parts
            except ValueError:  # pragma: no cover - defensive
                continue
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = "/".join(rel_parts)
            if _is_excluded(rel):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:  # pragma: no cover - defensive
                continue
            # The path counts as a reference too: a file that *lives* under
            # ``artifacts/<family>/`` is that family's presence in this tree,
            # even when its content never spells the family name.
            found.append((rel, rel + "\n" + text))
    found.sort()
    return found


def _identifiers(entry: dict) -> list[str]:
    """Search identifiers for one index entry."""
    out: list[str] = []
    family_id = str(entry.get("id") or "")
    schema = str(entry.get("schema") or "")
    for candidate in (family_id, schema):
        if candidate and candidate not in out:
            out.append(candidate)
    return out


# One pass of this over a file yields every identifier-shaped token in it.
# Tokenising once and intersecting is orders of magnitude faster than running
# one alternation per family over the whole tree.
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _build_matchers(
    entries: list[dict],
) -> tuple[dict[str, list[str]], re.Pattern[str] | None, dict[str, list[str]]]:
    """Build the token map, the short-identifier path pattern and its map.

    Long identifiers are matched as whole tokens.  Short identifiers are too
    generic to search for as words ("audio" would match every sentence), so
    they are only matched in their ``artifacts/<id>`` path form.
    """
    token_map: dict[str, list[str]] = {}
    path_map: dict[str, list[str]] = {}
    path_parts: list[str] = []

    for entry in entries:
        family_id = str(entry.get("id") or "")
        if not family_id:
            continue
        for identifier in _identifiers(entry):
            if len(identifier) >= MIN_BARE_IDENTIFIER:
                token_map.setdefault(identifier.lower(), []).append(family_id)
        if len(family_id) < MIN_BARE_IDENTIFIER:
            path_form = f"artifacts/{family_id}"
            path_map.setdefault(path_form, []).append(family_id)
            path_parts.append(re.escape(path_form))

    path_pattern = None
    if path_parts:
        alternation = "|".join(sorted(set(path_parts), key=len, reverse=True))
        path_pattern = re.compile(
            r"(?<![A-Za-z0-9_\-])(?:" + alternation + r")(?![A-Za-z0-9_\-])"
        )
    return token_map, path_pattern, path_map


def _status_for(rel: str) -> str:
    for scan_root, status in SCAN_ROOTS:
        if rel == scan_root or rel.startswith(scan_root + "/"):
            return status
    return "other"


def _link_ledger(entries: list[dict], ledger: list[dict]) -> dict[str, list[dict]]:
    """Map a family id to the ledger entries that name it as their source."""
    linked: dict[str, list[dict]] = {}
    families = [
        (str(entry.get("id") or ""), str(entry.get("path") or ""))
        for entry in entries
        if entry.get("kind") == "artifact"
    ]
    for ledger_entry in ledger:
        source = str(ledger_entry.get("source") or "")
        if not source:
            continue
        for family_id, family_path in families:
            if not family_path:
                continue
            if source == family_path or source.startswith(family_path.rstrip("/") + "/"):
                linked.setdefault(family_id, []).append(ledger_entry)
    return linked


def _manifest_hint(reverse_root: Path, entry: dict) -> str:
    """A one-line capability hint read from the reverse manifest, if present."""
    manifest = str(entry.get("manifest") or "")
    if not manifest:
        return ""
    path = reverse_root / manifest
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    for key in ("summary", "description", "scope", "coverage_claim", "title"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().replace("\n", " ")[:240]
    provides = data.get("provides")
    if isinstance(provides, list) and provides:
        return "provides: " + ", ".join(str(item) for item in provides[:8])[:240]
    return ""


def measure(root: Path, index_path: Path, reverse_root: Path) -> dict[str, Any]:
    if not index_path.is_file():
        raise FileNotFoundError(f"index not found: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = list(index.get("entries") or [])
    ledger = list(index.get("ledger") or [])

    files = _collect_text_files(root)
    token_map, path_pattern, path_map = _build_matchers(entries)

    # One pass over the tree: tokenise every file once, then intersect.
    hits: dict[str, list[str]] = {}
    for rel, text in files:
        found: set[str] = set()
        for token in _TOKEN_RE.findall(text):
            for family_id in token_map.get(token.lower(), ()):
                found.add(family_id)
        if path_pattern is not None:
            for match in path_pattern.finditer(text):
                for family_id in path_map.get(match.group(0), ()):
                    found.add(family_id)
        if not found:
            continue
        status = _status_for(rel)
        for family_id in found:
            bucket = hits.setdefault(family_id, [])
            bucket.append(f"{status}:{rel}")

    linked_ledger = _link_ledger(entries, ledger)

    rows: list[dict[str, Any]] = []
    for entry in entries:
        family_id = str(entry.get("id") or "")
        kind = str(entry.get("kind") or "")
        if not family_id:
            continue
        raw_hits = hits.get(family_id, [])
        statuses = {hit.split(":", 1)[0] for hit in raw_hits}
        for candidate in ("build", "local_artifact", "test", "doc"):
            if candidate in statuses:
                status = candidate
                break
        else:
            status = "none"
        ledger_entries = linked_ledger.get(family_id, [])
        row: dict[str, Any] = {
            "id": family_id,
            "kind": kind,
            "category": str(entry.get("category") or "other"),
            "path": str(entry.get("path") or ""),
            "schema": str(entry.get("schema") or ""),
            "status": status,
            "hits": sorted(raw_hits)[:12],
            "hit_count": len(raw_hits),
            "ledger_status": ledger_entries[0].get("status") if ledger_entries else None,
            "ledger_id": ledger_entries[0].get("id") if ledger_entries else None,
            "manifest_hint": _manifest_hint(reverse_root, entry),
        }
        rows.append(row)

    rows.sort(key=lambda row: (row["kind"], row["category"], row["id"]))

    by_status: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = {}
    by_kind: dict[str, dict[str, int]] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        by_category.setdefault(row["category"], {})
        by_category[row["category"]][row["status"]] = by_category[row["category"]].get(row["status"], 0) + 1
        by_kind.setdefault(row["kind"], {})
        by_kind[row["kind"]][row["status"]] = by_kind[row["kind"]].get(row["status"], 0) + 1

    result_kinds = set(RESULT_KINDS)
    gap_families = [
        row["id"]
        for row in rows
        if row["kind"] in result_kinds and row["status"] == "none"
    ]
    ledger_missing = sorted(
        str(entry.get("id"))
        for entry in ledger
        if entry.get("status") == "missing" and entry.get("id")
    )

    source = index.get("source") or {}
    return {
        "schema": GAP_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "index": {
            "path": str(index_path.relative_to(root)) if index_path.is_relative_to(root) else str(index_path),
            "sha256": _sha256(index_path),
            "schema": index.get("schema"),
            "reverse_root": source.get("reverse_root"),
            "reverse_commit": source.get("commit"),
            "reverse_dirty": source.get("dirty"),
            "rom_sha256": source.get("rom_sha256"),
        },
        "measurement": {
            "unit": "reverse result entry (artifact family / note / doc)",
            "result_kinds": list(RESULT_KINDS),
            "machinery_kinds": list(MACHINERY_KINDS),
            "scanned_files": len(files),
            "scan_roots": [name for name, _ in SCAN_ROOTS],
            "excluded_prefixes": list(EXCLUDED_PREFIXES_OUTPUT),
            "min_bare_identifier": MIN_BARE_IDENTIFIER,
        },
        "rows": rows,
        "gap_families": gap_families,
        "ledger_missing": ledger_missing,
        "summary": {
            "total": len(rows),
            "by_status": dict(sorted(by_status.items())),
            "by_category": {k: dict(sorted(v.items())) for k, v in sorted(by_category.items())},
            "by_kind": {k: dict(sorted(v.items())) for k, v in sorted(by_kind.items())},
            "result_total": sum(1 for row in rows if row["kind"] in result_kinds),
            "result_gap": len(gap_families),
            "ledger_missing": len(ledger_missing),
            # The artifact-family denominator moves whenever the reverse work
            # tree promotes a new family, so it is recorded here and must be
            # read from this receipt rather than hard-coded in prose.
            "artifact_family_total": sum(
                1 for row in rows if row["kind"] == "artifact"
            ),
            "artifact_family_by_status": {
                status: sum(
                    1
                    for row in rows
                    if row["kind"] == "artifact" and row["status"] == status
                )
                for status in sorted(by_status)
            },
        },
    }


def _status_order(status: str) -> int:
    return {"build": 0, "local_artifact": 1, "test": 2, "doc": 3, "none": 4}.get(status, 5)


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    index = payload["index"]
    lines: list[str] = []
    lines.append("# Butano 侧对逆向成果的差异清单（自动生成）")
    lines.append("")
    lines.append("本文件由 `tools/measure_butano_reverse_gap.py` 生成，不要手工编辑。")
    lines.append("")
    lines.append("输出：`gap.json`（机读）、`gap.md`（本文件）。")
    lines.append("")
    lines.append(f"- 索引：`{index['path']}`")
    lines.append(f"- 索引 SHA-256：`{index['sha256']}`")
    lines.append(f"- 逆向 commit：`{index['reverse_commit']}`（工作树 dirty={index['reverse_dirty']}）")
    lines.append(f"- ROM SHA-256：`{index['rom_sha256']}`")
    lines.append(f"- 测量单位：{payload['measurement']['unit']}")
    lines.append(f"- 扫描文件数：{payload['measurement']['scanned_files']}")
    lines.append(f"- 排除前缀：{', '.join('`' + p + '`' for p in payload['measurement']['excluded_prefixes'])}")
    lines.append("")
    lines.append("## 状态定义")
    lines.append("")
    lines.append("| 状态 | 含义 |")
    lines.append("| --- | --- |")
    lines.append("| `build` | remake 构建链（`butano-sequel/`、`tools/`）引用——**唯一算消费** |")
    lines.append("| `local_artifact` | 只有本树 `artifacts/` 引用——本树有，但没从逆向成果引入 |")
    lines.append("| `test` | 只有 `tests/` 引用——有契约，无生产使用 |")
    lines.append("| `doc` | 只有 `docs/`/`notes/` 提及——提及，不是使用 |")
    lines.append("| `none` | 全树无引用——**真正的差异项** |")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("| --- | ---: |")
    lines.append(f"| 条目总数 | {summary['total']} |")
    lines.append(f"| 成果类（artifact/note/doc） | {summary['result_total']} |")
    lines.append(f"| 成果类无引用（`none`） | {summary['result_gap']} |")
    family_total = summary.get("artifact_family_total")
    if family_total:
        family_build = summary.get("artifact_family_by_status", {}).get("build", 0)
        lines.append(
            f"| 成果族（artifact family） | {family_total} |"
        )
        lines.append(
            f"| 成果族 `build` 占比 | {family_build} / {family_total}"
            f" = {100.0 * family_build / family_total:.1f}% |"
        )
    lines.append(f"| 台账 `missing` 条目 | {summary['ledger_missing']} |")
    lines.append("")
    lines.append("| 状态 | 条目数 |")
    lines.append("| --- | ---: |")
    for status, count in summary["by_status"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.append("")
    lines.append("## 按类别 × 状态")
    lines.append("")
    header = "| 类别 | " + " | ".join(f"`{s}`" for s in summary["by_status"]) + " | 合计 |"
    lines.append(header)
    lines.append("| --- |" + " ---: |" * (len(summary["by_status"]) + 1))
    for category, counts in summary["by_category"].items():
        cells = [str(counts.get(status, 0)) for status in summary["by_status"]]
        lines.append(f"| {category} | " + " | ".join(cells) + f" | {sum(counts.values())} |")
    lines.append("")
    lines.append("## 真正未被触及的成果（`none`）")
    lines.append("")
    if payload["gap_families"]:
        lines.append("| id | kind | category | 逆向路径 |")
        lines.append("| --- | --- | --- | --- |")
        for row in payload["rows"]:
            if row["id"] in set(payload["gap_families"]):
                lines.append(
                    f"| `{row['id']}` | {row['kind']} | {row['category']} | `{row['path']}` |"
                )
    else:
        lines.append("（无）")
    lines.append("")
    lines.append("## 台账 `missing` 条目")
    lines.append("")
    if payload["ledger_missing"]:
        for ledger_id in payload["ledger_missing"]:
            lines.append(f"- `{ledger_id}`")
    else:
        lines.append("（无）")
    lines.append("")
    lines.append("## 全部条目")
    lines.append("")
    lines.append("| id | kind | category | 状态 | 台账 | 命中数 |")
    lines.append("| --- | --- | --- | --- | --- | ---: |")
    for row in sorted(payload["rows"], key=lambda r: (_status_order(r["status"]), r["id"])):
        lines.append(
            f"| `{row['id']}` | {row['kind']} | {row['category']} | `{row['status']}` | "
            f"{row['ledger_status'] or '—'} | {row['hit_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="remake work tree root")
    parser.add_argument(
        "--index",
        default="artifacts/reverse-results-index-v1/index.json",
        help="reverse results index to measure against",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/butano-reverse-gap-v1",
        help="output directory",
    )
    parser.add_argument(
        "--reverse-root",
        default="/Users/altair/github/gba-naruto-reverse",
        help="reverse work tree, read only, for manifest hints",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    index_path = Path(args.index)
    if not index_path.is_absolute():
        index_path = (root / index_path).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (root / out_dir).resolve()
    reverse_root = Path(args.reverse_root)

    try:
        payload = measure(root, index_path, reverse_root)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"error: index is not valid JSON: {error}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gap.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "gap.md").write_text(render_markdown(payload), encoding="utf-8")

    summary = payload["summary"]
    print(f"wrote {out_dir / 'gap.json'}")
    print(f"wrote {out_dir / 'gap.md'}")
    print(
        f"entries={summary['total']} results={summary['result_total']} "
        f"gaps={summary['result_gap']} ledger_missing={summary['ledger_missing']}"
    )
    for status, count in summary["by_status"].items():
        print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
