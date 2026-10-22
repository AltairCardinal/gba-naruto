# Persistent m4a track register state (2026-07-13)

`tools/m4a_track_state.py` connects decoded musical commands to persistent
per-track registers while `tools/m4a_command_vm.py` retains control flow. It
reuses the existing track volume/pan coefficient function; it does not decode
bytes again or duplicate the pitch/sample/envelope modules.

The state covers TEMPO, PRIO, VOICE, VOL, PAN, KEYSH, BEND, BENDR, TUNE,
LFOS/LFODL, MOD and MODT. A note command snapshots voice, inherited key and
velocity, gate or TIE identity, current pitch key/fine and track right/left
coefficients into a `NoteRequest`. EOT creates a matching-key release request;
FINE creates a track-stop request. LFO runs after the tick's command phase and
marks pitch or mix dirty according to MODT.

This runtime layer is deliberately separate from the one-loop MIDI report's
presentation policy. The two share decoded commands and coefficient formulas,
but MIDI stops at a loop boundary while runtime state must persist through it.

All 217 ROM tracks were driven for 2,048 ticks through the persistent command
VM and registers. They emitted 17,546 note requests, 21 EOT requests and 79
FINE stop requests with no invalid state. The note count exceeds the one-loop
16,180 corpus because runtime GOTO continues until the explicit duration
boundary. Compact counts live in
`artifacts/audio/track-register-evidence.json`.

The remaining wiring resolves each request through its song voicegroup and
terminal tone, applies the 10+4 allocator, initializes a channel's pitch/gain/
ADSR/sample state, processes gate/EOT/FINE lifecycle, and sends active channels
to SoundMain.
