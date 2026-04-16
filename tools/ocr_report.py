#!/usr/bin/env python3
"""Run local OCR over screenshot sets and emit a compact Markdown timeline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def frame_num(path: Path) -> int:
    match = re.search(r"-(\d+)\.png$", path.name)
    return int(match.group(1)) if match else -1


def run_ocr(ocr_bin: Path, image: Path) -> dict:
    proc = subprocess.run(
        [str(ocr_bin), str(image)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def summarize_line(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 48 else text[:45] + "..."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("glob", help="Glob of screenshots to OCR, e.g. 'notes/newgame-*.png'")
    parser.add_argument("--ocr-bin", default="tools/bin/ocr_screenshot")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    ocr_bin = Path(args.ocr_bin)
    if not ocr_bin.is_file():
        raise SystemExit(f"OCR binary not found: {ocr_bin}")
    images = sorted(Path().glob(args.glob), key=frame_num)
    report_lines = [
        f"# OCR Timeline: `{args.glob}`",
        "",
        f"- Image count: `{len(images)}`",
        f"- OCR binary: `{ocr_bin}`",
        "",
    ]

    for image in images:
        result = run_ocr(ocr_bin, image)
        snippets = [summarize_line(line["text"]) for line in result["lines"][:3]]
        if snippets:
            report_lines.append(f"- `{image.name}`: " + " | ".join(snippets))
        else:
            report_lines.append(f"- `{image.name}`: `(no OCR text)`")

    output = Path(args.output)
    output.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
