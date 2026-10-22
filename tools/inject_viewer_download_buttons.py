#!/usr/bin/env python3
"""Put a per-card download button in every card that has a section pack.

The packs already exist, but the only way to reach them was a long list on the
overview page.  A reader standing in front of a card wants to take that card's
images with them, so every card that owns images gets its own button in its
card header, next to the existing tag.

The button is inserted into the card-head by depth-aware scanning (a card head
contains a nested title div, so a naive ``</div>`` match would cut in the wrong
place), and the page is left untouched when the card has no pack.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HUB_PAGES = (
    "reverse-engineering-results.html",
    "reverse-engineering-visuals.html",
    "reverse-engineering-battle.html",
    "reverse-engineering-story.html",
    "reverse-engineering-data.html",
    "reverse-engineering-engineering.html",
)
CARD_OPEN = re.compile(r'<div class="card[^"]*" id="([^"]+)"[^>]*>')


def find_head_end(html: str, start: int) -> int:
    """Index just past the closing tag of the card-head div starting at ``start``."""
    depth = 0
    i = start
    while i < len(html):
        nxt_open = html.find("<div", i)
        nxt_close = html.find("</div>", i)
        if nxt_close == -1:
            return -1
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
            continue
        depth -= 1
        i = nxt_close + 6
        if depth == 0:
            return i
    return -1


def button_html(pack: dict) -> str:
    """Orange 3D button: a full-height download icon beside two-line text."""
    zip_name = Path(pack["zip"]).name
    return (
        f'\n          <a class="card-dl" href="downloads/sections/{zip_name}" download '
        f'title="下载本板块全部 {pack["files"]:,} 张图像（ZIP）">'
        f'<svg class="card-dl-icon" viewBox="0 0 24 24" aria-hidden="true">'
        f'<path d="M12 3v10m0 0 4.2-4.2M12 13l-4.2-4.2" fill="none" stroke="currentColor" '
        f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M4 16.5v1.8A2.7 2.7 0 0 0 6.7 21h10.6A2.7 2.7 0 0 0 20 18.3v-1.8" fill="none" '
        f'stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>'
        f'<span class="card-dl-text">'
        f'<span class="card-dl-main">下载本板块</span>'
        f'<span class="card-dl-sub">{pack["files"]:,} 张图像</span>'
        f'</span>'
        f'</a>'
    )


def inject(root: Path) -> int:
    """Add a download button to every card that owns a section pack."""
    docs = root / "docs"
    packs_path = root / "build/viewer-data/section-packs.json"
    if not packs_path.is_file():
        raise SystemExit("run tools/build_results_viewer_section_packs.py first")
    packs = {
        p["card_id"]: p
        for p in json.loads(packs_path.read_text(encoding="utf-8"))["packs"]
    }

    added = 0
    for page_name in HUB_PAGES:
        page_path = docs / page_name
        if not page_path.is_file():
            continue
        html = page_path.read_text(encoding="utf-8")
        original = html
        for match in list(CARD_OPEN.finditer(html))[::-1]:
            card_id = match.group(1)
            pack = packs.get(card_id)
            if not pack:
                continue
            head_start = html.find('<div class="card-head">', match.end())
            if head_start == -1:
                continue
            head_end = find_head_end(html, head_start)
            if head_end == -1:
                continue
            if "card-dl" in html[head_start:head_end]:
                continue
            html = html[:head_end - len("</div>")] + button_html(pack) + "\n        </div>" + html[head_end:]
            added += 1
        if html != original:
            page_path.write_text(html, encoding="utf-8")
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    added = inject(root)
    print(f"download buttons injected: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
