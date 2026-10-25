#!/usr/bin/env python3
"""MP2K (GBA software PSG synth) runtime layout for rom/base.gba.

Everything here is derived from the ROM itself plus the reverse-line notes, and
is re-derived at run time rather than hard-coded:

* sound-number dispatcher table at ROM 0x08465B70 -- one 8-byte row per sound
  ID: {u32 song_descriptor_ptr, u16 player_index}.  This is the authoritative
  "sound ID -> which MP2K player slot owns it" map.
* MP2K player state blocks in IWRAM.  Four slots, 0x40 bytes each:
      slot 0 @ 0x030076B0   (BGM range 1..18)
      slot 1 @ 0x030076F0   (101..105, 156..158)
      slot 2 @ 0x03007730   (106..155)
      slot 3 @ 0x03007780   (51..54)
  Each slot's +0x00 holds the *current song descriptor pointer*, which is the
  cue identity; +0x2C holds the track-array pointer.
* MP2K track arrays, 0x50 bytes per track:
      slot 0 @ 0x03005E58 (10 tracks), slot 1 @ 0x03006178 (1),
      slot 2 @ 0x030061C8 (1), slot 3 @ 0x03006218 (7)
  Track +0x20 is the track status byte (0x00 stopped / 0x40 / 0x80 / 0xC0
  running), +0x40 the current command pointer.

The single capture window used by stream J is IWRAM 0x03005E58..0x030077CF
(0x1978 bytes), which covers the four track arrays, SoundInfo, the DirectSound
and CGB channel pools, and the four player blocks in one contiguous read.
"""
from __future__ import annotations

import pathlib
import struct

# ── ROM-side tables ──────────────────────────────────────────────────────────
DISPATCH_TABLE_ROM = 0x08465B70
DISPATCH_ROW_SIZE = 8
MAX_SOUND_ID = 0x200

# ── IWRAM runtime layout ─────────────────────────────────────────────────────
CAPTURE_BASE = 0x03005E58
CAPTURE_LENGTH = 0x1978

PLAYER_STATE = {
    0: 0x030076B0,
    1: 0x030076F0,
    2: 0x03007730,
    3: 0x03007780,
}
PLAYER_SIZE = 0x40
PLAYER_SONG_OFFSET = 0x00     # u32 song descriptor pointer
PLAYER_TRACKS_OFFSET = 0x2C   # u32 track array pointer

TRACK_ARRAY = {
    0: (0x03005E58, 10),
    1: (0x03006178, 1),
    2: (0x030061C8, 1),
    3: (0x03006218, 7),
}
TRACK_SIZE = 0x50
# track+0x00 is the track status byte.  Verified empirically on this ROM:
#   0x80 -> the track is running
#   0xC0 -> the track is running AND was (re)dispatched on this frame
#            (MP2K's MPlayStart sets status = 0xC0 on the frame it loads a
#            track, and 0x80 on every later frame).
# track+0x40 is the track's current command pointer; it advances while the
# track executes and jumps backwards at a GOTO loop, so it must NOT be used
# as a re-dispatch detector on its own.
TRACK_STATUS_OFFSET = 0x00
TRACK_COMMAND_PTR_OFFSET = 0x40
TRACK_STATUS_RUNNING = 0x80
TRACK_STATUS_DISPATCHED = 0xC0

SOUND_INFO = 0x03006570
CGB_CHANNEL_POOL = 0x030075B0
CGB_CHANNEL_SIZE = 0x40

# ── PSG / I/O block ──────────────────────────────────────────────────────────
PSG_BASE = 0x04000060
PSG_LENGTH = 0x80


def build_sound_table(rom: bytes) -> dict[int, tuple[int, int]]:
    """sound_id -> (song_descriptor_ptr, player_index)."""
    base = DISPATCH_TABLE_ROM - 0x08000000
    table: dict[int, tuple[int, int]] = {}
    for sound_id in range(MAX_SOUND_ID):
        offset = base + sound_id * DISPATCH_ROW_SIZE
        if offset + DISPATCH_ROW_SIZE > len(rom):
            break
        descriptor, player_index = struct.unpack_from("<IH", rom, offset)
        if descriptor:
            table[sound_id] = (descriptor, player_index)
    return table


def build_descriptor_index(table: dict[int, tuple[int, int]]) -> dict[int, int]:
    """song_descriptor_ptr -> sound_id (first ID wins on duplicates)."""
    index: dict[int, int] = {}
    for sound_id, (descriptor, _player) in sorted(table.items()):
        index.setdefault(descriptor, sound_id)
    return index


def decode_player_state(buffer: bytes, slot: int,
                        descriptor_index: dict[int, int]) -> dict:
    """Decode one MP2K player block out of the capture window."""
    offset = PLAYER_STATE[slot] - CAPTURE_BASE
    descriptor = struct.unpack_from("<I", buffer, offset + PLAYER_SONG_OFFSET)[0]
    tracks_pointer = struct.unpack_from("<I", buffer, offset + PLAYER_TRACKS_OFFSET)[0]
    array_base, track_count = TRACK_ARRAY[slot]
    statuses = []
    for index in range(track_count):
        track_offset = (array_base + index * TRACK_SIZE + TRACK_STATUS_OFFSET) - CAPTURE_BASE
        statuses.append(buffer[track_offset])
    command_pointers = []
    for index in range(track_count):
        track_offset = (array_base + index * TRACK_SIZE + TRACK_COMMAND_PTR_OFFSET) - CAPTURE_BASE
        command_pointers.append(
            struct.unpack_from("<I", buffer, track_offset)[0])
    return {
        "slot": slot,
        "descriptor": descriptor,
        "sound_id": descriptor_index.get(descriptor),
        "tracks_pointer": tracks_pointer,
        "track_status": statuses,
        "track_command_ptr": command_pointers,
        "tracks_running": sum(
            1 for status in statuses
            if status & TRACK_STATUS_RUNNING),
        "dispatched_this_frame": any(
            status == TRACK_STATUS_DISPATCHED for status in statuses),
    }


def decode_frame(buffer: bytes, descriptor_index: dict[int, int]) -> dict:
    return {
        "players": [decode_player_state(buffer, slot, descriptor_index)
                    for slot in sorted(PLAYER_STATE)],
    }


def load_rom(path: pathlib.Path) -> bytes:
    return pathlib.Path(path).read_bytes()
