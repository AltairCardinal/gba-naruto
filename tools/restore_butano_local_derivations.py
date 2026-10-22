#!/usr/bin/env python3
"""Restore the local artifact copies that the 2026-10-19 cleanup took away.

``docs/butano-wiring-roadmap.md`` (W1) describes a line that is broken *in the
work tree* rather than broken *in the design*: 26 reverse families are named by
the remake's build chain -- ``tools/``, ``sequel/`` and ``butano-sequel/`` all
point at ``artifacts/<family>/`` -- but the local copy of that directory is
gone.  The producer scripts are still here, so the cheapest way to close the
line is to re-run them and check the bytes against the reverse work tree.

This tool does that, and it is deliberately strict about what counts as
"restored":

``rederived``
    A remake-side producer re-created the family and the result is
    **byte-identical** to the reverse work tree's copy.  This is the strong
    case: it proves the remake's own pipeline reproduces the reverse result,
    decoder included.

``imported``
    No remake-side producer reproduces this family (it is a capture, a
    verifier's evidence dump, or a schema version the remake's producer has
    since moved past), so the reverse work tree's copy is imported verbatim.
    The import is pinned by the reverse commit and by a per-file digest, and
    it is recorded as an import -- never as a local derivation.

``diverged``
    A producer ran, claimed the **same schema** as the reverse family, and
    still produced different bytes.  That is a decoder disagreement, not a
    version difference, and it is a hard failure: the roadmap says a
    divergence must be reported, never papered over by copying the nearest
    available file.

A producer that produces a *different schema* is a version difference, not a
divergence, so it may fall back to an import -- but the receipt says so
explicitly and names the producer that superseded it.

Every family is verified twice: the manifest hash (when both sides have one)
and a content digest over the whole directory tree (path + per-file SHA-256),
so a family that keeps its manifest but changes its payload is still caught.

Producers are run **into a staging directory** and only copied into
``artifacts/<family>/`` once they are byte-identical, so a failing producer
cannot leave a half-written family behind.  A file-system snapshot of every
pre-existing artifact directory is taken before and after the run, so a
producer that writes outside its ``--output-dir`` is reported instead of
silently rewriting the tree.

Usage::

    python3 tools/restore_butano_local_derivations.py \\
        --root . \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --wiring artifacts/butano-wiring-coverage-v1/wiring.json \\
        --out-dir artifacts/butano-local-derivations-v1

    # plan only: report what would be produced, change nothing
    python3 tools/restore_butano_local_derivations.py --root . --dry-run
"""

from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.butano.import_rom_reverse_families import (  # noqa: E402
    EXIT_INPUT_ERROR,
    EXIT_OK,
    reverse_commit,
    sha256_file,
)

RECEIPT_SCHEMA = "konoha.butano-local-derivations.v1"

EXIT_DIVERGED = 3

#: Every ``artifacts/<name>`` literal in a producer's source is a path the
#: producer may read.  They are the prerequisites: the tool restores them
#: (recursively) before the producer runs.
_ARTIFACT_LITERAL = re.compile(r"artifacts[/\\]([A-Za-z0-9_.\-]+)")

#: Modes that mean "this family has a byte-identical local copy".
DONE_MODES = {"rederived", "imported", "already-identical", "imported-prerequisite"}

#: Producers that need arguments or inputs the auto-discovery cannot see.
#:
#: ``battle-effect-affine-runtime-v1`` is the interesting one: its producer
#: consumes the raw mGBA capture that lives *inside the family directory it
#: writes* (``raw/`` and ``mirror-raw/``).  The capture cannot be re-derived
#: without a live emulator, so it is imported and the derived PNGs are then
#: produced from it.
PRODUCER_SPECS: dict[str, dict[str, Any]] = {
    "battle-effect-affine-runtime-v1": {
        "producer": "tools/export_battle_effect_affine_runtime.py",
        "extra_args": [
            "--raw-dir",
            "artifacts/battle-effect-affine-runtime-v1/raw",
            "--mirror-raw-dir",
            "artifacts/battle-effect-affine-runtime-v1/mirror-raw",
        ],
        "inputs": [
            "artifacts/battle-effect-affine-runtime-v1/raw",
            "artifacts/battle-effect-affine-runtime-v1/mirror-raw",
        ],
        "note": "raw capture is imported; the two PNGs and the manifest are re-derived",
    },
}


