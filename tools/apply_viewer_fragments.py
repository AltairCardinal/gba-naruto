#!/usr/bin/env python3
"""Apply generated fragments into the split pages, idempotently and safely.

``tools/build_results_viewer_artifact_sections.py`` emits standalone markup
blocks; this tool splices each block into the page that owns it, replacing the
existing card in place.

Two failure modes this exists to prevent:

1. **Crossing a card-grid / section boundary.**  Searching for "the next
   ``<div class="card``" can jump past ``</section>`` into the *next* hub and
   silently delete a section.  The scan stops at the enclosing ``</section>``.
2. **Non-idempotent splicing.**  Re-running would append a second copy.  Each
   fragment is keyed by the card id it owns, so a second run replaces it.

Usage:
    python3 tools/apply_viewer_fragments.py [--root .]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

# fragment file -> (page file, card id the fragment owns)
FRAGMENTS: dict[str, tuple[str, str]] = {
    "fragment-map-canvases.html": ("reverse-engineering-visuals.html", "sec-map-canvases"),
    "fragment-character-battle-visuals.html": (
        "reverse-engineering-visuals.html", "sec-character-battle-visuals",
    ),
    "fragment-bg-canvases.html": ("reverse-engineering-visuals.html", "sec-bg-canvases"),
    "fragment-scene-visual-packs.html": (
        "reverse-engineering-visuals.html", "sec-scene-visual-packs",
    ),
    "fragment-bg-scene-selection.html": (
        "reverse-engineering-visuals.html", "sec-bg-scene-selection",
    ),
    "fragment-battle-effect-pairs.html": (
        "reverse-engineering-battle.html", "sec-battle-effect-pairs",
    ),
    "fragment-battle-effect-anims.html": (
        "reverse-engineering-battle.html", "sec-battle-effect-anims",
    ),
    "fragment-battle-effect-sequences.html": (
        "reverse-engineering-battle.html", "sec-battle-effect-sequences",
    ),
    "fragment-battle-glyphs.html": ("reverse-engineering-story.html", "sec-battle-glyphs"),
    "fragment-sprite-definitions.html": ("reverse-engineering-data.html", "sec-sprite-definitions"),
}

CARD_OPEN = re.compile(r'<div class="card(?: full-width)?" id="')


def card_bounds(html: str, card_id: str) -> tuple[int, int] | None:
    """Return (start, end) of the card owning ``card_id``, never crossing
    the enclosing ``</section>``."""
    try:
        anchor = html.index(f'id="{card_id}"')
    except ValueError:
        return None
    start = html.rfind('<div class="card', 0, anchor)
    if start == -1:
        return None
    section_end = html.rfind("</section>", 0, anchor)
    limit = section_end if section_end != -1 else len(html)
    after = html.index(">", anchor) + 1
    nxt = CARD_OPEN.search(html, after)
    end = nxt.start() if (nxt and nxt.start() < limit) else limit
    return start, end


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--fragments", type=Path, default=Path("build/viewer-data")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    docs = root / "docs"

    applied = skipped = 0
    for name, (page_file, card_id) in FRAGMENTS.items():
        fragment_path = args.fragments / name
        page_path = docs / page_file
        if not fragment_path.is_file() or not page_path.is_file():
            skipped += 1
            continue
        fragment = fragment_path.read_text(encoding="utf-8").rstrip("\n")
        if card_id not in fragment:
            skipped += 1
            continue
        html = page_path.read_text(encoding="utf-8")
        bounds = card_bounds(html, card_id)
        if bounds is None:
            print(f"  ! {page_file}: card {card_id} not found")
            skipped += 1
            continue
        start, end = bounds
        if html[start:end].strip() == fragment.strip():
            continue  # already in sync
        page_path.write_text(
            html[:start] + fragment + "\n" + html[end:], encoding="utf-8"
        )
        applied += 1
        print(f"  applied {name} -> {page_file} [{card_id}]")

    print(f"applied={applied} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
