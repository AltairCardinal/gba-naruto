# ROM allocation space

## Summary

The immutable base ROM contains an exact **132,116-byte (129.02 KiB)** `0xFF` tail, but it is
no longer unallocated. The complete 6 MiB base range and the expanded 16 MiB build
range are owned by `sequel/rom-layout.json`; importers must request one exact
partition instead of scanning for an apparently empty run.

## Historical base-ROM tail

| Property | Value |
|---|---|
| Start offset (file) | `0x5DFBEC` |
| End offset (exclusive) | `0x600000` |
| Size | 132,116 bytes (129.02 KiB) |
| Fill value | `0xFF` (GBA cartridge erased state) |
| ROM file size | `0x600000` (6 MiB) |

## Registered layout

The current 16 MiB build is divided into non-overlapping audited owners:

| Range | Owner |
|---|---|
| `0x5E0000..0x5EFFFF` | editor DB audit rows |
| `0x5F0000..0x5F7FFF` | variable-length dialogue |
| `0x5F8000..0x5FFFFF` | semantic chapter scripts |
| `0x600000..0x7FFFFF` | character battle visual bundles |
| `0x800000..0xBFFFFF` | sequel image assets |
| `0xC00000..0xFFFFFF` | sequel audio, text and configuration |

### Allocation strategy

- `tools/rom_layout.py` verifies the base hash, target power-of-two size, 32 MiB
  profile ceiling, fill byte, alignment, overlap and owner.
- Writes above the immutable base require `patch_class=allocation`, the exact
  partition ID and the registered owner. Their virtual precondition must be the
  declared `0xFF` fill.
- Existing game-effective and audit writes remain bounded to the immutable 6 MiB
  base; expansion cannot be used to bypass their source-byte preconditions.
- Text is 4-byte aligned before writing.
- Each entry occupies `len(encoded_text) + 1` bytes (null-terminated).
- The cursor advances sequentially; no deallocation is performed.
- Dialogue and chapter importers each align to four bytes, validate their complete
  partition is still `0xFF`, enforce an exclusive upper bound, and derive every
  `before_hex` from the immutable base ROM.
- Chapter payloads and table redirects are planned together before any build write;
  the output ROM is only written after the complete safety gate passes.

## Verification Method

The historical tail measurement was performed by scanning for the first `0xFF`
byte after
offset `0x5D0000`. The scan found a contiguous 0xFF run starting at `0x5DFBEC`
and continuing through the final byte `0x5FFFFF` (half-open end `0x600000`). Current allocation
validity is instead established from the hash-pinned layout and each importer's
full-plan safety checks; visual emptiness alone is not allocation evidence.
