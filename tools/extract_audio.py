#!/usr/bin/env python3
"""Extract the ROM's real audio resources through the verified sound-ID table.

The table used here is **not** the old ``0x08599634`` guess.  That address is
the message/command pointer table consulted by the script dispatcher at
``0x08079668``; its entries are ninjutsu names, not audio.

The real audio index table is the sound-ID table at file ``0x465B70``
(ARM ``0x08465B70``):

* ``0x0809AAC0`` (reached through the public wrapper ``0x08061E6C``) computes
  ``sound_id * 8`` and indexes this table -- verified by the literal pool at
  ``0x0809AAE8`` (``0x08465B70``).
* every row is 8 bytes: ``u32 descriptor_ptr``, ``u16 player_index``,
  ``u16 player_config``;
* the descriptor is an m4a ``SongHeader``: ``u8 track_count``, ``u8 block_count``,
  ``u8 priority``, ``u8 reverb``, ``u32 voicegroup_ptr``, ``u32 track_ptrs[]``;
* a track pointer leads to m4a bytecode, a voicegroup pointer to 12-byte tone
  records, and a type-0 tone to a 16-byte DirectSound wave header followed by
  signed 8-bit PCM.

Command IDs and parameter widths come from the m4a/MP2K definition published
in pret/pokeemerald ``sound/MPlayDef.s``; they are validated against this ROM
here (every track must decode without an unknown opcode).

Usage:
    python tools/extract_audio.py rom/base.gba                     # manifest only
    python tools/extract_audio.py rom/base.gba --extract           # + wav/midi/blobs
    python tools/extract_audio.py rom/base.gba --extract --output-dir build/audio
    python tools/extract_audio.py rom/base.gba --sound-id 118 --extract
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.lib.io import write_text  # noqa: E402

ROM_BASE = 0x08000000

# --- verified tables -------------------------------------------------------
SOUND_ID_TABLE = 0x465B70          # ARM 0x08465B70, 8 bytes per sound id
SOUND_ID_STRIDE = 8
SOUND_ID_COUNT = 159               # ids 0..158; id 159 is the empty descriptor
EMPTY_DESCRIPTOR = 0x08466068      # ARM pointer of the "plays nothing" descriptor
DISPATCHER = 0x0809AAC0           # indexes SOUND_ID_TABLE by sound_id * 8
PUBLIC_WRAPPER = 0x08061E6C
ENGINE_INIT = 0x0809AE3C          # GBA sound / FIFO / DMA register setup

TONE_SIZE = 12
WAVE_HEADER_SIZE = 16
FREQ_SCALE = 1024
VALID_TONE_TYPES = {0, 1, 2, 3, 4, 8, 9, 10, 11, 12, 0x40, 0x80}

PPQN = 24

# --- m4a command set (pret/pokeemerald sound/MPlayDef.s) --------------------
WAIT_TICKS = tuple(range(25)) + (28, 30, 32, 36, 40, 42, 44, 48, 52, 54, 56, 60, 64,
                                 66, 68, 72, 76, 78, 80, 84, 88, 90, 92, 96)
NOTE_TICKS = tuple(range(1, 25)) + (28, 30, 32, 36, 40, 42, 44, 48, 52, 54, 56, 60, 64,
                                   66, 68, 72, 76, 78, 80, 84, 88, 90, 92, 96)
WAIT_NAMES = {0x80 + index: f"W{ticks:02d}" for index, ticks in enumerate(WAIT_TICKS)}
NOTE_NAMES = {0xD0 + index: f"N{ticks:02d}" for index, ticks in enumerate(NOTE_TICKS)}
ONE_ARG = {
    0xBA: "PRIO", 0xBB: "TEMPO", 0xBC: "KEYSH", 0xBD: "VOICE",
    0xBE: "VOL", 0xBF: "PAN", 0xC0: "BEND", 0xC1: "BENDR",
    0xC2: "LFOS", 0xC3: "LFODL", 0xC4: "MOD", 0xC5: "MODT",
    0xC8: "TUNE",
}


class DecodeError(ValueError):
    """Raised when a track cannot be decoded structurally."""


# ---------------------------------------------------------------------------
# Sound-ID table and song descriptors
# ---------------------------------------------------------------------------

def rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer 0x{pointer:08X} is outside ROM")
    return offset


def read_sound_id_table(rom: bytes) -> list[dict]:
    """Read every row of the sound-ID table (ids 0..158)."""
    rows = []
    for sound_id in range(SOUND_ID_COUNT):
        raw = SOUND_ID_TABLE + sound_id * SOUND_ID_STRIDE
        descriptor_ptr, player_index, player_config = struct.unpack_from("<IHH", rom, raw)
        rows.append({
            "sound_id": sound_id,
            "row_offset": raw,
            "descriptor_ptr": descriptor_ptr,
            "player_index": player_index,
            "player_config": player_config,
            "empty": descriptor_ptr == EMPTY_DESCRIPTOR,
        })
    return rows


def parse_descriptor(rom: bytes, descriptor_ptr: int) -> dict:
    """Parse an m4a SongHeader."""
    offset = rom_offset(descriptor_ptr, len(rom))
    track_count, block_count, priority, reverb = struct.unpack_from("<BBBB", rom, offset)
    if not 1 <= track_count <= 16:
        raise ValueError(f"implausible track count {track_count} at 0x{offset:06X}")
    voicegroup_ptr = struct.unpack_from("<I", rom, offset + 4)[0]
    rom_offset(voicegroup_ptr, len(rom))
    track_ptrs = list(struct.unpack_from(f"<{track_count}I", rom, offset + 8))
    for pointer in track_ptrs:
        rom_offset(pointer, len(rom))
    return {
        "descriptor_offset": offset,
        "track_count": track_count,
        "block_count": block_count,
        "priority": priority,
        "reverb": reverb,
        "voicegroup_ptr": voicegroup_ptr,
        "track_ptrs": track_ptrs,
    }


def collect_tracks(rom: bytes, entries: list[dict]) -> list[dict]:
    """Slice every referenced track out of the ROM.

    A track's end is the next referenced track or descriptor, so the extracted
    blob contains exactly the track's own bytecode.
    """
    track_offsets = sorted({
        rom_offset(pointer, len(rom))
        for entry in entries
        for pointer in entry["descriptor"]["track_ptrs"]
    })
    boundaries = sorted(set(track_offsets) | {
        entry["descriptor"]["descriptor_offset"] for entry in entries
    })
    tracks = []
    for offset in track_offsets:
        end = next((item for item in boundaries if item > offset), None)
        if end is None:
            raise ValueError(f"no boundary for track at 0x{offset:06X}")
        tracks.append({
            "offset": offset,
            "size": end - offset,
            "raw": rom[offset:end],
        })
    return tracks


# ---------------------------------------------------------------------------
# Voicegroups, tones and DirectSound waves
# ---------------------------------------------------------------------------

def parse_wave(rom: bytes, offset: int) -> dict | None:
    """Parse a 16-byte m4a DirectSound wave header."""
    if offset < 0 or offset + WAVE_HEADER_SIZE > len(rom):
        return None
    type_flags, status, frequency_raw, loop_start, sample_count = struct.unpack_from(
        "<HHIII", rom, offset)
    end = offset + WAVE_HEADER_SIZE + sample_count
    if frequency_raw == 0 or sample_count == 0 or loop_start > sample_count or end > len(rom):
        return None
    sample_rate = round(frequency_raw / FREQ_SCALE)
    if not 1000 <= sample_rate <= 96000:
        return None
    return {
        "offset": offset,
        "type_flags": type_flags,
        "status": status,
        "frequency_raw": frequency_raw,
        "sample_rate": sample_rate,
        "loop_start": loop_start,
        "sample_count": sample_count,
        "data_offset": offset + WAVE_HEADER_SIZE,
        "data_end": end,
        "looping": status & 0x40 != 0,
    }


def collect_tones(rom: bytes, entries: list[dict]) -> tuple[list[dict], dict[int, dict]]:
    """Walk every voicegroup and collect its tone records and reachable waves."""
    starts = sorted({rom_offset(entry["descriptor"]["voicegroup_ptr"], len(rom))
                     for entry in entries})
    tones: list[dict] = []
    waves: dict[int, dict] = {}
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else SOUND_ID_TABLE
        for offset in range(start, end - TONE_SIZE + 1, TONE_SIZE):
            (tone_type, key, length, pan_sweep, pointer,
             attack, decay, sustain, release) = struct.unpack_from("<BBBBIBBBB", rom, offset)
            if tone_type not in VALID_TONE_TYPES:
                break
            tone = {
                "offset": offset,
                "voicegroup_offset": start,
                "type": tone_type,
                "key": key,
                "length": length,
                "pan_sweep": pan_sweep,
                "pointer": pointer,
                "attack": attack,
                "decay": decay,
                "sustain": sustain,
                "release": release,
            }
            if tone_type == 0 and ROM_BASE <= pointer < ROM_BASE + len(rom):
                wave = parse_wave(rom, pointer - ROM_BASE)
                if wave is not None:
                    tone["wave_offset"] = wave["offset"]
                    waves.setdefault(wave["offset"], wave)
            tones.append(tone)
    return tones, waves


# ---------------------------------------------------------------------------
# m4a track bytecode
# ---------------------------------------------------------------------------

def decode_track(raw: bytes, base_offset: int) -> list[dict]:
    """Structurally decode one m4a track's bytecode.

    The **running opcode** rule (proved from this ROM's own engine at
    ``0x0809A4F8 cmp r1, #0xbd`` / ``0x0809A4FC strb r1, [r5, #7]``):
    a byte below ``0x80`` is a *continuation* byte -- an operand of the
    running opcode -- and the running opcode is refreshed for **every**
    opcode ``>= 0xBD``, not only for notes.  Getting that wrong turns a
    ``MOD`` parameter into a phantom key-0 note.
    """
    commands: list[dict] = []
    cursor = 0
    running_opcode: int | None = None
    while cursor < len(raw):
        start = cursor
        opcode = raw[cursor]
        explicit = opcode >= 0x80
        if explicit:
            cursor += 1
            if opcode >= 0xBD:
                # the engine refreshes the running opcode for every opcode
                # from 0xBD upwards (not notes only)
                running_opcode = opcode
        elif running_opcode is not None:
            opcode = running_opcode
        else:
            raise DecodeError(f"parameter 0x{raw[cursor]:02X} without running opcode at "
                              f"0x{base_offset + cursor:06X}")

        item: dict = {"offset": base_offset + start, "opcode": opcode}
        if opcode in WAIT_NAMES:
            item["name"] = WAIT_NAMES[opcode]
        elif opcode == 0xB1:
            item["name"] = "FINE"
        elif opcode in (0xB2, 0xB3):
            item["name"] = "GOTO" if opcode == 0xB2 else "PATT"
            if cursor + 4 > len(raw):
                raise DecodeError(f"truncated {item['name']} at 0x{base_offset + start:06X}")
            pointer = struct.unpack_from("<I", raw, cursor)[0]
            cursor += 4
            item["target_offset"] = pointer - ROM_BASE
        elif opcode == 0xB4:
            item["name"] = "PEND"
        elif opcode == 0xB5:
            item["name"] = "REPT"
            if cursor + 5 > len(raw):
                raise DecodeError(f"truncated REPT at 0x{base_offset + start:06X}")
            item["count"] = raw[cursor]
            item["target_offset"] = struct.unpack_from("<I", raw, cursor + 1)[0] - ROM_BASE
            cursor += 5
        elif opcode == 0xB9:
            item["name"] = "MEMACC"
            if cursor + 3 > len(raw):
                raise DecodeError(f"truncated MEMACC at 0x{base_offset + start:06X}")
            item["args"] = list(raw[cursor:cursor + 3])
            cursor += 3
        elif opcode in ONE_ARG:
            item["name"] = ONE_ARG[opcode]
            if cursor >= len(raw):
                raise DecodeError(f"truncated {item['name']} at 0x{base_offset + start:06X}")
            item["value"] = raw[cursor]
            cursor += 1
        elif opcode == 0xCD:
            item["name"] = "XCMD"
            if cursor + 2 > len(raw):
                raise DecodeError(f"truncated XCMD at 0x{base_offset + start:06X}")
            item["args"] = list(raw[cursor:cursor + 2])
            cursor += 2
        elif opcode == 0xCE:
            item["name"] = "EOT"
            if cursor < len(raw) and raw[cursor] < 0x80:
                item["key"] = raw[cursor]
                cursor += 1
        elif opcode == 0xCF or opcode in NOTE_NAMES:
            item["name"] = "TIE" if opcode == 0xCF else NOTE_NAMES[opcode]
            args = []
            while cursor < len(raw) and raw[cursor] < 0x80 and len(args) < 3:
                args.append(raw[cursor])
                cursor += 1
            item["args"] = args
        else:
            raise DecodeError(f"unknown opcode 0x{opcode:02X} at 0x{base_offset + start:06X}")
        item["size"] = cursor - start
        commands.append(item)
    return commands


def _ticks(name: str) -> int:
    return int(name[1:])


def _signed8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def execute_track(track: dict, command_map: dict[int, dict],
                  max_steps: int = 200_000) -> dict:
    """Run one track for a single loop and collect its musical events."""
    pc = track["offset"]
    tick = 0
    stack: list[int] = []
    visited: Counter[int] = Counter()
    events: list[dict] = []
    key = 60
    velocity = 100
    voice = 0
    volume = 127
    volume_multiplier = 64
    pan = 64
    key_shift = 0
    bend = 0
    bend_range = 2
    tune = 0
    lfo_speed = 22
    lfo_delay = 0
    lfo_countdown = 0
    lfo_phase = 0
    mod_depth = 0
    mod_type = 0
    mod_value = 0
    repeat_state: dict[int, int] = {}
    open_ties: dict[int, dict] = {}
    stop_reason = ""

    def pitch_total() -> int:
        modulation = (mod_value << 4) if mod_type == 0 else 0
        return ((tune + bend * bend_range) << 2) + (key_shift << 8) + modulation

    for step in range(max_steps):
        command = command_map.get(pc)
        if command is None:
            raise DecodeError(f"execution target 0x{pc:06X} is not a command boundary")
        visited[pc] += 1
        name = command["name"]
        next_pc = pc + command["size"]
        if name.startswith("W"):
            tick += _ticks(name)
        elif name == "FINE":
            for tied_note in open_ties.values():
                tied_note["duration"] = tick - tied_note["tick"]
                tied_note["release_reason"] = "fine"
            open_ties.clear()
            stop_reason = "fine"
            break
        elif name == "PATT":
            if len(stack) >= 16:
                raise DecodeError(f"pattern stack overflow at 0x{pc:06X}")
            stack.append(next_pc)
            pc = command["target_offset"]
            continue
        elif name == "PEND":
            if stack:
                pc = stack.pop()
                continue
            # This ROM points some tracks at shared fragments that start with
            # PEND; the engine falls through when no return address is active.
        elif name == "GOTO":
            target = command["target_offset"]
            if visited[target]:
                stop_reason = "one_loop"
                break
            pc = target
            continue
        elif name == "REPT":
            remaining = repeat_state.setdefault(pc, command["count"])
            if remaining > 0:
                repeat_state[pc] = remaining - 1
                pc = command["target_offset"]
                continue
            repeat_state.pop(pc, None)
        elif name == "TEMPO":
            events.append({"tick": tick, "type": "tempo", "bpm_x2": command["value"]})
        elif name == "VOICE":
            voice = command["value"]
            events.append({"tick": tick, "type": "program", "value": voice})
        elif name == "VOL":
            volume = command["value"]
            events.append({"tick": tick, "type": "volume", "value": volume})
        elif name == "PAN":
            pan = command["value"]
            events.append({"tick": tick, "type": "pan", "value": value_clamp(pan)})
        elif name == "BEND":
            bend = command["value"] - 0x40
            events.append({"tick": tick, "type": "bend", "value": command["value"]})
        elif name == "KEYSH":
            key_shift = _signed8(command["value"])
        elif name == "BENDR":
            bend_range = command["value"]
        elif name == "TUNE":
            tune = command["value"] - 0x40
        elif name == "LFOS":
            lfo_speed = command["value"]
            if lfo_speed == 0:
                mod_value = 0
                lfo_phase = 0
        elif name == "LFODL":
            lfo_delay = command["value"]
        elif name == "MOD":
            mod_depth = command["value"]
            if mod_depth == 0:
                mod_value = 0
                lfo_phase = 0
        elif name == "MODT":
            mod_type = command["value"]
        elif name == "EOT":
            tie_key = command.get("key", key)
            tied_note = open_ties.pop(tie_key, None)
            if tied_note is not None:
                tied_note["duration"] = tick - tied_note["tick"]
                tied_note["release_reason"] = "eot"
            events.append({"tick": tick, "type": "end_tie", "key": tie_key,
                           "matched": tied_note is not None})
        elif name == "TIE" or name.startswith("N"):
            args = command.get("args", [])
            if len(args) >= 1:
                key = args[0]
            if len(args) >= 2:
                velocity = args[1]
            gate = args[2] if len(args) >= 3 else 0
            lfo_countdown = lfo_delay
            duration = None if name == "TIE" else _ticks(name) + gate
            total = pitch_total()
            note_event = {
                "tick": tick, "type": "note", "key": key, "velocity": velocity,
                "duration": duration, "voice": voice, "volume": volume, "pan": pan,
                "tied": name == "TIE",
                "release_reason": None if name == "TIE" else "gate",
                "pitch_key": max(0, key + (total >> 8)),
                "pitch_fine": total & 0xFF,
            }
            events.append(note_event)
            if name == "TIE":
                open_ties[key] = note_event
        pc = next_pc
    else:
        raise DecodeError(f"track 0x{track['offset']:06X} exceeded {max_steps} steps")

    return {
        "offset": track["offset"],
        "duration_ticks": tick,
        "steps": step + 1,
        "stop_reason": stop_reason,
        "events": events,
        "open_tie_keys": sorted(open_ties),
    }


def value_clamp(value: int) -> int:
    return max(0, min(127, value))


# ---------------------------------------------------------------------------
# MIDI output
# ---------------------------------------------------------------------------

def _vlq(value: int) -> bytes:
    data = [value & 0x7F]
    value >>= 7
    while value:
        data.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(data))


def _midi_track(events: list[dict], channel: int) -> bytes:
    encoded = []
    for event in events:
        tick, kind = event["tick"], event["type"]
        if kind == "tempo" and event["bpm_x2"]:
            micros = round(120_000_000 / event["bpm_x2"])
            encoded.append((tick, 0, b"\xFF\x51\x03" + micros.to_bytes(3, "big")))
        elif kind == "program":
            encoded.append((tick, 1, bytes((0xC0 | channel, event["value"] & 0x7F))))
        elif kind == "volume":
            encoded.append((tick, 1, bytes((0xB0 | channel, 7, event["value"] & 0x7F))))
        elif kind == "pan":
            encoded.append((tick, 1, bytes((0xB0 | channel, 10, event["value"] & 0x7F))))
        elif kind == "bend":
            bend = max(0, min(16383, 8192 + (event["value"] - 64) * 128))
            encoded.append((tick, 1, bytes((0xE0 | channel, bend & 0x7F, bend >> 7))))
        elif kind == "note" and event["duration"] is not None:
            key, velocity = event["key"] & 0x7F, event["velocity"] & 0x7F
            encoded.append((tick, 2, bytes((0x90 | channel, key, velocity))))
            encoded.append((tick + event["duration"], 0, bytes((0x80 | channel, key, 0))))
    encoded.sort(key=lambda item: (item[0], item[1]))
    body = bytearray()
    previous = 0
    for tick, _order, message in encoded:
        body += _vlq(tick - previous) + message
        previous = tick
    body += b"\x00\xFF\x2F\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def midi_file(tracks: list[dict]) -> bytes:
    chunks = [_midi_track(track["events"], index % 16) for index, track in enumerate(tracks)]
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQN) + b"".join(chunks)


# ---------------------------------------------------------------------------
# WAV output
# ---------------------------------------------------------------------------

def write_wav(path: Path, signed_pcm: bytes, sample_rate: int) -> None:
    """Write a mono 8-bit PCM WAV file (ROM samples are signed, RIFF is not)."""
    unsigned_pcm = bytes(value ^ 0x80 for value in signed_pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(unsigned_pcm), b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate, 1, 8,
        b"data", len(unsigned_pcm),
    )
    path.write_bytes(header + unsigned_pcm)


# ---------------------------------------------------------------------------
# Extraction pipeline
# ---------------------------------------------------------------------------

def build_catalog(rom: bytes) -> dict:
    """Walk sound id -> descriptor -> tracks / voicegroups -> tones -> waves."""
    rows = read_sound_id_table(rom)
    entries = []
    for row in rows:
        if row["empty"]:
            continue
        descriptor = parse_descriptor(rom, row["descriptor_ptr"])
        entries.append({
            "sound_id": row["sound_id"],
            "row_offset": row["row_offset"],
            "descriptor_ptr": row["descriptor_ptr"],
            "player_index": row["player_index"],
            "player_config": row["player_config"],
            "descriptor": descriptor,
        })

    tracks = collect_tracks(rom, entries)
    tones, waves = collect_tones(rom, entries)

    decoded = []
    for track in tracks:
        commands = decode_track(track["raw"], track["offset"])
        decoded.append({
            "offset": track["offset"],
            "size": track["size"],
            "commands": commands,
        })

    command_map = {command["offset"]: command
                   for track in decoded for command in track["commands"]}
    tracks_by_offset = {track["offset"]: track for track in decoded}

    for entry in entries:
        rendered = []
        for pointer in entry["descriptor"]["track_ptrs"]:
            offset = pointer - ROM_BASE
            rendered.append(execute_track(tracks_by_offset[offset], command_map))
        entry["tracks"] = [{
            "offset": item["offset"],
            "duration_ticks": item["duration_ticks"],
            "stop_reason": item["stop_reason"],
            "event_count": len(item["events"]),
            "note_count": sum(1 for event in item["events"] if event["type"] == "note"),
        } for item in rendered]
        entry["note_count"] = sum(item["note_count"] for item in entry["tracks"])
        entry["duration_ticks"] = max((item["duration_ticks"] for item in rendered), default=0)
        entry["rendered"] = rendered

    opcode_counts = Counter(command["name"] for track in decoded for command in track["commands"])
    known = [(track["offset"], track["offset"] + track["size"]) for track in decoded]
    bad_targets = sorted({
        command["target_offset"]
        for track in decoded for command in track["commands"]
        if "target_offset" in command
        and not any(start <= command["target_offset"] < end for start, end in known)
    })

    return {
        "rows": rows,
        "entries": entries,
        "tracks": tracks,
        "decoded": decoded,
        "tones": tones,
        "waves": waves,
        "opcode_counts": dict(sorted(opcode_counts.items())),
        "invalid_control_targets": bad_targets,
    }


def export_catalog(rom: bytes, catalog: dict, output_dir: Path) -> dict:
    """Write WAV samples, track blobs, MIDI files and the JSON manifest."""
    waves_dir = output_dir / "waves"
    tracks_dir = output_dir / "tracks"
    midi_dir = output_dir / "midi"
    for path in (waves_dir, tracks_dir, midi_dir):
        path.mkdir(parents=True, exist_ok=True)

    for track in catalog["tracks"]:
        (tracks_dir / f"track_{track['offset']:06X}.bin").write_bytes(track["raw"])

    wave_files = {}
    for offset, wave in sorted(catalog["waves"].items()):
        pcm = rom[wave["data_offset"]:wave["data_end"]]
        name = f"wave_{offset:06X}_{wave['sample_rate']}hz.wav"
        write_wav(waves_dir / name, pcm, wave["sample_rate"])
        wave_files[offset] = name

    songs = []
    for entry in catalog["entries"]:
        sound_id = entry["sound_id"]
        name = f"sound_{sound_id:03d}.mid"
        (midi_dir / name).write_bytes(midi_file(entry["rendered"]))
        songs.append({
            "sound_id": sound_id,
            "row_offset": f"0x{entry['row_offset']:06X}",
            "descriptor_offset": f"0x{entry['descriptor']['descriptor_offset']:06X}",
            "descriptor_ptr": f"0x{entry['descriptor_ptr']:08X}",
            "player_index": entry["player_index"],
            "track_count": entry["descriptor"]["track_count"],
            "block_count": entry["descriptor"]["block_count"],
            "priority": entry["descriptor"]["priority"],
            "reverb": entry["descriptor"]["reverb"],
            "voicegroup_ptr": f"0x{entry['descriptor']['voicegroup_ptr']:08X}",
            "note_count": entry["note_count"],
            "duration_ticks": entry["duration_ticks"],
            "stop_reasons": dict(Counter(track["stop_reason"] for track in entry["rendered"])),
            "midi": name,
        })

    manifest = {
        "format": "GBA m4a sound-ID catalog",
        "rom": {
            "sound_id_table": f"0x{SOUND_ID_TABLE:06X}",
            "sound_id_table_arm": f"0x{ROM_BASE + SOUND_ID_TABLE:08X}",
            "sound_id_count": SOUND_ID_COUNT,
            "entry_size": SOUND_ID_STRIDE,
            "dispatcher": f"0x{DISPATCHER:08X}",
            "public_wrapper": f"0x{PUBLIC_WRAPPER:08X}",
            "engine_init": f"0x{ENGINE_INIT:08X}",
            "empty_descriptor": f"0x{EMPTY_DESCRIPTOR:08X}",
        },
        "summary": {
            "sound_id_rows": len(catalog["rows"]),
            "active_sound_ids": len(catalog["entries"]),
            "track_count": len(catalog["tracks"]),
            "tone_count": len(catalog["tones"]),
            "wave_count": len(catalog["waves"]),
            "opcode_counts": catalog["opcode_counts"],
            "invalid_control_targets": [f"0x{target:06X}" for target in catalog["invalid_control_targets"]],
        },
        "songs": songs,
        "waves": [
            {
                "offset": f"0x{offset:06X}",
                "sample_rate": wave["sample_rate"],
                "sample_count": wave["sample_count"],
                "loop_start": wave["loop_start"],
                "looping": wave["looping"],
                "wav": wave_files[offset],
            }
            for offset, wave in sorted(catalog["waves"].items())
        ],
        "tones": [
            {
                "offset": f"0x{tone['offset']:06X}",
                "type": tone["type"],
                "key": tone["key"],
                "pointer": f"0x{tone['pointer']:08X}",
                "wave_offset": (f"0x{tone['wave_offset']:06X}" if "wave_offset" in tone else None),
            }
            for tone in catalog["tones"]
        ],
        "tracks": [
            {
                "offset": f"0x{track['offset']:06X}",
                "size": track["size"],
                "command_count": len(track["commands"]),
            }
            for track in catalog["decoded"]
        ],
    }
    write_text(output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def print_summary(catalog: dict) -> None:
    rows = catalog["rows"]
    active = catalog["entries"]
    print(f"sound-ID table : file 0x{SOUND_ID_TABLE:06X} (ARM 0x{ROM_BASE + SOUND_ID_TABLE:08X}), "
          f"{len(rows)} rows x {SOUND_ID_STRIDE} bytes")
    print(f"dispatcher     : 0x{DISPATCHER:08X} indexes it with sound_id * {SOUND_ID_STRIDE}")
    print(f"active ids     : {len(active)}  "
          f"(empty rows point at 0x{EMPTY_DESCRIPTOR:08X})")
    print(f"tracks/tones/waves: {len(catalog['tracks'])} / {len(catalog['tones'])} / "
          f"{len(catalog['waves'])}")
    print(f"invalid control targets: {len(catalog['invalid_control_targets'])}")
    print()

    header = (f"{'id':>4}  {'slot':>4}  {'descriptor':>12}  {'trk':>3}  {'prio':>4}  "
              f"{'rev':>4}  {'notes':>6}  {'ticks':>6}  {'stop':>10}")
    print(header)
    print("-" * len(header))
    for entry in active:
        descriptor = entry["descriptor"]
        stops = ",".join(sorted({track["stop_reason"] for track in entry["rendered"]}))
        print(f"{entry['sound_id']:4d}  {entry['player_index']:4d}  "
              f"0x{descriptor['descriptor_offset']:06X}    {descriptor['track_count']:3d}  "
              f"{descriptor['priority']:4d}  {descriptor['reverb']:4d}  "
              f"{entry['note_count']:6d}  {entry['duration_ticks']:6d}  {stops or '-':>10}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract the ROM's m4a audio through the verified sound-ID table.")
    parser.add_argument("rom", type=Path, help="GBA ROM file")
    parser.add_argument("--extract", action="store_true",
                        help="Export WAV samples, track blobs, MIDI files and a manifest")
    parser.add_argument("--output-dir", type=Path, default=Path("build/audio"))
    parser.add_argument("--sound-id", type=int, default=None,
                        help="Only report this sound id")
    parser.add_argument("--manifest-only", action="store_true",
                        help="Skip the console table (quiet mode)")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}", file=sys.stderr)
        return 1

    rom = args.rom.read_bytes()
    print(f"ROM: {args.rom} ({len(rom):,} bytes)")
    catalog = build_catalog(rom)

    if args.sound_id is not None:
        wanted = [entry for entry in catalog["entries"] if entry["sound_id"] == args.sound_id]
        if not wanted:
            print(f"Error: sound id {args.sound_id} has no descriptor", file=sys.stderr)
            return 1
        catalog["entries"] = wanted

    if not args.manifest_only:
        print_summary(catalog)

    if args.extract:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        manifest = export_catalog(rom, catalog, args.output_dir)
        print(f"\nExported to {args.output_dir}/:")
        print(f"  manifest.json      {len(manifest['songs'])} sound ids")
        print(f"  tracks/            {len(manifest['tracks'])} m4a bytecode blobs")
        print(f"  waves/             {len(manifest['waves'])} DirectSound WAV samples")
        print(f"  midi/              {len(manifest['songs'])} one-loop MIDI files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
