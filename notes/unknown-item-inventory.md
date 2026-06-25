# Unknown Structure: Item / Inventory Tables

## Status: SUSPECTED (requires dynamic analysis)

## Why It's Hard to Find

Item/inventory tables are difficult to find via static analysis because:

1. **False positives**: Searches for sequential IDs + prices + effects return the level-up table at 0x5459D4
2. **May be embedded**: Item data might be embedded in other structures rather than in a standalone table
3. **Variable format**: Items might have variable-length entries (names, descriptions, effects)
4. **May be code-driven**: Item effects might be implemented in code rather than data

## Suspected Locations

1. **Level-up table area (0x5459D4)**: Contains sequential IDs and values that look like item data, but is actually the level-up stat progression table
2. **Battle config table (0x545458)**: Contains values like 612 that match skill table entries - might be item-related
3. **Character stat tables (0x54507A, 0x545200)**: Contains character stats that might be related to equipment/items

## Known Item-Related Structures

- **Skill table at 0x546100**: 12 entries × 16 bytes - contains skill/ability data
- **Skill data tables at 0x545EC4, 0x546074**: Contains skill parameters
- **Battle config table at 0x545458**: Contains battle configuration with skill references

## Next Steps (requires dynamic analysis)

1. Use mGBA to acquire/use items in-game
2. Dump WRAM before/after item acquisition
3. Look for changes in item-related memory regions
4. Trace back to ROM offsets using LLDB watchpoints

## Related Structures

- Skill table at 0x546100 (12 entries × 16 bytes)
- Battle config table at 0x545458 (32 entries × 16 bytes)
- Character stat tables at 0x54507A, 0x545200

## Reason for Stopping

Static analysis has been exhausted. All ROM regions 0x530000-0x5E0000 have been scanned for pointer tables and structured data. The remaining structures require dynamic analysis with mGBA/LLDB instrumentation.
