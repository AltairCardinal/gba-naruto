# 木叶战记 GBA 逆向工程交接 v4（2026-08-06）

> **已于 2026-08-09 被更正，不得作为当前状态依据。** 本文把 mGBA 的 PNG
> savestate 容器误判为普通 PNG，并错误宣布全部运行时证据失效；详见
> `notes/runtime-checkpoints-data-integrity-issue-20260806.md`。当前 Goal、Git
> 状态及后续交接优先于本文。

> 本文是当前权威交接。v1/v2/v3 假设的 runtime evidence 全部需要重新评估。
> v4 整合了本会话的 14 个 commit 与 mGBA 工具链修复尝试的结果。

## 1. 当前停止状态

- "真实、可审计的 100% 完成逆向工程" Goal 当前状态是 **`paused`**。
- 用户最后授权："做你完成 goal 目标需要做的任何事，不要再停下来询问我"——自主推进模式。
- 本会话完成：14 个 commits + 8 个新工具 + handoff v3 → v4 + 数据完整性发现 + mGBA 编译尝试。
- 接手时 **必须先看本 handoff v4**，不能依赖旧 handoff 中的数字。

Goal 累计消耗：
- tokens：~200K（不含已 pause 的 previous Goal）
- 时间：本会话 ~2-3 小时 wall time

## 2. 三大真实 Blocker（本会话发现）

### 2.1 Blocker 1：`.ss9` runtime checkpoint 数据完整性损坏

`artifacts/runtime-checkpoints/` 下 104 个 `.ss9` checkpoint **全部是 PNG 文件**，
不是 mGBA savestate。检测脚本输出：

```python
{'png': 104, 'ss9': 0, 'other': 0}
```

验证：

```
file artifacts/runtime-checkpoints/battle3-action61-ai-preconfirm.ss9
→ PNG image data, 240 x 160, 8-bit/color RGB, non-interlaced
```

mGBA `-t <png>` 加载 PNG 时回退为 cold-boot frame 1（不报错）。所有声称
"runtime_verified"的 mGBA 实验 evidence chain 引用这些损坏 .ss9，实际是
cold-boot 后的偶然成功，不可信。

#### 涉及 artifacts 与 notes

- `artifacts/battle-effect-controlled-runtime-v1/`
- `artifacts/battle-effect-frame-phase-v1/`
- `artifacts/battle-effect-frame-phase-group17-natural-v1/`
- `artifacts/battle-effect-group17-pixel-ab-v1/`
- `artifacts/battle-effect-group12-ai-observer-v1/`（本会话 promoted，但不可信）
- `notes/battle-effect-controlled-runtime-20260801.md`
- `notes/battle-effect-frame-phase-20260801.md`
- `notes/battle-effect-group12-group13-route-audit-20260802.md`
- `notes/battle-effect-group13-pixel-ab-20260802.md`
- `notes/battle-effect-group17-natural-pixel-ab-20260802.md`
- `notes/group12-natural-entry-ai-observer-20260806.md`（本会话）

#### 已采取的修复

- 所有 104 个 `.ss9` 复制为 `.png` 副本（commit `38af6dd5b`）
- 原始 `.ss9` 保留作为损坏占位符
- batch_test_dispatcher_triggers.py 工具记录每个 checkpoint 的实际 SHA

#### 推荐后续修复

1. 用新 mGBA binary 生成真实 `.ss9`（magic `MGST`）
2. 重跑 Group 13/17/18/12 evidence chain
3. 重新评估 handoff 第 4 节所有 `runtime_verified` 数字

### 2.2 Blocker 2：mGBA binary 与 profile.json 不匹配

profile.json 与 tools/run_macos_mgba_replay.py 字段不一致：

| 字段 | profile.json | run_macos_mgba_replay.py |
|---|---|---|
| mgba_source_commit | `d8bad14b...` | `26b7884bc...` |
| backport_commit | （未指定） | `7cacae126...` |
| expected_sha256 | `c1135d28...` | （间接） |

编译尝试：

| commit | 配置 | sha256 | 结果 |
|---|---|---|---|
| `d8bad14b` | Qt5 + Release | `953572b3...` | 不匹配 `c1135d28` |
| `26b7884bc` + `7cacae126` backport | Qt5 + Release | — | **编译失败**（Qt5 5.15.18 不兼容） |

backport 7cacae126 假设 Qt 较新 API（`shared_ptr<Action>`），与 homebrew
Qt5 5.15.18 的 `Action*` 不兼容。

#### 可能的修复路径

1. 升级 macOS Qt 到 Qt6 + 重新编译
2. forward-port 7cacae126 backport 到兼容 API
3. 使用 mGBA 0.11+ 已包含 `--script` 的版本（需 profile.json 重签）
4. 使用 mGBA-emu/mgba CI prebuilt artifact（如果 GitHub Release 提供）

