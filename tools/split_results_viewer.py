#!/usr/bin/env python3
"""Split the single-page results viewer into a small multi-page site.

The viewer outgrew one document: after the coverage pass it carried 749 images
and 28 cards, which makes a 480 KB single page slow to open and impossible to
link to at section granularity.

This rebuilds it as six pages that share one stylesheet and one script bundle:

    reverse-engineering-results.html       研发全景 + 覆盖总表（保留原入口 URL）
    reverse-engineering-visuals.html       1. 视觉与动画资产库
    reverse-engineering-battle.html        2. 战斗系统与时序引擎
    reverse-engineering-story.html         3. 剧情调度与文本系统
    reverse-engineering-data.html          4. 内存数据与音频架构
    reverse-engineering-engineering.html   5. 逆向基建与工程流水线

    assets/viewer.css     shared stylesheet
    assets/viewer.js       shared behaviour (nav, search, sidebar)
    assets/studio-data.js  character-studio payload, loaded only by the visuals page

Card markup is copied verbatim from the source page, so nothing is re-typed and
no claim can drift.  Run it from the repo root:

    python3 tools/split_results_viewer.py
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

DOCS = Path("docs")
SOURCE = DOCS / "reverse-engineering-results.html"

PAGES = (
    ("progress", "hub-progress", "reverse-engineering-results.html",
     "研发全景", "📈"),
    ("visuals", "hub-visuals", "reverse-engineering-visuals.html",
     "1. 视觉与动画资产库", "🎨"),
    ("battle", "hub-battle", "reverse-engineering-battle.html",
     "2. 战斗系统与时序引擎", "⚔️"),
    ("story", "hub-story", "reverse-engineering-story.html",
     "3. 剧情调度与文本系统", "💬"),
    ("data", "hub-data", "reverse-engineering-data.html",
     "4. 内存数据与音频架构", "🧠"),
    ("engineering", "hub-engineering", "reverse-engineering-engineering.html",
     "5. 逆向基建与工程流水线", "🛠️"),
    ("formulas", "hub-formulas", "reverse-engineering-formulas.html",
     "6. 逆向公式与运行时模型", "📐"),
    ("conclusions", "hub-conclusions", "reverse-engineering-conclusions.html",
     "7. 逆向结论索引", "📖"),
    ("dataindex", "hub-data-index", "reverse-engineering-data-index.html",
     "8. ROM 数据产物索引", "🗃️"),
)

DOWNLOADS_SIDEBAR_ENTRY = """          <a class="sidebar-link" data-hub="progress" data-anchor="sec-image-downloads" href="reverse-engineering-results.html#sec-image-downloads">
            <span class="link-icon">\U0001F4E7</span>
            <span class="link-text">图像打包下载</span>
            <span class="link-badge">21板块</span>
          </a>
"""

DATA_INDEX_SIDEBAR_ENTRY = """          <a class="sidebar-link" data-hub="dataindex" data-anchor="sec-data-index" href="reverse-engineering-data-index.html#sec-data-index">
            <span class="link-icon">\U0001F5C3</span>
            <span class="link-text">ROM 数据产物索引</span>
            <span class="link-badge">120族</span>
          </a>
"""

CONCLUSIONS_SIDEBAR_ENTRY = """          <a class="sidebar-link" data-hub="conclusions" data-anchor="sec-conclusions" href="reverse-engineering-conclusions.html#sec-conclusions">
            <span class="link-icon">\U0001F4D6</span>
            <span class="link-text">逆向结论索引</span>
            <span class="link-badge">240篇</span>
          </a>
"""

# The formula hub is not a section of the original single-page viewer, so its
# body is assembled from the generated formula fragments.
FORMULA_SIDEBAR_ENTRY = """          <a class="sidebar-link" data-hub="formulas" data-anchor="sec-formula-index" href="reverse-engineering-formulas.html#sec-formula-index">
            <span class="link-icon">📐</span>
            <span class="link-text">逆向公式与运行时模型</span>
            <span class="link-badge">2,170字段</span>
          </a>
