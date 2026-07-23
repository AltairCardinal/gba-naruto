#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


EXPECTED_BUTANO_COMMIT = "112a1827c9c6d9e6041a7e93e66f04c4561a6415"


def _git_head(path: Path) -> str | None:
    if not path.is_dir():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def collect_setup_errors(root: Path) -> list[str]:
    errors: list[str] = []
    gitmodules = root / ".gitmodules"
    gitmodules_text = gitmodules.read_text(encoding="utf-8") if gitmodules.is_file() else ""
    if "third_party/butano" not in gitmodules_text:
        errors.append("missing .gitmodules entry for third_party/butano")

    butano = root / "third_party" / "butano"
    if not butano.is_dir():
        errors.append("missing Butano checkout: third_party/butano")
    else:
        actual_commit = _git_head(butano)
        if actual_commit != EXPECTED_BUTANO_COMMIT:
            errors.append(
                f"Butano commit mismatch: expected {EXPECTED_BUTANO_COMMIT}, "
                f"got {actual_commit or 'unreadable'}"
            )

    if not (butano / "docs" / "index.html").is_file():
        errors.append("missing offline docs: third_party/butano/docs/index.html")
    if not (root / "butano-sequel" / "Makefile").is_file():
        errors.append("missing minimal project Makefile: butano-sequel/Makefile")
    if not (root / "butano-sequel" / "src" / "main.cpp").is_file():
        errors.append("missing minimal project source: butano-sequel/src/main.cpp")
    if not (root / "tools" / "butano" / "toolchain.lock").is_file():
        errors.append("missing toolchain lock: tools/butano/toolchain.lock")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the local Butano deployment")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors = collect_setup_errors(args.root.resolve())
    if errors:
        print("Butano setup is incomplete:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print("Butano setup is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
