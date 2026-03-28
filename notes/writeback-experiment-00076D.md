# Write-Back Experiment: `0x00076D`

Date: `2026-03-28`

## Goal

Validate that the project can safely create a patched ROM copy and modify a suspected low-ROM text bank without changing file size or breaking byte alignment.

## Input

- Source ROM: `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba`
- Target offset: `0x00076D`
- Original bytes: `89 DF 95 D1`
- Original decoded text: `過篇`

## Patch

Replacement text:

- `試験`

Replacement bytes:

- `8E 8E 8C B1`

This is a same-length replacement (`4` bytes), so it is low risk compared with pointer-moving edits.

## Output

Patched ROM:

- `rom/experiment-00076d.gba`

Patched ROM SHA-1:

- `383adf1bce4b0e7793648a13b3749c1bcf97c1b7`

Verified bytes at `0x00076C`:

```text
0000076c: 00 8e 8e 8c b1 81 40 0a 8a e2 89 7e 8b 62 95 4b
```

Verified decoded snippet:

```text
\0試験　\n岩円誼必
```

## What this proves

- The repository now has a repeatable ROM write-back path.
- A low-ROM text-like bank can be patched in-place with same-length Shift-JIS text.
- The patched output is stable and byte-verified.

## What this does not prove

- It does not prove the edited string is used on-screen.
- It does not prove this bank belongs to scenario script rather than menu/help/tutorial text.
- It does not prove the game will boot or render the edit correctly, because there is still no local emulator installed.

## Immediate next requirement

The next irreversible bottleneck is emulator validation. The patched ROM already exists; what is missing now is running it in `mGBA` or an equivalent emulator and checking whether the string appears in-game.
