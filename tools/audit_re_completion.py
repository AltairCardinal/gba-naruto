#!/usr/bin/env python3
"""Audit reverse-engineering bank metadata and documentation coverage.

This deliberately does not claim that a bank's runtime semantics or write-back
path are correct.  It checks only durable metadata: table offsets, format
descriptions, entries, verification labels, and references in Markdown notes.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORMAT_FIELDS = (
    "format",
    "entry_format",
    "chapter_data_format",
    "data_format",
    "palette_format",
    "animation_frame_format",
    "audio_table",
)
VALID_VERIFICATION = {"static_verified", "code_verified", "runtime_verified"}


def nonempty(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def load_documents(root: Path, excluded: set[Path]) -> dict[Path, str]:
    documents: dict[Path, str] = {}
    for directory in (root / "docs", root / "notes"):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.resolve() not in excluded:
                documents[path] = path.read_text(encoding="utf-8", errors="replace")
    return documents


def documentation_matches(
    root: Path, bank: Path, data: dict[str, Any], documents: dict[Path, str]
) -> list[str]:
    slug = bank.parent.name
    offset = data.get("table_offset")
    tokens = {slug, str(bank.relative_to(root))}
    if isinstance(offset, int):
        tokens.update({f"0x{offset:X}", f"0x{offset:x}"})
    offset_hex = data.get("table_offset_hex")
    if isinstance(offset_hex, str) and offset_hex:
        tokens.update({offset_hex, offset_hex.lower(), offset_hex.upper()})

    matches = []
    for path, text in documents.items():
        lower = text.lower()
        if any(token.lower() in lower for token in tokens if token):
            matches.append(str(path.relative_to(root)))
    return matches


def audit_bank(
    root: Path, bank: Path, documents: dict[Path, str], rom: bytes | None
) -> dict[str, Any]:
    rel = str(bank.relative_to(root))
    try:
        data = json.loads(bank.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "bank": rel,
            "structure": bank.parent.name,
            "load_error": str(exc),
            "checks": {name: False for name in ("table_offset", "format", "entries", "verification", "documentation")},
            "complete": False,
        }

    offset = data.get("table_offset")
    offset_ok = isinstance(offset, int) and offset >= 0
    offset_hex = data.get("table_offset_hex")
    hex_ok = not nonempty(offset_hex)
    if offset_ok and isinstance(offset_hex, str):
        try:
            hex_ok = int(offset_hex, 16) == offset
        except ValueError:
            hex_ok = False

    format_fields = [field for field in FORMAT_FIELDS if nonempty(data.get(field))]
    entries = data.get("entries")
    entries_ok = isinstance(entries, list) and len(entries) > 0
    declared_count = data.get("entry_count")
    count_ok = declared_count is None or (
        isinstance(declared_count, int) and isinstance(entries, list) and declared_count == len(entries)
    )

    verification = data.get("verification")
    verification_ok = verification in VALID_VERIFICATION
    docs = documentation_matches(root, bank, data, documents)
    fidelity_checked = 0
    fidelity_errors: list[str] = []
    entry_size = data.get("entry_size")
    entry_format = data.get("entry_format")
    fields = entry_format.get("fields", []) if isinstance(entry_format, dict) else []
    if rom is not None and offset_ok and isinstance(entry_size, int) and entry_size > 0 and isinstance(entries, list):
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                fidelity_errors.append(f"entry {index} is not an object")
                continue
            expected_offset = offset + index * entry_size
            raw_offset = entry.get("_raw_offset", entry.get("offset"))
            if isinstance(raw_offset, int) and raw_offset != expected_offset:
                fidelity_errors.append(
                    f"entry {index} offset 0x{raw_offset:X} != expected 0x{expected_offset:X}"
                )
            for field in fields:
                if not isinstance(field, dict):
                    continue
                name, field_offset, size = field.get("name"), field.get("offset"), field.get("size")
                hex_value = entry.get(f"{name}_hex") if isinstance(name, str) else None
                if not (isinstance(field_offset, int) and isinstance(size, int) and isinstance(hex_value, str)):
                    continue
                start = expected_offset + field_offset
                expected_hex = rom[start:start + size].hex()
                fidelity_checked += 1
                if hex_value.lower() != expected_hex:
                    fidelity_errors.append(
                        f"entry {index}.{name}={hex_value} != base ROM {expected_hex} at 0x{start:X}"
                    )
    fidelity_ok = fidelity_checked > 0 and not fidelity_errors
    checks = {
        "table_offset": offset_ok and hex_ok,
        "format": bool(format_fields),
        "entries": entries_ok and count_ok,
        "verification": verification_ok,
        "documentation": bool(docs),
        "rom_fidelity": fidelity_ok,
    }

    issues = []
    if not offset_ok:
        issues.append("table_offset is missing or is not a non-negative integer")
    elif not hex_ok:
        issues.append("table_offset_hex does not match table_offset")
    if not format_fields:
        issues.append("no non-empty recognized format field")
    if not entries_ok:
        issues.append("entries is missing, not an array, or empty")
    elif not count_ok:
        issues.append(f"entry_count={declared_count} but entries has {len(entries)} records")
    if not verification_ok:
        issues.append(f"verification={verification!r} is missing or unrecognized")
    if not docs:
        issues.append("no docs/*.md or notes/*.md reference to slug, bank path, or table offset")
    if not fidelity_ok:
        if fidelity_errors:
            issues.append(f"ROM fidelity failed: {fidelity_errors[0]}")
        else:
            issues.append("ROM fidelity not checkable from entry_format and extracted field hex")

    return {
        "bank": rel,
        "structure": bank.parent.name,
        "table_offset": offset,
        "table_offset_hex": offset_hex,
        "format_fields": format_fields,
        "entry_count_declared": declared_count,
        "entry_count_actual": len(entries) if isinstance(entries, list) else None,
        "verification": verification,
        "verification_method_present": nonempty(data.get("verification_method")),
        "documentation": docs,
        "rom_fidelity_fields_checked": fidelity_checked,
        "rom_fidelity_errors": fidelity_errors,
        "checks": checks,
        "issues": issues,
        "complete": all(checks.values()),
    }


def build_report(root: Path, output_md: Path, rom_path: Path | None = None) -> dict[str, Any]:
    banks = sorted((root / "sequel" / "content").glob("*/bank.json"))
    documents = load_documents(root, {output_md.resolve()})
    rom = rom_path.read_bytes() if rom_path is not None and rom_path.exists() else None
    results = [audit_bank(root, bank, documents, rom) for bank in banks]
    check_names = ("table_offset", "format", "entries", "verification", "documentation", "rom_fidelity")
    summary = {
        "banks_found": len(results),
        "expected_banks": 32,
        "all_expected_banks_found": len(results) == 32,
        "fully_satisfying_metadata_scope": sum(item["complete"] for item in results),
        "checks_passing": {
            name: sum(item["checks"][name] for item in results) for name in check_names
        },
        "verification_distribution": {},
    }
    for item in results:
        label = item.get("verification") or "missing"
        summary["verification_distribution"][label] = summary["verification_distribution"].get(label, 0) + 1
    return {
        "scope": "bank metadata/entries/verification/documentation and base-ROM byte fidelity; no runtime or write-back validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "banks": results,
    }


def markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 逆向工程 Bank 完成度审计",
        "",
        f"生成时间：`{report['generated_at']}`",
        "",
        f"范围：{report['scope']}。因此本报告不能证明运行时语义或实际回写闭环。",
        "",
        "## 汇总",
        "",
        f"- 发现 `{summary['banks_found']}` / 预期 `{summary['expected_banks']}` 个 bank。",
        f"- 同时满足六项元数据与字节检查：`{summary['fully_satisfying_metadata_scope']}` / `{summary['banks_found']}`。",
    ]
    for name, count in summary["checks_passing"].items():
        lines.append(f"- `{name}`：`{count}` / `{summary['banks_found']}`。")
    distribution = ", ".join(f"`{key}`={value}" for key, value in sorted(summary["verification_distribution"].items()))
    lines.extend([f"- verification 分布：{distribution}。", "", "## 逐结构结果", ""])
    lines.append("| 结构 | table_offset | format | entries | verification | 文档覆盖 | ROM字节 | 完整 | 问题 |")
    lines.append("|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|---|")
    mark = lambda value: "✅" if value else "❌"
    for item in report["banks"]:
        checks = item["checks"]
        offset = item.get("table_offset_hex") or item.get("table_offset") or "—"
        issues = "; ".join(item.get("issues", [])) or "—"
        lines.append(
            f"| `{item['structure']}` | {mark(checks['table_offset'])} `{offset}` | {mark(checks['format'])} | "
            f"{mark(checks['entries'])} ({item.get('entry_count_actual', '—')}) | "
            f"{mark(checks['verification'])} `{item.get('verification')}` | "
            f"{mark(checks['documentation'])} ({len(item.get('documentation', []))}) | "
            f"{mark(checks['rom_fidelity'])} ({item.get('rom_fidelity_fields_checked', 0)}) | "
            f"{mark(item['complete'])} | {issues} |"
        )
    lines.extend(["", "## 判定规则", ""])
    lines.extend([
        "- `table_offset`：必须为非负整数；若有 `table_offset_hex`，两者必须一致。",
        "- `format`：`format`、`entry_format` 或已知领域格式字段至少一个非空。",
        "- `entries`：必须是非空数组；若声明 `entry_count`，必须与实际数量一致。",
        "- `verification`：必须是 `static_verified`、`code_verified` 或 `runtime_verified`。",
        "- 文档覆盖：`docs/*.md` 或 `notes/*.md` 至少一处提到结构目录名、bank 路径或表偏移。",
        "- `rom_fidelity`：已提取字段的 `*_hex` 必须与校验过的基准 ROM 对应字节一致。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", type=Path, default=Path("notes/re-completion-audit.json"))
    parser.add_argument("--markdown", type=Path, default=Path("notes/re-completion-audit.md"))
    parser.add_argument("--rom", type=Path, help="base ROM used for byte-fidelity checks")
    args = parser.parse_args()
    root = args.root.resolve()
    output_json = args.json if args.json.is_absolute() else root / args.json
    output_md = args.markdown if args.markdown.is_absolute() else root / args.markdown
    rom_path = args.rom
    if rom_path is None:
        project = json.loads((root / "sequel/project.json").read_text(encoding="utf-8"))
        rom_path = root / project["base_rom"]["path"]
    elif not rom_path.is_absolute():
        rom_path = root / rom_path
    report = build_report(root, output_md, rom_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["all_expected_banks_found"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
