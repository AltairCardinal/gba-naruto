"""Build API ownership and isolated artifact contract tests."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("SECRET_KEY", "test-only-build-api-secret")

from routers.auth import User, get_current_user  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
