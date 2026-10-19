"""Recipe adapter and existing fixture helpers for frozen resource audits.

Battle-effect v1 stays immutable so its permanent receipts still replay.
New families reuse its fixture/identity mechanism and select an importer recipe.
"""
import os
import subprocess
import sys
from tools.audit_battle_effect_fixed_roundtrip import _managed_run, _write, _fixture_inputs, _edit


def build_cli(fixture, name, edits, *, catalog, spec_schema, patch_type):
    case = fixture / "cases" / name
    case.mkdir(parents=True, exist_ok=True)
    spec = {"schema": spec_schema, "source_catalog": catalog, "edits": edits}
    _write(case / "spec.json", spec)
    _write(case / "manifest.json", {"patches": [{"id": name, "type": patch_type,
                                                "spec": f"cases/{name}/spec.json"}]})
    _write(case / "project.json", {
        "project_id": name,
        "base_rom": {"path": "rom/base.gba", "sha1": "26f60795fa5e63b4f0264b84e453beffd56b9f7d"},
        "patch_manifest": f"cases/{name}/manifest.json",
        "build": {"output_rom": f"cases/{name}/output.gba", "report": f"cases/{name}/build-report.json"},
    })
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C",
                   "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(fixture),
                   "DB_PATH": str(fixture / "sequel/absent-editor.db")}
    completed = subprocess.run(
        [sys.executable, str(fixture / "tools/build_mod.py"), "--project", f"cases/{name}/project.json"],
        cwd=fixture, env=environment, capture_output=True, text=True, timeout=45, check=False,
    )
    (case / "stdout.txt").write_text(completed.stdout)
    (case / "stderr.txt").write_text(completed.stderr)
    return completed, case

