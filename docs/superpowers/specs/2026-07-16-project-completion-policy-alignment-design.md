---
title: 项目完成流程与 Comet 约束对齐设计
date: 2026-07-16
status: approved-for-planning
scope: project-only
---

# 项目完成流程与 Comet 约束对齐设计

## 目标

不修改 Comet 本体，只调整当前仓库，使现有 Comet 流程、Goal 权限和四个逆向 change 不再互相冲突，并能继续推进到真实、可审计的逆向工程 100%。

## 当前问题

1. `.comet/policy.yaml` 声明 `require_policy_support: true` 和 `unsupported_behavior: fail`，但当前 Comet 不解析该 schema，导致按项目规则必须停止。
2. 当前 Goal 明确禁止 push，而 active change、设计和实施计划仍把 push 写成完成门禁。
3. `f252dbd` 已实现 single-input runner 并提供 TDD 报告，但在用户切换到审计问题后才提交，尚未完成限定审查；检查点仍错误地停在 `dispatching`。
4. 当前工作树包含用户既有治理文档和构建产物，项目整改不得覆盖或混入这些改动。

## 方案边界

- 不修改、重装、重新打包或升级 Comet。
- 不修改 Codex 桌面会话、CLI、PATH 或全局技能目录。
- 只改当前仓库中的 policy、项目预检、OpenSpec change、设计、计划和测试。
- 只创建范围明确的本地 commit；不 push、不发布、不合并、不执行破坏性 Git 操作。
- 完成项目对齐后，仍按当前 `build_mode: subagent-driven-development` 恢复开发。

## 项目 Policy

保留 `.comet/policy.yaml`，但把它明确为“项目级机器清单”，由项目预检工具和 Goal/AGENTS 共同执行，不再要求 Comet 插件原生解析。

移除 `activation.require_policy_support` 和 `activation.unsupported_behavior`。保留并严格校验以下项目字段：

- Goal 活跃状态和新用户消息后的 writer 撤销；
- change 必须显式选择；
- 本地 commit 授权与 push 禁令；
- 单 writer、只读 reviewer/sidecar、父代理复核；
- guarded runner、heavy lock 和 owned-tree RSS；
- 已验证快照、单输入和零输入对照；
- immutable run、唯一 run ID、manifest、输入哈希和历史证据保留；
- 无新证据与无变化等待的停止阈值。

平台状态无法由仓库脚本独立读取时，预检输出 required action，由执行者调用对应平台工具核验；不得把它伪装成脚本已完成的硬隔离。

## 项目预检工具

新增：

- `tools/check_comet_project_policy.py`
- `tests/test_check_comet_project_policy.py`

工具使用 Python 标准库实现受限、严格的 schema parser，不引入 PyYAML。它只接受当前 policy 的已知层级、标量和 `resources.runner` 列表；未知键、重复键、缩进错误、错误类型或未知枚举均失败。

工具输出机器可读 JSON，至少包含：

- `policy_valid`
- `required_platform_checks`
- `push_denied`
- `active_change_push_conflicts`
- `errors`

项目审计模式读取 `openspec list --json`，检查四个 active change 及当前未完成计划：

- 未完成 checkbox 不得要求 push；
- proposal/design/spec 不得把远端存在或已推送 commit 作为验收条件；
- 已完成任务和明确标注为历史事实的 push 记录允许保留；
- 当前 policy、AGENTS 和 Goal 的权限描述不得互相矛盾。

若任何冲突存在，命令返回非零并列出文件、行号和原因。

## Active change 对齐

四个 change 统一采用以下交付规则：

1. 每个可独立验收批次形成范围明确的本地 commit。
2. commit 前运行范围匹配的测试、证据审计和 `git diff --check`。
3. push 不执行，也不是 build、verify、archive 或最终 100% 的前置条件。
4. 验证报告通过本地 commit hash、文件 hash 和机器制品定位证据。
5. 历史上已经发生的 push 只作为历史事实保留，不改写为当前授权。

需要同步修改：

- 四个 active change 的 proposal/design/tasks/spec；
- 当前 scenario 41 Design Doc 与实施计划；
- 最终 completion gate；
- 后续 change 的验证命令。

## Comet 接入方式

不改 Comet 代码。项目预检通过三处接入现有流程：

1. 恢复或派发 writer 前，执行项目预检并用 Goal 工具核验 required platform checks。
2. 每个 change 的验证任务显式运行项目预检。
3. 最终 completion audit 把项目预检 JSON 作为 required gate；缺失、过期或失败时 `completion_claim_allowed=false`。

## TDD

### RED

先编写失败测试，覆盖：

- 当前 policy 中不受支持的 activation 要求；
- 未完成任务或 spec 强制 push；
- unknown/duplicate key、错误缩进和错误类型；
- 历史 push 记录不应误报；
- policy/AGENTS 权限冲突。

确认测试因预检工具不存在或当前项目冲突而按预期失败。

### GREEN

实现最小 parser 和审计逻辑，随后修改 policy 与 active artifacts，使聚焦测试、项目预检和四个 change 的 strict OpenSpec validation 全部通过。

### REFACTOR

抽取 schema、路径遍历和诊断格式，保持 parser 范围只覆盖项目当前 schema，不发展成通用 YAML 或 Comet 替代实现。

## 恢复当前 Change

项目对齐完成并提交后：

1. 重新读取 Goal、Git、`.comet.yaml`、计划和 subagent progress。
2. 将 `f252dbd` 视为“已实现但未验收”，不重复派发 implementer。
3. 派发一个只读、范围限定的 thorough reviewer，核对 task 4.7 step 1、TDD RED/GREEN、single-input 边界、资源残留检查和文件范围。
4. reviewer 通过后才勾选 plan step；存在 Important/Critical 时最多执行当前 review 模式允许的修复轮次。
5. 随后执行 task 4.7 step 2：只从 accepted prebattle menu 发送单次 Down；不发送 A，不扩展证据框架。

## 完成标准

- 项目 policy 预检和测试通过；
- 四个 active change 及当前未完成计划不存在强制 push；
- 四个 change 的 strict OpenSpec validation 通过；
- 原插件整改设计从当前树移除，不留下“必须修改 Comet”的维护方向；
- `f252dbd` 恢复状态与真实提交一致；
- 当前 Goal 恢复后能够在禁止 push 的权限下继续 Comet build。
