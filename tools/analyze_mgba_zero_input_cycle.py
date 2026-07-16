#!/usr/bin/env python3
"""Select an exact RGB8 recurrence from a fixed 600-frame mGBA sample."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

try:
    from tools.inspect_mgba_savestate import png_screen_fingerprint
except ModuleNotFoundError:
    from inspect_mgba_savestate import png_screen_fingerprint


MAX_FRAME = 600
MAX_PERIOD = 300


class CycleAnalysisError(ValueError):
    pass


def select_exact_period(
    baseline_rgb_sha256: str, frame_hashes: Mapping[int, str]
) -> int | None:
    if set(frame_hashes) != set(range(1, MAX_FRAME + 1)):
        raise CycleAnalysisError("cycle sample must contain frames 1..600 exactly once")
    for period in range(1, MAX_PERIOD + 1):
        if (
            frame_hashes[period] == baseline_rgb_sha256
            and frame_hashes[period * 2] == baseline_rgb_sha256
        ):
            return period
    return None


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_regular_file(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise CycleAnalysisError(f"{label} must not be a symlink: {path}")
    if not path.is_file():
        raise CycleAnalysisError(f"{label} is not a regular file: {path}")
    return path.resolve(strict=True)


def _validate_screen_fingerprint(
    fingerprint: Mapping[str, object], label: str
) -> str:
    rgb_sha256 = fingerprint.get("rgb_pixels_sha256")
    if not isinstance(rgb_sha256, str):
        raise CycleAnalysisError(f"{label} has no normalized RGB8 SHA-256")
    return rgb_sha256


def analyze_frame_directory(frame_dir: Path | str) -> dict[int, str]:
    directory = Path(frame_dir)
    if directory.is_symlink():
        raise CycleAnalysisError(f"frame directory must not be a symlink: {directory}")
    if not directory.is_dir():
        raise CycleAnalysisError(f"frame directory does not exist: {directory}")

    expected_names = {f"frame-{frame:04d}.png" for frame in range(1, MAX_FRAME + 1)}
    actual_names = {
        entry.name
        for entry in directory.iterdir()
        if entry.name.startswith("frame-") and entry.suffix == ".png"
    }
    if actual_names != expected_names:
        raise CycleAnalysisError("cycle sample must contain frames 1..600 exactly once")

    hashes: dict[int, str] = {}
    for frame in range(1, MAX_FRAME + 1):
        path = directory / f"frame-{frame:04d}.png"
        if path.is_symlink():
            raise CycleAnalysisError(f"frame PNG must not be a symlink: {path}")
        if not path.is_file():
            raise CycleAnalysisError(f"frame PNG is not a regular file: {path}")
        try:
            fingerprint = png_screen_fingerprint(path)
        except (OSError, ValueError) as error:
            raise CycleAnalysisError(f"invalid frame PNG {path}: {error}") from error
        hashes[frame] = _validate_screen_fingerprint(
            fingerprint, f"frame {frame} PNG"
        )
    return hashes


def _load_audit(path: Path) -> tuple[Path, dict[str, object]]:
    canonical = _require_regular_file(path, "audit")
    try:
        payload = json.loads(canonical.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CycleAnalysisError(f"invalid audit JSON: {error}") from error
    if not isinstance(payload, dict):
        raise CycleAnalysisError("audit JSON must be an object")
    return canonical, payload


def _require_expected_hash(path: Path, expected: str, label: str) -> str:
    actual = _sha256_file(path)
    if actual != expected:
        raise CycleAnalysisError(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def _validate_diagnostic_audit(
    audit: Mapping[str, object], sampler: Path, sampler_sha256: str
) -> None:
    expected_pre_scripts = [
        {"path": str(sampler), "sha256": sampler_sha256}
    ]
    requirements = (
        (audit.get("evidence_mode") == "script-order-diagnostic", "evidence_mode"),
        (audit.get("zero_input_verified") is False, "zero_input_verified"),
        (audit.get("inputs") == [], "inputs"),
        (audit.get("capture_frame") == MAX_FRAME, "capture_frame"),
        (audit.get("pre_scripts") == expected_pre_scripts, "pre_scripts"),
    )
    for valid, field in requirements:
        if not valid:
            raise CycleAnalysisError(f"diagnostic audit has invalid {field}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-png", type=Path, required=True)
    parser.add_argument("--expected-baseline-png-sha256", required=True)
    parser.add_argument("--frame-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--sampler", type=Path, required=True)
    parser.add_argument("--expected-sampler-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    baseline = _require_regular_file(args.baseline_png, "baseline PNG")
    sampler = _require_regular_file(args.sampler, "sampler")
    baseline_file_sha256 = _require_expected_hash(
        baseline, args.expected_baseline_png_sha256, "baseline PNG"
    )
    sampler_sha256 = _require_expected_hash(
        sampler, args.expected_sampler_sha256, "sampler"
    )
    audit_path, audit = _load_audit(args.audit)
    _validate_diagnostic_audit(audit, sampler, sampler_sha256)
    audit_sha256 = _sha256_file(audit_path)

    try:
        baseline_fingerprint = png_screen_fingerprint(baseline)
    except (OSError, ValueError) as error:
        raise CycleAnalysisError(f"invalid baseline PNG {baseline}: {error}") from error
    baseline_rgb_sha256 = _validate_screen_fingerprint(
        baseline_fingerprint, "baseline PNG"
    )
    frame_hashes = analyze_frame_directory(args.frame_dir)
    period = select_exact_period(baseline_rgb_sha256, frame_hashes)

    report = {
        "schema_version": 1,
        "status": "cycle-found" if period is not None else "not-proven",
        "period": period,
        "match_frames": [0, period, period * 2] if period is not None else [],
        "baseline": {
            "path": str(baseline),
            "file_sha256": baseline_file_sha256,
            "rgb_sha256": baseline_rgb_sha256,
        },
        "frame_directory": str(Path(args.frame_dir).resolve(strict=True)),
        "frame_rgb_sha256": frame_hashes,
        "sampler": {"path": str(sampler), "sha256": sampler_sha256},
        "audit": {"path": str(audit_path), "sha256": audit_sha256},
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CycleAnalysisError as error:
        raise SystemExit(f"error: {error}") from error
