#!/usr/bin/env python3
"""Tests for the repository-local Comet project policy audit."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from tools.check_comet_project_policy import (
    audit_project,
    find_push_conflicts,
    parse_policy,
    validate_policy,
)


class CometProjectPolicyTests(unittest.TestCase):
    automatic_decisions = [
        "in-scope-reversible-technical",
        "backward-compatible-internal",
    ]
    required_user_confirmations = [
        "archive",
        "push",
        "publish",
        "destructive",
        "irreversible",
        "new-capability",
        "scope-growth-over-50-percent",
    ]
    valid_policy = """\
schema_version: 1
enforcement: strict
goal:
  required: true
  require_active_before_write: true
  revoke_writer_on_user_prompt: true
change:
  require_explicit_selection: true
  allow_first_active_fallback: false
decisions:
  automatic:
    - in-scope-reversible-technical
    - backward-compatible-internal
  require_confirmation:
    - archive
    - push
    - publish
    - destructive
    - irreversible
    - new-capability
    - scope-growth-over-50-percent
git:
  commit: prompt
  push: deny
agents:
  max_writers: 1
  reviewer_read_only: true
  sidecar_read_only: true
  require_parent_verification: true
resources:
  runner:
    - python3
    - tools/run_guarded.py
  heavy_lock: build/resource-guard/heavy.lock
  monitor_owned_tree_rss: true
rom:
  require_verified_snapshot: true
  prefer_latest_verified_snapshot: true
  require_single_input: true
  require_zero_input_control: true
evidence:
  immutable_runs: true
  require_unique_run_id: true
  require_manifest: true
  require_input_hashes: true
  preserve_superseded_results: true
limits:
  stop_after_no_new_evidence_cycles: 3
  stop_after_unchanged_waits: 3
