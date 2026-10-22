#!/usr/bin/env python3
"""Catalog the rom-* reverse-engineering families that live on the reverse branch.

Most of the completed ROM reverse engineering (55 of 85 family stems) has its
artifacts and evidence notes on the reverse branch, not in this worktree, so it
cannot be rendered.  What *can* be done honestly is publish an index: every
family the repo references, whether it exists here, and where it lives.

This tool never guesses what a family contains.  For each stem it records only
facts it can verify locally: the artifact path exists or not, whether a local
evidence note mentions it, and the version batch count.  Anything unknown is
rendered as "内容在逆向分支" rather than invented.

Usage:
    python3 tools/build_results_viewer_rom_catalog.py [--root .]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from measure_viewer_coverage import (  # noqa: E402
    census_repo_families, family_stem, is_remake_evidence,
)


def local_evidence_notes(root: Path) -> dict[str, list[str]]:
    """Map stem -> note filenames in THIS worktree that mention the artifact."""
    hits: dict[str, list[str]] = {}
    for path in sorted((root / "notes").rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name in set(re.findall(r"artifacts/([A-Za-z0-9][\w.\-]+)", text)):
            stem = family_stem(name)
            hits.setdefault(stem, [])
            rel = str(path.relative_to(root))
            if rel not in hits[stem]:
                hits[stem].append(rel)
    return hits


def artifact_present(root: Path, stem: str) -> bool:
    for candidate in (root / "artifacts", root / "notes"):
        if any(candidate.rglob(stem + "-v*")):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    discovered = census_repo_families(root)
    rom_names = sorted(n for n in discovered if not is_remake_evidence(n))
    notes = local_evidence_notes(root)

    entries: dict[str, list[str]] = {}
    for name in rom_names:
        entries.setdefault(family_stem(name), []).append(name)

    rows: list[dict] = []
    for stem in sorted(entries):
        versions = sorted(entries[stem])
        present = artifact_present(root, stem)
        evidence = [
            n for n in notes.get(stem, [])
            if "source-snapshots" not in n
        ]
        rows.append({
            "stem": stem,
            "versions": versions,
            "version_count": len(versions),
            "artifact_present_here": present,
            "local_notes": evidence[:3],
        })

    payload = {
        "schema": "rom-family-catalog-v1",
        "family_stem_count": len(rows),
        "present_here": sum(1 for r in rows if r["artifact_present_here"]),
        "on_reverse_branch": sum(1 for r in rows if not r["artifact_present_here"]),
        "families": rows,
    }
    out = args.output_dir / "rom-family-catalog.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    trs = []
    for r in rows:
        badge = (
            '<span class="tag tag-green">本工作树有产物</span>'
            if r["artifact_present_here"]
            else '<span class="tag tag-amber">内容在逆向分支</span>'
        )
        note_links = "、".join(
            f'<code>{n.split("/")[-1]}</code>' for n in r["local_notes"]
        ) or '<span style="color:var(--text-muted);">—</span>'
        trs.append(
            f'                <tr><td><code>{r["stem"]}</code></td>'
            f'<td><code>{r["version_count"]}</code></td>'
            f"<td>{badge}</td>"
            f"<td>{note_links}</td></tr>"
        )

    fragment = (
        '                <tr><td colspan="4" style="background:#0b1120; font-weight:600;">'
        f'共 {len(rows)} 个 rom-* 成果族：本工作树有产物 {payload["present_here"]}，'
        f'内容在逆向分支 {payload["on_reverse_branch"]}</td></tr>\n'
        + "\n".join(trs)
    )
    card = f'''        <div class="card full-width" id="sec-rom-catalog">
          <div class="card-head">
            <div class="card-title">ROM 逆向成果族全量目录 (ROM Family Catalog)</div>
            <span class="tag tag-amber">{payload["family_stem_count"]} 个家族 · 本工作树有产物 {payload["present_here"]} · 内容在逆向分支 {payload["on_reverse_branch"]}</span>
          </div>
          <p class="card-desc">
            由 <code>tools/build_results_viewer_rom_catalog.py</code> 全仓库普查生成，逐族列出仓库引用过的
            <code>artifacts/&lt;family&gt;</code> 成果族、其增量版本批次数，以及在本工作树是否实际存在产物。
            <strong>本表只记录可本地验证的事实</strong>：不推测每个族闭合了什么内容。
            标为「内容在逆向分支」的族，其产物与证据 notes 完整存在于逆向分支的 <code>artifacts/</code> 中，
            但<strong>无法在本工作树重建或渲染</strong>，因此本页只列目录、不展示其内容。
          </p>
          <div class="table-container" style="max-height:560px; overflow-y:auto;">
            <table>
              <thead><tr><th>成果族主干</th><th>版本批次</th><th>产物位置</th><th>本工作树证据 notes</th></tr></thead>
              <tbody>
{fragment}
              </tbody>
            </table>
          </div>
        </div>
'''
    frag_path = args.output_dir / "fragment-rom-catalog-card.html"
    frag_path.write_text(card + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print(f"wrote {frag_path}")
    print(f"stems={len(rows)} present={payload['present_here']} "
          f"reverse_branch={payload['on_reverse_branch']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
