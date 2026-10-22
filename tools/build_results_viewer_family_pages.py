#!/usr/bin/env python3
"""Generate one full sub-page per artifact family.

The viewer used to summarise each family in a card, which meant 99.4% of the
manifest fields were never shown.  Truncation is not presentation, so every
family now gets its own page tree that renders the **complete** manifest:

* every top-level key becomes a section with its own anchor;
* a family whose rendered size exceeds ``MAX_PAGE_BYTES`` is split into
  numbered segment pages (``<family>__seg2.html``), with navigation between
  them -- content is still complete, only paged;
* the raw ``manifest.json`` and every other file in the family directory are
  offered as downloads, so nothing is reachable only through the HTML.

Usage:
    python3 tools/build_results_viewer_family_pages.py [--root .]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from measure_viewer_coverage import is_remake_evidence  # noqa: E402

PAGE_DIR = "families"
# A family name is the census' shape: something-v1, something-v2, ...
FAMILY_NAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]*-v\d+")
# A single rendered page above this size is split into segment pages.
MAX_PAGE_BYTES = 1_200_000

SECTION_ORDER = (
    "schema", "artifact_schema", "artifact_status", "rom", "scope", "limits",
    "summary", "implementation", "combined_summary", "static_dispatch_summary",
    "decoder", "extension_policy", "extension_summary", "upstream",
    "consumer", "entries", "records", "messages", "glyphs", "groups",
    "resources", "slots", "packs", "canvases", "selections", "models",
    "components", "animations", "artifacts", "files", "outputs", "data",
)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


def render_scalar(value: Any) -> str:
    if value is None:
        return '<span class="fml-text">null</span>'
    if isinstance(value, bool):
        return f'<span class="fml-bool">{str(value).lower()}</span>'
    if isinstance(value, int):
        return (f'<span class="fml-num">{value:,}</span>'
                if abs(value) > 999 else f'<span class="fml-num">{value}</span>')
    if isinstance(value, float):
        return f'<span class="fml-num">{value}</span>'
    # No truncation: long strings are rendered in full.
    return f'<span class="fml-text">{esc(value)}</span>'


def looks_formula(text: str) -> bool:
    return bool(re.search(r"[=<>]=?|<<|>>|&\s*0x|\*\s*0x|/\s*0x", text))


def render_value(value: Any) -> str:
    if isinstance(value, dict):
        return "".join(
            f'<div class="fml-row"><div class="fml-key">{esc(k)}</div>'
            f'<div class="fml-val">{render_value(v)}</div></div>'
            for k, v in value.items()
        )
    if isinstance(value, list):
        if not value:
            return '<span class="fml-text">[]</span>'
        if all(not isinstance(v, (dict, list)) for v in value):
            # No truncation: every element is rendered.
            cells = "".join(f"<span>{render_scalar(v)}</span>" for v in value)
            return f'<div class="fml-list">{cells}</div>'
        rows = "".join(
            f'<div class="fml-row"><div class="fml-key">[{i:,}]</div>'
            f'<div class="fml-val">{render_value(item)}</div></div>'
            for i, item in enumerate(value)
        )
        return f'<div class="fml-rows">{rows}</div>'
    if looks_formula(str(value)):
        return f'<code class="fml-expr">{esc(value)}</code>'
    return render_scalar(value)


def family_files(root: Path, family: str) -> list[Path]:
    directory = root / "artifacts" / family
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file())


def order_keys(manifest: dict) -> list[str]:
    keys = list(manifest)
    ordered = [k for k in SECTION_ORDER if k in manifest]
    ordered += [k for k in keys if k not in ordered]
    return ordered


def split_oversized(value: Any, limit: int) -> list[Any]:
    """Break a single oversized value into chunks that each render under limit.

    A dict is split by its items, a list by its elements; the chunks keep the
    same shape so the renderer treats them identically.
    """
    if isinstance(value, dict):
        items = list(value.items())
        chunks: list[Any] = []
        current: dict = {}
        size = 0
        for k, v in items:
            body = render_value(v)
            if current and size + len(body) > limit:
                chunks.append(current)
                current, size = {}, 0
            current[k] = v
            size += len(body)
        if current:
            chunks.append(current)
        return chunks or [value]
    if isinstance(value, list):
        chunks = []
        current = []
        size = 0
        for item in value:
            body = render_value(item)
            if current and size + len(body) > limit:
                chunks.append(current)
                current, size = [], 0
            current.append(item)
            size += len(body)
        if current:
            chunks.append(current)
        return chunks or [value]
    return [value]


def segment_manifests(manifest: dict) -> list[list[tuple[str, Any]]]:
    """Split a manifest into segments of (key, value) pairs under the limit.

    A key whose own rendering exceeds the limit is split further, so no single
    section -- and therefore no single page -- can blow past the budget.
    """
    pieces: list[tuple[str, Any]] = []
    for key in order_keys(manifest):
        value = manifest[key]
        body = render_value(value)
        if len(body) <= MAX_PAGE_BYTES:
            pieces.append((key, value))
            continue
        for index, chunk in enumerate(split_oversized(value, MAX_PAGE_BYTES), 1):
            pieces.append((f"{key} (part {index})", chunk))

    segments: list[list[tuple[str, Any]]] = []
    current: list[tuple[str, Any]] = []
    current_size = 0
    for key, value in pieces:
        size = len(render_value(value))
        if current and current_size + size > MAX_PAGE_BYTES:
            segments.append(current)
            current, current_size = [], 0
        current.append((key, value))
        current_size += size
    if current:
        segments.append(current)
    return segments


def page_markup(root: Path, family: str, manifest: dict,
                keys: list[str], segment_index: int,
                segment_total: int, filename: str,
                all_filenames: list[str], all_labels: list[str]) -> str:
    directory = root / "artifacts" / family
    files = family_files(root, family)
    schema = manifest.get("schema") or manifest.get("artifact_schema") or family
    status = manifest.get("artifact_status")

    nav = "".join(
        f'<a class="sec-jump" href="#sec-{re.sub(r"[^a-zA-Z0-9]+", "-", k)}">'
        f'{esc(k)}</a>' for k, _v in keys
    )
    seg_nav = " ".join(
        f'<a class="sec-jump" href="{n}">{esc(l)}</a>'
        for n, l in zip(all_filenames, all_labels)
    )
    body = "\n".join(
        f'<section class="fam-sec" id="sec-{re.sub(r"[^a-zA-Z0-9]+", "-", k)}">'
        f'<h2 class="fam-sec-title">{esc(k)}</h2>{render_value(v)}</section>'
        for k, v in keys
    )
    downloads = "".join(
        f'<li><a href="../../artifacts/{family}/'
        f'{p.relative_to(directory).as_posix()}">{esc(p.relative_to(directory).as_posix())}</a>'
        f'<span class="fml-meta"> {p.stat().st_size:,} B</span></li>'
        for p in files
    ) or '<li class="fml-text">（无其他文件）</li>'

    label = all_labels[segment_index] if segment_index < len(all_labels) else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(family)} · 逆向成果族全量页</title>
  <link rel="stylesheet" href="../assets/viewer.css">
  <link rel="stylesheet" href="../assets/viewer-extra.css">
  <link rel="stylesheet" href="../assets/family.css">
</head>
<body data-page="families">
  <header class="top-bar">
    <div class="top-bar-left">
      <a class="brand-title" href="../reverse-engineering-data-index.html">← 成果族索引</a>
    </div>
    <div class="top-bar-right">
      <span class="fml-meta">{esc(label)} · 共 {segment_total} 段</span>
    </div>
  </header>

  <main class="family-page">
    <div class="fam-head">
      <h1 class="fam-title">{esc(family)}</h1>
      <div class="fam-meta">
        <span class="tag tag-purple">{esc(schema)}</span>
        {f'<span class="tag tag-amber">{esc(status)}</span>' if status else ''}
        <span class="tag tag-cyan">{len(manifest)} 个顶层分区 · {len(files)} 个可下载文件</span>
      </div>
      <p class="fam-note">
        本页<strong>完整呈现</strong>该成果族 manifest 的全部内容，不做任何截断。
        内容较多时按顶层分区分段成多页（见上方分段导航）；原始数据可整份下载。
      </p>
    </div>

    <nav class="fam-nav">{seg_nav}</nav>
    <nav class="fam-nav fam-nav-sub">{nav}</nav>

    <div class="fam-body">
{body}
    <section class="fam-sec" id="sec-downloads">
      <h2 class="fam-sec-title">原始文件下载（完整内容）</h2>
      <ul class="fam-dl">
{downloads}
      </ul>
    </section>
    </div>
  </main>

  <script src="../assets/viewer-runtime.js"></script>
</body>
</html>
"""


