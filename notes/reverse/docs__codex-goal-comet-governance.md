# Codex Goal 与 Comet 治理建议

## `/goal` 启动指令

建议每个 Goal 只绑定一个主 Comet change，并使用以下模板；删除不适用项即可。

```text
/goal
目标：<可验收的最终结果>
Comet：继续 <change-name>；若不存在则创建 <change-name>
当前里程碑：<本轮必须完成的最小闭环>
范围：允许 <路径/系统>；禁止 <路径/行为>
权限：允许自主技术决策和下载必要工具；本地 commit=<允许/禁止>；push=<允许/禁止>
执行：按 Comet 状态恢复；高风险/TDD/最终验收由 Codex 本体负责；独立低风险任务可外派；共享工作区最多一个 writer
ROM：统一经 tools/run_guarded.py；关键输入前后保存并验证快照；单输入实验配零输入对照；监控 owned-tree RSS
停止条件：需要扩大范围、改变目标、执行不可逆操作、权限不足，或同一阻塞连续三轮无新证据时暂停汇报
交付：更新 tasks.md、相关 notes/docs 和必要时 docs/sequel-roadmap.md；给出验证命令、结果、剩余风险、耗时和异常成本
```

不要把动态 change、权限和里程碑写入 `AGENTS.md`；它们应随 Goal 明确，并在恢复时重新核对。

## Comet 整改优先级

### P0：先消除错误执行

1. **显式绑定 change**：新增本轮 `active_change` 绑定；存在多个活跃 change 时，hook/guard 不得选择目录排序中的第一个。当前 `comet-hook-guard.sh` 对 change 外文件会回退到“第一个活跃 change”，应改为无唯一绑定即拒绝。
2. **提交权限结构化**：在 `.comet.yaml` 增加 `commit_policy: deny|local`、`push_policy: deny|allow`，默认均为 `deny`。删除 tweak/hotfix/build 中无条件 `git commit`，改为提交前 guard；未授权时允许完成验证，但停在提交决策点。
3. **Goal 写入租约**：写操作前要求有效租约，至少包含 Goal ID、状态、change、writer、签发时间和基准 HEAD。新用户消息或 Goal 非 active 时撤销租约；父代理复核后重新签发。
4. **单 writer 硬化**：Comet 状态记录 writer lease；第二个 writer 启动或写入时失败。reviewer/sidecar 使用只读运行方式，不只依赖提示词。

### P1：让守卫覆盖真实 Codex 路径

1. 项目当前没有 `.codex/hooks.json`，现有 `comet-hook-guard.sh` 也按其他 harness 的 `Write|Edit` 和 `file_path` 设计，尚未对桌面 Codex 的 `apply_patch`、shell 写入和 MCP 写入形成可靠覆盖。
2. 为当前桌面版本建立项目 hooks：`UserPromptSubmit` 撤销写租约；`PreToolUse` 校验明确 change、phase、租约和目标路径；`SubagentStart/Stop` 记录代理生命周期。Hook 只能作为防线之一，无法拦截的写路径还必须经过统一包装脚本。
3. 将 phase guard、Goal preflight、Git 权限和 writer lease 合并为一个 `comet preflight` 入口；所有 build、verify、ROM runner 和提交操作先调用它。
4. 新增 `comet doctor`：检查 `.comet.yaml` schema、tasks/plan 勾选、handoff hash、dirty worktree 归因、活跃 change 冲突及僵尸 writer lease；恢复任务先运行 doctor。

### P2：控制成本与恢复开销

1. 不依赖当前原生子代理不存在的 token/time budget 参数；在 Comet 台账记录 wall time、工具调用数、证据增量和停止原因。
2. 连续三轮没有新证据、三次等待状态不变或任务明显超出估算时停止外派，由父代理审计后决定拆分、换方法或终止。
3. 子代理只接收 handoff 摘要、精确路径和验证命令；禁止整段历史默认 fork。完成后立即关闭，不复用污染上下文的旧代理。
4. 将“实现完成”“验证通过”“允许提交”“已提交”“允许推送”拆为不同状态，避免 Comet 为满足流程而反复提交或重做证据链。

## 生效方式

1. **AGENTS**：修改项目 `AGENTS.md` 后新建 Codex 任务验证；当前长任务及已启动子代理不会可靠热加载。
2. **Goal 模板**：下一次 `/goal` 直接使用上方模板；必须写出唯一 change 和 commit/push 权限。
3. **Comet skill**：在 Comet 的源技能目录修改字段、skill 文案和脚本，并补充 shell 单元测试；不要只改插件缓存副本。重新安装或运行缓存刷新流程后，新建任务加载。
4. **Hooks**：新增项目 `.codex/hooks.json`，确认桌面 Codex 信任提示后重开项目；用允许/拒绝矩阵验证 `apply_patch`、shell、MCP、子代理和多 change 场景。
5. **验收矩阵**：至少验证 Goal paused、多个 active change、未授权 commit、两个 writer、用户中途发新指令、ROM heavy lock 冲突、内存门禁和恢复后 stale state 八种场景。
6. **灰度顺序**：先启用只记录模式采集误判，再启用 commit/push 拦截，最后启用通用写入拦截；出现无法覆盖的工具路径时保持 fail-closed 并记录例外。

当前桌面内置 Codex 路径以 `~/.codex/config.toml` 中的 `CODEX_CLI_PATH` 为准；本机已指向 `/Applications/ChatGPT.app/Contents/Resources/codex`。
