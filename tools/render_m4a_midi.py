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
    pan = 64
    repeat_state: dict[int, int] = {}
    stop_reason = ""
    for step in range(max_steps):
        command = command_map.get(pc)
        if command is None:
            raise ValueError(f"execution target 0x{pc:X} is not a command boundary")
        visited[pc] += 1
        name = command["name"]
        next_pc = pc + command["size"]
        if name.startswith("W"):
            tick += _ticks(name)
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
        elif name == "PAN":
            pan = command["value"]
            events.append({"tick": tick, "type": "pan", "value": pan})
        elif name == "BEND":
            events.append({"tick": tick, "type": "bend", "value": command["value"]})
        elif name == "EOT":
            events.append({"tick": tick, "type": "end_tie", "key": command.get("key", key)})
        elif name == "TIE" or name.startswith("N"):
            args = command.get("args", [])
            if len(args) >= 1:
                key = args[0]
            if len(args) >= 2:
                velocity = args[1]
            gate = args[2] if len(args) >= 3 else 0
            duration = None if name == "TIE" else _ticks(name) + gate
            events.append({
                "tick": tick, "type": "note", "key": key, "velocity": velocity,
                "duration": duration, "voice": voice, "volume": volume, "pan": pan,
            })
        pc = next_pc
    else:
        raise ValueError(f"track 0x{track['offset']:X} exceeded {max_steps} steps")
    return {
        "offset": track["offset"], "duration_ticks": tick, "steps": step + 1,
        "stop_reason": stop_reason, "stop_offset": pc, "events": events,
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
    for entry in bank["entries"]:
        rendered = []
        for pointer in entry["track_ptrs"]:
            offset = pointer - 0x08000000
            rendered.append(execute_track(tracks_by_offset[offset], command_map))
        sound_id = entry["sound_id"]
        path = output_dir / f"sound_{sound_id:03d}.mid"
        path.write_bytes(midi_file(rendered))
        songs.append({
            "sound_id": sound_id,
            "track_count": len(rendered),
            "duration_ticks": max(track["duration_ticks"] for track in rendered),
            "event_count": sum(len(track["events"]) for track in rendered),
            "stop_reasons": dict(Counter(track["stop_reason"] for track in rendered)),
            "midi": path.name,
        })
    result = {
        "format": "MP2K one-loop structural MIDI export",
        "ppqn": PPQN,
        "song_count": len(songs),
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
    print(json.dumps({"song_count": result["song_count"], "total_events": sum(song["event_count"] for song in result["songs"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
