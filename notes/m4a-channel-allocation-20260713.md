# m4a channel allocation and steal rules (2026-07-13)

`m4aSoundMode 0x0809AFD8..0x0809B05A` consumes mode literal `0x0095FA00`
(ROM file `0x9AAA4`) and sets `SoundInfo.maxChans=10`. This ROM therefore has
ten pooled DirectSound channels plus four fixed CGB hardware channels. The two
allocators are not interchangeable.

At `ply_note 0x0809A708..0x0809A8FE`, effective priority is
`min(255, playerPriority + trackPriority)`. No executed track contains PRIO, so
track priority remains zero; the 80 song headers use priority 255×58, 0×18 and
10×4.

## DirectSound pool

`0x0809A7F4..0x0809A846` scans the ten slots in order:

1. the first free slot (`status & 0xC7 == 0`) wins immediately;
2. if any released slot exists, every active slot is ignored; among released
   slots choose lowest priority, then highest track address;
3. otherwise an active slot is eligible only when its priority is lower than
   the new note, or equal with `oldTrack > newTrack`; choose lowest priority,
   then highest track address;
4. no eligible slot means the note is silently dropped.

The strict `>` matters: a full pool of the same track and priority cannot steal
its own older DirectSound note. Any released priority-255 channel still outranks
an active priority-0 channel for reuse.

## CGB fixed channels and chains

`0x0809A7B6..0x0809A7F2` maps `tone.type & 7` directly to one of four CGB
channels. Free or released is reusable. Otherwise lower old priority may be
stolen; equal priority uses `oldTrack >= newTrack`, so the same track can
retrigger its fixed hardware channel. This non-strict comparison differs from
DirectSound.

On allocation, `0x0809A848..0x0809A85E` clears the old doubly linked track chain
and inserts the channel at the new track's head. Chains are newest-first.
DirectSound has no same-key deduplication: two key-60 notes may occupy two free
slots. EOT `0x0809A908..0x0809A946` walks newest-first and marks only the first
matching active channel for release, so repeated same-key polyphony needs
repeated EOT.

Steal is immediate, with no release tail. A nonloop sample that exhausts in the
mixer becomes status zero but remains linked until the next track sweep or slot
reuse. FINE unlinks its release tails, so they retain final gain/pitch and no
longer receive dirty propagation.

## Durable implementation and boundary

`tools/m4a_channels.py` implements effective priority, the distinct CGB and
Direct selection rules, newest-first chain maintenance and matching-key EOT.
Tests lock first-free short circuit, released-over-active selection, strict vs
non-strict track-address ties, priority clamping, chain insertion/removal and
same-key behavior. Compact evidence lives in
`artifacts/audio/channel-allocation-evidence.json`.

The remaining renderer work is to connect persistent musical registers/note
commands to these slots and feed active channels through the existing pitch,
envelope, sample and 264-frame mixer modules.
