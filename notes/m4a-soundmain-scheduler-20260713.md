# m4a SoundMain scheduler (2026-07-13)

## Two clock domains

MP2K track ticks are not audio buffers. Every `SoundMain` invocation produces
exactly 264 stereo PCM frames, while each linked MPlay player may execute zero,
one or multiple ticks inside that invocation. Rendering audio once per track
tick is therefore incorrect.

The main path is `0x08061006 → 0x0809AAB4 → SoundMain 0x08099D8C`; VBlank uses
`0x080612BC → m4aSoundVSync 0x0809A3E0`. `SoundMain` first calls the linked
MPlay chain at `0x08099DC0..0x08099DCC`. `MPlayMain 0x0809A42C` recursively
updates its next player first. Only after every due player tick does SoundMain
call `CgbSound`, advance DirectSound ADSR and mix one 264-frame buffer.

## Tempo and per-tick order

At `0x0809A474..0x0809A5CA`:

```text
tempoC += tempoI
while tempoC >= 150:
    execute one full track tick
    tempoC -= 150
```

TEMPO at `0x0809A2E8` stores `tempoD=raw*2`, then
`tempoI=(tempoD*tempoU)>>8`. Default `tempoU=0x100`; raw 75 therefore yields
one tick per SoundMain call. A player with `tempoI=300` executes two ticks
before a single CGB/DirectSound update.

Within a track tick, the engine first decrements gates on channels that already
exist, marking release when a gate reaches zero. It then executes commands
continuously until WAIT/FINE/termination, decrements wait, and advances LFO.
New notes are not gate-decremented in their creation tick. However, a gate-1
note created in tick 1 of a two-tick buffer is released at the start of tick 2;
the first mixer update can therefore see NEW|RELEASE and make it entirely
silent. All ticks finish before one dirty-state propagation and one mix.

Runtime GOTO changes the command pointer and continues in the same tick. It
does not terminate at a backward edge or release TIE. The one-loop MIDI policy
remains valid for bounded structural auditing only; a faithful renderer must
continue until a requested duration or an explicit all-players/tails policy.

## DMA and reverb ring

`SampleFreqSet 0x0809AF34` establishes 264 samples/VBlank, integer WAV rate
15,768 Hz and `divFreq=532`. Each signed plane is `0x630=1584` bytes, six
264-frame chunks. The chronological chunk sequence is 0,1,2,3,4,5,0...

The reverb seed reads the old current ring chunk and old next ring chunk,
approximately output times t−6 and t−5. It is not a one-buffer delay. Chunk 5
wraps its next source to chunk 0. The seed formula and modulo-256 channel mixer
are documented in `notes/directsound-mixer-runtime-chain-20260713.md`.

## Durable implementation and remaining boundary

`tools/m4a_scheduler.py` implements the tempo accumulator, existing-channel
gate decrement, linked-player-before-mix ordering, fixed buffer size, DMA chunk
sequence and six-chunk reverb ring. Tests lock 0/1/2-tick vectors, recursive
player order, the gate-1 silent boundary, ring wrap and positive/negative
reverb seeds. Compact evidence is
`artifacts/audio/mixer-scheduler-evidence.json`.

The remaining final renderer work is the persistent command VM and channel
allocator: execute runtime GOTO/PATT/REPT, propagate track state, schedule note
gates/envelopes, combine every active DirectSound channel, and advance the
already-modeled noise oscillator on the same 264-frame timeline.
