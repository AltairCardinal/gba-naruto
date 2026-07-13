#!/usr/bin/env python3
"""Render every active ROM sound ID through the persistent MP2K song engine."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.m4a_pcm import interleave_wav_u8, write_stereo_wave
    from tools.m4a_scheduler import PCM_RATE
    from tools.m4a_song_engine import M4ASongEngine
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from m4a_pcm import interleave_wav_u8, write_stereo_wave
    from m4a_scheduler import PCM_RATE
    from m4a_song_engine import M4ASongEngine


def _looping_tracks(entry: dict, decoded_tracks: dict[int, dict]) -> list[int]:
    looping = []
    for track_ptr in entry["track_ptrs"]:
        offset = track_ptr - 0x08000000
        track = decoded_tracks[offset]
        if any(command["name"] == "GOTO" for command in track["commands"]):
            looping.append(track_ptr)
    return looping


def render_bank(
    rom: bytes,
    bank: dict,
    decoded: dict,
    output_dir: Path,
    *,
    loop_invocations: int,
    max_one_shot_invocations: int,
) -> dict:
    if loop_invocations <= 0 or max_one_shot_invocations <= 0:
        raise ValueError("render invocation bounds must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    decoded_tracks = {track["offset"]: track for track in decoded["tracks"]}
    songs = []
    for entry in bank["entries"]:
        sound_id = entry["sound_id"]
        looping_tracks = _looping_tracks(entry, decoded_tracks)
        engine = M4ASongEngine.from_bank(
            rom, bank, decoded, sound_id=sound_id
        )
        if looping_tracks:
            _, loop_boundary_reached = engine.render_until_loop_boundary(
                set(looping_tracks), max_invocations=loop_invocations
            )
            policy = "all_track_gotos_with_cap"
        else:
            engine.render_until_finished(
                max_invocations=max_one_shot_invocations
            )
            policy = "natural_finish_with_cap"
            loop_boundary_reached = None

        wav_name = f"sound_{sound_id:03d}.wav"
        write_stereo_wave(
            output_dir / wav_name,
            engine.right,
            engine.left,
            sample_rate=PCM_RATE,
        )
        pcm = interleave_wav_u8(engine.right, engine.left)
        allocations = [
            result
            for runner in engine.runners
            for result in runner.allocations
        ]
        goto_tie_snapshots = [
            snapshot
            for runner in engine.runners
            for snapshot in runner.goto_tie_snapshots
        ]
        songs.append({
            "sound_id": sound_id,
            "player_index": entry["player_index"],
            "track_count": entry["track_count"],
            "looping_tracks": [f"0x{ptr:08X}" for ptr in looping_tracks],
            "loop_boundary_reached": loop_boundary_reached,
            "policy": policy,
            "render_invocations": engine.invocations,
            "frames": len(engine.right),
            "duration_seconds": len(engine.right) / PCM_RATE,
            "finished": engine.finished,
            "direct_allocations": sum(a.kind == "direct" for a in allocations),
            "cgb_allocations": sum(a.kind == "cgb" for a in allocations),
            "allocator_rejections": sum(r.dropped_notes for r in engine.runners),
            "gate_releases": sum(len(r.gate_releases) for r in engine.runners),
            "matched_eot": sum(len(r.eot_releases) for r in engine.runners),
            "fine_unlinked_channels": sum(
                len(r.stop_releases) for r in engine.runners
            ),
            "goto_commands": sum(
                runner.vm.command_counts["GOTO"] for runner in engine.runners
            ),
            "first_goto_active_ties": sum(
                len(runner.goto_tie_snapshots[0])
                for runner in engine.runners
                if runner.goto_tie_snapshots
            ),
            "goto_active_tie_observations": sum(
                len(snapshot) for snapshot in goto_tie_snapshots
            ),
            "pcm_nonzero_frames": sum(
                right != 0 or left != 0
                for right, left in zip(engine.right, engine.left)
            ),
            "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            "wav": wav_name,
        })

    totals = {
        key: sum(row[key] for row in songs)
        for key in (
            "frames",
            "pcm_nonzero_frames",
            "direct_allocations",
            "cgb_allocations",
            "allocator_rejections",
            "gate_releases",
            "matched_eot",
            "fine_unlinked_channels",
            "goto_commands",
            "first_goto_active_ties",
            "goto_active_tie_observations",
        )
    }
    manifest = {
        "format": "gba-naruto-mp2k-bounded-pcm-v1",
        "sample_rate": PCM_RATE,
        "sample_format": "stereo unsigned 8-bit RIFF from signed hardware planes",
        "loop_invocations": loop_invocations,
        "max_one_shot_invocations": max_one_shot_invocations,
        "song_count": len(songs),
        "looping_song_count": sum(bool(row["looping_tracks"]) for row in songs),
        "naturally_finished_song_count": sum(row["finished"] for row in songs),
        "loop_boundary_song_count": sum(
            row["loop_boundary_reached"] is True for row in songs
        ),
        "silent_song_count": sum(row["pcm_nonzero_frames"] == 0 for row in songs),
        "totals": totals,
        "songs": songs,
        "boundary": (
            "Looping songs stop after every GOTO-bearing track crosses its first GOTO "
            "or the explicit cap; one-shots stop after FINE "
            "and channel tails or at the explicit cap. Emulator FIFO/PSG differential "
            "and player-slot concurrency remain separate runtime gates."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--bank", type=Path, default=Path("sequel/content/audio/bank.json"))
    parser.add_argument("--decoded", type=Path, default=Path("build/audio-v2/tracks-decoded.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/audio-v2/pcm"))
    parser.add_argument("--loop-invocations", type=int, default=598)
    parser.add_argument("--max-one-shot-invocations", type=int, default=3600)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    manifest = render_bank(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text()),
        json.loads(args.decoded.read_text()),
        args.output_dir,
        loop_invocations=args.loop_invocations,
        max_one_shot_invocations=args.max_one_shot_invocations,
    )
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "song_count": manifest["song_count"],
        "output_dir": str(args.output_dir),
        "finished_one_shots": sum(
            row["finished"] for row in manifest["songs"]
            if not row["looping_tracks"]
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
