# Episode 01 Dialogue Draft

> All text in this file must be compatible with cp932 (Shift-JIS) encoding.
> Roman characters and standard Japanese hiragana/katakana are safe.
> Traditional Chinese characters may not encode correctly.

## Beat 1: 边境异动 (Opening Briefing)

**Group 0 Main** (41 bytes max):
```
木葉村国境に異変あり小隊が調査に向かう。
```
Status: PATCHED in ROM (group0.main)

**Group 0 Label 1** (6 bytes max):
```
第１話
```
Note: "第"=0x95 0x7E, "１"=0x81 0x66, "話"=0x8A 0x8E → 6 bytes. Replaces "休４机".

## Beat 2: 遭遇戦 (Encounter)

**Group 1 Main** (41 bytes max):
```
忍刀の残党が附近に潜伏警戒せよ。
```
Status: PATCHED in ROM (group1.main)

## Beat 3: 戦後 (Post Battle)

**Group 2 Main** (41 bytes max):
```
輸送巻物守るべし。敵の狙いは明白だ。
```
Status: PATCHED in ROM (group2.main)

---

## Notes

- All sequel dialogue uses cp932-compatible text
- Patch system uses null-padding to fill to max_bytes
- Original Japanese text preserved in `dialogue-bank.json` expected_hex field
- Chinese authoring notes in `authoring-notes.md`
