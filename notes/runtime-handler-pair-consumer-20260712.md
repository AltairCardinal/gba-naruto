# Runtime handler pair table at `0x53E698` (2026-07-12)

## Corrected identity

The historical `map-events@0x53EB08` table was a misaligned view into a larger
object. The real table spans `0x53E698..0x53EE97` and contains 256 records of
eight bytes:

- `+0`: optional primary Thumb callback;
- `+4`: optional secondary Thumb callback.

Zero is allowed in either field. Nonzero values are Thumb pointers. The next
object begins at `0x53EE98`. The old base is exactly pair index 142, so reading
47 consecutive u32 values produced 23.5 pairs; matching the game's 47-map count
was coincidental and does not prove map indexing.

## Consumer

At `0x0807F934..0x0807F948`, code reads the byte at runtime state `sb+0x770`,
computes `index << 3`, adds literal `0x0853E698`, and passes a nonzero primary
handler to dispatcher `0x0809C114`. The following block
`0x0807F94E..0x0807F964` repeats the same index with literal `0x0853E69C` for
the secondary handler.

This closes the full 256-pair identity at `code_verified`; it does not yet name
the runtime-state index or each callback's player-visible purpose.

## Write-back boundary

Legacy `rom_map_events` rows are diagnostic-only. They cannot be safely mapped
to the complete pair schema. A future editor migration needs 256 rows with
explicit primary and secondary columns plus Thumb-pointer validation.
