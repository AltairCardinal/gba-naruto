# Scenario 41 lineup → controller 计划

> 当前白框 checkpoint 的活动 task 栈已通过离线分析证明位于 pre-controller lineup/deployment。
> 本计划只关闭 `0x0808F952 → 0x080732B4` 入口，不提前宣称玩家控制。

**目标：** 从 `artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9` 分段退出内层 unit-selection 与白框，选择
lineup 返回值 2，并固化第一个可离线证明 task 栈含 `0x0808F957` 的真实 controller
checkpoint。

**复用：** 继续使用 `play/_scripts/runtime-formation-probe.js`、base ROM、现有 state
load/export、input audit 和 `tools/run_guarded.py`。不新增 observer ROM；
`tools/inspect_mgba_savestate.py` 负责每段后的离线验收。

## 前置准入

1. 可用物理内存至少 4096 MiB；低于该值不启动 Chrome。该门槛高于 guard 默认值，是
   本轮外部 Java/QEMU 高占用下的保守运行门。
2. 项目 owned runtime=0、2345 listener=0、shared heavy lock 可用。
3. 校验 base ROM SHA-256
   `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`，输入 state
   SHA-256 `894dddec77d56d98bc9aca4a1edae3ac4c88206930f39fe06d627fe7bcf7110f`。
4. 所有运行固定 `PROBE_ADAPTIVE_BACK=0`、`PROBE_SETTLE_CONFIRM_EVERY=0`、
   `PROBE_STOP_ON_MATCH=0`、`PROBE_FORCE_SETTLE=1`、`PROBE_TAIL_DELAY_MS=600`。

## Step 1：第一 B，退出内层 `0x0806F718`

从 `artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9` 只发送一个显式 `KeyX/B`，导出
`build/scenario-41-after-unit-selection-b.ss9`。input audit 必须只有一个 B，automatic=0。

离线检查：

```powershell
python tools/inspect_mgba_savestate.py build/scenario-41-after-unit-selection-b.ss9 --output build/scenario-41-after-unit-selection-b-context.json
```

如果 task 2 仍在 `0x0806F996`，允许再从原输入 state 以更长
`PROBE_TAIL_DELAY_MS=1200` 重试一次；禁止在同一运行自动补键。若恢复点已离开
`0x0806F718`，接受 Step 1。

## Step 2：第二 B，退出 `0x0807509C` 白框

从 Step 1 state 只发送一个显式 B，导出
`build/scenario-41-lineup-menu-return.ss9`。期望离开 `0x0807513E` 的
`[0x0300000E] & 2` 等待并回到 `0x08088F10` 内部菜单；截图必须不再是白框地图。

如果截图仍是白框或 task 栈仍含 `0x0807513F`，保持 not-proven 并停止，不追加第三个 B。

## Step 3：Down+A 选择 lineup 返回值 2

从 Step 2 state 发送且仅发送 `ArrowDown,KeyZ`。`0x08088F10` 当前已知 selection/result
为 1；Down+A 的目标是令它走 result 2，设置 `r7=0,r5=2` 返回。导出
`build/scenario-41-controller-entry-candidate.ss9`。

验收同时要求：

- task 2 栈中出现 return word `0x0808F957`；
- task 调用链位于 `0x0808F952 → 0x080732B4` 内；
- input audit 恰为 Down、A，automatic=0；
- base ROM，无 observer patch；
- guard completed/0、Windows Job Object、无项目进程残留。

只有全部成立才把 candidate 复制到 `artifacts/runtime-checkpoints/` 并加入 ledger。
若只满足旧 battle/map/screen arrival，仍判失败；旧 classifier 不再是 controller-entry
acceptance gate。`[0x0202680C]` 只记录为入口初始化局部 `r6` 的补充上下文，不作为
controller-entry 的必要条件。

## 后续边界

真实 controller checkpoint 固化后，下一任务才是观察局部 `r6`：
`0x2000 → 0x08073940` 玩家选择、`0x3000 → 0x08073A04` 行动菜单。此计划不证明
player turn、MOVEDONE、胜利、EXP、升级或 postbattle。
