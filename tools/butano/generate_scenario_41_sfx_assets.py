#!/usr/bin/env python3
"""Generate mono Maxmod WAV assets for runtime-verified scenario 41 cues."""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path


SCENARIO_41_SOUND_IDS = (51, 52, 102, 103, 104, 105, 112, 116, 117, 126, 138, 149, 157, 158)
OUTPUT_SAMPLE_RATE = 22050
SEMANTICS = {
    2: "postbattle_map_bgm",
    5: "prebattle_bgm",
    8: "postbattle_dialogue_bgm",
    14: "battle_bgm",
    15: "combo_animation_bgm",
    51: "victory_jingle",
    52: "level_up_jingle",
    102: "ui_confirm_accept",
    103: "ui_cancel_back",
    104: "ui_cursor_move",
    105: "ui_rejected_invalid_action",
    112: "result_or_level_up_effect",
    116: "combo_attack_motion",
    117: "technique_target_or_submit",
    126: "battle_selection_or_transition",
    138: "combo_impact_or_dialogue_transition",
    149: "combat_popup_or_victory_transition",
    157: "result_transition",
    158: "victory_transition",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _downmix_stereo_u8(pcm: bytes) -> bytes:
    if len(pcm) % 2:
        raise ValueError("stereo PCM byte count is not frame aligned")
    return bytes((pcm[index] + pcm[index + 1]) // 2 for index in range(0, len(pcm), 2))


def _resample_nearest_u8(pcm: bytes, source_rate: int, output_rate: int) -> bytes:
    if source_rate <= 0 or output_rate <= 0:
        raise ValueError("sample rates must be positive")
    output_frames = (len(pcm) * output_rate + source_rate // 2) // source_rate
    return bytes(
        pcm[min((index * source_rate + output_rate // 2) // output_rate, len(pcm) - 1)]
        for index in range(output_frames)
    )


def generate_sfx_assets(
    source_dir: Path, output_dir: Path, sound_ids: tuple[int, ...] = SCENARIO_41_SOUND_IDS
) -> dict[str, object]:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for sound_id in sound_ids:
        source = source_dir / f"sound_{sound_id:03d}.wav"
        with wave.open(str(source), "rb") as stream:
            if (
                stream.getnchannels() != 2
                or stream.getsampwidth() != 1
                or stream.getcomptype() != "NONE"
            ):
                raise ValueError(f"{source} must be stereo unsigned 8-bit PCM")
            sample_rate = stream.getframerate()
            frame_count = stream.getnframes()
            source_pcm = stream.readframes(frame_count)
        mono_pcm = _resample_nearest_u8(
            _downmix_stereo_u8(source_pcm), sample_rate, OUTPUT_SAMPLE_RATE
        )
        destination = output_dir / source.name
        with wave.open(str(destination), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(1)
            stream.setframerate(OUTPUT_SAMPLE_RATE)
            stream.writeframes(mono_pcm)
        entries.append(
            {
                "sound_id": sound_id,
                "semantic": SEMANTICS[sound_id],
                "source_sample_rate": sample_rate,
                "sample_rate": OUTPUT_SAMPLE_RATE,
                "source_frame_count": frame_count,
                "frame_count": len(mono_pcm),
                "duration_seconds": frame_count / sample_rate,
                "source_pcm_sha256": _sha256(source_pcm),
                "mono_pcm_sha256": _sha256(mono_pcm),
                "wav_sha256": _sha256(destination.read_bytes()),
                "source": str(source),
                "output": str(destination),
            }
        )
    return {
        "format_version": 1,
        "sound_ids": list(sound_ids),
        "conversion": "stereo unsigned 8-bit PCM arithmetic mean to mono; nearest-neighbor resample to 22050 Hz",
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=Path("build/audio-v2/pcm"))
    parser.add_argument("--output-dir", type=Path, default=Path("butano-sequel/audio"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/scenario-41-audio-reference-v1/sfx-manifest.json"),
    )
    args = parser.parse_args()
    manifest = generate_sfx_assets(args.source_dir, args.output_dir)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
