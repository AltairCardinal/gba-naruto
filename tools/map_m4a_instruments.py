#!/usr/bin/env python3
"""Map executed m4a note events through voicegroups to terminal instruments."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from tools.extract_audio_assets import parse_wave
    from tools.m4a_pitch_step import midi_key_to_step
    from tools.render_m4a_midi import execute_track
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from extract_audio_assets import parse_wave
    from m4a_pitch_step import midi_key_to_step
    from render_m4a_midi import execute_track

ROM_BASE = 0x08000000
TONE_SIZE = 12


def _channel_mix_coefficients(
    track_right: int,
    track_left: int,
    *,
    velocity: int,
    tone_pan: int,
) -> tuple[int, int]:
    """Reproduce the pre-envelope channel gains at 0x0809A6D8."""
    right = min(255, (velocity * (tone_pan + 128) * track_right) >> 14)
    left = min(255, (velocity * (127 - tone_pan) * track_left) >> 14)
    return right, left


def parse_tone(rom: bytes, offset: int) -> dict:
    if not 0 <= offset <= len(rom) - TONE_SIZE:
        raise ValueError(f"tone offset 0x{offset:X} outside ROM")
    raw = rom[offset:offset + TONE_SIZE]
    return {
        "offset": offset,
        "type": raw[0],
        "key": raw[1],
        "length": raw[2],
        "pan_sweep": raw[3],
        "pointer": int.from_bytes(raw[4:8], "little"),
        "attack": raw[8],
        "decay": raw[9],
        "sustain": raw[10],
        "release": raw[11],
    }


def resolve_tone(rom: bytes, voicegroup_offset: int, voice: int, key: int) -> dict:
    parent = parse_tone(rom, voicegroup_offset + voice * TONE_SIZE)
    if parent["type"] != 0x80:
        return {"parent": parent, "terminal": parent, "drum": False}
    table = parent["pointer"] - ROM_BASE
    child = parse_tone(rom, table + key * TONE_SIZE)
    if child["type"] == 0x80:
        raise ValueError(f"nested drum tone at 0x{child['offset']:X} is unsupported")
    return {"parent": parent, "terminal": child, "drum": True}


def analyze(rom: bytes, bank: dict, decoded: dict) -> dict:
    command_map = {command["offset"]: command for track in decoded["tracks"] for command in track["commands"]}
    tracks = {track["offset"]: track for track in decoded["tracks"]}
    terminal_counts: Counter[int] = Counter()
    wave_counts: Counter[int] = Counter()
    song_rows = []
    drum_notes = 0
    missing = []
    center_pitch_steps: list[int] = []
    invalid_center_pitch_steps = []
    track_pitch_steps: list[int] = []
    invalid_track_pitch_steps = []
    noncenter_track_pitch_notes = 0
    mid_note_pitch_steps: list[int] = []
    mid_note_pitch_update_commands: Counter[str] = Counter()
    invalid_mid_note_pitch_updates = []
    channel_mix_notes: list[tuple[int, int]] = []
    invalid_channel_mix_notes = []
    mid_note_mix_updates: list[tuple[int, int]] = []
    mid_note_mix_update_commands: Counter[str] = Counter()
    invalid_mid_note_mix_updates = []
    for song in bank["entries"]:
        voicegroup = song["voicegroup_ptr"] - ROM_BASE
        song_types: Counter[int] = Counter()
        song_waves: Counter[int] = Counter()
        song_drums = 0
        for pointer in song["track_ptrs"]:
            timeline = execute_track(tracks[pointer - ROM_BASE], command_map)
            pitch_states = [
                (index, event)
                for index, event in enumerate(timeline["events"])
                if event["type"] == "pitch_state"
            ]
            mix_states = [
                (index, event)
                for index, event in enumerate(timeline["events"])
                if event["type"] == "mix_state"
            ]
            for event_index, event in enumerate(timeline["events"]):
                if event["type"] != "note":
                    continue
                resolved = resolve_tone(rom, voicegroup, event["voice"], event["key"])
                terminal = resolved["terminal"]
                terminal_counts[terminal["type"]] += 1
                song_types[terminal["type"]] += 1
                if resolved["drum"]:
                    drum_notes += 1
                    song_drums += 1
                if terminal["type"] == 0:
                    wave_offset = terminal["pointer"] - ROM_BASE
                    wave = parse_wave(rom, wave_offset)
                    if wave is None:
                        missing.append({"sound_id": song["sound_id"], "voice": event["voice"], "key": event["key"], "wave_offset": wave_offset})
                    else:
                        wave_counts[wave_offset] += 1
                        song_waves[wave_offset] += 1
                        pitch_key = terminal["key"] if resolved["drum"] else event["key"]
                        tone_pan = (
                            (terminal["pan_sweep"] - 0xC0) << 1
                            if resolved["drum"] and terminal["pan_sweep"] & 0x80
                            else 0
                        )
                        channel_mix = _channel_mix_coefficients(
                            event["track_mix_right"],
                            event["track_mix_left"],
                            velocity=event["velocity"],
                            tone_pan=tone_pan,
                        )
                        if all(0 <= value <= 0xFF for value in channel_mix):
                            channel_mix_notes.append(channel_mix)
                        else:
                            invalid_channel_mix_notes.append({
                                "sound_id": song["sound_id"],
                                "voice": event["voice"],
                                "event_key": event["key"],
                                "track_mix": [
                                    event["track_mix_right"], event["track_mix_left"]
                                ],
                                "velocity": event["velocity"],
                                "tone_pan": tone_pan,
                                "channel_mix": list(channel_mix),
                            })
                        step = midi_key_to_step(
                            rom, wave["frequency_raw"], key=pitch_key, fine=0
                        )
                        if step > 0:
                            center_pitch_steps.append(step)
                        else:
                            invalid_center_pitch_steps.append({
                                "sound_id": song["sound_id"],
                                "voice": event["voice"],
                                "event_key": event["key"],
                                "pitch_key": pitch_key,
                                "wave_offset": wave_offset,
                                "step": step,
                            })
                        pitch_delta = event.get("pitch_key", event["key"]) - event["key"]
                        track_key = max(0, pitch_key + pitch_delta)
                        track_fine = event.get("pitch_fine", 0)
                        if pitch_delta or track_fine:
                            noncenter_track_pitch_notes += 1
                        try:
                            track_step = midi_key_to_step(
                                rom,
                                wave["frequency_raw"],
                                key=track_key,
                                fine=track_fine,
                            )
                        except ValueError as exc:
                            invalid_track_pitch_steps.append({
                                "sound_id": song["sound_id"],
                                "voice": event["voice"],
                                "event_key": event["key"],
                                "track_key": track_key,
                                "track_fine": track_fine,
                                "error": str(exc),
                            })
                        else:
                            if track_step > 0:
                                track_pitch_steps.append(track_step)
                            else:
                                invalid_track_pitch_steps.append({
                                    "sound_id": song["sound_id"],
                                    "voice": event["voice"],
                                    "event_key": event["key"],
                                    "track_key": track_key,
                                    "track_fine": track_fine,
                                    "step": track_step,
                                })
                        note_end = (
                            event["tick"] + event["duration"]
                            if event["duration"] is not None
                            else timeline["duration_ticks"]
                        )
                        for update_index, update in pitch_states:
                            if update_index <= event_index:
                                continue
                            if not event["tick"] <= update["tick"] < note_end:
                                continue
                            update_key = max(0, pitch_key + update["pitch_key_delta"])
                            try:
                                update_step = midi_key_to_step(
                                    rom,
                                    wave["frequency_raw"],
                                    key=update_key,
                                    fine=update["pitch_fine"],
                                )
                            except ValueError as exc:
                                invalid_mid_note_pitch_updates.append({
                                    "sound_id": song["sound_id"],
                                    "voice": event["voice"],
                                    "event_key": event["key"],
                                    "update_tick": update["tick"],
                                    "update_key": update_key,
                                    "update_fine": update["pitch_fine"],
                                    "error": str(exc),
                                })
                            else:
                                if update_step > 0:
                                    mid_note_pitch_steps.append(update_step)
                                    mid_note_pitch_update_commands[update["command"]] += 1
                                else:
                                    invalid_mid_note_pitch_updates.append({
                                        "sound_id": song["sound_id"],
                                        "voice": event["voice"],
                                        "event_key": event["key"],
                                        "update_tick": update["tick"],
                                        "update_key": update_key,
                                        "update_fine": update["pitch_fine"],
                                        "step": update_step,
                                    })
                        for update_index, update in mix_states:
                            if update_index <= event_index:
                                continue
                            if not event["tick"] <= update["tick"] < note_end:
                                continue
                            update_mix = _channel_mix_coefficients(
                                update["track_right"],
                                update["track_left"],
                                velocity=event["velocity"],
                                tone_pan=tone_pan,
                            )
                            if all(0 <= value <= 0xFF for value in update_mix):
                                mid_note_mix_updates.append(update_mix)
                                mid_note_mix_update_commands[update["command"]] += 1
                            else:
                                invalid_mid_note_mix_updates.append({
                                    "sound_id": song["sound_id"],
                                    "voice": event["voice"],
                                    "event_key": event["key"],
                                    "update_tick": update["tick"],
                                    "track_mix": [
                                        update["track_right"], update["track_left"]
                                    ],
                                    "velocity": event["velocity"],
                                    "tone_pan": tone_pan,
                                    "channel_mix": list(update_mix),
                                })
        song_rows.append({
            "sound_id": song["sound_id"],
            "note_count": sum(song_types.values()),
            "drum_note_count": song_drums,
            "terminal_type_counts": {f"0x{key:02X}": value for key, value in sorted(song_types.items())},
            "wave_offsets": [f"0x{offset:06X}" for offset in sorted(song_waves)],
        })
    note_count = sum(terminal_counts.values())
    direct_count = terminal_counts[0]
    return {
        "format": "Executed m4a note -> voicegroup -> terminal tone coverage",
        "song_count": len(song_rows),
        "note_count": note_count,
        "drum_note_count": drum_notes,
        "terminal_type_counts": {f"0x{key:02X}": value for key, value in sorted(terminal_counts.items())},
        "directsound_note_count": direct_count,
        "directsound_coverage": direct_count / note_count if note_count else 0,
        "unique_wave_count": len(wave_counts),
        "missing_wave_count": len(missing),
        "missing_waves": missing,
        "center_pitch_step_count": len(center_pitch_steps),
        "invalid_center_pitch_step_count": len(invalid_center_pitch_steps),
        "invalid_center_pitch_steps": invalid_center_pitch_steps,
        "center_pitch_step_range": {
            "min": min(center_pitch_steps) if center_pitch_steps else None,
            "max": max(center_pitch_steps) if center_pitch_steps else None,
        },
        "center_pitch_step_boundary": (
            "Nominal note-on key with fine=0. Drum tones use the child root key. "
            "Track bend/tune/modulation and mid-note automation remain separate."
        ),
        "track_pitch_step_count": len(track_pitch_steps),
        "invalid_track_pitch_step_count": len(invalid_track_pitch_steps),
        "invalid_track_pitch_steps": invalid_track_pitch_steps,
        "noncenter_track_pitch_note_count": noncenter_track_pitch_notes,
        "track_pitch_step_range": {
            "min": min(track_pitch_steps) if track_pitch_steps else None,
            "max": max(track_pitch_steps) if track_pitch_steps else None,
        },
        "track_pitch_step_boundary": (
            "Applies note-on KEYSH, BEND, BENDR, TUNE and current MODT=0 pitch-LFO "
            "state. Commands occurring while a note is already sounding are counted "
            "separately as mid-note automation."
        ),
        "mid_note_pitch_update_count": len(mid_note_pitch_steps),
        "mid_note_pitch_update_command_counts": dict(
            sorted(mid_note_pitch_update_commands.items())
        ),
        "invalid_mid_note_pitch_update_count": len(invalid_mid_note_pitch_updates),
        "invalid_mid_note_pitch_updates": invalid_mid_note_pitch_updates,
        "mid_note_pitch_step_range": {
            "min": min(mid_note_pitch_steps) if mid_note_pitch_steps else None,
            "max": max(mid_note_pitch_steps) if mid_note_pitch_steps else None,
        },
        "mid_note_pitch_boundary": (
            "Applies KEYSH/BEND/BENDR/TUNE commands and MODT=0 pitch LFO ticks while "
            "a DirectSound note is active. Open ties are bounded by the one-loop track "
            "duration. MODT=1 volume and MODT=2 pan automation remain separate."
        ),
        "channel_mix_note_count": len(channel_mix_notes),
        "invalid_channel_mix_note_count": len(invalid_channel_mix_notes),
        "invalid_channel_mix_notes": invalid_channel_mix_notes,
        "channel_mix_right_range": {
            "min": min((item[0] for item in channel_mix_notes), default=None),
            "max": max((item[0] for item in channel_mix_notes), default=None),
        },
        "channel_mix_left_range": {
            "min": min((item[1] for item in channel_mix_notes), default=None),
            "max": max((item[1] for item in channel_mix_notes), default=None),
        },
        "mid_note_mix_update_count": len(mid_note_mix_updates),
        "mid_note_mix_update_command_counts": dict(
            sorted(mid_note_mix_update_commands.items())
        ),
        "invalid_mid_note_mix_update_count": len(invalid_mid_note_mix_updates),
        "invalid_mid_note_mix_updates": invalid_mid_note_mix_updates,
        "channel_mix_boundary": (
            "Reproduces 0x0809B3E0 track right/left gain caching and 0x0809A6D8 "
            "velocity plus drum-tone-pan propagation. The ROM corpus has no MODT or "
            "LFODL commands; synthetic tests lock MODT=1/2 behavior. Envelope scaling "
            "from channel gains to final mixer gains remains separate."
        ),
        "wave_usage": [{"offset": offset, "offset_hex": f"0x{offset:06X}", "note_count": count} for offset, count in sorted(wave_counts.items())],
        "songs": song_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument("--bank", type=Path, default=Path("sequel/content/audio/bank.json"))
    parser.add_argument("--decoded", type=Path, default=Path("build/audio-v2/tracks-decoded.json"))
    parser.add_argument("--output", type=Path, default=Path("build/audio-v2/instrument-map.json"))
    args = parser.parse_args()
    result = analyze(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text(encoding="utf-8")),
        json.loads(args.decoded.read_text(encoding="utf-8")),
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "song_count", "note_count", "drum_note_count", "terminal_type_counts",
        "directsound_coverage", "unique_wave_count", "missing_wave_count"
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
