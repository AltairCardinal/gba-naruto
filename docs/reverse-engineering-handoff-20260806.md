# 木叶战记 GBA 逆向工程交接（2026-08-06）

> 本文是当前权威交接。`docs/reverse-engineering-macos-intel-handoff-20260715.md`
> 保留为历史环境迁移记录，其中的 scenario 41 初期状态、旧分支和下一步计划已经过期。

## 1. 当前停止状态

- “真实、可审计的 100% 完成逆向工程” Goal 当前状态是 **`paused`**。
- 用户最后的执行边界是：暂停完全逆向目标，只完成当时手头的 Group 17，然后统计进度。
- Group 17 已完成、验证并提交；**不得自动启动 Group 6/7/8/9/10/12**。
- 接手 agent 只有在用户明确恢复 Goal 或下达新的写入任务后，才能继续逆向写入或启动
  mGBA。只读审计、解释和交接不等于恢复 Goal。
- 后续不使用 Comet；直接按 Goal、`AGENTS.md`、路线图、测试和证据执行。

Goal 在暂停时记录的累计消耗为：

- tokens：`113,635,646`
- wall time：`650,396 s`（约 180.67 小时）

这些是整个长期 Goal 的累计值，不是 Group 17 单项成本。

## 2. 仓库、工作树和 Git 状态

逆向工程不在默认 Butano 工作树中继续：

| 用途 | 路径 | 分支 |
|---|---|---|
| 逆向工程 | `/Users/altair/github/gba-naruto-reverse` | `codex/reverse-engineering` |
| 默认/Butano 工作 | `/Users/altair/github/gba-naruto` | 以该工作树当前状态为准 |

当前逆向 HEAD：

```text
686c555b8 reverse: close natural Group 17 pixel evidence
```

上两个里程碑：

```text
83303003b reverse: close natural Group 16 pixel evidence
8e39707c3 reverse: close natural Group 4 pixel evidence
```

Group 17 提交后逆向工作树是干净的。本文创建后会成为唯一新改动；接手时必须重新运行：

```bash
cd /Users/altair/github/gba-naruto-reverse
git status --short --branch
git log -3 --oneline --decorate
git worktree list
```

不要在默认工作树复制整个逆向工作树，也不要让 Butano 依赖 `build/experiments/`、未跟踪
文件或绝对路径。跨分支复用遵循 `docs/butano-reverse-results-guide.md`，只引入已提交且有
manifest/verifier 的成果。没有单独授权不得 push。

## 3. 最后完成的 Group 17

Group 17 / sequence 20 已从原版忍具 37 的自然 UI 路线闭合到精确帧事务和修改 ROM
最终像素 A/B。

### 3.1 静态与自然入口

- 忍具 ID：`37`
- encoded action：`0xA5` / `165`
- 忍具表动态 sequence：`0`
- handler：`0x0807ED20`
- selector callsite：`0x0807ED3A`
- callsite 硬编码 sequence：`20`
- resource group：`17`
- graphics pointer entry：ROM offset `0x5991A4`
- 相邻 palette pointer entry：`0x5991A8`，必须保持独立，不能因内容相同而与 Group 16
  合并。

独立 verifier 会读取基准 ROM 的 handler table、callsite 前一条 `MOVS #20` 和 BL 目标，
不能只依赖 profile 自述。

### 3.2 可复用 checkpoint

最终确认页：

```text
artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-confirmation.ss9
SHA-256 af37457d4cd41e180e61338fed77d6322b4aecd21386917739f2e56599708a46
```

确认页证据：

```text
artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-confirmation-evidence.json
SHA-256 dc8663ee50f2159e1eece70640e0ceb8f8cc6db7235c98ca4f306331dab0ab6d
```

提交后的活动状态：

```text
artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-group17-active.ss9
SHA-256 ac99cf9eba9582bad085226dd8683f33babafc3df83a0647e0deb05a9e76755f
```

活动证据：

```text
artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-group17-active-evidence.json
SHA-256 95af37047ce133f11d1a9bb0e8c74208b62d8a802510c73a1a2b59629513d023
```

确认后仅输入 `A:5:13`。capture frame 160 的唯一 Group 17 task 位于 slot 125 / 
`0x03005904`，flags `0xC1003391`，definition/animation 为
`0x083478B4/0x083478F0`。

### 3.3 Phase 与像素证据

Phase artifact：

```text
artifacts/battle-effect-frame-phase-group17-natural-v1/
```

- frame `132/132/133`
- renderer `0x08063328`
- submit `0x08061126`
- ack `0x080612AA`
- pending `0→1→0`
- 目标 task ordinal `[2,2,2]`

Pixel artifact：

```text
artifacts/battle-effect-group17-pixel-ab-v1/
```

