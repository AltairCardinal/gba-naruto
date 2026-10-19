# Current reverse-engineering progress (updated 2026-07-13)

This is the factual completion snapshot after rerunning the repository audit
and all automated tests. It supersedes historical “100% complete” summaries.

## Reproducible checks

- Python: 338 tests pass.
- Repository automated checks: 25/25 pass.
- Node/WASM probe helpers: 34 tests pass.
- `git diff --check`: pass.
- Catalog identity audit: 32/32 investigations closed. This consists of 23
  active data banks with ROM fidelity plus 9 documented, empty, write-disabled
  `disproved` tombstones; it is not a claim of 32 runtime-verified banks.
- Evidence labels: 13 runtime, 10 code, 0 static, 9 disproved.

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
   `0x465B70`; hook observes ID 118 → descriptor `0x53D06C`.
8. Alternate chapter flow: table `0x60D54`, scenario 39 → script `0x31281` →
   25 runtime dispatches → opcode `00` normal termination at `0x3142E`.
9. Save-state: natural UI Save writes valid descriptors/checksums and cold boot
   restores the Konoha state.
10. Skills: natural technique UI and controlled row-1 `+4:6→7` A/B change the
    visible attack value `6x3→7x3`.
11. Menu portrait, encyclopedia pointer/callback and the remaining bank-level
    runtime identities are recorded in `notes/re-completion-audit.json`.

## Other completed implementation closures

- Skills corrected to 94×16 bytes at `0x545BE4`; consumer `0x0806D910` and a
  natural UI/control A/B are runtime-verified.
- Audio dispatcher/track/FIFO chain is mapped and sound-ID mirror writeback is
  guarded. The corrected m4a extractor exports 217 track blobs, 23 voicegroups,
  387 tones and 79 pointer-reachable WAVs. All tracks structurally decode to
  18,090 commands and 6,750 note/tie events with 1,287/1,287 valid control-flow
  targets. A bounded PATT/PEND/GOTO executor exports standard one-loop MIDI for
  all 80 sound IDs (217 tracks, 17,202 timeline events). Forty-seven of 47
  tileset atlases are exported. Instrument coverage resolves 16,180/16,180
  notes: 16,169 DirectSound notes reach all 79 waves, 5,340 of them through
  drum tables, and the remaining 11 are explicit type-0x0C PSG/noise events.
- Variable dialogue uses audited partition `0x5F0000..0x5F7FFF`; chapter scripts own
  `0x5F8000..0x5FFFFF`. A real 6→20
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
- Complete MP2K musical-state/channel allocation, PSG/DirectSound combined PCM
  output and audible cue names. The persistent control VM now runs all 217 ROM
  tracks through runtime loop edges; 10+4 channel selection/steal/chains, pitch,
  gain, envelope, DirectSound mixer, tempo/SoundMain and DMA/reverb are code-locked.
  Persistent track registers now emit runtime NoteRequest/EOT/FINE requests and the
  terminal-tone/channel initialization plus active-note pitch/mix propagation are
  connected. Player-level full-song scheduling now emits 80/80 non-silent bounded
  WAVs, including CGB+Direct hardware-scale PCM and all first-GOTO loop boundaries.
  Independent mGBA differential now matches all 79 sound-101 Direct FIFO chunks
  byte-for-byte and all 68 sound-144 visible CGB register/channel-status snapshots.
  Follow-up probes match active same-slot hard replacement 27/27, linked-player
  DirectSound sharing 25/25 and cross-player fixed-CGB competition 68/68. Cue
  semantics remain: four A-grade and four B-grade candidates have callsite evidence,
  while 72 entries deliberately remain `unknown` and no official names are claimed.
- Alternate chapter table `0x60D54` and all six map resource streams are now
  runtime-closed. Next P0 is player-visible naming for remaining unit and skill
  fields, followed by individual semantic review of the code-verified banks.
- Character growth field semantics are closed. Remaining field work is the full
  unit `0xB4` player-visible mapping and skills `+2/+3/+9`.
- All formerly static banks now have a consumer or negative identity proof.
  The 10 code-verified banks still require prioritized controlled runtime and
  player-visible semantic closure; code evidence alone is not a “100%” claim.

## Durable evidence and next route

- Save result and failed-shortcut boundary:
  `notes/save-descriptor-layout-correction-20260712.md`.
- Runtime chains: `notes/character-growth-runtime-chain-20260711.md`,
  `notes/battle-effect-template-consumer-20260711.md`,
  `notes/chapter-flow-runtime-chain-20260712.md`, and
  `notes/audio-engine-runtime-chain-20260712.md`.
- Audio player runtime evidence:
  `notes/m4a-player-slot-runtime-differential-20260713.md`; cue callsite/semantic
  boundary: `notes/audio-cue-semantics-20260713.md`.
- Current execution order and gates: `docs/sequel-roadmap.md`.
- Machine-readable identity audit: `notes/re-completion-audit.json`.
