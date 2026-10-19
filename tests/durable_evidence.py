from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_binding(root: Path, filename: str) -> dict[str, Any]:
    return json.loads((root / "notes" / filename).read_text(encoding="utf-8"))


def raw_evidence_available(root: Path, observations: Path) -> bool:
    payload = json.loads(observations.read_text(encoding="utf-8"))
    paths: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str) and value.startswith("build/"):
            paths.append(value)

    collect(payload)
    return bool(paths) and all((root / path).is_file() for path in paths)
