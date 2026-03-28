# Dialogue Writer Addresses

## Confirmed Targets

### WRAM dialogue work buffer

- watch range: `0x0200A900-0x0200AA4A`
- stable writer PC: `0x08066D74`
- observed caller LRs:
  - `0x08066D67`
  - `0x08066D23`
- first observed frame: `1605`
- evidence:
  - `notes/dialogue-watch-wram.log`
  - `notes/dialogue-watch-wram.md`

### VRAM BG3 tilemap destination

- watch range: `0x06001800-0x06002000`
- effective destination hotspot:
  - `0x06001B00+`
  - earlier diff correlation also pointed to `0x06001B0A`, `0x06001B12`, `0x06001B0E`
- reported watchpoint PC: `0x000002A0`
- reported LR: `0x000000A4`
- first observed frame: `1607`
- interpretation:
  - likely DMA or another non-standard program access path rather than a normal ROM-side CPU instruction stream
- evidence:
  - `notes/dialogue-watch-vram-tilemap.log`
  - `notes/dialogue-watch-vram-tilemap.md`

### VRAM glyph upload

- watch range: `0x06002000-0x06002800`
- first captured destination region:
  - `0x06002600+`
- stable writer PC: `0x08065F50`
- stable caller LR: `0x08065EDF`
- first observed frame: `1605`
- evidence:
  - `notes/dialogue-watch-vram-glyph.log`
  - `notes/dialogue-watch-vram-glyph.md`

## Immediate Reverse-Engineering Priorities

1. Treat `0x08066D74` as the primary entry for tracing dialogue line materialization into the WRAM tilemap buffer.
2. Treat `0x08065F50` as the primary entry for tracing glyph/tile upload behavior.
3. Treat the `VRAM 0x06001B00+` path as a downstream copy stage, not the best first point for dialogue authoring.
