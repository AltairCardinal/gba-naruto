# `0x54229C` story visual descriptor consumer (2026-07-12)

## Corrected identity

The historical `battle-encounters@0x542384` catalog was misaligned. The real
object is 24 records of 16 bytes at `0x54229C..0x54241B`:

| Offset | Meaning |
|---:|---|
| `+0x00` | LZ77 graphics pointer |
| `+0x04` | LZ77 palette pointer |
| `+0x08` | LZ77 tilemap pointer |
| `+0x0C` | small visual/configuration ID |

All 72 pointer targets begin with GBA LZ77 header byte `0x10`. The old start
address is exactly `0x54229C + 14*0x10 + 8`, so its alleged repeating
`pointer/value/pointer/pointer` pattern was a third pointer, a config value, and
the next descriptor. This bank provides no encounter or enemy-selection
evidence.

## Consumer

Story opcode handler `0x0808FA2C` calls `0x0808A69C`, which calls loader
`0x08087C9C`. The loop at `0x08087DDC` uses `r7 << 4` and literal bases
`0x0854229C`, `0x085422A8`, and `0x085422A4` for the descriptor fields.
`0x08087E76`, `0x08087E82`, and `0x08087E90` decompress the three streams to
`0x0600E800`, `0x050001E0`, and `0x06001800`. It terminates after index 23.

## Safe write-back rule

Legacy `rom_battle_encounters` rows are diagnostic-only. Their 38 individual
u32 cells do not map safely to the corrected 24-record schema and extend beyond
the actual object. A future editor migration must introduce explicit gfx,
palette, tilemap, and config columns before real write-back is restored.
