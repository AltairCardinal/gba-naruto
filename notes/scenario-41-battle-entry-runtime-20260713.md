# scenario 41 开始任务与战斗入口边界（2026-07-13）

## 已确认的自然 UI 路线

scenario 41 剧情正常终止后的任务准备菜单有四个纵向入口。逐项重放确认：

- A：队伍/装备；
- Down,A：查看战场；
- Down,Down,A：“开始任务？”确认框；
- Down,Down,Down,A：保存页面。

在“开始任务？”保持默认“是”并输入 A 后，画面进入 Naruto 与 Iruka 的战斗
表现。与此前已撤销的 transient battle-map 不同，这次零输入继续运行后，连续六个
采样周期都保持：

- battle ID 41；
- map 36×44 / grid 9×22；
- slot 1 Naruto (4,10)；
- slot 2 Iruka (4,4)；
- screen classifier 为 battle-map；
- strict arrival 的 formation、battle ID、map 与 visible 四项全部为真。

临时提示 checkpoint SHA-256 为
8b94de1a84b4a5aff775bd783237a2fa1ab651d945de8bc3518c66fd1899967b，
临时战斗 checkpoint SHA-256 为
5d12491887f858cf49e92f665f322788258c623c4283a79dcf0f458d7c0120cb。
紧凑证据已固化到
artifacts/runtime-checkpoints/scenario-41-battle-entry-evidence.json。

## 诊断探针与 savestate 边界

tools/build_battle_start_runtime_probe.py 包装：

- prebattle menu call 0x0808F894 → 0x0808F190；
- start-task call 0x0808FA0A → 0x08086A54；
- lineup call 0x08086B0A → 0x080861C8；
- lineup exit 0x080866AC；
- deploy call 0x08086BD0 → 0x080868AC。

caller wrapper 的 lineup 计数保留在 scratch +0x20；exit hook 改为独立
scratch+0x40，避免一次正常返回被误读成两个调用。修正后探针 ROM SHA-256：
ca701983f5d566dc468f57e49e00ae2d61d8ef659395ed84284057514e1d52f5。

从“开始任务？”checkpoint 加载该新 ROM 并选择“是”，上述五个计数仍全部为零。
这不是旧 ss9 覆盖新 ROM：ss9 的 gbAs 数据只序列化 CPU/I/O/VRAM/IWRAM/EWRAM，
加载后 ROM bus 的 0x0808F894 明确读到新 BL，连续 ROM bytes 也与新 probe ROM
一致。零计数的真实含义是 checkpoint 已经越过这些调用，或恢复后走的是函数内部
continuation。

因此后续不得继续投入“savestate 后重注入 ROM”。应把 hook 移到恢复后必经的更近
控制边界；找不到稳定后继边界时才从冷启动重放。

## 尚未闭合的门槛

当前画面仍可能是开场自动交战/表现。B 后可切到 Iruka 战斗表现，但尚未证明玩家能
提交一个正常战斗行动，也未观察到胜利、EXP 或升级：

- A880=0；
- Naruto level 1；
- EXP 100；
- template +0xBA=0；
- secondary levels 仍为 FF。

所以该证据只升级“任务确认后能稳定进入 battle 41”的边界，不升级
sequel/content/levels/bank.json。下一步必须先找到玩家控制交接或自动演出终止
边界，再完成战斗并捕获 level 2、非零训练点与
0x08093070 → 0x080932CA。

重要地址：start-task 0x08086A54；lineup 0x080861C8；deploy
0x080868AC；battle control 0x02026804；Naruto template
0x02022EF0；训练点 0x02022FAA。

## 下一阶段的静态控制链

为避免继续在战前 selector 上重复试探，后续探针应沿战斗主控制器
`0x080732B4` 的已确认分支布置：

- `0x080738C0`：区分玩家/AI 行动方；
- `0x08073940`：玩家单位选择，命中即可证明玩家控制已接管；
- `0x080739D0`：确定当前单位；
- `0x08073A04`：行动菜单；
- `0x080722A8`：行动/MOVEDONE 事件队列；
- `0x0807444E`：玩家行动结算后的胜负检查；
- `0x080777FC`：实际胜负谓词；
- `0x08073068`：把结果写到 `0x02026807`；
- `0x08074FDA`：战斗控制器退出；
- `0x08074EE6`：进入 postbattle state `0xF400`。

scenario 41 的胜负描述符位于 ROM file `0x596804`。类型 1 条件扫描 slot 1..12：
unit `+0xC0` bit 0 是队伍，bit `0x80` 表示单位不再有效存活。当前 Iruka 的
`+0xC0=0x11`，仍是有效队伍 1 单位，所以现有 checkpoint 本身不能作为胜利证据。
自然教程路线仍是第一回合移动到 `(4,7)`，第二回合移动到宝箱 `(4,11)` 上方
`(4,10)` 并结束行动；应在这条路线捕获
`MOVEDONE → 胜负检查 → 结果写入 → postbattle`，再继续 levels 消费链。
