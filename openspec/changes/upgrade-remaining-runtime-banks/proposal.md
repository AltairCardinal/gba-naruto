## Why

`levels` 独立闭环后，仍有九个结构停留在 `code_verified`，它们缺少统一、可复现的运行时证据，或尚未明确为何运行时 A/B 不适用。需要逐项闭合这些证据缺口，才能让逆向工程完成度建立在自然游戏路径和可审计证据上，而不是仅依赖静态消费者分析。

## What Changes

- 为 `battle-encounters`、`cutscene-scripts`、`data-table-b`、`map-events`、`map-sprites`、`palettes`、`resource-pointers`、`sappy-engine`、`tile-assets` 建立逐项运行时验证门禁。
- 每项验证都从自然 selector 或自然游戏事件出发，证明运行时选择值与真实 ROM 表项一致，并捕获对应的可见、音频或行为结果；不得依据历史 slug 推断已被纠正的结构语义。
- 优先复用 scenario 41 的有效战斗事件闭合 `data-table-b` 与 `resource-pointers`，避免为相同状态重复导航和启动模拟器。
- 使用 mGBA 保存状态固化稳定检查点，并记录 ROM 哈希、状态来源、输入序列、目标地址、观测结果及资源守卫数据，使实验可重复。
- 对无法合理执行受控运行时 A/B 的结构，改用只读断点、自然命令链或前后状态因果证据；若替代路线仍不能达到运行时门禁，则记录阻塞证据并保持本 change 未完成，不得为追求数量而危险 patch 或虚假升级。
- 每完成一项或一组相互依赖的闭环，同步更新 bank 元数据、证据文档、路线图和完成度审计，并通过相关测试与验证。

## Capabilities

### New Capabilities

- `remaining-runtime-bank-verification`: 规定九个剩余 bank 的自然 selector、ROM 目标一致性、可见/行为结果、证据等级判定、快照复用和资源安全要求。

### Modified Capabilities

无。

## Impact

- 影响九个 `sequel/content/*/bank.json` 的验证元数据及其关联提取器、探针、测试和证据文件。
- 影响 scenario 41 战斗探针、mGBA/GDB 运行时探针及可复用保存状态资产，但不改变 `levels` change 的范围。
- 影响 `docs/sequel-roadmap.md`、逆向工程交接/完成度审计和对应 `notes/` 证据记录。
- 不包含 P2 audio cue 语义、legacy web/ROM mirror 收尾，也不实现续作编辑器功能。
