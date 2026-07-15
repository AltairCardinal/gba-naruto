## Why

前三个 change 闭合 scenario 41、`levels` 与其余 `code_verified` bank 后，项目仍有 P2 级完成缺口：72 个 audio cue 没有来源充分的玩家语义，legacy web CRUD 与真实 ROM mirror 的安全边界尚未逐入口收口，玩家可见字段及其语义写回也未全部达到交接门槛。只有把这些缺口和最终逐要求审计全部闭合，才能恢复“逆向工程 100% 完成”声明。

## What Changes

- 依赖 `close-scenario-41-battle-runtime`、`verify-levels-runtime` 与 `upgrade-remaining-runtime-banks` 的已验证成果；前三项未满足时，本 change 不得发布最终完成结论。
- 为 72 个仍为 `unknown` 的有效 audio cue 建立来源充分、可复现且不依赖听感猜测的语义证据；同时保留“候选名不等于官方名称”的显式元数据边界。
- 逐项核对 legacy web CRUD 入口与 `rom_*` lossless mirror，只有具备明确记录身份、immutable-base 前置字节、完整字段序列化、范围/冲突检查和失败回归测试的字段才允许产生 game-effective patch；其余入口继续拒绝写入并输出可审计诊断。
- 闭合 units、skills 及其他玩家可见但仍未命名字段的语义，建立从字段身份、可见/行为证据到安全语义写回的逐字段清单；无法证明的字段保持不可编辑且不得用推测命名。
- 扩展机器可读 completion audit，逐项验证 32/32 结构身份、提取器或等价机器验证、字段语义、编辑字段安全写回、集成告警、证据等级、完整构建、单元/集成测试与模拟器验收。
- 只有全部门槛真实通过且 `docs/final-completion-report.md` 与制品一致时，才恢复 100% 声明并允许 Draft PR 进入后续发布决策；否则报告必须明确列出未完成项并保持非完成状态。
- 逆向实验继续复用 mGBA 保存状态，所有重任务经过共享资源守卫并只清理本次 owned process tree；阶段成果按可独立验收的批次提交并推送。

## Capabilities

### New Capabilities

- `audio-cue-semantic-closure`: 为全部有效 audio cue 保存来源、证据等级、可复现事件语境及非官方名称边界，并消除无证据的 `unknown` 语义缺口。
- `legacy-rom-mirror-boundary`: 规定 legacy web CRUD 到真实 ROM mirror 的允许写入、拒绝写入、immutable-base 校验和集成告警契约。
- `player-visible-field-writeback`: 规定玩家可见字段从语义证明到字段级安全序列化、单因素验证与编辑权限的闭环。
- `reverse-engineering-completion-gate`: 规定 32/32 身份、提取、语义、写回、测试、构建、模拟器证据和最终报告共同通过后才可声明 100%。

### Modified Capabilities

无。当前 OpenSpec 尚无对应主规格；本 change 新建 P2 收尾与最终完成门禁规格。

## Impact

- 依赖前三个顺序 change 的快照、运行时证据、bank 状态与测试结果。
- 影响 audio 语义清单及提取/探针证据、`sequel/content/*/bank.json` 的字段元数据、legacy generator、`rom_*` mirror、editor CRUD 权限和补丁安全门禁。
- 影响 `tools/audit_re_completion.py` 及其机器可读制品、相关单元/集成/模拟器验收、`docs/reverse-engineering-handoff-20260711.md`、`docs/sequel-roadmap.md` 与 `docs/final-completion-report.md`。

## Non-goals

- 不重新实现前三个 change 已负责的 scenario 41、`levels` 或九个剩余 bank 的具体运行时闭环。
- 不启动续作网页编辑器产品功能开发，也不扩大现有 CRUD 的产品范围。
- 不把听感猜名、截图差异、构建成功、32/32 元数据/ROM fidelity 或单一模拟器命中当作整体 100% 证据。
