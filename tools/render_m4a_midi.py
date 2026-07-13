#!/usr/bin/env python3
"""Execute decoded MP2K tracks for one loop and export standard MIDI files."""
from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

PPQN = 24


def _ticks(name: str) -> int:
    return int(name[1:])


def _signed8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _track_mix_coefficients(
    volume: int,
    volume_multiplier: int,
    pan: int,
    *,
    mod_type: int,
    mod_value: int,
    pan_extra: int = 0,
) -> tuple[int, int]:
    """Reproduce the track right/left gain cache at 0x0809B3E0."""
    base = (volume * volume_multiplier) >> 5
    if mod_type == 1:
        base = (base * (mod_value + 128)) >> 7
    signed_pan = ((pan - 0x40) << 1) + pan_extra
    if mod_type == 2:
        signed_pan += mod_value
    signed_pan = max(-128, min(127, signed_pan))
    right = ((signed_pan + 128) * base >> 8) & 0xFF
    left = ((127 - signed_pan) * base >> 8) & 0xFF
    return right, left


def execute_track(track: dict, command_map: dict[int, dict], max_steps: int = 200_000) -> dict:
    pc = track["offset"]
    tick = 0
    stack: list[int] = []
    visited: Counter[int] = Counter()
    events = []
    key = 60
    velocity = 100
    voice = 0
    volume = 127
    volume_multiplier = 64
    pan = 64
    pan_extra = 0
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

    def append_pitch_state(command_name: str) -> None:
        modulation = (mod_value << 4) if mod_type == 0 else 0
        total = ((tune + bend * bend_range) << 2) + (key_shift << 8) + modulation
        events.append({
            "tick": tick,
            "type": "pitch_state",
            "command": command_name,
            "pitch_key_delta": total >> 8,
            "pitch_fine": total & 0xFF,
            "pitch_modulation": mod_value if mod_type == 0 else 0,
            "pitch_components": {
                "key_shift": key_shift,
                "bend": bend,
                "bend_range": bend_range,
                "tune": tune,
            },
        })

    def append_mix_state(command_name: str) -> None:
        right, left = _track_mix_coefficients(
            volume,
            volume_multiplier,
            pan,
            mod_type=mod_type,
            mod_value=mod_value,
            pan_extra=pan_extra,
        )
        events.append({
            "tick": tick,
            "type": "mix_state",
            "command": command_name,
            "track_right": right,
            "track_left": left,
            "modulation": mod_value if mod_type in (1, 2) else 0,
            "mod_type": mod_type,
        })

    def advance_pitch_lfo() -> None:
        nonlocal lfo_countdown, lfo_phase, mod_value
        if lfo_speed == 0 or mod_depth == 0:
            return
        if lfo_countdown:
            lfo_countdown = (lfo_countdown - 1) & 0xFF
            return
        lfo_phase = (lfo_phase + lfo_speed) & 0xFF
        if 0x40 <= lfo_phase <= 0xBF:
            triangle = 0x80 - lfo_phase
        else:
            triangle = _signed8(lfo_phase)
        next_mod = (mod_depth * triangle) >> 6
        if (next_mod & 0xFF) == (mod_value & 0xFF):
            return
        mod_value = next_mod
        if mod_type == 0:
            append_pitch_state("LFO")
        elif mod_type in (1, 2):
            append_mix_state("LFO")
    for step in range(max_steps):
        command = command_map.get(pc)
        if command is None:
            raise ValueError(f"execution target 0x{pc:X} is not a command boundary")
        visited[pc] += 1
        name = command["name"]
        next_pc = pc + command["size"]
        if name.startswith("W"):
            for _ in range(_ticks(name)):
                tick += 1
                advance_pitch_lfo()
        elif name == "FINE":
            stop_reason = "fine"
            break
        elif name == "PATT":
            if len(stack) >= 16:
                raise ValueError(f"pattern stack overflow at 0x{pc:X}")
            stack.append(next_pc)
            pc = command["target_offset"]
            continue
        elif name == "PEND":
            if stack:
                pc = stack.pop()
                continue
            # This ROM points some song tracks at shared fragments containing
            # PEND before their main body. The engine falls through when no
            # pattern return address is active.
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
            append_mix_state(name)
        elif name == "PAN":
            pan = command["value"]
            events.append({"tick": tick, "type": "pan", "value": pan})
            append_mix_state(name)
        elif name == "KEYSH":
            key_shift = _signed8(command["value"])
            append_pitch_state(name)
        elif name == "BEND":
            bend = command["value"] - 0x40
            events.append({"tick": tick, "type": "bend", "value": command["value"]})
            append_pitch_state(name)
        elif name == "BENDR":
            bend_range = command["value"]
            append_pitch_state(name)
        elif name == "TUNE":
            tune = command["value"] - 0x40
            append_pitch_state(name)
        elif name == "LFOS":
            lfo_speed = command["value"]
            if lfo_speed == 0:
                mod_value = 0
                lfo_phase = 0
                if mod_type == 0:
                    append_pitch_state(name)
                elif mod_type in (1, 2):
                    append_mix_state(name)
        elif name == "LFODL":
            lfo_delay = command["value"]
        elif name == "MOD":
            mod_depth = command["value"]
            if mod_depth == 0:
                mod_value = 0
                lfo_phase = 0
                if mod_type == 0:
                    append_pitch_state(name)
                elif mod_type in (1, 2):
                    append_mix_state(name)
        elif name == "MODT":
            previous_mod_type = mod_type
            mod_type = command["value"]
            if previous_mod_type == 0 or mod_type == 0:
                append_pitch_state(name)
            if previous_mod_type in (1, 2) or mod_type in (1, 2):
                append_mix_state(name)
        elif name == "EOT":
            tie_key = command.get("key", key)
            tied_note = open_ties.pop(tie_key, None)
            if tied_note is not None:
                tied_note["duration"] = tick - tied_note["tick"]
            events.append({
                "tick": tick, "type": "end_tie", "key": tie_key,
                "matched": tied_note is not None,
            })
        elif name == "TIE" or name.startswith("N"):
            args = command.get("args", [])
            if len(args) >= 1:
                key = args[0]
            if len(args) >= 2:
                velocity = args[1]
            gate = args[2] if len(args) >= 3 else 0
            lfo_countdown = lfo_delay
            duration = None if name == "TIE" else _ticks(name) + gate
            modulation = (mod_value << 4) if mod_type == 0 else 0
            pitch_total = (
                ((tune + bend * bend_range) << 2)
                + (key_shift << 8)
                + modulation
            )
            track_right, track_left = _track_mix_coefficients(
                volume,
                volume_multiplier,
                pan,
                mod_type=mod_type,
                mod_value=mod_value,
                pan_extra=pan_extra,
            )
            note_event = {
                "tick": tick, "type": "note", "key": key, "velocity": velocity,
                "duration": duration, "voice": voice, "volume": volume, "pan": pan,
                "tied": name == "TIE",
                "pitch_key": max(0, key + (pitch_total >> 8)),
                "pitch_fine": pitch_total & 0xFF,
                "pitch_modulation": mod_value if mod_type == 0 else 0,
                "pitch_components": {
                    "key_shift": key_shift,
                    "bend": bend,
                    "bend_range": bend_range,
                    "tune": tune,
                },
                "track_mix_right": track_right,
                "track_mix_left": track_left,
            }
            events.append(note_event)
            if name == "TIE":
                open_ties[key] = note_event
        pc = next_pc
    else:
        raise ValueError(f"track 0x{track['offset']:X} exceeded {max_steps} steps")
    return {
        "offset": track["offset"], "duration_ticks": tick, "steps": step + 1,
        "stop_reason": stop_reason, "stop_offset": pc, "events": events,
        "open_tie_keys": sorted(open_ties),
    }


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
    return b"MTrk" + struct.pack(">I", len(body)) + body


