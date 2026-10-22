#!/usr/bin/env python3
"""Assemble the publishable tree of the results viewer for GitHub Pages.

The viewer is built to live in ``docs/`` and reaches its images through
``../artifacts`` and ``../build`` -- paths that escape the document root.
GitHub Pages serves exactly one directory, so the publish tree is assembled
the way the site expects to be served:

    <root>/index.html                    entry (redirects to the progress hub)
    <root>/reverse-engineering-*.html    the hub pages and their sub-pages
    <root>/families/*.html               the per-family sub-pages
    <root>/assets/                       stylesheets, scripts, search index
    <root>/downloads/                    the per-section / theme / family packs
    <root>/artifacts/                    the evidence the pages link to
    <root>/build/                        the derived images the pages link to

Only files the pages actually reference are copied, and the ``../`` prefix
that used to escape ``docs/`` is dropped once -- the repository root becomes
the site root, so one level of ``..`` no longer has to be climbed.

The base ROM is never part of the tree: no page references it, and the copy
step only ever takes files that a page points at.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

PAGE_GLOBS = ("reverse-engineering-*.html",)
FAMILY_GLOB = "families/*.html"
ASSET_DIR = "assets"
DOWNLOAD_DIR = "downloads"
ENTRY = "reverse-engineering-results.html"

# Every attribute that can carry a file reference.
REF_ATTR = re.compile(
    r'((?:src|href|data-strip|data-frames)=")([^"]*)(")', re.IGNORECASE)

# Paths that JavaScript builds at runtime.  They never appear in the markup,
# so a scan of the pages alone would miss them -- and the character studio
# is built entirely this way.
RUNTIME_PATH = re.compile(r"""["'`]((?:build|artifacts|docs)/[^"'`\s]+)["'`]""")

# The pages sit in docs/ in the repository and at the site root once
# published, so the shared-asset prefix is one constant in the shared script.
ASSET_BASE_LOCAL = "const ASSET_BASE = '../';"
ASSET_BASE_PUBLISHED = "const ASSET_BASE = '';"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def page_files(docs: Path) -> list[Path]:
    pages: list[Path] = []
    for pattern in PAGE_GLOBS:
        pages.extend(sorted(docs.glob(pattern)))
    pages.extend(sorted(docs.glob(FAMILY_GLOB)))
    return [p for p in pages if p.is_file()]


def split_refs(value: str) -> list[str]:
    """A data-frames attribute carries several pipe-separated paths."""
    return [part for part in value.split("|") if part]


def classify(value: str, page_dir: Path, docs: Path) -> tuple[str | None, bool]:
    """Return (source path, escapes_docs) for one reference value."""
    if not value or value.startswith(("http:", "https:", "mailto:", "#",
                                      "javascript:", "data:")):
        return None, False
    target = (page_dir / value.split("#")[0]).resolve()
    if not target.is_file():
        return None, False
    try:
        target.relative_to(docs.resolve())
        escapes = False
    except ValueError:
        escapes = True
    return target, escapes


def rewrite(html: str, page_dir: Path, docs: Path) -> tuple[str, list[Path]]:
    """Drop one ``..`` from every reference that used to escape docs/."""
    sources: set[Path] = set()

    def fix(match: re.Match[str]) -> str:
        head, value, tail = match.groups()
        parts = split_refs(value)
        if not parts:
            return match.group(0)
        out = []
        changed = False
        for part in parts:
            target, escapes = classify(part, page_dir, docs)
            if target is not None:
                sources.add(target)
            if escapes and part.startswith("../"):
                part = part[3:]
                changed = True
            out.append(part)
        if not changed:
            return match.group(0)
        return head + "|".join(out) + tail

    return REF_ATTR.sub(fix, html), sorted(sources)


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source_dir: Path, destination_dir: Path) -> int:
    count = 0
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        copy_file(path, destination_dir / path.relative_to(source_dir))
        count += 1
    return count


def runtime_assets(root: Path, assets_dir: Path) -> tuple[set[Path], dict[str, str]]:
    """Files the shared scripts point at, plus the rewritten asset prefix.

    The character studio renders its GIFs and frame strips from JavaScript,
    so those files are referenced by nothing in the markup: a page-only scan
    would ship the studio without a single animation.  The scripts are
    scanned for path literals as well, and the shared-asset prefix is
    rewritten because the published pages sit at the site root.
    """
    files: set[Path] = set()
    rewritten: dict[str, str] = {}
    for script in sorted(assets_dir.glob("*.js")):
        text = script.read_text(encoding="utf-8")
        for token in RUNTIME_PATH.findall(text):
            candidate = (root / token).resolve()
            if candidate.is_file():
                files.add(candidate)
        if ASSET_BASE_LOCAL in text:
            rewritten[script.name] = text.replace(
                ASSET_BASE_LOCAL, ASSET_BASE_PUBLISHED)
    return files, rewritten


def entry_page() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>《火影忍者：木叶战记》逆向工程结果查看器</title>
<meta http-equiv="refresh" content="0; url=reverse-engineering-results.html">
<link rel="canonical" href="reverse-engineering-results.html">
<style>
  body { background:#0b1020; color:#cbd5e1; font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         display:flex; align-items:center; justify-content:center; height:100vh; margin:0; text-align:center; }
  .box { max-width:640px; padding:32px 40px; }
  h1 { font-size:1.5rem; color:#e2e8f0; margin:0 0 12px; }
  p { line-height:1.8; color:#94a3b8; font-size:.92rem; }
  a { color:#38bdf8; }
  .badge { display:inline-block; background:rgba(56,189,248,.14); border:1px solid rgba(56,189,248,.3);
           color:#38bdf8; border-radius:6px; padding:2px 10px; font-size:.78rem; margin-bottom:14px; }
</style>
</head>
<body>
  <div class="box">
    <span class="badge">GitHub Pages</span>
    <h1>《火影忍者：木叶战记》逆向工程结果查看器</h1>
    <p>正在进入 <a href="reverse-engineering-results.html">研发全景</a>……<br>
       若未自动跳转，请点击上面的链接。</p>
  </div>
</body>
</html>
"""


def build(root: Path, output: Path) -> dict:
    # Resolve both, so the tool behaves the same whether it is handed a
    # symlinked path (macOS /var vs /private/var) or a plain one.
    root = root.resolve()
    output = output.resolve()
    docs = root / "docs"
    if not docs.is_dir():
        raise FileNotFoundError(f"missing {docs}")
    pages = page_files(docs)
    if not pages:
        raise FileNotFoundError(f"no viewer pages under {docs}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    page_records = []
    referenced: set[Path] = set()
    page_set = {p.resolve() for p in pages}
    for page in pages:
        rel = page.relative_to(docs)
        destination = output / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        html, sources = rewrite(page.read_text(encoding="utf-8"), page.parent, docs)
        destination.write_text(html, encoding="utf-8")
        referenced.update(sources)
        page_records.append({
            "page": rel.as_posix(),
            "bytes": destination.stat().st_size,
            "sha256": _sha256(destination),
        })

    # The assets directory is copied whole: the runtime fetches the search
    # index by URL, which no static scan of the markup would ever find.
    asset_count = copy_tree(docs / ASSET_DIR, output / ASSET_DIR)
    download_count = copy_tree(docs / DOWNLOAD_DIR, output / DOWNLOAD_DIR)

    # The shared scripts point at their own assets, and the pages sit at the
    # site root now, so the prefix they use has to change with them.
    runtime_files, rewritten = runtime_assets(root, docs / ASSET_DIR)
    for name, text in rewritten.items():
        (output / ASSET_DIR / name).write_text(text, encoding="utf-8")
    referenced.update(runtime_files)

    asset_files = 0
    asset_bytes = 0
    for source in sorted(referenced):
        # Pages are written with their references rewritten; copying the
        # original back over them would undo that.  The same goes for the
        # assets directory, which is published wholesale and then has its
        # asset prefix rewritten.
        source = source.resolve()
        if source in page_set:
            continue
        rel = source.relative_to(root)
        if rel.parts[0] == "docs":
            if rel.parts[1] in (ASSET_DIR, DOWNLOAD_DIR):
                continue
            target_rel = Path(*rel.parts[1:])
        else:
            target_rel = rel
        copy_file(source, output / target_rel)
        asset_files += 1
        asset_bytes += source.stat().st_size

    (output / "index.html").write_text(entry_page(), encoding="utf-8")
    # GitHub Pages would otherwise run Jekyll over the tree.
    (output / ".nojekyll").write_text("", encoding="utf-8")

    manifest = {
        "schema": "viewer-publish-v1",
        "entry": "index.html",
        "page_count": len(page_records),
        "pages": page_records,
        "asset_files": asset_files,
        "asset_bytes": asset_bytes,
        "assets_copied_whole": {
            ASSET_DIR: asset_count,
            DOWNLOAD_DIR: download_count,
        },
        "total_bytes": sum(p.stat().st_size for p in output.rglob("*") if p.is_file()),
        "total_files": sum(1 for p in output.rglob("*") if p.is_file()),
    }
    (output / "publish-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(output: Path) -> list[str]:
    """Every reference inside the published tree must resolve inside it."""
    problems: list[str] = []
    pages = sorted(output.glob("*.html")) + sorted(output.glob("families/*.html"))
    for page in pages:
        html = page.read_text(encoding="utf-8")
        for match in REF_ATTR.finditer(html):
            for part in split_refs(match.group(2)):
                if part.startswith(("http:", "https:", "mailto:", "#",
                                    "javascript:", "data:")):
                    continue
                target = (page.parent / part.split("#")[0]).resolve()
                if not target.exists():
                    problems.append(f"{page.name}: {part}")
    # The scripts point at their own assets at runtime; those must be there
    # too, or the card renders empty.
    for script in sorted(output.glob("assets/*.js")):
        text = script.read_text(encoding="utf-8")
        for token in RUNTIME_PATH.findall(text):
            if not (output / token).exists():
                problems.append(f"{script.name}: {token}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path,
                        default=Path("build/viewer-publish"))
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    try:
        manifest = build(root, output)
    except (FileNotFoundError, ValueError) as error:
        print(f"publish build refused: {error}")
        return 2
    problems = verify(output)
    if problems:
        print(f"publish build refused: {len(problems)} dangling references")
        for problem in problems[:10]:
            print("  ", problem)
        return 3
    print(f"pages={manifest['page_count']} files={manifest['total_files']} "
          f"size={manifest['total_bytes'] / 1048576:.1f} MiB -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
