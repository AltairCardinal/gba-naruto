#!/usr/bin/env python3
"""Tests for the repository-local Comet project policy audit."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_comet_project_policy import (
    audit_project,
    find_push_conflicts,
    parse_policy,
    validate_policy,
)


class CometProjectPolicyTests(unittest.TestCase):
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

    def test_parses_current_schema_scalars_and_runner_list(self) -> None:
        policy = parse_policy(self.valid_policy)

        self.assertEqual(policy["schema_version"], 1)
        self.assertIs(policy["goal"]["required"], True)
        self.assertEqual(
            policy["resources"]["runner"],
            ["python3", "tools/run_guarded.py"],
        )
        self.assertEqual(validate_policy(policy), [])

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
                "policy_valid",
                "required_platform_checks",
                "push_denied",
                "active_change_push_conflicts",
                "errors",
            },
        )
        self.assertIn("goal_status_active", report["required_platform_checks"])
        self.assertIn("local_commit_authorization", report["required_platform_checks"])


if __name__ == "__main__":
    unittest.main()
