# Naruto Konoha Senki Sequel Workspace

This repository currently contains the Chinese-patched GBA ROM for:

- Title: `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba`
- Internal ROM title: `NARUTOKONOHA`
- Game code: `AUEJ`
- ROM size: `0x600000` bytes (`48 Mbit / 6 MiB`)
- SHA-1: `26f60795fa5e63b4f0264b84e453beffd56b9f7d`

The current goal is to turn the ROM reverse-engineering work into a repeatable sequel-development workspace with:

- persistent project memory in-repo
- content authoring files
- a reproducible ROM build entrypoint
- reverse-engineering notes tied to actual files and addresses

Documents:

- `docs/rom-sequel-plan.md`: product, scope, and implementation strategy
- `docs/reverse-engineering-roadmap.md`: ROM analysis and reverse-engineering workflow
- `docs/sequel-authoring-workspace.md`: how sequel content and ROM builds are organized
- `docs/development-status.md`: current practical development status
- `docs/build-pipeline.md`: current content import/build pipeline

Primary working files:

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

Current local environment status:

- `python3`: available
- local scripted `mGBA` build: available
- headless/offscreen automation: available
- OCR helper: available
- ROM build script: available

Useful commands:

```bash
python3 tools/project_status.py
python3 tools/build_mod.py
python3 tools/import_dialogue.py
python3 tools/import_map.py sequel/content/maps/episode-01-mountain-pass.json
python3 tools/import_battle_config.py
python3 tools/ocr_report.py 'notes/newgame-*.png' --output notes/ocr-newgame-report.md
NARUTO_TRACE_TARGET=wram tools/run_headless_mgba.sh tools/mgba_trace_dialogue_writes.lua build/naruto-sequel-dev.gba
```

Generated ROM build:

- `build/naruto-sequel-dev.gba`
