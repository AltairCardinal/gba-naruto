# Content Pipeline

## Overview

The sequel content pipeline converts high-level authoring content into ROM patches through a structured manifest system.

## Pipeline Flow

```
sequel/content/
  └── text/
      └── dialogue-bank.json     # ROM source locations
      └── dialogue-patches.json # New content (author writes here)
  └── story/
      └── episode-01.json      # Story structure
  └── maps/
      └── episode-01-mountain-pass.json
  └── units/
      └── sequel-units.json

         ↓ import_dialogue.py / import_map.py / import_battle_config.py

sequel/patches/manifest.json   # Patch manifest (references content)

         ↓ build_mod.py

build/naruto-sequel-dev.gba   # Development ROM
```

## Patch Types

| Type | Source | Build Support |
|------|--------|---------------|
| `bytes` | Direct hex patch | ✓ Always |
| `dialogue` | `dialogue-patches.json` | ✓ |
| `pointer_redirect` | Variable-length text | ✓ Framework |
| `map` | `episode-*-*.json` | ✓ Framework |
| `battle_config` | `story/` + `units/` | ✓ Framework |

## Adding New Dialogue

1. Add entry to `sequel/content/text/dialogue-bank.json`:
   - `id`: unique identifier
   - `offset`: ROM file offset
   - `max_bytes`: max encoded length
   - `expected_hex`: current ROM bytes (for verification)
   - `encoding`: `cp932`

2. Add content to `sequel/content/text/dialogue-patches.json`:
   ```json
   {
     "id": "my_entry_id",
     "text": "新对话文本内容。"
   }
   ```

3. Add manifest entry in `sequel/patches/manifest.json`:
   ```json
   {
     "id": "dialogue_my_entry",
     "type": "dialogue",
     "enabled": true,
     "bank": "sequel/content/text/dialogue-bank.json",
     "content": "sequel/content/text/dialogue-patches.json",
     "entry_id": "my_entry_id"
   }
   ```

4. Run: `python3 tools/build_mod.py`

## Content Rules

- All dialogue text must encode in cp932 (Shift-JIS)
- New text longer than `max_bytes` requires `redirect_offset` in bank entry
- Variable-length text redirect requires verified free ROM space
- All patches must have `enabled: true` in manifest to apply
- Build verifies base ROM sha1 before applying patches
