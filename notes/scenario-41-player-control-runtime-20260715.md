# Scenario 41 玩家控制运行时边界（2026-07-15）

## 结论

2026-07-17 的 canonical controller-entry 复验已经接纳首个玩家控制 checkpoint：
`artifacts/runtime-checkpoints/scenario-41-player-turn.ss9`，SHA-256
`ba411edee4ccf73c1b5a8392735d23dbbef6f8edce5240aef7acdcd76c436171`。fresh PCO1
在 `0x08073946` 记录 selector `(9,0,1)` / sequence 1，fresh PCA1 在
`0x08073BAC` 记录 current slot 1 / sequence 2；slot 1 映射到
`0x02024294` 的同一 WRAM unit record：character 1、affiliation 0、坐标 `(4,10)`。
基础 ROM 可见对照与独立 GDB direct-PC 证据均通过，fresh re-review 结论为
`Spec PASS / Quality APPROVED`。

下述 2026-07-15 结论保留为 **superseded 历史**：当时只接纳了稳定的 scenario 41
“开始任务”行 checkpoint，玩家控制确实仍为 `not-proven`。从该行发送一次、且仅一次实例内 `KeyZ/A`，observer ROM 与 base ROM
都自然进入相同的 scenario 41 pre-controller lineup/deployment；两者的前台画面、map、formation、单位与声明的非目标 WRAM
逐字段一致。然而 `0x08073946 -> 0x0806F718` 的 `PCO1` 和
`0x080739D8 -> 0x08069DB8` 的 `PCU1` 在 post-load baseline 与最终样本中都保持
24-byte 全零，所以 Task 4 evaluator 正确返回 `player-observer-not-fresh`。

该历史运行只证明稳定 pre-controller 画面和 observer ROM 的行为等价性，不证明真实 battle-controller
entry、玩家接管、动作提交、胜利、
EXP 或升级；当时没有创建或接纳 `scenario-41-player-turn.ss9`。后来的正证据证明了更晚的
canonical player-control 边界，不把旧 suffix 改写为当时已经证明。

## 2026-07-17 canonical 玩家控制验收

### 输入与 checkpoint 谱系

从 accepted `scenario-41-controller-entry.ss9`（SHA-256 `4569846c…cd6`）到接纳 p1 的
audit input/output SHA 图共 23 条连续边，起止 hash 完整闭合。显式输入严格为九个 A：

```text
A, A, A, A, A, A, A, A, A
```

其余边全部记录 `inputs=[]`，包括每次 wait/settle、action anchor、周期采样派生 anchor、
以及最终 p64 replay；零输入推进帧不计作按键。base-ROM final-A transient state
`25288f5a…146a` 本身没有满足 `H[0]=H[p]=H[2p]`，因此保留为 direct candidate 的
`not-proven` 负证据。随后取其零输入 frame-1 为 anchor（`6d13314f…1a8e`），从该 anchor
重新采样 600 帧，analyzer 选择 `p=64`、匹配帧 `[0,64,128]`。两段独立 replay 均为
`inputs=[]`：p1 为 `ba411ede…6171`，p2 为 `6b95d5f5…263a0`；两者与 anchor 的 PNG/RGB、
battle/map/unit/action fields/tasks/CPSR 一致。p1 机械复制为 tracked checkpoint。

### fresh observer、基础 ROM 对照与独立证据

- evaluator：`build/scenario-41-active-current-evaluator-20260717/evaluator.json`
  (`539e04b9…06280`)，结果 `player-control-verified`；独立 review
  `independent-review.json` (`c44bc6eb…0b481`) 为 `PASS/APPROVED`。
- baseline counter、PCU1、PCO1、PCA1 全零。final counter 为 2；PCO1 在
  `0x08073946` 命中一次并发布 `(9,0,1)` / sequence 1 / event 1；canonical PCA1 在
  `0x08073BAC` 命中一次并发布 slot 1 / sequence 2 / event 3。legacy PCU1 本链保持零，
  不影响 canonical `selector + PCA` evidence alternative。