# ---------------------------------------------------------------------------
# digests


def tree_digest(directory: Path) -> dict[str, Any]:
    """Digest a directory: every relative path plus every file's SHA-256."""
    files = sorted(p for p in directory.rglob("*") if p.is_file())
    per_file: dict[str, str] = {}
    rolling = hashlib.sha256()
    byte_count = 0
    for path in files:
        rel = path.relative_to(directory).as_posix()
        digest = sha256_file(path)
        per_file[rel] = digest
        byte_count += path.stat().st_size
        rolling.update(rel.encode("utf-8"))
        rolling.update(b"\0")
        rolling.update(digest.encode("ascii"))
        rolling.update(b"\n")
    return {
        "file_count": len(files),
        "digest": rolling.hexdigest(),
        "per_file": per_file,
        "byte_count": byte_count,
    }


def manifest_sha(directory: Path) -> str | None:
    manifest = directory / "manifest.json"
    return sha256_file(manifest) if manifest.is_file() else None


def manifest_schema(directory: Path) -> str | None:
    manifest = directory / "manifest.json"
    if not manifest.is_file():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    schema = payload.get("schema")
    return str(schema) if isinstance(schema, str) else None


def compare_trees(local: Path, reverse: Path) -> dict[str, Any]:
    """Compare a local directory with its reverse twin, file by file."""
    local_digest = tree_digest(local)
    reverse_digest = tree_digest(reverse)
    local_files = local_digest["per_file"]
    reverse_files = reverse_digest["per_file"]
    shared = sorted(set(local_files) & set(reverse_files))
    differing = [rel for rel in shared if local_files[rel] != reverse_files[rel]]
    return {
        "identical": local_digest["digest"] == reverse_digest["digest"],
        "local_digest": local_digest["digest"],
        "reverse_digest": reverse_digest["digest"],
        "local_file_count": local_digest["file_count"],
        "reverse_file_count": reverse_digest["file_count"],
        "only_local": sorted(set(local_files) - set(reverse_files))[:12],
        "only_reverse": sorted(set(reverse_files) - set(local_files))[:12],
        "differing": differing[:12],
        "differing_count": len(differing),
        "local_manifest_sha": manifest_sha(local),
        "reverse_manifest_sha": manifest_sha(reverse),
        "local_schema": manifest_schema(local),
        "reverse_schema": manifest_schema(reverse),
    }