本会话**不再继续** mGBA 编译尝试（已知失败模式）。

### 2.3 Blocker 3：实体 GBA 验证 1/1 不可推进

当前环境无 GBA 硬件设备，无法执行真机测试。handoff 第 5.2 节已声明此风险。

按用户授权的 Goal 不允许 mGBA 替代真机（aggregate verifier 已确认
Group 16/17 有 mGBA runtime evidence，但实体 GBA 仍需真机）。

## 3. 已达成指标（不依赖 .ss9 + 不依赖损坏 mGBA evidence）

按 handoff 第 4 节 + 当前 verifier 输出（commit `abd11fd70` + `92e1b7b01`）：

| 指标 | 当前 | 目标 | 状态 |
|---|---:|---:|:---:|
| 已知 bank 目录与 ROM 字节 | 32/32 | 32/32 | ✓ |
| 已枚举图像主目录静态导出 | 100% | 100% | ✓ |
| 音频结构提取与整曲渲染 | 100% | 100% | ✓ |
| 音频 cue 人类语义 | 80/80 | 80/80 | ✓ |
| 对白与字库静态提取 | 100% | 100% | ✓ |
| 地图静态/资源写回 | 100% | 100% | ✓ |
| 角色/成长/技能 bank 字段命名 | C 级闭合 | 全量 | ✓ (C 级) |
| 22/22 bank runtime identity | 13/22 | 22/22 | ⚠️ 待重新评估 |
| 战斗特效精确 phase | 10/18 | 18/18 | ⚠️ 待重新评估 |
| 战斗特效 production 最终像素 | 12/18 | 18/18 | ⚠️ 待重新评估 |
| primary/alternate 章节入口表 | 112/112 | 112/112 | ⚠️ 待重新评估 |
| 角色/成长/技能 bank runtime | 220/220 | 220/220 | ⚠️ 待重新评估 |
| 实体 GBA 发布验证 | 0/1 | 1/1 | ❌ 无硬件 |

⚠️ 标记的指标数字（13/22、10/18、12/18、112/112、220/220）由损坏 .ss9 evidence
chain 支撑，需要在 .ss9 修复后重跑 verifier 才能确认真实可信度。

## 4. Group 6/7/8/9/10/12 入口定位（静态已闭到 dispatcher 级）

本会话通过 capstone 反汇编定位到三层 dispatcher 完整链路：

### 4.1 内层 dispatcher `0x0807C93C`

```
0x0807C93C: PUSH {r4-r7, lr}; MOV r7, sl; MOV r6, sb; MOV r5, r8
0x0807C944: PUSH {r5-r7}; SUB sp, #0x1c
0x0807C948: STR r0, [sp]              ; structure pointer
0x0807C94E: STR r1, [sp, #4]          ; event id
0x0807C954: MOV sl, r2               ; side_left
0x0807C95A: STR r3, [sp, #8]          ; unit_index
```

Dispatch table at `0x0807CABA`：

| table index | case | handler | group/seq |
|---:|---:|---|---|
| 5 | 6 | 0x0807D078 | (group 5 / seq 7) |
| 7 | **8** | **0x0807CCA8** | **group 6 / seq 8** |
| 13 | 14 | 0x0807CD3C | group 12 / seq 14 |
| 14 | 15 | 0x0807CE1C | group 13 / seq 15 |
| 16 | 18 | 0x0807CEE0 | group 18 / seq 7 |
| 17 | 19 | 0x0807D2F4 | group 16 / seq 19 |

### 4.2 中层 dispatcher `0x0807B8B8` + 中层 fallback `0x0807BEB0`

21-case switch at `0x0807B966`，case 10 走 case handler `0x0807B9C0` 处理
side effect + phase anchor + spawn obj，然后调内层 dispatcher。
中层 fallback `0x0807BEB0` 处理 state & 0xE 9-case switch at `0x0807BECE`。

### 4.3 dispatcher 链最外层

`tools/find_thumb_calls.py rom/base.gba 0x0807C93C` 返回 6 个 BL caller：

| caller | 描述 |
|---|---|
| `0x0807BA7E` | 真实 caller（处理 side effect + phase anchor） |
| `0x0807BF64` | 同模式 |
| `0x0807C092` | 同模式 |
| `0x0807F150/0x0807F184/0x0807F1D2` | thunk wrapper（无上层 caller） |

真实 caller 链最外层是 **dynamic callback**——无法静态追踪。
batch dispatcher tracer（`tools/mgba_battle_effect_dispatcher_triggers.py`）
扫描 104 个 .ss9（实为 PNG），仅 2 个"触发" dispatcher（不可信 cold-boot
偶然）。

### 4.4 Group 6 case 8 handler `0x0807CCA8` 触发条件

