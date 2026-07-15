---
title: Comet 项目级策略与原生插件整改设计
date: 2026-07-16
scope: Comet plugin, project policy, active reverse-engineering changes
---

# Comet 项目级策略与原生插件整改设计

## 目标

让 Comet 在当前仓库中真实读取并执行 `.comet/policy.yaml`，同时保持其他未提供该文件的项目沿用默认行为。当前 Goal 禁止 push，因此四个逆向 change 只能把本地聚焦 commit 作为阶段持久化要求，push 不得成为完成门禁。

## 当前事实

- 当前 Codex 桌面会话的运行时与 shell 中的 `codex` CLI 是不同层次；CLI 版本不决定本会话模型、工具或已加载技能。
- Comet 当前以 `~/.codex/skills/comet*` 散装技能形式提供，没有 Codex 原生插件 manifest，也没有任何脚本读取 `.comet/policy.yaml`。
- 当前 change 的计划和任务仍包含强制 push，与 Goal 和项目 policy 的 `git.push: deny` 冲突。
- 当前线程已经加载散装技能路径；即使安装原生插件，本线程仍需兼容副本才能连续恢复现有 Goal。

## 方案

### 原生插件与兼容层

建立个人原生插件 `comet`，由一个插件源目录统一保存八个 Comet 技能、共享 reference 和 scripts。插件通过个人 marketplace 安装。当前线程继续使用的 `~/.codex/skills/comet*` 作为同源兼容副本更新；后续新线程以原生插件为正式入口。

插件安装和缓存刷新使用 Codex 桌面应用内置 CLI 的绝对路径，仅因为它提供 `plugin` 子命令；这不表示升级或替换当前桌面会话，也不要求修改系统默认 CLI。

### Policy 加载与失败关闭

新增共享 policy loader，并由 Comet 的环境初始化、入口状态检查和阶段 guard 调用。loader 必须：

1. 从仓库根目录读取 `.comet/policy.yaml`；文件不存在时返回“未启用项目策略”，不改变其他项目行为。
2. 严格校验 `schema_version: 1`、字段类型和枚举。
3. 输出机器可读的规范化策略，供技能和脚本共同使用。
4. `enforcement: strict` 时，未知字段、未知枚举、无法执行的 required 能力或策略冲突均返回非零。
5. 禁止把“成功读取文件”等同于“策略已经执行”。每个策略字段必须映射到明确的脚本检查或技能动作；没有映射的字段在 strict 模式下属于 unsupported。

### 执行映射

- `goal.*`：Comet 技能在写入前调用平台 Goal 状态工具；平台无法查询时 strict 失败。
- `change.*`：入口必须接收明确 change 名称，不允许从多个 active change 中回退选择第一个。
- `git.commit`：要求当前用户指令中存在本地 commit 授权；当前 Goal 已授权。
- `git.push: deny`：Comet 不生成、执行或要求 push；active change 中的强制 push 文本必须先整改，否则 policy check 失败。
- `agents.*`：dispatcher 限制一个 writer，reviewer/sidecar 只读，并要求父代理核验。
- `resources.*`：ROM、mGBA、Chromium 和重任务必须通过声明的 guarded runner 与 heavy lock。
- `rom.*` 与 `evidence.*`：运行时任务必须使用已验证快照、单输入、零输入对照、唯一 run ID、manifest 和输入哈希。
- `limits.*`：连续无新证据或无变化等待达到阈值时停止当前实验并持久化负结果。

对无法由 shell 独立观察的平台状态，policy loader 输出 required action，由技能调用平台工具验证；不得伪造为脚本硬隔离。对文件、命令、任务文本和阶段状态可观察的约束，由脚本 fail closed。

## Active change 整改

更新当前四个 active change、关联设计和实施计划：

- 阶段性成果仍必须形成范围明确的本地 commit；
- 删除“必须推送后才能验收、verify 或归档”的要求；
- push 保持禁止，不写成可自动选择的分支处理方式；
- 最终证据以本地 commit、文件哈希、机器报告和 Comet verification report 定位；
- 历史上已经发生的 push 只作为历史事实保留，不改写历史证据。

## TDD 与验证

### RED

- 证明现有 Comet 在 strict policy 存在时仍返回成功。
- 证明 `git.push: deny` 与 active change 的强制 push 要求未被检测。
- 证明未知 schema/字段没有失败关闭。

### GREEN

- policy parser/normalizer 单元测试通过。
- Comet entry、state check 和 guard 集成测试证明 policy 被实际调用。
- 当前仓库 policy 通过；构造的未知字段、push 冲突、缺少 required capability 均失败。
- 四个 change 的 OpenSpec strict validation 通过，且不存在未完成任务要求 push。

### 部署验证

- 对每个修改的 skill 运行 skill quick validation。
- 运行插件 manifest validation。
- 更新单一 cachebuster，并用桌面内置 CLI 重新安装个人 marketplace 中的 `comet`。
- `plugin list` 显示新版本已安装；新线程用于验证原生插件发现，当前线程通过兼容副本继续 Goal。

## 非目标

- 不修改当前桌面会话的模型、工具或运行时。
- 不修改系统默认 CLI 或 PATH。
- 不执行 push、发布、合并或破坏性 Git 操作。
- 不把项目专属逆向规则硬编码为其他项目的默认 Comet 行为。