"""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        policy = self.root / ".comet/policy.yaml"
        policy.parent.mkdir(parents=True)
        policy.write_text(self.valid_policy, encoding="utf-8")
        (self.root / "AGENTS.md").write_text(
            "push 始终需要单独授权。\n", encoding="utf-8"
        )

    def write_change(self, name: str, tasks: str = "") -> None:
        change = self.root / "openspec/changes" / name
        change.mkdir(parents=True, exist_ok=True)
        (change / "tasks.md").write_text(tasks, encoding="utf-8")

    def write_change_file(self, name: str, relative: str, text: str) -> None:
        path = self.root / "openspec/changes" / name / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_cli(
        self, openspec_payload: str, arguments: list[str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        executable = self.root / "bin/openspec"
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"sys.stdout.write({openspec_payload!r})\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        report_path = self.root / "audit.json"
        report_path.unlink(missing_ok=True)
        env = os.environ.copy()
        env["PATH"] = f"{executable.parent}{os.pathsep}{env.get('PATH', '')}"
        script = Path(__file__).resolve().parents[1] / "tools/check_comet_project_policy.py"
        command = [sys.executable, str(script), "--root", str(self.root)]
        if arguments is None:
            command.extend(["--json", str(report_path)])
        else:
            command.extend(arguments)
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def write_saved_report(
        self, path: Path, **overrides: object
    ) -> dict[str, object]:
        policy_path = self.root / ".comet/policy.yaml"
        payload: dict[str, object] = {
            "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
            "generated_at": "2026-07-16T00:00:00Z",
            "policy_valid": True,
            "required_platform_checks": [],
            "automatic_decisions": self.automatic_decisions,
            "required_user_confirmations": self.required_user_confirmations,
            "push_denied": True,
            "active_change_push_conflicts": [],
            "errors": [],
        }
        payload.update(overrides)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def test_parses_current_schema_scalars_and_runner_list(self) -> None:
        policy = parse_policy(self.valid_policy)

        self.assertEqual(policy["schema_version"], 1)
        self.assertIs(policy["goal"]["required"], True)
        self.assertEqual(
            policy["resources"]["runner"],
            ["python3", "tools/run_guarded.py"],
        )
        self.assertEqual(validate_policy(policy), [])

    def test_requires_exact_decision_lists_and_order(self) -> None:
        decision_block = (
            "decisions:\n"
            "  automatic:\n"
            "    - in-scope-reversible-technical\n"
            "    - backward-compatible-internal\n"
            "  require_confirmation:\n"
            "    - archive\n"
            "    - push\n"
            "    - publish\n"
            "    - destructive\n"
            "    - irreversible\n"
            "    - new-capability\n"
            "    - scope-growth-over-50-percent\n"
        )
        variants = {
            "missing": self.valid_policy.replace(decision_block, ""),
            "mistyped": self.valid_policy.replace(
                "  automatic:\n"
                "    - in-scope-reversible-technical\n"
                "    - backward-compatible-internal\n",
                "  automatic: in-scope-reversible-technical\n",
            ),
            "automatic reordered": self.valid_policy.replace(
                "    - in-scope-reversible-technical\n"
                "    - backward-compatible-internal\n",
                "    - backward-compatible-internal\n"
                "    - in-scope-reversible-technical\n",
            ),
            "confirmation reordered": self.valid_policy.replace(
                "    - archive\n    - push\n",
                "    - push\n    - archive\n",
            ),
            "unknown item": self.valid_policy.replace(
                "    - backward-compatible-internal\n",
                "    - backward-compatible-internal\n    - undocumented-choice\n",
            ),
            "high risk automatic": self.valid_policy.replace(
                "    - backward-compatible-internal\n",
                "    - backward-compatible-internal\n    - destructive\n",
            ),
        }

        for reason, document in variants.items():
            with self.subTest(reason=reason):
                self.assertTrue(validate_policy(parse_policy(document)))

    def test_rejects_unknown_duplicate_and_mistyped_policy_fields(self) -> None:
        unknown = self.valid_policy.replace("git:\n", "unknown: true\ngit:\n")
        duplicate = self.valid_policy + "\ngit:\n  push: deny\n"
        mistyped = self.valid_policy.replace("max_writers: 1", "max_writers: many")

        self.assertTrue(
            any("unknown" in item for item in validate_policy(parse_policy(unknown)))
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_policy(duplicate)
        self.assertTrue(
            any(
                "max_writers" in item
                for item in validate_policy(parse_policy(mistyped))
            )
        )

    def test_rejects_tabs_bad_indentation_empty_keys_and_quoted_scalars(self) -> None:
        invalid_documents = {
            "tab": "goal:\n\trequired: true\n",
            "indent": "goal:\n    required: true\n",
            "empty key": ": true\n",
            "quoted": 'enforcement: "strict"\n',
        }

        for reason, text in invalid_documents.items():
            with self.subTest(reason=reason):
                with self.assertRaises(ValueError):
                    parse_policy(text)

    def test_requires_exact_schema_and_denied_push(self) -> None:
        activation = self.valid_policy.replace(
            "goal:\n",
            "activation:\n  require_policy_support: true\n"
            "  unsupported_behavior: fail\n"
            "goal:\n",
        )
        allowed_push = self.valid_policy.replace("push: deny", "push: allow")
        missing_goal = self.valid_policy.replace(
            "goal:\n"
            "  required: true\n"
            "  require_active_before_write: true\n"
            "  revoke_writer_on_user_prompt: true\n",
            "",
        )

        self.assertTrue(
            any(
                "activation" in item and "unsupported" in item
                for item in validate_policy(parse_policy(activation))
            )
        )
        self.assertTrue(
            any(
                "git.push" in item
                for item in validate_policy(parse_policy(allowed_push))
            )
        )
        self.assertTrue(
            any("goal" in item for item in validate_policy(parse_policy(missing_goal)))
        )

    def test_reports_only_active_normative_or_unfinished_push_requirements(self) -> None:
        self.write_change(
            "demo", tasks="- [x] 历史提交并推送\n- [ ] 完成并推送远端\n"
        )
        self.write_change_file(
            "demo", "proposal.md", "阶段成果必须提交并推送。\n"
        )
        plan = self.root / "docs/superpowers/plans/demo.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(
            "- [x] 历史 push\n"
            "  git push origin old\n"
            "- [ ] Verify and push\n"
            "  git push origin demo\n",
            encoding="utf-8",
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [plan])
        locations = {(item["path"], item["line"]) for item in conflicts}

        self.assertIn(("openspec/changes/demo/tasks.md", 2), locations)
        self.assertIn(("openspec/changes/demo/proposal.md", 1), locations)
        self.assertIn(("docs/superpowers/plans/demo.md", 3), locations)
        self.assertIn(("docs/superpowers/plans/demo.md", 4), locations)
        self.assertNotIn(("openspec/changes/demo/tasks.md", 1), locations)
        self.assertNotIn(("docs/superpowers/plans/demo.md", 2), locations)

    def test_completed_checkbox_does_not_hide_push_after_heading(self) -> None:
        self.write_change(
            "demo",
            tasks="- [x] 历史 push\n\n## 发布\n\n```sh\ngit push origin demo\n```\n",
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("openspec/changes/demo/tasks.md", 6)],
        )

    def test_completed_checkbox_exempts_its_unindented_code_block_until_section_boundary(
        self,
    ) -> None:
        plan = self.root / "docs/plan.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(
            "- [x] **Step 1: historical delivery**\n\n"
            "当前分支 push 状态也不在本计划中声称。\n"
            "不再运行旧计划中的 git add/push 命令。\n\n"
            "```sh\n"
            "git commit -m done\n"
            "git push origin historical\n"
            "```\n\n"
            "---\n"
            "git push origin future\n",
            encoding="utf-8",
        )
        conflicts = find_push_conflicts(self.root, [], [plan])
        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("docs/plan.md", 12)],
        )

    def test_completed_checkbox_ignores_section_markers_inside_fenced_code(
        self,
    ) -> None:
        plan = self.root / "docs/fenced-plan.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(
            "- [x] **Step 1: historical delivery**\n\n"
            "````sh\n"
            "---\n"
            "### comment\n"
            "- [ ] git push origin fenced-example\n"
            "```\n"
            "git push origin historical-short-close\n"
            "~~~~\n"
            "git push origin historical-wrong-close\n"
            "`````\n\n"
            "   ~~~sh\n"
            "___\n"
            "### comment\n"
            "~~\n"
            "git push origin historical-short-tilde-close\n"
            "````\n"
            "git push origin historical-wrong-tilde-close\n"
            "   ~~~~\n\n"
            "- [ ] git push origin future\n",
            encoding="utf-8",
        )

        conflicts = find_push_conflicts(self.root, [], [plan])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("docs/fenced-plan.md", 22)],
        )

    def test_commonmark_section_boundaries_end_completed_checkbox_state(
        self,
    ) -> None:
        boundaries = {
            "asterisk": "***",
            "underscore": "___",
            "spaced_hyphen": "- - -",
            "three_space_thematic_break": "   * * *",
            "empty_atx_heading": "###",
        }
        for name, boundary in boundaries.items():
            with self.subTest(boundary=name):
                plan = self.root / f"docs/{name}.md"
                plan.parent.mkdir(parents=True, exist_ok=True)
                plan.write_text(
                    "- [x] historical delivery\n"
                    f"{boundary}\n"
                    "git push origin future\n",
                    encoding="utf-8",
                )

                conflicts = find_push_conflicts(self.root, [], [plan])

                self.assertEqual(
                    [(item["path"], item["line"]) for item in conflicts],
                    [(f"docs/{name}.md", 3)],
                )

        indented = self.root / "docs/four-space-thematic-break.md"
        indented.write_text(
            "- [x] historical delivery\n"
            "    ***\n"
            "git push origin historical\n"
            "- [ ] git push origin future\n",
            encoding="utf-8",
        )
        conflicts = find_push_conflicts(self.root, [], [indented])
        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("docs/four-space-thematic-break.md", 4)],
        )

    def test_unfinished_checkbox_reports_push_inside_fenced_code(self) -> None:
        plan = self.root / "docs/unfinished-fenced-plan.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(
            "- [ ] future delivery\n"
            "```sh\n"
            "git push origin future\n"
            "```\n",
            encoding="utf-8",
        )

        conflicts = find_push_conflicts(self.root, [], [plan])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("docs/unfinished-fenced-plan.md", 3)],
        )

    def test_exempts_only_explicit_historical_or_negative_normative_text(self) -> None:
        self.write_change_file(
            "demo",
            "design.md",
            "历史 push 已完成。\n"
            "曾推送到远端。\n"
            "不再运行 git push。\n"
            "不得 push。\n"
            "禁止推送。\n"
            "本步骤不执行 push。\n"
            "交付前必须 push。\n",
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("openspec/changes/demo/design.md", 7)],
        )

    def test_does_not_confuse_game_push_start_with_git_push(self) -> None:
        self.write_change_file(
            "demo",
            "design.md",
            "从 PUSH START 界面继续。\n交付前必须 git push。\n",
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("openspec/changes/demo/design.md", 2)],
        )

    def test_git_push_to_start_remote_is_not_ui_text(self) -> None:
        self.write_change_file(
            "demo", "design.md", "发布时运行 git push start release。\n"
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("openspec/changes/demo/design.md", 1)],
        )

    def test_negative_marker_only_exempts_its_push_clause(self) -> None:
        self.write_change_file(
            "demo",
            "design.md",
            "不得跳过验证；验证后必须推送。\n不得 push；也不执行推送。\n",
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("openspec/changes/demo/design.md", 1)],
        )

    def test_negative_marker_scope_splits_commas_and_connectors(self) -> None:
        self.write_change_file(
            "demo",
            "design.md",
            "不得跳过验证，但验证后必须推送。\n"
            "禁止绕过检查, but then must push release.\n"
            "历史 push 已完成，然后新版本必须 push。\n",
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [
                ("openspec/changes/demo/design.md", 1),
                ("openspec/changes/demo/design.md", 2),
                ("openspec/changes/demo/design.md", 3),
            ],
        )

    def test_exemption_must_directly_govern_push_phrase(self) -> None:
        self.write_change_file(
            "demo",
            "design.md",
            "不得跳过验证并且验证后必须推送。\n"
            "不得不推送。\n"
            "历史 push 已完成；新版本必须 push。\n"
            "不得 push；也不执行推送。\n",
        )
        conflicts = find_push_conflicts(self.root, ["demo"], [])
        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [
                ("openspec/changes/demo/design.md", 1),
                ("openspec/changes/demo/design.md", 2),
                ("openspec/changes/demo/design.md", 3),
            ],
        )

    def test_nested_negative_push_phrase_fails_closed(self) -> None:
        self.write_change_file("demo", "design.md", "禁止不执行推送。\n")

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [("openspec/changes/demo/design.md", 1)],
        )

    def test_only_exempts_contextual_game_ui_push_start(self) -> None:
        self.write_change_file(
            "demo",
            "design.md",
            "从 PUSH START 界面继续。\n"
            "零输入复验 PUSH START、Continue 与标题画面。\n"
            "发布前必须 push start release。\n"
            "发布前必须 PUSH START RELEASE。\n",
        )

        conflicts = find_push_conflicts(self.root, ["demo"], [])

        self.assertEqual(
            [(item["path"], item["line"]) for item in conflicts],
            [
                ("openspec/changes/demo/design.md", 3),
                ("openspec/changes/demo/design.md", 4),
            ],
        )

    def test_agents_separate_authorization_is_compatible_but_auto_push_is_not(self) -> None:
        compatible = audit_project(self.root, active_changes=[])
        self.assertFalse(
            any("AGENTS.md" in item for item in compatible["errors"]),
            compatible,
        )

        (self.root / "AGENTS.md").write_text(
            "允许 writer 自动 push，无需询问。\n", encoding="utf-8"
        )
        conflicting = audit_project(self.root, active_changes=[])

        self.assertTrue(
            any("AGENTS.md" in item for item in conflicting["errors"]),
            conflicting,
        )

    def test_agents_explicit_auto_push_deny_is_compatible(self) -> None:
        (self.root / "AGENTS.md").write_text(
            "不允许 writer 自动 push。\n禁止自动推送。\n不得 push。\n",
            encoding="utf-8",
        )

        report = audit_project(self.root, active_changes=[])

        self.assertFalse(
            any("AGENTS.md" in item for item in report["errors"]), report
        )

    def test_agents_adjacent_line_auto_push_allow_conflicts(self) -> None:
        (self.root / "AGENTS.md").write_text(
            "允许 writer 自动执行以下操作：\n- push\n", encoding="utf-8"
        )

        report = audit_project(self.root, active_changes=[])

        self.assertTrue(
            any("AGENTS.md:1" in item for item in report["errors"]), report
        )

    def test_agents_separate_authorization_and_mixed_clause_semantics(self) -> None:
        (self.root / "AGENTS.md").write_text(
            "允许在获得单独授权后 push。\n"
            "不得跳过验证；允许 writer 自动 push。\n",
            encoding="utf-8",
        )

        report = audit_project(self.root, active_changes=[])

        self.assertEqual(
            [item for item in report["errors"] if "AGENTS.md" in item],
            [
                "AGENTS.md:2: explicitly allows automatic push while policy denies push"
            ],
        )

    def test_audit_surfaces_agents_read_failure_as_structured_error(self) -> None:
        agents = self.root / "AGENTS.md"
        original_read_text = Path.read_text

        def fail_agents_read(path: Path, *args: object, **kwargs: object) -> str:
            if path.resolve() == agents.resolve():
                raise OSError("agents disappeared")
            return original_read_text(path, *args, **kwargs)

        try:
            with mock.patch.object(Path, "read_text", fail_agents_read):
                report = audit_project(self.root, active_changes=[])
        except (OSError, UnicodeError) as exc:
            self.fail(f"audit raised instead of returning a structured error: {exc}")

        self.assertIn("AGENTS.md: cannot read: agents disappeared", report["errors"])

    def test_audit_rejects_non_utf8_agents_text(self) -> None:
        (self.root / "AGENTS.md").write_bytes(b"\xff")

        report = audit_project(self.root, active_changes=[])

        self.assertIn("AGENTS.md: is not valid UTF-8", report["errors"])

    def test_audit_rejects_non_utf8_active_artifact(self) -> None:
        self.write_change("demo")
        artifact = self.root / "openspec/changes/demo/proposal.md"
        artifact.write_bytes(b"\xff")

        try:
            report = audit_project(self.root, active_changes=["demo"])
        except UnicodeError as exc:
            self.fail(f"audit raised instead of returning a structured error: {exc}")

        self.assertIn(
            "cannot scan active artifacts: "
            "openspec/changes/demo/proposal.md: is not valid UTF-8",
            report["errors"],
        )

    def test_audit_rejects_non_utf8_comet_artifact(self) -> None:
        self.write_change("demo")
        comet = self.root / "openspec/changes/demo/.comet.yaml"
        comet.write_bytes(b"\xff")

        report = audit_project(self.root, active_changes=["demo"])

        self.assertIn(
            "openspec/changes/demo/.comet.yaml: is not valid UTF-8",
            report["errors"],
        )

    def test_audit_uses_only_active_changes_and_their_nonempty_comet_plans(self) -> None:
        self.write_change("active", tasks="- [ ] 本地验证\n")
        self.write_change("inactive", tasks="- [ ] 必须 push\n")
        active_plan = self.root / "docs/plans/active.md"
        inactive_plan = self.root / "docs/plans/inactive.md"
        active_plan.parent.mkdir(parents=True)
        active_plan.write_text("- [ ] Verify and push\n", encoding="utf-8")
        inactive_plan.write_text("- [ ] Verify and push\n", encoding="utf-8")
        self.write_change_file(
            "active", ".comet.yaml", "plan: docs/plans/active.md\n"
        )
        self.write_change_file("inactive", ".comet.yaml", "plan: null\n")

        report = audit_project(self.root, active_changes=["active"])
        paths = {
            item["path"] for item in report["active_change_push_conflicts"]
        }

        self.assertIn("docs/plans/active.md", paths)
        self.assertNotIn("docs/plans/inactive.md", paths)
        self.assertNotIn("openspec/changes/inactive/tasks.md", paths)
        self.assertEqual(
            set(report),
            {
                "policy_sha256",
                "generated_at",
                "policy_valid",
                "required_platform_checks",
                "automatic_decisions",
                "required_user_confirmations",
                "push_denied",
                "active_change_push_conflicts",
                "errors",
            },
        )
        self.assertIn("goal_status_active", report["required_platform_checks"])
        self.assertIn("local_commit_authorization", report["required_platform_checks"])
        self.assertEqual(report["automatic_decisions"], self.automatic_decisions)
        self.assertEqual(
            report["required_user_confirmations"],
            self.required_user_confirmations,
        )

    def test_preflight_does_not_require_saved_report_and_emits_fresh_metadata(
        self,
    ) -> None:
        report = audit_project(self.root, active_changes=[])

        expected_hash = hashlib.sha256(
            (self.root / ".comet/policy.yaml").read_bytes()
        ).hexdigest()
        self.assertEqual(report["policy_sha256"], expected_hash)
        self.assertTrue(str(report["generated_at"]).endswith("Z"))
        parsed = datetime.fromisoformat(
            str(report["generated_at"]).replace("Z", "+00:00")
        )
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(report["errors"], [])

    def test_verify_report_rejects_missing_report(self) -> None:
        report = audit_project(
            self.root,
            active_changes=[],
            report_path=self.root / "missing.json",
        )

        self.assertTrue(
            any("saved policy report is missing" in item for item in report["errors"]),
            report,
        )

    def test_verify_report_rejects_malformed_json(self) -> None:
        report_path = self.root / "malformed.json"
        report_path.write_text("{not-json", encoding="utf-8")

        report = audit_project(
            self.root, active_changes=[], report_path=report_path
        )

        self.assertTrue(
            any(
                "saved policy report is not valid JSON" in item
                for item in report["errors"]
            ),
            report,
        )

    def test_verify_report_rejects_non_utf8_json(self) -> None:
        report_path = self.root / "non-utf8.json"
        report_path.write_bytes(b"\xff")

        report = audit_project(
            self.root, active_changes=[], report_path=report_path
        )

        self.assertTrue(
            any(
                "saved policy report is not valid UTF-8" in item
                for item in report["errors"]
            ),
            report,
        )

    def test_verify_report_rejects_stale_policy_hash(self) -> None:
        report_path = self.root / "stale.json"
        self.write_saved_report(report_path, policy_sha256="0" * 64)

        report = audit_project(
            self.root, active_changes=[], report_path=report_path
        )

        self.assertTrue(
            any("policy_sha256 does not match" in item for item in report["errors"]),
            report,
        )

    def test_verify_report_rejects_saved_errors(self) -> None:
        report_path = self.root / "errors.json"
        self.write_saved_report(report_path, errors=["prior audit failed"])

        report = audit_project(
            self.root, active_changes=[], report_path=report_path
        )

        self.assertTrue(
            any(
                "saved policy report errors must be empty" in item
                for item in report["errors"]
            ),
            report,
        )

    def test_verify_report_rejects_saved_push_conflicts(self) -> None:
        report_path = self.root / "conflicts.json"
        self.write_saved_report(
            report_path,
            active_change_push_conflicts=[{"path": "tasks.md", "line": 1}],
        )

        report = audit_project(
            self.root, active_changes=[], report_path=report_path
        )

        self.assertTrue(
            any(
                "saved policy report active_change_push_conflicts must be empty"
                in item
                for item in report["errors"]
            ),
            report,
        )

    def test_verify_report_requires_exact_decision_boundaries(self) -> None:
        cases = {
            "missing automatic": ("automatic_decisions", None),
            "reordered automatic": (
                "automatic_decisions",
                list(reversed(self.automatic_decisions)),
            ),
            "expanded automatic": (
                "automatic_decisions",
                self.automatic_decisions + ["destructive"],
            ),
            "missing confirmation": (
                "required_user_confirmations",
                self.required_user_confirmations[:-1],
            ),
            "reordered confirmation": (
                "required_user_confirmations",
                list(reversed(self.required_user_confirmations)),
            ),
            "expanded confirmation": (
                "required_user_confirmations",
                self.required_user_confirmations + ["routine-formatting"],
            ),
        }

        for reason, (field, value) in cases.items():
            with self.subTest(reason=reason):
                report_path = self.root / f"{reason.replace(' ', '-')}.json"
                payload = self.write_saved_report(report_path)
                if value is None:
                    payload.pop(field)
                else:
                    payload[field] = value
                report_path.write_text(json.dumps(payload), encoding="utf-8")

                report = audit_project(
                    self.root, active_changes=[], report_path=report_path
                )

                self.assertTrue(
                    any(field in item for item in report["errors"]), report
                )

    def test_verify_report_requires_valid_policy_and_denied_push(self) -> None:
        cases = (
            (
                "policy-invalid.json",
                {"policy_valid": False},
                "policy_valid must be true",
            ),
            ("push-allowed.json", {"push_denied": False}, "push_denied must be true"),
        )
        for filename, overrides, expected in cases:
            with self.subTest(filename=filename):
                report_path = self.root / filename
                self.write_saved_report(report_path, **overrides)

                report = audit_project(
                    self.root, active_changes=[], report_path=report_path
                )

                self.assertTrue(
                    any(expected in item for item in report["errors"]), report
                )

    def test_verify_report_accepts_current_passing_report(self) -> None:
        report_path = self.root / "passing.json"
        self.write_saved_report(report_path)

        report = audit_project(
            self.root, active_changes=[], report_path=report_path
        )

        self.assertEqual(report["errors"], [])

    def test_cli_verify_failure_exits_one_with_machine_readable_report(self) -> None:
        missing = self.root / "missing.json"

        completed = self.run_cli(
            '{"changes": []}\n', ["--verify-report", str(missing)]
        )
        report = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertTrue(
            any("saved policy report is missing" in item for item in report["errors"]),
            report,
        )

    def test_cli_verify_valid_report_fails_closed_on_current_audit_error(self) -> None:
        saved = self.root / "passing.json"
        self.write_saved_report(saved)
        (self.root / "AGENTS.md").write_bytes(b"\xff")

        completed = self.run_cli(
            '{"changes": []}\n', ["--verify-report", str(saved)]
        )
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"CLI did not return a machine-readable report: {exc}; "
                f"stderr={completed.stderr!r}"
            )

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("AGENTS.md: is not valid UTF-8", report["errors"])

    def test_rejects_active_change_and_plan_path_escapes(self) -> None:
        outside = Path(self.tempdir.name).parent / f"{self.root.name}-outside"
        outside.mkdir()
        self.addCleanup(lambda: outside.rmdir())
        outside_plan = outside / "plan.md"
        outside_plan.write_text("- [ ] git push origin demo\n", encoding="utf-8")
        self.addCleanup(outside_plan.unlink)

        for name in ("../outside", str(outside)):
            with self.subTest(active_change=name):
                with self.assertRaisesRegex(ValueError, "active change"):
                    find_push_conflicts(self.root, [name], [])

        changes = self.root / "openspec/changes"
        changes.mkdir(parents=True)
        (changes / "linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "active change"):
            find_push_conflicts(self.root, ["linked"], [])

        with self.assertRaisesRegex(ValueError, "plan path"):
            find_push_conflicts(self.root, [], [outside_plan])

        report = audit_project(self.root, active_changes=["../outside"])
        self.assertTrue(any("active change" in item for item in report["errors"]))

    def test_rejects_changes_root_symlink_escape(self) -> None:
        external_tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(external_tempdir.cleanup)
        external_changes = Path(external_tempdir.name) / "changes"
        external_change = external_changes / "demo"
        external_change.mkdir(parents=True)
        (external_change / "design.md").write_text(
            "发布前必须 git push。\n", encoding="utf-8"
        )
        openspec = self.root / "openspec"
        openspec.mkdir()
        (openspec / "changes").symlink_to(
            external_changes, target_is_directory=True
        )

        with self.assertRaisesRegex(ValueError, "active change"):
            find_push_conflicts(self.root, ["demo"], [])

        report = audit_project(self.root, active_changes=["demo"])
        self.assertTrue(any("active change" in item for item in report["errors"]))
        self.assertEqual(report["active_change_push_conflicts"], [])

    def test_rejects_missing_change_and_artifact_symlink_escape(self) -> None:
        outside = Path(self.tempdir.name).parent / f"{self.root.name}-artifact"
        outside.mkdir()
        self.addCleanup(lambda: outside.rmdir())
        proposal = outside / "proposal.md"
        proposal.write_text("必须 push。\n", encoding="utf-8")
        self.addCleanup(proposal.unlink)
        self.write_change("demo")
        local = self.root / "openspec/changes/demo/proposal.md"
        local.symlink_to(proposal)
        with self.assertRaisesRegex(ValueError, "artifact escapes active change"):
            find_push_conflicts(self.root, ["demo"], [])
        missing = audit_project(self.root, active_changes=["missing"])
        self.assertTrue(any("does not exist" in item for item in missing["errors"]))

    def test_audit_rejects_comet_artifact_symlink_escape(self) -> None:
        outside = Path(self.tempdir.name).parent / f"{self.root.name}-comet"
        outside.write_text("plan: docs/outside.md\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        self.write_change("demo")
        comet = self.root / "openspec/changes/demo/.comet.yaml"
        comet.symlink_to(outside)
        report = audit_project(self.root, active_changes=["demo"])
        self.assertTrue(
            any("artifact escapes active change" in item for item in report["errors"]),
            report,
        )

    def test_audit_surfaces_comet_artifact_path_failure(self) -> None:
        self.write_change("demo")

        with mock.patch(
            "tools.check_comet_project_policy._validated_artifact_path",
            side_effect=OSError("artifact path unavailable"),
        ):
            report = audit_project(self.root, active_changes=["demo"])

        self.assertTrue(
            any("artifact path unavailable" in item for item in report["errors"]),
            report,
        )

    def test_audit_surfaces_artifact_read_failure(self) -> None:
        self.write_change("demo")
        self.write_change_file("demo", "proposal.md", "必须 git push。\n")
        artifact = self.root / "openspec/changes/demo/proposal.md"
        original_read_text = Path.read_text

        def fail_artifact_read(path: Path, *args: object, **kwargs: object) -> str:
            if path.resolve() == artifact.resolve():
                raise OSError("artifact disappeared")
            return original_read_text(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", fail_artifact_read):
            report = audit_project(self.root, active_changes=["demo"])

        self.assertTrue(
            any(
                "openspec/changes/demo/proposal.md" in item
                and "artifact disappeared" in item
                for item in report["errors"]
            ),
            report,
        )

    def test_cli_success_stdout_matches_json_file(self) -> None:
        completed = self.run_cli('{"changes": []}\n')

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout,
            (self.root / "audit.json").read_text(encoding="utf-8"),
        )

    def test_cli_invalid_policy_exits_one_with_json_report(self) -> None:
        policy = self.root / ".comet/policy.yaml"
        policy.write_text(
            self.valid_policy.replace("push: deny", "push: allow"), encoding="utf-8"
        )

        completed = self.run_cli('{"changes": []}\n')
        report = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertFalse(report["policy_valid"])
        self.assertEqual(
            completed.stdout,
            (self.root / "audit.json").read_text(encoding="utf-8"),
        )

    def test_cli_push_conflict_exits_one_with_json_report(self) -> None:
        self.write_change("demo", tasks="- [ ] git push origin demo\n")

        completed = self.run_cli(
            '{"changes": [{"name": "demo", "status": "active"}]}\n'
        )
        report = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertTrue(report["active_change_push_conflicts"])
        self.assertEqual(
            completed.stdout,
            (self.root / "audit.json").read_text(encoding="utf-8"),
        )

    def test_cli_malformed_openspec_top_level_exits_one_with_json_report(self) -> None:
        for payload in ("[]\n", '"scalar"\n'):
            with self.subTest(payload=payload.strip()):
                completed = self.run_cli(payload)
                report_path = self.root / "audit.json"

                self.assertEqual(completed.returncode, 1, completed.stderr)
                self.assertTrue(report_path.is_file(), completed.stderr)
                report = json.loads(completed.stdout)
                self.assertTrue(
                    any(
                        "cannot load active OpenSpec changes" in item
                        for item in report["errors"]
                    ),
                    report,
                )
                self.assertEqual(
                    completed.stdout, report_path.read_text(encoding="utf-8")
                )

    def test_cli_rejects_malformed_openspec_change_records(self) -> None:
        payloads = (
            '{"changes": [3]}\n',
            '{"changes": [{"name": 123, "status": "in-progress"}]}\n',
            '{"changes": [{"name": "demo", "status": 3}]}\n',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                completed = self.run_cli(payload)
                report = json.loads(completed.stdout)
                self.assertEqual(completed.returncode, 1, completed.stderr)
                self.assertTrue(
                    any(
                        "cannot load active OpenSpec changes" in item
                        for item in report["errors"]
                    ),
                    report,
                )

    def test_deduplicates_plan_referenced_by_multiple_active_changes(self) -> None:
        plan = self.root / "docs/plans/shared.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("- [ ] git push origin demo\n", encoding="utf-8")
        for name in ("first", "second"):
            self.write_change(name)
            self.write_change_file(
                name, ".comet.yaml", "plan: docs/plans/shared.md\n"
            )

        report = audit_project(self.root, active_changes=["first", "second"])
        shared_conflicts = [
            item
            for item in report["active_change_push_conflicts"]
            if item["path"] == "docs/plans/shared.md"
        ]

        self.assertEqual(len(shared_conflicts), 1, report)


if __name__ == "__main__":
    unittest.main()
