# Audio / palette identity correction（2026-07-11）

The former `audio` and `palettes` banks both claimed file `0x53F138` because
the audio bank had copied the palette entries while its own metadata described
a different table.

Confirmed identities:

- `0x53F138`: the former 88-pointer palette interpretation is now revoked; it
  crossed unrelated motion/callback/sprite objects. The historical `palettes`
  slug now identifies the 15×10-byte motion/effect table at `0x53EE98`;
- `0x599634`: 100 pointers selected for commands `0x80..0xE3` by
  `0x08079668`.

The latter is not audio. `0x08066758` configures a message object and passes the
pointed zero-terminated data to parser `0x0806626C`; its 256 callers are text/UI
sites. Therefore the repository's “custom Sappy dispatcher” conclusion is
revoked. The message table remains reproducibly extractable through
`tools/extract_audio_command_table.py`, but no longer occupies `audio`.

The `audio` bank is now the real sound-ID table at `0x465B70`; the FIFO/DMA
engine and live ID 118 evidence are documented in
`notes/audio-engine-runtime-chain-20260712.md`.
