#!/usr/bin/env python3
"""Review a captured frame sequence with Antigravity's gemini-3.8-flash-high.

The reviewer is a read-only sidecar: this module only encodes already-recorded
frames, asks one question, and stores the raw answer with the hashes needed to
reproduce it. It never launches an emulator and never edits captured evidence.

Usage:
    python3 -m tools.butano.ask_antigravity_gemini FRAMES_DIR QUESTION \
        --work-dir RUN_DIR [--context TEXT] [--fps 60] [--scale 2]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image, ImageDraw

DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_AGY = Path.home() / ".local" / "bin" / "agy"
DEFAULT_FPS = 60
DEFAULT_SCALE = 2
# The reviewer must run ffprobe/ffmpeg, which headless mode cannot prompt for.
# The sandbox keeps that command surface confined while auto-approval avoids an
# interactive permission prompt; the reviewer stays a read-only sidecar.
DEFAULT_AGY_ARGS = ("--sandbox", "--dangerously-skip-permissions")
FRAME_NAME = "frame-{:03d}.png"
FRAME_PATTERN = "frame-%03d.png"


class ReviewError(RuntimeError):
    """The capture, the encoding, or the reviewer response was not trustworthy."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_frames(frames_dir: Path) -> list[Path]:
    """Return the contiguous frame-NNN.png run, rejecting gaps and stray images."""
    if not frames_dir.is_dir():
        raise ReviewError(f"frame directory does not exist: {frames_dir}")
    entries = sorted(path for path in frames_dir.iterdir() if path.is_file())
    stray = [path.name for path in entries if path.suffix.lower() == ".png"
             and not path.name.startswith("frame-")]
    if stray:
        raise ReviewError(
            f"non-frame images are not part of the reviewed run: {sorted(stray)}")
    if not entries:
        raise ReviewError(f"no frames recorded in {frames_dir}")
    frames = [frames_dir / FRAME_NAME.format(index) for index in range(len(entries))]
    for index, path in enumerate(frames):
        if not path.is_file():
            raise ReviewError(
                f"frame run is not contiguous: frame-{index:03d}.png is missing")
    return frames


def stage_frames(frames: Sequence[Path], staging_dir: Path, scale: int) -> list[Path]:
    """Upscale and index-stamp copies so the reviewer can cite exact frame numbers."""
    if staging_dir.exists():
        raise ReviewError(f"staging directory already exists: {staging_dir}")
    if scale < 1:
        raise ReviewError("scale must be at least 1")
    staging_dir.mkdir(parents=True)
    staged: list[Path] = []
    for index, source in enumerate(frames):
        with Image.open(source) as image:
            frame = image.convert("RGB")
            if scale != 1:
                frame = frame.resize(
                    (frame.width * scale, frame.height * scale), Image.NEAREST)
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 0, 7 * len(str(index)) + 4, 12), fill=(0, 0, 0))
            draw.text((2, 1), str(index), fill=(255, 255, 255))
            target = staging_dir / FRAME_NAME.format(index)
            frame.save(target)
            staged.append(target)
    return staged


def encode_video(staged: Sequence[Path], video: Path, fps: int) -> Path:
    """Encode with passthrough timing so no frame is dropped or duplicated."""
    if shutil.which("ffmpeg") is None:
        raise ReviewError("ffmpeg is unavailable; cannot encode the capture")
    if not staged:
        raise ReviewError("cannot encode an empty frame run")
    if video.exists():
        raise ReviewError(f"video already exists: {video}")
    video.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-framerate", str(fps),
        "-start_number", "0",
        "-i", str(staging_dir_pattern(staged)),
        "-fps_mode", "passthrough",
        "-c:v", "libx264", "-preset", "veryslow", "-crf", "12",
        "-pix_fmt", "yuv420p",
        str(video),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise ReviewError(f"ffmpeg failed: {completed.stderr.strip()}")
    if not video.is_file() or video.stat().st_size == 0:
        raise ReviewError(f"ffmpeg produced no video at {video}")
    return video


def staging_dir_pattern(staged: Sequence[Path]) -> str:
    return str(Path(staged[0]).parent / FRAME_PATTERN)


