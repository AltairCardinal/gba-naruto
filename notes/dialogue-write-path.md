# Dialogue Write Path

## Scope

This note records the first stable write-path capture for the opening dialogue scene.

Runtime method:

- binary: local scripted `mGBA` Qt build
- launcher: `tools/run_headless_mgba.sh`
- mode: offscreen + silent
- script: `tools/mgba_trace_dialogue_writes.lua`

Reference logs:

- `notes/dialogue-watch-wram.log`
- `notes/dialogue-watch-vram-tilemap.log`
- `notes/dialogue-watch-vram-glyph.log`

Reference summaries:

- `notes/dialogue-watch-wram.md`
- `notes/dialogue-watch-vram-tilemap.md`
- `notes/dialogue-watch-vram-glyph.md`

## Result

The dialogue renderer now has three separately observed write paths:

1. `WRAM 0x0200A900-0x0200AA4A`
2. `VRAM 0x06001800-0x06002000`
3. `VRAM 0x06002000-0x06002800`

These do **not** behave like a single writer.

## 1. Dialogue work buffer writer

Target:

- `WRAM 0x0200A900-0x0200AA4A`

Stable capture:

- first hit frame: `1605`
- hit width: `16-bit`
- stable PC: `0x08066D74`
- actual write instruction: `0x08066D70: strh r0, [r4]`
- dominant LR: `0x08066D67`
- early LR variant: `0x08066D23`

Interpretation:

- this is the first confirmed CPU-side writer for the dialogue work buffer
- it writes a dense run of halfwords starting at `0x0200A900`
- this is consistent with generating or clearing the `BG3` tilemap work area in WRAM

## 2. Dialogue tilemap copy into BG3 screen block

Target:

- `VRAM 0x06001800-0x06002000`

Stable capture:

- first hit frame: `1607`
- hit width: `16-bit`
- reported PC: `0x000002A0`
- reported LR: `0x000000A4`
- first captured addresses begin at `0x06001B00`

Interpretation:

- this does not look like a normal CPU code address inside ROM
- combined with the address pattern and the earlier `BG3 screen base = 0x1800` finding, this is the strongest evidence yet that the `WRAM` dialogue tilemap is copied into `BG3` through a DMA or other non-program access path
- in practical terms: `VRAM 0x1B00+` is the live dialogue tilemap destination, but the authoring-friendly edit point is still upstream in the WRAM-side buffer or the dialogue decoder

## 3. Dialogue glyph upload writer

Target:

- `VRAM 0x06002000-0x06002800`

Stable capture:

- first hit frame: `1605`
- hit width: `16-bit`
- stable PC: `0x08065F50`
- actual write instruction: `0x08065F4C: strh r1, [r3]`
- stable LR: `0x08065EDF`
- first captured writes begin at `0x06002600`

Interpretation:

- this is the first confirmed CPU-side writer for dialogue glyph/tile graphics upload
- the target range matches the previously observed `VRAM 0x2000+` hotspot
- this path is separate from the tilemap copy and should be treated as the glyph renderer / tile uploader side of the dialogue system

## Working Model

The opening dialogue path is now best described as:

1. dialogue logic writes or refreshes a tilemap-like work buffer in `WRAM 0x0200A900+`
2. that tilemap is copied into `BG3` screen block memory near `VRAM 0x06001B00+`
3. glyph tiles are uploaded separately into `VRAM 0x06002600+`

This is enough to split future reverse engineering into two focused tracks:

- upstream text/data decoding into the WRAM work buffer
- glyph generation/upload into `VRAM 0x2000+`

Disassembly reference:

- `notes/dialogue-function-analysis.md`

## Phase Status

Phase 1 completion criteria from `docs/sequel-roadmap.md` are now met at a practical level:

- stable writer addresses were captured
- tilemap update and glyph upload are now distinguishable behaviors

The next highest-value step is Phase 2:

- walk backward from `0x08066D74`
- determine where its input line data comes from
- confirm whether the source is a script command stream, a pointer table, or a custom encoded text block
