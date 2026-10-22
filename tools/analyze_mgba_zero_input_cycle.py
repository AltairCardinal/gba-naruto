#!/usr/bin/env python3
"""Select an exact RGB8 recurrence from a fixed 600-frame mGBA sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

try:
    from tools.inspect_mgba_savestate import png_screen_fingerprint
except ModuleNotFoundError:
    from inspect_mgba_savestate import png_screen_fingerprint


MAX_FRAME = 600
MAX_PERIOD = 300
GBA_SCREEN_WIDTH = 240
GBA_SCREEN_HEIGHT = 160


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


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_regular_file(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise CycleAnalysisError(f"{label} must not be a symlink: {path}")
    if not path.is_file():
        raise CycleAnalysisError(f"{label} is not a regular file: {path}")
    return path.resolve(strict=True)


def _validate_screen_fingerprint(
    fingerprint: Mapping[str, object], label: str
) -> str:
    if (
        fingerprint.get("width") != GBA_SCREEN_WIDTH
        or fingerprint.get("height") != GBA_SCREEN_HEIGHT
    ):
        raise CycleAnalysisError(f"{label} must be a 240x160 GBA screen")
    rgb_sha256 = fingerprint.get("rgb_pixels_sha256")
    if not isinstance(rgb_sha256, str):
        raise CycleAnalysisError(f"{label} has no normalized RGB8 SHA-256")
    return rgb_sha256


def _require_frame_directory(path: Path | str) -> Path:
    directory = Path(path)
    if directory.is_symlink():
        raise CycleAnalysisError(f"frame directory must not be a symlink: {directory}")
    if not directory.is_dir():
        raise CycleAnalysisError(f"frame directory does not exist: {directory}")
    return directory.resolve(strict=True)


def _frame_paths(directory: Path) -> list[Path]:
    expected_names = {f"frame-{frame:04d}.png" for frame in range(1, MAX_FRAME + 1)}
    actual_names = {
        entry.name
        for entry in directory.iterdir()
        if entry.name.startswith("frame-") and entry.suffix == ".png"
    }
    if actual_names != expected_names:
        raise CycleAnalysisError("cycle sample must contain frames 1..600 exactly once")

    paths = []
    for frame in range(1, MAX_FRAME + 1):
        path = directory / f"frame-{frame:04d}.png"
        if path.is_symlink():
            raise CycleAnalysisError(f"frame PNG must not be a symlink: {path}")
        if not path.is_file():
            raise CycleAnalysisError(f"frame PNG is not a regular file: {path}")
        paths.append(path.resolve(strict=True))
    return paths


def analyze_frame_directory(frame_dir: Path | str) -> dict[int, str]:
    directory = _require_frame_directory(frame_dir)
    paths = _frame_paths(directory)
    hashes: dict[int, str] = {}
    for frame, path in enumerate(paths, start=1):
        try:
            fingerprint = png_screen_fingerprint(path)
        except (OSError, ValueError) as error:
            raise CycleAnalysisError(f"invalid frame PNG {path}: {error}") from error
        hashes[frame] = _validate_screen_fingerprint(
            fingerprint, f"frame {frame} PNG"
        )
    return hashes


def _load_audit(path: Path) -> tuple[Path, dict[str, object], str]:
    canonical = _require_regular_file(path, "audit")
    try:
        raw_payload = canonical.read_bytes()
        payload = json.loads(raw_payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CycleAnalysisError(f"invalid audit JSON: {error}") from error
    if not isinstance(payload, dict):
        raise CycleAnalysisError("audit JSON must be an object")
    return canonical, payload, _sha256_bytes(raw_payload)


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


def _prepare_output_path(
    path: Path,
    *,
    protected_files: Sequence[Path],
    frame_directory: Path,
) -> Path:
    absolute = Path(os.path.abspath(os.path.expanduser(str(path))))
    if absolute.is_symlink():
        raise CycleAnalysisError(f"output must not be a symlink: {absolute}")
    try:
        absolute.lstat()
    except FileNotFoundError:
        pass
    else:
        raise CycleAnalysisError(f"output must be fresh and not already exist: {absolute}")

    parent = absolute.parent
    if parent.is_symlink() or not parent.is_dir():
        raise CycleAnalysisError(f"output parent must be an existing real directory: {parent}")
    canonical = absolute.resolve(strict=False)
    if canonical in {protected.resolve(strict=True) for protected in protected_files}:
        raise CycleAnalysisError(f"output overlaps an input evidence file: {canonical}")
    if canonical == frame_directory or frame_directory in canonical.parents:
        raise CycleAnalysisError(f"output must be outside the frame directory: {canonical}")
    return canonical


def _snapshot_files(paths: Sequence[Path], label: str) -> dict[Path, str]:
    snapshot: dict[Path, str] = {}
    for path in paths:
        canonical = _require_regular_file(path, label)
        snapshot[canonical] = _sha256_file(canonical)
    return snapshot


def _require_snapshot_unchanged(
    expected: Mapping[Path, str], label: str
) -> None:
    actual = _snapshot_files(list(expected), label)
    if actual != dict(expected):
        raise CycleAnalysisError(f"{label} changed during analysis")


def _publish_no_clobber(temporary: Path, output: Path) -> None:
    try:
        os.link(temporary, output)
    except FileExistsError as error:
        raise CycleAnalysisError(
            f"output ceased to be fresh before publish: {output}"
        ) from error


def _atomic_write_text(path: Path, payload: str) -> None:
    if path.is_symlink() or path.exists():
        raise CycleAnalysisError(f"output ceased to be fresh before publish: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _publish_no_clobber(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    audit_input = _require_regular_file(args.audit, "audit")
    frame_directory = _require_frame_directory(args.frame_dir)
    frame_paths = _frame_paths(frame_directory)
    output = _prepare_output_path(
        args.output,
        protected_files=(baseline, sampler, audit_input),
        frame_directory=frame_directory,
    )
    baseline_file_sha256 = _require_expected_hash(
        baseline, args.expected_baseline_png_sha256, "baseline PNG"
    )
    sampler_sha256 = _require_expected_hash(
        sampler, args.expected_sampler_sha256, "sampler"
    )
    audit_path, audit, audit_sha256 = _load_audit(audit_input)
    _validate_diagnostic_audit(audit, sampler, sampler_sha256)
    critical_snapshot = _snapshot_files(
        [baseline, sampler, audit_path, *frame_paths], "critical input"
    )

    try:
        baseline_fingerprint = png_screen_fingerprint(baseline)
    except (OSError, ValueError) as error:
        raise CycleAnalysisError(f"invalid baseline PNG {baseline}: {error}") from error
    baseline_rgb_sha256 = _validate_screen_fingerprint(
        baseline_fingerprint, "baseline PNG"
    )
    frame_hashes = analyze_frame_directory(args.frame_dir)
    period = select_exact_period(baseline_rgb_sha256, frame_hashes)

    _require_expected_hash(
        baseline, args.expected_baseline_png_sha256, "baseline PNG"
    )
    _require_expected_hash(sampler, args.expected_sampler_sha256, "sampler")
    if _sha256_file(audit_path) != audit_sha256:
        raise CycleAnalysisError("audit changed during analysis")
    _require_snapshot_unchanged(critical_snapshot, "critical input")

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
        "frame_directory": str(frame_directory),
        "frame_rgb_sha256": frame_hashes,
        "sampler": {"path": str(sampler), "sha256": sampler_sha256},
        "audit": {"path": str(audit_path), "sha256": audit_sha256},
    }
    _atomic_write_text(
        output, json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CycleAnalysisError as error:
        raise SystemExit(f"error: {error}") from error
