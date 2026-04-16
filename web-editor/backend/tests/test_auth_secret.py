"""Test that SECRET_KEY is not hardcoded in source files."""
import ast
import os
import pathlib

BACKEND_DIR = pathlib.Path("/root/gba-naruto/web-editor/backend/routers")


def get_all_py_files():
    return list(BACKEND_DIR.glob("*.py"))


def test_secret_key_not_in_source():
    """Verify SECRET_KEY literal string does not appear in any .py source file."""
    secret_value = "naruto-gba-editor-secret-change-in-production"

    violations = []
    for f in get_all_py_files():
        content = f.read_text()
        if secret_value in content:
            violations.append(str(f.relative_to(BACKEND_DIR)))

    assert not violations, (
        f"SECRET_KEY hardcoded value found in: {violations}"
    )


def test_auth_module_requires_env():
    """Verify auth.py reads SECRET_KEY from environment."""
    auth_path = BACKEND_DIR / "auth.py"
    content = auth_path.read_text()
    assert "os.environ.get" in content, "auth.py must read SECRET_KEY from env"
    assert "ValueError" in content, "auth.py must raise if SECRET_KEY not set"