def midi_file(tracks: list[dict]) -> bytes:
    chunks = [_midi_track(track["events"], index % 16) for index, track in enumerate(tracks)]
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQN) + b"".join(chunks)


def render(input_dir: Path, audio_bank: Path, output_dir: Path) -> dict:
    decoded = json.loads((input_dir / "tracks-decoded.json").read_text(encoding="utf-8"))
    bank = json.loads(audio_bank.read_text(encoding="utf-8"))
    command_map = {
        command["offset"]: command
        for track in decoded["tracks"] for command in track["commands"]
    }
    tracks_by_offset = {track["offset"]: track for track in decoded["tracks"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    songs = []
    tie_lifecycle = Counter()
    event_type_counts = Counter()
    for entry in bank["entries"]:
        rendered = []
        for pointer in entry["track_ptrs"]:
            offset = pointer - 0x08000000
            rendered.append(execute_track(tracks_by_offset[offset], command_map))
        sound_id = entry["sound_id"]
        path = output_dir / f"sound_{sound_id:03d}.mid"
        path.write_bytes(midi_file(rendered))
        tied_notes = [
            event
            for track in rendered for event in track["events"]
            if event["type"] == "note" and event.get("tied")
        ]
        event_type_counts.update(
            event["type"] for track in rendered for event in track["events"]
        )
        tie_lifecycle["total"] += len(tied_notes)
        tie_lifecycle["closed_by_eot"] += sum(
            event["duration"] is not None for event in tied_notes
        )
        tie_lifecycle["left_open_at_loop_end"] += sum(
            event["duration"] is None for event in tied_notes
        )
        songs.append({
            "sound_id": sound_id,
            "track_count": len(rendered),
            "duration_ticks": max(track["duration_ticks"] for track in rendered),
            "event_count": sum(len(track["events"]) for track in rendered),
            "stop_reasons": dict(Counter(track["stop_reason"] for track in rendered)),
            "tie_count": len(tied_notes),
            "closed_tie_count": sum(event["duration"] is not None for event in tied_notes),
            "midi": path.name,
        })
    result = {
        "format": "MP2K one-loop structural MIDI export",
        "ppqn": PPQN,
        "song_count": len(songs),
        "total_event_count": sum(event_type_counts.values()),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "tie_lifecycle": dict(tie_lifecycle),
        "songs": songs,
    }
    (output_dir / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("build/audio-v2"))
    parser.add_argument("--audio-bank", type=Path, default=Path("sequel/content/audio/bank.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/audio-v2/midi"))
    args = parser.parse_args()
    result = render(args.input_dir, args.audio_bank, args.output_dir)
    print(json.dumps({
        "song_count": result["song_count"],
        "total_events": result["total_event_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
