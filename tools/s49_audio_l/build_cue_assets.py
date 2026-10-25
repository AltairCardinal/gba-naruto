#!/usr/bin/env python3
"""Build Maxmod assets for original MP2K cues the remake does not have yet.

Stream L (S49 audio wiring).  The remake tree only ships the S49 battle BGM
missing: cue 10 (scenario 49 battle BGM) plus the two scenario-49 exclusive
tool cues 146 and 152.

Pipeline (identical in shape to the existing scenario-41 asset pipeline, see
``tools/butano/generate_scenario_41_sfx_assets.py`` and
``tools/butano/generate_scenario_41_audio_assets.py`` in the remake tree):

1. Render the cue offline from the original ROM with the MP2K engine
   (``tools/audio_song_export.py`` in the remake tree) -> 16-bit stereo WAV.
2. Downmix to mono and quantize to unsigned 8-bit, then resample to 22050 Hz
   with the same nearest-neighbour rule the scenario-41 SFX pipeline used.
3. SFX  -> write the mono 8-bit 22050 Hz WAV as ``butano-sequel/audio/sound_NNN.wav``.
   BGM  -> feed the mono WAV to the scenario-41 S3M builder and write
           ``butano-sequel/audio/sound_NNN.s3m``.

The original-side ground truth (per cue duration and PCM hash) comes from the
reverse tree's ``artifacts/audio/full-song-render-evidence.json``.

Usage:
    python tools/s49_audio_l/build_cue_assets.py --sound-id 10 --kind bgm
    python tools/s49_audio_l/build_cue_assets.py --sound-id 146 --kind sfx
    python tools/s49_audio_l/build_cue_assets.py --sound-id 102 --kind sfx --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import sys
import wave

REPO = pathlib.Path(__file__).resolve().parents[2]
REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
REVERSE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-reverse")
ORIGINAL_ROM = REMAKE_ROOT / "rom" / "base.gba"
RENDER_EVIDENCE = REVERSE_ROOT / "artifacts" / "audio" / "full-song-render-evidence.json"
RENDERER = REMAKE_ROOT / "tools" / "audio_song_export.py"
BGM_BUILDER = REMAKE_ROOT / "tools" / "butano" / "generate_scenario_41_audio_assets.py"

OUTPUT_SAMPLE_RATE = 22050
SEMANTICS = {
    10: "battle_bgm_s49",
    146: "tool_group17_sfx",
    152: "tool_expiry_sfx",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_evidence() -> dict:
    data = json.loads(RENDER_EVIDENCE.read_text(encoding="utf-8"))
    return {row["sound_id"]: row for row in data["songs"]}


def render_cue(sound_id: int, out_wav: pathlib.Path) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(RENDERER), str(ORIGINAL_ROM),
         "--sound-id", str(sound_id), "--wav", str(out_wav), "--loops", "1"],
        cwd=str(REMAKE_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"ERR renderer failed for sound id {sound_id}:\n{result.stderr}")


def read_stereo_wav(path: pathlib.Path) -> tuple[list[int], int]:
    """16-bit stereo WAV -> (mono signed 8-bit samples, sample rate)."""
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 2 or stream.getsampwidth() != 2:
            raise ValueError("expected 16-bit stereo PCM")
        rate = stream.getframerate()
        frames = stream.getnframes()
        raw = stream.readframes(frames)
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    mono: list[int] = []
    for index in range(0, len(samples), 2):
        left = samples[index]
        right = samples[index + 1]
        value = (left + right) / 2.0 / 32768.0
        quantised = int(round(value * 127.0))
        quantised = max(-128, min(127, quantised))
        mono.append((quantised & 0xFF) ^ 0x80)
    return mono, rate


def read_stereo_u8_wav(path: pathlib.Path) -> tuple[bytes, int]:
    """Stereo unsigned 8-bit WAV -> (interleaved bytes, sample rate).

    This is the exact format the MP2K bank renderer writes, so the
    downmix/resample below reproduces the shipped scenario-41 SFX assets
    byte for byte.
    """
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 2 or stream.getsampwidth() != 1:
            raise ValueError("expected stereo unsigned 8-bit PCM")
        rate = stream.getframerate()
        frames = stream.getnframes()
        raw = stream.readframes(frames)
    return raw, rate


def downmix_stereo_u8(pcm: bytes) -> bytes:
    """Same rule as the scenario-41 SFX pipeline."""
    if len(pcm) % 2:
        raise ValueError("stereo PCM byte count is not frame aligned")
    return bytes((pcm[index] + pcm[index + 1]) // 2
                 for index in range(0, len(pcm), 2))


def resample_nearest_u8(pcm: bytes, source_rate: int, output_rate: int) -> bytes:
    """Same rule as the scenario-41 SFX pipeline."""
    if source_rate <= 0 or output_rate <= 0:
        raise ValueError("sample rates must be positive")
    output_frames = (len(pcm) * output_rate + source_rate // 2) // source_rate
    return bytes(
        pcm[min((index * source_rate + output_rate // 2) // output_rate, len(pcm) - 1)]
        for index in range(output_frames)
    )


def resample_box_u8(pcm: bytes, source_rate: int, output_rate: int) -> bytes:
    """Box-filter decimation for live captures (source_rate > output_rate).

    A live mGBA capture runs at 65536 Hz; nearest-neighbour decimation to
    22050 Hz would alias the BGM down by 3x, so every output sample is the
    mean of the source window it covers.
    """
    if source_rate <= output_rate:
        return resample_nearest_u8(pcm, source_rate, output_rate)
    output_frames = (len(pcm) * output_rate + source_rate // 2) // source_rate
    result = bytearray()
    for index in range(output_frames):
        start = (index * source_rate) // output_rate
        end = max(start + 1, ((index + 1) * source_rate) // output_rate)
        window = pcm[start:min(end, len(pcm))]
        if not window:
            window = pcm[-1:]
        result.append(sum(window) // len(window))
    return bytes(result)


def write_mono_wav(path: pathlib.Path, pcm: bytes, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(1)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm)


def build(
    sound_id: int,
    kind: str,
    work_dir: pathlib.Path,
    dry_run: bool,
    from_wav: pathlib.Path | None = None,
    from_pcm_wav: pathlib.Path | None = None,
) -> dict:
    evidence = load_evidence()[sound_id]
    original_frames = evidence["frames"]
    original_rate = 15768
    original_duration = original_frames / original_rate

    if from_pcm_wav is not None:
        # Exact MP2K bank render: downmix + nearest resample, bit identical to
        # the shipped scenario-41 SFX assets.
        stereo, rate = read_stereo_u8_wav(pathlib.Path(from_pcm_wav))
        mono_bytes = downmix_stereo_u8(stereo)
        target_frames = int(round(original_duration * rate))
        mono_bytes = mono_bytes[:target_frames]
        pcm = resample_nearest_u8(mono_bytes, rate, OUTPUT_SAMPLE_RATE)
        source_description = str(from_pcm_wav)
    else:
        render_wav = work_dir / f"sound_{sound_id:03d}-render.wav"
        if from_wav is not None:
            render_wav = pathlib.Path(from_wav)
        else:
            render_cue(sound_id, render_wav)
        mono, rate = read_stereo_wav(render_wav)
        # The offline renderer appends a tail; keep the cue's original length
        # so the asset duration matches the original MP2K cue exactly.
        target_frames = int(round(original_duration * rate))
        mono = mono[:target_frames] if target_frames < len(mono) else mono
        pcm = resample_box_u8(bytes(mono), rate, OUTPUT_SAMPLE_RATE)
        source_description = str(render_wav)
    mono_wav = work_dir / f"sound_{sound_id:03d}-mono22050.wav"
    write_mono_wav(mono_wav, pcm, OUTPUT_SAMPLE_RATE)

    result = {
        "sound_id": sound_id,
        "kind": kind,
        "semantic": SEMANTICS.get(sound_id, "reference_only"),
        "original_frames": original_frames,
        "original_sample_rate": original_rate,
        "original_duration_seconds": round(original_duration, 3),
        "original_pcm_sha256": evidence["pcm_sha256"],
        "render_sample_rate": rate,
        "render_frames": len(pcm) * rate // OUTPUT_SAMPLE_RATE,
        "source": source_description,
        "asset_sample_rate": OUTPUT_SAMPLE_RATE,
        "asset_frames": len(pcm),
        "asset_duration_seconds": round(len(pcm) / OUTPUT_SAMPLE_RATE, 3),
        "asset_pcm_sha256": sha256_bytes(pcm),
        "mono_wav": str(mono_wav),
        "mono_wav_sha256": sha256_file(mono_wav),
    }

    if dry_run:
        return result

    if kind == "sfx":
        target = REMAKE_ROOT / "butano-sequel" / "audio" / f"sound_{sound_id:03d}.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(mono_wav.read_bytes())
        result["output"] = str(target)
        result["output_sha256"] = sha256_file(target)
    elif kind == "bgm":
        target = REMAKE_ROOT / "butano-sequel" / "audio" / f"sound_{sound_id:03d}.s3m"
        manifest = work_dir / f"cue-{sound_id}-manifest.json"
        command = [
            sys.executable, str(BGM_BUILDER),
            "--input", str(mono_wav),
            "--output", str(target),
            "--manifest", str(manifest),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise SystemExit(f"ERR S3M builder failed:\n{completed.stderr}")
        result["output"] = str(target)
        result["output_sha256"] = sha256_file(target)
        result["manifest"] = str(manifest)
        result["manifest_sha256"] = sha256_file(manifest)
    else:
        raise ValueError(f"unknown kind: {kind}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sound-id", type=int, required=True)
    parser.add_argument("--kind", choices=("bgm", "sfx"), required=True)
    parser.add_argument("--work-dir", type=pathlib.Path,
                        default=REPO / "build" / "s49-audio-l" / "cues")
    parser.add_argument("--from-wav", type=pathlib.Path, default=None,
                        help="use an existing 16-bit stereo WAV instead of the "
                             "offline renderer (e.g. a live mGBA capture)")
    parser.add_argument("--from-pcm-wav", type=pathlib.Path, default=None,
                        help="use an existing stereo unsigned 8-bit WAV (the "
                             "exact MP2K bank render) instead of the renderer")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    result = build(args.sound_id, args.kind, args.work_dir, args.dry_run,
                   args.from_wav, args.from_pcm_wav)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
