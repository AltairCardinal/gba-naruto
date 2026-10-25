#!/usr/bin/env python3
"""Wave 24 / G4 task 3 -- re-verify the zero-reference scenario_41 post-battle
dialogue assets and their linked ROM footprint.

Re-runs E4's scan (wave 20) against the CURRENT product tree, because the
product code changed since wave 20 and the reference set may have changed.

Outputs (build/w24-g4/):
  * unused-dialogue-assets.json      -- stems, per-stem reference evidence
  * dialogue-asset-cleanup-manifest.json -- per-file size + sha256 of the
                                          files that would be deleted
  * dialogue-asset-rom-footprint.json    -- linker-measured ROM bytes

Read-only against the shared tree.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

SHARED = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
REMIX = SHARED / "butano-sequel"
GRAPHICS = REMIX / "graphics"
OUTDIR = pathlib.Path(r"D:\Github\gba-naruto\build\w24-g4")

# Linker maps to cross-check the ROM footprint (oldest E4 baseline first).
MAPS = [
    pathlib.Path(
        r"D:\Github\gba-naruto\build\w20-e4\butano-sequel\build\butano-sequel.map"
    ),
    pathlib.Path(
        r"D:\Github\gba-naruto\build\w23-f1\butano-sequel\build\butano-sequel.map"
    ),
]

TEXT_SUFFIXES = {
    ".cpp", ".h", ".hpp", ".c", ".py", ".lua", ".json", ".txt", ".md", ".cmake",
    ".mk", ".make", ".yml", ".yaml", ".toml", ".sh", ".ps1", ".cfg", ".ini",
}
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "build", "obj",
    ".cache", ".idea",
}

LINE_RE = re.compile(
    r"^\s*\.(?P<section>rodata|data|bss|text)\s+0x(?P<addr>[0-9a-f]+)\s+"
    r"0x(?P<size>[0-9a-f]+)\s+(?P<object>\S+)"
)


def iter_candidates():
    for path in REMIX.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def footprint(map_path: pathlib.Path, stems: set[str]) -> tuple[dict, int]:
    totals: dict[str, dict[str, int]] = {}
    if not map_path.is_file():
        return {}, 0
    for line in map_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = LINE_RE.match(line)
        if not match:
            continue
        obj = match.group("object")
        if "postbattle_dialogue" not in obj:
            continue
        stem = obj.split("_bn_gfx.o")[0]
        totals.setdefault(stem, {})[match.group("section")] = int(
            match.group("size"), 16
        )
    rows = []
    for stem in sorted(stems):
        sections = totals.get(stem)
        if sections is None:
            rows.append({"stem": stem, "linked": False, "bytes": 0})
            continue
        rows.append(
            {
                "stem": stem,
                "linked": True,
                "rodata_bytes": sections.get("rodata", 0),
                "data_bytes": sections.get("data", 0),
                "bss_bytes": sections.get("bss", 0),
                "bytes": sections.get("rodata", 0) + sections.get("data", 0),
            }
        )
    return rows, sum(row["bytes"] for row in rows)


def main() -> int:
    assets = sorted(
        p for p in GRAPHICS.glob("scenario_41_postbattle_dialogue_*")
        if p.suffix in (".bmp", ".json")
    )
    stems = sorted({p.stem for p in assets})
    print(f"asset files: {len(assets)}  distinct stems: {len(stems)}")

    files = list(iter_candidates())
    print(f"scanned candidate text files: {len(files)}")

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
    for r in referenced:
        print(f"  REF {r['stem']:48s} {r['reference_count']:3d} hit(s) "
              f"{sorted({h['file'] for h in r['hits']})}")
    for r in unreferenced:
        print(f"  UNREF {r['stem']}")

    unused_stems = {r["stem"] for r in unreferenced}
    ref_stems = {r["stem"] for r in referenced}

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "unused-dialogue-assets.json").write_text(
        json.dumps(
            {
                "schema": "konoha.s49-unused-dialogue-assets.v1",
                "scanned_root": str(REMIX),
                "graphics_dir": str(GRAPHICS),
                "asset_file_count": len(assets),
                "stem_count": len(stems),
                "referenced_stems": sorted(ref_stems),
                "unreferenced_stems": sorted(unused_stems),
                "reference_evidence": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_files = []
    for stem in sorted(unused_stems):
        for path in assets:
            if path.stem == stem:
                manifest_files.append(
                    {
                        "path": str(path.relative_to(REMIX)).replace("\\", "/"),
                        "abs_path": str(path),
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )
    (OUTDIR / "dialogue-asset-cleanup-manifest.json").write_text(
        json.dumps(
            {
                "schema": "konoha.s49-dialogue-asset-cleanup-manifest.v1",
                "graphics_dir": str(GRAPHICS),
                "file_count": len(manifest_files),
                "total_bytes_on_disk": sum(f["bytes"] for f in manifest_files),
                "files": manifest_files,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    footprint_payload = {
        "schema": "konoha.s49-dialogue-asset-rom-footprint.v1",
        "maps": {},
    }
    for map_path in MAPS:
        rows, total = footprint(map_path, unused_stems)
        ref_rows, ref_total = footprint(map_path, ref_stems)
        footprint_payload["maps"][str(map_path)] = {
            "map_exists": map_path.is_file(),
            "unreferenced_assets_linked": sum(1 for r in rows if r["linked"]),
            "unreferenced_stem_count": len(rows),
            "unreferenced_rom_bytes": total,
            "referenced_rom_bytes": ref_total,
            "unreferenced": rows,
        }
        print(f"map {map_path.name}: linked "
              f"{sum(1 for r in rows if r['linked'])}/{len(rows)} "
              f"rom_bytes={total} (referenced={ref_total})")
    (OUTDIR / "dialogue-asset-rom-footprint.json").write_text(
        json.dumps(footprint_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"manifest files: {len(manifest_files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
