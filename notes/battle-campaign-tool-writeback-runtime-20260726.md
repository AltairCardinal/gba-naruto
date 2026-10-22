# 战役装备忍具消耗回写与冷启动恢复（2026-07-26）

## 纠错目标

此前 campaign 已能把每名角色的九个装备槽投影进 `BattleSession`，resolver 也会在忍具
成功提交后清空战斗内对应槽；但是 scene 退出只把成长记录合并回 campaign。结果是同一个
忍具换场或冷启动后重新出现。这个断点说明“存档有装备字段”和“战斗能消费忍具”并不等于
存在完整的跨层所有权链。

本里程碑闭合的是**九个已装备槽**的消费回写，不是完整背包系统。

## 所有权和提交边界

```text
battle_campaign_state（长期装备所有者）
        │ scene policy 投影
        ▼
BattleSession（单场可变装备槽）
        │ resolver 成功后把对应槽写 0
        ▼
battle_scene_controller（按原角色 ID 导出）
        │ scene 退出时一次提交
        ▼
battle_campaign_scene_progression
        │ 成长 + 九格装备原子合并
        ▼
battle_campaign_sram（双槽写入并读回验证）
```

- campaign 是已装备忍具身份的长期所有者；
- session 只拥有本场可变副本，动作失败或取消不会消耗；
- controller 以 `original_character_id` 绑定玩家单位，召唤、分身和敌方不能覆盖队伍档案；
- scene progression 同时提交成长与九格装备，任一角色、技能状态或忍具 ID 非法时整次
  合并零写；
- 未部署的队伍成员保留入场前九格装备，不会因本场没有对应单位而被清空；
- scene 退出后由唯一 SRAM adapter 保存；renderer、Lua 和截图没有写 campaign 的权限。

当前提交边界是“离开 battle scene”。已经成功消耗的忍具即使随后退出结果/训练页面，也会
随本场成长一起保存；战斗中途关闭进程不会产生一次未验证的独立装备写入。

## TDD 证据

RED：

1. `test_battle_scene_results` 首先因 controller 不存在
   `equipped_tools_roster()`、scene progression 不存在 `equipped_tools()` 而编译失败，
   guard 为
   `build/resource-guard/butano-campaign-tool-writeback-cpp-red-20260726-02.json`；
2. 加入未部署队员样本后，Sasuke 的首槽 93 被错误清空，失败证据为
   `build/resource-guard/butano-campaign-tool-preserve-cpp-red-20260726-01.json`；
3. 加入非法忍具 94 的原子性样本后，领域层尚无 `invalid_tool` 拒绝，失败证据为
   `build/resource-guard/butano-campaign-invalid-tool-cpp-red-20260726-01.json`；
4. 冷启动脚本契约先因缺少可配置的预期忍具槽和 audit 字段失败。

GREEN：

- `test_battle_campaign` 验证非法忍具 ID 拒绝且 campaign 逐字节不变；
- `test_battle_campaign_save` 验证消费后的零槽可编码、解码；
- `test_battle_campaign_scene_policy` 保持 campaign 到 loader 的入场投影；
- `test_battle_scene_results` 从真实 battle 41 controller 使用忍具 37，验证
  `67/11/37 → 67/11/0`，同时保留未部署队员装备并提交成长；
- `tests.test_butano_battle_campaign_runtime_script` 验证保存路线和零输入冷启动脚本契约；
- devkitARM 零缓存构建通过：
  `build/resource-guard/butano-campaign-tool-writeback-arm-clean-build-20260726-02.json`；
- 全量宿主 84/84 通过：
  `build/resource-guard/butano-campaign-tool-writeback-full-host-20260726-03.json`；
- campaign/共享路线/单一领域门禁/研究文档五组 Python 73/73 通过：
  `build/resource-guard/butano-campaign-tool-writeback-python-20260726-03.json`。

## 两进程运行时证据

保存进程使用隔离目录
`artifacts/butano-campaign-tool-writeback-runtime-20260726-01/`。状态驱动脚本从正式动作
目录选择忍具 37，等待 type-2 对象完成生命周期，再继续动作 5、结果、升级和 action 8
修炼，最后离开 scene：

- frame 610，battle 41，round 2，phase 16；
- 总经验 175，Naruto `LV2 / EXP25 / TP0 / action8 LV1`；
- campaign load generation 0 / default 1；
- save generation 1 / slot 1 / read-back verified 1；
- Naruto 九格前三项由 `67/11/37` 变为 `67/11/0`；
- campaign/controller/player error 均为 0。

完全关闭保存进程后，第二个 mGBA 进程使用相同隔离 ROM/SAV、零输入启动，证据目录为
`artifacts/butano-campaign-tool-writeback-load-20260726-01/`。frame 1 直接观察：

- load generation 1 / slot 1 / default 0；
- 本进程 save generation 0 / verified 0；
- Naruto 仍为 `LV2 / EXP25 / TP0 / action8 LV1`；
- 九格前三项仍为 `67/11/0`，error 0。

两个进程均经 `tools/run_guarded.py`、同一 heavy lock 和 success marker 执行，未出现 mGBA
crash。运行设置 `mute=1`，不验收音频听感。

## 哈希与数据安全

- ROM SHA-256：
  `b46467be9755c487b05f05378c1e254192d319a1146563248ba76a8c793e3c01`
- 两次 mGBA 运行所绑定的 ELF SHA-256：
  `9ae62e886be7383dc64e2c3502eacaa9989d4a5f606f76f3f53bf8238f0a5529`
- 头文件自包含修复后的最终清洁重链接 ELF SHA-256：
  `f2a9fa7b116ebf465dcec05bb3bac27568f06d56a717bea6c0a5d468f1df3f30`
- 最终 map 中 campaign/battle 遥测符号仍分别为 `0x02005a8c` / `0x0201f540`；
  清洁重链接后的 ROM 与运行验收 ROM 哈希完全相同；
- 隔离 SAV SHA-256：
  `2e5843e3fa3e26a97bb2df3c51c27cae5e6d1266dd1f16df6bbdb3e05d4aa68a`
- `rom/base.sav` 与 `butano-sequel/butano-sequel.sav` 均保持：
  `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`

## 当前边界

- 已闭合的是每角色九个**已装备忍具 ID**的战斗消费与保存；0 表示该装备槽已消耗；
- 尚无章节背包数量、同 ID 堆叠、战后补给、商店、拾取或战前装备 UI；
- 没有定义“从背包扣数量再自动补入装备槽”的规则，因此不能把九格回写称为完整库存；
- 未证明原作是否在撤退、失败或强制中断时采用相同提交时点；
- type-2 原版逐帧 hold、音效，type-1 起爆符专属动画和非静音音频仍未闭合；
- 完整章节入口、Arena 结算与全技能专属表现仍未完成，完整战斗 Goal 保持 active。