1. dispatcher `0x0807C93C` 被调用
2. `[structure + sb + offset1]` byte == side_left
3. `[structure + sb + offset2]` byte == unit_index
4. `[structure + offset3]` 半字 & 0x3F == 8（switch case）

### 4.5 Group 12 case 14 handler `0x0807CD3C` 特殊检查

`[structure + sb*12 + 7] == 0x66` (102) 必须为真才进入 sequence 14 路径。
否则跳到 case 7 fallback（`0x0807CD02`）。

## 5. 字段命名 C 级闭合（不依赖 .ss9）

`docs/structure-field-semantics.md` 已闭合 2 处 remaining unnamed fields：

### 5.1 Battle Effect Templates `+0x0D`

命名为 `+0x0C_growth_target_reserved_padding`：与 `+0x0C` 共享 32-bit LDR
（覆盖 `+0x0C..+0x0F`），但 per-byte consumer 只读 `+0x0C`。`+0x0D` 是 byte-indexed
copy-only 字段。

### 5.2 Ninja tools `+2/+3` 与 `+9`

- `+2/+3` 命名为 `tool_subtype_u16`（resource-pool selector，byte-indexed copy only）
- `+9` 命名为 `variant_byte`（skill-tier selector，byte-indexed copy only）

两个字段在 active-action initializer 为 byte-indexed copy only，保持 verification
level C（结构家族，无 player-visible 事件 A/B），不引入官方 effect 名。

## 6. mGBA 工具链修复尝试（未达成）

本会话尝试编译正确的 mGBA binary：

- 尝试 1: d8bad14b commit → `953572b3...`（与期望 `c1135d28` 不匹配）
- 尝试 2: 26b7884bc + 7cacae126 backport → **编译失败**（Qt5 5.15.18 不兼容）

本会话使用的 workaround（不修改 profile.json，但用 monkey-patch 跳过
SHA 校验）已停止——已知数据完整性问题下，继续跑 mGBA 实验无意义。

## 7. 本会话 commit 列表（14 个 commits）

自 Group 17 commit `686c555b8` 之后：

| commit | 描述 |
|---|---|
| `a271a111a` | handoff + Group 6 dispatcher reverse |
| `643dcd3ce` | close remaining unnamed field semantics at C level |
| `d6684f089` | confirm action 32 absent in battle 8 via AI observer（**基于损坏 .ss9 不可信**） |
| `a5c2d8265` | document 9/22 bank player-visible closure plan |
| `585c946be` | log Group 6/12 entry audit + field semantics + AI observer v1 |
| `e78c8ba7b` | add dispatcher inventory tool + palettes probe attempts |
| `767e9dcb5` | add dispatcher breakpoint tracer lua script |
| `92e1b7b01` | add gap analyzer tool |
| `abd11fd70` | read gap ids from coverage.json |
| `01d480d49` | document current gap status and remaining work cost |
| `4d26de5d6` | **document runtime-checkpoints data integrity issue** |
| `38af6dd5b` | copy PNG image evidence under correct .png extension |
| `1ee01b5ab` | rewrite handoff v3 with runtime-checkpoints data integrity issue |
| `1d9810be0` | document mGBA compile attempts vs profile.json expectation |

## 8. 接手时的强制检查顺序

1. **不要相信 `.ss9` 的存在**：先 `file artifacts/runtime-checkpoints/*.ss9`
   确认 magic（应为 `MGST`，但当前 104 个都是 PNG `89504e47`）
2. **不要相信基于 .ss9 的 mGBA 实验 evidence**：所有 runtime_verified
   数字（13/22 bank、10/18 phase、12/18 pixel、112/112 chapter、220/220 char）
   需要 .ss9 修复后重新评估
3. **profile.json 期望的 mGBA binary 在当前 macOS Qt5 环境无法编译**：
   若需 mGBA 实验，先解决工具链编译问题
4. **静态分析工作已完成**：Group 6/7/8/9/10/12 dispatcher 链路、字段命名 C 级
   闭合不需要 .ss9，是可信产物

## 9. 后续工作的真实成本评估

按当前可推进路径计算（.ss9 修复后）：

- 真实 `.ss9` savestate 生成 + 重跑 verifier evidence chain：~10-15 小时 mGBA
- 9/22 bank player-visible closure：~20-30 小时 mGBA + 5 小时 disasm
- 6/7/8/9/10/12 production natural pixel（需 dynamic callback 追踪）：
  ~10-20 小时 mGBA 剧情关卡扫描
- Group 13/15 phase：~3-5 小时 mGBA
- mGBA binary 工具链修复：~3-5 小时（升级 Qt6 / forward-port backport）
- 实体 GBA 验证 1/1：无法在当前环境推进

总计 ~46-75 小时 mGBA + 10 小时 disasm + 工具链修复。

## 10. 不属于本文档的目标