"""

TITLE_PREFIX = "《火影忍者：木叶战记》逆向工程结果查看器"

COVERAGE_CARD_ID = "sec-artifact-coverage"


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start) + len(start)
    j = text.index(end, i)
    return text[i:j]


CARD_OPEN = re.compile(r'<div class="card(?: full-width)?" id="')

PAGE_FILES = {hub: filename for hub, _, filename, _, _ in PAGES}

FRAGMENT_OWNERS = {
    "fragment-map-canvases.html": ("reverse-engineering-visuals.html", "sec-map-canvases"),
    "fragment-character-battle-visuals.html": (
        "reverse-engineering-visuals.html", "sec-character-battle-visuals"),
    "fragment-bg-canvases.html": ("reverse-engineering-visuals.html", "sec-bg-canvases"),
    "fragment-bg-scene-selection.html": (
        "reverse-engineering-visuals.html", "sec-bg-scene-selection"),
    "fragment-battle-effect-pairs.html": (
        "reverse-engineering-battle.html", "sec-battle-effect-pairs"),
    "fragment-battle-effect-sequences.html": (
        "reverse-engineering-battle.html", "sec-battle-effect-sequences"),
    "fragment-battle-glyphs.html": ("reverse-engineering-story.html", "sec-battle-glyphs"),
    "fragment-sprite-definitions.html": (
        "reverse-engineering-data.html", "sec-sprite-definitions"),
    "fragment-rom-catalog-card.html": (
        "reverse-engineering-results.html", "sec-rom-catalog"),
    "fragment-artifact-coverage-card.html": (
        "reverse-engineering-results.html", "sec-artifact-coverage"),
    "fragment-reverse-ledger.html": (
        "reverse-engineering-results.html", "sec-reverse-ledger"),
# --- generated by tools/build_results_viewer_generic_families.py ---
    "fragment-affine-runtime.html": ("reverse-engineering-battle.html", "sec-affine-runtime"),
    "fragment-battle-visual-catalog.html": ("reverse-engineering-battle.html", "sec-battle-visual-catalog"),
    "fragment-battle-visual-timelines.html": ("reverse-engineering-battle.html", "sec-battle-visual-timelines"),
    "fragment-cutscene-obj.html": ("reverse-engineering-story.html", "sec-cutscene-obj"),
    "fragment-dialogue-font.html": ("reverse-engineering-story.html", "sec-dialogue-font"),
    "fragment-sprite-def-anims.html": ("reverse-engineering-data.html", "sec-sprite-def-anims"),
    "fragment-story-scene-timelines.html": ("reverse-engineering-story.html", "sec-story-scene-timelines"),
    "fragment-story-visual-layers.html": ("reverse-engineering-story.html", "sec-story-visual-layers"),
    "fragment-tile-assets-bg.html": ("reverse-engineering-visuals.html", "sec-tile-assets-bg"),
    "fragment-world-map-bg.html": ("reverse-engineering-visuals.html", "sec-world-map-bg"),
}


# Fragments whose card does not exist in the single-page source: insert the
# card immediately after this existing one instead of replacing it.
# Fragments whose card does not exist in the source and are appended to the
# end of their hub section instead of being inserted at an anchor.
FRAGMENT_APPEND: set[str] = set()

FRAGMENT_INSERT_AFTER = {
    "fragment-battle-effect-sequences.html": "sec-battle-fsm-funcs",
    "fragment-bg-scene-selection.html": "sec-bg-canvases",
    "fragment-reverse-ledger.html": "sec-rom-catalog",

}

FRAGMENT_INSERT_AFTER.update({
    "fragment-tile-assets-bg.html": "sec-map-canvases",
    "fragment-battle-visual-catalog.html": "sec-battle-effect-sequences",
    "fragment-battle-visual-timelines.html": "sec-battle-visual-catalog",
    "fragment-cutscene-obj.html": "sec-chapter-fsm",
    "fragment-story-visual-layers.html": "sec-battle-glyphs",
    "fragment-story-scene-timelines.html": "sec-story-visual-layers",
    "fragment-sprite-def-anims.html": "sec-sprite-definitions",
    "fragment-rom-catalog-card.html": "sec-artifact-coverage",
})
FRAGMENT_INSERT_AFTER.update({
    "fragment-dialogue-font.html": "sec-chapter-fsm",
    "fragment-world-map-bg.html": "sec-scene-visual-packs",
    "fragment-affine-runtime.html": "sec-battle-visual-timelines",
})
FRAGMENT_INSERT_AFTER.update({
    "sec-dialogue-font": "sec-chapter-fsm",
    "sec-world-map-bg": "sec-scene-visual-packs",
    "sec-affine-runtime": "sec-battle-visual-timelines",
})


def extract_parts(html: str) -> dict[str, str]:
    style = _between(html, "<style>", "</style>")
    top_bar = _between(html, '<header class="top-bar">', "</header>")
    top_bar = '<header class="top-bar">' + top_bar + "</header>"
    sidebar = _between(html, '<aside class="left-sidebar"', "</aside>")
    sidebar = '<aside class="left-sidebar"' + sidebar + "</aside>"
    script = _between(html, "<script>", "</script>")
    sections: dict[str, str] = {}
    for hub, hub_id, _, _, _ in PAGES:
        if f'<section class="category-section" id="{hub_id}"' not in html:
            sections[hub] = ""   # assembled later (formula hub)
            continue
        start = html.index(f'<section class="category-section" id="{hub_id}"')
        nxt = html.find('<section class="category-section" id="hub-', start + 10)
        if nxt == -1:
            nxt = html.index("</main>", start)
        sections[hub] = html[start:nxt].rstrip() + "\n"
    return {
        "style": style,
        "top_bar": top_bar,
        "sidebar": sidebar,
        "script": script,
        "sections": sections,
    }


def split_studio_data(script: str) -> tuple[str, str]:
    match = re.search(r"\s*const STUDIO_DATA = \{.*?\};\n", script, re.S)
    if not match:
        return script, ""
    return script[: match.start()] + "\n" + script[match.end():], match.group(0)


def rewrite_sidebar(sidebar: str, current_file: str) -> str:
    """Point every sidebar entry at its own page instead of an in-page switch."""
    page_for_hub = {hub: filename for hub, _, filename, _, _ in PAGES}
    # The old flat "all hubs" view no longer exists as a single page.
    page_for_hub["all"] = page_for_hub["progress"]

    def to_href(hub: str, anchor: str | None) -> str:
        return page_for_hub[hub] + (f"#{anchor}" if anchor else "")

    sidebar = re.sub(
        r'onclick="switchHub\(\'(\w+)\',\s*\'([\w-]+)\'\)"',
        lambda m: f'href="{to_href(m.group(1), m.group(2))}"',
        sidebar,
    )
    sidebar = re.sub(
        r'onclick="switchHub\(\'(\w+)\'\)"',
        lambda m: f'href="{to_href(m.group(1), None)}"',
        sidebar,
    )
    # The flat "all modules" view no longer exists as a page; point it at index.
    sidebar = sidebar.replace(
        '<span class="link-icon">🌐</span>', '<span class="link-icon">🏠</span>'
    )
    sidebar = sidebar.replace(
        "<span class=\"link-text\">平铺查看所有模块</span>",
        "<span class=\"link-text\">返回研发全景总览</span>",
    )
    # Mark the entry belonging to this page so the active state survives a reload.
    sidebar = sidebar.replace(
        f'href="{current_file}"',
        f'href="{current_file}" data-current="1"',
    )
    return sidebar


COMMON_JS = """
    // Hub -> page map.  switchHub() navigates across pages and only scrolls in
    // place when the target already lives on this document.
    const VIEWER_PAGES = {
%(page_map)s
    };

    const VIEWER_PAGE = document.body.getAttribute('data-page');
    const HUB_FOR_PAGE = Object.keys(VIEWER_PAGES).find(
      hub => VIEWER_PAGES[hub] === VIEWER_PAGE
    ) || 'progress';
    let currentActiveHub = HUB_FOR_PAGE;

    // Where the shared assets live, relative to the page.  The pages sit in
    // docs/ in the repository and at the site root once published, so this
    // is one constant instead of a hard-coded "../" in every place that
    // builds a path at runtime; the publish build rewrites it to ''.
    const ASSET_BASE = '../';

    function switchHub(hubId, targetAnchor) {
      const file = VIEWER_PAGES[hubId];
      if (!file) return;
      const here = file.split('#')[0];
      if (here !== VIEWER_PAGE) {
        window.location.href = targetAnchor ? file + '#' + targetAnchor : file;
        return;
      }
      currentActiveHub = hubId;
      markActive(targetAnchor || null, here);
      if (targetAnchor) {
        const el = document.getElementById(targetAnchor);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }

    function markActive(targetAnchor, here) {
      document.querySelectorAll('.sidebar-link').forEach(link => {
        const href = link.getAttribute('href') || '';
        link.classList.toggle('active',
          targetAnchor ? href.endsWith('#' + targetAnchor)
                       : href === here);
      });
      // The scroll spy owns the highlight while the reader scrolls; let it
      // re-derive instead of leaving the two out of step.
      if (window.refreshSidebarSpy) window.refreshSidebarSpy();
    }

    // Restores the sidebar highlight after a reload or a cross-page anchor jump.
    function restoreActiveFromLocation() {
      const hash = window.location.hash.replace('#', '');
      const here = VIEWER_PAGE;
      document.querySelectorAll('.sidebar-link').forEach(link => {
        const href = link.getAttribute('href') || '';
        if (href.endsWith('#' + hash) || (href === here && !hash)) {
          link.classList.add('active');
        }
      });
    }

    // Restores every card on this page after a search is cleared.  This must
    // never call switchHub(), which would navigate to another page.
    function resetCards() {
      document.querySelectorAll('.category-section').forEach(sec => {
        sec.style.display = '';
      });
      document.querySelectorAll('.card').forEach(card => {
        card.style.display = '';
      });
      markActive(null, VIEWER_PAGE);
    }
"""


def build_common_js(script: str) -> str:
    page_map = "\n".join(
        f'      "{hub}": "{filename}",' for hub, _, filename, _, _ in PAGES
    )
    header = COMMON_JS % {"page_map": page_map}
    # The single-page script declares its own active-hub state; the shared
    # bundle derives it from <body data-page>, so drop the original.
    script = re.sub(
        r"\n\s*let currentActiveHub = 'progress';", "", script, count=1
    )
    # Drop the original single-page switchHub definition.
    script = re.sub(
        r"\n    function switchHub\(hubId, targetAnchor\) \{.*?\n    \}\n",
        "\n",
        script,
        count=1,
        flags=re.S,
    )
    # Search no longer crosses pages; it filters the current page only.
    script = script.replace(
        "      // In search mode, search across all sections",
        "      // Each hub is its own page, so search filters this page's cards.",
    )
    # Clearing a search must reset in place, never navigate.
    script = script.replace(
        "      switchHub(currentActiveHub);\n    }",
        "      resetCards();\n    }",
    )
    script = script.replace(
        "        switchHub(currentActiveHub);\n        return;",
        "        resetCards();\n        return;",
    )
    # The studio builds its asset paths at runtime, so they never appear in
    # the markup and no path rewriting would reach them.  Route them through
    # ASSET_BASE like every other runtime path.
    script = script.replace(
        '<a href="../${data.matrix_sheet}"',
        '<a href="${ASSET_BASE}${data.matrix_sheet}"',
    )
    script = script.replace(
        "        img.src = '../' + stripPath;",
        "        img.src = ASSET_BASE + stripPath;",
    )

    # Present every character action through one motion component.  14
    # characters ship an animated GIF and 21 ship only a frame strip; showing
    # one animated and the other frozen is the inconsistency the viewer had.
    script = script.replace(
        """          const p = act.gif_path || act.strip_path;
          actionCardsHtml += `
            <div class="studio-act-card" onclick="viewActionStrip('${act.strip_path}', '${name}')">
              <div class="studio-act-title">${name} (${act.frames_count}帧)</div>
              <div class="studio-act-img-wrap">
                <img src="../${p}" alt="${name}" style="image-rendering:pixelated; max-width:64px; max-height:64px;">
              </div>
            </div>`;""",
        """          const gif = act.gif_path;
          const media = gif
            ? `<img src="${ASSET_BASE}${gif}" alt="${name}">`
            : `<span class="is-motion" data-motion data-strip="${ASSET_BASE}${act.strip_path}" data-frames="${act.frames_count}" data-frame-width="64" data-frame-height="64" data-fps="10"></span>`;
          actionCardsHtml += `
            <div class="studio-act-card" onclick="viewActionStrip('${act.strip_path}', '${name}')">
              <div class="studio-act-title">${name} (${act.frames_count}帧)${gif ? '' : ' · 帧条'}</div>
              <div class="studio-act-img-wrap">${media}</div>
            </div>`;""",
    )
    script = script.replace(
        "      vp.innerHTML = `",
        "      vp.innerHTML = `",
    )
    script = script.replace(
        """      // Initialize with Progress View & Naruto""",
        """      // Initialize with Progress View & Naruto""",
    )

    # The studio replaces its container wholesale when the character changes,
    # so the motion components inside it are brand-new nodes.  Without this the
    # freshly inserted cells keep the container's dark background and read as
    # black squares until the page is reloaded.
    script = script.replace(
        """      `;
    }

    function viewActionStrip(stripPath, actionName) {""",
        """      `;
      if (window.initMotion) window.initMotion(document.body);
    }

    function viewActionStrip(stripPath, actionName) {""",
    )

    # Page init must not navigate; only restore the sidebar highlight.
    script = script.replace(
        "      switchHub('progress');\n      selectStudioChar(0);",
        "      restoreActiveFromLocation();\n"
        "      if (document.getElementById('charSelectorBar')) selectStudioChar(0);",
    )
    return header + script


