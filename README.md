# Naruto Konoha Senki Sequel Workspace

- Title: `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba`
- Internal ROM title: `NARUTOKONOHA`
- Game code: `AUEJ`
- ROM size: `0x600000` bytes (`48 Mbit / 6 MiB`)
- SHA-1: `26f60795fa5e63b4f0264b84e453beffd56b9f7d`

## Overview

This repository contains the reverse-engineering and sequel-development workspace for the GBA game "Naruto: Konoha Senki Sequel" (木叶战记).

The goal is to transform ROM reverse-engineering work into a repeatable sequel-development workspace with:

- persistent project memory in-repo
- content authoring files
- a reproducible ROM build entrypoint
- reverse-engineering notes tied to actual files and addresses

## Prerequisites

- Python 3.8+
- `python3`: available
- local scripted `mGBA` build: available
- headless/offscreen automation: available
- OCR helper: available

## Quick Start

```bash
# Check project status
python3 tools/project_status.py

# Build the modded ROM
python3 tools/build_mod.py

# Import dialogue/content
python3 tools/import_dialogue.py
python3 tools/import_map.py sequel/content/maps/episode-01-mountain-pass.json
python3 tools/import_battle_config.py

# Run automated tests
python3 tools/automated_test.py

# Run headless trace
NARUTO_TRACE_TARGET=wram tools/run_headless_mgba.sh tools/mgba_trace_dialogue_writes.lua build/naruto-sequel-dev.gba
```

## Web Editor

A web-based dialogue editor is provided in `web-editor/`.

```bash
cd web-editor/backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `web-editor/frontend/` in a browser to use the editor.

## Documents

- `docs/rom-sequel-plan.md`: product, scope, and implementation strategy
- `docs/reverse-engineering-roadmap.md`: ROM analysis and reverse-engineering workflow
- `docs/sequel-authoring-workspace.md`: how sequel content and ROM builds are organized
- `docs/development-status.md`: current practical development status
- `docs/build-pipeline.md`: current content import/build pipeline

## Primary Working Files

- `sequel/project.json`
- `sequel/patches/manifest.json`
- `sequel/content/`
- `notes/debugging-record.md`
- `notes/dialogue-memory-analysis.md`
- `notes/dialogue-render-analysis.md`
- `notes/dialogue-write-path.md`
- `notes/dialogue-writer-addresses.md`
- `notes/dialogue-function-analysis.md`
- `notes/dialogue-ram-structures.md`

## Generated ROM Build

- `build/naruto-sequel-dev.gba`
