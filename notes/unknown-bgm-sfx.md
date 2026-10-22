# Unknown Structure: BGM/SFX Channels

## Status: SUSPECTED (requires dynamic analysis)

## Why It's Hard to Find

BGM/SFX channel tables are difficult to find via static analysis because:

1. **Sappy engine**: The game uses the Sappy audio engine, which has its own internal format
2. **Code-driven**: Audio playback is controlled by code, not data tables
3. **No clear pattern**: Searches for event_id + audio_id pairs return no results
4. **Embedded in code**: Audio triggers might be embedded in game code rather than data

## Suspected Locations

1. **Audio table at 0x53F138**: Contains 88 entries × u32 pointer to Sappy audio entry
2. **Sappy engine code**: The audio engine is in the ROM code section
3. **Event handler code**: Audio triggers might be in event handler code

## Known Audio-Related Structures

- **Audio table at 0x53F138**: 88 entries × u32 pointer to Sappy audio entry
- **Audio entry format**: 16 bytes: u32 data_ptr, u16 type, u16 pad, u16 flags, u16 pad, u32 extra_ptr

## Next Steps (requires dynamic analysis)

1. Use mGBA to trigger different audio events (BGM, SFX)
2. Monitor Sappy engine state during audio playback
3. Trace audio trigger calls back to ROM offsets
4. Look for audio ID assignments in event handler code

## Related Structures

- Audio table at 0x53F138 (88 entries × u32 pointer)
- Map event handler table at 0x53EB08 (47 entries × u32 pointer)
- Battle event handler table at 0x53E6D8 (14 entries × u32 pointer)

## Reason for Stopping

Static analysis has been exhausted. Audio playback is controlled by the Sappy engine, which requires dynamic analysis with mGBA to examine audio trigger mechanisms.
