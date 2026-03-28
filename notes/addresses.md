# Address Notes

This file records confirmed and suspected ROM offsets.

## Confirmed

- `0x0000A0`: internal title area contains `NARUTOKONOHA`
- `0x09E6EE`: starts a zero-filled run at least `1100` bytes long; candidate free space for experiments
- `0x596F98` and nearby region: contains dense pointer-table-like structures referencing `0x17A1A4` and related `0x17xxxx`/`0x18xxxx` assets
- `0x596FA8`: appears to begin a regular `0x10`-byte resource table entry sequence
- `0x17ED7C`: points to a secondary structured block containing internal pointers and small numeric fields
- `0x17A1A4`: palette-like block; first 32 bytes decode cleanly as 16 little-endian values within GBA BGR555 range
- `0x596FA8` table columns now have a working role model:
  - col 0: palette-like/shared base block
  - col 1: nested descriptor block
  - col 2: sparse binary or secondary resource block
  - col 3: sparse binary or mask/attribute block
- `0x00076C`: large low-ROM Shift-JIS-like text block; likely menu/help/tutorial-adjacent string bank
- `0x5A4E14`: another confirmed `0x10`-byte four-pointer table, but with a different profile from `0x596FA8`; probably a flatter visual resource bank

## Suspected

- `0x004081`: heavily referenced target (`557` aligned in-ROM pointers point here); likely shared data block, possibly text or table data
- `0x17A1A4`: heavily referenced target (`97` hits); looks structured and may be graphics, palette, or table data rather than executable code
- `0x596F90-0x59xxxx`: likely one or more resource pointer tables with repeated `16-byte` entry spacing
- `0x17A1A4`: likely base resource or shared header block reused across multiple entries in the `0x596FA8` table
- `0x5A4E14` table columns may map to mostly palette-like blocks plus one more variable binary resource column

## Workflow

For each new finding, record:

- ROM offset
- virtual address if relevant
- confidence level
- why it matters
- how it was verified
