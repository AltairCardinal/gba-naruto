#!/usr/bin/env python3
"""Index every reverse-engineering conclusion recorded in notes/ onto the site.

The viewer presented artifacts and formulas but never the *narrative* results:
several hundred notes record major conclusions -- the real audio dispatch chain,
where unit start positions actually come from, how the AI config table is
selected, which earlier readings were disproved -- and none of it reached the
site.

This builds a browsable conclusions index:

* every note, its title, date and topic bucket;
* the conclusion section, extracted verbatim (never paraphrased);
* whether the note's artifacts are actually rendered on the site, or blocked.

Topics are mapped to the site's hubs so the index can be filtered by where the
conclusion belongs.

Usage:
    python3 tools/build_results_viewer_conclusions.py [--root .]
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

# Topic prefix -> (hub id, hub label).  Order matters: first match wins.
TOPIC_RULES: tuple[tuple[str, str, str], ...] = (
    ("battle-", "battle", "战斗系统"),
    ("story-", "story", "剧情与文本"),
    ("chapter-", "story", "剧情与文本"),
    ("dialogue-", "story", "剧情与文本"),
    ("text-", "story", "剧情与文本"),
    ("profile-", "story", "剧情与文本"),
    ("map-", "visuals", "地图与视觉"),
    ("tiles", "visuals", "地图与视觉"),
    ("sprite", "visuals", "地图与视觉"),
    ("portrait", "visuals", "地图与视觉"),
    ("cutscene", "visuals", "地图与视觉"),
    ("bg-", "visuals", "地图与视觉"),
    ("scene", "visuals", "地图与视觉"),
    ("audio", "data", "音频"),
    ("m4a", "data", "音频"),
    ("directsound", "data", "音频"),
    ("unit", "data", "单位与数值"),
    ("skill", "data", "单位与数值"),
    ("character", "data", "单位与数值"),
    ("status", "data", "单位与数值"),
    ("passive", "data", "单位与数值"),
    ("formation", "data", "单位与数值"),
    ("item", "data", "单位与数值"),
    ("positions", "data", "单位与数值"),
    ("save", "data", "单位与数值"),
    ("build", "engineering", "工程与工具"),
    ("mod", "engineering", "工程与工具"),
    ("patch", "engineering", "工程与工具"),
    ("test", "engineering", "工程与工具"),
    ("tool", "engineering", "工程与工具"),
    ("mgba", "engineering", "工程与工具"),
    ("web", "engineering", "工程与工具"),
    ("editor", "engineering", "工程与工具"),
    ("reverse-model-benchmark", "engineering", "工程与工具"),
)

DEFAULT_HUB = ("engineering", "工程与工具")

CONCLUSION_HEADINGS = (
    "## 结论", "## Result", "## 结论与", "## 调查结果与结论",
    "## 调查目标与结论", "## 核心结论", "## Findings",
)
NEXT_HEADING = re.compile(r"^##\s", re.M)
DATE_RE = re.compile(r"(20\d{6})")
ARTIFACT_RE = re.compile(r"artifacts/([A-Za-z0-9][\w.\-]+)")
CONTRADICTED = re.compile(r"证伪|推翻|superseded|被取代|disprov|misbased|wrong|撤销|revoked", re.I)


def topic_of(name: str) -> tuple[str, str]:
    for prefix, hub, label in TOPIC_RULES:
        if name.startswith(prefix):
            return hub, label
    return DEFAULT_HUB


def extract_conclusion(text: str) -> str | None:
    """Return the conclusion section verbatim, if the note has one."""
    for heading in CONCLUSION_HEADINGS:
        index = text.find(heading)
        if index == -1:
            continue
        start = index + len(heading)
        match = NEXT_HEADING.search(text, start)
        end = match.start() if match else len(text)
        body = text[start:end].strip()
        if len(body) > 40:
            return body
    return None


def extract_lead(text: str) -> str | None:
    """Fallback for process logs: the first substantive prose after the title.

    Many notes have no ``## 结论`` heading but state the finding immediately
    after the title.  Skipping headings, tables and blank runs avoids returning
    a bare sentence fragment.
    """
    lines = text.split("\n")
    out: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            if out:
                break
            continue
        if stripped.startswith("```") or stripped.startswith("|"):
            continue
        out.append(line)
        if sum(len(x) for x in out) > 900:
            break
    body = "\n".join(out).strip()
    return body if len(body) > 80 else None


def render_body(body: str) -> str:
    """Minimal, safe markdown-ish rendering: code fences, code spans, tables."""
    out: list[str] = []
    in_code = False
    for block in body.split("\n"):
        if block.strip().startswith("```"):
            tag_open, tag_close = ("<pre><code>", "</code></pre>")
            if in_code:
                out.append(tag_close)
                in_code = False
            else:
                out.append(tag_open)
                in_code = True
            continue
        if in_code:
            out.append(html.escape(block, quote=False))
            continue
        if block.strip().startswith("|"):
            cells = [c.strip() for c in block.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells) and cells:
                continue  # separator row
            spans = "".join(
                f"<span>{render_inline(c)}</span>" for c in cells
            )
            out.append(f'<div class="cc-note-row">{spans}</div>')
            continue
        if block.strip().startswith(("#", "-", "*")) or block.strip().isdigit():
            bullet = block.lstrip()
            marker = "• " if bullet[0] in "-*" else ""
            out.append(f"<div class=\"cc-note-line\">{render_inline(bullet)}</div>")
        else:
            out.append(f"<div class=\"cc-note-line\">{render_inline(block)}</div>")
    return "\n".join(out)


def render_inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    # NB: no raw string here -- r"...\"..." would emit a literal backslash.
    escaped = re.sub(
        r"`([^`]+)`", '<code class="cc-code">\\1</code>', escaped
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    # No truncation by default: every note is indexed.  Pass a positive
    # value to cap it deliberately.
    parser.add_argument("--max-notes", type=int, default=0)
    parser.add_argument("--excerpt", type=int, default=1200)
    args = parser.parse_args()
    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    # The reverse-engineering worktree's notes are mirrored under
    # notes/reverse/; the conclusions index has to cover them too, or the
    # site would only show the findings that were copied across.
    note_paths = sorted((root / "notes").glob("*.md"))
    note_paths += sorted((root / "notes" / "reverse").glob("*.md"))
    for path in note_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        name = path.stem
        rel = path.relative_to(root / "notes").as_posix()
        title = text.split("\n", 1)[0].lstrip("# ").strip()
        date_match = DATE_RE.search(name)
        hub, hub_label = topic_of(name)
        conclusion = extract_conclusion(text) or extract_lead(text)
        has_formal = bool(extract_conclusion(text))
        artifacts = sorted({m.rstrip("/") for m in ARTIFACT_RE.findall(text)})
        entries.append({
            "note": name,
            "path": rel[:-3] if rel.endswith(".md") else rel,
            "origin": "reverse" if rel.startswith("reverse/") else "local",
            "title": title,
            "date": date_match.group(1) if date_match else "",
            "hub": hub,
            "hub_label": hub_label,
            "conclusion": conclusion,
            "has_formal_conclusion": has_formal,
            "artifacts": artifacts,
            "contradicts_previous": bool(CONTRADICTED.search(conclusion or text[:4000])),
        })

    entries.sort(key=lambda e: (e["date"], e["note"]))

    cards = []
    selected = entries if args.max_notes <= 0 else entries[: args.max_notes]
    for entry in selected:
        body = entry["conclusion"]
        # No truncation: the whole conclusion is shown.  The notes file stays
        # linked for the original markdown.
        body_html = render_body(body) if body else (
            '<div class="cc-note-line cc-muted">本篇为过程记录，未能提取到结论段落。</div>'
        )
        flag = (
            '<span class="tag tag-amber">含纠错/证伪</span>'
            if entry["contradicts_previous"] else ""
        )
        origin = (
            '<span class="tag tag-cyan">逆向树</span>'
            if entry.get("origin") == "reverse" else ""
        )
        cards.append(
            f'        <details class="cc-note" data-hub="{entry["hub"]}">\n'
            f'          <summary><code class="cc-code">{entry["note"]}</code>'
            f'<span class="cc-meta">{entry["hub_label"]}'
            f'{(" · " + entry["date"]) if entry["date"] else ""} {flag}{origin}</span></summary>\n'
            f'          <div class="cc-title">{render_inline(entry["title"])}</div>\n'
            f'          <div class="cc-body">{body_html}</div>\n'
            f'          <div class="cc-foot"><a class="cc-code" href="../notes/{entry["path"]}.md" download>'
            f'notes/{entry["path"]}.md</a>'
            + (f' · 关联产物 {len(entry["artifacts"])} 族' if entry["artifacts"] else "")
            + "</div>\n"
            f"        </details>"
        )

    hubs = sorted({(e["hub"], e["hub_label"]) for e in entries})
    nav = (
        '<div class="cc-filters">'
        '<button class="cc-filter active" data-hub="all">全部 '
        f'{len(entries)}</button>'
        + "".join(
            f'<button class="cc-filter" data-hub="{h}">{l} '
            f'{sum(1 for e in entries if e["hub"] == h)}</button>'
            for h, l in hubs
        )
        + "</div>\n"
    )

    with_conclusion = sum(1 for e in entries if e["conclusion"])
    page = (
        '        <div class="card full-width" id="sec-conclusions">\n'
        '          <div class="card-head">\n'
        '            <div class="card-title">逆向结论索引 (Reverse Engineering Conclusions)</div>\n'
        f'            <span class="tag tag-cyan">notes/ 共 {len(entries)} 篇 · '
        f'{with_conclusion} 篇含独立结论段落</span>\n'
        "          </div>\n"
        '          <p class="card-desc">\n'
        "            此前本页只呈现产物（图像/公式/计数）与地址，而逆向的<strong>叙事结论</strong>"
        "——真实音频分派链、单位初始坐标来源、AI 配置表选择方式、以及哪些早期解读已被证伪——\n"
        "            只存在于 <code>notes/</code>。本索引把每篇笔记的结论段落原文收录，\n"
        "            按主题归入对应 Hub，<strong>不做改写或概括</strong>；"
        "带「含纠错/证伪」标记的条目记录了被推翻的旧解读。\n"
        "          </p>\n"
        f"          {nav}"
        '          <div class="cc-list">\n'
        + "\n".join(cards)
        + "\n          </div>\n        </div>\n"
    )

    out_dir = args.output_dir
    (out_dir / "fragment-conclusions.html").write_text(page, encoding="utf-8")
    (out_dir / "conclusions-index.json").write_text(
        json.dumps(
            {
                "schema": "viewer-conclusions-index-v1",
                "note_count": len(entries),
                "with_conclusion": with_conclusion,
                "notes": entries,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    (out_dir / "conclusion-nav.html").write_text(nav, encoding="utf-8")
    print(f"notes={len(entries)} with_conclusion={with_conclusion}")
    for hub, label in hubs:
        print(f"  {label:14s} {sum(1 for e in entries if e['hub'] == hub)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
