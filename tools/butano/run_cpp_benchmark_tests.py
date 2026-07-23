#!/usr/bin/env python3
"""Compile and run the isolated C++ Butano benchmark tests."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "butano-sequel" / "benchmark"


def selected_tests(root: Path, names: list[str]) -> list[Path]:
    tests = sorted((root / "tests").glob("test_*.cpp"))
    if names:
        requested = set(names)
        tests = [path for path in tests if path.stem in requested]
    return tests


def run_tests(root: Path, names: list[str]) -> int:
    tests = selected_tests(root, names)
    if not tests:
        print("no C++ benchmark tests selected", file=sys.stderr)
        return 2
    compiler = shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        print("no host C++ compiler found", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="butano-cpp-benchmark-") as temp_dir:
        for test_path in tests:
            executable = Path(temp_dir) / test_path.stem
            compile_result = subprocess.run(
                [
                    compiler,
                    "-std=c++23",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-pedantic",
                    "-I",
                    str(root / "include"),
                    "-I",
                    str(REPO_ROOT / "butano-sequel" / "game" / "include"),
                    str(test_path),
                    "-o",
                    str(executable),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if compile_result.returncode:
                sys.stderr.write(compile_result.stdout)
                sys.stderr.write(compile_result.stderr)
                return compile_result.returncode
            run_result = subprocess.run(
                [str(executable)], text=True, capture_output=True, check=False
            )
            if run_result.returncode:
                sys.stderr.write(run_result.stdout)
                sys.stderr.write(run_result.stderr)
                return run_result.returncode
            print(f"PASS {test_path.stem}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    return run_tests(args.root, args.names)


if __name__ == "__main__":
    raise SystemExit(main())