- runtime 状态为 battle 41，map `36×44`、grid `(9,22)`；slot 1 的 WRAM record
  `0x02024294` 为 character 1、byte `+3=13`、affiliation 0、当前位置/初始位置 `(4,10)`。
  PCO 的 9 是 selector accept-mask 参数，不是 unit slot；PCA `r0=1` 才是 current slot。
- 基础 ROM 对照 `build/scenario-41-base-control-comparison-20260717/comparison.json`
  (`fd5e6cbc…fb505`) 使用相同输入时序，七个 PNG 文件逐字节相同，全部边界的
  battle/map/unit/task 状态一致。full savestate 差异只来自 observer scratch 与两个相邻
  capture PC/IWRAM timing sample，不是用户可见行为变化。
- 基础 ROM 独立 GDB 证据 `build/scenario-41-base-gdb-evidence-20260717/evidence.json`
  (`48e53879…a391`) 在未打补丁 ROM 上精确停于 `0x08073946` 与 `0x08073BAC`；寄存器分别
  复核 `(9,0,1)` 与 current slot 1。失败的 selection-after-PCO breakpoint 尝试仍保留为
  边界选晚的 `not-proven` 负证据。

### 资源、用途与边界

所有 checkpoint acceptance 运行 guard 均 completed、non-degraded，最大 tree RSS
`52.30078125 MiB`；独立 GDB 成功轮最大 `132.55078125 MiB`，最终 `rom/base.sav` 不存在且
mGBA process clean。该 checkpoint 可作为第一回合自然行动的起点。下一步从此状态加载
MOVEDONE observer，继续短小、显式、逐边界输入。

这里仍未证明 MOVEDONE、第一回合完成、胜利谓词/result、battle exit 或 postbattle；也未证明
EXP、等级或训练点。不得从 player-control checkpoint 倒推这些后续边界。

## 资源预检与执行约束

- 首次预检可用物理内存 `5946.75 MiB`，shared heavy lock 可独占；后续每次运行均
  通过 `tools/run_guarded.py` 串行启动。
- 所有计划都禁用了 adaptive back、settle confirm 与其他 recovery 输入。单 A 计划的
  audit 只有 `tail/step 1/KeyZ/A/125 ms/explicit`，down/up 均完成；automatic 列表为空。
- 最高 owned-tree RSS 是 `622.47265625 MiB`。该次 observer 运行已先写完结果、截图与
  savestate，随后 guard 的原始终止值是 `idle-timeout/124`。证据文件时间早于 timeout，
  但六份 raw guard summary 都没有持久记录 residue、owned-tree postcheck 或 2345 listener
  postcheck；因此这三项统一标为 `not-recorded`，不能把当时的人工终检当作可复核证据。
  此资源退出不把 `not-proven` 升级或降级为正证据。

## 持久复现元数据与来源

`artifacts/runtime-checkpoints/scenario-41-player-control-evidence.json` 的 `runs` 为六轮逐轮
保存 ROM/checkpoint 路径与重算 SHA-256、精确 guard 命令，以及仅含证据相关变量的
`PROBE_*` allowlist。原始 probe/guard JSON 没有保存环境变量；这些命令和配置来自当时的
Task 5 操作者记录、执行计划与持久 input audit，明确标为 `operator_recorded`，不声称是
raw probe 自带元数据。ROM、checkpoint、result、截图、state dump 和 guard 文件哈希均按
当前文件重新计算核对。

可按 run id 复制配置并执行；例如重放 `observer-start-row-a`：

```powershell
$evidence = Get-Content -Raw artifacts/runtime-checkpoints/scenario-41-player-control-evidence.json | ConvertFrom-Json
$run = $evidence.runs | Where-Object id -eq 'observer-start-row-a'
$run.probe_environment.PSObject.Properties | ForEach-Object { Set-Item -LiteralPath "Env:$($_.Name)" -Value ([string]$_.Value) }
$parts = $run.exact_command.Split(' ')
& $parts[0] $parts[1..($parts.Count - 1)]
```

