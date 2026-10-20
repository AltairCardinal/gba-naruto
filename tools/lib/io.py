"""File writing helpers that keep line endings stable.

The repository uses file SHA-256 as evidence identity, and the local
`core.autocrlf` must stay `false`.  Windows' default text mode rewrites
`\n` as `\r\n`, which would silently invalidate every pinned digest while
`git status` stays clean.

Every tool that writes into the repository should go through `write_text`.
"""
from __future__ import annotations

import pathlib


def write_text(path: pathlib.Path | str, text: str, encoding: str = "utf-8") -> pathlib.Path:
    """Write `text` with LF line endings and create parent directories."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding, newline="\n") as handle:
        handle.write(text)
    return path


def write_json(path: pathlib.Path | str, payload, encoding: str = "utf-8") -> pathlib.Path:
    """Write a JSON document with LF line endings."""
    import json

    return write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding)
