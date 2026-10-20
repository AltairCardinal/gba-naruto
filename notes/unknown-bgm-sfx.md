# Unknown Structure: BGM/SFX Channels

## Status: SUSPECTED (requires dynamic analysis)

> **2026-10-20 冲突警告（重要）**
>
> 本文件与 `docs/structure-field-semantics.md` #22、`notes/dynamic-verification-audit.md`
> 都把 **`0x08599634`（file `0x599634`）记作 Sappy 音频索引表（100 条）**。
> 实测该地址**不是音频索引表**，而是一张**指向文本的指针表**：
> `u32[93]`，每项指向一段 SJIS 字符串，内容是**忍具名称**
> （例：id1 = `95 ab 9c a0 95 d3 90 ec 8f 41` → "忍具…型"）。
> 同类表还有 `0x5A7E8C`（强化素材名，16 条）、`0x599280`（人物名 / 认识卡，62 条）。
>
> 复现：`tools/probe_external_re_claims.py`；
> 详见 `notes/external-konoha-workshop-gap-20261020.md` §4 C3。
>
> **后果**：Sappy dispatcher `0x08079668` 对命令 0x80-0xE3 的真实索引表**需要重新定位**；
> 在重新定位之前，**不要**把 `0x599634` 当作音频表使用。
> `notes/patch-generator-audit.md` 里 `audio_events` 指向 `0x599634` 的写回路径
> 同样应视为高风险，先禁用。

## Why It's Hard to Find

BGM/SFX channel tables are difficult to find via static analysis because:

1. **Sappy engine**: The game uses the Sappy audio engine, which has its own internal format
2. **Code-driven**: Audio playback is controlled by code, not data tables
3. **No clear pattern**: Searches for event_id + audio_id pairs return no results
4. **Embedded in code**: Audio triggers might be embedded in game code rather than data

## Suspected Locations

1. **Audio table at 0x53F138**: Contains 88 entries × u32 pointer to Sappy audio entry
2. **Sappy engine code**: The audio engine is in the ROM code section
3. **Event handler code**: Audio triggers might be in event handler code

## Known Audio-Related Structures

- **Audio table at 0x53F138**: 88 entries × u32 pointer to Sappy audio entry
- **Audio entry format**: 16 bytes: u32 data_ptr, u16 type, u16 pad, u16 flags, u16 pad, u32 extra_ptr

## Next Steps (requires dynamic analysis)

1. Use mGBA to trigger different audio events (BGM, SFX)
2. Monitor Sappy engine state during audio playback
3. Trace audio trigger calls back to ROM offsets
4. Look for audio ID assignments in event handler code

## Related Structures

- Audio table at 0x53F138 (88 entries × u32 pointer)
- Map event handler table at 0x53EB08 (47 entries × u32 pointer)
- Battle event handler table at 0x53E6D8 (14 entries × u32 pointer)

## Reason for Stopping

Static analysis has been exhausted. Audio playback is controlled by the Sappy engine, which requires dynamic analysis with mGBA to examine audio trigger mechanisms.
