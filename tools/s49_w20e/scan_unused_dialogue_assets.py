#!/usr/bin/env python3
"""E4 task 2: find the unreferenced scenario_41_postbattle_dialogue_* assets.

Scans the whole remake tree (source + third_party + build scripts) for any
mention of each asset stem, so "unreferenced" means "zero hits outside the
asset files themselves", not "not found in game/src".

Read-only against the shared tree; writes only its report.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

SHARED = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
REMIX = SHARED / "butano-sequel"
GRAPHICS = REMIX / "graphics"
OUT = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e4\unused-dialogue-assets.json")

TEXT_SUFFIXES = {
    ".cpp", ".h", ".hpp", ".c", ".py", ".lua", ".json", ".txt", ".md", ".cmake",
    ".mk", ".make", ".yml", ".yaml", ".toml", ".sh", ".ps1", ".cfg", ".ini",
}
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "build", "obj",
    ".cache", ".idea",
}


def iter_candidates():
    """Every file in the tree that could hold a reference (text files)."""
    for path in REMIX.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def main() -> int:
    assets = sorted(
        p for p in GRAPHICS.glob("scenario_41_postbattle_dialogue_*")
        if p.suffix in (".bmp", ".json")
    )
    stems = sorted({p.stem for p in assets})
    print(f"asset files: {len(assets)}  distinct stems: {len(stems)}")

    files = list(iter_candidates())
    print(f"scanned candidate text files: {len(files)}")

    # Cache the file contents once (they are small enough in aggregate).
    corpus = []
    for path in files:
        try:
            corpus.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue

    results = []
    for stem in stems:
        pattern = re.compile(re.escape(stem))
        hits = []
        for path, text in corpus:
            # The asset's own .json sidecar mentions its own stem; ignore those.
            if path.parent == GRAPHICS:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(
                        {
                            "file": str(path.relative_to(REMIX)).replace("\\", "/"),
                            "line": number,
                            "text": line.strip()[:160],
                        }
                    )
        results.append({"stem": stem, "reference_count": len(hits), "hits": hits})

    referenced = [r for r in results if r["reference_count"] > 0]
    unreferenced = [r for r in results if r["reference_count"] == 0]
    print(f"referenced stems   : {len(referenced)}")
    print(f"unreferenced stems : {len(unreferenced)}")
    print()
    print("REFERENCED:")
    for r in referenced:
        files_hit = sorted({h["file"] for h in r["hits"]})
        print(f"  {r['stem']:48s} {r['reference_count']:3d} hit(s)  {files_hit}")
    print()
    print("UNREFERENCED:")
    for r in unreferenced:
        print(f"  {r['stem']}")

    payload = {
        "schema": "konoha.s49-unused-dialogue-assets.v1",
        "scanned_root": str(REMIX),
        "graphics_dir": str(GRAPHICS),
        "asset_file_count": len(assets),
        "stem_count": len(stems),
        "referenced_stems": [r["stem"] for r in referenced],
        "unreferenced_stems": [r["stem"] for r in unreferenced],
        "unreferenced_files": [
            str(p.relative_to(REMIX)).replace("\\", "/")
            for stem in unreferenced
            for p in assets
            if p.stem == stem
        ],
        "reference_evidence": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print()
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
