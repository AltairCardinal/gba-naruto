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

The usable tail is divided into non-overlapping audited owners:

| Range | Owner |
|---|---|
| `0x5E0000..0x5EFFFF` | DB audit rows |
| `0x5F0000..0x5F7FFF` | variable-length dialogue |
| `0x5F8000..0x5FFFFF` | semantic chapter scripts |

### Allocation strategy

- Text is 4-byte aligned before writing.
- Each entry occupies `len(encoded_text) + 1` bytes (null-terminated).
- The cursor advances sequentially; no deallocation is performed.
- Dialogue and chapter importers each align to four bytes, validate their complete
  partition is still `0xFF`, enforce an exclusive upper bound, and derive every
  `before_hex` from the immutable base ROM.
- Chapter payloads and table redirects are planned together before any build write;
  the output ROM is only written after the complete safety gate passes.

## Verification Method

Performed a linear scan of the ROM file looking for the first 0xFF byte after
offset `0x5D0000`. The scan found a contiguous 0xFF run starting at `0x5DFBEC`
and continuing to the end of the 6 MiB file (`0x5FFFFF`), confirming ~128 KB of
free space. No game code or data was found in this range.