def snapshot_artifacts(root: Path) -> dict[str, tuple[int, int]]:
    """Cheap fingerprint of every file under ``artifacts/``."""
    snapshot: dict[str, tuple[int, int]] = {}
    base = root / "artifacts"
    if not base.is_dir():
        return snapshot
    for path in base.rglob("*"):
        if path.is_file():
            stat = path.stat()
            snapshot[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


# ---------------------------------------------------------------------------
# producer discovery


def _eval_path_segments(node: ast.AST, constants: dict[str, str]) -> list[str] | None:
    """Evaluate a path expression to its string segments.

    ``REPO_ROOT / "artifacts" / SCHEMA`` is the shape most producers use for
    their output directory, and the literal scan alone never sees it: the
    family name hides behind a module constant.  An unknown root (``REPO_ROOT``
    is a ``Path``, not a string) contributes no segment, which is exactly what
    is needed to read the *suffix* of the path.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [part for part in node.value.split("/") if part]
    if isinstance(node, ast.Name):
        value = constants.get(node.id)
        return [value] if value is not None else []
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _eval_path_segments(node.left, constants)
        right = _eval_path_segments(node.right, constants)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.Call):
        for arg in node.args:
            segments = _eval_path_segments(arg, constants)
            if segments is not None:
                return segments
    return None


def producer_output_family(script: Path) -> str | None:
    """The family a producer writes, read from its ``--output-dir`` default."""
    try:
        tree = ast.parse(script.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return None
    constants: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.targets[0].id] = node.value.value
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in {"--output-dir", "--output"}
        ):
            continue
        default = None
        for keyword in node.keywords:
            if keyword.arg == "default":
                default = keyword.value
        if default is None:
            continue
        segments = _eval_path_segments(default, constants)
        if not segments:
            continue
        flat = [seg for seg in segments if seg]
        if "artifacts" in flat:
            index = flat.index("artifacts")
            if index + 1 < len(flat):
                return flat[index + 1]
        if flat:
            return flat[-1]
    return None


def discover_producers(root: Path) -> dict[str, list[str]]:
    """Map a family to the remake-side tools that can produce it.

    Two signals are used: the ``artifacts/<family>`` literals in the source
    (an input or a hard-coded output) and the ``--output-dir`` default
    resolved through the module's own constants (the common case, where the
    family name never appears as a literal).
    """
    producers: dict[str, set[str]] = {}
    for script in sorted(root.glob("tools/**/export_*.py")):
        try:
            source = script.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = script.relative_to(root).as_posix()
        for name in set(_ARTIFACT_LITERAL.findall(source)):
            producers.setdefault(name, set()).add(rel)
        output_family = producer_output_family(script)
        if output_family:
            producers.setdefault(output_family, set()).add(rel)
    return {name: sorted(paths) for name, paths in producers.items()}


def producer_flag(root: Path, script: str) -> str:
    """The flag that selects the producer's output directory."""
    source = (root / script).read_text(encoding="utf-8", errors="ignore")
    if "--output-dir" in source:
        return "--output-dir"
    return "--output"


def producer_prerequisites(root: Path, script: str, family: str) -> list[str]:
    """``artifacts/<x>`` paths the producer reads, excluding its own output."""
    source = (root / script).read_text(encoding="utf-8", errors="ignore")
    names = set(_ARTIFACT_LITERAL.findall(source))
    names.discard(family)
    return sorted(f"artifacts/{name}" for name in names)


def producer_score(family: str, script: str) -> int:
    """Rank a producer by how likely it is to be *the* producer of a family."""
    stem = Path(script).stem
    normalised = family.rsplit("-v", 1)[0] if re.search(r"-v\d+$", family) else family
    normalised = normalised.replace("-", "_")
    if normalised and normalised in stem:
        return 0
    if family.replace("-", "_") in stem:
        return 1
    return 2


# ---------------------------------------------------------------------------
# the restore itself