DOWNLOADS_TOPBAR_ENTRY = (
    '        <a class="top-action-btn badge-cyan" '
    'href="reverse-engineering-results.html#sec-image-downloads" '
    'title="按板块打包下载全部图像">\n'
    '          \U0001F4E7 图像打包下载\n'
    '        </a>\n'
)



PAGES_BY_HUB = {hub: (hub, filename, label) for hub, _sid, filename, label, _icon in PAGES}


def _card_title_text(body: str) -> str:
    """Card title text, with any nested markup removed.

    The title div may contain a nested span (an icon), so matching up to the
    first "</" would truncate the title and bleed into the next card.
    """
    marker = 'class="card-title">'
    i = body.find(marker)
    if i == -1:
        return ""
    start = i + len(marker)
    depth = 1
    j = start
    while j < len(body):
        nxt_open = body.find("<div", j)
        nxt_close = body.find("</div>", j)
        if nxt_close == -1:
            break
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            j = nxt_open + 4
            continue
        depth -= 1
        j = nxt_close + 6
        if depth == 0:
            break
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", body[start:j]))).strip()


def collect_cards(section_html: str) -> list[tuple[str, str]]:
    """(card_id, title) for every card in a hub section, in document order."""
    out = []
    marks = [(m.start(), m.group(1))
             for m in re.finditer(r'<div class="card[^"]*" id="([^"]+)"[^>]*>', section_html)]
    for i, (pos, cid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(section_html)
        body = section_html[pos:end]
        title = _card_title_text(body) or cid
        out.append((cid, title))
    return out


def build_sidebar(card_index: dict[str, list[tuple[str, str]]],
                  current_hub: str) -> str:
    """Build the sidebar from the cards that actually exist.

    The previous sidebar was a hand-written list, so every card added later
    silently had no navigation entry.  Generating it from the real cards keeps
    the table of contents and the page in sync by construction.
    """
    groups = []
    for hub, _section_id, _file, label, _icon in PAGES:
        cards = card_index.get(hub, [])
        if not cards:
            continue
        entries = []
        for cid, title in cards:
            href = PAGES_BY_HUB[hub][1]
            entries.append(
                f'          <a class="sidebar-link sidebar-sub" '
                f'data-hub="{hub}" data-anchor="{cid}" '
                f'href="{href}#{cid}">'
                f'<span class="link-text">{html.escape(title)}</span></a>'
            )
        active = " active" if hub == current_hub else ""
        # The group header IS the clickable hub link; repeating it as plain
        # text above would just be a dead duplicate row.
        groups.append(
            f'        <div class="sidebar-group">\n'
            f'          <a class="sidebar-link sidebar-hub{active}" data-hub="{hub}" '
            f'href="{PAGES_BY_HUB[hub][1]}">'
            f'<span class="link-text">{html.escape(label)}</span>'
            f'<span class="link-badge">{len(cards)}</span></a>\n'
            + "\n".join(entries) + "\n"
            f"        </div>"
        )
    return (
        '<aside class="left-sidebar" id="leftSidebar">\n'
        '    <nav class="sidebar-nav">\n'
        + "\n".join(groups)
        + "\n    </nav>\n</aside>"
    )


def rewrite_top_bar(top_bar: str) -> str:
    """Cross-page buttons in the header become real links (middle-click works)."""
    page_for_hub = {hub: filename for hub, _, filename, _, _ in PAGES}

    def to_link(match: re.Match[str]) -> str:
        classes, hub, anchor, body = match.groups()
        return (
            f'<a class="top-action-btn{classes}" '
            f'href="{page_for_hub[hub]}#{anchor}"{body}</a>'
        )

    # Match the whole element so the closing tag is converted too; converting
    # only the opening tag leaves a dangling </button> that breaks layout.
    top_bar = re.sub(
        r'<button class="top-action-btn([^"]*)" '
        r"onclick=\"switchHub\('(\w+)',\s*'([\w-]+)'\)\"(.*?)</button>",
        to_link,
        top_bar,
        flags=re.S,
    )
    # Download entry: the image packs are the most-used affordance on the site.
    top_bar = top_bar.replace(
        '<div class="top-actions">',
        '<div class="top-actions">\n' + DOWNLOADS_TOPBAR_ENTRY,
        1,
    )
    # Search is now page-scoped, so say so instead of implying a global index.
    top_bar = top_bar.replace(
        "全局检索地址/角色/技能/道具/函数 (Ctrl+K)...",
        "本页检索地址/角色/技能/道具/函数 (Ctrl+K)...",
    )
    return top_bar


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="assets/viewer.css">
  <link rel="stylesheet" href="assets/viewer-extra.css">
</head>
<body data-page="{filename}">

  <div id="toast">已复制</div>
  <div id="searchPanel"></div>

{top_bar}

  <div class="app-layout">
{sidebar}

    <main class="main-workspace" id="mainWorkspace">

{sections}
    </main>
  </div>

  <script src="assets/viewer.js" defer></script>
  <script src="assets/viewer-runtime.js" defer></script>
{scripts}</body>
</html>
"""


CARD_START = re.compile(
    r'\n        <div class="card(?: full-width)?" id="'  # sibling card at card-grid depth
)



def link_index(entries: list[tuple[str, str, str]], title: str, note: str,
                card_id: str = "sec-heavy-index") -> str:
    """Compact index page body that links out to the split sub-pages."""
    rows = "\n".join(
        f'                <tr><td><a class="tag tag-cyan" style="text-decoration:none;" '
        f'href="{href}">{name}</a></td><td>{desc}</td></tr>'
        for name, href, desc in entries
    )
    return f"""        <div class="card full-width" id="{card_id}">
          <div class="card-head">
            <div class="card-title">{title}</div>
            <span class="tag tag-cyan">{len(entries)} 个子页</span>
          </div>
          <p class="card-desc">{note}</p>
          <div class="table-container">
            <table>
              <thead><tr><th>子页</th><th>内容</th></tr></thead>
              <tbody>
{rows}
              </tbody>
            </table>
          </div>
        </div>
"""


def move_coverage_card(sections: dict[str, str]) -> None:
    """The coverage table is an overview, so it belongs on the index page."""
    engineering = sections["engineering"]
    marker = f'<div class="card full-width" id="{COVERAGE_CARD_ID}">'
    start = engineering.find(marker)
    if start == -1:
        return
    # Match a *sibling* card only.  A plain substring search would hit the
    # card's own <div class="card-head"> and slice the card in half.
    sibling = CARD_START.search(engineering, start + len(marker))
    end = sibling.start() + 1 if sibling else len(engineering)
    card = engineering[start:end].rstrip()
    sections["engineering"] = engineering[:start] + engineering[end:]
    sections["progress"] = sections["progress"].rstrip() + "\n\n" + card + "\n"


CARD_CLOSE = re.compile(r"\n        </div>\n")


def _card_bounds(html: str, card_id: str) -> tuple[int, int] | None:
    """(start, end) of the card owning ``card_id``, end just past its close.

    The end must be the card's own matching ``</div>``: using the *next* card's
    start as the end silently swallows everything in between and inserts new
    content in the wrong place.
    """
    opening = re.compile(
        r'<div class="card[^"]*" id="' + re.escape(card_id) + r'"[^>]*>')
    match = opening.search(html)
    if not match:
        return None
    start = match.start()
    depth = 0
    i = start
    while i < len(html):
        nxt_open = html.find("<div", i)
        nxt_close = html.find("</div>", i)
        if nxt_close == -1:
            return None
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
            continue
        depth -= 1
        i = nxt_close + 6
        if depth == 0:
            return start, i
    return None


def _card_title_text(body: str) -> str:
    """Card title text, with any nested markup removed.

    The title div may contain a nested span (an icon), so matching up to the
    first "</" would truncate the title and bleed into the next card.
    """
    marker = 'class="card-title">'
    i = body.find(marker)
    if i == -1:
        return ""
    start = i + len(marker)
    depth = 1
    j = start
    while j < len(body):
        nxt_open = body.find("<div", j)
        nxt_close = body.find("</div>", j)
        if nxt_close == -1:
            break
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            j = nxt_open + 4
            continue
        depth -= 1
        j = nxt_close + 6
        if depth == 0:
            break
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", body[start:j]))).strip()


def collect_cards(section_html: str) -> list[tuple[str, str]]:
    """(card_id, title) for every card in a hub section, in document order."""
    out = []
    marks = [(m.start(), m.group(1))
             for m in re.finditer(r'<div class="card[^"]*" id="([^"]+)"[^>]*>', section_html)]
    for i, (pos, cid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(section_html)
        body = section_html[pos:end]
        title = _card_title_text(body) or cid
        out.append((cid, title))
    return out


def build_sidebar(card_index: dict[str, list[tuple[str, str]]],
                  current_hub: str) -> str:
    """Build the sidebar from the cards that actually exist.

    The previous sidebar was a hand-written list, so every card added later
    silently had no navigation entry.  Generating it from the real cards keeps
    the table of contents and the page in sync by construction.
    """
    groups = []
    for hub, _section_id, _file, label, _icon in PAGES:
        cards = card_index.get(hub, [])
        if not cards:
            continue
        entries = []
        for cid, title in cards:
            href = PAGES_BY_HUB[hub][1]
            entries.append(
                f'          <a class="sidebar-link sidebar-sub" '
                f'data-hub="{hub}" data-anchor="{cid}" '
                f'href="{href}#{cid}">'
                f'<span class="link-text">{html.escape(title)}</span></a>'
            )
        active = " active" if hub == current_hub else ""
        # The group header IS the clickable hub link; repeating it as plain
        # text above would just be a dead duplicate row.
        groups.append(
            f'        <div class="sidebar-group">\n'
            f'          <a class="sidebar-link sidebar-hub{active}" data-hub="{hub}" '
            f'href="{PAGES_BY_HUB[hub][1]}">'
            f'<span class="link-text">{html.escape(label)}</span>'
            f'<span class="link-badge">{len(cards)}</span></a>\n'
            + "\n".join(entries) + "\n"
            f"        </div>"
        )
    return (
        '<aside class="left-sidebar" id="leftSidebar">\n'
        '    <nav class="sidebar-nav">\n'
        + "\n".join(groups)
        + "\n    </nav>\n</aside>"
    )


def rewrite_top_bar(top_bar: str) -> str:
    """Cross-page buttons in the header become real links (middle-click works)."""
    page_for_hub = {hub: filename for hub, _, filename, _, _ in PAGES}

    def to_link(match: re.Match[str]) -> str:
        classes, hub, anchor, body = match.groups()
        return (
            f'<a class="top-action-btn{classes}" '
            f'href="{page_for_hub[hub]}#{anchor}"{body}</a>'
        )

    # Match the whole element so the closing tag is converted too; converting
    # only the opening tag leaves a dangling </button> that breaks layout.
    top_bar = re.sub(
        r'<button class="top-action-btn([^"]*)" '
        r"onclick=\"switchHub\('(\w+)',\s*'([\w-]+)'\)\"(.*?)</button>",
        to_link,
        top_bar,
        flags=re.S,
    )
    # Download entry: the image packs are the most-used affordance on the site.
    top_bar = top_bar.replace(
        '<div class="top-actions">',
        '<div class="top-actions">\n' + DOWNLOADS_TOPBAR_ENTRY,
        1,
    )
    # Search is now page-scoped, so say so instead of implying a global index.
    top_bar = top_bar.replace(
        "全局检索地址/角色/技能/道具/函数 (Ctrl+K)...",
        "本页检索地址/角色/技能/道具/函数 (Ctrl+K)...",
    )
    return top_bar


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="assets/viewer.css">
  <link rel="stylesheet" href="assets/viewer-extra.css">
</head>
<body data-page="{filename}">

  <div id="toast">已复制</div>
  <div id="searchPanel"></div>

{top_bar}

  <div class="app-layout">
{sidebar}

    <main class="main-workspace" id="mainWorkspace">

{sections}
    </main>
  </div>

  <script src="assets/viewer.js" defer></script>
  <script src="assets/viewer-runtime.js" defer></script>
{scripts}</body>
</html>
"""


CARD_START = re.compile(
    r'\n        <div class="card(?: full-width)?" id="'  # sibling card at card-grid depth
)



def link_index(entries: list[tuple[str, str, str]], title: str, note: str,
                card_id: str = "sec-heavy-index") -> str:
    """Compact index page body that links out to the split sub-pages."""
    rows = "\n".join(
        f'                <tr><td><a class="tag tag-cyan" style="text-decoration:none;" '
        f'href="{href}">{name}</a></td><td>{desc}</td></tr>'
        for name, href, desc in entries
    )
    return f"""        <div class="card full-width" id="{card_id}">
          <div class="card-head">
            <div class="card-title">{title}</div>
            <span class="tag tag-cyan">{len(entries)} 个子页</span>
          </div>
          <p class="card-desc">{note}</p>
          <div class="table-container">
            <table>
              <thead><tr><th>子页</th><th>内容</th></tr></thead>
              <tbody>
{rows}
              </tbody>
            </table>
          </div>
        </div>
"""


def move_coverage_card(sections: dict[str, str]) -> None:
    """The coverage table is an overview, so it belongs on the index page."""
    engineering = sections["engineering"]
    marker = f'<div class="card full-width" id="{COVERAGE_CARD_ID}">'
    start = engineering.find(marker)
    if start == -1:
        return
    # Match a *sibling* card only.  A plain substring search would hit the
    # card's own <div class="card-head"> and slice the card in half.
    sibling = CARD_START.search(engineering, start + len(marker))
    end = sibling.start() + 1 if sibling else len(engineering)
    card = engineering[start:end].rstrip()
    sections["engineering"] = engineering[:start] + engineering[end:]
    sections["progress"] = sections["progress"].rstrip() + "\n\n" + card + "\n"


CARD_CLOSE = re.compile(r"\n        </div>\n")


def _card_bounds(html: str, card_id: str) -> tuple[int, int] | None:
    """(start, end) of the card owning ``card_id``.

    ``end`` is the card's own closing tag at its 8-space indentation, NOT the
    next card and NOT ``</section>``: cutting at either swallows the enclosing
    card-grid close and unbalances the page.
    """
    try:
        anchor = html.index(f'id="{card_id}"')
    except ValueError:
        return None
    start = html.rfind('<div class="card', 0, anchor)
    if start == -1:
        return None
    close = CARD_CLOSE.search(html, html.index(">", anchor) + 1)
    if not close:
        return None
    return start, close.end()


# Fragments that must be applied before others on the same page, because a
# later one anchors on a card an earlier one inserts.  Dict order alone is not
# an ordering guarantee we want to rely on for correctness.
FRAGMENT_ORDER = (
    "fragment-rom-catalog-card.html",
    "fragment-dialogue-font.html",
    "fragment-world-map-bg.html",
    "fragment-affine-runtime.html",
    "fragment-artifact-coverage-card.html",
    "fragment-battle-glyphs.html",
    "fragment-story-visual-layers.html",
    "fragment-story-scene-timelines.html",
)


def apply_fragments(sections: dict[str, str], hub: str,
                    fragments_dir: Path | None) -> None:
    """Replace (or insert) each card a generated fragment owns.

    Applied as a fixpoint rather than in a hand-maintained order: a fragment
    may anchor on a card that another fragment inserts, and hand-ordering kept
    missing those.  Re-running until the page stops changing converges in two
    passes and removes the ordering requirement entirely.
    """
    if fragments_dir is None:
        return
    page_file = PAGE_FILES[hub]
    entries = [
        (name, *owner) for name, owner in FRAGMENT_OWNERS.items()
        if owner[0] == page_file
    ]
    for _pass in range(len(entries) + 1):
        changed = False
        for name, _owner_page, card_id in entries:
            fragment_path = fragments_dir / name
            if not fragment_path.is_file():
                continue
            fragment = fragment_path.read_text(encoding="utf-8").rstrip("\n")
            html = sections[hub]
            bounds = _card_bounds(html, card_id)
            if bounds is not None:
                start, end = bounds
                if html[start:end].strip() == fragment.strip():
                    continue
                sections[hub] = html[:start] + fragment + "\n" + html[end:]
                changed = True
                continue
            if name in FRAGMENT_APPEND:
                sections[hub] = html.rstrip() + "\n" + fragment + "\n"
                changed = True
                continue
            anchor_id = FRAGMENT_INSERT_AFTER.get(name)
            if not anchor_id:
                continue
            anchor = _card_bounds(html, anchor_id)
            if anchor is None:
                continue
            at = anchor[1]
            sections[hub] = html[:at] + fragment + "\n" + html[at:]
            changed = True
        if not changed:
            break


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument(
        "--fragments",
        type=Path,
        default=None,
        help="Directory of generated fragments to apply during emission.",
    )
    args = parser.parse_args()
    root = Path.cwd()

    html = args.source.read_text(encoding="utf-8")
    if "<body data-page=" in html or "docs/assets/viewer.css" in html:
        raise SystemExit(
            f"{args.source} is already a split page (it carries data-page=).\n"
            "This tool is a one-time migration from the single-page viewer.\n"
            "The per-hub pages are now the source of truth: edit them directly,\n"
            "plus docs/assets/viewer.css and docs/assets/viewer.js.\n"
            "Re-running against an already-split source would drop cards."
        )
    parts = extract_parts(html)
    script_without_studio, studio = split_studio_data(parts["script"])

    assets = DOCS / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "viewer.css").write_text(parts["style"].strip() + "\n", encoding="utf-8")
    if studio:
        (assets / "studio-data.js").write_text(studio.strip() + "\n", encoding="utf-8")

    sections = parts["sections"]
    move_coverage_card(sections)

    data_index = args.fragments / "fragment-data-index.html" if args.fragments else None
    if data_index and data_index.is_file():
        sections["dataindex"] = (
            '<section class="category-section" id="hub-data-index" data-category="dataindex">\n'
            '      <div class="section-header">\n'
            '        <div class="section-title">\n'
            '          <span class="icon">\U0001F5C3</span> 8. ROM 数据产物索引 '
            '(ROM Data Artifacts)\n'
            '        </div>\n'
            '        <span class="section-tag">逆向分支已提交产物：控制流图、'
            '解码器契约与有界清单</span>\n'
            '      </div>\n'
            '      <div class="card-grid">\n'
            + data_index.read_text(encoding="utf-8").rstrip("\n")
            + "\n      </div>\n    </section>\n"
        )

    toolbox = args.fragments / "fragment-toolbox-full.html" if args.fragments else None
    if toolbox and toolbox.is_file():
        anchor = '<div class="card full-width" id="sec-toolbox-index">'
        engineering = sections["engineering"]
        if anchor in engineering:
            engineering = engineering.replace(
                anchor,
                toolbox.read_text(encoding="utf-8").rstrip("\n") + "\n        " + anchor,
                1,
            )
            sections["engineering"] = engineering

    dl_panel = args.fragments / "fragment-image-downloads.html" if args.fragments else None
    if dl_panel and dl_panel.is_file():
        # First card on the page: two 255-row tables sit below it, so a
        # download panel at the bottom would be effectively invisible.
        sections["progress"] = (
            dl_panel.read_text(encoding="utf-8").rstrip("\n")
            + "\n\n" + sections["progress"].lstrip("\n")
        )

    concl_fragment = args.fragments / "fragment-conclusions.html" if args.fragments else None
    note_count = 0
    concl_index = args.fragments / "conclusions-index.json" if args.fragments else None
    if concl_index and concl_index.is_file():
        try:
            note_count = json.loads(concl_index.read_text(encoding="utf-8")).get(
                "note_count", 0)
        except (OSError, ValueError):
            note_count = 0
    if concl_fragment and concl_fragment.is_file():
        concl_pages = sorted((args.fragments.parent.parent / "docs").glob(
            "reverse-engineering-conclusions-*.html"))
        entries = []
        for page in concl_pages:
            hub = page.stem.rsplit("-", 1)[-1]
            entries.append((hub, f"reverse-engineering-conclusions-{hub}.html",
                            f"「{hub}」主题下的结论全文"))
        sections["conclusions"] = (
            '<section class="category-section" id="hub-conclusions" data-category="conclusions">\n'
            '      <div class="section-header">\n'
            '        <div class="section-title">\n'
            '          <span class="icon">\U0001F4D6</span> 7. 逆向结论索引 '
            '(Reverse Engineering Conclusions)\n'
            '        </div>\n'
            '        <span class="section-tag">notes/ 全部笔记的结论原文，'
            '按主题分页</span>\n'
            '      </div>\n'
            '      <div class="card-grid">\n'
            + link_index(entries, "结论分主题索引",
                         f"结论原文按主题拆成子页，避免一次加载全部 {note_count} 篇正文。",
                         card_id="sec-conclusions")
            + "\n      </div>\n    </section>\n"
        )

    formula_body = (args.fragments / "fragment-formula-page.html") if args.fragments else None
    formula_index_text = ""
    if formula_body and formula_body.is_file():
        fi = args.fragments / "fragment-formula-index.html"
        formula_index_text = fi.read_text(encoding="utf-8") if fi.is_file() else ""
    formula_index = (args.fragments / "fragment-formula-index.html") if args.fragments else None
    if formula_body and formula_body.is_file() and formula_index.is_file():
        sections["formulas"] = (
            '<section class="category-section" id="hub-formulas" data-category="formulas">\n'
            '      <div class="section-header">\n'
            '        <div class="section-title">\n'
            '          <span class="icon">📐</span> 6. 逆向公式与运行时模型 '
            '(Formulas &amp; Runtime Models)\n'
            '        </div>\n'
            '        <span class="section-tag">逆向结论中的方程本身，'
            '全部由各成果族 manifest 直接导出</span>\n'
            '      </div>\n'
            '      <div class="card-grid">\n'
            + re.sub(
                r'reverse-engineering-formulas\.html#fml-([\w-]+)',
                r'reverse-engineering-formulas-\1.html',
                formula_index_text,
            ).rstrip("\n")
            + "\n"
            + link_index(
                [(f, f"reverse-engineering-formulas-{f}.html", "运行时模型与公式")
                 for f in sorted(
                     re.findall(r'id="fml-([\w-]+)"',
                                formula_body.read_text(encoding="utf-8")))],
                "公式与运行时模型索引",
                "每个成果族的运行时模型单独成页，避免一次加载全部公式正文。")
            + "\n      </div>\n    </section>\n"
        )

    # The bundle is shared, so it is written once, not per page.
    (assets / "viewer.js").write_text(
        build_common_js(script_without_studio).strip() + "\n", encoding="utf-8"
    )

    # The sidebar is generated from the cards that actually exist, so the
    # table of contents can never drift from the page content.
    for hub in list(sections):
        apply_fragments(sections, hub, args.fragments)
    # Scene visual packs: background + animated OBJ layers.  Appended once
    # after fragment application so it cannot be duplicated by the fixpoint.
    for special_id, special_file in (
        ("sec-scene-visual-packs", "fragment-scene-visual-packs.html"),
        ("sec-battle-effect-anims", "fragment-battle-effect-anims.html"),
    ):
        special = args.fragments / special_file if args.fragments else None
        if not (special and special.is_file()):
            continue
        markup = special.read_text(encoding="utf-8").rstrip("\n")
        hub = "visuals" if special_id == "sec-scene-visual-packs" else "battle"
        body = sections[hub]
        bounds = _card_bounds(body, special_id)
        if bounds is not None:
            start, end = bounds
            sections[hub] = body[:start] + markup + body[end:]
        else:
            sections[hub] = body.rstrip() + "\n" + markup + "\n"

    card_index = {hub: collect_cards(body) for hub, body in sections.items()}

    for hub, _, filename, label, icon in PAGES:
        needs_studio = hub == "visuals"
        # Paginate AFTER fragments land, so every gallery on the page counts
        # and no single document renders a thousand <img> at once.
        sections[hub] = re.sub(
            r'<div class="tileset-gallery"(\s+style="[^"]*")?>',
            lambda m: '<div class="tileset-gallery" data-paginate="24"'
                      + (m.group(1) or "") + ">",
            sections[hub],
        )
        # The formula hub is a nav entry on every page, not just its own.
        sidebar = build_sidebar(card_index, hub)
        scripts = ""
        if hub == "conclusions":
            scripts = """  <script>
    document.addEventListener('DOMContentLoaded', function () {
      var buttons = document.querySelectorAll('.cc-filter');
      var notes = document.querySelectorAll('.cc-note');
      buttons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          var want = btn.getAttribute('data-hub');
          buttons.forEach(function (b) { b.classList.remove('active'); });
          btn.classList.add('active');
          notes.forEach(function (note) {
            note.style.display = (want === 'all' || note.getAttribute('data-hub') === want) ? '' : 'none';
          });
        });
      });
    });
  </script>
"""
        page = PAGE_TEMPLATE.format(
            title=f"{TITLE_PREFIX} · {label}",
            filename=filename,
            top_bar=rewrite_top_bar(parts["top_bar"]),
            sidebar=sidebar,
            sections=sections[hub],
            scripts=scripts or (
                '  <script src="assets/studio-data.js"></script>\n'
                if needs_studio else ""
            ),
        )
        (DOCS / filename).write_text(page, encoding="utf-8")
        print(f"wrote docs/{filename}")

    # Per-card download buttons: the packs are keyed by card id, so the
    # buttons must be added after the pages exist but before the run ends,
    # otherwise a re-run would silently drop them.
    try:
        from inject_viewer_download_buttons import inject as _inject_downloads
        added = _inject_downloads(root)
        if added:
            print(f"injected {added} per-card download buttons")
    except Exception as exc:  # packs may not be built yet
        print(f"per-card download buttons skipped: {exc}")

    print(f"wrote docs/assets/viewer.css, docs/assets/viewer.js"
          f"{', docs/assets/studio-data.js' if studio else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
