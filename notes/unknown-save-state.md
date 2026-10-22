# Unknown Structure: Save State Structure

## Status: SUSPECTED (requires dynamic analysis)

## Why It's Hard to Find

Save state structure is difficult to find via static analysis because:

1. **SRAM-based**: Save data is stored in SRAM (0x0E000000-0x0E00FFFF), not in ROM
2. **Runtime-only**: The save state format is only visible during gameplay
3. **Code-driven**: Save/load routines are implemented in code, not data tables
4. **Variable format**: Save data might be compressed or have variable-length fields

## Suspected Locations

1. **SRAM region**: Save data is stored in SRAM at 0x0E000000-0x0E00FFFF
2. **Save/load code**: The routines that read/write save data are in the ROM code section
3. **WRAM buffer**: Save data is likely loaded into WRAM before being written to SRAM

## Known Save-Related Structures

- **Chapter progress**: Likely stored as u8/u16 values indicating current chapter
- **Character unlocks**: Likely stored as bitfield or array of u8 values
- **Item counts**: Likely stored as array of u8/u16 values

## Next Steps (requires dynamic analysis)

1. Use mGBA to save game state
2. Dump SRAM before/after save
3. Compare SRAM contents to identify save data format
4. Load save state and dump WRAM to identify in-memory format

## Related Structures

- Story/chapter tables at 0x53636C, 0x536BC8, 0x538FF0, 0x53AB78, 0x53C3C0
- Character stat tables at 0x54507A, 0x545200

## Reason for Stopping

Static analysis has been exhausted. Save state data is stored in SRAM and WRAM, not in ROM. Dynamic analysis with mGBA is required to examine save state format.
