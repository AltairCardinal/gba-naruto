# Next Reverse-Engineering Steps

Date: `2026-03-28`

## What is established now

1. The ROM contains at least one typed, nested visual resource descriptor table at `0x596FA8`.
2. The ROM also contains additional four-pointer tables such as `0x5A4E14`, likely for other asset banks.
3. There are promising low-ROM text banks, especially around `0x00076C` and `0x000C3D`.
4. There is at least one candidate free-space block at `0x09E6EE`.
5. A same-length text patch has been written successfully to a copied ROM at `0x00076D`.

## What is still missing before sequel production can start

1. A confirmed text pointer path from visible in-game UI/script to ROM offsets.
2. A confirmed chapter or event-script table.
3. A confirmed battle/unit/map configuration table.
4. A validated write-back experiment that changes visible game content.

## Highest-value next tasks

### A. Text confirmation

- Install and use a GBA debugger-capable emulator such as `mGBA`.
- Navigate to a screen likely using strings from `0x00076C` or `0x000C3D`.
- Set read breakpoints on those ranges if the emulator allows it, or patch a small byte sequence and observe the result.

### B. Text table ownership

- Search for pointers or caller code around the low-ROM text banks.
- Treat short binary runs embedded between strings as command records, not noise.
- Build a text-bank extractor/importer once one bank is visually confirmed.

### C. Resource schema deepening

- Decode the exact field layout of nested descriptors like `0x17ED7C`.
- Work out whether columns 2 and 3 in `0x596FA8` are masks, layouts, or tile attributes.
- Compare a few more similar tables to cluster them into schema families.

### D. First write-back experiment

- Copy the ROM.
- Patch one obvious text string in a low-risk bank.
- Run in emulator and verify on-screen impact.

This is the real gate from “analysis” to “editable project”.

Status:

- The copy-and-patch step is now complete.
- The remaining blocker is emulator-side validation.

## Strategic recommendation

Do not start authoring sequel chapters yet.

The correct engineering order is:

1. confirm one editable text bank
2. confirm one editable resource bank
3. confirm one flow or battle table
4. only then define the sequel slice in ROM terms

Until those three editable subsystems exist, sequel design should stay at document level rather than content-production level.