class Restorer:
    def __init__(
        self,
        root: Path,
        reverse_root: Path,
        *,
        dry_run: bool = False,
        provenance: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.root = root
        self.reverse_root = reverse_root
        self.dry_run = dry_run
        self.producers = discover_producers(root)
        self.rows: dict[str, dict[str, Any]] = {}
        self.provenance = dict(provenance or {})
        # Families whose local directory already existed when the run started.
        # A copy that this run did not create is reported as "already
        # identical" (unknown provenance) rather than as an import.
        self.pre_existing: set[str] = {
            path.name for path in (root / "artifacts").glob("*") if path.is_dir()
        }

    # -- helpers ---------------------------------------------------------
    def _local_dir(self, family: str) -> Path:
        return self.root / "artifacts" / family

    def _reverse_dir(self, family: str) -> Path:
        return self.reverse_root / "artifacts" / family

    def _record(self, family: str, **fields: Any) -> dict[str, Any]:
        row = self.rows.setdefault(family, {"family": family})
        row.update(fields)
        return row

    def _mode(self, family: str) -> str | None:
        row = self.rows.get(family)
        return str(row.get("mode")) if row else None

    # -- import ----------------------------------------------------------
    def _import_tree(self, source: Path, target: Path) -> None:
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)

    def _import_family(self, family: str, reason: str) -> bool:
        source = self._reverse_dir(family)
        target = self._local_dir(family)
        if not source.is_dir():
            self._record(family, mode="unavailable", reason=reason)
            return False
        if target.is_dir() and compare_trees(target, source)["identical"]:
            if family in self.pre_existing:
                self._record(family, mode="already-identical", reason=reason)
            else:
                # This run put the bytes there (an imported input subtree);
                # say so instead of pretending the copy was already there.
                self._record(
                    family,
                    mode="imported",
                    reason=reason
                    + "; the local copy was assembled from the reverse tree's raw input",
                    producer=None,
                    local_digest=tree_digest(target)["digest"],
                    reverse_digest=tree_digest(source)["digest"],
                    local_manifest_sha=manifest_sha(target),
                    reverse_manifest_sha=manifest_sha(source),
                    identical=True,
                )
            return True
        if not self.dry_run:
            self._import_tree(source, target)
        comparison = compare_trees(target, source) if target.is_dir() else {
            "identical": False,
            "local_digest": None,
            "reverse_digest": tree_digest(source)["digest"],
            "local_manifest_sha": None,
            "reverse_manifest_sha": manifest_sha(source),
        }
        self._record(
            family,
            mode="imported",
            reason=reason,
            producer=None,
            local_digest=comparison.get("local_digest"),
            reverse_digest=comparison.get("reverse_digest"),
            identical=comparison.get("identical"),
            local_manifest_sha=comparison.get("local_manifest_sha"),
            reverse_manifest_sha=comparison.get("reverse_manifest_sha"),
        )
        return bool(comparison.get("identical"))

    def _import_subtree(self, rel: str, reason: str) -> bool:
        """Import one subtree of a family (e.g. a raw capture) from the twin."""
        source = self.reverse_root / rel
        target = self.root / rel
        if not source.exists():
            return False
        if not self.dry_run:
            self._import_tree(source, target)
        return True

    # -- prerequisites ---------------------------------------------------
    def _ensure_prerequisites(
        self,
        family: str,
        script: str,
        stack: tuple[str, ...],
    ) -> list[str]:
        """Make sure every ``artifacts/<x>`` the producer reads exists locally."""
        spec = PRODUCER_SPECS.get(family)
        paths = list(producer_prerequisites(self.root, script, family))
        if spec:
            paths.extend(spec.get("inputs", []))
        needed: list[str] = []
        for rel in sorted(set(paths)):
            target = self.root / rel
            if target.exists():
                continue
            needed.append(rel)
            name = Path(rel).name
            if name == family:
                # A raw capture living inside the family directory it writes.
                self._import_subtree(rel, f"raw input of {family}")
                continue
            if name not in stack and self._reverse_dir(name).is_dir():
                self.restore(name, stack + (family,))
            if not target.exists():
                self._import_subtree(rel, f"prerequisite of {family} ({script})")
        return needed

    # -- re-derive -------------------------------------------------------
    def _run_producer(
        self,
        family: str,
        script: str,
        stage: Path,
    ) -> tuple[int, str, str]:
        target = stage / family
        cmd = [
            sys.executable,
            str(self.root / script),
            "--root",
            str(self.root),
            producer_flag(self.root, script),
            str(target),
        ]
        spec = PRODUCER_SPECS.get(family)
        if spec and spec.get("extra_args"):
            cmd.extend(spec["extra_args"])
        proc = subprocess.run(
            cmd,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        return proc.returncode, proc.stdout[-4000:], proc.stderr[-4000:]

    def _try_rederive(
        self,
        family: str,
        script: str,
        stage: Path,
        stack: tuple[str, ...],
    ) -> dict[str, Any]:
        """Run one producer and report what it produced."""
        record: dict[str, Any] = {"producer": script}
        record["bootstrapped"] = self._ensure_prerequisites(family, script, stack)
        target = stage / family
        code, out, err = self._run_producer(family, script, stage)
        record["returncode"] = code
        if code != 0:
            tail = (err or out).strip().splitlines()
            record["error"] = tail[-1:] or ["failed"]
            record["missing_inputs"] = sorted(set(_ARTIFACT_LITERAL.findall(err or out)))
            return record
        if not target.is_dir():
            record["error"] = ["producer produced no directory"]
            return record
        comparison = compare_trees(target, self._reverse_dir(family))
        record.update(
            {
                "identical": comparison["identical"],
                "local_digest": comparison["local_digest"],
                "reverse_digest": comparison["reverse_digest"],
                "local_manifest_sha": comparison["local_manifest_sha"],
                "reverse_manifest_sha": comparison["reverse_manifest_sha"],
                "local_schema": comparison["local_schema"],
                "reverse_schema": comparison["reverse_schema"],
                "differing_count": comparison["differing_count"],
                "only_local": comparison["only_local"],
                "only_reverse": comparison["only_reverse"],
                "differing": comparison["differing"],
            }
        )
        if comparison["identical"] and not self.dry_run:
            self._import_tree(target, self._local_dir(family))
        return record

    # -- per family ------------------------------------------------------
    def restore(self, family: str, stack: tuple[str, ...] = ()) -> dict[str, Any]:
        if self._mode(family) in DONE_MODES:
            return self.rows[family]
        if family in stack:
            return self._record(
                family,
                mode="imported",
                reason="imported to break a dependency cycle",
                producer=None,
            )

        reverse_dir = self._reverse_dir(family)
        if not reverse_dir.is_dir():
            return self._record(family, mode="unavailable", reason="no reverse twin")

        local_dir = self._local_dir(family)
        if local_dir.is_dir():
            comparison = compare_trees(local_dir, reverse_dir)
            if comparison["identical"]:
                known = self.provenance.get(family)
                if known and known.get("local_digest") == comparison["local_digest"]:
                    # The copy is byte-identical and the provenance record
                    # still describes these exact bytes: keep the recorded
                    # mode instead of downgrading it to "already identical".
                    return self._record(
                        family,
                        mode=known.get("mode", "already-identical"),
                        reason=known.get("reason", "local copy already byte-identical"),
                        producer=known.get("producer"),
                        local_digest=comparison["local_digest"],
                        reverse_digest=comparison["reverse_digest"],
                        local_manifest_sha=comparison["local_manifest_sha"],
                        reverse_manifest_sha=comparison["reverse_manifest_sha"],
                        local_schema=comparison["local_schema"],
                        reverse_schema=comparison["reverse_schema"],
                        identical=True,
                        provenance_recorded_at=known.get("recorded_at"),
                    )
                return self._record(
                    family,
                    mode="already-identical",
                    reason="local copy already byte-identical",
                    producer=None,
                    local_digest=comparison["local_digest"],
                    reverse_digest=comparison["reverse_digest"],
                    local_manifest_sha=comparison["local_manifest_sha"],
                    reverse_manifest_sha=comparison["reverse_manifest_sha"],
                    local_schema=comparison["local_schema"],
                    reverse_schema=comparison["reverse_schema"],
                    identical=True,
                )

        scripts = list(self.producers.get(family, []))
        spec = PRODUCER_SPECS.get(family)
        if spec:
            spec_script = spec["producer"]
            scripts = [spec_script] + [s for s in scripts if s != spec_script]
        scripts.sort(key=lambda s: (producer_score(family, s), s))

        attempts: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="w1-stage-") as tmp:
            stage = Path(tmp)
            for script in scripts:
                record = self._try_rederive(family, script, stage, stack)
                attempts.append(record)
                if record.get("identical"):
                    self._record(
                        family,
                        mode="rederived",
                        reason="remake-side producer reproduced the family byte-for-byte",
                        producer=script,
                        local_digest=record["local_digest"],
                        reverse_digest=record["reverse_digest"],
                        local_manifest_sha=record["local_manifest_sha"],
                        reverse_manifest_sha=record["reverse_manifest_sha"],
                        local_schema=record["local_schema"],
                        reverse_schema=record["reverse_schema"],
                        identical=True,
                    )
                    self.rows[family]["attempts"] = attempts
                    return self.rows[family]

        # No producer reproduced it.  Decide between "the version moved on" and
        # "the decoder disagrees".
        same_schema_divergence = None
        for record in attempts:
            if record.get("returncode") != 0:
                continue
            local_schema = record.get("local_schema")
            reverse_schema = record.get("reverse_schema")
            if local_schema and reverse_schema and local_schema == reverse_schema:
                same_schema_divergence = record
                break

        if same_schema_divergence is not None:
            self._record(
                family,
                mode="diverged",
                reason=(
                    "producer claimed the same schema but produced different bytes; "
                    "the roadmap forbids papering over a divergence"
                ),
                producer=same_schema_divergence.get("producer"),
                local_digest=same_schema_divergence.get("local_digest"),
                reverse_digest=same_schema_divergence.get("reverse_digest"),
                differing_count=same_schema_divergence.get("differing_count"),
                differing=same_schema_divergence.get("differing"),
                identical=False,
                attempts=attempts,
            )
            return self.rows[family]

        schemas = sorted(
            {
                f"{a.get('local_schema')} != {a.get('reverse_schema')}"
                for a in attempts
                if a.get("local_schema") or a.get("reverse_schema")
            }
        )
        if schemas:
            reason = (
                "remake-side producer emits a different schema version; observed "
                + "; ".join(schemas)
            )
        else:
            reason = (
                "no remake-side producer reproduces this family "
                "(capture / verifier evidence / superseded schema)"
            )
        self._import_family(family, reason)
        self.rows[family]["attempts"] = attempts
        return self.rows[family]


