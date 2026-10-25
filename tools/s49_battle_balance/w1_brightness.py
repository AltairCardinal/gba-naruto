#!/usr/bin/env python3
"""W1: classify captured frames by brightness (black field detection)."""
import pathlib
import sys
from PIL import Image


def main(argv):
    root = pathlib.Path(argv[1])
    for path in sorted(root.glob("*.png")):
        with Image.open(path) as image:
            gray = image.convert("L")
            values = list(gray.getdata())
        mean = sum(values) / len(values)
        dark = sum(1 for value in values if value < 16)
        print(f"{path.name} mean={mean:6.1f} dark={dark:5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
