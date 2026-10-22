#!/usr/bin/env python3
"""Package images by the viewer's own content sections.

The earlier archives were grouped by artifact-family name prefix, which does not
match how the site is organised: a reader looking at "角色动作交互工作室" wants
one archive with every character's animation, not a pile of per-family archives.

This builds the packs the way the site is actually laid out: for every card on
every hub page, collect the image files that card references and write one ZIP
named after the card.  The studio card renders its images from JavaScript, so
its list is read from the studio payload rather than from the HTML.

What you see on a card is exactly what the matching ZIP contains.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

# Allow further attributes after id (e.g. id="sec-studio" style="...").
CARD_OPEN = re.compile(r'<div class="card[^"]*" id="([^"]+)"[^>]*>')
HUB_PAGES = (
    "reverse-engineering-results.html",
    "reverse-engineering-visuals.html",
    "reverse-engineering-battle.html",
    "reverse-engineering-story.html",
    "reverse-engineering-data.html",
    "reverse-engineering-engineering.html",
)
IMAGE_SUFFIXES = (".png", ".gif", ".jpg", ".jpeg", ".webp")


# The studio card renders its own heading instead of a card-title.
CARD_TITLE_OVERRIDE = {
    "sec-studio": "角色动作交互工作室 (Character Action Studio)",
}


def card_title(body: str, card_id: str = "") -> str:
    if card_id in CARD_TITLE_OVERRIDE:
        return CARD_TITLE_OVERRIDE[card_id]
    m = re.search(r'class="card-title">([^<]*)', body)
    return m.group(1).strip() if m else ""


def split_cards(html: str) -> list[tuple[str, str]]:
    """Return (card_id, card_markup) for every card on the page."""
    marks = [(m.start(), m.group(1)) for m in CARD_OPEN.finditer(html)]
    out = []
    for i, (pos, cid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(html)
        out.append((cid, html[pos:end]))
    return out


def images_in(body: str) -> list[str]:
    """Site-relative asset paths of images referenced by this card."""
    found = []
    for m in re.finditer(
        r'(?:src|data-strip|href)="((?:\.\./)?(?:build|artifacts)/[^"]+)"', body
    ):
        path = m.group(1).replace("../", "")
        if path.lower().endswith(IMAGE_SUFFIXES):
            found.append(path)
    # Frame-sequence players list their frames in data-frames, not src.
    for m in re.finditer(r'data-frames="([^"]+)"', body):
        for frame in m.group(1).split("|"):
            path = frame.replace("../", "")
            if path.lower().endswith(IMAGE_SUFFIXES):
                found.append(path)
    return sorted(set(found))


def studio_images(root: Path) -> list[str]:
    """The studio renders from JavaScript; read its payload instead."""
    payload = root / "docs/assets/studio-data.js"
    if not payload.is_file():
        return []
    raw = payload.read_text(encoding="utf-8")
    data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    paths = set()
    for character in data.values():
        for action in character.get("actions", {}).values():
            for key in ("gif_path", "strip_path"):
                if action.get(key):
                    paths.add(action[key])
    return sorted(paths)


def write_zip(target: Path, items: list[tuple[Path, str]], root: Path) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path, arcname in items:
            zf.write(path, arcname)
    return {
        "files": len(items),
        "source_bytes": sum(p.stat().st_size for p, _ in items),
        "zip_bytes": target.stat().st_size,
    }


def slug(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text).strip("-") or "pack"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    docs = root / "docs"
    out_dir = docs / "downloads" / "sections"

    packs: list[dict] = []
    seen: set[str] = set()

    for page_name in HUB_PAGES:
        page_path = docs / page_name
        if not page_path.is_file():
            continue
        html = page_path.read_text(encoding="utf-8")
        for card_id, body in split_cards(html):
            if card_id == "sec-studio":
                rel = studio_images(root)
            else:
                rel = images_in(body)
            if not rel:
                continue
            title = card_title(body, card_id) or card_id
            items = []
            for path in rel:
                src = root / path
                if not src.is_file():
                    continue
                if path in seen:
                    continue
                seen.add(path)
                items.append((src, path))
            if not items:
                continue
            name = f"{slug(card_id)}.zip"
            info = write_zip(out_dir / name, items, root)
            info.update({"card_id": card_id, "title": title,
                         "zip": f"downloads/sections/{name}",
                         "page": page_name})
            packs.append(info)

    manifest = {
        "schema": "viewer-section-packs-v1",
        "pack_count": len(packs),
        "image_count": sum(p["files"] for p in packs),
        "packs": packs,
    }
    (root / "build/viewer-data/section-packs.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"section packs={len(packs)} images={manifest['image_count']}")
    for p in sorted(packs, key=lambda x: -x["files"]):
        print(f"  {p['files']:5d} 张  {p['zip_bytes'] / 1024:8.0f} KiB  {p['title'][:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
