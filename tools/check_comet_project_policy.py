#!/usr/bin/env python3
"""Strictly parse and audit this repository's Comet project policy."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


EXPECTED_POLICY: dict[str, object] = {
    "schema_version": 1,
    "enforcement": "strict",
    "goal": {
        "required": True,
        "require_active_before_write": True,
        "revoke_writer_on_user_prompt": True,
    },
    "change": {
        "require_explicit_selection": True,
        "allow_first_active_fallback": False,
    },
    "git": {"commit": "prompt", "push": "deny"},
    "agents": {
        "max_writers": 1,
        "reviewer_read_only": True,
        "sidecar_read_only": True,
        "require_parent_verification": True,
    },
    "resources": {
        "runner": ["python3", "tools/run_guarded.py"],
        "heavy_lock": "build/resource-guard/heavy.lock",
        "monitor_owned_tree_rss": True,
    },
    "rom": {
        "require_verified_snapshot": True,
        "prefer_latest_verified_snapshot": True,
        "require_single_input": True,
        "require_zero_input_control": True,
    },
    "evidence": {
        "immutable_runs": True,
        "require_unique_run_id": True,
        "require_manifest": True,
        "require_input_hashes": True,
        "preserve_superseded_results": True,
    },
    "limits": {
        "stop_after_no_new_evidence_cycles": 3,
        "stop_after_unchanged_waits": 3,
    },
}

CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]")
PUSH_RE = re.compile(r"\bpush\b|推送", re.IGNORECASE)
PUSH_START_UI_RE = re.compile(r"\bpush\s+start\b", re.IGNORECASE)
NORMATIVE_EXEMPTIONS = ("历史", "曾", "不再运行", "不得", "禁止", "不执行")


def _scalar(value: str, line_number: int) -> object:
    if not value:
        raise ValueError(f"line {line_number}: empty scalar")
    if value[0] in "\"'" or value[-1] in "\"'":
        raise ValueError(f"line {line_number}: quoted scalars are unsupported")
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
        return int(value)
    return value


def parse_policy(text: str) -> dict[str, object]:
    """Parse the small YAML subset accepted by the project policy schema."""
    logical_lines: list[tuple[int, int, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        if "\t" in raw_line:
            raise ValueError(f"line {line_number}: tabs are unsupported")
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent % 2:
            raise ValueError(f"line {line_number}: indentation must use two spaces")
        logical_lines.append((line_number, indent, raw_line[indent:]))

    if not logical_lines:
        return {}
    if logical_lines[0][1] != 0:
        raise ValueError(
            f"line {logical_lines[0][0]}: top-level keys must not be indented"
        )

    def parse_block(index: int, indent: int) -> tuple[object, int]:
        first_number, first_indent, first_content = logical_lines[index]
        if first_indent != indent:
            raise ValueError(f"line {first_number}: skipped indentation level")
        is_list = first_content.startswith("- ")
        container: object = [] if is_list else {}

        while index < len(logical_lines):
            line_number, current_indent, content = logical_lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(f"line {line_number}: skipped indentation level")
            if content.startswith("- ") != is_list:
                raise ValueError(f"line {line_number}: mixed map and list block")

            if is_list:
                item = content[2:].strip()
                if not item:
                    raise ValueError(f"line {line_number}: empty list item")
                assert isinstance(container, list)
                container.append(_scalar(item, line_number))
                index += 1
                if index < len(logical_lines) and logical_lines[index][1] > indent:
                    raise ValueError(
                        f"line {logical_lines[index][0]}: nested list items are unsupported"
                    )
                continue

            if ":" not in content:
                raise ValueError(f"line {line_number}: map entry requires ':'")
            key, raw_value = content.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if not key:
                raise ValueError(f"line {line_number}: empty key")
            assert isinstance(container, dict)
            if key in container:
                raise ValueError(f"line {line_number}: duplicate key {key!r}")

            index += 1
            if raw_value:
                container[key] = _scalar(raw_value, line_number)
                if index < len(logical_lines) and logical_lines[index][1] > indent:
                    raise ValueError(
                        f"line {logical_lines[index][0]}: scalar cannot contain a child block"
                    )
                continue

            if index >= len(logical_lines) or logical_lines[index][1] <= indent:
                raise ValueError(f"line {line_number}: key {key!r} has no child block")
            if logical_lines[index][1] != indent + 2:
                raise ValueError(
                    f"line {logical_lines[index][0]}: skipped indentation level"
                )
            child, index = parse_block(index, indent + 2)
            container[key] = child

        return container, index

    parsed, end = parse_block(0, 0)
    if end != len(logical_lines):
        raise ValueError(f"line {logical_lines[end][0]}: invalid indentation")
    if not isinstance(parsed, dict):
        raise ValueError("top-level policy must be a map")
    return parsed


def validate_policy(policy: dict[str, object]) -> list[str]:
    """Return all deviations from the exact project policy schema."""
    errors: list[str] = []

    def validate(actual: object, expected: object, path: str) -> None:
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                errors.append(f"{path or 'policy'} must be a map")
                return
            for key in actual:
                child_path = f"{path}.{key}" if path else key
                if key not in expected:
                    if child_path == "activation":
                        errors.append("activation is unsupported by the project policy schema")
                    else:
                        errors.append(f"{child_path} is unknown")
            for key, child_expected in expected.items():
                child_path = f"{path}.{key}" if path else key
                if key not in actual:
                    errors.append(f"{child_path} is required")
                else:
                    validate(actual[key], child_expected, child_path)
            return

        if isinstance(expected, list):
            if not isinstance(actual, list):
                errors.append(f"{path} must be a list")
            elif actual != expected:
                errors.append(f"{path} must equal {expected!r}")
            return

        if type(actual) is not type(expected):
            errors.append(f"{path} must be {type(expected).__name__}")
        elif actual != expected:
            errors.append(f"{path} must equal {expected!r}")

    validate(policy, EXPECTED_POLICY, "")
    return errors


def _relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _validated_change_path(root: Path, name: str) -> Path:
    name_path = Path(name)
    if (
        not name
        or name_path.is_absolute()
        or len(name_path.parts) != 1
        or name in {".", ".."}
    ):
        raise ValueError(f"invalid active change name: {name!r}")
    changes_root = (root / "openspec/changes").resolve()
    change = (changes_root / name).resolve()
    try:
        change.relative_to(changes_root)
    except ValueError as exc:
        raise ValueError(f"active change escapes repository: {name!r}") from exc
    return change


def _validated_plan_path(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    plan = candidate.resolve()
    try:
        plan.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"plan path escapes repository: {path}") from exc
    return plan


def _contains_push(text: str) -> bool:
    if re.search(r"\bgit\s+push\b", text, re.IGNORECASE):
        return True
    return PUSH_RE.search(PUSH_START_UI_RE.sub("", text)) is not None


def _normative_push_required(text: str) -> bool:
    for clause in re.split(r"[；;。.!?！？]", text):
        if _contains_push(clause) and not any(
            marker in clause for marker in NORMATIVE_EXEMPTIONS
        ):
            return True
    return False


def _scan_push_lines(
    root: Path, path: Path, checkbox_aware: bool
) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    checkbox_unfinished: bool | None = None
    checkbox_indent: int | None = None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise OSError(f"{_relative_path(root, path)}: {exc}") from exc

    for line_number, text in enumerate(lines, 1):
        checkbox = CHECKBOX_RE.match(text) if checkbox_aware else None
        if checkbox:
            checkbox_unfinished = checkbox.group(1) == " "
            checkbox_indent = len(text) - len(text.lstrip())
        elif checkbox_unfinished is not None and text.strip():
            line_indent = len(text) - len(text.lstrip())
            if checkbox_indent is not None and line_indent <= checkbox_indent:
                checkbox_unfinished = None
                checkbox_indent = None
        if checkbox_aware and not _contains_push(text):
            continue
        if not checkbox_aware and not _normative_push_required(text):
            continue
        if checkbox_aware and checkbox_unfinished is False:
            continue
        conflicts.append(
            {
                "path": _relative_path(root, path),
                "line": line_number,
                "text": text.strip(),
                "reason": (
                    "unfinished task or plan requires push"
                    if checkbox_aware
                    else "active normative artifact requires push"
                ),
            }
        )
    return conflicts


def find_push_conflicts(
    root: Path, active_changes: list[str], plan_paths: list[Path]
) -> list[dict[str, object]]:
    """Find active normative and unfinished plan requirements to push."""
    conflicts: list[dict[str, object]] = []
    for name in active_changes:
        change = _validated_change_path(root, name)
        normative_paths = [change / "proposal.md", change / "design.md"]
        specs = change / "specs"
        if specs.exists():
            normative_paths.extend(sorted(specs.rglob("*.md")))
        for path in normative_paths:
            if path.is_file():
                conflicts.extend(_scan_push_lines(root, path, checkbox_aware=False))
        tasks = change / "tasks.md"
        if tasks.is_file():
            conflicts.extend(_scan_push_lines(root, tasks, checkbox_aware=True))

    for raw_path in plan_paths:
        path = _validated_plan_path(root, raw_path)
        if path.is_file():
            conflicts.extend(_scan_push_lines(root, path, checkbox_aware=True))
    return conflicts


def _load_active_changes(root: Path) -> list[str]:
    completed = subprocess.run(
        ["openspec", "list", "--json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("openspec list --json did not return a top-level object")
    changes = payload.get("changes")
    if not isinstance(changes, list):
        raise ValueError("openspec list --json did not return a changes list")
    return [
        item["name"]
        for item in changes
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item.get("status") not in {"completed", "archived"}
    ]


def _active_plan_paths(root: Path, active_changes: list[str]) -> tuple[list[Path], list[str]]:
    plans: list[Path] = []
    seen_plans: set[Path] = set()
    errors: list[str] = []
    root_resolved = root.resolve()
    for name in active_changes:
        comet = _validated_change_path(root, name) / ".comet.yaml"
        if not comet.is_file():
            continue
        try:
            lines = comet.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            errors.append(f"{_relative_path(root, comet)}: {exc}")
            continue
        plan_values = [
            line.split(":", 1)[1].strip()
            for line in lines
            if line.startswith("plan:")
        ]
        if len(plan_values) > 1:
            errors.append(f"{_relative_path(root, comet)}: duplicate plan field")
            continue
        if not plan_values or plan_values[0] in {"", "null"}:
            continue
        plan = (root / plan_values[0]).resolve()
        try:
            plan.relative_to(root_resolved)
        except ValueError:
            errors.append(f"{_relative_path(root, comet)}: plan escapes repository root")
            continue
        if not plan.is_file():
            errors.append(
                f"{_relative_path(root, comet)}: plan does not exist: {plan_values[0]}"
            )
            continue
        if plan not in seen_plans:
            seen_plans.add(plan)
            plans.append(plan)
    return plans, errors


def _required_platform_checks(policy: dict[str, object]) -> list[str]:
    checks: list[str] = []
    goal = policy.get("goal")
    change = policy.get("change")
    git = policy.get("git")
    agents = policy.get("agents")
    if isinstance(goal, dict) and goal.get("require_active_before_write") is True:
        checks.append("goal_status_active")
    if isinstance(goal, dict) and goal.get("revoke_writer_on_user_prompt") is True:
        checks.append("writer_authorization_after_latest_user_prompt")
    if isinstance(change, dict) and change.get("require_explicit_selection") is True:
        checks.append("explicit_active_change_selection")
    if isinstance(git, dict) and git.get("commit") == "prompt":
        checks.append("local_commit_authorization")
    if isinstance(agents, dict) and agents.get("max_writers") == 1:
        checks.append("single_writer")
    if isinstance(agents, dict) and agents.get("require_parent_verification") is True:
        checks.append("parent_verification")
    return checks


def _agents_push_conflicts(root: Path, push_denied: bool) -> list[str]:
    if not push_denied:
        return []
    agents_path = root / "AGENTS.md"
    if not agents_path.is_file():
        return []
    allow_patterns = (
        re.compile(r"允许.{0,40}(?:\bpush\b|推送)", re.IGNORECASE),
        re.compile(r"(?:automatic|auto)\s+push.{0,20}(?:allow|允许)", re.IGNORECASE),
        re.compile(r"(?:\bpush\b|推送).{0,30}(?:无需|不需).{0,10}(?:授权|询问)", re.IGNORECASE),
        re.compile(r"\bpush\s*:\s*allow\b", re.IGNORECASE),
    )
    errors: list[str] = []
    lines = agents_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, text in enumerate(lines):
        candidate = text
        if index + 1 < len(lines) and re.search(
            r"(?:允许|allow).{0,30}(?:自动|automatic|auto)", text, re.IGNORECASE
        ):
            candidate = f"{text} {lines[index + 1]}"
        if any(marker in candidate for marker in ("不允许", "禁止", "不得")):
            continue
        if any(pattern.search(candidate) for pattern in allow_patterns):
            errors.append(
                f"AGENTS.md:{index + 1}: explicitly allows automatic push while policy denies push"
            )
    return errors


def audit_project(
    root: Path, active_changes: list[str] | None = None
) -> dict[str, object]:
    """Audit the policy, platform-required checks, and active push gates."""
    root = root.resolve()
    errors: list[str] = []
    policy: dict[str, object] = {}
    policy_errors: list[str] = []
    policy_path = root / ".comet/policy.yaml"
    try:
        policy = parse_policy(policy_path.read_text(encoding="utf-8"))
        policy_errors = validate_policy(policy)
    except (OSError, ValueError) as exc:
        policy_errors = [f".comet/policy.yaml: {exc}"]
    errors.extend(policy_errors)

    git = policy.get("git")
    push_denied = isinstance(git, dict) and git.get("push") == "deny"
    errors.extend(_agents_push_conflicts(root, push_denied))

    if active_changes is None:
        try:
            active_changes = _load_active_changes(root)
        except (
            OSError,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            errors.append(f"cannot load active OpenSpec changes: {exc}")
            active_changes = []

    validated_changes: list[str] = []
    for name in active_changes:
        try:
            _validated_change_path(root, name)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            validated_changes.append(name)

    plans, plan_errors = _active_plan_paths(root, validated_changes)
    errors.extend(plan_errors)
    try:
        conflicts = find_push_conflicts(root, validated_changes, plans)
    except OSError as exc:
        errors.append(f"cannot scan active artifacts: {exc}")
        conflicts = []
    return {
        "policy_valid": not policy_errors,
        "required_platform_checks": _required_platform_checks(policy),
        "push_denied": push_denied,
        "active_change_push_conflicts": conflicts,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    report = audit_project(args.root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    failed = (
        not report["policy_valid"]
        or not report["push_denied"]
        or bool(report["active_change_push_conflicts"])
        or bool(report["errors"])
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
