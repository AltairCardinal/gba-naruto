# Scenario 41 自然胜利与战后世界地图（2026-07-18）

## 已证明边界

- 从已验收 `scenario-41-turn-1-complete` 沿自然输入继续，第二、第三回合均以行动结束；第 4 回合玩家从 `(5,6)` 移到 `(6,4)`，对 `(6,3)` 的敌人提交相邻技能。
- 技能演出后出现“胜利”，`0x02026807=1`。同一决定性 A 在 immutable base ROM 上重放，画面与 observer 运行完全一致，EWRAM/IWRAM 也逐字节一致；base-control run 为 `dae8d9689279c84745f3312dcfc0dfd0`。
- 胜利结果页显示经验/奖励，随后自然进入升级页和战后对白，最终回到木叶世界地图主菜单。没有强制 WRAM 结果、自动补键或跳过战斗。
- 两个 base-ROM 零输入可恢复快照已固化：
  - `scenario-41-victory.ss9`：`7a24a7a628c301493418d93e88ab239c0fbb6b77de139a67b91e8e0bcadf6200`，task 2 `0x08073114`；
  - `scenario-41-postbattle.ss9`：`950652381ae03ad60ad028f9063b9fc22f133ea532396fbafe7f5353d2553162`，task 2 `0x08067D02`。
- postbattle 零输入 run `5ad3c6ab83031b1e76525ab33517fc16` 峰值为 `52.4453125 MiB`；本批所有有效运行均 nondegraded，owned PGID 与监听端口清理完成。

## 输入与单位纠正

- 战斗单位记录 stride 是十进制 234 (`0xEA`)；敌人是索引 2，不是连续的索引 1。第三回合结算后玩家 `(5,6)`、敌人 `(6,3)`。
- 光标仍由 `0x02026A78/79` 给出。第 4 回合路线为选择玩家、移动到 `(6,4)`、打开技能、将目标光标上移到 `(6,3)`、确认技能与“可以吗？”提示。
- `0x08073114` 是等待胜利画面的稳定任务恢复点；世界地图主菜单复用常见菜单回调 `0x08067D02`，不能只凭该地址区分战前菜单和战后地图，必须同时使用画面和业务内存。

## 未证明边界

- 现有 `0x08074F2C` natural-save observer 在决定性胜利输入、胜利至世界地图整链，以及最终对白后 A 的 20/40/80 帧采样中均保持零。该结果未证明保存调用不可达：短暂 marker 可能在采样间被世界地图初始化清除。
- 因此本轮只接纳“自然胜利”和“战后世界地图”快照，不把 `0xF400` 瞬态或 `0x08074F2C` 自然保存命中写成已证明，也不给 ledger 的 `victory` / `postbattle` hook evidence 授权。
- `scenario-41-postbattle.ss9` 可直接作为 levels/升级字段运行时相关性的新起点；自然保存如仍是最终审计要求，应改用命中即落盘的 observer，而不是继续增加固定帧切片。

机器可读证据见 `artifacts/runtime-checkpoints/scenario-41-completion-evidence.json`。
