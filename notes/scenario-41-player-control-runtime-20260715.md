# Scenario 41 玩家控制运行时边界（2026-07-15）

## 结论

本轮接纳了稳定的 scenario 41 “开始任务”行 checkpoint，但玩家控制仍是
`not-proven`。从该行发送一次、且仅一次实例内 `KeyZ/A`，observer ROM 与 base ROM
都自然进入 battle 41；两者的前台画面、map、formation、单位与声明的非目标 WRAM
逐字段一致。然而 `0x08073946 -> 0x0806F718` 的 `PCO1` 和
`0x080739D8 -> 0x08069DB8` 的 `PCU1` 在 post-load baseline 与最终样本中都保持
24-byte 全零，所以 Task 4 evaluator 正确返回 `player-observer-not-fresh`。

这证明了稳定入场和 observer ROM 的行为等价性，不证明玩家接管、动作提交、胜利、
EXP 或升级。没有创建或接纳 `scenario-41-player-turn.ss9`。

## 资源预检与执行约束

- 首次预检可用物理内存 `5946.75 MiB`，shared heavy lock 可独占；后续每次运行均
  通过 `tools/run_guarded.py` 串行启动。
- 所有计划都禁用了 adaptive back、settle confirm 与其他 recovery 输入。单 A 计划的
  audit 只有 `tail/step 1/KeyZ/A/125 ms/explicit`，down/up 均完成；automatic 列表为空。
- 每次运行后按命令行归属检查本次 probe tree，并检查 2345 listener；均无残留。
- 最高 owned-tree RSS 是 `622.47265625 MiB`。该次 observer 运行已先写完结果、截图与
  savestate，随后停在 browser close，guard 以 `idle-timeout` 精确终止 owned Job；证据
  文件时间早于 timeout，且 cleanup 后 residue/listener 都为空。此资源退出不把
  `not-proven` 升级或降级为正证据。

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

- observer：`build/task5-after-start-a.json`、`build/task5-after-start-a-settle.png`、
  `build/task5-after-start-a.ss9`；
- base control：`build/task5-base-control-start-a.json`、
  `build/task5-base-control-start-a-settle.png`、
  `build/task5-base-control-start-a.ss9`。

## 实验 3：临时 battle-entry candidate

`build/task5-after-start-a.ss9` 仅作为 build candidate，不进入 artifacts。零输入重放
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
- `build/task5-after-start-a.ss9` 只证明 strict battle-entry/白框边界，不是已经证明的
  player turn。
- `artifacts/runtime-checkpoints/actionable-move-grid.ss9` 已位于旧玩家选择 hook 之后，
  只能用于后续行动导航或负对照，不能倒推本轮 fresh player-control call。
- 对可能已越过 hook 的 savestate，加载 observer ROM 后 scratch 为零只表示“加载后的
  后缀没有再次执行 hook”。savestate 会恢复 WRAM，却不会重放保存前的调用；因此零值
  既不能否定历史调用，也不能成为正证据。
- 本轮 observer 从 accepted start-row 就已激活，因此它的零 scratch 可以严格说明：
  两个已 instrument 的 call site 在被观察的 start-row→battle-entry 后缀没有执行。
  它不能说明没有其他 scenario 41 tutorial player-control 路径。

## 下一步

不要继续猜按键。应先用静态调用图/严格 native breakpoint 定位 scenario 41 教程白框
状态实际消费 A/方向键的入口，再把 observer 移到该直接调用点或函数入口；新的正证据仍
必须使用 post-load baseline、单一显式输入、fresh shared sequence、独立 controlled-unit
诊断、foreground battle screen 和 base-ROM control 的同一组门禁。
