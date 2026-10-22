#!/usr/bin/env python3
"""Build the cross-page search index for the results viewer.

Per-page filtering stopped being useful once the viewer split into nine
documents: a query for an address or a formula only matched the page it
happened to land on.  This walks the generated pages and emits one flat index
of every section, card, note and artifact family, each tagged with the page
and anchor that owns it.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

PAGE_LABEL = {
    "reverse-engineering-results.html": "概览",
    "reverse-engineering-visuals.html": "视觉资产",
    "reverse-engineering-battle.html": "战斗系统",
    "reverse-engineering-story.html": "剧情文本",
    "reverse-engineering-data.html": "内存数据",
    "reverse-engineering-engineering.html": "工程工具",
    "reverse-engineering-formulas.html": "公式模型",
    "reverse-engineering-conclusions.html": "结论索引",
    "reverse-engineering-data-index.html": "产物族索引",
}

SECTION = re.compile(
    r'<(?:div|section)[^>]*id="(sec-[\w-]+)"[^>]*>(.*?)(?=<(?:div|section)[^>]*id="sec-|\Z)',
    re.S,
)
CARD = re.compile(r'<div class="card[^"]*" id="([\w-]+)"[^>]*>(.*?)(?=<div class="card|\Z)', re.S)
NOTE = re.compile(r'<details class="cc-note"[^>]*>(.*?)</details>', re.S)
TAG = re.compile(r"<[^>]+>")


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", fragment))).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path, default=Path("docs/assets/search-index.json")
    )
    args = parser.parse_args()
    docs = args.root.resolve() / "docs"

    entries: list[dict] = []
    for page in sorted(docs.glob("reverse-engineering-*.html")):
        page_name = page.name
        label = PAGE_LABEL.get(page_name, page.stem)
        source = page.read_text(encoding="utf-8")

        for sec_id, body in SECTION.findall(source):
            heading = re.search(r'class="card-title">([^<]+)', body)
            entries.append({
                "page": page_name,
                "anchor": sec_id,
                "title": html.unescape(heading.group(1).strip()) if heading else sec_id,
                "key": f"{label} {sec_id}",
                "text": text_of(body)[:1200],
            })

        for card_id, body in CARD.findall(source):
            if card_id.startswith("sec-"):
                continue
            heading = re.search(r'class="card-title">([^<]+)', body)
            if not heading:
                continue
            entries.append({
                "page": page_name,
                "anchor": card_id,
                "title": html.unescape(heading.group(1).strip()),
                "key": f"{label} {card_id}",
                "text": text_of(body)[:900],
            })

        for note in NOTE.findall(source):
            code = re.search(r'<code class="cc-code">([^<]+)</code>', note)
            title = re.search(r'class="cc-title">([^<]+)', note)
            if not code:
                continue
            entries.append({
                "page": page_name,
                "anchor": "sec-conclusions",
                "title": (html.unescape(title.group(1).strip())
                          if title else code.group(1)),
                "key": f"note {code.group(1)}",
                "text": text_of(note)[:700],
            })

    payload = {
        "schema": "viewer-search-index-v1",
        "entry_count": len(entries),
        "pages": sorted({e["page"] for e in entries}),
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"entries={len(entries)} pages={len(payload['pages'])} "
          f"-> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
