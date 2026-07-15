---
design-doc: docs/superpowers/specs/2026-07-16-project-completion-policy-alignment-design.md
base-ref: 72d4e35
execution: subagent-driven-development
---

# 项目完成流程与 Comet 约束对齐实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 不修改 Comet 本体，在当前仓库内建立可执行的 policy 预检，消除四个逆向 change 与 Goal 的 push 冲突，使现有 Comet build 能继续运行。

**Architecture:** 用一个无第三方依赖的 Python 工具严格解析项目 `.comet/policy.yaml`，输出机器可读的 required platform checks，并审计 active OpenSpec artifacts 与未完成计划中的 push 冲突。随后以该工具的失败结果驱动 policy、change、Design Doc 和计划的最小文本对齐，最后把预检加入当前及最终验收命令。

**Tech Stack:** Python 3 标准库、`unittest`、OpenSpec CLI、Git、现有 Comet artifacts。

## Global Constraints

- 不修改、重装、重新打包或升级 Comet。
- 不修改 Codex 桌面会话、CLI、PATH 或全局技能目录。
- 不覆盖或提交用户既有的 `AGENTS.md`、`docs/sequel-roadmap.md`、治理文档及 `build/` 产物。
- 只创建范围明确的本地 commit；禁止 push、发布、合并和破坏性 Git 操作。
- 所有功能代码严格执行 RED—GREEN—REFACTOR。
- 项目预检不能声称能读取平台 Goal 状态；它必须输出 required platform checks，由父代理调用平台工具核验。
- 已完成任务和明确标注为历史事实的 push 记录保留；未完成任务、proposal、design、spec 和全局约束不得要求 push。

---

### Task 1: 严格项目 policy parser 与 push 冲突审计

**Files:**
- Create: `tools/check_comet_project_policy.py`
- Create: `tests/test_check_comet_project_policy.py`

**Interfaces:**
- Produces: `parse_policy(text: str) -> dict[str, object]`
- Produces: `validate_policy(policy: dict[str, object]) -> list[str]`
- Produces: `find_push_conflicts(root: Path, active_changes: list[str], plan_paths: list[Path]) -> list[dict[str, object]]`
- Produces: `audit_project(root: Path, active_changes: list[str] | None = None) -> dict[str, object]`
- CLI: `python3 tools/check_comet_project_policy.py [--root PATH] [--json PATH]`

- [x] **Step 1: 编写 parser 与 schema RED 测试**

在 `tests/test_check_comet_project_policy.py` 创建临时仓库 fixture，覆盖：

```python
def test_rejects_unknown_duplicate_and_mistyped_policy_fields(self):
    unknown = self.valid_policy.replace("git:\n", "unknown: true\ngit:\n")
    duplicate = self.valid_policy + "\ngit:\n  push: deny\n"
    mistyped = self.valid_policy.replace("max_writers: 1", "max_writers: many")
    self.assertTrue(any("unknown" in item for item in validate_policy(parse_policy(unknown))))
    with self.assertRaisesRegex(ValueError, "duplicate"):
        parse_policy(duplicate)
    self.assertTrue(any("max_writers" in item for item in validate_policy(parse_policy(mistyped))))
```

fixture 的有效 policy 必须与项目 schema 一致：`schema_version=1`、`enforcement=strict`，并包含 `goal/change/git/agents/resources/rom/evidence/limits`；不得包含 `activation`。

- [x] **Step 2: 运行测试并确认 RED**

Run:

```bash
python3 -m unittest tests.test_check_comet_project_policy -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.check_comet_project_policy'`。

- [x] **Step 3: 编写 push 冲突与历史豁免 RED 测试**

增加 fixture：

