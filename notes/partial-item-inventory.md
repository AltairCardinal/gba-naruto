# Partial Findings: Item / Inventory Tables

## Status: SUSPECTED (static analysis inconclusive)

Correction (2026-07-11): the `0x54507A` / `0x545200` stat candidates mentioned
below are not item evidence. They are misaligned views of the character-growth
table at `0x545068`.

## Why It's Hard to Find

Item/inventory tables are difficult to find via static analysis because:

1. **No code references found**: All LDR instructions targeting 0x54xxxx and 0x53xxxx regions are inside data tables, not code sections
2. **No item-related text**: No ASCII strings like "item", "equip", "weapon", "armor" found in ROM
3. **Indirect access**: Item data may be accessed through indirect addressing (register + offset) rather than direct LDR from literal pool
4. **Code-driven**: Item effects may be implemented in code rather than data tables

## Suspected Locations

1. **Skill table at 0x546100**: 12 entries × 16 bytes - contains skill/ability data that might be item-related
2. **Battle config table at 0x545458**: 32 entries × 16 bytes - contains battle configuration with skill references
3. **Character stat tables at 0x54507A, 0x545200**: Contains character stats that might be related to equipment/items

## Related Structures

- Skill table at 0x546100 (12 entries × 16 bytes)
- Battle config table at 0x545458 (32 entries × 16 bytes)
- Character stat tables at 0x54507A, 0x545200

## Reason for Stopping

Static analysis has been exhausted. All code sections have been searched for references to data tables. The remaining structures require dynamic analysis with mGBA/LLDB to observe runtime behavior.

## Recommendation

Complete item/inventory table investigation using mGBA Qt frontend with Lua scripting to:
1. Open menu → focus items → dump WRAM
2. Acquire an item → dump WRAM
3. Diff WRAM snapshots → identify item record array
