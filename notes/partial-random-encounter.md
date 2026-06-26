# Partial Findings: Random Encounter Tables

## Status: SUSPECTED (static analysis inconclusive)

## Why It's Hard to Find

Random encounter tables are difficult to find via static analysis because:

1. **Map event handlers not encounter-related**: Disassembled handler at 0x07F064 - handles map transitions, not encounters
2. **Code at 0x542310 is data**: LDR instructions referencing battle encounter table are inside data tables, not code
3. **No encounter-related patterns**: No "random number < threshold → enter battle" patterns found
4. **Code-driven**: Encounters may be triggered by code that reads map data directly, not from a separate table

## Suspected Locations

1. **Battle encounter table at 0x542384**: 38 entries × u32 (mixed pointers and small numbers) - contains battle IDs (48, 49, 51, 52, etc.)
2. **Map headers at 0x53D910**: 47 entries × 32 bytes - each map has extra_ptr that might contain encounter data
3. **Map event handlers at 0x53EB08**: 47 entries × u32 pointer - 6 unique handlers for 47 maps

## Related Structures

- Battle encounter table at 0x542384 (38 entries × u32)
- Map header table at 0x53D910 (47 entries × 32 bytes)
- Map event handler table at 0x53EB08 (47 entries × u32 pointer)

## Reason for Stopping

Static analysis has been exhausted. Map event handlers don't contain encounter logic. The encounter system may be code-driven rather than data-driven.

## Recommendation

Complete random encounter table investigation using mGBA Qt frontend with Lua scripting to:
1. Walk around a map long enough to trigger encounter
2. Capture WRAM state at encounter trigger moment
3. Diff between non-encounter and encounter-trigger WRAM
4. Trace from encounter handler code back to ROM table
