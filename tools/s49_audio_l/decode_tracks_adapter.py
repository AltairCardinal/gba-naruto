#!/usr/bin/env python3
"""Adapt the current extract_audio.py manifest to decode_m4a_tracks.py.

Stream L (S49 audio wiring).  ``tools/extract_audio.py`` now writes the track
offsets as strings ("0x535CFC") while ``tools/decode_m4a_tracks.py`` still
expects integers, so the stock decoder aborts with

    ValueError: Unknown format code 'X' for object of type 'str'

This adapter reuses the stock ``decode_track()`` (read only) and only fixes the
offset type, so the produced ``tracks-decoded.json`` is the format the stock
``tools/render_m4a_pcm_bank.py`` expects.

Usage:
    python tools/s49_audio_l/decode_tracks_adapter.py \
        --input-dir <remake>/build/audio-v2 \
        --output <remake>/build/audio-v2/tracks-decoded.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
sys.path.insert(0, str(REMAKE_ROOT / "tools"))

import decode_m4a_tracks  # noqa: E402  (read-only reuse of the remake tree)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", type=pathlib.Path,
                        default=REMAKE_ROOT / "build" / "audio-v2")
    parser.add_argument("--output", type=pathlib.Path,
                        default=REMAKE_ROOT / "build" / "audio-v2" / "tracks-decoded.json")
    args = parser.parse_args()

    manifest = json.loads(
        (args.input_dir / "manifest.json").read_text(encoding="utf-8"))
    decoded = []
    for track in manifest["tracks"]:
        offset = int(track["offset"], 16) if isinstance(track["offset"], str) \
            else int(track["offset"])
        raw = (args.input_dir / "tracks" / f"track_{offset:06X}.bin").read_bytes()
        commands = decode_m4a_tracks.decode_track(raw, offset)
        decoded.append({
            "offset": offset,
            "size": len(raw),
            "command_count": len(commands),
            "commands": commands,
        })
    result = {
        "format": "MP2K/m4a structural track command decode",
        "track_count": len(decoded),
        "command_count": sum(item["command_count"] for item in decoded),
        "tracks": decoded,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.output} ({result['track_count']} tracks, "
          f"{result['command_count']} commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
