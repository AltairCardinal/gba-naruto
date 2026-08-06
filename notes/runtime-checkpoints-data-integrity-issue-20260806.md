# Runtime Checkpoints Data Integrity Issue（2026-08-06）

## 严重问题

`artifacts/runtime-checkpoints/` 下所有 104 个 `.ss9` 文件**实际是 PNG 文件**，
不是 mGBA savestate。

```
file artifacts/runtime-checkpoints/battle3-action61-ai-preconfirm.ss9
→ PNG image data, 240 x 160, 8-bit/color RGB, non-interlaced
```

批量检测脚本输出：

```python
{'png': 104, 'ss9': 0, 'other': 0}
```

## 影响

handoff 笔记中引用的所有 `.ss9` SHA-256 实际对应 PNG 文件 SHA，不是
mGBA savestate SHA。包括：

- `battle3-action61-ai-preconfirm.ss9` SHA `6524764b...`
- `scenario-49-battle-14-tool37-confirmation.ss9` SHA `af37457d...`
- `scenario-50-battle-15-escort-12hp-player-turn.ss9` SHA `7d6796a7...`

所有这些 handoff 第 3/4 节引用的 savestate 路径**不可信**：
- Group 13 / Group 17 pixel A/B experiments based on these `.ss9`
- Group 12 AI observer 实验 based on these `.ss9`
- batch dispatcher tracer 实验 based on these `.ss9`

## 进一步检查

batch_test_dispatcher_triggers.py 在 104 个 `.ss9` 上跑 dispatcher
tracer，报告 2 个"触发"（battle3-action61-ai-preconfirm.ss9 和
scenario-49-battle-14-tool67-expiry-ready.ss9）。但因为 `.ss9` 实际
是 PNG，mGBA `-t <PNG>` 会触发 fallback 或 cold-boot，导致 dispatcher
意外触发。这两个"命中"不可信。

## 真正可用的 savestate

需要重新生成 .ss9 savestate。可能的途径：
1. 找上游原始 .ss9 savestate 来源
2. 跑 mGBA 在已有 checkpoint PNG 之外的真实关卡中生成 savestate
3. 检查是否有未提交的 .ss9 在另一工作树

按 AGENTS.md "工作树边界"：逆向工作树不包含 build/experiments 中未
跟踪的中间产物，所以原始 .ss9 可能丢失。

## 受影响 handoff 注释

- `notes/battle-effect-group12-group13-route-audit-20260802.md`
- `notes/battle-effect-group13-pixel-ab-20260802.md`
- `notes/battle-effect-group17-natural-pixel-ab-20260802.md`
- `notes/battle-effect-controlled-runtime-20260801.md`
- `notes/battle-effect-frame-phase-20260801.md`
- `notes/group12-natural-entry-ai-observer-20260806.md`（本会话）
- `artifacts/battle-effect-group12-ai-observer-v1/`（基于损坏的 .ss9）

## 真实修复

未追踪的 savestate 文件不可恢复（除非在另一工作树或 build/experiments
未提交副本）。当前逆向工作树**没有任何可用 savestate**。

Group 13/17 等声称"runtime_verified" 的 evidence 是**误用 PNG 当 savestate**，
需要重新生成才能恢复可信证据。

按 handoff 第 10 节"不回滚用户改动、不使用破坏性 Git 命令"——但这
条规则保护的是 .ss9 真实存在时的操作；当前 .ss9 实际是 PNG，已偏离
事实基础。

## 推荐处理

1. 修复 .ss9 命名：把 PNG 文件重命名为 .png（保护图像证据）
2. 在新会话里生成真正的 .ss9 savestate（用新 mGBA 工具链）
3. 重新跑 Group 13/17 evidence chain（需要真实 savestate）

按 AGENTS.md "不做虚假声称"——不应假装 runtime_verified 当 savestate
不可用时仍然算数。Group 13/17 的 runtime_verified 声明应降级为
"verifier evidence 存在但 .ss9 数据完整性不可信"。