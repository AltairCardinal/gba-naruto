"""Keep every backend test away from the repository's real editor database."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_editor_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "editor.db"))
