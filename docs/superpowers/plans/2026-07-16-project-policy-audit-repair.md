---
base-ref: 53aead6
execution: subagent-driven-development
---

# 项目 policy 审计剩余边界修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭最终审查发现的三个 fail-open 边界，使 Task 1 可通过独立审查并恢复原项目对齐计划。

**Architecture:** 不再用开放式自然语言分句启发式判断豁免，而只移除明确直接作用于 push 的历史/否定短语，剩余任何 push 都视为冲突。所有 active change 与实际读取 artifact 均在 resolved repository/change 边界内校验；OpenSpec JSON 对每个 change record 严格验证后再筛选状态。

**Tech Stack:** Python 3 标准库、`unittest`、OpenSpec CLI、Git。

## Global Constraints

- 仅修改 `tools/check_comet_project_policy.py` 与 `tests/test_check_comet_project_policy.py`；本计划 checkbox 由父代理在审查通过后单独更新。
- 不修改 Comet 本体、`.comet/policy.yaml`、任何 OpenSpec change、`AGENTS.md`、路线图或用户既有 dirty 文件。
- 严格执行 RED—GREEN—REFACTOR；每个失败边界必须先有因正确原因失败的回归测试。
- 审计器对歧义语义、路径逃逸、缺失 active change 和畸形 OpenSpec record 一律 fail-closed。
- 只创建范围明确的本地 commit；禁止 push、发布、合并和破坏性 Git 操作。

---

### Task 1: 关闭语义、artifact containment 与 OpenSpec record 边界

**Files:**
- Modify: `tests/test_check_comet_project_policy.py`
- Modify: `tools/check_comet_project_policy.py`

**Interfaces:**
- Preserves: `find_push_conflicts(root: Path, active_changes: list[str], plan_paths: list[Path]) -> list[dict[str, object]]`
- Preserves: `audit_project(root: Path, active_changes: list[str] | None = None) -> dict[str, object]`
- Tightens: `_load_active_changes(root: Path) -> list[str]` rejects every malformed record.
- Adds internal containment validation for every active artifact before existence checks or reads.

- [x] **Step 1: 编写三组最小 RED 回归测试**

在现有 `CometProjectPolicyTests` 中加入：

```python
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
                any("cannot load active OpenSpec changes" in item for item in report["errors"]),
                report,
            )
```

另加 `.comet.yaml` 指向仓库外文件的 fixture：

```python
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
```

该测试要求审计返回机器可读 `errors`，不得读取外部文件或抛出未捕获异常。

- [x] **Step 2: 分别运行新增测试并确认 RED 原因**

Run:

```bash
python3 -m unittest \
  tests.test_check_comet_project_policy.CometProjectPolicyTests.test_exemption_must_directly_govern_push_phrase \
  tests.test_check_comet_project_policy.CometProjectPolicyTests.test_rejects_missing_change_and_artifact_symlink_escape \
  tests.test_check_comet_project_policy.CometProjectPolicyTests.test_audit_rejects_comet_artifact_symlink_escape \
  tests.test_check_comet_project_policy.CometProjectPolicyTests.test_cli_rejects_malformed_openspec_change_records -v
```

Expected: 三组均 FAIL；分别表现为 conflict 数量不足、路径未拒绝/缺失 change 静默通过、畸形 record CLI exit 0。

- [x] **Step 3: 用直接短语移除替代开放式豁免 substring**

用只覆盖明确历史/否定 push 短语的表达式替代 `NORMATIVE_EXEMPTIONS` 在 `_normative_push_required` 中的用法：

```python
EXEMPT_PUSH_RE = re.compile(
    r"(?:"
    r"历史\s*(?:git\s+push|push|推送)"
    r"|曾(?:经)?\s*(?:运行\s*)?(?:git\s+push|push|推送)"
    r"|不再运行\s*(?:git\s+push|push|推送)"
    r"|不得\s*(?:运行\s*)?(?:git\s+push|push|推送)"
    r"|禁止\s*(?:运行\s*)?(?:git\s+push|push|推送)"
    r"|不执行\s*(?:git\s+push|push|推送)"
    r")",
    re.IGNORECASE,
)

def _normative_push_required(text: str) -> bool:
    return _contains_push(EXEMPT_PUSH_RE.sub("", text.replace("`", "")))