- 两份 16 MiB ROM 只重定向 Group 17 graphics 指针；
- candidate 只把解压 graphics offset 22 的字节 `0x14→0x34`；
- baseline/candidate LZ77 大小均为 103 bytes；
- 六个运行时内存域仅 OBJ-VRAM `0x06014E16` 一字节不同；
- 同一源 tile 被三个 component 使用，其中一个水平翻转；
- 最终像素差恰为 `(165,92)`、`(194,95)`、`(173,97)`，均从
  `[247,255,222]` 变为 `[115,123,107]`。

详细说明：`notes/battle-effect-group17-natural-pixel-ab-20260802.md`。

## 4. 当前可审计进度

不要给出一个任意加权的“全项目总百分比”。静态提取、运行时因果、人类语义和实体硬件
发布门不是同一种分母。当前硬指标如下：

| 类别 | 百分比 | 分子/分母与边界 |
|---|---:|---|
| 已知数据 bank 目录与 ROM 字节 | **100%** | 32/32；含 22 个有效 bank 和 10 个 disproved tombstone |
| 有效 bank 运行时身份 | **59.09%** | 13/22；另 9/22 仅 code-verified |
| 已枚举图像主目录静态导出 | **100%** | 地图 47/47、画布 61/61、角色战斗源帧 2004/2004、regular BG 12/12、角色场景包 9/9、战斗特效 18/18 |
| 战斗特效精确 phase | **55.56%** | 10/18 |
| 战斗特效 production 最终像素 | **66.67%** | 12/18 |
| 音频结构提取与整曲渲染 | **100%** | 217/217 tracks、79/79 waves、80/80 sound IDs |
| 音频 cue 人类语义 | **10%** | 8/80；其余 72 项必须保持 `unknown` |
| 对白与字库静态提取 | **100%** | 309/309 对白、4602/4602 逻辑字形 |
| 地图静态/资源写回 | **100%** | 47/47 maps、61/61 canvases、217/217 物理资源槽 |
| primary/alternate 章节入口表运行时身份 | **100%** | 112/112 |
| 角色/成长/技能 bank 运行时身份 | **100%** | 63+63+94 = 220/220 entries；部分字段语义仍未命名 |
| 实体 GBA 发布验证 | **0%** | 当前只有 mGBA/离线证据 |

完整统计口径：`notes/reverse-engineering-progress-snapshot-20260802.md`。

战斗特效当前集合：

```text
phase verified:       {1,2,3,4,5,11,14,16,17,18} = 10/18
production pixel A/B: {1,2,3,4,5,11,13,14,15,16,17,18} = 12/18
remaining pixel:      {6,7,8,9,10,12}
```

注意：18/18 特效已经有静态资源和至少一条自然或受控资源/task 身份，但这不能替代
production 最终像素、完整 affine/blend/时序/音频或实体 GBA 验证。

## 5. 剩余工作与恢复优先级

### 5.1 当前暂停点后的战斗特效

只有用户恢复完全逆向 Goal 后才执行：

1. Group 6–10 / sequences 8–12：目前只有 unresolved hardcoded immediate
   callsites，缺 handler/action/tool 的真实上游绑定。先批量做静态 producer 归因，
   不要盲跑 mGBA。
2. Group 12 / sequence 14：已有 action 32 静态关系，但当前 formation 路线中
   `formation_occurrence_count=0`，已有约 190 个 tracked state 也没有 action 32。
   必须先找到真实角色/关卡入口。
3. 找到真实入口后，复用 Group 16/17 已有的 confirmation → phase → pixel A/B 工具链；
   每组仍需单独证明 pointer 隔离、task 身份、OAM/VRAM 和最终像素。

不要把受控直接 selector 探针升级为 production 自然像素，也不要用目录名或旧 state 中
已经存在的 VRAM 冒充修改 ROM 的重新加载因果。

### 5.2 其他主要缺口

- 音频：72/80 cue 仍无可靠人类语义名；不要创造“官方名称”。
- 有效 bank：9/22 仍只有 code-verified，需要玩家可见的运行时语义闭环。
- 角色/技能：单位 `0xB4` 全字段、技能 `+2/+3/+9` 仍缺全量玩家可见命名。
- 图像：战斗特效剩余六组；完整 affine、blend、动态混合和音频同步没有统一全量门。
- 发布：实体 GBA 验证为 0/1，不能宣称“完美运行于 GBA 平台”。

路线图以 `docs/sequel-roadmap.md` 末尾为准，不要按旧聊天摘要恢复过期任务。

## 6. 验证命令

接手后先做只读验证；Goal 暂停时不要借验证之名生成新实验。

