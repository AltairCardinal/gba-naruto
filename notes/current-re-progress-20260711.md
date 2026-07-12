# Current reverse-engineering progress (updated 2026-07-12)

This is the factual completion snapshot after rerunning the repository audit
and all automated tests. It supersedes historical “100% complete” summaries.

## Reproducible checks

- Python: 116 tests pass.
- Repository automated checks: 25/25 pass.
- Node/WASM probe helpers: 27 tests pass.
- `git diff --check`: pass.
- Catalog identity audit: 32/32 investigations closed. This consists of 25
  active data banks with ROM fidelity plus 7 documented, empty, write-disabled
  `disproved` tombstones; it is not a claim of 32 runtime-verified banks.
- Evidence labels: 9 runtime, 6 code, 10 static, 7 disproved.

## Runtime-closed chains

1. Positions: formation matrix `0x5461C4`, first-battle coordinate match.
2. Units: definitions `0x54241C`; controlled record-byte A/B reaches template
   and battle slot. Loader-derived fields and guarded 0xB4 mirror writeback exist.
3. Character growth: `0x545068`, consumer `0x0806D964`; two-factor A/B closes
   growth record → template → battle slot.
4. Battle effects: `0x545458`, consumer `0x0806D85C`; level-2 growth A/B matches
   the predicted type-4 output.
5. Maps: row-40 width A/B changes live `[36,44,9,22]` to `[32,44,8,22]`;
   the full 47×32-byte header has guarded mirror writeback.
6. Primary chapter flow: table `0x60C74`, scenario 39 → script `0x31020` →
   opcode `0x1A` operand 40 → live battle ID 40.
7. Audio bank runtime identity is additionally closed: master sound-ID table
   `0x465B70`; hook observes ID 118 → descriptor `0x53D06C`. It is counted in
   the six runtime bank labels; this list separates chains rather than banks.

## Other completed implementation closures

- Skills corrected to 94×16 bytes at `0x545BE4`; consumer `0x0806D910` is
  code-verified.
- Audio dispatcher/track/FIFO chain is mapped and sound-ID mirror writeback is
  guarded. The corrected m4a extractor exports 217 track blobs, 23 voicegroups,
  387 tones and 79 pointer-reachable WAVs. All tracks structurally decode to
  18,090 commands and 6,750 note/tie events with 1,287/1,287 valid control-flow
  targets. A bounded PATT/PEND/GOTO executor exports standard one-loop MIDI for
  all 80 sound IDs (217 tracks, 17,202 timeline events). Forty-seven of 47
  tileset atlases are exported. Instrument coverage resolves 16,180/16,180
  notes: 16,169 DirectSound notes reach all 79 waves, 5,340 of them through
  drum tables, and the remaining 11 are explicit type-0x0C PSG/noise events.
- Variable dialogue uses audited partition `0x5F0000..0x5FFFFF`; a real 6→20
  byte relocation at pointer `0x461CF0` survived build, boot, dialogue and strict
  first-battle arrival.
- Five false catalogs (`character-stats-b`, `items`, `story-c/d/e`) retain only
  negative evidence and disabled writeback; the audit explicitly rejects fake
  entries for them.

## Work still required before a defensible full-runtime “100%” claim

- Save-state is now `runtime_verified`. The tutorial was completed naturally,
  UI Save wrote valid active descriptors 0 and 2, and a cold restart restored
  the same Konoha state. The corrected physical record is 19-byte header +
  payload + checksum. Tutorial completion bypasses optional postbattle wrapper
  `0x08074F2C`; title loading likewise does not use optional wrapper
  `0x08068AF0`. See `notes/tutorial-victory-save-load-runtime-20260712.md`.
- Complete pitch-step semantics, PSG/noise synthesis, envelopes/LFO/ties,
  bit-accurate mixing and audible cue names. Instrument/sample and drum mapping
  are now complete for the executed one-loop corpus; MIDI remains an audition
  artifact rather than final audio.
- Alternate chapter table `0x60D54` and all six map resource streams are now
  runtime-closed. Next P0 is player-visible naming for remaining unit/growth/
  skill fields, followed by individual semantic review of the remaining static banks.
- Correlate remaining unit/growth/skill fields with player-visible UI labels.
- Review the 10 static banks individually; byte fidelity proves extraction
  accuracy, not complete runtime semantics.

## Durable evidence and next route

- Save result and failed-shortcut boundary:
  `notes/save-descriptor-layout-correction-20260712.md`.
- Runtime chains: `notes/character-growth-runtime-chain-20260711.md`,
  `notes/battle-effect-template-consumer-20260711.md`,
  `notes/chapter-flow-runtime-chain-20260712.md`, and
  `notes/audio-engine-runtime-chain-20260712.md`.
- Current execution order and gates: `docs/sequel-roadmap.md`.
- Machine-readable identity audit: `notes/re-completion-audit.json`.
