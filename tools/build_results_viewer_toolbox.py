#!/usr/bin/env python3
"""Full inventory of tools/, tests/ and notes/ for the results viewer.

The toolbox card listed 8 tools while ``tools/`` holds 261; 49 of 51 analyzers
and 21 of 24 extractors were named nowhere on the site.  This enumerates the
real tree -- every script, its docstring summary, its group, and whether it is
referenced by the viewer -- so the inventory is generated, never hand-kept.

Usage:
    python3 tools/build_results_viewer_toolbox.py [--root .]
"""
from __future__ import annotations

import argparse
import ast
import glob
import html
import json
import re
from pathlib import Path

GROUPS: tuple[tuple[str, str, str], ...] = (
    ("export_", "导出器", "把 ROM 数据导出为可视产物（图像 / manifest / 内容表）"),
    ("verify_", "校验器", "独立复验导出结果，不依赖导出器本身"),
    ("analyze_", "分析器", "静态 / 运行时分析，结论写入 notes 与 JSON"),
    ("extract_", "提取器", "早期资产提取脚本，多为离线可跑"),
    ("build_", "构建器", "Butano 续作工程与产物构建"),
    ("generate_", "生成器", "由 manifest / bank 生成下游内容"),
    ("m4a_", "音频", "m4a 音频引擎链分析"),
    ("import_", "导入器", "把外部内容写回 ROM / 构建流水线"),
    ("compare_", "对比器", "原作与复刻的差分比对"),
    ("mgba", "模拟器", "无头 mGBA 录制、快照与调试"),
    ("patch_", "补丁", "ROM 补丁与变长重定向"),
    ("run_", "运行器", "构建 / 测试 / 受控执行"),
)

OTHER_LABELS = {
    "split_results_viewer": "站点拆分",
    "measure_viewer_coverage": "覆盖率测量",
    "automated_test": "自动化测试",
}


def summary_of(path: Path) -> str:
    """First meaningful sentence of the module docstring."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return ""
    doc = ast.get_docstring(tree) or ""
    for line in doc.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith(("Usage", "python3", "-")):
            return line[:150]
    return doc.strip().split("\n")[0][:150] if doc.strip() else ""


def group_of(name: str) -> tuple[str, str]:
    for prefix, label, desc in GROUPS:
        if name.startswith(prefix):
            return label, desc
    return "其它", "辅助脚本"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    site = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in sorted((root / "docs").glob("reverse-engineering-*.html"))
    )

    tools: list[dict] = []
    # The reverse-engineering worktree's tools are mirrored under
    # tools/reverse/; the inventory has to list them too, or "全量" is a
    # claim about one branch only.
    tool_paths = sorted((root / "tools").glob("*.py"))
    tool_paths += sorted((root / "tools" / "reverse").glob("*.py"))
    for path in tool_paths:
        name = path.stem
        if name == "__init__":
            continue
        label, desc = group_of(name)
        rel = path.relative_to(root / "tools").as_posix()
        tools.append({
            "name": name,
            "path": rel,
            "origin": "reverse" if rel.startswith("reverse/") else "local",
            "group": label,
            "summary": summary_of(path) or OTHER_LABELS.get(name, ""),
            "referenced_on_site": name in site,
        })

    tests = sorted(p.stem for p in (root / "tests").glob("test_*.py"))
    notes = sorted(p.stem for p in (root / "notes").glob("*.md"))
    notes += sorted(p.stem for p in (root / "notes" / "reverse").glob("*.md"))
    reverse_tools = sum(1 for t in tools if t["origin"] == "reverse")

    by_group: dict[str, list[dict]] = {}
    for tool in tools:
        by_group.setdefault(tool["group"], []).append(tool)

    rows: list[str] = []
    # Iterate the group *labels* (2nd tuple element), not the prefixes.
    for group in [label for _prefix, label, _desc in GROUPS] + ["其它"]:
        items = by_group.get(group)
        if not items:
            continue
        rows.append(
            f'                <tr><td colspan="4" style="background:#0b1120; font-weight:600;">'
            f"{html.escape(group)} · {len(items)} 个</td></tr>"
        )
        for tool in items:
            flag = (
                '<span class="tag tag-cyan">已收录</span>'
                if tool["referenced_on_site"]
                else '<span class="tag tag-purple">结论见结论索引</span>'
            )
            if tool["origin"] == "reverse":
                flag += '<span class="tag tag-amber">逆向树</span>'
            rows.append(
                f'                <tr><td><a class="cc-code" href="../tools/{html.escape(tool["path"])}" download>'
                f'<code>{html.escape(tool["path"])}</code></a></td>'
                f'<td>{html.escape(tool["summary"])}</td>'
                f"<td>{flag}</td></tr>"
            )

    card = (
        '        <div class="card full-width" id="sec-toolbox-full">\n'
        '          <div class="card-head">\n'
        '            <div class="card-title">工具全量清单 (Complete Tool Inventory)</div>\n'
        f'            <span class="tag tag-cyan">tools/ {len(tools)} 个'
        f'（含逆向树 {reverse_tools}）· '
        f'tests/ {len(tests)} 个 · notes/ {len(notes)} 篇</span>\n'
        "          </div>\n"
        '          <p class="card-desc">\n'
        "            本表由 <code>tools/build_results_viewer_toolbox.py</code> 扫描 "
        "<code>tools/</code> 实目录生成（含逆向工作树镜像的 <code>tools/reverse/</code>），\n"
        "            摘要取自各脚本的模块 docstring 首句。标注「结论见结论索引」的脚本本身不直接产出\n"
        "            图像产物，但它们分析出的结论已收录在\n"
        "            <a class=\"tag tag-cyan\" style=\"text-decoration:none;\" "
        "href=\"reverse-engineering-conclusions.html#sec-conclusions\">逆向结论索引 →</a>。\n"
        "          </p>\n"
        '          <div class="table-container" style="max-height:640px; overflow-y:auto;">\n'
        "            <table>\n"
        "              <thead><tr><th>脚本</th><th>职责摘要（docstring）</th><th>状态</th></tr></thead>\n"
        "              <tbody>\n"
        + "\n".join(rows)
        + "\n              </tbody>\n            </table>\n          </div>\n"
        f'          <p class="card-desc" style="margin-top:10px;">仓库另含 '
        f"<code>tests/ {len(tests)}</code> 个测试文件与 <code>notes/ {len(notes)}</code> 篇笔记；"
        f"笔记结论全部收录于结论索引页。</p>\n"
        "        </div>\n"
    )

    (args.output_dir / "fragment-toolbox-full.html").write_text(card, encoding="utf-8")
    (args.output_dir / "toolbox-inventory.json").write_text(
        json.dumps(
            {
                "schema": "viewer-toolbox-inventory-v1",
                "tool_count": len(tools),
                "test_count": len(tests),
                "note_count": len(notes),
                "groups": {g: len(v) for g, v in sorted(by_group.items())},
                "tools": tools,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"tools={len(tools)} tests={len(tests)} notes={len(notes)}")
    for g in sorted(by_group, key=lambda x: -len(by_group[x])):
        print(f"  {g:8s} {len(by_group[g])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
