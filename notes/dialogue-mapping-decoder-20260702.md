# Dialogue Mapping - Decoder Discovery (2026-07-02)

## Major Breakthrough (corrects previous analysis)

The breakthrough commit `473a737` claimed "IWRAM 0x03000078 = current dialogue ROM
file offset". This is partially wrong. The records at ROM 0x8DF0-0xB8EB (LE-correct
pointers) are **NOT dialogue text in SJIS**, they're **packed dialogue event records**
in a custom format.

## What the records actually contain

Decoding the records with Python's `cp932` codec reveals:

```
state 0 record (358 bytes) decoded as cp932:
"絈・尖・夜夜訴嬉煮瓜奇移訴……奇妓訴嬉扶誼誘嬉煮瓜奇移訴……"
```

This is **JAPANESE cp932 SJIS text**. The records contain the original Japanese
dialogue (before 熊组汉化 patch replaced the tile graphics).

**Key insight**: The bytes 0x81XX etc. are valid cp932 SJIS Japanese characters,
which were originally displayed as Japanese kanji/hiragana. 熊组汉化 replaced
the tile graphics so the same SJIS bytes now display as Chinese characters.

## Confirmed SJIS→cp932 mapping for top byte pairs in records

| SJIS bytes | cp932 char | Likely Chinese display |
|------------|------------|------------------------|
| 0x8140     | "　" (space) | (full-width space, unchanged) |
| 0x8143     | "，" (comma) | (punctuation, unchanged) |
| 0x8148     | "？" | Chinese "！" (existing mapping) |
| 0x8149     | "！" | (Chinese exclamation?) |
| 0x8163     | "…" | (Chinese ellipsis?) |
| 0x8167     | """ | (Chinese opening quote?) |
| 0x8168     | """ | (Chinese closing quote?) |
| 0x8AEF     | "奇" | (Chinese char unknown) |
| 0x88DA     | "移" | (Chinese char unknown) |
| 0x9169     | "訴" | (Chinese char unknown) |
| 0x8ECF     | "煮" | (Chinese char unknown) |
| 0x8AF0     | "嬉" | (Chinese char unknown) |

## Existing 20-char mapping decoded

The existing sjis-to-tile-mapping.json was validated against cp932:

| SJIS    | cp932 Japanese | Chinese display |
|---------|----------------|-----------------|
| 88CF    | 委             | 什 |
| 8FC2    | 渉             | 么 |
| 97AF    | 留             | ！ |
| 99C7    | 夘             | ？ |
| 8DF9    | 笹             | … |
| 8C81    | 戟             | … |
| 9A6A    | 嗚             | 真 |
| 9B45    | 妣             | 拿 |
| 9298    | 著             | 你 |
| 94C8    | 畔             | 没 |
| 96E2    | 問             | 办 |
| 92D7    | 潰             | 法 |
| 8B62    | 誼             | \n |
| 95C4    | 米             | 最 |
| 8B78    | 休             | 后 |
| 8EB5    | 七             | 一 |
| 8AF7    | 机             | 次 |
| 8E8F    | 誌             | 哦 |
| 9A79    | 噐             | ！ |
| 8148    | ？             | ！ |

Each SJIS byte pair decodes to a Japanese character via cp932. The DISPLAYED
Chinese character is determined by the tile table (replaced by 熊组汉化).

## What this means

1. **ROM has cp932 SJIS Japanese dialogue text** in packed records at offsets
   computed from IWRAM 0x78 LE-interpreted values.
2. **Each SJIS byte pair → tile index → Chinese character** (via replaced tiles)
3. **The TILE TABLE** (which maps SJIS bytes to tile indices) is the key mapping
4. **Original Japanese chars stay as Japanese** (hiragana like で/す unchanged)
5. **Original Japanese kanji → Chinese kanji** (tile swap by 熊组汉化)

## What needs to be done

To fully decode chapter 1 intro dialogue, I need:

1. **Comprehensive SJIS byte → cp932 char map** for ALL byte pairs in records (482 unique)
2. **Comprehensive cp932 char → Chinese display map** by capturing rendered text

Approach:
- Decode ALL records as cp932 → get Japanese text
- Use puppeteer to OCR-render each state → get Chinese text
- Align Japanese cp932 chars with Chinese OCR chars (need byte alignment in records)
- Each (SJIS, cp932, Chinese) triple is a mapping entry

## Captured data so far

- `/tmp/ewram-v1/state-XXX.json` (30 states) - EWRAM 0x0201BD48 area
- `/tmp/vram-bg-v1/state-XXX.json` (30 states) - all 4 BG tilemaps
- `/tmp/vram-tile-v1/state-XXX.json` (30 states) - VRAM tile data 32KB + BG3 tilemap
- `/tmp/oam-v1/state-XXX.json` (30 states) - OAM sprite attribute memory

## Pending work

1. Decode records properly (extract cp932 chars in record order)
2. Get OCR text from rendered dialogue for each state (alignment unknown)
3. Try to find cp932 char → Chinese display by searching for matches
4. Build the comprehensive SJIS→Chinese mapping
