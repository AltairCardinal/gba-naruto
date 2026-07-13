"""Build API ownership and isolated artifact contract tests."""

from __future__ import annotations

import asyncio
import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("SECRET_KEY", "test-only-build-api-secret")

from routers.auth import User, create_access_token, get_current_user  # noqa: E402
from routers import build  # noqa: E402


class BuildApiOwnershipTests(unittest.TestCase):
    def setUp(self):
        build.build_states.clear()
        build.build_websockets.clear()
        app = FastAPI()
        app.include_router(build.router)

        async def test_user(x_test_user: str = Header(...)) -> User:
            return User(username=x_test_user, role="editor")

        app.dependency_overrides[get_current_user] = test_user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        build.build_states.clear()
        build.build_websockets.clear()

    def test_user_cannot_status_or_download_another_users_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = pathlib.Path(tmp) / "private.gba"
            rom.write_bytes(b"alice-private-marker")
            state = build.BuildState("alice-build", "alice")
            state.status = "done"
            state.progress = 100
            state.rom_path = str(rom)
            build.build_states[state.build_id] = state

            owner_headers = {"X-Test-User": "alice"}
            self.assertEqual(
                self.client.get(
                    "/api/build/status?build_id=alice-build", headers=owner_headers
                ).status_code,
                200,
            )
            self.assertEqual(
                self.client.get(
                    "/api/build/download?build_id=alice-build", headers=owner_headers
                ).content,
                b"alice-private-marker",
            )

            other_headers = {"X-Test-User": "bob"}
            self.assertEqual(
                self.client.get(
                    "/api/build/status?build_id=alice-build", headers=other_headers
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.get(
                    "/api/build/download?build_id=alice-build", headers=other_headers
                ).status_code,
                403,
            )

    def test_latest_build_uses_creation_order_not_uuid_lexical_order(self):
        older = build.BuildState("z-older", "alice")
        older.status = "done"
        newer = build.BuildState("a-newer", "alice")
        newer.status = "running"
        build.build_states[older.build_id] = older
        build.build_states[newer.build_id] = newer
        self.assertEqual(build._resolve_latest_build_for_user("alice"), "a-newer")

    def test_editor_db_snapshot_uses_sqlite_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "source.db"
            destination = pathlib.Path(tmp) / "build" / "editor.db"
            conn = sqlite3.connect(source)
            conn.execute("CREATE TABLE marker (value TEXT)")
            conn.execute("INSERT INTO marker VALUES ('stable')")
            conn.commit()
            conn.close()
            build._snapshot_editor_db(source, destination)
            copied = sqlite3.connect(destination)
            value = copied.execute("SELECT value FROM marker").fetchone()[0]
            copied.close()
            self.assertEqual(value, "stable")

    def test_run_build_uses_injected_cwd_and_persists_all_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            output = root / "output"
            state = build.BuildState("isolated-build", "alice")
            state.output_dir = str(output)
            request_db = root / "request-editor.db"
            request_db.write_bytes(b"sqlite-snapshot")
            state.db_path = str(request_db)
            captured = {}

            class FakeProcess:
                returncode = 0
                stdout = []

                def __init__(self, command, **kwargs):
                    captured["command"] = command
                    captured.update(kwargs)
                    output.mkdir(parents=True, exist_ok=True)
                    (output / "naruto-sequel-dev.gba").write_bytes(b"rom")
                    (output / "naruto-sequel-build-report.json").write_text("{}")
                    (output / "automated-test-report.json").write_text("{}")

                def wait(self):
                    return self.returncode

            with patch.dict(os.environ, {"BUILD_CWD": str(root)}), patch.object(
                build.subprocess, "Popen", FakeProcess
            ):
                asyncio.run(build.run_build(state))

            self.assertEqual(captured["cwd"], str(root))
            self.assertEqual(captured["command"][0], sys.executable)
            self.assertEqual(
                captured["command"][-2:],
                ["--json-output", str(output / "automated-test-report.json")],
            )
            self.assertEqual(captured["env"]["BUILD_OUTPUT_DIR"], str(output))
            self.assertEqual(captured["env"]["DB_PATH"], str(request_db))
            self.assertEqual(state.status, "done")

    def _websocket_close_code(self, message: dict) -> int:
        with self.assertRaises(WebSocketDisconnect) as caught:
            with self.client.websocket_connect("/ws/build") as websocket:
                websocket.send_json(message)
                websocket.receive_json()
        return caught.exception.code

    def test_websocket_requires_explicit_build_id(self):
        token = create_access_token({"sub": "alice", "role": "editor"})
        self.assertEqual(
            self._websocket_close_code({"type": "auth", "token": token}),
            4400,
        )

    def test_websocket_rejects_missing_token(self):
        self.assertEqual(
            self._websocket_close_code({"type": "auth", "build_id": "alice-build"}),
            4401,
        )

    def test_websocket_rejects_another_users_build(self):
        state = build.BuildState("alice-build", "alice")
        state.status = "running"
        build.build_states[state.build_id] = state
        token = create_access_token({"sub": "bob", "role": "editor"})
        self.assertEqual(
            self._websocket_close_code({
                "type": "auth", "token": token, "build_id": "alice-build"
            }),
            4403,
        )

    def test_websocket_streams_only_owned_build_without_server_path(self):
        state = build.BuildState("alice-build", "alice")
        state.status = "running"
        state.logs = ["private build log"]
        state.rom_path = "/tmp/private-alice.gba"
        build.build_states[state.build_id] = state
        token = create_access_token({"sub": "alice", "role": "editor"})
        with self.client.websocket_connect("/ws/build") as websocket:
            websocket.send_json({
                "type": "auth", "token": token, "build_id": "alice-build"
            })
            snapshot = websocket.receive_json()
        self.assertEqual(snapshot["build_id"], "alice-build")
        self.assertEqual(snapshot["logs"], ["private build log"])
        self.assertNotIn("rom_path", snapshot)


if __name__ == "__main__":
    unittest.main()
