# levels / effect progression runtime probe（2026-07-13）

## 身份修正

`0x5459C8` 的 45×12-byte 表不是角色经验等级表，而是角色模板 `+0x50` 的 24 个
次槽/被动效果所引用的成长记录。`0x0806DDA4` 按 requested `target_type` 查询：

```text
record = 0x085459C8 + record_id*12
level_minus_one = stored_level-1
out_a = base_a + per_level_a*level_minus_one
out_b = base_b + per_level_b*level_minus_one
```

返回匹配的 slot index，无匹配返回 `0xFF`。15 个调用点请求 type
`0x0C,0x14..0x20`。

## 两条被否决的捷径

现有 actionable battle 与人物 checkpoint 中，Naruto 次槽虽保留 IDs 1..24，
stored levels 全为 `0xFF`，消费者会在读取 ROM 表项前跳过。

第一版诊断直接把 ROM 角色定义次槽改为 record 16 / level 1。它在到达资料页前改变
了游戏状态，同一输入落入“木叶旋风”演出，scratch 为零；该方案已撤销。

`tools/build_levels_runtime_probe.py` 现改为更安全的 call-local 方案：只在
`0x080890C2` 调 `0x0806DDA4` 的瞬间临时替换 EWRAM slot 0，调用返回后立即恢复，
ROM 角色定义完全不变。自然存档确实到达鸣人简介页，但该 UI 路线没有执行
`0x080890C2`：scratch `0x0203F100` 36 bytes 全零。control ROM SHA-256
`af7abe8fc8d4f023b0b4e6fd7c65a6a2a384e91b954e578c92b4868eb8ed3cfc`；
scratch SHA-256 `6db65fd59fd356f6729140571b5bcd6bb3b83492a16e1bf0a3884442fc3c8a0e`。

因此 levels 严格保持 `code_verified`。下一条有效路线必须先自然获得已激活的次槽，
优先固化 `0x080932CA` 的次槽升级/奖励 UI checkpoint，再对真实命中 record 的
`per_level_a` 做单字段 A/B。不能用强制激活把 bank 提前升级。

重要地址：table `0x5459C8..0x545BE3`；pair query `0x0806DDA4`；升级 consumer
`0x080932CA`。

## 自然升级入口补充

`0x080932CA` 属于角色升级后的修炼点分配 UI，不是普通术列表。自然链为：

```text
[0x0200A880] == 3
  -> 0x0808E16E calls 0x08093698
  -> 0x080937DE calls training-list controller 0x0809337C
  -> confirm row at 0x08093670 calls 0x08093070
  -> 0x080932CA consumes record +6 per_level_a
```

训练点字段纠正为 character template `+0xBA`；旧资料中的 `+0xAA` 是笔误。Naruto
template slot 1 基址 `0x02022EF0`，所以自然训练点地址是 `0x02022FAA`。现有所有
tracked ss9 的 `0x0200A880` 都不是 3，且 Naruto `+0xBA=0`，不能直接命中。

最短自然路线是从 `tutorial-ui-save.sav` 继续完成下一场足以令 Naruto 从经验
100/250 升级的战斗，等待游戏自动进入 state 3，再在分配前固化 checkpoint。成功
证据必须同时包含：`A880==3`、`template+BA>0`、`0x0808E16E/0x08093698` 命中、
训练 row type 4 与有效 levels ID；确认后还需 `0x08093070/0x080932CA` 命中、训练点
恰减 1、对应次槽等级加 1，并记录 `0x5459C8+ID*12` 与读出的 `+6` 值。最后只对
自然命中 record 的 `+6:n→n+1` 做 A/B。

## 真正 Continue 与升级前置状态

已在 `/tmp` 逐阶段稳定画面并重存临时 ss9，复现真正的存档读取流程；固定连续延迟
容易丢键边沿，自动化必须在每个屏幕边界等待稳定：

```text
冷启动安装 tutorial-ui-save
KeyZ×5 -> PUSH START
Enter -> 标题菜单（有效存档存在时 Continue 已预选）
KeyZ -> 存档槽页面
KeyZ -> “要读取记录档1吗？”
KeyZ -> “读取记录档1完成”
KeyZ -> 关闭完成提示，进入木叶主界面
```

真实恢复后：`A880=0`、`A88C=1`，battle/chapter control 为 0；Naruto template
`0x02022EF0` 为 ID 1、level 1、经验 `+0x10=100`、训练点 `+0xBA=0`、secondary
slot1 level `+0x51=FF`。这与标题人物图鉴路线明确区分。

从恢复态选择“移动→对战”后先进入 Naruto/木叶丸长对白；期间没有战斗、经验或
`A880` 变化。截图一度令该队伍/菜单界面被误判成标题人物图鉴；自然 selector 探针
现已撤销该判断。`tools/build_alternate_chapter_runtime_probe.py --natural-selector`
保留原始 primary/alternate 分支，只安装 selector/opcode hook。两次 selector hit 均
捕获 scenario 41 选择 primary `0x60C74[41] = 0x08031A12`。

