# Persistent m4a command VM (2026-07-13)

The MIDI executor intentionally stops at the first revisited backward GOTO to
produce a bounded structural audition. That policy cannot drive final PCM:
runtime GOTO changes the command pointer and continues in the same MP2K tick,
and TIE/channel state survives the loop edge.

`tools/m4a_command_vm.py` now consumes the existing decoded command map as a
persistent one-tick-at-a-time control VM. It owns only control state—PC, WAIT,
the 16-entry PATT return stack, REPT counters and running status—and reports
each decoded command to the musical-state/channel layer. This reuses
`tools/decode_m4a_tracks.py`; it does not introduce a second byte parser or
duplicate pitch/gain/envelope logic.

The tick order is explicit:

1. scan gates on channels that existed before the tick;
2. if WAIT is zero, interpret commands continuously until WAIT, FINE or error;
3. decrement WAIT in the same tick in which it is installed;
4. advance LFO after command interpretation.

Backward GOTO and PATT/PEND/REPT execute immediately in that same command
phase. A control loop that consumes the per-tick command budget without ever
reaching WAIT fails explicitly instead of hanging the offline renderer.

All 217 decoded ROM tracks were then executed for a bounded 2,048 ticks. The
VM interpreted 39,825 commands and crossed 163 runtime GOTOs; 79 tracks reached
FINE and 138 remained intentionally active/looping at the duration boundary.
There were no invalid command targets, stack failures or no-WAIT hangs. Compact
counts live in `artifacts/audio/command-vm-evidence.json`.

The remaining renderer layer must retain each track's musical registers,
allocate/steal DirectSound and CGB channels, apply the already-modeled pitch,
gain and envelopes, and feed those channels to the 264-frame SoundMain/DMA
scheduler. The VM alone is not an audible song claim.
