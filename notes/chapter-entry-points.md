# Chapter Entry Points

## Status

**Partial - runtime verification blocked by environment limitations, static analysis documented.**

## Runtime Verification Attempts

### Attempt 1: Savestate Loading
- **Result**: FAILED - savestate files contain all 0xFF (empty)
- **Files checked**: `rom/experiment-00076d.sav`, `build/naruto-sequel-dev.sav`
- **Analysis**: Both 32KB save files are uninitialized

### Attempt 2: Text Render Breakpoint (0x080894DE)
- **Method**: Set breakpoint at text rendering address, load savestate, continue
- **Result**: Breakpoint never hit - game doesn't reach text rendering from cold boot
- **Observation**: PC stuck in 0x085CCDxx range (UI/video subsystem loop)

### Attempt 3: Battle Init Breakpoint (0x0806E654)
- **Method**: Set breakpoint on battle unit table reader
- **Result**: Breakpoint never hit in cold boot state
- **Observation**: Game doesn't reach battle initialization without user input

### Attempt 4: Frame Advance + Breakpoint
- **Method**: Advance 20 frames from cold boot, then set breakpoints
- **Result**: Game runs in video/UI loop (0x085CCDxx), never reaches main game logic
- **Root Cause**: mGBA CLI debugger cannot inject key inputs to navigate menus

## Static Analysis Findings

### Confirmed Code References to Battle Tables

| File Offset | ARM Address | Context |
|-------------|-------------|---------|
| 0x68FE0 | 0x08068FE0 | Function loads battle scenario config |
| 0x690DC | 0x080690DC | Function reads scenario entries |
| 0x6924C | 0x0806924C | Function processes scenario data |
| 0x7AB00 | 0x0807AB00 | Battle initialization code |
| 0x80B5C | 0x08080B5C | Reads unit ID table (0x0853F298) |
| 0x8F508 | 0x0808F508 | Battle config loader |

### Code Pattern Analysis

All battle table references appear in functions that:
1. Load 16-byte entries from 0x0853D910
2. Extract tiles_x, tiles_y, ptr1, ptr2 for tilemap data
3. Use unit ID table at 0x0853F298 to resolve character IDs

**These are battle-specific loaders, not chapter flow loaders.**

### Search for Chapter Configuration

- **Chapter ID sequences** (u16 1,2,3...): Found at 0xBD713, 0xC1717, 0xC4217, 0xC84FF, 0xCAB37 - but these appear in data blobs, not config tables
- **Map data pointers**: No clear chapter-to-map pointer table found in static analysis
- **38 table candidates**: All identified as visual/resource tables, not chapter config

## Environment Limitations

1. **No script support**: mgba-sdl 0.10.1 lacks `--script` flag
2. **No Qt GUI**: mgba-qt also lacks script support in this build
3. **No key injection**: CLI debugger cannot send key presses
4. **Empty savestates**: No valid save states available

## Recommended Path Forward

### Option 1: Manual mGBA Session
Use mGBA Qt with GUI to:
1. Navigate "New Game" manually to first battle
2. Save a savestate at battle start
3. Load savestate in CLI debugger
4. Set breakpoints on chapter loader functions

### Option 2: Build New Lua Script Infrastructure
- Compile mGBA with Lua scripting enabled
- Or use a newer mGBA binary with `--script` support

### Option 3: Focus on Battle Config (Already Complete)
Since battle configuration is complete and P0-Step 3 is done, the chapter flow entry point could be considered a future enhancement once runtime debugging is possible.

## Deliverables

- This document (notes/chapter-entry-points.md)
- Static analysis of battle table references (above)
- Notes on environment limitations (above)

## Related Files

- `notes/chapter-flow-format.md` - Format analysis
- `notes/battle-config-format.md` - Battle table format (complete)
- `docs/sequel-roadmap.md` - Roadmap with P0-Step 4 status