其余可复制 run id 为 `zero-replay-1`、`zero-replay-2`、`base-start-row-a`、
`battle-entry-zero` 与 `battle-entry-a`。`PROBE_INPUT_MODE=instance-api` 表示实例内
`window.__mGBA.buttonPress/buttonUnpress` 路径；`PROBE_KEY_HOLD_MS=125` 固定 audit 中的
按键持续时间。空的 `PROBE_TAIL_KEYS` 或 `PROBE_STATE_DUMP` 表示该轮没有对应输入或导出。

六轮 raw guard 终止值如下；`interpretation` 与原始值分开，不能把退出状态当成 PASS：

| Run | Raw reason / exit | Peak MiB | Backend | Durable postcheck |
|---|---|---:|---|---|
| zero replay 1 | `child-exit / 1` | 568.48828125 | Job Object, non-degraded | `not-recorded` |
| zero replay 2 | `child-exit / 1` | 539.46484375 | Job Object, non-degraded | `not-recorded` |
| observer start-row A | `idle-timeout / 124` | 622.47265625 | Job Object, non-degraded | `not-recorded` |
| base start-row A | `child-exit / 1` | 551.0703125 | Job Object, non-degraded | `not-recorded` |
| battle-entry zero | `child-exit / 1` | 556.0390625 | Job Object, non-degraded | `not-recorded` |
| battle-entry A | `child-exit / 1` | 552.1015625 | Job Object, non-degraded | `not-recorded` |

Task 5 的 Node 验证与这六轮 runtime probe 不混算：首次默认 reporter 的 raw guard 是
`idle-timeout/124`，属于失败；随后 TAP streaming retry 才是 `completed/0`，属于 PASS。

## 实验 1：start-row 两轮零输入稳定性

候选 `build/natural-s41-menu-index2.ss9` 的实际 SHA-256 是
`e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81`，与 ledger
登记一致。两次 base-ROM 重放都使用：

```text
START=0, ADVANCE=0, TAIL empty, SETTLE_CONFIRM=0,
ADAPTIVE_BACK=0, STOP_ON_MATCH=0, FORCE_SETTLE=1, SETTLE_COUNT=8
```

两轮均停在同一蓝色“开始任务”选中行，battle ID `0`、map `00000000`、formation
为空、`PCO1/PCU1` 全零、input events 为空。排除页面 FPS/浏览器 chrome 像素、路径
和导出元数据后，最终 diagnostics 没有差异。由此复制为
`artifacts/runtime-checkpoints/scenario-41-start-row.ss9`；复制后 hash 仍为上述值。

原始报告与 guard 峰值：

- `build/task5-zero-replay-1.json`，`568.48828125 MiB`；
- `build/task5-zero-replay-2.json`，`539.46484375 MiB`。

接纳只证明 checkpoint 的来源、UI 和零输入稳定性。动态运行没有证明它处于两个 hook
之前，因此 ledger 的 `before_hooks` 与 `allowed_evidence` 都保守留空。

## 实验 2：start-row 的 observer/base 单 A 对照

observer ROM SHA-256：
`2992a8434da391d6191ddf71119c9409dcf3ca5223010d5f9d405e0b35a96dd8`。
从 accepted start-row 的 observer 运行仅发送一个 A，20 settle polls 后得到：

- battle `41`，map `36x44` / grid `9x22`；
- slot 1 Naruto，affiliation 0，active，`(4,10)`；
- slot 2 Iruka，affiliation 1，active，`(4,4)`；
- foreground `battle-map`，画面显示 Naruto 与白色选择框；
- controlled diagnostic 唯一且有效；
- `PCO1` 与 `PCU1` baseline/final 均为
  `000000000000000000000000000000000000000000000000`；
- evaluator：`verified=false`，reason=`player-observer-not-fresh`。

同 checkpoint、同单 A 的 `rom/base.gba` control 得到相同前台战斗画面；`status`、
unit bytes/positions/summaries/templates、battle control、map、save/effect/chapter/audio/
natural-load/postbattle probes、screen state 与 input audit 逐字段全部相同。observer ROM
没有改变这段用户行为，但 strict arrival 不能替代 fresh hook。

