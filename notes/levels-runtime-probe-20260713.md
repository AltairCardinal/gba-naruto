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
`A880` 变化。继续逐键探索纠正了上一版判断：相似的“队伍·装备/四项菜单”最终会
进入标题存档读取页，属于标题人物图鉴/队伍展示上下文，并不是下一任务准备流程。
Right 只移动到空卡位，A 对鸣人打开人物信息/术/装备、对空位无效，Start 短暂黑屏后
回原页；B 后继续操作会回标题存档页。所有相关 `/tmp` ss9 均不得固化成战斗 checkpoint。

因此“Continue 后立即下一战”和“该队伍页可开始下一任务”均被否决。下一步必须从
真实木叶恢复态 hook chapter selector 与 outer-state 写入，用 state variables 区分
标题人物图鉴与任务控制器，再寻找第二战入口，不能再用相似截图和盲按推断。升级
checkpoint 判据保持：`A880=3`、Naruto level 2、分配前 `+BA=1`，并命中
`0x0808E16E→0x08093698`。