```

保留 `CLAUSE_SPLIT_RE` 供 AGENTS allow/deny 分句使用；不得用继续枚举连接词来修补 normative 语义。

- [x] **Step 4: 对 active change 和每个实际 artifact 做 containment 校验**

`_validated_change_path` 在 resolved containment 后必须要求 `change.is_dir()`，否则抛出包含 `does not exist` 的 `ValueError`。新增内部 helper：

```python
def _validated_artifact_path(change: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(change)
    except ValueError as exc:
        raise ValueError(f"artifact escapes active change: {path}") from exc
    return resolved
```

在 `proposal.md`、`design.md`、`tasks.md`、`specs/`、spec markdown 和 `.comet.yaml` 的 `exists`/`is_file`/`rglob`/`read_text` 之前调用该 helper。`audit_project` 扫描 artifact 时捕获 `ValueError` 与 `OSError` 并写入 `errors`，不得崩溃或返回成功。

- [x] **Step 5: 严格验证 OpenSpec change record**

把过滤式 list comprehension 改为显式循环：

```python
active: list[str] = []
for index, item in enumerate(changes):
    if not isinstance(item, dict):
        raise ValueError(f"openspec changes[{index}] must be an object")
    name = item.get("name")
    status = item.get("status")
    if not isinstance(name, str) or not name:
        raise ValueError(f"openspec changes[{index}].name must be a nonempty string")
    if not isinstance(status, str) or not status:
        raise ValueError(f"openspec changes[{index}].status must be a nonempty string")
    if status not in {"completed", "archived"}:
        active.append(name)
return active
```

- [x] **Step 6: 运行 GREEN、负向仓库审计与范围检查**

Run:

```bash
python3 -m unittest tests.test_check_comet_project_policy -v
python3 -m py_compile tools/check_comet_project_policy.py
python3 tools/check_comet_project_policy.py --root . --json build/comet-project-policy-repair.json
git diff --check
```

Expected: 单元测试全部 PASS；compile 和 diff check exit 0。当前仓库审计仍预期 exit 1，原因只包含现有 unsupported `activation`、真实 active push 冲突或明确的项目 policy 问题；`PUSH START` UI 冲突数为 0。

- [x] **Step 7: 仅提交工具与测试**

```bash
git add tools/check_comet_project_policy.py tests/test_check_comet_project_policy.py
git diff --cached --name-only
git commit -m "fix(comet): close strict audit fail-open edges"
```

Expected staged paths exactly equal the two files above；不得 push。

Task 1 implementation commits: `47f7cf1`, `1b12124`；parent verification 31/31 PASS；task review `Spec ✅ / Quality ✅`。

---

### Task 2: 正确保留已完成 Markdown section 的历史 push

**Files:**
- Modify: `tests/test_check_comet_project_policy.py`
- Modify: `tools/check_comet_project_policy.py`

**Interfaces:**
- Preserves: `_scan_push_lines(root: Path, path: Path, checkbox_aware: bool) -> list[dict[str, object]]`
- Changes internal state boundary: checkbox 状态持续到下一个 checkbox、Markdown heading 或 horizontal rule，而不是被普通零缩进段落/代码围栏重置。

- [x] **Step 1: 编写已完成 section 历史代码块 RED**

```python
def test_completed_checkbox_exempts_its_unindented_code_block_until_section_boundary(self) -> None:
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
        "---\n\n"
        "### Next task\n\n"
        "- [ ] git push origin future\n",
        encoding="utf-8",
    )
    conflicts = find_push_conflicts(self.root, [], [plan])
    self.assertEqual(
        [(item["path"], item["line"]) for item in conflicts],
        [("docs/plan.md", 15)],
    )
```

- [x] **Step 2: 运行聚焦测试并确认 RED**

Run:

```bash
python3 -m unittest \
  tests.test_check_comet_project_policy.CometProjectPolicyTests.test_completed_checkbox_exempts_its_unindented_code_block_until_section_boundary -v
```

Expected: FAIL；实际额外报告 completed section 内的历史 `git push`，证明当前 indent reset 过早。

- [x] **Step 3: 用 Markdown section 边界替代普通缩进重置**

新增：

```python
MARKDOWN_SECTION_BOUNDARY_RE = re.compile(r"^\s*(?:#{1,6}\s+|-{3,}\s*$)")
```

在 `_scan_push_lines` 中：

```python
checkbox = CHECKBOX_RE.match(text) if checkbox_aware else None
if checkbox:
    checkbox_unfinished = checkbox.group(1) == " "
elif checkbox_aware and MARKDOWN_SECTION_BOUNDARY_RE.match(text):
    checkbox_unfinished = None
```

删除 `checkbox_indent` 及“普通非空行同级/低缩进即重置”的逻辑。新 checkbox 始终覆盖前一状态；heading/horizontal rule 在扫描该行 push 之前重置。不得用具体行号或当前计划文件名硬编码。

- [x] **Step 4: 运行 GREEN 与真实仓库分类验证**

Run:

```bash
python3 -m unittest tests.test_check_comet_project_policy -v
python3 -m py_compile tools/check_comet_project_policy.py
python3 tools/check_comet_project_policy.py --root . --json build/comet-project-policy-checkbox-fixed.json
git diff --check
```

Expected: tests、compile、diff check 通过；仓库审计仍因 `activation` 与未来/未完成 push 要求 exit 1，但不再报告当前 scenario 计划中已完成 Step 的历史代码块或历史说明。全局约束与未完成 Task 6/7/8 push 仍必须报告。

- [x] **Step 5: 仅提交工具与测试并通过独立审查**

```bash
git add tools/check_comet_project_policy.py tests/test_check_comet_project_policy.py
git diff --cached --name-only
git commit -m "fix(comet): preserve completed plan history"
```

Expected staged paths exactly equal the two文件；不得 push。父代理复验后派全新只读 reviewer，只有 `Spec ✅ / Quality ✅` 且无 Critical/Important 才能完成本 Task。

Task 2 implementation commits: `64a9f40`, `be2099e`；parent verification 35/35 PASS；task review `Spec ✅ / Quality ✅`。
