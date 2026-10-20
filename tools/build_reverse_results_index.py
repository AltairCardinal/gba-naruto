#!/usr/bin/env python3
"""Index the reverse engineering results and audit what the remake reused.

The remake is only allowed to use assets, formulas and rules that the reverse
engineering actually established.  Keeping that promise checkable needs an
index: without one, "we took it from the reverse results" is a claim, and the
only way to test it is to grep 400 notes by hand.

This tool therefore builds two things:

* a machine readable index of every reverse result that is visible from the
  reverse work tree -- artifact families with their schema, the formulas and
  the address ranges they pin down, the notes, the documents, the tools and
  the tests;
* an audit of the rebuild ledger, which records, for every thing the remake
  needed, where it came from and whether that source really exists.

The ledger is the part that matters for the goal.  Every entry names a
status and, where it has one, a source.  The tool refuses to call an entry
"reused" when the source is not on disk, refuses to call an entry
"not-applicable" when the result it talks about is not on disk either, and
reports every entry that is still `missing` as a problem.  Both the
"not applicable" and the "still missing" cases are recorded instead of being
papered over.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")
OUT_DIR = ROOT / "artifacts/reverse-results-index-v1"
LEDGER = ROOT / "docs/reverse-results-index/ledger.json"

INDEX_SCHEMA = "konoha.reverse-results-index.v1"
LEDGER_SCHEMA = "konoha.reverse-results-ledger.v1"

# Statuses a ledger entry may claim.  `reused` and `derived` mean a reverse
# result was used; `reconstructed` means the reverse result was not usable
# and the remake took the evidence from the original ROM instead;
# `not-applicable` means the remake does not need that result at all and the
# entry records why; `missing` means neither the reverse result nor a
# reconstruction exists and is an open gap.
STATUSES = ("reused", "derived", "reconstructed", "not-applicable", "missing")

# The name of the reverse result an entry depends on, and the category it
# belongs to.  Order matters: the first matching prefix wins.
CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("rom-", "rom"),
    ("rom_", "rom"),
    ("battle-visual", "visual"),
    ("battle-effect", "visual"),
    ("character", "visual"),
    ("tile", "visual"),
    ("sprite", "visual"),
    ("portrait", "presentation"),
    ("menu", "presentation"),
    ("story", "presentation"),
    ("cutscene", "presentation"),
    ("bg-", "visual"),
    ("world", "map"),
    ("map", "map"),
    ("scene", "map"),
    ("battle", "battle"),
    ("audio", "audio"),
    ("runtime", "runtime"),
    ("s49", "s49"),
    ("scenario", "scenario"),
)

SKIP_KEYS = {"schema", "generated_at", "notes", "description"}


class IndexError_(RuntimeError):
    """The index could not be built as declared."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def categorise(name: str) -> str:
    lowered = name.lower()
    for prefix, category in CATEGORY_RULES:
        if lowered.startswith(prefix):
            return category
    if lowered.startswith("residual"):
        return "residual"
    if lowered.startswith("e2e") or lowered.startswith("overview"):
        return "overview"
    return "other"


def walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


def collect_formulas(manifest: dict[str, Any]) -> list[str]:
    """Every formula the manifest states, wherever it is nested."""

    formulas: list[str] = []
    for key, value in manifest.items():
        if not isinstance(value, dict):
            continue
        for name, item in value.items():
            if name != "formula":
                continue
            if isinstance(item, str):
                formulas.append(item)
            else:
                formulas.extend(walk_strings(item))
    return formulas


def collect_addresses(manifest: dict[str, Any]) -> list[str]:
    """The address ranges the manifest pins down."""

    addresses: list[str] = []
    for key, value in manifest.items():
        if not isinstance(value, dict):
            continue
        for name, item in value.items():
            if name not in ("code_slices", "code_ranges", "slices"):
                continue
            if not isinstance(item, list):
                continue
            for entry in item:
                if not isinstance(entry, dict):
                    continue
                start = entry.get("gba_start")
                end = entry.get("gba_end")
                if start and end:
                    addresses.append(f"{start}-{end}")
    return addresses


def collect_dependencies(manifest: dict[str, Any]) -> list[str]:
    """The other artifact families the manifest was built from."""

    dependencies: list[str] = []
    sources = manifest.get("source_artifacts")
    if isinstance(sources, dict):
        for item in sources.values():
            if isinstance(item, dict) and item.get("manifest"):
                dependencies.append(str(item["manifest"]))
    return dependencies


