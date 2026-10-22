# Partial Findings: Random Encounter Tables

## Status: SUSPECTED (static analysis inconclusive)

## Why It's Hard to Find

Random encounter tables are difficult to find via static analysis because:

1. **Map event handlers not encounter-related**: Disassembled handler at 0x07F064 - handles map transitions, not encounters
2. **Code at 0x542310 is data**: LDR instructions referencing battle encounter table are inside data tables, not code
3. **No encounter-related patterns**: No "random number < threshold → enter battle" patterns found
4. **Code-driven**: Encounters may be triggered by code that reads map data directly, not from a separate table

## Suspected Locations

1. **Former battle encounter table at 0x542384**: disproved. It is a misaligned slice of 24 story visual descriptors beginning at 0x54229C.
2. **Map headers at 0x53D910**: 47 entries × 32 bytes. The former `encounter-zones` interpretation of `+0x1C` is disproved: this is the runtime-consumed map `flags` field, not a zone ID.
3. **Former map-events at 0x53EB08**: disproved as a 47-map table; it is pair index 142 inside a 256×8 handler table at 0x53E698.

## Related Structures

- The historical 0x542384 catalog is excluded; it has no encounter semantics.
- Map header table at 0x53D910 (47 entries × 32 bytes)
- Runtime handler pair table at 0x53E698 is not currently encounter evidence.

## Reason for Stopping

Static analysis has been exhausted. Map event handlers don't contain encounter logic. The encounter system may be code-driven rather than data-driven.

The former `sequel/content/encounter-zones/bank.json` is therefore an empty,
write-disabled tombstone. Its 47 rows duplicated the full map descriptor table;
legacy editor rows must remain diagnostic-only until a distinct ROM identity is
found.

## Recommendation

Complete random encounter table investigation using mGBA Qt frontend with Lua scripting to:
1. Walk around a map long enough to trigger encounter
2. Capture WRAM state at encounter trigger moment
3. Diff between non-encounter and encounter-trigger WRAM
4. Trace from encounter handler code back to ROM table
