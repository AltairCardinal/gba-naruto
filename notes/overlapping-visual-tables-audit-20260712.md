# Overlapping visual-table audit at `0x53EE98..0x53F298` (2026-07-12)

## Status

This is an in-progress boundary audit. Do not upgrade or write through the
historical `palettes`, `map-sprites`, or `sprite-animations` banks yet.

## Confirmed boundaries and references

The three historical banks overlap:

- `palettes@0x53F138`, 88 u32 words, ends at `0x53F298`;
- `map-sprites@0x53F1DC`, 47 u32 words, ends at `0x53F298`;
- `sprite-animations@0x53F200`, 38 u32 words, ends at `0x53F298`.

None of those three bases has a literal reference in the ROM. Code instead
contains three literals for `0x0853EE98` at `0x08080744`, `0x080807F0`, and
`0x08080898`; it contains a literal for `0x0853F140` at `0x08080B54` and an
independent following-object literal `0x0853F298` at `0x08080B5C`.

The arithmetic gives two exact candidate objects:

- `0x53EE98..0x53F13F`: 68 records × 10 bytes;
- `0x53F140..0x53F297`: 43 records × 8 bytes.

The first consumer family (`0x080806B0`, `0x08080764`, `0x08080814`) multiplies
a runtime index by 10, then walks 10-byte records and passes signed halfword
fields to `0x08080218`. This proves the old `palettes` base `0x53F138` begins
two bytes into the final 10-byte record and then crosses into the next object.

`0x08080B08` loads `0x0853F140` and passes it to `0x08063494`; the same routine
uses `0x0853F298` independently as a following u16 lookup base. Static analysis
still needs to close the 8-byte record field semantics and record-count bound.

## Next TDD step

Add failing identity tests that:

1. reject the three historical overlapping shapes and their write generators;
2. require one canonical 68×10 bank and one canonical 43×8 bank;
3. pin the literal addresses and index arithmetic above;
4. verify the `0x53F298` following object is not absorbed into either table.

Only after those tests fail for the current catalogs should the banks be
reshaped/tombstoned and their editor migrations disabled or replaced.
