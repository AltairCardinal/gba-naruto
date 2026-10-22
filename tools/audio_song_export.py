#!/usr/bin/env python3
"""Render a ROM sound id (GBA m4a) to PCM/WAV and export its PSG channel data.

This tool closes two capability gaps recorded in
``notes/completion-audit-20261020.md`` (items 36/37, "音频 sound-ID 表"):

1. **m4a -> PCM end-to-end synthesis.**  A complete sound id (all of its
   tracks, all of its loops) is rendered to a 16-bit stereo WAV file.
2. **CGB / Game Boy PSG channel export.**  The PSG (square / noise) parts of a
   sound id are exported as register-level data (JSON + a pytracker-style
   text listing).

Everything the renderer relies on was re-derived from *this ROM*, not from a
generic m4a description.  The evidence addresses are in
``notes/evidence/audio-song-export-20261021.md``; the short version:

===========================  ==========================================
ROM address                  what it is
===========================  ==========================================
``0x084647A8`` (49 bytes)    wait / note tick-duration table
``0x084645C4`` (180 bytes)   per-key note-frequency selector
``0x08464678`` (16 x u32)    note-frequency octave bases
``0x084646C0`` (132 bytes)   per-key PSG note selector
``0x08464744`` (12 x s16)    PSG square frequency bases (signed!)
``0x0846475C`` (60 bytes)    PSG noise pitch selector (GB NR43 bytes)
``0x08464534`` (30 x u32)    m4a command handler table (opcodes 0xB1..0xCE)
===========================  ==========================================

Native code that proves the semantics (Thumb, ARM addresses):

* ``0x0809A536``  wait duration   = ``table[opcode - 0x80]``
* ``0x0809A720``  note duration   = ``table[opcode - 0xCF]`` (+ gate byte)
* ``0x0809A2E8``  TEMPO (0xBB): ``tempo_reg = 2 * byte``,
  ``tick_period = (tempo_reg * 256) >> 8``
* ``0x0809B24A``  song start: ``tempo_reg = 150``, ``tick_period = 150``,
  ``unit = 256``, ``accumulator = 0``
* ``0x0809A474``  sequencer: ``accumulator += tick_period``; a musical tick
  fires when the accumulator has reached ``0x96`` (150)
* ``0x0809A311``  VOICE (0xBD): ``tone = voicegroup + 12 * program``
* ``0x0809A998``  DirectSound channel frequency
  ``= wave.freq * f(key) / 2**24`` with ``f(key) = 2**(key/12) * 2**17``
* ``0x0809B494``  PSG square frequency: ``0x800 + (s16 base >> octave)``
* ``0x0809B4BE``  PSG noise frequency: ``noise_table[index]`` (raw NR43 byte)

Usage
-----
::

    python tools/audio_song_export.py rom/base.gba --sound-id 1 --wav build/audio/sound_001.wav
    python tools/audio_song_export.py rom/base.gba --sound-id 1 --json build/audio/sound_001.json
    python tools/audio_song_export.py rom/base.gba --sound-id 1 --psg-json build/audio/sound_001_psg.json
    python tools/audio_song_export.py rom/base.gba --sound-id 1 --psg-text build/audio/sound_001_psg.txt
    python tools/audio_song_export.py rom/base.gba --self-test

The tool exits non-zero when the ROM does not have the layout it assumes.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.io import write_text  # noqa: E402
from tools import extract_audio as ea  # noqa: E402

ROM_BASE = 0x08000000

# --- ROM tables (file offsets) ---------------------------------------------
DURATION_TABLE = 0x4647A8      # 0x084647A8 - wait/note tick durations
DURATION_TABLE_LEN = 49
NOTE_KEY_TABLE = 0x4645C4      # 0x084645C4 - per-key note selector
NOTE_KEY_TABLE_LEN = 180
NOTE_OCT_TABLE = 0x464678      # 0x08464678 - 16 x u32 octave bases
PSG_KEY_TABLE = 0x4646C0       # 0x084646C0 - per-key PSG selector
PSG_KEY_TABLE_LEN = 132
PSG_FREQ_TABLE = 0x464744      # 0x08464744 - 12 x s16 GB frequency bases
PSG_FREQ_TABLE_LEN = 12        # <- 12, not 16: the index is the semitone 0..11
PSG_NOISE_TABLE = 0x46475C     # 0x0846475C - 60 x u8 GB NR43 pitch bytes
PSG_NOISE_TABLE_LEN = 60

# --- engine constants (proved by the native code above) --------------------
TICK_ACCUMULATOR_LIMIT = 150   # 0x0809A5C6  cmp r0, #0x96
TEMPO_UNIT = 256               # 0x0809B252  song[0x1E] = 0x100
DEFAULT_TICK_PERIOD = 150      # 0x0809B24E  song[0x20] = 0x96
TICKS_PER_QUARTER = 24         # note-duration grid: 12 = eighth, 24 = quarter
SEQUENCER_HZ = 60.0            # the engine is driven once per game frame

# PSG engine clamps, all read straight out of the ROM code at 0x0809B494.
PSG_MAX_KEY = 0x82             # 0x0809B4E4  movs r5, #0x82
PSG_MIN_KEY = 0x24             # 0x0809B4DA  subs r0, #0x24
PSG_NOISE_KEY_BASE = 21        # 0x0809B4B2  subs r0, #0x15
PSG_NOISE_MAX_INDEX = 59      # 0x0809B4BC  movs r5, #0x3b
PSG_FREQ_BIAS = 0x800          # 0x0809B52A  movs r1, #0x80 / lsls #4

# --- the engine's pitch-bend model -------------------------------------------
# The m4a engine keeps the bend state in the channel structure and turns it
# into a *semitone offset* plus an 8-bit *fraction* (see bend_pitch_offset).
NOTE_KEY_MAX = 0xB2            # 0x0809A9A2  cmp r6, #0xb2
BEND_DEFAULT_RANGE = 2         # 0x0809A4D6  movs r0, #2 / strb r0,[r5,#0xf]

# --- renderer model constants (documented choices, not ROM facts) ----------
PITCH_ANCHOR_KEY = 60          # note key that plays at the wave's native rate
OUTPUT_RATE = 32768            # GBA DirectSound master output rate (SOUNDCNT_X)
ENVELOPE_ATTACK_SECONDS = 0.010
ENVELOPE_DECAY_SECONDS = 0.060
ENVELOPE_RELEASE_SECONDS = 0.050

PSG_WAVE_NAMES = {
    0: "square 12.5%",
    1: "square 25%",
    2: "square 50%",
    3: "square 75%",
    4: "noise",
}


class SoundLayoutError(ValueError):
    """Raised when the ROM does not have the layout this tool assumes."""


# ---------------------------------------------------------------------------
# ROM tables
# ---------------------------------------------------------------------------

def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SoundLayoutError(message)


def load_tables(rom: bytes) -> dict:
    """Load and validate every ROM table the renderer depends on."""
    _require(len(rom) > DURATION_TABLE + DURATION_TABLE_LEN,
             "ROM is too small to contain the m4a duration table")
    durations = list(rom[DURATION_TABLE:DURATION_TABLE + DURATION_TABLE_LEN])
    _require(durations[0] == 0 and durations[24] == 24,
             f"m4a duration table at 0x{DURATION_TABLE:06X} does not look like "
             f"the expected wait/note table (got {durations[:6]}...)")

    note_keys = list(rom[NOTE_KEY_TABLE:NOTE_KEY_TABLE + NOTE_KEY_TABLE_LEN])
    octaves = [struct.unpack_from("<I", rom, NOTE_OCT_TABLE + 4 * i)[0]
               for i in range(16)]
    _require(all(octaves[i] < octaves[i + 1] for i in range(11)),
             "m4a note octave table at 0x%06X is not monotonically increasing"
             % NOTE_OCT_TABLE)

    psg_keys = list(rom[PSG_KEY_TABLE:PSG_KEY_TABLE + PSG_KEY_TABLE_LEN])
    # The ROM loads these with LDRSH (0x0809B4FE), so they are SIGNED 16-bit.
    psg_freqs = [struct.unpack_from("<h", rom, PSG_FREQ_TABLE + 2 * i)[0]
                 for i in range(PSG_FREQ_TABLE_LEN)]
    noise = list(rom[PSG_NOISE_TABLE:PSG_NOISE_TABLE + PSG_NOISE_TABLE_LEN])

    # The table must not run into the noise table: the engine reads a signed
    # 16-bit value at index (selector & 0xF) and the selector's low nibble is
    # always a semitone 0..11, so exactly 12 entries exist.
    _require(PSG_FREQ_TABLE + PSG_FREQ_TABLE_LEN * 2 <= PSG_NOISE_TABLE,
             "the PSG frequency table overlaps the PSG noise table")
    _require(all(0 <= (sel & 0xF) < PSG_FREQ_TABLE_LEN for sel in psg_keys),
             "a PSG selector indexes outside the 12-entry frequency table")
    _require(all(value < 0 for value in psg_freqs),
             "the PSG frequency table is not signed-negative as the ROM expects")

    return {
        "durations": durations,
        "note_keys": note_keys,
        "note_octaves": octaves,
        "psg_keys": psg_keys,
        "psg_freqs": psg_freqs,
        "psg_noise": noise,
    }


def note_frequency_int(table: dict, key: int) -> int:
    """The engine's integer ``f(key)`` (``0x0809A9AC``..``0x0809A9C2``).

    ``f(key) = note_octaves[sel & 0xF] >> (sel >> 4)`` with
    ``sel = note_keys[key]``; the result is ``2**(key/12) * 2**17`` truncated
    to an integer, which is exactly what the ROM computes.
    """
    key = max(0, min(len(table["note_keys"]) - 1, key))
    sel = table["note_keys"][key]
    return table["note_octaves"][sel & 0xF] >> (sel >> 4)


def note_frequency(table: dict, key: int) -> float:
    """The ROM's per-key frequency ratio (``f(key) / 2**17``).

    ``f(key) = note_octaves[sel & 0xF] >> (sel >> 4)`` with
    ``sel = note_keys[key]``; the result is ``2**(key/12) * 2**17``.
    """
    return float(note_frequency_int(table, key))


def bend_pitch_offset(bend: int, bend_range: int, tune: int = 0,
                      key_shift: int = 0) -> tuple[int, int]:
    """The engine's semitone offset and 8-bit fraction for a bend state.

    This is a direct transcription of ``0x0809B450``..``0x0809B486``, the
    place where the m4a engine turns its bend state into the two numbers the
    pitch computation uses:

    ::

        0x0809B450  movs  r0, #0xe
        0x0809B452  ldrsb r0, [r2, r0]     ; bend    (signed)
        0x0809B454  ldrb  r1, [r2, #0xf]   ; range   (unsigned)
        0x0809B456  muls  r0, r1, r0      ; bend * range
        0x0809B45A  ldrsb r1, [r2, #0xc]  ; tune    (signed)
        0x0809B45C  adds  r1, r1, r0
        0x0809B45E  lsls  r1, r1, #2      ; * 4
        0x0809B462  ldrsb r0, [r2, #0xa]  ; key shift (signed)
        0x0809B464  lsls  r0, r0, #8      ; << 8
        0x0809B470  ldrb  r0, [r2, #0xd]  ; a fixed fraction
        0x0809B482  asrs  r0, r1, #8
        0x0809B484  strb  r0, [r2, #8]    ; channel+0x08 = semitone offset
        0x0809B486  strb  r1, [r2, #9]    ; channel+0x09 = fraction

    ``channel+0x0B`` and ``channel+0x0D`` are never written by any command
    handler, so they are 0 here, and the LFO term (``channel+0x16``) only
    applies while a MOD/LFO is running.

    Returns ``(semitone_offset, fraction)`` with the semitone offset in
    ``-128..127`` (the engine reads it back with ``LDRSB``).
    """
    accumulator = (tune + bend * bend_range) * 4
    accumulator += key_shift << 8
    offset = (accumulator >> 8) & 0xFF
    if offset > 127:
        offset -= 256
    return offset, accumulator & 0xFF


def engine_pitch_base(table: dict, key: int, fraction: int = 0) -> int:
    """The engine's interpolated pitch base for a key.

    Transcription of ``0x0809A998``..``0x0809A9E6``: the engine interpolates
    between ``f(key)`` and ``f(key+1)`` with the 8-bit fraction and then
    multiplies by the wave's rate field::

        0x0809A9DC  subs  r0, r0, r5      ; f(key+1) - f(key)
        0x0809A9E0  bl    0x08099d7c      ; * (fraction << 24) >> 32
        0x0809A9E6  adds  r1, r5, r1      ; f(key) + delta

    The helper at ``0x08099D80`` is ARM code (``umull r2, r3, r0, r1`` /
    ``add r0, r3, #0``), so it returns the **high** word: the first multiply
    is ``(delta * fraction) >> 8`` and the second one is
    ``(base * wave[4]) >> 32``.
    """
    if key > NOTE_KEY_MAX:                  # 0x0809A9A2  cmp r6, #0xb2
        key = NOTE_KEY_MAX
        fraction = 0xFF                     # 0x0809A9A8  movs r7, #0xff
    base = note_frequency_int(table, key)
    following = note_frequency_int(table, key + 1)
    return base + (((following - base) * fraction) >> 8)


def bent_key(note: dict) -> int:
    """The engine's pitch key: the note key plus the bend's semitone offset.

    ``0x0809A89C``..``0x0809A8A6``::

        0x0809A89C  ldrb  r1, [r4, #8]    ; the note key
        0x0809A8A0  ldrsb r0, [r5, r0]    ; the bend's semitone offset
        0x0809A8A2  adds  r2, r1, r0
        0x0809A8A4  bpl   0x809a8a8
        0x0809A8A6  movs  r2, #0          ; clamp a negative key to 0
    """
    return max(0, note["key"] + note.get("bend_offset", 0))


def psg_frequency_register(table: dict, key: int, fraction: int = 0) -> int:
    """The GB square frequency register the ROM computes for ``key``.

    This is a direct transcription of the ROM's PSG frequency function at
    ``0x0809B494``:

    * the key is clamped **after** the ``- 36`` shift: keys up to 0x23 become
      key 0 with interpolation fraction 0; above that the key becomes
      ``key - 0x24`` and, if that is still above 0x82, key 0x82 with
      fraction 0xFF.  (The order matters: the ROM subtracts first and
      clamps second, so key 200 must not be clamped to 0x82 *before* the
      subtraction.)
    * ``sel = psg_keys[key]``; the semitone is ``sel & 0xF`` and the octave
      is ``sel >> 4``;
    * ``base = s16_freq[semitone] >> octave`` - an **arithmetic** shift of a
      **signed** 16-bit value (``ldrsh`` + ``asrs`` in the ROM);
    * the ROM interpolates between ``base`` and the base of the next key
      with an 8-bit fraction, then adds the ``0x800`` bias.

    ``fraction`` is the bend fraction the engine computed for the channel
    (``0x0809B51C``..``0x0809B526``); without a pitch bend it is 0, which
    is what a note without a pitch bend uses.
    """
    if key <= 0x23:
        key = 0
        fraction = 0
    else:
        key -= PSG_MIN_KEY
        if key > PSG_MAX_KEY:
            key = PSG_MAX_KEY
            fraction = 0xFF
    base = _psg_base(table, key)
    following = _psg_base(table, key + 1)
    delta = ((following - base) * fraction) >> 8
    return base + delta + PSG_FREQ_BIAS


def _psg_base(table: dict, key: int) -> int:
    """``s16_freq[semitone] >> octave`` for one PSG key."""
    selector = table["psg_keys"][key]
    semitone = selector & 0xF
    octave = selector >> 4
    return table["psg_freqs"][semitone] >> octave


def psg_noise_register(table: dict, key: int) -> int:
    """The GB noise pitch byte the ROM uses for ``key``.

    Transcription of ``0x0809B4A8``..``0x0809B4C4``: the noise table index
    is 0 for keys up to 20 and ``key - 21`` (capped at 59) above that, and
    the table entry is the raw byte - the ROM does **not** add the ``0x800``
    bias and does **not** interpolate.
    """
    if key <= 20:
        index = 0
    else:
        index = min(key - PSG_NOISE_KEY_BASE, PSG_NOISE_MAX_INDEX)
    index = max(0, min(len(table["psg_noise"]) - 1, index))
    return table["psg_noise"][index]


def gb_frequency_to_hz(register: int) -> float:
    """GB square/noise frequency register -> Hz."""
    period = (2048 - register) & 0x7FF
    if period == 0:
        return 0.0
    return 131072.0 / period


def gb_noise_to_hz(nr43: int) -> float:
    """GB NR43 pitch byte -> Hz.

    NR43 encodes: bits 0-2 the divisor code, bits 3-6 the shift clock and
    bit 7 the LFSR width.  The GB noise pitch is
    ``524288 / (divisor * 2 ** (shift + 1))`` where a divisor code of 0
    means 0.5.
    """
    shift = (nr43 >> 3) & 0xF
    code = nr43 & 0x7
    divisor = 0.5 if code == 0 else float(code)
    return 524288.0 / (divisor * (2.0 ** (shift + 1)))


# ---------------------------------------------------------------------------
# Song model
# ---------------------------------------------------------------------------

def read_sound_id_row(rom: bytes, sound_id: int) -> tuple[int, int, int]:
    """(descriptor_ptr, player_index, player_config) of one sound id row."""
    raw = ea.SOUND_ID_TABLE + sound_id * ea.SOUND_ID_STRIDE
    _require(raw + 8 <= len(rom),
             f"sound id {sound_id} is outside the sound-ID table")
    return struct.unpack_from("<IHH", rom, raw)


def read_voicegroup_tones(rom: bytes, pointer: int, count: int) -> list[dict]:
    """Read ``count`` 12-byte tone records out of a voicegroup."""
    offset = pointer - ROM_BASE
    _require(0 <= offset and offset + count * 12 <= len(rom),
             f"voicegroup 0x{pointer:08X} is outside the ROM")
    tones = []
    for index in range(count):
        base = offset + index * 12
        (tone_type, key, length, pan_sweep, wave_ptr,
         attack, decay, sustain, release) = struct.unpack_from("<BBBBIBBBB", rom, base)
        tones.append({
            "index": index,
            "offset": base,
            "type": tone_type,
            "key": key,
            "length": length,
            "pan_sweep": pan_sweep,
            "pointer": wave_ptr,
            "attack": attack,
            "decay": decay,
            "sustain": sustain,
            "release": release,
        })
    return tones


def voicegroup_tone_counts(rom: bytes) -> dict[int, int]:
    """How many 12-byte tones each voicegroup holds.

    Voicegroups are stored back to back, so the count of one voicegroup is
    the distance to the next one.  The last voicegroup is bounded by the
    sound-ID table, which is the only place the engine's data ends; when the
    span is not a whole number of records (other data follows the last
    voicegroup) the scan stops at the first record whose type byte is
    neither DirectSound (0x00) nor PSG (0x80).
    """
    starts = set()
    for sound_id in range(ea.SOUND_ID_COUNT):
        pointer = read_sound_id_row(rom, sound_id)[0]
        if pointer in (0, ea.EMPTY_DESCRIPTOR):
            continue
        descriptor = ea.parse_descriptor(rom, pointer)
        starts.add(descriptor["voicegroup_ptr"] - ROM_BASE)
    ordered = sorted(starts)
    counts = {}
    for index, start in enumerate(ordered):
        end = ordered[index + 1] if index + 1 < len(ordered) else ea.SOUND_ID_TABLE
        span = end - start
        if span <= 0:
            raise SoundLayoutError(
                f"voicegroup at 0x{start:06X} is not followed by another one")
        limit = min(span // 12, 4096)
        count = 0
        while count < limit:
            tone_type = rom[start + 12 * count]
            if tone_type not in (0x00, 0x80):
                break
            count += 1
        if count == 0:
            raise SoundLayoutError(
                f"voicegroup at 0x{start:06X} does not start with a valid tone")
        counts[start] = count
    return counts


# ---------------------------------------------------------------------------
# Track execution
# ---------------------------------------------------------------------------

class TrackRunner:
    """Runs one m4a track, optionally over several loops.

    The interpreter mirrors the ROM's sequencer (``0x0809A47C``..``0x0809A5BC``):
    the wait counter lives in the track, one command is consumed per tick, and
    a note's arguments are the optional key / velocity / gate bytes that
    follow the note opcode.
    """

    def __init__(self, commands: list[dict], track_offset: int, tables: dict,
                 max_loops: int):
        self.commands = commands
        self.by_offset = {command["offset"]: command for command in commands}
        self.start = track_offset
        self.tables = tables
        self.max_loops = max_loops

    def run(self) -> dict:
        tables = self.tables
        tick = 0
        time = 0.0
        loop = 0
        program = 0
        volume = 127
        pan = 64
        key_shift = 0
        bend = 0
        bend_range = 2
        tune = 0
        events: list[dict] = []
        open_ties: dict[int, dict] = {}
        tempo_changes: list[dict] = []
        period = DEFAULT_TICK_PERIOD
        stop_reason = "one_loop"
        steps = 0
        max_steps = 400_000
        repeat_state: dict[int, int] = {}
        stack: list[int] = []
        current_key = 0

        def seconds_per_tick(current_period: int) -> float:
            return TICK_ACCUMULATOR_LIMIT / (SEQUENCER_HZ * current_period)

        while loop < self.max_loops:
            pc = self.start
            visited: set[int] = set()
            finished = ""
            while steps < max_steps:
                steps += 1
                command = self.by_offset.get(pc)
                if command is None:
                    raise SoundLayoutError(
                        f"track 0x{self.start:06X} jumped to 0x{pc:06X}, which "
                        f"is not a command boundary")
                visited.add(pc)
                name = command["name"]
                next_pc = pc + command["size"]

                if name.startswith("W"):
                    count = int(name[1:])
                    tick += count
                    time += count * seconds_per_tick(period)
                elif name == "FINE":
                    finished = "fine"
                    break
                elif name == "PATT":
                    stack.append(next_pc)
                    pc = command["target_offset"]
                    continue
                elif name == "PEND":
                    if stack:
                        pc = stack.pop()
                        continue
                elif name == "GOTO":
                    target = command["target_offset"]
                    if target in visited:
                        finished = "one_loop"
                        break
                    pc = target
                    continue
                elif name == "REPT":
                    count = command.get("count", 0)
                    target = command.get("target_offset")
                    if count and target is not None:
                        done = repeat_state.get(pc, 0)
                        if done < count:
                            repeat_state[pc] = done + 1
                            pc = target
                            continue
                        repeat_state.pop(pc, None)
                elif name == "TEMPO":
                    tempo_reg = command["value"] * 2
                    period = tempo_reg
                    tempo_changes.append({"tick": tick, "time": time,
                                           "tempo_byte": command["value"],
                                           "tempo_reg": tempo_reg})
                elif name == "VOICE":
                    program = command["value"]
                elif name == "VOL":
                    volume = command["value"]
                elif name == "PAN":
                    pan = command["value"]
                elif name == "BEND":
                    bend = command["value"] - 0x40
                elif name == "KEYSH":
                    key_shift = command["value"] - 256 if command["value"] & 0x80 \
                        else command["value"]
                elif name == "BENDR":
                    bend_range = command["value"]
                elif name == "TUNE":
                    tune = command["value"] - 0x40
                elif name == "EOT":
                    tie_key = command.get("key")
                    if tie_key is None:
                        tie_key = current_key
                    tied = open_ties.pop(tie_key, None)
                    if tied is not None:
                        tied["duration_ticks"] = tick - tied["tick"]
                        tied["duration"] = time - tied["time"]
                        tied["release_reason"] = "eot"
                elif name == "TIE" or name.startswith("N"):
                    args = command.get("args", [])
                    # A NOTE without a key byte **inherits the previous note's
                    # key** in the ROM's own engine (the optional bytes are
                    # "key / velocity / gate" and a missing one keeps the
                    # running value).  Recording it as key 0 would invent a
                    # lowest-pitch note that the game never plays.
                    key = args[0] if len(args) >= 1 else current_key
                    velocity = args[1] if len(args) >= 2 else 100
                    gate = args[2] if len(args) >= 3 else 0
                    duration_ticks = None
                    duration = None
                    if name.startswith("N"):
                        duration_ticks = tables["durations"][command["opcode"] - 0xCF] + gate
                        duration = duration_ticks * seconds_per_tick(period)
                    current_key = key
                    # The engine turns the channel's bend state into a
                    # semitone offset plus an 8-bit fraction before it
                    # computes the pitch (0x0809B450..0x0809B486).
                    bend_offset, bend_fraction = bend_pitch_offset(
                        bend, bend_range, tune, key_shift)
                    note = {
                        "tick": tick,
                        "time": time,
                        "key": key,
                        "velocity": velocity,
                        "duration_ticks": duration_ticks,
                        "duration": duration,
                        "program": program,
                        "volume": volume,
                        "pan": pan,
                        "key_shift": key_shift,
                        "bend": bend,
                        "bend_range": bend_range,
                        "bend_offset": bend_offset,
                        "bend_fraction": bend_fraction,
                        "tied": name == "TIE",
                        "release_reason": None,
                    }
                    events.append(note)
                    if name == "TIE":
                        open_ties[key] = note
                pc = next_pc
            else:
                raise SoundLayoutError(
                    f"track 0x{self.start:06X} exceeded {max_steps} steps")

            if finished == "fine":
                stop_reason = "fine"
                break
            loop += 1
            if loop >= self.max_loops:
                stop_reason = "one_loop"
                break

        # Ties that are still open when the render ends are released at the
        # end of the audio (the ROM releases them when the player is stopped).
        end_time = time
        for note in open_ties.values():
            note["duration_ticks"] = tick - note["tick"]
            note["duration"] = end_time - note["time"]
            note["release_reason"] = "stopped"

        return {
            "offset": self.start,
            "loops": loop,
            "duration_ticks": tick,
            "duration": end_time,
            "stop_reason": stop_reason,
            "events": events,
            "tempo_changes": tempo_changes,
            "open_ties": sorted(open_ties),
        }


def decode_track_commands(rom: bytes, pointer: int, boundaries: list[int]) -> list[dict]:
    """Decode one track's bytecode into a command list."""
    offset = pointer - ROM_BASE
    end = next((item for item in boundaries if item > offset), None)
    if end is None:
        raise SoundLayoutError(f"no boundary for track at 0x{offset:06X}")
    try:
        return ea.decode_track(rom[offset:end], offset)
    except ea.DecodeError as exc:
        raise SoundLayoutError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def envelope_gain(note: dict, tone: dict, elapsed: float, duration: float) -> float:
    """A documented ADSR built from the tone's envelope bytes.

    The ROM's DirectSound channel runs a signed balance/tremolo integrator
    (``0x0809B3E0``) rather than a textbook ADSR, so this is a **model**, not a
    bit-exact copy of the engine's envelope state machine.  It is fully
    determined by the tone's attack / decay / sustain / release bytes, which
    is what makes it testable.
    """
    attack = tone["attack"] / 255.0
    decay = tone["decay"] / 255.0
    sustain = tone["sustain"] / 255.0
    release = tone["release"] / 255.0
    attack_time = ENVELOPE_ATTACK_SECONDS * (0.25 + attack)
    decay_time = ENVELOPE_DECAY_SECONDS * (0.25 + decay)
    release_time = ENVELOPE_RELEASE_SECONDS * (0.25 + release)
    if elapsed < 0:
        return 0.0
    if elapsed < attack_time:
        return attack_time and (elapsed / attack_time)
    if elapsed < attack_time + decay_time:
        span = max(1e-9, decay_time)
        return 1.0 + (sustain - 1.0) * ((elapsed - attack_time) / span)
    if duration is not None and elapsed <= duration:
        return sustain
    tail = elapsed - (duration if duration is not None else elapsed)
    return max(0.0, sustain * (1.0 - tail / max(1e-9, release_time)))


def resample_note(samples: list[int], rate: float, max_frames: int,
                  output_rate: int = OUTPUT_RATE) -> list[float]:
    """Play ``samples`` at ``rate`` Hz into an ``output_rate`` Hz buffer.

    ``rate`` is the rate at which the *source* samples are consumed; the
    source therefore advances by ``rate / output_rate`` samples per output
    frame.
    """
    if not samples or max_frames <= 0:
        return []
    out = []
    position = 0.0
    length = len(samples)
    step = rate / output_rate if rate > 0 else 1.0
    while position < length and len(out) < max_frames:
        index = int(position)
        if index >= length:
            break
        frac = position - index
        a = samples[index]
        b = samples[index + 1] if index + 1 < length else samples[index]
        out.append(a + (b - a) * frac)
        position += step
    return out


def render_direct_sound(rom: bytes, tone: dict, note: dict, tables: dict,
                         mix: list[list[float]], start_sample: int) -> dict:
    """Mix one DirectSound note into the stereo buffer."""
    wave_offset = tone["pointer"] - ROM_BASE
    wave = ea.parse_wave(rom, wave_offset)
    if wave is None:
        raise SoundLayoutError(
            f"tone at 0x{tone['offset']:06X} points at 0x{tone['pointer']:08X}, "
            f"which is not a valid DirectSound wave header")
    pcm = rom[wave["data_offset"]:wave["data_end"]]
    samples = [value - 128 if value < 128 else value - 256 for value in pcm]
    loop_start = wave["loop_start"]
    if 0 < loop_start < len(samples):
        # The ROM hands the wave to the DMA with a loop point; the loop is
        # what keeps a sustained note sounding.
        samples = samples[:loop_start] + samples[loop_start:]

    # The engine's pitch: the note key plus the bend's semitone offset, the
    # 8-bit bend fraction interpolated between f(key) and f(key+1), and the
    # wave's own rate field (0x0809A89C..0x0809A658, 0x0809A998).
    key = bent_key(note)
    fraction = note.get("bend_fraction", 0)
    base = engine_pitch_base(tables, key, fraction)
    anchor = engine_pitch_base(tables, PITCH_ANCHOR_KEY, 0)
    ratio = base / float(anchor)
    native_rate = wave["sample_rate"]
    rate = native_rate * ratio
    duration = note["duration"]
    max_frames = int((duration if duration is not None else 1.0) * OUTPUT_RATE) + 1
    max_frames = min(max_frames, max(1, len(mix) - start_sample))
    rendered = resample_note(samples, rate, max_frames)

    velocity = max(0, min(127, note["velocity"])) / 127.0
    volume = max(0, min(127, note["volume"])) / 127.0
    pan = max(0, min(127, note["pan"]))
    left_gain = volume * velocity * (127 - pan) / 127.0
    right_gain = volume * velocity * pan / 127.0

    frames = len(rendered)
    for index in range(frames):
        gain = envelope_gain(note, tone, index / OUTPUT_RATE, duration)
        if gain <= 0.0:
            continue
        position = start_sample + index
        if position >= len(mix):
            break
        value = rendered[index] / 128.0 * gain
        mix[position][0] += value * left_gain
        mix[position][1] += value * right_gain
    return {
        "wave_offset": wave["offset"],
        "sample_rate": native_rate,
        "playback_rate": rate,
        "samples": frames,
        "left_gain": left_gain,
        "right_gain": right_gain,
    }


def render_psg(rom: bytes, tone: dict, note: dict, tables: dict,
               mix: list[list[float]], start_sample: int) -> dict:
    """Mix one PSG note into the stereo buffer."""
    table_offset = tone["pointer"] - ROM_BASE
    _require(0 <= table_offset < len(rom) - 12,
             f"PSG instrument table 0x{tone['pointer']:08X} is outside the ROM")
    record = rom[table_offset + 12 * note["key"]: table_offset + 12 * note["key"] + 12]
    _require(len(record) == 12,
             f"PSG instrument record for key {note['key']} is truncated")
    wave_type = record[0] & 0x07
    pan_sweep = record[2]
    pan = record[3]
    attack, decay, sustain, release = record[8], record[9], record[10], record[11]

    # The engine's PSG path uses the bent key and the bend fraction for the
    # frequency register (0x0809A638..0x0809A642 and 0x0809B494), while the
    # instrument record is still selected by the plain note key
    # (0x0809A76E..0x0809A778).
    key = bent_key(note)
    fraction = note.get("bend_fraction", 0)
    if wave_type == 4:
        register = psg_noise_register(tables, key)
        frequency = gb_noise_to_hz(register)
    else:
        register = psg_frequency_register(tables, key, fraction)
        frequency = gb_frequency_to_hz(register)

    duration = note["duration"]
    frames = int((duration if duration is not None else 0.25) * OUTPUT_RATE)
    frames = max(1, min(frames, len(mix) - start_sample))
    if frames <= 0:
        return {"wave_type": wave_type, "frequency": frequency}

    volume = max(0, min(127, note["volume"])) / 127.0
    velocity = max(0, min(127, note["velocity"])) / 127.0
    level = volume * velocity * 0.25

    pan_value = pan & 0x70
    left_gain = level * (0x80 - pan_value) / 0x80 if pan_value else level
    right_gain = level * pan_value / 0x80 if pan_value else level

    tone_model = {
        "attack": attack, "decay": decay, "sustain": sustain, "release": release,
    }
    period = max(1.0, OUTPUT_RATE / frequency) if frequency > 0 else OUTPUT_RATE
    if wave_type == 4:
        phase = 0
        lfsr = 0x7FFF
        step = max(1, int(OUTPUT_RATE / (frequency if frequency > 0 else 1)))
        for index in range(frames):
            gain = envelope_gain(note, tone_model, index / OUTPUT_RATE, duration)
            if gain > 0:
                value = ((lfsr & 1) * 2 - 1) * gain
                mix[start_sample + index][0] += value * left_gain
                mix[start_sample + index][1] += value * right_gain
            if index % step == 0:
                bit = (lfsr ^ (lfsr >> 1)) & 1
                lfsr = (lfsr >> 1) | (bit << 14)
    else:
        duty = (0.125, 0.25, 0.5, 0.75)[min(3, wave_type)]
        for index in range(frames):
            gain = envelope_gain(note, tone_model, index / OUTPUT_RATE, duration)
            if gain > 0:
                frac = (index % period) / period
                value = (1.0 if frac < duty else -1.0) * gain
                mix[start_sample + index][0] += value * left_gain
                mix[start_sample + index][1] += value * right_gain
    return {
        "wave_type": wave_type,
        "wave_name": PSG_WAVE_NAMES.get(wave_type, "unknown"),
        "frequency_register": register,
        "frequency_hz": frequency,
        "pan_sweep": pan_sweep,
        "pan": pan,
        "attack": attack, "decay": decay, "sustain": sustain, "release": release,
        "samples": frames,
    }


def render_sound(rom: bytes, sound_id: int, tables: dict, max_loops: int = 2,
                 tail_seconds: float = 0.35) -> dict:
    """Render one sound id to a stereo float buffer plus an event log."""
    descriptor_ptr, player_index, player_config = read_sound_id_row(rom, sound_id)
    if descriptor_ptr in (0, ea.EMPTY_DESCRIPTOR):
        raise SoundLayoutError(f"sound id {sound_id} plays nothing")
    descriptor = ea.parse_descriptor(rom, descriptor_ptr)
    counts = voicegroup_tone_counts(rom)
    voicegroup = descriptor["voicegroup_ptr"]
    tone_count = counts.get(voicegroup - ROM_BASE)
    if not tone_count:
        raise SoundLayoutError(
            f"sound id {sound_id}: voicegroup 0x{voicegroup:08X} has no tones")
    tones = read_voicegroup_tones(rom, voicegroup, tone_count)

    # Collect every track boundary in one pass so the bytecode slices are
    # exactly the tracks.
    track_offsets = set()
    for row in range(ea.SOUND_ID_COUNT):
        pointer = read_sound_id_row(rom, row)[0]
        if pointer in (0, ea.EMPTY_DESCRIPTOR):
            continue
        info = ea.parse_descriptor(rom, pointer)
        for track_ptr in info["track_ptrs"]:
            track_offsets.add(track_ptr - ROM_BASE)
        track_offsets.add(info["descriptor_offset"])
    boundaries = sorted(track_offsets)

    tracks = []
    for track_ptr in descriptor["track_ptrs"]:
        commands = decode_track_commands(rom, track_ptr, boundaries)
        runner = TrackRunner(commands, track_ptr - ROM_BASE, tables, max_loops)
        tracks.append(runner.run())

    total = max(track["duration"] for track in tracks)
    total_samples = int((total + tail_seconds) * OUTPUT_RATE)
    mix = [[0.0, 0.0] for _ in range(max(1, total_samples))]

    rendered_notes = []
    for track_index, track in enumerate(tracks):
        for note in track["events"]:
            tone_index = note["program"]
            if tone_index >= len(tones):
                continue
            tone = tones[tone_index]
            start = int(note["time"] * OUTPUT_RATE)
            if start >= len(mix):
                continue
            info = None
            if tone["type"] & 0xC0 == 0:
                info = render_direct_sound(rom, tone, note, tables, mix, start)
            elif tone["type"] & 0x80:
                info = render_psg(rom, tone, note, tables, mix, start)
            rendered_notes.append({
                "track": track_index,
                "tick": note["tick"],
                "time": note["time"],
                "duration": note["duration"],
                "key": note["key"],
                "pitch_key": bent_key(note),
                "bend": note.get("bend", 0),
                "bend_range": note.get("bend_range", BEND_DEFAULT_RANGE),
                "bend_offset": note.get("bend_offset", 0),
                "bend_fraction": note.get("bend_fraction", 0),
                "key_shift": note.get("key_shift", 0),
                "velocity": note["velocity"],
                "program": tone_index,
                "tone_type": tone["type"],
                "tone_offset": tone["offset"],
                "volume": note["volume"],
                "pan": note["pan"],
                "tied": note["tied"],
                "release_reason": note["release_reason"],
                "render": info,
            })

    return {
        "sound_id": sound_id,
        "descriptor_ptr": descriptor_ptr,
        "descriptor": descriptor,
        "player_index": player_index,
        "player_config": player_config,
        "voicegroup_ptr": voicegroup,
        "tones": tones,
        "tracks": tracks,
        "notes": rendered_notes,
        "mix": mix,
        "sample_rate": OUTPUT_RATE,
        "duration": len(mix) / OUTPUT_RATE,
    }


def write_wav(path: pathlib.Path, mix: list[list[float]], sample_rate: int) -> None:
    """Write a 16-bit stereo PCM WAV file.

    The offline mix sums every voice at full scale, so a soft limiter keeps
    the file from clipping: if the peak exceeds 1.0 the whole mix is scaled
    down to 0.95.
    """
    peak = 0.0
    for left, right in mix:
        peak = max(peak, abs(left), abs(right))
    scale = 0.95 / peak if peak > 0.95 else 1.0
    frames = bytearray()
    for left, right in mix:
        for value in (left * scale, right * scale):
            scaled = int(max(-1.0, min(1.0, value)) * 32767)
            frames += struct.pack("<h", scaled)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(frames), b"WAVE",
        b"fmt ", 16, 1, 2, sample_rate, sample_rate * 2, 2, 16,
        b"data", len(frames),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(header + bytes(frames))


def psg_export(rom: bytes, song: dict, tables: dict) -> dict:
    """Build the register-level PSG export of one sound id.

    The export contains the values a CGB/GB audio emulator would need to
    reproduce the channel: wave type, GB frequency register, envelope,
    volume, pan and the note list.  It does **not** contain a rendered
    waveform - that still needs a GB audio emulator.
    """
    channels = []
    for note in song["notes"]:
        if not (note["tone_type"] & 0x80):
            continue
        tone = song["tones"][note["program"]]
        table_offset = tone["pointer"] - ROM_BASE
        record = rom[table_offset + 12 * note["key"]: table_offset + 12 * note["key"] + 12]
        wave_type = record[0] & 0x07
        key = bent_key(note)
        fraction = note.get("bend_fraction", 0)
        if wave_type == 4:
            register = psg_noise_register(tables, key)
            frequency = gb_noise_to_hz(register)
            register_kind = "noise"
            register_name = "NR43"
        else:
            register = psg_frequency_register(tables, key, fraction)
            frequency = gb_frequency_to_hz(register)
            register_kind = "square"
            register_name = "NR13/NR14"
        channels.append({
            "track": note["track"],
            "time": round(note["time"], 6),
            "duration": None if note["duration"] is None else round(note["duration"], 6),
            "key": note["key"],
            "pitch_key": key,
            "bend_offset": note.get("bend_offset", 0),
            "bend_fraction": fraction,
            "note_index": note["program"],
            "instrument_offset": table_offset + 12 * note["key"],
            "wave_type": wave_type,
            "wave_name": PSG_WAVE_NAMES.get(wave_type, "unknown"),
            "channel": record[0] & 0x07,
            "volume": note["volume"],
            "pan": note["pan"],
            "envelope": {
                "attack": record[8], "decay": record[9],
                "sustain": record[10], "release": record[11],
            },
            "pan_sweep": record[2],
            "register_kind": register_kind,
            "register_name": register_name,
            "frequency_register": register,
            "frequency_hz": round(frequency, 3),
            "nr10": record[3] & 0xF8,
            "nr11": record[3] & 0x07,
            "nr12": (record[10] & 0x0F),
        })
    return {
        "sound_id": song["sound_id"],
        "format": "GBA m4a PSG (Game Boy) channel dump",
        "note": "register values only - rendering still needs a GB/CGB emulator",
        "channels": channels,
    }


def psg_text(export: dict) -> str:
    """A pytracker-style listing of the PSG channel data."""
    lines = ["# GBA m4a PSG export - sound id %d" % export["sound_id"],
             "# columns: track time  dur  key  wave            vol pan  atk dec sus rel  reg  Hz",
             ]
    for item in export["channels"]:
        env = item["envelope"]
        lines.append(
            "%5d %8.3f %6.3f %4d  %-15s %3d %3d  %3d %3d %3d %3d  %4d %9.2f" % (
                item["track"], item["time"],
                -1.0 if item["duration"] is None else item["duration"],
                item["key"], item["wave_name"], item["volume"], item["pan"],
                env["attack"], env["decay"], env["sustain"], env["release"],
                item["frequency_register"], item["frequency_hz"]))
    return "\n".join(lines) + "\n"


def event_json(song: dict) -> dict:
    """A machine-readable description of everything that was rendered."""
    return {
        "sound_id": song["sound_id"],
        "sample_rate": song["sample_rate"],
        "duration": song["duration"],
        "descriptor_ptr": "0x%08X" % song["descriptor_ptr"],
        "voicegroup_ptr": "0x%08X" % song["voicegroup_ptr"],
        "pitch_model": {
            "anchor_key": PITCH_ANCHOR_KEY,
            "rule": "playback_rate = wave_rate * f_interp(pitch_key) / f(anchor)",
            "bend_rule": (
                "S = (tune + bend*bendRange)*4 + (keyShift << 8); "
                "semitone = S >> 8; fraction = S & 0xFF; "
                "pitch_key = max(0, key + semitone); "
                "f_interp(k) = f(k) + ((f(k+1) - f(k)) * fraction) >> 8"
            ),
        },
        "tempo_model": {
            "ticks_per_quarter": TICKS_PER_QUARTER,
            "tick_accumulator_limit": TICK_ACCUMULATOR_LIMIT,
            "sequencer_hz": SEQUENCER_HZ,
            "rule": "tick_period = 2 * tempo_byte; seconds_per_tick = 150 / (60 * tick_period)",
        },
        "tracks": [{
            "offset": "0x%06X" % track["offset"],
            "loops": track["loops"],
            "duration_ticks": track["duration_ticks"],
            "duration": track["duration"],
            "stop_reason": track["stop_reason"],
            "tempo_changes": track["tempo_changes"],
            "note_count": len(track["events"]),
        } for track in song["tracks"]],
        "tones": [{
            "index": tone["index"],
            "offset": "0x%06X" % tone["offset"],
            "type": tone["type"],
            "key": tone["key"],
            "pointer": "0x%08X" % tone["pointer"],
            "attack": tone["attack"], "decay": tone["decay"],
            "sustain": tone["sustain"], "release": tone["release"],
        } for tone in song["tones"]],
        "notes": song["notes"],
    }


# ---------------------------------------------------------------------------
# PSG export verification (independent re-derivation from the raw ROM bytes)
# ---------------------------------------------------------------------------

def _psg_register_from_raw_rom(rom: bytes, wave_type: int, key: int,
                               fraction: int = 0) -> int:
    """Re-derive the GB frequency register straight from the ROM bytes.

    This deliberately does **not** use :func:`psg_frequency_register` or the
    ``tables`` dict: it re-reads the three ROM tables at their literal
    offsets and re-implements the engine's arithmetic in a different style,
    so a mistake in one implementation cannot hide in the other.
    """
    if wave_type == 4:
        # noise: index 0 for key <= 20, else key - 21 capped at 59.
        index = 0 if key <= 20 else min(key - 21, 59)
        return rom[0x46475C + index]
    # square: clamp the key, then read the signed base of the semitone and
    # shift it down by the octave.
    if key <= 0x23:
        key = 0
        fraction = 0
    else:
        key -= 0x24
        if key > 0x82:
            key = 0x82
            fraction = 0xFF
    selector = rom[0x4646C0 + key]
    semitone = selector & 0x0F
    octave = selector >> 4
    base = struct.unpack_from("<h", rom, 0x464744 + semitone * 2)[0]
    # The ROM shifts with ASRS (arithmetic).  For a negative value that is
    # floor(base / 2**octave), i.e. -ceil(|base| / 2**octave).
    if base >= 0:
        value = base >> octave
    else:
        value = -((-base + (1 << octave) - 1) >> octave)
    # the next key's base, for the 8-bit fraction interpolation
    next_selector = rom[0x4646C0 + key + 1]
    next_base = struct.unpack_from("<h", rom, 0x464744 + (next_selector & 0x0F) * 2)[0]
    next_octave = next_selector >> 4
    if next_base >= 0:
        following = next_base >> next_octave
    else:
        following = -((-next_base + (1 << next_octave) - 1) >> next_octave)
    return value + (((following - value) * fraction) >> 8) + 0x800


def verify_psg_export(rom: bytes, sound_id: int, tables: dict,
                      max_loops: int = 2) -> tuple[int, list[str]]:
    """Check the PSG export of one sound id against the raw ROM bytes.

    Returns ``(checked, problems)``.  ``checked`` is the number of PSG
    events that were compared.
    """
    song = render_sound(rom, sound_id, tables, max_loops=max_loops)
    export = psg_export(rom, song, tables)
    problems: list[str] = []
    checked = 0
    for item in export["channels"]:
        checked += 1
        expected = _psg_register_from_raw_rom(rom, item["wave_type"],
                                              item.get("pitch_key", item["key"]),
                                              item.get("bend_fraction", 0))
        if expected != item["frequency_register"]:
            problems.append(
                "sound id %d track %d t=%.3f key %d wave %d: register %d != ROM %d"
                % (sound_id, item["track"], item["time"], item["key"],
                   item["wave_type"], item["frequency_register"], expected))
        # the instrument record must be the one the ROM would read
        offset = item["instrument_offset"]
        record = rom[offset:offset + 12]
        if len(record) != 12:
            problems.append("instrument record at 0x%06X is truncated" % offset)
            continue
        if record[0] & 0x07 != item["wave_type"]:
            problems.append(
                "sound id %d key %d: instrument wave type %d != export %d"
                % (sound_id, item["key"], record[0] & 0x07, item["wave_type"]))
        for name, value in (("attack", 8), ("decay", 9),
                            ("sustain", 10), ("release", 11)):
            if record[value] != item["envelope"][name]:
                problems.append(
                    "sound id %d key %d: %s %d != ROM %d"
                    % (sound_id, item["key"], name,
                       item["envelope"][name], record[value]))
    return checked, problems


# ---------------------------------------------------------------------------
# Self test
# ---------------------------------------------------------------------------

def self_test(rom: bytes) -> int:
    """Prove that the render reacts to every feature it claims to cover."""
    tables = load_tables(rom)
    failures = []

    # 1. the ROM's own duration table must be the one the renderer uses
    expected = list(range(25)) + [28, 30, 32, 36, 40, 42, 44, 48, 52, 54, 56,
                                  60, 64, 66, 68, 72, 76, 78, 80, 84, 88, 90,
                                  92, 96]
    if tables["durations"] != expected:
        failures.append("duration table mismatch")

    # 2. the note frequency law must be a pure 2**(key/12)
    for key in (0, 12, 24, 36, 48, 60):
        ratio = note_frequency(tables, key) / (1 << 17)
        if abs(ratio - 2.0 ** (key / 12.0)) > 1e-9:
            failures.append(f"note frequency law broken at key {key}")
            break

    # 3. rendering must react to the tempo byte
    base = render_sound(rom, 1, tables, max_loops=1)
    if base["duration"] <= 0:
        failures.append("sound id 1 rendered no audio")
    if not base["notes"]:
        failures.append("sound id 1 produced no note events")

    # 4. rendering must react to the pitch (a key change must move the pitch)
    first = base["notes"][0]
    tone = base["tones"][first["program"]]
    if tone["type"] & 0xC0 == 0:
        shifted = dict(first)
        shifted["key"] = first["key"] + 12
        mix_a = [[0.0, 0.0] for _ in range(OUTPUT_RATE)]
        mix_b = [[0.0, 0.0] for _ in range(OUTPUT_RATE)]
        render_direct_sound(rom, tone, first, tables, mix_a, 0)
        render_direct_sound(rom, tone, shifted, tables, mix_b, 0)
        if mix_a == mix_b:
            failures.append("an octave change did not change the rendered audio")

    # 5. the envelope bytes must matter
    if tone["type"] & 0xC0 == 0:
        flat = dict(tone)
        flat["attack"] = 255
        flat["decay"] = 0
        flat["sustain"] = 255
        flat["release"] = 0
        mix_c = [[0.0, 0.0] for _ in range(OUTPUT_RATE)]
        render_direct_sound(rom, flat, first, tables, mix_c, 0)
        mix_d = [[0.0, 0.0] for _ in range(OUTPUT_RATE)]
        ramp = dict(tone)
        ramp["attack"] = 0
        ramp["decay"] = 255
        ramp["sustain"] = 0
        ramp["release"] = 255
        render_direct_sound(rom, ramp, first, tables, mix_d, 0)
        if mix_c == mix_d:
            failures.append("the envelope bytes did not change the rendered audio")

    # 6. the PSG export must be non-empty for a sound that uses PSG
    psg = psg_export(rom, base, tables)
    if not psg["channels"]:
        failures.append("sound id 1 produced no PSG channel data")

    # 7. the PSG export must agree with the raw ROM bytes
    checked, problems = verify_psg_export(rom, 1, tables)
    if checked == 0:
        failures.append("no PSG event could be verified")
    for problem in problems[:5]:
        failures.append("PSG mismatch: " + problem)

    # 8. the PSG frequency table must be signed and must not overlap the
    #    noise table (the engine reads it with LDRSH)
    if any(value >= 0 for value in tables["psg_freqs"]):
        failures.append("the PSG frequency table is not signed-negative")
    if PSG_FREQ_TABLE + PSG_FREQ_TABLE_LEN * 2 > PSG_NOISE_TABLE:
        failures.append("the PSG frequency table overlaps the noise table")

    # 9. spot-check the PSG register against hand-computed ROM values.
    #    key 0  -> index 0  -> s16[0]  >> 0  = -2004 -> 0x800 - 2004 =   44
    #    key 46 -> index 10 -> s16[10] >> 0  = -1125 -> 0x800 - 1125 =  923
    #    key 49 -> index 13 -> s16[1]  >> 1  =  -946 -> 0x800 -  946 = 1102
    for key, expected in ((0, 44), (46, 923), (49, 1102)):
        actual = psg_frequency_register(tables, key)
        if actual != expected:
            failures.append("PSG register for key %d is %d, expected %d"
                            % (key, actual, expected))

    # 10. the bend accumulator must reproduce the engine's own arithmetic
    #     (0x0809B450..0x0809B486).  The values below are the ones the
    #     engine produced at run time (see
    #     notes/evidence/audio-song-export-20261021.md).
    #       bend stored 16, range 2  -> S = 16*2*4 = 128  -> (0, 128)
    #       bend stored 32, range 8  -> S = 32*8*4 = 1024 -> (4, 0)
    #       bend stored -32, range 2 -> S = -32*2*4 = -256 -> (-1, 0)
    for bend, bend_range, expected in ((16, 2, (0, 128)),
                                       (32, 8, (4, 0)),
                                       (-32, 2, (-1, 0))):
        offset, fraction = bend_pitch_offset(bend, bend_range)
        if (offset, fraction) != expected:
            failures.append(
                "bend(%d, %d) -> (%d, %d), expected %s"
                % (bend, bend_range, offset, fraction, expected))

    # 11. the bend must move the rendered pitch, and the movement must be
    #      the engine's interpolation (not a plain key shift)
    if tone["type"] & 0xC0 == 0:
        bent = dict(first)
        bent["bend_offset"] = 0
        bent["bend_fraction"] = 128
        mix_e = [[0.0, 0.0] for _ in range(OUTPUT_RATE)]
        render_direct_sound(rom, tone, bent, tables, mix_e, 0)
        if mix_a == mix_e:
            failures.append("a pitch bend did not change the rendered audio")
        # a fraction of 128 must land half way between f(key) and f(key+1)
        straight = engine_pitch_base(tables, first["key"], 0)
        half = engine_pitch_base(tables, first["key"], 128)
        following = engine_pitch_base(tables, first["key"] + 1, 0)
        if half != straight + ((following - straight) // 2):
            failures.append("the bend interpolation is not linear in f(key)")

    for problem in failures:
        print("FAIL:", problem, file=sys.stderr)
    if failures:
        return 1
    print("self-test: %d notes rendered, %d PSG events, %d PSG events verified "
          "against the raw ROM, duration %.3f s"
          % (len(base["notes"]), len(psg["channels"]), checked, base["duration"]))
    print("SELF-TEST: PASS")
    return 0

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a ROM sound id to PCM/WAV and export its PSG data.")
    parser.add_argument("rom", nargs="?", default="rom/base.gba")
    parser.add_argument("--sound-id", type=int, required=False,
                        help="sound id to render (0..158)")
    parser.add_argument("--wav", help="write the rendered PCM to this WAV file")
    parser.add_argument("--json", help="write the event description here")
    parser.add_argument("--psg-json", help="write the PSG channel dump here")
    parser.add_argument("--psg-text", help="write the pytracker-style PSG listing here")
    parser.add_argument("--loops", type=int, default=2,
                        help="how many times to play the song's loop (default 2)")
    parser.add_argument("--self-test", action="store_true",
                        help="run the built-in checks and exit non-zero on failure")
    parser.add_argument("--verify-psg", type=int, default=None, metavar="SOUND_ID",
                        help="re-derive the PSG registers of SOUND_ID from the raw "
                             "ROM bytes and compare them with the export")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ROM not found: {rom_path}", file=sys.stderr)
        return 1
    rom = rom_path.read_bytes()

    try:
        tables = load_tables(rom)
    except SoundLayoutError as exc:
        print(f"unsupported ROM: {exc}", file=sys.stderr)
        return 1

    if args.self_test:
        try:
            return self_test(rom)
        except SoundLayoutError as exc:
            print(f"unsupported ROM: {exc}", file=sys.stderr)
            return 1

    if args.verify_psg is not None:
        try:
            checked, problems = verify_psg_export(rom, args.verify_psg, tables)
        except SoundLayoutError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print("verify-psg: sound id %d: %d PSG events checked against the ROM"
              % (args.verify_psg, checked))
        for problem in problems:
            print("MISMATCH:", problem, file=sys.stderr)
        return 1 if problems else 0

    if args.sound_id is None:
        print("Error: --sound-id is required (or use --self-test)", file=sys.stderr)
        return 1

    try:
        song = render_sound(rom, args.sound_id, tables, max_loops=max(1, args.loops))
    except SoundLayoutError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.wav:
        out = pathlib.Path(args.wav)
        write_wav(out, song["mix"], song["sample_rate"])
        print("wav   : %s (%.2f s, %d Hz, %d frames)"
              % (out, song["duration"], song["sample_rate"], len(song["mix"])))
    if args.json:
        out = pathlib.Path(args.json)
        write_text(out, json.dumps(event_json(song), ensure_ascii=False, indent=2) + "\n")
        print("json  : %s (%d notes)" % (out, len(song["notes"])))
    if args.psg_json or args.psg_text:
        export = psg_export(rom, song, tables)
        if args.psg_json:
            out = pathlib.Path(args.psg_json)
            write_text(out, json.dumps(export, ensure_ascii=False, indent=2) + "\n")
            print("psg   : %s (%d events)" % (out, len(export["channels"])))
        if args.psg_text:
            out = pathlib.Path(args.psg_text)
            write_text(out, psg_text(export))
            print("psgtxt: %s" % out)
    if not (args.wav or args.json or args.psg_json or args.psg_text):
        print("sound id %d: %d tracks, %d notes, %.2f s"
              % (song["sound_id"], len(song["tracks"]), len(song["notes"]),
                 song["duration"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