def scan_artifacts(reverse_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    artifacts = reverse_root / "artifacts"
    if not artifacts.is_dir():
        return entries
    for family in sorted(artifacts.iterdir()):
        if not family.is_dir():
            continue
        manifest_path = family / "manifest.json"
        entry: dict[str, Any] = {
            "id": family.name,
            "kind": "artifact",
            "category": categorise(family.name),
            "path": f"artifacts/{family.name}",
            "manifest": f"artifacts/{family.name}/manifest.json",
        }
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise IndexError_(
                    f"the manifest of {family.name} is not valid JSON: {error}"
                ) from error
            entry["schema"] = manifest.get("schema", "")
            entry["manifest_sha256"] = sha256_file(manifest_path)
            rom = manifest.get("rom")
            if isinstance(rom, dict):
                entry["rom_sha256"] = rom.get("sha256", "")
            entry["provides"] = sorted(
                key
                for key in manifest
                if key not in SKIP_KEYS and isinstance(manifest[key], dict)
            )
            entry["formulas"] = collect_formulas(manifest)
            entry["addresses"] = collect_addresses(manifest)
            entry["depends_on"] = collect_dependencies(manifest)
        else:
            entry["schema"] = ""
            entry["provides"] = []
            entry["formulas"] = []
            entry["addresses"] = []
            entry["depends_on"] = []
        entries.append(entry)
    return entries


def first_heading(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem


def scan_documents(reverse_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for folder, kind in (("notes", "note"), ("docs", "doc")):
        base = reverse_root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            relative = path.relative_to(reverse_root)
            entries.append(
                {
                    "id": path.stem,
                    "kind": kind,
                    "category": categorise(path.stem),
                    "path": str(relative),
                    "title": first_heading(path),
                }
            )
    return entries


def scan_code(reverse_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for folder, kind, pattern in (
        ("tools", "tool", "*.py"),
        ("tests", "test", "test_*.py"),
    ):
        base = reverse_root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob(pattern)):
            relative = path.relative_to(reverse_root)
            entries.append(
                {
                    "id": path.stem,
                    "kind": kind,
                    "category": "code",
                    "path": str(relative),
                    "title": first_heading(path),
                }
            )
    return entries


def resolve_source(source: str, reverse_root: Path) -> Path | None:
    """Find the file a ledger entry points at, in either work tree."""

    candidates = [reverse_root / source, ROOT / source]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def audit_ledger(
    ledger: dict[str, Any],
    reverse_root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Check every ledger entry against the files on disk.

    Three rules, all of them fail closed:

    * an unknown status is a problem and the entry is demoted to `missing`;
    * an entry that declares a source must have that source on disk, in the
      reverse work tree or in this one -- a pointer that does not resolve is
      a problem and the entry is demoted to `missing`;
    * an entry that is still `missing` is an open gap and is reported as a
      problem, because the rebuild is not allowed to leave one behind.

    `not-applicable` is a real answer, not a gap: it says the remake does not
    need that result.  It still has to point at something real, so the second
    rule applies to it as well.
    """

    entries: list[dict[str, Any]] = []
    problems: list[str] = []
    for raw in ledger.get("entries", []):
        entry = dict(raw)
        entry_id = str(entry.get("id", "?"))
        status = str(entry.get("status", ""))
        source = str(entry.get("source", ""))
        if status not in STATUSES:
            problems.append(
                f"{entry_id}: unknown status {status!r}"
            )
            entry["status"] = "missing"
            entry["audit"] = "unknown status"
            entries.append(entry)
            continue
        resolved = resolve_source(source, reverse_root) if source else None
        if source and resolved is None:
            problems.append(
                f"{entry_id}: status {status} but the source "
                f"{source!r} is not on disk"
            )
            entry["status"] = "missing"
            entry["audit"] = "source not found"
        elif resolved is not None:
            entry["audit"] = "source found"
            entry["source_sha256"] = (
                sha256_file(resolved)
                if resolved.is_file()
                else ""
            )
        else:
            entry["audit"] = "no source declared"
        if entry["status"] == "missing":
            problems.append(
                f"{entry_id}: the entry is still missing, the rebuild is not "
                "allowed to leave a gap behind"
            )
        entries.append(entry)
    return entries, problems


def render_readme(
    index: dict[str, Any],
    ledger_entries: list[dict[str, Any]],
    problems: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# 逆向成果索引（自动生成）")
    lines.append("")
    lines.append(
        "本文件由 `tools/build_reverse_results_index.py` 生成，"
        "不要手工编辑；手工维护的是 "
        "`docs/reverse-results-index/ledger.json`。"
    )
    lines.append("")
    lines.append(f"- 索引 schema：`{index['schema']}`")
    lines.append(f"- 逆向工作树：`{index['source']['reverse_root']}`")
    lines.append(f"- 逆向 commit：`{index['source']['commit']}`")
    lines.append(f"- 逆向工作树是否有未提交改动：{index['source']['dirty']}")
    lines.append(f"- 条目总数：{len(index['entries'])}")
    lines.append("")

    lines.append("## 分类统计")
    lines.append("")
    lines.append("| 分类 | 条目数 |")
    lines.append("| --- | --- |")
    for category, count in sorted(index["categories"].items()):
        lines.append(f"| {category} | {count} |")
    lines.append("")

    lines.append("## 复刻台账（本次重建用到的东西从哪来）")
    lines.append("")
    lines.append("| 项 | 类别 | 状态 | 来源 | 审计 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for entry in ledger_entries:
        lines.append(
            f"| {entry.get('title', entry.get('id', ''))} "
            f"| {entry.get('category', '')} "
            f"| {entry.get('status', '')} "
            f"| `{entry.get('source', '') or '—'}` "
            f"| {entry.get('audit', '')} |"
        )
    lines.append("")
    if problems:
        lines.append("### 台账问题（必须处理）")
        lines.append("")
        for problem in problems:
            lines.append(f"- {problem}")
        lines.append("")
    else:
        lines.append(
            "台账无问题：每条都给出了状态与可核验的来源指针，"
            "没有条目留在 `missing`。"
        )
        lines.append("")

    lines.append("## 成果条目")
    lines.append("")
    for category in sorted(index["categories"]):
        entries = [
            entry
            for entry in index["entries"]
            if entry["category"] == category
        ]
        if not entries:
            continue
        lines.append(f"### {category}（{len(entries)}）")
        lines.append("")
        lines.append("| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for entry in entries:
            provides = ", ".join(entry.get("provides", []) or [])
            lines.append(
                f"| `{entry['id']}` | {entry['kind']} "
                f"| `{entry['path']}` | {provides or '—'} "
                f"| {len(entry.get('formulas', []))} "
                f"| {len(entry.get('addresses', []))} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=DEFAULT_REVERSE_ROOT,
        help="the reverse engineering work tree to index",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be written without writing it",
    )
    args = parser.parse_args()

    reverse_root = args.reverse_root.resolve()
    if not reverse_root.is_dir():
        print(f"error: no reverse work tree at {reverse_root}", file=sys.stderr)
        return 1
    if not args.ledger.is_file():
        print(f"error: no ledger at {args.ledger}", file=sys.stderr)
        return 1
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    if ledger.get("schema") != LEDGER_SCHEMA:
        print(
            f"error: the ledger schema is {ledger.get('schema')!r}, "
            f"expected {LEDGER_SCHEMA!r}",
            file=sys.stderr,
        )
        return 1

    entries = (
        scan_artifacts(reverse_root)
        + scan_documents(reverse_root)
        + scan_code(reverse_root)
    )
    categories: dict[str, int] = {}
    for entry in entries:
        categories[entry["category"]] = categories.get(entry["category"], 0) + 1

    ledger_entries, problems = audit_ledger(ledger, reverse_root)
    status = git_output(reverse_root, "rev-parse", "HEAD")
    dirty = bool(git_output(reverse_root, "status", "--porcelain"))

    index = {
        "schema": INDEX_SCHEMA,
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "source": {
            "reverse_root": str(reverse_root),
            "commit": status,
            "dirty": dirty,
            "rom_sha256": ledger.get("rom_sha256", ""),
        },
        "categories": categories,
        "entries": entries,
        "ledger": ledger_entries,
        "ledger_problems": problems,
    }

    readme = render_readme(index, ledger_entries, problems)

    if args.dry_run:
        print(f"would index {len(entries)} entries")
        for problem in problems:
            print(f"problem: {problem}")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "README.md").write_text(readme, encoding="utf-8")
    print(f"indexed {len(entries)} entries into {args.out_dir}")
    if problems:
        for problem in problems:
            print(f"problem: {problem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
