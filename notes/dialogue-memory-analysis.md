# Dialogue Memory Analysis

## Scope

This note captures the first useful result from the headless dialogue snapshot pipeline:

- `notes/dialogue-2160.png`
- `notes/dialogue-2340.png`
- `notes/dialogue-2520.png`
- `notes/dialogue-2700.png`
- matching `WRAM/IWRAM/VRAM` binary dumps

The screenshots come from opening dialogue lines that OCR recognizes as:

- frame `2160`: `“是啊。是我这个班主任所承认的嘛！”`
- frame `2340`: `“你已经从忍者学校率业。`
- frame `2520`: `…成了木叶村里优秀的忍者了！`
- frame `2700`: `“伊鲁卡老师！我有一个请求….`

## Main Findings

### 1. No direct text encoding hit in RAM

Searches against `WRAM` and `IWRAM` found no direct matches for visible dialogue strings in these encodings:

- `utf-8`
- `utf-16le`
- `utf-16be`
- `gbk`
- `gb18030`
- `big5`
- `cp932`
- `shift_jis`

This strongly suggests the active dialogue line is **not** stored in RAM as a normal encoded text string.

### 2. WRAM hotspot changes in a tight band

Diffing dialogue frames isolates one very small changing region:

- `WRAM 0x00A900-0x00AA4A`

Relevant reports:

- `notes/diff-dialogue-2160-2340-wram.md`
- `notes/diff-dialogue-2340-2520-wram.md`

The changes are sparse and 16-bit aligned, e.g.:

- `0xA904: 30 -> 24`
- `0xA906: 32 -> 26`
- `0xA908: 34 -> 28`
- `0xA940: 31 -> 25`
- `0xA942: 33 -> 27`
- `0xA944: 35 -> 29`

Later lines populate a wider area:

- `0xA9F4-0xAA0E`
- `0xAA30-0xAA4A`

The surrounding values are dominated by repeated halfwords such as:

- `C1 E1`
- `D4 E1`
- `D7 E1`
- and changing entries like `24 F1`, `26 F1`, `2A E1`, `31 E1`

This does **not** look like script text. It looks like a tilemap-style buffer or renderer work buffer made of 16-bit entries.

### 3. VRAM changes line up with text refresh

Visible dialogue changes correspond to large differences in:

- `VRAM 0x002000-0x002700`

Reports:

- `notes/diff-dialogue-2160-2340-vram.md`
- `notes/diff-dialogue-2340-2520-vram.md`

Examples:

- `0x002100`: `184` changed bytes
- `0x002200`: `188` changed bytes
- `0x002300`: `183` changed bytes
- `0x002600`: `170` changed bytes

This is consistent with text rendering or tile upload activity for the dialogue box.

### 4. Dialogue is rendered on `BG3`

`IO` snapshots for frames `2160`, `2340`, `2520`, and `2700` are identical:

- `DISPCNT = 0x1940`
- `BG0CNT = 0x0087`
- `BG3CNT = 0x0300`

Interpretation:

- scene is `Mode 0`
- enabled backgrounds are `BG0` and `BG3`
- `BG3` uses:
  - char base `0x0000`
  - screen base `0x1800`

Relevant files:

- `notes/dialogue-io-2160-io.bin`
- `notes/dialogue-io-2340-io.bin`
- `notes/dialogue-io-2520-io.bin`
- `notes/dialogue-io-2700-io.bin`
- `notes/dialogue-render-analysis.md`

Most importantly, the `WRAM 0xA8C0-0xAA7F` dialogue work buffer has its best byte-level match inside VRAM around:

- `0x1B0A`
- `0x1B12`
- `0x1B0E`

These offsets fall inside the `BG3` screen block region beginning at `0x1800`.

That means the current best model is no longer just “tilemap-like”. It is specifically:

- `WRAM 0xA900+` is a `BG3` dialogue tilemap work buffer
- that buffer is copied into `VRAM 0x1800+`
- the much larger changes in `VRAM 0x2000+` are more likely glyph/tile uploads than tilemap updates

## Working Interpretation

Current best model:

1. Script engine reads compressed or custom-encoded dialogue source from ROM.
2. It converts the current line into a compact intermediate representation.
3. That representation lands in `WRAM 0x00A900-0x00AA4A` as `BG3` tilemap entries.
4. The tilemap is copied into `VRAM 0x1800+`.
5. Character glyph tiles are uploaded or refreshed in `VRAM 0x2000+`.

So the next breakthrough is unlikely to come from raw string scanning. It will come from:

- tracing the code path that writes `WRAM 0x00A900+`, or
- tracing the renderer that copies this region into `VRAM 0x002000+`

## Immediate Next Steps

1. Capture the relevant BG/I/O state during the same dialogue frame to confirm whether `VRAM 0x002000+` is a BG screenblock.
2. Use debugger/watchpoint automation to catch writes into `WRAM 0x00A900-0x00AA4A`.
3. Use debugger/watchpoint automation to catch uploads into `VRAM 0x2000+`.
4. From either write site, walk backward to the dialogue decoder or script interpreter.
