# naruto-sequel-dev.gba ROM Source

This file documents the source of `build/naruto-sequel-dev.gba`.

## Current source (as of 2026-06-30)

**base ROM**: `rom/base.gba` (md5: cd7fb9a4b60d01cf63e2406ffe18b07c)

**Origin**: 熊组汉化版 GBA 续作《火影忍者 - 木叶战记》v1.3 (简体中文, JP, 48Mb)

**Identification**:
- Title: NARUTOKONOHA
- Game code: AUEJ
- Maker code: DA

## What was overwritten

2026-06-28 T7 dialogue verification wrote 検証用 test bytes to:
- 0x459414 (group0.main): 41 bytes overwritten with `【検証用】` test data
- 0x459488 (group1.main): 41 bytes overwritten
- 0x459508 (group2.main): 41 bytes overwritten

After T7, the dev ROM no longer represented the canonical 熊组 汉化版.

## What was restored (2026-06-30)

dev ROM copied from `rom/base.gba` so the 熊组 dialogue bytes
(0x459414 etc.) are back. Editor can now save user edits that
will display as Chinese in the actual game (via 熊组's replaced
font tile table).

## Note on dialogue display

The bytes in 0x459xxx are SJIS (cp932) encoded. cp932-decoded
text shows 日文 characters like "委渉留夘笹戟嗚妣著畔問潰誼"
but the actual game (mGBA) renders these as 简体中文 dialogue
("讲鲁卡: 什么！？……真拿你没办法……最后……响喷！！")
because 熊组 replaced the SJIS-to-tile font mapping so SJIS bytes
point to Chinese tile images.

Editor.db currently stores cp932-decoded 字面 values in `text_ja`.
These are the SJIS byte interpretations, not the rendered Chinese.
A future enhancement would OCR all 12240+ tile images to build a
SJIS byte → 实际显示字符 mapping.
