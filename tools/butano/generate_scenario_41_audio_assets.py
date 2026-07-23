#!/usr/bin/env python3
"""Package original MP2K PCM as a Maxmod-safe mono 22050 Hz S3M stream."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import wave
from pathlib import Path


CONVERTER_COMMIT = "ec956fc951cc637153139cb968721f427c802e51"
SCENARIO_41_MUSIC_SEMANTICS = {
    2: "postbattle_map_bgm",
    5: "prebattle_bgm",
    8: "postbattle_dialogue_bgm",
    14: "battle_bgm",
    15: "combo_animation_bgm",
}
MAXMOD_SAMPLE_RATE = 22050
MAXMOD_PEAK = 120


def _align(value: int, alignment: int = 16) -> int:
    return (value + alignment - 1) & -alignment


def _memory_segment(offset: int) -> bytes:
    if offset % 16:
        raise ValueError(f"sample offset is not paragraph aligned: {offset}")
    paragraph = offset >> 4
    return bytes(((paragraph >> 16) & 0xFF, paragraph & 0xFF, (paragraph >> 8) & 0xFF))


def _sample_header(offset: int, data: bytes, sample_rate: int, name: str) -> bytes:
    short_name = name.encode("ascii")[:12].ljust(12, b"\0")
    long_name = name.encode("ascii")[:28].ljust(28, b"\0")
    return b"".join(
        (
            b"\x01",
            short_name,
            _memory_segment(offset),
            struct.pack("<III", len(data), 0, 0),
            bytes((64, 0, 0, 0)),
            struct.pack("<I", sample_rate),
            bytes(12),
            long_name,
            b"SCRS",
        )
    )


def _pattern(instruments: tuple[int, ...], speed: int, tempo: int) -> bytes:
    events = bytearray()
    for channel, instrument in enumerate(instruments):
        if channel == 0:
            events.extend((0xA0 | channel, 0x40, instrument, 0x14, tempo))
        elif channel == 1:
            events.extend((0xA0 | channel, 0x40, instrument, 0x01, speed))
        else:
            events.extend((0x20 | channel, 0x40, instrument))
    if len(instruments) == 1:
        # A separate silent control channel carries the speed command because
        # one S3M row cannot attach both tempo and speed effects to channel 0.
        events.extend((0x81, 0x01, speed))
    packed_length = 2 + len(events) + 64
    result = bytearray(struct.pack("<H", packed_length))
    result.extend(events)
    result.extend(bytes(64))
    if len(result) > 80:
        raise ValueError("pattern does not fit the converter-compatible 80-byte slot")
    result.extend(bytes(80 - len(result)))
    return bytes(result)


def _pattern_timing(duration: float, channels: int) -> tuple[int, int, float]:
    candidates = []
    speeds = range(1, 32)
    for speed in speeds:
        for tempo in range(32, 256):
            pattern_duration = 160 * speed / tempo
            candidates.append((abs(pattern_duration - duration), speed, tempo, pattern_duration))
    _, speed, tempo, pattern_duration = min(candidates)
    return speed, tempo, pattern_duration


def prepare_maxmod_pcm(
    pcm: bytes, channels: int, sample_rate: int
) -> tuple[bytes, dict[str, float | int]]:
    """Downmix, remove DC, resample and headroom-limit unsigned 8-bit PCM."""
    if channels not in (1, 2):
        raise ValueError("only mono or stereo unsigned 8-bit PCM is supported")
    if sample_rate <= 0 or len(pcm) % channels:
        raise ValueError("invalid PCM format")
    frame_count = len(pcm) // channels
    if not frame_count:
        raise ValueError("input WAV has no PCM frames")

    mono = [
        sum(pcm[index + channel] - 128 for channel in range(channels)) / channels
        for index in range(0, len(pcm), channels)
    ]
    dc_offset_before = sum(mono) / frame_count
    centered = [sample - dc_offset_before for sample in mono]
    peak_before = max(abs(sample) for sample in centered)
    gain = min(1.0, MAXMOD_PEAK / peak_before) if peak_before else 1.0

    output_count = max(1, round(frame_count * MAXMOD_SAMPLE_RATE / sample_rate))
    converted = bytearray(output_count)
    for output_index in range(output_count):
        source_position = output_index * sample_rate / MAXMOD_SAMPLE_RATE
        source_index = min(int(source_position), frame_count - 1)
        next_index = min(source_index + 1, frame_count - 1)
        fraction = source_position - source_index
        sample = centered[source_index]
        sample += (centered[next_index] - centered[source_index]) * fraction
        quantized = round(sample * gain) + 128
        converted[output_index] = min(255, max(0, quantized))

    dc_offset_after = sum(sample - 128 for sample in converted) / output_count
    return bytes(converted), {
        "source_channels": channels,
        "source_sample_rate": sample_rate,
        "source_frame_count": frame_count,
        "channels": 1,
        "sample_rate": MAXMOD_SAMPLE_RATE,
        "frame_count": output_count,
        "dc_offset_before": dc_offset_before,
        "dc_offset_after": dc_offset_after,
        "peak_before": peak_before,
        "gain": gain,
    }


def build_s3m(
    pcm: bytes, channels: int, sample_rate: int, segment_seconds: int, sound_id: int = 8
) -> bytes:
    if channels not in (1, 2):
        raise ValueError("only mono or stereo unsigned 8-bit PCM is supported")
    if len(pcm) % channels:
        raise ValueError("PCM byte count is not frame aligned")
    if sample_rate <= 0 or segment_seconds <= 0:
        raise ValueError("sample rate and segment duration must be positive")

    segment_bytes = sample_rate * segment_seconds * channels
    interleaved_segments = [
        pcm[offset : offset + segment_bytes]
        for offset in range(0, len(pcm), segment_bytes)
    ]
    if not interleaved_segments:
        raise ValueError("input WAV has no PCM frames")

    samples: list[bytes] = []
    pattern_instruments: list[tuple[int, ...]] = []
    for segment in interleaved_segments:
        instruments = []
        for channel in range(channels):
            samples.append(segment[channel::channels])
            instruments.append(len(samples))
        pattern_instruments.append(tuple(instruments))

    order_count = len(pattern_instruments)
    orders = bytearray(range(order_count))
    if len(orders) % 2:
        orders.append(0xFF)
    order_count_padded = len(orders)
    sample_count = len(samples)
    pattern_count = len(pattern_instruments)

    pointer_tables_end = 96 + order_count_padded + sample_count * 2 + pattern_count * 2
    panning_offset = pointer_tables_end
    instrument_offset = _align(panning_offset + 32)
    pattern_offset = _align(instrument_offset + sample_count * 80)
    sample_data_offset = _align(pattern_offset + pattern_count * 80)

    sample_offsets: list[int] = []
    next_sample_offset = sample_data_offset
    for sample in samples:
        sample_offsets.append(next_sample_offset)
        next_sample_offset += _align(len(sample))

    title = f"scenario 41 cue {sound_id}".encode("ascii").ljust(28, b"\0")
    channel_settings = bytearray((0xFF,) * 32)
    channel_settings[0] = 0x00
    if channels == 2:
        channel_settings[1] = 0x08
    else:
        channel_settings[1] = 0x01
    header = bytearray()
    header.extend(title)
    header.extend((0x1A, 0x10, 0, 0))
    header.extend(struct.pack("<HHH", order_count_padded, sample_count, pattern_count))
    header.extend(struct.pack("<HHH", 0, 0x5131, 2))
    header.extend(b"SCRM")
    header.extend((0x40, 0x04, 0x80, 0xB0, 0x10, 0xFC))
    header.extend(bytes((0, 2, 0, 0, 0, 0, 0, 0)))
    header.extend(bytes(2))
    header.extend(channel_settings)
    if len(header) != 96:
        raise AssertionError(f"unexpected S3M header length: {len(header)}")

    result = bytearray(header)
    result.extend(orders)
    result.extend(struct.pack(f"<{sample_count}H", *(offset // 16 for offset in range(
        instrument_offset, instrument_offset + sample_count * 80, 80
    ))))
    result.extend(struct.pack(f"<{pattern_count}H", *(offset // 16 for offset in range(
        pattern_offset, pattern_offset + pattern_count * 80, 80
    ))))

    panning = bytearray((0x08,) * 32)
    panning[0] = 0x20 if channels == 2 else 0x28
    if channels == 2:
        panning[1] = 0x2F
    result.extend(panning)
    result.extend(bytes(instrument_offset - len(result)))

    for index, (offset, sample) in enumerate(zip(sample_offsets, samples), start=1):
        result.extend(_sample_header(offset, sample, sample_rate, f"s41-{index:02d}"))
    result.extend(bytes(pattern_offset - len(result)))
    for instruments, segment in zip(pattern_instruments, interleaved_segments):
        duration = len(segment) / (sample_rate * channels)
        speed, tempo, _ = _pattern_timing(duration, channels)
        result.extend(_pattern(instruments, speed, tempo))
    result.extend(bytes(sample_data_offset - len(result)))
    for sample in samples:
        result.extend(sample)
        result.extend(bytes((0x80,)) * (_align(len(sample)) - len(sample)))
    return bytes(result)


def generate(input_path: Path, output_path: Path, manifest_path: Path, segment_seconds: int) -> dict:
    with wave.open(str(input_path), "rb") as stream:
        if stream.getsampwidth() != 1 or stream.getcomptype() != "NONE":
            raise ValueError("input must be uncompressed unsigned 8-bit PCM")
        source_channels = stream.getnchannels()
        source_sample_rate = stream.getframerate()
        source_frame_count = stream.getnframes()
        pcm = stream.readframes(source_frame_count)

    converted_pcm, conversion = prepare_maxmod_pcm(
        pcm, source_channels, source_sample_rate
    )
    channels = int(conversion["channels"])
    sample_rate = int(conversion["sample_rate"])
    frame_count = int(conversion["frame_count"])

    match = re.fullmatch(r"sound_(\d+)", input_path.stem)
    sound_id = int(match.group(1)) if match else 8
    module = build_s3m(converted_pcm, channels, sample_rate, segment_seconds, sound_id)
    segment_frame_count = sample_rate * segment_seconds
    segment_durations = [
        min(segment_frame_count, frame_count - offset) / sample_rate
        for offset in range(0, frame_count, segment_frame_count)
    ]
    module_loop_duration = sum(
        _pattern_timing(duration, channels)[2] for duration in segment_durations
    )
    source_duration = source_frame_count / source_sample_rate
    metadata = {
        "format_version": 1,
        "sound_id": sound_id,
        "semantic": SCENARIO_41_MUSIC_SEMANTICS.get(sound_id, "reference_only"),
        "loop": True,
        "channels": channels,
        "sample_rate": sample_rate,
        "sample_width_bytes": 1,
        "frame_count": frame_count,
        "source_channels": source_channels,
        "source_sample_rate": source_sample_rate,
        "source_frame_count": source_frame_count,
        "dc_offset_before": conversion["dc_offset_before"],
        "dc_offset_after": conversion["dc_offset_after"],
        "peak_before": conversion["peak_before"],
        "gain": conversion["gain"],
        "duration_seconds": source_duration,
        "module_loop_duration_seconds": module_loop_duration,
        "module_loop_error_seconds": module_loop_duration - source_duration,
        "segment_seconds": segment_seconds,
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "converted_pcm_sha256": hashlib.sha256(converted_pcm).hexdigest(),
        "wav_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "s3m_sha256": hashlib.sha256(module).hexdigest(),
        "converter_reference_commit": CONVERTER_COMMIT,
        "source": str(input_path),
        "output": str(output_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(module)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("build/audio-v2/pcm/sound_008.wav"))
    parser.add_argument("--output", type=Path, default=Path("butano-sequel/audio/sound_008.s3m"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/scenario-41-audio-reference-v1/cue-8-manifest.json"),
    )
    parser.add_argument("--segment-seconds", type=int, default=5)
    args = parser.parse_args()
    metadata = generate(args.input, args.output, args.manifest, args.segment_seconds)
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