def build_prompt(
    question: str,
    frame_count: int,
    fps: int,
    scale: int,
    context: str | None,
) -> str:
    """Describe the capture exactly enough that frame citations stay checkable."""
    lines = [
        "You are reviewing a screen recording of a Game Boy Advance battle.",
        f"The attached capture file is capture.mp4: {frame_count} frames at {fps} fps,",
        f"each frame upscaled {scale}x from 240x160 with its frame number stamped",
        "in the top-left corner as plain text.",
        f"Frame numbers are 0-based; the last frame is frame {frame_count - 1}.",
        f"Time of frame n is n/{fps} seconds.",
        "",
        "Rules:",
        "- Use ffprobe and ffmpeg on capture.mp4; quote exact frame numbers.",
        "- Do not guess from a single frame when the answer depends on motion.",
        "- State plainly when the capture does not show something.",
    ]
    if context:
        lines.extend(["", f"Context: {context}"])
    lines.extend(["", f"Question: {question}"])
    return "\n".join(lines)


def invoke_agy(
    prompt: str,
    work_dir: Path,
    model: str,
    agy: Path,
    timeout_s: float,
    extra_args: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Run one non-interactive Antigravity turn and fail closed on a thin answer."""
    if not agy.is_file():
        raise ReviewError(f"antigravity CLI is unavailable: {agy}")
    command = [
        str(agy), "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--add-dir", str(work_dir),
        "--disable-slash-commands",
        *extra_args,
    ]
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False,
        timeout=timeout_s, env={**(env or {})} if env else None,
    )
    if completed.returncode:
        raise ReviewError(
            f"antigravity exited {completed.returncode}: {completed.stderr.strip()[:400]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ReviewError(f"antigravity output was not JSON: {error}") from error
    if payload.get("denied_actions"):
        denied = ", ".join(
            str(item.get("action")) for item in payload["denied_actions"])
        raise ReviewError(
            f"antigravity had tool actions denied, so the analysis is incomplete: {denied}")
    if payload.get("status") != "SUCCESS":
        raise ReviewError(f"antigravity status was {payload.get('status')!r}")
    response = payload.get("response")
    if not isinstance(response, str) or not response.strip():
        raise ReviewError("antigravity returned an empty response")
    return payload


def review(
    frames_dir: Path,
    question: str,
    work_dir: Path,
    context: str | None = None,
    fps: int = DEFAULT_FPS,
    scale: int = DEFAULT_SCALE,
    model: str = DEFAULT_MODEL,
    agy: Path = DEFAULT_AGY,
    timeout_s: float = 900.0,
    extra_args: Sequence[str] = DEFAULT_AGY_ARGS,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Encode, ask once, and write a receipt that pins every input to a hash."""
    frames = list_frames(Path(frames_dir))
    work_dir = Path(work_dir)
    if work_dir.exists():
        raise ReviewError(f"work directory already exists: {work_dir}")
    work_dir.mkdir(parents=True)

    staged = stage_frames(frames, work_dir / "staged", scale=scale)
    video = encode_video(staged, work_dir / "capture.mp4", fps=fps)
    prompt = build_prompt(question, len(frames), fps, scale, context)
    prompt_path = work_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    payload = invoke_agy(
        prompt, work_dir, model, Path(agy), timeout_s, extra_args, env)

    response = str(payload["response"])
    response_path = work_dir / "response.md"
    response_path.write_text(response, encoding="utf-8")
    receipt = {
        "status": "ok",
        "model": model,
        "agy": str(agy),
        "question": question,
        "context": context,
        "fps": fps,
        "scale": scale,
        "frames": len(frames),
        "frames_dir": str(frames_dir),
        "video": str(video),
        "video_sha256": sha256_file(video),
        "prompt": str(prompt_path),
        "prompt_sha256": sha256_file(prompt_path),
        "response": response,
        "response_path": str(response_path),
        "conversation_id": payload.get("conversation_id"),
        "usage": payload.get("usage"),
        "duration_seconds": payload.get("duration_seconds"),
        "receipt_path": str(work_dir / "receipt.json"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (work_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("question")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--context")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--agy", type=Path, default=DEFAULT_AGY)
    parser.add_argument("--timeout-s", type=float, default=900.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = review(
            frames_dir=args.frames_dir,
            question=args.question,
            work_dir=args.work_dir,
            context=args.context,
            fps=args.fps,
            scale=args.scale,
            model=args.model,
            agy=args.agy,
            timeout_s=args.timeout_s,
            extra_args=DEFAULT_AGY_ARGS,
        )
    except ReviewError as error:
        print(f"ask_antigravity_gemini: {error}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("ask_antigravity_gemini: antigravity timed out", file=sys.stderr)
        return 3
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
