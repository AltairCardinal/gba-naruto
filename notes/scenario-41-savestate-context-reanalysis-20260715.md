# Scenario 41 savestate 任务上下文复核（2026-07-15）

## 结论纠正

`artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9` 保存时的活动任务链
不在 `0x080732B4` 战斗主控制器内，而是在开始任务后的编成/部署链中；画面和 battle/map WRAM 足以通过旧
`strict battle arrival`，但不足以证明 battle controller 已启动。此前“稳定进入战斗表现”
必须收窄为“稳定进入 scenario 41 的 pre-controller lineup/deployment 画面”。玩家控制、
MOVEDONE、胜利、EXP 与升级仍全部 `not-proven`。

## 无模拟器复核方法

mGBA `.ss9` 是 PNG 容器；`gbAs` chunk 经 zlib 解压后是固定 `0x61000`
bytes 的 `GBASerializedState`。CPU GPR 位于 `+0x20`，IWRAM 位于 `+0x19000`，
EWRAM 位于 `+0x21000`。格式依据是 mGBA 0.10.5 官方
`include/mgba/internal/gba/serialize.h`；项目内复现工具为
`tools/inspect_mgba_savestate.py`。

游戏自己的协作式任务切换入口是 `0x0809C574`，ARM veneer 跳到
`0x0800026C`。后者把任务寄存器保存到 `0x03000A88` 起、stride `0x4C` 的 8 个
context；当前 context 指针位于 `0x03000D18`，主循环保存的 LR/SP 位于
`0x03002E1C/0x03002E20`。因此硬件 CPU PC 停在 `0x0806112A/2C` 的帧循环时，仍可从
任务 context 和任务栈恢复真正的游戏调用链。

## 两个 checkpoint 的可核对差异

### `artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9`

- SHA-256：`894dddec77d56d98bc9aca4a1edae3ac4c88206930f39fe06d627fe7bcf7110f`；
- `[0x0202680C]=0`；该 byte 只控制 `0x080732B4` 入口把初始 `r6` 置为
  `0` 或 `0x1000`，不是持久 dispatcher state；
- task 2：SP `0x030011FC`，resume PC `0x0806F996`；
- 栈上的 checked returns 包含 `0x0807513F`、`0x08089029`、`0x0808F92D`；
- 对应链为 `0x0808F928 → 0x08088F10 → 0x08089020/24 →
  0x08075184/0x0807509C → 0x0806F718`；
- 当前活动 unwind 中没有 `0x0808F957`，也没有 `0x080732B4` 内部 return；所以不能把白框画面
  记为 battle-controller entry；
- `0x0807513E` 在内层 `0x0806F718` 返回后读取 `0x0300000E & 2`（B），但当前
  context 仍在 `0x0806F718` 的 yield loop；不能据此声称“单 B 必然开始战斗”。

### `artifacts/runtime-checkpoints/actionable-move-grid.ss9`

- SHA-256：`4821a3a6694d32871a23bbea6a93ba1724663cb4a3c6e5f691d4fd48a5635fac`；
- `[0x0202680C]=1`；
- task 2：SP `0x03001154`；
- 当前活动 unwind 的 raw return words 为 `0x080718F3 → 0x08074197 →
  0x0808F957`；`0x080751A7` 是栈中的局部/陈旧 word，不属于活动 unwind；
- `0x0808F957` 是 `0x0808F952 → 0x080732B4` 的返回点，证明该 checkpoint 的
  suspended task 确实处于主控制器调用内。

这解释了 controller-path probe 的正对照为何没有覆盖所选五个更下游 BL：
`actionable-move-grid` 虽已在控制器中，但当前挂起路径是 `0x08074190` 的其他状态；
五点 observer 不能倒推所有 controller state。

## dispatcher 静态边界

`0x080732B4` 是唯一函数入口，`0x080738C0/0x08073940/0x080739D0/0x08073A04`
是同一函数内部由局部 `r6` 分派的标签：

- `r6=0x1300 → 0x080738C0`；
- `r6=0x2000 → 0x08073940`；
- `r6=0x1020 → 0x080739D0`；
- `r6=0x3000 → 0x08073A04`。

`0x0807504E` 是公共收尾，不是持久状态写入器；`0x0807339C → 0x0807504E`
位于比较链前，但单独观察它仍需发布调用时 `r6`，现有 published-call ABI 不够。

## 下一验收门

下一步先完成 pre-controller lineup/deployment，而不是从白框直接探玩家行动：

1. 从 accepted `scenario-41-start-row.ss9` 复放，按静态确认的输入边界逐步导出 state；
2. 新 battle-entry checkpoint 必须满足当前活动 task unwind 含 `0x0808F957`（或 entry
   observer fresh 命中 `0x0808F952 → 0x080732B4`）；`[0x0202680C]` 只作入口模式补充记录，
   不作为必要条件；
3. 达到该门后，才观察 `r6=0x2000/0x3000` 与玩家选择/行动菜单；
4. 当前机器可用内存仅约 2.3 GiB，低内存来自项目外 Java/QEMU；本轮不启动 Chrome，
   也不结束用户进程。后续运行时实验仍必须经 `tools/run_guarded.py`。

本轮尝试了：有界 Thumb/ARM 反汇编、mGBA 官方 state layout、两个 savestate 的 CPU/
IWRAM/EWRAM/任务栈对比。学到的关键地址是 `0x03000A88`、`0x03000D18`、
`0x03002E1C/20`、`0x0809C574`、`0x0800026C`、`0x0808F928`、`0x0808F952`。
