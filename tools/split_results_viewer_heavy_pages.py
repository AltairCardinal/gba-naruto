#!/usr/bin/env python3
"""Split the two heaviest hub pages into per-topic sub-pages.

Online load pressure comes from pages that carry everything at once:

* the conclusions page inlines every note body (515 after the reverse
  worktree's notes were mirrored in);
* the formulas page inlines 72 families' worth of runtime models.

Both are split here into small sub-pages, with the hub page reduced to an
index that links to them.  Nothing is dropped -- each note and each formula
model still exists, just on a lighter page.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HUB = "reverse-engineering-"


def split_conclusions(root: Path, out_dir: Path) -> list[str]:
    src = root / "build/viewer-data/fragment-conclusions.html"
    if not src.is_file():
        return []
    text = src.read_text(encoding="utf-8")

    head = text[: text.index('<details class="cc-note"')] if '<details class="cc-note"' in text else ""
    blocks = re.findall(
        r'<details class="cc-note"[^>]*data-hub="([\w-]+)"[^>]*>.*?</details>', text, re.S
    )
    items = re.findall(
        r'(<details class="cc-note"[^>]*data-hub="[\w-]+"[^>]*>.*?</details>)', text, re.S
    )
    by_hub: dict[str, list[str]] = {}
    for hub, item in zip(blocks, items):
        by_hub.setdefault(hub, []).append(item)

    written = []
    for hub, group in sorted(by_hub.items()):
        page = f"{HUB}conclusions-{hub}.html"
        body = "\n".join(group)
        out_dir.joinpath(page).write_text(
            make_page(root, f"逆向结论 · {hub}", body,
                      back="reverse-engineering-conclusions.html"),
            encoding="utf-8",
        )
        written.append(page)
    return written


def split_formulas(root: Path, out_dir: Path) -> list[str]:
    src = root / "build/viewer-data/fragment-formula-page.html"
    if not src.is_file():
        return []
    text = src.read_text(encoding="utf-8")
    # Split on the card boundary itself; a non-greedy match breaks on the
    # nested </div> of a card body.
    parts = re.split(r'(?=<div class="card full-width" id="fml-)', text)
    cards = []
    for part in parts:
        m = re.match(r'<div class="card full-width" id="fml-([\w-]+)">', part)
        if not m:
            continue
        family = m.group(1)
        body = part
        # Trim to the card's own end: the next split already did that, but the
        # trailing </div></div> of the card must stay.
        cards.append((body, family))
    written = []
    for markup, family in cards:
        page = f"{HUB}formulas-{family}.html"
        out_dir.joinpath(page).write_text(
            make_page(root, f"运行时模型 · {family}", markup,
                      back="reverse-engineering-formulas.html"),
            encoding="utf-8",
        )
        written.append(page)
    return written


def make_page(root: Path, title: str, body: str, back: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} · 逆向结果查看器</title>
  <link rel="stylesheet" href="assets/viewer.css">
  <link rel="stylesheet" href="assets/viewer-extra.css">
  <link rel="stylesheet" href="assets/family.css">
</head>
<body>
  <header class="top-bar">
    <div class="top-bar-left">
      <a class="brand-title" href="{back}">← 返回</a>
    </div>
  </header>
  <main class="family-page">
{body}
  </main>
  <script src="assets/viewer-runtime.js" defer></script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    out_dir = root / "docs"
    c = split_conclusions(root, out_dir)
    f = split_formulas(root, out_dir)
    print(f"conclusion sub-pages={len(c)} formula sub-pages={len(f)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
