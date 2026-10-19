#!/usr/bin/env python3
"""Cross-platform screenshot OCR with the repository's stable JSON schema.

Linux uses Tesseract TSV output. macOS delegates to the existing Vision/AppKit
binary so historical results and its command-line contract remain compatible.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import struct
import subprocess
import sys
from collections import OrderedDict
from io import StringIO
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VISION_BIN = ROOT / "tools" / "bin" / "ocr_screenshot"
DEFAULT_LANGUAGES = ("chi_sim", "jpn", "eng")


class OcrError(RuntimeError):
    """OCR invocation or output was invalid."""


class OcrUnavailable(OcrError):
    """The selected OCR backend or one of its language packs is unavailable."""


def _resolve_executable(command: str | Path) -> str:
    value = os.fspath(command)
    if os.sep in value or (os.altsep and os.altsep in value):
        path = Path(value)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise OcrUnavailable(f"OCR executable is missing or not executable: {path}")
    resolved = shutil.which(value)
    if not resolved:
        raise OcrUnavailable(f"OCR executable was not found on PATH: {value}")
    return resolved


def preflight_tesseract(
    executable: str | Path,
    *,
    required_languages: Sequence[str] = DEFAULT_LANGUAGES,
) -> str:
    """Return the resolved executable or fail before attempting recognition."""
    resolved = _resolve_executable(executable)
    completed = subprocess.run(
        [resolved, "--list-langs"], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise OcrUnavailable(
            f"Tesseract language preflight failed ({completed.returncode}): {detail}"
        )
    available = {
        line.strip()
        for line in (completed.stdout + "\n" + completed.stderr).splitlines()
        if line.strip() and not line.lower().startswith("list of available languages")
    }
    missing = [language for language in required_languages if language not in available]
    if missing:
        raise OcrUnavailable(
            "Tesseract is missing required language packs: " + ", ".join(missing)
        )
    return resolved


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise OcrError(f"Tesseract adapter currently requires a PNG screenshot: {path}")
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0:
        raise OcrError(f"PNG has invalid dimensions {width}x{height}: {path}")
    return width, height


def parse_tesseract_tsv(
    tsv: str,
    *,
    image: str,
    image_width: int,
    image_height: int,
) -> dict:
    """Group Tesseract words into Vision-compatible line records."""
    if image_width <= 0 or image_height <= 0:
        raise OcrError("image dimensions must be positive")
    reader = csv.DictReader(StringIO(tsv), delimiter="\t")
    required = {
        "level", "block_num", "par_num", "line_num", "left", "top",
        "width", "height", "conf", "text",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise OcrError("Tesseract TSV is missing required columns")

    grouped: OrderedDict[tuple[str, str, str], list[dict]] = OrderedDict()
    for row in reader:
        if row.get("level") != "5":
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            confidence = float(row["conf"])
            left = int(row["left"])
            top = int(row["top"])
            width = int(row["width"])
            height = int(row["height"])
        except (TypeError, ValueError, KeyError) as exc:
            raise OcrError(f"invalid Tesseract TSV word row: {exc}") from exc
        if confidence < 0 or width <= 0 or height <= 0:
            continue
        key = (row["block_num"], row["par_num"], row["line_num"])
        grouped.setdefault(key, []).append(
            {
                "text": text,
                "confidence": confidence / 100.0,
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
            }
        )

    lines = []
    for words in grouped.values():
        left = min(word["left"] for word in words)
        top = min(word["top"] for word in words)
        right = max(word["right"] for word in words)
        bottom = max(word["bottom"] for word in words)
        lines.append(
            {
                "text": " ".join(word["text"] for word in words),
                "confidence": sum(word["confidence"] for word in words) / len(words),
                # Vision uses normalized coordinates with a bottom-left origin.
                "boundingBox": [
                    left / image_width,
                    1.0 - bottom / image_height,
                    (right - left) / image_width,
                    (bottom - top) / image_height,
                ],
            }
        )
    return {"image": image, "lineCount": len(lines), "lines": lines}


def run_tesseract(
    image: Path,
    executable: str | Path = "tesseract",
    *,
    required_languages: Sequence[str] = DEFAULT_LANGUAGES,
) -> dict:
    resolved = preflight_tesseract(
        executable, required_languages=required_languages
    )
    width, height = _png_dimensions(image)
    completed = subprocess.run(
        [
            resolved,
            str(image),
            "stdout",
            "-l",
            "+".join(required_languages),
            "--psm",
            "6",
            "tsv",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise OcrError(
            f"Tesseract OCR failed ({completed.returncode}): {completed.stderr.strip()}"
        )
    return parse_tesseract_tsv(
        completed.stdout,
        image=str(image),
        image_width=width,
        image_height=height,
    )


def _validate_result(result: object) -> dict:
    if not isinstance(result, dict):
        raise OcrError("OCR backend returned a non-object JSON result")
    if not {"image", "lineCount", "lines"}.issubset(result):
        raise OcrError("OCR backend result does not match image/lineCount/lines schema")
    if not isinstance(result["lines"], list) or result["lineCount"] != len(result["lines"]):
        raise OcrError("OCR backend lineCount does not match lines")
    return result


def run_vision(image: Path, executable: Path = DEFAULT_VISION_BIN) -> dict:
    completed = subprocess.run(
        [str(executable), str(image)], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise OcrError(
            f"macOS Vision OCR failed ({completed.returncode}): {completed.stderr.strip()}"
        )
    try:
        return _validate_result(json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise OcrError(f"macOS Vision OCR returned invalid JSON: {exc}") from exc


def _backend(platform: str, requested: str) -> str:
    if requested != "auto":
        return requested
    return "vision" if platform == "darwin" else "tesseract"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--backend", choices=("auto", "tesseract", "vision"), default="auto")
    parser.add_argument("--tesseract-bin", default="tesseract")
    parser.add_argument("--vision-bin", type=Path, default=DEFAULT_VISION_BIN)
    parser.add_argument(
        "--languages",
        default="+".join(DEFAULT_LANGUAGES),
        help="Required Tesseract languages joined by '+'",
    )
    args = parser.parse_args(argv)
    languages = tuple(value for value in args.languages.split("+") if value)
    try:
        selected = _backend(sys.platform, args.backend)
        if selected == "vision":
            _resolve_executable(args.vision_bin)
            result = run_vision(args.image, args.vision_bin)
        else:
            result = run_tesseract(
                args.image,
                args.tesseract_bin,
                required_languages=languages,
            )
        result = _validate_result(result)
        encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
        return 0
    except OcrUnavailable as exc:
        print(f"OCR unavailable: {exc}", file=sys.stderr)
        return 1
    except (OcrError, OSError) as exc:
        print(f"OCR failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
