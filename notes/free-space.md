# Free ROM Space

## Summary

The ROM contains approximately **128 KB of unallocated space** at the end of the file,
verified by scanning for contiguous 0xFF-filled bytes after all known game data.

## Confirmed Region

| Property | Value |
|---|---|
| Start offset (file) | `0x5DFBEC` |
| End offset (file) | `0x5FFFFF` |
| Size | ~131,092 bytes (~128 KB) |
| Fill value | `0xFF` (GBA cartridge erased state) |
| ROM file size | `0x600000` (6 MiB) |

## Usage

This region is used by the variable-length dialogue pipeline (`import_dialogue_var.py`)
to store new text that is longer than the original slot, with the dialogue pointer table
updated via `pointer_redirect` patches to point to the new location.

### Allocation strategy

- Text is 4-byte aligned before writing.
- Each entry occupies `len(encoded_text) + 1` bytes (null-terminated).
- The cursor advances sequentially; no deallocation is performed.
- `FREE_SPACE_START = 0x5DFBEC` and `FREE_SPACE_END = 0x5FFFFF` are defined as
  constants in `tools/import_dialogue_var.py`.

## Verification Method

Performed a linear scan of the ROM file looking for the first 0xFF byte after
offset `0x5D0000`. The scan found a contiguous 0xFF run starting at `0x5DFBEC`
and continuing to the end of the 6 MiB file (`0x5FFFFF`), confirming ~128 KB of
free space. No game code or data was found in this range.