```bash
cd /Users/altair/github/gba-naruto-reverse

python3 tools/verify_battle_effect_frame_phase.py \
  --artifact artifacts/battle-effect-frame-phase-group17-natural-v1

python3 tools/verify_battle_effect_pixel_ab_evidence.py \
  --root . \
  --artifact artifacts/battle-effect-group17-pixel-ab-v1

python3 tools/verify_battle_effect_observed_frame_phases.py \
  --root . \
  --artifact artifacts/battle-effect-observed-frame-phases-v1

python3 -m unittest -q \
  tests.test_build_battle_effect_pixel_ab \
  tests.test_verify_battle_effect_frame_phase \
  tests.test_verify_battle_effect_pixel_ab_evidence \
  tests.test_scenario49_tool37_confirmation_persistence \
  tests.test_scenario49_tool37_group17_persistence \
  tests.test_export_battle_effect_observed_frame_phases \
  tests.test_verify_battle_effect_observed_frame_phases

git diff --check
```

最后一次验证结果：

- 90 项相关测试通过；
- Group 17 phase verifier：`verified=true, errors=[]`；
- Group 17 pixel verifier：`verified=true, errors=[]`；
- aggregate：`all_groups=18`、`phase_verified_groups=10`、
  `production_pixel_ab_groups=12`、`errors=[]`；
- 独立只读审查：无 Critical、Important 或 Minor 问题。

## 7. Manifest 重签依赖顺序

Group 17 收尾暴露了 artifact 的真实依赖拓扑。若以后修改通用 phase/pixel verifier，
不要逐个碰运气；按以下顺序刷新：

1. 固定并刷新 generic pixel artifacts；
2. 更新 `sequel/content/battle-effect-phase-capture/source-provenance-v1.json` 中引用的
   parent pixel manifest SHA；
3. 一次性刷新全部受影响的 frame-phase artifacts；
4. 更新 Group 3/18 natural pixel profile 中的 source phase manifest SHA；
5. 刷新 Group 3/18 natural pixel artifacts；
6. 最后重建 `artifacts/battle-effect-observed-frame-phases-v1/`。

使用现有工具，不手改生成 manifest：

```text
tools/rebuild_battle_effect_frame_phase_artifacts.py
tools/rebuild_battle_effect_pixel_ab_artifacts.py
tools/export_battle_effect_observed_frame_phases.py
```

重建工具会证明 capture payload 不变。Group 3/18 的 `raw.tar` 可因内部 provenance
元数据更新而改变整体 tar hash，但 capture PNG、savestate 和 graphics 等捕获字节必须
保持不变。

## 8. mGBA、内存和快照纪律

- mGBA、Chromium 和高开销静态任务必须经 `tools/run_guarded.py` 使用同一 heavy lock。
- 只清理本轮 owned process group，禁止按进程名全局 kill。
- 启动前检查可用内存；运行中记录 owned-tree RSS、超时、退出码和残留。
- Group 17 自然建点、phase 和 pixel 运行峰值约为 66 MiB、74.23 MiB、69.95 MiB，
  均无崩溃或 listener 残留。显著偏离应先停止并审计。
- 冗长导航前、关键输入前后建立 checkpoint，并先做零输入恢复验证。
- 单次实验只改变一个输入；保存 baseline/candidate 的 ROM、state、profile、guard、audit
  和 manifest 哈希。
- CPU 暂时为 0 不能单独证明挂死；同时检查帧、marker、wall/idle timeout 和进程树。

此前崩溃的主要诱因是无界实验产物、过多小文件进入 Git 工作树、孤儿 mGBA 和上下文膨胀。
临时数据进入 `build/experiments/<run-id>/`，只有经过 promotion 的小型成果进入
`artifacts/`；完成后归档或清理本轮实验目录。

## 9. 接手时的强制检查顺序

1. 读取当前工作树的 `AGENTS.md`，不要依赖本交接复述来替代规则。
2. 调用 Goal 状态；若不是 `active`，不得继续旧 Goal 写操作。
3. 检查所有存活代理，避免与另一个 writer 并发。
4. 检查 `git status`、HEAD、worktree 和未跟踪文件。
5. 阅读：
   - `docs/sequel-roadmap.md` 末尾；
   - `notes/reverse-engineering-progress-snapshot-20260802.md`；
   - `notes/battle-effect-group17-natural-pixel-ab-20260802.md`；
   - 本文。
6. 运行第 6 节只读验证。
7. 只有用户恢复 Goal 后，才建立下一个可验收里程碑；不要恢复 Comet 微步骤编排。

## 10. 不得遗失的边界

- `100% static extraction` 只对已枚举目录成立，不等于整个逆向工程 100%。
- `18/18 resource/task identity` 不等于 18/18 production pixel。
- mGBA 验证不等于实体 GBA 验证。
- code-verified bank 不等于玩家可见语义闭合。
- cue 候选不等于官方音频名。
- 子代理结论只是草稿/审查输入；最终判断必须回到本地代码、manifest、测试和证据。
- 不回滚用户改动、不使用破坏性 Git 命令、不自动 push。

本交接的目标不是催促接手 agent 立即继续，而是让其在用户决定恢复时能从已验证的暂停点
准确接续，不重跑 Group 17、不重复剧情导航，也不把局部 100% 冒充总目标完成。