关键文件：

- observer：`build/task5-after-start-a.json`、`build/task5-after-start-a-settle.png`；其
  state 已持久化为 `artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9`；
- base control：`build/task5-base-control-start-a.json`、
  `build/task5-base-control-start-a-settle.png`、
  `build/task5-base-control-start-a.ss9`。

## 实验 3：临时 battle-entry candidate

`build/task5-after-start-a.ss9` 在实验当时仅作为 build candidate；复核后同哈希副本已作为
pre-controller 负边界固化为 `artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9`。零输入重放
8 polls 后仍为同一 battle/map/formation/白框画面，两个 scratch 仍全零，input events
为空。随后从该 candidate 另起一个独立计划，仅发送一次 A；20 polls 后 UI/WRAM 没有
形成可验收的新边界，两个 observer 仍全零，evaluator 仍为
`player-observer-not-fresh`。因此停止盲键探索，不把该 candidate 命名或接纳为
player-turn。

关键文件：

- 零输入：`build/task5-player-selection-zero.json`、
  `build/task5-player-selection-zero-settle.png`；
- 独立单 A：`build/task5-after-selection-a.json`、
  `build/task5-after-selection-a-settle.png`、`build/task5-after-selection-a.ss9`。

## 已知错误命名与证据边界

- `build/natural-s41-start-prompt.ss9` 实际是队伍/装备页，ledger 保持 rejected。
- `artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9` 经离线 task 栈复核只证明保存时活动链位于 pre-controller
  lineup/deployment：其链为 `0x0808F928 → 0x08088F10 → 0x0807509C →
  0x0806F718`，活动 unwind 没有 `0x0808F957`，不能作为 battle-controller entry 或 player turn 证据。
- `artifacts/runtime-checkpoints/actionable-move-grid.ss9` 已位于旧玩家选择 hook 之后，
  只能用于后续行动导航或负对照，不能倒推本轮 fresh player-control call。
- 对可能已越过 hook 的 savestate，加载 observer ROM 后 scratch 为零只表示“加载后的
  后缀没有再次执行 hook”。savestate 会恢复 WRAM，却不会重放保存前的调用；因此零值
  既不能否定历史调用，也不能成为正证据。
- 本轮 observer 从 accepted start-row 就已激活，因此它的零 scratch 可以严格说明：
  两个已 instrument 的 call site 在被观察的 start-row→battle-entry 后缀没有执行。
  它不能说明没有其他 scenario 41 tutorial player-control 路径。

## 下一步

不要继续猜 action-dispatch 按键。应先完成白框所在的 lineup/deployment，并用 task 栈
`0x0808F957` 或 fresh observer 证明 `0x0808F952 → 0x080732B4`；新的正证据仍
必须使用 post-load baseline、单一显式输入、fresh shared sequence、独立 controlled-unit
诊断、foreground battle screen 和 base-ROM control 的同一组门禁。

## 2026-07-15 controller-path 后续

strict-GDB 探针没有受审计输入通道，因此没有执行无输入推动的 2×5 breakpoint 矩阵。
改用五点 published-call observer 后，`actionable-move-grid.ss9` 的零输入 baseline 与显式
`KeyX,Down,Down,A,A` final dump 逐字节相同，compare 的 `fresh_records=[]`。由于预设
正对照没有成立，scenario 41 白框的零输入/单 A 两轮未执行，玩家控制继续为
`not-proven`（这是 2026-07-15 当时的结论，现已由上文 2026-07-17 canonical 证据
supersede）。随后离线 task 栈复核确认白框 state 保存时的活动链不在 `0x080732B4` 内，所以应先关闭
pre-controller 门，再寻找穿过 `0x08073A04` 的 controller checkpoint。详见
`notes/scenario-41-controller-path-runtime-20260715.md` 与
`notes/scenario-41-savestate-context-reanalysis-20260715.md`。
