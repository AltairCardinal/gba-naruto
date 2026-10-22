# Text Region Notes

Date: `2026-03-28`

## Summary

The ROM contains multiple low-offset regions that decode plausibly as Shift-JIS-like text. This strongly suggests at least some text resources are stored as ordinary byte streams rather than entirely custom encoded script blobs.

This does not prove the Chinese patch uses the same layout everywhere, but it gives the project a viable text-attack path.

Primary scan output:

- `notes/sjis-blocks.json`

Tool used:

```bash
python3 tools/find_sjis_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  --output notes/sjis-blocks.json
```

## Promising low-ROM text blocks

These offsets are in the early ROM and look more like menu/help/script text than false positives from graphics data:

- `0x00076C` length `414`
- `0x000919` length `51`
- `0x00099D` length `37`
- `0x000BFE` length `48`
- `0x000C3D` length `42`
- `0x000C75` length `42`
- `0x000CF3` length `50`

Examples:

```text
0x00076C: 過篇 / 岩円誼必奏 / 碑靭嶷必 / 翁嶷甑碑靭 ...
0x00099D: 咒峡 / 奉・繁賞 / 画進征 / 僣蓮 / 傀峡準峯
0x000C3D: 舎冂文嚶遷冂垢事 / 女傀垢事啄？
```

The wording is garbled because this is not a clean retail Japanese dump. Likely causes:

- the Chinese patch changed font/text assets but not all byte patterns
- the scanner is only validating Shift-JIS byte shapes, not semantic correctness
- command bytes are mixed into strings

## Important caveat

The raw scanner also produces many false positives in graphics-heavy regions, especially high offsets around `0x45xxxx` and `0x5Axxxx-0x5Dxxxx`. Those long blocks should not be treated as script banks without more evidence.

## Working interpretation

The early ROM region likely contains UI/help/tutorial or menu-adjacent text resources. That matters because those are often easier to locate, edit, and repoint than full event scripts.

## Recommended next text steps

1. Build a stricter extractor that splits low-ROM candidate blocks on `0x00`, `0x0A`, and command-like bytes
2. Cross-check one candidate block in an emulator against visible menu/help text
3. Once one text block is confirmed on-screen, use its pointer or caller path to reach the owning script/text table

## Follow-up extraction

Tool outputs:

- `notes/text-block-00076C.json`
- `notes/text-block-000C3D.json`

The `0x00076C` block is now clearly one large string bank with many newline-separated labels or menu/help items. It is not just random noise.

The `0x000C3D` block is more interesting structurally:

- text fragments appear
- short binary records are interleaved between them

That suggests at least some low-ROM text banks are not plain contiguous strings. They may alternate between:

- visible text
- compact command or formatting records

This is still good news, because it means the project is getting close to a realistic script/text format rather than a total dead end.