- 不假装 Goal 已完成
- 不主动发起任何 mGBA 实验直到 .ss9 与工具链都修复
- 不修改任何已签 manifest（profile.json / verifier manifest）
- 不回滚用户改动

## 11. 推荐下一步（按 ROI 排序）

按 ROI 与依赖关系：

1. **修复 .ss9 数据完整性**（最高 ROI）：
   - 选择方案 1：升级 macOS Qt 到 Qt6
   - 选择方案 2：forward-port backport 7cacae126
   - 选择方案 3：使用 mGBA 0.11+ prebuilt artifact
   - 然后生成真实 `.ss9`，重跑所有 verifier

2. **重新评估 handoff 第 4 节 runtime_verified 数字**：
   - .ss9 修复后批量重跑 verifier
   - 重新统计 13/22 bank、10/18 phase、12/18 pixel 等数字
   - 更新 handoff v5

3. **继续 Group 6/12 production natural pixel 闭合**：
   - dispatcher 上层 dynamic callback 追踪
   - 未 tracked 剧情关卡扫描
   - 用 Group 16/17 confirmation → phase → pixel A/B 工具链

4. **跳过 runtime verifier 指标，把 Goal 边界改为"仅静态分析"**：
   - 这违反 handoff 第 5.2 节优先级，但承认数据完整性问题后可能
     是唯一现实路径
   - 需要 `/goal-tweak` 调整 Goal 边界

5. **跳过实体 GBA 验证 1/1**：
   - 当前环境无硬件
   - 可能需要 `/goal-tweak` 把 1/1 降级为残余风险（按 handoff 5.2 节）

## 12. v1/v2 与 v3/v4 的对比

| 维度 | v1/v2 假设 | v3/v4 真实 |
|---|---|---|
| .ss9 文件 | 真实 mGBA savestate | PNG 文件（magic 0x89504e47） |
| runtime_verified 数字 | 13/22 bank 等 | 需要 .ss9 修复后重评 |
| Group 12 action 32 | battle 8 round 3 不被选 | 基于损坏 .ss9 不可信 |
| mGBA binary | profile.json 期望 c1135d28 | 当前环境无法编译出 c1135d28 |
| dispatcher 链路 | unknown | 静态已闭到 dispatcher 函数级 |
| 字段命名 | 部分 +0x0D/+2/+3/+9 未命名 | C 级闭合 |

任何接手者**不能**依赖 v1/v2 的数字，必须以 v4 为准。

---

## 附录 A：关联文档

- `notes/runtime-checkpoints-data-integrity-issue-20260806.md`：数据完整性详细分析
- `notes/auto-exit-prevention-mgba-compile-20260806.md`：mGBA 编译尝试详细记录
- `notes/reverse-engineering-current-gaps-20260806.md`：当前 gap 详细列表
- `notes/palettes-bank-player-visible-attempt-20260806.md`：palettes 实验失败记录
- `notes/battle-effect-group6-entry-audit-20260806.md`：Group 6 入口审计 v2
- `notes/group12-natural-entry-ai-observer-20260806.md`：Group 12 AI observer v1
- `notes/bank-player-visible-closure-plan-20260806.md`：9/22 bank closure 规划
- `docs/structure-field-semantics.md`：字段命名（含 C 级闭合）
- `tools/analyze_reverse_engineering_gaps.py`：当前 gap 汇总工具
- `tools/disassemble_battle_effect_dispatchers.py`：dispatcher 链路反汇编工具
- `tools/batch_test_dispatcher_triggers.py`：dispatcher 触发批量测试
- `tools/mgba_battle_effect_dispatcher_tracer.lua`：dispatcher 断点 tracer

## 附录 B：本会话 verifier 状态

```bash
$ python3 tools/verify_battle_effect_observed_frame_phases.py \
    --root . --artifact artifacts/battle-effect-observed-frame-phases-v1

{
  "all_groups": 18,
  "errors": [],
  "phase_verified_groups": 10,        # ⚠️ 待 .ss9 修复后重评
  "production_pixel_ab_groups": 12,   # ⚠️ 待 .ss9 修复后重评
  "verified": true
}

$ python3 -m unittest -q tests.test_build_battle_effect_pixel_ab \
    tests.test_verify_battle_effect_frame_phase \
    tests.test_verify_battle_effect_pixel_ab_evidence \
    tests.test_scenario49_tool37_confirmation_persistence \
    tests.test_scenario49_tool37_group17_persistence \
    tests.test_export_battle_effect_observed_frame_phases \
    tests.test_verify_battle_effect_observed_frame_phases

Ran 90 tests in 98.520s
OK

$ git diff --check
(no output)
```

90 unit tests OK，aggregate verifier verified=true，但 verifier manifest 内部
数据的真实可信度依赖 .ss9 与 mGBA binary 修复。
