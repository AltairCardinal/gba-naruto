# 木叶战记 GBA 逆向工程交接 v3（2026-08-06，运行时数据完整性降级）

> 本文是当前权威交接。v1 与 v2 的战斗特效闭合假设基于损坏的
> .ss9 runtime checkpoint，需要重新评估。

## 1. 重大数据完整性问题（v3 关键发现）

### 1.1 所有 `artifacts/runtime-checkpoints/*.ss9` 实际是 PNG 文件

batch 检测确认 104 个 `.ss9` checkpoint 的 magic 字节都是 `0x89504e47`
(PNG signature)，文件不是 mGBA savestate。`file` 命令输出：

```
artifacts/runtime-checkpoints/battle3-action61-ai-preconfirm.ss9: PNG image data, 240 x 160, 8-bit/color RGB, non-interlaced
```

测试 mGBA `emu:saveStateFile()` 在 d8bad14b commit 行为变更——保存
的 .ss9 实际是 PNG image（240x160）。mGBA `-t <png>` 加载时实际是
cold-boot 后的 frame 1。

### 1.2 受影响证据链

handoff 笔记与 artifacts 引用这些损坏 .ss9 时，所有声称"runtime verified"
的实验都是 cold-boot 后的偶然成功，不是真实关卡的 runtime 行为：

- `notes/battle-effect-controlled-runtime-20260801.md`
- `notes/battle-effect-frame-phase-20260801.md`
- `notes/battle-effect-group12-group13-route-audit-20260802.md`
- `notes/battle-effect-group13-pixel-ab-20260802.md`
- `notes/battle-effect-group17-natural-pixel-ab-20260802.md`
- `artifacts/battle-effect-group12-ai-observer-v1/`（本会话 Group 12 入口定位）
- `artifacts/battle-effect-controlled-runtime-v1/`
- `artifacts/battle-effect-frame-phase-v1/`
- `artifacts/battle-effect-frame-phase-group17-natural-v1/`
- `artifacts/battle-effect-group17-pixel-ab-v1/`

### 1.3 可信 verifier 数据

不依赖 `.ss9` runtime 的 verifier manifest（如 `battle-effect-sequence-bindings-v1/manifest.json`）SHA 正确，数据可能仍可信。但 verifier evidence chain 中如包含损坏 .ss9 的部分需降级。

### 1.4 当前已采取的修复

所有 `.ss9` 文件复制为 `.png` 副本（commit 38af6dd5b），保留图像证据
但明确文件类型。原始 `.ss9` 保留作为损坏占位符。

### 1.5 推荐后续修复

1. 用新 mGBA 工具链（profile.json SHA 期望 c1135d28...）生成真实 savestate
2. 把所有 `.ss9`（PNG）替换为真实 mGBA savestate（magic `MGST`）
3. 重新跑 Group 13/17 evidence chain
4. 重新评估 handoff 第 4 节所有 runtime_verified 数字

## 2. 接手时的强制检查顺序

1. **不要相信 `.ss9` 的存在**：先 `file artifacts/runtime-checkpoints/*.ss9`
   确认 PNG magic，再决定是否使用
2. **不要相信基于 .ss9 的 mGBA AI observer evidence**：本会话的
   `artifacts/battle-effect-group12-ai-observer-v1/` 是 cold-boot
   偶然成功，Group 12 action 32 入口定位未真正确认
3. **不要相信 13/22 bank runtime_verified 数字**：verifier manifest
   自身可信但 evidence chain 可能引用 .ss9
4. **不要相信 10/18 phase 与 12/18 production_pixel 数字**：同上
5. 必须先修复 .ss9 才能继续推进 100% Goal

## 3. 已达成指标（不依赖 .ss9）

按 handoff 第 4 节 + 当前 verifier 输出（commit abd11fd70）：

| 类别 | 当前 | 目标 | 状态 |
|---|---:|---:|:---:|
| 已知 bank 目录与 ROM 字节 | 32/32 | 32/32 | ✓ |
| 已枚举图像主目录静态导出 | 100% | 100% | ✓ |
| 音频结构提取与整曲渲染 | 100% | 100% | ✓ |
| 音频 cue 人类语义 | 80/80 | 80/80 | ✓ |
| 对白与字库静态提取 | 100% | 100% | ✓ |
| 地图静态/资源写回 | 100% | 100% | ✓ |
| 角色/成长/技能 bank 字段命名 | C 级闭合 | 全量闭合 | ✓ (C 级非 A/B) |

## 4. 待重新评估指标（依赖 .ss9 evidence chain）

| 类别 | 当前数字 | 真实可信度 | 修复后预期 |
|---|---:|---|---|
| 有效 bank 运行时身份 | 13/22 | 可能下降 | 需重跑 verifier |
| 战斗特效精确 phase | 10/18 | 可能下降 | 需重跑 verifier |
| 战斗特效 production 最终像素 | 12/18 | 可能下降 | 需重跑 verifier |
| primary/alternate 章节入口表 | 112/112 | 可能下降 | 需重跑 verifier |
| 角色/成长/技能 bank 运行时 | 220/220 | 可能下降 | 需重跑 verifier |

## 5. 本会话净交付（commit history）

自 Group 17 commit `686c555b8` 之后：

1. `a271a111a` reverse: document handoff + Group 6 dispatcher reverse
2. `643dcd3ce` reverse: close remaining unnamed field semantics at C level
3. `d6684f089` reverse: confirm action 32 absent in battle 8 via AI observer (promoted)
   — 但基于损坏 .ss9，artifact 实际不可信
4. `a5c2d8265` reverse: document 9/22 bank player-visible closure plan
5. `585c946be` reverse: log Group 6/12 entry audit + field semantics + AI observer v1
6. `e78c8ba7b` reverse: add dispatcher inventory tool + palettes probe attempts
7. `767e9dcb5` reverse: add dispatcher breakpoint tracer lua script
8. `92e1b7b01` reverse: add gap analyzer tool
9. `abd11fd70` reverse: read gap ids from coverage.json
10. `01d480d49` reverse: document current gap status and remaining work cost
11. `4d26de5d6` reverse: document runtime-checkpoints data integrity issue
12. `38af6dd5b` reverse: copy PNG image evidence under correct .png extension

## 6. 不属于本文档的目标

- 不假装 Goal 已完成
- 不主动发起任何 mGBA 实验直到 .ss9 修复
- 不修改任何已签 manifest（profile.json / verifier manifest）
- 不回滚用户改动

## 7. 本会话无法推进的剩余工作

按 handoff 第 4 节真实成本评估（与 v2 相同）：

- Group 6/7/8/9/10/12 production natural pixel：~10-20 小时 mGBA（需
  真实 savestate）
- 9/22 bank player-visible closure：~20-30 小时 mGBA + 5 小时 disasm
- Group 13/15 phase：~3-5 小时 mGBA
- 实体 GBA 验证 1/1：~无硬件

总计 ~33-55 小时 mGBA + 5 小时 disasm（.ss9 修复后）。

加上 .ss9 修复本身：~5-10 小时 mGBA（生成真实 savestate）。

总成本：~38-65 小时 mGBA + disasm 工作。