```python
def test_reports_only_active_normative_or_unfinished_push_requirements(self):
    self.write_change("demo", tasks="- [x] 历史提交并推送\n- [ ] 完成并推送远端\n")
    self.write_change_file("demo", "proposal.md", "阶段成果必须提交并推送。\n")
    plan = self.root / "docs/superpowers/plans/demo.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("- [x] 历史 push\n  git push origin old\n- [ ] Verify and push\n  git push origin demo\n")
    conflicts = find_push_conflicts(self.root, ["demo"], [plan])
    locations = {(item["path"], item["line"]) for item in conflicts}
    self.assertIn(("openspec/changes/demo/tasks.md", 2), locations)
    self.assertIn(("openspec/changes/demo/proposal.md", 1), locations)
    self.assertIn(("docs/superpowers/plans/demo.md", 3), locations)
    self.assertIn(("docs/superpowers/plans/demo.md", 4), locations)
    self.assertNotIn(("openspec/changes/demo/tasks.md", 1), locations)
    self.assertNotIn(("docs/superpowers/plans/demo.md", 2), locations)
```

另外覆盖：policy 中存在 `activation.require_policy_support` 必须报 unsupported；`git.push` 不是 `deny` 必须失败；当前 AGENTS 的“push 始终需要单独授权”与 `deny` 不冲突；显式允许自动 push 必须冲突。

- [x] **Step 4: 实现最小 parser、schema 和审计器**

实现受限 YAML：

- 仅支持两空格缩进的 map、布尔、整数、未引号字符串和 `- value` 列表；
- 忽略空行和整行注释；
- 重复键、跳级缩进、tab、空 key 和当前 schema 外的结构抛出 `ValueError`；
- `validate_policy` 精确校验设计文档列出的字段和枚举；
- `audit_project` 通过 `openspec list --json` 获取 active change，测试可显式传入列表；
- 未显式传入 `plan_paths` 时，只读取每个 active change `.comet.yaml` 中非空 `plan` 字段指向的计划；不得扫描全部历史 plan；
- 计划扫描跟踪最近 checkbox 状态，使已完成 section 内的历史 `git push` 不误报；
- proposal/design/spec 的 push 词只在带 `历史`、`曾`、`不再运行`、`不得`、`禁止` 或 `不执行` 时豁免；
- 输出 JSON 中包含 `policy_valid`、`required_platform_checks`、`push_denied`、`active_change_push_conflicts`、`errors`。

- [x] **Step 5: 运行 GREEN 与 CLI fixture 测试**

Run:

```bash
python3 -m unittest tests.test_check_comet_project_policy -v
python3 -m py_compile tools/check_comet_project_policy.py
```

Expected: all tests PASS，compile exit 0。

- [x] **Step 6: 对当前仓库运行预检并确认它因真实冲突失败**

Run:

```bash
python3 tools/check_comet_project_policy.py --root . --json build/comet-project-policy-before.json
```

Expected: exit 1；报告至少包含不受支持的 `activation` 和 active artifacts 中的强制 push，证明工具不是空检查。

- [x] **Step 7: 提交工具与测试**

```bash
git add tools/check_comet_project_policy.py tests/test_check_comet_project_policy.py
git commit -m "test(comet): audit project policy conflicts"
```

#### 历史阻塞与解除记录（2026-07-16）

Task 1 已完成两轮有界修复，代码提交为 `e06966a`、`c3a7eab`、`656080c`。父代理复验 25/25 单元测试、`py_compile` 和 `git diff --check` 通过；当前仓库负向审计仍正确报告 34 条真实 push 冲突与不受支持的 `activation`，并且没有把游戏 UI `PUSH START` 误报为 push 门禁。

初次最终只读审查未批准，修复轮次达到 `2/2` 后曾停止进入 Task 2/3。当时剩余 Important：

1. 否定/历史豁免仍可能被“并且”连接或“不得不推送”等语义绕过，未严格证明豁免词支配 push 分句。
2. active change 的子 artifact symlink、缺失 change 目录和 `.comet.yaml` 读取边界尚未全部 fail-closed。
3. `openspec list --json` 的 `changes` 数组中畸形成员会被静默丢弃，可能把无效 active change 集合解释为空并成功退出。