# ---------------------------------------------------------------------------
# receipt


def candidate_families(wiring_path: Path) -> list[str]:
    payload = json.loads(wiring_path.read_text(encoding="utf-8"))
    rows = payload.get("source_rows") or []
    return sorted(
        str(row["id"])
        for row in rows
        if row.get("state") == "local-derivation-missing"
    )


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = payload["summary"]
    lines.append("# 本地派生产物补回收据（自动生成）")
    lines.append("")
    lines.append("本文件由 `tools/restore_butano_local_derivations.py` 生成，不要手工编辑。")
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("| --- | ---: |")
    for key in (
        "candidate_families",
        "rederived",
        "imported",
        "already_identical",
        "imported_prerequisite",
        "diverged",
        "unavailable",
        "byte_identical",
    ):
        lines.append(f"| {key} | {summary.get(key, 0)} |")
    lines.append("")
    lines.append("## 逐族结果")
    lines.append("")
    lines.append("| 族 | 模式 | producer | 与逆向树逐字节相同 | manifest sha |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in payload["rows"]:
        lines.append(
            "| `{family}` | {mode} | {producer} | {identical} | {manifest} |".format(
                family=row["family"],
                mode=row.get("mode"),
                producer=f"`{row['producer']}`" if row.get("producer") else "—",
                identical="✅" if row.get("identical") else "❌",
                manifest=(row.get("local_manifest_sha") or "—")[:16],
            )
        )
    lines.append("")
    lines.append("## 边界声明")
    lines.append("")
    lines.append(
        "- `rederived` 是强结论：复刻侧自己的 producer 复现了逆向树的字节，"
        "**包括解码器**。"
    )
    lines.append(
        "- `imported` 是弱结论：字节来自逆向树，按 reverse commit + 逐文件摘要钉死，"
        "**不是本地派生**。"
    )
    lines.append(
        "- `diverged` 是硬失败：producer 声称同一 schema 却产出不同字节，"
        "路线图要求报错而不是「就近取一个」。"
    )
    lines.append("- 本回执的读数来自当轮工作树与逆向树，逆向树一变就变，不得写死。")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=Path("/Users/altair/github/gba-naruto-reverse"),
    )
    parser.add_argument(
        "--wiring",
        type=Path,
        default=Path("artifacts/butano-wiring-coverage-v1/wiring.json"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/butano-local-derivations-v1"),
    )
    parser.add_argument("--only", action="append", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    reverse_root = args.reverse_root.resolve()
    wiring_path = args.wiring if args.wiring.is_absolute() else root / args.wiring

    if not wiring_path.is_file():
        print(f"wiring receipt not found: {wiring_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if not (reverse_root / "artifacts").is_dir():
        print(f"reverse tree not found: {reverse_root}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    families = candidate_families(wiring_path)
    if args.only:
        wanted = set(args.only)
        families = [f for f in families if f in wanted]

    before = snapshot_artifacts(root)
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    provenance_path = out_dir / "provenance.json"
    known: dict[str, dict[str, Any]] = {}
    if provenance_path.is_file():
        try:
            known = json.loads(provenance_path.read_text(encoding="utf-8")).get("families", {})
        except (json.JSONDecodeError, OSError):
            known = {}
    restorer = Restorer(root, reverse_root, dry_run=args.dry_run, provenance=known)
    for family in families:
        try:
            restorer.restore(family)
        except Exception as exc:  # pragma: no cover - defensive
            restorer._record(family, mode="error", reason=f"{type(exc).__name__}: {exc}")
    after = snapshot_artifacts(root)

    touched = sorted(
        path for path in set(before) & set(after) if before[path] != after[path]
    )
    removed = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))

    rows = [restorer.rows[f] for f in sorted(restorer.rows)]
    summary = {
        "candidate_families": len(families),
        "rederived": sum(1 for r in rows if r.get("mode") == "rederived"),
        "imported": sum(1 for r in rows if r.get("mode") == "imported"),
        "already_identical": sum(1 for r in rows if r.get("mode") == "already-identical"),
        "imported_prerequisite": sum(
            1 for r in rows if r.get("mode") == "imported-prerequisite"
        ),
        "diverged": sum(1 for r in rows if r.get("mode") == "diverged"),
        "unavailable": sum(1 for r in rows if r.get("mode") == "unavailable"),
        "error": sum(1 for r in rows if r.get("mode") == "error"),
    }
    summary["byte_identical"] = sum(1 for r in rows if r.get("mode") in DONE_MODES)

    payload = {
        "schema": RECEIPT_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": {
            "wiring": {
                "path": str(wiring_path.relative_to(root))
                if wiring_path.is_relative_to(root)
                else str(wiring_path),
                "sha256": sha256_file(wiring_path),
            },
            "reverse_root": str(reverse_root),
            "reverse_commit": reverse_commit(reverse_root),
        },
        "mode": "dry-run" if args.dry_run else "apply",
        "summary": summary,
        "collateral": {
            "modified_existing": touched,
            "removed_existing": removed,
            "added_count": len(added),
            "added_families": sorted(
                {
                    Path(p).parts[1]
                    for p in added
                    if len(Path(p).parts) > 1 and Path(p).parts[0] == "artifacts"
                }
            ),
        },
        "rows": rows,
    }

    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "local.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "local.md").write_text(render_markdown(payload), encoding="utf-8")

    # The provenance record survives re-runs: it remembers *how* each local
    # copy came to be, so a second run does not downgrade "rederived" to
    # "already identical" and lose the distinction the roadmap asks for.
    recorded_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    families_record: dict[str, dict[str, Any]] = dict(known)
    for row in rows:
        if row.get("mode") in {"error", "unavailable"}:
            continue
        families_record[row["family"]] = {
            "mode": row.get("mode"),
            "producer": row.get("producer"),
            "reason": row.get("reason"),
            "local_digest": row.get("local_digest"),
            "reverse_digest": row.get("reverse_digest"),
            "local_manifest_sha": row.get("local_manifest_sha"),
            "reverse_manifest_sha": row.get("reverse_manifest_sha"),
            "recorded_at": recorded_at,
        }
    (out_dir / "provenance.json").write_text(
        json.dumps(
            {
                "schema": RECEIPT_SCHEMA + ".provenance",
                "generated_at": recorded_at,
                "reverse_root": str(reverse_root),
                "reverse_commit": reverse_commit(reverse_root),
                "families": families_record,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    print(
        json.dumps(payload["collateral"], ensure_ascii=False, sort_keys=True)[:400],
        file=sys.stderr,
    )
    if summary["diverged"] or summary["error"] or summary["unavailable"]:
        return EXIT_DIVERGED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
