#!/usr/bin/env python3
"""Publish the hash-bound scenario 41 combo animation frame timeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.inspect_mgba_savestate import png_screen_fingerprint


FIRST_FRAME = 6
LAST_FRAME = 269
EXPECTED_TIMELINE_SHA256 = (
    "f10ddd3cf9a6088bc574cf41c069c4c7e701a1d1dd2c49aa4ce98c3dd560e931"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_attack_animation(source: Path, output: Path) -> dict[str, object]:
    source = Path(source)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")

    rows: list[tuple[Path, str, str]] = []
    for frame in range(FIRST_FRAME, LAST_FRAME + 1):
        path = source / f"frame-{frame:04d}.png"
        screen = png_screen_fingerprint(path)
        if (screen["width"], screen["height"]) != (240, 160):
            raise ValueError(f"unexpected frame dimensions: {path}")
        rows.append((path, str(screen["rgb_pixels_sha256"]), _sha256(path)))

    timeline_hash = hashlib.sha256(
        "".join(rgb_hash for _, rgb_hash, _ in rows).encode("ascii")
    ).hexdigest()
    if timeline_hash != EXPECTED_TIMELINE_SHA256:
        raise ValueError(f"animation timeline SHA-256 mismatch: {timeline_hash}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    published = False
    try:
        frames_dir = temporary / "frames"
        frames_dir.mkdir()
        timeline = []
        unique: dict[str, dict[str, str]] = {}
        for source_path, rgb_hash, file_hash in rows:
            filename = f"{rgb_hash}.png"
            timeline.append(filename)
            if rgb_hash not in unique:
                shutil.copyfile(source_path, frames_dir / filename)
                unique[rgb_hash] = {
                    "file": filename,
                    "png_sha256": file_hash,
                    "rgb_sha256": rgb_hash,
                }
        manifest: dict[str, object] = {
            "schema_version": 1,
            "source_first_frame": FIRST_FRAME,
            "source_last_frame": LAST_FRAME,
            "timeline_frames": len(timeline),
            "unique_frames": len(unique),
            "timeline_sha256": timeline_hash,
            "timeline": timeline,
            "frames": unique,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(output)
        published = True
        return manifest
    finally:
        if not published and temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_attack_animation(args.source, args.output)
    print(json.dumps({
        "timeline_frames": manifest["timeline_frames"],
        "unique_frames": manifest["unique_frames"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
