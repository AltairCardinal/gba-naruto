"""Repository line-ending guard.

The repo uses file SHA-256 as evidence identity and the local
`core.autocrlf` must stay `false` (see `notes/windows-migration-20261020.md`).
On Windows, `Path.write_text` rewrites `\\n` as `\\r\\n` by default, so a tool
that writes a tracked file can silently change every digest while
`git status` stays clean.

This test fails as soon as any tracked file carries CRLF.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".txt", ".lua", ".sh", ".yml", ".yaml", ".cfg",
    ".toml", ".ini", ".js", ".ts", ".vue", ".html", ".css", ".sql", ".asm",
    ".c", ".h", ".S", ".ld", ".ips", ".jsonl",
}


def _tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.decode("utf-8", "replace").split("\0") if f]


class LineEndingTests(unittest.TestCase):
    def test_no_tracked_text_file_has_crlf(self):
        offenders = []
        for rel in _tracked_files():
            path = REPO / rel
            if not path.exists() or path.is_dir():
                continue
            if path.suffix not in TEXT_SUFFIXES and not path.name.endswith(".S"):
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in data[:4096]:
                continue  # binary
            if b"\r\n" in data:
                offenders.append((rel, data.count(b"\r\n")))
        self.assertEqual(
            [], offenders,
            "tracked files contain CRLF line endings (this invalidates the "
            "SHA-256 evidence identity):\n"
            + "\n".join(f"  {rel}: {count} CRLF" for rel, count in offenders),
        )

    def test_no_tracked_text_file_has_a_utf8_bom(self):
        """A BOM is the same class of silent corruption as a CRLF.

        `Path.write_text(..., encoding="utf-8")` does not add one, but
        `encoding="utf-8-sig"` does, and so does a round trip through some
        editors.  The repository writes through `tools/lib/io.write_text`,
        which never adds one; this test keeps it that way.

        (Found in the wild: `tools/font_roundtrip.py` was committed with a
        BOM, which also breaks `python3` shebang parsing on some systems.)
        """
        offenders = []
        for rel in _tracked_files():
            path = REPO / rel
            if not path.exists() or path.is_dir():
                continue
            if path.suffix not in TEXT_SUFFIXES and not path.name.endswith(".S"):
                continue
            # The vendored third-party package is a read-only copy of somebody
            # else's files; their bytes are not ours to normalise.
            if rel.startswith("third_party/"):
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in data[:4096]:
                continue  # binary
            if data.startswith(b"\xef\xbb\xbf"):
                offenders.append(rel)
        self.assertEqual(
            [], offenders,
            "tracked text files start with a UTF-8 BOM:\n"
            + "\n".join(f"  {rel}" for rel in offenders),
        )

    def test_core_autocrlf_is_false(self):
        result = subprocess.run(
            ["git", "config", "--get", "core.autocrlf"], cwd=REPO,
            capture_output=True, text=True,
        )
        value = result.stdout.strip()
        self.assertIn(
            value, ("false", ""),
            f"core.autocrlf must stay false, found {value!r}",
        )


if __name__ == "__main__":
    unittest.main()