上述问题已通过独立修复计划 `docs/superpowers/plans/2026-07-16-project-policy-audit-repair.md` 关闭。补充提交为 `47f7cf1`、`1b12124`、`64a9f40`、`be2099e`；父代理最终复验 35/35 单元测试、`py_compile` 与 `git diff --check` 通过，真实仓库审计只保留 28 条未来/未完成 push 冲突和既有 unsupported `activation`，已完成历史与 UI `PUSH START` 不再误报。两个修复 Task 均获独立 reviewer `Spec ✅ / Quality ✅`，因此解除阻塞并进入 Task 2。

---

### Task 2: 对齐 policy 与四个 active change

**Files:**
- Modify: `.comet/policy.yaml`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/proposal.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/design.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`
- Modify: `openspec/changes/upgrade-remaining-runtime-banks/design.md`
- Modify: `openspec/changes/upgrade-remaining-runtime-banks/tasks.md`
- Modify: `openspec/changes/upgrade-remaining-runtime-banks/specs/remaining-runtime-bank-verification/spec.md`
- Modify: `openspec/changes/close-reverse-engineering-completion-gaps/proposal.md`
- Modify: `openspec/changes/close-reverse-engineering-completion-gaps/tasks.md`
- Modify: `openspec/changes/close-reverse-engineering-completion-gaps/specs/reverse-engineering-completion-gate/spec.md`
- Modify: `docs/superpowers/specs/2026-07-15-scenario-41-battle-runtime-design.md`
- Modify: `docs/superpowers/plans/2026-07-15-scenario-41-battle-runtime.md`

**Interfaces:**
- Consumes: Task 1 project policy audit.
- Produces: policy-valid repository with no active or unfinished push completion requirements.

- [x] **Step 1: 保存当前项目 RED 结果摘要**

从 `build/comet-project-policy-before.json` 记录冲突总数和路径到实现报告；不得提交 `build/` 文件。

- [x] **Step 2: 最小修改项目 policy**

删除 `.comet/policy.yaml` 的 `activation` 段，并把头部注释改为：

```yaml
# Comet 项目级策略。由 Goal、AGENTS.md 和 tools/check_comet_project_policy.py
# 在当前仓库内共同执行；不要求 Comet 插件原生解析。
```

保留 `schema_version: 1`、`enforcement: strict` 和其余项目字段；`git.commit: prompt`、`git.push: deny` 不变。

- [x] **Step 3: 对齐 scenario 41 当前与未来任务**

把 proposal、design、Design Doc 和计划全局约束中的“提交并推送”改为“创建范围明确的本地 commit”。

对当前计划：

- 已完成任务中的历史 push 命令和标题保留；
- 未完成 Task 6/7/8 的标题、命令和验收删除 push，只保留本地 commit；
- 最终 sync step 不得包含 `git push`；
- OpenSpec task 7.4 改为检查状态并创建聚焦本地 commit。

- [x] **Step 4: 对齐剩余 bank 与最终 completion change**

把所有未完成批次和 normative spec 的 push 要求改为本地 commit + 本地 commit hash 可追溯。最终 completion gate 不得要求远端分支或“已推送 commit”，但仍必须要求同一 commit 上的测试、构建、mGBA 和文档一致性。

`verify-levels-runtime` 没有 push 门禁，只由预检确认，不制造无关 diff。

- [x] **Step 5: 运行项目 GREEN**

Run:

```bash
python3 tools/check_comet_project_policy.py --root . --json build/comet-project-policy-after.json
```

Expected: exit 0；`policy_valid=true`、`push_denied=true`、`active_change_push_conflicts=[]`，并输出 Goal active、commit authorization 等 required platform checks。

- [x] **Step 6: 运行四个 change 的严格验证**

Run:

```bash
openspec validate close-scenario-41-battle-runtime --strict
openspec validate verify-levels-runtime --strict
openspec validate upgrade-remaining-runtime-banks --strict
openspec validate close-reverse-engineering-completion-gaps --strict
git diff --check
```

Expected: all commands exit 0；不得把其他 dirty 文件混入验证结论。

- [x] **Step 7: 提交项目对齐**

仅暂存本 Task 列出的 policy/change/design/plan 文件和本计划 checkbox 更新：

```bash
git commit -m "chore(comet): align project gates with local-only delivery"
```

Implementation commit: `fe93ab9`；parent policy audit GREEN；四个 OpenSpec strict validate PASS；task review `Spec ✅ / Quality ✅`。Minor 报告分类笔误已在 ignored report 中更正。

---

### Task 3: 接入最终门禁并恢复真实 Comet 断点

**Files:**
- Modify: `tools/check_comet_project_policy.py`
- Modify: `tests/test_check_comet_project_policy.py`
- Modify: `openspec/changes/close-reverse-engineering-completion-gaps/tasks.md`
- Modify: `openspec/changes/close-reverse-engineering-completion-gaps/specs/reverse-engineering-completion-gate/spec.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/.comet/subagent-progress.md`
- Modify: `docs/superpowers/plans/2026-07-16-project-completion-policy-alignment.md`

**Interfaces:**
- Consumes: passing project policy audit and commit `f252dbd`.
- Produces: final completion gate requires a fresh policy report; current subagent checkpoint says implemented-but-unreviewed.

- [ ] **Step 1: 为最终 policy report 门禁编写 RED fixture**

扩展 `tests/test_check_comet_project_policy.py`：`audit_project` 接收可选 `report_path`，当 final-gate 模式下报告缺失、报告的 policy hash 不等于当前文件或报告含 errors 时失败；普通 preflight 不要求已有报告。

- [ ] **Step 2: 运行 RED**

Run:

```bash
python3 -m unittest tests.test_check_comet_project_policy -v
```

Expected: FAIL because final-gate report validation does not exist。

- [ ] **Step 3: 实现 report freshness 最小逻辑并运行 GREEN**

报告写入 `policy_sha256` 和 `generated_at`；`--verify-report PATH` 只读取并核对当前 policy hash、`policy_valid`、空冲突和空 errors。

Run:

```bash
python3 -m unittest tests.test_check_comet_project_policy -v
python3 tools/check_comet_project_policy.py --root . --json build/comet-project-policy-final.json
python3 tools/check_comet_project_policy.py --root . --verify-report build/comet-project-policy-final.json
```

Expected: tests PASS，生成与复核命令 exit 0。

- [ ] **Step 4: 把 policy report 加入最终 completion gate**

在最终 change 的 tasks/spec 中要求：同一 commit 上先生成 policy report，再由 `--verify-report` 复核；缺失、过期或失败时 `completion_claim_allowed=false`。

- [ ] **Step 5: 校正当前 subagent checkpoint**

把 `.comet/subagent-progress.md` 从 `dispatching` 改为：

```markdown
- stage: `quality-review`
- implementation commit: `f252dbd922062294b51fa3da58f4b157751b43ef`
- review note: implementation report exists; no ROM/input run; bounded thorough review pending
```

从 `.superpowers/sdd/task-4.7-step1-report.md` 填入实际变更文件和 RED/GREEN 命令摘要；不得勾选 plan 或 OpenSpec task。

- [ ] **Step 6: 运行最终整改验证**

Run:

```bash
python3 -m unittest tests.test_check_comet_project_policy -v
python3 tools/check_comet_project_policy.py --root . --json build/comet-project-policy-final.json
python3 tools/check_comet_project_policy.py --root . --verify-report build/comet-project-policy-final.json
openspec validate close-scenario-41-battle-runtime --strict
openspec validate verify-levels-runtime --strict
openspec validate upgrade-remaining-runtime-banks --strict
openspec validate close-reverse-engineering-completion-gaps --strict
git diff --check
```

Expected: all commands exit 0。

- [ ] **Step 7: 提交最终接入与断点校正**

```bash
git commit -m "chore(comet): gate completion on project policy audit"
```

- [ ] **Step 8: 回到 Goal 前置检查**

父代理重新调用 Goal 状态工具。若仍为 `blocked`，停止写入并请用户恢复 Goal；若为 `active`，加载当前 Comet build 状态并派发一个全新的只读 reviewer 审查 `f252dbd`，不得重新实现 Task 4.7 Step 1。
