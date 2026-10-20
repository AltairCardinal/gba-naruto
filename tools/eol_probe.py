"""Byte-exactness probe: compare working-tree files against their git blobs.

Run from a worktree root.  Reports, per path:
  - sha256 of the working-tree file as it sits on disk
  - sha256 of the blob as stored in git (HEAD:<path>)
  - CR / LF counts for both
This is the diagnostic behind the Windows autocrlf hazard: the repo pins
SHA-256 values of tracked files in its evidence receipts, so a working tree
whose bytes differ from the blob breaks every pin.
"""
import hashlib
import subprocess
import sys
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_bytes(repo: Path, spec: str) -> bytes:
    out = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", spec],
        check=True,
        stdout=subprocess.PIPE,
    )
    return out.stdout


def crlf(data: bytes) -> tuple[int, int]:
    return data.count(b"\r"), data.count(b"\n")


def main() -> int:
    repo = Path(sys.argv[1]).resolve()
    paths = sys.argv[2:]
    bad = 0
    for path in paths:
        wt_path = repo / path
        if not wt_path.is_file():
            print(f"{path}: MISSING in working tree")
            bad += 1
            continue
        wt = wt_path.read_bytes()
        blob = blob_bytes(repo, f"HEAD:{path}")
        wt_sha, blob_sha = sha256_bytes(wt), sha256_bytes(blob)
        wt_cr, wt_lf = crlf(wt)
        blob_cr, blob_lf = crlf(blob)
        same = wt_sha == blob_sha
        if not same:
            bad += 1
        print(
            f"{path}\n"
            f"  worktree sha256 {wt_sha}  CR={wt_cr} LF={wt_lf} size={len(wt)}\n"
            f"  blob     sha256 {blob_sha}  CR={blob_cr} LF={blob_lf} size={len(blob)}\n"
            f"  byte-identical: {'YES' if same else 'NO  <-- pin-breaking'}"
        )
    print(f"\nchecked={len(paths)} mismatched={bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