def synthetic_manifest(directory: Path) -> dict:
    """A family that ships no manifest of its own still has to be reachable.

    Two of the reverse-engineering families are plain payload directories --
    an index and a measurement dump.  Without a page they would be invisible
    to the viewer even though the import put them in ``artifacts/``.  The
    listing is generated from the files on disk; nothing in the family is
    modified, and the page says so.
    """
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        files[path.relative_to(directory).as_posix()] = {
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    if not files:
        return {}
    return {
        "schema": "viewer-synthetic-manifest-v1",
        "note": ("该族没有自带 manifest.json；下列清单由查看器按族目录的实际文件生成，"
                 "文件本身未被改动。"),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/families"))
    args = parser.parse_args()
    root = args.root.resolve()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    pages_written = 0
    for family_dir in sorted(p for p in (root / "artifacts").iterdir() if p.is_dir()):
        family = family_dir.name
        manifest_path = family_dir / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            # Only real families get a page: a working directory or a remake
            # capture tree is not a reverse-engineering deliverable.
            if not FAMILY_NAME_RE.fullmatch(family) or is_remake_evidence(family):
                continue
            manifest = synthetic_manifest(family_dir)
            if not manifest:
                continue
        segments = segment_manifests(manifest)
        total = len(segments)
        filenames = [
            f"{family}.html" if i == 0 else f"{family}__seg{i + 1}.html"
            for i in range(total)
        ]
        labels = [f"第 {i + 1}/{total} 段" for i in range(total)]
        for i, keys in enumerate(segments):
            page = page_markup(root, family, manifest, keys, i, total,
                               filenames[i], filenames, labels)
            (out_dir / filenames[i]).write_text(page, encoding="utf-8")
            pages_written += 1
        index.append({
            "family": family,
            "page": f"{PAGE_DIR}/{filenames[0]}",
            "pages": [f"{PAGE_DIR}/{n}" for n in filenames],
            "segments": total,
            "schema": manifest.get("schema") or manifest.get("artifact_schema"),
            "status": manifest.get("artifact_status"),
            "sections": len(manifest),
            "files": len(family_files(root, family)),
        })

    (root / "build/viewer-data/family-pages.json").write_text(
        json.dumps({"schema": "viewer-family-pages-v1",
                    "families": len(index), "pages": pages_written,
                    "index": index}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    biggest = max((out_dir / p.name).stat().st_size for p in out_dir.glob("*.html"))
    print(f"families={len(index)} pages={pages_written} "
          f"largest_page={biggest // 1024}KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
