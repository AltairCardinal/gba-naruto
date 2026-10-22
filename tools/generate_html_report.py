#!/usr/bin/env python3
"""Generate the Consolidated Reverse Engineering HTML Dashboard.

Features:
- Dedicated Project Progress & Milestones Hub (not pinned on top; full KPI & Phase Roadmap)
- Structured Top Bar + Left Sidebar Navigation Layout
- 5 High-Density Thematic Hubs:
  1. progress    : 📈 项目全景进度 (KPI Cards, 7 P0 Milestones Matrix, ROM Memory Topology, CI Tests)
  2. visuals     : 🎨 视觉与动画资产库 (Interactive Character Studio, 9 Action GIFs, 155 Portraits, Tilesets)
  3. battle      : ⚔️ 战斗系统与时序引擎 (Jutsu VM Bytecode, 36 Scripts, Particle Splines, 32B Scenarios)
  4. story       : 💬 剧情调度与文本系统 (Render Pipeline, 305 Script Groups, Chapter SM, 128KB Free Space)
  5. data        : 🧠 内存数据与音频架构 (Unit RAM Mapping, 80+ Item Matrix, DirectSound PCM Audio)
  6. engineering : 🛠️ 逆向基建与工程流水线 (build_mod.py 6 Patches, Automated Tests 17/17, Tools Matrix)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.report_sections import (
    build_character_studio_data_json,
    build_progress_hub,
    build_visuals_hub,
    build_battle_hub,
    build_story_hub,
    build_data_hub,
    build_engineering_hub,
)

OUTPUT_HTML = Path("docs/reverse-engineering-results.html")


def main() -> None:
    studio_data_json = build_character_studio_data_json()
    hub_progress = build_progress_hub()
    hub_visuals = build_visuals_hub()
    hub_battle = build_battle_hub()
    hub_story = build_story_hub()
    hub_data = build_data_hub()
    hub_engineering = build_engineering_hub()

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>火影忍者 - 木叶战记 GBA 逆向工程成果全景控制台</title>
  <style>
    :root {{
      --bg-primary: #0b1120;
      --bg-secondary: #131c31;
      --bg-card: #18233c;
      --bg-card-hover: #1f2e4d;
      --border-color: #263554;
      --border-focus: #38bdf8;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --accent-cyan: #38bdf8;
      --accent-green: #4ade80;
      --accent-amber: #fbbf24;
      --accent-rose: #fb7185;
      --accent-purple: #c084fc;
      --accent-indigo: #818cf8;
      --code-bg: #090d16;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background-color: var(--bg-primary);
      color: var(--text-primary);
      font-family: var(--font-sans);
      line-height: 1.5;
    }}

    /* Toast Notification */
    #toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--accent-green);
      color: #000;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 0.85rem;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s;
      z-index: 9999;
    }}

    #toast.show {{
      opacity: 1;
    }}

    /* Top Bar */
    .top-bar {{
      position: sticky;
      top: 0;
      z-index: 1000;
      height: 56px;
      background: rgba(11, 17, 32, 0.96);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
    }}

    .top-bar-left {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}

    .sidebar-toggle-btn {{
      background: transparent;
      border: 1px solid var(--border-color);
      color: var(--text-secondary);
      width: 32px;
      height: 32px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.15s;
    }}

    .sidebar-toggle-btn:hover {{
      background: var(--bg-card);
      color: #fff;
      border-color: var(--accent-cyan);
    }}

    .top-bar-brand {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .brand-badge {{
      background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
      color: #000;
      font-weight: 800;
      font-size: 0.72rem;
      padding: 2px 7px;
      border-radius: 4px;
      letter-spacing: 0.05em;
    }}

    .brand-title {{
      font-size: 1.05rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: #fff;
      white-space: nowrap;
    }}

    .rom-status-tag {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(74, 222, 128, 0.1);
      border: 1px solid rgba(74, 222, 128, 0.25);
      padding: 3px 10px;
      border-radius: 9999px;
      font-size: 0.75rem;
      color: var(--accent-green);
      font-weight: 600;
    }}

    .pulse-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent-green);
      box-shadow: 0 0 8px var(--accent-green);
      animation: pulse 2s infinite;
    }}

    @keyframes pulse {{
      0% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
      100% {{ opacity: 1; transform: scale(1); }}
    }}

    .top-bar-right {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .search-box {{
      position: relative;
      width: 320px;
    }}

    .search-input {{
      width: 100%;
      background: var(--code-bg);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 6px 30px 6px 32px;
      border-radius: 6px;
      font-size: 0.82rem;
      outline: none;
      transition: all 0.2s;
    }}

    .search-input:focus {{
      border-color: var(--accent-cyan);
      box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
    }}

    .search-icon {{
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-muted);
      pointer-events: none;
      font-size: 0.8rem;
    }}

    .search-clear-btn {{
      position: absolute;
      right: 8px;
      top: 50%;
      transform: translateY(-50%);
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.85rem;
      padding: 2px;
    }}

    .search-clear-btn:hover {{
      color: #fff;
    }}

    .top-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .top-action-btn {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-secondary);
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }}

    .top-action-btn:hover {{
      background: var(--bg-card-hover);
      color: #fff;
      border-color: var(--accent-cyan);
    }}

    .top-action-btn.badge-green {{
      background: rgba(74, 222, 128, 0.12);
      border-color: rgba(74, 222, 128, 0.35);
      color: var(--accent-green);
    }}

    .top-action-btn.badge-green:hover {{
      background: var(--accent-green);
      color: #000;
    }}

    /* App Layout Container */
    .app-layout {{
      display: flex;
      min-height: calc(100vh - 56px);
    }}

    /* Left Sidebar */
    .left-sidebar {{
      width: 280px;
      flex-shrink: 0;
      position: sticky;
      top: 56px;
      height: calc(100vh - 56px);
      overflow-y: auto;
      background: rgba(13, 20, 36, 0.98);
      border-right: 1px solid var(--border-color);
      padding: 16px 12px 32px;
      transition: transform 0.25s ease, margin-left 0.25s ease;
    }}

    .left-sidebar::-webkit-scrollbar {{
      width: 5px;
    }}

    .left-sidebar::-webkit-scrollbar-thumb {{
      background: #223252;
      border-radius: 3px;
    }}

    .sidebar-group {{
      margin-bottom: 18px;
    }}

    .sidebar-group-title {{
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
      padding: 4px 10px 6px;
    }}

    .sidebar-link {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 7px 10px;
      border-radius: 6px;
      color: var(--text-secondary);
      font-size: 0.82rem;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
      border-left: 2px solid transparent;
      margin-bottom: 2px;
    }}

    .sidebar-link:hover {{
      background: var(--bg-card-hover);
      color: #fff;
    }}

    .sidebar-link.active {{
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-cyan);
      border-left: 2px solid var(--accent-cyan);
      font-weight: 600;
    }}

    .link-icon {{
      font-size: 0.95rem;
      width: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}

    .link-text {{
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .link-badge {{
      font-size: 0.7rem;
      font-family: var(--font-mono);
      background: rgba(148, 163, 184, 0.12);
      border: 1px solid rgba(148, 163, 184, 0.2);
      padding: 1px 6px;
      border-radius: 4px;
      color: var(--text-muted);
      white-space: nowrap;
    }}

    .link-badge.green {{
      background: rgba(74, 222, 128, 0.15);
      border-color: rgba(74, 222, 128, 0.35);
      color: var(--accent-green);
    }}

    .link-badge.cyan {{
      background: rgba(56, 189, 248, 0.15);
      border-color: rgba(56, 189, 248, 0.35);
      color: var(--accent-cyan);
    }}

    .link-badge.purple {{
      background: rgba(192, 132, 252, 0.15);
      border-color: rgba(192, 132, 252, 0.35);
      color: var(--accent-purple);
    }}

    .link-badge.amber {{
      background: rgba(251, 191, 36, 0.15);
      border-color: rgba(251, 191, 36, 0.35);
      color: var(--accent-amber);
    }}

    /* Main Workspace */
    .main-workspace {{
      flex: 1;
      min-width: 0;
      padding: 24px 32px 64px;
      max-width: 1440px;
    }}

    /* Responsive Sidebar Toggle */
    body.sidebar-collapsed .left-sidebar {{
      transform: translateX(-100%);
      margin-left: -280px;
    }}

    /* Category Section */
    .category-section {{
      margin-bottom: 48px;
    }}

    .section-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 2px solid var(--border-color);
      padding-bottom: 10px;
      margin-bottom: 18px;
    }}

    .section-title {{
      font-size: 1.35rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .section-tag {{
      font-size: 0.78rem;
      font-family: var(--font-mono);
      background: rgba(148, 163, 184, 0.1);
      border: 1px solid var(--border-color);
      padding: 2px 8px;
      border-radius: 4px;
      color: var(--text-muted);
    }}

    .card-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 16px;
    }}

    .card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 16px;
      transition: border-color 0.2s;
    }}

    .card:hover {{
      border-color: #3b4e72;
    }}

    .card.full-width {{
      grid-column: 1 / -1;
    }}

    .card-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }}

    .card-title {{
      font-size: 1.05rem;
      font-weight: 700;
      color: #fff;
    }}

    .card-desc {{
      color: var(--text-secondary);
      font-size: 0.88rem;
      line-height: 1.5;
      margin-bottom: 12px;
    }}

    /* Tags & Badges */
    .tag {{
      font-size: 0.72rem;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      display: inline-block;
    }}

    .tag-cyan {{ background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.3); }}
    .tag-green {{ background: rgba(74, 222, 128, 0.15); color: var(--accent-green); border: 1px solid rgba(74, 222, 128, 0.3); }}
    .tag-amber {{ background: rgba(251, 191, 36, 0.15); color: var(--accent-amber); border: 1px solid rgba(251, 191, 36, 0.3); }}
    .tag-purple {{ background: rgba(192, 132, 252, 0.15); color: var(--accent-purple); border: 1px solid rgba(192, 132, 252, 0.3); }}
    .tag-rose {{ background: rgba(251, 113, 133, 0.15); color: var(--accent-rose); border: 1px solid rgba(251, 113, 133, 0.3); }}
    .tag-blue {{ background: rgba(96, 165, 250, 0.15); color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.3); }}

    .addr-badge {{
      font-family: var(--font-mono);
      background: #090d16;
      border: 1px solid #334155;
      color: var(--accent-cyan);
      padding: 1px 6px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.78rem;
      transition: all 0.15s;
    }}

    .addr-badge:hover {{
      background: var(--accent-cyan);
      color: #000;
    }}

    /* High Density Tables */
    .table-container {{
      border: 1px solid var(--border-color);
      border-radius: 6px;
      background: var(--code-bg);
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
      text-align: left;
    }}

    th {{
      background: rgba(30, 41, 59, 0.8);
      color: var(--text-muted);
      font-weight: 600;
      padding: 8px 12px;
      border-bottom: 1px solid var(--border-color);
      white-space: nowrap;
    }}

    td {{
      padding: 7px 12px;
      border-bottom: 1px solid rgba(51, 65, 85, 0.4);
      color: var(--text-primary);
    }}

    tr:last-child td {{
      border-bottom: none;
    }}

    tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
    }}

    /* Interactive Character Action Studio */
    .studio-selector-bar {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 6px 2px 10px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 14px;
    }}

    .char-chip {{
      background: #090d16;
      border: 1px solid var(--border-color);
      color: var(--text-secondary);
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }}

    .char-chip:hover {{
      border-color: var(--accent-cyan);
      color: #fff;
    }}

    .char-chip.active {{
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.25);
    }}

    .studio-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      background: rgba(9, 13, 22, 0.6);
      padding: 10px 14px;
      border-radius: 8px;
      margin-bottom: 14px;
      border: 1px solid var(--border-color);
    }}

    .studio-char-name {{
      font-size: 1.25rem;
      font-weight: 800;
      color: #fff;
    }}

    .studio-char-en {{
      font-size: 0.88rem;
      color: var(--text-muted);
      font-weight: 400;
      margin-left: 6px;
    }}

    .studio-char-meta {{
      display: flex;
      gap: 16px;
      font-size: 0.8rem;
      color: var(--text-secondary);
      margin-top: 4px;
      flex-wrap: wrap;
    }}

    .studio-body {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 16px;
    }}

    @media (max-width: 960px) {{
      .studio-body {{
        grid-template-columns: 1fr;
      }}
    }}

    .studio-pane-title {{
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text-secondary);
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .studio-act-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(105px, 1fr));
      gap: 10px;
    }}

    .studio-act-card {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 8px 6px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s;
    }}

    .studio-act-card:hover {{
      border-color: var(--accent-cyan);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }}

    .studio-act-title {{
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--accent-cyan);
      margin-bottom: 6px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .studio-act-img-wrap {{
      height: 72px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: radial-gradient(circle, #1a253c 0%, #090d16 100%);
      border-radius: 6px;
    }}

    .studio-portrait-list {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      gap: 10px;
    }}

    .studio-portrait-card {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 8px 6px;
      text-align: center;
      transition: all 0.2s;
    }}

    .studio-portrait-card:hover {{
      border-color: var(--accent-amber);
    }}

    .studio-portrait-img {{
      width: 64px;
      height: 64px;
      margin: 0 auto 6px;
      background: #000;
      border-radius: 4px;
      overflow: hidden;
      border: 1px solid #334155;
    }}

    .studio-portrait-name {{
      font-size: 0.75rem;
      font-weight: 700;
      color: #fff;
    }}

    .studio-portrait-sub {{
      font-size: 0.68rem;
      color: var(--text-muted);
    }}

    .studio-portrait-addr {{
      margin-top: 4px;
    }}

    .studio-strip-preview {{
      margin-top: 14px;
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px;
    }}

    .studio-strip-img-wrap {{
      background: #000;
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 8px;
      overflow-x: auto;
      text-align: center;
    }}

    /* Accordion details */
    details {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 6px;
      padding: 8px 12px;
    }}

    summary {{
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--accent-cyan);
      cursor: pointer;
      outline: none;
    }}

    .details-body {{
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid rgba(51, 65, 85, 0.4);
    }}

    /* Tileset Gallery */
    .tileset-gallery {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 14px;
    }}

    .tileset-item {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 10px;
    }}

    .tileset-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 0.85rem;
    }}

    .tileset-img-wrap {{
      background: #000;
      border: 1px solid #334155;
      border-radius: 4px;
      padding: 6px;
      text-align: center;
      overflow-x: auto;
      margin-bottom: 6px;
    }}

    .tileset-img-wrap img {{
      image-rendering: pixelated;
      max-width: 100%;
      height: auto;
    }}

    .tileset-meta {{
      font-size: 0.72rem;
      color: var(--text-muted);
      font-family: var(--font-mono);
    }}

    /* Pipeline Diagram */
    .pipeline-diagram {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 14px;
    }}

    .flow-steps {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .flow-node {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      padding: 10px 14px;
      flex: 1;
      min-width: 170px;
      text-align: center;
    }}

    .flow-node .node-title {{
      font-size: 0.82rem;
      font-weight: 700;
      color: #fff;
    }}

    .flow-node .node-addr {{
      font-family: var(--font-mono);
      font-size: 0.75rem;
      color: var(--accent-cyan);
      margin: 4px 0;
      cursor: pointer;
    }}

    .flow-node .node-desc {{
      font-size: 0.72rem;
      color: var(--text-muted);
    }}

    .flow-arrow {{
      color: var(--accent-cyan);
      font-weight: 800;
      font-size: 1.1rem;
    }}

    /* Item Category Grid */
    .item-category-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
    }}

    .item-cat-box {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px;
    }}

    .item-cat-title {{
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--accent-amber);
      margin-bottom: 8px;
    }}

    .item-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}

    .item-pill {{
      background: rgba(148, 163, 184, 0.08);
      border: 1px solid var(--border-color);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      color: var(--text-secondary);
    }}

    /* Dedicated Progress Hub CSS */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 12px;
    }}

    .kpi-card {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      transition: all 0.2s;
    }}

    .kpi-card:hover {{
      border-color: var(--accent-cyan);
      transform: translateY(-2px);
    }}

    .kpi-title {{
      font-size: 0.74rem;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--text-muted);
    }}

    .kpi-num {{
      font-size: 1.4rem;
      font-weight: 800;
      font-family: var(--font-mono);
      color: #fff;
      margin: 4px 0 2px;
    }}

    .kpi-num.cyan {{ color: var(--accent-cyan); }}
    .kpi-num.green {{ color: var(--accent-green); }}
    .kpi-num.amber {{ color: var(--accent-amber); }}
    .kpi-num.purple {{ color: var(--accent-purple); }}
    .kpi-num.rose {{ color: var(--accent-rose); }}

    .kpi-sub {{
      font-size: 0.72rem;
      color: var(--text-secondary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    /* Phase Progress Bars */
    .phase-progress-list {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}

    .phase-item {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px 16px;
    }}

    .phase-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }}

    .phase-name {{
      font-size: 0.88rem;
      color: #fff;
    }}

    .phase-percent {{
      font-size: 0.82rem;
      font-weight: 700;
      font-family: var(--font-mono);
    }}

    .phase-percent.green {{ color: var(--accent-green); }}
    .phase-percent.amber {{ color: var(--accent-amber); }}
    .phase-percent.purple {{ color: var(--accent-purple); }}
    .phase-percent.cyan {{ color: var(--accent-cyan); }}

    .progress-bar-bg {{
      width: 100%;
      height: 7px;
      background: rgba(30, 41, 59, 0.8);
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 6px;
    }}

    .progress-bar-fill {{
      height: 100%;
      border-radius: 4px;
      transition: width 0.4s ease;
    }}

    .progress-bar-fill.green {{ background: linear-gradient(90deg, #10b981, #4ade80); }}
    .progress-bar-fill.amber {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
    .progress-bar-fill.purple {{ background: linear-gradient(90deg, #8b5cf6, #c084fc); }}
    .progress-bar-fill.cyan {{ background: linear-gradient(90deg, #0284c7, #38bdf8); }}

    .phase-desc {{
      font-size: 0.78rem;
      color: var(--text-secondary);
    }}

    /* ROM Topology Visualizer */
    .rom-bar-container {{
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
    }}

    .rom-bar-visual {{
      display: flex;
      height: 28px;
      border-radius: 6px;
      overflow: hidden;
      margin-bottom: 14px;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }}

    .rom-chunk {{
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.72rem;
      font-weight: 700;
      color: #fff;
      text-shadow: 0 1px 2px rgba(0,0,0,0.8);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      padding: 0 4px;
    }}

    .rom-chunk.code {{ background: #2563eb; }}
    .rom-chunk.audio {{ background: #059669; }}
    .rom-chunk.gfx {{ background: #d97706; }}
    .rom-chunk.script {{ background: #7c3aed; }}
    .rom-chunk.anim {{ background: #db2777; }}
    .rom-chunk.free {{ background: #0891b2; box-shadow: inset 0 0 8px rgba(255,255,255,0.4); }}

    .rom-bar-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      font-size: 0.78rem;
      color: var(--text-secondary);
    }}

    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 2px;
      display: inline-block;
    }}
  </style>
</head>
<body>

  <div id="toast">已复制</div>

  <!-- Top Bar -->
  <header class="top-bar">
    <div class="top-bar-left">
      <button class="sidebar-toggle-btn" onclick="toggleSidebar()" title="折叠/展开侧边栏">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>
      <div class="top-bar-brand">
        <span class="brand-badge">GBA</span>
        <span class="brand-title">火影忍者：木叶战记 · 逆向工程研发控制台</span>
      </div>
      <div class="rom-status-tag">
        <span class="pulse-dot"></span>
        <span>ROM v1.3 (简)(JP) 48Mb · 校验通过</span>
      </div>
    </div>

    <div class="top-bar-right">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" class="search-input" placeholder="全局检索地址/角色/技能/道具/函数 (Ctrl+K)..." oninput="handleSearch()">
        <button class="search-clear-btn" id="searchClearBtn" onclick="clearSearch()" style="display:none;" title="清空检索">✕</button>
      </div>
      <div class="top-actions">
        <button class="top-action-btn badge-green" onclick="switchHub('progress', 'sec-progress-tests')" title="查看 17 项自动化回归测试详情">
          ✓ 17/17 测试通过
        </button>
        <button class="top-action-btn" onclick="copyCurrentUrl()" title="复制本页面分享链接">
          🔗 分享
        </button>
      </div>
    </div>
  </header>

  <!-- App Layout Container -->
  <div class="app-layout">
    <!-- Left Sidebar -->
    <aside class="left-sidebar" id="leftSidebar">
      <nav class="sidebar-nav">
        
        <!-- Group: 研发全景 -->
        <div class="sidebar-group">
          <div class="sidebar-group-title">研发全景</div>
          <a class="sidebar-link active" data-hub="progress" onclick="switchHub('progress')">
            <span class="link-icon">📈</span>
            <span class="link-text">研发进度与看板</span>
            <span class="link-badge green">100% P0</span>
          </a>
        </div>

        <!-- Group: 1. 视觉与动画资产库 -->
        <div class="sidebar-group">
          <div class="sidebar-group-title">1. 视觉与动画资产库</div>
          <a class="sidebar-link" data-hub="visuals" data-anchor="sec-studio" onclick="switchHub('visuals', 'sec-studio')">
            <span class="link-icon">🕹️</span>
            <span class="link-text">角色动作研发展示台</span>
            <span class="link-badge cyan">19角色</span>
          </a>
          <a class="sidebar-link" data-hub="visuals" data-anchor="sec-action-matrix" onclick="switchHub('visuals', 'sec-action-matrix')">
            <span class="link-icon">📋</span>
            <span class="link-text">35角色动作状态矩阵</span>
            <span class="link-badge">1,500+帧</span>
          </a>
          <a class="sidebar-link" data-hub="visuals" data-anchor="sec-portraits-poster" onclick="switchHub('visuals', 'sec-portraits-poster')">
            <span class="link-icon">🎭</span>
            <span class="link-text">155款忍术立绘海报</span>
            <span class="link-badge">8bpp</span>
          </a>
          <a class="sidebar-link" data-hub="visuals" data-anchor="sec-roster-poster" onclick="switchHub('visuals', 'sec-roster-poster')">
            <span class="link-icon">👥</span>
            <span class="link-text">35角色精灵全家福</span>
            <span class="link-badge">全员</span>
          </a>
          <a class="sidebar-link" data-hub="visuals" data-anchor="sec-tilesets" onclick="switchHub('visuals', 'sec-tilesets')">
            <span class="link-icon">🗺️</span>
            <span class="link-text">8大战役地图 Tileset</span>
            <span class="link-badge">4bpp</span>
          </a>
        </div>

        <!-- Group: 2. 战斗系统与时序引擎 -->
        <div class="sidebar-group">
          <div class="sidebar-group-title">2. 战斗系统与时序引擎</div>
          <a class="sidebar-link" data-hub="battle" data-anchor="sec-battle-vm" onclick="switchHub('battle', 'sec-battle-vm')">
            <span class="link-icon">⚡</span>
            <span class="link-text">忍术字节码 VM 规范</span>
            <span class="link-badge purple">8大指令</span>
          </a>
          <a class="sidebar-link" data-hub="battle" data-anchor="sec-battle-scripts" onclick="switchHub('battle', 'sec-battle-scripts')">
            <span class="link-icon">📜</span>
            <span class="link-text">36项忍术动作脚本表</span>
            <span class="link-badge">全检索</span>
          </a>
          <a class="sidebar-link" data-hub="battle" data-anchor="sec-scenario-fsm" onclick="switchHub('battle', 'sec-scenario-fsm')">
            <span class="link-icon">🛡️</span>
            <span class="link-text">32字节战场配置与状态机</span>
            <span class="link-badge amber">8大场景</span>
          </a>
        </div>

        <!-- Group: 3. 剧情调度与文本系统 -->
        <div class="sidebar-group">
          <div class="sidebar-group-title">3. 剧情调度与文本系统</div>
          <a class="sidebar-link" data-hub="story" data-anchor="sec-dialogue-pipeline" onclick="switchHub('story', 'sec-dialogue-pipeline')">
            <span class="link-icon">🖥️</span>
            <span class="link-text">GBA 文本渲染全链路</span>
            <span class="link-badge">BG3</span>
          </a>
          <a class="sidebar-link" data-hub="story" data-anchor="sec-dialogue-asm" onclick="switchHub('story', 'sec-dialogue-asm')">
            <span class="link-icon">⚙️</span>
            <span class="link-text">核心文本汇编与关卡控制</span>
            <span class="link-badge">WRAM</span>
          </a>
          <a class="sidebar-link" data-hub="story" data-anchor="sec-free-space-pipe" onclick="switchHub('story', 'sec-free-space-pipe')">
            <span class="link-icon">📦</span>
            <span class="link-text">128KB 动态扩容管道</span>
            <span class="link-badge green">Free Space</span>
          </a>
        </div>

        <!-- Group: 4. 内存数据与音频架构 -->
        <div class="sidebar-group">
          <div class="sidebar-group-title">4. 内存数据与音频架构</div>
          <a class="sidebar-link" data-hub="data" data-anchor="sec-unit-struct" onclick="switchHub('data', 'sec-unit-struct')">
            <span class="link-icon">🧬</span>
            <span class="link-text">单位 ID 映射与战斗阵列</span>
            <span class="link-badge">64单元</span>
          </a>
          <a class="sidebar-link" data-hub="data" data-anchor="sec-item-matrix" onclick="switchHub('data', 'sec-item-matrix')">
            <span class="link-icon">🎒</span>
            <span class="link-text">80+ 种忍具道具分类矩阵</span>
            <span class="link-badge amber">9大类</span>
          </a>
          <a class="sidebar-link" data-hub="data" data-anchor="sec-audio-pcm" onclick="switchHub('data', 'sec-audio-pcm')">
            <span class="link-icon">🎵</span>
            <span class="link-text">DirectSound PCM 原生音频</span>
            <span class="link-badge green">10 WAV</span>
          </a>
        </div>

        <!-- Group: 5. 逆向基建与工程流水线 -->
        <div class="sidebar-group">
          <div class="sidebar-group-title">5. 逆向基建与工程流水线</div>
          <a class="sidebar-link" data-hub="engineering" data-anchor="sec-mod-builder" onclick="switchHub('engineering', 'sec-mod-builder')">
            <span class="link-icon">🔨</span>
            <span class="link-text">build_mod 补丁流水线</span>
            <span class="link-badge">6种补丁</span>
          </a>
          <a class="sidebar-link" data-hub="engineering" data-anchor="sec-auto-tests" onclick="switchHub('engineering', 'sec-auto-tests')">
            <span class="link-icon">🧪</span>
            <span class="link-text">17项自动化回归测试</span>
            <span class="link-badge green">17/17 PASS</span>
          </a>
          <a class="sidebar-link" data-hub="engineering" data-anchor="sec-toolbox-index" onclick="switchHub('engineering', 'sec-toolbox-index')">
            <span class="link-icon">🧰</span>
            <span class="link-text">自研逆向工具箱清单</span>
            <span class="link-badge">7大工具</span>
          </a>
        </div>

        <!-- Group: 平铺模式 -->
        <div class="sidebar-group" style="margin-top: 16px; border-top: 1px solid var(--border-color); padding-top: 12px;">
          <a class="sidebar-link" data-hub="all" onclick="switchHub('all')">
            <span class="link-icon">🌐</span>
            <span class="link-text">平铺查看所有模块</span>
          </a>
        </div>
      </nav>
    </aside>

    <!-- Main Workspace -->
    <main class="main-workspace" id="mainWorkspace">
      {hub_progress}
      {hub_visuals}
      {hub_battle}
      {hub_story}
      {hub_data}
      {hub_engineering}
    </main>
  </div>

  <script>
    const STUDIO_DATA = {studio_data_json};

    function copyAddr(addr) {{
      navigator.clipboard.writeText(addr);
      const toast = document.getElementById('toast');
      toast.textContent = '已复制: ' + addr;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 1800);
    }}

    function copyCurrentUrl() {{
      navigator.clipboard.writeText(window.location.href);
      const toast = document.getElementById('toast');
      toast.textContent = '已复制控制台页面链接';
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 1800);
    }}

    function toggleSidebar() {{
      document.body.classList.toggle('sidebar-collapsed');
    }}

    let currentActiveHub = 'progress';

    function switchHub(hubId, targetAnchor) {{
      currentActiveHub = hubId;
      document.getElementById('searchInput').value = '';
      document.getElementById('searchClearBtn').style.display = 'none';

      // Update sidebar active link
      document.querySelectorAll('.sidebar-link').forEach(link => {{
        const linkHub = link.getAttribute('data-hub');
        const linkAnchor = link.getAttribute('data-anchor');
        if (targetAnchor && linkAnchor === targetAnchor) {{
          link.classList.add('active');
        }} else if (!targetAnchor && linkHub === hubId && !linkAnchor) {{
          link.classList.add('active');
        }} else {{
          link.classList.remove('active');
        }}
      }});

      // Show/hide section hubs
      const sections = document.querySelectorAll('.category-section');
      sections.forEach(sec => {{
        const cat = sec.getAttribute('data-category');
        if (hubId === 'all' || cat === hubId) {{
          sec.style.display = 'block';
        }} else {{
          sec.style.display = 'none';
        }}
        // Restore all cards inside
        sec.querySelectorAll('.card').forEach(c => c.style.display = '');
      }});

      // If anchor specified, scroll into view
      if (targetAnchor) {{
        setTimeout(() => {{
          const el = document.getElementById(targetAnchor);
          if (el) {{
            el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
          }}
        }}, 50);
      }} else {{
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }}
    }}

    function clearSearch() {{
      document.getElementById('searchInput').value = '';
      document.getElementById('searchClearBtn').style.display = 'none';
      switchHub(currentActiveHub);
    }}

    function handleSearch() {{
      const query = document.getElementById('searchInput').value.trim().toLowerCase();
      const clearBtn = document.getElementById('searchClearBtn');
      const sections = document.querySelectorAll('.category-section');

      if (!query) {{
        clearBtn.style.display = 'none';
        switchHub(currentActiveHub);
        return;
      }}

      clearBtn.style.display = 'block';

      // In search mode, search across all sections
      sections.forEach(sec => {{
        let secHasMatch = false;
        const cards = sec.querySelectorAll('.card');

        cards.forEach(card => {{
          const text = card.textContent.toLowerCase();
          if (text.includes(query)) {{
            card.style.display = '';
            secHasMatch = true;
          }} else {{
            card.style.display = 'none';
          }}
        }});

        sec.style.display = secHasMatch ? 'block' : 'none';
      }});
    }}

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {{
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{
        e.preventDefault();
        document.getElementById('searchInput').focus();
      }} else if (e.key === 'Escape' && document.activeElement === document.getElementById('searchInput')) {{
        clearSearch();
        document.getElementById('searchInput').blur();
      }}
    }});

    function selectStudioChar(charId) {{
      const data = STUDIO_DATA[charId];
      if (!data) return;

      document.querySelectorAll('.char-chip').forEach(btn => btn.classList.remove('active'));
      const activeBtn = document.querySelector(`.char-chip[onclick*="selectStudioChar(${{charId}})"]`);
      if (activeBtn) activeBtn.classList.add('active');

      const vp = document.getElementById('studioViewport');
      const actionNames = {{
        "locomotion": "四向位移步态",
        "attack1": "普攻连击 (Combo)",
        "attack2": "重击击退 (Strike)",
        "charge": "结印蓄力 (Chakra)",
        "cast": "奥义释放 (Jutsu)",
        "victory": "胜利姿态 (Victory)",
        "hurt": "受创击退 (Hurt)",
        "guard": "防御格挡 (Guard)",
        "defeat": "倒地击溃 (Defeat)"
      }};

      let actionCardsHtml = '';
      for (const [k, name] of Object.entries(actionNames)) {{
        const act = data.actions[k];
        if (act) {{
          const p = act.gif_path || act.strip_path;
          actionCardsHtml += `
            <div class="studio-act-card" onclick="viewActionStrip('${{act.strip_path}}', '${{name}}')">
              <div class="studio-act-title">${{name}} (${{act.frames_count}}帧)</div>
              <div class="studio-act-img-wrap">
                <img src="../${{p}}" alt="${{name}}" style="image-rendering:pixelated; max-width:64px; max-height:64px;">
              </div>
            </div>`;
        }}
      }}

      let portraitsHtml = '';
      if (data.portraits && data.portraits.length > 0) {{
        for (const p of data.portraits) {{
          portraitsHtml += `
            <div class="studio-portrait-card">
              <div class="studio-portrait-img">
                <img src="../${{p.file_path}}" alt="${{p.zh_title}}" style="image-rendering:pixelated; width:64px; height:64px;">
              </div>
              <div class="studio-portrait-name">${{p.zh_title}}</div>
              <div class="studio-portrait-sub">${{p.en_title}}</div>
              <div class="studio-portrait-addr"><code class="addr-badge" onclick="copyAddr('${{p.c0_ptr}}')">${{p.c0_ptr}}</code></div>
            </div>`;
        }}
      }} else {{
        portraitsHtml = '<div style="color:var(--text-muted); font-size:0.8rem; padding:8px;">共享基础战斗头像</div>';
      }}

      vp.innerHTML = `
        <div class="studio-header">
          <div class="studio-char-info">
            <div class="studio-char-name">${{data.zh_name}} <span class="studio-char-en">${{data.en_name}}</span></div>
            <div class="studio-char-meta">
              <span>角色编号: <strong>#${{data.id < 10 ? '0' + data.id : data.id}}</strong></span>
              <span>描述表起始行: <strong>${{data.start_row}}</strong></span>
              <span>调色板地址: <code class="addr-badge" onclick="copyAddr('${{data.pal_offset}}')">${{data.pal_offset}}</code></span>
            </div>
          </div>
          <div>
            <a href="../${{data.matrix_sheet}}" target="_blank" class="tag tag-cyan" style="text-decoration:none; font-size:0.8rem;">查看全套动作图谱 ↗</a>
          </div>
        </div>

        <div class="studio-body">
          <div class="studio-actions-pane">
            <div class="studio-pane-title">🎮 9 大行动状态循环动图 (点击查看完整切片)</div>
            <div class="studio-act-grid">
              ${{actionCardsHtml}}
            </div>
          </div>
          <div class="studio-portraits-pane">
            <div class="studio-pane-title">🎭 高精特写立绘与剧情表情 (8bpp 64色)</div>
            <div class="studio-portrait-list">
              ${{portraitsHtml}}
            </div>
          </div>
        </div>

        <div class="studio-strip-preview" id="studioStripPreview" style="display:none;">
          <div class="studio-pane-title" id="stripPreviewTitle">动作切片预览</div>
          <div class="studio-strip-img-wrap">
            <img id="stripPreviewImg" src="" style="image-rendering:pixelated; max-width:100%; height:auto;">
          </div>
        </div>
      `;
    }}

    function viewActionStrip(stripPath, actionName) {{
      const box = document.getElementById('studioStripPreview');
      const img = document.getElementById('stripPreviewImg');
      const title = document.getElementById('stripPreviewTitle');
      if (box && img && title) {{
        box.style.display = 'block';
        img.src = '../' + stripPath;
        title.textContent = '动作完整帧切片: ' + actionName;
        box.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
      }}
    }}

    // Initialize with Progress View & Naruto
    window.addEventListener('DOMContentLoaded', () => {{
      switchHub('progress');
      selectStudioChar(0);
    }});
  </script>
</body>
</html>
"""
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"Generated Consolidated HTML report with Top/Sidebar layout at: {OUTPUT_HTML} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