从 Konoha 恢复态输入“移动→对战”后，最初捕获 13 次 opcode；outer state
`0x020311D4` 的 `+0x12:0x20→0x30`、`+0x16:40→41`、`+0x17:0→39`。继续约 20 次
确认后累计 44 次 opcode，在 `0x08031D5F` 捕获与 ROM 一致的 `00 1B 08 00`；
`+0x12(u16)=0x0100`、`+0x16=41`、`+0x17=39`、`+0x18=1`。battle state 与 A880
仍为零。该脚本以 opcode 00 正常终止且没有 SetBattle，因此 scenario 41 本来就是
story-only，并有意转入故事后的队伍/任务准备 UI。

所以“Continue 后立即下一战”仍被否决，但“该 UI 属于标题图鉴”也被更强的 selector
证据否决。下一步继续在队伍页逐键采样同一 outer state；新的 selector hit（scenario
大于 41）或 `0x08097C78` SetBattle hit 才是第二战入口。升级 checkpoint 判据保持：
`A880=3`、Naruto level 2、分配前 `+BA=1`，并命中
`0x0808E16E→0x08093698`。紧凑证据见
`artifacts/runtime-checkpoints/natural-scenario-41-runtime-evidence.json`。

## scenario 41 终止后的队伍 UI 状态边界

从 terminal 后稳定菜单逐键采样，chapter selector 始终为 2 hits / scenario 41，
opcode count 44；outer state `+0x12=0x0100/+0x16=41/+0x18=1`、battle=0、A880=0
均不变。A 或 Up+A 进入队伍页；Down+A、Down×2+A、Down×3+A、Start、B 会进入不同
子页/黑屏转场，但没有一个产生新 selector 或 SetBattle。变化集中在 UI 子状态：A882/
A884 会从 1 变 2，部分返回路径变 0，A885 可变为 `0xFC`。

这证明 chapter outer state 只保留章节级状态，不能判断队伍配置条件。第二战入口不在
“菜单直接触发 selector”，必须先满足队伍 UI 内部条件。下一探针应记录 A882/A884/
A885 writer 的调用返回，同时保留 selector `0x0808F5CC` 与 SetBattle
`0x08097C78`；不得继续靠固定方向键或截图猜选中项。

一次 `A, B, Down, Down, A` 运行曾在 step 5 短暂读到 battle 41/map 36×44；默认
`PROBE_STOP_ON_MATCH` 随即提前返回，造成“自然入口已闭合”的假阳性。关闭提前停止并
设置 `PROBE_FORCE_SETTLE=1` 后，同一输入最终为 battle=0、map=0、无 units，画面回到
“队伍·装备”character-panel。短暂 checkpoint 零输入显示战场，但第一下 A 立即打开
队伍装备页而非战斗行动菜单，证明前台控制器从未进入可操作战斗。

该错误结论已撤销；负证据保存在
`artifacts/runtime-checkpoints/natural-scenario-41-transient-battle-false-positive.json`。
真正入口的新门槛是：完整 settle 后 battle/map/formation 仍成立，并且下一下 A 打开
可操作战斗菜单，而不是队伍装备 UI。tracked `actionable-move-grid.ss9` 仍是真战斗，
但它处于教程锁定的空目标范围，A/B 只能弹范围提示，不能作为自然通关起点。

因此下一步仍是从 scenario 41 preparation UI 找到真正“开始任务”控制路径，再完成
battle 并捕获战后 EXP/level/训练点；levels 严格保持 `code_verified`。

## “开始任务？”后的稳定 battle 41 边界

preparation menu 的真实映射已确认：A 是队伍/装备，Down,A 是查看战场，
Down,Down,A 是“开始任务？”，Down,Down,Down,A 是保存。选择“开始任务？”
的默认“是”后，battle 41、map 36×44、Naruto (4,10)、Iruka (4,4)
及 battle-map 画面连续六次采样都稳定，严格 arrival 四项全部通过。该状态明显强于
旧 transient 假阳性。

不过当前仍像开场自动交战/表现：Naruto 仍为 level 1 / EXP 100，A880=0，
+BA=0，尚无玩家行动、胜利或升级证据。加载提示 checkpoint 后 start/lineup/
deploy hook 全零，已确认是 checkpoint 位于调用之后，而非 ss9 覆盖新 ROM。
完整边界见 notes/scenario-41-battle-entry-runtime-20260713.md 与
artifacts/runtime-checkpoints/scenario-41-battle-entry-evidence.json。

所以下一步从“寻找开始任务入口”收窄为“找到 battle 41 开场表现到玩家控制或胜利的
交接点”；levels 继续严格保持 `code_verified`。
