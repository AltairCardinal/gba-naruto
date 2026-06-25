# Unknown Structure: Random Encounter Tables

## Status: SUSPECTED (requires dynamic analysis)

## Why It's Hard to Find

Random encounter tables are difficult to find via static analysis because:

1. **No clear pattern**: Unlike pointer tables, encounter tables may be embedded in map data or stored as variable-length structures
2. **False positives**: Searches for u8 rate + u8 count + u16 enemy_ids return many false positives (entries with enemy_id=0)
3. **May be code-driven**: The encounter system might be implemented in code rather than data tables
4. **May be per-map**: Each map might have its own encounter configuration embedded in map data

## Suspected Locations

1. **0x541A08 area**: Found sequences of u8 values (43%, 44%, 45%, 46%, 47%) that look like encounter rates, but all have enemy_id=0
2. **0x5433A0 area**: Found sequences of u8 values (1%, 2%, 3%, 4%, 5%, 6%) that look like encounter rates, but all have enemy_id=0
3. **Battle encounter table at 0x542384**: Contains mixed pointers and small numbers (48, 49, 51, 52, 58, 61, 74, 16, 77, 5) - these might be encounter-related

## Next Steps (requires dynamic analysis)

1. Use mGBA to trigger random encounters on different maps
2. Dump WRAM before/after encounter trigger
3. Look for changes in encounter-related memory regions
4. Trace back to ROM offsets using LLDB watchpoints

## Related Structures

- Map header table at 0x53D910 (47 entries × 32 bytes)
- Battle encounter table at 0x542384 (38 entries × u32)

## Reason for Stopping

Static analysis has been exhausted. All ROM regions 0x530000-0x5E0000 have been scanned for pointer tables and structured data. The remaining structures require dynamic analysis with mGBA/LLDB instrumentation.
